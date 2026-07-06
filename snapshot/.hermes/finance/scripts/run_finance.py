#!/usr/bin/env python3
"""
Finance crew — faze 1 (verejna data, reporty). vm12890.

Stejny vzor jako ostatni crews (hermes -p <profil> chat -Q ...), ale s
TIEROVANYM routingem:
  - rutinni role (formatovani reportu, jednoduche vypocty) -> LEVNY tier
  - analyza/usudek + finalni kontrola -> DRAHY tier (architekt/konzultant/tester)
  - escalation: levny -> levny druhy provider -> drahy (opravar kdyz se zasekne)

FAZE 1 = jen verejna data + reporty. Firemni/osobni finance NE (ty na Macu).
Burza (faze 2) je oddeleny projekt, tady NENI.

Spusteni:
  scripts/run_finance.py --mode report   --task "Q2 P&L shrnuti z verejnych dat firmy X"
  scripts/run_finance.py --mode cashflow --task "cashflow forecast 6M dle verejnych vykazu"
  scripts/run_finance.py --mode anomaly  --task "najdi anomalie v serii ..."
  scripts/run_finance.py --mode full     --task "..."
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

BASE = Path.home() / ".hermes" / "finance"
PROMPTS = BASE / "prompts"
RUNS = BASE / "runs"

CHEAP_GPT, CHEAP_CLAUDE = "worker-gpt-mini", "worker-sonnet"
EXP_GPT, EXP_CLAUDE = "deepresearch-gpt55", "deepresearch-claude-opus"

# escalation: levny -> levny druhy provider -> drahy same-provider; drahy -> drahy cross
FALLBACK = {
    CHEAP_GPT:    [CHEAP_CLAUDE, EXP_GPT],
    CHEAP_CLAUDE: [CHEAP_GPT, EXP_CLAUDE],
    EXP_GPT:      [EXP_CLAUDE],
    EXP_CLAUDE:   [EXP_GPT],
}

# role -> (prompt, primarni profil, toolsety, je_finalni_kvalita)
ROLE = {
    "analyst":       ("analyst.md",       EXP_CLAUDE,  "file,web", True),   # usudek/architekt
    "cashflow":      ("cashflow.md",      EXP_CLAUDE,  "file,web", True),
    "anomaly":       ("anomaly.md",       CHEAP_CLAUDE, "file,web", False),  # rutinni scan -> levny
    "report_writer": ("report_writer.md", CHEAP_GPT,   "file",     False),  # formatovani -> levny
    "final_review":  ("final_review.md",  EXP_CLAUDE,  "file",     True),    # finalni tester
}
MODES = {
    "report":   ["analyst", "report_writer", "final_review"],
    "cashflow": ["cashflow", "report_writer"],
    "anomaly":  ["anomaly", "final_review"],
    "full":     ["analyst", "cashflow", "anomaly", "report_writer", "final_review"],
}
ROLE_TIMEOUT = 300
BAD = ["api call failed", "broken pipe", "cannot write", "nemohu zapisovat"]

CAVEMAN = ("\n# Interni efektivita — caveman-lite\nInterne hutne: bez vaty, kratke husty bullets/tabulky. "
           "Zachovej vsechna cisla, zdroje, nejistotu. Validni Markdown.\n")
FINAL = ("\n# Finalni vystup — plna kvalita\nUceleny Markdown s tabulkami a jasnym zaverem. "
         "Nevymyslej cisla — rozlis 'z verejneho zdroje' / 'odhad' / 'chybi'. Vzdy uved zdroj/URL.\n")


def hermes_cmd(profile, role, prompt, toolsets):
    return ["hermes", "-p", profile, "chat", "-Q", "--source", f"finance-{role}",
            "--max-turns", "12", "-t", toolsets, "-q", prompt]


def bad(t):
    low = (t or "").lower()
    return (not low.strip()) or any(m in low for m in BAD)


def run_role(role, prompt):
    _, primary, toolsets, _ = ROLE[role]
    attempts = [primary] + FALLBACK.get(primary, [])
    errors, res = [], {}
    for idx, profile in enumerate(attempts):
        started = time.time()
        try:
            proc = subprocess.run(hermes_cmd(profile, role, prompt, toolsets),
                                  text=True, capture_output=True, timeout=ROLE_TIMEOUT)
            res = {"returncode": proc.returncode, "stdout": proc.stdout.strip(),
                   "stderr": proc.stderr.strip(), "elapsed_seconds": round(time.time()-started, 2)}
        except FileNotFoundError:
            return {"returncode": 127, "stdout": f"[DRY-RUN: hermes not found] {role}",
                    "stderr": "hermes not found", "profile": profile, "escalated": False}
        except subprocess.TimeoutExpired as e:
            res = {"returncode": 124, "stdout": (e.stdout or ""), "stderr": f"timeout {ROLE_TIMEOUT}s",
                   "elapsed_seconds": ROLE_TIMEOUT}
        res.update({"profile": profile, "escalated": idx > 0})
        if res.get("returncode") == 0 and not bad(res.get("stdout", "")):
            if errors:
                res["previous_errors"] = errors
            return res
        errors.append({"profile": profile, "rc": res.get("returncode"),
                       "stderr": (res.get("stderr", "") or "")[-600:]})
    res["previous_errors"] = errors
    return res


def build_prompt(role, task, prior, compression):
    _, _, _, is_final = ROLE[role]
    base = (PROMPTS / ROLE[role][0]).read_text(encoding="utf-8").replace("{{TASK}}", task)
    ctx = ""
    if prior:
        ctx = "\n\n# Kontext od predchozich roli\n" + "\n\n".join(
            f"## {r}\n{(t or '')[:6000]}" for r, t in prior.items())
    contract = FINAL if is_final else (CAVEMAN if compression == "caveman" else "")
    return base + contract + ctx


def telegram(msg):
    try:
        subprocess.run(["/usr/bin/env", "PYTHONPATH=/home/david_master/.agent2telegram-src",
                        "/usr/bin/python3", "-m", "agent2telegram", "notify", msg],
                       capture_output=True, text=True, timeout=30)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="Finance crew (faze 1)")
    ap.add_argument("--mode", choices=MODES.keys(), required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--internal-compression", choices=["caveman", "off"], default="caveman")
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / f"{args.mode}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    prior, meta, issues = {}, {}, []
    for role in MODES[args.mode]:
        prompt = build_prompt(role, args.task, prior, args.internal_compression)
        print(f"-> {role} ({ROLE[role][1]})")
        res = run_role(role, prompt)
        out = res.get("stdout") or f"# ERROR rc={res.get('returncode')}\n\n{res.get('stderr','')}"
        (run_dir / f"{role}.md").write_text(out + "\n", encoding="utf-8")
        prior[role] = out
        meta[role] = {"profile": res.get("profile"), "rc": res.get("returncode"), "escalated": res.get("escalated")}
        if res.get("returncode") != 0:
            issues.append(f"{role} rc={res.get('returncode')}")
        elif res.get("escalated"):
            issues.append(f"{role} eskalovan na {res.get('profile')}")

    (run_dir / "summary.json").write_text(json.dumps(
        {"crew": "finance", "mode": args.mode, "task": args.task, "roles": meta,
         "issues": issues, "dir": str(run_dir)}, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "OK" if not issues else "s vyhradami: " + "; ".join(issues)
    if not args.no_telegram:
        telegram(f"[finance:{args.mode}] {status}\nukol: {args.task}\n{run_dir}")
    print(f"{status} -> {run_dir}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())

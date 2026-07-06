#!/usr/bin/env python3
"""
Legal-lite crew — JEN sablony + obecna compliance + NDA z neutralnich vstupu. vm12890.

TVRDE PRAVIDLO: nezpracovava duverna/klientska data. Ta patri na Mac + lokalni model.
Tady jen verejne sablony, obecne pravni dotazy, generovani NDA z neutralnich zadani.

Tierovany routing (levny na rutinu, drahy na usudek + finalni kontrolu),
escalation levny -> levny druhy provider -> drahy.

Spusteni:
  scripts/run_legal.py --mode review     --task "posud rizika v teto VEREJNE sablone smlouvy: ..."
  scripts/run_legal.py --mode compliance --task "gap analyza vuci GDPR pro obecny scenar ..."
  scripts/run_legal.py --mode draft      --task "vygeneruj NDA z techto NEUTRALNICH vstupu ..."
  scripts/run_legal.py --mode compare    --task "porovnej verzi A vs B teto sablony ..."
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

BASE = Path.home() / ".hermes" / "legal-lite"
PROMPTS = BASE / "prompts"
RUNS = BASE / "runs"

CHEAP_GPT, CHEAP_CLAUDE = "worker-gpt-mini", "worker-sonnet"
EXP_GPT, EXP_CLAUDE = "deepresearch-gpt55", "deepresearch-claude-opus"
FALLBACK = {
    CHEAP_GPT: [CHEAP_CLAUDE, EXP_GPT],
    CHEAP_CLAUDE: [CHEAP_GPT, EXP_CLAUDE],
    EXP_GPT: [EXP_CLAUDE],
    EXP_CLAUDE: [EXP_GPT],
}
# role -> (prompt, profil, toolsety, finalni_kvalita)
ROLE = {
    "clause_analyzer":   ("clause_analyzer.md",   EXP_CLAUDE,   "file,web", True),   # usudek
    "risk_assessor":     ("risk_assessor.md",     EXP_CLAUDE,   "file,web", True),   # usudek
    "compliance_checker":("compliance_checker.md", CHEAP_CLAUDE, "file,web", False),  # checklist
    "nda_drafter":       ("nda_drafter.md",       CHEAP_GPT,    "file",     False),  # drafting
    "comparator":        ("comparator.md",        CHEAP_GPT,    "file",     False),  # diff
    "final_review":      ("final_review.md",      EXP_CLAUDE,   "file",     True),   # tester
}
MODES = {
    "review":     ["clause_analyzer", "risk_assessor", "final_review"],
    "compliance": ["compliance_checker", "final_review"],
    "draft":      ["nda_drafter", "final_review"],
    "compare":    ["comparator"],
    "full":       ["clause_analyzer", "risk_assessor", "compliance_checker", "final_review"],
}
ROLE_TIMEOUT = 300
BAD = ["api call failed", "broken pipe", "cannot write", "nemohu zapisovat"]

DISCLAIMER = ("\n# TVRDE PRAVIDLO\nZpracovavej JEN verejne sablony / obecne dotazy / neutralni vstupy. "
              "Pokud zadani obsahuje konkretni duverna klientska/firemni data, ODMITNI je zpracovat a "
              "napis, ze patri na Mac + lokalni model. Vystup je NAVRH, ne pravni rada — vyzaduje lidskou revizi.\n")
CAVEMAN = ("\n# Interni efektivita — caveman-lite\nHutne, bez vaty, strukturovane. Zachovej presne citace klauzuli.\n")
FINAL = ("\n# Finalni vystup — plna kvalita\nUceleny Markdown, konkretni, s odkazy na klauzule. "
         "Vzdy dolozek: 'Navrh, ne pravni rada; vyzaduje lidskou revizi.'\n")


def hermes_cmd(profile, role, prompt, toolsets):
    return ["hermes", "-p", profile, "chat", "-Q", "--source", f"legal-{role}",
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
    return base + DISCLAIMER + contract + ctx


def telegram(msg):
    try:
        subprocess.run(["/usr/bin/env", "PYTHONPATH=/home/david_master/.agent2telegram-src",
                        "/usr/bin/python3", "-m", "agent2telegram", "notify", msg],
                       capture_output=True, text=True, timeout=30)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="Legal-lite crew")
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
        {"crew": "legal-lite", "mode": args.mode, "task": args.task, "roles": meta,
         "issues": issues, "dir": str(run_dir)}, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "OK" if not issues else "s vyhradami: " + "; ".join(issues)
    if not args.no_telegram:
        telegram(f"[legal:{args.mode}] {status}\nukol: {args.task}\n{run_dir}")
    print(f"{status} -> {run_dir}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Marketing crew — rozsirene mody (strategy / campaign / content / analytics / social).

Samostatny runner: NEMENI funkcni auditni run_marketing_audit.py (--mode audit
zustava tam, zpetna kompatibilita). Stejna volaci konvence jako audit runner:
`hermes -p <profil> chat -Q ...`, artefakty do runs/, souhrn do Telegramu.

Spusteni:
  scripts/run_marketing_ext.py --mode strategy  --task "positioning pro produkt X"
  scripts/run_marketing_ext.py --mode campaign  --task "Q3 kampan, kanaly web+email"
  scripts/run_marketing_ext.py --mode content   --task "5 postu + vizualy k launchi"
  scripts/run_marketing_ext.py --mode analytics --task "tydenni reach report"   # cron
  scripts/run_marketing_ext.py --mode social    --task "denni monitoring zminky"  # cron
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

BASE = Path.home() / ".hermes" / "marketing-crew"
PROMPTS = BASE / "prompts"
RUNS = BASE / "runs"
WORKFLOW_VERSION = "ext-0.1.0"

# role -> (prompt soubor, primarni profil, toolsety, je_finalni_vystup)
# TIER: strategie/kampan/analytika (usudek) drahy; copy/content/social (rutina) levny
ROLE = {
    "strategist":       ("strategist.md",       "deepresearch-claude-opus", "file,web",           True),   # architekt
    "campaign_planner": ("campaign_planner.md", "deepresearch-claude-opus", "file,web",           True),   # architekt
    "copywriter":       ("copywriter.md",       "worker-gpt-mini",          "file",               False),  # rutina -> levny
    "content_maker":    ("content_maker.md",    "worker-gpt-mini",          "file,web,image_gen", True),   # rutina -> levny
    "reach_analyst":    ("reach_analyst.md",    "deepresearch-claude-opus", "file,web",           True),   # analytik
    "social_analyst":   ("social_analyst.md",   "worker-gpt-mini",          "file,web,browser",   True),   # monitoring -> levny
}
# escalation: levny -> levny druhy provider -> drahy (opravar kdyz se zasekne)
FALLBACK = {
    "worker-gpt-mini":          ["worker-sonnet", "deepresearch-gpt55"],
    "worker-sonnet":            ["worker-gpt-mini", "deepresearch-claude-opus"],
    "deepresearch-gpt55":       ["deepresearch-claude-opus"],
    "deepresearch-claude-opus": ["deepresearch-gpt55"],
}
# poradi = poradi provedeni; predchozi vystupy se predaji dalsi roli jako kontext
MODES = {
    "strategy":  ["strategist"],
    "campaign":  ["campaign_planner", "copywriter"],
    "content":   ["copywriter", "content_maker"],
    "analytics": ["reach_analyst"],
    "social":    ["social_analyst"],
}
ROLE_TIMEOUT = 300
BAD_MARKERS = ["api call failed", "broken pipe", "cannot write", "can't write", "nemohu zapisovat"]

CAVEMAN_INTERNAL = (
    "\n# Interni efektivita — caveman-lite\n"
    "Interne pis hutne: zadna vata, kratke husty bullets/tabulky, jedna informace jednou. "
    "Zachovej vsechnu substanci: presna cisla, URL, citace, prioritky, nejistotu. Vystup zustava validni Markdown.\n"
)
FINAL_QUALITY = (
    "\n# Finalni vystup — plna kvalita\n"
    "Toto je finalni vystup pro cloveka. Piš uceleny, konkretni Markdown s tabulkami, "
    "prioritami a jasnym akcnim planem. Zadny caveman/terse styl. Nevymyslej cisla — oznac nejistotu.\n"
)


def read_global_lessons(max_chars: int = 5000) -> str:
    p = Path.home() / ".hermes" / "LESSONS.md"
    if not p.exists():
        return ""
    txt = p.read_text(encoding="utf-8", errors="replace")
    if len(txt) <= max_chars:
        return txt
    return txt[: max_chars // 2] + f"\n\n[...TRUNCATED {len(txt)-max_chars} CHARS; FULL FILE ON DISK...]\n\n" + txt[-max_chars // 2 :]


def hermes_cmd(profile: str, role: str, prompt: str, toolsets: str) -> list[str]:
    return ["hermes", "-p", profile, "chat", "-Q", "--source", f"marketing-ext-{role}",
            "--max-turns", "10", "-t", toolsets, "-q", prompt]


def output_is_bad(text: str) -> bool:
    low = (text or "").lower()
    return (not low.strip()) or any(m in low for m in BAD_MARKERS)


def run_role(role: str, prompt: str) -> dict:
    _, primary, toolsets, _ = ROLE[role]
    attempts = [primary] + [p for p in FALLBACK.get(primary, []) if p != primary]
    errors, res = [], {}
    for idx, profile in enumerate(attempts):
        started = time.time()
        try:
            proc = subprocess.run(hermes_cmd(profile, role, prompt, toolsets),
                                  text=True, capture_output=True, timeout=ROLE_TIMEOUT)
            res = {"returncode": proc.returncode, "stdout": proc.stdout.strip(),
                   "stderr": proc.stderr.strip(), "elapsed_seconds": round(time.time() - started, 2)}
        except FileNotFoundError:
            return {"returncode": 127, "stdout": f"[DRY-RUN: hermes not found] {role}",
                    "stderr": "hermes not found", "profile": profile, "elapsed_seconds": 0}
        except subprocess.TimeoutExpired as e:
            res = {"returncode": 124, "stdout": (e.stdout or ""), "stderr": f"timeout {ROLE_TIMEOUT}s",
                   "elapsed_seconds": ROLE_TIMEOUT}
        res.update({"profile": profile, "fallback_used": idx > 0})
        if res.get("returncode") == 0 and not output_is_bad(res.get("stdout", "")):
            if errors:
                res["previous_errors"] = errors
            return res
        errors.append({"profile": profile, "returncode": res.get("returncode"),
                       "stderr": (res.get("stderr", "") or "")[-800:]})
    res["previous_errors"] = errors
    return res


def build_prompt(role: str, task: str, prior: dict, compression: str) -> str:
    _, _, _, is_final = ROLE[role]
    base = (PROMPTS / ROLE[role][0]).read_text(encoding="utf-8").replace("{{TASK}}", task)
    ctx = ""
    if prior:
        ctx = "\n\n# Kontext od predchozich roli\n" + "\n\n".join(
            f"## {r}\n{(t or '')[:6000]}" for r, t in prior.items())
    contract = FINAL_QUALITY if is_final else (CAVEMAN_INTERNAL if compression == "caveman" else "")
    lessons = "\n\n# Global server self-learning / Lessons\n" + read_global_lessons()
    return base + lessons + contract + ctx


def telegram(msg: str) -> None:
    try:
        subprocess.run(["/usr/bin/env", "PYTHONPATH=/home/david_master/.agent2telegram-src",
                        "/usr/bin/python3", "-m", "agent2telegram", "notify", msg],
                       capture_output=True, text=True, timeout=30)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Marketing crew - rozsirene mody")
    ap.add_argument("--mode", choices=MODES.keys(), required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--internal-compression", choices=["caveman", "off"], default="caveman")
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / f"ext-{args.mode}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    prior, meta, issues = {}, {}, []
    for role in MODES[args.mode]:
        prompt = build_prompt(role, args.task, prior, args.internal_compression)
        print(f"-> {role}")
        res = run_role(role, prompt)
        out = res.get("stdout") or f"# ERROR\nreturncode={res.get('returncode')}\n\n{res.get('stderr','')}"
        (run_dir / f"{role}.md").write_text(out + "\n", encoding="utf-8")
        prior[role] = out
        meta[role] = {"profile": res.get("profile"), "returncode": res.get("returncode"),
                      "fallback_used": res.get("fallback_used"), "elapsed_seconds": res.get("elapsed_seconds")}
        if res.get("returncode") != 0:
            issues.append(f"{role} rc={res.get('returncode')}")
        elif res.get("fallback_used"):
            issues.append(f"{role} fallback")

    (run_dir / "summary.json").write_text(
        json.dumps({"workflow_version": WORKFLOW_VERSION, "mode": args.mode, "task": args.task,
                    "roles": meta, "issues": issues, "dir": str(run_dir)}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    status = "OK" if not issues else "s vyhradami: " + "; ".join(issues)
    if not args.no_telegram:
        telegram(f"[marketing:{args.mode}] {status}\nukol: {args.task}\n{run_dir}")
    print(f"{status} -> {run_dir}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())

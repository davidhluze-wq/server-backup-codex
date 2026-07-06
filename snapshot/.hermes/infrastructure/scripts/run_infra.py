#!/usr/bin/env python3
"""
Infrastructure crew runner (vm12890).

Stejny vzor jako marketing-crew/scripts/run_marketing_audit.py:
rozhodi ukol na Hermes profily po rolich pres SKUTECNOU CLI konvenci
`hermes -p <profil> chat -Q ...`, ulozi durable artefakty do runs/,
posle souhrn do Telegramu pres `agent2telegram notify`.

Role produkuji PLAN / prikazy / unity (k lidskemu schvaleni), nikoli
autonomni vykon — LLM nema terminal toolset, jen file+web. Nevratne
kroky delas ty dle ~/Hermes/policies/human-in-the-loop.md.

Spusteni:
  scripts/run_infra.py --mode deploy    --task "nasad X jako systemd sluzbu"
  scripts/run_infra.py --mode db        --task "zaloz DB finance + uzivatele"
  scripts/run_infra.py --mode dashboard --task "pridej marketing metriky pod Caddy"
  scripts/run_infra.py --mode full      --task "..."      # deploy+db+dashboard
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PROMPTS = BASE / "prompts"
RUNS = BASE / "runs"

# role -> (prompt soubor, primarni Hermes profil, toolsety)
# TIER: architekturu (deploy/dashboard) drahy tier; rutinni SQL (db) levny tier
ROLE_PROFILE = {
    "deploy":    ("deploy.md",            "deepresearch-claude-opus", "file,web"),  # architekt
    "db":        ("db_steward.md",        "worker-gpt-mini",          "file,web"),  # rutinni SQL -> levny
    "dashboard": ("dashboard_curator.md", "deepresearch-claude-opus", "file,web"),  # architekt
}
# escalation: levny -> levny druhy provider -> drahy (opravar kdyz se zasekne)
FALLBACK_PROFILES = {
    "worker-gpt-mini":          ["worker-sonnet", "deepresearch-gpt55"],
    "worker-sonnet":            ["worker-gpt-mini", "deepresearch-claude-opus"],
    "deepresearch-gpt55":       ["deepresearch-claude-opus"],
    "deepresearch-claude-opus": ["deepresearch-gpt55"],
}
# ktere role bezi v jakem modu (poradi = poradi provedeni)
MODES = {
    "deploy":    ["deploy"],
    "db":        ["db"],
    "dashboard": ["dashboard"],
    "full":      ["deploy", "db", "dashboard"],
}
ROLE_TIMEOUT = 600
BAD_MARKERS = ["api call failed", "broken pipe", "cannot write", "can't write"]


def hermes_cmd(profile: str, role: str, prompt: str, toolsets: str) -> list[str]:
    return ["hermes", "-p", profile, "chat", "-Q", "--source", f"infrastructure-{role}",
            "--max-turns", "10", "-t", toolsets, "-q", prompt]


def output_is_bad(text: str) -> bool:
    low = (text or "").lower()
    return (not low.strip()) or any(m in low for m in BAD_MARKERS)


def run_role(role: str, prompt: str) -> dict:
    _, primary, toolsets = ROLE_PROFILE[role]
    attempts = [primary] + [p for p in FALLBACK_PROFILES.get(primary, []) if p != primary]
    errors = []
    res: dict = {}
    for idx, profile in enumerate(attempts):
        started = time.time()
        try:
            proc = subprocess.run(hermes_cmd(profile, role, prompt, toolsets),
                                  text=True, capture_output=True, timeout=ROLE_TIMEOUT)
            res = {"returncode": proc.returncode, "stdout": proc.stdout.strip(),
                   "stderr": proc.stderr.strip(), "elapsed_seconds": round(time.time() - started, 2)}
        except FileNotFoundError:
            return {"returncode": 127, "stdout": f"[DRY-RUN: hermes CLI not found] {role}: {prompt[:200]}",
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


def load_prompt(fname: str, task: str) -> str:
    return (PROMPTS / fname).read_text(encoding="utf-8").replace("{{TASK}}", task)


def telegram(msg: str) -> None:
    """Souhrn majiteli pres a2t notify (owner bot). Nikdy nespadni kvuli notifikaci."""
    try:
        subprocess.run(["/usr/bin/env", "PYTHONPATH=/home/david_master/.agent2telegram-src",
                        "/usr/bin/python3", "-m", "agent2telegram", "notify", msg],
                       capture_output=True, text=True, timeout=30)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Infrastructure crew runner")
    ap.add_argument("--mode", choices=MODES.keys(), required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / f"{args.mode}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results, issues = {}, []
    for role in MODES[args.mode]:
        fname, _, _ = ROLE_PROFILE[role]
        prompt = load_prompt(fname, args.task)
        print(f"-> {role}")
        res = run_role(role, prompt)
        out = res.get("stdout") or f"# ERROR\nreturncode={res.get('returncode')}\n\n{res.get('stderr','')}"
        (run_dir / f"{role}.md").write_text(out + "\n", encoding="utf-8")
        results[role] = {"profile": res.get("profile"), "returncode": res.get("returncode"),
                         "fallback_used": res.get("fallback_used"), "elapsed_seconds": res.get("elapsed_seconds")}
        if res.get("returncode") != 0:
            issues.append(f"{role} rc={res.get('returncode')}")
        elif res.get("fallback_used"):
            issues.append(f"{role} pouzil fallback profil")

    (run_dir / "summary.json").write_text(
        json.dumps({"mode": args.mode, "task": args.task, "roles": results,
                    "issues": issues, "dir": str(run_dir)}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    status = "OK" if not issues else "s vyhradami: " + "; ".join(issues)
    if not args.no_telegram:
        telegram(f"[infra:{args.mode}] {status}\nukol: {args.task}\n{run_dir}")
    print(f"{status} -> {run_dir}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())

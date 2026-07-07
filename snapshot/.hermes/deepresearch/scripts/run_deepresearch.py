#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import subprocess
import time
from pathlib import Path

BASE = Path.home() / ".hermes" / "deepresearch"
PROMPTS = BASE / "prompts"
CONFIG = BASE / "config"
MODES = CONFIG / "modes"
RUNS = BASE / "runs"
SCRIPTS = BASE / "scripts"
INDEX_JSONL = BASE / "index.jsonl"
INDEX_MD = BASE / "index.md"
WORKFLOW_VERSION = "0.4.0-caveman-internal-efficiency"

ROLE_FILES = {
    "research_a": "researcher-a.md",
    "research_b": "researcher-b.md",
    "arbitration": "arbitrator.md",
    "source_audit": "source-auditor.md",
    "final_report": "final-writer.md",
    "quality_review": "quality-reviewer.md",
}
OUTPUT_FILES = {
    "research_a": "research_a.md",
    "research_b": "research_b.md",
    "arbitration": "arbitration.md",
    "source_url_audit": "source_url_audit.md",
    "source_url_audit_json": "source_url_audit.json",
    "source_audit": "source_audit.md",
    "final_report": "final_report.md",
    "quality_review": "quality_review.md",
    "export_manifest": "export_manifest.json",
}
ROLE_PROFILES = {
    "research_a": os.getenv("HERMES_DR_PROFILE_RESEARCH_A", "deepresearch-gpt55"),
    "research_b": os.getenv("HERMES_DR_PROFILE_RESEARCH_B", "deepresearch-claude-opus"),
    "arbitration": os.getenv("HERMES_DR_PROFILE_ARBITRATOR", "deepresearch-claude-opus"),
    "source_audit": os.getenv("HERMES_DR_PROFILE_SOURCE_AUDITOR", "worker-sonnet"),
    "final_report": os.getenv("HERMES_DR_PROFILE_FINAL_WRITER", "deepresearch-gpt55"),
    "quality_review": os.getenv("HERMES_DR_PROFILE_QUALITY_REVIEWER", "deepresearch-claude-opus"),
}
FALLBACK_PROFILE = os.getenv("HERMES_DEEPRESEARCH_FALLBACK_PROFILE", "deepresearch-gpt55")

INTERNAL_COMPRESSION_ROLES = {"research_a", "research_b", "arbitration", "source_audit"}
FINAL_QUALITY_ROLES = {"final_report", "quality_review"}

def efficiency_contract(role: str, mode: str) -> str:
    if mode == "off":
        return ""
    if role in FINAL_QUALITY_ROLES:
        return """
# Final-output quality contract
Do NOT use caveman/terse style in the final report or quality review. Produce polished, complete, audit-ready Markdown with citation tables, uncertainty labels, source coverage, and reviewer-useful detail. Internal compression is allowed only upstream; final file quality must not degrade.
"""
    if role in INTERNAL_COMPRESSION_ROLES:
        return """
# Internal communication efficiency contract — caveman-lite
Use caveman-lite internally: no filler, no pleasantries, compact evidence bullets/tables, one fact once. Preserve all research substance: exact URLs/DOIs, titles, dates, numbers, quotes, confidence, disagreements, and uncertainty labels. Do not shorten URLs, citations, code, commands, or errors. Output remains valid Markdown for downstream synthesis. Goal: cheaper agent handoff, not lower-quality research.
"""
    return ""


def slugify(text: str, max_len: int = 48) -> str:
    s = text.lower().translate(str.maketrans("áčďéěíňóřšťúůýž", "acdeeinorstuuyz"))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:max_len].strip("-") or "research")


def read_prompt(role: str) -> str:
    return (PROMPTS / ROLE_FILES[role]).read_text(encoding="utf-8")


def read_limited(path: Path, max_chars: int = 18000) -> str:
    txt = path.read_text(encoding="utf-8")
    if len(txt) <= max_chars:
        return txt
    head = max_chars // 2
    tail = max_chars - head
    omitted = len(txt) - max_chars
    return txt[:head] + f"\n\n[...TRUNCATED {omitted} CHARS FOR ORCHESTRATION PROMPT; FULL FILE IS ON DISK...]\n\n" + txt[-tail:]


def read_global_lessons(max_chars: int = 5000) -> str:
    p = Path.home() / ".hermes" / "LESSONS.md"
    if not p.exists():
        return ""
    try:
        return read_limited(p, max_chars=max_chars)
    except Exception:
        return ""

def read_mode_rules(mode: str) -> str:
    if mode == "auto":
        return "# Mode: Auto\n\nZvol vhodný research styl podle zadání. Pokud jde o zdraví/medicínu, použij scientific pravidla; u trhu market; u technologií/software software.\n"
    path = MODES / f"{mode}.md"
    if not path.exists():
        raise FileNotFoundError(f"Unknown mode rules file: {path}")
    return path.read_text(encoding="utf-8")


def hermes_cmd(profile: str, role: str, prompt: str, toolsets: str) -> list[str]:
    return [
        "hermes", "-p", profile, "chat", "-Q", "--source", f"deepresearch-{role}",
        "--max-turns", "30", "-t", toolsets, "-q", prompt,
    ]


def run_one_command(cmd: list[str], timeout: int) -> tuple[int, str, str, float]:
    started = time.time()
    try:
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip(), round(time.time() - started, 2)
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout if isinstance(e.stdout, str) else ""
        stderr = f"TIMEOUT after {timeout}s\n{e.stderr or ''}"
        return 124, stdout.strip(), stderr.strip(), round(time.time() - started, 2)


def run_hermes(role: str, prompt: str, run_dir: Path, timeout: int, toolsets: str) -> dict:
    logs = run_dir / "logs"
    logs.mkdir(exist_ok=True)
    profile = ROLE_PROFILES.get(role, "default")
    cmd = hermes_cmd(profile, role, prompt, toolsets)
    rc, stdout, stderr, elapsed = run_one_command(cmd, timeout)
    used_profile = profile
    fallback_used = False
    if rc != 0 and profile != FALLBACK_PROFILE:
        fallback_used = True
        fallback_note = f"\n\n--- FALLBACK from profile {profile} to {FALLBACK_PROFILE}; original rc={rc}; original stderr tail ---\n{stderr[-1200:]}\n"
        fcmd = hermes_cmd(FALLBACK_PROFILE, role, prompt, toolsets)
        frc, fstdout, fstderr, felapsed = run_one_command(fcmd, timeout)
        rc, stdout, stderr, elapsed = frc, fstdout, fallback_note + fstderr, round(elapsed + felapsed, 2)
        used_profile = FALLBACK_PROFILE
        cmd = fcmd
    (logs / f"{role}.stderr.txt").write_text(stderr, encoding="utf-8")
    (logs / f"{role}.command.json").write_text(json.dumps({
        "cmd": cmd[:-1] + ["<prompt redacted>"],
        "requested_profile": profile,
        "used_profile": used_profile,
        "fallback_used": fallback_used,
        "returncode": rc,
        "elapsed_seconds": elapsed,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"role": role, "returncode": rc, "stdout": stdout, "stderr": stderr, "elapsed_seconds": elapsed, "profile": used_profile, "fallback_used": fallback_used}


def save_role_output(run_dir: Path, role: str, result: dict):
    out = result.get("stdout", "").strip()
    if not out:
        out = f"# {role}\n\nERROR: Agent returned empty output. See logs/{role}.stderr.txt\n"
    if result.get("returncode") != 0:
        out += f"\n\n---\n\n⚠️ Agent return code: {result.get('returncode')}. See logs/{role}.stderr.txt\n"
    (run_dir / OUTPUT_FILES[role]).write_text(out + "\n", encoding="utf-8")


def build_prompt(role: str, run_dir: Path, mode: str, internal_compression: str = "caveman") -> str:
    base = read_prompt(role)
    input_txt = (run_dir / "input.md").read_text(encoding="utf-8")
    mode_rules = read_mode_rules(mode)
    lessons = read_global_lessons()
    parts = [base, "\n# Global server self-learning / Lessons\n", lessons, "\n# Research mode rules\n", mode_rules, "\n# Uživatelské zadání\n", input_txt, efficiency_contract(role, internal_compression)]
    if role in {"arbitration", "source_audit", "final_report", "quality_review"}:
        for dep in ["research_a", "research_b"]:
            p = run_dir / OUTPUT_FILES[dep]
            parts.append(f"\n# Soubor {p.name}\n\n" + read_limited(p))
    if role in {"source_audit", "final_report", "quality_review"}:
        p = run_dir / OUTPUT_FILES["arbitration"]
        parts.append(f"\n# Soubor {p.name}\n\n" + read_limited(p, 12000))
    if role in {"source_audit", "final_report", "quality_review"} and (run_dir / "source_url_audit.md").exists():
        p = run_dir / "source_url_audit.md"
        parts.append(f"\n# Deterministický URL audit {p.name}\n\n" + read_limited(p, 12000))
    if role in {"final_report", "quality_review"}:
        p = run_dir / OUTPUT_FILES["source_audit"]
        parts.append(f"\n# Soubor {p.name}\n\n" + read_limited(p, 12000))
    if role == "quality_review":
        p = run_dir / OUTPUT_FILES["final_report"]
        parts.append(f"\n# Soubor {p.name}\n\n" + read_limited(p, 14000))
    parts.append("\n# Output instruction\nVrať pouze obsah cílového markdown souboru. Žádné úvodní komentáře mimo report. Drž výstup stručný, auditovatelný a s robustními citacemi.\n")
    return "\n".join(parts)


def run_helper(script: str, args: list[str], timeout: int = 180) -> dict:
    cmd = [str(SCRIPTS / script), *args]
    started = time.time()
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(), "elapsed_seconds": round(time.time() - started, 2)}


def make_manifest(run_id: str, topic: str, mode: str, internal_compression: str, status: str, issues: list[str], timings: dict, role_profiles: dict, helpers: dict) -> dict:
    return {
        "run_id": run_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "topic": topic,
        "mode": mode,
        "internal_compression": internal_compression,
        "workflow_version": WORKFLOW_VERSION,
        "orchestration": "python-wrapper/hermes-chat-subprocess+deterministic-source-audit+drive-export",
        "agents": {
            "research_a": role_profiles.get("research_a"),
            "research_b": role_profiles.get("research_b"),
            "arbitrator": role_profiles.get("arbitration"),
            "source_auditor": role_profiles.get("source_audit"),
            "final_writer": role_profiles.get("final_report"),
            "quality_reviewer": role_profiles.get("quality_review"),
        },
        "outputs": OUTPUT_FILES,
        "status": status,
        "known_issues": issues,
        "timings_seconds": timings,
        "helpers": helpers,
    }


def _read_export_links(run_dir: Path) -> dict:
    p = run_dir / "export_manifest.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    links = {}
    for item in data.get("uploads", []):
        name = item.get("name")
        url = item.get("webViewLink")
        if name and url:
            links[name] = url
    return links


def update_indexes(manifest: dict, run_dir: Path) -> None:
    """Append machine index and regenerate human index for Codex/Hermes audit."""
    row = {
        "run_id": manifest["run_id"],
        "created_at": manifest["created_at"],
        "topic": manifest["topic"],
        "mode": manifest.get("mode", "auto"),
        "status": manifest["status"],
        "run_dir": str(run_dir),
        "final_report": str(run_dir / "final_report.md"),
        "quality_review": str(run_dir / "quality_review.md"),
        "pdf": str(run_dir / "final_report.pdf"),
        "drive_links": _read_export_links(run_dir),
        "known_issues": manifest.get("known_issues", []),
    }
    existing = []
    if INDEX_JSONL.exists():
        for line in INDEX_JSONL.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("run_id") != row["run_id"]:
                existing.append(obj)
    existing.append(row)
    INDEX_JSONL.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in existing) + "\n", encoding="utf-8")

    recent = sorted(existing, key=lambda x: x.get("created_at", ""), reverse=True)
    lines = [
        "# Hermes DeepResearch Run Index",
        "",
        f"Updated: `{dt.datetime.now(dt.timezone.utc).isoformat()}`",
        "",
        "| Created | Status | Mode | Run ID | Topic | Final | PDF | Quality |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for x in recent:
        topic = str(x.get("topic", "")).replace("|", "\\|")[:90]
        final = x.get("drive_links", {}).get("final_report.md") or x.get("final_report", "")
        pdf = x.get("drive_links", {}).get("final_report.pdf") or x.get("pdf", "")
        qr = x.get("drive_links", {}).get("quality_review.md") or x.get("quality_review", "")
        final_cell = f"[final]({final})" if final else "—"
        pdf_cell = f"[pdf]({pdf})" if pdf else "—"
        qr_cell = f"[quality]({qr})" if qr else "—"
        lines.append(f"| {x.get('created_at','')[:19]} | {x.get('status','')} | {x.get('mode','auto')} | `{x.get('run_id','')}` | {topic} | {final_cell} | {pdf_cell} | {qr_cell} |")
    INDEX_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Hermes DeepResearch orchestration")
    ap.add_argument("topic", help="Research task/topic")
    ap.add_argument("--slug", default=None)
    ap.add_argument("--timeout", type=int, default=900, help="Timeout per agent in seconds")
    ap.add_argument("--toolsets", default="web", help="Hermes toolsets for worker subprocesses")
    ap.add_argument("--mode", choices=["auto", "scientific", "market", "software"], default="auto", help="Research mode/ruleset to inject into every role")
    ap.add_argument("--no-upload", action="store_true", help="Do not upload final artefacts to Google Drive")
    ap.add_argument("--internal-compression", choices=["caveman", "off"], default="caveman", help="Compress research handoffs with caveman-lite while preserving final report quality")
    args = ap.parse_args()

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"{ts}-{slugify(args.slug or args.topic)}"
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "input.md").write_text(args.topic.strip() + "\n", encoding="utf-8")

    issues: list[str] = []
    timings: dict[str, float] = {}
    used_profiles: dict[str, str] = {}
    helpers: dict[str, dict] = {}

    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        futs = {
            ex.submit(run_hermes, role, build_prompt(role, run_dir, args.mode, args.internal_compression), run_dir, args.timeout, args.toolsets): role
            for role in ["research_a", "research_b"]
        }
        for fut in cf.as_completed(futs):
            role = futs[fut]
            res = fut.result()
            timings[role] = res["elapsed_seconds"]
            used_profiles[role] = res.get("profile")
            if res.get("fallback_used"):
                issues.append(f"{role} used fallback profile {res.get('profile')}")
            if res["returncode"] != 0:
                issues.append(f"{role} return code {res['returncode']}")
            save_role_output(run_dir, role, res)

    for role in ["arbitration"]:
        res = run_hermes(role, build_prompt(role, run_dir, args.mode, args.internal_compression), run_dir, args.timeout, args.toolsets)
        timings[role] = res["elapsed_seconds"]
        used_profiles[role] = res.get("profile")
        if res.get("fallback_used"):
            issues.append(f"{role} used fallback profile {res.get('profile')}")
        if res["returncode"] != 0:
            issues.append(f"{role} return code {res['returncode']}")
        save_role_output(run_dir, role, res)

    try:
        helpers["source_url_audit"] = run_helper("source_url_audit.py", [str(run_dir)], timeout=240)
        if helpers["source_url_audit"]["returncode"] != 0:
            issues.append("source_url_audit helper failed")
    except Exception as e:
        issues.append(f"source_url_audit helper exception: {type(e).__name__}: {e}")

    for role in ["source_audit", "final_report", "quality_review"]:
        res = run_hermes(role, build_prompt(role, run_dir, args.mode, args.internal_compression), run_dir, args.timeout, args.toolsets)
        timings[role] = res["elapsed_seconds"]
        used_profiles[role] = res.get("profile")
        if res.get("fallback_used"):
            issues.append(f"{role} used fallback profile {res.get('profile')}")
        if res["returncode"] != 0:
            issues.append(f"{role} return code {res['returncode']}")
        save_role_output(run_dir, role, res)

    try:
        export_args = [str(run_dir)] + ([] if args.no_upload else ["--upload"])
        helpers["export_final"] = run_helper("export_final.py", export_args, timeout=300)
        if helpers["export_final"]["returncode"] != 0:
            issues.append("export_final helper failed")
    except Exception as e:
        issues.append(f"export_final helper exception: {type(e).__name__}: {e}")

    # Live propojeni s Lana RAG: ingestuj tento beh do znalostni baze (best-effort, nikdy nezhodi run).
    try:
        haw = Path.home() / "humanagentwiki"
        venv_py = haw / ".venv" / "bin" / "python"
        ingest = Path.home() / "lana-research" / "scripts" / "ingest_deepresearch.py"
        env = os.environ.copy()
        envf = haw / ".env"
        if envf.exists():
            for ln in envf.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("#") and "=" in ln:
                    k, _, v = ln.partition("=")
                    env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        if venv_py.exists() and ingest.exists() and env.get("DATABASE_URL"):
            proc = subprocess.run([str(venv_py), str(ingest), str(run_dir)], text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, env=env)
            helpers["lana_ingest"] = {"returncode": proc.returncode,
                                      "stdout": proc.stdout.strip()[-300:], "stderr": proc.stderr.strip()[-300:]}
            if proc.returncode != 0:
                issues.append("lana_ingest failed")
    except Exception as e:
        issues.append(f"lana_ingest exception: {type(e).__name__}: {e}")

    status = "success" if not [i for i in issues if "fallback" not in i] else "partial"
    manifest = make_manifest(run_id, args.topic, args.mode, args.internal_compression, status, issues, timings, used_profiles, helpers)
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    update_indexes(manifest, run_dir)
    print(str(run_dir))
    print(f"status={status}")
    if issues:
        print("issues=" + "; ".join(issues))
    return 0 if status == "success" else 1

if __name__ == "__main__":
    raise SystemExit(main())

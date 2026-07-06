#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

BASE = Path.home() / ".hermes" / "marketing-crew"
PROMPTS = BASE / "prompts"
CONFIG = BASE / "config"
RUNS = BASE / "runs"
SCRIPTS = BASE / "scripts"
INDEX_JSONL = BASE / "index.jsonl"
INDEX_MD = BASE / "index.md"
WORKFLOW_VERSION = "0.3.0-caveman-internal-efficiency"

ROLE_FILES = {
    "website_audit": "website-auditor.md",
    "seo_content": "seo-content.md",
    "competitor_market": "competitor-market.md",
    "messaging_conversion": "messaging-conversion.md",
    "strategy_synthesizer": "strategy-synthesizer.md",
    "quality_review": "quality-reviewer.md",
}
OUTPUT_FILES = {
    "website_probe": "website_probe.md",
    "website_probe_json": "website_probe.json",
    "website_audit": "website_audit.md",
    "seo_content": "seo_content.md",
    "competitor_market": "competitor_market.md",
    "messaging_conversion": "messaging_conversion.md",
    "strategy_synthesizer": "audit_report.md",
    "quality_review": "quality_review.md",
    "export_manifest": "export_manifest.json",
    "client_report": "client_report.md",
    "client_report_html": "client_report.html",
    "client_report_pdf": "client_report.pdf",
}
ROLE_PROFILES = {
    "website_audit": "deepresearch-claude-opus",       # usudek
    "seo_content": "worker-gpt-mini",                  # rutinni sekce -> levny
    "competitor_market": "deepresearch-claude-opus",   # usudek
    "messaging_conversion": "worker-gpt-mini",         # rutinni sekce -> levny
    "strategy_synthesizer": "deepresearch-claude-opus",# architekt
    "quality_review": "deepresearch-claude-opus",      # finalni tester
}
# escalation: levny -> levny druhy provider -> drahy
FALLBACK_PROFILES = {
    "worker-gpt-mini": ["worker-sonnet", "deepresearch-gpt55"],
    "worker-sonnet": ["worker-gpt-mini", "deepresearch-claude-opus"],
    "deepresearch-gpt55": ["deepresearch-claude-opus"],
    "deepresearch-claude-opus": ["deepresearch-gpt55"],
}
BAD_OUTPUT_MARKERS = [
    "api call failed",
    "broken pipe",
    "nemám nástroj pro zápis",
    "nemohu zapisovat do soubor",
    "can't write",
    "cannot write",
]
ROLE_TIMEOUT_CAPS = {
    "website_audit": 240,
    "seo_content": 240,
    "competitor_market": 300,
    "messaging_conversion": 240,
    "strategy_synthesizer": 300,
    "quality_review": 240,
}

INTERNAL_COMPRESSION_ROLES = {"website_audit", "seo_content", "competitor_market", "messaging_conversion"}
FINAL_QUALITY_ROLES = {"strategy_synthesizer", "quality_review"}

def efficiency_contract(role: str, mode: str) -> str:
    if mode == "off":
        return ""
    if role in FINAL_QUALITY_ROLES:
        return """
# Final-output quality contract
Do NOT use caveman/terse style in the client-facing final report or quality review. Produce polished, complete Markdown with tables, priorities, citations/evidence, and clear action plan. Internal compression is allowed only upstream; final file quality must not degrade.
"""
    if role in INTERNAL_COMPRESSION_ROLES:
        return """
# Internal communication efficiency contract — caveman-lite
Use caveman-lite internally: no filler, no pleasantries, short dense bullets/tables, one fact once. Preserve all technical substance: exact URLs, numbers, errors, citations, evidence, priorities, and uncertainty labels. Do not shorten code/commands/URLs. Output remains valid Markdown for the orchestrator. Goal: cheaper specialist handoff, not lower-quality analysis.
"""
    return ""


def slugify(s: str) -> str:
    s = re.sub(r"^https?://", "", s.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:70] or "marketing-audit"


def read_limited(path: Path, max_chars: int = 8000) -> str:
    txt = path.read_text(encoding="utf-8", errors="replace")
    if len(txt) <= max_chars:
        return txt
    return txt[: max_chars // 2] + f"\n\n[...TRUNCATED {len(txt)-max_chars} CHARS; FULL FILE ON DISK...]\n\n" + txt[-max_chars // 2 :]


def compact_probe_json(path: Path, max_chars: int = 5000) -> str:
    """Return a small JSON context so subprocess LLM calls do not hang on huge argv/tool contexts."""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return read_limited(path, max_chars=max_chars)
    for page in data.get("pages", []):
        if isinstance(page, dict):
            if len(page.get("text_sample", "")) > 800:
                page["text_sample"] = page["text_sample"][:800] + " [...truncated]"
            for k in ("internal_links_sample", "external_links_sample"):
                if isinstance(page.get(k), list):
                    page[k] = page[k][:12]
    if isinstance(data.get("link_checks"), list):
        data["link_checks"] = data["link_checks"][:12]
    txt = json.dumps(data, ensure_ascii=False, indent=2)
    if len(txt) > max_chars:
        txt = txt[:max_chars] + "\n[...compact probe truncated...]"
    return txt


def output_is_bad(text: str) -> bool:
    low = (text or "").lower()
    if not low.strip():
        return True
    return any(m in low for m in BAD_OUTPUT_MARKERS)


def effective_timeout(role: str, requested: int) -> int:
    return min(max(60, requested), ROLE_TIMEOUT_CAPS.get(role, 240))


def run_cmd(cmd: list[str], timeout: int) -> dict:
    started = time.time()
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(), "elapsed_seconds": round(time.time() - started, 2)}


def hermes_cmd(profile: str, role: str, prompt: str, toolsets: str) -> list[str]:
    return ["hermes", "-p", profile, "chat", "-Q", "--source", f"marketing-crew-{role}", "--max-turns", "10", "-t", toolsets, "-q", prompt]


def run_hermes(role: str, prompt: str, timeout: int, toolsets: str) -> dict:
    primary = ROLE_PROFILES[role]
    attempts = [primary] + [p for p in FALLBACK_PROFILES.get(primary, []) if p != primary]
    role_timeout = effective_timeout(role, timeout)
    errors = []
    for idx, profile in enumerate(attempts):
        try:
            res = run_cmd(hermes_cmd(profile, role, prompt, toolsets), role_timeout)
        except subprocess.TimeoutExpired as e:
            res = {"cmd": hermes_cmd(profile, role, "<prompt omitted>", toolsets), "returncode": 124, "stdout": e.stdout or "", "stderr": f"TimeoutExpired after {role_timeout}s", "elapsed_seconds": role_timeout}
        res.update({"profile": profile, "fallback_used": idx > 0, "attempt": idx + 1})
        if res.get("returncode") == 0 and not output_is_bad(res.get("stdout", "")):
            if errors:
                res["previous_errors"] = errors
            return res
        errors.append({"profile": profile, "returncode": res.get("returncode"), "stderr": res.get("stderr", "")[-1000:], "stdout_preview": (res.get("stdout") or "")[:500]})
    res["previous_errors"] = errors
    return res


def save_output(run_dir: Path, role: str, res: dict) -> None:
    out = res.get("stdout") or ""
    if not out:
        out = f"# ERROR: no output\n\nReturn code: {res.get('returncode')}\n\nSTDERR:\n```\n{res.get('stderr','')}\n```\n"
    (run_dir / OUTPUT_FILES[role]).write_text(out + "\n", encoding="utf-8")


def build_prompt(role: str, run_dir: Path, internal_compression: str = "caveman") -> str:
    base = (PROMPTS / ROLE_FILES[role]).read_text(encoding="utf-8")
    rules = (CONFIG / "audit-rules.md").read_text(encoding="utf-8")
    input_txt = (run_dir / "input.md").read_text(encoding="utf-8")
    io_contract = """
# Output contract
Return ONLY the final Markdown content for your assigned role. Do not call file tools. Do not say you cannot write files; the orchestrator captures your stdout and saves it to the correct file. Be concise, evidence-based, and finish in one response.
"""
    parts = [base, "\n# Audit rules\n", rules, "\n# User input\n", input_txt, efficiency_contract(role, internal_compression), io_contract]
    md_probe = run_dir / OUTPUT_FILES["website_probe"]
    if md_probe.exists():
        parts += [f"\n# {md_probe.name}\n", read_limited(md_probe, max_chars=6000)]
    json_probe = run_dir / OUTPUT_FILES["website_probe_json"]
    if json_probe.exists():
        parts += [f"\n# {json_probe.name} (compact)\n", compact_probe_json(json_probe)]
    if role in {"strategy_synthesizer", "quality_review"}:
        for dep in ["website_audit", "seo_content", "competitor_market", "messaging_conversion"]:
            p = run_dir / OUTPUT_FILES[dep]
            if p.exists():
                parts += [f"\n# {p.name}\n", read_limited(p)]
    if role == "quality_review":
        p = run_dir / "audit_report.md"
        if p.exists():
            parts += ["\n# audit_report.md\n", read_limited(p)]
    return "\n".join(parts)


def file_has_valid_content(path: Path) -> bool:
    if not path.exists():
        return False
    txt = path.read_text(encoding="utf-8", errors="replace")
    return len(txt.strip()) > 500 and not output_is_bad(txt)


def deterministic_autofinalize(run_dir: Path, reason: str) -> list[str]:
    """Create usable report/review from completed artifacts when LLM manager stalls.

    This prevents the workflow from requiring David to manually synthesize a PDF.
    """
    created = []
    input_txt = read_limited(run_dir / "input.md", max_chars=3000) if (run_dir / "input.md").exists() else ""
    probe = read_limited(run_dir / "website_probe.md", max_chars=6000) if (run_dir / "website_probe.md").exists() else ""
    sections = []
    for name in ["website_audit.md", "seo_content.md", "competitor_market.md", "messaging_conversion.md"]:
        p = run_dir / name
        if file_has_valid_content(p):
            sections.append(f"\n## Specialistický vstup: {name}\n\n" + read_limited(p, max_chars=9000))
    report = run_dir / "audit_report.md"
    if not file_has_valid_content(report):
        report.write_text(
            "# Marketingový audit — automaticky dokončený report\n\n"
            "Status: automatická finalizace po selhání/stallu manager agenta.\n\n"
            f"Důvod: {reason}\n\n"
            "## Vstup\n\n" + input_txt + "\n\n"
            "## Deterministický website probe\n\n" + probe + "\n\n"
            "## Konsolidované nálezy\n\n"
            "Níže jsou zachované výstupy dokončených specialistů. Pokud některý specialista selhal, není zde zahrnut jako důkaz.\n"
            + "\n".join(sections)
            + "\n\n## Doporučený plán nápravy\n\n"
            "### Krátkodobě\n- Opravit technické/SEO chyby označené ve website probe a website audit.\n- Doplnit jasné CTA, kontaktní cestu a měřitelné konverzní prvky.\n\n"
            "### Střednědobě\n- Rozšířit landing pages a obsah podle nejbližších relevantních konkurenčních témat.\n- Doplnit reference, FAQ, lokální SEO a strukturovaná data.\n\n"
            "### Dlouhodobě\n- Pravidelně opakovat audit, sledovat konkurenci, měřit konverze a iterovat nabídku podle dat.\n",
            encoding="utf-8",
        )
        created.append("audit_report.md")
    review = run_dir / "quality_review.md"
    if not file_has_valid_content(review):
        review.write_text(
            "# Quality review — automatická finalizace\n\n"
            "Semafor: 🟡\n\n"
            f"Report byl automaticky dokončen fallbackem, protože: {reason}\n\n"
            "## Limity\n- Některý specialista nebo manager agent mohl selhat/timeoutovat.\n"
            "- Report používá jen existující artefakty na disku a deterministic website probe.\n"
            "- Browser proklikávání, formuláře a autentizované části nejsou ověřené, pokud to výslovně neuvádí report.\n\n"
            "## Kontrola\n- PDF/export lze vytvořit bez ruční syntézy.\n- Evidence pochází ze souborů v run adresáři.\n",
            encoding="utf-8",
        )
        created.append("quality_review.md")
    return created


def export_links(run_dir: Path) -> dict:
    p = run_dir / "export_manifest.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    links = {}
    for item in data.get("uploads", []):
        if item.get("name") and item.get("webViewLink"):
            links[item["name"]] = item["webViewLink"]
    return links


def first_link_matching(links: dict, *needles: str) -> str:
    for name, link in reversed(list(links.items())):
        lname = name.lower()
        if all(n in lname for n in needles):
            return link
    return ""


def update_index(row: dict) -> None:
    rows = []
    if INDEX_JSONL.exists():
        for line in INDEX_JSONL.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("run_id") != row["run_id"]:
                rows.append(obj)
    rows.append(row)
    rows = sorted(rows, key=lambda x: x.get("created_at", ""))
    INDEX_JSONL.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
    lines = ["# Hermes Marketing Crew Run Index", "", f"Updated: `{dt.datetime.now(dt.timezone.utc).isoformat()}`", "", "| Created | Status | Run ID | URL | Region | Report | PDF | Quality |", "|---|---|---|---|---|---|---|---|"]
    for x in reversed(rows):
        links = x.get("drive_links", {})
        report = links.get("audit_report.md") or first_link_matching(links, "klientsky", ".md") or x.get("audit_report", "")
        pdf = links.get("audit_report.pdf") or first_link_matching(links, "klientsky", ".pdf") or x.get("pdf", "")
        qr = links.get("quality_review.md") or x.get("quality_review", "")
        rc = f"[report]({report})" if report else "—"
        pc = f"[pdf]({pdf})" if pdf else "—"
        qc = f"[quality]({qr})" if qr else "—"
        lines.append(f"| {x.get('created_at','')[:19]} | {x.get('status','')} | `{x.get('run_id','')}` | {x.get('url','')} | {x.get('region','')} | {rc} | {pc} | {qc} |")
    INDEX_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Hermes Marketing Crew website audit")
    ap.add_argument("--url", required=True)
    ap.add_argument("--region", default="Czech Republic")
    ap.add_argument("--business", default="")
    ap.add_argument("--customers", default="")
    ap.add_argument("--competitors", default="")
    ap.add_argument("--focus", default="full website marketing audit")
    ap.add_argument("--language", default="cs")
    ap.add_argument("--slug", default=None)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--toolsets", default="web")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--internal-compression", choices=["caveman", "off"], default="caveman", help="Compress specialist handoffs with caveman-lite while preserving final report quality")
    args = ap.parse_args()

    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + (args.slug or slugify(urllib.parse.urlparse(args.url).netloc or args.url))
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input.md").write_text(f"# Marketing audit input\n\nURL: {args.url}\nRegion: {args.region}\nBusiness/product: {args.business}\nCustomers: {args.customers}\nKnown competitors: {args.competitors}\nFocus: {args.focus}\nLanguage: {args.language}\n", encoding="utf-8")

    issues = []
    timings = {}
    profiles = {}
    helpers = {}

    probe = run_cmd([str(SCRIPTS / "website_probe.py"), args.url, str(run_dir)], timeout=120)
    helpers["website_probe"] = probe
    if probe["returncode"] != 0:
        issues.append(f"website_probe failed: {probe.get('stderr') or probe.get('stdout')}")

    specialist_roles = ["website_audit", "seo_content", "competitor_market", "messaging_conversion"]
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(run_hermes, r, build_prompt(r, run_dir, args.internal_compression), args.timeout, args.toolsets): r for r in specialist_roles}
        for fut in cf.as_completed(futs):
            role = futs[fut]
            res = fut.result()
            timings[role] = res.get("elapsed_seconds")
            profiles[role] = res.get("profile")
            if res.get("fallback_used"):
                issues.append(f"{role} used fallback profile")
            if res.get("returncode") != 0 or output_is_bad(res.get("stdout", "")):
                issues.append(f"{role} failed or produced invalid output; profile={res.get('profile')} code={res.get('returncode')}")
            save_output(run_dir, role, res)

    for role in ["strategy_synthesizer", "quality_review"]:
        res = run_hermes(role, build_prompt(role, run_dir, args.internal_compression), args.timeout, args.toolsets)
        timings[role] = res.get("elapsed_seconds")
        profiles[role] = res.get("profile")
        if res.get("fallback_used"):
            issues.append(f"{role} used fallback profile")
        if res.get("returncode") != 0 or output_is_bad(res.get("stdout", "")):
            issues.append(f"{role} failed or produced invalid output; profile={res.get('profile')} code={res.get('returncode')}")
        save_output(run_dir, role, res)

    auto_finalized = deterministic_autofinalize(run_dir, "; ".join(issues) or "all agents finished but report/review was missing or invalid")
    if auto_finalized:
        issues.append("automatic deterministic finalization created: " + ", ".join(auto_finalized))

    client_prefix = args.slug or slugify(urllib.parse.urlparse(args.url).netloc or args.url)
    export_cmd = [str(SCRIPTS / "export_report.py"), str(run_dir), "--client-prefix", client_prefix]
    if args.no_upload:
        export_cmd.append("--no-upload")
    export = run_cmd(export_cmd, timeout=180)
    helpers["export_report"] = export
    if export["returncode"] != 0:
        issues.append(f"export_report failed: {export.get('stderr') or export.get('stdout')}")

    status = "success" if not [x for x in issues if "fallback" not in x] else "partial"
    manifest = {
        "run_id": run_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "workflow_version": WORKFLOW_VERSION,
        "internal_compression": args.internal_compression,
        "url": args.url,
        "region": args.region,
        "business": args.business,
        "status": status,
        "agents": profiles,
        "outputs": OUTPUT_FILES,
        "known_issues": issues,
        "timings_seconds": timings,
        "helpers": helpers,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    row = {"run_id": run_id, "created_at": manifest["created_at"], "url": args.url, "region": args.region, "business": args.business, "status": status, "run_dir": str(run_dir), "audit_report": str(run_dir / "audit_report.md"), "quality_review": str(run_dir / "quality_review.md"), "pdf": str(run_dir / "audit_report.pdf") if (run_dir / "audit_report.pdf").exists() else "", "drive_links": export_links(run_dir), "known_issues": issues}
    update_index(row)
    print(str(run_dir))
    print(f"status={status}")
    if issues:
        print("issues=" + json.dumps(issues, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
import datetime as dt
from pathlib import Path

BASE = Path.home() / ".hermes" / "deepresearch"
RUNS = BASE / "runs"
INDEX_JSONL = BASE / "index.jsonl"
INDEX_MD = BASE / "index.md"


def read_export_links(run_dir: Path) -> dict:
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


def build_row(run_dir: Path, manifest: dict) -> dict:
    pdf_path = run_dir / "final_report.pdf"
    return {
        "run_id": manifest.get("run_id", run_dir.name),
        "created_at": manifest.get("created_at", ""),
        "topic": manifest.get("topic", ""),
        "mode": manifest.get("mode", "legacy"),
        "status": manifest.get("status", "unknown"),
        "run_dir": str(run_dir),
        "final_report": str(run_dir / "final_report.md"),
        "quality_review": str(run_dir / "quality_review.md"),
        "pdf": str(pdf_path) if pdf_path.exists() else "",
        "drive_links": read_export_links(run_dir),
        "known_issues": manifest.get("known_issues", []),
    }


def main() -> int:
    rows = []
    for mf in sorted(RUNS.glob("*/run_manifest.json")):
        try:
            manifest = json.loads(mf.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append(build_row(mf.parent, manifest))
    rows = sorted(rows, key=lambda x: x.get("created_at", ""))
    INDEX_JSONL.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + ("\n" if rows else ""), encoding="utf-8")
    recent = list(reversed(rows))
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
        lines.append(f"| {x.get('created_at','')[:19]} | {x.get('status','')} | {x.get('mode','legacy')} | `{x.get('run_id','')}` | {topic} | {final_cell} | {pdf_cell} | {qr_cell} |")
    INDEX_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"indexed_runs={len(rows)}")
    print(INDEX_JSONL)
    print(INDEX_MD)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

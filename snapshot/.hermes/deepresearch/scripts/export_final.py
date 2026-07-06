#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
from pathlib import Path

SAFE_DRIVE_FOLDER_ID = os.environ.get("HERMES_DEEPRESEARCH_DRIVE_FOLDER_ID", "1DELdcngk0lUfjiLuxFXOimB4xB8_2wql")
GAPI = Path.home() / ".hermes/skills/productivity/google-workspace/scripts/google_api.py"
PY = Path.home() / ".hermes/hermes-agent/venv/bin/python"


def md_to_plain(md: str) -> str:
    txt = re.sub(r"```.*?```", "", md, flags=re.S)
    txt = re.sub(r"`([^`]*)`", r"\1", txt)
    txt = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", txt)
    txt = re.sub(r"[*_#>]+", "", txt)
    return txt


def md_to_html(md: str) -> str:
    try:
        import markdown
        body = markdown.markdown(md, extensions=["tables", "fenced_code"])
    except Exception:
        body = "<pre>" + html.escape(md) + "</pre>"
    return """<!doctype html>
<html><head><meta charset='utf-8'>
<style>
body{font-family:Arial,sans-serif;max-width:920px;margin:40px auto;line-height:1.55;color:#111}
h1,h2,h3{color:#0f172a} code,pre{background:#f1f5f9;padding:2px 4px} table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:6px;vertical-align:top}
</style></head><body>
""" + body + "\n</body></html>\n"


def esc_pdf_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap_lines(text: str, width: int = 92) -> list[str]:
    import textwrap
    out: list[str] = []
    for para in text.splitlines():
        if not para.strip():
            out.append("")
        else:
            out.extend(textwrap.wrap(para, width=width, replace_whitespace=False) or [""])
    return out


def write_simple_pdf(text: str, path: Path) -> None:
    lines = wrap_lines(md_to_plain(text), 92)
    pages = [lines[i:i+48] for i in range(0, len(lines), 48)] or [[""]]
    objects: list[bytes] = []
    # 1 catalog, 2 pages, 3 font, then page/content pairs
    kids = []
    for idx, page_lines in enumerate(pages):
        page_obj = 4 + idx*2
        content_obj = page_obj + 1
        kids.append(f"{page_obj} 0 R")
        stream_lines = ["BT", "/F1 10 Tf", "50 800 Td", "14 TL"]
        for line in page_lines:
            stream_lines.append(f"({esc_pdf_text(line[:160])}) Tj")
            stream_lines.append("T*")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1", errors="replace")
        page = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj} 0 R >>".encode()
        content = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        objects.extend([page, content])
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ] + objects
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode())
        data.extend(obj)
        data.extend(b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        data.extend(f"{off:010d} 00000 n \n".encode())
    data.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(data)


def upload(path: Path, parent: str) -> dict:
    if not GAPI.exists() or not PY.exists():
        return {"status": "skipped", "reason": "google_api.py or Hermes venv Python not found", "path": str(path)}
    cmd = [str(PY), str(GAPI), "drive", "upload", str(path), "--parent", parent]
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if proc.returncode != 0:
        return {"status": "error", "path": str(path), "stderr": proc.stderr[-1000:], "stdout": proc.stdout[-1000:]}
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"status": "uploaded_unknown", "path": str(path), "stdout": proc.stdout[:1000]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--drive-folder-id", default=SAFE_DRIVE_FOLDER_ID)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    md_path = run_dir / "final_report.md"
    md = md_path.read_text(encoding="utf-8")
    html_path = run_dir / "final_report.html"
    pdf_path = run_dir / "final_report.pdf"
    html_path.write_text(md_to_html(md), encoding="utf-8")
    write_simple_pdf(md, pdf_path)
    result = {"html": str(html_path), "pdf": str(pdf_path), "uploads": []}
    if args.upload:
        for p in [md_path, html_path, pdf_path, run_dir / "quality_review.md", run_dir / "run_manifest.json"]:
            if p.exists():
                result["uploads"].append(upload(p, args.drive_folder_id))
    (run_dir / "export_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

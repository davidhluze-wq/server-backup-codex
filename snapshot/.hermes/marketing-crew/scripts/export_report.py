#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import subprocess
from urllib.parse import urlparse
from pathlib import Path
from shutil import copyfile

SAFE_DRIVE_FOLDER_ID = os.environ.get("HERMES_SAFE_DRIVE_FOLDER_ID", "1DELdcngk0lUfjiLuxFXOimB4xB8_2wql")
GWS = Path.home() / ".hermes/skills/productivity/google-workspace/scripts/google_api.py"
HERMES_PYTHON = Path(os.environ.get("HERMES_PYTHON", str(Path.home() / ".hermes/hermes-agent/venv/bin/python")))


def md_to_html(md: str) -> str:
    try:
        import markdown
        body = markdown.markdown(md, extensions=["tables", "fenced_code", "toc"])
    except Exception:
        esc = html.escape(md)
        esc = re.sub(r"^# (.*)$", r"<h1>\1</h1>", esc, flags=re.M)
        esc = re.sub(r"^## (.*)$", r"<h2>\1</h2>", esc, flags=re.M)
        esc = "<pre>" + esc + "</pre>"
        body = esc
    return """<!doctype html><html><head><meta charset='utf-8'><style>
body{font-family:Arial,sans-serif;max-width:980px;margin:40px auto;line-height:1.55;color:#17202a}
h1,h2,h3{color:#102a43} table{border-collapse:collapse;width:100%;margin:1em 0;font-size:14px}
th,td{border:1px solid #d9e2ec;padding:7px;vertical-align:top} th{background:#f0f4f8}
code,pre{background:#f7f7f7;padding:2px 4px} pre{padding:12px;overflow:auto}
</style></head><body>""" + body + "</body></html>"


def simple_pdf(text: str, out: Path) -> None:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    lines = []
    for raw in text.splitlines():
        raw = re.sub(r"[#*_`|\[\]]", "", raw).strip()
        if not raw:
            lines.append("")
        else:
            while len(raw) > 95:
                lines.append(raw[:95])
                raw = raw[95:]
            lines.append(raw)
    pages = [lines[i:i+42] for i in range(0, len(lines), 42)] or [[]]
    objs = []
    def add(obj: str) -> int:
        objs.append(obj); return len(objs)
    font_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    for page in pages:
        y = 800
        content = ["BT", "/F1 10 Tf", "50 800 Td"]
        first = True
        for line in page:
            if not first:
                content.append("0 -16 Td")
            content.append(f"({esc(line)}) Tj")
            first = False
            y -= 16
        content.append("ET")
        stream = "\n".join(content)
        content_id = add(f"<< /Length {len(stream.encode('latin-1','replace'))} >>\nstream\n{stream}\nendstream")
        page_id = add(f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>")
        page_ids.append(page_id)
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    pages_id = add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")
    for pid in page_ids:
        objs[pid-1] = objs[pid-1].replace("/Parent 0 0 R", f"/Parent {pages_id} 0 R")
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for i, obj in enumerate(objs, 1):
        offsets.append(sum(len(c) for c in chunks))
        chunks.append(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1", "replace"))
    xref = sum(len(c) for c in chunks)
    chunks.append(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        chunks.append(f"{off:010d} 00000 n \n".encode())
    chunks.append(f"trailer << /Size {len(objs)+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    out.write_bytes(b"".join(chunks))


def google_api(args: list[str], timeout: int = 120) -> dict:
    if not GWS.exists():
        return {"error": f"google_api.py not found: {GWS}"}
    python = str(HERMES_PYTHON if HERMES_PYTHON.exists() else sys.executable)
    cmd = [python, str(GWS), *args]
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode != 0:
        return {"error": proc.stderr.strip() or proc.stdout.strip(), "cmd": " ".join(cmd)}
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"raw": proc.stdout.strip()}


def drive_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def first_drive_match(data: object) -> dict | None:
    if isinstance(data, dict):
        for key in ("files", "items", "results"):
            value = data.get(key)
            if isinstance(value, list) and value:
                return value[0]
        if data.get("id"):
            return data
    if isinstance(data, list) and data:
        first = data[0]
        return first if isinstance(first, dict) else None
    return None


def find_folder(name: str, parent_id: str) -> dict | None:
    query = (
        f"name = '{drive_quote(name)}' and "
        "mimeType = 'application/vnd.google-apps.folder' and "
        f"'{drive_quote(parent_id)}' in parents and trashed = false"
    )
    return first_drive_match(google_api(["drive", "search", query, "--raw-query", "--max", "10"]))


def find_or_create_folder(name: str, parent_id: str) -> dict:
    found = find_folder(name, parent_id)
    if found:
        found["name"] = found.get("name") or name
        found["reused"] = True
        return found
    created = google_api(["drive", "create-folder", name, "--parent", parent_id])
    created["name"] = created.get("name") or name
    created["reused"] = False
    return created


def upload_to_folder(path: Path, folder_id: str) -> dict:
    data = google_api(["drive", "upload", str(path), "--name", path.name, "--parent", folder_id])
    data["name"] = data.get("name") or path.name
    return data


def client_slug(run_dir: Path) -> str:
    manifest = run_dir / "run_manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            url = str(data.get("url") or "").strip()
            host = urlparse(url).netloc or urlparse("https://" + url).netloc
            if host:
                return re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")
        except Exception:
            pass
    return re.sub(r"[^a-z0-9]+", "-", run_dir.name.lower()).strip("-") or "klient"


def project_folder_name(run_dir: Path) -> str:
    manifest = run_dir / "run_manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            run_id = str(data.get("run_id") or "").strip()
            if run_id:
                return re.sub(r"[^a-zA-Z0-9._ -]+", "-", run_id).strip("- ")
        except Exception:
            pass
    return run_dir.name


def write_drive_links(run_dir: Path, drive: dict, uploads: list[dict]) -> None:
    lines = ["# Google Drive odkazy", ""]
    project = drive.get("project_folder") or {}
    client = drive.get("client_folder") or {}
    if client.get("webViewLink"):
        lines.append(f"- Klientská složka: {client['webViewLink']}")
    if project.get("webViewLink"):
        lines.append(f"- Složka projektu: {project['webViewLink']}")
    if uploads:
        lines.extend(["", "## Finální výstupy"])
        for item in uploads:
            name = item.get("name", "soubor")
            link = item.get("webViewLink") or item.get("error", "")
            lines.append(f"- {name}: {link}")
    (run_dir / "drive_links.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--client-prefix", default="", help="When set, also create <prefix>-klientsky-audit.md/html/pdf from client_report.*")
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    report = run_dir / "audit_report.md"
    md = report.read_text(encoding="utf-8")
    html_path = run_dir / "audit_report.html"
    pdf_path = run_dir / "audit_report.pdf"
    html_path.write_text(md_to_html(md), encoding="utf-8")
    simple_pdf(md, pdf_path)

    client_report = run_dir / "client_report.md"
    client_html_path = None
    client_pdf_path = None
    if client_report.exists():
        client_md = client_report.read_text(encoding="utf-8")
        client_html_path = run_dir / "client_report.html"
        client_pdf_path = run_dir / "client_report.pdf"
        client_html_path.write_text(md_to_html(client_md), encoding="utf-8")
        simple_pdf(client_md, client_pdf_path)
        slug = client_slug(run_dir)
        prefixed_md = run_dir / f"{slug}-klientsky-audit.md"
        prefixed_html = run_dir / f"{slug}-klientsky-audit.html"
        prefixed_pdf = run_dir / f"{slug}-klientsky-audit.pdf"
        prefixed_md.write_text(client_md, encoding="utf-8")
        visual_html = run_dir / "client_report_visual.html"
        html_source = visual_html if visual_html.exists() else client_html_path
        prefixed_html.write_text(html_source.read_text(encoding="utf-8"), encoding="utf-8")
        prefixed_pdf.write_bytes(client_pdf_path.read_bytes())
        if args.client_prefix:
            named_client_report = run_dir / f"{args.client_prefix}-klientsky-audit.md"
            named_client_html = run_dir / f"{args.client_prefix}-klientsky-audit.html"
            named_client_pdf = run_dir / f"{args.client_prefix}-klientsky-audit.pdf"
            copyfile(client_report, named_client_report)
            copyfile(client_html_path, named_client_html)
            copyfile(client_pdf_path, named_client_pdf)
    uploads = []
    drive = {}
    if not args.no_upload:
        slug = client_slug(run_dir)
        client_folder = find_or_create_folder(slug, SAFE_DRIVE_FOLDER_ID)
        project_folder = find_or_create_folder(project_folder_name(run_dir), client_folder.get("id", SAFE_DRIVE_FOLDER_ID))
        drive = {
            "root_folder_id": SAFE_DRIVE_FOLDER_ID,
            "client_folder": client_folder,
            "project_folder": project_folder,
        }
        project_folder_id = project_folder.get("id")
        upload_paths = []
        if client_report.exists():
            upload_paths.extend([prefixed_md, prefixed_html, prefixed_pdf])
        else:
            upload_paths.extend([report, html_path, pdf_path])
        for p in upload_paths:
            if p.exists() and project_folder_id:
                uploads.append(upload_to_folder(p, project_folder_id))
        write_drive_links(run_dir, drive, uploads)
    manifest = {"html": str(html_path), "pdf": str(pdf_path), "uploads": uploads, "drive": drive}
    if client_html_path and client_pdf_path:
        manifest["client_html"] = str(client_html_path)
        manifest["client_pdf"] = str(client_pdf_path)
        manifest["client_prefixed"] = {
            "md": str(prefixed_md),
            "html": str(prefixed_html),
            "pdf": str(prefixed_pdf),
        }
        if args.client_prefix:
            manifest["named_client_markdown"] = str(run_dir / f"{args.client_prefix}-klientsky-audit.md")
            manifest["named_client_html"] = str(run_dir / f"{args.client_prefix}-klientsky-audit.html")
            manifest["named_client_pdf"] = str(run_dir / f"{args.client_prefix}-klientsky-audit.pdf")
    (run_dir / "export_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

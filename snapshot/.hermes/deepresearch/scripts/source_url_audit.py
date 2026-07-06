#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import ssl
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://[^\s\])>\"']+")


def extract_urls(paths: list[Path]) -> list[str]:
    seen = set()
    urls = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for raw in URL_RE.findall(text):
            url = raw.rstrip('.,;:)]}')
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def probe_url(url: str, timeout: int = 12) -> dict:
    parsed = urlparse(url)
    result = {
        "url": url,
        "host": parsed.netloc,
        "status": None,
        "content_type": None,
        "title": None,
        "sha256_16": None,
        "bytes_sampled": 0,
        "ok": False,
        "error": None,
    }
    headers = {"User-Agent": "HermesDeepResearchSourceAuditor/0.1"}
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            data = r.read(65536)
            result["status"] = getattr(r, "status", None)
            result["content_type"] = r.headers.get("content-type")
            result["bytes_sampled"] = len(data)
            result["sha256_16"] = hashlib.sha256(data).hexdigest()[:16]
            result["ok"] = 200 <= int(result["status"] or 0) < 400
            text = data.decode("utf-8", errors="ignore")
            m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
            if m:
                title = re.sub(r"\s+", " ", m.group(1)).strip()
                result["title"] = title[:200]
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def write_markdown(results: list[dict], path: Path) -> None:
    ok = sum(1 for r in results if r.get("ok"))
    lines = [
        "# Deterministic Source URL Audit",
        "",
        f"Created: `{dt.datetime.now(dt.timezone.utc).isoformat()}`",
        f"URLs checked: `{len(results)}`; OK: `{ok}`; problem/unknown: `{len(results)-ok}`",
        "",
        "| URL | Status | Type | Title / Error | Hash |",
        "|---|---:|---|---|---|",
    ]
    for r in results:
        title = (r.get("title") or r.get("error") or "").replace("|", "\\|")[:180]
        lines.append(f"| {r['url']} | {r.get('status') or ''} | {r.get('content_type') or ''} | {title} | {r.get('sha256_16') or ''} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--timeout", type=int, default=12)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    inputs = [run_dir / name for name in ["research_a.md", "research_b.md", "arbitration.md", "source_audit.md", "final_report.md"]]
    urls = extract_urls(inputs)
    results = [probe_url(u, timeout=args.timeout) for u in urls]
    (run_dir / "source_url_audit.json").write_text(json.dumps({"urls": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(results, run_dir / "source_url_audit.md")
    print(f"source_url_audit urls={len(results)} ok={sum(1 for r in results if r.get('ok'))}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

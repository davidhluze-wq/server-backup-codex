#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

UA = "HermesMarketingCrew/0.1 (+non-intrusive audit probe)"

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.current_heading = None
        self.h1 = []
        self.h2 = []
        self.links = []
        self.images = []
        self.forms = []
        self.buttons = []
        self.inputs = []
        self.meta = {}
        self.canonical = ""
        self.lang = ""
        self.text_chunks = []
        self._capture_text = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        tag = tag.lower()
        if tag == "html":
            self.lang = a.get("lang", "")
        if tag == "title":
            self._in_title = True
        if tag in {"h1", "h2"}:
            self.current_heading = tag
            self._capture_text = True
        if tag == "a":
            self.links.append({"href": a.get("href", ""), "text": ""})
        if tag == "img":
            self.images.append({"src": a.get("src", ""), "alt": a.get("alt", "")})
        if tag == "form":
            self.forms.append({"action": a.get("action", ""), "method": a.get("method", "get")})
        if tag == "button":
            self.buttons.append({"type": a.get("type", ""), "text": ""})
        if tag == "input":
            self.inputs.append({"type": a.get("type", ""), "name": a.get("name", ""), "placeholder": a.get("placeholder", "")})
        if tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key:
                self.meta[key] = a.get("content", "")
        if tag == "link" and a.get("rel") and "canonical" in " ".join(a.get("rel", "")).lower():
            self.canonical = a.get("href", "")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in {"h1", "h2"}:
            self.current_heading = None
            self._capture_text = False

    def handle_data(self, data):
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self._in_title:
            self.title += text + " "
        if self.current_heading == "h1":
            self.h1.append(text)
        elif self.current_heading == "h2":
            self.h2.append(text)
        if len(self.text_chunks) < 80 and len(text) > 2:
            self.text_chunks.append(text)


def fetch(url: str, timeout: int = 12) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            data = r.read(2_000_000)
            ctype = r.headers.get("content-type", "")
            return {"url": r.geturl(), "status": r.status, "headers": dict(r.headers), "content_type": ctype, "body": data, "error": "", "tls_warning": ""}
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        if isinstance(e, urllib.error.HTTPError):
            try:
                data = e.read(2_000_000)
            except Exception:
                data = b""
            return {"url": e.geturl(), "status": e.code, "headers": dict(e.headers or {}), "content_type": (e.headers or {}).get("content-type", ""), "body": data, "error": err, "tls_warning": ""}
        # For audits, a certificate-chain failure is itself an important finding, but we still
        # retry without verification to inspect the public page content. This is non-intrusive.
        if "CERTIFICATE_VERIFY_FAILED" in err or "self-signed certificate" in err.lower():
            try:
                insecure_ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=timeout, context=insecure_ctx) as r:
                    data = r.read(2_000_000)
                    ctype = r.headers.get("content-type", "")
                    return {"url": r.geturl(), "status": r.status, "headers": dict(r.headers), "content_type": ctype, "body": data, "error": "", "tls_warning": err}
            except Exception as e2:
                return {"url": url, "status": None, "headers": {}, "content_type": "", "body": b"", "error": f"{err}; unverified retry failed: {type(e2).__name__}: {e2}", "tls_warning": err}
        return {"url": url, "status": None, "headers": {}, "content_type": "", "body": b"", "error": err, "tls_warning": ""}


def norm_url(base: str, href: str) -> str:
    if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return ""
    return urllib.parse.urljoin(base, href.split("#", 1)[0])


def same_host(a: str, b: str) -> bool:
    return urllib.parse.urlparse(a).netloc.lower() == urllib.parse.urlparse(b).netloc.lower()


def parse_page(url: str, resp: dict) -> dict:
    body = resp.get("body", b"")
    text = body.decode("utf-8", errors="replace")
    p = PageParser()
    try:
        p.feed(text)
    except Exception:
        pass
    links = []
    for item in p.links:
        u = norm_url(resp.get("url") or url, item.get("href", ""))
        if u:
            links.append(u)
    return {
        "url": resp.get("url") or url,
        "status": resp.get("status"),
        "error": resp.get("error"),
        "tls_warning": resp.get("tls_warning", ""),
        "https_attempt": resp.get("https_attempt", {}),
        "content_type": resp.get("content_type"),
        "title": p.title.strip(),
        "title_length": len(p.title.strip()),
        "meta_description": p.meta.get("description", ""),
        "meta_description_length": len(p.meta.get("description", "")),
        "canonical": p.canonical,
        "lang": p.lang,
        "h1": p.h1,
        "h2": p.h2[:20],
        "og_title": p.meta.get("og:title", ""),
        "og_description": p.meta.get("og:description", ""),
        "links_total": len(links),
        "internal_links_sample": [x for x in links if same_host(url, x)][:40],
        "external_links_sample": [x for x in links if not same_host(url, x)][:30],
        "images_total": len(p.images),
        "images_missing_alt": sum(1 for i in p.images if not i.get("alt")),
        "forms": p.forms,
        "buttons_count": len(p.buttons),
        "inputs": p.inputs[:30],
        "text_sample": " ".join(p.text_chunks[:35])[:3000],
        "sha256_head": hashlib.sha256(body[:200000]).hexdigest() if body else "",
    }


def check_urls(urls: list[str], limit: int = 30) -> list[dict]:
    out = []
    seen = set()
    for u in urls:
        if u in seen or len(out) >= limit:
            continue
        seen.add(u)
        r = fetch(u, timeout=10)
        out.append({"url": u, "status": r.get("status"), "final_url": r.get("url"), "error": r.get("error"), "content_type": r.get("content_type")})
    return out


def robots_and_sitemap(base_url: str) -> dict:
    parsed = urllib.parse.urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    robots = fetch(root + "/robots.txt")
    sitemap = fetch(root + "/sitemap.xml")
    return {
        "robots_txt": {"url": root + "/robots.txt", "status": robots.get("status"), "error": robots.get("error"), "sample": robots.get("body", b"").decode("utf-8", errors="replace")[:2000]},
        "sitemap_xml": {"url": root + "/sitemap.xml", "status": sitemap.get("status"), "error": sitemap.get("error"), "sample": sitemap.get("body", b"").decode("utf-8", errors="replace")[:2000]},
    }


def write_markdown(run_dir: Path, data: dict) -> None:
    home = data["pages"][0] if data.get("pages") else {}
    lines = [
        "# Deterministic Website Probe",
        "",
        f"- URL: {data.get('url')}",
        f"- Final URL: {home.get('url')}",
        f"- Status: {home.get('status')}",
        f"- TLS warning: {home.get('tls_warning') or 'none'}",
        f"- HTTPS attempt issue: {home.get('https_attempt', {}).get('error') or home.get('https_attempt', {}).get('status') or 'none'}",
        f"- Accessed at: {data.get('accessed_at')}",
        "",
        "## Homepage SEO basics",
        f"- Title ({home.get('title_length')} chars): {home.get('title')}",
        f"- Meta description ({home.get('meta_description_length')} chars): {home.get('meta_description')}",
        f"- H1 count: {len(home.get('h1', []))}; H1: {home.get('h1')}",
        f"- H2 sample: {home.get('h2')}",
        f"- Lang: {home.get('lang')}",
        f"- Canonical: {home.get('canonical')}",
        f"- OG title: {home.get('og_title')}",
        f"- OG description: {home.get('og_description')}",
        "",
        "## UX / technical signals",
        f"- Internal links sampled: {len(home.get('internal_links_sample', []))}",
        f"- External links sampled: {len(home.get('external_links_sample', []))}",
        f"- Images total: {home.get('images_total')}",
        f"- Images missing alt: {home.get('images_missing_alt')}",
        f"- Forms: {home.get('forms')}",
        f"- Inputs sample: {home.get('inputs')}",
        "",
        "## robots/sitemap",
        f"- robots.txt status: {data.get('robots_sitemap', {}).get('robots_txt', {}).get('status')}",
        f"- sitemap.xml status: {data.get('robots_sitemap', {}).get('sitemap_xml', {}).get('status')}",
        "",
        "## Link status sample",
        "| URL | Status | Error |",
        "|---|---:|---|",
    ]
    for row in data.get("link_checks", []):
        lines.append(f"| {row.get('url')} | {row.get('status')} | {row.get('error','')} |")
    lines += ["", "## Homepage text sample", "", home.get("text_sample", "")]
    (run_dir / "website_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("run_dir")
    ap.add_argument("--limit-links", type=int, default=30)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    url = args.url if re.match(r"^https?://", args.url) else "https://" + args.url
    resp = fetch(url)
    if urllib.parse.urlparse(url).scheme == "https" and (resp.get("status") is None or int(resp.get("status") or 0) >= 400):
        http_url = "http://" + urllib.parse.urlparse(url).netloc + (urllib.parse.urlparse(url).path or "")
        http_resp = fetch(http_url)
        if http_resp.get("status") and int(http_resp.get("status")) < 400:
            http_resp["https_attempt"] = {k: v for k, v in resp.items() if k != "body"}
            resp = http_resp
    pages = [parse_page(url, resp)]
    link_checks = check_urls(pages[0].get("internal_links_sample", []) + pages[0].get("external_links_sample", []), args.limit_links)
    data = {
        "url": url,
        "accessed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "probe_version": "0.1.0",
        "pages": pages,
        "robots_sitemap": robots_and_sitemap(pages[0].get("url") or url),
        "link_checks": link_checks,
    }
    (run_dir / "website_probe.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(run_dir, data)
    bad = sum(1 for x in link_checks if x.get("error") or (x.get("status") and int(x.get("status")) >= 400))
    print(f"website_probe status={pages[0].get('status')} links={len(link_checks)} bad={bad}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

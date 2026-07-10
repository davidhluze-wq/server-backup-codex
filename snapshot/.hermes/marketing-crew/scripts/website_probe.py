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
from typing import Any

UA = "HermesMarketingCrew/0.2 (+non-intrusive GEO/SEO audit probe)"
AI_CRAWLERS = [
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "PerplexityBot",
    "Google-Extended",
    "Googlebot",
    "Bingbot",
    "Amazonbot",
    "Bytespider",
    "CCBot",
    "Applebot-Extended",
    "FacebookBot",
    "Cohere-ai",
]
CRITICAL_AI_CRAWLERS = {"gptbot", "oai-searchbot", "chatgpt-user", "claudebot", "perplexitybot", "googlebot"}

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.current_heading = None
        self.h1 = []
        self.h2 = []
        self.h3 = []
        self.links = []
        self.images = []
        self.forms = []
        self.buttons = []
        self.inputs = []
        self.meta = {}
        self.canonical = ""
        self.lang = ""
        self.text_chunks = []
        self.all_text_chunks = []
        self.script_srcs = []
        self.inline_script_count = 0
        self.ld_json_raw = []
        self._capture_ld_json = False
        self._ld_buf = []
        self._capture_text = False
        self._skip_text_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        tag = tag.lower()
        if tag == "html":
            self.lang = a.get("lang", "")
        if tag == "title":
            self._in_title = True
        if tag in {"h1", "h2", "h3"}:
            self.current_heading = tag
            self._capture_text = True
        if tag == "a":
            self.links.append({"href": a.get("href", ""), "text": ""})
        if tag == "img":
            self.images.append({"src": a.get("src", ""), "alt": a.get("alt", ""), "width": a.get("width", ""), "height": a.get("height", "")})
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
        if tag == "script":
            if a.get("src"):
                self.script_srcs.append(a.get("src", ""))
            else:
                self.inline_script_count += 1
            if "ld+json" in (a.get("type") or "").lower():
                self._capture_ld_json = True
                self._ld_buf = []
            self._skip_text_depth += 1
        if tag in {"style", "noscript"}:
            self._skip_text_depth += 1

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in {"h1", "h2", "h3"}:
            self.current_heading = None
            self._capture_text = False
        if tag == "script":
            if self._capture_ld_json:
                self.ld_json_raw.append("".join(self._ld_buf).strip())
                self._capture_ld_json = False
                self._ld_buf = []
            self._skip_text_depth = max(0, self._skip_text_depth - 1)
        if tag in {"style", "noscript"}:
            self._skip_text_depth = max(0, self._skip_text_depth - 1)

    def handle_data(self, data):
        if self._capture_ld_json:
            self._ld_buf.append(data)
            return
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self._in_title:
            self.title += text + " "
        if self.current_heading == "h1":
            self.h1.append(text)
        elif self.current_heading == "h2":
            self.h2.append(text)
        elif self.current_heading == "h3":
            self.h3.append(text)
        if self._skip_text_depth:
            return
        if len(self.text_chunks) < 80 and len(text) > 2:
            self.text_chunks.append(text)
        if len(text) > 2:
            self.all_text_chunks.append(text)


def fetch(url: str, timeout: int = 12, extra_headers: dict[str, str] | None = None) -> dict:
    headers = {"User-Agent": UA}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
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


def schema_types(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        t = obj.get("@type")
        if isinstance(t, str):
            found.append(t)
        elif isinstance(t, list):
            found.extend(str(x) for x in t)
        for v in obj.values():
            found.extend(schema_types(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(schema_types(item))
    return found


def parse_json_ld(raw_blocks: list[str]) -> dict:
    blocks = []
    types: list[str] = []
    errors = []
    same_as_count = 0
    has_speakable = False
    for raw in raw_blocks:
        if not raw:
            continue
        try:
            obj = json.loads(raw)
            blocks.append(obj)
            types.extend(schema_types(obj))
            raw_txt = json.dumps(obj, ensure_ascii=False).lower()
            same_as_count += raw_txt.count('"sameas"')
            has_speakable = has_speakable or '"speakable"' in raw_txt
        except Exception as e:
            errors.append(f"{type(e).__name__}: {e}")
    uniq_types = sorted(set(types))
    return {
        "json_ld_blocks": len(blocks),
        "schema_types": uniq_types,
        "json_ld_errors": errors[:5],
        "has_organization_or_localbusiness": any(t in {"Organization", "LocalBusiness"} for t in uniq_types),
        "has_person": "Person" in uniq_types,
        "has_article_or_blogposting": any(t in {"Article", "BlogPosting", "NewsArticle"} for t in uniq_types),
        "has_breadcrumb": "BreadcrumbList" in uniq_types,
        "has_website_searchaction": "WebSite" in uniq_types and "SearchAction" in uniq_types,
        "has_speakable": has_speakable,
        "same_as_mentions": same_as_count,
    }


def score_passage(text: str, heading: str = "") -> dict:
    words = text.split()
    wc = len(words)
    if wc < 25:
        return {"heading": heading, "word_count": wc, "total_score": 0, "label": "Too short", "preview": text[:180]}
    score = 0
    # Answer block quality
    if re.search(r"\b\w+\s+(?:je|jsou|is|are|means?|refers?)\b", text, re.I):
        score += 15
    if heading.endswith("?") or re.match(r"^(co|jak|proč|kdy|kde|what|how|why|when|where)\b", heading or "", re.I):
        score += 10
    first_60 = " ".join(words[:60])
    if re.search(r"\d+%|\b\d+[\s-]?(?:let|dnů|měsíců|years|days|users|customers|zákazníků)\b", first_60, re.I):
        score += 8
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if sentences:
        avg = wc / max(1, len(sentences))
        if 8 <= avg <= 24:
            score += 10
    # Self-containment
    if 134 <= wc <= 167:
        score += 15
    elif 100 <= wc <= 200:
        score += 11
    elif 80 <= wc <= 250:
        score += 7
    pronouns = len(re.findall(r"\b(?:to|tento|tato|tamto|on|ona|oni|it|they|this|that|these|those)\b", text, re.I))
    if pronouns / max(1, wc) < 0.03:
        score += 8
    if len(re.findall(r"\b[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][\wÁ-ž]+", text)) >= 3:
        score += 7
    # Structure/stat density/uniqueness
    if re.search(r"(?:1\.|2\.|- |•|první|druhý|first|second|step|krok)", text, re.I):
        score += 8
    if re.search(r"\d+(?:[,.]\d+)?\s?(?:%|Kč|EUR|USD|let|dnů|x|×)", text, re.I):
        score += 10
    if re.search(r"(?:podle|studie|výzkum|data|case study|příklad|reference|our study|research shows)", text, re.I):
        score += 7
    score = min(score, 100)
    if score >= 80:
        label = "Highly citable"
    elif score >= 65:
        label = "Good citability"
    elif score >= 50:
        label = "Moderate citability"
    elif score >= 35:
        label = "Low citability"
    else:
        label = "Poor citability"
    return {"heading": heading, "word_count": wc, "total_score": score, "label": label, "preview": " ".join(words[:32]) + ("..." if wc > 32 else "")}


def citability_analysis(page: dict) -> dict:
    chunks = []
    headings = page.get("h2", []) + page.get("h3", [])
    for i, chunk in enumerate(page.get("all_text_chunks", [])[:80]):
        if len(chunk.split()) >= 25:
            chunks.append(score_passage(chunk, headings[min(i, len(headings)-1)] if headings else ""))
    chunks = sorted(chunks, key=lambda x: x.get("total_score", 0), reverse=True)
    top = chunks[:5]
    avg = round(sum(x.get("total_score", 0) for x in top) / max(1, len(top)), 1) if top else 0
    return {
        "page_citability_score": avg,
        "citation_ready_count": sum(1 for x in chunks if x.get("total_score", 0) >= 70),
        "top_passages": top,
        "weak_passages_sample": [x for x in chunks if x.get("total_score", 0) < 35][:3],
    }


def parse_robot_groups(txt: str) -> list[dict]:
    groups = []
    current = {"agents": [], "rules": []}
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = [x.strip() for x in line.split(":", 1)]
        key_l = key.lower()
        if key_l == "user-agent":
            if current["rules"]:
                groups.append(current)
                current = {"agents": [], "rules": []}
            current["agents"].append(val.lower())
        elif key_l in {"allow", "disallow", "crawl-delay"}:
            current["rules"].append((key_l, val))
    if current["agents"] or current["rules"]:
        groups.append(current)
    return groups


def ai_crawler_access(robots_sample: str) -> dict:
    groups = parse_robot_groups(robots_sample or "")
    statuses = {}
    issues = []
    for crawler in AI_CRAWLERS:
        cl = crawler.lower()
        relevant = [g for g in groups if cl in g["agents"]] or [g for g in groups if "*" in g["agents"]]
        blocked_root = False
        restricted = False
        crawl_delay = ""
        for g in relevant:
            for rule, val in g["rules"]:
                if rule == "disallow" and val.strip() == "/":
                    blocked_root = True
                elif rule == "disallow" and val.strip():
                    restricted = True
                elif rule == "crawl-delay":
                    crawl_delay = val
        status = "Allowed/unknown"
        if blocked_root:
            status = "Blocked"
            issues.append(f"{crawler} blocked at root")
        elif restricted:
            status = "Restricted"
        statuses[crawler] = {"status": status, "crawl_delay": crawl_delay}
    score = 100
    for crawler, row in statuses.items():
        if row["status"] == "Blocked":
            score -= 15 if crawler.lower() in CRITICAL_AI_CRAWLERS else 5
    if "sitemap:" not in (robots_sample or "").lower():
        score -= 10
        issues.append("robots.txt does not reference sitemap")
    content_signals = []
    for line in (robots_sample or "").splitlines():
        if line.lower().startswith("content-signal:"):
            content_signals.append(line.split(":", 1)[1].strip())
    return {"score": max(0, score), "crawler_statuses": statuses, "issues": issues[:12], "content_signals": content_signals}


def robots_and_sitemap(base_url: str) -> dict:
    parsed = urllib.parse.urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    robots = fetch(root + "/robots.txt")
    sitemap = fetch(root + "/sitemap.xml")
    robots_sample = robots.get("body", b"").decode("utf-8", errors="replace")[:5000]
    return {
        "robots_txt": {"url": root + "/robots.txt", "status": robots.get("status"), "error": robots.get("error"), "sample": robots_sample},
        "sitemap_xml": {"url": root + "/sitemap.xml", "status": sitemap.get("status"), "error": sitemap.get("error"), "sample": sitemap.get("body", b"").decode("utf-8", errors="replace")[:2000]},
        "ai_crawler_access": ai_crawler_access(robots_sample),
    }


def llms_txt_check(url: str) -> dict:
    parsed = urllib.parse.urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    llms = fetch(root + "/llms.txt")
    full = fetch(root + "/llms-full.txt")
    txt = llms.get("body", b"").decode("utf-8", errors="replace") if llms.get("status") == 200 else ""
    lines = txt.strip().splitlines()
    has_title = bool(lines and lines[0].startswith("# "))
    has_description = any(line.startswith("> ") for line in lines)
    section_count = sum(1 for line in lines if line.startswith("## "))
    link_count = len(re.findall(r"- \[.+?\]\(.+?\)", txt))
    valid = has_title and has_description and section_count > 0 and link_count > 0
    if llms.get("status") != 200:
        score = 0
    elif valid and full.get("status") == 200 and link_count >= 10:
        score = 95
    elif valid and link_count >= 5:
        score = 75
    elif valid:
        score = 55
    else:
        score = 30
    issues = []
    if llms.get("status") != 200:
        issues.append("/llms.txt missing or inaccessible")
    else:
        if not has_title: issues.append("missing H1 title")
        if not has_description: issues.append("missing blockquote description")
        if section_count == 0: issues.append("missing sections")
        if link_count == 0: issues.append("missing markdown links")
        if full.get("status") != 200: issues.append("/llms-full.txt not found")
    return {
        "url": root + "/llms.txt",
        "status": llms.get("status"),
        "exists": llms.get("status") == 200,
        "format_valid": valid,
        "score": score,
        "has_title": has_title,
        "has_description": has_description,
        "section_count": section_count,
        "link_count": link_count,
        "llms_full_status": full.get("status"),
        "issues": issues,
        "sample": txt[:1000],
    }


def technical_geo_signals(url: str, resp: dict, page: dict) -> dict:
    headers = {str(k).lower(): str(v) for k, v in (resp.get("headers") or {}).items()}
    body = resp.get("body", b"").decode("utf-8", errors="replace")
    visible_words = len(" ".join(page.get("all_text_chunks", [])).split())
    root_div_only = bool(re.search(r'<div[^>]+id=["\'](?:root|app|__next)["\'][^>]*>\s*</div>', body, re.I))
    framework_markers = [m for m in ["__NEXT_DATA__", "__NUXT__", "data-reactroot", "ng-version", "id=\"app\"", "id=\"root\""] if m.lower() in body.lower()]
    if visible_words < 80 and root_div_only:
        ssr_status = "Critical JS dependency risk"
    elif visible_words < 250:
        ssr_status = "High/medium JS or thin-content risk"
    else:
        ssr_status = "Raw HTML contains substantive content"
    md_resp = fetch(url, timeout=10, extra_headers={"Accept": "text/markdown"})
    link_headers = {k: v for k, v in (resp.get("headers") or {}).items() if str(k).lower() == "link"}
    service_discovery = []
    for val in link_headers.values():
        for rel in ["api-catalog", "describedby", "service-doc", "mcp-server-card"]:
            if rel in str(val):
                service_discovery.append(rel)
    return {
        "security_headers": {
            "strict_transport_security": bool(headers.get("strict-transport-security")),
            "content_security_policy": bool(headers.get("content-security-policy")),
            "x_frame_options": bool(headers.get("x-frame-options")),
            "x_content_type_options": bool(headers.get("x-content-type-options")),
            "referrer_policy": bool(headers.get("referrer-policy")),
            "permissions_policy": bool(headers.get("permissions-policy")),
        },
        "ssr_js_dependency": {"visible_word_count_raw_html": visible_words, "status": ssr_status, "framework_markers": framework_markers[:8], "script_src_count": len(page.get("script_srcs", [])), "inline_script_count": page.get("inline_script_count", 0)},
        "agent_readiness": {"markdown_accept_status": md_resp.get("status"), "markdown_accept_content_type": md_resp.get("content_type"), "serves_markdown_on_accept": "text/markdown" in (md_resp.get("content_type") or "").lower(), "service_discovery_rels": sorted(set(service_discovery))},
    }


def platform_readiness(page: dict, robots: dict, schema: dict, citability: dict, llms: dict) -> dict:
    h_questions = sum(1 for h in (page.get("h2", []) + page.get("h3", [])) if h.strip().endswith("?") or re.match(r"^(co|jak|proč|kdy|kde|what|how|why|when|where)\b", h, re.I))
    has_tables_or_lists_hint = bool(re.search(r"\b(?:tabulka|srovnání|kroky|výhody|nevýhody|1\.|2\.)\b", page.get("text_sample", ""), re.I))
    crawler_status = robots.get("ai_crawler_access", {}).get("crawler_statuses", {})
    def allowed(name: str) -> bool:
        return crawler_status.get(name, {}).get("status") != "Blocked"
    chatgpt = min(100, (25 if allowed("OAI-SearchBot") else 0) + (20 if allowed("ChatGPT-User") else 0) + (25 if schema.get("has_organization_or_localbusiness") else 0) + (20 if schema.get("same_as_mentions") else 0) + min(10, int(citability.get("page_citability_score", 0) / 10)))
    aio = min(100, h_questions * 10 + (20 if has_tables_or_lists_hint else 0) + min(35, int(citability.get("page_citability_score", 0) * 0.35)) + (20 if schema.get("has_article_or_blogposting") or schema.get("has_organization_or_localbusiness") else 0))
    perplexity = min(100, (30 if allowed("PerplexityBot") else 0) + min(30, int(citability.get("page_citability_score", 0) * 0.3)) + (20 if re.search(r"reference|recenze|case study|data|zdroj", page.get("text_sample", ""), re.I) else 0) + (20 if page.get("meta_description") else 0))
    gemini = min(100, (20 if allowed("Googlebot") else 0) + (20 if schema.get("same_as_mentions") else 0) + (20 if page.get("images_total", 0) else 0) + min(40, int(citability.get("page_citability_score", 0) * 0.4)))
    bing = min(100, (20 if allowed("Bingbot") else 0) + (20 if schema.get("has_organization_or_localbusiness") else 0) + (20 if page.get("canonical") else 0) + (20 if llms.get("exists") else 0) + (20 if page.get("meta_description") else 0))
    scores = {"Google AI Overviews": aio, "ChatGPT Web Search": chatgpt, "Perplexity AI": perplexity, "Google Gemini": gemini, "Bing Copilot": bing}
    return {"scores": scores, "average": round(sum(scores.values()) / len(scores), 1), "strongest": max(scores, key=scores.get), "weakest": min(scores, key=scores.get)}


def geo_scorecard(page: dict, robots_sitemap: dict, llms: dict, schema: dict, citability: dict, technical: dict, platform: dict) -> dict:
    cit = float(citability.get("page_citability_score", 0))
    crawler = float(robots_sitemap.get("ai_crawler_access", {}).get("score", 0))
    llms_score = float(llms.get("score", 0))
    ai_visibility = round(cit * 0.35 + crawler * 0.25 + llms_score * 0.10 + 20, 1)  # + baseline for brand unknown; LLM later evaluates brand authority
    schema_score = 0
    schema_score += 20 if schema.get("has_organization_or_localbusiness") else 0
    schema_score += 15 if schema.get("has_article_or_blogposting") else 0
    schema_score += 15 if schema.get("has_person") else 0
    schema_score += min(15, int(schema.get("same_as_mentions", 0) * 5))
    schema_score += 10 if schema.get("has_speakable") else 0
    schema_score += 5 if schema.get("has_breadcrumb") else 0
    schema_score += 5 if schema.get("has_website_searchaction") else 0
    schema_score += 5 if not schema.get("json_ld_errors") else 0
    content_quality = min(100, (30 if page.get("meta_description") else 0) + (20 if page.get("h1") else 0) + (20 if page.get("h2") else 0) + min(30, int(cit / 100 * 30)))
    tech = 50
    ssr_status = technical.get("ssr_js_dependency", {}).get("status", "")
    tech += 25 if "substantive" in ssr_status.lower() else 0
    tech += 10 if robots_sitemap.get("sitemap_xml", {}).get("status") == 200 else 0
    tech += 10 if page.get("canonical") else 0
    tech += 5 if page.get("lang") else 0
    technical_score = min(100, tech)
    platform_score = float(platform.get("average", 0))
    # Brand authority needs live brand-platform research; deterministic probe can only flag schema/entity signals.
    brand_authority_proxy = min(100, schema.get("same_as_mentions", 0) * 20 + (20 if schema.get("has_organization_or_localbusiness") else 0))
    composite = round(ai_visibility * 0.25 + brand_authority_proxy * 0.20 + content_quality * 0.20 + technical_score * 0.15 + schema_score * 0.10 + platform_score * 0.10, 1)
    return {
        "composite_geo_score": composite,
        "category_scores": {
            "ai_citability_visibility": ai_visibility,
            "brand_authority_proxy": brand_authority_proxy,
            "content_quality_proxy": content_quality,
            "technical_foundations": technical_score,
            "structured_data": schema_score,
            "platform_optimization": platform_score,
        },
        "weights": {"ai_citability_visibility": "25%", "brand_authority_proxy": "20%", "content_quality_proxy": "20%", "technical_foundations": "15%", "structured_data": "10%", "platform_optimization": "10%"},
        "note": "Brand authority is a deterministic proxy only; specialist agents should verify Wikipedia/Wikidata/YouTube/Reddit/LinkedIn/industry mentions before making factual claims.",
    }


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
    schema = parse_json_ld(p.ld_json_raw)
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
        "h2": p.h2[:30],
        "h3": p.h3[:30],
        "og_title": p.meta.get("og:title", ""),
        "og_description": p.meta.get("og:description", ""),
        "robots_meta": p.meta.get("robots", ""),
        "links_total": len(links),
        "internal_links_sample": [x for x in links if same_host(url, x)][:50],
        "external_links_sample": [x for x in links if not same_host(url, x)][:40],
        "images_total": len(p.images),
        "images_missing_alt": sum(1 for i in p.images if not i.get("alt")),
        "images_missing_dimensions": sum(1 for i in p.images if not i.get("width") or not i.get("height")),
        "forms": p.forms,
        "buttons_count": len(p.buttons),
        "inputs": p.inputs[:30],
        "script_srcs": p.script_srcs[:40],
        "inline_script_count": p.inline_script_count,
        "text_sample": " ".join(p.text_chunks[:35])[:3000],
        "all_text_chunks": p.all_text_chunks[:120],
        "schema": schema,
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


def write_markdown(run_dir: Path, data: dict) -> None:
    home = data["pages"][0] if data.get("pages") else {}
    geo = data.get("geo", {})
    scorecard = geo.get("scorecard", {})
    ai_access = data.get("robots_sitemap", {}).get("ai_crawler_access", {})
    llms = geo.get("llms_txt", {})
    cit = geo.get("citability", {})
    schema = home.get("schema", {})
    platform = geo.get("platform_readiness", {})
    technical = geo.get("technical_geo", {})
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
        "## GEO / AI Search Scorecard",
        f"- Composite GEO score: {scorecard.get('composite_geo_score')}/100",
        f"- Note: {scorecard.get('note', '')}",
        "",
        "| Category | Score | Weight |",
        "|---|---:|---:|",
    ]
    for k, v in scorecard.get("category_scores", {}).items():
        lines.append(f"| {k} | {v}/100 | {scorecard.get('weights', {}).get(k, '')} |")
    lines += [
        "",
        "## AI Crawler Access",
        f"- Score: {ai_access.get('score')}/100",
        f"- Issues: {ai_access.get('issues') or 'none detected'}",
        f"- Content-Signal directives: {ai_access.get('content_signals') or 'absent'}",
        "",
        "| Crawler | Status | Crawl delay |",
        "|---|---|---|",
    ]
    for crawler, row in ai_access.get("crawler_statuses", {}).items():
        lines.append(f"| {crawler} | {row.get('status')} | {row.get('crawl_delay') or ''} |")
    lines += [
        "",
        "## llms.txt",
        f"- URL: {llms.get('url')}",
        f"- Status: {llms.get('status')}; exists: {llms.get('exists')}; valid format: {llms.get('format_valid')}; score: {llms.get('score')}/100",
        f"- Sections: {llms.get('section_count')}; links: {llms.get('link_count')}; llms-full status: {llms.get('llms_full_status')}",
        f"- Issues: {llms.get('issues') or 'none detected'}",
        "",
        "## AI Citability",
        f"- Page citability score: {cit.get('page_citability_score')}/100",
        f"- Citation-ready passages found: {cit.get('citation_ready_count')}",
        "",
        "| Score | Label | Words | Passage preview |",
        "|---:|---|---:|---|",
    ]
    for p in cit.get("top_passages", [])[:5]:
        preview = str(p.get("preview", "")).replace("|", " ")
        lines.append(f"| {p.get('total_score')} | {p.get('label')} | {p.get('word_count')} | {preview} |")
    lines += [
        "",
        "## Schema / Structured Data for AI Discoverability",
        f"- JSON-LD blocks: {schema.get('json_ld_blocks')}; types: {schema.get('schema_types')}",
        f"- Organization/LocalBusiness: {schema.get('has_organization_or_localbusiness')}; Person: {schema.get('has_person')}; Article/BlogPosting: {schema.get('has_article_or_blogposting')}",
        f"- Breadcrumb: {schema.get('has_breadcrumb')}; WebSite+SearchAction: {schema.get('has_website_searchaction')}; speakable: {schema.get('has_speakable')}; sameAs mentions: {schema.get('same_as_mentions')}",
        f"- JSON-LD errors: {schema.get('json_ld_errors') or 'none detected'}",
        "",
        "## Platform Readiness for AI Search",
        f"- Average: {platform.get('average')}/100; strongest: {platform.get('strongest')}; weakest: {platform.get('weakest')}",
        "",
        "| Platform | Readiness score |",
        "|---|---:|",
    ]
    for name, score in platform.get("scores", {}).items():
        lines.append(f"| {name} | {score}/100 |")
    lines += [
        "",
        "## Technical Agent-Readiness Signals",
        f"- SSR/JS dependency: {technical.get('ssr_js_dependency', {}).get('status')} ({technical.get('ssr_js_dependency', {}).get('visible_word_count_raw_html')} visible raw-HTML words)",
        f"- Framework markers: {technical.get('ssr_js_dependency', {}).get('framework_markers')}",
        f"- Accept: text/markdown served as markdown: {technical.get('agent_readiness', {}).get('serves_markdown_on_accept')} (status {technical.get('agent_readiness', {}).get('markdown_accept_status')}, content-type {technical.get('agent_readiness', {}).get('markdown_accept_content_type')})",
        f"- RFC/service discovery rels: {technical.get('agent_readiness', {}).get('service_discovery_rels') or 'none detected'}",
        "",
        "## Homepage SEO basics",
        f"- Title ({home.get('title_length')} chars): {home.get('title')}",
        f"- Meta description ({home.get('meta_description_length')} chars): {home.get('meta_description')}",
        f"- H1 count: {len(home.get('h1', []))}; H1: {home.get('h1')}",
        f"- H2 sample: {home.get('h2')}",
        f"- H3 sample: {home.get('h3')}",
        f"- Lang: {home.get('lang')}",
        f"- Canonical: {home.get('canonical')}",
        f"- Meta robots: {home.get('robots_meta')}",
        f"- OG title: {home.get('og_title')}",
        f"- OG description: {home.get('og_description')}",
        "",
        "## UX / technical signals",
        f"- Internal links sampled: {len(home.get('internal_links_sample', []))}",
        f"- External links sampled: {len(home.get('external_links_sample', []))}",
        f"- Images total: {home.get('images_total')}",
        f"- Images missing alt: {home.get('images_missing_alt')}",
        f"- Images missing dimensions: {home.get('images_missing_dimensions')}",
        f"- Forms: {home.get('forms')}",
        f"- Inputs sample: {home.get('inputs')}",
        "",
        "## Security headers",
    ]
    for k, v in technical.get("security_headers", {}).items():
        lines.append(f"- {k}: {v}")
    lines += [
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
    home = pages[0]
    link_checks = check_urls(home.get("internal_links_sample", []) + home.get("external_links_sample", []), args.limit_links)
    robots_sitemap = robots_and_sitemap(home.get("url") or url)
    llms = llms_txt_check(home.get("url") or url)
    citability = citability_analysis(home)
    technical = technical_geo_signals(home.get("url") or url, resp, home)
    platform = platform_readiness(home, robots_sitemap, home.get("schema", {}), citability, llms)
    scorecard = geo_scorecard(home, robots_sitemap, llms, home.get("schema", {}), citability, technical, platform)
    data = {
        "url": url,
        "accessed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "probe_version": "0.2.0-geo-ai-search",
        "pages": pages,
        "robots_sitemap": robots_sitemap,
        "link_checks": link_checks,
        "geo": {"llms_txt": llms, "citability": citability, "technical_geo": technical, "platform_readiness": platform, "scorecard": scorecard},
    }
    # Keep JSON evidence useful but bounded: full text chunks are already summarized in markdown.
    for page in data["pages"]:
        page["all_text_chunks"] = page.get("all_text_chunks", [])[:40]
    (run_dir / "website_probe.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(run_dir, data)
    bad = sum(1 for x in link_checks if x.get("error") or (x.get("status") and int(x.get("status")) >= 400))
    print(f"website_probe status={home.get('status')} links={len(link_checks)} bad={bad} geo_score={scorecard.get('composite_geo_score')} citability={citability.get('page_citability_score')} llms={llms.get('status')}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

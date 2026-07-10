#!/usr/bin/env python3
"""
Lana — ZERO-LLM harvester trading literatury (zadne API tokeny).

Stahuje nejnovejsi ("trendy") odbornou literaturu z arXiv q-fin pres verejne API,
deduplikuje proti lana.sources a uklada do RAG (sources + chunks + FTS). Cilem je
postupne vstrebat veskerou dostupnou literaturu k tradingu: strategie, portfolio,
bezpecne provadeni obchodu, risk a financni cile — od prehledu po technicky detail.

Token cost = 0 (jen HTTP + Postgres). Embeddingy (BGE-M3, lokalne, tez bez tokenu)
jsou volitelne pres --embed; bez pgvectoru se retrieval dela FTS, takze default je
neembedovat a jen ukladat text (rychle, lehke).

Pouziti (pres venv humanagentwiki kvuli psycopg + DATABASE_URL):
  harvest_trading_lit.py [--limit 120] [--per-query 30] [--embed]
"""
from __future__ import annotations
import argparse, datetime as dt, os, re, sys, time
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "https://export.arxiv.org/api/query"

# Pokryti temat, ktere uzivatel chce vstrebat (od strategie po technicke provedeni).
QUERIES = [
    "cat:q-fin.TR",  # Trading & Market Microstructure — provedeni obchodu, detail
    "cat:q-fin.PM",  # Portfolio Management — portfolio
    "cat:q-fin.CP",  # Computational Finance — technicka implementace
    "cat:q-fin.RM",  # Risk Management — bezpecne obchody, risk
    "cat:q-fin.ST",  # Statistical Finance
    "cat:q-fin.MF",  # Mathematical Finance
    "cat:q-fin.PR",  # Pricing of Securities
    'all:"prediction market"',
    'all:"algorithmic trading"',
    'all:"market making"',
    'all:"reinforcement learning" AND all:"trading"',
    'all:"portfolio optimization"',
    'all:"execution" AND all:"limit order book"',
]


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def _fetch(query: str, per_query: int) -> bytes:
    url = (f"{ARXIV}?search_query={urllib.parse.quote(query)}"
           f"&sortBy=submittedDate&sortOrder=descending&start=0&max_results={per_query}")
    req = urllib.request.Request(url, headers={"User-Agent": "lana-research/1.0 (research RAG)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _parse(xml_bytes: bytes) -> list[dict]:
    out = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out
    for e in root.findall(ATOM + "entry"):
        aid = (e.findtext(ATOM + "id") or "").strip()
        title = re.sub(r"\s+", " ", (e.findtext(ATOM + "title") or "").strip())
        summary = re.sub(r"\s+", " ", (e.findtext(ATOM + "summary") or "").strip())
        published = (e.findtext(ATOM + "published") or "")[:10] or None
        authors = ", ".join(a.findtext(ATOM + "name") or "" for a in e.findall(ATOM + "author"))[:400]
        cats = [c.get("term") for c in e.findall(ATOM + "category") if c.get("term")]
        if aid and title and summary:
            out.append({"url": aid, "title": title, "summary": summary,
                        "published": published, "authors": authors, "cats": cats})
    return out


def _chunk(txt: str, size: int = 1200) -> list[str]:
    txt = txt.strip()
    if len(txt) <= size:
        return [txt] if txt else []
    words, buf, out = txt.split(), "", []
    for w in words:
        if len(buf) + len(w) + 1 > size:
            out.append(buf); buf = w
        else:
            buf = (buf + " " + w) if buf else w
    if buf:
        out.append(buf)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=120, help="max novych praci za beh")
    ap.add_argument("--per-query", type=int, default=30)
    ap.add_argument("--embed", action="store_true", help="pocitej lokalni BGE-M3 embeddingy (CPU, bez tokenu)")
    args = ap.parse_args()

    embed_fn = None
    if args.embed:
        try:
            sys.path.insert(0, os.path.expanduser("~/humanagentwiki"))
            from common import embed as _embed
            embed_fn = _embed
        except Exception as e:
            print(f"embed nedostupny ({e}); pokracuji bez embeddingu", file=sys.stderr)

    c = _db(); cur = c.cursor()
    cur.execute("select url from lana.sources")
    known = {r[0] for r in cur.fetchall()}

    seen, papers = set(), []
    for q in QUERIES:
        if len(papers) >= args.limit:
            break
        try:
            for p in _parse(_fetch(q, args.per_query)):
                u = p["url"]
                if u in known or u in seen:
                    continue
                seen.add(u); papers.append(p)
                if len(papers) >= args.limit:
                    break
        except Exception as e:
            print(f"query fail [{q}]: {type(e).__name__}: {e}", file=sys.stderr)
        time.sleep(3)  # arXiv etiketa: max ~1 dotaz / 3 s (python sleep, ne shell)

    n_src = n_chunk = 0
    for p in papers:
        cur.execute(
            """insert into lana.sources(url,title,kind,authors,published,trust,meta)
               values(%s,%s,'preprint',%s,%s,0.7,%s) on conflict(url) do nothing returning id""",
            (p["url"], p["title"], p["authors"], p["published"],
             _json(p["cats"], p["summary"][:500])))
        row = cur.fetchone()
        if not row:
            continue
        sid = row[0]; n_src += 1
        chunks = _chunk(p["title"] + ". " + p["summary"])
        embs = embed_fn(chunks) if (embed_fn and chunks) else [None] * len(chunks)
        for i, (ch, emb) in enumerate(zip(chunks, embs)):
            cur.execute(
                "insert into lana.chunks(source_id,ord,content,embedding,tsv) "
                "values(%s,%s,%s,%s,to_tsvector('simple',%s))",
                (sid, i, ch, list(emb) if emb is not None else None, ch))
            n_chunk += 1
        c.commit()

    cur.execute(
        """insert into lana.runs(kind,started_at,finished_at,sources_added,findings_added,notes)
           values('harvest', now(), now(), %s, 0, %s) returning id""",
        (n_src, f"arxiv-harvest:{dt.date.today().isoformat()}"))
    c.commit(); c.close()
    print(f"harvest: novych zdroju={n_src}, chunku={n_chunk}, kandidatu={len(papers)}, embed={'ano' if embed_fn else 'ne'}")
    return 0


def _json(cats, summary):
    import json
    return json.dumps({"source": "arxiv", "categories": cats, "abstract": summary})


if __name__ == "__main__":
    raise SystemExit(main())

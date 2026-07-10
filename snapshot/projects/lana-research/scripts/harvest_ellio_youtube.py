#!/usr/bin/env python3
"""
Harvest EllioTrades (YouTube) do Lana RAG — ZERO-LLM. Tahá veřejný Atom RSS feed kanálu
(titulky + popisy videí = investiční tipy/narativy), tématicky taguje a ingestuje do schématu
`lana` (sources kind='youtube' + chunks s FTS). Inkrementální: nová videa přidá, existující přeskočí.

Podpírá strategii ~/lana-research/strategies/aschenbrenner-ellio.md (AI compute supercycle).
Spouštěj přes humanagentwiki venv (DATABASE_URL).  harvest_ellio_youtube.py [--channel-id UC...] [--limit 15]
"""
import argparse, os, re, html, urllib.request
import xml.etree.ElementTree as ET

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

NS = {"a": "http://www.w3.org/2005/Atom",
      "yt": "http://www.youtube.com/xml/schemas/2015",
      "m": "http://search.yahoo.com/mrss/"}

THEME_KW = {
    "energy": ["power", "energy", "grid", "electric", "nuclear", "uranium", "vistra", "constellation",
               "talen", "vertiv", "cameco", "reactor", "datacenter power", "utility"],
    "datacenter": ["datacenter", "data center", "coreweave", "core scientific", "nebius", "equinix",
                   "digital realty", "compute", "hyperscaler", "cloud"],
    "semis": ["nvidia", "nvda", "chip", "semiconductor", "broadcom", "amd", "tsmc", "asml", "micron",
              "intel", "gpu"],
    "crypto": ["crypto", "bitcoin", "btc", "ethereum", "eth", "altcoin", "token", "miner", "defi",
               "bittensor", "render", "akash"],
    "ai": ["ai ", "artificial intelligence", "agi", "openai", "anthropic", "aschenbrenner", "superintelligence"],
}


def _theme(text):
    t = text.lower()
    best, n = "general", 0
    for th, kws in THEME_KW.items():
        c = sum(1 for k in kws if k in t)
        if c > n:
            best, n = th, c
    return best


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel-id", default="UCMtJYS0PrtiUwlk6zjGDEMA")  # EllioTrades
    ap.add_argument("--limit", type=int, default=15)
    a = ap.parse_args()

    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={a.channel_id}"
    ua = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/122 Safari/537.36")
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    root = ET.fromstring(raw)
    author = (root.findtext("a:author/a:name", default="EllioTrades", namespaces=NS) or "EllioTrades")

    c = _db(); cur = c.cursor()
    added = skipped = 0
    themes = {}
    for e in root.findall("a:entry", NS)[:a.limit]:
        vid = e.findtext("yt:videoId", namespaces=NS) or ""
        title = html.unescape((e.findtext("a:title", namespaces=NS) or "").strip())
        link_el = e.find("a:link", NS)
        vurl = (link_el.get("href") if link_el is not None else f"https://youtu.be/{vid}")
        published = e.findtext("a:published", namespaces=NS)
        desc = e.findtext("m:group/m:description", namespaces=NS) or ""
        desc = html.unescape(re.sub(r"\s+", " ", desc)).strip()
        if not title:
            continue
        cur.execute("select id from lana.sources where url=%s", (vurl,))
        if cur.fetchone():
            skipped += 1
            continue
        theme = _theme(title + " " + desc)
        themes[theme] = themes.get(theme, 0) + 1
        meta = f'{{"channel":"EllioTrades","channel_id":"{a.channel_id}","video_id":"{vid}","theme":"{theme}"}}'
        cur.execute("""insert into lana.sources(url,title,kind,authors,published,trust,meta,added_at)
                       values(%s,%s,'youtube',%s,%s,%s,%s::jsonb,now()) returning id""",
                    (vurl, title[:300], author, published, 0.5, meta))
        sid = cur.fetchone()[0]
        content = (title + "\n" + desc)[:1800]
        cur.execute("insert into lana.chunks(source_id,ord,content,tsv) values(%s,0,%s,to_tsvector('simple',%s))",
                    (sid, content, content))
        added += 1

    try:
        cur.execute("""insert into lana.runs(kind,started_at,finished_at,sources_added,notes)
                       values('harvest-ellio',now(),now(),%s,%s)""",
                    (added, f"EllioTrades feed; témata={themes}"))
    except Exception:
        pass
    c.commit(); c.close()
    print(f"ellio harvest: +{added} videí, {skipped} už měl. Témata: {themes}")


if __name__ == "__main__":
    main()

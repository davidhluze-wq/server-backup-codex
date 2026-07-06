#!/usr/bin/env python3
"""AI news monitor for Hermes cron.

Modes:
  --breaking: every 30 min; prints one Telegram-ready HTML message or stays silent.
  --digest: 2x/day; prints a Telegram-ready HTML digest with 5 items.

Cron should run this as no_agent=True so non-empty stdout is delivered to Telegram.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE = Path.home() / ".hermes" / "news-agent"
DEDUP_PATH = BASE / "dedup.json"
HISTORY_PATH = BASE / "sent_history.txt"
DIGEST_LAST_PATH = BASE / "digest_last_sent.txt"
DIGEST_DEDUP_PATH = BASE / "digest_topics.json"
LOG_PATH = BASE / "news_monitor.log"

HERMES = os.environ.get("HERMES_BIN", "hermes")
TRUSTED_BREAKING = "Reuters, AP, BBC, The New York Times"
TRUSTED_DIGEST = "Reuters, AP, BBC, The New York Times, The Guardian"
BLOCKED_SOURCES = "Al Jazeera, Fox News"

STOP = {
    "and", "the", "for", "with", "that", "this", "from", "have", "has", "was", "were", "are", "about", "after",
    "before", "over", "under", "into", "than", "then", "they", "their", "them", "will", "would", "could", "should",
    "you", "your", "a", "an", "of", "to", "in", "on", "at", "by", "as", "is", "it", "or", "be", "not", "new",
    "jako", "který", "která", "které", "pro", "před", "pod", "nad", "mezi", "jsou", "byl", "byla", "bylo",
    "bude", "jeho", "její", "jejich", "toto", "tato", "této", "podle", "také", "další", "zprávy", "řekl",
}

PREAMBLE_RE = re.compile(r"^\s*(based on|i['’]?ll|i will|let me|according to my|here (is|are)|zde jsou|na základě)", re.I)
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
TAG_RE = re.compile(r"<[^>]+>")


def log(msg: str) -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{ts} {msg}\n")


def now_cz() -> datetime:
    # Czechia is CET/CEST; stdlib fixed offset is acceptable for prompt wording here.
    # Use system UTC plus Europe/Prague if zoneinfo exists.
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Prague"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=1)))


def acquire_lock(name: str):
    BASE.mkdir(parents=True, exist_ok=True)
    lock_path = BASE / f"{name}.lock"
    f = lock_path.open("w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return None
    f.write(str(os.getpid()))
    f.flush()
    return f


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def recent_history(limit: int = 10) -> str:
    if not HISTORY_PATH.exists():
        return "(zatím nic)"
    lines = [l.strip() for l in HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    return "\n".join(lines[-limit:]) if lines else "(zatím nic)"


def append_history(preview: str) -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    lines = []
    if HISTORY_PATH.exists():
        lines = HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    lines.append(preview.strip()[:220])
    HISTORY_PATH.write_text("\n".join(lines[-80:]) + "\n", encoding="utf-8")


def strip_html(text: str) -> str:
    return html.unescape(TAG_RE.sub(" ", text))


def words_for(text: str) -> set[str]:
    text = strip_html(URL_RE.sub(" ", text)).lower()
    toks = re.findall(r"[a-zá-ž0-9]{4,}", text, flags=re.I)
    return {t for t in toks if t not in STOP and not t.isdigit()}


def urls_for(text: str) -> set[str]:
    out = set()
    for u in URL_RE.findall(text):
        p = urlparse(u.rstrip(".,)\"]"))
        if p.netloc:
            out.add(f"{p.netloc.lower()}{p.path}".rstrip("/"))
    return out


def normalized_hash(text: str) -> str:
    norm = " ".join(sorted(words_for(text))) + "|" + " ".join(sorted(urls_for(text)))
    return hashlib.sha256(norm.encode()).hexdigest()


def is_duplicate_breaking(text: str) -> bool:
    cache = load_json(DEDUP_PATH, [])
    cutoff = time.time() - 14 * 24 * 3600
    cache = [x for x in cache if x.get("ts", 0) > cutoff]
    h = normalized_hash(text)
    urls = urls_for(text)
    words = words_for(text)
    for item in cache:
        if item.get("hash") == h:
            save_json(DEDUP_PATH, cache)
            return True
        if urls and urls.intersection(set(item.get("urls", []))):
            save_json(DEDUP_PATH, cache)
            return True
        old_words = set(item.get("words", []))
        if words and old_words:
            j = len(words & old_words) / max(1, len(words | old_words))
            if j >= 0.18:
                save_json(DEDUP_PATH, cache)
                return True
    cache.append({"ts": time.time(), "hash": h, "urls": sorted(urls), "words": sorted(words), "preview": strip_html(text)[:220]})
    save_json(DEDUP_PATH, cache)
    return False


def run_hermes(prompt: str, timeout: int) -> str:
    # Rutinni sumarizace zprav -> levny tier (gpt-5.4-mini) misto default gpt-5.5.
    # Override pres HERMES_NEWS_PROFILE, kdyby bylo potreba eskalovat.
    profile = os.environ.get("HERMES_NEWS_PROFILE", "worker-gpt-mini")
    cmd = [HERMES, "-p", profile, "chat", "-Q", "-t", "web", "-q", prompt]
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        log(f"timeout after {timeout}s")
        return ""
    if p.returncode != 0:
        log(f"hermes rc={p.returncode} stderr={p.stderr[-1000:]}")
        return ""
    out = p.stdout.strip()
    # Quiet mode should be clean, but strip common wrappers if any.
    out = re.sub(r"^```(?:html|text)?\s*", "", out).strip()
    out = re.sub(r"\s*```$", "", out).strip()
    return out


def validate_breaking(text: str) -> bool:
    if not text:
        return False
    if text.strip().upper() == "NOTHING" or "NOTHING" in text[:40].upper():
        return False
    if len(strip_html(text)) < 80:
        return False
    if "http" not in text:
        return False
    if PREAMBLE_RE.search(text):
        return False
    if len(text) > 900:  # allow wrapper + HTML, but reject long rambles
        return False
    return True




def split_digest_items(text: str) -> list[str]:
    """Split an HTML digest into item-like blocks; skip the header."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    return [b for b in blocks if "<b>" in b and "http" in b and "Zprávy ze světa" not in strip_html(b) and "Významné nové" not in strip_html(b)]


def item_title(item: str) -> str:
    m = re.search(r"<b>(.*?)</b>", item, flags=re.I | re.S)
    if m:
        return strip_html(m.group(1)).strip()
    return strip_html(item).strip().split("\n", 1)[0][:120]


def novelty_filter_digest(text: str) -> tuple[str, list[str]]:
    """Keep only digest items materially new vs the last 30 days.

    Returns (filtered_text, titles_kept). Empty filtered_text means stay silent.
    """
    cache = load_json(DIGEST_DEDUP_PATH, [])
    cutoff = time.time() - 30 * 24 * 3600
    cache = [x for x in cache if x.get("ts", 0) > cutoff]
    items = split_digest_items(text)
    kept = []
    titles = []
    for item in items:
        words = words_for(item)
        urls = urls_for(item)
        title = item_title(item)
        duplicate = False
        for old in cache:
            old_words = set(old.get("words", []))
            old_urls = set(old.get("urls", []))
            if urls and old_urls and urls & old_urls:
                duplicate = True
                break
            if words and old_words:
                j = len(words & old_words) / max(1, len(words | old_words))
                # Digest is conservative: suppress repeated storylines unless clearly different.
                if j >= 0.24:
                    duplicate = True
                    break
        if duplicate:
            log(f"digest duplicate item suppressed: {title[:120]}")
            continue
        kept.append(item)
        titles.append(title)
        cache.append({"ts": time.time(), "title": title, "hash": normalized_hash(item), "urls": sorted(urls), "words": sorted(words), "preview": strip_html(item)[:220]})
    save_json(DIGEST_DEDUP_PATH, cache[-250:])
    if len(kept) < 2:
        return "", titles
    n = now_cz()
    header = f"🌍 <b>Významné nové události</b> — {n:%d.%m. %H:%M}"
    return header + "\n\n" + "\n\n".join(kept[:5]), titles[:5]


def breaking_prompt() -> str:
    n = now_cz()
    return f"""Pracuj POUZE s web search nástrojem. NEPOUŽÍVEJ shell, terminal ani souborové nástroje.
Aktuální čas: {n:%H:%M} Praha, datum: {n:%d.%m.%Y}.

Zkontroluj, zda se za posledních 30 minut stala SKUTEČNÁ breaking news ve světové politice, bezpečnosti nebo ekonomice. Prohledej {TRUSTED_BREAKING}. Nepoužívej {BLOCKED_SOURCES}.

KRITÉRIUM NOVOSTI: neposílej stejný příběh znovu jen s jiným titulkem. Pošli pouze tehdy, když nastal NOVÝ fakt, který významně posouvá situaci (rozhodnutí, útok, rezignace, podpis zákona, kolaps jednání, mimořádný ekonomický šok apod.). Rutinní komentáře, analýzy, follow-up bez nové okolnosti a opakované shrnutí stejné kauzy = NOTHING.

ZPRÁVY ODESLANÉ V POSLEDNÍCH DNECH (NEopakuj tyto události, pokud není zásadní nový obrat):
{recent_history(20)}

Pokud NENASTALA významná nová okolnost, nebo jde o stejnou událost/titulek, odpověz pouze: NOTHING
Pokud NASTALA, napiš JEDNU zprávu v tomto formátu:
[emoji] <b>[český titulek, max 8 slov]</b>
— [max 3 věty shrnutí česky]
🔗 <a href=\"[url]\">[název média]</a>

Používej výhradně HTML tagy (<b>, <a href>), ŽÁDNÝ markdown. Začni přímo zprávou. MAX 400 znaků. Pouze skutečné breaking news, ne běžné zprávy."""


def digest_prompt() -> str:
    n = now_cz()
    return f"""Pracuj POUZE s web search nástrojem. Aktuální čas: {n:%d.%m. %H:%M} Praha.
Prohledej DNEŠNÍ zprávy — POUZE z posledních 8 hodin (starší nevyužívej, pokud nejde o průběžně se vyvíjející top událost).
Vyber pouze události, kde se stala NOVÁ významná okolnost, která téma posouvá. Neopakuj stejné příběhy/titulky z předchozích digestů jen proto, že je média znovu zmiňují. Vynech rutinní komentáře, analýzy, spekulace, sport, celebrity, lifestyle.

Nedávno poslané/potlačené okruhy — neopakuj bez zásadního nového obratu:
{recent_history(20)}

Pokud nenajdeš aspoň 2 skutečně nové významné události, odpověz pouze: NOTHING
Jinak vyber 2–5 nejdůležitějších: geopolitika, ekonomika, bezpečnost, technologie. Zdroje: {TRUSTED_DIGEST}. Nepoužívej {BLOCKED_SOURCES}.

Hlavička: 🌍 <b>Zprávy ze světa</b> — {n:%d.%m. %H:%M}
Pak 2–5 zpráv (odděl prázdným řádkem):
[emoji] <b>[český titulek, max 8 slov]</b>
— [3–4 věty: kdo, co, kde, proč]
🔗 <a href=\"[skutečná URL]\">[název média]</a>

Výhradně HTML tagy, žádný markdown. Začni přímo hlavičkou. MAX 3500 znaků. Neopakuj zbytečně tutéž událost ve více bodech. Pokud jde jen o opakování známé věci, NOTHING."""


def run_breaking() -> int:
    # Only run on :00/:30-ish if cron is imprecise. Allow a wide window for scheduler drift.
    n = now_cz()
    if n.minute not in {0, 1, 2, 28, 29, 30, 31, 32}:
        log(f"breaking skipped minute={n.minute}")
        return 0
    lock = acquire_lock("breaking")
    if lock is None:
        return 0
    text = run_hermes(breaking_prompt(), timeout=180)
    if not validate_breaking(text):
        log("breaking nothing/invalid")
        return 0
    if is_duplicate_breaking(text):
        log("breaking duplicate")
        return 0
    msg = "🚨 <b>BREAKING</b>\n\n" + text.strip()
    append_history(strip_html(text).replace("\n", " "))
    print(msg)
    return 0


def run_digest(force: bool = False) -> int:
    lock = acquire_lock("digest")
    if lock is None:
        return 0
    if DIGEST_LAST_PATH.exists() and not force:
        try:
            last = float(DIGEST_LAST_PATH.read_text().strip())
            if time.time() - last < 20 * 60:
                log("digest cooldown")
                return 0
        except Exception:
            pass
    text = run_hermes(digest_prompt(), timeout=600)
    if not text or text.strip().upper().startswith("NOTHING") or PREAMBLE_RE.search(text) or "http" not in text or len(strip_html(text)) < 250:
        log("digest invalid/nothing")
        return 0
    filtered, titles = novelty_filter_digest(text)
    if not filtered:
        log("digest no sufficiently novel items")
        return 0
    DIGEST_LAST_PATH.write_text(str(time.time()))
    for t in titles:
        append_history("DIGEST ITEM " + now_cz().strftime("%d.%m. %H:%M") + " — " + t)
    print(filtered[:3900])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--breaking", action="store_true")
    g.add_argument("--digest", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore digest cooldown")
    args = ap.parse_args()
    BASE.mkdir(parents=True, exist_ok=True)
    if args.breaking:
        return run_breaking()
    if args.digest:
        return run_digest(force=args.force)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())

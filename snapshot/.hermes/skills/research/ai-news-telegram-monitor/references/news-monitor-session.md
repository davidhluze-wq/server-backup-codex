# AI news monitor deployment notes

This reference captures the implementation pattern proven in the session that created `~/.hermes/scripts/news_monitor.py`.

## Script shape

- Location used: `~/.hermes/scripts/news_monitor.py`
- State directory: `~/.hermes/news-agent/`
- State files:
  - `dedup.json` — breaking-news dedup cache
  - `sent_history.txt` — recent sent titles/context for prompt
  - `digest_last_sent.txt` — digest cooldown
  - `news_monitor.log` — local diagnostic log

## Working Hermes invocation

Use Hermes one-shot with only web tools:

```bash
hermes chat -Q -t web -q "$PROMPT"
```

The cron job itself should be `no_agent=True`; the script invokes Hermes internally only when it needs reasoning/search.

## Validation rules that mattered

Breaking news should be discarded if:

- output is empty,
- starts/contains `NOTHING`,
- has no `http`,
- is too short to be a real sourced news item,
- starts with an LLM preamble (`based on`, `let me`, `zde jsou`, etc.),
- duplicates recent events via normalized hash, URL overlap, or keyword Jaccard similarity >= 0.22.

Digest should be discarded if missing URLs, too short, or starts with a preamble.

## Schedule used

The user asked for breaking throughout the day and **2× daily** digest:

```text
*/30 * * * *   news_monitor.py --breaking
0 8,18 * * *   news_monitor.py --digest
```

The server cron was UTC, so `08:00/18:00 UTC` was selected for roughly `10:00/20:00` Prague during summer time.

## Manual verification

```bash
chmod 700 ~/.hermes/scripts/news_monitor.py
python3 -m py_compile ~/.hermes/scripts/news_monitor.py
~/.hermes/scripts/news_monitor.py --help
~/.hermes/scripts/news_monitor.py --breaking
~/.hermes/scripts/news_monitor.py --digest --force
hermes cron list
```

A forced digest test produced a valid ~2.4KB Telegram HTML digest with 5 items and real source URLs.

## User-facing style

For this user, summarize setup in Czech with a small table, exact paths, schedules, and first-run timing. Avoid overexplaining internals unless asked.

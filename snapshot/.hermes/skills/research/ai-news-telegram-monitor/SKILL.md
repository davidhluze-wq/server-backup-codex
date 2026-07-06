---
name: ai-news-telegram-monitor
description: "Build an AI-powered world-news monitor for Telegram: deduplicated breaking news plus scheduled Czech digest summaries via Hermes cron."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [news, telegram, cron, web-search, breaking-news, digest, monitoring]
    created_by: agent
---

# AI News Telegram Monitor

Use this skill when a user asks for an autonomous news agent that watches world events and sends Telegram updates. This is **not** an RSS/feed reader pattern; it uses an LLM agent with web search, strict prompts, validation, deduplication, and Hermes cron delivery.

## Core behavior

- **Breaking mode:** run every 30 minutes. Send at most one message, only for a genuinely major new world event. If nothing strong is found, output nothing.
- **Digest mode:** run on a fixed schedule. Produce a concise Czech digest with exactly 5 important world-news items.
- **Delivery:** use Hermes `cronjob` with `no_agent=True` and `deliver="origin"`. The script prints the final Telegram-ready message to stdout; empty stdout means silent success.
- **Format:** Telegram HTML only (`<b>`, `<a href="...">`), not Markdown.
- **Sources:** prefer Reuters, AP, BBC, New York Times, The Guardian. Avoid sources the user rejects.
- **Quality over volume:** validate aggressively; silence is better than hallucinated or stale breaking news.

## Implementation steps

1. Create a script under `~/.hermes/scripts/`, e.g. `news_monitor.py`.
2. Include two modes: `--breaking` and `--digest`.
3. The script invokes Hermes one-shot with web-only tools:

```bash
hermes chat -Q -t web -q "$PROMPT"
```

4. Breaking prompt must include:
   - current date/time,
   - trusted sources,
   - excluded sources,
   - recent sent-history context,
   - explicit `NOTHING` output when no major new event exists,
   - one-item HTML format with a real URL.
5. Digest prompt must include:
   - current date/time,
   - last-hours freshness window,
   - exactly 5 items,
   - categories to prefer/avoid,
   - HTML output and max length.
6. Implement hard validation:
   - reject empty output,
   - reject `NOTHING`,
   - reject missing `http`,
   - reject reasoning preambles (`based on`, `let me`, `zde jsou`, etc.),
   - reject too-short breaking output.
7. Implement breaking dedup:
   - normalized hash of words/URLs,
   - URL overlap,
   - Jaccard similarity of keyword sets with threshold around `0.22`,
   - keep 48–96h of history.
8. Implement locks/cooldowns:
   - flock per mode,
   - breaking only on `:00`/`:30` windows if scheduler may drift,
   - digest cooldown around 20 minutes.
9. Test manually before scheduling:

```bash
~/.hermes/scripts/news_monitor.py --breaking
~/.hermes/scripts/news_monitor.py --digest --force
python3 -m py_compile ~/.hermes/scripts/news_monitor.py
```

10. Schedule with Hermes cron:

```text
*/30 * * * *   news_monitor.py --breaking
0 8,18 * * *   news_monitor.py --digest    # UTC = ~10:00/20:00 Prague in summer
```

## Prompt templates

### Breaking prompt shape

```text
Pracuj POUZE s web search nástrojem. NEPOUŽÍVEJ shell, terminal ani souborové nástroje.
Aktuální čas: {HH:MM} Praha, datum: {DD.MM.RRRR}.

Zkontroluj, zda se za posledních 30 minut stala SKUTEČNÁ breaking news ve světové politice,
bezpečnosti nebo ekonomice. Prohledej Reuters, AP, BBC, The New York Times.
Nepoužívej Al Jazeera. Nepoužívej Fox News.

ZPRÁVY ODESLANÉ V POSLEDNÍCH DNECH (NEopakuj tyto události):
{history}

Pokud NENASTALA nová breaking news, nebo jde o stejnou událost, odpověz pouze: NOTHING
Pokud NASTALA, napiš JEDNU zprávu v tomto formátu:
[emoji] <b>[český titulek, max 8 slov]</b>
— [max 3 věty shrnutí česky]
🔗 <a href="[url]">[název média]</a>

Používej výhradně HTML tagy (<b>, <a href>), ŽÁDNÝ markdown. Začni přímo zprávou. MAX 400 znaků.
```

### Digest prompt shape

```text
Pracuj POUZE s web search nástrojem. Aktuální čas: {DD.MM. HH:MM} Praha.
Prohledej DNEŠNÍ zprávy — POUZE z posledních 8 hodin.
Vyber PŘESNĚ 5 nejdůležitějších: geopolitika, ekonomika, bezpečnost, technologie.
Vynech sport, celebrity, lifestyle. Zdroje: Reuters, AP, BBC, NYT, The Guardian.
Nepoužívej Al Jazeera ani Fox News.

Hlavička: 🌍 <b>Zprávy ze světa</b> — {DD.MM. HH:MM}
Pak PŘESNĚ 5 zpráv (odděl prázdným řádkem):
[emoji] <b>[český titulek, max 8 slov]</b>
— [3–4 věty: kdo, co, kde, proč]
🔗 <a href="[skutečná URL]">[název média]</a>

Výhradně HTML tagy, žádný markdown. Začni přímo hlavičkou. MAX 3500 znaků.
```

## Hermes cron pattern

Use script-only cron jobs so the script controls silence/noise exactly:

```python
cronjob(action="create", name="AI zpravodaj — breaking news", schedule="*/30 * * * *",
        script="news_monitor.py --breaking", no_agent=True, deliver="origin",
        prompt="Script-only job. Empty stdout means no delivery.")

cronjob(action="create", name="AI zpravodaj — souhrn 2× denně", schedule="0 8,18 * * *",
        script="news_monitor.py --digest", no_agent=True, deliver="origin",
        prompt="Script-only job. Prints Telegram-ready digest.")
```

## Pitfalls

- Do not use RSS/blogwatcher for this class unless the user explicitly asks for feed monitoring. The desired behavior is editorial selection via web search.
- Do not send every run. Breaking mode should often be silent.
- Do not let a cron-run LLM recursively create cron jobs. Use a script as the cron target.
- Do not use Markdown in Telegram messages when the content is built for HTML parsing.
- Watch time zones: Hermes cron schedules are UTC unless configured otherwise. For Prague summer time, `08:00/18:00 UTC` corresponds to `10:00/20:00` local.

## References

- `references/news-monitor-session.md` — session notes and concrete implementation details from the first deployment.

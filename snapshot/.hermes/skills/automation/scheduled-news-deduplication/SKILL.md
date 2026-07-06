---
name: scheduled-news-deduplication
description: Build and maintain scheduled news/radar automations that stay quiet on repeated headlines and only alert when a story materially advances.
version: 1.0.0
created_by: agent
metadata:
  hermes:
    tags: [news, cron, automation, deduplication, telegram, watchdog]
---

# Scheduled News Deduplication

Use this skill when creating, tuning, or troubleshooting scheduled news/radar jobs for the user: world news, AI/automotive radar, breaking-news monitors, Telegram reports, RSS/blog monitors, or any cron job whose main risk is repeated headlines.

## User expectation

The user does **not** want daily repeats of the same headline/topic. Send only when a **significant new development materially moves the story forward**. Silence is correct when nothing meaningful changed.

Good alert triggers:

- formal decision, verdict, signed law, sanction, resignation, ceasefire, attack, merger/acquisition, bankruptcy, recall, launch, model release, security incident, major regulatory move,
- new verified data that changes the interpretation of the topic,
- escalation/de-escalation that affects consequences or next actions.

Bad alert triggers:

- same story rewritten by another outlet,
- opinion/analysis without a new fact,
- minor quote, speculation, recap, or headline variation,
- a digest that exists only because the schedule fired.

## Implementation pattern

Prefer `cronjob(no_agent=True, script=...)` for news watchdogs. The script should print output only when there is something worth sending; empty stdout means silent success.

State files should record **topic/story keys and titles**, not just timestamps. Keep a durable state directory such as:

```text
~/.hermes/news-agent/
  dedup.json
  sent_history.txt
  news_monitor.log
```

Recommended dedupe windows:

| Job type | Window | Send threshold |
|---|---:|---|
| Breaking news | 14 days | one material story movement |
| Scheduled digest | 30 days | at least 2 genuinely new significant developments |
| Niche radar, e.g. AI + automotive | 14-30 days | material product/regulatory/company move only |

## Story-key rules

Generate a normalized story key from the entities + event class, not raw title. Example:

```text
openai-gpt-5-release
ukraine-ceasefire-negotiations
vw-ev-battery-recall
```

Before sending, compare the candidate with previous keys/titles. If same key appears inside the dedupe window, only send if the new item has a stronger event class than the previous one.

## Prompt rules for LLM-assisted filtering

If an LLM is used to classify candidates, include this contract:

```text
Do not return a report just because the schedule fired. Compare against prior sent topics. Emit nothing unless there is a significant new fact that materially advances the story. Reworded headlines, commentary, and routine follow-ups are duplicates.
```

## Verification checklist

- Run the script manually; verify empty output when no qualifying story exists.
- Inspect `sent_history.txt` / `dedup.json` and confirm it stores story identifiers or titles.
- Confirm the cron job uses `no_agent=True` for watchdog-style delivery.
- Confirm non-zero exit still alerts so broken jobs do not fail silently.

## Existing server notes

The user's news automations use scripts under:

```text
~/.hermes/scripts/news_monitor.py
~/.hermes/scripts/news_breaking.sh
~/.hermes/scripts/news_digest.sh
~/.hermes/scripts/ai_auto_radar.py
~/.hermes/scripts/ai_auto_radar.sh
```

These should remain quiet unless a topic materially moves forward.
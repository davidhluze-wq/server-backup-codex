---
name: scheduled-telegram-automation
description: "Build durable Telegram-delivered automations with Hermes cron, script-only jobs, no-agent watchdogs, and LLM-driven scheduled reports."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [cron, telegram, automation, scheduled-jobs, no-agent, watchdog]
---

# Scheduled Telegram Automation

Use this skill when the user asks to create an autonomous Telegram automation: recurring reports, watchdogs, security audits, news monitors, notification bots, or scheduled summaries delivered back to the current Telegram chat.

## Core pattern

1. **Keep the future job self-contained.** Cron sessions start fresh; prompts and scripts must include all context they need.
2. **Use `cronjob` for durable scheduling.** Do not spawn long-lived background subagents for work that must survive the current session.
3. **Choose the right cron mode:**
   - `no_agent=true` + `script` for deterministic alerts/digests where the script prints the exact Telegram message.
   - Default LLM-driven cron (`no_agent=false`) when the scheduled task must reason, search the web, synthesize, or write files.
   - `script` + LLM-driven cron when the script only collects context before the model reasons.
4. **Delivery:** normally omit `deliver` or use `origin` for the current Telegram chat. Use `local` for data-collection jobs whose output should not be sent to the user.
5. **Silence is a feature:** for `no_agent=true`, empty stdout means no Telegram message. Use this for watchdogs and breaking-news monitors.

## References

- `references/cron-script-arguments.md` — concrete failure transcript and fix for cron `script` values that accidentally include arguments.

## Important pitfall: script arguments

Hermes cron `script` is a script path, not a shell command line. Do **not** set:

```text
script="news_monitor.py --breaking"
```

That is treated as a literal file path and fails with `Script not found`.

Instead create executable wrapper scripts under `~/.hermes/scripts/`:

```bash
# ~/.hermes/scripts/news_breaking.sh
#!/usr/bin/env bash
set -euo pipefail
exec "$HOME/.hermes/scripts/news_monitor.py" --breaking
```

```bash
# ~/.hermes/scripts/news_digest.sh
#!/usr/bin/env bash
set -euo pipefail
exec "$HOME/.hermes/scripts/news_monitor.py" --digest
```

Then schedule the wrappers:

```text
script="news_breaking.sh"
script="news_digest.sh"
```

## Verification checklist

Before telling the user it is done:

1. `chmod 700` every script/wrapper.
2. Run `python3 -m py_compile` for Python scripts.
3. Run the wrapper manually once. For silent watchdogs, confirm exit code `0` and inspect its log/state file.
4. `cronjob(action="list")` and verify:
   - job is enabled,
   - schedule is correct,
   - `next_run_at` is plausible,
   - `script` is the wrapper path only,
   - `no_agent` matches the design.
5. If a cron run fails, read its saved output under `~/.hermes/cron/output/<job_id>/...` and fix the actual cause.

## Telegram output guidance

- Keep scheduled notifications short and directly useful.
- If a job decides there is nothing important, print nothing.
- For user-facing recurring reports, make the script/LLM produce the final message body, not a debugging transcript.
- For Telegram Markdown/HTML details, verify with an actual delivery or a manual script run; do not assume all parse modes behave the same across no-agent stdout delivery and normal assistant messages.

## Common designs

### Breaking-news monitor

- Cron: every 30 minutes.
- Script: calls a web-enabled Hermes one-shot or other search agent.
- Output: one short message only for major genuinely new events; otherwise empty stdout.
- State: keep `dedup.json` and recent headline history; compare hashes, URL overlap, and keyword similarity.
- **Novelty gate:** suppress "same story, new headline" repeats. Send only when a new fact materially moves the story forward (decision, attack, resignation, signed law, collapsed negotiation, major market shock, etc.). Use a long enough dedup window (often 14+ days for breaking items).

### Daily or twice-daily digest

- Cron: fixed hours.
- Script/agent: gather current items and synthesize key points.
- Do **not** force exactly 5 items if the news cycle is stale. Prefer 2–5 genuinely new items, and print nothing if fewer than 2 pass novelty checks.
- Add a cooldown state file to avoid duplicate delivery if the scheduler reruns.
- Add per-item topic dedup (30–45 day state) based on normalized URLs and word-set similarity, not just exact headlines.
- See `references/news-novelty-dedup.md` for the concrete novelty/dedup pattern and prompt criteria.

### Security/report watchdog

- Collection job writes facts and report to disk.
- Failsafe job is `no_agent=true` and prints one alert only if today's report is missing.
- Digest job is `no_agent=true` and extracts a preformatted Telegram section from the report.

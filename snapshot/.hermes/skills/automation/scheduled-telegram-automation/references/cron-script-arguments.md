# Session note: news monitor + cron wrapper failure

This reference captures a reusable debugging path from a Telegram news-monitor setup.

## Symptom

A `no_agent=true` Hermes cron job showed `last_status: error` for a script configured like:

```text
script: news_monitor.py --breaking
```

The saved run output under `~/.hermes/cron/output/<job_id>/...` said:

```text
Status: script failed
Script not found: /home/<user>/.hermes/scripts/news_monitor.py --breaking
```

## Root cause

The `cronjob` tool's `script` field is a script path, not a shell command line. Arguments are not parsed there.

## Fix

Create argument-specific wrapper scripts in `~/.hermes/scripts/`:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec "$HOME/.hermes/scripts/news_monitor.py" --breaking
```

and:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec "$HOME/.hermes/scripts/news_monitor.py" --digest
```

Then update cron jobs to use only:

```text
script="news_breaking.sh"
script="news_digest.sh"
```

## Verification

- Run the wrapper manually.
- Trigger one cron run with `cronjob(action="run", job_id="...")`.
- Confirm `last_status: ok` via `cronjob(action="list")`.
- If the script is designed to be silent, check its own log file; an empty stdout can still be a successful run.

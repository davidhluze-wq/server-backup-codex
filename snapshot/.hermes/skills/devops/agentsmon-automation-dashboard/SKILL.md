---
name: agentsmon-automation-dashboard
description: Register recurring/automatic jobs in the agentsmon dashboard with expandable descriptions, status, and Start/Stop controls.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [agentsmon, dashboard, automation, cron, monitoring, start-stop]
    created_by: agent
---

# Agentsmon Automation Dashboard

Use this skill whenever you create, modify, or troubleshoot a recurring/automatic job for this user and the job should be visible in **agentsmon**. The user's expectation is: an automation is not "done" until it appears in the dashboard with a clear description and Start/Stop control when feasible.

Typical triggers:

- A new crontab line, Hermes cron job, systemd timer, watcher, ETL refresh, monitor, radar, report, digest, or scheduled data pipeline is created.
- A recurring job is modified and its dashboard description/status should stay accurate.
- The user asks to see automatic runs in agentsmon or control them from the dashboard.

## Core rule

When creating anything that runs automatically/repeatedly:

1. Create or update the actual automation.
2. Register it in agentsmon's automatic-runs dashboard area.
3. Include an expandable description of what it does, outputs, schedule, logs, and limitations.
4. Provide Stop/Start behavior appropriate to the automation source.
5. Verify both the automation and the dashboard registration.

## Current agentsmon layout on this VPS

```text
Source checkout: ~/.agentsmon-src/
Dashboard module: ~/.agentsmon-src/agentsmon/dashboard.py
Config: ~/.config/agentsmon/config.json
State dir: ~/.local/state/agentsmon/
Launcher: ~/.local/state/agentsmon/agentsmon-launch.sh
Public dashboard: http://38.19.198.4:8765
```

The dashboard already serves public Power BI commodity files without auth:

```text
/commodities.csv
/commodities.json
```

Other dashboard API/UI routes normally require the configured agentsmon Basic Auth.

## Registration pattern for non-Hermes-cron jobs

Use a registry file in agentsmon state:

```text
~/.local/state/agentsmon/automatic_runs.json
```

Shape:

```json
{
  "runs": [
    {
      "id": "stable-machine-id",
      "name": "Human readable name",
      "source": "crontab",
      "schedule": "0 6 1 * *",
      "command": "/usr/bin/python3 /path/script.py >> /path/log 2>&1",
      "description": "What this automatic run does, what it updates, and what Stop/Start mean.",
      "url": "http://optional-output-url",
      "meta_url": "http://optional-status-url",
      "log": "/path/logfile.log"
    }
  ]
}
```

Use stable IDs, not dates. Good examples:

- `commodity-etl-monthly`
- `security-audit-lite-auto-update`
- `ai-news-breaking`

## Start/Stop semantics

### Hermes cron jobs

Use Hermes cron controls:

```bash
hermes cron pause <job_id>
hermes cron resume <job_id>
```

The dashboard should show `enabled`, `last_status`, `last_run_at`, `schedule`, and a compact description from the job prompt/script.

### User crontab jobs

For external crontab entries, Stop should comment the exact line using a reversible marker:

```text
# agentsmon-disabled <id> | <original crontab line>
```

Start should restore exactly the original line. Verify after toggling:

```bash
crontab -l | grep '<unique command or id>'
```

### Systemd timers/services

If adding this class later, prefer:

```bash
systemctl --user disable --now <timer-or-service>
systemctl --user enable --now <timer-or-service>
```

Only wire Stop/Start if the exact service/timer name is known and low-risk.

## UI expectations

In agentsmon, add an `Automatické běhy` table under the activity/kanban area or equivalent. Each row should include:

- name + source badge (`hermes-cron`, `crontab`, `systemd`, etc.),
- a clearly visible real button labeled `▸ Detail` for the popisek, not only a native `<details>` disclosure or row click,
- after opening, the button should change to `▾ Skrýt`,
- details should remain open across the dashboard auto-refresh; track opened rows client-side with a stable key such as `source|id` and re-render them open,
- schedule,
- last run/status,
- output/status links when present,
- `Stop` when active and `Start` when paused.

For this Czech-speaking user, keep labels practical and concise:

```text
Automatické běhy
Název + popisek
Schedule
Poslední běh / stav
Akce
Stop / Start
```

## Verification checklist

Before reporting completion:

- [ ] The underlying recurring job still exists and is active unless intentionally stopped.
- [ ] `automatic_runs.json` parses as JSON if used.
- [ ] `agentsmon.dashboard._automation_rows()` includes the new job.
- [ ] Stop/Start round-trip works on a safe target or a test instance, and leaves the job active if it should remain active.
- [ ] Dashboard process was restarted/reloaded so the UI uses new code.
- [ ] Public data endpoints that share the dashboard port still work.
- [ ] If the automation is itself a backup/restore/sync job, make sure the agentsmon registry (`~/.local/state/agentsmon/automatic_runs.json`) and any updated backup script are included in the backup payload.
- [ ] If you start a temporary test dashboard/process for UI verification, kill it before finishing and expect delayed watch-pattern notifications; verify only the production port remains listening.

Useful local checks:

```bash
PYTHONPATH=~/.agentsmon-src AGENTSMON_CONFIG=~/.config/agentsmon/config.json \
AGENTSMON_STATE=~/.local/state/agentsmon python3 - <<'PY'
from agentsmon import dashboard
rows = dashboard._automation_rows()
print(len(rows))
print([r for r in rows if r.get('id') == 'commodity-etl-monthly'])
PY

python3 -m py_compile ~/.agentsmon-src/agentsmon/dashboard.py
~/.local/state/agentsmon/agentsmon-launch.sh
curl -sS http://127.0.0.1:8765/commodities.json | python3 -m json.tool | head
```

## Pitfalls

- Do not stop a production automation as a demo and forget to restart it. If you test Stop/Start, always perform a full round-trip and verify the final active state.
- Do not expose secret-bearing dashboard APIs publicly without auth. Commodity CSV/JSON can be public because they are intentionally anonymous Power BI inputs.
- Avoid broad/irreversible Stop actions. For crontab, reversible comment markers are safer than deleting lines.
- Keep this as a class-level registry. Do not create a new skill for every individual automation.

## References

- `references/2026-07-07-agentsmon-automatic-runs.md` — implementation details from the commodity ETL dashboard integration session.
- `references/2026-07-07-backup-automation-registration.md` — registering the GitHub backup automation in agentsmon and ensuring the registry itself is included in backup payloads.

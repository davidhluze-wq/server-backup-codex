---
name: agentsmon-automation-dashboard
description: Register recurring automations and persistent monitored processes in agentsmon with accurate status and safe restart controls.
version: 1.1.0
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
- A persistent Telegram/agent bridge has multiple profiles and needs safe restart monitoring without duplicate processes.
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

For a script-only (`no_agent`) job, Hermes accepts a script **name relative to `~/.hermes/scripts/`**, not an absolute project path. Keep implementation in the project and create a thin wrapper such as:

```sh
#!/bin/sh
exec /bin/sh /absolute/path/to/project/scripts/run_daily_sync.sh
```

Register the wrapper name (for example `meeting-intelligence-daily-sync.sh`) with the cron job. This keeps project code versioned in its repository while satisfying Hermes Cron's script boundary. Manually run the project runner once before scheduling it; do not schedule an untested sync.

#### Long-running research loops

For a nightly research pipeline that can outlive Hermes Cron's per-tick agent limit, do **not** run the long worker directly as the Cron script. Use a small deterministic launcher that returns promptly and starts the project-owned runner in a separate session; the runner itself must enforce a PID/lock guard and a hard end-of-window deadline.

Before enabling the recurring job, run a **queue-health canary** against the source of work. A runner that consumes one queued research topic per night must have a low-water replenisher that turns newly ingested, deduplicated evidence into queued candidates before the worker step. Verify: (1) there is at least one queued item after the canary, (2) new candidates retain a source/provenance marker to prevent duplicate research, and (3) the runner selects items deterministically (for example by priority/order). Register both the schedule and the work-window/deadline in the dashboard description so a paused or exhausted queue is observable rather than silently appearing healthy.

The dashboard should show `enabled`, `last_status`, `last_run_at`, `schedule`, and a compact description from the job prompt/script. Verify Hermes-cron discovery after creation with `agentsmon.dashboard._automation_rows()`; a row with `source: hermes-cron` is sufficient when the dashboard discovers Hermes jobs automatically, so do not add a duplicate `automatic_runs.json` entry.

#### Long-running overnight pipelines

Hermes Cron runs have a bounded agent/tick lifetime. Do not run a multi-hour pipeline directly as a `no_agent` cron script: it can be interrupted even though the underlying workload is designed to run all night.

Use this split instead:

1. Keep the real runner in its project directory. It must own a PID/lock guard, log path, an explicit time-window cutoff, and its own cleanup trap.
2. Add a short project launcher that checks the runner lock, starts the runner detached (`nohup ... </dev/null >>launcher.log 2>&1 &`), prints its PID, and exits immediately.
3. Place only a thin `0700` wrapper in `~/.hermes/scripts/` and point the Hermes cron job at the wrapper name (never arguments embedded in `script`).
4. Before scheduling, inspect the work queue itself. A healthy scheduled runner can still do no research when every queue item is `done`. Add a deterministic, idempotent replenisher that maintains a small queued backlog from new source evidence, storing a stable source marker so the same source is not re-added.
5. Verify separately: launcher exits quickly, the detached runner owns the lock, queue contains candidates, the dashboard discovers the enabled cron row, and Start/Stop leaves the final intended state active.

Do not characterize a generated research handoff as a live deployment or trading action. Preserve research-only and paper-trading safety gates in the dashboard description.

#### Content-sync automation pattern

For a recurring content export such as meeting minutes → Drive → optional CMS:

1. Generate one deterministic local artifact first (for example a daily Markdown file with a content SHA-256 comment).
2. Make the remote sink idempotent: look up the target by stable folder/file identity, store the content hash as remote metadata, and **update** the existing file instead of creating a duplicate.
3. Run the sync twice before scheduling; the first can report `changed=true`, the second must report `changed=false` with the same remote file ID.
4. Keep external publishing as an opt-in adapter. A WordPress REST adapter should require base URL, username, and Application Password, default to `draft`, persist only its post ID/content hash locally, and return a benign `configured=false` state until credentials exist. Do not schedule a job that produces recurring credential errors.
5. Keep generated artifacts, local remote-ID state, WordPress state, and logs out of Git; version only code, migrations, tests, and non-secret configuration documentation.

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

## Persistent multi-profile Telegram bridges

Treat an interactive Telegram bridge as a **persistent monitored process**, not a cron-style automatic run. Keep one configuration per bot/profile and do not put raw credentials in dashboard commands or logs.

1. **Audit safely.** Read config only through a purpose-built parser that reports booleans (`elevenlabs_stt_configured=true/false`), never broad-search credential-bearing JSON or transcript logs.
2. **Check the attach precondition.** An `agent2telegram` bridge in `attach` mode requires its target tmux session to exist. Do not loop-restart a profile whose session is absent; mark it configured/standby and start it only once the session exists.
3. **Use one idempotent launcher.** Keep a `0700` launcher under `~/.local/bin/` that checks for an existing process per config, checks the target tmux session, uses `umask 077`, and starts missing eligible bridges with `nohup`.
4. **Register the launcher as the dashboard restart action.** Update the relevant `daemons[]` item in `~/.config/agentsmon/config.json` so its restart command calls the launcher. The restart action must recover the default bridge as well as profile-specific bridges.
5. **Protect transcript logs.** Bridge logs can contain full private voice transcriptions. Set existing logs to `0600`; create new logs under `umask 077`; inspect only `Attach bridge live`, error, and health metadata during verification.
6. **Verify each layer.** Confirm config key presence as boolean, `agent2telegram doctor` bot connectivity, active process lines, target-session availability, launcher `bash -n`, JSON parsing of agentsmon config, and a startup metadata line. A live voice canary requires the owner to send a voice note; do not manufacture one or expose transcript text.

See `references/telegram-bridge-multiprofile.md` for a concise implementation and verification pattern.

## Updating proxied dashboard views

Use this pattern when changing a dashboard view served through an agentsmon proxy (for example a meeting or workflow backend), even when the change is not an automation registration:

1. Inspect the current API payload and client template before editing; identify whether the visual duplication is a separate route/view or duplicate rendering of the same data.
2. Write a focused RED test that asserts the obsolete navigation/view selector is absent and the replacement label is present. A passing replacement test alone does not prove the duplicate was removed.
3. If the replacement needs related records (for example tags for ideas created by a meeting), extend the backend payload first and run a live-data canary that validates the field shape.
4. Keep minute/detail content lazy-loaded behind the one surviving expandable view, rather than retaining a second card for the same entity.
5. Run the full test suite and syntax check, then restart only the relevant proxied backend process. Verify its listener/process and the proxy auth boundary; use authenticated UI/API verification when credentials are available.
6. When a user intentionally replaces an interaction model, update only legacy tests that assert the removed control; retain unrelated behavior coverage.

## Next.js Command Center routes vs proxied backend views

A dashboard port can serve more than one UI layer. In this environment, `/meetings` is proxied to the standalone Meeting Intelligence backend, while hash routes such as `#/meeting-ideas` and `#/meeting-timeline` are rendered by the Startup Command Center Next.js application. A change to one layer does **not** change the other.

When a user reports that a meeting/dashboard change is not visible:

1. Start from the exact URL the user supplied. Identify whether it is a backend path or a client-side hash route.
2. Inspect the actual renderer/component and API model used by that route; do not infer it from the backend process alone.
3. For a Next.js route, edit the corresponding `components/views/*` component and `lib/modules/*` normalizer if the API contract needs new fields.
4. Run the focused model/UI tests, `pnpm typecheck`, and `pnpm build` in the Next.js project.
5. Restart the real Next.js production process through a tracked process/service mechanism (not an untracked shell background wrapper), then verify the port and the exact user-facing route after auth.
6. Report a change as deployed only after the correct frontend bundle has been rebuilt and restarted. A healthy backend listener or a modified standalone template is insufficient evidence.

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

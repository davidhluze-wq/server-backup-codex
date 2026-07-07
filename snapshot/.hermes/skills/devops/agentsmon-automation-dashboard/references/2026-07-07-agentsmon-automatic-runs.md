# 2026-07-07 Agentsmon Automatic Runs Implementation Notes

## Context

The user asked that every recurring/automatic implementation be completed by adding it to the agentsmon dashboard. The dashboard must show automatic runs with an expandable Czech description and Start/Stop controls. The motivating job was the monthly commodity ETL for Power BI.

## Files touched in the session

```text
~/.agentsmon-src/agentsmon/dashboard.py
~/.local/state/agentsmon/automatic_runs.json
~/.local/state/agentsmon/agentsmon-launch.sh
~/commodity-etl/build_commodities.py
~/commodity-etl/POWERBI_QUERIES.md
```

## Registry pattern

External crontab jobs are registered in:

```text
~/.local/state/agentsmon/automatic_runs.json
```

Example:

```json
{
  "runs": [
    {
      "id": "commodity-etl-monthly",
      "name": "Commodity ETL — Power BI CSV refresh",
      "source": "crontab",
      "schedule": "0 6 1 * *",
      "command": "/usr/bin/python3 /home/david_master/commodity-etl/build_commodities.py >> /home/david_master/commodity-etl/etl.log 2>&1",
      "description": "Každý měsíc obnoví veřejný komoditní CSV/JSON feed pro Power BI...",
      "url": "http://38.19.198.4:8765/commodities.csv",
      "meta_url": "http://38.19.198.4:8765/commodities.json",
      "log": "/home/david_master/commodity-etl/etl.log"
    }
  ]
}
```

## Stop/Start implementation

External crontab Stop comments the exact line with a reversible marker:

```text
# agentsmon-disabled <id> | <original crontab line>
```

Start restores the original line exactly. Always perform a round-trip during testing and leave production jobs active unless the user explicitly asked to stop them.

Hermes cron Stop/Start should use:

```bash
hermes cron pause <job_id>
hermes cron resume <job_id>
```

## UI lesson from user correction

A native `<details>` row was not sufficient; the user reported that cron activity details were not visible. Use a real button:

```text
▸ Detail
```

When opened:

```text
▾ Skrýt
```

Details must remain open across auto-refresh. In the implementation this is done with a client-side `Set` keyed by `source|id` and re-rendering rows open if their key is present.

## Verification checklist used

```bash
PYTHONPATH=/home/david_master/.agentsmon-src python3 -m py_compile /home/david_master/.agentsmon-src/agentsmon/dashboard.py
```

Test dashboard without production auth:

```bash
TMP=$(mktemp -d)
python3 - <<'PY' "$TMP/config.json"
import json, sys
c=json.load(open('/home/david_master/.config/agentsmon/config.json'))
c['dashboard']={'host':'127.0.0.1','port':9876,'poll_seconds':1}
json.dump(c, open(sys.argv[1],'w'), ensure_ascii=False)
PY
PYTHONPATH=/home/david_master/.agentsmon-src \
AGENTSMON_CONFIG="$TMP/config.json" \
AGENTSMON_STATE=/home/david_master/.local/state/agentsmon \
python3 -m agentsmon dashboard --host 127.0.0.1 --port 9876
```

Then verify in browser/DOM that clicking `Detail` reveals text and that it remains visible after refresh. Kill the temp dashboard afterward and confirm only production `:8765` remains.

Production restart:

```bash
pkill -f 'agentsmon dashboard' || true
~/.local/state/agentsmon/agentsmon-launch.sh
ss -ltnp | grep ':8765'
```

Check that commodity ETL stayed active:

```bash
crontab -l | grep 'commodity-etl'
```

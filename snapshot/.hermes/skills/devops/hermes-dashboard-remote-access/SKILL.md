---
name: hermes-dashboard-remote-access
description: Safely start, verify, and access Hermes Dashboard from a phone or remote browser via SSH tunnel or authenticated bind.
version: 1.0.0
created_by: agent
metadata:
  hermes:
    tags: [hermes, dashboard, ssh-tunnel, mobile, troubleshooting, remote-access]
---

# Hermes Dashboard Remote Access

Use this skill when the user asks how to open Hermes Dashboard, especially from a phone, or reports a blank dashboard page.

## Default safe pattern

Start dashboard bound to localhost:

```bash
hermes dashboard --host 127.0.0.1 --port 9119 --no-open
```

Verify server-side:

```bash
curl -sS -D- http://127.0.0.1:9119/ -o /tmp/hermes-dashboard-index.html | sed -n '1,40p'
curl -sS http://127.0.0.1:9119/api/status | python3 -m json.tool | sed -n '1,80p'
ss -ltnp | grep ':9119'
```

Expected:

```text
GET / -> 200 OK
/api/status -> JSON
LISTEN 127.0.0.1:9119
```

If `--skip-build` fails with missing `web_dist`, restart without `--skip-build` so Hermes builds the UI.

## Mobile access via SSH tunnel

Because `127.0.0.1` on a phone means the phone itself, the user must enable SSH local port forwarding.

Termius / JuiceSSH / Blink example:

```text
SSH host: <server public IP>
SSH user: <server user>
Local port: 9119
Destination host: 127.0.0.1
Destination port: 9119
```

Then open in the phone's normal browser:

```text
http://127.0.0.1:9119/sessions
```

Prefer `/sessions` over bare `/` when helping a user test whether the React app loaded.

## Blank page troubleshooting

If the user says the page is blank:

1. Confirm the tunnel is active; without it the phone opens its own localhost.
2. Use a normal browser, not Telegram's embedded browser.
3. Try:

```text
http://127.0.0.1:9119/sessions
```

4. Ask user to disable content blockers or try an incognito/private tab.
5. Server-side verify assets:

```bash
curl -sS -I http://127.0.0.1:9119/assets/<index-js-from-html>.js
curl -sS -I http://127.0.0.1:9119/assets/<index-css-from-html>.css
```

If `/`, JS, CSS, and `/api/status` are OK server-side, the blank page is usually browser/tunnel/client-side, not a dashboard server failure.

## Public exposure warning

Do not bind the dashboard to `0.0.0.0` unless authentication and firewall/reverse proxy are configured. Dashboard can manage config, keys, sessions, cron jobs, and gateway settings.

For remote public access, require strong auth first, e.g. environment variables for basic auth plus firewall/reverse proxy. Prefer SSH tunnel for quick mobile access.
---
name: hermes-dashboard-remote-access
description: "Set up and troubleshoot Hermes Web Dashboard access from mobile/remote devices: SSH tunnels, public bind with basic auth, systemd service, and auth-gate pitfalls."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, dashboard, mobile, ssh-tunnel, basic-auth, systemd, remote-access]
    created_by: agent
---

# Hermes Dashboard Remote Access

Use this skill when the user asks how to reach **Hermes Dashboard** from mobile, asks for a link, reports a blank page / cannot connect, or wants dashboard exposed publicly.

## Decision guide

Prefer safest first:

| Need | Pattern |
|---|---|
| One-off mobile access | SSH local tunnel to `127.0.0.1:9119` |
| User cannot/will not tunnel | Public bind with Basic Auth, preferably temporary |
| Long-term remote access | Reverse proxy + HTTPS + strong auth + firewall |

Do **not** expose `hermes dashboard --host 0.0.0.0` without an auth provider. Dashboard can edit config, env/API keys, cron jobs, sessions, channels, etc.

## Local / SSH tunnel path

Server:

```bash
hermes dashboard --host 127.0.0.1 --port 9119 --no-open
```

Mobile SSH app tunnel:

```text
Type: Local
Local host: 127.0.0.1
Local port: 9119
Destination host: 127.0.0.1
Destination port: 9119
SSH host: <server-ip>
SSH user: <user>
```

Open in normal Safari/Chrome, not Telegram embedded browser:

```text
http://127.0.0.1:9119/sessions
```

If mobile says it cannot connect, check whether tunnel is actually active. `127.0.0.1` on the phone means the phone itself unless an SSH tunnel maps it to the server.

## Public Basic Auth path

Set credentials in `~/.hermes/.env`:

```bash
HERMES_DASHBOARD_BASIC_AUTH_USERNAME=<username>
HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<strong-random-password>
HERMES_DASHBOARD_BASIC_AUTH_SECRET=<32+ random bytes/base64>
```

Start public dashboard:

```bash
hermes dashboard --host 0.0.0.0 --port 9119 --no-open --skip-build
```

Verify:

```bash
ss -ltnp | grep ':9119'
curl -s http://127.0.0.1:9119/api/status | python3 -m json.tool | grep -E 'auth_required|auth_providers'
curl -I 'http://<server-ip>:9119/login?next=/sessions'
```

Expected:

```text
0.0.0.0:9119 listening
auth_required: true
auth_providers: ["basic"]
/login?next=/sessions returns 200
/sessions unauthenticated redirects to /login?next=%2Fsessions
```

Use direct link:

```text
http://<server-ip>:9119/login?next=/sessions
```

## Systemd user service

Create `~/.config/systemd/user/hermes-dashboard.service`:

```ini
[Unit]
Description=Hermes Dashboard public web UI
After=network-online.target

[Service]
Type=simple
EnvironmentFile=%h/.hermes/.env
ExecStart=%h/.hermes/hermes-agent/venv/bin/hermes dashboard --host 0.0.0.0 --port 9119 --no-open --skip-build
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Enable:

```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-dashboard.service
systemctl --user status hermes-dashboard.service --no-pager
```

## Pitfalls

- `--skip-build` fails if `hermes_cli/web_dist` does not exist. Run once without `--skip-build` to build assets, then use `--skip-build` for services.
- Blank page usually means assets/JS did not load or browser issue. Probe `/`, `/assets/...js`, and `/api/status` with `curl`; try Safari/Chrome instead of Telegram embedded browser.
- `HEAD /` may return `405`; use `GET /` for real checks.
- If basic auth is the only provider and `/sessions` redirects to `/auth/login?provider=basic...` then 500s, the auto-SSO middleware is treating password-only basic auth like OAuth. The fix is to skip auto-SSO for providers with `supports_password=True` so `/login` renders the username/password form. See `references/basic-auth-auto-sso.md`.
- Public HTTP sends the password over plaintext. Treat public HTTP as temporary; use HTTPS/reverse proxy for long-term.

## Verification checklist

- [ ] Dashboard process/service running.
- [ ] Port listening on intended bind address.
- [ ] `/api/status` reports `auth_required: true` for public binds.
- [ ] `/api/auth/providers` lists `basic` with `supports_password: true`.
- [ ] `/login?next=/sessions` renders a sign-in form.
- [ ] `POST /auth/password-login` returns `{"ok":true,"next":"/sessions"}` and sets session cookies.
- [ ] User has exact URL, username, and one-time/strong password.

## References

- `references/basic-auth-auto-sso.md` — session-specific diagnosis/fix for password-only basic auth being auto-redirected through OAuth `/auth/login`.
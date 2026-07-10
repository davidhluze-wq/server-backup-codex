# Activate LANA on a new VPS

This package is source code and configuration only. It does not include credentials, users,
research records, signals, trades, or P&L history. A fresh installation starts with an empty
database and paper/research mode.

## 1. Prepare the server

Install PostgreSQL, Python 3, a reverse proxy such as Caddy or Nginx, and Git. Create a dedicated
non-root user named `lana`, then place this directory at `/home/lana/lana-research`.

```bash
sudo -u postgres createuser --pwprompt lana_user
sudo -u postgres createdb --owner=lana_user lana
cd /home/lana/lana-research
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
psql "postgresql://lana_user@127.0.0.1:5432/lana" -f sql/schema.full.sql
```

## 2. Add protected local configuration

Create `/etc/lana/lana.env` from `.env.example`, set a strong `DATABASE_URL`, and set ownership to
`root:lana` with mode `640`. Create `/home/lana/lana-research/.auth` from `.auth.example` with a
new username and password hash, then set mode `600`.

Leave `LANA_HAW`, `LANA_SYNTH`, and `LANA_RESEARCHER` set to `0` until optional HumanAgentWiki and
agent integrations have been installed and reviewed.

## 3. Start the dashboard

Copy `deploy/lana-research.service.example` to
`/etc/systemd/system/lana-research.service`, review the paths and user, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lana-research
curl -u lana-admin:YOUR_PASSWORD http://127.0.0.1:8811/api/health
```

Expose it only through an HTTPS reverse proxy. Do not publish port 8811 directly to the internet.

## 4. Optional nightly research

After the base dashboard and PostgreSQL connection work, install
`deploy/lana-nightly.cron.example` for the `lana` user. Enable optional integrations one by one in
`/etc/lana/lana.env`; the first deployment should remain paper/research only.

## What must be configured separately

- PostgreSQL database and `DATABASE_URL`
- Basic-auth username and password hash in `.auth`
- HTTPS reverse proxy and DNS
- Optional HumanAgentWiki, agent access, Telegram notifications, and any model credentials

Never copy credentials or live trading data from another server into this installation.

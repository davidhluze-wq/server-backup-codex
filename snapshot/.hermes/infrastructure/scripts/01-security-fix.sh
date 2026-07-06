#!/usr/bin/env bash
# 01 — Security hardening pro vm12890  (SPOUSTIS TY, vyzaduje sudo + schvaleni)
#
# OPRAVENO proti realite (2026-07-05):
#   - :8765 (agentsmon) i :8808 (humanagentwiki-web) UZ MAJI Basic Auth (HTTP 401).
#   - Postgres :5432 posloucha jen na 127.0.0.1 (zvenku NEDOSTUPNY).
#   => Puvodni "porty bez auth + expozice Postgresu" byl PREHNANY.
#
# REALNE zbyva doresit:
#   1) TLS  — Basic Auth ted jde pres NESIFROVANE HTTP (creds v plaintextu). Caddy = HTTPS.
#   2) Firewall — ufw NENI nainstalovan; :8765/:8808 visi na 0.0.0.0.
#   3) Postgres default heslo humanagentwiki/humanagentwiki (localhost, nizke riziko, presto zmenit).
#
# Delej to jako male overene kroky. Nic tady nebezi automaticky — je to
# pruvodce; odkomentuj/uprav bloky a spousti je vedome.
set -euo pipefail
echo "Tento skript je pruvodce. Cti komentare, spoustej bloky vedome." && exit 0

# ---------------------------------------------------------------------------
# KROK 0 — stav (nic nemeni)
sudo ss -tlnp | grep -E '0\.0\.0\.0|\[::\]' | grep -E '8765|8808|8802|5432|8642' || true
sudo ufw status verbose 2>/dev/null || echo "ufw neni nainstalovan"

# ---------------------------------------------------------------------------
# KROK 1 — Caddy (TLS + necha existujici Basic Auth backendu, jen zabali do HTTPS)
sudo apt update && sudo apt install -y caddy
# Bez vlastni domeny: pouzij sslip.io (real cert) NEBO tls internal (self-signed).
# Priklad Caddyfile pro IP 38.19.198.4 pres sslip.io:
#   38-19-198-4.sslip.io {
#       reverse_proxy /mon*  127.0.0.1:8765
#       reverse_proxy /wiki* 127.0.0.1:8808
#   }
# (Basic Auth uz resi samotne sluzby; Caddy tu pridava jen TLS. Pripadne pridej
#  i caddy `basic_auth` jako druhou vrstvu.)
# sudo nano /etc/caddy/Caddyfile ; sudo systemctl restart caddy
# sudo systemctl status caddy --no-pager

# ---------------------------------------------------------------------------
# KROK 2 — firewall (ufw): ven jen SSH + HTTPS(+80 pro ACME)
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp        # jen pro ACME cert challenge
sudo ufw enable
sudo ufw status numbered
# Po tomhle jsou :8765/:8808/:8802/:5432 z internetu nedostupne (jen pres Caddy/localhost).

# ---------------------------------------------------------------------------
# KROK 3 — Postgres: pryc s default heslem
# sudo -u postgres psql -c "ALTER USER humanagentwiki WITH PASSWORD 'DLOUHE-NAHODNE';"
# pak najdi a nahrad connection string (heslo NE do gitu):
grep -rl 'humanagentwiki/humanagentwiki\|humanagentwiki:humanagentwiki' ~/.hermes ~/humanagentwiki 2>/dev/null || true
# restartuj humanagentwiki a over, ze RAG/MCP jede.

# ---------------------------------------------------------------------------
# KONTROLA na zaver
sudo ss -tlnp | grep -E '0\.0\.0\.0' | grep -E '8765|8808|5432' || echo "OK: nic verejne na tech portech"
curl -s http://38.19.198.4:8765 --max-time 5 -o /dev/null && echo "POZOR: jeste dostupne zvenku" || echo "OK: zvenku zavreno"

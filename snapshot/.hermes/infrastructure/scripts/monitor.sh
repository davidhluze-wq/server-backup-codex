#!/usr/bin/env bash
# Infra Monitor — zero-LLM (nestoji tokeny). Na cron kazdych 5 min.
# Kontroluje ze klicove porty/procesy ziji; pri vypadku posle alert do Telegramu
# pres `agent2telegram notify` (owner bot). Kdyz je vse OK, mlci (zadny spam).
#
# Cron (Hermes cron nebo crontab):
#   */5 * * * * /home/david_master/.hermes/infrastructure/scripts/monitor.sh
#
# Pozn.: HTTP 401 u agentsmon/humanagentwiki = sluzba BEZI (ma Basic Auth) -> OK.
set -uo pipefail

A2T_PY="/usr/bin/env PYTHONPATH=/home/david_master/.agent2telegram-src /usr/bin/python3 -m agent2telegram notify"

# port:popisek  (listener musi existovat v `ss -tln`)
PORT_CHECKS=(
  "5432:postgres"
  "8802:mcp-humanagentwiki"
  "8765:agentsmon"
  "8808:humanagentwiki-web"
  "8642:hermes-health"
)
# pgrep pattern:popisek  (proces musi bezet)
PROC_CHECKS=(
  # Hermes entrypoint changed from hermes_cli.main to the console command.
  "hermes gateway run:hermes-gateway"
  "agent2telegram run:telegram-bridge"
)

down=()

for c in "${PORT_CHECKS[@]}"; do
  port="${c%%:*}"; label="${c##*:}"
  if ! ss -tln 2>/dev/null | grep -qE "[:.]${port}[[:space:]]"; then
    down+=("port ${port} (${label})")
  fi
done

for c in "${PROC_CHECKS[@]}"; do
  pat="${c%%:*}"; label="${c##*:}"
  if ! pgrep -f "${pat}" >/dev/null 2>&1; then
    down+=("proc ${label}")
  fi
done

if (( ${#down[@]} > 0 )); then
  msg="[infra-monitor] DOWN: ${down[*]}"
  ${A2T_PY} "${msg}" >/dev/null 2>&1 || true
  logger -t infra-monitor "${msg}" 2>/dev/null || true
  exit 1
fi
exit 0

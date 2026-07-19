#!/bin/sh
# Spustí dlouhý noční LANA runner odděleně od krátkého Hermes cron ticku.
set -eu
LR="${LANA_ROOT:-$HOME/lana-research}"
RUNNER="$LR/scripts/nightly_lana.sh"
LOCK="$LR/.nightly.lock"
LOG="$LR/nightly-launcher.log"

if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "lana-nightly: již běží (pid $(cat "$LOCK"))"
  exit 0
fi

nohup "$RUNNER" </dev/null >>"$LOG" 2>&1 &
pid=$!
echo "lana-nightly: spuštěn pid=$pid (runner skončí nejpozději v 05:00)"

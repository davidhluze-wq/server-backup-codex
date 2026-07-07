#!/usr/bin/env bash
set -uo pipefail
BASE="$HOME/.hermes/security-audit-lite"
LOG="$BASE/auto-update.log"
LOCK="$BASE/auto-update.lock"
mkdir -p "$BASE"
exec 9>"$LOCK"
if ! flock -n 9; then exit 0; fi
{
  echo "[$(date -Is)] auto-update start"
} >> "$LOG"

if ! command -v apt-get >/dev/null 2>&1; then
  echo "⚠️ Auto-update: apt-get není dostupný, aktualizace přeskočena."
  echo "[$(date -Is)] no apt-get" >> "$LOG"
  exit 0
fi

PRE_UPGRADABLE="$(apt list --upgradable 2>/dev/null | sed '1d' | sed -n '1,80p')"

# Do not require broad `sudo -n true`; sudoers is intentionally limited to
# apt-get update/upgrade only. Probe the exact command this script needs.
sudo -n apt-get update >> "$LOG" 2>&1 || {
  if [ -n "$PRE_UPGRADABLE" ]; then
    PRE_COUNT="$(printf '%s\n' "$PRE_UPGRADABLE" | sed '/^$/d' | wc -l | tr -d ' ')"
    echo "⚠️ Auto-update: čeká $PRE_COUNT balíčků, ale chybí passwordless sudo pro apt-get update/upgrade. Zkontroluj /etc/sudoers.d/hermes-auto-update"
  fi
  echo "[$(date -Is)] sudo apt-get update unavailable" >> "$LOG"
  exit 0
}

# apt index is fresh now.

UPGRADABLE="$(apt list --upgradable 2>/dev/null | sed '1d' | sed -n '1,80p')"
if [ -z "$UPGRADABLE" ]; then
  echo "[$(date -Is)] no upgrades" >> "$LOG"
  exit 0
fi

BEFORE_COUNT="$(printf '%s\n' "$UPGRADABLE" | sed '/^$/d' | wc -l | tr -d ' ')"
printf '[%s] upgrades before: %s\n%s\n' "$(date -Is)" "$BEFORE_COUNT" "$UPGRADABLE" >> "$LOG"

if ! sudo -n apt-get -y upgrade >> "$LOG" 2>&1; then
  echo "🔴 Auto-update selhal při apt-get upgrade. Čeká $BEFORE_COUNT balíčků. Log: $LOG"
  exit 0
fi

AFTER="$(apt list --upgradable 2>/dev/null | sed '1d' | sed -n '1,80p')"
AFTER_COUNT="$(printf '%s\n' "$AFTER" | sed '/^$/d' | wc -l | tr -d ' ')"
REBOOT="no"
if [ -e /var/run/reboot-required ]; then REBOOT="yes"; fi

printf '[%s] upgrades after: %s reboot=%s\n' "$(date -Is)" "$AFTER_COUNT" "$REBOOT" >> "$LOG"

if [ "$AFTER_COUNT" = "0" ]; then
  echo "🟢 Auto-update hotový: aktualizováno $BEFORE_COUNT balíčků. Reboot required: $REBOOT"
else
  echo "🟡 Auto-update částečný: aktualizováno něco z $BEFORE_COUNT balíčků, stále čeká $AFTER_COUNT. Reboot required: $REBOOT. Log: $LOG"
fi

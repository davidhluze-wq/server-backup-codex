#!/bin/sh
# Lana — nocni token-setrny beh. Cron ho pousti v 00:00; tvrdy strop do 05:00.
# Jednou denne, zamek proti prekryvu. Harvest = zero-LLM (zadne tokeny), synteza = mala/levna.
#   LANA_HARVEST_LIMIT (120)  LANA_SYNTH (1=zap)  LANA_SYNTH_LIMIT (8)  LANA_EMBED (0)
set -u
LR="${LANA_ROOT:-$HOME/lana-research}"
HAW="${HUMANAGENTWIKI_HOME:-$HOME/humanagentwiki}"
LOG="$LR/nightly.log"
LOCK="$LR/.nightly.lock"
PY="${LANA_PYTHON:-$HAW/.venv/bin/python}"
export PATH="$HOME/.local/bin:/usr/bin:/bin"
A2T="/usr/bin/env PYTHONPATH=${AGENT2TELEGRAM_SOURCE:-$HOME/.agent2telegram-src} /usr/bin/python3 -m agent2telegram notify"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "$(ts) $1" >> "$LOG"; }

# --- zamek (jeden beh) ---
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  log "uz bezi (lock) — koncim"; exit 0
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

# --- jen v okne 00:00–05:00 (cron pousti v 00:00; mimo-okno rucni spusteni se ignoruje) ---
h=$(date +%H)
if [ "$h" -ge 5 ]; then log "mimo okno (cas ${h}h, okno 00-05) — koncim"; exit 0; fi

# --- okno: tvrdy strop do 05:00 ---
now=$(date +%s)
end=$(date -d 'today 05:00' +%s 2>/dev/null) || end=$((now + 18000))
[ "$end" -le "$now" ] && end=$(date -d 'tomorrow 05:00' +%s 2>/dev/null || echo $((now + 18000)))
budget=$((end - now))
if [ "$budget" -lt 60 ]; then log "mimo okno (<60s do 05:00) — koncim"; exit 0; fi

# --- DATABASE_URL z humanagentwiki/.env ---
set -a; . "$HAW/.env" 2>/dev/null; set +a
if [ -z "${DATABASE_URL:-}" ]; then log "CHYBI DATABASE_URL — koncim"; exit 1; fi

log "START (budget ${budget}s do 05:00)"

# --- 1) HARVEST (zero LLM) ---
EMBEDFLAG=""; [ "${LANA_EMBED:-0}" = "1" ] && EMBEDFLAG="--embed"
timeout "$budget" "$PY" "$LR/scripts/harvest_trading_lit.py" --limit "${LANA_HARVEST_LIMIT:-120}" $EMBEDFLAG >> "$LOG" 2>&1
log "harvest rc=$?"
# EllioTrades YouTube tipy (zero-LLM, inkrementalni) — podpira strategii aschenbrenner-ellio
if [ "${LANA_ELLIO:-1}" = "1" ]; then
  timeout 120 "$PY" "$LR/scripts/harvest_ellio_youtube.py" >> "$LOG" 2>&1
  log "ellio harvest rc=$?"
fi

# --- 2) SYNTEZA (mala, levna, zastropovana) ---
now=$(date +%s); rem=$((end - now))
if [ "${LANA_SYNTH:-1}" = "1" ] && [ "$rem" -gt 120 ]; then
  timeout "$rem" "$PY" "$LR/scripts/synthesize_findings.py" --limit "${LANA_SYNTH_LIMIT:-8}" >> "$LOG" 2>&1
  log "synth rc=$?"
else
  log "synth preskocen (vypnut nebo malo casu)"
fi

# --- 3) KURACE / KONTROLA (zero-LLM dedup + cross-korroborace + topic + rank + strategie + QA) ---
#     Jednou denne po kazdem zapisu: cisti, sjednocuje a strukturuje RAG pro budouci trading crew.
now=$(date +%s); rem=$((end - now))
if [ "$rem" -gt 60 ]; then
  timeout "$rem" "$PY" "$LR/scripts/curate_lana.py" >> "$LOG" 2>&1
  log "curate rc=$?"
else
  log "curate preskocen (malo casu)"
fi

# --- 4) RESEARCHER (fáze 2): jedno téma z fronty, jen pokud zbývá dost času (>45 min) ---
now=$(date +%s); rem=$((end - now))
if [ "${LANA_RESEARCHER:-1}" = "1" ] && [ "$rem" -gt 2700 ]; then
  timeout "$rem" "$PY" "$LR/scripts/run_researcher.py" >> "$LOG" 2>&1
  log "researcher rc=$?"
else
  log "researcher preskocen (vypnut nebo malo casu)"
fi

# --- 5) HAW SYNC: Lanina literatura + zjisteni -> HAW knowledge graf ---
if [ "${LANA_HAW:-1}" = "1" ]; then
  "$PY" "$LR/scripts/lana_to_haw.py" >> "$LOG" 2>&1
  ( cd "$HAW" && "$PY" cli.py index >> "$LOG" 2>&1 )
  log "haw-sync rc=$?"
fi
log "END"

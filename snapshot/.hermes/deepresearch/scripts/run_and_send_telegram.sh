#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 1 ]; then
  echo "Usage: $0 'research topic' [telegram-target] [mode: auto|scientific|market|software]" >&2
  exit 2
fi
TOPIC="$1"
TARGET="${2:-telegram}"
MODE="${3:-auto}"
OUT="$($HOME/.hermes/deepresearch/scripts/run_deepresearch.py "$TOPIC" --mode "$MODE")"
RUN_DIR="$(printf '%s\n' "$OUT" | sed -n '1p')"
STATUS="$(printf '%s\n' "$OUT" | sed -n '2p' | sed 's/^status=//')"
MSG_FILE="$RUN_DIR/telegram_summary.md"
cat > "$MSG_FILE" <<EOF
✅ DeepResearch dokončen

Status: $STATUS
Run: $RUN_DIR

Final report:
$RUN_DIR/final_report.md

Quality review:
$RUN_DIR/quality_review.md

PDF:
MEDIA:$RUN_DIR/final_report.pdf
EOF
hermes send --to "$TARGET" --file "$MSG_FILE" --quiet
printf '%s\n' "$RUN_DIR"
printf 'status=%s\n' "$STATUS"

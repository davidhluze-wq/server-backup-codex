#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <url> <region> <business> [telegram-target]" >&2
  exit 2
fi
URL="$1"
REGION="$2"
BUSINESS="$3"
TARGET="${4:-telegram}"
OUT="$($HOME/.hermes/marketing-crew/scripts/run_marketing_audit.py --url "$URL" --region "$REGION" --business "$BUSINESS")"
RUN_DIR="$(printf '%s\n' "$OUT" | sed -n '1p')"
STATUS="$(printf '%s\n' "$OUT" | sed -n '2p' | sed 's/^status=//')"
MSG_FILE="$RUN_DIR/telegram_summary.md"
cat > "$MSG_FILE" <<EOF
✅ Marketing Crew audit dokončen

Status: $STATUS
URL: $URL
Region: $REGION
Run: $RUN_DIR

Report:
$RUN_DIR/audit_report.md

Quality review:
$RUN_DIR/quality_review.md

PDF:
MEDIA:$RUN_DIR/audit_report.pdf
EOF
hermes send --to "$TARGET" --file "$MSG_FILE" --quiet
printf '%s\n' "$RUN_DIR"
printf 'status=%s\n' "$STATUS"

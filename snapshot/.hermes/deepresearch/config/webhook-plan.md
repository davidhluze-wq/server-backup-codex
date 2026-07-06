# DeepResearch Webhook Plan

Status: prepared, not enabled.

Reason: Hermes webhook platform is currently disabled. Enabling it would expose/listen on a webhook port, which is a global operational change. Per safety rule, this should only be enabled after explicit confirmation of host/port/public exposure.

## Recommended route

Route name:

```text
deepresearch
```

Expected JSON payload:

```json
{
  "event": "deepresearch.run",
  "topic": "Research task text here"
}
```

Suggested command after user confirms webhook exposure:

```bash
hermes gateway setup
# enable webhook platform, recommended port 8644, with generated HMAC secret

hermes webhook subscribe deepresearch \
  --description 'Start Hermes DeepResearch run from webhook payload; expects JSON with topic field.' \
  --events deepresearch.run \
  --deliver telegram \
  --prompt 'Spusť Hermes DeepResearch pro zadání z webhook payloadu: {topic}. Použij příkaz ~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "{topic}" telegram. Po dokončení vrať stručně cestu k runu a status.'
```

## Primary Telegram path already works

For now, Telegram-first operation is via:

```bash
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "Tvoje research zadání" telegram
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "Tvoje research zadání" telegram scientific
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "Tvoje research zadání" telegram market
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "Tvoje research zadání" telegram software
```

This runs the full orchestration, creates markdown/html/pdf, uploads selected artefacts to Google Drive safe folder, and sends Telegram message with run path + PDF attachment reference.

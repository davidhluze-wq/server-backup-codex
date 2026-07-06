# Marketing Crew Webhook Plan

Status: prepared, not enabled.

Webhook platform is currently disabled. Enabling it would expose/listen on a webhook port, so keep it disabled until explicitly approved.

Expected payload:

```json
{
  "event": "marketing_audit.run",
  "url": "https://example.com",
  "region": "Czech Republic",
  "business": "B2B service description"
}
```

Telegram-first local command already exists:

```bash
~/.hermes/marketing-crew/scripts/run_and_send_telegram.sh "https://example.com" "Czech Republic" "business description" telegram
```

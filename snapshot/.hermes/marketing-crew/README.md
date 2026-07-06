# Hermes Marketing Crew

CrewAI-inspired multi-agent marketing audit workflow for websites, products and regional competitors.

Concepts borrowed at the architecture level from CrewAI-style orchestration:

- explicit agents with role/goal/backstory-like prompt files,
- explicit tasks and dependencies,
- manager/synthesis step,
- sequential + parallel phases,
- audit artefacts on disk for later review.

This is implemented natively in Hermes as a transparent file-based runner, not as a CrewAI dependency.

## Quick run

```bash
~/.hermes/marketing-crew/scripts/run_marketing_audit.py \
  --url https://example.com \
  --region "Czech Republic" \
  --business "short description"
```

Telegram-first:

```bash
~/.hermes/marketing-crew/scripts/run_and_send_telegram.sh \
  https://example.com \
  "Czech Republic" \
  "short business description" \
  telegram
```

Outputs are in:

```text
~/.hermes/marketing-crew/runs/<timestamp-domain>/
```

Every run produces markdown, HTML/PDF, a deterministic website probe, a run manifest and index entries.

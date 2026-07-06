# 2026-07-03 Marketing Crew MVP Implementation Note

## Context

The user asked for another agent group: a marketing team inspired by `joaomdmoura/crewai` / CrewAI-style multi-agent orchestration. Required capabilities:

- audit websites,
- identify weak spots, SEO issues, inconsistencies, non-working features, bugs, marketing weaknesses,
- research regional competition,
- compare basic services/products against competitors,
- produce a PDF audit report and improvement plan split into short / medium / long term.

## Implemented Path

Created a native Hermes implementation rather than installing CrewAI as a dependency. The durable export layer lives at:

```text
~/.hermes/marketing-crew/
```

Key files:

```text
README.md
SETUP_REPORT.md
config/workflow.md
config/agent-profiles.md
config/audit-rules.md
config/task-template.md
config/webhook-plan.md
prompts/website-auditor.md
prompts/seo-content.md
prompts/competitor-market.md
prompts/messaging-conversion.md
prompts/strategy-synthesizer.md
prompts/quality-reviewer.md
scripts/website_probe.py
scripts/export_report.py
scripts/run_marketing_audit.py
scripts/run_and_send_telegram.sh
```

## Important Design Choices

- CrewAI is used as an architecture inspiration only: agents/tasks/crew/manager/process. No runtime dependency on CrewAI.
- Four specialists run in parallel, then manager and reviewer run sequentially.
- Model mix mirrors the DeepResearch setup:
  - GPT-5.5 for SEO/content and messaging/final-style writing.
  - Claude Opus for QA, competitor research, synthesis, and quality review.
- A local deterministic probe runs before LLM stages. This reduces hallucination and gives concrete evidence for the final report.
- PDF export uses a simple built-in PDF writer so it works without Chromium/weasyprint/reportlab. It is audit-valid, not design-polished.
- Telegram wrapper exists; webhook is only a plan because enabling a new webhook listener/port requires explicit approval.

## Deterministic Probe Outputs

`website_probe.py` writes:

```text
website_probe.md
website_probe.json
```

It collects HTTP status, metadata, headings, link samples/status, image alt counts, forms/inputs, robots/sitemap, text sample, and a hash. It deliberately avoids login, form submission, and intrusive security checks.

## Smoke Test

Smoke test command used:

```bash
~/.hermes/marketing-crew/scripts/run_marketing_audit.py \
  --url https://example.com \
  --region "Global" \
  --business "Smoke test placeholder website" \
  --focus "minimal smoke test of marketing crew pipeline" \
  --slug example-com-smoke \
  --timeout 180 \
  --no-upload
```

Result:

```text
/home/david_master/.hermes/marketing-crew/runs/20260703-065502-example-com-smoke
status=success
website_probe status=200 links=1 bad=0
PDF document, version 1.4, 6 pages
known_issues=[]
```

Generated smoke artifacts included `audit_report.md`, `audit_report.html`, `audit_report.pdf`, `quality_review.md`, `run_manifest.json`, `website_probe.json`, and `website_probe.md`.

## Future Improvements

1. Add optional browser-driven QA mode using the `dogfood` skill pattern for screenshots and click-through evidence.
2. Add Lighthouse/PageSpeed adapter if Chrome/Lighthouse is available.
3. Add business-type templates: local service, e-commerce, B2B SaaS, automotive, healthcare.
4. Enable webhook only after explicit approval for listener/port.
5. Improve PDF rendering if Chromium or weasyprint becomes available.

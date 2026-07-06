# 2026-07-02 DeepResearch production extension: GPT-5.5 + Claude Opus + Drive + Telegram

## Context

The user wanted Hermes to choose the best low-maintenance production direction for the DeepResearch orchestration, with ChatGPT 5.5 combined with Claude Opus, robust citations, PDF/Google Drive output, Telegram-first operation, and optionally a webhook.

## Durable lessons

### Preferred architecture

Use the explicit Python audit wrapper as the primary runner when the workflow requires exportable files and extra stages beyond `hermes kanban swarm`:

```text
Research A/B in parallel -> Arbitrator -> deterministic URL audit -> LLM Source Auditor -> Final Writer -> Quality Reviewer -> exports
```

Keep `hermes kanban swarm` as a later backend/adapter for long projects, not the first production path.

### Role/model mapping that worked

Create Hermes profiles and call them explicitly with `hermes -p <profile> chat ...`:

```text
deepresearch-gpt55          openai-codex / gpt-5.5
deepresearch-claude-opus    anthropic / claude-opus-4-8
```

Working mapping:

| Role | Profile |
|---|---|
| Research A | deepresearch-gpt55 |
| Research B | deepresearch-claude-opus |
| Arbitrator | deepresearch-claude-opus |
| Source Auditor | deepresearch-claude-opus |
| Final Writer | deepresearch-gpt55 |
| Quality Reviewer | deepresearch-claude-opus |

Add fallback to `deepresearch-gpt55`; record any fallback in `known_issues` and `logs/<role>.command.json`.

### Claude Opus model id

`claude-opus-4` and `claude-opus-4-20250514` returned 404 in this environment. `claude-opus-4-8` worked via the Anthropic provider.

This is a provider/model-id note, not a permanent universal rule; re-check live docs if it stops working.

### Robust citation schema

Use this evidence table for key claims:

```markdown
| Claim | Evidence | Source title | URL/DOI | Source type | Date / year | Accessed at | Confidence | Notes |
```

Missing title/date/accessed fields should be explicitly marked `unknown`, then penalized by Source Auditor.

### Deterministic URL audit helper

A useful helper extracts URLs from `research_a.md`, `research_b.md`, `arbitration.md`, `source_audit.md`, `final_report.md`, probes URL status/content-type/title, hashes the first response chunk, and writes:

```text
source_url_audit.md
source_url_audit.json
```

The LLM Source Auditor then reads these files for semantic assessment.

### Export + Drive

When Google Drive is authorized with a safe folder, export:

```text
final_report.md
final_report.html
final_report.pdf
quality_review.md
run_manifest.json
export_manifest.json
```

Upload only to the approved safe folder unless the user explicitly says otherwise. A simple valid PDF is acceptable for audit output if no richer renderer is installed; label it as a basic PDF layout.

### Telegram-first wrapper

Provide a wrapper like:

```bash
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "Research topic" telegram
```

It should run the orchestration, upload artifacts, and send a short Telegram completion message containing status, run path, final report path, quality review path, and PDF reference.

### Webhook safety

Do not enable webhook listener or expose a new port silently. If webhook is disabled, create `config/webhook-plan.md` with:

- route name, e.g. `deepresearch`,
- expected JSON payload,
- exact `hermes webhook subscribe ...` command,
- note that enabling requires explicit confirmation of host/port/public exposure.

## Verification used

- `hermes profile list`
- direct one-shot profile smoke tests for GPT-5.5 and Claude Opus
- `python3 -m py_compile` for scripts
- run manifest JSON validation
- inspect `logs/*.command.json` for requested/used profile and fallback status
- confirm PDF with `file final_report.pdf`
- confirm Drive upload via `export_manifest.json`

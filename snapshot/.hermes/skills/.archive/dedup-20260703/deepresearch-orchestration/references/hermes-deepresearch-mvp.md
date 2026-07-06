# Hermes DeepResearch MVP Session Reference

This reference captures a concrete implementation session for a durable Hermes deepresearch orchestration. Use it as a pattern, not as a one-off task log.

## User goal

Create an audit-ready multi-agent deepresearch system in Hermes with:

- parallel research agents,
- arbitrator/verifier,
- source auditor,
- final writer,
- quality reviewer,
- file-based outputs that a Codex Master/controller can read,
- Telegram-first operation,
- optional webhook plan,
- Google Drive safe-folder export.

## Validated environment observations

- Hermes Agent v0.17.0.
- Active default model/provider: `gpt-5.5` via `openai-codex`.
- `hermes kanban swarm` exists and supports `parallel workers → verifier → synthesizer`.
- Only one default profile initially existed, so the implementation created dedicated research profiles.
- Google Drive safe folder already existed and was used for uploads: `Hermes Safe Folder` ID `1DELdcngk0lUfjiLuxFXOimB4xB8_2wql`.
- Webhook platform was not enabled; no public port was opened.

## Filesystem layout created

```text
~/.hermes/deepresearch/
  README.md
  SETUP_REPORT.md
  index.jsonl
  index.md
  config/
    workflow.md
    agent-profiles.md
    quality-rules.md
    source-rules.md
    task-template.md
    review-template.md
    webhook-plan.md
    modes/scientific.md
    modes/market.md
    modes/software.md
  prompts/
    researcher-a.md
    researcher-b.md
    arbitrator.md
    source-auditor.md
    final-writer.md
    quality-reviewer.md
  scripts/
    run_deepresearch.py
    source_url_audit.py
    export_final.py
    rebuild_index.py
    run_and_send_telegram.sh
  runs/<timestamp-slug>/...
```

## Profiles created

Commands used:

```bash
hermes profile create deepresearch-gpt55 --clone --no-alias --description "DeepResearch role profile for audit-oriented multi-agent research"
hermes profile create deepresearch-claude-opus --clone --no-alias --description "DeepResearch role profile for audit-oriented multi-agent research"

hermes -p deepresearch-gpt55 config set model.provider openai-codex
hermes -p deepresearch-gpt55 config set model.default gpt-5.5
hermes -p deepresearch-gpt55 config set model.base_url https://chatgpt.com/backend-api/codex

hermes -p deepresearch-claude-opus config set model.provider anthropic
hermes -p deepresearch-claude-opus config set model.default claude-opus-4-8
```

Validation commands:

```bash
hermes -p deepresearch-gpt55 chat -Q -t web --max-turns 1 -q 'Respond exactly: GPT55_PROFILE_OK'
hermes -p deepresearch-claude-opus chat -Q --max-turns 1 -t web -q 'Respond exactly: CLAUDE_OPUS_PROFILE_OK'
```

Note: older Claude Opus IDs such as `claude-opus-4` and `claude-opus-4-20250514` returned 404 in this environment; `claude-opus-4-8` worked.

## Role mapping validated

| Role | Profile |
|---|---|
| Research Agent A | `deepresearch-gpt55` |
| Research Agent B | `deepresearch-claude-opus` |
| Arbitrator / Verifier | `deepresearch-claude-opus` |
| Deterministic URL Auditor | local script |
| Source Auditor | `deepresearch-claude-opus` |
| Final Writer | `deepresearch-gpt55` |
| Quality Reviewer | `deepresearch-claude-opus` |

The runner includes fallback to `deepresearch-gpt55` if a Claude role fails and records fallback use in `known_issues`.

## Runner capabilities

`run_deepresearch.py` supports:

```bash
~/.hermes/deepresearch/scripts/run_deepresearch.py "topic"
~/.hermes/deepresearch/scripts/run_deepresearch.py "topic" --mode scientific
~/.hermes/deepresearch/scripts/run_deepresearch.py "topic" --mode market
~/.hermes/deepresearch/scripts/run_deepresearch.py "topic" --mode software
~/.hermes/deepresearch/scripts/run_deepresearch.py "topic" --no-upload
```

Important design points:

- Researchers A/B run concurrently with `ThreadPoolExecutor`.
- Downstream steps run sequentially.
- Dependency outputs are passed with head+tail truncation to avoid oversized prompts, while full files remain on disk.
- Each role writes stdout to its target markdown file and stderr/session IDs under `logs/`.
- `source_url_audit.py` extracts URLs from research/arbitration/final artifacts and probes HTTP status/title/content-type/hash.
- `export_final.py` creates `final_report.html` and a simple valid `final_report.pdf`; optionally uploads markdown/html/pdf/quality review to Drive.
- `rebuild_index.py` rebuilds `index.jsonl` and `index.md` from existing run manifests.

## Citation schema

Researchers were updated to use:

```markdown
| Claim | Evidence | Source title | URL/DOI | Source type | Date / year | Accessed at | Confidence | Notes |
```

Source auditor inventory was updated to include title, URL/DOI, type, date/year, accessed-at, HTTP/check status, and audit status.

## Validated smoke tests

### EGCG MVP test

Run path:

```text
~/.hermes/deepresearch/runs/20260702-165123-egcg-katechiny-longevity-mvp2/
```

Status: `success`.

### GPT 5.5 + Claude Opus + Drive export smoke test

Run path:

```text
~/.hermes/deepresearch/runs/20260702-180306-smoke-gpt55-claude-drive/
```

Validated:

- all roles used intended profiles,
- no fallback,
- source URL audit: `urls=11 ok=7`,
- PDF file type: `PDF document, version 1.4, 2 pages`,
- Drive uploads succeeded for final markdown/html/pdf and quality review.

### Scientific mode + index smoke test

Run path:

```text
~/.hermes/deepresearch/runs/20260702-181845-scientific-mode-index-smoke/
```

Validated:

- status: `success`,
- mode: `scientific`,
- workflow version: `0.3.0-modes-index`,
- source URL audit: `urls=12 ok=8`,
- `index.jsonl` and `index.md` updated.

## Telegram wrapper

Script:

```bash
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "topic" telegram scientific
```

Arguments:

1. topic,
2. target, default `telegram`,
3. mode, default `auto`.

It runs the full orchestration and sends a concise Telegram message with run path and PDF reference. It relies on `hermes send`.

## Webhook plan

Webhook platform was not enabled. Prepared plan file:

```text
~/.hermes/deepresearch/config/webhook-plan.md
```

Reason: enabling webhooks is a global operational change and may expose/listen on a new port. Confirm public vs local vs reverse-proxy exposure first.

## Pitfalls and fixes found

- Oversized initial researcher outputs made downstream arbitration too large/slow. Fix: add output-length constraints and head+tail truncation when passing dependencies.
- Cron/script-style commands with arguments can be misinterpreted as a literal script path in Hermes cron. Fix pattern: use wrapper scripts when a scheduler expects a script file path.
- Simple PDF export can be done without external packages via a minimal PDF writer, but quality is audit-grade only.
- Rebuilding the index from manifests is useful because older legacy runs may predate the index feature.

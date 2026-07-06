---
name: deepresearch-orchestration
description: "Build and operate audit-ready multi-agent deep research workflows in Hermes: parallel researchers, verifier/arbitrator, source audit, final writer, quality review, run manifests, indexes, Telegram/Drive delivery."
version: 1.0.0
created_by: agent
---

# DeepResearch Orchestration

Use this skill when the user asks to create, extend, debug, or run a durable **deep research system** rather than a one-off answer: parallel research agents, arbitration/verifier, source auditor, final writer, quality review, citation policy, run manifests, report export, Telegram delivery, or Codex/master-agent auditability.

## Core pattern

Prefer an audit-friendly filesystem contract over opaque chat-only output:

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
    modes/{scientific,market,software}.md
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
  runs/<timestamp-slug>/
    input.md
    research_a.md
    research_b.md
    arbitration.md
    source_url_audit.md
    source_url_audit.json
    source_audit.md
    final_report.md
    final_report.html
    final_report.pdf
    quality_review.md
    run_manifest.json
    export_manifest.json
    logs/*.json|*.txt
```

## Recommended MVP architecture

When Hermes has only one or a few profiles, a Python orchestration wrapper can be better than jumping straight to `hermes kanban swarm`, because it is easier to maintain exact run artifacts and extra review phases.

Use this DAG:

```text
USER TOPIC
  ├─ Research Agent A  — e.g. GPT-5.5 profile
  └─ Research Agent B  — e.g. Claude Opus profile
        ↓
  Arbitrator / Verifier
        ↓
  Deterministic Source URL Auditor
        ↓
  LLM Source Auditor
        ↓
  Final Writer
        ↓
  Quality Reviewer
        ↓
  Markdown/HTML/PDF + Drive/Telegram + index
```

### Profile/model mapping

If the user wants model diversity, create named Hermes profiles instead of relying on prompt-only role separation. Example mapping that worked:

| Role | Profile/model |
|---|---|
| Research A | `deepresearch-gpt55` / `gpt-5.5` |
| Research B | `deepresearch-claude-opus` / `claude-opus-4-8` |
| Arbitrator | `deepresearch-claude-opus` |
| Source Auditor | deterministic script + `deepresearch-claude-opus` |
| Final Writer | `deepresearch-gpt55` |
| Quality Reviewer | `deepresearch-claude-opus` |

Add a fallback profile (usually the known-good GPT profile) and write fallback use into `known_issues` in `run_manifest.json`.

## Run manifest schema

Each run should write a machine-readable manifest:

```json
{
  "run_id": "timestamp-slug",
  "created_at": "ISO-8601",
  "topic": "string",
  "mode": "auto|scientific|market|software|...",
  "workflow_version": "string",
  "orchestration": "python-wrapper/hermes-chat-subprocess+deterministic-source-audit+drive-export",
  "agents": {
    "research_a": "profile/model",
    "research_b": "profile/model",
    "arbitrator": "profile/model",
    "source_auditor": "profile/model",
    "final_writer": "profile/model",
    "quality_reviewer": "profile/model"
  },
  "outputs": {
    "research_a": "research_a.md",
    "research_b": "research_b.md",
    "arbitration": "arbitration.md",
    "source_url_audit": "source_url_audit.md",
    "source_audit": "source_audit.md",
    "final_report": "final_report.md",
    "quality_review": "quality_review.md"
  },
  "status": "success|partial|failed",
  "known_issues": [],
  "timings_seconds": {},
  "helpers": {}
}
```

Also maintain:

- `index.jsonl` — one JSON row per run for agents/Codex.
- `index.md` — human-readable table with created time, status, mode, run ID, topic, final/PDF/quality links.
- `scripts/rebuild_index.py` — rebuilds the index from all `runs/*/run_manifest.json` files.

## Citation rules

For robust research, require a richer evidence table than just a URL:

```markdown
| Claim | Evidence | Source title | URL/DOI | Source type | Date / year | Accessed at | Confidence | Notes |
```

Source Auditor should penalize missing `Source title`, `URL/DOI`, `Source type`, `Date/year`, or `Accessed at` on important claims. Use `unknown` explicitly rather than leaving fields blank.

Do not let final writer add claims not approved by arbitration/source audit. Final report must separate:

- facts,
- interpretation,
- uncertainty/limitations,
- practical implications,
- sources.

## Research modes

Build modes as files under `config/modes/` and inject them into every role prompt.

Starter modes:

- `scientific.md`: systematic reviews, meta-analyses, RCTs, human vs animal/in-vitro evidence, safety, dose, contraindications, evidence quality.
- `market.md`: primary company/regulator/data sources, time horizon, geography, supply chain, regulation, costs, margins, uncertainty.
- `software.md`: official docs, release notes, RFCs, GitHub issues/PRs, benchmarks with methodology, security, scaling, observability, lock-in.

Runner interface:

```bash
~/.hermes/deepresearch/scripts/run_deepresearch.py "topic" --mode scientific
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "topic" telegram market
```

## Delivery/export

For the user's preferred Telegram-first flow, provide a wrapper that:

1. runs the full orchestration,
2. writes markdown/html/pdf,
3. uploads selected artifacts to the user's Google Drive safe folder when configured,
4. sends a concise Telegram message with run path and PDF attachment/reference.

Keep Drive writes constrained to the configured safe folder unless the user explicitly directs otherwise.

## Webhook rule

Do **not** enable webhook or expose a new public port implicitly. If the user wants webhook, prepare `config/webhook-plan.md`, then ask/confirm whether it should run publicly, locally, or behind reverse proxy. Enabling a webhook platform is a global operational change.

## Common pitfalls

- First deepresearch runs can produce oversized researcher outputs. Add output-length instructions to researcher prompts and use head+tail truncation when passing dependency outputs to downstream roles. Always keep full files on disk.
- If a role-specific model profile fails, fallback can keep the run alive, but record it in `known_issues`.
- A deterministic URL auditor should not be treated as semantic proof. It checks availability/metadata/hash; LLM source audit still evaluates claim support.
- Built-in simple PDF writers are acceptable for audit PDFs but not design-quality documents. Note the limitation and optionally improve later with WeasyPrint/Chromium.

## Reference

See `references/hermes-deepresearch-mvp.md` for the concrete session implementation details, file list, commands, and validated smoke-test results.
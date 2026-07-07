---
name: hermes-deepresearch-orchestration
description: Build audit-ready Hermes DeepResearch workflows with parallel researchers, verification, source audit, final writing, quality review, manifests, and Codex Master review artifacts.
version: 1.0.0
created_by: agent
metadata:
  hermes:
    tags: [deepresearch, orchestration, hermes, multi-agent, audit, research]
    category: research
---

# Hermes DeepResearch Orchestration

Use this skill when the user asks to set up, run, debug, or extend an audit-ready deep research workflow in Hermes: parallel research agents, verifier/arbitrator, source auditor, final writer, quality reviewer, and persistent markdown/JSON outputs.

## Goals

A good DeepResearch setup is not a one-off answer. It is a reusable workflow that leaves a complete audit trail:

```text
USER TASK
  ├─ Research Agent A  ┐
  └─ Research Agent B  ┘  parallel and independent
        ↓
  Arbitrator / Verifier
        ↓
  Source Auditor
        ↓
  Final Writer
        ↓
  Quality Reviewer
        ↓
  final_report.md + quality_review.md + run_manifest.json
```

The user expects practical Czech status/reporting and explicit artifacts that an external Codex Master reviewer can inspect.

## Default File Layout

Create or maintain this export layer unless the user provides another path:

```text
~/.hermes/deepresearch/
  README.md
  SETUP_REPORT.md
  config/
    workflow.md
    agent-profiles.md
    quality-rules.md
    source-rules.md
    task-template.md
    review-template.md
    modes/
      scientific.md
      market.md
      software.md
  prompts/
    researcher-a.md
    researcher-b.md
    arbitrator.md
    source-auditor.md
    final-writer.md
    quality-reviewer.md
  scripts/
    run_deepresearch.py
  runs/
    <timestamp-slug>/
      input.md
      research_a.md
      research_b.md
      arbitration.md
      source_audit.md
      final_report.md
      quality_review.md
      run_manifest.json
      logs/
  index.jsonl
  index.md
```

Keep everything readable and editable by Codex: plain markdown, JSON, and small scripts. Maintain `index.jsonl` as the machine-readable run ledger and `index.md` as the human-readable Codex/Hermes audit index. Provide a `rebuild_index.py` helper when multiple historical runs already exist.

## Setup Procedure

1. **Load Hermes context first.** If configuring Hermes itself, load the `hermes-agent` skill and treat official docs as authoritative.
2. **Read the user's master prompt fully.** Do not infer omitted requirements.
3. **Analyze current Hermes capabilities before building:**
   - `hermes --version`
   - `hermes config path`
   - `hermes profile list`
   - `hermes tools list`
   - `hermes kanban swarm --help`
   - `hermes chat --help`
   - `hermes cron status` if scheduling may be involved
4. **Avoid global config changes unless explicitly approved.** Prefer files under `~/.hermes/deepresearch/`.
5. **Pick the simplest viable orchestration:**
   - If `hermes kanban swarm` supports the complete graph and profiles exist, use it or add an adapter.
   - If only one profile exists or the workflow needs extra sequential audit stages, use an explicit wrapper over `hermes chat -Q` and export all stage outputs.
   - Use `delegate_task` only for short interactive in-session research, not durable workflows that must survive the session.
6. **Create class-level prompts:** researcher A, researcher B, arbitrator, source auditor, final writer, quality reviewer.
7. **Run a short test.** The test verifies the workflow, not perfect research quality.
8. **Verify:** compile scripts, validate manifest JSON, check required outputs are non-empty, inspect headings and logs.
9. **Return a Setup Report** with created files, how to run, mapping, limitations, test result, recommended improvements, and Codex Master questions.

## Runner Design Notes

A minimal Python runner should:

- spawn Research A and Research B in parallel (`ThreadPoolExecutor` or equivalent),
- run arbitration, deterministic source URL audit, LLM source audit, final writer, and quality review sequentially,
- call role-specific profiles with `hermes -p <profile> chat -Q --source deepresearch-<role> --max-turns <N> -t web -q <prompt>`,
- use a mixed-model default when available: GPT-5.5/OpenAI-Codex for broad research/final writing and Claude Opus for independent research, arbitration, source audit, and quality review,
- implement a fallback profile (usually GPT-5.5) so a Claude/API outage yields a partial-but-auditable run instead of total failure,
- write each role output immediately to disk,
- write `logs/<role>.stderr.txt` and `logs/<role>.command.json` including requested profile, used profile, fallback flag, return code, and elapsed seconds,
- write `run_manifest.json` with `run_id`, `created_at`, `topic`, `mode`, `workflow_version`, `agents`, `outputs`, `status`, `known_issues`, helper outputs, and timings,
- support `--mode auto|scientific|market|software` by injecting mode-specific rules from `config/modes/` into every role prompt,
- update `index.jsonl` and `index.md` after every run; include local artifact paths and Drive links when available.

### Critical Pitfall: Prompt Size Between Stages

Research agents can produce long outputs. If you feed full `research_a.md` + `research_b.md` + later files into every downstream stage, arbitration or quality review can hang or become slow.

Mitigation:

- Add a `read_limited(path, max_chars)` helper with head+tail truncation.
- Keep full files on disk for audit.
- Mark truncation clearly in the downstream prompt:

```text
[...TRUNCATED N CHARS FOR ORCHESTRATION PROMPT; FULL FILE IS ON DISK...]
```

Also instruct researchers to keep MVP/test outputs bounded, e.g. max ~1800 words and max 8 key sources.

### Caveman internal compression

Caveman is installed on this server and DeepResearch runner supports `--internal-compression caveman|off` (default `caveman`), workflow `0.4.0-caveman-internal-efficiency`. Use caveman-lite only for internal handoffs (`research_a`, `research_b`, `arbitration`, `source_audit`): compact evidence bullets/tables, no filler, preserve URLs/DOIs/numbers/dates/uncertainty. Never apply caveman style to final `final_report.md` or `quality_review.md`; final artifacts must remain polished and audit-ready.

## Quality Rules

Every run should enforce:

1. Important factual claims need a citation or an explicit uncertainty label.
2. Primary sources beat secondary sources.
3. If sources disagree, the report must show the disagreement.
4. Never invent DOI/URL/citations.
5. Final report must not hide weak evidence.
6. Research A and B must be independent.
7. Arbitrator must decide what is allowed/rejected, not merely summarize.
8. Source Auditor must be skeptical and identify weak/inaccessible sources.
9. Quality Reviewer must be concrete and useful for Codex Master.
10. Use robust citation tables for key evidence: `Claim`, `Evidence`, `Source title`, `URL/DOI`, `Source type`, `Date/year`, `Accessed at`, `Confidence`, `Notes`. Unknown fields must be explicitly marked, not silently omitted.

## Deterministic Source Audit Pattern

For flexible but auditable source checking, combine two layers:

1. A local deterministic helper (`source_url_audit.py`) extracts URLs from research/arbitration/final files, probes HTTP status/content type/title, hashes a sampled response, and writes `source_url_audit.md` + `source_url_audit.json`.
2. The LLM Source Auditor reads those deterministic outputs and performs semantic judgment: source relevance, primary vs secondary, claim coverage, fact vs interpretation, and no-use claims.

This is preferable to a pure LLM source audit when the user wants robust citations but does not want to manage the system manually.

## Output, Drive, Telegram, and Webhook Pattern

When the user wants hands-off operation:

- Generate `final_report.md`, `final_report.html`, and a simple `final_report.pdf` even if high-end PDF tooling is not installed. A minimal PDF writer is acceptable for audit artifacts; note the limitation if typography is basic.
- Upload selected artifacts to the user's approved Google Drive safe folder only when Drive is already authorized and the user wants Drive output.
- Provide a Telegram-first wrapper such as `run_and_send_telegram.sh` that runs the full orchestration, writes all files, uploads artifacts, and sends a short Telegram completion message with paths/links/PDF attachment.
- Do **not** enable a webhook platform or expose a new port silently. If `hermes webhook list` says webhook is disabled, write `config/webhook-plan.md` with the intended route/payload/commands and ask/record that explicit confirmation is needed before enabling a listener.

## Recommended Setup Report Shape

Return or write:

```markdown
# Hermes DeepResearch Setup Report

## What Was Created
## Hermes Capability / Config Analysis
## How To Run A New Research
## Agent/Profile Mapping
## Files And Directories
## Current Limitations
## Test Run Result
## Recommended Next Improvements
## Questions For Codex Master Review
```

Include exact paths and the test run directory.

## User-Specific Preferences

For this user:

- Prefer Czech, practical reporting with concise semafor/status summaries.
- Preserve auditability: created-file list, setup report, manifest, limitations, known issues, and questions for Codex Master.
- Do not expose secrets or open new public ports during setup.
- Do not modify global Hermes config unless the user explicitly approves.

## References

- Session-specific implementation note: `references/2026-07-02-hermes-deepresearch-mvp.md`
- Production extension note: `references/2026-07-02-deepresearch-gpt55-claude-drive-telegram.md`
- Caveman internal compression note: `references/caveman-internal-compression.md`

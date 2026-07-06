# 2026-07-02 Hermes DeepResearch MVP Session Notes

## User Request

Create a durable, audit-ready Hermes DeepResearch orchestration from `/home/david_master/hermes-deepresearch-master-prompt.md` with:

- parallel Research Agent A/B,
- Arbitrator / Verifier,
- Source Auditor,
- Final Writer,
- Quality Reviewer,
- readable file export for Codex Master review,
- test run on green tea catechins / EGCG and longevity.

## Capability Findings

Environment observed during setup:

- Hermes Agent `v0.17.0 (2026.6.19)`.
- Active profile: `default` only.
- Model/provider: `gpt-5.5` via `openai-codex`.
- `hermes kanban swarm` exists and supports `parallel workers → verifier → synthesizer`.
- Available tools included `web`, `browser`, `terminal`, `file`, `code_execution`, `delegation`, and `cronjob`.

Decision: create MVP as a Python wrapper under `~/.hermes/deepresearch/scripts/run_deepresearch.py` rather than full kanban rollout, because the user required extra `Source Auditor` and `Quality Reviewer` steps plus exact export files. No global Hermes config changes were made.

## Created MVP Paths

```text
/home/david_master/.hermes/deepresearch/README.md
/home/david_master/.hermes/deepresearch/SETUP_REPORT.md
/home/david_master/.hermes/deepresearch/config/workflow.md
/home/david_master/.hermes/deepresearch/config/agent-profiles.md
/home/david_master/.hermes/deepresearch/config/quality-rules.md
/home/david_master/.hermes/deepresearch/config/source-rules.md
/home/david_master/.hermes/deepresearch/config/task-template.md
/home/david_master/.hermes/deepresearch/config/review-template.md
/home/david_master/.hermes/deepresearch/config/modes/scientific.md
/home/david_master/.hermes/deepresearch/config/modes/market.md
/home/david_master/.hermes/deepresearch/config/modes/software.md
/home/david_master/.hermes/deepresearch/prompts/researcher-a.md
/home/david_master/.hermes/deepresearch/prompts/researcher-b.md
/home/david_master/.hermes/deepresearch/prompts/arbitrator.md
/home/david_master/.hermes/deepresearch/prompts/source-auditor.md
/home/david_master/.hermes/deepresearch/prompts/final-writer.md
/home/david_master/.hermes/deepresearch/prompts/quality-reviewer.md
/home/david_master/.hermes/deepresearch/scripts/run_deepresearch.py
```

## Test Run

Successful test run:

```text
/home/david_master/.hermes/deepresearch/runs/20260702-165123-egcg-katechiny-longevity-mvp2/
status=success
```

Required outputs existed and manifest validated:

```text
input.md
research_a.md
research_b.md
arbitration.md
source_audit.md
final_report.md
quality_review.md
run_manifest.json
logs/
```

## Important Pitfall Found And Fixed

First test attempt had to be killed because downstream arbitration received too much context from long researcher outputs and ran too slowly.

Fix added to runner:

- `read_limited(path, max_chars)` helper with head+tail truncation,
- explicit truncation marker in prompts,
- tighter researcher prompt instruction for MVP: max about 1800 words and max 8 key sources.

Keep full source stage files on disk; only downstream prompt context is truncated.

## Recommended Next Steps

1. Create role-specific Hermes profiles: researcher, verifier, writer, reviewer.
2. Add a kanban adapter using `hermes kanban swarm` for production/long runs.
3. Add deterministic URL/source checker that records HTTP status, title, accessed_at, and content hash.
4. Add `--mode scientific|market|software` injection from `config/modes/`.
5. Add `index.jsonl` across runs for Codex Master navigation.
6. Optional: add PDF/Drive export only after explicit user approval.

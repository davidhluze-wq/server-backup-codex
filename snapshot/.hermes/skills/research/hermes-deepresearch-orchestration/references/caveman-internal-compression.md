# Caveman internal compression integration — DeepResearch

## Goal

Reduce token-heavy intermediate handoffs in DeepResearch without degrading final research artifacts.

## Installed package

```text
~/.hermes/vendor/caveman
~/.hermes/skills/productivity/caveman*
~/.hermes/skills/productivity/cavecrew
```

## Runner behavior

DeepResearch runner supports:

```bash
--internal-compression caveman|off
```

Default:

```text
caveman
```

Compressed internal roles:

```text
research_a
research_b
arbitration
source_audit
```

Final-quality roles are not compressed:

```text
final_report
quality_review
```

## Design rule

Use a compact local `caveman-lite` instruction for internal roles instead of loading the full caveman skill into every worker. Preserve:

- exact URLs/DOIs,
- source titles,
- dates and numbers,
- confidence/uncertainty labels,
- disagreements between sources,
- quotes, commands, code, errors.

Final `final_report.md` and `quality_review.md` must be polished, complete, audit-ready Markdown with citation tables and reviewer-useful detail.

## Verification pattern

```bash
python3 -m py_compile ~/.hermes/deepresearch/scripts/run_deepresearch.py
~/.hermes/deepresearch/scripts/run_deepresearch.py --help | grep internal-compression
```

Smoke run should record in `run_manifest.json`:

```json
{
  "workflow_version": "0.4.0-caveman-internal-efficiency",
  "internal_compression": "caveman"
}
```

Use `--internal-compression off` for A/B quality/cost comparisons or if final synthesis appears starved of evidence.
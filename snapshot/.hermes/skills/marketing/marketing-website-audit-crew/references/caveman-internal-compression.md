# Caveman internal compression integration — marketing crew

## Goal

Use `juliusbrussee/caveman` ideas to reduce internal specialist handoff tokens while preserving final client-facing audit quality.

## Installed package

```text
~/.hermes/vendor/caveman
~/.hermes/skills/productivity/caveman*
~/.hermes/skills/productivity/cavecrew
```

Installed via:

```bash
cd ~/.hermes/vendor/caveman
node bin/install.js --only hermes --minimal --non-interactive
```

## Runner behavior

Marketing runner supports:

```bash
--internal-compression caveman|off
```

Default:

```text
caveman
```

Compressed internal specialist roles:

```text
website_audit
seo_content
competitor_market
messaging_conversion
```

Final roles are explicitly not compressed:

```text
strategy_synthesizer
quality_review
```

## Design rule

Do not load the full caveman skill into every worker just to save output; that can add input prompt overhead. Instead use a compact local `caveman-lite` contract:

- no filler/pleasantries,
- compact bullets/tables,
- preserve exact URLs, numbers, errors, evidence, uncertainty labels,
- output valid Markdown,
- final `audit_report.md` and `quality_review.md` stay polished/full quality.

## Verification pattern

```bash
python3 -m py_compile ~/.hermes/marketing-crew/scripts/run_marketing_audit.py
~/.hermes/marketing-crew/scripts/run_marketing_audit.py --help | grep internal-compression
```

Smoke run should record in `run_manifest.json`:

```json
{
  "workflow_version": "0.3.0-caveman-internal-efficiency",
  "internal_compression": "caveman"
}
```

Use `--internal-compression off` for A/B quality/cost comparisons.
---
name: marketing-crew-orchestration
description: Build audit-ready Hermes marketing-crew workflows for website, SEO, UX/QA, conversion, and regional competitor audits using CrewAI-inspired multi-agent orchestration.
version: 1.0.0
created_by: agent
metadata:
  hermes:
    tags: [marketing, website-audit, seo, ux, qa, competitors, multi-agent, orchestration, crewai-inspired]
    category: business
---

# Marketing Crew Orchestration

Use this skill when the user wants a reusable team of agents to audit a website or product/service marketing presence: website weaknesses, SEO, UX/QA, broken or risky features, messaging, conversion, regional competitors, basic competitor comparison, and a PDF audit report with short/medium/long-term fixes.

This is a class-level workflow skill. It is inspired by CrewAI architecture concepts — explicit agents, tasks, crews, manager/synthesizer, and sequential/parallel process — but implements the workflow natively in Hermes with transparent files and scripts, not as a hard dependency on the CrewAI Python package.

## Default Crew Shape

```text
input.md + deterministic website_probe.json/md
  ├─ Website Auditor / QA Agent
  ├─ SEO and Content Agent
  ├─ Competitor / Market Agent
  └─ Messaging / Conversion Agent
        ↓
  Strategy Synthesizer / Manager
        ↓
  Quality Reviewer
        ↓
  audit_report.md/html/pdf + quality_review.md + run_manifest.json + index
```

Recommended model split when available:

| Role | Preferred profile/model | Output |
|---|---|---|
| Website Auditor / QA | Claude Opus | `website_audit.md` |
| SEO and Content Analyst | GPT-5.5 | `seo_content.md` |
| Competitor / Market Analyst | Claude Opus | `competitor_market.md` |
| Messaging / Conversion Strategist | GPT-5.5 | `messaging_conversion.md` |
| Strategy Synthesizer / Manager | Claude Opus | `audit_report.md/html/pdf` |
| Quality Reviewer | Claude Opus | `quality_review.md` |

Always include a fallback profile so the run can finish as partial/auditable instead of failing completely.

## Default File Layout

Use this unless the user specifies another path:

```text
~/.hermes/marketing-crew/
  README.md
  SETUP_REPORT.md
  index.jsonl
  index.md
  config/
    workflow.md
    agent-profiles.md
    audit-rules.md
    task-template.md
    webhook-plan.md
  prompts/
    website-auditor.md
    seo-content.md
    competitor-market.md
    messaging-conversion.md
    strategy-synthesizer.md
    quality-reviewer.md
  scripts/
    website_probe.py
    export_report.py
    run_marketing_audit.py
    run_and_send_telegram.sh
  runs/
    <timestamp-domain>/
      input.md
      website_probe.md
      website_probe.json
      website_audit.md
      seo_content.md
      competitor_market.md
      messaging_conversion.md
      audit_report.md
      audit_report.html
      audit_report.pdf
      quality_review.md
      export_manifest.json
      run_manifest.json
```

## Deterministic Website Probe Pattern

Before LLM agents run, create a non-intrusive deterministic probe that writes `website_probe.md` and `website_probe.json`. It should collect:

- HTTP status and final URL.
- Title, meta description, H1/H2, `lang`, canonical, OG metadata.
- Internal/external link samples and status checks.
- Images and missing alt counts.
- Forms/inputs/buttons metadata without submitting forms.
- `robots.txt` and `sitemap.xml` status/sample.
- Text sample and a response hash.

Safety rules:

- Do not log in.
- Do not type secrets or passwords.
- Do not submit real lead/contact/order forms.
- Do not perform intrusive security scanning.
- Use normal public web access only.

## Agent Prompt Requirements

Each specialist prompt should specify a concrete output file and acceptance criteria.

### Website Auditor / QA

Focus: visible bugs, navigation, broken/risky features, trust issues, UX friction, inconsistencies, conversion blockers. Use the deterministic probe as evidence. For browser-driven audits, also follow the `dogfood` skill's evidence discipline, but do not edit that protected skill.

### SEO and Content Analyst

Focus: on-page SEO, metadata, H1/H2, content gaps, local/regional SEO, search intent hypotheses, crawl/index signals visible from the page. Do not invent keyword volumes.

### Competitor / Market Analyst

Focus: public regional competitors, positioning, basic offer comparison, trust/proof points, gaps/opportunities. Cite public URLs or mark assumptions.

### Messaging / Conversion Strategist

Focus: value proposition clarity, CTA/funnel, objections, proof points, landing copy, lead-flow improvements. Do not claim analytics/conversion performance without analytics access.

### Strategy Synthesizer / Manager

Produce the final client-facing report:

```markdown
# Marketing & Website Audit Report

## 1. Executive Summary
## 2. Audit Scope and Method
## 3. Website / UX / Functional Findings
## 4. SEO and Content Findings
## 5. Marketing / Positioning / Conversion Findings
## 6. Regional Competitor Snapshot
## 7. Prioritized Action Plan
### Short term: 0–14 days
### Medium term: 1–3 months
### Long term: 3–12 months
## 8. Suggested Backlog
## 9. Evidence and Limitations
```

### Quality Reviewer

Check for hallucinations, unsupported competitor claims, missing evidence, overclaims, weak prioritization, and whether the backlog is actionable.

## Runner Design Notes

A minimal runner should:

1. Write `input.md` from URL, region, business, customers, competitors, focus, and language.
2. Run deterministic `website_probe.py` first.
3. Run the four specialists in parallel with `ThreadPoolExecutor`.
4. Run synthesizer and quality reviewer sequentially.
5. Save every role's output immediately.
6. Generate Markdown, HTML, and a simple PDF even when high-end PDF dependencies are not installed.
7. Optionally upload selected artifacts to the user's approved Google Drive safe folder if already authorized and requested.
8. Update `index.jsonl` and `index.md` for all runs.
9. Write `run_manifest.json` with `run_id`, `created_at`, `workflow_version`, URL, region, business, agents, outputs, known issues, helper outputs, and timings.

Use `hermes -p <profile> chat -Q --source marketing-crew-<role> --max-turns 10 -t web -q <prompt>` for subprocess role calls.

## Telegram and Webhook Pattern

Prefer Telegram-first for this user:

```bash
~/.hermes/marketing-crew/scripts/run_and_send_telegram.sh \
  https://example.com \
  "Czech Republic" \
  "business description" \
  telegram
```

If webhooks are requested, prepare `config/webhook-plan.md` first. Do not enable a new public listener or port silently.

## Verification Checklist

Before reporting success:

- `python3 -m py_compile` all Python scripts.
- `bash -n` shell wrappers.
- Run at least a smoke test with `--no-upload` on a harmless public site.
- Confirm `run_manifest.json` status and no unexpected issues.
- Confirm `audit_report.md`, `audit_report.html`, `audit_report.pdf`, `quality_review.md`, and `website_probe.json/md` exist and are non-empty.
- Confirm PDF file type is valid.
- Confirm `index.jsonl` and `index.md` are updated.

## User-Specific Reporting Preferences

For this user:

- Respond in practical Czech.
- Include exact paths and commands.
- Include concise status/semaphore summaries.
- Preserve auditability: setup report, created-file list, manifest, limitations, test result, and reviewer questions.
- Do not expose secrets or open ports without explicit approval.

## References

- Session implementation note: `references/2026-07-03-marketing-crew-mvp.md`

---
name: marketing-website-audit-crew
description: "Build and run CrewAI-inspired Hermes marketing crews for website audits: UX/QA, SEO, conversion, competitors, PDF reports."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [marketing, website-audit, seo, conversion, competitor-analysis, multi-agent, pdf, telegram]
    created_by: agent
---

# Marketing Website Audit Crew

Use this skill when the user wants a **marketing/SEO/UX/competitor audit of a website** or asks to create/run a team of marketing agents inspired by CrewAI.

The preferred pattern is a transparent Hermes-native crew: explicit role prompts + deterministic probe + parallel specialist agents + manager synthesis + quality review + PDF/export + index. Do **not** require CrewAI as a runtime dependency unless the user explicitly asks for the Python CrewAI library.

## Trigger examples

- “Vytvoř tým marketérů inspirovaný CrewAI.”
- “Zaudituj web / SEO / slabá místa marketingu / konkurenci.”
- “Vytvoř PDF audit webu s návrhem oprav krátkodobě/střednědobě/dlouhodobě.”
- “Pošli mi PDF výstup z auditu.”

## Recommended architecture

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

CrewAI inspiration to preserve:

- agent = role + goal + backstory-like prompt,
- task = explicit output file with acceptance criteria,
- crew = graph of parallel specialists + manager,
- process = parallel specialists, sequential synthesis/review,
- memory/auditability = durable run directory with manifests.

## Existing implementation on this server

A working MVP was created at:

```text
~/.hermes/marketing-crew/
```

Primary runner:

```bash
~/.hermes/marketing-crew/scripts/run_marketing_audit.py \
  --url https://example.com \
  --region "Czech Republic" \
  --business "short business/service description"
```

Telegram wrapper:

```bash
~/.hermes/marketing-crew/scripts/run_and_send_telegram.sh \
  https://example.com \
  "Czech Republic" \
  "short business/service description" \
  telegram
```

Typical outputs:

```text
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

Indexes:

```text
~/.hermes/marketing-crew/index.jsonl
~/.hermes/marketing-crew/index.md
```

## Agent roles

Recommended model split if available:

| Role | Suggested model/profile | Output |
|---|---|---|
| Website Auditor / QA | Claude Opus-style careful reviewer | `website_audit.md` |
| SEO and Content Analyst | GPT 5.5-style broad content/SEO analyst | `seo_content.md` |
| Competitor / Market Analyst | Claude Opus-style cautious researcher | `competitor_market.md` |
| Messaging / Conversion Strategist | GPT 5.5-style marketer/copy strategist | `messaging_conversion.md` |
| Strategy Synthesizer / Manager | Claude Opus-style arbiter/synthesizer | `audit_report.md` |
| Quality Reviewer | Claude Opus-style verifier | `quality_review.md` |

If specialist subprocesses stall or fail, do **not** pretend the full crew succeeded. Preserve partial artefacts, mark the manifest as partial, and synthesize only from verified artefacts. The runner should include stall guards, compact website-probe context, cross-profile fallbacks, and deterministic auto-finalization so a PDF/report is created without requiring David to manually finish it.

Important implementation lessons:

- Subagents invoked via `hermes chat -q` with only the `web` toolset cannot write files; prompts must say **return Markdown only**, and the parent orchestrator saves stdout.
- Treat `Broken pipe`, `API call failed`, empty output, or “nemám nástroj pro zápis” as invalid output and retry/fallback.
- Do not pass full large JSON/text dumps to subprocesses; compact `website_probe.json` and truncate text/link samples.
- Cap per-role timeouts so one stalled agent cannot block the whole audit for 15+ minutes.
- If manager/reviewer agents still fail, create `audit_report.md` and `quality_review.md` deterministically from valid existing artefacts, then export PDF and record this in `run_manifest.json`.
- Caveman integration is installed on this server. Marketing runner supports `--internal-compression caveman|off` (default `caveman`), workflow `0.3.0-caveman-internal-efficiency`. Use caveman-lite only for specialist handoffs; final `audit_report.md` and `quality_review.md` must remain polished/full quality.

## Deterministic website probe

Always include a deterministic probe before LLM judgement. It should collect at least:

- HTTP status and final URL,
- HTTPS/certificate/redirect findings,
- title/meta description/H1/H2,
- lang/canonical/OG metadata,
- internal/external links sample and status,
- image count and missing alt count,
- forms/inputs/buttons,
- robots.txt and sitemap.xml status,
- text sample and hash.

### Important TLS/HTTP pitfall

Some sites have broken HTTPS but working HTTP. Treat this as a **major audit finding**, but still inspect HTTP content if safe and public. The probe should:

1. Try the user-provided HTTPS URL.
2. Record certificate/HTTPS errors exactly.
3. If HTTPS fails or returns 4xx, try HTTP fallback for content inspection.
4. Keep the HTTPS failure in `website_probe.md/json` and final report.

Do not silently “fix” the URL and omit the HTTPS issue.

## Safety rules

- Do not type credentials or handle passwords.
- Do not submit real lead/contact forms.
- Do not perform intrusive scanning, exploitation, or aggressive crawling.
- Stick to public pages and normal GET/HEAD-style checks unless the user authorizes more.
- Mark analytics/conversion claims as judgement unless GA/GSC/CRM data was provided.

## Report structure

The final audit report should include:

1. Executive summary and semafor.
2. Audit scope and method.
3. Website / UX / functional findings.
4. SEO and content findings.
5. Marketing / positioning / conversion findings.
6. Regional competitor snapshot.
7. Short/medium/long-term action plan.
8. Prioritized backlog.
9. Evidence and limitations.
10. Final recommendation.

Use tables for priorities and explicit evidence. Include a PDF and attach it with `MEDIA:/absolute/path/to/file` when the platform supports native files.

## Verification checklist

Before delivering:

- `run_manifest.json` exists and honestly records partial failures/fallbacks.
- `audit_report.md` exists and is non-empty.
- `audit_report.pdf` exists and `file audit_report.pdf` reports a PDF.
- `quality_review.md` exists, or the limitation is documented.
- Index files are updated.
- If delivering a file, include `MEDIA:/absolute/path/to/audit_report.pdf`.

## References

- `references/retrobudka-session-notes.md` — notes from the retrobudka.cz audit run, including HTTPS fallback and partial-agent-finalization pattern.
- `references/caveman-internal-compression.md` — how marketing crew uses caveman-lite for internal specialist handoffs while preserving final report/PDF quality.

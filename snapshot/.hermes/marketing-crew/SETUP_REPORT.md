# Hermes Marketing Crew Setup Report

## What was created

Vytvořen nový CrewAI-inspired tým marketingových agentů v:

```text
/home/david_master/.hermes/marketing-crew/
```

Cíl: audit webu, SEO, UX/QA, marketingových slabin, regionální konkurence a základního porovnání služeb/produktů; výstupem je auditní report v Markdown/HTML/PDF + quality review + manifest/index.

## Architecture

```text
input.md + deterministic website_probe.json/md
  ├─ Website Auditor / QA Agent — Claude Opus
  ├─ SEO and Content Agent — GPT 5.5
  ├─ Competitor / Market Agent — Claude Opus
  └─ Messaging / Conversion Agent — GPT 5.5
        ↓
  Strategy Synthesizer / Manager — Claude Opus
        ↓
  Quality Reviewer — Claude Opus
        ↓
  audit_report.md/html/pdf + quality_review.md + run_manifest.json + index
```

CrewAI inspiration is structural, not a runtime dependency:

- explicit agents with role/goal/backstory-like prompts,
- explicit task outputs,
- parallel specialists,
- manager/synthesizer,
- quality reviewer,
- durable artefacts on disk.

## Agent mapping

| Role | Profile | Model | Output |
|---|---|---|---|
| Website Auditor / QA | `deepresearch-claude-opus` | `claude-opus-4-8` | `website_audit.md` |
| SEO and Content Analyst | `deepresearch-gpt55` | `gpt-5.5` | `seo_content.md` |
| Competitor / Market Analyst | `deepresearch-claude-opus` | `claude-opus-4-8` | `competitor_market.md` |
| Messaging / Conversion Strategist | `deepresearch-gpt55` | `gpt-5.5` | `messaging_conversion.md` |
| Strategy Synthesizer / Manager | `deepresearch-claude-opus` | `claude-opus-4-8` | `audit_report.md/html/pdf` |
| Quality Reviewer | `deepresearch-claude-opus` | `claude-opus-4-8` | `quality_review.md` |

Fallback profile:

```text
deepresearch-gpt55
```

## Deterministic website probe

Přidán lokální neintruzivní scanner:

```text
/home/david_master/.hermes/marketing-crew/scripts/website_probe.py
```

Kontroluje:

- HTTP status a final URL,
- title / meta description / H1 / H2,
- lang / canonical / OG metadata,
- interní/externí odkazy sample,
- link status sample,
- obrázky bez alt,
- formuláře/inputy,
- robots.txt a sitemap.xml,
- text sample a hash.

Bezpečnost:

- nepřihlašuje se,
- nevyplňuje formuláře,
- nedělá intrusive scanning,
- používá běžné GET/HEAD-like dotazy.

## How to run

Lokálně bez Telegramu:

```bash
~/.hermes/marketing-crew/scripts/run_marketing_audit.py \
  --url https://example.com \
  --region "Czech Republic" \
  --business "stručný popis firmy/služby"
```

S doplňujícími parametry:

```bash
~/.hermes/marketing-crew/scripts/run_marketing_audit.py \
  --url https://example.com \
  --region "Praha / ČR" \
  --business "B2B služba" \
  --customers "malé a střední firmy" \
  --competitors "konkurent1.cz, konkurent2.cz" \
  --focus "SEO, lead generation, lokální konkurence"
```

Telegram-first wrapper:

```bash
~/.hermes/marketing-crew/scripts/run_and_send_telegram.sh \
  https://example.com \
  "Czech Republic" \
  "stručný popis firmy/služby" \
  telegram
```

## Outputs

Každý run vytvoří adresář:

```text
/home/david_master/.hermes/marketing-crew/runs/<timestamp-domain>/
```

Typické soubory:

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

Index:

```text
/home/david_master/.hermes/marketing-crew/index.jsonl
/home/david_master/.hermes/marketing-crew/index.md
```

## Files created

```text
/home/david_master/.hermes/marketing-crew/README.md
/home/david_master/.hermes/marketing-crew/SETUP_REPORT.md
/home/david_master/.hermes/marketing-crew/config/workflow.md
/home/david_master/.hermes/marketing-crew/config/agent-profiles.md
/home/david_master/.hermes/marketing-crew/config/audit-rules.md
/home/david_master/.hermes/marketing-crew/config/task-template.md
/home/david_master/.hermes/marketing-crew/config/webhook-plan.md
/home/david_master/.hermes/marketing-crew/prompts/website-auditor.md
/home/david_master/.hermes/marketing-crew/prompts/seo-content.md
/home/david_master/.hermes/marketing-crew/prompts/competitor-market.md
/home/david_master/.hermes/marketing-crew/prompts/messaging-conversion.md
/home/david_master/.hermes/marketing-crew/prompts/strategy-synthesizer.md
/home/david_master/.hermes/marketing-crew/prompts/quality-reviewer.md
/home/david_master/.hermes/marketing-crew/scripts/website_probe.py
/home/david_master/.hermes/marketing-crew/scripts/export_report.py
/home/david_master/.hermes/marketing-crew/scripts/run_marketing_audit.py
/home/david_master/.hermes/marketing-crew/scripts/run_and_send_telegram.sh
```

## Smoke test

Spuštěn testovací audit na `https://example.com`:

```text
/home/david_master/.hermes/marketing-crew/runs/20260703-065502-example-com-smoke
status=success
```

Ověření:

```text
website_probe status=200 links=1 bad=0
PDF document, version 1.4, 6 pages
known_issues=[]
```

Vytvořené smoke artefakty:

```text
audit_report.md      14261 bytes
audit_report.html    17182 bytes
audit_report.pdf     17706 bytes
quality_review.md     8587 bytes
run_manifest.json     2255 bytes
website_probe.json    1809 bytes
website_probe.md      1007 bytes
```

## Current limitations

1. Není to plnohodnotný browser-driven dogfood test s klikáním přes UI; deterministic probe je HTTP/HTML based.
2. Neprovádí se Lighthouse/PageSpeed měření, protože není zaručený Chrome/Lighthouse runtime.
3. Formuláře se neodesílají, záměrně kvůli bezpečnosti.
4. PDF renderer je jednoduchý built-in PDF writer; validní PDF, ne designový report.
5. Webhook je připravený jako plán, ale není enabled, aby se zbytečně neotevíral nový port.
6. Google Drive upload je v runneru zapnutý defaultně, smoke test běžel s `--no-upload`, aby se nevytvářely testovací Drive soubory.

## Recommended next improvements

1. Přidat volitelný browser QA režim pro klikání a screenshots přes Hermes browser/computer-use.
2. Přidat Lighthouse/PageSpeed adapter, pokud bude dostupný Chrome/Node Lighthouse.
3. Přidat šablony podle typu byznysu: lokální služba, e-shop, B2B SaaS, automotive, zdravotnictví.
4. Přidat plánovaný Telegram příkaz/webhook po explicitním schválení portu.
5. Přidat hezčí PDF renderer přes Chromium/weasyprint, pokud se doinstaluje.

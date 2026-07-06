# Hermes DeepResearch Setup Report

## What Was Created

Vytvořeno a rozšířeno MVP auditovatelné multi-agentní deepresearch orchestrace v:

```text
/home/david_master/.hermes/deepresearch/
```

Aktuální workflow:

```text
input.md
  ├─ Research Agent A — ChatGPT 5.5 profile
  └─ Research Agent B — Claude Opus profile
        ↓
  Arbitrator / Verifier — Claude Opus
        ↓
  Deterministic Source URL Auditor
        ↓
  Source Auditor — Claude Opus
        ↓
  Final Writer — ChatGPT 5.5
        ↓
  Quality Reviewer — Claude Opus
        ↓
  final_report.md/html/pdf + quality_review.md + run_manifest.json + export_manifest.json
        ↓
  Google Drive safe folder upload + Telegram wrapper
```

Implementace neupravuje globální Hermes konfiguraci kromě vytvoření samostatných Hermes profilů pro deepresearch. Nevystavil jsem žádný nový veřejný port.

## What Changed After Codex Master Questions

1. Zvolil jsem flexibilnější cestu: hlavní orchestrace zůstává Python runner s auditní exportní vrstvou. `hermes kanban swarm` zůstává doporučený budoucí backend, ale ne jako první produkční runner.
2. Vytvořil jsem dva Hermes profily:
   - `deepresearch-gpt55` → `openai-codex` / `gpt-5.5`
   - `deepresearch-claude-opus` → `anthropic` / `claude-opus-4-8`
3. Zvolil jsem hybridní Source Audit: LLM auditor + deterministický URL checker. To je flexibilní a zároveň auditovatelnější.
4. Zpřísnil jsem citation schema na robustnější tabulku s `Source title`, `URL/DOI`, `Source type`, `Date/year`, `Accessed at`, `Confidence`, `Notes`.
5. Přidal jsem export do HTML/PDF a upload do Google Drive safe folder.
6. Přidal jsem Telegram-first wrapper. Webhook jsem připravil jako plán, ale nezapnul jsem ho, protože webhook platforma je vypnutá a zapnutí by znamenalo nový globální port.

## Hermes Capability / Config Analysis

Zjištěno:

- Hermes Agent: `v0.17.0 (2026.6.19)`.
- Aktivní hlavní profil: `default`.
- Hlavní model: `gpt-5.5` přes `openai-codex`.
- Nový Claude profil testován úspěšně s `claude-opus-4-8`.
- Terminal backend: local.
- Gateway/cron běží.
- `hermes kanban swarm` existuje a podporuje základní graf `parallel workers → verifier → synthesizer`.
- Telegram target existuje: `telegram:David Hluze [8629730938]`.
- Webhook platforma aktuálně není enabled.

## How To Run A New Research

Lokálně bez Telegram zprávy:

```bash
~/.hermes/deepresearch/scripts/run_deepresearch.py "Tvoje research zadání"
```

Telegram-first varianta:

```bash
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "Tvoje research zadání" telegram
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "Tvoje research zadání" telegram scientific
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "Tvoje research zadání" telegram market
~/.hermes/deepresearch/scripts/run_and_send_telegram.sh "Tvoje research zadání" telegram software
```

Volitelné parametry runneru:

```bash
~/.hermes/deepresearch/scripts/run_deepresearch.py \
  "Tvoje research zadání" \
  --slug vlastni-slug \
  --mode scientific \
  --timeout 900 \
  --toolsets web
```

Dostupné módy:

```text
auto        default, nechá workflow vybrat styl podle zadání
scientific  zdravotní/vědecké evidence, RCT, reviews, bezpečnost
market      trh/business/konkurence, data a nejistoty
software    architektura, dokumentace, provozní dopady
```

Výsledek bude vždy v:

```text
/home/david_master/.hermes/deepresearch/runs/<timestamp-slug>/
```

## Agent/Profile Mapping

| Role | Profil | Model | Output |
|---|---|---|---|
| Research Agent A | `deepresearch-gpt55` | `gpt-5.5` | `research_a.md` |
| Research Agent B | `deepresearch-claude-opus` | `claude-opus-4-8` | `research_b.md` |
| Arbitrator / Verifier | `deepresearch-claude-opus` | `claude-opus-4-8` | `arbitration.md` |
| Deterministic URL Auditor | local script | n/a | `source_url_audit.md/json` |
| Source Auditor | `deepresearch-claude-opus` | `claude-opus-4-8` | `source_audit.md` |
| Final Writer | `deepresearch-gpt55` | `gpt-5.5` | `final_report.md/html/pdf` |
| Quality Reviewer | `deepresearch-claude-opus` | `claude-opus-4-8` | `quality_review.md` |

Runner má fallback profil:

```text
deepresearch-gpt55
```

Pokud Claude profil selže, run se pokusí pokračovat přes GPT 5.5 a zapíše to do `known_issues`.

## Files And Directories

Hlavní soubory:

```text
/home/david_master/.hermes/deepresearch/README.md
/home/david_master/.hermes/deepresearch/SETUP_REPORT.md
/home/david_master/.hermes/deepresearch/index.jsonl
/home/david_master/.hermes/deepresearch/index.md
/home/david_master/.hermes/deepresearch/config/workflow.md
/home/david_master/.hermes/deepresearch/config/agent-profiles.md
/home/david_master/.hermes/deepresearch/config/quality-rules.md
/home/david_master/.hermes/deepresearch/config/source-rules.md
/home/david_master/.hermes/deepresearch/config/task-template.md
/home/david_master/.hermes/deepresearch/config/review-template.md
/home/david_master/.hermes/deepresearch/config/webhook-plan.md
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
/home/david_master/.hermes/deepresearch/scripts/source_url_audit.py
/home/david_master/.hermes/deepresearch/scripts/export_final.py
/home/david_master/.hermes/deepresearch/scripts/rebuild_index.py
/home/david_master/.hermes/deepresearch/scripts/run_and_send_telegram.sh
```

Nové Hermes profily:

```text
/home/david_master/.hermes/profiles/deepresearch-gpt55/
/home/david_master/.hermes/profiles/deepresearch-claude-opus/
```

## Current Limitations

1. Kanban swarm zatím není hlavní produkční runner; Python runner je zvolen kvůli auditní vrstvě a jednodušší údržbě.
2. PDF export je jednoduchý built-in PDF writer bez typograficky dokonalého layoutu. Je validní PDF, ale ne designový dokument.
3. Deterministický URL audit kontroluje dostupnost a metadata URL, ale neprovádí hlubokou semantickou verifikaci celého obsahu.
4. Webhook není enabled, protože by to znamenalo nový port / globální změnu gateway konfigurace. Připravený plán je v `config/webhook-plan.md`.
5. Dlouhé research výstupy se do navazujících rolí předávají jako head+tail truncation; plné soubory zůstávají na disku.

## Test Run Result

### Původní EGCG test

Úspěšný MVP run:

```text
/home/david_master/.hermes/deepresearch/runs/20260702-165123-egcg-katechiny-longevity-mvp2/
status=success
```

### Nový smoke test s GPT 5.5 + Claude Opus + Drive exportem

Spuštěno:

```text
MVP smoke test: stručně ověř, že zelený čaj obsahuje katechiny včetně EGCG, uveď 1-2 robustní zdroje a nepřeháněj závěry.
```

Výsledek:

```text
/home/david_master/.hermes/deepresearch/runs/20260702-180306-smoke-gpt55-claude-drive/
status=success
```

Ověřeno:

- `research_a` běžel přes `deepresearch-gpt55`.
- `research_b`, `arbitration`, `source_audit`, `quality_review` běžely přes `deepresearch-claude-opus`.
- Žádný fallback nebyl použit.
- `source_url_audit`: `urls=11`, `ok=7`.
- PDF vytvořeno: `PDF document, version 1.4, 2 pages`.
- Upload do Google Drive safe folder proběhl.

Drive artefakty ze smoke testu:

```text
final_report.md   https://drive.google.com/file/d/1bHJ_8yTxCOshUYcU-60NH5C_SloSULFq/view?usp=drivesdk
final_report.html https://drive.google.com/file/d/1GqedFpHzhCEt8vk9dETZxBTMp0a9d6GU/view?usp=drivesdk
final_report.pdf  https://drive.google.com/file/d/1DFoPlc_MdAR20iVwyCDkbe-Jth9MPkXs/view?usp=drivesdk
quality_review.md https://drive.google.com/file/d/1XSX1DgVDkF3r3iPLqaImdU9W5CC88HlI/view?usp=drivesdk
```

### Scientific mode + index smoke test

Spuštěno s `--mode scientific --no-upload`:

```text
Scientific smoke test: stručně ověř, že zelený čaj obsahuje EGCG a uveď bezpečnostní opatrnost u extraktů. Použij robustní citace, ale drž výstup krátký.
```

Výsledek:

```text
/home/david_master/.hermes/deepresearch/runs/20260702-181845-scientific-mode-index-smoke/
status=success
mode=scientific
workflow_version=0.3.0-modes-index
source_url_audit urls=12 ok=8
```

Index ověřen:

```text
/home/david_master/.hermes/deepresearch/index.jsonl  # 3 runs
/home/david_master/.hermes/deepresearch/index.md     # human-readable table
```

## Recommended Next Improvements

1. Po potvrzení explicitně zapnout webhook platformu a vytvořit route `deepresearch`.
2. Přidat lepší PDF rendering přes `weasyprint`/Chromium, pokud bude nainstalováno.
3. Přidat kanban adapter pro dlouhé multi-day research projekty.
4. Přidat source cache se snapshotem extrahovaného textu a hash celého obsahu.
5. Přidat další režimy podle potřeby: legal/regulatory, investment, competitive intelligence, product comparison.

## Questions For Codex Master Review

1. Souhlasí Codex Master s tím, že hlavní runner má zůstat Python auditní wrapper a kanban má být druhý backend?
2. Má se přidat další model/profil pro levnější rychlé research preview?
3. Má source auditor vyžadovat `accessed_at` a `source title` jako hard-fail pro final report?
4. Jaký PDF standard stačí: jednoduchý auditní PDF, nebo hezký report přes HTML renderer?
5. Má webhook běžet veřejně na `8644`, nebo jen lokálně za reverse proxy?
6. Má Telegram wrapper posílat celý final report do chatu, nebo jen stručné oznámení + PDF/Drive link?

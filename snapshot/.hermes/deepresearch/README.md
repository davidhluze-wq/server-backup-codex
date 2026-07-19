# Hermes DeepResearch MVP

Auditovatelná multi-agentní deepresearch orchestrace pro Hermes.

## Cíl

Workflow spouští nezávislé paralelní research agenty, poté sekvenční kontrolní kroky:

```text
USER TASK
  ├─ Research Agent A  ┐
  └─ Research Agent B  ┘  parallel
        ↓
  Arbitrator / Verifier
        ↓
  Source Auditor
        ↓
  Final Writer
        ↓
  Quality Reviewer
        ↓
  runs/<timestamp-slug>/*.md + run_manifest.json
```

## Rychlé spuštění

```bash
~/.hermes/deepresearch/scripts/run_deepresearch.py "Tvoje research zadání"
~/.hermes/deepresearch/scripts/run_deepresearch.py "Tvoje research zadání" --mode scientific
~/.hermes/deepresearch/scripts/run_deepresearch.py "Tvoje research zadání" --mode market
~/.hermes/deepresearch/scripts/run_deepresearch.py "Tvoje research zadání" --mode software
```

Index všech runů:

```text
~/.hermes/deepresearch/index.jsonl   # machine-readable
~/.hermes/deepresearch/index.md      # human-readable pro Codex/Hermes
```

Ruční rebuild indexu:

```bash
~/.hermes/deepresearch/scripts/rebuild_index.py
```

Pokud selže jen finální autor, lze bez opakování sběru zdrojů opravit závěr existujícího běhu:

```bash
~/.hermes/deepresearch/scripts/retry_final_report.py ~/.hermes/deepresearch/runs/<run-id>
```

Výstup se uloží do:

```text
~/.hermes/deepresearch/runs/<timestamp-slug>/
```

## Bezpečnost

- Runner neupravuje globální Hermes konfiguraci.
- Všechny výstupy jsou textové a čitelné pro Codex Master kontrolora.
- API klíče ani tokeny se do výstupů záměrně nezapisují.
- Veřejné porty se nevytvářejí ani neotevírají.

## Odolnost finálního výstupu

- Finální autor standardně používá profil `deepresearch-claude-opus`; při chybě automaticky přechází na `worker-sonnet` a poté se jednou zopakuje celá finální fáze.
- Jeden pokus finálního autora i kontroly kvality má standardně nejvýše pět minut; lze jej upravit proměnnou `HERMES_DEEPRESEARCH_FINAL_QUALITY_TIMEOUT`.
- Pokud selžou všechny pokusy, run se označí jako částečný, přeskočí kontrolu kvality i export a odešle Telegram upozornění s doporučením. Chybový soubor se proto nikdy nevydává za hotový report.

## Implementační poznámka

Aktuální Hermes má dostupný `hermes kanban swarm` s grafem worker → verifier → synthesizer. Pro flexibilnější auditovatelnou exportní vrstvu a extra kroky `Source Auditor` + `Quality Reviewer` používá MVP explicitní Python runner, který spouští dvě paralelní `hermes chat -Q` instance a následné kontrolní kroky. Runner používá kombinaci profilů `deepresearch-gpt55` a `deepresearch-claude-opus`, deterministický URL audit a export do HTML/PDF/Google Drive.

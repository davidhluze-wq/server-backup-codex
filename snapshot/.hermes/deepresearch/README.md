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

Výstup se uloží do:

```text
~/.hermes/deepresearch/runs/<timestamp-slug>/
```

## Bezpečnost

- Runner neupravuje globální Hermes konfiguraci.
- Všechny výstupy jsou textové a čitelné pro Codex Master kontrolora.
- API klíče ani tokeny se do výstupů záměrně nezapisují.
- Veřejné porty se nevytvářejí ani neotevírají.

## Implementační poznámka

Aktuální Hermes má dostupný `hermes kanban swarm` s grafem worker → verifier → synthesizer. Pro flexibilnější auditovatelnou exportní vrstvu a extra kroky `Source Auditor` + `Quality Reviewer` používá MVP explicitní Python runner, který spouští dvě paralelní `hermes chat -Q` instance a následné kontrolní kroky. Runner používá kombinaci profilů `deepresearch-gpt55` a `deepresearch-claude-opus`, deterministický URL audit a export do HTML/PDF/Google Drive.

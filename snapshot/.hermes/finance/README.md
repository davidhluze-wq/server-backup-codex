# Finance crew (faze 1) — vm12890

Finanční analýza nad **veřejnými daty** + reporty. Stejný vzor (Python runner +
Hermes profily), ale **tierovaný routing**: rutinu dělá levný model, úsudek a finální
kontrolu drahý.

> **Scope:** jen veřejná data. Firemní/osobní finance patří na Mac. Burza (fáze 2) je
> oddělený projekt `trading/`, tady NENÍ — a vždy jen signál ke schválení, nikdy objednávky.

## Role → tier
| Role | Profil | Tier |
|---|---|---|
| analyst | `deepresearch-claude-opus` | 🧠 úsudek |
| cashflow | `deepresearch-claude-opus` | 🧠 úsudek |
| anomaly | `worker-sonnet` | 💰 rutinní scan |
| report_writer | `worker-gpt-mini` | 💰 formátování |
| final_review | `deepresearch-claude-opus` | 🧠 finální tester |

Escalation: levný → levný druhý provider → drahý (opravář, když se levný zasekne).

## Spuštění
```bash
cd ~/Hermes/projects/finance
python3 scripts/run_finance.py --mode report   --task "Q2 shrnuti z verejnych vykazu firmy X"
python3 scripts/run_finance.py --mode cashflow --task "cashflow forecast 6M"
python3 scripts/run_finance.py --mode anomaly  --task "anomalie v serii ..."
python3 scripts/run_finance.py --mode full     --task "..."
```
Výstup: `runs/<mode>-<stamp>/<role>.md` + `summary.json` + souhrn do Telegramu.

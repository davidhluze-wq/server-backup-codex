# Legal-lite crew — vm12890

**Jen šablony, obecná compliance a NDA z neutrálních vstupů.** Tvrdé pravidlo:
žádná důvěrná/klientská data (ta patří na Mac + lokální model). Výstup = návrh,
ne právní rada; vyžaduje lidskou revizi.

Tierovaný routing: rutinu (drafting, diff, checklist) dělá levný model, úsudek
(rozbor klauzulí, rizika) a finální kontrolu drahý. Escalation levný→drahý.

## Role → tier
| Role | Profil | Tier |
|---|---|---|
| clause_analyzer | `deepresearch-claude-opus` | 🧠 úsudek |
| risk_assessor | `deepresearch-claude-opus` | 🧠 úsudek |
| compliance_checker | `worker-sonnet` | 💰 checklist |
| nda_drafter | `worker-gpt-mini` | 💰 drafting |
| comparator | `worker-gpt-mini` | 💰 diff |
| final_review | `deepresearch-claude-opus` | 🧠 tester |

## Spuštění
```bash
cd ~/Hermes/projects/legal-lite
python3 scripts/run_legal.py --mode review     --task "posud rizika v teto VEREJNE sablone: ..."
python3 scripts/run_legal.py --mode compliance --task "GDPR gap analyza obecneho scenare ..."
python3 scripts/run_legal.py --mode draft      --task "NDA z neutralnich vstupu ..."
python3 scripts/run_legal.py --mode compare    --task "porovnej verzi A vs B ..."
```
> Doporučeno napojit na `humanagentwiki` MCP jako znalostní bázi vlastních šablon.

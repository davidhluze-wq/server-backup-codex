# lana-trading — Trading crew (fáze 4/5)

Multiagentní posádka pro prediction-market / trading nad znalostní bází Lana (RAG).
Architektura inspirovaná open-source řešením **ai-hedge-fund**: několik analytiků →
risk manažer → exekuce → reviewer.

## Tok
market data + RAG evidence → [research, quant, sentiment] analytici → agregace odhadu
→ risk manažer (frakční Kelly, limity) → reviewer (brána) → exekuce (demo/live dle režimu).

## Role (7)
1. **strategist** — zaměření a alokace (opus, drahý)
2. **research** — thesis z RAG (gpt-5.4-mini, levný)
3. **quant** — odhad pravděpodobnosti + edge (gpt-5.4-mini, levný)
4. **sentiment** — sentiment/katalyzátory (gpt-5.4-mini, levný)
5. **risk** — limity, sizing, kill-switch (sonnet, levný)
6. **execution** — příkaz na účet (deterministický skript)
7. **reviewer** — finální kontrola + audit (opus, drahý)

## Režimy
- **offline dry-run** (deterministický, bez tokenů) — výchozí
- **demo** (od 2026-07-07) — Hermes modely + demo účet
- **live** — reálné peníze, lidské schválení dle `~/lana-research/phases/approval_policy.json`
  (operace s účtem vždy zakázány)

## Runner & přehled
`~/lana-research/scripts/trading_crew.py [--mode demo|paper] [--limit N] [--llm]`
Živě: **Lana → záložka 📈 Trading**. Bezpečnost: `phases/phase4-demo-mode.md`, `phase5-live-trading.md`.

# Commodity Autopilot — návrh implementace

## Účel a hranice

LANA bude paper-only denní až swingový scanner pro 20–30 likvidních komoditních futures.
Není to automatické live obchodování, investiční doporučení ani systém pro hledání nejvyššího
historického PnL. TradingView zůstává jen volitelný vizualizační vstup; LANA nesmí automaticky
sbírat jeho data.

## Doporučený stack

- Licencovaný datový provider: nejdříve EOD/delayed data a ověření licence pro interní research.
- `pandas`/`vectorbt`: deterministický výpočet features a denní ranking.
- Vlastní Postgres paper ledger: auditovatelný zdroj pravdy.
- NautilusTrader: až po samostatném technickém spike; kandidát pro event-driven paper engine,
  nikoli podmínka prvního scanneru.
- Docker Compose: samostatné služby `data`, `scanner`, `research`, `ledger`, `digest`; žádné
  veřejné databázové porty.

## Denní pipeline

1. Data Steward uloží immutable snapshot s providerem, časem, hashem, kontraktem a roll metodikou.
2. Data-quality gate blokuje missing bars, duplicitní data, neznámý nebo sentinelový multiplier, nebo nejasnou licenci.
3. Commodity Scanner počítá předem zmrazený ranking: trend/momentum, volatilita, likvidita a
   sektorová korelace. Neprovádí LLM predikce cen.
4. Jen top kandidáti projdou fundamentálním a event-risk research.
5. Research Skeptic vyžaduje pre-registraci, OOS/walk-forward, realistické fees/slippage a limit
   počtu testovaných variant.
6. Risk Officer aplikuje contract multiplier, volatility target, sektorové limity, drawdown stop a
   kill-switch.
7. Paper Ledger zapíše order intent a simulated fill podle předem definovaného pravidla; žádný
   broker connector není v této fázi načítán.
8. Dashboard a Telegram digest ukážou pouze odvozený ranking, risk, blokace a paper PnL.

## Povinné kontroly

- Každý experiment má konfiguraci, data snapshot, časové splity a replay test.
- Paper fill model má explicitní settlement/next-session pravidlo, poplatky a slippage; tick value se validuje proti oficiální specifikaci kontraktu včetně cenové škály a měny.
- Secrets jsou výhradně v souborech s oprávněním 600 nebo runtime secret store, nikdy v Git,
  dashboardu, Telegramu ani logu. Klíč vložený do chatu se považuje za kompromitovaný, zneplatní
  se a nahradí novým klíčem vloženým přímo do secret store.
- Monitoring sleduje čerstvost dat, chyby provideru, zpoždění pipeline, kill-switch, poslední
  digest a integritu ledgeru. Externě je vystaven pouze autentizovaný dashboard přes HTTPS.
- Licence dat se kontroluje před ingestem i před sdílením výstupů; raw licencovaná data se do
  Telegramu ani dashboardu nerepublikují bez výslovného oprávnění.
- Každý placený datový provider nebo spotřeba jeho kreditu vyžaduje před prvním requestem výslovné
  schválení rozpočtu; bez něj je ingest zablokovaný.

## Technický spike před výběrem enginu

Porovnat vlastní lehký simulator a NautilusTrader na stejném malém EOD datasetu. Pass kritéria:
reprodukovatelný replay, správný contract multiplier/roll, definované fees/slippage, auditní log,
maximálně přiměřená spotřeba CPU/RAM na tomto VPS a žádný live connector. Bez splnění zůstává
NautilusTrader pouze kandidátem, nikoli závislostí LANA.

### Výsledek lokálního feasibility testu (2026-07-13)

Izolovaný test na tomto VPS prošel: lehký ledger pro 20 syntetických instrumentů a 15 120 barů
byl deterministický ve dvou samostatných bězích (503 událostí); NautilusTrader 1.221.0 se bez
externích dat či připojení inicializoval. Proces dosáhl přibližně 254 MiB RAM a izolované runtime
prostředí zabírá 664 MiB disku. Rozhodnutí: první verze zůstává u vlastního lehkého ledgeru a
NautilusTrader se nenasazuje jako trvale běžící služba. Další spike smí začít až s licencovanými
futures daty a musí prokázat roll, multiplier, settlement/next-session fill, náklady a replay.

## Go/no-go

Paper signál je možný jen při `data_quality=pass`, platné licenci, zmrazeném rankingu, OOS a
walk-forward reportu, realistickém fill modelu a schválení Risk Officer + Research Skeptic.
Live režim je mimo tento playbook.

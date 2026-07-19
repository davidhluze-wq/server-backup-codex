# FÁZE 3 — Signály, obchody & P&L dashboard (PAPER)

> Scénář ("noty") k provedení. Připraveno pro exekuci Opusem. Předchozí sessions psala Fable;
> tuto fázi dotáhne a provede Opus podle tohoto souboru. **Žádné reálné peníze v této fázi.**

## Kritické upřesnění po revizi

- Tento playbook původně míchal dva rozdílné typy dat: predikční trhy (pravděpodobnost 0-1,
  *edge*, Kelly) a ceny aktiv z TradingView. Cena BTC, akcie nebo CFD **není pravděpodobnost**;
  z TradingView proto nelze odvozovat *edge* ani sizing bez samostatně ověřeného cenového modelu.
- Vzorek z automatického optimalizování parametrů není důkazem obchodovatelnosti. Každá strategie
  musí mít předem danou hypotézu, oddělený in-sample/out-of-sample test, walk-forward test,
  náklady/slippage a kontrolu více testování. Nejlepší historický profit factor sám o sobě nestačí.
- TradingView je v této fázi zdroj alertu, nikoliv broker. Alert vytvoří pouze auditovaný
  `research-pass` paper signál. Do lokálního paper obchodu může přejít až po nezávislém
  schválení `paper-watch`; propojení s reálným brokerem patří až do samostatné, ručně schvalované fáze.
- Veřejný TradingView webhook vyžaduje samostatnou HTTPS doménu a rychlou odpověď. Port 8811 se
  nesmí zveřejňovat přímo; popis aktivace je v `docs/TRADINGVIEW_PAPER_SETUP.md`.

## Cíl
Nad znalostní bází (RAG + blueprint z fáze 1–2) postavit **demo trading vrstvu**, která:
1. generuje obchodní **signály** (kalibrovaný odhad pravděpodobnosti vs. tržní cena → *edge*),
2. **paper-exekvuje** (simulace, žádné reálné objednávky),
3. ukazuje **dashboard obchodů, P&L a monitoring signálů/strategie**.

## Vstupy (co už existuje)
- RAG schéma `lana` (sources, chunks, findings, blueprints, plan_queue) v Postgresu humanagentwiki.
- `~/lana-research/scripts/server.py` (dashboard, port 8811, přes agentsmon `/lana`).
- Blueprint (krok 10) = korroborovaná strategie po tématech.
- Veřejná tržní data: **Polymarket CLOB API** (`https://clob.polymarket.com`, read-only markets/prices) a/nebo **Kalshi** veřejné API. Vše read-only, bez klíčů.

## Datový model (nové tabulky ve schématu `lana`)
```sql
create table if not exists lana.signals(
  id bigserial primary key, market text, question text,
  prob_estimate real, market_price real, edge real, confidence real,
  side text, thesis text, evidence jsonb, status text default 'open', -- open|acted|expired
  created_at timestamptz default now());
create table if not exists lana.trades(
  id bigserial primary key, signal_id bigint references lana.signals(id),
  market text, side text, size real, entry_price real, entry_at timestamptz default now(),
  exit_price real, exit_at timestamptz, pnl real, status text default 'open', -- open|closed
  mode text default 'paper');
create table if not exists lana.pnl_snapshots(
  id bigserial primary key, ts timestamptz default now(),
  equity real, realized real, unrealized real, open_positions int, win_rate real);
```

## Komponenty k vytvoření (soubory)
1. `scripts/market_data.py` — **zero-LLM** fetch veřejných trhů (Polymarket CLOB `/markets`, ceny). Cache do `lana` (tabulka `lana.markets` volitelně). Ošetři rate-limit, timeouty.
2. `scripts/signal_engine.py` — pro aktivní trhy: sestav *thesis* z RAG (FTS/retrieval nad `chunks` + relevantní `findings`), odhadni pravděpodobnost (levný model `worker-gpt-mini` navrhne, `worker-sonnet`/opus jako **judge** potvrdí kalibraci), spočti `edge = prob_estimate - market_price`. Zapiš `lana.signals`. Tiery: návrh levně, finální kalibrace judge dráž — jen u signálů s |edge| nad prahem.
3. `scripts/paper_trader.py` — z otevřených signálů s edge > práh a confidence > práh vytvoř **paper** `lana.trades` (size = frakční Kelly z blueprintu, cap). Průběžně přeceňuj otevřené pozice tržní cenou, uzavírej dle exit pravidel (take-profit / stop / resolution). Ulož `lana.pnl_snapshots`.
4. **Dashboard rozšíření** (`server.py`): nová sekce/kroky nebo záložka:
   - `/api/trades` → otevřené + uzavřené obchody s P&L.
   - `/api/signals` → aktivní signály (edge, confidence, thesis, stav).
   - `/api/pnl` → equity křivka + realized/unrealized, win rate, počet pozic.
   - UI: tabulka obchodů, **equity curve** (SVG jako growth graf), karty (Equity, Realized P&L, Win rate, Otevřené pozice), monitor signálů. Napoj na **Implementation Loop** záložku.
5. `scripts/run_trader_paper.sh` — orchestrátor: market_data → signal_engine → paper_trader → pnl snapshot. Cron např. každou hodinu (token-šetrně: signal_engine jen pro trhy s pohybem/nové).

## Bezpečnost / pravidla (dodržet)
- **Pouze paper.** `mode='paper'` všude; žádný connector k reálným účtům, žádné klíče.
- Nikdy nevydávej investiční doporučení; jde o experiment/simulaci.
- Token rozpočet: signal_engine jen na trhy s |edge| kandidátem; judge (dražší) jen na top N.
- Vše logováno; deterministické části (fetch, P&L, sizing) bez LLM.
- Každý příchozí alert má stabilní `event_id`, je idempotentní a nesmí obsahovat žádné přihlašovací
  údaje ani klíče.

## Akceptační kritéria (hotovo když)
- Dashboard ukazuje **živě paper obchody, P&L statement, equity křivku a monitor signálů**.
- Běží na rozvrhu, plní `lana.signals`/`lana.trades`/`lana.pnl_snapshots`.
- Signály jsou **podložené** RAG evidencí (odkaz na findings/sources).
- 0 reálných objednávek, 0 klíčů v repu/logu.

## Handoff pro fázi 4
Až paper vrstva poběží stabilně a bude mít smysluplné metriky (win rate, kalibrace, drawdown),
připrav shrnutí výkonu jako vstupní bránu pro fázi 4 (viz `phase4-live-trading.md`, sekce „Go-live brána").

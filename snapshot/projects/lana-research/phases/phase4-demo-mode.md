# FÁZE 4 — Agenti v DEMO režimu (mezistupeň mezi paper a naostro)

> Scénář k provedení Opusem. Cíl: nechat celý trading crew běžet **autonomně na demo účtech**
> (reálná tržní data, reálná mechanika objednávek, ale **demo peníze**) — poslední validace
> před reálným kapitálem. Žádné reálné peníze.

## Proč mezistupeň
Paper (fáze 3) je čistá simulace v našem kódu. Demo režim je realističtější: skutečné order
routing, latence, sloupce/spready, částečné fills — ale na **demo účtu brokera**, takže riziko = 0.
Tady se crew "rozjede naostro nanečisto" a odladí se chování před fází 5.

## Demo účty / prostředí
- **XTB** — xStation5 **DEMO** účet (plnohodnotné API, demo peníze).
- **TradingView** — paper trading účet (příchozí alerty jako signály).
- **Polymarket** — nemá klasický demo; použij **malý testovací režim / testnet** nebo zůstaň u paper
  simulace nad reálnými cenami (žádné reálné USDC).
Začni **XTB demo** (nejčistší API pro demo).

## Co postavit (nad fází 3)
1. `scripts/connectors/xtb_demo.py` — připojení k xStation5 demo (login z env `XTB_DEMO_*`),
   dotazy na trhy/ceny, zadání/rušení příkazů, stav pozic. Tenký wrapper, plný log.
2. **Crew v autonomním demo běhu** — stejné agenty jako fáze 5 (strateg/signál/risk/exekuce/reviewer),
   ale exekuce míří na **demo connector**. Bez lidského schválení (jde o demo peníze) — přesně tady
   se testuje autonomní chování, které fáze 5 zapne až s pojistkami.
3. `scripts/run_demo_crew.sh` — orchestrace: signály (z fáze 3) → risk sizing → demo exekuce → monitor.
   Rozvrh (např. každou hodinu v tržních hodinách), token-šetrně.
4. Dashboard: rozliš `mode='demo'` v `lana.trades`, přidej filtr paper/demo/live, samostatnou
   equity křivku a metriky pro demo (win rate, drawdown, kalibrace, průměrný slippage vs. paper).

## Bezpečnost
- **Pouze demo účty / demo peníze.** Ověř, že connector cílí na demo endpoint, ne na reálný.
- Risk engine (limity, sizing, kill-switch) běží i v demu — otestuje se tu, než chrání reálné peníze.
- Klíče k demo účtům jen v env, nikdy v repu/logu.

## Akceptační kritéria / go k fázi 5
- Crew autonomně obchoduje na demo účtu, dashboard ukazuje demo obchody + P&L + risk stav.
- Kill-switch a risk limity ověřeny na demu (vč. simulace překročení).
- Nasbírané metriky (min. období, kalibrace, drawdown v limitu) tvoří **go-live bránu** pro fázi 5.
- Teprve po schválení Davidem → přechod na fázi 5 (reálný kapitál).

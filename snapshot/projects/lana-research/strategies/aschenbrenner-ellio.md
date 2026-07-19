# Strategie: AI Compute Supercycle — à la Aschenbrenner × EllioTrades

> Tematická strategie pro Lana trading crew. **Research/paper — modeluje veřejně známou tezi,
> není to investiční doporučení.** Live obchodování zůstává za bránou fáze 5 (lidské schválení).
> Zdroje na konci; tvrzení bez zdroje označ jako nejisté.

## Jádro teze (Leopold Aschenbrenner — Situational Awareness Fund)
Nejcennější aktiva éry AI nemusí být modely, ale **elektřina a výpočetní výkon**. Úzké hrdlo
AI boomu = **energetika a compute kapacita**, ne samotné AI modely. Fond (~$1.5B → $20B+ AUM 2026,
~$5.5B akciová expozice, ~30 pozic) sází na profitéry AI build-outu, **hedguje/shortuje přehřáté**.

Distinktivní rys: **long energetika/infrastruktura + vybrané čipy**, ale **velké PUT pozice na široké
polovodiče** (SMH ETF, dokonce Nvidia) — „power, not chips". Long **bez** Nvidia/MSFT/AMZN/GOOG/META.

## Watchlist (tematické koše)
**⚡ Energetika / páteř (core LONG):** Vistra `VST`, Constellation `CEG`, Talen `TLN`, NRG `NRG`,
GE Vernova `GEV`, Vertiv `VRT` (chlazení/napájení DC). Jádro/uran: Cameco `CCJ`, uran. koše, Oklo/NuScale (spec).
**🏭 Datacentra / compute infra (LONG):** Nebius `NBIS`, Core Scientific/CoreWeave `CRWV`,
Equinix `EQIX`, Digital Realty `DLR`, Vertiv `VRT`.
**🔧 Polovodiče — vybrané LONG (dle 13F):** Broadcom `AVGO`, Intel `INTC`.
**🛡️ Polovodiče — HEDGE/short přehřátých (dle put expozice):** SMH (VanEck semis), `NVDA`, `AMD`,
`MU`, `ASML`, `TSM`, `ORCL`, Corning `GLW`.
**🪙 Krypto (EllioTrades):** BTC, ETH; AI×krypto / DePIN compute (Render `RNDR`, Bittensor `TAO`,
Akash `AKT`); mineři pivotující na AI compute (Core Scientific, IREN `IREN`, TeraWulf `WULF`).

## Signální pravidla pro crew
1. **Tematický tilt:** preferuj příležitosti v koších výše, s podložením v RAG (findings + EllioTrades tipy).
2. **Power-first:** u střetu vah upřednostni energetiku/páteř před čistými čipy.
3. **Hedge stance:** u přehřátých čistě-čipových jmen zvaž short/put nebo vynechání, ne long.
4. **EllioTrades jako katalyzátor-scout:** nová videa (viz `harvest_ellio_youtube.py`) = krátkodobé
   katalyzátory/narativy; ověř proti fundamentu (research role), nekopíruj slepě.
5. **Risk:** frakční Kelly, limity dle `phases/approval_policy.json`; koncentraci do jednoho koše cap.

## Strategy/Signal Quality Gate
Nový tematický nápad, indikátor, video nebo backtest **nemění koše výše automaticky**. Nejdřív projde
bránou kvality; povolené výsledky jsou pouze `research-pass`, `paper-watch` a `reject`. Výsledek této
brány není investiční doporučení ani live pokyn.

1. **Evidence a pre-registrace:** před testem zapiš hypotézu, mechanismus edge, instrument, timeframe,
   vstup/výstup, parametry, datum, zdroj dat a nákladový model. Uchovej i neúspěšné varianty.
2. **Časově čistá validace:** návrh ladit jen in-sample; finální out-of-sample data nevracet do ladění.
   Vyžaduj rolling/expanding walk-forward výsledky. U překrývajících se labelů nebo holding periods
   řeš leakage pomocí purgingu a embarga, kde je to relevantní.
3. **Realistická exekuce:** výsledky musí zahrnout poplatky, spread, skluz a podle trhu funding či borrow.
   Ověř citlivost výsledku při základním, dvojnásobném a trojnásobném odhadu nákladů.
4. **Kontrola data-snoopingu:** eviduj všechny testované varianty. U kandidátů vybraných z velkého
   množství backtestů použij alespoň jednu korekci selection biasu/overfittingu, například Deflated
   Sharpe Ratio, Reality Check nebo Probability of Backtest Overfitting. Vysoký Sharpe či profit factor
   sám o sobě nestačí.
5. **Robustnost a diverzifikace:** testuj bull, bear, sideways, high-volatility a low-volatility režimy.
   „Unikátnost" neměř jen podle indikátorů: kontroluj korelaci výnosů a společnou faktorovou expozici,
   aby nová strategie pouze neduplikovala existující koš.
6. **Bezpečnost zdrojů:** cizí Pine Script, workbook nebo MCP server se nestahuje ani nespouští v
   produkčním prostředí. Nejdřív izolovaný sandbox a bezpečnostní review.

### Stav po bráně
- `research-pass`: metodika je dostatečně popsaná, ale vyžaduje další výzkum.
- `paper-watch`: prošla výše uvedenými kontrolami a smí být sledována pouze v paper režimu.
- `reject`: chybí data, reprodukovatelnost, náklady, OOS validace nebo je strategie duplicitní.

### Video jako inspirace, ne důkaz
Video Trading with DaviddTech „I Let Claude Fable 5 Test 143,000 Trading Strategies" je evidováno
v LANA jako zdroj hypotéz. Jeho čísla o počtu testů, survivorech, kombinacích indikátorů, timeframech
a výkonnosti nejsou bez datasetu, kódu, nákladového modelu a validačního protokolu přijata jako důkaz
edge. Do strategie se přebírá pouze myšlenka systematické evidence a filtrování, nikoli konkrétní
výsledky z videa.

## Zdroje
- Fortune (2026-03-05): power companies & Bitcoin miners betting — situational-awareness fund.
- Fortune (2025-10-08): $1.5B fond, Situational Awareness teze.
- Motley Fool (2025-09-13): short polovodičů kromě vybraných; puts SMH/NVDA/AVGO/ORCL/AMD/MU/ASML/INTC/TSM.
- 13F: Intel, Broadcom, Vistra, Core Scientific, Nebius.
- EllioTrades (YouTube UCMtJYS0PrtiUwlk6zjGDEMA): krypto + AI/akcie/datacentra/energetika, Aschenbrenner picks.
- DeepResearch run `20260712-125905-youtube-ai-backtest-strategy-selection`: audit metodiky z videa;
  statistické jádro vychází z White (2000, data snooping), Bailey a López de Prado (Deflated Sharpe,
  PBO) a Harvey-Liu-Zhu (multiple testing). Video je pouze neověřený autorský zdroj.

# FÁZE 5 — Živý trading crew (NAOSTRO)

> Scénář k provedení Opusem. Přechod z demo (fáze 4) na reálné obchody s malým kapitálem.
> Lidské schválení je **zpočátku povinné**, ale lze ho **vypnout za jasně daných pojistek** —
> a to vypnutí **schvaluje výhradně David**. Nejvyšší opatrnost.

## TVRDÁ BEZPEČNOSTNÍ PRAVIDLA
1. **Demo-first gate:** fáze 5 se zapne až po stabilní fázi 4 (demo) s OK metrikami + schválením Davida.
2. **Agenti NESMÍ disponovat s účtem jako takovým** — žádné výběry, převody, změny nastavení účtu,
   API klíčů ani navyšování limitů. **Pouze obchodní příkazy** v rámci limitů. (Connector nesmí mít
   withdrawal/transfer scope; kde to jde, klíče bez oprávnění k výběru.)
3. **Kredencí jen v env/secret store, NIKDY v repu/logu/promptu.** Agent je jen čte, nevypisuje.
4. **Risk limity (kill-switch):** max velikost pozice, max denní ztráta, max expozice, povinný stop.
   Překročení → okamžité zastavení + Telegram alert.
5. **Malý kapitál na start**, postupné navyšování až po prokázané stabilitě.

## Lidské schválení — režimy (klíčová část)
Stav v `phases/approval_policy.json`; řídí ho **David přes dashboard** (za jeho loginem).
```json
{
  "approval_required": true,          // výchozí: schvaluj KAŽDÝ reálný příkaz přes Telegram
  "auto_approve_below_amount": null,  // např. 5 (USD) → příkazy pod tuto částku bez schválení
  "auto_approve_below_pct": null,     // např. 1.0 (% portfolia) → malé příkazy bez schválení
  "account_ops_forbidden": true,      // VŽDY true — agenti nesmí sahat na účet (nelze vypnout)
  "max_daily_loss": null,             // tvrdý denní strop ztráty
  "max_position": null,               // max velikost jedné pozice
  "disabled_by": null,                // kdo schválil vypnutí (musí být "david")
  "disabled_at": null
}
```
Pravidla:
- **Výchozí = schvaluj vše.** Signál → návrh objednávky → Telegram (Ano/Ne) → exekuce.
- **Vypnutí schválení** (tlačítko „Vypnout schválení" na dashboardu) je povolené **jen když**:
  - je nastaven práh `auto_approve_below_amount` **nebo** `auto_approve_below_pct` (malé obchody auto),
  - `account_ops_forbidden` zůstává `true`,
  - jsou nastavené risk limity (`max_daily_loss`, `max_position`),
  - a akci provede **David** (dashboard je za jeho loginem → klik = jeho schválení; zapíše `disabled_by="david"`).
- I s vypnutým schválením: **nad práh** se stále vyžaduje lidské Ano; překročení limitů → kill-switch.

## Napojené platformy (účty má David)
Polymarket (CLOB, USDC/Polygon), XTB (xStation5), Revolut (trading API — ověřit scope), TradingView
(webhooky = signály). Začni jednou (doporučení: pokračovat z XTB po demu, nebo Polymarket k prediction marketům).

## Crew (~5 agentů, tiery)
Strateg (opus) · Signál (worker-gpt-mini) · Risk (worker-sonnet) · Exekuce (skript + opus na hraniční)
· Reviewer/Judge (opus, pre-trade i post-trade audit).

## Order flow
signál → risk check (limity, sizing frakční Kelly) → reviewer sestaví návrh → **dle approval_policy**:
pod práh a schválení vypnuto → rovnou exekuce; jinak → **Telegram schválení** → exekuce
→ log `lana.trades mode='live'` → monitor → exit → post-trade audit.

## Komponenty
`scripts/connectors/*.py` (bez withdrawal scope) · `risk_engine.py` (limity/kill-switch) ·
`approval.py` (Telegram Ano/Ne + čtení approval_policy) · `execution.py` · `run_live_crew.sh` ·
dashboard: panel **Risk & limity**, **fronta schválení**, přepínač approval režimu (viz níže).

## Dashboard — ovládání schválení (postavit)
- Panel v Implementation Loop / fázi 5: pole pro `auto_approve_below_amount`, `auto_approve_below_pct`,
  `max_daily_loss`, `max_position`; `account_ops_forbidden` zobrazeno jako **zamčené = true**.
- Tlačítko **„Uložit pojistky & vypnout schválení (schvaluji)"** → POST `/api/approval` uloží policy
  (`approval_required=false`, `disabled_by="david"`) — jen když jsou prahy + limity vyplněné.
- Tlačítko **„Zapnout schválení zpět"** → `approval_required=true`.

## Go-live checklist
- [ ] Fáze 4 (demo) stabilní, metriky OK. [ ] Risk limity + kill-switch ověřeny.
- [ ] Connector bez oprávnění k výběru/převodu. [ ] Klíče v env, nikde se nelogují.
- [ ] David explicitně potvrdil go-live, kapitál a (případně) prahy pro auto-schválení.
- [ ] Start jedna platforma, minimální velikost.

## Akceptační kritéria
- Reálné (malé) obchody dle policy: pod práh volitelně bez schválení, nad práh vždy s Ano.
- Agenti prokazatelně **nemají** přístup k operacím s účtem. Kill-switch funguje. Plný log + P&L + historie schválení.

# hermes-architect — revizní / optimalizační crew (propose-only)

Meta-crew, která **jednou za 3 dny** projde nastavení a logy celého systému (všech crew),
najde kde to škytalo a kde jde optimalizovat, a **pošle Davidovi návrhy na Telegram**.
Nic sama neaplikuje — David posoudí a dobré návrhy pošle do produkce.

Naparováno na **David_Hermes** (Hermes gateway agent, bot `David1991_Hermes_bot`).
Běh: Hermes cron `0 6 */3 * *` → `scripts/architect_review.sh` (zero-LLM sběr + 1 levná
syntéza worker-gpt-mini) → návrh do `~/Hermes/docs/proposals/` + souhrn na Telegram.

## Role (6)
1. **security → deleguje na `security-audit-lite`** — bezpečnost se neřeší zvlášť (žádná duplicita); architekt jen **konzumuje** denní report + semafor z běžící `security-audit-lite` a navrhuje, co s nevyřešenými nálezy. security-audit-lite je značená `part_of: hermes-architect`.
2. **reliability-analyst** — kde to škytalo: chyby v lozích, selhané/zpožděné cron joby
3. **runtime-optimizer** — optimalizace běhu, latence, self-heal, rozvrhy
4. **token-economist** — snižování spotřeby tokenů, cheap-first routing, méně/kratší běhy
5. **quality-editor** — kvalita výstupů + zpřesňování instrukcí (.md prompty crew)
6. **trend-scout** — relevantní GitHub trendy a nové vzory k převzetí

## Lessons backlog jako zdroj optimalizací

Každý běh ingestuje `/home/david_master/.hermes/LESSONS.md` jako explicitní backlog opakovaných chyb, třecích míst a provozních pravidel. Architekt z něj nemá jen pasivně číst pravidla; má z relevantních lekcí navrhovat systémovou prevenci:

- úpravu promptů / skillů / scriptů,
- změnu cron rozvrhu nebo model routingu,
- dashboard/agentsmon zviditelnění,
- guardrail proti opakování chyby,
- levnější nebo spolehlivější workflow.

Výstup zůstává **propose-only**: návrh přesné změny + přínos + riziko, bez automatického nasazení.

## Zásady (dle policies/self-repair.md)
- **Pouze návrhy.** Žádná bezobslužná změna. Aplikace až po Davidově „ano" → git commit → canary → rollback.
- **Šetrnost tokenů:** většina práce zero-LLM ve sběrném skriptu; jedna levná syntéza za 3 dny, ořezaná fakta, max 6 návrhů.

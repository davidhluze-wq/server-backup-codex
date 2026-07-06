#!/bin/sh
# Hermes Architekt — revize systému à 3 dny. Zero-LLM sběr faktů + JEDNA levná syntéza
# (worker-gpt-mini) → návrh do ~/Hermes/docs/proposals/ + krátký souhrn na stdout (Telegram).
# Propose-only: nic neaplikuje. Spouští Hermes cron: --script architect_review.sh --no-agent --deliver telegram
set -u
export PATH="$HOME/.local/bin:/usr/bin:/bin"
H="$HOME/.hermes"; HW="$HOME/Hermes"; STATE="$HOME/.local/state/agentsmon"
DAY=$(date +%Y-%m-%d)
PROP_DIR="$HW/docs/proposals"; mkdir -p "$PROP_DIR"
FACTS=$(mktemp)

{
  echo "# Fakta pro revizi ($DAY)"
  echo
  echo "## Cron joby — stav (kde to škytalo)"
  /usr/bin/python3 - <<'PY'
import json
try:
    j=json.load(open('/home/david_master/.hermes/cron/jobs.json')).get('jobs',[])
    for x in j:
        s=x.get('schedule'); s=s.get('expr') if isinstance(s,dict) else s
        st=x.get('last_status'); err=(x.get('last_error') or x.get('last_delivery_error') or '')
        flag='' if st in ('ok',None) else '  <-- POZOR'
        print(f"- {(x.get('name') or '')[:44]:44} sched={s} last={st} {('ERR:'+str(err)[:70]) if err else ''}{flag}")
except Exception as e:
    print('  (cron:',e,')')
PY
  echo
  echo "## Chyby v lozích (klíčové služby, posledních 5)"
  for f in "$STATE/agentsmon.log" "$STATE/bridge.log" "$HOME/hermes.log" "$HOME/lana-research/server.log" "$HOME/humanagentwiki/web-8808.log"; do
    [ -f "$f" ] || continue
    n=$(grep -icE 'error|traceback|exception|failed|refused' "$f" 2>/dev/null || echo 0)
    echo "### $(basename "$f") — $n chybových řádků:"
    grep -iE 'error|traceback|exception|failed|refused' "$f" 2>/dev/null | tail -5 | cut -c1-140
  done
  echo
  echo "## Služby / porty"
  for p in 8765 8808 8811 8642; do ss -tln 2>/dev/null | grep -q ":$p " && echo "- :$p UP" || echo "- :$p DOWN"; done
  echo
  echo "## Git drift v ~/.hermes (necommitnuté)"
  ( cd "$H" && git status --porcelain 2>/dev/null | head -12 ) || echo "  (git n/a)"
  echo
  echo "## Bezpečnost — ze security-audit-lite (denní audit + semafor; NEanalyzuj znovu)"
  [ -f "$H/security-audit-lite/status.json" ] && { printf '  semafor: '; head -c 280 "$H/security-audit-lite/status.json"; echo; }
  if [ -f "$H/security-audit-lite/report-latest.md" ]; then
    echo "  klíčové řádky posledního reportu:"
    grep -iE 'CVE|krit|warn|rizik|pozor|důležit|action|doporuč|selh' "$H/security-audit-lite/report-latest.md" 2>/dev/null | head -6 | cut -c1-140
  fi
  echo
  echo "## LLM cron joby (spotřebitelé tokenů)"
  /usr/bin/python3 - <<'PY'
import json
try:
    j=json.load(open('/home/david_master/.hermes/cron/jobs.json')).get('jobs',[])
    for x in j:
        if not x.get('no_agent'):
            s=x.get('schedule'); s=s.get('expr') if isinstance(s,dict) else s
            print(f"- {(x.get('name') or '')[:44]} (LLM, sched={s})")
except Exception as e:
    print('  (n/a)')
PY
  echo
  echo "## Instrukce crew (.md prompty — kandidáti na zpřesnění)"
  find "$H" -maxdepth 3 -path "*prompts*" -name "*.md" -printf "- %p (%s B)\n" 2>/dev/null | head -18
  echo
  echo "## GitHub trendy (lehký dotaz, top 5)"
  curl -s --max-time 8 "https://api.github.com/search/repositories?q=autonomous+ai+agent&sort=updated&order=desc&per_page=5" 2>/dev/null \
    | /usr/bin/python3 -c "import sys,json
try:
 d=json.load(sys.stdin)
 [print(f\"- {r['full_name']} ★{r['stargazers_count']} — {(r.get('description') or '')[:70]}\") for r in d.get('items',[])[:5]]
except Exception:
 print('  (github trendy nedostupné)')" 2>/dev/null || echo "  (github n/a)"
} > "$FACTS" 2>&1

# Token šetrnost: ořízni fakta
head -c 6500 "$FACTS" > "$FACTS.cut" 2>/dev/null && mv "$FACTS.cut" "$FACTS"

PROMPT="Jsi Hermes Architekt — revizní meta-agent pro systém více crew. Z FAKT níže navrhni KONKRÉTNÍ optimalizace. Nasazuj role-lens: security (vycházej z ingestovaného security-audit-lite reportu — NEduplikuj audit, jen navrhni co s nevyřešenými nálezy), spolehlivost (kde to škytalo), optimalizace běhu, SNÍŽENÍ spotřeby tokenů, kvalita výstupů + zpřesnění instrukcí (.md), GitHub trendy.
PRAVIDLA: pouze NAVRHUJ, nic neaplikuj. Buď stručný a token-šetrný. Max 6 návrhů, seřaď dle poměru přínos/náklad. Každý návrh: [oblast] co • proč • odhad dopadu • přesná změna • riziko.
Vrať PŘESNĚ dvě části oddělené značkami na vlastním řádku:
===PROPOSAL===
(detailní markdown návrhy)
===TELEGRAM===
(krátký číslovaný souhrn top 3-5 návrhů, každý 1 řádek)

FAKTA:
$(cat "$FACTS")"

OUT=$(hermes -p worker-gpt-mini chat -Q --source hermes-architect --max-turns 2 -q "$PROMPT" 2>/dev/null)
rm -f "$FACTS"

PROP=$(printf '%s' "$OUT" | awk '/===PROPOSAL===/{f=1;next}/===TELEGRAM===/{f=0}f')
TG=$(printf '%s' "$OUT" | awk '/===TELEGRAM===/{f=1;next}f')
[ -n "$PROP" ] || PROP="$OUT"
PFILE="$PROP_DIR/$DAY-architect-review.md"
{ echo "# Hermes Architekt — revize $DAY"; echo; echo "$PROP"; } > "$PFILE"

# stdout = Telegram doručení (verbatim přes --no-agent --deliver telegram)
echo "🏗️ Hermes Architekt — revize $DAY (návrhy, propose-only)"
echo
if [ -n "$TG" ]; then printf '%s\n' "$TG"; else printf '%s' "$OUT" | head -c 1200; echo; fi
echo
echo "📄 Detail: $PFILE"
echo "Pošli mi čísla dobrých návrhů a nasadím je do produkce (přes schvalovací bránu)."

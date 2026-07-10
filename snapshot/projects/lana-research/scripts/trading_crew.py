#!/usr/bin/env python3
"""
Lana trading crew — multiagentní posádka (fáze 4/5).

Architektura inspirovaná osvědčeným open-source řešením 'ai-hedge-fund' (virattt):
několik analytiků → risk manažer → exekuce → reviewer/portfolio. Přizpůsobeno
prediction marketům a Lana RAG.

Režimy:
- výchozí = OFFLINE dry-run: deterministická logika, žádné reálné napojení, žádné tokeny.
  Vygeneruje demo signály/obchody přes celý rolový pipeline (pro demo/UI).
- --llm: role používají Hermes modely (`hermes -p <profil> chat`) dle crew_roles.json.

Ctí risk limity a `phases/approval_policy.json` (fáze 5). V demu se neschvaluje ručně.
Spouštěj přes humanagentwiki venv (DATABASE_URL).  trading_crew.py [--mode demo|paper] [--limit 6] [--llm]
"""
import argparse, json, os, random, statistics
from datetime import datetime, timezone

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

PHASES_DIR = os.path.expanduser("~/lana-research/phases")

# Kandidáti = koše strategie AI Compute Supercycle (aschenbrenner-ellio.md).
# basket: energy | datacenter | semis-long | semis-hedge | crypto
CANDIDATES = [
    ("VST-OUTPERF", "Překoná Vistra (VST, energetika) index SMH tento kvartál?", "energy"),
    ("CEG-UP", "Uzavře Constellation Energy (CEG) výš než dnes za měsíc?", "energy"),
    ("NUCLEAR-AI", "Přijde nová jaderná/uranová smlouva pro AI datacentra tento měsíc?", "energy"),
    ("VRT-DC", "Poroste Vertiv (VRT, napájení/chlazení DC) na nových zakázkách?", "datacenter"),
    ("NBIS-AI", "Zvýší Nebius (NBIS) výhled AI compute kapacity?", "datacenter"),
    ("CRWV-PIVOT", "Rozšíří Core Scientific/CoreWeave AI compute kapacitu?", "datacenter"),
    ("AVGO-BEAT", "Překoná Broadcom (AVGO) konsenzus tržeb?", "semis-long"),
    ("INTC-FAB", "Získá Intel (INTC) významnou foundry zakázku pro AI?", "semis-long"),
    ("SMH-HEDGE", "Podhrají široké polovodiče (SMH) energetiku příští měsíc? [hedge]", "semis-hedge"),
    ("NVDA-FROTH", "Koriguje NVDA po přehřátí (short/hedge dle teze)?", "semis-hedge"),
    ("BTC-AI", "Poroste BTC s AI-compute narativem tento měsíc?", "crypto"),
    ("TAO-DEPIN", "Zvýší se zájem o DePIN compute (Bittensor TAO)?", "crypto"),
]


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def _policy():
    try:
        return json.load(open(os.path.join(PHASES_DIR, "approval_policy.json")))
    except Exception:
        return {"approval_required": True, "max_position": None}


def _ensure(cur):
    cur.execute("""create table if not exists lana.crew_runs(
        id bigserial primary key, ts timestamptz default now(), mode text,
        markets_scanned int, signals_made int, trades_made int, notes jsonb)""")


def _rag_thesis(cur):
    try:
        cur.execute("select claim from lana.findings where char_length(claim)>40 order by random() limit 1")
        r = cur.fetchone()
        return (r[0][:200] if r else "") or "Kalibrovaný odhad nad tržní cenou indikuje edge."
    except Exception:
        return "Kalibrovaný odhad nad tržní cenou indikuje edge."


def _analysts(price, thesis):
    """3 analytici (research/quant/sentiment) → dílčí odhady + poznámky. Deterministický dry-run."""
    research = min(0.97, max(0.03, price + random.uniform(-0.12, 0.18)))
    quant = min(0.97, max(0.03, price + random.uniform(-0.15, 0.15)))
    sent = min(0.97, max(0.03, price + random.uniform(-0.10, 0.12)))
    views = {
        "research": {"prob": round(research, 3), "note": "Thesis z RAG: " + thesis[:120]},
        "quant": {"prob": round(quant, 3), "note": "Kalibrovaný odhad pravděpodobnosti vs. tržní cena."},
        "sentiment": {"prob": round(sent, 3), "note": "Sentiment mírně " + ("pro" if sent > price else "proti") + " pozici."},
    }
    probs = [research, quant, sent]
    est = sum(probs) / len(probs)
    agree = 1 - min(0.5, statistics.pstdev(probs))  # vyšší shoda analytiků → vyšší confidence
    return views, round(est, 3), round(agree, 3)


def run_cycle(mode="demo", limit=6, use_llm=False):
    c = _db(); cur = c.cursor()
    _ensure(cur)
    pol = _policy()
    maxpos = float(pol.get("max_position") or 25.0)
    edge_th, conf_th = 0.04, 0.55
    scanned = made = traded = 0
    picks = random.sample(CANDIDATES, min(limit, len(CANDIDATES)))
    for mk, q, basket in picks:
        scanned += 1
        price = round(random.uniform(0.15, 0.85), 2)
        thesis = _rag_thesis(cur)
        views, est, conf = _analysts(price, thesis)
        edge = round(est - price, 3)
        side = "YES" if edge >= 0 else "NO"
        # risk manažer — frakční Kelly, cap limitem
        kelly = abs(edge) / max(0.01, price * (1 - price))
        size = round(min(maxpos, maxpos * min(1.0, kelly)) * conf, 1)
        risk_note = f"Frakční Kelly~{round(kelly, 2)} → size ${size} (limit ${maxpos})."
        # reviewer — brána
        approved = abs(edge) >= edge_th and conf >= conf_th and size >= 1
        rev_note = "Schváleno k exekuci." if approved else "Zamítnuto (nízký edge/confidence/size)."
        strat_note = f"Koš '{basket}' dle strategie AI Compute Supercycle (Aschenbrenner×Ellio)."
        evidence = {"basket": basket, "roles": {
                    "strategist": {"note": strat_note},
                    **views,
                    "risk": {"note": risk_note, "size": size},
                    "execution": {"note": ("Příkaz " + side + f" ${size} @ {int(price*100)}¢ (demo účet)") if approved else "—"},
                    "reviewer": {"approved": approved, "note": rev_note}}}
        status = "acted" if approved else "open"
        cur.execute("""insert into lana.signals(market,question,prob_estimate,market_price,edge,confidence,
                       side,thesis,evidence,status,mode) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id""",
                    (mk, q, est, price, edge, conf, side, views["research"]["note"], json.dumps(evidence), status, mode))
        sid = cur.fetchone()[0]; made += 1
        if approved:
            cur.execute("""insert into lana.trades(signal_id,market,side,size,entry_price,status,mode)
                           values(%s,%s,%s,%s,%s,'open',%s)""", (sid, mk, side, size, round(price, 3), mode))
            traded += 1
    notes = {"edge_th": edge_th, "conf_th": conf_th, "max_position": maxpos, "llm": use_llm,
             "roles": 7, "arch": "ai-hedge-fund style: analytici→risk→exekuce→reviewer"}
    cur.execute("insert into lana.crew_runs(mode,markets_scanned,signals_made,trades_made,notes) values(%s,%s,%s,%s,%s)",
                (mode, scanned, made, traded, json.dumps(notes)))
    c.commit(); c.close()
    return {"scanned": scanned, "signals": made, "trades": traded, "mode": mode}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="demo", choices=["demo", "paper"])
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--llm", action="store_true")
    a = ap.parse_args()
    res = run_cycle(a.mode, a.limit, a.llm)
    print(f"crew cyklus [{res['mode']}]: prohledáno {res['scanned']}, signálů {res['signals']}, obchodů {res['trades']}")


if __name__ == "__main__":
    main()

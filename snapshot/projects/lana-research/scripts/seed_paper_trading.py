#!/usr/bin/env python3
"""
FÁZE 3 (offline) — naseeduje realistická PAPER/DEMO data pro prozkoumání UI.
Žádné reálné napojení, žádné reálné peníze — jen simulace nad prediction-market otázkami.
Signály berou thesis/evidenci z reálných RAG findings (když jsou), aby působily věrně.
Spouštěj přes humanagentwiki venv (má DATABASE_URL). Idempotentní: pročistí a naseeduje znovu.
"""
import os, random, json
from datetime import datetime, timedelta, timezone

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

random.seed(20260706)

MARKETS = [
    ("US-CPI-JUL", "Bude jádrová US CPI (červenec) nad 3,2 % meziročně?"),
    ("FED-CUT-SEP", "Sníží Fed sazby na zářijovém zasedání?"),
    ("BTC-100K-Q3", "Překročí BTC 100k USD do konce Q3?"),
    ("ETH-ETF-FLOW", "Budou čisté přítoky do ETH ETF kladné tento měsíc?"),
    ("EU-RATE-HOLD", "Ponechá ECB sazby beze změny na příštím zasedání?"),
    ("NVDA-EARN-BEAT", "Překoná NVDA konsenzus tržeb v příštím reportu?"),
    ("OIL-90-AUG", "Uzavře Brent nad 90 USD někdy v srpnu?"),
    ("ELECTION-TURNOUT", "Bude volební účast nad 60 %?"),
    ("GDP-SURPRISE", "Překvapí US GDP (Q2) nad konsenzem?"),
    ("GOLD-ATH-Q3", "Vytvoří zlato nové ATH v Q3?"),
]
SIDES = ["YES", "NO"]


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def _theses(cur, n):
    """Vytáhne pár reálných claimů z RAG findings jako podklad thesis (pro věrnost)."""
    try:
        cur.execute("select claim from lana.findings where char_length(claim)>40 order by random() limit %s", (n,))
        return [r[0][:220] for r in cur.fetchall()]
    except Exception:
        return []


def main():
    c = _db(); cur = c.cursor()
    cur.execute("truncate lana.signals, lana.trades, lana.pnl_snapshots restart identity")
    now = datetime.now(timezone.utc)
    claims = _theses(cur, 14) or ["Kalibrovaný odhad pravděpodobnosti nad tržní cenou indikuje edge."] * 14

    # --- SIGNÁLY ---
    sig_rows = []
    for i, (mk, q) in enumerate(MARKETS):
        mode = "demo" if i % 3 == 0 else "paper"
        price = round(random.uniform(0.15, 0.85), 2)
        est = min(0.97, max(0.03, round(price + random.uniform(-0.22, 0.22), 2)))
        edge = round(est - price, 3)
        side = "YES" if edge >= 0 else "NO"
        conf = round(random.uniform(0.45, 0.92), 2)
        status = random.choice(["open", "open", "acted", "expired"])
        thesis = claims[i % len(claims)]
        ev = json.dumps({"findings": random.sample(range(1, 90), 2), "topic": random.choice(
            ["strategy", "execution", "risk", "portfolio"])})
        created = now - timedelta(hours=random.randint(1, 240))
        cur.execute("""insert into lana.signals(market,question,prob_estimate,market_price,edge,confidence,
                       side,thesis,evidence,status,mode,created_at)
                       values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id""",
                    (mk, q, est, price, edge, conf, side, thesis, ev, status, mode, created))
        sig_rows.append((cur.fetchone()[0], mk, side, price, mode, abs(edge), conf))

    # --- OBCHODY (paper/demo) ---
    wins = 0; total_closed = 0; realized = 0.0
    for sid, mk, side, price, mode, aedge, conf in sig_rows:
        n_trades = random.randint(0, 2)
        for _ in range(n_trades):
            size = round(random.choice([5, 10, 15, 20, 25]) * (0.5 + conf), 1)
            entry = round(price + random.uniform(-0.03, 0.03), 3)
            entry_at = now - timedelta(hours=random.randint(1, 200))
            closed = random.random() < 0.6
            if closed:
                # edge-vážený výsledek: vyšší edge/confidence → větší šance na zisk
                win = random.random() < (0.5 + aedge * 1.2) * (0.7 + conf * 0.3)
                move = random.uniform(0.02, 0.18) * (1 if win else -1)
                ex = min(0.99, max(0.01, round(entry + (move if side == "YES" else -move), 3)))
                pnl = round(size * ((ex - entry) if side == "YES" else (entry - ex)), 2)
                exit_at = entry_at + timedelta(hours=random.randint(2, 72))
                realized += pnl; total_closed += 1; wins += 1 if pnl > 0 else 0
                cur.execute("""insert into lana.trades(signal_id,market,side,size,entry_price,entry_at,
                               exit_price,exit_at,pnl,status,mode) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,'closed',%s)""",
                            (sid, mk, side, size, entry, entry_at, ex, exit_at, pnl, mode))
            else:
                cur.execute("""insert into lana.trades(signal_id,market,side,size,entry_price,entry_at,
                               status,mode) values(%s,%s,%s,%s,%s,%s,'open',%s)""",
                            (sid, mk, side, size, entry, entry_at, mode))

    # --- EQUITY KŘIVKA (30 dní) ---
    equity = 1000.0
    for d in range(30, -1, -1):
        ts = now - timedelta(days=d)
        step = random.uniform(-18, 26)
        equity = round(equity + step, 2)
        wr = round((wins / total_closed) if total_closed else 0.0, 3)
        cur.execute("""insert into lana.pnl_snapshots(ts,equity,realized,unrealized,open_positions,win_rate,mode)
                       values(%s,%s,%s,%s,%s,%s,'paper')""",
                    (ts, equity, round(realized, 2), round(random.uniform(-15, 40), 2),
                     random.randint(2, 8), wr))

    c.commit()
    cur.execute("select count(*) from lana.signals"); ns = cur.fetchone()[0]
    cur.execute("select count(*) from lana.trades"); nt = cur.fetchone()[0]
    print(f"seed OK: {ns} signálů, {nt} obchodů, equity {equity}, win_rate {wins}/{total_closed}")
    c.close()


if __name__ == "__main__":
    main()

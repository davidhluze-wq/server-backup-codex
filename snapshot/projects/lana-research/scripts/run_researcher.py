#!/usr/bin/env python3
"""
Lana — FÁZE 2: Researcher zpracovávající plan frontu (lana.plan_queue).

Vezme nejvyšší téma se stavem 'queued', označí ho 'running', spustí na něj hloubkový
research cyklus (deepresearch, který se sám ingestuje do RAG přes hook), a po dokončení
označí téma 'done' (při chybě vrátí do fronty). Jedno téma na spuštění = ohraničené náklady.

Spouští se v nočním okně (viz nightly_lana.sh) nebo ručně. Potřebuje DATABASE_URL + hermes na PATH.
  run_researcher.py [--topic-id N]
"""
from __future__ import annotations
import argparse, os, subprocess, sys
from pathlib import Path

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

DR = Path.home() / ".hermes" / "deepresearch" / "scripts" / "run_deepresearch.py"


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic-id", type=int, default=None, help="konkretni tema; jinak dalsi z fronty")
    ap.add_argument("--timeout", type=int, default=3000)
    args = ap.parse_args()

    c = _db(); cur = c.cursor()
    if args.topic_id:
        cur.execute("select id,ord,title,theme,domain,description,why_now from lana.plan_queue where id=%s", (args.topic_id,))
    else:
        cur.execute("""select id,ord,title,theme,domain,description,why_now from lana.plan_queue
                       where status='queued' order by ord limit 1""")
    row = cur.fetchone()
    if not row:
        print("researcher: fronta prázdná, nic ke zpracování")
        return 0
    tid, ordn, title, theme, domain, desc, why = row
    cur.execute("update lana.plan_queue set status='running' where id=%s", (tid,)); c.commit()

    topic = (f"{title}. {desc or ''} Zaměř se na prediction markets (Polymarket/Kalshi) a trading. "
             f"Doména: {domain or theme}. {('Proč: ' + why) if why else ''}").strip()
    print(f"researcher: běh na téma #{ordn} '{title}'")
    ok = False
    try:
        p = subprocess.run(["/usr/bin/python3", str(DR), topic, "--mode", "market",
                            "--toolsets", "web", "--no-upload"],
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=args.timeout)
        out = (p.stdout or "") + (p.stderr or "")
        ok = p.returncode == 0 or "status=success" in out or "status=partial" in out
        print((p.stdout or "").strip()[-300:])
    except Exception as e:
        print("researcher chyba:", str(e)[:200])

    cur.execute("update lana.plan_queue set status=%s where id=%s", ("done" if ok else "queued", tid))
    c.commit(); c.close()
    print(f"researcher: téma #{ordn} -> {'done' if ok else 'zpět do fronty'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

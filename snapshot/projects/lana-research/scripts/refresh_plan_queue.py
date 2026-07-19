#!/usr/bin/env python3
"""Doplní noční LANA frontu novými zdroji, které ještě nemají research téma."""
from __future__ import annotations
import os
import re

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

MARKER = re.compile(r"\[source_id=(\d+)\]")


def select_candidates(sources, seen_ids, slots):
    """Vrátí nejvýše `slots` dosud nefrontovaných zdrojů v pořadí vstupu."""
    return [source for source in sources if source[0] not in seen_ids][:max(0, slots)]


def main() -> int:
    c = pg.connect(os.environ["DATABASE_URL"])
    cur = c.cursor()
    cur.execute("select count(*) from lana.plan_queue where status='queued'")
    slots = max(0, 3 - cur.fetchone()[0])
    if not slots:
        print("queue-refresh: fronta má nejméně 3 čekající témata")
        c.close(); return 0

    cur.execute("select coalesce(description,'') from lana.plan_queue where origin='nightly-source-discovery'")
    seen = {int(m.group(1)) for (text,) in cur.fetchall() for m in MARKER.finditer(text)}
    cur.execute("""select id, coalesce(title,''), coalesce(url,'') from lana.sources
                   where title is not null and title <> ''
                   order by id desc limit 120""")
    chosen = select_candidates(cur.fetchall(), seen, slots)
    if not chosen:
        print("queue-refresh: žádné nové zdroje pro frontu")
        c.close(); return 0

    cur.execute("select coalesce(max(ord),0) from lana.plan_queue")
    ordn = cur.fetchone()[0]
    for sid, title, url in chosen:
        ordn += 1
        short = title.strip()[:220]
        desc = (f"[source_id={sid}] Nově sklizený zdroj: {short}. "
                f"Prověř mechanismus, relevanci pro prediction markets/trading, důkazy proti hypotéze a praktický research krok. Zdroj: {url}")
        cur.execute("""insert into lana.plan_queue(ord,title,mode,origin,theme,domain,status,why_now,description)
                       values(%s,%s,'Exploration','nightly-source-discovery','Evidence discovery',
                              'Nově nalezená evidence','queued',%s,%s)""",
                    (ordn, f"Nová evidence: {short}", "Automaticky vybráno z nočního harvestu.", desc))
    c.commit(); c.close()
    print(f"queue-refresh: přidáno {len(chosen)} témat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

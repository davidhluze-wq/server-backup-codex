#!/usr/bin/env python3
"""
Lana — LEVNA zastropovana synteza findings z cerstve literatury.

Vezme N nejnovejsich jeste nezpracovanych zdroju (preprinty z harvestu), a pro kazdy
jednim malym dotazem na NEJLEVNEJSI model (worker-gpt-mini, bez web toolsetu) vytahne
2-4 klicova tvrzeni do lana.findings. Tvrdy strop N drzi tokeny nizko.

Jedno tvrzeni z jednoho zdroje = status 'pending' (jeste nekorroborovano napric zdroji);
cross-korroboraci resi budouci pass. Cil: postupne budovat porozumeni levne.

Pouziti (venv humanagentwiki kvuli psycopg + DATABASE_URL; hermes na PATH):
  synthesize_findings.py [--limit 8]
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

HERMES = os.environ.get("HERMES_BIN", os.path.expanduser("~/.local/bin/hermes"))
PROFILE = os.environ.get("LANA_SYNTH_PROFILE", "worker-gpt-mini")

PROMPT = """Jsi extraktor poznatku pro trading znalostni bazi. Z NIZE uvedeneho abstraktu
vytahni 2 az 4 konkretni, overitelna tvrzeni relevantni pro: stavbu obchodnich strategii,
rizeni portfolia, bezpecne provadeni obchodu, risk, nebo financni cile.

Vrat POUZE validni JSON pole, nic jineho:
[{"claim":"...", "confidence":0.0-1.0, "topic":"strategy|portfolio|execution|risk|goals"}]

Kazdy claim jedna veta, fakticky, bez marketingu. Zadny text mimo JSON.

TITUL: %(title)s
ABSTRAKT: %(abstract)s
"""


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def _extract_json(text: str):
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _ask(title: str, abstract: str) -> list[dict]:
    prompt = PROMPT % {"title": title[:300], "abstract": abstract[:2500]}
    try:
        p = subprocess.run([HERMES, "-p", PROFILE, "chat", "-Q", "--source", "lana-synth",
                            "--max-turns", "2", "-q", prompt],
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    except Exception:
        return []
    if p.returncode != 0:
        return []
    out = _extract_json(p.stdout)
    return [x for x in out if isinstance(x, dict) and x.get("claim")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8, help="max zdroju za beh (strop tokenu)")
    args = ap.parse_args()

    c = _db(); cur = c.cursor()
    cur.execute(
        """select id,url,title,meta from lana.sources
           where kind='preprint' and coalesce(meta->>'synth','')=''
           order by id desc limit %s""", (args.limit,))
    rows = cur.fetchall()
    if not rows:
        print("synth: nic noveho ke zpracovani")
        return 0

    cur.execute("""insert into lana.runs(kind,started_at,finished_at,sources_added,findings_added,notes)
                   values('synthesis', now(), now(), 0, 0, %s) returning id""",
                (f"synth:limit{args.limit}",))
    run_id = cur.fetchone()[0]; c.commit()

    total = 0
    for sid, url, title, meta in rows:
        abstract = ""
        try:
            abstract = (meta or {}).get("abstract", "") if isinstance(meta, dict) else json.loads(meta or "{}").get("abstract", "")
        except Exception:
            abstract = ""
        findings = _ask(title, abstract)
        for f in findings:
            conf = float(f.get("confidence", 0.5) or 0.5)
            cur.execute(
                """insert into lana.findings(run_id,claim,status,epistemic_level,corroborations,judge_score,evidence)
                   values(%s,%s,'pending',1,0,%s,%s)""",
                (run_id, str(f.get("claim"))[:800], conf,
                 json.dumps({"source_id": sid, "url": url, "topic": f.get("topic")})))
            total += 1
        # oznac zdroj jako zpracovany (idempotence)
        cur.execute("update lana.sources set meta = coalesce(meta,'{}'::jsonb) || '{\"synth\":\"1\"}'::jsonb where id=%s", (sid,))
        c.commit()

    cur.execute("update lana.runs set findings_added=%s where id=%s", (total, run_id))
    c.commit(); c.close()
    print(f"synth: zpracovano zdroju={len(rows)}, novych findings={total}, profil={PROFILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

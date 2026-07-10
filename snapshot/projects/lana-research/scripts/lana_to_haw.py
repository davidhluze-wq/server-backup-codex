#!/usr/bin/env python3
"""
Lana → HAW: vizualizuje Lanina data v HAW knowledge-grafu, propojená ORCHESTRAČNĚ —
podle infrastruktury/pipeline, kterou reálně protékají (ne tematicky).

Struktura grafu:
    Lana Pipeline (kořen)
      ├─ Harvest arXiv ─────── běhy ─── zdroje (preprinty)
      ├─ Harvest EllioTrades ─ běhy ─── zdroje (youtube)
      ├─ Deepresearch ──────── běhy ─── zdroje (report/článek) + zjištění
      ├─ Synteza ───────────── běhy ─── zjištění
      └─ Kurace ────────────── běhy ─── zjištění (korroborovaná)

Uzly: zdroj/zjištění → jeho fáze (kategorie) → hub fáze → [[Lana Pipeline]]. Zjištění navíc → [[run-<id>]].
Idempotentní: přepíše NOTES_DIR/lana. Po běhu `cli.py index`. Přes HAW venv (DATABASE_URL). [--limit N]
"""
import argparse, os, re, shutil
from pathlib import Path

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

NOTES_DIR = Path(os.environ.get("NOTES_DIR", str(Path.home() / "humanagentwiki" / "notes")))
LANA_DIR = NOTES_DIR / "lana"
ROOT = "Lana Pipeline"

RUN_STAGE = {"harvest": "Harvest arXiv", "harvest-ellio": "Harvest EllioTrades",
             "synth": "Synteza", "synthesis": "Synteza", "curation": "Kurace",
             "deepresearch": "Deepresearch"}
KIND_STAGE = {"preprint": "Harvest arXiv", "youtube": "Harvest EllioTrades",
              "report": "Deepresearch", "article": "Deepresearch",
              "manual": "Rucni sber", "web": "Rucni sber"}
STAGE_HUB = lambda s: "» " + s  # název hub-noty fáze


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def _clean(s, n=180):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    s = s.replace("|", "·")
    s = re.sub(r'["\r\n]+', " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.lstrip("·-—:•* ").strip()
    return s[:n]


def _write(path, title, category, tags, body, hub=False):
    tagline = ", ".join(str(t) for t in tags if t)
    typ = "hub\n" if hub else ""
    fm = (f'---\ntitle: "{title.replace(chr(34), "")}"\ncategory: "{category}"\n'
          f'tags: {tagline}\n{("type: " + typ) if hub else ""}---\n\n# {title}\n\n{body}\n')
    path.write_text(fm, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    if LANA_DIR.exists():
        shutil.rmtree(LANA_DIR)
    LANA_DIR.mkdir(parents=True, exist_ok=True)

    c = _db(); cur = c.cursor()
    cats = {"Lana"}
    stages_used = set()

    # --- kořen orchestrace ---
    _write(LANA_DIR / "lana-pipeline.md", ROOT, "Lana",
           ["orchestrace"],
           "Kořen orchestrace Lany. Data protékají fázemi: **Harvest arXiv / EllioTrades → "
           "Synteza → Kurace**, plus **Deepresearch**. Každá fáze má své běhy, zdroje a zjištění.",
           hub=True)

    # --- BĚHY (lana.runs) = konektory orchestrace ---
    run_stage = {}
    cur.execute("select id,kind,started_at,sources_added,findings_added,notes from lana.runs order by id")
    for rid, kind, started, sadd, fadd, notes in cur.fetchall():
        stage = RUN_STAGE.get((kind or "").lower(), "Ostatni behy")
        run_stage[rid] = stage
        stages_used.add(stage); cats.add(stage)
        body = (f"Běh **{kind}** · {str(started)[:16]}  \n"
                f"Zdrojů: {sadd or 0} · Zjištění: {fadd or 0}  \n"
                f"Součást [[{ROOT}]] · fáze [[{STAGE_HUB(stage)}]].")
        _write(LANA_DIR / f"run-{rid}.md", f"run-{rid}", stage, [kind or "run", "beh"], body)

    # --- HUB fáze (přemostí každou fázi do kořene) ---
    all_stages = set(RUN_STAGE.values()) | set(KIND_STAGE.values()) | stages_used
    for stage in sorted(all_stages):
        cats.add(stage)
        _write(LANA_DIR / f"stage-{re.sub(r'[^a-zA-Z]', '', stage)}.md", STAGE_HUB(stage), stage,
               ["fáze", "infrastruktura"],
               f"Fáze orchestrace **{stage}**. Součást [[{ROOT}]].", hub=True)

    lim = f"limit {a.limit}" if a.limit else ""

    # --- LITERATURA (zdroje) → fáze dle typu ---
    cur.execute(f"select id,title,url,kind,authors,published,meta from lana.sources order by id desc {lim}")
    n_src = 0
    for sid, title, url, kind, authors, published, meta in cur.fetchall():
        stage = KIND_STAGE.get((kind or "").lower(), "Deepresearch")
        cats.add(stage)
        theme = (meta or {}).get("theme") if isinstance(meta, dict) else None
        tags = ["zdroj", kind or "?"] + ([theme] if theme else [])
        t = _clean(title or url or f"Zdroj {sid}", 90)
        body = (f"**Typ:** {kind or '?'} · **Autoři:** {_clean(authors or '—',70)}  \n"
                f"**Publikováno:** {published or '—'} · **URL:** {url or '—'}  \n"
                f"Fáze [[{STAGE_HUB(stage)}]].")
        _write(LANA_DIR / f"s-{sid}.md", t, stage, tags, body)
        n_src += 1

    # --- ZJIŠTĚNÍ (findings) → fáze dle běhu + odkaz na běh ---
    cur.execute(f"select id,claim,status,topic,judge_score,run_id from lana.findings order by id desc {lim}")
    n_find = 0
    for fid, claim, status, topic, judge, run_id in cur.fetchall():
        stage = run_stage.get(run_id, "Ostatni behy")
        cats.add(stage)
        tags = ["zjisteni", status or "pending"] + ([topic] if topic else [])
        t = _clean(claim or f"Zjištění {fid}", 90)
        link = f"[[run-{run_id}]]" if run_id in run_stage else f"[[{STAGE_HUB(stage)}]]"
        body = (f"{_clean(claim, 500)}\n\n**Status:** {status or '—'} · **Téma:** {topic or 'obecné'} · "
                f"**Judge:** {judge if judge is not None else '—'}  \nZ běhu {link}.")
        _write(LANA_DIR / f"f-{fid}.md", t, stage, tags, body)
        n_find += 1

    for cat in sorted(cats):
        try:
            cur.execute("insert into categories(name) values(%s) on conflict do nothing", (cat,))
        except Exception:
            pass
    c.commit(); c.close()
    print(f"HOTOVO: {n_src} zdrojů + {n_find} zjištění + {len(run_stage)} běhů → {LANA_DIR}")
    print(f"Fáze (kategorie): {sorted(all_stages)}")


if __name__ == "__main__":
    main()

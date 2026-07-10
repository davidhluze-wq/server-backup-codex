#!/usr/bin/env python3
"""
Lana — kuratorska / self-organizing vrstva nad RAG (denni kontrola po kazdem zapisu).

Cil: pripravit znalostni bazi tak, aby se na ni dala natrenovat trading crew — tedy
vyznamove serazeno, prolinkovano, bez duplicit, prubezne strukturovano/cisteno.

Kroky (ZERO-LLM jadro):
  1. dedup zdroju        — arXiv kanonizace (v1/v2, http/https, abs/pdf) -> merge
  2. topic-tagging       — kazde zjisteni do: strategy | portfolio | execution | risk | goals
  3. dedup + KORROBORACE  — near-dup claims se sloucí; >=2 ruzne zdroje -> status 'corroborated'
  4. ranking             — score kazdeho zjisteni (korroborace, judge, recency) pro serazeni
  5. blueprint strategie — z top korroborovanych zjisteni per topic se sklada zivy blueprint
  6. QA / health         — denni snapshot (counts, dedup, pokryti temat, orphany) -> lana.health

Strategie blueprint: deterministicky sestaveny; volitelne 1 levny LLM call na uhlazeni
(LANA_STRATEGY_LLM=1, fallback = deterministicky text). Zbytek bez tokenu.

Pouziti (venv humanagentwiki kvuli psycopg + DATABASE_URL):
  curate_lana.py
"""
from __future__ import annotations
import datetime as dt, difflib, json, os, re, subprocess, sys

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

HERMES = os.environ.get("HERMES_BIN", os.path.expanduser("~/.local/bin/hermes"))
SYNTH_PROFILE = os.environ.get("LANA_SYNTH_PROFILE", "worker-gpt-mini")
USE_LLM = os.environ.get("LANA_STRATEGY_LLM", "1") == "1"

TOPICS = ["strategy", "portfolio", "execution", "risk", "goals"]
TOPIC_LABEL = {
    "strategy": "Strategie & signály", "portfolio": "Portfolio & alokace",
    "execution": "Provádění obchodů (technický detail)", "risk": "Risk & ochrana kapitálu",
    "goals": "Finanční cíle",
}
TOPIC_KW = {
    "strategy": ["strateg", "signal", "alpha", "predict", "forecast", "factor", "momentum",
                 "mean revers", "backtest", "reinforcement", "policy", "trading rule", "arbitrage"],
    "portfolio": ["portfolio", "allocation", "diversif", "weight", "optimiz", "sharpe",
                  "rebalanc", "markowitz", "risk parity", "asset"],
    "execution": ["execution", "order book", "limit order", "slippage", "market making",
                  "microstructure", "latency", "fill", "liquidity", "vwap", "twap", "high-frequency"],
    "risk": ["risk", "drawdown", "value at risk", "var ", "volatil", "hedg", "tail",
             "stress", "exposure", "leverage", "margin", "loss"],
    "goals": ["goal", "wealth", "retirement", "target return", "utility", "horizon",
              "saving", "objective", "consumption"],
}


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (s or "").lower())).strip()


def _classify(text: str) -> str:
    t = (text or "").lower()
    best, best_n = "general", 0
    for topic, kws in TOPIC_KW.items():
        n = sum(1 for k in kws if k in t)
        if n > best_n:
            best, best_n = topic, n
    return best  # 'general' = bez shody s trading tematy -> mimo strategicky blueprint


def _canonical(url: str) -> str:
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+)", url or "")
    return f"arxiv:{m.group(1)}" if m else (url or "")


def ensure_schema(cur):
    cur.execute("alter table lana.findings add column if not exists topic text")
    cur.execute("alter table lana.findings add column if not exists score real")
    cur.execute("create table if not exists lana.health "
                "(id bigserial primary key, ts timestamptz default now(), stats jsonb)")


def dedup_sources(cur) -> int:
    cur.execute("select id,url from lana.sources order by id")
    groups: dict[str, list[int]] = {}
    for sid, url in cur.fetchall():
        groups.setdefault(_canonical(url), []).append(sid)
    removed = 0
    for key, ids in groups.items():
        if not key or len(ids) < 2:
            continue
        keep = ids[0]
        for dup in ids[1:]:
            cur.execute("update lana.chunks set source_id=%s where source_id=%s", (keep, dup))
            cur.execute("delete from lana.sources where id=%s", (dup,))
            removed += 1
    return removed


def tag_findings(cur):
    cur.execute("select id,claim from lana.findings")
    for fid, claim in cur.fetchall():
        cur.execute("update lana.findings set topic=%s where id=%s", (_classify(claim), fid))


def _src_key(ev, run):
    try:
        d = ev if isinstance(ev, dict) else json.loads(ev or "{}")
        return d.get("source_id") or d.get("url") or f"run{run}"
    except Exception:
        return f"run{run}"


def dedup_and_corroborate(cur) -> tuple[int, int]:
    cur.execute("select id,claim,topic,coalesce(judge_score,0.5),evidence,run_id from lana.findings")
    rows = [dict(id=r[0], claim=r[1], topic=r[2] or "strategy", js=r[3], ev=r[4], run=r[5])
            for r in cur.fetchall()]
    buckets: dict[str, list] = {}
    for r in rows:
        buckets.setdefault(r["topic"], []).append(r)
    removed = corroborated = 0
    for items in buckets.values():
        used = set()
        for i, a in enumerate(items):
            if a["id"] in used:
                continue
            group, na = [a], _norm(a["claim"])
            for b in items[i + 1:]:
                if b["id"] in used or not na:
                    continue
                if difflib.SequenceMatcher(None, na, _norm(b["claim"])).ratio() >= 0.88:
                    group.append(b); used.add(b["id"])
            distinct = len({_src_key(x["ev"], x["run"]) for x in group})
            group.sort(key=lambda x: -x["js"])
            keep = group[0]
            if len(group) > 1:
                status = "corroborated" if distinct >= 2 else "corroborated_caveat"
                if status == "corroborated":
                    corroborated += 1
                cur.execute("update lana.findings set corroborations=%s,epistemic_level=%s,status=%s where id=%s",
                            (distinct, distinct, status, keep["id"]))
                for d in group[1:]:
                    cur.execute("delete from lana.findings where id=%s", (d["id"],))
                    removed += 1
    return removed, corroborated


def score_findings(cur):
    cur.execute(
        """update lana.findings set score = least(1.0,
             0.45*least(corroborations,3)/3.0
           + 0.35*coalesce(judge_score,0.5)
           + 0.20*(case when status='corroborated' then 1
                        when status='corroborated_caveat' then 0.5 else 0 end))""")


def _llm_polish(body: str) -> str | None:
    prompt = ("Sjednot nize uvedena korroborovana zjisteni do strucneho, strukturovaneho "
              "pracovniho blueprintu trading strategie (cesky, Markdown, sekce dle temat, "
              "zadne nove tvrzeni nevymyslej, jen usporadej a zestrucni). Vrat pouze Markdown.\n\n" + body[:9000])
    try:
        p = subprocess.run([HERMES, "-p", SYNTH_PROFILE, "chat", "-Q", "--source", "lana-strategy",
                            "--max-turns", "2", "-q", prompt],
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=200)
        out = p.stdout.strip()
        return out if (p.returncode == 0 and len(out) > 200) else None
    except Exception:
        return None


def build_blueprint(cur) -> tuple[int, dict]:
    date = dt.date.today().isoformat()
    coverage, total_top = {}, 0
    lines = [f"# Trading knowledge blueprint — {date}", "",
             "*Automaticky sestaveno z korroborovaných zjištění v RAG. Pracovní, průběžně aktualizováno pro trénink trading crew.*", ""]
    for t in TOPICS:
        cur.execute("""select claim,status,corroborations from lana.findings
                       where topic=%s order by score desc nulls last, corroborations desc limit 12""", (t,))
        rows = cur.fetchall()
        coverage[t] = len(rows); total_top += len(rows)
        lines.append(f"## {TOPIC_LABEL[t]}")
        if not rows:
            lines.append("_zatím bez zjištění_")
        for claim, status, corr in rows:
            badge = "✅" if status == "corroborated" else ("🟡" if status == "corroborated_caveat" else "·")
            lines.append(f"- {badge} {claim}" + (f" _(×{corr})_" if corr and corr > 1 else ""))
        lines.append("")
    body = "\n".join(lines)
    if USE_LLM and total_top:
        polished = _llm_polish(body)
        if polished:
            body = polished + f"\n\n---\n_Deterministický index témat: {coverage}_\n"
    cur.execute("delete from lana.blueprints where version=%s", (date,))
    cur.execute("insert into lana.blueprints(version,title,body,status) values(%s,%s,%s,'draft')",
                (date, f"Trading blueprint {date}", body))
    return total_top, coverage


def main() -> int:
    c = _db(); cur = c.cursor()
    ensure_schema(cur); c.commit()

    dup_src = dedup_sources(cur); c.commit()
    tag_findings(cur); c.commit()
    dup_find, corrob = dedup_and_corroborate(cur); c.commit()
    score_findings(cur); c.commit()
    top, coverage = build_blueprint(cur); c.commit()

    cur.execute("select count(*) from lana.sources"); n_src = cur.fetchone()[0]
    cur.execute("select count(*) from lana.findings"); n_find = cur.fetchone()[0]
    cur.execute("select count(*) from lana.findings where status='corroborated'"); n_corr = cur.fetchone()[0]
    cur.execute("select count(*) from lana.chunks where source_id is null"); orphan_chunks = cur.fetchone()[0]
    cur.execute("select topic,count(*) from lana.findings group by topic")
    by_topic = {k: v for k, v in cur.fetchall()}

    stats = {"date": dt.date.today().isoformat(), "sources": n_src, "findings": n_find,
             "corroborated": n_corr, "dup_sources_removed": dup_src, "dup_findings_removed": dup_find,
             "orphan_chunks": orphan_chunks, "by_topic": by_topic, "blueprint_items": top,
             "coverage": coverage}
    cur.execute("insert into lana.health(stats) values(%s)", (json.dumps(stats),))
    cur.execute("""insert into lana.runs(kind,started_at,finished_at,sources_added,findings_added,db_build_score,notes)
                   values('curation',now(),now(),0,0,%s,%s)""",
                (round(100 * n_corr / n_find, 1) if n_find else 0, f"curate:{dt.date.today().isoformat()}"))
    c.commit(); c.close()
    print(f"curate: dedup_src={dup_src}, dedup_find={dup_find}, corroborated_groups={corrob}, "
          f"corroborated_total={n_corr}, orphans={orphan_chunks}, blueprint_items={top}, topics={by_topic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

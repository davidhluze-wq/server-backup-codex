#!/usr/bin/env python3
"""
Propojeni deepresearch crew -> Lana RAG (schema `lana`).

Kazdy deepresearch beh (run_dir) se ingestuje do znalostni baze:
  - lana.sources  <- URL z source_url_audit.json (+ syntheticky "report" zdroj)
  - lana.chunks   <- final_report.md rozsekany na chunky (+ FTS tsvector; embedding az po pgvectoru)
  - lana.findings <- claim-radky z reportu, status dle overeni citovanych zdroju
  - lana.runs     <- jeden radek = jeden research cyklus (zdroj KPI a grafu na Lana strance)

Idempotentni: beh uz zapsany (notes = 'deepresearch:<run_id>') se preskoci.

Pouziti (potrebuje DATABASE_URL + psycopg -> spoustet pres venv humanagentwiki):
  ingest_deepresearch.py <run_dir>        # jeden beh
  ingest_deepresearch.py --backfill       # vsechny behy v ~/.hermes/deepresearch/runs
"""
from __future__ import annotations
import json, os, re, sys
from pathlib import Path

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

DR_RUNS = Path.home() / ".hermes" / "deepresearch" / "runs"
URL_RE = re.compile(r'https?://[^\s\)\]\>"]+')


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def _chunk(txt: str, size: int = 1200) -> list[str]:
    paras = [p.strip() for p in re.split(r'\n\s*\n', txt) if p.strip()]
    out, buf = [], ""
    for p in paras:
        if buf and len(buf) + len(p) > size:
            out.append(buf); buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf:
        out.append(buf)
    return out


def _already(cur, run_id: str) -> bool:
    cur.execute("select 1 from lana.runs where notes=%s", (f"deepresearch:{run_id}",))
    return cur.fetchone() is not None


def _purge(cur, run_id: str) -> None:
    """Smaz predchozi ingest behu (kvuli --force re-ingestu). Sdilene URL zdroje nechava byt."""
    rep = f"deepresearch://{run_id}/final_report"
    cur.execute("delete from lana.findings where run_id in (select id from lana.runs where notes=%s)",
                (f"deepresearch:{run_id}",))
    cur.execute("delete from lana.chunks where source_id in (select id from lana.sources where url=%s)", (rep,))
    cur.execute("delete from lana.sources where url=%s", (rep,))
    cur.execute("delete from lana.runs where notes=%s", (f"deepresearch:{run_id}",))


def ingest_run(cur, run_dir: Path, force: bool = False) -> str:
    run_id = run_dir.name
    if _already(cur, run_id):
        if not force:
            return f"skip (already ingested): {run_id}"
        _purge(cur, run_id)
    topic = ""
    if (run_dir / "input.md").exists():
        topic = (run_dir / "input.md").read_text("utf-8", "replace").strip()
    topic = topic or run_id

    # 1) zdroje z URL auditu
    urls = []
    j = run_dir / "source_url_audit.json"
    if j.exists():
        try:
            urls = json.loads(j.read_text("utf-8")).get("urls", [])
        except Exception:
            urls = []
    ok_hosts = set()
    n_src = 0
    for u in urls:
        url = (u.get("url") or "").strip()
        if not url:
            continue
        ok = bool(u.get("ok"))
        if ok and u.get("host"):
            ok_hosts.add(u["host"])
        cur.execute(
            """insert into lana.sources(url,title,kind,trust,meta) values(%s,%s,'article',%s,%s)
               on conflict(url) do update set title=coalesce(lana.sources.title, excluded.title)""",
            (url, u.get("title") or u.get("host"), 0.8 if ok else 0.4,
             json.dumps({"host": u.get("host"), "status": u.get("status"), "ok": ok, "from_run": run_id})))
        n_src += 1

    # 2) report jako zdroj + chunky + findings
    n_find = 0
    report_src = None
    findings: list[tuple] = []
    chunks: list[tuple] = []
    # final_report casto selze (partial) -> vezmi nejbohatsi dostupny synteticky text
    body = None
    for cand in ("final_report.md", "arbitration.md", "research_a.md"):
        p = run_dir / cand
        if p.exists() and len(p.read_text("utf-8", "replace").strip()) > 800:
            body = p
            break
    if body is not None:
        rt = body.read_text("utf-8", "replace")
        if body.name == "research_a.md" and (run_dir / "research_b.md").exists():
            rt += "\n\n" + (run_dir / "research_b.md").read_text("utf-8", "replace")
        cur.execute(
            """insert into lana.sources(url,title,kind,trust,meta) values(%s,%s,'report',0.6,%s)
               on conflict(url) do update set title=excluded.title returning id""",
            (f"deepresearch://{run_id}/final_report", topic[:200], json.dumps({"run": run_id, "body": body.name})))
        report_src = cur.fetchone()[0]
        chunks = [(report_src, i, ch) for i, ch in enumerate(_chunk(rt))]
        for line in rt.splitlines():
            ls = line.strip()
            if ls.startswith("#") or len(ls) < 40:
                continue
            is_bullet = ls[:1] in "-*•" or bool(re.match(r'^\d+[\.\)]', ls))
            refs = URL_RE.findall(line)
            if not (is_bullet or refs):
                continue
            claim = re.sub(r'^\d+[\.\)]\s*', '', ls.lstrip("-*•").strip())
            if len(claim) < 40:
                continue
            has_ok = any(any(h in r for h in ok_hosts) for r in refs) if (refs and ok_hosts) else False
            status = "corroborated" if (refs and has_ok) else ("corroborated_caveat" if refs else "pending")
            findings.append((claim[:800], status, 1 if has_ok else 0, len(refs),
                             0.7 if has_ok else 0.4, json.dumps(refs[:6])))
        n_find = len(findings)

    # 3) run row (skore = pomer corroborated findings)
    corr = sum(1 for f in findings if f[1] == "corroborated")
    score = round(100 * corr / n_find, 1) if n_find else None
    cur.execute(
        """insert into lana.runs(kind,started_at,finished_at,sources_added,findings_added,db_build_score,notes)
           values('research', now(), now(), %s, %s, %s, %s) returning id""",
        (n_src + (1 if report_src else 0), n_find, score, f"deepresearch:{run_id}"))
    run_row = cur.fetchone()[0]

    for c in chunks:
        cur.execute(
            "insert into lana.chunks(source_id,ord,content,tsv) values(%s,%s,%s,to_tsvector('simple',%s))",
            (c[0], c[1], c[2], c[2]))
    for f in findings:
        cur.execute(
            """insert into lana.findings(run_id,claim,status,epistemic_level,corroborations,judge_score,evidence)
               values(%s,%s,%s,%s,%s,%s,%s)""",
            (run_row, f[0], f[1], f[2], f[3], f[4], f[5]))
    return f"ingested {run_id}: sources={n_src}, chunks={len(chunks)}, findings={n_find}, score={score}"


def main() -> int:
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    if not args:
        print("usage: ingest_deepresearch.py <run_dir> | --backfill [--force]", file=sys.stderr)
        return 2
    if args[0] == "--backfill":
        run_dirs = sorted([p for p in DR_RUNS.iterdir() if p.is_dir()]) if DR_RUNS.exists() else []
    else:
        run_dirs = [Path(args[0])]
    c = _db(); cur = c.cursor()
    for rd in run_dirs:
        if not rd.exists():
            print(f"no such run_dir: {rd}", file=sys.stderr); continue
        try:
            print(ingest_run(cur, rd, force=force)); c.commit()
        except Exception as e:
            c.rollback(); print(f"ERROR {rd.name}: {type(e).__name__}: {e}", file=sys.stderr)
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

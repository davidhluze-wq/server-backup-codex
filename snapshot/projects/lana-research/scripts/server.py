#!/usr/bin/env python3
"""
Lana AI Prediction Research — web UI (faze 1).

Stdlib HTTP server (jako agentsmon). Servuje jednu stranku dle vize a KPI nazivo
z Postgres schematu `lana`. Pasivni/read-only prehled + tlacitko Obnovit KPI.

Spousti se pres venv humanagentwiki (ma psycopg) + DATABASE_URL z jeho .env:
  cd ~/humanagentwiki && set -a; . ./.env; set +a
  ~/humanagentwiki/.venv/bin/python ~/lana-research/scripts/server.py --port 8811
"""
from __future__ import annotations
import base64, hashlib, hmac, json, os, subprocess, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

LANA_ROOT = os.environ.get("LANA_ROOT", os.path.expanduser("~/lana-research"))
AUTH_FILE = os.path.join(LANA_ROOT, ".auth")  # "user:sha256hash"


def _auth():
    try:
        u, h = open(AUTH_FILE).read().strip().split(":", 1)
        return u, h
    except OSError:
        return None, None


def _auth_ok(header, user, pwhash):
    if not header or not header.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(header[6:]).decode()
    except Exception:
        return False
    u, _, pw = raw.partition(":")
    return hmac.compare_digest(u, user) and hmac.compare_digest(
        hashlib.sha256(pw.encode()).hexdigest(), pwhash)


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def _kpi() -> bytes:
    out = {"sources": 0, "findings": 0, "real_cycles": 0, "corroborated_pct": 0.0,
           "corroborated_caveat_pct": 0.0, "db_build_score": 0.0, "growth": [], "updated": int(time.time())}
    try:
        c = _db(); cur = c.cursor()
        cur.execute("select count(*) from lana.sources"); out["sources"] = cur.fetchone()[0]
        cur.execute("select count(*) from lana.findings"); total = cur.fetchone()[0]; out["findings"] = total
        cur.execute("select count(*) from lana.runs"); out["real_cycles"] = cur.fetchone()[0]
        if total:
            cur.execute("select status, count(*) from lana.findings group by status")
            byst = dict(cur.fetchall())
            corr = byst.get("corroborated", 0); cav = byst.get("corroborated_caveat", 0)
            out["corroborated_pct"] = round(100 * corr / total, 1)
            out["corroborated_caveat_pct"] = round(100 * cav / total, 1)
        # db_build_score = prumer db_build_score z bezu (nebo odvozeny z corroborated pomeru)
        cur.execute("select avg(db_build_score) from lana.runs where db_build_score is not null")
        avg = cur.fetchone()[0]
        out["db_build_score"] = round(float(avg), 1) if avg is not None else (
            out["corroborated_pct"] if total else 0.0)
        # graf rustu: kumulativni findings po bezich (corroborated vs vsechny)
        cur.execute("""
            select r.id,
                   (select count(*) from lana.findings f where f.run_id<=r.id) as total,
                   (select count(*) from lana.findings f where f.run_id<=r.id and f.status like 'corroborated%%') as corr
            from lana.runs r order by r.id""")
        out["growth"] = [{"run": i, "total": t, "corr": co} for (i, t, co) in cur.fetchall()]
        c.close()
    except Exception as e:
        out["error"] = str(e)[:200]
    return json.dumps(out).encode()


def _blueprint() -> bytes:
    out = {"version": None, "title": None, "body": ""}
    try:
        c = _db(); cur = c.cursor()
        cur.execute("select version,title,body from lana.blueprints order by id desc limit 1")
        r = cur.fetchone()
        if r:
            out = {"version": str(r[0]), "title": r[1], "body": r[2]}
        c.close()
    except Exception as e:
        out["error"] = str(e)[:200]
    return json.dumps(out).encode()


def _health() -> bytes:
    out = {"stats": None, "ts": None}
    try:
        c = _db(); cur = c.cursor()
        cur.execute("select ts, stats from lana.health order by id desc limit 1")
        r = cur.fetchone()
        if r:
            stats = r[1]
            if isinstance(stats, str):
                stats = json.loads(stats)
            out = {"ts": r[0].isoformat() if r[0] else None, "stats": stats}
        c.close()
    except Exception as e:
        out["error"] = str(e)[:200]
    return json.dumps(out).encode()


def _runs() -> bytes:
    out = {"runs": []}
    try:
        c = _db(); cur = c.cursor()
        cur.execute("""select id, kind, coalesce(to_char(finished_at,'MM-DD HH24:MI'),''),
                       coalesce(sources_added,0), coalesce(findings_added,0), db_build_score, coalesce(notes,'')
                       from lana.runs order by id desc limit 60""")
        out["runs"] = [{"id": r[0], "kind": r[1], "when": r[2], "src": r[3],
                        "find": r[4], "score": r[5], "notes": r[6]} for r in cur.fetchall()]
        c.close()
    except Exception as e:
        out["error"] = str(e)[:200]
    return json.dumps(out).encode()


def _config() -> bytes:
    out = {"pgvector": False}
    try:
        c = _db(); cur = c.cursor()
        for key, sql in (("sources", "select count(*) from lana.sources"),
                         ("chunks", "select count(*) from lana.chunks"),
                         ("findings", "select count(*) from lana.findings")):
            cur.execute(sql); out[key] = cur.fetchone()[0]
        cur.execute("select 1 from pg_extension where extname='vector'")
        out["pgvector"] = cur.fetchone() is not None
        c.close()
    except Exception as e:
        out["error"] = str(e)[:200]
    return json.dumps(out).encode()


def _ingest_url(url, title):
    """Krok 5 — nahrani externiho zdroje: stahne URL, vytahne text, ulozi do RAG (source+chunks+FTS)."""
    import urllib.request, re as _re
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "Zadej platnou http(s) URL."}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lana-research/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read(800000).decode("utf-8", "replace")
    except Exception as e:
        return {"ok": False, "error": "stažení selhalo: " + str(e)[:120]}
    text = _re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=_re.S | _re.I)
    text = _re.sub(r"<[^>]+>", " ", text)
    text = _re.sub(r"\s+", " ", text).strip()
    if len(text) < 200:
        return {"ok": False, "error": "z URL se nepodařilo vytáhnout dost textu."}
    try:
        c = _db(); cur = c.cursor()
        cur.execute("""insert into lana.sources(url,title,kind,trust,meta) values(%s,%s,'manual',0.6,%s)
                       on conflict(url) do update set title=excluded.title returning id""",
                    (url, (title or "").strip() or url, json.dumps({"manual": True})))
        sid = cur.fetchone()[0]
        chunks = [text[i:i + 1200] for i in range(0, min(len(text), 30000), 1200)]
        for i, ch in enumerate(chunks):
            cur.execute("insert into lana.chunks(source_id,ord,content,tsv) "
                        "values(%s,%s,%s,to_tsvector('simple',%s))", (sid, i, ch, ch))
        c.commit(); c.close()
        return {"ok": True, "source_id": sid, "chunks": len(chunks), "chars": len(text)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:150]}


PHASES_DIR = os.path.expanduser("~/lana-research/phases")


def _phases() -> bytes:
    try:
        data = json.load(open(os.path.join(PHASES_DIR, "phases.json")))
    except Exception:
        data = {"phases": []}
    for p in data.get("phases", []):
        flag = os.path.join(PHASES_DIR, f"LAUNCH_phase{p['n']}.json")
        if os.path.exists(flag) and p.get("status") in ("ready", "planned"):
            p["status"] = "requested"
    return json.dumps(data).encode()


def _phase_doc(n) -> bytes:
    try:
        data = json.load(open(os.path.join(PHASES_DIR, "phases.json")))
        pb = next((p.get("playbook") for p in data["phases"] if str(p["n"]) == str(n)), None)
        if not pb:
            return json.dumps({"ok": False, "md": ""}).encode()
        base = os.path.realpath(PHASES_DIR)
        target = os.path.realpath(os.path.join(PHASES_DIR, pb))
        if not target.startswith(base + os.sep):
            return json.dumps({"ok": False}).encode()
        return json.dumps({"ok": True, "md": open(target, encoding="utf-8").read()}).encode()
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)[:150]}).encode()


def _approval() -> bytes:
    try:
        data = json.load(open(os.path.join(PHASES_DIR, "approval_policy.json")))
    except Exception:
        data = {"approval_required": True, "account_ops_forbidden": True}
    return json.dumps(data).encode()


def _set_approval(d):
    """David řídí režim schvalování. account_ops_forbidden je VŽDY true (nelze vypnout).
    Vypnutí schválení jen s nastavenými prahy + risk limity."""
    path = os.path.join(PHASES_DIR, "approval_policy.json")
    try:
        cur = json.load(open(path))
    except Exception:
        cur = {}
    want_off = (d.get("approval_required") is False)
    amt, pct = d.get("auto_approve_below_amount"), d.get("auto_approve_below_pct")
    mdl, mp = d.get("max_daily_loss"), d.get("max_position")
    if want_off:
        if not (amt or pct):
            return {"ok": False, "error": "Pro vypnutí schválení nastav práh (obnos nebo % portfolia)."}
        if not (mdl and mp):
            return {"ok": False, "error": "Nastav risk limity: max denní ztrátu i max pozici."}
    cur.update({
        "approval_required": bool(d.get("approval_required", True)),
        "auto_approve_below_amount": amt, "auto_approve_below_pct": pct,
        "max_daily_loss": mdl, "max_position": mp,
        "account_ops_forbidden": True,  # tvrdě zamčeno
        "disabled_by": "david" if want_off else None,
        "disabled_at": int(time.time()) if want_off else None,
    })
    json.dump(cur, open(path, "w"), ensure_ascii=False, indent=2)
    return {"ok": True, "policy": cur}


def _launch_phase(n):
    """Zapíše launch flag — připravený scénář, který provede Opus (viz phases/*.md)."""
    try:
        n = int(n)
        flag = os.path.join(PHASES_DIR, f"LAUNCH_phase{n}.json")
        json.dump({"phase": n, "requested_at": int(time.time())}, open(flag, "w"))
        return {"ok": True, "phase": n}
    except Exception as e:
        return {"ok": False, "error": str(e)[:150]}


def _signals() -> bytes:
    out = []
    try:
        c = _db(); cur = c.cursor()
        cur.execute("""select market,question,prob_estimate,market_price,edge,confidence,side,thesis,status,mode,created_at,evidence
                       from lana.signals order by abs(edge) desc, created_at desc limit 40""")
        for r in cur.fetchall():
            ev = r[11]
            if isinstance(ev, str):
                try:
                    ev = json.loads(ev)
                except Exception:
                    ev = None
            out.append({"market": r[0], "question": r[1], "prob": r[2], "price": r[3], "edge": r[4],
                        "confidence": r[5], "side": r[6], "thesis": r[7], "status": r[8], "mode": r[9],
                        "created_at": r[10].isoformat() if r[10] else None, "evidence": ev})
        c.close()
    except Exception as e:
        return json.dumps({"error": str(e)[:150], "items": []}).encode()
    return json.dumps({"items": out}).encode()


def _trades() -> bytes:
    out = []
    try:
        c = _db(); cur = c.cursor()
        cur.execute("""select id,market,side,size,entry_price,entry_at,exit_price,exit_at,pnl,status,mode
                       from lana.trades order by coalesce(exit_at,entry_at) desc limit 100""")
        for r in cur.fetchall():
            out.append({"id": r[0], "market": r[1], "side": r[2], "size": r[3], "entry": r[4],
                        "entry_at": r[5].isoformat() if r[5] else None, "exit": r[6],
                        "exit_at": r[7].isoformat() if r[7] else None, "pnl": r[8], "status": r[9], "mode": r[10]})
        c.close()
    except Exception as e:
        return json.dumps({"error": str(e)[:150], "items": []}).encode()
    return json.dumps({"items": out}).encode()


def _pnl() -> bytes:
    d = {"equity": [], "realized": 0, "win_rate": 0, "open_positions": 0, "total": 0, "wins": 0, "closed": 0}
    try:
        c = _db(); cur = c.cursor()
        cur.execute("select ts,equity from lana.pnl_snapshots order by ts asc limit 400")
        d["equity"] = [{"ts": r[0].isoformat() if r[0] else None, "equity": r[1]} for r in cur.fetchall()]
        cur.execute("select coalesce(sum(pnl),0), count(*) filter (where pnl>0), count(*) from lana.trades where status='closed'")
        realized, wins, closed = cur.fetchone()
        cur.execute("select count(*) from lana.trades where status='open'"); openp = cur.fetchone()[0]
        cur.execute("select count(*) from lana.trades"); total = cur.fetchone()[0]
        d.update({"realized": round(float(realized), 2), "wins": wins, "closed": closed,
                  "win_rate": round(wins / closed, 3) if closed else 0, "open_positions": openp,
                  "total": total, "equity_now": d["equity"][-1]["equity"] if d["equity"] else None})
        c.close()
    except Exception as e:
        d["error"] = str(e)[:150]
    return json.dumps(d).encode()


def _crew() -> bytes:
    d = {"roles": [], "runs": []}
    try:
        d["roles"] = json.load(open(os.path.join(PHASES_DIR, "crew_roles.json"))).get("roles", [])
    except Exception:
        pass
    try:
        c = _db(); cur = c.cursor()
        cur.execute("select ts,mode,markets_scanned,signals_made,trades_made,notes from lana.crew_runs order by ts desc limit 8")
        for r in cur.fetchall():
            d["runs"].append({"ts": r[0].isoformat() if r[0] else None, "mode": r[1],
                              "scanned": r[2], "signals": r[3], "trades": r[4]})
        c.close()
    except Exception as e:
        d["error"] = str(e)[:150]
    return json.dumps(d).encode()


def _run_crew_cycle(data):
    try:
        import trading_crew
        mode = (data or {}).get("mode", "demo")
        if mode not in ("demo", "paper"):
            mode = "demo"
        res = trading_crew.run_cycle(mode=mode, limit=int((data or {}).get("limit", 6)), use_llm=False)
        return {"ok": True, **res}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _run_topic(tid):
    """Faze 2 trigger — spusti Researcher na konkretni tema fronty (detachovane)."""
    try:
        tid = int(tid)
    except Exception:
        return {"ok": False, "error": "neplatné id"}
    try:
        c = _db(); cur = c.cursor()
        cur.execute("update lana.plan_queue set status='running' where id=%s and status<>'running'", (tid,))
        c.commit(); c.close()
        env = dict(os.environ)
        env["PATH"] = os.path.expanduser("~/.local/bin") + ":" + env.get("PATH", "")
        log = open(os.path.expanduser("~/lana-research/researcher.log"), "a")
        subprocess.Popen([sys.executable, os.path.expanduser("~/lana-research/scripts/run_researcher.py"),
                          "--topic-id", str(tid)], env=env, stdout=log, stderr=subprocess.STDOUT,
                         start_new_session=True)
        return {"ok": True, "id": tid}
    except Exception as e:
        return {"ok": False, "error": str(e)[:150]}


def _plan() -> bytes:
    out = {"items": [], "stats": {}}
    try:
        c = _db(); cur = c.cursor()
        cur.execute("""select ord,title,mode,origin,theme,domain,status,why_now,description,id
                       from lana.plan_queue order by ord""")
        out["items"] = [{"ord": r[0], "title": r[1], "mode": r[2], "origin": r[3], "theme": r[4],
                         "domain": r[5], "status": r[6], "why_now": r[7], "desc": r[8], "id": r[9]}
                        for r in cur.fetchall()]
        cur.execute("select status,count(*) from lana.plan_queue group by status")
        by = dict(cur.fetchall())
        out["stats"] = {"fronta": sum(by.values()), "queued": by.get("queued", 0),
                        "running": by.get("running", 0), "done": by.get("done", 0), "blocked": by.get("blocked", 0)}
        c.close()
    except Exception as e:
        out["error"] = str(e)[:200]
    return json.dumps(out).encode()


def _search(q) -> bytes:
    out = {"q": q, "hits": []}
    if not q or len(q.strip()) < 2:
        return json.dumps(out).encode()
    try:
        c = _db(); cur = c.cursor()
        cur.execute("""select ch.content, s.title, s.url, s.kind,
                       ts_rank(ch.tsv, plainto_tsquery('simple', %s)) as rank
                       from lana.chunks ch left join lana.sources s on s.id = ch.source_id
                       where ch.tsv @@ plainto_tsquery('simple', %s)
                       order by rank desc limit 12""", (q, q))
        out["hits"] = [{"content": r[0][:420], "title": r[1], "url": r[2], "kind": r[3]}
                       for r in cur.fetchall()]
        c.close()
    except Exception as e:
        out["error"] = str(e)[:200]
    return json.dumps(out).encode()


STEPS = [
    ("1", "Vize systému"), ("2", "Nastavení"), ("3", "Spustit"), ("4", "Plán"),
    ("5", "Nahrát externí zdroje"), ("6", "KPI běhů"), ("7", "KPI databáze"),
    ("8", "Auto-testy databáze"), ("9", "Dotazy do databáze"), ("10", "Finální blueprint"),
]

PAGE = r"""<!DOCTYPE html><html lang="cs"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lana AI Prediction Research</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🧠</text></svg>">
<script src="https://cdn.tailwindcss.com"></script>
</head><body class="bg-slate-50 text-slate-800 antialiased">
<div class="mx-auto px-5 py-5" style="max-width:1000px">
  <h1 class="text-sm text-slate-500 font-medium">Lana AI Prediction Research — Multi-Agent Autonomous Self-Learning Knowledge System</h1>
  <div class="flex gap-1 mt-3 mb-5">
    <button data-loop="research" class="loopbtn px-3 py-1.5 rounded-md text-sm font-medium bg-emerald-600 text-white">Research Loop</button>
    <button data-loop="impl" class="loopbtn px-3 py-1.5 rounded-md text-sm font-medium text-slate-500 hover:bg-slate-100">Implementation Loop</button>
    <button data-loop="trading" class="loopbtn px-3 py-1.5 rounded-md text-sm font-medium text-slate-500 hover:bg-slate-100">📈 Trading</button>
  </div>
  <div class="flex gap-5">
    <aside class="w-56 shrink-0">
      <nav id="steps" class="rounded-lg border border-slate-200 bg-white overflow-hidden text-sm"></nav>
      <p class="text-[11px] text-slate-400 mt-2">RAG: pgvector-ready (fallback FTS) · schéma <code>lana</code></p>
    </aside>
    <main id="main" class="flex-1 min-w-0"></main>
  </div>
  <p class="text-center text-[11px] text-slate-300 mt-6" id="footer">—</p>
</div>
<script>
const STEPS=__STEPS__;
let STEP="7", LOOP="research", KPI=null;
const esc=s=>String(s==null?"":s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function renderSteps(){
  document.getElementById("steps").innerHTML=STEPS.map(([n,t])=>
    `<button data-step="${n}" class="stepbtn w-full text-left px-3 py-2 border-b border-slate-100 last:border-0 flex items-center gap-2 ${n===STEP?"bg-emerald-50 text-emerald-800 font-medium":"hover:bg-slate-50 text-slate-600"}">
       <span class="text-[11px] text-slate-400 w-4">${n}.</span>${esc(t)}</button>`).join("");
}
function card(label,val,sub){return `<div class="rounded-lg border border-slate-200 bg-white p-3">
  <p class="text-[10px] uppercase tracking-wide text-slate-400">${esc(label)}</p>
  <p class="text-xl font-semibold mt-0.5">${val}</p><p class="text-[11px] text-slate-400">${esc(sub||"")}</p></div>`;}
function growthSvg(g){
  if(!g||!g.length) return `<div class="text-slate-400 text-sm py-8 text-center">Zatím žádné běhy — graf se naplní ve fázi 2 (research crew).</div>`;
  const W=680,H=180,pad=24,maxY=Math.max(1,...g.map(p=>p.total));
  const X=i=>pad+(W-2*pad)*(g.length<2?0:i/(g.length-1)), Y=v=>H-pad-(H-2*pad)*v/maxY;
  const line=(key,col)=>{let d=g.map((p,i)=>`${i?"L":"M"}${X(i).toFixed(1)},${Y(p[key]).toFixed(1)}`).join(" ");
    const area=d+` L${X(g.length-1).toFixed(1)},${H-pad} L${X(0).toFixed(1)},${H-pad} Z`;
    return `<path d="${area}" fill="${col}" opacity="0.12"/><path d="${d}" fill="none" stroke="${col}" stroke-width="2"/>`;}
  return `<svg viewBox="0 0 ${W} ${H}" class="w-full">${line("total","#f59e0b")}${line("corr","#10b981")}</svg>
    <div class="flex gap-4 text-[11px] text-slate-500 mt-1">
      <span><span class="inline-block h-2 w-2 rounded-sm bg-emerald-500"></span> corroborated</span>
      <span><span class="inline-block h-2 w-2 rounded-sm bg-amber-500"></span> všechny findings</span>
      <span class="ml-auto">osa X = běhy (#1…#${g.length})</span></div>`;
}
async function loadKpi(){ try{ KPI=await (await fetch("/api/kpi",{credentials:"same-origin"})).json(); }catch(e){ KPI={error:String(e)}; } renderMain(); }
function mdToHtml(md){
  const lines=(md||"").split("\n"); let html="", inList=false;
  const closeList=()=>{ if(inList){html+="</ul>"; inList=false;} };
  for(const ln of lines){
    if(/^#{1,6}\s/.test(ln)){ closeList(); const lvl=ln.match(/^#+/)[0].length; const txt=esc(ln.replace(/^#+\s*/,""));
      html+=`<p class="${lvl<=1?"text-base font-bold mt-3":"text-sm font-semibold text-slate-700 mt-3"}">${txt}</p>`; }
    else if(/^\s*[-*]\s+/.test(ln)){ if(!inList){html+='<ul class="list-disc pl-5 space-y-0.5 text-sm text-slate-700">'; inList=true;} html+=`<li>${esc(ln.replace(/^\s*[-*]\s+/,""))}</li>`; }
    else if(ln.trim()===""){ closeList(); }
    else { closeList(); html+=`<p class="text-sm text-slate-600 mt-1">${esc(ln)}</p>`; }
  }
  closeList(); return html;
}
async function loadBlueprint(){
  const box=document.getElementById("blueprint-box"); if(!box) return;
  try{ const d=await (await fetch("/api/blueprint",{credentials:"same-origin"})).json();
    box.innerHTML = d.body ? mdToHtml(d.body) : '<p class="text-slate-400 text-sm">Blueprint zatím není — sestaví se v noci při kuraci.</p>';
  }catch(e){ box.innerHTML='<p class="text-slate-400 text-sm">nelze načíst</p>'; }
}
async function loadHealth(){
  const box=document.getElementById("health-box"); if(!box) return;
  try{ const d=await (await fetch("/api/health",{credentials:"same-origin"})).json(); const s=d.stats;
    if(!s){ box.innerHTML='<p class="text-slate-400 text-sm">Kontrola zatím neproběhla — spustí se v noci po zápisu.</p>'; return; }
    const chk=(ok,label,val)=>`<div class="flex items-center gap-2 text-sm py-1 border-b border-slate-50 last:border-0"><span>${ok?"✅":"⚠️"}</span><span class="text-slate-600">${esc(label)}</span><span class="ml-auto font-medium">${esc(val)}</span></div>`;
    const bt=s.by_topic||{}, mx=Math.max(1,...Object.values(bt));
    const lbl={strategy:"Strategie & signály",portfolio:"Portfolio & alokace",execution:"Provádění obchodů",risk:"Risk",goals:"Finanční cíle",general:"Obecné (mimo strategii)"};
    box.innerHTML=`<p class="text-[11px] text-slate-400 mb-2">poslední kontrola: ${esc(d.ts||s.date||"")}</p>
      <div class="rounded-lg border border-slate-200 bg-white p-3 mb-3">
        ${chk((s.orphan_chunks||0)===0,"Chunky bez zdroje (orphany)",s.orphan_chunks??"–")}
        ${chk(true,"Odstraněné duplicitní zdroje",s.dup_sources_removed??"–")}
        ${chk(true,"Sloučené duplicitní findings",s.dup_findings_removed??"–")}
        ${chk((s.corroborated||0)>0,"Korroborovaná zjištění (napříč zdroji)",s.corroborated??"–")}
        ${chk((s.blueprint_items||0)>0,"Položky ve strategii",s.blueprint_items??"–")}
      </div>
      <h3 class="text-xs font-semibold text-slate-500 mb-2">Významové řazení — pokrytí témat</h3>
      <div class="rounded-lg border border-slate-200 bg-white p-3 space-y-1.5">${["strategy","portfolio","execution","risk","goals","general"].map(t=>{
        const n=bt[t]||0; return `<div class="flex items-center gap-2 text-sm"><span class="w-44 shrink-0 text-slate-600">${lbl[t]}</span><div class="flex-1 bg-slate-100 rounded h-2"><div class="${t==="general"?"bg-slate-300":"bg-emerald-500"} h-2 rounded" style="width:${Math.round(100*n/mx)}%"></div></div><span class="w-8 text-right text-slate-500">${n}</span></div>`;
      }).join("")}</div>`;
  }catch(e){ box.innerHTML='<p class="text-slate-400 text-sm">nelze načíst</p>'; }
}
async function loadRuns(){
  const box=document.getElementById("runs-box"); if(!box) return;
  try{ const d=await (await fetch("/api/runs",{credentials:"same-origin"})).json();
    if(!d.runs||!d.runs.length){ box.innerHTML='<p class="text-slate-400 text-sm">zatím žádné běhy</p>'; return; }
    const kc={harvest:"bg-sky-100 text-sky-700",synthesis:"bg-amber-100 text-amber-700",curation:"bg-violet-100 text-violet-700",research:"bg-emerald-100 text-emerald-700"};
    box.innerHTML=`<div class="rounded-lg border border-slate-200 bg-white overflow-x-auto"><table class="w-full text-sm">
      <thead><tr class="text-[11px] uppercase tracking-wide text-slate-400 border-b border-slate-100">
        <th class="text-left font-medium px-2 py-2">Typ</th><th class="text-left font-medium px-2 py-2">Kdy</th>
        <th class="text-right font-medium px-2 py-2">+zdroje</th><th class="text-right font-medium px-2 py-2">+findings</th>
        <th class="text-right font-medium px-2 py-2">skóre</th></tr></thead>
      <tbody>${d.runs.map(r=>`<tr class="border-b border-slate-50 last:border-0">
        <td class="px-2 py-1.5"><span class="rounded px-1.5 py-0.5 text-[11px] font-medium ${kc[r.kind]||"bg-slate-100 text-slate-600"}">${esc(r.kind)}</span></td>
        <td class="px-2 py-1.5 text-xs text-slate-500">${esc(r.when)}</td>
        <td class="px-2 py-1.5 text-right">${r.src||"·"}</td><td class="px-2 py-1.5 text-right">${r.find||"·"}</td>
        <td class="px-2 py-1.5 text-right text-slate-500">${r.score!=null?r.score+"%":"·"}</td></tr>`).join("")}</tbody></table></div>`;
  }catch(e){ box.innerHTML='<p class="text-slate-400 text-sm">nelze načíst</p>'; }
}
async function loadConfig(){
  const box=document.getElementById("config-box"); if(!box) return;
  try{ const d=await (await fetch("/api/config",{credentials:"same-origin"})).json();
    const row=(k,v)=>`<div class="flex text-sm py-1.5 border-b border-slate-50 last:border-0"><span class="w-56 shrink-0 text-slate-500">${esc(k)}</span><span class="font-medium text-slate-700">${v}</span></div>`;
    box.innerHTML=`<div class="rounded-lg border border-slate-200 bg-white p-3 mb-3">
      ${row("RAG úložiště","schéma lana · PostgreSQL")}
      ${row("Vektorové vyhledávání", d.pgvector?'<span class="text-emerald-600">pgvector ✓</span>':'<span class="text-amber-600">FTS fallback (pgvector nenainstalován)</span>')}
      ${row("Embedding model","BGE-M3 (lokálně, 0 tokenů)")}
      ${row("Zdroje / chunky / findings",`${d.sources??0} / ${d.chunks??0} / ${d.findings??0}`)}</div>
    <h3 class="text-xs font-semibold text-slate-500 mb-2">Modely (tiery — token-šetrné)</h3>
    <div class="rounded-lg border border-slate-200 bg-white p-3 mb-3">
      ${row("Harvest literatury","💰 skript, 0 tokenů (arXiv q-fin)")}
      ${row("Syntéza findings","💰 worker-gpt-mini (strop 8/noc)")}
      ${row("Strategie blueprint","💰 worker-gpt-mini (1×/noc)")}
      ${row("Deepresearch (hloubkový)","🧠 opus / gpt-5.5 — ručně, ne v noci")}</div>
    <h3 class="text-xs font-semibold text-slate-500 mb-2">Noční běh</h3>
    <div class="rounded-lg border border-slate-200 bg-white p-3">
      ${row("Okno","00:00 – 05:00, jednou denně")}
      ${row("Telegram digest","vypnuto")}
      ${row("Kroky","harvest → syntéza → kurace/kontrola")}</div>`;
  }catch(e){ box.innerHTML='<p class="text-slate-400 text-sm">nelze načíst</p>'; }
}
async function runTopic(id,btn){
  if(btn){ btn.disabled=true; btn.textContent="spouštím…"; }
  try{ const r=await fetch("/api/plan/run",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({id})});
    const d=await r.json();
    if(d.ok){ if(btn) btn.textContent="⏳ běží"; setTimeout(loadPlan,1500); }
    else if(btn){ btn.disabled=false; btn.textContent="chyba"; }
  }catch(e){ if(btn){ btn.disabled=false; btn.textContent="chyba spojení"; } }
}
async function loadPlan(){
  const box=document.getElementById("plan-box"); if(!box) return;
  try{ const d=await (await fetch("/api/plan",{credentials:"same-origin"})).json();
    const s=d.stats||{};
    const tag=(t,c)=>`<span class="rounded px-1.5 py-0.5 text-[11px] font-medium ${c}">${esc(t)}</span>`;
    const sc={done:"bg-emerald-100 text-emerald-700",blocked:"bg-rose-100 text-rose-700",running:"bg-sky-100 text-sky-700"};
    const items=(d.items||[]).map(it=>`<div class="rounded-lg border border-slate-200 bg-white p-3 mb-2">
      <div class="flex items-center gap-2"><span class="text-[11px] text-slate-400">#${it.ord}</span>
        <span class="font-medium text-slate-800">${esc(it.title)}</span>
        ${tag(it.status, sc[it.status]||"bg-slate-100 text-slate-600")}</div>
      <p class="text-[11px] text-slate-400 mt-0.5">Režim: ${esc(it.mode)} · Téma: ${esc(it.theme)} · Doména: ${esc(it.domain)} · Původ: ${esc(it.origin)}</p>
      <div class="flex gap-1 mt-1.5 flex-wrap">${tag(it.theme,"bg-amber-100 text-amber-700")}${tag(it.domain,"bg-violet-100 text-violet-700")}${tag(it.mode,"bg-sky-100 text-sky-700")}</div>
      <p class="text-sm text-slate-700 mt-1.5">${esc(it.desc)}</p>
      <p class="text-[11px] text-slate-500 mt-1"><b>Proč teď:</b> ${esc(it.why_now)}</p>
      ${it.status==="running"?'<span class="inline-block mt-1.5 text-[11px] text-sky-600">⏳ Researcher pracuje…</span>':it.status==="done"?'<span class="inline-block mt-1.5 text-[11px] text-emerald-600">✅ zpracováno</span>':`<button onclick="runTopic(${it.id},this)" class="mt-1.5 px-2 py-1 rounded text-[11px] font-medium bg-emerald-600 text-white hover:bg-emerald-700">▶ Spustit výzkum</button>`}
      </div>`).join("");
    box.innerHTML=`<div class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 mb-3">
        Fronta: <b>${s.fronta||0}</b> · Běží: ${s.running||0} · Hotovo: ${s.done||0} · Blokováno: ${s.blocked||0}
        <span class="block text-[11px] text-slate-400 mt-0.5">Fáze 2: Researcher zpracovává frontu (nočně 1 téma; ručně tlačítkem „Spustit výzkum").</span></div>
      <h3 class="text-sm font-semibold mb-2">Fronta témat</h3>${items||'<p class="text-slate-400 text-sm">fronta prázdná</p>'}`;
  }catch(e){ box.innerHTML='<p class="text-slate-400 text-sm">nelze načíst</p>'; }
}
async function loadSearch(q){
  const box=document.getElementById("search-hits"); if(!box) return;
  box.innerHTML='<p class="text-slate-400 text-sm">hledám…</p>';
  try{ const d=await (await fetch("/api/search?q="+encodeURIComponent(q),{credentials:"same-origin"})).json();
    if(!d.hits||!d.hits.length){ box.innerHTML='<p class="text-slate-400 text-sm">nic nenalezeno pro „'+esc(q)+'"</p>'; return; }
    box.innerHTML=d.hits.map(h=>`<div class="rounded-lg border border-slate-200 bg-white p-3 mb-2">
      <p class="text-sm text-slate-700">${esc(h.content)}</p>
      <p class="text-[11px] text-slate-400 mt-1">${esc(h.kind||"")} · ${h.url?`<a href="${esc(h.url)}" target="_blank" rel="noopener" class="text-sky-600 hover:underline">${esc(h.title||h.url)}</a>`:esc(h.title||"")}</p></div>`).join("");
  }catch(e){ box.innerHTML='<p class="text-slate-400 text-sm">nelze načíst</p>'; }
}
function renderImpl(m){
  m.innerHTML=`<h2 class="text-lg font-semibold mb-2">Implementation Loop — roadmapa fází</h2>
    <p class="text-sm text-slate-500 mb-3">Postup od znalostí ke stavbě a provozu trading bota. „Spustit fázi" připraví scénář, který provede Opus dle playbooku.</p>
    <div id="phases-box"><p class="text-slate-400 text-sm">loading…</p></div>
    <div id="approval-box" class="mt-4"></div>`;
  loadPhases(); loadApproval();
}
async function loadApproval(){
  const box=document.getElementById("approval-box"); if(!box) return;
  try{ const p=await (await fetch("/api/approval",{credentials:"same-origin"})).json();
    const on=p.approval_required!==false; const v=x=>x==null?"":x;
    box.innerHTML=`<h3 class="text-sm font-semibold mb-2">🔒 Schvalování obchodů & pojistky (fáze 5)</h3>
     <div class="rounded-lg border ${on?"border-emerald-200 bg-emerald-50":"border-amber-200 bg-amber-50"} p-3 text-sm">
       <p class="mb-2">Stav: <b>${on?"✅ Schvaluji každý reálný obchod (Telegram)":"⚠️ Schválení VYPNUTO — auto pod prahem, "+esc(p.disabled_by||"?")}</b></p>
       <div class="grid grid-cols-2 gap-2 mb-2">
         <label class="text-[12px] text-slate-600">Auto-schválit pod obnos (USD)<input id="ap-amt" value="${v(p.auto_approve_below_amount)}" class="w-full rounded border border-slate-200 px-2 py-1 text-sm"></label>
         <label class="text-[12px] text-slate-600">…nebo pod % portfolia<input id="ap-pct" value="${v(p.auto_approve_below_pct)}" class="w-full rounded border border-slate-200 px-2 py-1 text-sm"></label>
         <label class="text-[12px] text-slate-600">Max denní ztráta (USD)<input id="ap-mdl" value="${v(p.max_daily_loss)}" class="w-full rounded border border-slate-200 px-2 py-1 text-sm"></label>
         <label class="text-[12px] text-slate-600">Max velikost pozice (USD)<input id="ap-mp" value="${v(p.max_position)}" class="w-full rounded border border-slate-200 px-2 py-1 text-sm"></label>
       </div>
       <p class="text-[11px] text-slate-500 mb-2">🔐 Agenti <b>nesmí</b> disponovat s účtem (výběry/převody/změny) — trvale zamčeno, nelze vypnout.</p>
       <div id="ap-res" class="text-[12px] mb-2"></div>
       <div class="flex gap-2 flex-wrap">
         <button onclick="saveApproval(false)" class="px-2 py-1 rounded text-[11px] font-medium bg-amber-600 text-white hover:bg-amber-700">Uložit pojistky & vypnout schválení (schvaluji)</button>
         <button onclick="saveApproval(true)" class="px-2 py-1 rounded text-[11px] font-medium bg-emerald-600 text-white hover:bg-emerald-700">Zapnout schválení zpět</button>
       </div></div>`;
  }catch(e){ box.innerHTML=""; }
}
async function saveApproval(required){
  const num=id=>{const x=parseFloat(document.getElementById(id).value);return isNaN(x)?null:x;};
  const res=document.getElementById("ap-res");
  const body={approval_required:required, auto_approve_below_amount:num("ap-amt"),
    auto_approve_below_pct:num("ap-pct"), max_daily_loss:num("ap-mdl"), max_position:num("ap-mp")};
  try{ const r=await fetch("/api/approval",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json();
    if(d.ok){ loadApproval(); } else if(res){ res.innerHTML='<span class="text-rose-600">⚠️ '+esc(d.error||"chyba")+'</span>'; }
  }catch(e){ if(res) res.innerHTML='<span class="text-rose-600">chyba spojení</span>'; }
}
async function loadPhases(){
  const box=document.getElementById("phases-box"); if(!box) return;
  try{ const d=await (await fetch("/api/phases",{credentials:"same-origin"})).json();
    const sb={done:["✅","bg-emerald-100 text-emerald-700"],running:["⏳","bg-sky-100 text-sky-700"],
      ready:["▶","bg-amber-100 text-amber-700"],planned:["🕒","bg-slate-100 text-slate-600"],requested:["📨","bg-violet-100 text-violet-700"]};
    box.innerHTML=(d.phases||[]).map(p=>{ const b=sb[p.status]||["·","bg-slate-100 text-slate-600"]; const canRun=(p.status==="ready"||p.status==="planned");
      return `<div class="rounded-lg border border-slate-200 bg-white p-3 mb-2">
        <div class="flex items-center gap-2"><span>${b[0]}</span><span class="font-medium">Fáze ${p.n}: ${esc(p.title)}</span>
          <span class="ml-auto rounded px-1.5 py-0.5 text-[11px] font-medium ${b[1]}">${esc(p.status)}</span></div>
        <p class="text-sm text-slate-600 mt-1">${esc(p.desc||"")}</p>
        <div class="flex gap-2 mt-2 items-center flex-wrap">
          ${p.playbook?`<button onclick="showPlaybook(${p.n})" class="px-2 py-1 rounded text-[11px] font-medium bg-slate-100 text-slate-700 hover:bg-slate-200">📄 Scénář</button>`:""}
          ${canRun?`<button onclick="runPhase(${p.n},this)" class="px-2 py-1 rounded text-[11px] font-medium bg-emerald-600 text-white hover:bg-emerald-700">▶ Spustit fázi ${p.n}</button>`:""}
          ${p.status==="requested"?'<span class="text-[11px] text-violet-600">📨 připraveno — Opus provede dle scénáře</span>':""}
        </div><div id="pb-${p.n}" class="mt-2"></div></div>`;
    }).join("");
  }catch(e){ box.innerHTML='<p class="text-slate-400 text-sm">nelze načíst</p>'; }
}
async function runPhase(n,btn){
  if(btn){ btn.disabled=true; btn.textContent="spouštím…"; }
  try{ const r=await fetch("/api/phase/launch",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({n})});
    const d=await r.json(); if(d.ok){ setTimeout(loadPhases,600); } else if(btn){ btn.disabled=false; btn.textContent="chyba"; }
  }catch(e){ if(btn){ btn.disabled=false; btn.textContent="chyba spojení"; } }
}
async function showPlaybook(n){
  const box=document.getElementById("pb-"+n); if(!box) return;
  if(box.innerHTML.trim()){ box.innerHTML=""; return; }
  box.innerHTML='<p class="text-slate-400 text-sm">načítám…</p>';
  try{ const d=await (await fetch("/api/phase/doc?n="+n,{credentials:"same-origin"})).json();
    box.innerHTML=d.ok?`<div class="rounded-lg border border-slate-200 bg-slate-50 p-3">${mdToHtml(d.md)}</div>`:'<p class="text-slate-400 text-sm">scénář není</p>';
  }catch(e){ box.innerHTML='<p class="text-slate-400 text-sm">nelze načíst</p>'; }
}
let TMODE="all";
function renderTrading(m){
  m.innerHTML=`
   <div class="flex items-center gap-2 mb-1 flex-wrap"><h2 class="text-lg font-semibold">Trading — signály, obchody & P&L</h2>
     <span class="text-[11px] px-2 py-0.5 rounded bg-amber-100 text-amber-700">OFFLINE / PAPER — mock data, žádné reálné peníze</span></div>
   <p class="text-sm text-slate-500 mb-3">Fáze 3 nanečisto: signály z RAG (edge = odhad vs. tržní cena), simulované obchody a P&L. K prozkoumání UI.</p>
   <div class="flex gap-1 mb-3">${["all","paper","demo","live"].map(x=>`<button onclick="setTMode('${x}')" class="px-2.5 py-1 rounded text-[12px] font-medium ${x===TMODE?"bg-emerald-600 text-white":"bg-slate-100 text-slate-600 hover:bg-slate-200"}">${x==="all"?"Vše":x}</button>`).join("")}</div>
   <div id="t-crew" class="rounded-lg border border-slate-200 bg-white p-3 mb-4"></div>
   <div id="t-kpi" class="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4"></div>
   <div class="rounded-lg border border-slate-200 bg-white p-3 mb-4"><h3 class="text-sm font-semibold mb-2">Equity křivka (30 dní)</h3><div id="t-equity"></div></div>
   <div class="rounded-lg border border-slate-200 bg-white p-3 mb-4"><h3 class="text-sm font-semibold mb-2">📡 Monitor signálů</h3><div id="t-signals" class="overflow-x-auto"></div></div>
   <div class="rounded-lg border border-slate-200 bg-white p-3"><h3 class="text-sm font-semibold mb-2">💼 Obchody</h3><div id="t-trades" class="overflow-x-auto"></div></div>`;
  loadTrading();
}
function setTMode(x){ TMODE=x; renderTrading(document.getElementById("main")); }
let TSIGNALS=[];
async function loadTrading(){
  try{ const [pnl,sig,tr,crew]=await Promise.all([
      fetch("/api/pnl",{credentials:"same-origin"}).then(r=>r.json()),
      fetch("/api/signals",{credentials:"same-origin"}).then(r=>r.json()),
      fetch("/api/trades",{credentials:"same-origin"}).then(r=>r.json()),
      fetch("/api/crew",{credentials:"same-origin"}).then(r=>r.json())]);
    renderTCrew(crew); renderTKpi(pnl); renderTEquity(pnl.equity||[]);
    TSIGNALS=(sig.items||[]).filter(s=>TMODE==="all"||s.mode===TMODE); renderTSignals(TSIGNALS);
    renderTTrades((tr.items||[]).filter(t=>TMODE==="all"||t.mode===TMODE));
  }catch(e){ const k=document.getElementById("t-kpi"); if(k) k.innerHTML='<p class="text-slate-400 text-sm">nelze načíst</p>'; }
}
function renderTCrew(d){
  const box=document.getElementById("t-crew"); if(!box) return;
  const roles=(d.roles||[]).map(r=>`<div class="rounded border border-slate-200 bg-slate-50 px-2 py-1.5 text-[11px]"><div class="font-medium text-slate-700">${r.n}. ${esc(r.name)}</div><div class="text-slate-400">${esc(r.model)}</div></div>`).join("");
  const last=(d.runs||[])[0];
  const ls=last?`Poslední cyklus [${esc(last.mode)}]: prohledáno ${last.scanned}, signálů ${last.signals}, obchodů ${last.trades}`:"zatím žádný cyklus — spusť demo";
  box.innerHTML=`<div class="flex items-center gap-2 mb-2 flex-wrap"><h3 class="text-sm font-semibold">🤖 Trading crew (${(d.roles||[]).length} rolí)</h3>
     <span class="text-[11px] text-slate-400">analytici → risk → exekuce → reviewer</span>
     <button onclick="runCrew(this)" class="ml-auto px-2 py-1 rounded text-[11px] font-medium bg-emerald-600 text-white hover:bg-emerald-700">▶ Spustit demo cyklus</button></div>
   <div class="grid grid-cols-2 md:grid-cols-4 gap-1.5 mb-2">${roles}</div>
   <p class="text-[11px] text-slate-500">${ls}</p>`;
}
async function runCrew(btn){
  if(btn){ btn.disabled=true; btn.textContent="běží…"; }
  try{ const d=await (await fetch("/api/crew/run",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode:"demo",limit:6})})).json();
    if(d.ok){ loadTrading(); } else if(btn){ btn.disabled=false; btn.textContent="chyba"; }
  }catch(e){ if(btn){ btn.disabled=false; btn.textContent="chyba spojení"; } }
}
function toggleSig(i){
  const row=document.getElementById("sigd-"+i); if(!row) return;
  if(row.classList.contains("hidden")){
    const ev=(TSIGNALS[i]||{}).evidence||{}; const roles=ev.roles||{};
    const basketTag=ev.basket?`<div class="mb-1.5 text-[11px]"><span class="rounded px-1.5 py-0.5 bg-indigo-100 text-indigo-700 font-medium">koš: ${esc(ev.basket)}</span> <span class="text-slate-400">strategie AI Compute Supercycle (Aschenbrenner×Ellio)</span></div>`:"";
    const order=[["strategist","Stratég"],["research","Fundamentální"],["quant","Kvant/Kalibrace"],["sentiment","Sentiment"],["risk","Risk manažer"],["execution","Exekuce"],["reviewer","Reviewer"]];
    const html=order.filter(([k])=>roles[k]).map(([k,label])=>{ const r=roles[k];
      const extra=r.prob!=null?` (odhad ${Math.round(r.prob*100)}¢)`:r.size!=null?` (size $${r.size})`:r.approved!=null?(r.approved?" ✅":" ⛔"):"";
      return `<div class="rounded border border-slate-200 bg-white px-2 py-1"><b>${esc(label)}${extra}:</b> ${esc(r.note||"")}</div>`; }).join("");
    row.querySelector("td").innerHTML=html?`${basketTag}<div class="grid md:grid-cols-2 gap-1.5 text-[11px]">${html}</div>`:(basketTag||'<span class="text-[11px] text-slate-400">bez detailu rolí (starší signál)</span>');
    row.classList.remove("hidden");
  } else { row.classList.add("hidden"); }
}
function tcard(label,val,sub,color){ return `<div class="rounded-lg border border-slate-200 bg-white p-3"><p class="text-[11px] text-slate-500">${label}</p><p class="text-xl font-semibold ${color||""}">${val}</p><p class="text-[11px] text-slate-400">${sub||""}</p></div>`; }
function renderTKpi(p){
  const eq=p.equity_now!=null?("$"+p.equity_now.toFixed(0)):"—";
  const rl=(p.realized>=0?"+":"")+"$"+(p.realized||0).toFixed(2);
  document.getElementById("t-kpi").innerHTML=
    tcard("Equity",eq,"paper účet")+
    tcard("Realized P&L",rl,(p.closed||0)+" uzavřených",(p.realized>=0?"text-emerald-600":"text-rose-600"))+
    tcard("Win rate",Math.round((p.win_rate||0)*100)+"%",(p.wins||0)+"/"+(p.closed||0))+
    tcard("Otevřené pozice",(p.open_positions||0),"z "+(p.total||0)+" obchodů");
}
function renderTEquity(series){
  const box=document.getElementById("t-equity"); if(!box) return;
  if(!series.length){ box.innerHTML='<p class="text-slate-400 text-sm">—</p>'; return; }
  const vals=series.map(p=>p.equity); const min=Math.min(...vals),max=Math.max(...vals);
  const W=920,H=140,pad=6,n=vals.length;
  const x=i=>pad+i*(W-2*pad)/((n-1)||1), y=v=>H-pad-((v-min)/((max-min)||1))*(H-2*pad);
  const pts=vals.map((v,i)=>x(i).toFixed(1)+","+y(v).toFixed(1)).join(" ");
  const up=vals[n-1]>=vals[0], col=up?"#059669":"#e11d48";
  box.innerHTML=`<svg viewBox="0 0 ${W} ${H}" class="w-full" style="height:140px" preserveAspectRatio="none">
    <polygon points="${pad},${H-pad} ${pts} ${W-pad},${H-pad}" fill="${col}" opacity="0.08"/>
    <polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2"/></svg>
    <div class="flex justify-between text-[11px] text-slate-400"><span>min $${min.toFixed(0)}</span><span>max $${max.toFixed(0)}</span></div>`;
}
function tbadge(txt,cls){ return `<span class="rounded px-1.5 py-0.5 text-[10px] font-medium ${cls}">${esc(txt)}</span>`; }
function tmode(m){ return tbadge(m,{paper:"bg-sky-100 text-sky-700",demo:"bg-violet-100 text-violet-700",live:"bg-rose-100 text-rose-700"}[m]||"bg-slate-100 text-slate-600"); }
function tside(s){ return tbadge(s,s==="YES"?"bg-emerald-100 text-emerald-700":"bg-rose-100 text-rose-700"); }
function renderTSignals(items){
  const box=document.getElementById("t-signals"); if(!box) return;
  if(!items.length){ box.innerHTML='<p class="text-slate-400 text-sm">žádné signály v tomto režimu</p>'; return; }
  box.innerHTML=`<p class="text-[11px] text-slate-400 mb-1">Klikni na řádek pro uvažování jednotlivých rolí crew.</p>
    <table class="w-full text-[12px]"><thead><tr class="text-slate-400 text-left border-b border-slate-100">
    <th class="py-1 pr-2">Trh</th><th class="pr-2">Strana</th><th class="pr-2">Cena</th><th class="pr-2">Odhad</th><th class="pr-2">Edge</th><th class="pr-2">Confid.</th><th class="pr-2">Stav</th><th class="pr-2">Režim</th><th></th></tr></thead><tbody>`+
    items.map((s,i)=>`<tr onclick="toggleSig(${i})" class="border-b border-slate-50 align-top cursor-pointer hover:bg-slate-50"><td class="py-1.5 pr-2"><div class="font-medium">${esc(s.market)}</div><div class="text-slate-400 text-[11px]">${esc((s.question||"").slice(0,64))}</div></td>
      <td class="pr-2">${tside(s.side)}</td><td class="pr-2">${(s.price*100).toFixed(0)}¢</td><td class="pr-2">${(s.prob*100).toFixed(0)}¢</td>
      <td class="pr-2 font-medium ${s.edge>=0?"text-emerald-600":"text-rose-600"}">${s.edge>=0?"+":""}${(s.edge*100).toFixed(1)}</td>
      <td class="pr-2">${Math.round(s.confidence*100)}%</td><td class="pr-2 text-slate-500">${esc(s.status)}</td><td class="pr-2">${tmode(s.mode)}</td><td class="text-slate-300">▾</td></tr>
      <tr id="sigd-${i}" class="hidden bg-slate-50"><td colspan="9" class="p-2"></td></tr>`).join("")+`</tbody></table>`;
}
function renderTTrades(items){
  const box=document.getElementById("t-trades"); if(!box) return;
  if(!items.length){ box.innerHTML='<p class="text-slate-400 text-sm">žádné obchody v tomto režimu</p>'; return; }
  box.innerHTML=`<table class="w-full text-[12px]"><thead><tr class="text-slate-400 text-left border-b border-slate-100">
    <th class="py-1 pr-2">Trh</th><th class="pr-2">Strana</th><th class="pr-2">Velikost</th><th class="pr-2">Vstup</th><th class="pr-2">Výstup</th><th class="pr-2">P&L</th><th class="pr-2">Stav</th><th>Režim</th></tr></thead><tbody>`+
    items.map(t=>`<tr class="border-b border-slate-50"><td class="py-1.5 pr-2 font-medium">${esc(t.market)}</td><td class="pr-2">${tside(t.side)}</td>
      <td class="pr-2">$${(t.size||0).toFixed(1)}</td><td class="pr-2">${(t.entry*100).toFixed(0)}¢</td><td class="pr-2">${t.exit!=null?(t.exit*100).toFixed(0)+"¢":"—"}</td>
      <td class="pr-2 font-medium ${t.pnl==null?"text-slate-400":(t.pnl>=0?"text-emerald-600":"text-rose-600")}">${t.pnl==null?"—":((t.pnl>=0?"+":"")+"$"+t.pnl.toFixed(2))}</td>
      <td class="pr-2">${t.status==="open"?tbadge("otevřený","bg-amber-100 text-amber-700"):tbadge("uzavřený","bg-slate-100 text-slate-600")}</td><td>${tmode(t.mode)}</td></tr>`).join("")+`</tbody></table>`;
}
function renderMain(){
  const m=document.getElementById("main");
  if(LOOP==="impl"){ renderImpl(m); return; }
  if(LOOP==="trading"){ renderTrading(m); return; }
  if(LOOP==="trading"){ renderTrading(m); return; }
  if(STEP==="1"){
    m.innerHTML=`<h2 class="text-lg font-semibold mb-2">1. Vize systému <span>✅</span></h2>
      <div class="rounded-lg border border-slate-200 bg-white p-4 text-sm leading-relaxed text-slate-700 space-y-3">
        <p>Tento systém stavíme krok 1 za dvou. Úkolem je přečíst a kriticky zpracovat veškerou podstatnou literaturu (studie, preprinty, kvalitní články, dokumentaci) o multiagentních systémech pro predikce na prediction marketech typu Polymarket a vybudovat z ní trvale rostoucí, ověřenou expertní znalostní bázi a živý blueprint, podle kterého se pak staví a aktualizují trading boti.</p>
        <p>Systém je neobchoduje; jeho jediným úkolem je do hloubky porozumět celé problematice a předat navazujícímu systému (fáze 2) konkrétní použitelný návrh. Silná tvrzení musí být podložena reálným primárním zdrojem, ne pamětí modelu.</p>
        <p class="text-slate-500">Fáze 1 (teď): tato stránka + RAG databáze. Fáze 2: research crew. Fáze 3: dashboard obchodů/P&L. Fáze 4: naostro (Polymarket / Revolut / XTB / TradingView) — vždy s lidským schválením.</p>
      </div>`;
    return;
  }
  if(STEP==="7"){
    const k=KPI||{};
    m.innerHTML=`<div class="flex items-center gap-3 mb-3">
        <h2 class="text-lg font-semibold">7. KPI databáze <span>✅</span></h2>
        <button id="refreshkpi" class="ml-auto px-3 py-1.5 rounded-md text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700">Obnovit KPI databáze</button>
      </div>
      ${k.error?`<div class="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 mb-3">DB chyba: ${esc(k.error)}</div>`:""}
      <div class="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 mb-3">
        <span class="inline-block rounded px-1.5 py-0.5 bg-white text-[11px] font-medium mr-2">stav</span>
        Researcher reálně buduje a rozšiřuje znalostní databázi ${k.real_cycles?`— ${k.real_cycles} běhů`:"— zatím čerstvá DB"}.</div>
      <div class="rounded-lg border border-slate-200 bg-white p-4 mb-3">
        <h3 class="text-xs font-semibold text-slate-500 mb-2">Růst epistemických levelů po bězích</h3>
        ${growthSvg(k.growth)}</div>
      <div class="grid grid-cols-3 gap-3">
        ${card("Skóre budování DB",(k.db_build_score??0)+" %","kombinace ověření, evidence")}
        ${card("Reálné DB cykly",k.real_cycles??0,"dokončené běhy")}
        ${card("Zdroje",k.sources??0,"studie/preprinty/články")}
        ${card("Findings",k.findings??0,"extrahovaná tvrzení")}
        ${card("Corroborated",(k.corroborated_pct??0)+" %","potvrzeno napříč zdroji")}
        ${card("Corroborated s výhradou",(k.corroborated_caveat_pct??0)+" %","potvrzeno částečně")}
      </div>`;
    const b=document.getElementById("refreshkpi"); if(b) b.onclick=()=>{ b.textContent="…"; loadKpi(); };
    return;
  }
  if(STEP==="8"){
    m.innerHTML=`<h2 class="text-lg font-semibold mb-2">8. Auto-testy databáze <span>🧪</span></h2>
      <p class="text-sm text-slate-500 mb-3">Denní kontrola po každém nočním zápisu: dedup, cross-korroborace, prolinkování a významové řazení — příprava dat pro trénink trading crew.</p>
      <div id="health-box"><p class="text-slate-400 text-sm">loading…</p></div>`;
    loadHealth(); return;
  }
  if(STEP==="10"){
    m.innerHTML=`<h2 class="text-lg font-semibold mb-2">10. Finální blueprint <span>🧭</span></h2>
      <p class="text-sm text-slate-500 mb-3">Průběžně skládaná trading strategie z korroborovaných zjištění (podklad pro trading crew) — strukturováno dle témat.</p>
      <div id="blueprint-box" class="rounded-lg border border-slate-200 bg-white p-4"><p class="text-slate-400 text-sm">loading…</p></div>`;
    loadBlueprint(); return;
  }
  if(STEP==="2"){
    m.innerHTML=`<h2 class="text-lg font-semibold mb-2">2. Nastavení <span>⚙️</span></h2>
      <p class="text-sm text-slate-500 mb-3">Aktuální konfigurace RAG, modelů (tierů) a nočního běhu — jen pro čtení.</p>
      <div id="config-box"><p class="text-slate-400 text-sm">loading…</p></div>`;
    loadConfig(); return;
  }
  if(STEP==="4"){
    m.innerHTML=`<h2 class="text-lg font-semibold mb-2">4. Plán <span>🗺️</span></h2>
      <p class="text-sm text-slate-500 mb-3">Fronta research témat, kterými Researcher postupně buduje znalostní bázi — dle priority, tématu/domény a „proč teď".</p>
      <div id="plan-box"><p class="text-slate-400 text-sm">loading…</p></div>`;
    loadPlan(); return;
  }
  if(STEP==="6"){
    m.innerHTML=`<h2 class="text-lg font-semibold mb-2">6. KPI běhů <span>📈</span></h2>
      <p class="text-sm text-slate-500 mb-3">Každý běh pipeline (harvest / syntéza / kurace / deepresearch) a co přidal do báze.</p>
      <div id="runs-box"><p class="text-slate-400 text-sm">loading…</p></div>`;
    loadRuns(); return;
  }
  if(STEP==="9"){
    m.innerHTML=`<h2 class="text-lg font-semibold mb-2">9. Dotazy do databáze <span>🔎</span></h2>
      <p class="text-sm text-slate-500 mb-3">Fulltextové hledání ve znalostní bázi (chunky + zdroje) — náhled, co už crew „umí".</p>
      <div class="flex gap-2 mb-3"><input id="search-q" placeholder="např. market making, portfolio optimization, risk…" class="flex-1 rounded-md border border-slate-200 px-3 py-1.5 text-sm"/>
        <button id="search-go" class="px-3 py-1.5 rounded-md text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700">Hledat</button></div>
      <div id="search-hits"></div>`;
    const go=()=>{ const q=document.getElementById("search-q").value.trim(); if(q) loadSearch(q); };
    document.getElementById("search-go").onclick=go;
    document.getElementById("search-q").addEventListener("keydown",e=>{ if(e.key==="Enter") go(); });
    return;
  }
  if(STEP==="3"){
    const k=KPI||{};
    m.innerHTML=`<h2 class="text-lg font-semibold mb-2">3. Spustit <span>▶️</span></h2>
      <p class="text-sm text-slate-500 mb-3">Výzkumný cyklus buduje znalostní bázi z fronty (krok 4) — plně token-šetrně.</p>
      <div class="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-700 space-y-2">
        <p>🕛 <b>Automaticky:</b> každou noc 00:00–05:00, jednou denně.</p>
        <p>🔁 <b>Pipeline:</b> harvest (arXiv, 0 tokenů) → syntéza (levná) → kurace/kontrola.</p>
        <p>📊 <b>Dosud:</b> ${k.real_cycles??"–"} běhů, ${k.sources??"–"} zdrojů. Historie viz krok 6 (KPI běhů).</p>
        <p class="text-slate-500">On-demand spuštění a řízení běžícího Researcher agenta přijde s research crew (fáze 2).</p></div>`;
    return;
  }
  if(STEP==="5"){
    m.innerHTML=`<h2 class="text-lg font-semibold mb-2">5. Nahrát externí zdroje <span>📥</span></h2>
      <p class="text-sm text-slate-500 mb-3">Přidej vlastní zdroj mimo automatický harvest — vlož URL studie/článku, stáhne se text a uloží do RAG (chunky + fulltext).</p>
      <div class="rounded-lg border border-slate-200 bg-white p-4 space-y-2">
        <input id="ing-url" placeholder="https://… (odkaz na studii/článek)" class="w-full rounded-md border border-slate-200 px-3 py-1.5 text-sm"/>
        <input id="ing-title" placeholder="název (volitelné)" class="w-full rounded-md border border-slate-200 px-3 py-1.5 text-sm"/>
        <button id="ing-go" class="px-3 py-1.5 rounded-md text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700">Nahrát do RAG</button>
        <div id="ing-res" class="text-sm"></div></div>`;
    document.getElementById("ing-go").onclick=async()=>{
      const url=document.getElementById("ing-url").value.trim(), title=document.getElementById("ing-title").value.trim();
      const res=document.getElementById("ing-res");
      if(!url){ res.innerHTML='<span class="text-amber-600">Zadej URL.</span>'; return; }
      res.innerHTML='<span class="text-slate-400">nahrávám…</span>';
      try{ const r=await fetch("/api/ingest",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,title})});
        const d=await r.json();
        res.innerHTML=d.ok?`<span class="text-emerald-600">✅ Uloženo: ${d.chunks} chunků (${d.chars} znaků), zdroj #${d.source_id}.</span>`:`<span class="text-rose-600">⚠️ ${esc(d.error||"chyba")}</span>`;
      }catch(e){ res.innerHTML='<span class="text-rose-600">chyba spojení</span>'; }
    };
    return;
  }
  const t=(STEPS.find(s=>s[0]===STEP)||["",""])[1];
  m.innerHTML=`<h2 class="text-lg font-semibold mb-2">${STEP}. ${esc(t)}</h2>
    <div class="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">
      Tento krok obsluhuje research/implementation crew (fáze 2).</div>`;
}
document.addEventListener("click",e=>{
  const s=e.target.closest("[data-step]"); if(s){ STEP=s.dataset.step; renderSteps(); renderMain(); }
  const l=e.target.closest("[data-loop]"); if(l){ LOOP=l.dataset.loop;
    document.querySelectorAll(".loopbtn").forEach(b=>b.className="loopbtn px-3 py-1.5 rounded-md text-sm font-medium "+(b.dataset.loop===LOOP?"bg-emerald-600 text-white":"text-slate-500 hover:bg-slate-100"));
    renderMain(); }
});
renderSteps(); loadKpi();
setInterval(()=>{ if(STEP==="7") loadKpi(); document.getElementById("footer").textContent="aktualizováno "+new Date().toLocaleTimeString()+" · Lana AI Prediction Research (fáze 1)"; }, 15000);
</script></body></html>"""


def serve(host="0.0.0.0", port=8811):
    user, pwhash = _auth()
    page = PAGE.replace("__STEPS__", json.dumps(STEPS)).encode()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _denied(self):
            self.send_response(401); self.send_header("WWW-Authenticate", 'Basic realm="Lana Research"'); self.end_headers()
        def do_GET(self):
            if user and pwhash and not _auth_ok(self.headers.get("Authorization"), user, pwhash):
                return self._denied()
            if self.path.startswith("/api/kpi"):
                body = _kpi(); ctype = "application/json"
            elif self.path.startswith("/api/blueprint"):
                body = _blueprint(); ctype = "application/json"
            elif self.path.startswith("/api/health"):
                body = _health(); ctype = "application/json"
            elif self.path.startswith("/api/runs"):
                body = _runs(); ctype = "application/json"
            elif self.path.startswith("/api/config"):
                body = _config(); ctype = "application/json"
            elif self.path.startswith("/api/phases"):
                body = _phases(); ctype = "application/json"
            elif self.path.startswith("/api/approval"):
                body = _approval(); ctype = "application/json"
            elif self.path.startswith("/api/signals"):
                body = _signals(); ctype = "application/json"
            elif self.path.startswith("/api/trades"):
                body = _trades(); ctype = "application/json"
            elif self.path.startswith("/api/pnl"):
                body = _pnl(); ctype = "application/json"
            elif self.path.startswith("/api/crew"):
                body = _crew(); ctype = "application/json"
            elif self.path.startswith("/api/phase/doc"):
                from urllib.parse import urlparse, parse_qs
                n = parse_qs(urlparse(self.path).query).get("n", [""])[0]
                body = _phase_doc(n); ctype = "application/json"
            elif self.path.startswith("/api/plan"):
                body = _plan(); ctype = "application/json"
            elif self.path.startswith("/api/search"):
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
                body = _search(q); ctype = "application/json"
            elif self.path == "/" or self.path.startswith("/index"):
                body = page; ctype = "text/html; charset=utf-8"
            else:
                self.send_response(404); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            if user and pwhash and not _auth_ok(self.headers.get("Authorization"), user, pwhash):
                return self._denied()
            if (self.path.startswith("/api/ingest") or self.path.startswith("/api/plan/run")
                    or self.path.startswith("/api/phase/launch") or self.path.startswith("/api/approval")
                    or self.path.startswith("/api/crew/run")):
                ln = int(self.headers.get("Content-Length", 0) or 0)
                try:
                    data = json.loads(self.rfile.read(ln) or b"{}") if ln else {}
                except Exception:
                    data = {}
                if self.path.startswith("/api/plan/run"):
                    res = _run_topic(data.get("id"))
                elif self.path.startswith("/api/phase/launch"):
                    res = _launch_phase(data.get("n"))
                elif self.path.startswith("/api/approval"):
                    res = _set_approval(data)
                elif self.path.startswith("/api/crew/run"):
                    res = _run_crew_cycle(data)
                else:
                    res = _ingest_url(data.get("url"), data.get("title"))
                body = json.dumps(res).encode()
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            else:
                self.send_response(404); self.end_headers()

    print(f"Lana Research → http://{host}:{port}")
    ThreadingHTTPServer((host, port), H).serve_forever()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8811)
    ap.add_argument("--host", default="0.0.0.0"); a = ap.parse_args()
    serve(a.host, a.port)

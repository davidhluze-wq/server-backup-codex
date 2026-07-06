"""Live status web page — `agentsmon dashboard`.

Pure standard-library HTTP server (no Flask/FastAPI). Serves one self-contained page that polls
``/api/state`` and renders the same layout as a clean status page: a **Persistent agents** table
and one availability card per **service** (status dot, Uptime / Availability-SLA / Latency
metrics, and a day-by-day availability timeline). A background thread probes services on an
interval and appends to the uptime DB, so just leaving the dashboard running builds history.
Binds 127.0.0.1 by default; optional HTTP Basic auth (config.dashboard.auth). UI text is English.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, db, detect, keepalive, probe


def password_hash(password: str) -> str:
    """Hash a dashboard password for storage (we never keep the plaintext in config)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _auth_ok(header: str | None, user: str, pwhash: str) -> bool:
    if not header or not header.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(header[6:]).decode("utf-8")
    except Exception:
        return False
    u, _, pw = raw.partition(":")
    return hmac.compare_digest(u, user) and hmac.compare_digest(password_hash(pw), pwhash)


PAGE = r"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agents Monitoring</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🤖</text></svg>">
<script src="https://cdn.tailwindcss.com"></script>
<style>.bar{transition:opacity .15s ease}.bar:hover{opacity:.65}.copied-flash{color:#059669!important;transition:color .1s}#toast{transition:opacity .2s ease}</style>
</head><body class="bg-slate-50 text-slate-800 antialiased">
<div id="toast" class="fixed left-1/2 bottom-5 -translate-x-1/2 bg-slate-800 text-white text-sm px-2 py-1.5 rounded-md shadow-lg opacity-0 pointer-events-none" style="z-index:50">&nbsp;</div>
<div class="mx-auto px-5 py-6" style="max-width:850px">

  <nav class="flex gap-1 mb-5 border-b border-slate-200 pb-2">
    <button id="tabbtn-overview" data-tab="overview" class="px-3 py-1.5 rounded-md text-sm font-medium bg-slate-800 text-white">Overview</button>
    <button id="tabbtn-crews" data-tab="crews" class="px-3 py-1.5 rounded-md text-sm font-medium text-slate-500 hover:bg-slate-100">Crews</button>
    <button id="tabbtn-kanban" data-tab="kanban" class="px-3 py-1.5 rounded-md text-sm font-medium text-slate-500 hover:bg-slate-100">Kanban &amp; Activity</button>
    <span class="ml-auto flex items-center gap-1">
      <a href="/lana" class="px-3 py-1.5 rounded-md text-sm font-medium text-emerald-600 hover:bg-emerald-50">🧠 Lana ↗</a>
      <a href="/hermes" class="px-3 py-1.5 rounded-md text-sm font-medium text-sky-600 hover:bg-sky-50">🌐 Hermes ↗</a>
      <a href="#" onclick="window.open('http://'+location.hostname+':8808','_blank');return false;" class="px-3 py-1.5 rounded-md text-sm font-medium text-violet-600 hover:bg-violet-50">📚 HAW ↗</a>
    </span>
  </nav>

  <div id="tab-overview">
  <section class="mb-6" data-svc="agents">
    <div class="svc-head flex items-center gap-2.5 mb-3 rounded-lg border px-3 py-2 bg-white border-slate-200">
      <span class="svc-dot h-3 w-3 rounded-full bg-slate-300 shrink-0"></span>
      <h2 class="text-base font-semibold">Persistent Agents</h2>
      <span class="agents-count ml-auto text-sm font-medium text-slate-400">loading…</span>
    </div>
    <div class="rounded-lg border border-slate-200 bg-white overflow-x-auto">
      <table class="w-full text-sm"><thead>
        <tr class="text-[11px] uppercase tracking-wide text-slate-400 border-b border-slate-100">
          <th class="text-left font-medium px-2 py-2">Agent</th>
          <th class="text-left font-medium px-2 py-2">Model</th>
          <th class="text-left font-medium px-2 py-2">Session ID / Port</th>
          <th class="text-left font-medium px-2 py-2">Started</th>
          <th class="text-left font-medium px-2 py-2">Status</th>
          <th class="text-right font-medium px-2 py-2"></th>
        </tr></thead>
        <tbody id="agents-rows"><tr><td colspan="6" class="px-3 py-3 text-slate-400">loading…</td></tr></tbody>
      </table>
    </div>
    <p class="text-[11px] text-slate-400 mt-2">tmux sessions running an agent, linked by their <code>--resume</code> session id</p>
  </section>

  <div id="services"></div>
  </div><!-- /tab-overview -->

  <div id="tab-crews" class="hidden">
    <div class="flex items-center gap-2.5 mb-3 flex-wrap">
      <h2 class="text-base font-semibold">Crews</h2>
      <span class="text-[11px] text-slate-400">💰 levný = gpt-5.4-mini / Sonnet · 🧠 drahý = gpt-5.5 / Opus — rozklikni pro role a .md</span>
    </div>
    <div id="crews-box"><p class="text-slate-400 text-sm">loading…</p></div>
  </div>

  <div id="tab-kanban" class="hidden">
    <section class="mb-6">
      <div class="flex items-center gap-2.5 mb-3">
        <h2 class="text-base font-semibold">Kanban — otevřené úkoly</h2>
        <span class="kanban-tasks-count ml-auto text-sm font-medium text-slate-400"></span>
      </div>
      <div class="rounded-lg border border-slate-200 bg-white overflow-x-auto">
        <table class="w-full text-sm"><thead><tr class="text-[11px] uppercase tracking-wide text-slate-400 border-b border-slate-100">
          <th class="text-left font-medium px-2 py-2">Úkol</th><th class="text-left font-medium px-2 py-2">Status</th><th class="text-left font-medium px-2 py-2">Assignee</th></tr></thead>
          <tbody id="kanban-tasks"><tr><td colspan="3" class="px-3 py-3 text-slate-400">loading…</td></tr></tbody></table>
      </div>
      <p class="text-[11px] text-slate-400 mt-2">otevřené tasky z Hermes Kanbanu (živě)</p>
    </section>
    <section class="mb-6">
      <h2 class="text-base font-semibold mb-3">Opakující se úlohy (cron)</h2>
      <div class="rounded-lg border border-slate-200 bg-white overflow-x-auto">
        <table class="w-full text-sm"><thead><tr class="text-[11px] uppercase tracking-wide text-slate-400 border-b border-slate-100">
          <th class="text-left font-medium px-2 py-2">Název</th><th class="text-left font-medium px-2 py-2">Schedule</th><th class="text-left font-medium px-2 py-2">Poslední běh</th></tr></thead>
          <tbody id="kanban-cron"><tr><td colspan="3" class="px-3 py-3 text-slate-400">loading…</td></tr></tbody></table>
      </div>
      <p class="text-[11px] text-slate-400 mt-2">Hermes cron úlohy · 🟢 zero-LLM = neplatí tokeny</p>
    </section>
  </div>

  <p class="text-center text-[11px] text-slate-300" id="footer">auto-refresh</p>
</div>

<template id="svc-tpl">
  <section class="mb-6">
    <div class="svc-head flex items-center gap-2.5 mb-3 rounded-lg border px-3 py-2 bg-white border-slate-200">
      <span class="svc-dot h-3 w-3 rounded-full bg-slate-300 shrink-0"></span>
      <h2 class="svc-name text-base font-semibold"></h2>
      <span class="svc-state ml-auto text-sm font-medium text-slate-400">loading…</span>
    </div>
    <div class="grid grid-cols-3 gap-3 mb-3">
      <div class="rounded-lg border border-slate-200 bg-white p-3">
        <p class="text-[11px] uppercase tracking-wide text-slate-400">Uptime</p>
        <p class="m-uptime text-lg font-semibold mt-0.5">–</p>
        <p class="text-[11px] text-slate-400">current streak</p>
      </div>
      <div class="rounded-lg border border-slate-200 bg-white p-3">
        <p class="text-[11px] uppercase tracking-wide text-slate-400">Availability</p>
        <p class="m-sla text-lg font-semibold mt-0.5">–</p>
        <p class="m-sla-sub text-[11px] text-slate-400">SLA</p>
      </div>
      <div class="rounded-lg border border-slate-200 bg-white p-3">
        <p class="m-x-label text-[11px] uppercase tracking-wide text-slate-400">Latency</p>
        <p class="m-x text-lg font-semibold mt-0.5">–</p>
        <p class="m-x-sub text-[11px] text-slate-400">health check</p>
      </div>
    </div>
    <div class="rounded-lg border border-slate-200 bg-white p-4">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-xs font-semibold text-slate-500">Availability history</h3>
        <span class="svc-tl-window text-[11px] text-slate-400"></span>
      </div>
      <div class="svc-timeline flex items-end gap-[2px] h-8"></div>
      <div class="flex items-center justify-between mt-2 text-[11px] text-slate-400">
        <span class="svc-tl-start"></span>
        <div class="flex items-center gap-3">
          <span class="flex items-center gap-1"><span class="h-2 w-2 rounded-sm bg-emerald-500"></span>Operational</span>
          <span class="flex items-center gap-1"><span class="h-2 w-2 rounded-sm bg-rose-500"></span>Outage</span>
          <span class="flex items-center gap-1"><span class="h-2 w-2 rounded-sm bg-slate-200"></span>No data</span>
        </div>
        <span>now</span>
      </div>
    </div>
  </section>
</template>

<script>
const STATE = {
  operational: ["bg-emerald-500", "Operational", "text-emerald-600", "bg-emerald-50 border-emerald-200"],
  outage:      ["bg-rose-500", "Outage", "text-rose-600", "bg-rose-50 border-rose-200"],
  nodata:      ["bg-slate-300", "No data / not running", "text-slate-400", "bg-white border-slate-200"],
};
const VENDOR = { "anthropic":"bg-orange-100 text-orange-700", "openai":"bg-emerald-100 text-emerald-700",
  "google":"bg-violet-100 text-violet-700", "gold":"bg-amber-100 text-amber-700",
  "red":"bg-rose-100 text-rose-700", "other":"bg-slate-100 text-slate-600" };
// Optional background highlight behind the agent NAME (like the model tags), text stays normal.
const NAME_BG = { "red":"bg-rose-100", "gold":"bg-amber-100", "green":"bg-emerald-100", "blue":"bg-sky-100" };
function fmtDuration(s){if(s==null)return "–";const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);
  return d?`${d}d ${h}h`:h?`${h}h ${m}m`:`${m}m`;}
function fmtTime(u){return u?new Date(u*1000).toLocaleString():"";}
function fmtLat(ms){return ms==null?"–":(ms<1?"<1 ms":ms+" ms");}
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
const q=(r,s)=>r.querySelector(s);

function renderTimeline(root, buckets, windowDays){
  const tl=q(root,".svc-timeline"); tl.innerHTML=""; const GREEN=99;
  buckets.forEach(b=>{
    const el=document.createElement("div"); let cls,status;
    if(b.uptime_pct==null){cls="bg-slate-200";status="no data";}
    else if(b.uptime_pct>=GREEN){cls="bg-emerald-500";status=`${b.uptime_pct}% uptime`;}
    else{cls="bg-rose-500";status=`outage (${b.uptime_pct}% uptime)`;}
    el.className="bar flex-1 rounded-sm h-full "+cls;
    el.title=`${new Date(b.start*1000).toLocaleDateString()} · ${status}`;
    tl.appendChild(el);
  });
  q(root,".svc-tl-window").textContent="last "+windowDays+" days";
  if(buckets.length) q(root,".svc-tl-start").textContent=new Date(buckets[0].start*1000).toLocaleDateString();
}
function renderService(root, s){
  const st=STATE[s.state]||STATE.nodata;
  q(root,".svc-head").className="svc-head flex items-center gap-2.5 mb-3 rounded-lg border px-3 py-2 "+st[3];
  q(root,".svc-dot").className="svc-dot h-3 w-3 rounded-full shrink-0 "+st[0];
  const se=q(root,".svc-state"); se.textContent=st[1]; se.className="svc-state ml-auto text-sm font-medium "+st[2];
  q(root,".m-uptime").textContent=fmtDuration(s.uptime_seconds);
  q(root,".m-sla").textContent=s.sla!=null?s.sla.toFixed(2)+" %":"–";
  q(root,".m-sla-sub").textContent="over "+s.sla_window_days+" days ("+(s.sla_samples||0)+" samples)";
  if(s.metric==="agents"){
    q(root,".m-x-label").textContent="Agents";
    q(root,".m-x").textContent=(s.metric_value!=null?s.metric_value:"–")+(s.metric_value!=null?" running":"");
    q(root,".m-x-sub").textContent="live in tmux";
  }else if(s.metric==="system_latency"){
    q(root,".m-x-label").textContent="Avg latency";
    q(root,".m-x").textContent=fmtLat(s.system_latency_ms);
    q(root,".m-x-sub").textContent=(s.system_latency_n||0)+" source"+(s.system_latency_n===1?"":"s");
  }else if(s.metric==="avg_latency"){
    q(root,".m-x-label").textContent="Avg latency";
    q(root,".m-x").textContent=fmtLat(s.avg_latency_ms);
    q(root,".m-x-sub").textContent="over "+s.sla_window_days+" days";
  }else{
    q(root,".m-x-label").textContent="Latency";
    q(root,".m-x").textContent=fmtLat(s.latency_ms);
    q(root,".m-x-sub").textContent=s.metric_sub||"health check";
  }
  renderTimeline(root, s.timeline, s.timeline_days);
}
function renderAgents(root, agents){
  const tb=document.getElementById("agents-rows");
  const on=agents.some(a=>a.alive); const running=agents.filter(a=>a.alive).length;
  q(root,".svc-head").className="svc-head flex items-center gap-2.5 mb-3 rounded-lg border px-3 py-2 "+(on?"bg-emerald-50 border-emerald-200":"bg-white border-slate-200");
  q(root,".svc-dot").className="svc-dot h-3 w-3 rounded-full shrink-0 "+(on?"bg-emerald-500":"bg-slate-300");
  const cnt=q(root,".agents-count");
  cnt.textContent=running?`${running} agent${running===1?"":"s"} running`:"no agents running";
  cnt.className="agents-count ml-auto text-sm font-medium "+(running?"text-emerald-600":"text-slate-400");
  if(!agents.length){tb.innerHTML=`<tr><td colspan="6" class="px-3 py-3 text-slate-400">No tmux sessions found.</td></tr>`;return;}
  tb.innerHTML="";
  agents.forEach(a=>{
    const tcls=VENDOR[a.vendor]||"bg-slate-100 text-slate-600";
    const copy=a.resume_cmd||a.session_id||"";
    const tip=copy?`${copy} (click to copy)`:"no resume";
    let sid;
    if(a.session_id){
      sid=`<span class="sid font-mono text-xs text-slate-600 whitespace-nowrap cursor-pointer hover:text-sky-600" title="${esc(tip)}" data-copy="${esc(copy)}">${esc(a.session_id)}</span>`;
    }else if(a.kind==="daemon" && a.port){
      // Daemons (gateways) have no session id — show the port they actually listen on instead.
      sid=`<span class="font-mono text-xs text-slate-500 whitespace-nowrap" title="gateway port">:${a.port}</span>`;
    }else{
      sid=`<span class="text-xs text-slate-300 cursor-help" title="${esc(tip)}">— none</span>`;
    }
    const ok=a.alive; const dot=ok?"bg-emerald-500":"bg-slate-300";
    // A daemon with a health endpoint shows its latency in place of Running/Idle.
    const statusTxt=(a.latency_ms!=null&&ok)?fmtLat(a.latency_ms):(ok?"Running":"Idle");
    const stCls=ok?"text-slate-600":"text-slate-400";
    const tr=document.createElement("tr"); tr.className="border-b border-slate-100 last:border-0";
    const nameBg=NAME_BG[a.name_color];
    const nameInner=nameBg?`<span class="inline-block rounded px-1.5 py-0.5 ${nameBg}">${esc(a.name)}</span>`:esc(a.name);
    // Only tmux agents can be attached to; daemons (kind "daemon", e.g. OpenClaw/Hermes) aren't in
    // tmux. For a tmux agent, clicking its name copies the attach command (toast feedback so the
    // column width never jumps).
    const attachCmd=`tmux attach -t "${a.name}"`;
    const nameCell=(a.kind!=="daemon")
      ? `<span class="agent-name cursor-pointer hover:text-sky-600" data-copy="${esc(attachCmd)}" title="${esc(attachCmd)} (click to copy)">${nameInner}</span>`
      : nameInner;
    // Telegram deep-link icon for agents bridged to a bot (opens t.me/<bot> in a new tab).
    const tg=a.telegram_url?` <a href="${esc(a.telegram_url)}" target="_blank" rel="noopener" title="Open @${esc(a.telegram_bot)} in Telegram" class="inline-flex align-middle ml-1 hover:opacity-70"><svg viewBox="0 0 24 24" class="h-4 w-4" fill="#229ED9"><path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.27 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z"/></svg></a>`:"";
    tr.innerHTML=
      `<td class="px-2 py-1.5 font-medium text-slate-700 whitespace-nowrap">${nameCell}${tg}</td>`+
      `<td class="px-2 py-1.5 whitespace-nowrap"><span class="inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${tcls}">${esc(a.label)}</span></td>`+
      `<td class="px-2 py-1.5">${sid}</td>`+
      `<td class="px-2 py-1.5 text-slate-500 text-xs whitespace-nowrap">${a.age!=null?"ago "+fmtDuration(a.age):"–"}</td>`+
      `<td class="px-2 py-1.5"><span class="inline-flex items-center gap-1.5 whitespace-nowrap ${stCls}"><span class="h-2 w-2 rounded-full ${dot} shrink-0"></span>${statusTxt}</span></td>`+
      // Per-row actions: ↻ restart, ✕ stop. Small icons at the very end of the row.
      `<td class="px-2 py-1.5 text-right whitespace-nowrap">`+
        `<button class="agent-act inline-flex align-middle p-1 rounded text-slate-400 hover:text-sky-600 hover:bg-slate-100" data-act="restart" data-name="${esc(a.name)}" title="Restart ${esc(a.name)}">`+
          `<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6"/></svg></button>`+
        `<button class="agent-act inline-flex align-middle p-1 ml-0.5 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50" data-act="stop" data-name="${esc(a.name)}" title="Stop ${esc(a.name)}">`+
          `<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>`+
      `</td>`;
    tb.appendChild(tr);
  });
}
async function refresh(){
  try{
    const d=await (await fetch("/api/state",{credentials:"same-origin"})).json();
    renderAgents(document.querySelector('section[data-svc="agents"]'), d.agents);
    const box=document.getElementById("services"); const tpl=document.getElementById("svc-tpl");
    if(box.childElementCount!==d.services.length){
      box.innerHTML=""; d.services.forEach(()=>box.appendChild(tpl.content.cloneNode(true)));
    }
    const sections=box.querySelectorAll("section");
    d.services.forEach((s,i)=>{ const root=sections[i]; q(root,".svc-name").textContent=s.name; renderService(root,s); });
    document.getElementById("footer").textContent="updated "+new Date().toLocaleTimeString()+" · auto-refresh";
  }catch(e){document.getElementById("footer").textContent="connection lost…";}
}
function copyText(text){
  if(navigator.clipboard && window.isSecureContext){ return navigator.clipboard.writeText(text); }
  // Fallback for plain http (e.g. over a VPN IP): clipboard API needs a secure context.
  const ta=document.createElement("textarea"); ta.value=text; ta.style.position="fixed"; ta.style.opacity="0";
  document.body.appendChild(ta); ta.focus(); ta.select();
  try{ document.execCommand("copy"); }catch(e){} document.body.removeChild(ta);
  return Promise.resolve();
}
let _toastTimer;
function showToast(msg){
  const t=document.getElementById("toast"); if(!t) return;
  t.textContent=msg; t.style.opacity="1";
  clearTimeout(_toastTimer); _toastTimer=setTimeout(()=>{ t.style.opacity="0"; }, 1300);
}
document.addEventListener("click", e=>{
  const el=e.target.closest("[data-copy]"); if(!el) return;
  copyText(el.dataset.copy).then(()=>{
    // Flash the element green + toast — no textContent swap, so column width never jumps.
    el.classList.add("copied-flash");
    setTimeout(()=>el.classList.remove("copied-flash"), 700);
    showToast("✓ Copied to clipboard");
  });
});
// Restart / Stop buttons → POST /api/agent/action, then refresh. Stop asks for confirmation.
document.addEventListener("click", async e=>{
  const btn=e.target.closest(".agent-act"); if(!btn) return;
  const name=btn.dataset.name, act=btn.dataset.act;
  if(act==="stop" && !confirm(`Stop agent "${name}"? It won't be auto-restarted until you press ↻.`)) return;
  btn.disabled=true; btn.classList.add("opacity-40");
  showToast((act==="restart"?"↻ Restarting ":"✕ Stopping ")+name+"…");
  try{
    const r=await fetch("/api/agent/action",{method:"POST",credentials:"same-origin",
      headers:{"Content-Type":"application/json"},body:JSON.stringify({name,action:act})});
    const j=await r.json().catch(()=>({}));
    showToast((j&&j.ok?"✓ ":"⚠ ")+((j&&j.message)||(r.ok?"done":"failed")));
  }catch(err){ showToast("⚠ "+err); }
  setTimeout(refresh, act==="restart"?2500:600);
});
// ---- Tabs ----
let ACTIVE="overview";
function tabBtnCls(on){return "px-3 py-1.5 rounded-md text-sm font-medium "+(on?"bg-slate-800 text-white":"text-slate-500 hover:bg-slate-100");}
function showTab(t){
  ACTIVE=t;
  ["overview","crews","kanban"].forEach(x=>{
    const s=document.getElementById("tab-"+x); if(s) s.classList.toggle("hidden", x!==t);
    const b=document.getElementById("tabbtn-"+x); if(b) b.className=tabBtnCls(x===t);
  });
  if(t==="crews") loadCrews();
  if(t==="kanban") loadKanban();
}
document.addEventListener("click",e=>{const b=e.target.closest("[data-tab]"); if(b) showTab(b.dataset.tab);});

// ---- Crews (tab 2) ----
function tierCls(t){return t==="levny"?"bg-emerald-100 text-emerald-700":(t==="drahy"?"bg-orange-100 text-orange-700":"bg-slate-100 text-slate-600");}
function tierIcon(t){return t==="levny"?"💰":(t==="drahy"?"🧠":"🟢");}
function docLink(p,label){return p?`<a href="/api/doc?path=${encodeURIComponent(p)}" target="_blank" rel="noopener" class="text-sky-600 hover:underline">${label}</a>`:"";}
async function loadCrews(){
  const box=document.getElementById("crews-box");
  try{
    const d=await (await fetch("/api/crews",{credentials:"same-origin"})).json();
    if(!d.crews||!d.crews.length){box.innerHTML='<p class="text-slate-400 text-sm">žádné crews</p>';return;}
    box.innerHTML="";
    d.crews.forEach(c=>{
      const rows=(c.roles||[]).map(r=>`<tr class="border-b border-slate-100 last:border-0">
        <td class="px-2 py-1 font-medium text-slate-700 whitespace-nowrap">${esc(r.role)}</td>
        <td class="px-2 py-1 whitespace-nowrap"><span class="inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${tierCls(r.tier)}">${tierIcon(r.tier)} ${esc(r.model)}</span></td>
        <td class="px-2 py-1 text-right whitespace-nowrap">${docLink(r.doc,".md ↗")}</td></tr>`).join("");
      const models=[...new Set((c.roles||[]).map(r=>r.model))].join(", ");
      const el=document.createElement("details");
      el.className="rounded-lg border border-slate-200 bg-white mb-3";
      el.innerHTML=`<summary class="cursor-pointer px-3 py-2 flex items-center gap-2 select-none">
          <span class="font-semibold">${esc(c.name)}</span>
          <span class="text-[11px] rounded px-1.5 py-0.5 bg-slate-100 text-slate-500">${esc(c.host)}</span>
          <span class="ml-auto text-[11px] text-slate-400">${(c.roles||[]).length} rolí</span>
        </summary>
        <div class="px-3 pb-3">
          <p class="text-sm text-slate-600 mb-2">${esc(c.description||"")}</p>
          <p class="text-[11px] text-slate-400 mb-2">modely: ${esc(models)}</p>
          <div class="overflow-x-auto"><table class="w-full text-sm"><thead><tr class="text-[11px] uppercase tracking-wide text-slate-400 border-b border-slate-100">
            <th class="text-left font-medium px-2 py-1">Role</th><th class="text-left font-medium px-2 py-1">Model (tier)</th><th></th></tr></thead>
            <tbody>${rows}</tbody></table></div>
          <p class="text-[11px] text-slate-400 mt-2">módy: <code>${esc((c.modes||[]).join("  ·  "))}</code> · ${docLink(c.doc,"README ↗")}</p>
        </div>`;
      box.appendChild(el);
    });
  }catch(e){box.innerHTML='<p class="text-slate-400 text-sm">nelze načíst crews</p>';}
}

// ---- Kanban & Activity (tab 3) ----
async function loadKanban(){
  try{
    const d=await (await fetch("/api/kanban",{credentials:"same-origin"})).json();
    const tt=document.getElementById("kanban-tasks");
    tt.innerHTML=(d.tasks&&d.tasks.length)?d.tasks.map(t=>`<tr class="border-b border-slate-100 last:border-0">
        <td class="px-2 py-1.5 text-slate-700">${esc(t.title)}</td>
        <td class="px-2 py-1.5 text-xs text-slate-500">${esc(t.status||"")}</td>
        <td class="px-2 py-1.5 text-xs text-slate-500">${esc(t.assignee||"")}</td></tr>`).join(""):
      `<tr><td colspan="3" class="px-3 py-3 text-slate-400 text-sm">Žádné otevřené kanban úkoly.</td></tr>`;
    const cnt=document.querySelector(".kanban-tasks-count"); if(cnt) cnt.textContent=(d.tasks?d.tasks.length:0)+" otevřených";
    const ct=document.getElementById("kanban-cron");
    ct.innerHTML=(d.cron&&d.cron.length)?d.cron.map(c=>`<tr class="border-b border-slate-100 last:border-0 ${c.enabled?"":"opacity-50"}">
        <td class="px-2 py-1.5 text-slate-700">${c.zero_llm?"🟢 ":""}${esc(c.name)}</td>
        <td class="px-2 py-1.5 font-mono text-xs text-slate-500 whitespace-nowrap">${esc(c.schedule)}</td>
        <td class="px-2 py-1.5 text-xs ${c.last_ok?"text-emerald-600":"text-slate-500"}">${esc(c.last||"")}</td></tr>`).join(""):
      `<tr><td colspan="3" class="px-3 py-3 text-slate-400 text-sm">Žádné cron úlohy.</td></tr>`;
  }catch(e){
    document.getElementById("kanban-cron").innerHTML='<tr><td colspan="3" class="px-3 py-3 text-slate-400 text-sm">nelze načíst</td></tr>';
  }
}

refresh();
setInterval(()=>{ refresh(); if(ACTIVE==="kanban") loadKanban(); }, POLL*1000);
</script></body></html>"""


def _service_state(cfg: dict, running_agents: int = 0) -> list[dict]:
    win_days = int(cfg.get("probe", {}).get("sla_window_days", 90))
    tdays = int(cfg.get("probe", {}).get("timeline_days", 90))
    min_outage = int(cfg.get("probe", {}).get("min_outage_samples", 3))
    out = []
    for s in cfg.get("services", []):
        name = s.get("name")
        if not name:
            continue
        cur = db.last(name)
        sla_pct, samples = db.sla(name, win_days * 86400)
        lat = cur["latency"] if (cur and cur["latency"] is not None) else None
        metric = s.get("metric", "latency")   # "latency" | "agents" (show running-agent count)
        out.append({
            "name": name,
            "up": bool(cur and cur["up"]),
            "state": "operational" if (cur and cur["up"]) else ("outage" if cur else "nodata"),
            "detail": cur["detail"] if cur else "no data yet",
            "last_ts": cur["ts"] if cur else None,
            "latency_ms": round(lat * 1000) if lat is not None else None,
            "avg_latency_ms": (lambda a: round(a * 1000) if a is not None else None)(db.avg_latency(name, win_days * 86400)),
            "health_url": s.get("health_url"),
            "metric": metric, "metric_value": running_agents if metric == "agents" else None,
            "metric_sub": s.get("latency_label", "health check"),
            "uptime_seconds": db.uptime_seconds(name, min_outage),
            "sla": sla_pct, "sla_window_days": win_days, "sla_samples": samples,
            "timeline": db.timeline(name, tdays * 86400, tdays), "timeline_days": tdays,
        })
    return out


def _tg_link(value: str) -> tuple[str, str]:
    """Normalise a Telegram reference (``@bot``, ``bot``, or a full ``https://t.me/bot`` URL) into
    (url, username)."""
    v = (value or "").strip()
    if v.startswith("http"):
        return v, v.rstrip("/").split("/")[-1].lstrip("@")
    uname = v.lstrip("@")
    return f"https://t.me/{uname}", uname


def _agents_state(cfg: dict) -> list[dict]:
    """Pinned daemons (OpenClaw/Hermes…) first, then running tmux agents, with config display
    overrides (tag → label, vendor → tag colour) applied."""
    overrides = {a["name"]: a for a in cfg.get("agents", []) if a.get("name")}
    tmux = [a for a in detect.discover_agents(config.agent_matches(cfg)) if a["alive"]]
    for a in tmux:
        ov = overrides.get(a["name"], {})
        if ov.get("tag"):
            a["label"] = ov["tag"]
        if ov.get("vendor"):
            a["vendor"] = ov["vendor"]
        if ov.get("restart"):
            a["resume_cmd"] = ov["restart"]
    agents = detect.pinned_agents(cfg.get("pinned_daemons", [])) + tmux
    # Telegram deep-link icon. Two sources, explicit wins:
    #  1) an explicit `telegram` field on an agent/daemon config entry (for daemons with their OWN
    #     native bot, e.g. OpenClaw/Hermes) — value is a @username or a full t.me URL;
    #  2) auto: a tmux session bridged via Agent2Telegram (reads only the non-secret bot username).
    explicit = {d["name"]: d["telegram"] for d in
                (cfg.get("pinned_daemons", []) + cfg.get("agents", []))
                if d.get("name") and d.get("telegram")}
    links = detect.telegram_links()
    for a in agents:
        bot = explicit.get(a.get("name")) or links.get(a.get("name"))
        if bot:
            url, uname = _tg_link(bot)
            a["telegram_bot"] = uname
            a["telegram_url"] = url
    return agents


def _set_enabled(name: str, enabled: bool) -> None:
    """Persist enabled=true/false on the named agent/daemon in the RAW config file (so keepalive
    stops reviving a stopped agent). Targeted edit — preserves the rest of the user's file."""
    path = config.DEFAULT_PATH
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return
    changed = False
    for key in ("agents", "daemons"):
        for entry in raw.get(key, []):
            if entry.get("name") == name:
                entry["enabled"] = enabled
                changed = True
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
        os.chmod(path, 0o600)


def _agent_action(name: str, action: str) -> tuple[bool, str]:
    """Dashboard row actions. action: 'restart' | 'stop'. Returns (ok, message)."""
    cfg = config.load()
    tmux_bin = shutil.which(cfg.get("tmux_bin", "tmux")) or "tmux"
    agent = next((a for a in cfg.get("agents", []) if a.get("name") == name), None)
    daemon = next((d for d in cfg.get("daemons", []) if d.get("name") == name), None)
    if not agent and not daemon:
        return False, f"unknown agent '{name}'"
    if action == "restart":
        # Re-enable (in case it was stopped) and relaunch fresh so it picks up new config (e.g. MCP).
        _set_enabled(name, True)
        if agent:
            keepalive._start(agent, tmux_bin, recreate=True)   # kill session + recreate + resume cmd
            return True, f"restarting {name}"
        cmd = daemon.get("restart")
        if not cmd:
            return False, f"{name} has no restart command"
        subprocess.run(cmd, shell=True, capture_output=True, timeout=30)
        return True, f"restarting {name}"
    if action == "stop":
        # Disable first so keepalive won't revive it, then kill the session / process.
        _set_enabled(name, False)
        if agent:
            subprocess.run([tmux_bin, "kill-session", "-t", name], capture_output=True, timeout=10)
            return True, f"stopped {name}"
        pat = daemon.get("pattern") or daemon.get("binary") or name
        subprocess.run(["pkill", "-f", pat], capture_output=True, timeout=10)
        return True, f"stopped {name}"
    return False, f"unknown action '{action}'"


HERMES_HOME = os.path.expanduser("~/.hermes")


def _crews() -> bytes:
    """Crew overview (tab 2) — read a curated registry describing every crew, its roles, models
    (tier) and doc paths. Passive/read-only."""
    try:
        with open(os.path.join(HERMES_HOME, "crews_registry.json"), "rb") as fh:
            return fh.read()
    except OSError:
        return json.dumps({"crews": []}).encode()


def _kanban() -> bytes:
    """Kanban tab (tab 3) — open kanban tasks (from kanban.db) + recurring cron jobs (from the cron
    store, not the CLI). Passive live view."""
    cron = []
    try:
        with open(os.path.join(HERMES_HOME, "cron", "jobs.json"), encoding="utf-8") as fh:
            jobs = json.load(fh).get("jobs", [])
        for j in jobs:
            sched = j.get("schedule") or {}
            lr = j.get("last_run_at") or ""
            cron.append({
                "name": j.get("name"),
                "schedule": (sched.get("expr") if isinstance(sched, dict) else "") or j.get("schedule_display") or "",
                "enabled": j.get("enabled", True),
                "zero_llm": bool(j.get("no_agent")),
                "last": ((j.get("last_status") or "") + (" · " + lr[:16].replace("T", " ") if lr else "")).strip(" ·"),
                "last_ok": (j.get("last_status") == "ok"),
            })
    except (OSError, ValueError):
        pass
    tasks = []
    try:
        import sqlite3
        con = sqlite3.connect("file:" + os.path.join(HERMES_HOME, "kanban.db") + "?mode=ro", uri=True, timeout=2)
        for row in con.execute("select title, status, assignee from tasks "
                               "where status is null or status != 'done' order by created_at desc limit 100"):
            tasks.append({"title": row[0], "status": row[1], "assignee": row[2]})
        con.close()
    except Exception:
        pass
    return json.dumps({"tasks": tasks, "cron": cron}).encode()


def _doc(rel: str):
    """Serve a crew instruction file (README/prompt/script) read-only for the 'open .md' links.
    Path-restricted to ~/.hermes, text types only, escaped into a simple page."""
    try:
        base = os.path.realpath(HERMES_HOME)
        target = os.path.realpath(os.path.join(HERMES_HOME, rel))
        if not (target == base or target.startswith(base + os.sep)):
            return None
        if os.path.isdir(target):
            return None
        if os.path.splitext(target)[1].lower() not in (".md", ".py", ".sh", ".yaml", ".yml", ".json", ".txt"):
            return None
        with open(target, encoding="utf-8", errors="replace") as fh:
            text = fh.read(200000)
    except OSError:
        return None
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_rel = rel.replace("<", "").replace(">", "")
    html = ("<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>" + safe_rel + "</title><script src='https://cdn.tailwindcss.com'></script></head>"
            "<body class='bg-slate-50 text-slate-800 p-5'><div class='mx-auto' style='max-width:850px'>"
            "<p class='text-xs text-slate-400 mb-2'>" + safe_rel + "</p>"
            "<pre class='whitespace-pre-wrap text-sm bg-white border border-slate-200 rounded-lg p-4'>" + esc + "</pre>"
            "</div></body></html>")
    return html.encode(), "text/html; charset=utf-8"


# Lokalni dashboardy dostupne pres agentsmon (jeho port je otevreny na provider firewallu).
PROXY_BACKENDS = {
    "lana": "http://127.0.0.1:8811",     # Lana Research (vlastni auth = shodny hash)
    "hermes": "http://127.0.0.1:9119",   # Hermes Agent Dashboard (bez auth; SPA + WebSocket)
}


def _proxy(prefix, path, auth):
    """Reverse-proxy k lokalnimu dashboardu. Preposila Authorization a prefixuje absolutni cesty,
    aby app bezela pod /<prefix>/. Pozn.: WebSocket (Hermes live) pres stdlib server neprojde —
    obsah/architektura se nacte, ale live updaty ne (na to je treba firewall+expose)."""
    import urllib.request, urllib.error
    backend = PROXY_BACKENDS.get(prefix)
    if not backend:
        return None
    sub = path[len("/" + prefix):] or "/"
    if not sub.startswith("/"):
        sub = "/" + sub
    req = urllib.request.Request(backend + sub)
    if auth:
        req.add_header("Authorization", auth)
    status = 200
    try:
        r = urllib.request.urlopen(req, timeout=8)
        data, ctype, status = r.read(), r.headers.get("Content-Type", "application/octet-stream"), r.status
    except urllib.error.HTTPError as e:  # zachovej 401/404/... misto 502
        data = e.read() if hasattr(e, "read") else b""
        ctype = (e.headers.get("Content-Type", "text/plain") if e.headers else "text/plain")
        status = e.code
    except Exception:
        return None
    p = ("/" + prefix).encode()
    if "text/html" in ctype:
        data = (data.replace(b'href="/', b'href="' + p + b'/')
                    .replace(b'src="/', b'src="' + p + b'/')
                    .replace(b'fetch("/', b'fetch("' + p + b'/'))
        # Zpetny odkaz na domaci stranku agentsmon. Injektujeme AZ po prepisu cest,
        # aby href="/" ukazovalo na korenu agentsmon (ne na /<prefix>/).
        back = (b'<a href="/" title="Zpet na agentsmon" style="position:fixed;top:10px;right:10px;'
                b'z-index:99999;background:#059669;color:#fff;padding:6px 12px;border-radius:8px;'
                b'font:500 13px system-ui,-apple-system,sans-serif;text-decoration:none;'
                b'box-shadow:0 1px 4px rgba(0,0,0,.25)">\xe2\x86\x90 agentsmon</a>')
        if b'</body>' in data:
            data = data.replace(b'</body>', back + b'</body>', 1)
        else:
            data = data + back
    elif "javascript" in ctype:
        data = (data.replace(b'"/api/', b'"' + p + b'/api/')
                    .replace(b'"/assets/', b'"' + p + b'/assets/')
                    .replace(b"'/api/", b"'" + p + b"/api/"))
    return data, ctype, status


def _state() -> bytes:
    cfg = config.load()
    agents = _agents_state(cfg)
    running = sum(1 for a in agents if a.get("alive"))
    services = _service_state(cfg, running)
    # System-wide current latency = average across every component with a health endpoint
    # (pinned daemons + services), deduped by URL — feeds a "system_latency" metric card.
    lat_by_url: dict[str, int] = {}
    for item in agents + services:
        url, lm = item.get("health_url"), item.get("latency_ms")
        if url and lm is not None:
            lat_by_url.setdefault(url, lm)
    sysavg = round(sum(lat_by_url.values()) / len(lat_by_url)) if lat_by_url else None
    for s in services:
        s["system_latency_ms"] = sysavg
        s["system_latency_n"] = len(lat_by_url)
    data = {"time": int(time.time()), "agents": agents, "services": services}
    return json.dumps(data).encode()


def _probe_loop(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            probe.probe_once(config.load())
        except Exception:
            pass
        stop.wait(int(config.load().get("probe", {}).get("interval_seconds", 60)))


def serve(host: str, port: int) -> None:
    # Bring an older config up to the current schema on startup (e.g. fold per-daemon availability
    # cards into the synthetic Multi-Agent System card). The dashboard restarts on every update,
    # so this self-heals existing installs without needing a special migration step.
    try:
        from . import wizard
        cfg0 = config.load()
        if wizard.migrate_config(cfg0):
            config.save(cfg0)
    except Exception:
        pass
    cfg = config.load()
    poll = cfg.get("dashboard", {}).get("poll_seconds", 15)
    page = PAGE.replace("POLL", str(poll)).encode()
    auth = cfg.get("dashboard", {}).get("auth") or {}
    auth_user, auth_hash = auth.get("user"), auth.get("pwhash")

    if cfg.get("services"):
        threading.Thread(target=_probe_loop, args=(threading.Event(),), daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _denied(self):
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Agents Monitoring"')
            self.end_headers()

        def do_GET(self):
            if auth_user and auth_hash and not _auth_ok(self.headers.get("Authorization"),
                                                        auth_user, auth_hash):
                return self._denied()
            if self.path.startswith("/api/state"):
                body = _state()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif self.path.startswith("/api/crews"):
                body = _crews()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif self.path.startswith("/api/kanban"):
                body = _kanban()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif self.path.startswith("/api/doc"):
                from urllib.parse import urlparse, parse_qs
                rel = parse_qs(urlparse(self.path).query).get("path", [""])[0]
                res = _doc(rel)
                if not res:
                    self.send_response(404)
                    self.end_headers()
                    return
                body, ctype = res
                self.send_response(200)
                self.send_header("Content-Type", ctype)
            elif self.path[1:].split("/", 1)[0].split("?")[0] in PROXY_BACKENDS:
                prefix = self.path[1:].split("/", 1)[0].split("?")[0]
                res = _proxy(prefix, self.path, self.headers.get("Authorization"))
                if not res:
                    self.send_response(502)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(("Dashboard '%s' nedostupný (backend neběží?)" % prefix).encode())
                    return
                body, ctype, status = res
                self.send_response(status)
                self.send_header("Content-Type", ctype)
            elif self.path == "/" or self.path.startswith("/index"):
                body = page
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if auth_user and auth_hash and not _auth_ok(self.headers.get("Authorization"),
                                                        auth_user, auth_hash):
                return self._denied()
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            if parsed.path != "/api/agent/action":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b""
            params = {}
            try:
                params = json.loads(raw or b"{}")
            except ValueError:
                params = {k: v[0] for k, v in parse_qs(raw.decode("utf-8", "replace")).items()}
            qs = parse_qs(parsed.query)
            name = params.get("name") or (qs.get("name", [None])[0])
            act = params.get("action") or (qs.get("action", [None])[0])
            if not name or act not in ("restart", "stop"):
                body = json.dumps({"ok": False, "error": "need name + action (restart|stop)"}).encode()
                status = 400
            else:
                try:
                    ok, msg = _agent_action(name, act)
                except Exception as exc:                      # never 500 the dashboard on a bad action
                    ok, msg = False, str(exc)
                body = json.dumps({"ok": ok, "message": msg}).encode()
                status = 200 if ok else 500
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    print(f"Agents Monitoring dashboard → http://{host}:{port}  (Ctrl-C to stop)")
    ThreadingHTTPServer((host, port), Handler).serve_forever()

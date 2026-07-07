#!/usr/bin/env python3
from __future__ import annotations

import hashlib, html, json, os, re, subprocess, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE = Path.home()/'.hermes'/'news-agent'
STATE = BASE/'ai_auto_radar_topics.json'
HISTORY = BASE/'ai_auto_radar_history.txt'
LOG = BASE/'news_monitor.log'
HERMES = os.environ.get('HERMES_BIN','hermes')
URL_RE = re.compile(r'https?://[^\s\"\'<>]+')
TAG_RE = re.compile(r'<[^>]+>')
STOP = {'the','and','for','with','from','that','this','have','has','will','new','news','about','into','after','before','jako','který','která','pro','podle','také','další','zprávy','umělá','inteligence','automotive','trh','markets'}

def log(msg:str):
    BASE.mkdir(parents=True, exist_ok=True)
    with LOG.open('a',encoding='utf-8') as f: f.write(datetime.now(timezone.utc).isoformat(timespec='seconds')+' ai_auto '+msg+'\n')

def now_cz():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('Europe/Prague'))
    except Exception:
        return datetime.now(timezone(timedelta(hours=1)))

def strip_html(s:str)->str:
    return html.unescape(TAG_RE.sub(' ',s))

def words(s:str)->set[str]:
    s=strip_html(URL_RE.sub(' ',s)).lower()
    return {t for t in re.findall(r'[a-zá-ž0-9]{4,}',s,re.I) if t not in STOP and not t.isdigit()}

def urls(s:str)->set[str]:
    out=set()
    for u in URL_RE.findall(s):
        p=urlparse(u.rstrip('.,)]"'))
        if p.netloc: out.add((p.netloc.lower()+p.path).rstrip('/'))
    return out

def load(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default

def save(path,data):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def recent_history(n=20):
    if not HISTORY.exists(): return '(zatím nic)'
    lines=[x.strip() for x in HISTORY.read_text(encoding='utf-8',errors='replace').splitlines() if x.strip()]
    return '\n'.join(lines[-n:]) or '(zatím nic)'

def global_lessons(max_chars=4000):
    p=Path.home()/'.hermes'/'LESSONS.md'
    if not p.exists(): return ''
    txt=p.read_text(encoding='utf-8',errors='replace')
    if len(txt)<=max_chars: return txt
    return txt[:max_chars//2]+f'\n\n[...TRUNCATED {len(txt)-max_chars} CHARS; FULL FILE ON DISK...]\n\n'+txt[-max_chars//2:]

def prompt():
    n=now_cz()
    return f'''Pracuj POUZE s web search nástrojem. Aktuální čas: {n:%d.%m.%Y %H:%M} Praha.

GLOBAL SELF-LEARNING / LESSONS — zohledni tyto serverové lekce a pokud narazíš na novou opakovatelnou chybu, vrať jednu stručnou lekci pro orchestrátor:
{global_lessons()}

Připrav ranní AI + automotive trend radar pro Telegram, ale POŠLI HO POUZE tehdy, když se za posledních 24 hodin stala významná NOVÁ okolnost, která téma posouvá. Nechci každý den stejné titulky ani stejné kauzy jen s jinou formulací.

Kritérium novosti:
- nové rozhodnutí/regulace/produkt/model/partnerství/finanční výsledek/incident, které mění situaci;
- u automotive nové dopady na Toyota/BMW/Škoda/VW, EU/ČR automotive, ropa, plasty, kartony, logistika, energie, sazby/měny;
- pokud jde jen o komentář, opakování, starou kauzu bez posunu, nebo stejný titulek jako níže, odpověz pouze NOTHING.

Nedávno poslané okruhy — neopakuj bez zásadního nového obratu:
{recent_history(25)}

Formát pokud existují novinky:
🤖 <b>AI signál</b>
— [2–3 věty: co je nové a proč na tom záleží]
🔗 <a href="[url]">[zdroj]</a>

🚗 <b>Automotive/trhy signál</b>
— [2–3 věty: co je nové a praktický dopad]
🔗 <a href="[url]">[zdroj]</a>

Pokud je významná jen jedna z oblastí, pošli jen tu jednu. HTML tagy pouze <b> a <a href>. Žádný markdown. MAX 1800 znaků.'''

def run_hermes()->str:
    prof=os.environ.get('HERMES_RADAR_PROFILE','worker-gpt-mini')  # rutina -> levny tier
    p=subprocess.run([HERMES,'-p',prof,'chat','-Q','-t','web','-q',prompt()],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600)
    if p.returncode!=0:
        log('hermes rc=%s stderr=%s'%(p.returncode,p.stderr[-500:]))
        return ''
    out=p.stdout.strip()
    out=re.sub(r'^```(?:html|text)?\s*','',out).strip(); out=re.sub(r'\s*```$','',out).strip()
    return out

def blocks(text:str)->list[str]:
    return [b.strip() for b in re.split(r'\n\s*\n',text) if '<b>' in b and 'http' in b]

def is_novel(block:str, cache:list[dict])->bool:
    w=words(block); u=urls(block)
    for old in cache:
        ow=set(old.get('words',[])); ou=set(old.get('urls',[]))
        if u and ou and u & ou: return False
        if w and ow and len(w & ow)/max(1,len(w|ow)) >= 0.24: return False
    return True

def main():
    BASE.mkdir(parents=True, exist_ok=True)
    text=run_hermes()
    if not text or text.upper().startswith('NOTHING') or 'http' not in text:
        log('nothing/invalid')
        return 0
    cache=load(STATE,[])
    cutoff=time.time()-45*24*3600
    cache=[x for x in cache if x.get('ts',0)>cutoff]
    kept=[]
    for b in blocks(text):
        if is_novel(b,cache):
            kept.append(b)
            cache.append({'ts':time.time(),'words':sorted(words(b)),'urls':sorted(urls(b)),'preview':strip_html(b)[:220]})
        else:
            log('duplicate block suppressed: '+strip_html(b)[:140])
    save(STATE,cache[-250:])
    if not kept:
        log('no novel blocks')
        return 0
    msg='🌅 <b>Ranní trend radar</b>\n\n'+'\n\n'.join(kept[:2])
    lines=[]
    if HISTORY.exists(): lines=HISTORY.read_text(encoding='utf-8',errors='replace').splitlines()
    for b in kept[:2]: lines.append(now_cz().strftime('%d.%m. %H:%M')+' — '+strip_html(b).replace('\n',' ')[:220])
    HISTORY.write_text('\n'.join(lines[-120:])+'\n',encoding='utf-8')
    print(msg[:3000])
    return 0

if __name__=='__main__':
    raise SystemExit(main())

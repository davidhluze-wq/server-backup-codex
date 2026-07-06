#!/usr/bin/env python3
from pathlib import Path
from datetime import date
import json, re
base = Path.home()/'.hermes/security-audit-lite'
today = date.today().isoformat()
report = base/f'report-{today}.md'
status = base/'status.json'

def from_status():
    if not status.exists():
        return None
    try:
        d=json.loads(status.read_text(encoding='utf-8'))
    except Exception:
        return None
    areas=d.get('areas') or []
    sev={'red':0,'yellow':1,'green':2}
    emoji={'red':'🔴','yellow':'🟡','green':'🟢'}
    lines=[]
    for a in sorted(areas, key=lambda x: sev.get(x.get('status','green'),2)):
        st=a.get('status','green')
        note=a.get('note') or a.get('name') or ''
        name=a.get('name') or ''
        desc = note if name.lower() in note.lower() else f"{name}: {note}".strip(': ')
        lines.append(f"{emoji.get(st,'🟢')} – {desc}")
    if not lines:
        return None
    if any((a.get('status') in ('red','yellow')) for a in areas):
        lines.append('')
        lines.append('❓ Mám opravit vše, co půjde? (napiš ano)')
    return '\n'.join(lines)

if report.exists():
    txt=report.read_text(encoding='utf-8', errors='replace')
    m=re.search(r'^##\s*Shrnutí pro Telegram\s*\n(?P<body>.*?)(?=\n##\s+|\Z)', txt, flags=re.M|re.S|re.I)
    if m:
        body=m.group('body').strip()
        # Strip code fences if the agent wrapped the summary.
        body=re.sub(r'^```(?:text|markdown)?\s*', '', body).strip()
        body=re.sub(r'\s*```$', '', body).strip()
        if body:
            print(body)
            raise SystemExit(0)
msg=from_status()
if msg:
    print(msg)
else:
    print('⚠️ Ranní bezpečnostní souhrn se nepodařilo načíst. Mrknu na to.')

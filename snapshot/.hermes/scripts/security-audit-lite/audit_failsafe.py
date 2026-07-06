#!/usr/bin/env python3
from pathlib import Path
from datetime import date
import os
base = Path.home()/'.hermes/security-audit-lite'
today = date.today().isoformat()
report = base/f'report-{today}.md'
marker = base/f'failsafe-alert-{today}.sent'
if report.exists() and report.stat().st_size > 200:
    raise SystemExit(0)
if marker.exists():
    raise SystemExit(0)
marker.write_text('sent\n', encoding='utf-8')
print('⚠️ Noční bezpečnostní audit dnes neproběhl nebo nevytvořil report. Mrknu na to.')

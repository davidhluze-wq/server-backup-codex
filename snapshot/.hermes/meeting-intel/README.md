# meeting-intel — Meeting Intelligence crew

Zpracuje nahrávku porady → přepis → minutes (souhrn, rozhodnutí, akční kroky) → destilace nápadů
(obchodní příležitosti / projekty) → u nápadu deepresearch + koncept produkce (road-plan + prompt
pro stavbu v Hermes). Vše v DB (schema `meeting`) a v dashboardu **agentsmon → 📝 Meetings**.
Zálohuje na Google Drive (Startup/Meeting minutes), sdílitelné s kolegou; kód dashboardu na GitHubu.

## Role (6)
1. **transcriber** — audio → text (whisper, lokálně, zdarma)
2. **minutes-writer** — souhrn + rozhodnutí + akční kroky
3. **idea-distiller** — destilace nápadů / příležitostí / dalších projektů
4. **concept-architect** — road-plan + hotový prompt pro Hermes
5. **researcher** — deepresearch tématu nápadu (deleguje na deepresearch crew)
6. **reviewer-auditor** — finální review, audit, cleanup, předání

## Fáze
F0 kostra+DB+crew · F1 audio→minutes→nápady · F2 dashboard · F3 koncepty · F4 Google Drive záloha/sdílení
· F5 GitHub · F6 review/audit/cleanup/handover.

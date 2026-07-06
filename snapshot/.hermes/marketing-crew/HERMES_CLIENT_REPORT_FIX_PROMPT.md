# Prompt pro Hermes: oprava klientského audit reportu

Přečti si prosím instrukce od Codex Master kontrolora:

```text
/home/david_master/.hermes/marketing-crew/CODEX_REVIEW_INSTRUCTIONS.md
```

Potom zkontroluj poslední auditní run:

```text
/home/david_master/.hermes/marketing-crew/runs/20260703-075619-retrobudka-cz-audit-final/
```

Codex už vytvořil návrh klientské verze:

```text
client_report.md
client_report_visual.html
client_report.pdf
```

Nový optimalizovaný klientský výstup musí mít v názvu souboru název klienta nebo domény. Pro tento run použij prefix:

```text
retrobudka-cz
```

Vytvoř tedy minimálně:

```text
retrobudka-cz-klientsky-audit.md
retrobudka-cz-klientsky-audit.html
retrobudka-cz-klientsky-audit.pdf
```

Tvůj úkol:

1. Zkontroluj, zda klientská verze věcně odpovídá původnímu auditu.
2. Zkontroluj, že neobsahuje interní/programátorské výrazy.
3. Zkontroluj, že je použitelná pro běžného klienta a maximálně na cca 2 strany.
4. Pokud něco chybí, navrhni opravy, ale zatím nepřepisuj klientský report bez potvrzení uživatele.
5. Uprav svoje budoucí workflow tak, aby každý další audit generoval:
   - detailní interní `audit_report.md`,
   - krátký klientský `client_report.md`,
   - vizuální `client_report.html` nebo `client_report_visual.html`,
   - `quality_review.md` s kontrolou klientské čitelnosti.
   - finální klientské soubory pojmenované podle klienta/domény ve formátu `<domena-nebo-klient>-klientsky-audit.md/html/pdf`.
   - upload finálních klientských souborů na Google Drive do složek `klient/projekt-run`.
   - `drive_links.md` a `export_manifest.json` s odkazy na vytvořené výstupy.

Google Drive pravidlo:

```text
Finalni soubory vzdy nahraj do Drive struktury:
root folder -> <klient-nebo-domena> -> <konkretni-run-nebo-projekt>

Po dokonceni uzivateli posli:
- odkaz na slozku projektu,
- odkaz na PDF,
- odkaz na HTML,
- odkaz na Markdown.
```

Vrať krátkou zprávu:

```markdown
# Hermes Client Report Fix Summary

## Checked Files

## Is Client Report Ready?

## Issues Found

## Recommended Edits Before Client Approval

## Workflow Changes Needed For Future Runs

## Google Drive Links
```

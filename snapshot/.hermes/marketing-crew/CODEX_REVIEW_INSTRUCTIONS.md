# Codex review: klientsky citelny audit report

## Problem

Aktualni Hermes audit report je obsahove pouzitelny, ale pro klienta je prilis technicky a spatne citelny:

- dlouhe tabulky,
- interni/probe detaily,
- programatorske formulace,
- chyby nastroju ve zdrojovych vystupech,
- malo vizualni hierarchie,
- chybi kratky klientsky zaver na max. 2 strany.

## Cil pro dalsi vystupy

Hermes Marketing Crew ma vedle interniho `audit_report.md` generovat i klientsky report:

```text
client_report.md
client_report.html
```

Volitelne pozdeji:

```text
client_report.pdf
```

## Klientsky format

Report musi byt psany laickym jazykem pro majitele firmy. Nesmí obsahovat:

- nazvy internich souboru,
- tracebacky,
- chyby API,
- "probe/json/backend/session",
- formulace typu "v teto session nemam nastroj",
- dlouhe technicke evidence bloky.

Technicka evidence patri pouze do interniho reportu.

Preferovany HTML styl:

- zachovej vzdušný klientský layout jako ve schválené první HTML verzi,
- nahoře výrazný nadpis, krátký cíl auditu a barevný status badge,
- sekce `Semafor priorit` jako 5 přehledných boxů,
- `Hlavní zjištění` jako 2x2 karty s krátkými odstavci,
- samostatný krátký blok pro faktickou korekci nebo tržní srovnání,
- akční plán v jednoduché tabulce,
- žádné dlouhé hutné bloky, žádný interní auditní jazyk,
- pokud přidáš SEO/konkurenci/produktovou jasnost, drž je v krátkých klientských blocích, ne jako technickou přílohu.

Povinne obsahove prvky pro konkurenci a SEO:

- uvést konkrétní přímé konkurenční weby, ne pouze obecné shrnutí trhu,
- u konkurentů porovnat nabídku, CTA/poptávkovou cestu, recenze/důkazy, balíčky/ceník, lokální stránky a vizuální náhled/logo,
- SEO část nesmí být jen seznam chyb; musí obsahovat cílové doporučené nastavení,
- vždy navrhnout konkrétní title, meta description, H1, H2 osnovu, canonical, OG/social thumbnail, logo/favicon/site icon, schema a strukturu landing pages,
- pokud web ukazuje výchozí WordPress logo nebo náhled, označit to jako rychlou důvěryhodnostní opravu.

## Maximalni struktura

```markdown
# Rychly audit webu <domena>

Celkové hodnocení: 🔴/🟠/🟡/🟢

## Semafor priorit

| Oblast | Stav | Co to znamená |

## Hlavní zjištění

### 1. ...
### 2. ...
### 3. ...
### 4. ...

## Doporučený akční plán

| Termín | Priorita | Co udělat | Proč |

## Doporučená komunikace / CTA

## Závěr
```

## Vizualni pravidla

- pouzit barevny semafor,
- max. 4 hlavni zjisteni,
- max. 6-8 akcnich kroku,
- kratke odstavce,
- zadne dlouhe technicke tabulky,
- kazda sekce musi odpovidat na klientskou otazku "Co to znamena pro muj byznys?"

## Vzor

Vzor vytvoreny Codexem:

```text
/home/david_master/.hermes/marketing-crew/runs/20260703-075619-retrobudka-cz-audit-final/client_report.md
/home/david_master/.hermes/marketing-crew/runs/20260703-075619-retrobudka-cz-audit-final/client_report.html
```

## Pozadovana uprava Hermese

1. Aktualizovat `prompts/strategy-synthesizer.md`, aby jasne oddelil:
   - interni audit,
   - klientsky report.
2. Aktualizovat `prompts/quality-reviewer.md`, aby kontroloval i klientskou citelnost.
3. Upravit export, aby dokazal vytvorit HTML/PDF i z `client_report.md`.
4. Export musi nahrat finalni klientsky vystup na Google Drive do struktury:
   - korenova bezpecna slozka,
   - slozka klienta/projektu podle domeny nebo nazvu klienta,
   - slozka konkretniho auditu/runu.
5. Hermes musi po exportu vratit uzivateli odkaz na slozku projektu a odkazy na finalni soubory.
6. Dalsi run musi obsahovat client-friendly vystup bez technickeho balastu.

## Google Drive vystupy

Exportni skript musi vytvorit nebo znovu pouzit slozky podle klienta/projektu a nahrat finalni klientskou trojici:

```text
<domena-nebo-klient>-klientsky-audit.md
<domena-nebo-klient>-klientsky-audit.html
<domena-nebo-klient>-klientsky-audit.pdf
```

Po uploadu musi vzniknout:

```text
export_manifest.json
drive_links.md
```

V odpovedi uzivateli Hermes nesmi psat technicke logy. Ma napsat kratce:

```markdown
Hotovo. Finalni vystupy jsou ulozene zde:

- Slozka projektu: <Google Drive folder link>
- PDF: <Google Drive file link>
- HTML: <Google Drive file link>
- Markdown: <Google Drive file link>
```

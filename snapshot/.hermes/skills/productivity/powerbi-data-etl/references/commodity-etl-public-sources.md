# Commodity ETL Public Sources — Session Notes

This reference captures source/implementation details from the commodity Power BI dashboard work.

## Live target shape

- Public CSV endpoint: `/commodities.csv`
- Public metadata endpoint: `/commodities.json`
- Stable schema: `Datum,Hodnota,Komodita,Jednotka,Zdroj,Frekvence`
- Power BI should consume a single anonymous Web CSV query where possible.

## Sources that worked

### Alpha Vantage commodities

Used for monthly energy/metals:

- `BRENT`
- `WTI`
- `NATURAL_GAS`
- `COPPER`
- `ALUMINUM`

Keep `AV_API_KEY` in project `.env`; demo may work but has lower reliability/limits.

### ČNB

ČNB API worked for CZK/EUR daily-year endpoint; aggregate EUR to monthly end-of-month by keeping last observation per `YYYY-MM`.

### World Bank Pink Sheet

Current XLSX link is discoverable from:

```text
https://www.worldbank.org/en/research/commodity-markets
```

Search page HTML for `CMO-Historical-Data-Monthly.xlsx`. The workbook has a `Monthly Prices` sheet. In the XLSX XML it is commonly `xl/worksheets/sheet2.xml`; headers are around workbook row 5 and units around row 6.

Useful public proxy series:

- `Rubber, TSR20 **` → `Kaučuk TSR20 (World Bank)`
- `Rubber, RSS3` → `Kaučuk RSS3 (World Bank)`
- `Plywood` → `Překližka (World Bank)`
- `Logs, Malaysian` → `Kulatina Malajsie (World Bank)`
- `Sawnwood, Malaysian` → `Řezivo Malajsie (World Bank)`

Stdlib parsing works without `openpyxl`:

- download XLSX bytes,
- open as `zipfile.ZipFile(BytesIO(data))`,
- read `xl/sharedStrings.xml`,
- read `xl/worksheets/sheet2.xml`,
- map cells by row/column reference,
- convert periods like `2026M06` to `2026-06-01`.

## Sources that need keys or caveats

### FRED

Public browser CSVs (`fredgraph.csv`) can be unreliable from VPS due to Akamai/timeouts. Do not block the entire ETL on them. Prefer official API when user can provide free API key:

```text
FRED_API_KEY=...
```

Useful PPI series:

- `WPU072205011` — Unlaminated Polyethylene Film and Sheet
- `WPU07` — Rubber and Plastic Products
- `WPU0913` — Paper
- `WPU09150301` — Corrugated Shipping Containers
- `WPU091405` — Corrugated Paperboard Sheets/Rolls

### Freight / container data

- Historical WCI/FBX/C3 is commonly paid/licensed.
- Use `balticdryindex.com/data/latest.json` for BDI latest public signal.
- Freightos public page can expose current FBX labels/values in embedded payload, but treat as latest/proxy, not a historical licensed feed.
- Metadata should say this explicitly.

## Verification commands

```bash
cd ~/commodity-etl
python3 -m py_compile build_commodities.py
python3 build_commodities.py
curl -sS -D- http://127.0.0.1:8765/commodities.csv -o /tmp/commodities.csv
curl -sS http://127.0.0.1:8765/commodities.json | python3 -m json.tool
python3 - <<'PY'
import csv, collections
rows=list(csv.DictReader(open('/tmp/commodities.csv', encoding='utf-8')))
print('rows', len(rows))
print(collections.Counter(r['Komodita'] for r in rows))
PY
```

## User-facing handoff

Always update a markdown handoff file with:

- public CSV and JSON URLs,
- Power Query M block,
- date table DAX,
- useful measures,
- visual recommendations,
- source limitations and optional API keys.

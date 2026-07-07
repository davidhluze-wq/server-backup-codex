---
name: powerbi-data-etl
description: Build and maintain Power BI-friendly public CSV/JSON ETL endpoints, commodity dashboards, scheduled refresh, and M/DAX handoff docs.
version: 1.0.0
created_by: agent
metadata:
  hermes:
    tags: [powerbi, etl, csv, dashboard, commodities, automation]
    category: productivity
---

# Power BI Data ETL

Use this skill when the user asks to finish, automate, debug, or extend a Power BI data pipeline: public CSV/JSON endpoints, scheduled VPS ETL, commodity dashboards, Power Query M, DAX measures, or source substitution/research for missing feeds.

## Operating principles

1. **Finish a working artifact, not just instructions.** Produce or update the ETL script, run it, verify the public endpoint returns `200`, validate row counts/schema, and update the Power BI handoff doc.
2. **Prefer one stable public CSV for Power BI.** Power BI Web connector works best with an anonymous, no-login CSV endpoint. Publish a sibling JSON metadata/status endpoint for freshness, row counts, sources, warnings, and limitations.
3. **Keep schema narrow and stable.** Default columns:
   - `Datum`
   - `Hodnota`
   - `Komodita`
   - `Jednotka`
   - `Zdroj`
   - `Frekvence`
4. **Do not silently hide source quality.** Metadata must disclose proxy sources, latest-only signals, API-key fallbacks, and paid/licensed historical gaps.
5. **For this user, report in Czech with concise status/semaphore and exact copy-paste Power Query/DAX blocks.**

## Recommended workflow

1. Inspect current files and live endpoint:
   - project files under `~/commodity-etl/` or user-specified path,
   - `build_commodities.py`, `POWERBI_QUERIES.md`, `public/*.csv`, `public/*meta*.json`,
   - cron/systemd serving layer,
   - `curl -D- <public-url>` for CSV/JSON.
2. Research alternative sources only where the existing feed is blocked, unstable, or incomplete. Capture the replacement source and its caveat in metadata.
3. Extend ETL with deterministic fetch/parse functions. Avoid heavyweight dependencies unless necessary; XLSX can be parsed with stdlib `zipfile` + XML for stable machine-generated workbooks.
4. Run ETL locally and verify:
   - script compiles,
   - CSV has header + data rows,
   - row counts by `Komodita`,
   - public endpoint sees the new file,
   - scheduled refresh remains active.
5. Update `POWERBI_QUERIES.md` with:
   - live URLs,
   - Power Query M,
   - model/date table,
   - DAX measures,
   - visual recommendations,
   - source limitations and optional API keys.

## Source patterns learned

### FRED

- Public `fredgraph.csv` endpoints may work from a browser but time out or hit Akamai from a VPS.
- Build ETL so FRED is optional via `FRED_API_KEY` from `.env`:

```text
FRED_API_KEY=...
```

- If no key is configured, try public CSV briefly, then proceed with alternative sources rather than blocking the whole ETL.
- Useful FRED PPI examples for packaging/material dashboards:
  - `WPU072205011` — unlaminated polyethylene film and sheet
  - `WPU07` — rubber and plastic products
  - `WPU0913` — paper
  - `WPU09150301` — corrugated shipping containers
  - `WPU091405` — corrugated paperboard sheets/rolls

### World Bank Pink Sheet

World Bank commodity markets page exposes a current monthly XLSX link for `CMO-Historical-Data-Monthly.xlsx`. It is a good automated public fallback/proxy for commodity inputs.

Useful rows/columns include:

- rubber TSR20 / RSS3,
- plywood,
- logs,
- sawnwood,
- metals and energy already covered by many other sources.

Use the current link from `https://www.worldbank.org/en/research/commodity-markets` when possible; keep a fallback URL only as a last resort.

### Freight and container proxies

- Full historical WCI/FBX/C3 container data is often paid/licensed.
- For a free automatic dashboard, use public latest-only signals and clearly label them as latest/proxy:
  - Baltic Dry Index from `balticdryindex.com/data/latest.json`,
  - Freightos public page current FBX global value if extractable.
- Do not represent latest-only FBX/BDI as a complete historical container index.

## Power Query template

```m
let
    Source  = Csv.Document(
        Web.Contents("http://HOST:PORT/commodities.csv"),
        [Delimiter=",", Columns=6, Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed   = Table.TransformColumnTypes(Headers, {
        {"Datum", type date},
        {"Hodnota", type number},
        {"Komodita", type text},
        {"Jednotka", type text},
        {"Zdroj", type text},
        {"Frekvence", type text}
    })
in
    Typed
```

## Verification checklist

- [ ] `python3 -m py_compile build_commodities.py`
- [ ] ETL run produces non-empty CSV and metadata JSON
- [ ] Public CSV returns `HTTP 200` and expected content type
- [ ] Public JSON returns `HTTP 200` and current `updated` timestamp
- [ ] Row count and commodity count increased/changed as intended
- [ ] Cron/systemd refresh remains installed
- [ ] `POWERBI_QUERIES.md` matches the live schema and URL

## References

- `references/commodity-etl-public-sources.md` — concrete source notes and pitfalls from the commodity dashboard implementation.

# Marketing Website Audit Rules

## Scope

Find practical weaknesses and improvement opportunities across:

- website UX and conversion flow,
- technical / functional bugs visible without authentication,
- broken links and assets,
- SEO basics and on-page content,
- messaging clarity and positioning,
- regional competition,
- basic product/service comparison,
- product/service clarity for a first-time visitor,
- factual inconsistencies and false assumptions in the report itself,
- short / medium / long term improvement plan.

## Evidence standards

- Every concrete bug or SEO issue should reference a URL, page element, HTTP status, metadata or observed text.
- Distinguish deterministic findings from LLM judgement.
- Mark each important claim as one of:
  - `FAKT`: directly observed on audited website or cited public source.
  - `ÚSUDEK`: reasonable interpretation from observed evidence.
  - `CHYBÍ DATA`: cannot be confirmed from available sources.
- Do not claim analytics/conversion performance without access to analytics.
- Competitor comparison must cite public sources or mark assumptions.
- Do not claim that a contact, price, CTA, reference or product detail is missing until you explicitly checked the visible page text and probe output.
- If a previous draft contains a factual error, correct it in the next synthesis instead of repeating it.
- Avoid intrusive security testing.

## Minimum coverage checklist

Every full audit must cover these client-relevant sections:

- SEO basics: title, meta description, H1/H2, indexability hints, robots/sitemap if observable, local SEO, content gaps.
- Regional market: at least 3 relevant competitors when public search allows it; otherwise list exact search queries and uncertainty.
- Competitor comparison: offer clarity, proof points, CTA, region relevance, pricing/packages if public, trust signals.
- Product clarity: what is sold, for whom, where available, what is included, next step for the customer.
- Factual error check: verify contacts, CTA, offer, region, references and key product statements before calling them missing.
- Client report: short, visual, non-technical, but still includes SEO, market comparison and product clarity.

## Priority scale

- P0: critical blocker / site unavailable / conversion flow broken.
- P1: high-impact SEO/UX/bug affecting trust or leads.
- P2: medium improvement with clear business upside.
- P3: low priority polish.

## Improvement horizon

- Short term: 0–14 days.
- Medium term: 1–3 months.
- Long term: 3–12 months.

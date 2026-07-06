# Retrobudka.cz Audit Session Notes

This reference captures reusable lessons from the first real run of the Hermes Marketing Crew on `retrobudka.cz`.

## What happened

- User requested a PDF website audit for `retrobudka.cz`.
- Full crew run initially timed out/stalled because some GPT subprocesses hung or returned `Broken pipe`.
- Deterministic probe initially failed to inspect the page because HTTPS had a certificate-chain failure and unverified HTTPS returned 404.
- Probe was patched to preserve the HTTPS failure as evidence but fall back to `http://` content inspection.
- Final delivery succeeded by manually synthesizing a report from verified artefacts:
  - `website_probe.md/json`,
  - completed `website_audit.md`,
  - completed `competitor_market.md`.
- Manifest honestly recorded partial/manual finalization.
- PDF was generated and delivered via `MEDIA:`.

## Durable workflow lesson

For marketing website audits, **do not block on perfect completion of every specialist** when enough verified artefacts exist. Instead:

1. Preserve all completed specialist outputs.
2. Mark failed/stalled specialists explicitly in `run_manifest.json`.
3. Produce a conservative final report using only deterministic probe + successful agent outputs.
4. Add a `quality_review.md` explaining evidence risks and missing checks.
5. Deliver the PDF with a short caveat.

## HTTPS fallback pattern

When a site has broken HTTPS but working HTTP:

- record the HTTPS certificate/404 issue exactly;
- try HTTP only for content inspection;
- classify HTTPS as P0/P1 trust/SEO/conversion issue;
- mention that after HTTPS repair the probe should be rerun.

Example observed finding:

```text
URL: https://retrobudka.cz
Final URL for content: http://retrobudka.cz
HTTPS issue: CERTIFICATE_VERIFY_FAILED / self-signed certificate chain; unverified retry 404
HTTP content status: 200
```

## Report findings that were strongly supported

- HTTPS/cert problem and HTTP fallback.
- Generic title: `Home - Retrobudka`.
- Missing canonical.
- Sitemap/schema/internal URLs using HTTP.
- No form/input detected on homepage.
- Placeholder `admin` in structured data.
- Link-check sample had no broken links.
- Images had no missing alt in the probe sample.

## Do not overclaim

Avoid claiming:

- exact conversion loss without analytics;
- exact search volume without SEO tools;
- exhaustive competitor coverage without a full crawl;
- form deliverability unless a form test was authorized and completed.

## Useful final-delivery wording

```text
PDF přikládám. Poznámka: část agentů timeoutovala, proto je manifest označen jako partial/manual-finalization. Finální report je syntéza z deterministic probe + dokončených auditních artefaktů, nikoli předstíraný plný multi-agent run.
```

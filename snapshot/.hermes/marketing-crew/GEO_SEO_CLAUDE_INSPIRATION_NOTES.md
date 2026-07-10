# GEO SEO Claude inspiration notes

Source: https://github.com/zubair-trabzada/geo-seo-claude, cloned to `/tmp/geo-seo-claude` for implementation analysis.

## Useful ideas extracted

1. **GEO scorecard, not just classic SEO**
   - AI Citability & Visibility
   - Brand Authority Signals
   - Content Quality & E-E-A-T
   - Technical Foundations
   - Structured Data
   - Platform Optimization

2. **AI visibility / citability**
   - Score content blocks for direct-answer quality, self-containment, structure, statistical density, uniqueness.
   - Highlight citation-ready passages and citation-unlikely areas.

3. **AI crawler access**
   - Check robots.txt for GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, PerplexityBot, Google-Extended, CCBot, Applebot-Extended, etc.
   - Detect sitemap references and emerging `Content-Signal:` directives.

4. **llms.txt**
   - Check `/llms.txt` and `/llms-full.txt`.
   - Validate title, blockquote description, section headings, markdown links.
   - Recommend a concise llms.txt structure for important pages.

5. **Brand/entity authority**
   - Treat Wikipedia/Wikidata, YouTube, Reddit, LinkedIn, review platforms and industry mentions as AI-era authority signals.
   - Separate factual presence from recommendations when live checks are not available.

6. **Platform readiness**
   - Google AI Overviews: question headings, direct answer paragraphs, tables/lists, source authority.
   - ChatGPT web search: entity recognition, factual statements, sources, OAI crawler access.
   - Perplexity: Reddit/community validation, direct-source content, freshness.
   - Gemini: Google ecosystem, YouTube/Business Profile, knowledge graph, topical depth.
   - Bing Copilot: Bing index signals, LinkedIn/GitHub ecosystem, structured professional content.

7. **Schema for AI discoverability**
   - Organization/LocalBusiness with `sameAs`.
   - Person schema for authors.
   - Article/BlogPosting with dateModified.
   - BreadcrumbList.
   - WebSite + SearchAction.
   - speakable property for AI assistants.
   - Warn about JS-injected schema and deprecated/restricted schema types.

8. **Technical agent-readiness**
   - SSR/raw HTML content visibility because AI crawlers usually do not execute JS.
   - RFC 8288 Link headers for service discovery.
   - Markdown content negotiation via `Accept: text/markdown`.

## Implementation target in Hermes Marketing Crew

Add deterministic GEO extraction into `website_probe.py`, then require `seo-content`, `strategy-synthesizer`, and `quality-reviewer` to consume these fields in audit reports. Do not copy Claude-specific install/workflow; adapt concepts provider-neutrally for Hermes.

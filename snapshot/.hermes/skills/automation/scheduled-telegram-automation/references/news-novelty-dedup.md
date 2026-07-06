# News monitor novelty and dedup pattern

Use this when a scheduled Telegram news job starts repeating the same headlines or storylines.

## User-facing rule

For news automations, silence is better than filler. Send only when a significant new circumstance materially moves the topic forward. Do not send the same story again just because another source published a new headline or a routine follow-up.

## Prompt criteria

Add an explicit novelty gate to both breaking-news and digest prompts:

- Send only if there is a new material fact: decision, attack, resignation, signed law, collapsed negotiation, product/model launch, earnings shock, supply-chain disruption, major regulatory action, etc.
- Suppress routine commentary, analysis, repeated summaries, speculation, and "same story, new headline" updates.
- Include recent sent topics in the prompt and say: "do not repeat without a significant new turn".
- If fewer than 2 genuinely new digest items exist, output `NOTHING` and stay silent.

## Script-level dedup

Do not rely only on the LLM. Maintain state files with recent story fingerprints:

- Breaking cache: 14 days minimum.
- Digest/topic cache: 30–45 days.
- Store per-item title/preview, normalized word set, normalized URL set, timestamp.
- Suppress if URL overlaps or Jaccard similarity of normalized word sets is high enough (typical thresholds: breaking ~0.18, digest ~0.24).

## Digest filtering pattern

For no-agent digest scripts:

1. Let the web-enabled agent propose 2–5 items or `NOTHING`.
2. Split the HTML/text digest into item blocks.
3. Run each block through deterministic novelty filtering.
4. If fewer than 2 items remain, print nothing.
5. Otherwise print only the retained items and append their titles/previews to history.

## Operational note

When testing with `--force`, a dry run can mutate dedup/history state. Either avoid force tests on production state or reset the test-created state before finishing.

# Lifecycle artifacts: portable contract

Use this as a starting point when a dashboard needs to connect records with asynchronous research, concepts, and production handoffs.

## Record fields

```sql
ALTER TABLE app.items
  ADD COLUMN IF NOT EXISTS research_key text,
  ADD COLUMN IF NOT EXISTS production_output text;
```

- `research_key`: unique opaque slug assigned at research launch and passed to the runner.
- `production_output`: filename/key only, not a browser-supplied path or arbitrary URL.

## Read payload

```json
{
  "id": 42,
  "title": "Example idea",
  "status": "concept",
  "has_concept": true,
  "research": {"state": "ready", "ready": true},
  "production_ready": false
}
```

Keep server filesystem paths out of browser payloads.

## Safe endpoints

```text
GET  /api/item/artifact?item_id=42&kind=research|production
POST /api/item/research       {"id": 42}
POST /api/item/concept        {"id": 42}
POST /api/item/production     {"id": 42}
```

For `artifact`, validate `kind` against a fixed set, retrieve only metadata for `item_id`, and resolve the final path under a fixed base directory. Reject paths outside that base even if database data is malformed.

## Production handoff

If no external deployment target is configured, make “send to production” create an auditable handoff Markdown file that includes description, implementation plan, prompt/specification, and research reference. State clearly that it is a workflow handoff, not a live deployment.

## Legacy runs

Do not fabricate links from titles for runs started before `research_key` existed. Mark them unlinked, or provide an explicit manual association workflow.

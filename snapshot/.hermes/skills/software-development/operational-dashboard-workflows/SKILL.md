---
name: operational-dashboard-workflows
description: Build and evolve internal operational dashboards with lifecycle Kanban boards, meeting-derived work items, safe artifacts, and production handoff.
version: 1.0.0
---

# Operational Dashboard Workflows

## Use when

Use for an internal web dashboard that turns meetings, ideas, research, concepts, or delivery work into a visible operating workflow. Typical requests include Kanban lifecycle changes, meeting-to-idea navigation, showing generated Markdown artifacts, or replacing a static status with a real handoff action.

## Core model

Keep the lifecycle on the primary record rather than duplicating state in presentation-only tables.

```text
new → researching / concept → production → done
                         └→ removed
```

- `removed` is a soft-delete state: hide it from active lists, preserve it in a dedicated history column, and do not physically delete the source record.
- Map internal states to a small number of stable Kanban columns in one pure function, covered by unit tests.
- A derived UI label (for example, “Concept ready”) must not hide the control required to inspect the underlying artifact.

See `references/lifecycle-artifacts.md` for a portable data/API contract.

## Implementation sequence

1. **Discover the real source of truth.** Inspect current tables, existing generators, and output directories before adding fields. Do not invent output URLs if generators only create local files.
2. **Write a failing vertical-slice test.** Test the requested user-visible behavior first: e.g. tag click-through, visible concept action, or a production output button. If the user explicitly replaces an old interaction, update the obsolete test contract first, then add the new failing assertion.
3. **Use an idempotent migration.** Add nullable metadata columns for generated artifacts (e.g. research run key, production handoff filename), plus narrow indexes where needed.
4. **Bind generated files deterministically.** When starting an asynchronous run, create and persist a unique key/slug on the record; configure the runner to include that key in its output directory. Do not try to infer historic ownership from loosely matching titles.
5. **Expose artifacts through a narrow endpoint.** Accept only record ID plus a fixed artifact kind. Resolve the stored metadata under allowlisted base directories, verify containment after `resolve()`, and return escaped Markdown or a safe file response. Never accept a filesystem path from the browser.
6. **Make lifecycle actions real.** “Send to production” must do more than set a badge. Create a handoff artifact or invoke the explicitly configured delivery target, persist its output reference, then transition state only after that succeeds.
7. **Unify navigation.** Meeting tags must carry record IDs, not just text. Clicking a tag should switch to the relevant view and focus the matching card or detail panel.
8. **Verify without mutating user work.** Use a read-only dashboard payload canary and artifact metadata assertions. Do not mark an existing idea as production merely to test the button; use a disposable fixture only with explicit scope.
9. **Deploy and verify the listener.** After restart, check the actual listener owner/PID and the local authenticated boundary. Treat a launcher PID as provisional until the listening process is confirmed.

## UI requirements checklist

- [ ] Kanban uses lifecycle states of the actual entity.
- [ ] Active list filters soft-deleted records; Removed remains visible in history/Kanban.
- [ ] Every generated concept has an explicit “view concept” action.
- [ ] Completed research has an explicit “view research” action.
- [ ] Production shows both state and an output/handoff action.
- [ ] Meeting-derived tags are clickable and navigate by ID.
- [ ] Markdown is escaped before inline HTML rendering.
- [ ] Async runs distinguish not started, running, and ready.

## Pitfalls

- **Static “in production” badges are not workflow actions.** Persist a handoff/output and expose it once completed.
- **Historic artifacts can be ambiguous.** Only claim an automatic link when a stable record-to-run key was stored at launch time; describe older unlinked outputs honestly.
- **Do not use display titles for cross-links.** Titles are mutable and non-unique; pass IDs.
- **Do not leak arbitrary server files.** Artifact endpoints must derive a path from allowlisted roots and database metadata.
- **Do not read generated Markdown directly into unescaped HTML.** Render as escaped text or use a reviewed Markdown renderer.
- **When a user replaces a UI flow, stale tests asserting the removed control are not regressions.** Align the test contract to the new requirement before evaluating the suite.

## Verification

Run the focused new test, then the full suite and syntax check. For a live database canary, assert that meeting tags contain `{id, title}` and records expose only metadata (`ready`, `state`, boolean output flags), not raw server paths. After deployment, verify the process owns the expected local port and the access boundary remains active.

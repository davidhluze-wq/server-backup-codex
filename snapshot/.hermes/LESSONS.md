# Global Self-Learning Rule

This server uses provider-neutral self-learning for all agents, models, crews, and recurring automations.

## Self-learning
When the user corrects you, you discover a mistake, a tool/process fails, or you learn a reusable operational lesson before continuing:
1. Add a concise one-line lesson under `## Lessons` in `/home/david_master/.hermes/LESSONS.md` so the same issue is not repeated.
2. If the lesson belongs to a recurring workflow, crew, dashboard, automation, or skill, also update the closest durable prompt/skill/script note that controls that workflow.
3. Keep lessons factual and reusable. Do not store secrets, temporary task progress, PR IDs, one-off artifact IDs, or stale details.
4. For providers without file-write tools, clearly return the exact one-line lesson to be added by the orchestrator.

## Lessons
- A failed Deep Research run exposed in the shared dashboard must be diagnosed from its runner log and given a configured fallback model; account-specific Codex timeouts are not an authorization failure for the collaborator.
- Final DeepResearch delivery needs a bounded automatic retry after profile fallback plus an explicit Telegram escalation when every final-writer attempt fails.
- The local Next Command Center listener enforces basic authentication, so deployment canaries must authenticate or use browser checks rather than treating its expected HTTP 401 as a service failure.
- When the primary final-writer profile repeatedly times out but the Claude research and review profiles succeed, make Claude the default final writer and retain a separate fallback instead of consuming the known-bad timeout on every run.
- Inspect long-running agent processes by PID and command name without printing their full arguments, because prompts can be large and overwhelm operational diagnostics.
- A transient user unit started with `systemd-run --collect` can disappear immediately after process exit or collection; verify it through `systemctl --user list-units` and journal output before assuming the retry is still running.
- Background units do not inherit the interactive shell PATH; set the Hermes binary path explicitly and normalize executable-launch errors into retryable runner results instead of crashing the orchestrator.
- Bound final-writer and quality-review attempts independently of the broad workflow timeout, so a stalled model triggers fallback and escalation within a predictable time.
- After applying a role-specific timeout change, inspect each orchestration call site; a broad context patch can accidentally constrain an upstream role instead of the intended final-quality role.
- Before declaring a Next dashboard deployed, exercise every visible navigation and header control in the live browser; rendered controls alone do not prove their handlers are connected.
- Shared Meeting Intelligence ingestion must trigger the full transcript-to-ideas workflow for every authorized account; accepting a transcript without analysis creates inconsistent records across collaborators.
- After migrating a running process to a user systemd unit, verify the listener before proxy checks; an active unit can still fail during application startup and leave the public route at 502.
- When a documentation patch fails because wording has drifted, reread the exact current section and patch a smaller verified context instead of retrying the stale block.
- Deduplikace nápadů musí testovat běžně rozšířený název téhož návrhu, nejen téměř shodný text, jinak uživatelé stále vytvářejí zjevné duplicity.
- If a dashboard launched through an untracked `nohup` wrapper repeatedly exits after passing an initial probe, migrate it to a user-level systemd unit with restart supervision instead of retrying the wrapper.
- Keep deployment health checks independent from a secondary collaborator account when the primary product path uses a different shared-proxy credential; verify listener and contract shape separately.
- After a supervisor-driven restart, revalidate the exact live authentication path before using its response in deployment assertions; a local credential can be replaced by service configuration drift.
- For a managed Next.js restart, identify the server process from its listening port and walk its parent chain; the `next-server` command line does not reliably retain the project path.
- Use the JSON resource hook only for JSON APIs; document endpoints need a text fetcher before their content can be rendered in an in-app dialog.
- Do not hand out a dashboard credential until its intended public route has been verified; a local account check alone does not make an isolated external login usable.
- A successful immediate post-restart health check does not prove persistence; repeat the listener check after subsequent deployment validation before declaring a managed service stable.
- When validating a generated credential, pass the stored test value into the verifier explicitly; a placeholder check can only prove rejection, not successful authentication.
- On this VPS, Caddy configuration under `/etc/caddy` requires interactive sudo; do not apply a non-persistent runtime proxy change when the permanent configuration cannot be updated.
- For externally shared dashboard access, isolate the app behind its own authenticated route and grant collaborators an application-level read-only account instead of server or sudo access.
- When a user reports a paid entitlement, distinguish account-level access from the current agent session's configured model and check local model/config state before concluding availability.
- If an official docs/manual fetch fails with DNS or restricted-network symptoms, retry the same fetch with explicit network approval before falling back.
- Automatic/recurring jobs created for David must also be registered in agentsmon dashboard automatic runs with a clear expandable description and Start/Stop controls when technically feasible.
- If `execute_code` is blocked by approval/cron trust policy, switch to explicit read/write/patch/terminal tools instead of retrying the same helper.
- Hermes Architect must ingest `/home/david_master/.hermes/LESSONS.md` as an optimization-idea backlog and convert recurring lessons into propose-only improvements.
- If `web_extract` reports the configured backend is search-only, verify GitHub/pages via `git ls-remote`, `gh`, `curl`, or browser instead of retrying `web_extract`.
- In shell backup scripts running with `set -u`, define new path variables explicitly before use and run `bash -n` plus a real dry/run check after edits.
- If a terminal command is blocked by approval policy as lacking user consent, stop the workflow and ask for explicit approval before retrying or using an equivalent route.
- Before writing through a `*-latest` report path, check whether it is a symlink; update the symlink target instead of overwriting the old dated report via the link.
- For the Telegram-bridged Claude session (agent2telegram attach → tmux `David_Claude`), set `permissions.defaultMode: "bypassPermissions"` in `~/.claude/settings.local.json` so auto-approve survives restarts; the shift+tab bypass toggle is per-session only and is lost on restart, forcing manual approvals the Telegram user can't click.
- Monitor process checks must match the deployed console command and be validated against a live process after Hermes upgrades to avoid false outage alerts.
- Treat ElevenLabs TTS and incoming-message transcription as separate capabilities: Hermes requires a configured STT provider (local Whisper, Groq, OpenAI, or Mistral) for Telegram voice input.
- Verify the server backup remote with its configured deploy key; an unkeyed interactive Git command can fail even though the scheduled backup push is correctly configured.
- Secret scans for `sk-` API keys must require a word boundary before the prefix, otherwise ordinary hyphenated prose such as `risk-free` can block a sanitized backup.
- Before attempting transcription of a Telegram voice message, confirm that the bridge downloaded an audio attachment; message delivery alone does not guarantee that media reached the server.
- On this server, inspect JSON configuration with the standard Python `json` module when `jq` is unavailable instead of assuming a JSON CLI is installed.
- A configured ElevenLabs key is not sufficient evidence that Telegram voice transcription works; validate it with a non-billing API request and replace it when the provider returns HTTP 401.
- For YouTube captions, parse the player response structurally rather than relying on a brittle `captionTracks` regular expression, because the watch-page serialization can vary.
- The system Python on this server has no `pip` module; use the installed `uv` workflow or a project virtual environment for temporary Python dependencies.
- When arbitrating research agents, combine complementary primary evidence but keep unverified numeric thresholds and source-specific claims explicitly labeled until their full text is checked.
- Do not reuse prediction-market probability fields for spot or CFD prices; provider-specific price semantics must remain explicit in storage and the dashboard.
- If a configuration audit needs secret-presence evidence, parse credential-bearing config with a purpose-built script that prints booleans only; never run broad content search over those files.
- When a patch cannot find its expected text, read the current file and use exact nearby context rather than retrying the stale match.
- For voice/Telegram health checks, query only status/error metadata; never stream broad bridge logs because they can contain private transcript content.
- An agent2telegram attach bridge cannot start without its configured tmux session; configure STT first, but defer the bridge launch until the target agent session exists.
- After restarting a dashboard service, verify its live listener and process rather than relying on a stale PID or the launch command's exit status.
- Tests of idempotent webhook ingestion must use a unique event key and explicitly clean it up, otherwise a correct duplicate response can mask the intended assertion.
- Verify webhook persistence tests against the public result contract and the stored record; do not assume an ingestion helper returns a full database object.
- Reuse the application's database compatibility helper in verification scripts; this environment may expose `psycopg` without the legacy `psycopg2` module.
- Before running Git status or diff checks for a deployed component, resolve its repository root; service directories may be deployed outside a Git worktree.
- Deploying a public HTTPS listener requires verified privileged access for ports, packages, and firewall rules; do not assume a user session has passwordless sudo.
- When adding a multi-line deployment script with `apply_patch`, ensure every added blank and content line is represented inside the file hunk, then run a syntax check before handing it off.
- When a long-running command's execution cell closes before its child processes, monitor the child process and run artifacts directly instead of relying on the stale cell identifier.
- During research arbitration, never mark a source verified when deterministic URL checks report 403, timeout, or a client challenge; verify licenses and material claims from direct repository content before adopting them.
- Do not equate a free commodity quote feed with sufficient futures paper-trading data; contract rolls, multipliers, settlement rules, and licence scope must be verified before enabling a commodity ledger.
- Keep feasibility-spike result validation aligned with the runner's declared JSON schema; assert actual event fields rather than inventing trade-count aliases.
- When provider research is limited to search snippets or blocked source text, quarantine exact prices, licence terms, and feature availability until the full official page, API response, or contract is verified.
- A final research report must retain every explicitly requested decision artifact and must not keep a provider ranking after the source audit invalidates the evidence supporting that ranking.
- When a user pastes an API credential into chat, do not use or repeat it; require revocation and local secret-store entry before proceeding.
- In a non-interactive cron run, if execution of a temporary verifier requires approval, do not claim suite verification; report the concrete approval blocker and retain only independently validated artifact checks.
- Before validating a new provider credential, confirm its SDK exists in the isolated test environment; do not assume another trading dependency installed it transitively.
- For provider SDK integration checks, inspect methods on an authenticated client instance rather than assuming class-level endpoint attributes.
- For market-data definitions, validate semantic values and provider sentinels, not only field presence or non-null status; a populated multiplier field can still be unusable for sizing.
- Do not derive futures tick value by multiplying displayed tick increment and unit quantity without validating the provider's price scale, currency convention, and official contract specification.
- Before consuming any paid data-provider usage or promotional credits, obtain explicit user approval of a spending limit; an insignificant estimated request is not implicit budget consent.

## Lessons
- agentsmon reverse-proxy: proxovaný dashboard musí volat API přes prefix (`/meetings`, `/lana`). Nepoužívej `fetch(u)` s proměnnou (proxy přepisuje jen literál `fetch("/`) — spočítej v JS `BASE = location.pathname.startsWith("/<prefix>")?"/<prefix>":""` a volej `fetch(BASE+u)`.
- agentsmon do_POST původně neproxoval POST (jen `/api/agent|auto/action`) → tlačítka přes proxy vracela 404; přidán `_proxy_post` + větev v do_POST pro PROXY_BACKENDS (timeout 300s kvůli LLM/deepresearch).
- After modifying a unittest file, run a syntax/import check before interpreting a test-runner failure as a feature failure.
- When a VPS has multiple projects with generic modules such as `server.py`, run integration code from the target project directory or import by absolute path to avoid module-shadowing false failures.
- Hermes cron scripts must reside under `~/.hermes/scripts/`; use a thin wrapper for project-local runners.
- For managed service restarts, do not use shell-level `nohup` in a foreground terminal command; use a tracked background process or the existing supervisor.
- If `web_extract` is backed by a search-only provider, use `web_search` result metadata or another approved fetch path; do not retry the same unsupported extraction.
- In non-interactive cron runs, a `python3 -c` temporary verifier may require approval; report that concrete block rather than treating JSON syntax validation as full behavioral verification.
- Keep temporary-verifier execution separate from cleanup in cron jobs: approval gating a deletion can prevent an otherwise safe verifier from running.
- After restarting a public web app, verify both the local listener and the public proxy response before declaring the deployment healthy.
- Verify whether an application directory is a Git repository before including Git status or commit steps in its verification plan.
- Before planning a Git commit, verify a repository has a configured author identity; do not infer or set user identity without explicit user direction.
- When replacing a dashboard view with a different interaction model, update legacy UI tests that assert removed controls before interpreting their failure as a regression.
- After a managed-service restart, report the PID that actually owns the listener after verification; an intermediate background launcher can lose a port race to the supervisor.
- A managed service may fail to auto-restart after a child is terminated; verify within a bounded window and launch a tracked replacement only if no listener returns.
- If a targeted web-search query times out, retain successful source results and do not infer a negative advisory result from the timeout.
- In a non-interactive cron run, a terminal operation pending approval cannot update a symlink; complete independently writable artifacts and report the blocked alias update rather than overwriting its old target.
- In non-interactive runs, keep verification execution separate from cleanup because an approval block on deletion can prevent the verification command from starting.
- Temporary verification-file deletion may require approval in this environment; when no approver exists, leave the harmless `/tmp/hermes-verify-*` file and report it.
- For read-only web research, do not pipe a downloaded response directly into an interpreter; save or inspect it first to avoid an approval block.
- When a shared artifact reports a sibling-writer warning, read it immediately and confirm the intended content before proceeding; avoid blind overwrites.
- In a temporary verifier, keep the target artifact path separate from the verifier path; never use the target variable for cleanup.
- Before ordering a live database query by a timestamp, inspect the deployed schema; use its actual monotonic ingest field when no timestamp exists.
- When replacing a combined UI renderer, preserve helper functions still called by the replacement before running the client bundle.
- The Meeting Intelligence BaseHTTP server does not implement HEAD; use GET for listener/auth canaries.
- When inspecting a service's Python module, preserve its process PYTHONPATH; the host interpreter may not resolve the deployed package otherwise.
- Run `systemctl --user daemon-reload` before optional unit maintenance commands; a newly created unit is not addressable until the user manager has loaded it.
- Before patching a deployed schema, locate the migration that owns the table; the base schema may intentionally omit later-added tables.
- Run Meeting Intelligence tests with the deployed virtual environment; the host Python intentionally lacks the PostgreSQL driver used by export scripts.
- Run Meeting Intelligence test discovery from its project root; several UI tests resolve templates and scripts through relative paths.
- When replacing the shared Meeting Intelligence template, revise its source-level UI assertions to validate the new supported workflow instead of retired markup.
- Validate a dedicated account against the live proxy before declaring access complete; a stale plaintext credential cannot be inferred from its stored hash.
- When a user requests a duplicate dashboard address, confirm whether it must serve the current Next.js Command Center rather than the legacy backend template before wiring the proxy.
- For a shared Next.js workspace, scope the rendered navigation as well as backend permissions; granting only Meeting APIs is insufficient if the full Command Center shell remains visible.
- After manually restarting the AgentsMon gateway, verify it remains bound beyond the initial request; a successful immediate response does not establish durable public availability.
- Before enabling a systemd replacement for a manually launched listener, terminate the old process holding the port; otherwise the service will enter an avoidable bind-failure restart loop.
- A shared Meeting Intelligence ingest must persist validated idea candidates as well as minutes and tasks; a summary-only upload leaves the downstream ideas workflow incomplete.
- Hermes hard-blocks system reboot commands even with user confirmation; instruct the user to run reboot manually in their own terminal.
- In non-interactive cron runs, execute a temporary verifier separately from cleanup: a deletion approval gate can prevent the verifier from running.
- For a proxied SPA, verify the exact user-facing hash route and its frontend bundle; a healthy ba...[truncated]

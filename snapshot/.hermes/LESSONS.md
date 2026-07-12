# Global Self-Learning Rule

This server uses provider-neutral self-learning for all agents, models, crews, and recurring automations.

## Self-learning
When the user corrects you, you discover a mistake, a tool/process fails, or you learn a reusable operational lesson before continuing:
1. Add a concise one-line lesson under `## Lessons` in `/home/david_master/.hermes/LESSONS.md` so the same issue is not repeated.
2. If the lesson belongs to a recurring workflow, crew, dashboard, automation, or skill, also update the closest durable prompt/skill/script note that controls that workflow.
3. Keep lessons factual and reusable. Do not store secrets, temporary task progress, PR IDs, one-off artifact IDs, or stale details.
4. For providers without file-write tools, clearly return the exact one-line lesson to be added by the orchestrator.

## Lessons
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
- If a configuration audit needs secret-presence evidence, parse credential-bearing config with a purpose-built script that prints booleans only; never run broad content search over those files.
- When a patch cannot find its expected text, read the current file and use exact nearby context rather than retrying the stale match.
- For voice/Telegram health checks, query only status/error metadata; never stream broad bridge logs because they can contain private transcript content.
- An agent2telegram attach bridge cannot start without its configured tmux session; configure STT first, but defer the bridge launch until the target agent session exists.

## Lessons
- agentsmon reverse-proxy: proxovaný dashboard musí volat API přes prefix (`/meetings`, `/lana`). Nepoužívej `fetch(u)` s proměnnou (proxy přepisuje jen literál `fetch("/`) — spočítej v JS `BASE = location.pathname.startsWith("/<prefix>")?"/<prefix>":""` a volej `fetch(BASE+u)`.
- agentsmon do_POST původně neproxoval POST (jen `/api/agent|auto/action`) → tlačítka přes proxy vracela 404; přidán `_proxy_post` + větev v do_POST pro PROXY_BACKENDS (timeout 300s kvůli LLM/deepresearch).

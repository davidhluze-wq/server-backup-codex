---
name: agent2telegram-elevenlabs-stt
description: Audit and enable ElevenLabs Scribe voice-message transcription for Agent2Telegram attach bridges without exposing API keys.
---

# Agent2Telegram + ElevenLabs STT

## Use when

A Telegram-connected Codex/Claude attach bridge needs voice-message transcription through ElevenLabs Scribe.

## Safety

- Never print, paste, search broadly for, or put API keys in command output.
- For configuration checks, use a small script that returns only a boolean `key_present`.
- Never stream broad bridge logs: they can contain private voice transcript content. Query only startup/error metadata.
- Preserve configuration and transcript/log permissions at `0600` (launcher scripts at `0700`).
- `agent2telegram` attach mode requires its target tmux session to exist before the bridge can start.

## Audit

1. List bridge configs and report only `elevenlabs_key_present`, `tmux_session`, and bot health:
   ```bash
   env AGENT2TELEGRAM_CONFIG=/path/to/config.json \
     PYTHONPATH=~/.agent2telegram-src /usr/bin/python3 -m agent2telegram doctor
   ```
2. Verify running bridges without credentials:
   ```bash
   ps -eo pid,etime,args | grep -E '[a]gent2telegram run'
   ```
3. Verify the target session before starting an attach bridge:
   ```bash
   tmux has-session -t SESSION_NAME
   ```
4. Inspect only bridge startup/error lines, never transcript lines:
   ```bash
   grep -Ei 'Attach bridge live as|error|exception|failed|tmux session' LOGFILE | tail -20
   ```

## Enable an existing bridge

1. Get explicit user approval before propagating an existing ElevenLabs key into another bridge config or starting a model session.
2. Atomically copy only the `elevenlabs_api_key` field from an approved source config; do not print its value. Keep targets `0600`.
3. Start explicitly configured workers with:
   ```bash
   PYTHONPATH=~/.agent2telegram-src \
   AGENT2TELEGRAM_CONFIG=/path/to/config.json \
   /usr/bin/python3 -m agent2telegram run --config /path/to/config.json
   ```
4. For a missing agent session, create the tmux session only with explicit approval, then run the bridge launcher.
5. Verify `agent2telegram doctor`, the bridge process, and its `Attach bridge live` line. A genuine voice-note canary is the final real STT proof.

## Dashboard / persistence

- Register the launcher/restart command and service label in `~/.config/agentsmon/config.json` whenever bridge topology changes.
- Ensure a launcher is idempotent: do not duplicate existing bridge processes, and skip an attach bridge until its target tmux session exists.
- Verify registry parsing with `python3 -m json.tool ~/.config/agentsmon/config.json` and `PYTHONPATH=~/.agentsmon-src /usr/bin/python3 -m agentsmon doctor`.

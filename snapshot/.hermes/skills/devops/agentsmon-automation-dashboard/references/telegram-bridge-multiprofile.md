# Multi-profile Agent2Telegram bridges

## When to use

Use when one VPS has several Telegram bots connected to separate interactive agent/tmux sessions and voice transcription is enabled per bridge.

## Safe audit sequence

1. Enumerate `~/.config/agent2telegram/*.json` with a parser that prints only:
   - config file name,
   - target tmux session,
   - agent type,
   - `elevenlabs_key_present=true|false`.
2. Inspect process lines and tmux sessions separately.
3. Run `agent2telegram doctor` per config; it verifies bot reachability and agent binary, but does not prove a live transcription.
4. Inspect only startup/error metadata in logs. Never stream full bridge logs: they can include the complete text of Telegram voice messages.

## Attach-mode rule

`agent2telegram run --config <file>` in `attach` mode exits if its configured tmux session does not exist. A launcher must check:

```bash
tmux has-session -t "$session" 2>/dev/null
```

before starting that profile. This avoids a restart loop and misleading dashboard green status.

## Launcher design

- Store it under `~/.local/bin/` with mode `0700`.
- Start with `set -euo pipefail` and `umask 077`.
- For each config, detect an existing process using its `--config` argument before `nohup` launch.
- Handle the default/no-`--config` Master process separately so dashboard recovery does not forget it.
- Keep per-profile logs in a private state directory and use `0600` for historical logs.

## Dashboard registration

For a process monitored by agentsmon, update the existing `daemons[]` record in `~/.config/agentsmon/config.json` to call the launcher as its `restart` command. Retain a truthful shared service status label if the dashboard cannot model per-profile status. Validate JSON before reporting success.

## Verification

```bash
bash -n ~/.local/bin/start-agent2telegram-bridges.sh
python3 -m json.tool ~/.config/agentsmon/config.json >/dev/null
~/.local/bin/start-agent2telegram-bridges.sh
ps -eo pid,args | grep -E '[a]gent2telegram run'
```

Then check all configs with `agent2telegram doctor`. A user-sent short voice note is the only meaningful end-to-end transcription canary; report the result without reproducing transcript text.

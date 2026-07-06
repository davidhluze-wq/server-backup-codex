# Server Agent Environment Backup

Created: 2026-07-06T17:38:59Z

This repository is a sanitized backup of the agent environment on `/home/david_master`.
It is intended for configuration recovery, review, and migration planning.

## Included

- Agent2Telegram configuration snapshots with tokens redacted.
- Codex configuration, rules, and local skill metadata.
- Claude settings that are safe to store, with sensitive values redacted.
- Hermes orchestration configuration, crews, prompts, scripts, profiles, and audit workflows.
- Local source snapshots for Agent2Telegram, AgentsMonitoring, and HumanAgentWiki without their `.git` directories.
- System inventory files:
  - `system/tmux-sessions.txt`
  - `system/processes.txt`
  - `system/user-services.txt`
  - `system/crontab.txt`
  - `system/ufw-status.txt`
  - `system/git-remotes.txt`
  - `system/repo-status.txt`
  - `system/file-list.txt`

## Excluded

- API keys, Telegram bot tokens, Google OAuth tokens, credentials, and private keys.
- `.env` backup files and local secret files.
- Runtime databases, logs, caches, sessions, history files, lock files, PID files, virtualenvs, and `node_modules`.
- Large generated state that is not needed to understand or rebuild the setup.

## Restore Notes

Do not blindly copy this backup over a live server. Use it as a reference:

1. Recreate the source repositories from their upstream GitHub remotes where possible.
2. Copy selected configuration files into place.
3. Reinsert fresh secrets manually from the password manager or provider dashboards.
4. Restart services only after checking paths, ports, tokens, and tmux/session names.

The backup intentionally does not contain live secrets, so it is not a one-command restore archive.

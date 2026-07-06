# Restore Notes

This backup is documentation-first and secret-free.

## Main Paths

- Agent2Telegram config: `snapshot/.config/agent2telegram`
- Codex config: `snapshot/.codex`
- Claude settings: `snapshot/.claude`
- Hermes config and crews: `snapshot/.hermes`
- Source snapshots: `snapshot/repos`
- Server inventory: `system`

## Recommended Recovery Order

1. Install base packages and Python/Node dependencies required by the original projects.
2. Clone the upstream repositories listed in `system/git-remotes.txt`.
3. Compare the cloned repositories with `snapshot/repos`.
4. Copy only the required config files from `snapshot`.
5. Add fresh secrets locally. Do not commit secrets.
6. Recreate or enable systemd/tmux/cron services based on files in `system`.
7. Validate each bot or dashboard endpoint before exposing it publicly.

## Secret Handling

Secrets were removed or redacted before commit. Search for `[REDACTED` markers after restore and replace them only on the target server.

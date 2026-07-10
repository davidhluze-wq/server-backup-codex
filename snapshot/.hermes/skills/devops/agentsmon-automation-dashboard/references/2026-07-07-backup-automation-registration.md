# 2026-07-07 — Backup automation registration and verification notes

Session pattern worth reusing:

- User asked to repeat a sanitized GitHub backup to the existing branch `server-agent-env-backup-20260706`.
- The weekly backup job already existed as a user crontab line:
  `15 3 * * 0 /home/david_master/.local/bin/weekly-server-agent-backup.sh`.
- Because the user's standing rule says recurring jobs are incomplete until visible in agentsmon, the backup job was also added to `~/.local/state/agentsmon/automatic_runs.json` with:
  - stable id: `server-agent-env-backup-weekly`
  - source: `crontab`
  - output URL: GitHub branch URL
  - log path: `~/.local/state/server-agent-env-backup/weekly-backup.log`
  - Stop/Start semantics: reversible crontab commenting/restoring.

## Backup-specific pitfall

When the automation being registered is the backup itself, remember to include the agentsmon registry and updated backup script in the next backup payload; otherwise the dashboard integration exists locally but is missing from the GitHub restore reference.

Useful payload files:

```text
snapshot/.local/state/agentsmon/automatic_runs.json
system/weekly-server-agent-backup.sh
```

## Verification pattern

After running the backup script:

```bash
git -C ~/server-agent-env-backup status --short
GIT_SSH_COMMAND='ssh -i ~/.ssh/server_backup_codex_ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new' \
  git -C ~/server-agent-env-backup ls-remote origin refs/heads/server-agent-env-backup-20260706
rg -n --hidden -S '<secret-regex>' ~/server-agent-env-backup --glob '!.git/**'
```

If `set -u` is enabled in a shell script, define any new path variables before use and run both `bash -n` and a real execution check. A syntax check alone will not catch unbound runtime variables.

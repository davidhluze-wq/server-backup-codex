# Weekly Backup Automation

The server has a weekly cron task for this backup.

Cron entry:

```cron
15 3 * * 0 /home/david_master/.local/bin/weekly-server-agent-backup.sh
```

Schedule: every Sunday at 03:15 UTC.

The task rebuilds the sanitized backup, runs a secret scan, commits changes, and pushes to:

```text
git@github.com:davidhluze-wq/server-backup-codex.git
```

Branch:

```text
server-agent-env-backup-20260706
```

The cron job uses this local SSH key:

```text
/home/david_master/.ssh/server_backup_codex_ed25519
```

Public deploy key to add in GitHub:

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK/43wk67e9XQTkhggimhWhgKM8royrNJirf5Bmc3pZ4 server-backup-codex@david-master
```

GitHub setup required:

1. Open `davidhluze-wq/server-backup-codex`.
2. Go to Settings -> Deploy keys.
3. Add the public key above.
4. Enable write access.

Until the deploy key is added with write access, local backup commits will work but GitHub push will fail with `Permission denied (publickey)`.

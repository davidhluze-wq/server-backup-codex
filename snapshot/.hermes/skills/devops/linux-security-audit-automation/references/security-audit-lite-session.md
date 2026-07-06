# Security Audit Lite session notes

This reference captures durable techniques from a Linux/VPS security-audit setup/remediation session. It is not a transcript; it is a compact recipe for future similar work.

## User-provided audit shape

- Daily cadence:
  - `03:00` read-only audit and CVE analysis writes report/status to disk.
  - `07:30` deterministic failsafe alerts if today’s report is missing.
  - `07:45` digest sends the `## Shrnutí pro Telegram` section.
- Keep it lightweight: no FIM and no Lynis.
- Report in Czech with semafor lines: `🔴/🟡/🟢 – popis`.
- If any yellow/red finding exists, ask one final question: `❓ Mám opravit vše, co půjde? (napiš ano)`.
- Do not disable AI-agent autonomy flags (`--dangerously-*`, `--skip-permissions`, `--bypass-approvals`).
- Do not flag SSH password authentication when the environment intentionally accepts it; assess root login and brute-force protection instead.

## Files used in this implementation

A user-home implementation avoided root-owned `/opt`/`/var` paths:

- Base: `~/.hermes/security-audit-lite/`
- Scripts: `~/.hermes/scripts/security-audit-lite/`
- Collector: `audit_collect.sh`
- Failsafe: `audit_failsafe.py`
- Digest: `audit_digest.py`
- Dashboard: `index.html` + `status.json`

## Hermes cron pattern

Create three jobs:

1. **Night audit**
   - Schedule: `0 3 * * *`
   - `script`: collector shell script.
   - `deliver`: `local`.
   - Toolsets: `web`, `file`, `terminal`.
   - Prompt tells the LLM to read facts, compare previous report, perform a capped CVE search, write `report-YYYY-MM-DD.md`, update `report-latest.md`, and write `status.json`.
2. **Failsafe**
   - Schedule: `30 7 * * *`
   - `no_agent=True`, script-only.
   - Prints one warning only if today’s report is missing/empty; empty stdout means no delivery.
3. **Digest**
   - Schedule: `45 7 * * *`
   - `no_agent=True`, script-only.
   - Extracts `## Shrnutí pro Telegram` from today’s report and prints it verbatim.

## Collector details

Useful read-only commands:

```bash
apt list --upgradable 2>/dev/null
apt-get -s upgrade 2>/dev/null
ss -tulnp 2>/dev/null
ss -tunp state established 2>/dev/null
ufw status verbose 2>&1 || true
nft list ruleset 2>/dev/null | sed -n '1,160p'
iptables -S 2>/dev/null | sed -n '1,160p'
sshd -T 2>/dev/null | egrep '^(permitrootlogin|passwordauthentication|pubkeyauthentication|port|listenaddress|maxauthtries)'
journalctl -u ssh -u sshd --since '24 hours ago' 2>/dev/null
systemctl is-active fail2ban 2>/dev/null
getent group sudo
awk -F: '$3 >= 1000 && $3 < 65534 {print}' /etc/passwd
last -10
crontab -l 2>/dev/null
systemctl list-units --type=service --state=running --no-pager
ps aux --sort=-%cpu | head -25
df -h /
df -ih /
```

When wrapping the AWK command inside a shell function that itself evaluates a string, escape `$3` as `\$3` so the outer shell does not expand it.

## Findings and remediation pattern from the session

Findings:

- Public SSH on `0.0.0.0:22` and `[::]:22`.
- Active root SSH session from a public IP.
- `fail2ban` inactive, though no failed attempts in the last 24h.
- Reboot required due to `libc6`; 172 packages upgradable, including security-sensitive packages.
- Firewall could not be verified because `sudo -n` required a password.
- A Python dashboard (`agentsmon dashboard`) listened on `0.0.0.0:8765`.

Safe remediation completed without sudo:

1. Inspect dashboard config and launcher.
2. Change dashboard host from `0.0.0.0` to `127.0.0.1` in the user-owned config.
3. Kill/restart only the dashboard via its launcher.
4. Verify with `ss -tulnp | grep ':8765'` that it now listens on `127.0.0.1:8765`.
5. Probe local HTTP; `401` was acceptable because it confirmed auth was enabled.

Privileged remediation blockers:

- System upgrade and reboot.
- fail2ban install/enable.
- firewall verification/rules.
- SSH `PermitRootLogin` verification/change.

When `sudo -n true` returns nonzero, do not ask for the sudo password. Report that the remaining items need a privileged shell and list the exact categories.

## CVE lookup pattern

Keep to authoritative/capped checks:

- NVD API examples:
  - `https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=OpenSSH&pubStartDate=YYYY-MM-DDT00:00:00.000&pubEndDate=YYYY-MM-DDT23:59:59.999`
  - `https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=Linux%20kernel&pubStartDate=...`
- Vendor pages:
  - Ubuntu Security Notices.
  - nginx security advisories if nginx is installed/running.

Only mark CVEs as findings when they map to installed/running components and versions. Otherwise label them watch items.

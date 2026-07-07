---
name: linux-security-audit-automation
description: "Set up and run lightweight Linux/VPS security audits with read-only collection, CVE checks, Telegram-style semafor reports, and safe remediation handoff."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [linux, security, audit, cron, vps, telegram, cve]
    created_by: agent
---

# Linux Security Audit Automation

Use this skill when the user asks to create, run, schedule, review, or remediate a lightweight security audit for a Linux/VPS host. It is optimized for practical operations: collect facts read-only, summarize risks in plain language, schedule recurring checks, and only remediate after explicit user approval.

## Core principles

1. **Audit first, mutate later.** The audit path is read-only: collect facts, analyze, report. Do not install updates, change firewall rules, stop processes, restart services, or modify SSH until the user explicitly approves remediation.
2. **Do not ask for secrets.** Never ask the user to type passwords/API keys into chat. If sudo/root is required and passwordless sudo is unavailable, report exactly which commands/actions require a privileged shell.
3. **Plain-language semafor output.** User-facing summary should be short Czech/English as appropriate, with one risk per line and clear severity: `🔴/🟡/🟢 – short description`.
4. **Preserve intentional automation risks.** Do not flag or disable AI-agent autonomy flags such as `--dangerously-*`, `--skip-permissions`, or `--bypass-approvals`. Treat them as consciously accepted operational risk unless the user explicitly asks otherwise.
5. **SSH password login may be intentional.** Do not flag `PasswordAuthentication yes` or propose key-only SSH if the audit brief says password login is accepted. For SSH, focus on root login, brute-force protection, exposed port, failed attempts, and anomalous sessions.
6. **Honor user-declared accepted risks immediately.** If the user says a public port, active root SSH session, or `PermitRootLogin yes` is intentional, remove it from findings/status and record it as accepted context. Do not keep asking to "fix" it unless the user explicitly asks to harden that area.

## Lightweight audit workflow

1. **Collect host facts read-only**
   - OS/kernel: `/etc/os-release`, `uname -a`, uptime.
   - Updates/reboot: `apt list --upgradable`, `apt-get -s upgrade`, `/var/run/reboot-required`.
   - Ports/connections: `ss -tulnp`, `ss -tunp state established`.
   - Firewall: `ufw status verbose`, `nft list ruleset`, `iptables -S` where privileges allow.
   - SSH: `sshd -T` for `permitrootlogin` etc.; recent SSH logs; `last -10`.
   - Brute-force protection: `systemctl is-active fail2ban`, `fail2ban-client status`.
   - Accounts: `getent group sudo`, `/etc/passwd` UID >= 1000.
   - Persistence: user/system cron, running systemd services.
   - Processes: top CPU/memory; suspicious public listeners.
   - Disk/backups: `df -h /`, `df -ih /`, obvious backup services/dirs.
2. **Analyze for actionable risks**
   - Prioritize public listeners on `0.0.0.0`, active root SSH sessions, missing/unknown firewall, many pending security updates, reboot-required, inactive brute-force protection, unexpected sudo users or cron jobs.
   - If firewall or SSH config needs sudo and cannot be read, mark as *unverified*, not as definitely broken.
3. **CVE/advisory check**
   - Keep it short: query only the actual stack found on the host.
   - Prefer authoritative sources: Ubuntu Security Notices, NVD API, OSV, vendor advisory pages.
   - Tie CVEs back to installed/running versions; otherwise mark as watch item, not confirmed finding.
4. **Report**
   - Write a full markdown report with facts, reasoning, limitations, and a section exactly like `## Shrnutí pro Telegram` when a digest script expects it.
   - Generate a small `status.json` for dashboards: `{updated, overall, areas:[{name,status,note}]}`.
5. **Remediate only after approval**
   - First fix non-privileged, low-risk items that do not break services, e.g. binding a user-owned dashboard to `127.0.0.1` and restarting only that user process.
   - For privileged changes (apt upgrade, reboot, fail2ban install/enable, firewall, SSH root-login), check `sudo -n true`. If it fails, provide a concise privileged-command plan rather than asking for the password in chat.
   - If the user narrows scope (for example: "backups are handled; solve only updates"), do not revisit backup findings or broader hardening in that remediation pass. Act only on the accepted scope and report only that scope.

## Practical patterns and pitfalls

### Updates-only remediation

When the user asks to resolve only system updates:

1. Check current pending updates and reboot state: `apt list --upgradable` and `/var/run/reboot-required`.
2. Run `sudo -n apt-get update` first.
3. For noninteractive upgrade under sudo, prefer `sudo -n env DEBIAN_FRONTEND=noninteractive apt-get -y upgrade`; direct `sudo DEBIAN_FRONTEND=... apt-get ...` may fail if sudoers disallows setting environment variables.
4. If the sudo timestamp expires mid-task, do not ask for a password in chat; report the exact command plan or retry only if passwordless sudo is still available.
5. After upgrades, verify no packages remain upgradable, whether reboot is required, and restart only services explicitly requested by apt/needrestart or clearly safe services the user approved.


### Public dashboard remediation

If a user-owned dashboard is listening on `0.0.0.0`, look for its config and CLI help before killing it. Before changing the bind address, check whether the user intentionally exposes it and whether it already has authentication (for example HTTP `401` without login). If the user confirms it is intentionally public and password-protected, mark it accepted/green and do not restrict it.

If it is not intentional, prefer changing its configured host to `127.0.0.1`, then restart via its own launcher. Verify with:

```bash
ss -tulnp | grep ':PORT'
curl -sS -o /tmp/probe.html -w 'http_code=%{http_code}\n' http://127.0.0.1:PORT/ || true
```

A listener on `127.0.0.1:PORT` is no longer directly public via application bind. Still note that firewall/cloud firewall may need separate privileged verification.

### Cron scheduling with Hermes

For recurring audit in Hermes:

- Night audit cron can deliver `local`, collect facts via script, and let an LLM write report/status.
- Failsafe and digest jobs can be `no_agent=True` scripts delivered to `origin`.
- Failsafe should print only when today’s report is missing; empty stdout means silent success.
- Digest should extract `## Shrnutí pro Telegram` verbatim and send that.
- For this user, recurring audit/update jobs are not complete until they are also visible in agentsmon's `Automatické běhy` dashboard with an expandable description and Start/Stop control when feasible. Use the `agentsmon-automation-dashboard` skill for the registration/control pattern.

### Avoid brittle collector quoting

When embedding AWK in shell collector functions, protect `$3` from the parent shell. Example:

```bash
run_sh "human users UID>=1000" "awk -F: '\$3 >= 1000 && \$3 < 65534 {print}' /etc/passwd || true"
```

### User-facing answer style

When reporting results to this user, lead with what changed and the current semafor. Keep remediation output short:

- `Opraveno` for completed safe changes.
- `Zůstává k opravě — vyžaduje sudo/root` for privileged blockers.
- Include only essential verification snippets.

## Verification checklist

Before claiming completion:

- Re-run/read the relevant facts after any remediation.
- Verify public listeners changed as intended (`0.0.0.0` → `127.0.0.1` or gone).
- Validate `status.json` parses.
- Run the digest extractor and confirm it prints the expected semafor.
- Confirm cron jobs are scheduled and enabled when scheduling was requested.

## Auto-update sudoers pitfall

When enabling Hermes-managed apt updates with narrowly scoped `NOPASSWD`, do **not** test with broad `sudo -n true`: that should remain denied. Test the exact allowed commands instead:

```bash
sudo -u david_master sudo -n apt-get update
sudo -u david_master sudo -n apt-get -y upgrade
sudo -u david_master sudo -n env DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
```

The auto-update script should likewise probe `sudo -n apt-get update`, not `sudo -n true`, otherwise a correctly least-privilege sudoers file is misdiagnosed as missing sudo.

Known-good limited sudoers shape:

```sudoers
Cmnd_Alias HERMES_APT_UPDATE = /usr/bin/apt-get update
Cmnd_Alias HERMES_APT_UPGRADE = /usr/bin/apt-get -y upgrade
Cmnd_Alias HERMES_APT_UPGRADE_ENV = /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get -y upgrade, /usr/bin/env DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get -y upgrade

david_master ALL=(root) NOPASSWD: HERMES_APT_UPDATE, HERMES_APT_UPGRADE, HERMES_APT_UPGRADE_ENV
```

Validate as root with `visudo -cf /etc/sudoers.d/hermes-auto-update` before testing.

## References

- `references/security-audit-lite-session.md` — details from the session that motivated this skill, including the read-only audit design and dashboard bind fix.

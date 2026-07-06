---
name: linux-system-updates
description: Handle Linux/VPS package updates for the user, including apt checks, sudo limits, reboot-required checks, and update-only remediation.
version: 1.0.0
created_by: agent
metadata:
  hermes:
    tags: [linux, apt, updates, vps, sudo, maintenance]
---

# Linux System Updates

Use this skill when the user asks to perform or verify server/package updates.

## User preference

If the user says backups are already handled, **do not spend the response on backup advice**. Focus only on updates and concise status.

The user prefers practical Czech status with a short semaphore:

```text
🟢 hotovo
🟡 ruční krok potřeba
🔴 chyba/blokace
```

## Update workflow

Check current state first:

```bash
date '+%Y-%m-%d %H:%M:%S %Z'
apt list --upgradable 2>/dev/null | sed -n '1,100p'
```

If passwordless sudo works:

```bash
sudo -n apt-get update
sudo -n env DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
```

Then verify:

```bash
apt list --upgradable 2>/dev/null | sed -n '1,100p'
if [ -e /var/run/reboot-required ]; then cat /var/run/reboot-required; else echo 'reboot není potřeba'; fi
```

If services need restart and it is safe/non-disruptive, restart only the named services and report them.

## If sudo is unavailable

Do not claim updates were applied. Say clearly that this session lacks passwordless sudo and provide the exact manual command:

```bash
sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
```

Then ask the user to run the command or configure limited sudo if they want automatic updates.

## Automation pattern

A no-agent cron watchdog can apply updates when sudo is available and stay silent when nothing is upgradable. If sudo is unavailable and updates exist, it should print a short Telegram instruction instead of failing silently.

State/log path used on this server:

```text
~/.hermes/scripts/security-audit-lite/auto_update.sh
~/.hermes/security-audit-lite/auto-update.log
```

## Reporting format

Keep final concise:

```text
🟢 Aktualizace hotové. Upgradable: 0. Reboot: no.
```

or

```text
🟡 Aktualizace jsem nemohl spustit: sudo vyžaduje heslo. Teď nevidím žádné pending balíky / vidím N balíků. Ruční příkaz: ...
```
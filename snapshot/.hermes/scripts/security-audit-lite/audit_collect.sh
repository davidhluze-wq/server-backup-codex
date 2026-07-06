#!/usr/bin/env bash
set -uo pipefail
BASE="${HOME}/.hermes/security-audit-lite"
DATE="$(date +%F)"
FACTS="$BASE/facts-$DATE.txt"
mkdir -p "$BASE"

run() {
  local title="$1"; shift
  {
    echo
    echo "===== $title ====="
    echo "$ $*"
    timeout 25s "$@" 2>&1 || true
  } >> "$FACTS"
}

run_sh() {
  local title="$1"; shift
  {
    echo
    echo "===== $title ====="
    echo "$ $*"
    timeout 35s bash -lc "$*" 2>&1 || true
  } >> "$FACTS"
}

{
  echo "# Security audit facts"
  echo "generated_at=$(date -Is)"
  echo "host=$(hostname -f 2>/dev/null || hostname)"
  echo "user=$(id)"
  echo "kernel=$(uname -a)"
  echo "base_dir=$BASE"
  echo "facts_file=$FACTS"
  echo
  echo "Accepted risks / DO NOT FLAG AS FIXES:"
  echo "- Agent bypass/dangerous/skip-permissions modes may be intentionally enabled for autonomous operation; do not disable or propose disabling."
  echo "- SSH password authentication may be intentionally accepted; do not flag passwordauthentication=yes as a finding. For SSH only assess root login and brute-force protection."
} > "$FACTS"

run "OS release" bash -lc 'cat /etc/os-release 2>/dev/null || true'
run "Uptime" uptime
run "Reboot required" bash -lc 'test -f /var/run/reboot-required && { echo yes; cat /var/run/reboot-required.pkgs 2>/dev/null; } || echo no'
run_sh "APT upgradable packages" 'apt list --upgradable 2>/dev/null | sed -n "1,120p"'
run_sh "APT simulated upgrade summary" 'apt-get -s upgrade 2>/dev/null | sed -n "1,180p"'
run_sh "Listening ports" 'ss -tulnp 2>/dev/null || netstat -tulnp 2>/dev/null || true'
run_sh "Established connections sample" 'ss -tunp state established 2>/dev/null | sed -n "1,120p" || true'
run_sh "Firewall status" 'if command -v ufw >/dev/null; then ufw status verbose; fi; if command -v nft >/dev/null; then nft list ruleset 2>/dev/null | sed -n "1,160p"; fi; iptables -S 2>/dev/null | sed -n "1,160p" || true'
run_sh "SSH effective config" 'sshd -T 2>/dev/null | egrep "^(permitrootlogin|passwordauthentication|pubkeyauthentication|port|listenaddress|maxauthtries)" || true'
run_sh "SSH failed/invalid attempts last 24h" '(journalctl -u ssh -u sshd --since "24 hours ago" 2>/dev/null || true) | grep -Eci "failed|invalid|authentication failure|disconnecting authenticating" || true'
run_sh "Recent SSH/auth log lines" '(journalctl -u ssh -u sshd --since "24 hours ago" 2>/dev/null || grep -hEi "failed|invalid|authentication failure" /var/log/auth.log* 2>/dev/null || true) | tail -80'
run_sh "fail2ban status" 'systemctl is-active fail2ban 2>/dev/null; fail2ban-client status 2>/dev/null || true'
run_sh "sudo group" 'getent group sudo || true'
run_sh "human users UID>=1000" "awk -F: '\$3 >= 1000 && \$3 < 65534 {print}' /etc/passwd || true"
run_sh "last logins" 'last -10 2>/dev/null || true'
run_sh "current crontab" 'crontab -l 2>/dev/null || true'
run_sh "system cron entries" 'ls -la /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/crontab 2>/dev/null; sed -n "1,160p" /etc/crontab 2>/dev/null || true'
run_sh "running services" 'systemctl list-units --type=service --state=running --no-pager 2>/dev/null | sed -n "1,180p" || true'
run_sh "top cpu/mem processes" 'ps aux --sort=-%cpu | head -25; echo; ps aux --sort=-%mem | head -25'
run_sh "disk usage" 'df -h /; df -ih /'
run_sh "backup hints" 'systemctl list-units --type=service --all --no-pager 2>/dev/null | egrep -i "backup|restic|borg|duplicity|rsync|rclone" || true; ls -ld /backup /backups /var/backups "$HOME/backups" "$HOME/.restic" 2>/dev/null || true'
run_sh "exposed service package versions" 'printf "openssh-server\nnginx\napache2\npostgresql\nmysql-server\nmariadb-server\nredis-server\ndocker.io\ncontainerd\nnodejs\npython3\n" | while read p; do dpkg-query -W -f="${Package} ${Version}\n" "$p" 2>/dev/null; done'
run_sh "Hermes/Codex/Claude process flags sample" 'ps aux | egrep -i "hermes|codex|claude|opencode|antigravity|openclaw" | grep -v egrep | sed -n "1,80p" || true'

# Keep a stable pointer for other scripts.
ln -sfn "$FACTS" "$BASE/facts-latest.txt"
echo "$FACTS"

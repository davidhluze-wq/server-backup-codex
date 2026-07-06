#!/usr/bin/env bash
set -euo pipefail

HOME_DIR="/home/david_master"
BACKUP_DIR="$HOME_DIR/server-agent-env-backup"
LOG_DIR="$HOME_DIR/.local/state/server-agent-env-backup"
BRANCH="server-agent-env-backup-20260706"
REMOTE_URL="git@github.com:davidhluze-wq/server-backup-codex.git"
SSH_KEY="$HOME_DIR/.ssh/server_backup_codex_ed25519"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$LOG_DIR"
exec >>"$LOG_DIR/weekly-backup.log" 2>&1

echo "== $STAMP weekly server agent backup =="

cd "$BACKUP_DIR"

rm -rf snapshot system
mkdir -p \
  snapshot/.config/agent2telegram \
  snapshot/.codex \
  snapshot/.claude/daemon \
  snapshot/.claude/jobs \
  snapshot/.claude/plugins \
  snapshot/.hermes \
  snapshot/repos \
  system

rsync -a "$HOME_DIR/.codex/config.toml" "$HOME_DIR/.codex/rules" "$HOME_DIR/.codex/skills" snapshot/.codex/ \
  --exclude='auth.json' --exclude='*.sqlite*' --exclude='history.jsonl' --exclude='*.log' \
  --exclude='snapshots' --exclude='cache' --exclude='tmp' --exclude='node_modules' --exclude='venv' --exclude='.venv' || true

python3 - <<'PY'
import json
import re
from pathlib import Path

src = Path("/home/david_master/.config/agent2telegram")
dst = Path("/home/david_master/server-agent-env-backup/snapshot/.config/agent2telegram")
dst.mkdir(parents=True, exist_ok=True)
secret_key = re.compile(r"(token|secret|password|api[_-]?key|authorization|credential)", re.I)
telegram_token = re.compile(r"\b\d{7,12}:[A-Za-z0-9_-]{30,}\b")

def scrub(value, key=""):
    if secret_key.search(key):
        return "<REDACTED>"
    if isinstance(value, dict):
        return {k: scrub(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, key) for v in value]
    if isinstance(value, str):
        return telegram_token.sub("[REDACTED_TELEGRAM_TOKEN]", value)
    return value

for path in src.glob("*.json*"):
    target = dst / path.name
    try:
        data = json.loads(path.read_text())
        target.write_text(json.dumps(scrub(data), ensure_ascii=False, indent=2) + "\n")
    except Exception:
        text = path.read_text(errors="ignore")
        text = telegram_token.sub("[REDACTED_TELEGRAM_TOKEN]", text)
        text = re.sub(r'("?(?:token|secret|password|api[_-]?key|authorization|credential)"?\s*[:=]\s*)["\']?[^"\'\n,}]+', r'\1"<REDACTED>"', text, flags=re.I)
        target.write_text(text)

for path in src.glob("*.txt"):
    (dst / path.name).write_text(path.read_text(errors="ignore"))
PY

for f in \
  "$HOME_DIR/.claude/settings.json" \
  "$HOME_DIR/.claude/settings.local.json" \
  "$HOME_DIR/.claude/policy-limits.json" \
  "$HOME_DIR/.claude/remote-settings.json" \
  "$HOME_DIR/.claude/mcp-needs-auth-cache.json" \
  "$HOME_DIR/.claude/daemon/roster.json" \
  "$HOME_DIR/.claude/jobs/pins.json" \
  "$HOME_DIR/.claude/plugins/known_marketplaces.json"; do
  if [ -f "$f" ]; then
    dest="$BACKUP_DIR/snapshot/${f#$HOME_DIR/}"
    mkdir -p "$(dirname "$dest")"
    cp "$f" "$dest"
    perl -0pi -e 's/("(?:token|secret|password|api[_-]?key|authorization|credential|key)"\s*:\s*")[^"]+/$1[REDACTED]/ig; s/[0-9]{7,12}:[A-Za-z0-9_-]{30,}/[REDACTED_TELEGRAM_TOKEN]/g; s/sk-[A-Za-z0-9_-]{20,}/[REDACTED_OPENAI_KEY]/g; s/ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}/[REDACTED_GITHUB_TOKEN]/g' "$dest"
  fi
done

rsync -a \
  "$HOME_DIR/.hermes/config.yaml" \
  "$HOME_DIR/.hermes/channel_directory.json" \
  "$HOME_DIR/.hermes/crews_registry.json" \
  "$HOME_DIR/.hermes/cron" \
  "$HOME_DIR/.hermes/profiles" \
  "$HOME_DIR/.hermes/scripts" \
  "$HOME_DIR/.hermes/skills" \
  "$BACKUP_DIR/snapshot/.hermes/" \
  --exclude='.git' --exclude='.env' --exclude='.env.*' --exclude='auth.json' --exclude='auth.lock' \
  --exclude='google*token*' --exclude='google_client_secret.json' --exclude='*token*' --exclude='*secret*' --exclude='*credential*' \
  --exclude='*.lock' --exclude='*.pid' --exclude='*.sqlite*' --exclude='*.db' --exclude='*.log' \
  --exclude='__pycache__' --exclude='node_modules' --exclude='venv' --exclude='.venv' \
  --exclude='output' --exclude='runs' --exclude='runs/**' --exclude='audio_cache' --exclude='image_cache' --exclude='cache' --exclude='logs' \
  --exclude='sessions' --exclude='state' --exclude='memories' --exclude='sandboxes' \
  --exclude='profiles/*/skills' --exclude='profiles/*/bin' --exclude='profiles/*/state.db*' --exclude='profiles/*/models_dev_cache.json' \
  --exclude='productivity/powerpoint/scripts/office/schemas' || true

python3 - <<'PY'
import json
import subprocess
from pathlib import Path

home = Path("/home/david_master")
backup = home / "server-agent-env-backup" / "snapshot" / ".hermes"
registry = home / ".hermes" / "crews_registry.json"
exclude = [
    "--exclude=.git", "--exclude=.env", "--exclude=.env.*", "--exclude=auth.json", "--exclude=auth.lock",
    "--exclude=google*token*", "--exclude=google_client_secret.json", "--exclude=*token*", "--exclude=*secret*", "--exclude=*credential*",
    "--exclude=*.lock", "--exclude=*.pid", "--exclude=*.sqlite*", "--exclude=*.db", "--exclude=*.log",
    "--exclude=__pycache__", "--exclude=node_modules", "--exclude=venv", "--exclude=.venv",
    "--exclude=cache", "--exclude=logs", "--exclude=sessions", "--exclude=state", "--exclude=memories", "--exclude=sandboxes",
    "--exclude=runs", "--exclude=runs/**", "--exclude=output", "--exclude=output/**",
    "--exclude=facts-*", "--exclude=report-*", "--exclude=failsafe-alert-*", "--exclude=status.json", "--exclude=index.html",
    "--exclude=dedup.json", "--exclude=sent_history.txt", "--exclude=*history.txt", "--exclude=*_last_sent.txt",
]
crews = json.loads(registry.read_text())
if isinstance(crews, dict):
    crews = crews.get("crews", [])
for crew in crews:
    d = crew.get("dir")
    if not d:
        continue
    src = home / ".hermes" / d
    if src.exists():
        subprocess.run(["rsync", "-a", str(src), str(backup), *exclude], check=False)
PY

for repo in "$HOME_DIR/.agent2telegram-src" "$HOME_DIR/.agentsmon-src" "$HOME_DIR/humanagentwiki"; do
  if [ -d "$repo" ]; then
    rsync -a "$repo" "$BACKUP_DIR/snapshot/repos/" \
      --exclude='.git' --exclude='.env' --exclude='.env.*' --exclude='*.sqlite*' --exclude='*.db' \
      --exclude='__pycache__' --exclude='node_modules' --exclude='venv' --exclude='.venv' \
      --exclude='cache' --exclude='attachments' --exclude='*.log'
  fi
done

tmux ls > system/tmux-sessions.txt 2>&1 || true
ps -eo pid,ppid,user,etime,cmd --sort=cmd > system/processes.txt 2>&1 || true
systemctl --user --no-pager --type=service --state=running > system/user-services.txt 2>&1 || true
crontab -l > system/crontab.txt 2>&1 || true
ufw status verbose > system/ufw-status.txt 2>&1 || true

{
  for repo in "$HOME_DIR/.agent2telegram-src" "$HOME_DIR/.agentsmon-src" "$HOME_DIR/humanagentwiki"; do
    if [ -d "$repo/.git" ]; then
      echo "## $repo"
      git -C "$repo" remote -v
      echo
    fi
  done
} > system/git-remotes.txt

{
  for repo in "$HOME_DIR/.agent2telegram-src" "$HOME_DIR/.agentsmon-src" "$HOME_DIR/humanagentwiki"; do
    if [ -d "$repo/.git" ]; then
      echo "## $repo"
      git -C "$repo" status --short --branch
      echo
    fi
  done
} > system/repo-status.txt

find "$BACKUP_DIR" -type f -not -path '*/.git/*' | sed "s#^$BACKUP_DIR/##" | sort > system/file-list.txt

find "$BACKUP_DIR/snapshot/.hermes" -type f -path '*/runs/*' -delete 2>/dev/null || true
find "$BACKUP_DIR/snapshot/.hermes" -type d -empty -delete 2>/dev/null || true

while IFS= read -r file; do
  perl -0pi -e 's/ghp_x{10,}/ghp_[REDACTED_EXAMPLE]/g; s/sk-x{10,}/sk-[REDACTED_EXAMPLE]/g' "$file"
done < <(rg -l --hidden -I -S 'ghp_x{10,}|sk-x{10,}' "$BACKUP_DIR" --glob '!.git/**' || true)

find "$BACKUP_DIR" -type f -not -path '*/.git/*' | sed "s#^$BACKUP_DIR/##" | sort > system/file-list.txt

if rg -n --hidden -S '\b[0-9]{7,12}:[A-Za-z0-9_-]{30,}\b|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|ya29\.[A-Za-z0-9_-]+|AIza[A-Za-z0-9_-]{20,}|BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY' "$BACKUP_DIR" --glob '!.git/**'; then
  echo "Secret scan found a possible live secret. Aborting commit/push."
  exit 10
fi

git checkout "$BRANCH"
git remote set-url origin "$REMOTE_URL"
git add -A
if git diff --cached --quiet; then
  echo "No backup changes to commit."
else
  git commit -m "Weekly sanitized server backup $STAMP"
fi

GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" git push origin "$BRANCH"

echo "Backup completed."

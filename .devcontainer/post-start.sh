#!/usr/bin/env bash
# Runs on EVERY container start (postStartCommand). Idempotent.
# 1. harness -> ~/.claude, ~/.codex, ~/.agents   3. SSH keys from the host
# 2. git trusts the workspace                     4. gh -> git credentials   5. Cloudflare Tunnel
# The harness comes first on purpose: it is what makes the sandbox usable, so nothing that
# depends on the host (SSH files, logins, tunnel token) may abort the script before it.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- 1. harness: regenerate agent config from ./.ai (single source of truth) ----
python3 "$ROOT/.devcontainer/render.py" --home "$HOME" --workspace "$ROOT"

# --- 2. git: the bind-mounted workspace is owned by a different uid than the host --
git config --global --get-all safe.directory 2>/dev/null | grep -qx "$ROOT" \
  || git config --global --add safe.directory "$ROOT"

# --- 3. SSH: host files arrive via a read-only bind mount; copy regular files with sane perms.
# Directories, sockets and symlinks (dangling inside the container) are skipped, and a host
# .ssh that holds only those must not abort the script: every command below tolerates zero files.
if [ -d /run/host-ssh ] && [ -n "$(ls -A /run/host-ssh 2>/dev/null)" ]; then
  rm -rf "$HOME/.ssh" && mkdir -m 700 "$HOME/.ssh"
  find /run/host-ssh -maxdepth 1 -type f -exec cp {} "$HOME/.ssh/" \;
  shopt -s nullglob
  for f in "$HOME"/.ssh/*; do
    grep -Iq . "$f" && sed -i 's/\r$//' "$f"   # Windows line endings break OpenSSH
  done
  shopt -u nullglob
  find "$HOME/.ssh" -maxdepth 1 -type f -exec chmod 600 {} +
  chmod 644 "$HOME"/.ssh/*.pub "$HOME/.ssh/known_hosts" "$HOME/.ssh/config" 2>/dev/null || true
  echo "ssh: $(find "$HOME/.ssh" -maxdepth 1 -type f | wc -l) file(s) copied from host"
else
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  echo "ssh: no host keys found (agent forwarding still works if VS Code provides it)"
fi
grep -qs '^github.com ' "$HOME/.ssh/known_hosts" \
  || ssh-keyscan -t ed25519,rsa github.com >> "$HOME/.ssh/known_hosts" 2>/dev/null || true

# --- 4. GitHub CLI: if logged in (volume or GH_TOKEN), let git push over HTTPS ------
if gh auth status >/dev/null 2>&1; then
  gh auth setup-git >/dev/null 2>&1 || true
  echo "gh: authenticated"
else
  echo "gh: not logged in (run once: gh auth login)"
fi

# --- 5. Cloudflare Tunnel: background service when the host provides a token --------
if [ -n "${TUNNEL_TOKEN:-}" ]; then
  if pgrep -x cloudflared >/dev/null 2>&1; then
    echo "cloudflared: already running"
  else
    setsid nohup cloudflared tunnel --no-autoupdate run </dev/null >/tmp/cloudflared.log 2>&1 &
    echo "cloudflared: tunnel started (log: /tmp/cloudflared.log)"
  fi
else
  echo "cloudflared: CLOUDFLARE_TUNNEL_TOKEN not set on host, tunnel not started"
fi

echo "sandbox ready: $(claude --version 2>/dev/null | head -1) | codex $(codex --version 2>/dev/null | head -1)"
echo "check it: bash .devcontainer/healthcheck.sh"

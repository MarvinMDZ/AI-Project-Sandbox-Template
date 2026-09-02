#!/usr/bin/env bash
# Sandbox health check. Run inside the container:
#     bash .devcontainer/healthcheck.sh
# FAIL = the image or the harness is broken (exit 1). WARN = a login or a host-side
# integration is missing; the sandbox still works. CI runs it after building the image.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0 WARN=0 FAIL=0
pass() { printf '[PASS] %s\n' "$1"; PASS=$((PASS + 1)); }
warn() { printf '[WARN] %s\n' "$1"; WARN=$((WARN + 1)); }
fail() { printf '[FAIL] %s\n' "$1"; FAIL=$((FAIL + 1)); }

echo "## Tools"
for tool in node pnpm python3 uv git gh docker cloudflared claude codex jq rg fd; do
  if command -v "$tool" >/dev/null 2>&1; then
    pass "$tool: $("$tool" --version 2>/dev/null | head -n 1)"
  else
    fail "$tool: missing from the image"
  fi
done

echo "## Isolation"
if [ "${CLAUDE_CONFIG_DIR:-}" = "$HOME/.claude" ]; then
  pass "CLAUDE_CONFIG_DIR=$CLAUDE_CONFIG_DIR"
else
  fail "CLAUDE_CONFIG_DIR should be $HOME/.claude (got '${CLAUDE_CONFIG_DIR:-unset}')"
fi
if [ "${CODEX_HOME:-}" = "$HOME/.codex" ]; then
  pass "CODEX_HOME=$CODEX_HOME"
else
  fail "CODEX_HOME should be $HOME/.codex (got '${CODEX_HOME:-unset}')"
fi
for dir in "$HOME/.claude" "$HOME/.codex" "$HOME/.config/gh" /commandhistory; do
  if mountpoint -q "$dir" 2>/dev/null; then
    pass "$dir is a volume"
  else
    fail "$dir is not a mounted volume: logins and history would die with the container"
  fi
done
if [ -f /etc/claude-code/managed-settings.json ] && [ ! -w /etc/claude-code/managed-settings.json ]; then
  pass "managed-settings.json present and read-only for $(id -un)"
else
  fail "managed-settings.json missing or writable by $(id -un)"
fi
if [ "${DISABLE_UPDATES:-}" = "1" ]; then
  pass "CLI self-update disabled"
else
  fail "DISABLE_UPDATES is not 1: the CLIs could drift from the image pin"
fi

echo "## Harness (.ai/)"
if [ -f /etc/claude-code/CLAUDE.md ] && [ ! -w /etc/claude-code/CLAUDE.md ] \
   && [ -f /etc/codex/AGENTS.md ] && [ ! -w /etc/codex/AGENTS.md ]; then
  pass "global rules baked into the image, read-only"
else
  fail "global rules: /etc/claude-code/CLAUDE.md or /etc/codex/AGENTS.md is missing or writable"
fi
if cmp -s "$ROOT/.ai/RULES.md" /etc/claude-code/CLAUDE.md; then
  pass "image rules match .ai/RULES.md"
else
  warn "image rules differ from .ai/RULES.md: rebuild the container, or with the prebuilt image pin the release that matches .ai/TEMPLATE_VERSION"
fi
if [ -f "$ROOT/.ai/TEMPLATE_VERSION" ]; then
  pass "template version $(tr -d '[:space:]' < "$ROOT/.ai/TEMPLATE_VERSION") (/harness-update moves it)"
else
  warn "template version unknown: .ai/TEMPLATE_VERSION is missing"
fi
# Everything under $HOME is render.py's manifest: one --verify call replaces the old file counting,
# the ~/.codex/AGENTS.md link check and the AGENTS.override.md check.
out=$(python3 "$ROOT/.devcontainer/render.py" --verify --workspace "$ROOT" 2>&1); rc=$?
case "$rc" in
  0) pass "render.py --verify: ${out##*$'\n'}" ;;
  2) warn "harness drift (a session or a hand edit changed a managed file; restart or run render.py):"
     printf '%s\n' "$out" | sed 's/^/       /' ;;
  *) fail "harness broken (render.py --verify exit $rc):"
     printf '%s\n' "$out" | sed 's/^/       /' ;;
esac

echo "## Logins and host integration"
if [ -f "$HOME/.claude/.credentials.json" ] || [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  pass "Claude Code: credentials present"
else
  warn "Claude Code: not logged in (run: claude)"
fi
if [ -f "$HOME/.codex/auth.json" ] || [ -n "${OPENAI_API_KEY:-}" ]; then
  pass "Codex: credentials present"
else
  warn "Codex: not logged in (run: codex login --device-auth)"
fi
if gh auth status >/dev/null 2>&1; then
  pass "gh: authenticated"
else
  warn "gh: not logged in (run: gh auth login, or set GH_TOKEN on the host)"
fi
if ls "$HOME"/.ssh/id_* >/dev/null 2>&1; then
  pass "ssh: keys copied from the host"
elif [ -n "${SSH_AUTH_SOCK:-}" ] && [ -S "$SSH_AUTH_SOCK" ]; then
  pass "ssh: agent forwarded"
else
  warn "ssh: no keys and no agent (is there a ~/.ssh on the host?)"
fi
if docker info >/dev/null 2>&1; then
  pass "docker: host daemon reachable"
else
  warn "docker: host daemon not reachable"
fi
if pgrep -x cloudflared >/dev/null 2>&1; then
  pass "cloudflared: tunnel running"
elif [ -n "${TUNNEL_TOKEN:-}" ]; then
  fail "cloudflared: TUNNEL_TOKEN is set but no tunnel is running (see /tmp/cloudflared.log)"
else
  warn "cloudflared: idle (CLOUDFLARE_TUNNEL_TOKEN not set on the host)"
fi

printf '\n%d passed, %d warnings, %d failed\n' "$PASS" "$WARN" "$FAIL"
[ "$FAIL" -eq 0 ]

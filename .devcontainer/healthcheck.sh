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
count() { local dir="$1"; shift; find "$dir" -mindepth 1 -maxdepth 1 "$@" 2>/dev/null | wc -l; }

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
if python3 "$ROOT/.devcontainer/render.py" --check >/dev/null 2>&1; then
  pass "render.py --check"
else
  fail "render.py --check failed; run it to see why"
fi
if [ -f "$HOME/.claude/CLAUDE.md" ] && [ -f "$HOME/.codex/AGENTS.md" ]; then
  pass "rules rendered into both CLIs"
else
  fail "rules not rendered (did post-start.sh run?)"
fi
want=$(count "$ROOT/.ai/agents" -name '*.md')
got_claude=$(count "$HOME/.claude/agents" -name '*.md')
got_codex=$(count "$HOME/.codex/agents" -name '*.toml')
if [ "$want" -gt 0 ] && [ "$got_claude" -eq "$want" ] && [ "$got_codex" -eq "$want" ]; then
  pass "$want agents rendered for Claude Code and Codex"
else
  fail "agents: .ai/ has $want, ~/.claude/agents has $got_claude, ~/.codex/agents has $got_codex"
fi
want=$(( $(count "$ROOT/.ai/skills" -type d) + $(count "$ROOT/.ai/workflows" -type d) ))
got_claude=$(count "$HOME/.claude/skills" -type d)
got_codex=$(count "$HOME/.agents/skills" -type d)
if [ "$want" -gt 0 ] && [ "$got_claude" -eq "$want" ] && [ "$got_codex" -eq "$want" ]; then
  pass "$want skills/workflows rendered for Claude Code and Codex"
else
  fail "skills: .ai/ has $want, ~/.claude/skills has $got_claude, ~/.agents/skills has $got_codex"
fi

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

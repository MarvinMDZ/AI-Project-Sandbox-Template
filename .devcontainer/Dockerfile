# syntax=docker/dockerfile:1
# Sandbox image: every tool the agents may use is installed and pinned HERE.
# Nothing is inherited from the host. Change a version => edit the arg in devcontainer.json and rebuild.
FROM node:22-bookworm

ARG TZ=Europe/Madrid
ARG CLAUDE_CODE_VERSION=stable
ARG CODEX_VERSION=latest
ARG PNPM_VERSION=10
ARG UV_VERSION=

ENV TZ=${TZ} \
    DEVCONTAINER=true \
    LANG=C.UTF-8

# --- system packages ----------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget gnupg2 git openssh-client sudo \
      build-essential python3 python3-pip python3-venv \
      jq less procps unzip zip ripgrep fd-find fzf man-db \
 && ln -s /usr/bin/fdfind /usr/local/bin/fd \
 && rm -rf /var/lib/apt/lists/*

# --- GitHub CLI (official apt repo) --------------------------------------------
RUN install -d -m 0755 /etc/apt/keyrings \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
 && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*

# --- cloudflared (official apt repo) -------------------------------------------
RUN curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /usr/share/keyrings/cloudflare-main.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main" \
      > /etc/apt/sources.list.d/cloudflared.list \
 && apt-get update && apt-get install -y --no-install-recommends cloudflared \
 && rm -rf /var/lib/apt/lists/*

# --- uv (Python environments and packages) -------------------------------------
RUN curl -LsSf "https://astral.sh/uv/${UV_VERSION:+${UV_VERSION}/}install.sh" \
      | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh \
 && uv --version

# --- pnpm + Codex CLI (root-owned global npm: agents cannot self-update them) ----
RUN npm install -g "pnpm@${PNPM_VERSION}" "@openai/codex@${CODEX_VERSION}" \
 && npm cache clean --force \
 && pnpm --version && codex --version

# --- Claude Code hard policies: highest precedence, nobody can relax them -------
COPY managed-settings.json /etc/claude-code/managed-settings.json

# --- dev conveniences ------------------------------------------------------------
RUN echo "node ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/node && chmod 440 /etc/sudoers.d/node \
 && mkdir -p /commandhistory && touch /commandhistory/.bash_history \
 && chown -R node:node /commandhistory

USER node
ENV HOME=/home/node \
    PATH=/home/node/.local/bin:${PATH} \
    CLAUDE_CONFIG_DIR=/home/node/.claude \
    CODEX_HOME=/home/node/.codex \
    DISABLE_AUTOUPDATER=1

# --- Claude Code: native installer pinned by build arg (version | stable | latest)
RUN curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_CODE_VERSION}" \
 && claude --version

# Mount points must exist, owned by node, before the volumes are attached.
# ~/.claude.json follows CLAUDE_CONFIG_DIR; the symlink is a fallback so it lands in the volume either way.
RUN mkdir -p /home/node/.claude /home/node/.codex /home/node/.config/gh /home/node/.agents \
 && mkdir -p -m 700 /home/node/.ssh \
 && ln -s /home/node/.claude/.claude.json /home/node/.claude.json

RUN cat >> /home/node/.bashrc <<'BASHRC'

# --- sandbox ---
export PROMPT_COMMAND="history -a"
# Host passthrough vars arrive as empty strings when unset on the host: drop them.
for v in ANTHROPIC_API_KEY OPENAI_API_KEY GH_TOKEN TUNNEL_TOKEN; do
  [ -z "${!v:-}" ] && unset "$v"
done
unset v
BASHRC

WORKDIR /workspaces

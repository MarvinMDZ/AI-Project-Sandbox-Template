# Project Sandbox Harness Template

GitHub template for new projects. It gives every project the same **sealed development
environment** (a devcontainer with Claude Code, Codex, GitHub CLI, SSH, Cloudflare Tunnel and
the toolchains) and the same **agent harness** (rules, agents, workflows, skills, schemas,
docs), both versioned in the repository. Nothing leaks in from the host except authentication.

## Quick start

1. **Use this template** on GitHub, clone the new repository, open it in VS Code, *Reopen in
   Container*. The first build takes a few minutes.
2. One-time logins inside the container (they persist in Docker volumes shared by all your
   sandboxes on this machine):
   ```bash
   claude                      # OAuth login, or set ANTHROPIC_API_KEY on the host
   codex login --device-auth   # or set OPENAI_API_KEY on the host
   gh auth login               # or set GH_TOKEN on the host
   ```
3. Fill `AGENTS.md`, `docs/PROJECT.md`, `docs/SETUP.md`. Start work with `/plan <request>`.

## What is inside

```text
.devcontainer/
  devcontainer.json     image build args (tool versions), volumes, host passthrough env
  Dockerfile            Node 22, pnpm, Python 3 + uv, git, gh, cloudflared, Claude Code, Codex
  managed-settings.json Claude Code hard policies (secret files denied), not overridable
  post-start.sh         every start: SSH keys, git trust, harness render, gh, cloudflared
  render.py             .ai/ -> ~/.claude, ~/.codex, ~/.agents (single source of truth)
.ai/
  RULES.md              global rules for both CLIs
  agents/               architect, developer, reviewer, qa, tech-writer
  workflows/            /plan /implement /verify /review /commit /docs-sync
  skills/               reusable know-how (harness maintenance)
  schemas/ templates/   task + handoff schemas, plan / decision / handoff templates
  models.json           logical model profiles -> Claude alias / Codex model + effort
  claude/ codex/        tool-specific settings
docs/                   PROJECT, SETUP, STATUS, DECISIONS, plans/
AGENTS.md  CLAUDE.md    project instructions (Codex native; Claude imports AGENTS.md)
.github/                CI (harness check + devcontainer build), PR and issue templates
```

## How isolation works

| Concern                                                | Mechanism                                                                        | To change it                                                          |
|--------------------------------------------------------|----------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| Tool versions                                          | Pinned by build args in `devcontainer.json`; auto-update disabled                | edit the arg, rebuild                                                 |
| Agent config (rules, agents, skills, settings)         | `.ai/` rendered into the container on every start; managed dirs wiped first | edit `.ai/`, run `python3 .devcontainer/render.py` or restart     |
| Hard policies                                          | `/etc/claude-code/managed-settings.json` baked into the image                    | edit `.devcontainer/managed-settings.json`, rebuild                   |
| Credentials, sessions, history                         | Named volumes `sandbox-claude`, `sandbox-codex`, `sandbox-gh`, `sandbox-history` | `docker volume rm <name>` to forget a login                           |
| Host config (`~/.claude`, `~/.codex`, plugins, skills) | never mounted                                                                    | -                                                                     |
| Project files                                          | Workspace folder bind-mounted at `/workspaces/<repo>`                            | -                                                                     |

Host environment variables passed through when set: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GH_TOKEN`, `CLOUDFLARE_TUNNEL_TOKEN` (arrives as `TUNNEL_TOKEN`). Unset ones are dropped.

## GitHub, SSH, Docker

- **git over HTTPS**: once `gh` is authenticated, `post-start.sh` runs `gh auth setup-git`.
  VS Code also forwards the host git credential helper.
- **git over SSH**: the host `~/.ssh` is bind-mounted read-only and copied into the container
  with correct permissions on every start (keys, `config`, `known_hosts`; CRLF fixed).
  `github.com` is added to `known_hosts`. VS Code SSH agent forwarding works as well.
- **Docker**: `docker` and `docker compose` inside the container drive the host daemon.

## Cloudflare Tunnel

`cloudflared` is installed. If `CLOUDFLARE_TUNNEL_TOKEN` is set on the host (token of a
dashboard-managed tunnel), `post-start.sh` starts `cloudflared tunnel run` in the background
and logs to `/tmp/cloudflared.log`. Map public hostnames to `http://localhost:<port>` in the
Cloudflare dashboard. Without the token nothing runs; start one by hand with
`cloudflared tunnel --url http://localhost:3000` for a throwaway URL.

The token is visible to processes inside the container, including the agents.

## Harness

`.ai/README.md` explains the mapping and how to add agents, workflows and skills. Short
version: one Markdown file per agent, one `SKILL.md` per workflow or skill, and the same file
serves both Claude Code and Codex. `python3 .devcontainer/render.py --check` validates.

## Updating

- Claude Code / Codex / pnpm / uv: `.devcontainer/devcontainer.json` build args, then
  *Rebuild Container*. `stable` and `latest` channels resolve at build time; use an exact
  version for full reproducibility.
- Base image: `node:22-bookworm` in the Dockerfile; pin a digest for byte-identical builds.
- Docker feature `docker-outside-of-docker` is pinned to major `1`.

## Requirements on the host

Docker Desktop (or another Docker engine), VS Code with the Dev Containers extension (or the
`devcontainer` CLI). Windows, macOS and Linux hosts are supported; on Windows the SSH mount
uses `%USERPROFILE%\.ssh`.

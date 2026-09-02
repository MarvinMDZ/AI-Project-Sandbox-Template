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
   bash .devcontainer/healthcheck.sh   # tools, isolation, harness, logins
   ```
3. `/bootstrap` (Codex: `$bootstrap`) fills `AGENTS.md` and `docs/` from the repository, dates
   `DEC-001` and runs the healthcheck. Then start work with `/plan <request>`.

## What is inside

```text
.devcontainer/
  devcontainer.json     image build args (tool versions), volumes, host passthrough env
  Dockerfile            Node 24, pnpm, Python 3 + uv, git, gh, cloudflared, Claude Code, Codex
  managed-settings.json Claude Code hard policies (credential, key and .env reads, sudo), not overridable
  post-start.sh         every start: SSH keys, git trust, harness render, gh, cloudflared
  healthcheck.sh        tools, isolation, harness render, logins; CI runs it after the build
  render.py             .ai/ -> ~/.claude, ~/.codex, ~/.agents (single source of truth)
  project.sh            your tools, run as root at the end of the image build; the rest is the template's
  prebuilt/             second configuration: pull the published image instead of building
.ai/
  RULES.md              global rules for both CLIs, baked into the image (rebuild to change)
  agents/               architect, developer, reviewer, qa, tech-writer
  workflows/            /bootstrap /plan /implement /verify /review /commit /docs-sync /harness-update
  skills/               reusable know-how (harness maintenance)
  schemas/ templates/   task + handoff schemas, plan / decision / handoff templates
  models.json           logical model profiles -> Claude alias / Codex model + effort
  claude/ codex/        tool-specific settings
  state/                current-task.md, checkpoint of an unfinished task (git-ignored)
docs/                   PROJECT, SETUP, STATUS, DECISIONS, plans/
AGENTS.md  CLAUDE.md    project instructions (Codex native; Claude imports AGENTS.md)
.github/                CI (harness check, shell and Python lint, devcontainer build), image publish on release tags, PR and issue templates
```

## How isolation works

| Concern                                                | Mechanism                                                                        | To change it                                                          |
|--------------------------------------------------------|----------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| Tool versions                                          | Pinned by build args in `devcontainer.json`; auto-update disabled                | edit the arg, rebuild                                                 |
| Global rules                                           | `.ai/RULES.md` baked into the image as `/etc/claude-code/CLAUDE.md` and `/etc/codex/AGENTS.md`, root-owned, read-only | propose upstream; `/harness-update`, then rebuild (or pin the release with the prebuilt image) |
| Agent config (agents, skills, settings)                | `.ai/` rendered into the container on every start; managed dirs wiped first | edit `.ai/`, run `python3 .devcontainer/render.py` or restart     |
| Hard policies                                          | `/etc/claude-code/managed-settings.json` baked into the image                    | edit `.devcontainer/managed-settings.json`, rebuild                   |
| Credentials, sessions, history                         | Named volumes `sandbox-claude`, `sandbox-codex`, `sandbox-gh`, `sandbox-history` | `docker volume rm <name>` to forget a login                           |
| Host config (`~/.claude`, `~/.codex`, plugins, skills) | never mounted                                                                    | -                                                                     |
| Project files                                          | Workspace folder bind-mounted at `/workspaces/<repo>`                            | -                                                                     |

Host environment variables passed through when set: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GH_TOKEN`, `CLOUDFLARE_TUNNEL_TOKEN` (arrives as `TUNNEL_TOKEN`). Unset ones are dropped.

The container is a hygiene boundary, not a security boundary: `docker` drives the host daemon
and `sudo` works for you. The managed policy raises the bar for agents without sealing it:

- Claude Code: the `Read` deny rules cover the built-in file tools and the file commands
  Claude Code recognizes in Bash (`cat`, `head`, `tail`, `sed`), not a script that opens the
  file itself. `Bash(sudo:*)` matches `sudo` inside compound commands and behind wrappers such
  as `nohup` or `timeout`; inside an environment runner (`bash -c`, `docker exec`, `npx`) it
  falls through to the normal permission prompt, so it holds only while a human approves.
  `--dangerously-skip-permissions` stays available on purpose (the policy does not set
  `disableBypassPermissionsMode`): unattended runs are what the sandbox is for, and in that
  mode the deny rules are the only guard.
- Codex: the `workspace-write` sandbox limits writes and network, not reads. A Codex agent can
  read any file the `node` user can, including the credential files listed above.

A missing tool goes into `.devcontainer/project.sh` and a rebuild, never a hand install and
never the Dockerfile, which a template update replaces (`.ai/OWNERSHIP` lists what is the
template's and what is yours). Root shell when you need one:
`docker exec -u root -it <container> bash`.

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
serves both Claude Code and Codex. `python3 .devcontainer/render.py --check` validates the sources;
`python3 .devcontainer/render.py --verify` compares the running container with them.

## Sessions

Both CLIs default to medium reasoning effort; `claude-hard` and `codex-hard` start a session at
`xhigh` for architecture, concurrency or hard debugging. Claude auto memory is off: durable
knowledge goes to `docs/`, and an unfinished task leaves a checkpoint in
`.ai/state/current-task.md` (git-ignored) so a fresh session resumes from it instead of a
bloated conversation.

## Updating

- Template release: `/harness-update [vX.Y.Z]` (Codex: `$harness-update`) fetches the release
  from the template repository and restores exactly the paths its `.ai/OWNERSHIP` lists as the
  template's, never yours; review the diff, then *Rebuild Container* when the image inputs
  changed. `healthcheck.sh` prints the release you are on (`.ai/TEMPLATE_VERSION`).
- Global rules: `.ai/RULES.md` is the template's. In a project, propose the change upstream
  and receive it with `/harness-update`; in the template repository, edit and *Rebuild
  Container*. Until the image matches, `healthcheck.sh` warns that the image copy is stale.
- Claude Code / Codex / pnpm / uv: `.devcontainer/devcontainer.json` build args, then
  *Rebuild Container*. `stable` and `latest` channels resolve at build time; use an exact
  version for full reproducibility.
- Base image: `node:24-bookworm` in the Dockerfile; pin a digest for byte-identical builds.
- Docker feature `docker-outside-of-docker` is pinned to major `1`.

## Releasing the template

For maintainers of the template repository: set `.ai/TEMPLATE_VERSION` to the new version,
commit, tag that commit `vX.Y.Z` (annotated) and push the tag. Bump the tag in
`.devcontainer/prebuilt/devcontainer.json` in the same commit; the tag then runs
`publish-image.yml`, which builds, checks and publishes
`ghcr.io/marvinmdz/ai-project-sandbox:vX.Y.Z` (and `latest`) and proves the prebuilt
configuration pulls it. Projects pick it up with `/harness-update`. Files a release removes
stay in projects; name them in the release notes.

## Prebuilt image

`.devcontainer/prebuilt/devcontainer.json` pulls the image the template published for the
release in `.ai/TEMPLATE_VERSION` instead of building it: choose it in *Reopen in Container*.
The package is private until its owner makes it public in the package settings; while private,
run `docker login ghcr.io` on the host with a token that has `read:packages`. A pulled image
does not run `.devcontainer/project.sh`; projects with their own tools keep the build
configuration.

## Requirements on the host

Docker Desktop (or another Docker engine), VS Code with the Dev Containers extension (or the
`devcontainer` CLI). Windows, macOS and Linux hosts are supported; on Windows the SSH mount
uses `%USERPROFILE%\.ssh`. That directory must exist (empty is fine): Docker refuses to start
the container when a bind-mount source is missing.

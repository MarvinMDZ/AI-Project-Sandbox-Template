# Harness

Single source of truth for how Claude Code and Codex behave inside the sandbox.
`.devcontainer/render.py` projects it into both CLIs on **every container start**:

| Source                      | Claude Code                    | Codex                                  |
|-----------------------------|--------------------------------|----------------------------------------|
| `RULES.md` (image build)    | `/etc/claude-code/CLAUDE.md`   | `/etc/codex/AGENTS.md`, linked from `~/.codex/AGENTS.md` |
| `agents/<name>.md`          | `~/.claude/agents/<name>.md`   | `~/.codex/agents/<name>.toml`          |
| `skills/<name>/SKILL.md`    | `~/.claude/skills/<name>/`     | `~/.agents/skills/<name>/`             |
| `workflows/<name>/SKILL.md` | `~/.claude/skills/<name>/`     | `~/.agents/skills/<name>/`             |
| `claude/settings.json`      | `~/.claude/settings.json`      | -                                      |
| `codex/config.toml`         | -                              | `~/.codex/config.toml` (+ trust entry) |
| `models.json`               | agent `model:` -> alias        | agent `model:` -> model / effort       |
| `schemas/`, `templates/`    | referenced by rules and workflows, read from the repo   |

Managed targets are deleted and rewritten. Anything installed by hand inside the container
(a skill, an agent, a setting) disappears on the next start unless it lives here.
Credentials, sessions and history are never touched.

## Vocabulary

- **Managed targets**: the paths under the home directories that the harness owns and rewrites
  on every start (the right-hand column of the table above). Anything else there is session
  state and is never touched.
- **Manifest**: what the harness expects every managed target to contain, derived from `.ai/`
  alone. A render writes it; a verify compares against it.
- **Render**: write the manifest into the managed targets (`render.py`, every container start).
- **Verify**: compare the managed targets with the manifest without changing anything
  (`render.py --verify`, run by `healthcheck.sh`). Verdicts: *verified*; *drift*, a session or a
  hand edit changed something and the next start resets it; *broken*, something is missing or a
  hand-written rules file shadows the image rules.

## Layout

- `RULES.md`: global rules loaded into every session of both CLIs. Baked into the image by the
  Dockerfile, root-owned and read-only inside the container; a change needs *Rebuild Container*.
- `agents/`: specialist roles. One Markdown file per agent: flat `key: value` frontmatter + system prompt.
  - `name`, `description` (one line): required.
  - `model`: profile from `models.json` (`fast` | `standard` | `reasoning` | `inherit`).
  - `tools`: Claude allowlist, comma separated (omit = all tools).
  - `sandbox`: Codex `sandbox_mode` (`read-only` | `workspace-write` | `danger-full-access`).
  - Other keys Claude Code documents (`disallowedTools`, `permissionMode`, `maxTurns`, `skills`,
    `memory`, `effort`, `background`, `isolation`, `color`, `initialPrompt`) pass through to
    Claude only. Any other key is rejected by `render.py`; nested keys (`hooks`, `mcpServers`)
    are not supported by the flat frontmatter.
- `workflows/`: lifecycle playbooks, one per directory. Invoked as `/plan`, `/implement`, ... in Claude Code
  and `$plan`, `$implement`, ... in Codex. Format: [Agent Skills](https://agentskills.io) `SKILL.md`.
- `skills/`: reusable know-how in the same format. Names must not collide with `workflows/`.
- `schemas/`: JSON Schemas for the structured artifacts agents exchange (task, handoff).
- `templates/`: Markdown/JSON templates for plans, decisions and handoffs.
- `claude/`, `codex/`: tool-specific configuration that has no common representation.
- `state/`: git-ignored. `current-task.md` is the checkpoint an agent writes before clearing a
  bloated session (goal, done, remaining, files, decisions, verification) and deletes when done.

## Ownership

`.ai/OWNERSHIP` lists every file the template ships as `template` (replaced wholesale by a
template update; never edit it in a project, propose the change upstream) or `project` (yours
after `/bootstrap`; an update never touches it). Files a project adds next to them, such as
`.ai/skills/<name>/`, `.ai/agents/<name>.md` or `.ai/workflows/<name>/`, are project-owned by
definition, which is why the list names agents, workflows and skills one by one. Where the
project's own additions go:

- Claude Code permissions, hooks, env: the repository-level `.claude/settings.json` (merged by
  Claude Code with the rendered `~/.claude/settings.json`).
- Codex settings and MCP servers: the project's `.codex/config.toml` (`render.py` renders a
  trust entry for the workspace so that layer loads).
- Tools in the image: `.devcontainer/project.sh`, run as root at the end of the image build.
- CI jobs: a second workflow file next to `.github/workflows/ci.yml`.
- Global rules (`RULES.md`) and the hard policy (`managed-settings.json`) have no project
  layer on purpose.

## Change something

1. Edit or add the file here.
2. `python3 .devcontainer/render.py` (or restart the container).
3. Restart the CLI session so it re-reads its config.

`RULES.md` is the exception: it lives in the image, so *Rebuild Container* replaces step 2.

`python3 .devcontainer/render.py --check` renders into a temp dir and verifies it (CI runs it);
`python3 .devcontainer/render.py --verify` compares your running container with `.ai/`
(`healthcheck.sh` runs it).

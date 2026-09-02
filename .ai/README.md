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

## Layout

- `RULES.md`: global rules loaded into every session of both CLIs. Baked into the image by the
  Dockerfile, root-owned and read-only inside the container; a change needs *Rebuild Container*.
- `agents/`: specialist roles. One Markdown file per agent: flat `key: value` frontmatter + system prompt.
  - `name`, `description` (one line): required.
  - `model`: profile from `models.json` (`fast` | `standard` | `reasoning` | `inherit`).
  - `tools`: Claude allowlist, comma separated (omit = all tools).
  - `sandbox`: Codex `sandbox_mode` (`read-only` | `workspace-write` | `danger-full-access`).
  - Any other Claude subagent key (`permissionMode`, `maxTurns`, ...) is passed through to Claude only.
- `workflows/`: lifecycle playbooks, one per directory. Invoked as `/plan`, `/implement`, ... in Claude Code
  and `$plan`, `$implement`, ... in Codex. Format: [Agent Skills](https://agentskills.io) `SKILL.md`.
- `skills/`: reusable know-how in the same format. Names must not collide with `workflows/`.
- `schemas/`: JSON Schemas for the structured artifacts agents exchange (task, handoff).
- `templates/`: Markdown/JSON templates for plans, decisions and handoffs.
- `claude/`, `codex/`: tool-specific configuration that has no common representation.
- `state/`: git-ignored. `current-task.md` is the checkpoint an agent writes before clearing a
  bloated session (goal, done, remaining, files, decisions, verification) and deletes when done.

## Change something

1. Edit or add the file here.
2. `python3 .devcontainer/render.py` (or restart the container).
3. Restart the CLI session so it re-reads its config.

`RULES.md` is the exception: it lives in the image, so *Rebuild Container* replaces step 2.

`python3 .devcontainer/render.py --check` renders into a temp dir and validates (CI runs it).

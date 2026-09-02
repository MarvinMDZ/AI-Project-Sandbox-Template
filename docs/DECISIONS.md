# Decisions

Append-only log. New entries at the bottom, from `.ai/templates/decision.md`.
Supersede instead of editing.

## DEC-001 - Project created from the sandbox template

**Date:** YYYY-MM-DD
**Status:** accepted

### Context

New project; development happens inside the template's devcontainer with the shared harness.

### Decision

Keep the template-owned files listed in `.ai/OWNERSHIP` as provided. Project rules go in
`AGENTS.md`, project tools in `.devcontainer/project.sh`, project agent settings in
`.claude/settings.json` and `.codex/config.toml`, project CI in its own workflow file.

### Consequences

- Agent behavior changes are made in `.ai/`, never by hand inside the container.
- Tool versions are pinned in `.devcontainer/devcontainer.json`.

# Decisions

Append-only log. New entries at the bottom, from `.ai/templates/decision.md`.
Supersede instead of editing.

## DEC-001 - Project created from the sandbox template

**Date:** YYYY-MM-DD
**Status:** accepted

### Context

New project; development happens inside the template's devcontainer with the shared harness.

### Decision

Keep `.devcontainer/` and `.ai/` as provided. Project-specific rules go in `AGENTS.md`.

### Consequences

- Agent behavior changes are made in `.ai/`, never by hand inside the container.
- Tool versions are pinned in `.devcontainer/devcontainer.json`.

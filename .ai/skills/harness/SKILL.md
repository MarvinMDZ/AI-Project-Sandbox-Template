---
name: harness
description: How this project's agent harness works and how to change it - add or remove an agent, skill, workflow or rule, adjust model profiles, re-render into Claude Code and Codex, and validate. Use when asked to modify agents, skills, workflows, rules or sandbox config.
---

# Harness maintenance

`.ai/` is the single source of truth; `.devcontainer/render.py` projects it into
`~/.claude`, `~/.codex` and `~/.agents/skills` on every container start. Read
`.ai/README.md` for the full mapping.

## Add or change

| What            | Where                                   | Format                                              |
|-----------------|-----------------------------------------|-----------------------------------------------------|
| global rule     | `.ai/RULES.md`                      | Markdown, keep it short; loads into every session; baked into the image, rebuild to apply |
| agent           | `.ai/agents/<name>.md`              | flat frontmatter (`name`, `description`, `model`, `tools`, `sandbox`) + system prompt |
| workflow        | `.ai/workflows/<name>/SKILL.md`     | Agent Skills `SKILL.md`; invoked as `/<name>` or `$<name>` |
| skill           | `.ai/skills/<name>/SKILL.md`        | same; may bundle scripts and reference files        |
| model profile   | `.ai/models.json`                   | `fast` / `standard` / `reasoning` / `inherit`       |
| Claude-only     | `.ai/claude/settings.json`          | permissions, hooks, env                             |
| Codex-only      | `.ai/codex/config.toml`             | approval, sandbox, MCP servers                      |
| hard policy     | `.devcontainer/managed-settings.json`   | Claude managed settings; needs image rebuild        |

Remove = delete the file or directory. Nothing else references it.

## Constraints

- Frontmatter is one `key: value` per line; `description` on a single line.
- Agent `name` must be a valid identifier for both tools: lowercase, digits, `-` (`render.py`
  rejects anything else, as it rejects unknown frontmatter keys and duplicate names).
- A skill name must be unique across `skills/` and `workflows/`.
- Tool versions live in `.devcontainer/devcontainer.json` build args; changing them is a rebuild.

## Apply and validate

```bash
python3 .devcontainer/render.py --check   # validate without touching ~/.claude or ~/.codex
python3 .devcontainer/render.py           # apply now (same as a container restart)
python3 .devcontainer/render.py --verify  # compare ~/.claude, ~/.codex, ~/.agents with .ai/: exit 0 verified, 1 broken, 2 drift
python3 -m unittest discover -s .devcontainer -p "test_*.py"   # unit tests for render.py (CI runs them)
```

Then restart the CLI session: both tools read their config at startup.

Rules are the exception: `.ai/RULES.md` is baked into the image, so *Rebuild Container*;
`bash .devcontainer/healthcheck.sh` warns while the image copy is stale.

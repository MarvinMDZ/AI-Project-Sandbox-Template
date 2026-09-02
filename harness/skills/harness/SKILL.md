---
name: harness
description: How this project's agent harness works and how to change it - add or remove an agent, skill, workflow or rule, adjust model profiles, re-render into Claude Code and Codex, and validate. Use when asked to modify agents, skills, workflows, rules or sandbox config.
---

# Harness maintenance

`harness/` is the single source of truth; `.devcontainer/render.py` projects it into
`~/.claude`, `~/.codex` and `~/.agents/skills` on every container start. Read
`harness/README.md` for the full mapping.

## Add or change

| What            | Where                                   | Format                                              |
|-----------------|-----------------------------------------|-----------------------------------------------------|
| global rule     | `harness/RULES.md`                      | Markdown, keep it short; it loads into every session|
| agent           | `harness/agents/<name>.md`              | flat frontmatter (`name`, `description`, `model`, `tools`, `sandbox`) + system prompt |
| workflow        | `harness/workflows/<name>/SKILL.md`     | Agent Skills `SKILL.md`; invoked as `/<name>` or `$<name>` |
| skill           | `harness/skills/<name>/SKILL.md`        | same; may bundle scripts and reference files        |
| model profile   | `harness/models.json`                   | `fast` / `standard` / `reasoning` / `inherit`       |
| Claude-only     | `harness/claude/settings.json`          | permissions, hooks, env                             |
| Codex-only      | `harness/codex/config.toml`             | approval, sandbox, MCP servers                      |
| hard policy     | `.devcontainer/managed-settings.json`   | Claude managed settings; needs image rebuild        |

Remove = delete the file or directory. Nothing else references it.

## Constraints

- Frontmatter is one `key: value` per line; `description` on a single line.
- Agent `name` must be a valid identifier for both tools: lowercase, digits, `-`.
- A skill name must be unique across `skills/` and `workflows/`.
- Tool versions live in `.devcontainer/devcontainer.json` build args; changing them is a rebuild.

## Apply and validate

```bash
python3 .devcontainer/render.py --check   # validate without touching ~/.claude or ~/.codex
python3 .devcontainer/render.py           # apply now (same as a container restart)
```

Then restart the CLI session: both tools read their config at startup.

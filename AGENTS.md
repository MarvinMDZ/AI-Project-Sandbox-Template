# Project instructions

Read before working here. Global rules (`.ai/RULES.md`) are loaded automatically inside
the devcontainer; outside it, read that file first.

## Orientation

- `docs/PROJECT.md`: what this system is. `docs/STATUS.md`: where work stands.
- `docs/DECISIONS.md`: decisions already taken; do not relitigate them silently.
- `docs/plans/`: approved work. Non-trivial changes start with `/plan`.
- `.ai/`: agents, workflows, skills and schemas. Change behavior there, not by hand.

## Commands

<!-- Replace with the real ones once verified; keep in sync with docs/SETUP.md -->

```bash
pnpm install && pnpm test && pnpm lint
uv sync && uv run pytest
```

## Conventions

- Branches: `feature/P###`, tasks `task/P###/T###`. Commits: Conventional Commits.
- JavaScript/TypeScript: `pnpm`. Python: `uv`. Respect the repository's formatter and linter.
- Secrets only via environment or `.env` (ignored); `.env.example` documents the names.

## Project-specific rules

<!-- Supported versions, forbidden dependencies, architecture constraints, data handling. -->

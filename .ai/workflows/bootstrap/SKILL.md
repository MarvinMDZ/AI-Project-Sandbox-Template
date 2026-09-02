---
name: bootstrap
description: First run in a project created from the sandbox template - replace the template placeholders in AGENTS.md and docs/ with verified facts about this repository (purpose, stack, commands), date DEC-001, run the healthcheck, and stop before committing. Use once, right after the first container start.
---

# Bootstrap

Input: nothing. Output: `AGENTS.md`, `docs/PROJECT.md`, `docs/SETUP.md`, `docs/DECISIONS.md`
and `docs/STATUS.md` without template placeholders, plus a healthcheck report.

1. **Check it applies**: `grep -n 'YYYY-MM-DD' docs/DECISIONS.md`. No match means the project
   was bootstrapped already: report that and stop.
2. **Read the repository, not the docs**: `git remote get-url origin`, the root listing, and
   the manifests that exist (`package.json` scripts and `packageManager`, `pyproject.toml`,
   `uv.lock`, `pnpm-lock.yaml`, `Cargo.toml`, `go.mod`, `Dockerfile`, `compose.yaml`, `src/`,
   `tests/`). A fresh repository may have none of them: that is a finding, not a reason to
   invent a stack.
3. **Ask** at most three questions, only what the repository cannot answer: the purpose (one
   paragraph, for whom), the stack when no manifest exists, and the external systems (credential
   names only, never values). Everything else becomes a stated assumption.
4. **Verify the commands**: run every install, run and validate command you intend to document
   (`pnpm install`, `pnpm test`, `uv sync`, `uv run pytest`, ...). A command is documented only
   if it exited 0 in this session; the rest is listed as "not yet" with one line on what is
   missing. Never write the template's sample commands as if they were verified.
5. **Delegate the writing** to the `tech-writer` agent with the verified facts, the answers and
   the command results. It replaces the placeholders in place and keeps every heading:
   - `AGENTS.md`: the `## Commands` block (drop the HTML comment) and `## Project-specific rules`;
   - `docs/PROJECT.md`: purpose, scope, tech stack, repository layout, external systems, constraints;
   - `docs/SETUP.md`: requirements, install, run, validate, verified commands only;
   - `docs/DECISIONS.md`: `DEC-001` dated today (`date +%F`), nothing else changed;
   - `docs/STATUS.md`: drop the `/bootstrap` line under `## Next`; keep "First plan".
6. **Healthcheck**: `bash .devcontainer/healthcheck.sh`. Quote its summary line and every
   `[FAIL]` or `[WARN]` the user must act on.
7. **Report** the files changed, the assumptions made and the healthcheck result. Do not
   commit; offer `/commit`. The next step is `/plan <request>`.

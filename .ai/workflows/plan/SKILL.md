---
name: plan
description: Turn a feature request or problem statement into an approved implementation plan in docs/plans/. Clarifies scope, writes acceptance criteria, splits work into phases and tasks with validation, and stops for approval. Use before any non-trivial implementation.
---

# Plan

Input: the user's request. Output: `docs/plans/P###-<slug>.md` awaiting approval.

1. **Read first**: `docs/PROJECT.md`, `docs/STATUS.md`, `docs/DECISIONS.md`, and the code
   the request touches. Do not plan from file names.
2. **Clarify**: ask at most five questions, only those that change scope, behavior, risk or
   acceptance. Otherwise write the assumption into the plan and continue.
3. **Escalate** to the `architect` agent when the request changes system boundaries, data
   contracts, security-sensitive paths, public APIs, or needs a non-trivial migration.
   Record its recommendation as a decision in the plan.
4. **Write the plan** from `.ai/templates/plan.md`. Next id = highest `P###` in
   `docs/plans/` + 1. Every task has: objective, files, acceptance criteria, validation
   command, risk. Tasks are small enough for one `developer` run each.
5. **Stop.** Present the plan summary and ask for approval. Do not implement.

On approval: set plan status to `approved`, add it to `docs/STATUS.md`, and create the
branch `feature/P###` only if the user asks for it.

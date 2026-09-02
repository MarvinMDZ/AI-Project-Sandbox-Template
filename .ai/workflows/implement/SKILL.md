---
name: implement
description: Execute the next task of an approved plan end to end - delegate to the developer agent with a minimal context pack, run validation, review when risk requires it, and record the handoff. Use to make progress on docs/plans/P###.
---

# Implement

Input: a plan id (`P###`) and optionally a task id. Default: the first task not done.

1. **Build the task** as `.ai/schemas/task.schema.json` from the plan: objective,
   acceptance criteria, files, validation, risk, context (relevant `DEC-###`, docs).
2. **Delegate** to the `developer` agent with that task only. Do not forward the whole
   conversation or repository.
3. **Validate**: run the task's validation commands (or delegate to `qa`). A failed check
   returns the task to `developer` with the decisive error, at most twice; then stop and report.
4. **Review** with the `reviewer` agent when task risk is `medium` or `high`, or the diff
   touches security, data, or public interfaces. Blocking findings go back to `developer`.
5. **Record**: tick the task in the plan; if the handoff says `documentation_impact:
   update_required`, run `docs-sync`. Any `decisions` become `DEC-###` entries.
6. **Report** the handoff to the user: status, files changed, validation executed and
   result, what is next. Do not commit unless the user asked; offer `/commit`.

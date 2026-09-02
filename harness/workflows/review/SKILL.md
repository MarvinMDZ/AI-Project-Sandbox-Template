---
name: review
description: Independent, risk-based review of the current diff, a branch or a pull request using the reviewer agent. Reports findings by severity and whether they block. Use before committing, merging or when asked to review code.
---

# Review

1. Determine the target: `git diff` (unstaged + staged) by default; a branch (`git diff
   main...HEAD`) or a PR (`gh pr diff <n>`) when given.
2. Collect context: the plan or task the change belongs to, relevant `DEC-###` entries.
3. Delegate to the `reviewer` agent with the diff target and that context. Read-only.
4. Present the findings unchanged, most severe first, then **Blocking:** yes | no.
5. Only if the user asks: fix the findings (via `developer` or directly), then re-run
   `verify` and re-review the changed hunks.

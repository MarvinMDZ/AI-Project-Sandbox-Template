---
name: verify
description: Prove that the current working tree meets its acceptance conditions without changing code - run the relevant tests, linters, type checks and builds, and report evidence. Use before claiming anything is done, fixed or passing.
---

# Verify

1. Determine what applies: the task's `validation` list, else the commands in `docs/SETUP.md`,
   else the repository's own scripts (`package.json`, `pyproject.toml`, `Makefile`).
2. Run them (directly, or via the `qa` agent for long suites). Never modify code or tests to
   make them pass.
3. Report, in this order:
   - commands executed with pass/fail;
   - failing checks with the shortest decisive excerpt;
   - checks not run and why;
   - acceptance criteria abandoned, each with its reason;
   - **Verified:** yes | partially | no.

A claim without a command behind it is not a verification.

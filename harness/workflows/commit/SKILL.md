---
name: commit
description: Guarded commit of validated work - checks branch, scope and secrets, writes a Conventional Commits message, commits. Never pushes, never force-pushes. Use only when the user asks to commit.
---

# Commit

Preconditions, all verified with commands, else stop and report:

1. Not on `main`/`master` unless the user explicitly asked for that.
2. Validation for the work has passed in this session (`verify`), or the user waived it.
3. `git status --porcelain`: every changed file is inside the task scope; anything else is
   listed and left unstaged unless the user includes it.
4. No secret-like files or content staged: `.env*`, `*.pem`, `*.key`, `id_*`,
   `credentials*`, tokens in diffs (`git diff --cached | grep -iE 'api[_-]?key|secret|token'`).

Then:

5. Stage the in-scope files explicitly (`git add <paths>`, never `git add -A`).
6. Message: Conventional Commits (`feat|fix|docs|refactor|test|chore(scope): summary`),
   imperative, body explains why, references `P###-T###` when applicable. Follow the
   repository's own convention if `git log` shows one.
7. `git commit`. Report the hash and the files. Do not push.

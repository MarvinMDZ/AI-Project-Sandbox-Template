---
name: harness-update
description: Bring the template-owned files of this project (.devcontainer, .ai, CI, editor config) to a release of the sandbox template - fetch the tag, restore exactly the paths that release lists as the template's in .ai/OWNERSHIP, run the harness checks, review the diff, commit. Never merges histories, never touches project-owned files. Use when the template published a new release.
---

# Harness update

Input: a template tag (`vX.Y.Z`); default: the newest one. Output: one commit that moves the
template-owned paths, `.ai/TEMPLATE_VERSION` included, to that release.

1. **Preconditions**: `git status --short` prints nothing, else stop. The `template` remote
   exists (`git remote get-url template`); if not, add it from the `source` line of
   `.ai/OWNERSHIP`: `git remote add template <url>`. The template repository is private:
   `gh auth setup-git` (run by `post-start.sh` once `gh` is logged in) supplies the credentials.
2. **Fetch and pick**: `git fetch template --tags`. Tag = the input, else
   `git tag --list 'v*' --sort=-v:refname | head -n 1`. If it equals
   `v$(tr -d '[:space:]' < .ai/TEMPLATE_VERSION)`, report "already at <tag>" and stop.
3. **Read the list from the release, not from this checkout**, because the release may ship
   files this project does not have yet:
   `git show <tag>:.ai/OWNERSHIP | awk '$1 == "template" { print $2 }'`.
4. **Restore those paths, by name**:
   `git restore --source=<tag> --staged --worktree -- <every path from step 3>`.
   Never restore `.ai` or `.devcontainer` as a directory: a directory restore deletes every
   file the project added there.
5. **Check**: `python3 .devcontainer/render.py --check` and
   `python3 -m unittest discover -s .devcontainer -p "test_*.py"`. A failure means this project
   and the release disagree: report the decisive line, undo with
   `git restore --source=HEAD --staged --worktree -- <the same paths>`, and stop.
6. **Review**: `git diff --cached --stat`. Every line is a template-owned path. A path the
   project had edited locally shows up as a revert: list those for the user; the template does
   not take local edits to its files, the change belongs upstream.
7. **Commit** `chore(harness): update template-owned files to <tag>` (the user asked for the
   update by invoking this workflow; nothing is pushed). Report the files changed, the reverts,
   and whether a *Rebuild Container* is due: it is when `Dockerfile`, `devcontainer.json`,
   `managed-settings.json` or `RULES.md` changed (`healthcheck.sh` warns about stale rules
   until then).

Files a release deleted stay in the project; the release notes list them.

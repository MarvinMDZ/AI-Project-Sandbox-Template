---
name: docs-sync
description: Bring docs/ in line with verified state after a completed task, phase or decision - STATUS, DECISIONS, SETUP, PROJECT and the plan file - via the tech-writer agent. Use when a handoff reports documentation_impact update_required.
---

# Docs sync

1. Gather only verified inputs: the completed handoff(s), the approved plan, decisions the
   user stated. Nothing in progress.
2. Delegate to the `tech-writer` agent with those inputs and the list of docs to touch.
3. Review its diff: verified state only, no secrets, STATUS still short, DECISIONS only
   appended.
4. Report the files changed.

Do nothing when every handoff says `documentation_impact: none`.

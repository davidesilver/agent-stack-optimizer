---
name: handoff
description: Save task state and the next action for a fresh session.
---
<!-- agent-stack-managed-v1 -->

# Handoff

Save a short Markdown file under `docs/handoff/` in a code repository, or `handoffs/` in a notes workspace.
Use the date and a task slug; do not overwrite an existing file.
Include objective, current state, failed approaches and reasons, decisions, changed files,
verification performed, unresolved limits, and one concrete next action.
Link existing specifications and diffs instead of repeating them. Exclude secrets and private data.
For automatic threshold requests, reconstruct the state without asking questions; label uncertainty.
Return the file path and a prompt for a fresh chat to read it and continue.
Never start another chat or run an agent automatically.

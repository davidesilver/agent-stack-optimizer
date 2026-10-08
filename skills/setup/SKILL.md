---
name: setup
description: Configure context thresholds and optimization modules for Claude Code and Codex.
---
<!-- agent-stack-managed-v1 -->

# Setup

Run `python3 "{{ROOT}}/stack.py" audit` first (Windows: `python`).
Ask which agents and modules to enable and the warning/max context thresholds.
The maximum is a handoff threshold, not an extension of the model window or a hard token cap.
Choose percent or tokens, and warning-only or handoff at the end of a turn.
Use `python3 "{{ROOT}}/stack.py" setup --help` for available flags.
Preview the agreed choices with `--dry-run`, then apply the user's authorized choices.
Preserve existing custom settings and skills. Never change the model or effort.
Run `check` afterwards. Registration is not proof of hooks executing in the client.
Report the backup ID and `rollback ID` command. Do not enable optional integrations without a demonstrated need.

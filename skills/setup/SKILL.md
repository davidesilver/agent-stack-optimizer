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
If the audit shows `markitdown` not installed and the module `pdf` or `markitdown` is enabled, offer `uv tool install "markitdown[pdf,docx,pptx,xlsx]"` (or `pipx install` with the same extras). Run it only after a yes; without it Office files fall back to the native Read.
Optional, only if the user asks and the audit shows Claude Code 2.1.287+: Claude Code mods (see README "Optional Claude Code mods"). Third-party code that runs with the user's permissions, so: clone into a new empty directory, read the code, run `claude plugin validate <dir>`, copy `~/.claude/settings.json` to a timestamped backup, show the exact `env.CLAUDE_CODE_PLUGIN_DIRS` change and apply it only after a yes. Suggest cache-tax with `/cache-tax guard warn`, never `keepwarm` (pings cost tokens). Mods are not covered by `rollback`: report the settings backup path instead.
Report the backup ID and `rollback ID` command. Do not enable optional integrations without a demonstrated need.

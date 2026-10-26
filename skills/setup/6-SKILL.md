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
Ask how long sessions should be handled. Default `handoff`: warn at the first threshold and save a handoff at the second, so the user starts a new chat. Say at which context level this happens and let the user change it. Alternative `--strategy jev-plugin` (Claude Code only, optional, off by default): the third-party fast-jev-compaction plugin compacts by dropping stale tool calls and results. Before offering it, state plainly: conversation text is sent to api.typesafe.ai on every compaction, it needs the user's own paid TypeSafe key, savings are unmeasured claims (prompt-cache effects), it runs outside `rollback`, and it triggers at 60% context. Only if the user says yes, pass `--accept-external-data`; never infer consent from other answers. The choice is recorded as `pending`: setup installs nothing, never reads or stores a key, and the handoff guard keeps working unchanged (Codex too, which the plugin does not support). Only after the user installed the plugin and confirmed it runs, apply `--strategy jev-plugin --plugin-active`: the Claude guard then only warns so it does not pre-empt compaction. Switching back with `--strategy handoff` restores the guard and clears consent.
Guided plugin install is untested end to end. After a separate yes: clone https://github.com/tamaratran/fast-jev-compaction into a new empty directory, read `hooks/fast-jev.ts` and `src/request.ts`, run `claude plugin validate`, back up `~/.claude/settings.json`, and enable function hooks only after a yes. The user sets `TYPESAFE_API_KEY` themselves with a secure local method such as their shell profile or OS secret store; never ask for the key in chat or write it into a file this tool manages. Test first on a synthetic session. Report the settings backup path.
Preview the agreed choices with `--dry-run`, then apply the user's authorized choices.
Preserve existing custom settings and skills. Never change the model or effort.
Run `check` afterwards. Registration is not proof of hooks executing in the client.
If the audit shows `markitdown` not installed and the module `pdf` or `markitdown` is enabled, offer `uv tool install "markitdown[pdf,docx,pptx,xlsx]"` (or `pipx install` with the same extras). Run it only after a yes; without it Office files fall back to the native Read.
Optional, only if the user asks and the audit shows Claude Code 2.1.287+: Claude Code mods (see README "Optional Claude Code mods"). Third-party code that runs with the user's permissions, so: clone into a new empty directory, read the code, run `claude plugin validate <dir>`, copy `~/.claude/settings.json` to a timestamped backup, show the exact `env.CLAUDE_CODE_PLUGIN_DIRS` change and apply it only after a yes. Suggest cache-tax with `/cache-tax guard warn`, never `keepwarm` (pings cost tokens). Mods are not covered by `rollback`: report the settings backup path instead.
Report the backup ID and `rollback ID` command. Do not enable optional integrations without a demonstrated need.

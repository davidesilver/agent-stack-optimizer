# Agent Stack Optimizer

[![Tests](https://github.com/davidesilver/agent-stack-optimizer/actions/workflows/tests.yml/badge.svg)](https://github.com/davidesilver/agent-stack-optimizer/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

**Reduce token usage in Claude Code and Codex with a small, reversible, dependency-free setup:** context-threshold handoff guard, PDF/Word/Excel-to-text Read hook (with [markitdown](https://github.com/microsoft/markitdown)), statusline, audit, usage reports and one-command rollback. No automatic model switching and no blanket installation of skills or MCP servers.

## What it does

- **Handoff guard:** warns at a context threshold you choose, optionally saves a handoff at the end of a turn, so you start a fresh session instead of paying for a bloated one.
- **Read hook:** PDFs and Office files (`.docx .pptx .xlsx .xls .epub`) are read as extracted text instead of binary or page images. Scans and failures fall back to the original file.
- **Audit and reports:** see what is configured and measure real input/cache/output tokens per session, for Claude and Codex.
- **Reversible:** every change is backed up with hashes; `rollback` restores the previous state.

## How it compares

| Tool | Focus | Relation to this project |
|---|---|---|
| [RTK](https://github.com/rtk-ai/rtk) | Filters command output before the agent reads it | Optional filter via `stack.py run --filter rtk` |
| [ccusage](https://github.com/ccusage/ccusage) | Reads Claude Code logs to show usage and cost | Complementary; `stack.py report` also covers Codex |
| [context-mode](https://github.com/mksglu/context-mode) | Retrieves relevant parts of large outputs | Optional, not bundled |
| This project | Thresholds, handoff, input conversion, audit, rollback | Setup layer that keeps your existing config |


## Requirements

Python 3.10+; an existing Claude Code and/or Codex installation. PDF extraction needs `pypdf`, `markitdown` or `pdftotext`; Word/PowerPoint/Excel/EPUB conversion and the `markitdown` module need [Microsoft markitdown](https://github.com/microsoft/markitdown) (`uv tool install "markitdown[pdf,docx,pptx,xlsx,xls,outlook]"`). Core has no third-party Python dependencies. macOS tested locally; Linux and Windows CI are configured, with live client behavior still requiring verification on each platform.

## Quick start

```sh
git clone https://github.com/davidesilver/agent-stack-optimizer.git
cd agent-stack-optimizer
python3 stack.py audit
python3 stack.py setup --interactive --dry-run
python3 stack.py setup --interactive
python3 stack.py check
```

On Windows use `python`. Keep the checkout in a stable location: hooks point to its scripts. After installation `/setup` invokes the setup skill in clients that expose skill slash commands. If a client does not expose it, run the CLI directly. Existing custom `setup` or `handoff` skills are retained.

Choose exactly the same flags for preview and application when using the noninteractive CLI:

```sh
python3 stack.py setup --agents claude,codex --modules handoff,pdf,statusline,setup,markitdown --warn 50 --max 60 --dry-run
python3 stack.py setup --agents claude,codex --modules handoff,pdf,statusline,setup,markitdown --warn 50 --max 60
python3 stack.py setup --unit tokens --warn 60000 --max 80000 --mode warn
```

`--mode handoff` saves state at the end of a turn. `--mode warn` only warns. The maximum is an operational threshold: it cannot enlarge the model context window, stop a turn at an exact token, or prevent native auto-compaction. Thresholds may be exceeded during a turn. An absolute threshold can be used without knowing the model window.

Claude window detection uses the client's statusline data; Codex uses session telemetry. If no window is available, percentage thresholds emit a one-time notice and do not trigger a handoff. `--window-tokens NUMBER` declares a window manually; `--window-tokens 0` restores detection. Legacy `AI_HANDOFF_WARN`, `AI_HANDOFF_FORCE` (fractions) and `AI_CTX_WINDOW` override saved policy when present. The tool does not change the client/model context settings.

## Modules

| Module | Behavior |
|---|---|
| `handoff` | Warning + optional end-of-turn handoff guard; reusable skill |
| `pdf` | Claude Read hook: PDF to text (pypdf, then markitdown, then pdftotext); `.docx .pptx .xlsx .xls .epub` to Markdown via markitdown. Scans, missing tools and failures use the original file |
| `markitdown` | Skill for explicit conversion of any markitdown-supported format (HTML, CSV/JSON/XML, ZIP, images, audio, YouTube) with the `markitdown` CLI |
| `statusline` | Claude terminal context display and window telemetry |
| `rules` | Short workflow rules in a delimited block; other text retained |
| `setup` | Guided setup skill backed by this CLI |

Omitting a module removes its managed hooks/statusline for selected agents. Installed skill/rule files are retained; rollback is the way to restore a prior installation. Other agents and third-party hooks are retained. Identical legacy Codex handoff duplicates migrate to `.agents/skills`, with reversible removal of the duplicate Markdown file.

The PDF hook provides a visual escape: `touch ~/.claude/pdf-visual-once`, then read the original PDF. On Windows create that empty file with PowerShell `New-Item`. Text extraction deliberately excludes images and layout. Never use it as the only source when those are relevant.

## Backups and rollback

```sh
python3 stack.py backups
python3 stack.py rollback BACKUP_ID --dry-run
python3 stack.py rollback BACKUP_ID
```

Each changed file has an original snapshot and before/after hashes under `~/.config/ai-config/backups/`. IDs are unique. New files are deleted on rollback; existing files are restored. If any target changed after installation, rollback refuses before restoring any file. Interrupted installs retain a recovery manifest. Rollback leaves empty directories and its own backup history in place. Symlink destinations are refused; review your layout instead of overwriting a symlink-managed configuration.

Snapshots may contain local credentials copied from settings: backup files use private permissions and must never be committed. No settings values or transcript content are exported by audit/report.

## Optional output filtering

RTK is an optional external executable, not installed or globally enabled by setup. Install a reviewed release from [rtk-ai/rtk](https://github.com/rtk-ai/rtk) if you want to test it.

```sh
python3 stack.py run --filter rtk -- python3 -m unittest discover -s tests
python3 stack.py run --filter raw -- git status
```

The original command runs once, without a shell. Full combined stdout/stderr is saved locally. Successful output can be deduplicated by `rtk log`; failed commands always show full diagnostics. If RTK is unavailable or fails, full output is shown. Exit codes are retained. A local metadata record contains duration, exit code and original/displayed bytes, not command arguments. Byte reduction is not a token or cost measurement. Output files may contain private data; delete old local files when no longer needed.

## Reports

```sh
python3 stack.py report --days 7 --save /tmp/before.json
python3 stack.py report --days 7 --compare /tmp/before.json
```

Reports show anonymized session keys and input/cache/output counters separately per agent, plus durations/exit codes for commands run through this tool. Codex input includes cached input; Claude reports it separately. Codex cumulative snapshots are not summed, and Claude repeated message IDs use the latest usage record. Session totals are not the current context size. Billing, correctness and task completion are not inferred from token counts or successful process exits. Compare matched tasks and periods before claiming savings.

## Optional Claude Code mods

Mods (Claude Code 2.1.287+) are separate plugins and are **not** bundled or installed by this project. Read a mod's code before enabling it: mods run with your permissions. Judged by whether they reduce token cost:

| Mod | Effect | Verdict |
|---|---|---|
| [cache-tax](https://github.com/karanb192/cache-tax) | Warns before, or drops once, a message sent to a cold prompt cache and shows the rewrite cost | Useful. Use `/cache-tax guard warn`; its `keepwarm` pings cost tokens |
| [blast-radius](https://github.com/anthropics/claude-code-playground/tree/main/claude-code/mods/blast-radius) | Holds `rm -rf`, `git reset --hard`, force push and migrations and shows what they would touch | Safety, no token savings |
| [filetree](https://github.com/data-goblin/claude-code-filetree) and Savvy Progress | Show files touched, progress and subagent cost | Visibility only, no savings |

Load a local mod with `claude --plugin-dir <path>`, or persistently through `env.CLAUDE_CODE_PLUGIN_DIRS` in `settings.json` (path-separated list).

## Optional indexing

Use your existing graph/index tooling first. [context-mode](https://github.com/mksglu/context-mode) can retrieve relevant portions of large outputs; it has its own ELv2 license and is not bundled. [code-review-graph](https://pypi.org/project/code-review-graph/) is another candidate for code indexing; verify the source and overlap before integrating. These tools are not installed by the core setup.

## Compatibility and verification

`check` validates registered commands, skills and extraction dependencies. It cannot prove a hook is approved or actually executes. Review Codex `/hooks` in the installed client and start a fresh session. Claude custom statuslines are retained; if they do not supply window telemetry, choose token thresholds or declare a window. Hook schemas vary between client versions; the adapters follow the local setup used during development and must be smoke-tested on your clients.

Tests use isolated homes and synthetic logs:

```sh
python3 -m unittest discover -s tests -v
```

## FAQ

**How do I reduce Claude Code token usage?** Keep sessions short (one task each), hand off at a threshold instead of compacting, read documents as text rather than images, and measure before and after. This tool automates those steps and does not claim savings you have not measured.

**Does it work with Codex?** Yes for the handoff guard, skills and reports. The Read hook and statusline are Claude Code only. Codex requires you to approve hooks with `/hooks`.

**Can I undo it?** Yes: `python3 stack.py backups`, then `rollback BACKUP_ID`. Interrupted installs keep a recovery manifest.

**Will it change my model or settings?** No. Model, effort, MCP servers, custom skills and third-party hooks are retained.

**Does it convert Word and Excel files?** Yes, through Microsoft markitdown when it is installed: `uv tool install "markitdown[pdf,docx,pptx,xlsx,xls,outlook]"`.

## Sources

Inspired by modular bootstrap in [claude-reimagined](https://github.com/kunaltulsidasani/claude-reimagined), context-budget workflows in [ECC](https://github.com/affaan-m/ECC), output filtering in RTK, and retrieval in context-mode. Their source code is not bundled. The PDF/statusline scripts adapt the author's existing personal setup; see [NOTICE](NOTICE).

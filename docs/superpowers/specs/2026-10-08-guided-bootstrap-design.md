# Guided bootstrap and Gemini CLI adapter

Status: proposed for user review. This spec follows the user's selection of the guided CLI approach and the recommended third target, Gemini CLI.

## Goal

Make first-time setup a single guided CLI flow that detects installed agents, checks requirements before changing files, gathers choices once, previews the full change set, and applies it through the existing reversible transaction system. Add a Gemini CLI adapter with an explicit feature boundary based on its different hook lifecycle.

## Existing behavior

`stack.py setup --interactive` asks a sequence of questions and immediately applies the configuration. Preview currently requires a separate `--dry-run` invocation with the same flags. Agent selection defaults to Claude and Codex without detecting which clients are installed. The installer embeds this checkout's absolute path in hook commands, so moving the checkout can break installed hooks. Transactions already create per-file backups and support conflict-aware rollback.

## Proposed flow

Add a guided setup path that can be started from the existing checkout with one command. It will:

1. Require Python 3.10 or newer and verify that the checkout's managed scripts are present.
2. Detect Claude Code, Codex, and Gemini CLI from executable paths and show detected versions. Detection is advisory; users may select any detected target, and the installer will not claim support for a target that is absent.
3. Offer only modules supported by each selected target. Show target-specific limitations before selection.
4. Collect module and context policy choices in one pass, reusing saved values as defaults.
5. Preflight all selected destinations, JSON configuration, symlinks, and module dependencies before mutation. If PDF extraction is selected without `pypdf` or `pdftotext`, explain the missing requirement and let the user remove that module or exit. Do not install dependencies automatically.
6. Show one consolidated preview of selected agents, modules, affected paths, detected limitations, and backup behavior. A single confirmation applies the transaction; declining exits without writes.
7. Finish with a check summary and the backup identifier. Existing `--dry-run`, explicit flags, and rollback commands remain available for scripted use.

The guided flow must not ask the user to repeat the questionnaire for preview and application. Noninteractive invocations remain explicit and deterministic.

## Agent capabilities

The adapter model declares capabilities per agent and per module. Shared configuration must not imply feature parity.

- **Claude Code:** retain current supported modules and behavior.
- **Codex:** retain current supported modules and behavior.
- **Gemini CLI, initial scope:** install compatible user-level skills and rules, and a nonblocking context warning only after the live adapter test verifies its hook contract. Do not offer PDF conversion or statusline integration.
- **Gemini context handoff:** do not claim support in the initial adapter. Gemini's `AfterAgent` can reject a response and trigger a retry, while `SessionEnd` is best-effort and ignores flow-control fields. Neither is currently a verified equivalent of the existing end-of-turn `Stop` guard. Mark handoff as unsupported until a separate design and live test establish safe semantics.

Gemini skills use `~/.gemini/skills/` or the shared `~/.agents/skills/` location, and its user context file is `~/.gemini/GEMINI.md`. The adapter must preserve unrelated settings and text, detect custom files, and use the existing backup/rollback transaction. Official references: [hook lifecycle](https://github.com/google-gemini/gemini-cli/blob/main/docs/hooks/reference.md), [skills](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/using-agent-skills.md), and [GEMINI.md context](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md).

## Stable checkout path

Hook commands continue to reference the checkout used to install them. Before applying, display that absolute path and state that moving or deleting it will break managed hooks. `check` must verify that managed hook commands point to existing scripts and report stale paths clearly. Re-running setup from a new checkout updates the commands through the existing transaction and preserves rollback. This phase does not add self-updating launchers or clone the project into a hidden directory.

## Error handling and safety

- No target files are written until all selected targets and modules pass preflight and the user confirms the preview.
- Existing custom hooks, skills, rules, and statuslines remain preserved according to current installer behavior.
- Malformed config, unsupported Python, missing required files, unresolved conflicts, symlinks, and missing selected-module dependencies produce a specific actionable error and leave targets unchanged.
- Hook failures remain fail-open where the current guard does so; this change does not alter model, effort, MCP, or context-window settings.
- Do not send telemetry, prompts, or configuration contents to external services during detection or setup.

## Verification criteria

1. The guided flow selects only detected agents by default and permits an explicit target choice.
2. Missing requirements are reported before any target changes.
3. The preview and apply use the same collected configuration; declining leaves a clean filesystem.
4. A successful apply is idempotent, reports its backup ID, passes `check`, and can be rolled back without losing preexisting custom configuration.
5. Moving the checkout is detected by `check`; reapplying from the new path repairs managed hook commands.
6. Gemini configuration merges safely with existing user settings, skills, and rules. Its capability matrix does not list unsupported handoff, PDF, or statusline modules.
7. Live smoke tests verify Gemini skill discovery and warning-hook behavior without invoking unrelated work. Codex and Claude smoke tests are recorded with client versions and terminal/Desktop limits; unavailable service responses are marked unverified rather than inferred.

## Out of scope

This phase does not create a GUI, one-line network installer, platform-specific launcher scripts, automatic dependency installation, broad integrations beyond Gemini CLI, public release publication, social posts, or claims of measured token/cost savings. Release copy, demo, and launch materials follow after the adapter and bootstrap are verified.

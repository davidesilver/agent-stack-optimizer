# Evaluation: fast-jev-compaction (optional, not enabled)

Status: optional choice in `/setup` (`--strategy jev-plugin`), off by default. Setup records the choice and the data-sharing confirmation only; it installs nothing and never reads a key.
Source: https://github.com/tamaratran/fast-jev-compaction (MIT, plugin 0.3.0, package 0.2.0 at time of review).

## What it does

Claude Code plugin using the early-access function-hook surface (`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, reference types generated for Claude Code 2.1.274). On `session.compact` it keeps every user and assistant text verbatim and only drops or truncates tool calls and tool results. A Jev model (TypeSafe) decides, per tool call, whether the call and its result are still needed. If the service fails, the key is missing, or the reduction is below `minReductionRatio` (0.25), it falls back to the built-in summary.

## Verified from source

- The only network target in `src/request.ts` is `https://api.typesafe.ai/v1/systemone`, with `Authorization: Bearer <TYPESAFE_API_KEY>`.
- Each request carries the whole conversation as state: user and assistant text, tool inputs (truncated to fit), tool results replaced by a one-line note. The same state is resent for every batch of questions.
- The hook reads the key from plugin option, `TYPESAFE_API_KEY`, or the `env` block of Claude settings.
- `turn.complete` asks for compaction at `compactAtPercent` (default 60).
- The upstream unit tests (29) pass offline with an injected fetch. No live Jev call was made in this review.

## Not verified

- Real token or cost savings. Figures in the author's page and videos are claims. Dropping messages from the middle of history changes the prompt prefix and can invalidate the prompt cache, so the net effect has to be measured.
- Behaviour on Windows, and on current Claude Code versions beyond the one the types were generated for.
- Codex: the plugin targets Claude Code only.

## Fit with this project

- Conversation content leaves the machine. Anyone enabling it must decide whether that is acceptable for their sessions. It is a separate service and key, with usage-based pricing.
- The handoff guard is configured to hand off at 30-35% context. The plugin triggers at 60%, so with the default guard it would rarely run. It only matters for sessions that continue past the guard (`--mode warn`, or long unavoidable sessions).
- It cannot be part of the reversible `stack.py` transaction: it is installed with `claude plugin install`, outside the managed files. Setup records the choice as pending and the guard keeps working; only `--plugin-active` (after you installed and saw it run) makes the Claude guard warn-only. The guided install in the setup skill is untested end to end.

## Experiment (opt-in, synthetic data only)

1. Use a fixture transcript with no personal data, for example a scripted session that reads and edits files of a public repo.
2. Run the same fixture three ways: built-in compact, handoff guard only, plugin with a throwaway key.
3. Record input, cache read, cache write and output tokens with `python3 stack.py report`, plus whether the task finished.
4. Adopt only if the plugin beats the guard on total tokens including cache effects, without losing task success.

Remove this file or move it to a changelog once the experiment gives a result.

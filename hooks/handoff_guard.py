#!/usr/bin/env python3
"""End-of-turn handoff at user thresholds. Never assumes a model window."""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stacklib.config import load, validate
from stacklib.usage import last_context


def evaluate(ctx, window, policy):
    if policy["unit"] == "percent":
        if not window:
            return "unknown", None
        value = ctx / window * 100
    else:
        value = ctx
    level = "max" if value >= policy["max"] else "warn" if value >= policy["warn"] else "ok"
    return level, value


def main():
    try:
        d = json.load(sys.stdin)
        agent = sys.argv[1] if len(sys.argv) > 1 else "claude"
        home = Path(os.environ.get("AI_CONFIG_HOME", str(Path.home())))
        cfg = load(home)
        if "handoff" not in cfg["modules"] or agent not in cfg["agents"]:
            return
        p = cfg["context"]
        ls = cfg.get("long_sessions", {})
        if agent == "claude" and ls.get("strategy") == "jev-plugin" and ls.get("plugin_status") == "active":
            p = {**p, "mode": "warn"}  # the confirmed plugin compacts; Codex keeps its own policy
        # Legacy environment settings remain supported; explicitly chosen overrides win.
        if "AI_HANDOFF_WARN" in os.environ or "AI_HANDOFF_FORCE" in os.environ:
            p.update(unit="percent", warn=float(os.environ.get("AI_HANDOFF_WARN", p["warn"] / 100)) * 100,
                     max=float(os.environ.get("AI_HANDOFF_FORCE", p["max"] / 100)) * 100)
        if "AI_CTX_WINDOW" in os.environ:
            p["window_tokens"] = int(os.environ["AI_CTX_WINDOW"])
        validate(cfg)
        tp = Path(d.get("transcript_path") or "")
        if not tp.is_file():
            return
        ctx, window = last_context(tp, agent)
        sid = str(d.get("session_id") or tp.resolve())
        key = hashlib.sha256((agent + sid).encode()).hexdigest()[:24]
        state_dir = home / ".config" / "ai-config" / "runtime"
        if agent == "claude":
            cw = d.get("context_window") or {}
            window = cw.get("context_window_size") or window
            cached = state_dir / f"window-{hashlib.sha256(sid.encode()).hexdigest()[:24]}.json"
            if not window and cached.exists():
                window = json.loads(cached.read_text()).get("window")
        window = p.get("window_tokens") or window
        if not ctx:
            return
        level, value = evaluate(ctx, window, p)
        sf = state_dir / f"guard-{key}.json"
        state = json.loads(sf.read_text()) if sf.exists() else {}
        event = d.get("hook_event_name")
        if level == "unknown" and event == "UserPromptSubmit" and not state.get("unknown"):
            state["unknown"] = True
            print(json.dumps({"systemMessage": "Context window unavailable: percent thresholds are inactive. Declare window_tokens or use token thresholds in setup."}))
        elif level in {"warn", "max"} and event == "UserPromptSubmit" and not state.get("warned"):
            state["warned"] = True
            label = f"{value:.0f}%" if p["unit"] == "percent" else f"{int(value):,} tokens"
            action = "Handoff at end of turn" if p["mode"] == "handoff" else "Warning only"
            print(json.dumps({"systemMessage": f"Context: {label}. Configured max: {p['max']} {p['unit']}. {action}."}))
        elif level == "max" and p["mode"] == "handoff" and event == "Stop" and not state.get("forced") and not d.get("stop_hook_active"):
            state["forced"] = True
            reason = ("The configured context handoff threshold has been reached. Save the current task state with the handoff skill, "
                      "including failed approaches, decisions, changed files, validation and next action. Do not ask questions; label uncertainty. "
                      "Exclude secrets. Return the saved path and a fresh-chat continuation prompt, then stop. Do not launch another agent or chat.")
            print(json.dumps({"decision": "block", "reason": reason}))
        else:
            return
        state_dir.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(state))
    except (ValueError, TypeError, KeyError, OSError):
        return  # fail open: missing/malformed telemetry must never block user work


if __name__ == "__main__":
    main()

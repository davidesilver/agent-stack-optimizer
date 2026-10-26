import json
import math
from pathlib import Path

MODULES = {"handoff", "pdf", "statusline", "rules", "setup", "markitdown"}
DEFAULT = {"schema": 1, "agents": ["claude", "codex"],
           "modules": sorted(MODULES), "context": {"unit": "percent", "warn": 30,
           "max": 35, "mode": "handoff", "window_tokens": None},
           "long_sessions": {"strategy": "handoff", "external_data_ack": False, "plugin_status": "none"}}

# "handoff": start a new chat at the thresholds (default, no external service).
# "jev-plugin": optional alternative, the third-party fast-jev-compaction plugin.
#   It sends conversation text to api.typesafe.ai and needs the user's own paid key.
#   plugin_status "pending" = chosen but not yet confirmed active: the handoff guard keeps
#   working unchanged. "active" = the user confirmed the plugin runs: the Claude guard then only
#   warns (the plugin compacts at 60%, a handoff at the max threshold would pre-empt it).
#   Codex never changes policy: the plugin does not support it.
STRATEGIES = {"handoff", "jev-plugin"}
PLUGIN_STATUS = {"none", "pending", "active"}


def config_path(home):
    return Path(home) / ".config" / "ai-config" / "config.json"


def validate(c):
    if c.get("schema") != 1:
        raise ValueError("Unsupported config schema")
    if not c.get("agents") or set(c["agents"]) - {"claude", "codex"}:
        raise ValueError("Agents must be claude and/or codex")
    if set(c.get("modules", [])) - MODULES:
        raise ValueError("Unknown module")
    ctx = c["context"]
    if ctx["unit"] not in {"percent", "tokens"} or ctx["mode"] not in {"warn", "handoff"}:
        raise ValueError("Invalid context unit or mode")
    a, b = ctx["warn"], ctx["max"]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (a, b)):
        raise ValueError("Thresholds must be finite numbers")
    if not 0 < a < b or (ctx["unit"] == "percent" and b > 100):
        raise ValueError("Require 0 < warn < max (percent max <= 100)")
    if ctx["unit"] == "tokens" and (int(a) != a or int(b) != b):
        raise ValueError("Token thresholds must be integers")
    window = ctx.get("window_tokens")
    if window is not None and (isinstance(window, bool) or not isinstance(window, int) or window <= 0):
        raise ValueError("Window must be a positive integer or null")
    if window and ctx["unit"] == "tokens" and b > window:
        raise ValueError("Maximum threshold exceeds declared window")
    ls = c.get("long_sessions", DEFAULT["long_sessions"])
    status = ls.get("plugin_status", "none" if ls.get("strategy") == "handoff" else "pending")
    if ls.get("strategy") not in STRATEGIES or status not in PLUGIN_STATUS:
        raise ValueError("Unknown long-session strategy or plugin status")
    if ls["strategy"] == "handoff" and status != "none":
        raise ValueError("plugin_status must be none with the handoff strategy")
    if ls["strategy"] == "jev-plugin":
        if ls.get("external_data_ack") is not True:
            raise ValueError("jev-plugin sends conversation text to api.typesafe.ai: confirm with --accept-external-data")
        if "claude" not in c["agents"]:
            raise ValueError("jev-plugin works with Claude Code only")
        if status == "none":
            raise ValueError("jev-plugin needs plugin_status pending or active")
    return c


def load(home):
    p = config_path(home)
    return validate(json.loads(p.read_text()) if p.exists() else json.loads(json.dumps(DEFAULT)))

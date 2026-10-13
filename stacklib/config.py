import json
import math
from pathlib import Path

MODULES = {"handoff", "pdf", "statusline", "rules", "setup", "markitdown"}
DEFAULT = {"schema": 1, "agents": ["claude", "codex"],
           "modules": sorted(MODULES), "context": {"unit": "percent", "warn": 30,
           "max": 35, "mode": "handoff", "window_tokens": None}}


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
    return c


def load(home):
    p = config_path(home)
    return validate(json.loads(p.read_text()) if p.exists() else json.loads(json.dumps(DEFAULT)))

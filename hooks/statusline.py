#!/usr/bin/env python3
"""Status line per Claude Code (terminale): modello, % contesto, limiti sessione/settimana.
Legge il JSON che Claude Code passa su stdin. Tollerante: se un campo manca, lo salta."""
import hashlib
import json
import os
from pathlib import Path
import sys

try:
    d = json.load(sys.stdin)
except Exception:
    d = {}


def get(*keys):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def colour(pct):
    return "\033[32m" if pct < 40 else "\033[33m" if pct < 70 else "\033[31m"


R = "\033[0m"
parts = []
model = get("model", "display_name")
if model:
    parts.append(str(model))
ctx = get("context_window", "used_percentage")
if isinstance(ctx, (int, float)):
    parts.append(f"ctx {colour(ctx)}{ctx:.0f}%{R}")
for label, key in (("5h", "five_hour"), ("7d", "seven_day")):
    p = get("rate_limits", key, "used_percentage")
    if isinstance(p, (int, float)):
        parts.append(f"{label} {colour(p)}{p:.0f}%{R}")
print(" | ".join(parts) if parts else "claude")

# Expose the client-reported window to the guard without assuming a model limit.
try:
    sid = d.get("session_id")
    window = get("context_window", "context_window_size")
    if sid and isinstance(window, int) and window > 0:
        root = Path(os.environ.get("AI_CONFIG_HOME", str(Path.home()))) / ".config" / "ai-config" / "runtime"
        root.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(str(sid).encode()).hexdigest()[:24]
        (root / f"window-{key}.json").write_text(json.dumps({"window": window}))
except OSError:
    pass

"""Normalized telemetry. Codex cumulative snapshots are never summed."""
import json
from pathlib import Path


def rows(path, tail=False):
    with Path(path).open("rb") as f:
        if tail:
            f.seek(max(0, Path(path).stat().st_size - 600_000))
        for line in f:
            try:
                d = json.loads(line)
                if isinstance(d, dict):
                    yield d
            except (ValueError, UnicodeDecodeError):
                continue


def last_context(path, agent):
    result = (0, None)
    window = None
    for d in rows(path, tail=True):
        if agent == "codex":
            payload = d.get("payload") or {}
            if payload.get("type") != "token_count":
                continue
            info = payload.get("info") or {}
            u = info.get("last_token_usage") or {}
            window = info.get("model_context_window") or window
            if u:
                result = (u.get("input_tokens", 0), window)
        else:
            cw = d.get("context_window") or {}
            window = cw.get("context_window_size") or d.get("model_context_window") or window
            u = (d.get("message") or {}).get("usage") or {}
            if u:
                window = u.get("context_window_size") or window
                result = (sum(u.get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")), window)
    return result


def _summarize_codex(path):
    total = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "reasoning": 0, "requests": 0}
    initial = None
    latest = None
    for d in rows(path):
        payload = d.get("payload") or {}
        if payload.get("type") != "token_count":
            continue
        info = payload.get("info") or {}
        if initial is None and info.get("last_token_usage"):
            initial = info["last_token_usage"].get("input_tokens", 0)
        if info.get("total_token_usage"):
            latest = info["total_token_usage"]
    if latest:
        total.update(input=latest.get("input_tokens", 0), cache_read=latest.get("cached_input_tokens", 0),
                     cache_write=latest.get("cache_write_input_tokens", 0), output=latest.get("output_tokens", 0),
                     reasoning=latest.get("reasoning_output_tokens", 0))
    # Codex input includes cached input; cache_read is a subset. Request count is unavailable.
    return total, initial


def _summarize_default(path):
    total = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "reasoning": 0, "requests": 0}
    initial = None
    seen = {}
    anonymous = []
    for d in rows(path):
        m = d.get("message") or {}
        u = m.get("usage")
        if not u:
            continue
        if initial is None:
            initial = sum(u.get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        # Streaming updates repeat message IDs; latest values replace earlier partial usage.
        if m.get("id"):
            seen[m["id"]] = u
        else:
            anonymous.append(u)
    for u in [*seen.values(), *anonymous]:
        for dst, key in (("input", "input_tokens"), ("cache_read", "cache_read_input_tokens"),
                         ("cache_write", "cache_creation_input_tokens"), ("output", "output_tokens")):
            total[dst] += u.get(key, 0) or 0
        total["requests"] += 1
    return total, initial


def summarize(path, agent):
    if agent == "codex":
        total, initial = _summarize_codex(path)
    else:
        total, initial = _summarize_default(path)
    return {"agent": agent, **total, "initial_context": initial}

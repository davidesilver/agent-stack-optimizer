#!/usr/bin/env python3
"""Portable setup, audit, telemetry and reversible changes for coding agents."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from stacklib.audit import audit, check
from stacklib.config import load, validate, MODULES
from stacklib.install import install
from stacklib.transaction import rollback
from stacklib.usage import summarize


def setup(args, home):
    c = load(home)
    if args.interactive:
        if not sys.stdin.isatty():
            raise ValueError("Interactive setup requires a terminal; use explicit flags")
        c["agents"] = input(f"Agents comma-separated [{','.join(c['agents'])}]: ").strip().split(",") or c["agents"]
        c["agents"] = [x.strip() for x in c["agents"] if x.strip()] or load(home)["agents"]
        value = input(f"Modules [{','.join(c['modules'])}]: ").strip()
        if value:
            c["modules"] = [x.strip() for x in value.split(",")]
        p = c["context"]
        p["unit"] = input(f"Context unit percent/tokens [{p['unit']}]: ").strip() or p["unit"]
        p["warn"] = float(input(f"Warn [{p['warn']}]: ").strip() or p["warn"])
        p["max"] = float(input(f"Max [{p['max']}]: ").strip() or p["max"])
        p["mode"] = input(f"Mode handoff/warn [{p['mode']}]: ").strip() or p["mode"]
        declared = input(f"Declared window tokens (0 = automatic) [{p.get('window_tokens') or 0}]: ").strip()
        if declared:
            p["window_tokens"] = int(declared) or None
        print("Max is an end-of-turn threshold, not a hard model-window limit.")
    if args.agents is not None:
        c["agents"] = args.agents.split(",")
    if args.modules is not None:
        c["modules"] = args.modules.split(",") if args.modules else []
    if not args.interactive and args.unit is not None and args.unit != c["context"]["unit"] and (args.warn is None or args.max is None):
        raise ValueError("Changing context units requires both --warn and --max")
    for key in ("unit", "warn", "max", "mode", "window_tokens"):
        value = getattr(args, key)
        if value is not None:
            c["context"][key] = None if key == "window_tokens" and value == 0 else value
    validate(c)
    print(json.dumps(c, indent=2))
    install(home, c, args.dry_run)


def report(args, home):
    cutoff = time.time() - args.days * 86400
    sessions = []
    for agent, directory, pattern in (("claude", ".claude/projects", "*/*.jsonl"), ("codex", ".codex/sessions", "*/*/*/*.jsonl")):
        for p in (home / directory).glob(pattern):
            if p.stat().st_mtime < cutoff:
                continue
            row = summarize(p, agent)
            # Stable anonymous key, never include transcript paths or task text.
            import hashlib
            row["session"] = hashlib.sha256(str(p.relative_to(home)).encode()).hexdigest()[:16]
            sessions.append(row)
    runs = []
    for p in (home / ".config/ai-config/outputs").glob("*.json"):
        if p.stat().st_mtime >= cutoff:
            runs.append(json.loads(p.read_text()))
    r = {"schema": 1, "period_days": args.days, "sessions": sessions, "command_runs": runs,
         "notes": ["Claude input excludes cache; Codex input includes cache_read (a subset).",
                   "No billing estimate. Timing and task success require a controlled benchmark; not inferred from token counts."]}
    if args.save:
        Path(args.save).write_text(json.dumps(r, indent=2) + "\n")
    if args.compare:
        previous = json.loads(Path(args.compare).read_text())
        r["comparison"] = {}
        for agent in ("claude", "codex"):
            def totals(rows):
                count = i = cr = cw = o = 0
                for x in rows:
                    if x.get("agent") == agent:
                        count += 1
                        i += x.get("input", 0)
                        cr += x.get("cache_read", 0)
                        cw += x.get("cache_write", 0)
                        o += x.get("output", 0)
                return {"sessions": count, "input": i, "cache_read": cr, "cache_write": cw, "output": o}
            r["comparison"][agent] = {"before": totals(previous["sessions"]), "after": totals(sessions)}
        r["notes"].append("Different tasks/periods are not evidence of optimization savings.")
    print(json.dumps(r, indent=2))


def run_command(args, home):
    argv = args.command
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        raise ValueError("Provide a command after --")
    root = home / ".config" / "ai-config" / "outputs"
    root.mkdir(parents=True, exist_ok=True)
    p = root / (uuid.uuid4().hex + ".log")
    started = time.monotonic()
    with p.open("xb") as f:
        os.chmod(p, 0o600)
        try:
            result = subprocess.run(argv, stdout=f, stderr=subprocess.STDOUT)
        except FileNotFoundError:
            print("Command not found", file=sys.stderr)
            return 127
    print(f"Full output: {p}", file=sys.stderr)
    displayed = False
    filtered_bytes = None
    # Failed commands always show full output, so diagnostics are never filtered away.
    if args.filter == "rtk" and result.returncode == 0:
        rtk = shutil.which("rtk")
        if rtk:
            filtered = subprocess.run([rtk, "log", str(p)], capture_output=True)
            if filtered.returncode == 0 and filtered.stdout:
                sys.stdout.buffer.write(filtered.stdout)
                displayed = True
                filtered_bytes = len(filtered.stdout)
        if not displayed:
            print("RTK unavailable/failed: showing original output", file=sys.stderr)
    if not displayed:
        with p.open("rb") as f:
            shutil.copyfileobj(f, sys.stdout.buffer)
    metadata = {"id": p.stem, "duration_seconds": round(time.monotonic() - started, 3),
                "exit_code": result.returncode, "original_bytes": p.stat().st_size,
                "displayed_bytes": filtered_bytes if displayed else p.stat().st_size,
                "filter": "rtk" if displayed else "raw"}
    mp = p.with_suffix(".json")
    with mp.open("x") as f:
        os.chmod(mp, 0o600)
        json.dump(metadata, f, indent=2)
    return result.returncode if result.returncode >= 0 else 128 - result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help="Alternate home, for isolated tests")
    sub = parser.add_subparsers(dest="action", required=True)
    s = sub.add_parser("setup", help="Install selected modules; defaults preserve saved choices")
    s.add_argument("--interactive", action="store_true")
    s.add_argument("--agents", help="claude,codex")
    s.add_argument("--modules", help=",".join(sorted(MODULES)))
    s.add_argument("--unit", choices=["percent", "tokens"])
    s.add_argument("--warn", type=float)
    s.add_argument("--max", type=float)
    s.add_argument("--mode", choices=["warn", "handoff"])
    s.add_argument("--window-tokens", type=int, help="Manual declared window; 0 restores automatic detection")
    s.add_argument("--dry-run", action="store_true")
    sub.add_parser("audit")
    sub.add_parser("check")
    r = sub.add_parser("rollback")
    r.add_argument("id")
    r.add_argument("--dry-run", action="store_true")
    sub.add_parser("backups")
    r = sub.add_parser("report")
    r.add_argument("--days", type=int, default=7)
    r.add_argument("--save")
    r.add_argument("--compare")
    r = sub.add_parser("run", help="Explicit optional RTK filter; original output always retained")
    r.add_argument("--filter", choices=["raw", "rtk"], default="raw")
    r.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    try:
        if args.action == "setup":
            setup(args, home)
        elif args.action == "audit":
            print(json.dumps(audit(home), indent=2))
        elif args.action == "check":
            result = check(home)
            print(json.dumps(result, indent=2))
            print("Registration checked; review hook approval/execution in your client.")
            return int(not all(x["ok"] for x in result))
        elif args.action == "rollback":
            rollback(home, args.id, args.dry_run)
        elif args.action == "backups":
            for p in sorted((home / ".config/ai-config/backups").glob("*/manifest.json")):
                m = json.loads(p.read_text())
                print(m["id"], m["status"], len(m["files"]))
        elif args.action == "report":
            if args.days <= 0:
                raise ValueError("days must be positive")
            report(args, home)
        elif args.action == "run":
            return run_command(args, home)
        return 0
    except (ValueError, KeyError, OSError, TypeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

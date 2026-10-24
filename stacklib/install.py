import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from .config import config_path, validate
from .transaction import Transaction, safe_path

ROOT = Path(__file__).resolve().parent.parent
BEGIN, END = "<!-- ai-config:begin -->", "<!-- ai-config:end -->"


def read_json(p):
    result = json.loads(p.read_text()) if p.exists() else {}
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON object: {p.name}")
    return result


def owned(h):
    command = h.get("command", "").replace("\\", "/")
    return ("/ai-config/hooks/" in command or "/agent-stack-optimizer/hooks/" in command
            or "agent_stack_hook_v1" in command)


def command(script, *args):
    launcher = ("import os,sys,subprocess;agent_stack_hook_v1=True;"
                "p=sys.argv[1];sys.exit(subprocess.call([sys.executable]+sys.argv[1:]) "
                "if os.path.isfile(p) else 0)")
    argv = [sys.executable, "-c", launcher, str(ROOT / "hooks" / script), *args]
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


def events(existing, entries):
    # Remove only our command handlers; keep other handlers sharing the same event entry.
    result = dict(existing)
    for event in {"PreToolUse", "UserPromptSubmit", "Stop"}:
        kept = []
        for entry in result.get(event, []):
            handlers = [h for h in entry.get("hooks", []) if not owned(h)]
            if handlers:
                kept.append({**entry, "hooks": handlers})
        kept.extend(entries.get(event, []))
        if kept:
            result[event] = kept
        else:
            result.pop(event, None)
    return result


def rule_block(current, body):
    block = f"{BEGIN}\n{body.strip()}\n{END}"
    if (BEGIN in current) != (END in current) or current.count(BEGIN) > 1 or current.count(END) > 1:
        raise ValueError("Malformed managed rules block")
    if BEGIN in current:
        pre, rest = current.split(BEGIN)
        _, post = rest.split(END)
        return pre + block + post
    return current.rstrip() + ("\n\n" if current.strip() else "") + block + "\n"


def _configure_agent(home, agent, modules, writes):
    p = safe_path(home, f".{agent}/" + ("settings.json" if agent == "claude" else "hooks.json"))
    s = read_json(p)
    entries = {}
    if "handoff" in modules:
        for event in ("UserPromptSubmit", "Stop"):
            entries[event] = [{"hooks": [{"type": "command", "command": command("handoff_guard.py", agent), "timeout": 30}]}]
    if agent == "claude" and "pdf" in modules:
        entries["PreToolUse"] = [{"matcher": "Read", "hooks": [{"type": "command", "command": command("pdf_to_text.py")}]}]
    s["hooks"] = events(s.get("hooks", {}), entries)
    if agent == "claude":
        sl = s.get("statusLine")
        is_ours = isinstance(sl, dict) and owned(sl)
        if "statusline" in modules and (not sl or is_ours):
            s["statusLine"] = {"type": "command", "command": command("statusline.py")}
        elif "statusline" not in modules and is_ours:
            s.pop("statusLine", None)
        elif sl and not is_ours:
            print("Keep existing custom statusline")
    writes[p] = json.dumps(s, indent=2, ensure_ascii=False) + "\n"
    if "rules" in modules:
        rp = safe_path(home, f".{agent}/" + ("CLAUDE.md" if agent == "claude" else "AGENTS.md"))
        current = rp.read_text() if rp.exists() else ""
        writes[rp] = rule_block(current, (ROOT / "templates" / "rules.md").read_text())


def _configure_skills(home, cfg, modules, writes):
    skill_dirs = []
    if "claude" in cfg["agents"]:
        skill_dirs.append(".claude/skills")
    if "codex" in cfg["agents"]:
        skill_dirs.append(".agents/skills")  # one canonical location, no second Codex copy
    for sk in ("handoff", "setup", "markitdown"):
        if sk not in modules:
            continue
        body = (ROOT / "skills" / sk / "SKILL.md").read_text().replace("{{ROOT}}", str(ROOT))
        for location in skill_dirs:
            dst = safe_path(home, f"{location}/{sk}/SKILL.md")
            if dst.exists() and "agent-stack-managed-v1" not in dst.read_text():
                print(f"Keep existing custom skill: {location}/{sk}")
            else:
                writes[dst] = body


def _migrate_legacy(home, cfg, modules, writes):
    # Migrate identical legacy duplicate; snapshot makes removal reversible.
    if "codex" in cfg["agents"] and "handoff" in modules:
        a = safe_path(home, ".agents/skills/handoff/SKILL.md")
        b = safe_path(home, ".codex/skills/handoff/SKILL.md")
        if a.exists() and b.exists() and a.read_bytes() == b.read_bytes():
            extras = list(b.parent.iterdir())
            if extras == [b]:
                writes[b] = None


def install(home, cfg, dry=False):
    home = Path(home).resolve()
    validate(cfg)
    tx = Transaction(home, dry)
    modules = set(cfg["modules"])
    writes = {}

    for agent in cfg["agents"]:
        _configure_agent(home, agent, modules, writes)

    _configure_skills(home, cfg, modules, writes)
    _migrate_legacy(home, cfg, modules, writes)

    writes[config_path(home)] = json.dumps(cfg, indent=2) + "\n"
    # Validate all destinations before the first mutation.
    for p in writes:
        safe_path(home, p.relative_to(home))
    try:
        for p, body in writes.items():
            tx.write(p, body)
        tx.finish()
    except BaseException:
        if tx.manifest["files"] and not dry:
            print(f"Interrupted install; recover with rollback {tx.id}", file=sys.stderr)
        raise
    if "codex" in cfg["agents"]:
        print("Codex: hook registration does not prove execution. Review /hooks in your installed client.")
    print("Existing model, effort, MCP servers and cache-timer configuration retained.")
    return tx.id

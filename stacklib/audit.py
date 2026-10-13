import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from .config import load
from .install import command, read_json, owned


def audit(home):
    home = Path(home)
    versions = {}
    for tool in ("claude", "codex", "rtk", "graphify"):
        exe = shutil.which(tool)
        if not exe:
            versions[tool] = "not installed"
            continue
        try:
            r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
            versions[tool] = (r.stdout or r.stderr).splitlines()[0][:120] if r.returncode == 0 else "installed (version unavailable)"
        except (OSError, subprocess.TimeoutExpired, IndexError):
            versions[tool] = "installed (version unavailable)"
    skills = {}
    for location in (".claude/skills", ".agents/skills", ".codex/skills"):
        for p in (home / location).glob("*/SKILL.md"):
            body = p.read_bytes()
            skills.setdefault(p.parent.name, []).append({"location": location, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
    duplicates = {k: v for k, v in skills.items() if len([x for x in v if x["location"] in {".agents/skills", ".codex/skills"}]) > 1}
    rules = {}
    for path in (".claude/CLAUDE.md", ".codex/AGENTS.md"):
        p = home / path
        rules[path] = {"bytes": p.stat().st_size if p.exists() else 0}
    hooks = {}
    integrations = {}
    for path in (".claude/settings.json", ".codex/hooks.json"):
        d = read_json(home / path)
        hooks[path] = {event: sum(len(e.get("hooks", [])) for e in entries) for event, entries in d.get("hooks", {}).items()}
        # Counts only: never output credentials or environment values.
        if "settings" in path:
            integrations["claude_enabled_plugins"] = sum(bool(x) for x in d.get("enabledPlugins", {}).values())
    return {"versions": versions, "config": load(home), "skill_count": len(skills),
            "codex_duplicate_skills": duplicates, "rules": rules, "registered_hooks": hooks,
            "integrations": integrations, "note": "File sizes are not loaded token counts. Hook registration is not proof of execution. No settings values or transcript content exported."}


def check(home):
    cfg = load(home)
    results = []
    modules = set(cfg["modules"])
    for agent in cfg["agents"]:
        d = read_json(Path(home) / f".{agent}" / ("settings.json" if agent == "claude" else "hooks.json"))
        for event in ("UserPromptSubmit", "Stop"):
            expected = command("handoff_guard.py", agent)
            registered = any(h.get("command") == expected for e in d.get("hooks", {}).get(event, []) for h in e.get("hooks", []))
            results.append({"check": f"{agent} {event}", "ok": registered == ("handoff" in modules)})
        if agent == "claude" and "pdf" in modules:
            registered = any(h.get("command") == command("pdf_to_text.py") for e in d.get("hooks", {}).get("PreToolUse", []) if e.get("matcher") == "Read" for h in e.get("hooks", []))
            results.append({"check": "claude PDF hook", "ok": registered})
            results.append({"check": "PDF extractor installed", "ok": bool(shutil.which("pdftotext") or __import__("importlib.util", fromlist=["find_spec"]).find_spec("pypdf"))})
        if agent == "claude" and "markitdown" in modules:
            results.append({"check": "markitdown CLI installed", "ok": bool(shutil.which("markitdown"))})
        for skill in ("setup", "handoff", "markitdown"):
            if skill in modules:
                location = ".claude/skills" if agent == "claude" else ".agents/skills"
                results.append({"check": f"{agent} skill {skill}", "ok": (Path(home) / location / skill / "SKILL.md").is_file()})
    return results

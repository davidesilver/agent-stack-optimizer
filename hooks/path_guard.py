#!/usr/bin/env python3
"""PreToolUse (Write|Edit): protegge Wiki/raw/ esistente e la radice di OneDrive.

Blocca (exit 2): modifica di un file GIA' esistente in Wiki/raw/; creazione di una
nuova voce di primo livello nella radice di OneDrive. Fail-open: ogni eccezione -> exit 0.
Kill switch: PATH_GUARD_OFF=1. Blocchi loggati in ~/.cache/path_guard.log.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("PATH_GUARD_ROOT", str(Path.home() / "Library/CloudStorage/OneDrive-Personale")))
LOG = Path.home() / ".cache" / "path_guard.log"


def check(tool, path):
    """Ritorna il messaggio di blocco, oppure None se permesso."""
    p = Path(os.path.abspath(os.path.expanduser(path)))
    raw = ROOT / "Wiki" / "raw"
    if p.is_file() and (p == raw or raw in p.parents):
        return f"Bloccato: {p} e' un file gia' esistente in Wiki/raw/ (le fonti non si modificano; i file nuovi in raw/ sono ammessi)."
    top = ROOT / p.relative_to(ROOT).parts[0] if ROOT in p.parents else None
    if tool == "Write" and top and not top.exists():
        return f"Bloccato: '{top.name}' sarebbe una nuova voce nella radice di OneDrive. Usa Projects/, Documents/, '! Inbox/' o Review/ (vedi CLAUDE.md)."
    return None


def main():
    try:
        if os.environ.get("PATH_GUARD_OFF") == "1":
            return 0
        d = json.load(sys.stdin)
        tool = d.get("tool_name", "")
        path = (d.get("tool_input") or {}).get("file_path")
        if tool not in ("Write", "Edit") or not path:
            return 0
        msg = check(tool, path)
        if msg:
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a") as f:
                f.write(f"{time.strftime('%F %T')} {tool} {path}\n")
            print(msg, file=sys.stderr)
            return 2
    except Exception:
        pass  # fail-open
    return 0


def selftest():
    import tempfile
    global ROOT
    with tempfile.TemporaryDirectory() as t:
        ROOT = Path(t).resolve()
        (ROOT / "Wiki/raw").mkdir(parents=True)
        (ROOT / "Wiki/Library").mkdir()
        (ROOT / "Wiki/raw/old.md").write_text("x")
        (ROOT / "Wiki/Library/p.md").write_text("x")
        assert check("Edit", str(ROOT / "Wiki/raw/old.md"))            # raw esistente: bloccato
        assert not check("Write", str(ROOT / "Wiki/raw/new.md"))       # raw nuovo: ok
        assert not check("Edit", str(ROOT / "Wiki/Library/p.md"))      # pagina wiki: ok
        assert check("Write", str(ROOT / "nuova-cartella/x.md"))       # cartella nuova in radice: bloccato
        assert not check("Write", str(ROOT / "Wiki/Library/nuovo.md"))  # file nuovo in cartella esistente: ok
        assert check("Write", str(ROOT / "nuovo.md"))                  # radice: bloccato
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        sys.exit(main())

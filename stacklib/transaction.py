"""File snapshots; rollback refuses subsequent edits and symlink targets."""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def safe_path(home, relative):
    home = Path(home).resolve()
    p = home / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Path outside home")
    for node in [p, *p.parents]:
        if node == home:
            break
        if node.is_symlink():
            raise ValueError(f"Symlink target refused: {node}")
    if not p.resolve().is_relative_to(home):
        raise ValueError("Path outside home")
    return p


def atomic_write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with tmp.open("xb") as f:
            os.chmod(tmp, 0o600)
            f.write(data)
        if p.exists():
            os.chmod(tmp, p.stat().st_mode & 0o777)
        tmp.replace(p)
    finally:
        tmp.unlink(missing_ok=True)


class Transaction:
    def __init__(self, home, dry=False):
        self.home = Path(home).resolve()
        self.dry = dry
        self.id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10]
        self.root = self.home / ".config" / "ai-config" / "backups" / self.id
        safe_path(self.home, self.root.relative_to(self.home))
        self.manifest = {"schema": 1, "id": self.id, "status": "in-progress", "files": []}
        self._written_paths = set()

    def save_manifest(self):
        atomic_write(self.root / "manifest.json", json.dumps(self.manifest, indent=2).encode())

    def write(self, path, data):
        p = safe_path(self.home, Path(path).relative_to(self.home))
        data = data.encode() if isinstance(data, str) else data
        before = p.read_bytes() if p.exists() else None
        if before == data:
            return
        print(("[dry-run] " if self.dry else "") + f"Update {p.relative_to(self.home)}")
        if self.dry:
            return
        path_str = str(p.relative_to(self.home))
        if path_str in self._written_paths:
            raise ValueError("Duplicate write in transaction")
        index = len(self.manifest["files"])
        if before is not None:
            atomic_write(self.root / f"{index}.bak", before)
        self.manifest["files"].append({"path": path_str, "before": digest(before),
                                      "after": digest(data), "backup": f"{index}.bak" if before is not None else None,
                                      "mode": p.stat().st_mode & 0o777 if p.exists() else 0o600})
        self._written_paths.add(path_str)
        self.save_manifest()  # recovery information exists before changing target
        if data is None:
            p.unlink(missing_ok=True)
        else:
            atomic_write(p, data)

    def finish(self):
        if self.dry or not self.manifest["files"]:
            print("No changes" if not self.dry else "Preview only")
            return
        self.manifest["status"] = "complete"
        self.save_manifest()
        print(f"Backup / rollback ID: {self.id}")


def rollback(home, run_id, dry=False):
    home = Path(home).resolve()
    if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for c in run_id):
        raise ValueError("Invalid backup ID")
    root = safe_path(home, Path(".config/ai-config/backups") / run_id)
    m = json.loads((root / "manifest.json").read_text())
    if m["status"] == "rolled-back":
        return
    targets = []
    for entry in m["files"]:
        p = safe_path(home, entry["path"])
        current = p.read_bytes() if p.exists() else None
        h = digest(current)
        if h == entry["before"]:  # also allows recovery from interrupted installs
            continue
        if h != entry["after"]:
            raise ValueError(f"Rollback conflict: {entry['path']} changed since installation; no files restored")
        original = None
        if entry["backup"]:
            bp = safe_path(home, (root / entry["backup"]).relative_to(home))
            original = bp.read_bytes()
            if digest(original) != entry["before"]:
                raise ValueError("Corrupt backup; no files restored")
        targets.append((p, original, entry["mode"]))
    for p, original, mode in reversed(targets):
        print(("[dry-run] " if dry else "") + f"Restore {p.relative_to(home)}")
        if not dry:
            if original is None:
                p.unlink(missing_ok=True)
            else:
                atomic_write(p, original)
                os.chmod(p, mode)
    if not dry:
        m["status"] = "rolled-back"
        atomic_write(root / "manifest.json", json.dumps(m, indent=2).encode())

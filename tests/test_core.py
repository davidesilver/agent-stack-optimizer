import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from stacklib.config import DEFAULT, validate
from stacklib.install import install, command
from stacklib.transaction import Transaction, rollback
from stacklib.usage import last_context, summarize


def cfg(**context):
    c = json.loads(json.dumps(DEFAULT))
    c["context"].update(context)
    return c


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def install(self, config=None, dry=False):
        with contextlib.redirect_stdout(io.StringIO()):
            return install(self.home, config or cfg(), dry)

    def test_install_preserves_shared_hooks_model_and_is_idempotent(self):
        p = self.home / ".claude/settings.json"
        p.parent.mkdir()
        external = {"type": "command", "command": "echo external"}
        p.write_text(json.dumps({"model": "custom", "env": {"TOKEN": "fixture"}, "hooks": {"Stop": [{"hooks": [external, {"type": "command", "command": "/old/ai-config/hooks/handoff_guard.py"}]}]}}))
        first = self.install()
        result = json.loads(p.read_text())
        self.assertEqual(result["model"], "custom")
        self.assertEqual(result["env"], {"TOKEN": "fixture"})
        self.assertEqual(result["hooks"]["Stop"][0]["hooks"], [external])
        snapshot = {str(x.relative_to(self.home)): x.read_bytes() for x in self.home.rglob("*") if x.is_file()}
        self.install()
        self.assertEqual(snapshot, {str(x.relative_to(self.home)): x.read_bytes() for x in self.home.rglob("*") if x.is_file()})
        self.assertTrue((self.home / f".config/ai-config/backups/{first}/manifest.json").exists())

    def test_long_session_strategy_validation(self):
        c = cfg()
        legacy = {k: v for k, v in c.items() if k != "long_sessions"}
        validate(legacy)  # legacy config without the key stays valid
        c["long_sessions"] = {"strategy": "jev-plugin", "external_data_ack": False, "plugin_status": "pending"}
        with self.assertRaises(ValueError):
            validate(c)  # no consent
        c["long_sessions"]["external_data_ack"] = True
        validate(c)  # pending with handoff mode is allowed: guard stays active
        c["long_sessions"]["plugin_status"] = "active"
        validate(c)
        c["agents"] = ["codex"]
        with self.assertRaises(ValueError):
            validate(c)  # Claude Code only
        c["agents"] = ["claude", "codex"]
        c["long_sessions"] = {"strategy": "handoff", "external_data_ack": False, "plugin_status": "active"}
        with self.assertRaises(ValueError):
            validate(c)

    def stack(self, *args, env=None):
        return subprocess.run([sys.executable, str(ROOT / "stack.py"), "--home", str(self.home), *args],
                              capture_output=True, text=True, env=env)

    def saved(self):
        return json.loads((self.home / ".config/ai-config/config.json").read_text())

    def test_setup_jev_pending_then_active_then_back(self):
        env = {**os.environ, "TYPESAFE_API_KEY": "sentinel-key-123"}
        self.assertNotEqual(self.stack("setup", "--strategy", "jev-plugin", env=env).returncode, 0)  # consent denied
        self.assertFalse((self.home / ".config/ai-config/config.json").exists())
        ok = self.stack("setup", "--strategy", "jev-plugin", "--accept-external-data", env=env)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        c = self.saved()
        self.assertEqual(c["long_sessions"]["plugin_status"], "pending")
        self.assertEqual(c["context"]["mode"], "handoff")  # guard policy untouched, both agents
        self.assertEqual(c["agents"], ["claude", "codex"])
        everything = "".join(p.read_text(errors="ignore") for p in self.home.rglob("*") if p.is_file()) + ok.stdout
        self.assertNotIn("sentinel-key-123", everything)
        self.assertFalse((self.home / ".claude/plugins").exists())
        act = self.stack("setup", "--plugin-active")
        self.assertEqual(act.returncode, 0, act.stderr)
        self.assertEqual(self.saved()["long_sessions"]["plugin_status"], "active")
        self.assertEqual(self.saved()["context"]["mode"], "handoff")  # stored policy still handoff
        back = self.stack("setup", "--strategy", "handoff")
        self.assertEqual(back.returncode, 0, back.stderr)
        self.assertEqual(self.saved()["long_sessions"], {"strategy": "handoff", "external_data_ack": False, "plugin_status": "none"})
        self.assertEqual(self.saved()["context"]["mode"], "handoff")

    def test_plugin_active_requires_consent_and_dry_run_writes_nothing(self):
        self.assertNotEqual(self.stack("setup", "--plugin-active", "--strategy", "handoff").returncode, 0)
        self.assertNotEqual(self.stack("setup", "--plugin-active").returncode, 0)
        r = self.stack("setup", "--strategy", "jev-plugin", "--accept-external-data", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.home / ".config/ai-config/config.json").exists())

    def test_rollback_restores_config_after_strategy_change(self):
        self.stack("setup")
        before = self.saved()
        r = self.stack("setup", "--strategy", "jev-plugin", "--accept-external-data")
        self.assertEqual(r.returncode, 0, r.stderr)
        backups = sorted((self.home / ".config/ai-config/backups").glob("*/manifest.json"), key=lambda p: p.stat().st_mtime_ns)
        self.assertTrue(backups)
        bid = json.loads(backups[-1].read_text())["id"]
        rb = self.stack("rollback", bid)
        self.assertEqual(rb.returncode, 0, rb.stderr)
        self.assertEqual(self.saved()["long_sessions"], before["long_sessions"])

    def run_guard(self, agent, event, transcript, extra=None):
        payload = {"hook_event_name": event, "transcript_path": str(transcript), "session_id": agent, **(extra or {})}
        env = {k: v for k, v in os.environ.items() if not k.startswith("AI_HANDOFF") and k != "AI_CTX_WINDOW"}
        env["AI_CONFIG_HOME"] = str(self.home)
        r = subprocess.run([sys.executable, str(ROOT / "hooks/handoff_guard.py"), agent], input=json.dumps(payload),
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout else None

    def claude_transcript(self):
        p = self.home / "claude-session.jsonl"
        p.write_text(json.dumps({"message": {"id": "m1", "usage": {"input_tokens": 400, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 5}}}) + "\n")
        return p

    def test_guard_policy_by_plugin_status(self):
        c = cfg(unit="tokens", warn=100, max=200)
        for status, claude_blocks in (("pending", True), ("active", False)):
            c["long_sessions"] = {"strategy": "jev-plugin", "external_data_ack": True, "plugin_status": status}
            self.install(c)
            state = self.home / ".config/ai-config/runtime"
            if state.exists():
                for f in state.iterdir():
                    f.unlink()
            ct, xt = self.claude_transcript(), self.transcript()
            claude = self.run_guard("claude", "Stop", ct)
            codex = self.run_guard("codex", "Stop", xt)
            self.assertEqual(bool(claude and claude.get("decision") == "block"), claude_blocks, status)
            self.assertEqual(codex["decision"], "block", status)  # Codex policy never changes

    def test_audit_counts_mod_dirs_without_values(self):
        from stacklib.audit import audit
        p = self.home / ".claude/settings.json"
        p.parent.mkdir()
        p.write_text(json.dumps({"env": {"CLAUDE_CODE_PLUGIN_DIRS": os.pathsep.join(["/a", "/b"])}}))
        r = audit(self.home)
        self.assertEqual(r["integrations"]["claude_mod_dirs"], 2)
        self.assertNotIn("/a", json.dumps(r))

    def test_dry_run_no_writes(self):
        self.install(dry=True)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_invalid_config_and_invalid_existing_json_no_partial_changes(self):
        with self.assertRaises(ValueError):
            self.install(cfg(warn=60, max=40))
        self.assertEqual(list(self.home.iterdir()), [])
        p = self.home / ".codex/hooks.json"
        p.parent.mkdir()
        p.write_text("broken JSON")
        with self.assertRaises(ValueError):
            self.install()
        self.assertFalse((self.home / ".claude").exists())

    def test_rollback_refuses_conflict_before_restoring_any_file(self):
        run = self.install()
        p = self.home / ".claude/CLAUDE.md"
        p.write_text("user changed")
        other = self.home / ".codex/hooks.json"
        before = other.read_bytes()
        with self.assertRaisesRegex(ValueError, "conflict"):
            rollback(self.home, run)
        self.assertEqual(other.read_bytes(), before)
        self.assertEqual(p.read_text(), "user changed")

    def test_rollback_restores_original_and_removes_new_files(self):
        p = self.home / ".claude/settings.json"
        p.parent.mkdir()
        p.write_text('{"model":"original"}')
        original = p.read_bytes()
        run = self.install()
        with contextlib.redirect_stdout(io.StringIO()):
            rollback(self.home, run)
        self.assertEqual(p.read_bytes(), original)
        self.assertFalse((self.home / ".codex/hooks.json").exists())
        self.assertFalse((self.home / ".config/ai-config/config.json").exists())

    def test_duplicate_migration_preserves_custom_skill_and_is_reversible(self):
        for location in (".agents", ".codex"):
            p = self.home / location / "skills/handoff/SKILL.md"
            p.parent.mkdir(parents=True)
            p.write_text("custom handoff")
        run = self.install()
        a = self.home / ".agents/skills/handoff/SKILL.md"
        b = self.home / ".codex/skills/handoff/SKILL.md"
        self.assertEqual(a.read_text(), "custom handoff")
        self.assertFalse(b.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            rollback(self.home, run)
        self.assertEqual(b.read_text(), "custom handoff")

    def test_symlink_is_refused(self):
        outside = self.home / "outside"
        outside.mkdir()
        try:
            (self.home / ".claude").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Symlinks unavailable")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.install()
        self.assertEqual(list(outside.iterdir()), [])

    def test_disabling_handoff_removes_only_managed_hook(self):
        self.install()
        c = cfg()
        c["modules"] = ["setup"]
        self.install(c)
        s = json.loads((self.home / ".claude/settings.json").read_text())
        self.assertNotIn("Stop", s["hooks"])
        self.assertNotIn("statusLine", s)

    def test_threshold_validation(self):
        for context in ({"warn": float("nan")}, {"max": 101}, {"window_tokens": -1},
                        {"unit": "tokens", "warn": 1.5}, {"unit": "tokens", "warn": 5, "max": 20, "window_tokens": 10}):
            with self.assertRaises(ValueError):
                validate(cfg(**context))

    def guard(self, event, transcript, extra=None):
        payload = {"hook_event_name": event, "transcript_path": str(transcript), "session_id": "fixture", **(extra or {})}
        env = {k: v for k, v in os.environ.items() if not k.startswith("AI_HANDOFF") and k != "AI_CTX_WINDOW"}
        env["AI_CONFIG_HOME"] = str(self.home)
        r = subprocess.run([sys.executable, str(ROOT / "hooks/handoff_guard.py"), "codex"], input=json.dumps(payload), capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout else None

    def transcript(self, window=1000):
        p = self.home / "session.jsonl"
        info = {"last_token_usage": {"input_tokens": 400}, "total_token_usage": {"input_tokens": 400, "cached_input_tokens": 100, "output_tokens": 10}}
        if window:
            info["model_context_window"] = window
        p.write_text(json.dumps({"payload": {"type": "token_count", "info": info}}) + "\n")
        return p

    def test_guard_handoff_once_and_stop_recursion(self):
        self.install()
        p = self.transcript()
        self.assertIn("systemMessage", self.guard("UserPromptSubmit", p))
        self.assertIsNone(self.guard("Stop", p, {"stop_hook_active": True}))
        r = self.guard("Stop", p)
        self.assertEqual(r["decision"], "block")
        self.assertNotIn("cost", r["reason"])
        self.assertIsNone(self.guard("Stop", p))

    def test_guard_unknown_window_and_token_warning_only(self):
        self.install()
        p = self.transcript(None)
        self.assertIn("unavailable", self.guard("UserPromptSubmit", p)["systemMessage"])
        self.assertIsNone(self.guard("Stop", p))
        self.install(cfg(unit="tokens", warn=100, max=300, mode="warn"))
        self.assertIsNone(self.guard("Stop", p))

    def test_claude_statusline_supplies_real_window_to_guard(self):
        self.install()
        p = self.home / "claude.jsonl"
        p.write_text(json.dumps({"message": {"usage": {"input_tokens": 400}}}) + "\n")
        env = {k: v for k, v in os.environ.items() if not k.startswith("AI_HANDOFF") and k != "AI_CTX_WINDOW"}
        env["AI_CONFIG_HOME"] = str(self.home)
        d = {"session_id": "claude-fixture", "context_window": {"context_window_size": 1000, "used_percentage": 40}}
        r = subprocess.run([sys.executable, str(ROOT / "hooks/statusline.py")], input=json.dumps(d), capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0)
        payload = {"hook_event_name": "Stop", "session_id": "claude-fixture", "transcript_path": str(p)}
        r = subprocess.run([sys.executable, str(ROOT / "hooks/handoff_guard.py"), "claude"], input=json.dumps(payload), capture_output=True, text=True, env=env)
        self.assertEqual(json.loads(r.stdout)["decision"], "block")

    def test_token_handoff_works_without_window(self):
        self.install(cfg(unit="tokens", warn=100, max=300))
        p = self.transcript(None)
        self.assertEqual(self.guard("Stop", p)["decision"], "block")

    def test_run_filtered_failure_still_shows_original_and_records_duration(self):
        r = subprocess.run([sys.executable, str(ROOT / "stack.py"), "--home", str(self.home), "run", "--filter", "rtk", "--", sys.executable, "-c", "print('important failure');raise SystemExit(9)"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 9)
        self.assertIn("important failure", r.stdout)
        metadata = json.loads(next((self.home / ".config/ai-config/outputs").glob("*.json")).read_text())
        self.assertEqual(metadata["filter"], "raw")
        self.assertEqual(metadata["exit_code"], 9)
        self.assertGreaterEqual(metadata["duration_seconds"], 0)

    def test_codex_cumulative_usage_is_not_double_counted(self):
        p = self.transcript()
        first = p.read_text()
        second = json.loads(first)
        second["payload"]["info"]["total_token_usage"] = {"input_tokens": 900, "cached_input_tokens": 300, "output_tokens": 20}
        p.write_text(first + json.dumps(second) + "\n" + json.dumps(second) + "\n")
        report = summarize(p, "codex")
        self.assertEqual(report["input"], 900)
        self.assertEqual(report["cache_read"], 300)
        self.assertEqual(last_context(p, "codex"), (400, 1000))

    def test_claude_streaming_usage_replaces_partial_message(self):
        p = self.home / "claude.jsonl"
        p.write_text("\n".join(json.dumps({"message": {"id": "same", "usage": {"input_tokens": 10, "cache_read_input_tokens": 20, "output_tokens": output}}}) for output in (1, 5)))
        self.assertEqual(summarize(p, "claude")["output"], 5)
        self.assertEqual(last_context(p, "claude"), (30, None))

    @unittest.skipIf(os.name == "nt", "POSIX shell quoting test")
    def test_launcher_handles_spaces_and_missing_script(self):
        r = subprocess.run(command("nonexistent.py"), shell=True, capture_output=True)
        self.assertEqual(r.returncode, 0)

    def test_run_preserves_failure_and_full_output(self):
        r = subprocess.run([sys.executable, str(ROOT / "stack.py"), "--home", str(self.home), "run", "--", sys.executable, "-c", "print('fixture error');raise SystemExit(7)"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 7)
        self.assertIn("fixture error", r.stdout)
        logs = list((self.home / ".config/ai-config/outputs").glob("*.log"))
        self.assertEqual(logs[0].read_text(), "fixture error\n")


    def _run_pdf_hook(self, target, path_dirs=None):
        env = {**os.environ, "HOME": str(self.home), "USERPROFILE": str(self.home)}
        if path_dirs is not None:
            env["PATH"] = os.pathsep.join(path_dirs)
        payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": str(target)}})
        return subprocess.run([sys.executable, str(ROOT / "hooks" / "pdf_to_text.py")], input=payload,
                              capture_output=True, text=True, env=env)

    def test_pdf_hook_converts_office_with_markitdown_and_falls_back_without_it(self):
        doc = self.home / "report.docx"
        doc.write_bytes(b"PK fixture")
        bin_dir = self.home / "fakebin"
        bin_dir.mkdir()
        if os.name == "nt":
            (bin_dir / "markitdown.cmd").write_text("@echo # converted fixture\r\n")
        else:
            fake = bin_dir / "markitdown"
            fake.write_text("#!/bin/sh\necho '# converted fixture'\n")
            fake.chmod(0o755)
        r = self._run_pdf_hook(doc, [str(bin_dir), os.path.dirname(sys.executable)])
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)["hookSpecificOutput"]["updatedInput"]["file_path"]
        self.assertIn("converted fixture", Path(out).read_text(encoding="utf-8"))
        other = self.home / "other.docx"
        other.write_bytes(b"PK other")
        r = self._run_pdf_hook(other, [os.path.dirname(sys.executable)])
        self.assertEqual((r.returncode, r.stdout), (0, ""))  # no markitdown: native Read proceeds


if __name__ == "__main__":
    unittest.main()

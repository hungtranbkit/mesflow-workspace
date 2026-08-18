"""Tests for bin/reset_admin_password.py -- the local-only Bootstrap admin
password reset added for the "Khôi phục truy cập / Quên mật khẩu" guide
section.

All tests run against isolated scratch directories under tempfile; nothing
here ever touches /var/lib/mesflow-bootstrap or any real Bootstrap state,
per the standing "never let a spawned test process touch real state" rule.
Only `perform_reset()` (the pure core) is exercised directly -- no root
check, no getpass/TTY, no argparse -- matching how `reset_admin_password.py`
itself separates that core from `main()`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

BOOTSTRAP_DIR = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("reset_admin_password", BOOTSTRAP_DIR / "bin" / "reset_admin_password.py")
rap = importlib.util.module_from_spec(spec)
sys.modules["reset_admin_password"] = rap
spec.loader.exec_module(rap)


def _seeded_state(**overrides) -> dict:
    state = {
        "setup_complete": True,
        "secret_key": "unchanged-secret-key",
        "admin_username": "admin",
        "admin_password_hash": generate_password_hash("old-password-123"),
        "bind_host": "0.0.0.0",
        "created_at": "2026-01-01T00:00:00+00:00",
        "agent_updater_token": "unchanged-token-value",
    }
    state.update(overrides)
    return state


class ResetAdminPasswordTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        (self.data_dir / "logs").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_state(self, state: dict) -> None:
        (self.data_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    def test_missing_state_file_refuses_with_actionable_message(self):
        with self.assertRaises(rap.ResetError) as ctx:
            rap.perform_reset(self.data_dir, generate_password_hash,
                               new_username=None, password="newpassword1", confirm="newpassword1")
        self.assertIn("never completed initial setup", str(ctx.exception))

    def test_setup_not_complete_refuses(self):
        self._write_state(_seeded_state(setup_complete=False))
        with self.assertRaises(rap.ResetError) as ctx:
            rap.perform_reset(self.data_dir, generate_password_hash,
                               new_username=None, password="newpassword1", confirm="newpassword1")
        self.assertIn("has not completed initial setup", str(ctx.exception))

    def test_short_password_rejected(self):
        self._write_state(_seeded_state())
        with self.assertRaises(rap.ResetError) as ctx:
            rap.perform_reset(self.data_dir, generate_password_hash,
                               new_username=None, password="short", confirm="short")
        self.assertIn("at least 10 characters", str(ctx.exception))

    def test_mismatched_confirmation_rejected(self):
        self._write_state(_seeded_state())
        with self.assertRaises(rap.ResetError) as ctx:
            rap.perform_reset(self.data_dir, generate_password_hash,
                               new_username=None, password="newpassword1", confirm="different1")
        self.assertIn("does not match", str(ctx.exception))

    def test_short_username_rejected(self):
        self._write_state(_seeded_state())
        with self.assertRaises(rap.ResetError):
            rap.perform_reset(self.data_dir, generate_password_hash,
                               new_username="ab", password="newpassword1", confirm="newpassword1")

    def test_successful_reset_changes_only_credential_fields(self):
        before = _seeded_state()
        self._write_state(before)

        rap.perform_reset(self.data_dir, generate_password_hash,
                           new_username=None, password="brandnewpassword1", confirm="brandnewpassword1")

        after = json.loads((self.data_dir / "state.json").read_text(encoding="utf-8"))
        # Username unchanged (no --username given), password hash changed.
        self.assertEqual(after["admin_username"], "admin")
        self.assertNotEqual(after["admin_password_hash"], before["admin_password_hash"])
        self.assertTrue(check_password_hash(after["admin_password_hash"], "brandnewpassword1"))
        self.assertFalse(check_password_hash(after["admin_password_hash"], "old-password-123"))
        # Everything else -- secret_key, agent_updater_token, setup_complete,
        # bind_host, created_at -- is untouched.
        for key in ("secret_key", "agent_updater_token", "setup_complete", "bind_host", "created_at"):
            self.assertEqual(after[key], before[key], f"{key} was unexpectedly modified")

    def test_username_can_be_changed_explicitly(self):
        self._write_state(_seeded_state())
        rap.perform_reset(self.data_dir, generate_password_hash,
                           new_username="newadmin", password="brandnewpassword1", confirm="brandnewpassword1")
        after = json.loads((self.data_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(after["admin_username"], "newadmin")

    def test_audit_log_entry_written_without_leaking_password(self):
        self._write_state(_seeded_state())
        rap.perform_reset(self.data_dir, generate_password_hash,
                           new_username=None, password="brandnewpassword1", confirm="brandnewpassword1")
        log_text = (self.data_dir / "logs" / "audit.log").read_text(encoding="utf-8")
        self.assertIn("admin_password_reset", log_text)
        self.assertIn("admin=admin", log_text)
        self.assertNotIn("brandnewpassword1", log_text)

    def test_state_file_written_atomically_no_leftover_tmp(self):
        self._write_state(_seeded_state())
        rap.perform_reset(self.data_dir, generate_password_hash,
                           new_username=None, password="brandnewpassword1", confirm="brandnewpassword1")
        self.assertFalse((self.data_dir / "state.tmp").exists())
        self.assertTrue((self.data_dir / "state.json").exists())


if __name__ == "__main__":
    unittest.main()

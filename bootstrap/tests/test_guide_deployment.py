"""Tests for the beginner deployment guide (guide_content.py + the
/guide/deployment route + templates/guide_deployment.html).

Two layers:
1. Content-integrity tests on guide_content.py directly -- no Flask, no
   filesystem beyond what py_compile/import needs. Catches broken
   structure (duplicate ids, empty commands, unresolved placeholders) fast.
2. A route-level smoke test using Flask's test client, loaded the same way
   tests/test_agent_lifecycle.py loads app.py (importlib, isolated scratch
   DATA_DIR) but pointed at THIS checkout's real templates/static/
   guide_content.py (MESFLOW_BOOTSTRAP_HOME = the actual bootstrap/ source
   dir) so it renders the real Jinja templates, not empty stand-ins. Never
   touches /opt/mesflow-bootstrap or a real Deploy Agent/Docker.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

BOOTSTRAP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOOTSTRAP_DIR))

import guide_content  # noqa: E402


class GuideContentIntegrityTests(unittest.TestCase):
    """Structural sanity on the single source of truth, independent of Flask."""

    def test_step_ids_unique_and_sequential(self):
        ids = guide_content.all_step_ids()
        self.assertEqual(len(ids), len(set(ids)), "duplicate step id")
        nums = [s["num"] for s in guide_content.STEPS]
        self.assertEqual(nums, [f"{i:02d}" for i in range(1, len(nums) + 1)])

    def test_every_step_has_required_fields(self):
        for s in guide_content.STEPS:
            for field in ("id", "num", "title", "purpose", "where", "expected", "on_error", "next"):
                self.assertTrue(s.get(field), f"step {s.get('id')} missing {field}")
            self.assertTrue(s["blocks"], f"step {s['id']} has no content blocks")

    def test_every_command_has_a_known_machine_label(self):
        known = set(guide_content.MACHINE_LABELS)
        checked = 0
        for s in guide_content.STEPS:
            for b in s["blocks"]:
                for cmd in b["commands"]:
                    self.assertIn(cmd["machine"], known)
                    self.assertTrue(cmd["code"].strip())
                    checked += 1
        for f in guide_content.FAILURES:
            for cmd in f["diagnose"] + f.get("extra_commands", []):
                self.assertIn(cmd["machine"], known)
                checked += 1
        self.assertGreater(checked, 20, "expected many commands across the guide")

    def test_no_raw_angle_bracket_placeholder_in_fields_rendered_as_safe_html(self):
        """Fields rendered with |safe in guide_deployment.html (cmd.note,
        block.text, block.note, step.expected/on_error, failure.fix) must
        entity-encode any <PLACEHOLDER> or the browser will silently eat it
        as an unknown tag. Real <code>/<b>/<br> tags are fine and expected."""
        bad_tag_re = re.compile(r"<(?!/?(code|b|br)\b)[A-Za-z_]")

        def check(label, text):
            if text:
                self.assertIsNone(bad_tag_re.search(text), f"{label!r} has an unescaped placeholder: {text!r}")

        for s in guide_content.STEPS:
            check(f"{s['id']}.expected", s["expected"])
            check(f"{s['id']}.on_error", s["on_error"])
            for b in s["blocks"]:
                check(f"{s['id']}.block.text", b.get("text"))
                check(f"{s['id']}.block.note", b.get("note"))
                for cmd in b["commands"]:
                    check(f"{s['id']}.cmd.note", cmd.get("note"))
        for f in guide_content.FAILURES:
            check(f"{f['title']}.fix", f["fix"])
        for a in guide_content.RECOVERY_ACCESS:
            for field in ("if_forgotten", "access_required", "expected", "do_not"):
                check(f"{a['system']}.{field}", a[field])
            for cmd in a["commands"] + a["verify"]:
                check(f"{a['system']}.cmd.note", cmd.get("note"))
        check("recovery_access_env_warning", guide_content.RECOVERY_ACCESS_ENV_WARNING)
        check("recovery_access_cli_fallback", guide_content.RECOVERY_ACCESS_CLI_FALLBACK)
        for row in guide_content.EMERGENCY_ACCESS_MATRIX:
            check("emergency_access_matrix.recovery", row["recovery"])

    def test_recovery_access_covers_all_three_systems_with_required_fields(self):
        systems = [a["system"] for a in guide_content.RECOVERY_ACCESS]
        self.assertEqual(systems, ["Bootstrap", "Deploy Agent", "MESFlow"])
        for a in guide_content.RECOVERY_ACCESS:
            for field in ("if_forgotten", "access_required", "expected", "do_not"):
                self.assertTrue(a[field], f"{a['system']}.{field} is empty")
            self.assertTrue(a["commands"], f"{a['system']} has no recovery commands")
            self.assertTrue(a["verify"], f"{a['system']} has no verify step")
            known = set(guide_content.MACHINE_LABELS)
            for cmd in a["commands"] + a["verify"]:
                self.assertIn(cmd["machine"], known)
                self.assertTrue(cmd["code"].strip())

    def test_mesflow_card_labels_server_commands_distinctly_and_never_mixes_dev_into_server_steps(self):
        mesflow = next(a for a in guide_content.RECOVERY_ACCESS if a["system"] == "MESFlow")
        machines = [cmd["machine"] for cmd in mesflow["commands"]]
        # Step A (ssh) is typed on the laptop; steps B-F run on the MESFlow
        # server itself and must use the distinct MESFLOW_SERVER label the
        # task required ("CHẠY TRÊN SERVER MESFLOW"), not the generic
        # SERVER label used elsewhere in the guide.
        self.assertEqual(machines[0], guide_content.DEV)
        self.assertTrue(all(m == guide_content.MESFLOW_SERVER for m in machines[1:]))
        self.assertNotIn(guide_content.SERVER, machines)  # never the generic/ambiguous label here

    def test_emergency_access_matrix_has_one_row_per_scenario_plus_lost_ssh_note(self):
        # 4 rows: MESFlow normal-user reset, MESFlow admin reset, Deploy
        # Agent, Bootstrap -- normal-user and admin are split into two
        # separate MESFlow rows per the "don't use reset-admin for ordinary
        # account maintenance" guidance.
        self.assertEqual(len(guide_content.EMERGENCY_ACCESS_MATRIX), 4)
        for row in guide_content.EMERGENCY_ACCESS_MATRIX:
            for field in ("forgot", "need", "recovery"):
                self.assertTrue(row[field])
        self.assertTrue(guide_content.LOST_SSH_NOTE)
        self.assertIn("SSH", guide_content.LOST_SSH_NOTE)

    def test_emergency_access_matrix_mesflow_rows_use_reset_admin_not_reset_password(self):
        mesflow_rows = [r for r in guide_content.EMERGENCY_ACCESS_MATRIX if "MESFlow" in r["forgot"]]
        self.assertEqual(len(mesflow_rows), 2)
        recoveries = " ".join(r["recovery"] for r in mesflow_rows)
        self.assertIn("reset-admin", recoveries)
        self.assertNotIn("reset-password", recoveries)

    def test_recovery_security_warnings_present_and_non_empty(self):
        self.assertGreaterEqual(len(guide_content.RECOVERY_SECURITY_WARNINGS), 5)
        for warn in guide_content.RECOVERY_SECURITY_WARNINGS:
            self.assertTrue(warn.strip())

    def test_render_markdown_has_no_leftover_html_entities_or_tags(self):
        md = guide_content.render_markdown()
        self.assertNotIn("&lt;", md)
        self.assertNotIn("&gt;", md)
        self.assertNotIn("&amp;", md)
        self.assertNotIn("<code>", md)
        self.assertNotIn("</code>", md)
        self.assertNotIn("<br>", md)

    def test_recovery_tree_last_node_has_no_dangling_yes(self):
        self.assertFalse(guide_content.RECOVERY_TREE[-1]["yes_next"])


def _load_app(tmp_path: Path, module_name: str):
    """Load app.py against THIS checkout's real templates/static/
    guide_content.py, but with an isolated scratch DATA_DIR -- mirrors
    tests/test_agent_lifecycle.py's load_app() pattern, minus the
    updater-core vendoring this suite doesn't need."""
    import os

    data = tmp_path / "var"
    data.mkdir(parents=True)
    env_backup = dict(os.environ)
    os.environ["MESFLOW_BOOTSTRAP_HOME"] = str(BOOTSTRAP_DIR)
    os.environ["MESFLOW_BOOTSTRAP_DATA_DIR"] = str(data)
    os.environ["MESFLOW_AGENT_HOME"] = str(tmp_path / "agent-home")
    os.environ["MESFLOW_AGENT_DATA_DIR"] = str(tmp_path / "agent-data")
    try:
        spec = importlib.util.spec_from_file_location(module_name, BOOTSTRAP_DIR / "app.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        os.environ.clear()
        os.environ.update(env_backup)
    return module


class GuideRouteSmokeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.app = _load_app(self.tmp_path, f"bootstrap_guide_test_{id(self)}")
        self.client = self.app.app.test_client()
        self._complete_setup_and_login()

    def tearDown(self):
        self._tmp.cleanup()

    def _csrf(self, html: str) -> str:
        return re.search(r'name="_csrf" value="([^"]+)"', html).group(1)

    def _complete_setup_and_login(self):
        token = self.app.SETUP_TOKEN_FILE.read_text(encoding="utf-8").strip()
        r = self.client.get("/setup")
        self.client.post("/setup", data={
            "_csrf": self._csrf(r.text), "token": token, "username": "admin",
            "password": "supersecret123", "confirm": "supersecret123",
        }, follow_redirects=True)
        r = self.client.get("/login")
        self.client.post("/login", data={
            "_csrf": self._csrf(r.text), "username": "admin", "password": "supersecret123",
        }, follow_redirects=True)

    def test_guide_route_requires_login(self):
        self.client.post("/logout", data={"_csrf": "x"})  # invalid csrf, session persists either way in test client
        fresh = self.app.app.test_client()
        r = fresh.get("/guide/deployment", follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_guide_route_renders_all_sections_and_anchors(self):
        r = self.client.get("/guide/deployment")
        self.assertEqual(r.status_code, 200)
        html = r.text
        self.assertIn("Hướng dẫn triển khai", html)
        for step_id in guide_content.all_step_ids():
            self.assertIn(f'id="{step_id}"', html)
        for anchor in ("kien-truc", "vai-tro", "su-co", "quen-mat-khau", "cay-quyet-dinh", "checklist", "thuat-ngu"):
            self.assertIn(f'id="{anchor}"', html)
        self.assertNotIn("{%", html)  # no unresolved Jinja tags
        self.assertNotIn("&amp;lt;", html)  # no double-escaped placeholders
        # every in-page anchor link resolves to a real id on the page
        hrefs = set(re.findall(r'href="#([^"]+)"', html))
        ids = set(re.findall(r'id="([^"]+)"', html))
        self.assertEqual(hrefs - ids, set())

    def test_guide_route_renders_password_recovery_section(self):
        r = self.client.get("/guide/deployment")
        html = r.text
        self.assertIn("reset-admin-password", html)
        self.assertIn("/agent/local-reset", html)
        self.assertIn("mesflow.cli reset-admin", html)
        self.assertIn("Ma trận truy cập khẩn cấp", html)
        self.assertIn("Người dùng hệ thống", html)
        self.assertIn("CHẠY TRÊN SERVER MESFLOW", html)  # task-specified exact label
        # all three system cards present
        for system in ("Bootstrap", "Deploy Agent", "MESFlow"):
            self.assertIn(f"<h3>{system}</h3>", html)

    def test_guide_route_never_renders_the_stale_mesflow_reset_command(self):
        """Regression test for the exact bug this task fixes: a previous
        guide revision told operators to run
        `docker compose run --rm mesflow python -m mesflow.cli reset-password
        admin`, a command that doesn't exist in any deployed MESFlow image
        (verified live: `docker exec mesflow-app grep -o "funcs={[^}]*}"
        /app/mesflow/cli.py` on this DEV host's real running container does
        not list reset-password)."""
        r = self.client.get("/guide/deployment")
        html = r.text
        self.assertNotIn("reset-password admin", html)
        self.assertNotIn("docker compose run --rm mesflow", html)

    def test_troubleshooting_covers_unknown_command_and_container_not_running(self):
        r = self.client.get("/guide/deployment")
        html = r.text
        self.assertIn("unknown command", html)
        self.assertIn('grep -o &#34;funcs={[^}]*}&#34;', html)  # Jinja-escaped quotes in the real command
        self.assertIn("docker ps -a --filter name=mesflow-app", html)
        # "docker compose down -v" appears only as an explicit "KHÔNG tự ý" (don't) warning,
        # never as a suggested action -- both must be present together.
        self.assertIn("docker compose down -v", html)
        self.assertIn("KHÔNG tự ý", html)

    def test_nav_link_present_on_other_pages(self):
        r = self.client.get("/overview")
        self.assertIn(">Hướng dẫn triển khai</a>", r.text)

    def test_existing_pages_still_render(self):
        for path in ("/overview", "/docker", "/services", "/logs", "/commands", "/install-agent"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)


if __name__ == "__main__":
    unittest.main()

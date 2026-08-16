"""Bootstrap's Deploy Agent lifecycle wiring (app.py's agent_do_update /
agent_do_rollback / agent_updater_core / the /updater/* and /agent/*
routes) -- NOT a re-test of the vendored update/rollback state machine
itself, which is already covered by
deploy-agent/tests/test_updater.py and reused unmodified here (see
reports/BOOTSTRAP_AGENT_UPDATER_CONSOLIDATION.md).

Everything here runs against isolated scratch directories and a mocked
`subprocess.run` -- per the standing "never let a spawned test process
touch a real container" rule, no test in this file may reach the real
Docker daemon or a real mesflow-deploy-agent container.

Imported directly from the workspace files via importlib, same technique
deploy-agent/tests/test_updater.py uses, so each test gets a fresh app.py
module instance with its own config.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

BOOTSTRAP_DIR = Path(__file__).resolve().parents[1]
UPDATER_SRC = BOOTSTRAP_DIR.parent / "deploy-agent" / "updater" / "updater.py"


def load_app(tmp_path: Path, module_name: str):
    home = tmp_path / "opt"
    data = tmp_path / "var"
    (home / "templates").mkdir(parents=True)
    (home / "static").mkdir(parents=True)
    data.mkdir(parents=True)
    shutil.copy(UPDATER_SRC, home / "agent_updater_core.py")

    import os
    env_backup = dict(os.environ)
    os.environ["MESFLOW_BOOTSTRAP_HOME"] = str(home)
    os.environ["MESFLOW_BOOTSTRAP_DATA_DIR"] = str(data)
    os.environ["MESFLOW_AGENT_HOME"] = str(tmp_path / "agent-home")
    os.environ["MESFLOW_AGENT_DATA_DIR"] = str(tmp_path / "agent-data")
    (tmp_path / "agent-home" / "docker").mkdir(parents=True)
    (tmp_path / "agent-home" / "docker" / "compose.linux.yml").write_text(
        "services: {mesflow-deploy-agent: {}}\n")
    try:
        spec = importlib.util.spec_from_file_location(module_name, BOOTSTRAP_DIR / "app.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        os.environ.clear()
        os.environ.update(env_backup)
    return module


def build_artifact(tmp_path: Path, version="9.9.9-docker-runtime", image_id="sha256:" + "a" * 64, tamper=False):
    root = tmp_path / "pkgstage" / "mesflow-deploy-agent-release"
    root.mkdir(parents=True)
    tar_name = f"mesflow-deploy-agent_{version.replace('-docker-runtime', '')}.tar"
    (root / tar_name).write_bytes(b"fake-tar-bytes")
    manifest = {"type": "mesflow-agent-release", "version": version,
                "image": "mesflow-deploy-agent:test", "image_digest": image_id, "image_id": image_id,
                "bundle": tar_name, "api_protocol_version": 2, "capabilities": ["image_release_receive"]}
    (root / "agent-release.json").write_text(json.dumps(manifest))
    lines = []
    for fname in (tar_name, "agent-release.json"):
        h = hashlib.sha256((root / fname).read_bytes()).hexdigest()
        lines.append(f"{h}  {fname}")
    if tamper:
        lines[0] = "0" * 64 + f"  {tar_name}"
    (root / "checksums.txt").write_text("\n".join(lines) + "\n")
    zip_path = tmp_path / "AGENT_UPDATE.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        for f in root.iterdir():
            z.write(f, f"mesflow-deploy-agent-release/{f.name}")
    return zip_path, manifest


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class AgentLifecycleWiringTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.app = load_app(self.tmp_path, f"bootstrap_app_test_{id(self)}")
        self.commands = []
        self.compose_up_rc = 0
        self.expected_id = "sha256:" + "a" * 64
        self.docker_inspect_env_lines = []

    def tearDown(self):
        self._tmp.cleanup()

    def _fake_run(self, health_sequence):
        calls = {"idx": 0}

        def fake(cmd, capture_output=True, text=True, timeout=None, cwd=None, env=None):
            self.commands.append(list(cmd))
            if cmd[:3] == ["docker", "inspect", self.app.DEPLOY_AGENT_CONTAINER] and "{{range" in (cmd[-1] if cmd else ""):
                return _FakeCompletedProcess(0, "\n".join(self.docker_inspect_env_lines), "")
            if cmd[:2] == ["docker", "load"]:
                return _FakeCompletedProcess(0, "Loaded image", "")
            if cmd[:3] == ["docker", "image", "inspect"]:
                return _FakeCompletedProcess(0, self.expected_id, "")
            if cmd[:2] == ["docker", "compose"] and "up" in cmd:
                return _FakeCompletedProcess(self.compose_up_rc, "", "")
            if cmd[0] == "curl":
                idx = min(calls["idx"], len(health_sequence) - 1)
                calls["idx"] += 1
                payload = health_sequence[idx]
                if payload is None:
                    return _FakeCompletedProcess(1, "", "connection refused")
                return _FakeCompletedProcess(0, json.dumps(payload), "")
            return _FakeCompletedProcess(0, "", "")

        return fake

    def _seed_installed(self, tag="8.8.8", role="PRODUCTION_TEST"):
        core = self.app.agent_updater_core()
        core.write_compose_env({"AGENT_IMAGE": f"mesflow-deploy-agent:{tag}", "SERVER_ROLE": role,
                                 "AGENT_BIND_IP": "127.0.0.1", "AGENT_PORT": "8090"})

    # -- vendored-core loading / config wiring --------------------------------
    def test_agent_updater_core_loads_and_points_at_this_host(self):
        core = self.app.agent_updater_core()
        self.assertEqual(core.TARGET_DIR, self.app.DEPLOY_AGENT_HOME)
        self.assertIn("docker/compose.linux.yml", core.COMPOSE_FILES)

    # -- compose layout must preserve an already-DEV host's role ------------
    # Regression coverage for a real incident: a Bootstrap-driven
    # install/update silently flipped a local DEV Deploy Agent to
    # PRODUCTION_TEST because compose.dev.override.yml was never included
    # in the compose file set, even though the host was already running as
    # SERVER_ROLE=DEV. See _agent_compose_layout()/_detect_dev_server_role().
    def test_compose_layout_includes_dev_override_when_role_already_dev(self):
        (self.app.DEPLOY_AGENT_HOME / "docker" / "compose.dev.override.yml").write_text(
            "services: {mesflow-deploy-agent: {}}\n")
        self.app.AGENT_UPDATE_ENV_FILE.write_text("SERVER_ROLE=DEV\n")
        core = self.app.agent_updater_core()
        self.assertIn("docker/compose.dev.override.yml", core.COMPOSE_FILES)

    def test_compose_layout_excludes_dev_override_when_role_production_test(self):
        (self.app.DEPLOY_AGENT_HOME / "docker" / "compose.dev.override.yml").write_text(
            "services: {mesflow-deploy-agent: {}}\n")
        self.app.AGENT_UPDATE_ENV_FILE.write_text("SERVER_ROLE=PRODUCTION_TEST\n")
        core = self.app.agent_updater_core()
        self.assertNotIn("docker/compose.dev.override.yml", core.COMPOSE_FILES)

    def test_compose_layout_falls_back_to_live_container_env_when_no_env_file_yet(self):
        (self.app.DEPLOY_AGENT_HOME / "docker" / "compose.dev.override.yml").write_text(
            "services: {mesflow-deploy-agent: {}}\n")
        self.assertFalse(self.app.AGENT_UPDATE_ENV_FILE.exists())
        self.docker_inspect_env_lines = ["SERVER_ROLE=DEV", "MESFLOW_BUILD_ENABLED=1"]
        with patch("subprocess.run", side_effect=self._fake_run([{}])):
            core = self.app.agent_updater_core()
        self.assertIn("docker/compose.dev.override.yml", core.COMPOSE_FILES)

    def test_compose_layout_never_includes_dev_override_when_file_absent(self):
        # No compose.dev.override.yml in this sandbox at all -- must never
        # be added regardless of the recorded role.
        self.app.AGENT_UPDATE_ENV_FILE.write_text("SERVER_ROLE=DEV\n")
        core = self.app.agent_updater_core()
        self.assertNotIn("docker/compose.dev.override.yml", core.COMPOSE_FILES)

    def test_missing_vendor_file_raises_actionable_error(self):
        (self.app.HOME / "agent_updater_core.py").unlink()
        self.app._agent_core_cache["module"] = None
        self.app._agent_core_cache["error"] = None
        with self.assertRaisesRegex(RuntimeError, "not found"):
            self.app.agent_updater_core()

    # -- update / rollback wrapper glue --------------------------------------
    def test_successful_update_persists_previous_image_for_rollback(self):
        self._seed_installed(tag="8.8.8")
        zip_path, manifest = build_artifact(self.tmp_path, version="9.9.9-docker-runtime")
        self.expected_id = manifest["image_id"]
        health_ok = {"agent_version": "9.9.9-docker-runtime", "server_role": "PRODUCTION_TEST"}
        with patch("subprocess.run", side_effect=self._fake_run([health_ok])), \
             patch.object(self.app, "HEALTH_POLL_TIMEOUT", 5):
            result = self.app.agent_do_update(zip_path.read_bytes(), allow_downgrade=False)
        self.assertEqual(result["status"], "SUCCESS")
        st = self.app.load_state()
        self.assertEqual(st.get("agent_previous_image"), "mesflow-deploy-agent:8.8.8")

    def test_downgrade_rejected_by_default(self):
        self._seed_installed(tag="8.8.8")
        zip_path, _ = build_artifact(self.tmp_path, version="1.0.0-docker-runtime")
        with patch("subprocess.run", side_effect=self._fake_run([{}])):
            with self.assertRaisesRegex(ValueError, "DOWNGRADE_REJECTED"):
                self.app.agent_do_update(zip_path.read_bytes(), allow_downgrade=False)

    def test_concurrent_update_rejected(self):
        self._seed_installed(tag="8.8.8")
        zip_path, _ = build_artifact(self.tmp_path, version="9.9.9-docker-runtime")
        core = self.app.agent_updater_core()
        import fcntl
        core.STATE_DIR.mkdir(parents=True, exist_ok=True)
        held = open(core.STATE_DIR / "update.lock", "w")
        try:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "AGENT_UPDATE_ALREADY_RUNNING"):
                self.app.agent_do_update(zip_path.read_bytes(), allow_downgrade=False)
        finally:
            fcntl.flock(held, fcntl.LOCK_UN)
            held.close()

    def test_bad_zip_rejected(self):
        self._seed_installed()
        bad = self.tmp_path / "bad.zip"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("root/README.txt", "nope")
        with self.assertRaises(ValueError):
            self.app.agent_do_update(bad.read_bytes(), allow_downgrade=False)

    def test_checksum_mismatch_rejected(self):
        self._seed_installed()
        zip_path, _ = build_artifact(self.tmp_path, tamper=True)
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            self.app.agent_do_update(zip_path.read_bytes(), allow_downgrade=False)

    def test_rollback_with_no_previous_image_reports_failed(self):
        self._seed_installed()
        result = self.app.agent_do_rollback()
        self.assertEqual(result["status"], "ROLLBACK_FAILED")

    def test_rollback_after_recorded_update_succeeds(self):
        self._seed_installed(tag="8.8.8")
        zip_path, manifest = build_artifact(self.tmp_path, version="9.9.9-docker-runtime")
        self.expected_id = manifest["image_id"]
        health_ok = {"agent_version": "9.9.9-docker-runtime", "server_role": "PRODUCTION_TEST"}
        with patch("subprocess.run", side_effect=self._fake_run([health_ok])), \
             patch.object(self.app, "HEALTH_POLL_TIMEOUT", 5):
            self.app.agent_do_update(zip_path.read_bytes(), allow_downgrade=False)
        rollback_health = {"agent_version": "8.8.8-docker-runtime", "server_role": "PRODUCTION_TEST"}
        with patch("subprocess.run", side_effect=self._fake_run([rollback_health])), \
             patch.object(self.app, "HEALTH_POLL_TIMEOUT", 5):
            result = self.app.agent_do_rollback()
        self.assertEqual(result["status"], "ROLLED_BACK")

    # -- HTTP layer: bearer-token machine endpoints --------------------------
    def test_updater_health_requires_no_auth(self):
        client = self.app.app.test_client()
        r = client.get("/updater/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])

    def test_updater_status_requires_bearer_token(self):
        client = self.app.app.test_client()
        r = client.get("/updater/status")
        self.assertEqual(r.status_code, 401)

    def test_updater_update_end_to_end_over_http(self):
        self._seed_installed(tag="8.8.8")
        token = self.app.load_state()["agent_updater_token"]
        zip_path, manifest = build_artifact(self.tmp_path, version="9.9.9-docker-runtime")
        self.expected_id = manifest["image_id"]
        health_ok = {"agent_version": "9.9.9-docker-runtime", "server_role": "PRODUCTION_TEST"}
        client = self.app.app.test_client()
        with patch("subprocess.run", side_effect=self._fake_run([health_ok])), \
             patch.object(self.app, "HEALTH_POLL_TIMEOUT", 5):
            r = client.post("/updater/update", data=zip_path.read_bytes(),
                             headers={"Authorization": f"Bearer {token}", "Content-Type": "application/zip"})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["status"], "SUCCESS")

    def test_updater_update_wrong_token_rejected_over_http(self):
        zip_path, _ = build_artifact(self.tmp_path)
        client = self.app.app.test_client()
        r = client.post("/updater/update", data=zip_path.read_bytes(),
                         headers={"Authorization": "Bearer wrong-token", "Content-Type": "application/zip"})
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""MESFlow Bootstrap / Recovery Console.

A small, independent host-level web console for a brand-new Ubuntu server.
It never depends on Docker, MESFlow or the Deploy Agent being up -- its own
job is to prepare the minimum host environment and to own Deploy Agent
lifecycle (install/update/rollback/restart/status/logs), nothing more.

Explicitly NOT this project's job (see bootstrap/AGENTS.md and
reports/SERVER_BOOTSTRAP_RECOVERY.md,
reports/BOOTSTRAP_AGENT_UPDATER_CONSOLIDATION.md): release management, OTA,
QA Center management, Production promotion, or an arbitrary web shell.
Deploy Agent install/update/rollback logic (build, image verification,
compose orchestration) is never re-implemented here: the first-install flow
validates an uploaded installer package and runs its own `install.sh`
exactly as a human operator would over SSH; the update/rollback flow loads
install.sh's vendored, unmodified copy of the former
deploy-agent/updater/updater.py :8099 service for its already-tested logic
(see agent_updater_core() below) instead of forking it.

Stdlib + Flask + waitress only. No psutil/paramiko/docker SDK -- host and
Docker facts are read via /proc and short-timeout subprocess calls to
`docker`/`systemctl`/`ss`, all of which degrade to "unknown" instead of
raising when the tool is missing.
"""
from __future__ import annotations

import fcntl
import hashlib
import io
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from waitress import serve
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import guide_content

BOOTSTRAP_VERSION = "1.3.1"  # 1.3.1: corrects the guide's MESFlow admin-recovery command (reset-admin via
# docker exec, not the unreleased reset-password) -- content-only fix, no route/behavior change
# 1.3.0: adds bin/reset-admin-password (local-only admin password reset) and the
# guide's "Khôi phục truy cập / Quên mật khẩu" section
# 1.2.0: adds the beginner deployment guide (/guide/deployment)
# 1.1.0: Deploy Agent update/rollback consolidated from deploy-agent/updater/ (:8099)

# --------------------------------------------------------------------------
# Configuration (env-overridable; see install.sh / mesflow-bootstrap.env)
# --------------------------------------------------------------------------
HOME = Path(os.environ.get("MESFLOW_BOOTSTRAP_HOME", "/opt/mesflow-bootstrap"))
DATA_DIR = Path(os.environ.get("MESFLOW_BOOTSTRAP_DATA_DIR", "/var/lib/mesflow-bootstrap"))
UPLOAD_DIR = DATA_DIR / "uploads"
LOG_DIR = DATA_DIR / "logs"
STATE_FILE = DATA_DIR / "state.json"
SETUP_TOKEN_FILE = DATA_DIR / "SETUP_TOKEN.txt"
AUDIT_LOG = LOG_DIR / "audit.log"
APP_LOG = LOG_DIR / "bootstrap.log"

BIND_HOST = os.environ.get("MESFLOW_BOOTSTRAP_HOST", "0.0.0.0")
BIND_PORT = int(os.environ.get("MESFLOW_BOOTSTRAP_PORT", "8098"))
SESSION_TIMEOUT_MIN = max(5, int(os.environ.get("MESFLOW_BOOTSTRAP_SESSION_TIMEOUT_MIN", "30")))
MAX_UPLOAD_MB = int(os.environ.get("MESFLOW_BOOTSTRAP_MAX_UPLOAD_MB", "512"))

DEPLOY_AGENT_HOME = Path(os.environ.get("MESFLOW_AGENT_HOME", "/opt/mesflow-deploy-agent"))
DEPLOY_AGENT_DATA_DIR = Path(os.environ.get("MESFLOW_AGENT_DATA_DIR", "/var/lib/mesflow-deploy-agent"))
DEPLOY_AGENT_BIND_IP = os.environ.get("AGENT_BIND_IP", "127.0.0.1")
DEPLOY_AGENT_PORT = int(os.environ.get("AGENT_PORT", "8090"))
DEPLOY_AGENT_HEALTH_URL = f"http://{DEPLOY_AGENT_BIND_IP}:{DEPLOY_AGENT_PORT}/agent/health"
DEPLOY_AGENT_CONTAINER = "mesflow-deploy-agent"
DEPLOY_AGENT_SYSTEMD_UNIT = "mesflow-deploy-agent.service"  # legacy host/venv install
MES_HOME = Path(os.environ.get("MESFLOW_TARGET_HOME", "/opt/mesflow"))

INSTALL_LOCK_FILE = DATA_DIR / "install.lock"
CMD_TIMEOUT = 8
INSTALL_TIMEOUT = int(os.environ.get("MESFLOW_BOOTSTRAP_INSTALL_TIMEOUT", "600"))
HEALTH_POLL_TIMEOUT = int(os.environ.get("MESFLOW_BOOTSTRAP_HEALTH_POLL_TIMEOUT", "60"))

# Deploy Agent update/rollback capability (consolidated from the former
# deploy-agent/updater/ :8099 service -- see
# reports/BOOTSTRAP_AGENT_UPDATER_CONSOLIDATION.md). Bootstrap does not
# re-implement artifact verification/update/rollback: install.sh vendors an
# unmodified copy of deploy-agent/updater/updater.py here and app.py loads
# it for its tested logic, only pointing its config at this host's actual
# Deploy Agent location. That service (port 8099) may still be running on
# this same host during migration -- both are safe to run at once, they
# never touch the same lock/log files.
AGENT_UPDATER_CORE_FILE = HOME / "agent_updater_core.py"
AGENT_UPDATE_ENV_FILE = DATA_DIR / "agent-updater.env"
AGENT_UPDATE_STATE_DIR = DATA_DIR / "agent-updater-state"
AGENT_UPDATE_LOG_FILE = AGENT_UPDATE_STATE_DIR / "updater.log"

for d in (DATA_DIR, UPLOAD_DIR, LOG_DIR, AGENT_UPDATE_STATE_DIR):
    d.mkdir(parents=True, exist_ok=True, mode=0o700)

app = Flask(__name__, template_folder=str(HOME / "templates"), static_folder=str(HOME / "static"))
app.config.update(
    MAX_CONTENT_LENGTH=MAX_UPLOAD_MB * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=SESSION_TIMEOUT_MIN * 60,
)


# --------------------------------------------------------------------------
# State persistence
# --------------------------------------------------------------------------
def _default_state() -> dict:
    return {
        "setup_complete": False,
        "secret_key": secrets.token_hex(32),
        "admin_username": None,
        "admin_password_hash": None,
        "bind_host": BIND_HOST,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def load_state() -> dict:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    state = _default_state()
    save_state(state)
    return state


def save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(STATE_FILE)


STATE = load_state()
app.secret_key = STATE["secret_key"]

# Bearer token for the machine-to-machine /updater/* endpoints (the DEV ->
# target update-push flow). An operator migrating off the old :8099 service
# can set MESFLOW_AGENT_UPDATER_TOKEN to that service's EXISTING token so
# the cutover changes only a URL, not a secret -- "preserve existing secret
# configuration mechanism". Env wins when supplied; otherwise the
# auto-generated value already in state.json (or a fresh one) is kept, so a
# plain reinstall never silently rotates -- and therefore invalidates -- an
# already-configured DEV-side token.
_env_updater_token = os.environ.get("MESFLOW_AGENT_UPDATER_TOKEN", "").strip()
if _env_updater_token and STATE.get("agent_updater_token") != _env_updater_token:
    STATE["agent_updater_token"] = _env_updater_token
    save_state(STATE)
elif not STATE.get("agent_updater_token"):
    STATE["agent_updater_token"] = secrets.token_urlsafe(32)
    save_state(STATE)

if not STATE["setup_complete"] and not SETUP_TOKEN_FILE.is_file():
    token = secrets.token_urlsafe(24)
    SETUP_TOKEN_FILE.write_text(token + "\n", encoding="utf-8")
    SETUP_TOKEN_FILE.chmod(0o600)
    # Printed once to the service's own stdout (systemd journal), which is an
    # operator-only channel reached with `journalctl`/`sudo cat`, not the app
    # log file and never the UI -- matches "do not expose secrets in UI/logs".
    print(f"[mesflow-bootstrap] First run: setup token written to {SETUP_TOKEN_FILE} "
          f"(readable by root only). Use it once at /setup, then it is deleted.", flush=True)


# --------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------
def audit(action: str, detail: str = "", ok: bool = True) -> None:
    user = session.get("username", "-") if session else "-"
    line = json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "remote_addr": request.remote_addr if request else "-",
        "action": action,
        "detail": detail[:2000],
        "ok": ok,
    })
    try:
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def applog(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    try:
        with APP_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def tail_file(path: Path, max_lines: int = 200) -> str:
    if not path.is_file():
        return ""
    try:
        with path.open("rb") as f:
            f.seek(0, io.SEEK_END)
            size = f.tell()
            block = 65536
            data = b""
            while size > 0 and data.count(b"\n") <= max_lines:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
        text = data.decode("utf-8", errors="replace")
        return "\n".join(text.splitlines()[-max_lines:])
    except OSError:
        return "(log unavailable)"


# --------------------------------------------------------------------------
# Auth / CSRF / session
# --------------------------------------------------------------------------
def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def check_csrf() -> bool:
    sent = request.form.get("_csrf", "")
    return bool(sent) and secrets.compare_digest(sent, session.get("_csrf", ""))


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        state = load_state()
        if not state["setup_complete"]:
            return redirect(url_for("setup"))
        if not session.get("username"):
            return redirect(url_for("login", next=request.path))
        last = session.get("_last_seen", 0)
        if time.time() - last > SESSION_TIMEOUT_MIN * 60:
            session.clear()
            flash("Session expired, please sign in again.", "error")
            return redirect(url_for("login"))
        session["_last_seen"] = time.time()
        session.permanent = True
        return fn(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    return {
        "csrf_token": csrf_token,
        "bootstrap_version": BOOTSTRAP_VERSION,
        "current_user": session.get("username"),
    }


# --------------------------------------------------------------------------
# Host facts (stdlib only, all best-effort / degrade to "unknown")
# --------------------------------------------------------------------------
def run(cmd: list[str], timeout: int = CMD_TIMEOUT, env: dict | None = None) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"{cmd[0]}: timed out after {timeout}s"
    except OSError as e:
        return 1, "", str(e)


def primary_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        rc, out, _ = run(["hostname", "-I"])
        return out.split()[0] if rc == 0 and out else "unknown"


def os_release() -> dict:
    info = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                info[k] = v.strip('"')
    except OSError:
        pass
    return info


def is_supported_ubuntu(info: dict) -> bool:
    return info.get("ID") == "ubuntu"


def mem_info() -> dict:
    out = {"total_mb": None, "available_mb": None}
    try:
        vals = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            k, v = line.split(":", 1)
            vals[k] = int(v.strip().split()[0])  # kB
        out["total_mb"] = vals.get("MemTotal", 0) // 1024
        out["available_mb"] = vals.get("MemAvailable", 0) // 1024
    except (OSError, ValueError):
        pass
    return out


def uptime_seconds() -> float | None:
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def human_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def disk_info(path: str = "/") -> dict:
    try:
        total, used, free = shutil.disk_usage(path)
        return {"total_gb": round(total / 1e9, 1), "used_gb": round(used / 1e9, 1), "free_gb": round(free / 1e9, 1)}
    except OSError:
        return {"total_gb": None, "used_gb": None, "free_gb": None}


def docker_state() -> dict:
    rc, out, _ = run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=5)
    if rc != 0:
        return {"installed": shutil.which("docker") is not None, "running": False, "version": None}
    rc2, _, _ = run(["docker", "info"], timeout=5)
    return {"installed": True, "running": rc2 == 0, "version": out or None}


def compose_available() -> bool:
    rc, _, _ = run(["docker", "compose", "version"], timeout=5)
    return rc == 0


def ssh_state() -> dict:
    unit = None
    for candidate in ("ssh", "sshd"):
        rc, out, _ = run(["systemctl", "is-active", candidate], timeout=5)
        if rc == 0 or out in ("active", "inactive", "failed"):
            unit = candidate
            active = out
            break
    else:
        active = "unknown"
    installed = shutil.which("sshd") is not None or Path("/usr/sbin/sshd").exists()
    port = None
    rc, out, _ = run(["ss", "-ltnp"], timeout=5)
    if rc == 0:
        for line in out.splitlines():
            m = re.search(r":(\d+)\s", line)
            if m and "sshd" in line:
                port = int(m.group(1))
                break
    return {"installed": installed, "unit": unit, "active": active == "active", "state": active, "port": port or 22}


def docker_container_state(name: str) -> dict:
    rc, out, _ = run(["docker", "inspect", "--format", "{{.State.Status}}|{{.Config.Image}}", name], timeout=5)
    if rc != 0:
        return {"exists": False, "status": None, "image": None}
    status, _, image = out.partition("|")
    return {"exists": True, "status": status, "image": image or None}


def docker_container_error(name: str) -> str | None:
    """Docker's own recorded failure reason for the container's last start
    attempt (e.g. "...port is already allocated"). Preferred over a live
    listener scan for diagnosis: Bootstrap runs on the host, but a container
    on a bridge network can fail to bind a port Bootstrap's own socket list
    never sees -- Docker's State.Error always reflects what Docker itself
    tried and saw, regardless of network namespace."""
    rc, out, _ = run(["docker", "inspect", "--format", "{{.State.Error}}", name], timeout=5)
    return out.strip() if rc == 0 and out.strip() else None


def http_get_json(url: str, timeout: float = 3.0) -> tuple[bool, dict | str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mesflow-bootstrap"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return True, json.loads(body)
            except json.JSONDecodeError:
                return True, body
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return False, str(e)


def deploy_agent_installed() -> bool:
    return (DEPLOY_AGENT_HOME / "VERSION.txt").is_file() or (DEPLOY_AGENT_HOME / "docker").is_dir()


def deploy_agent_installed_version() -> str | None:
    vf = DEPLOY_AGENT_HOME / "VERSION.txt"
    if vf.is_file():
        try:
            return vf.read_text(encoding="utf-8").strip()
        except OSError:
            return None
    return None


def deploy_agent_runtime() -> dict:
    """Deploy Agent may be running as a Docker container (current, preferred)
    or as a legacy host systemd unit (install_agent.sh). Report whichever is
    actually present; never assume one over the other."""
    docker_c = docker_container_state(DEPLOY_AGENT_CONTAINER)
    if docker_c["exists"]:
        return {"method": "docker", "running": docker_c["status"] == "running", "detail": docker_c["status"]}
    rc, out, _ = run(["systemctl", "is-active", DEPLOY_AGENT_SYSTEMD_UNIT], timeout=5)
    if rc == 0 or out in ("active", "inactive", "failed"):
        return {"method": "systemd", "running": out == "active", "detail": out}
    return {"method": "absent", "running": False, "detail": None}


def deploy_agent_health() -> dict:
    ok, body = http_get_json(DEPLOY_AGENT_HEALTH_URL, timeout=3.0)
    if ok and isinstance(body, dict):
        return {"reachable": True, "healthy": bool(body.get("ok")), "version": body.get("agent_version"), "raw": body}
    return {"reachable": False, "healthy": False, "version": None, "raw": None}


def overview_snapshot() -> dict:
    osr = os_release()
    mem = mem_info()
    disk = disk_info()
    dstate = docker_state()
    sstate = ssh_state()
    installed = deploy_agent_installed()
    runtime = deploy_agent_runtime() if installed else {"method": "absent", "running": False, "detail": None}
    health = deploy_agent_health() if runtime["running"] else {"reachable": False, "healthy": False, "version": None, "raw": None}
    load1, load5, load15 = os.getloadavg() if hasattr(os, "getloadavg") else (None, None, None)
    return {
        "hostname": socket.gethostname(),
        "ip": primary_ip(),
        "os_name": osr.get("PRETTY_NAME", platform.platform()),
        "os_supported": is_supported_ubuntu(osr),
        "cpu_count": os.cpu_count(),
        "load_avg": {"1m": load1, "5m": load5, "15m": load15},
        "mem": mem,
        "disk": disk,
        "uptime": human_uptime(uptime_seconds()),
        "docker": dstate,
        "compose": compose_available() if dstate["running"] else False,
        "ssh": sstate,
        "deploy_agent": {
            "installed": installed,
            "installed_version": deploy_agent_installed_version(),
            "runtime": runtime,
            "health": health,
            "error": docker_container_error(DEPLOY_AGENT_CONTAINER) if runtime["method"] == "docker" else None,
            "rollback_available": bool(load_state().get("agent_previous_image")),
            "updater_core_available": AGENT_UPDATER_CORE_FILE.is_file(),
        },
    }


# --------------------------------------------------------------------------
# Safe, allowlisted diagnostic commands (bounded output, timeout, audited)
# --------------------------------------------------------------------------
SAFE_COMMANDS: dict[str, list[str]] = {
    "uptime": ["uptime"],
    "free": ["free", "-h"],
    "df": ["df", "-h"],
    "ip_addr": ["ip", "addr"],
    "ss_listen": ["ss", "-ltnp"],
    "systemd_failed": ["systemctl", "--failed", "--no-pager"],
    "docker_ps": ["docker", "ps"],
    "docker_ps_all": ["docker", "ps", "-a"],
    "docker_images": ["docker", "images"],
    "docker_compose_ls": ["docker", "compose", "ls"],
}
MAX_OUTPUT_CHARS = 20000


def run_safe_command(key: str) -> dict:
    cmd = SAFE_COMMANDS.get(key)
    if not cmd:
        return {"ok": False, "output": f"Unknown command: {key}"}
    rc, out, err = run(cmd, timeout=CMD_TIMEOUT)
    text = (out + ("\n" + err if err else "")).strip()
    truncated = len(text) > MAX_OUTPUT_CHARS
    if truncated:
        text = text[:MAX_OUTPUT_CHARS] + "\n... (truncated)"
    audit("safe_command", f"{key} rc={rc}")
    return {"ok": rc == 0, "rc": rc, "output": text or "(no output)"}


# --------------------------------------------------------------------------
# Docker / service actions (scoped allowlist, confirmation required)
# --------------------------------------------------------------------------
ACTIONABLE_CONTAINERS = {DEPLOY_AGENT_CONTAINER}  # deliberately not extensible from the UI


def docker_container_action(name: str, action: str) -> dict:
    if name not in ACTIONABLE_CONTAINERS:
        return {"ok": False, "output": "Container not in the allowed action list."}
    if action not in ("start", "restart", "stop"):
        return {"ok": False, "output": "Unsupported action."}
    rc, out, err = run(["docker", action, name], timeout=30)
    audit("docker_action", f"{action} {name} rc={rc}", ok=rc == 0)
    return {"ok": rc == 0, "output": (out + "\n" + err).strip()}


def systemd_action(unit: str, action: str) -> dict:
    allowed_units = {DEPLOY_AGENT_SYSTEMD_UNIT: {"start", "restart", "stop"}, "ssh": {"start"}, "sshd": {"start"}}
    if unit not in allowed_units or action not in allowed_units[unit]:
        return {"ok": False, "output": "Unit/action not in the allowed list."}
    rc, out, err = run(["systemctl", action, unit], timeout=20)
    audit("systemd_action", f"{action} {unit} rc={rc}", ok=rc == 0)
    return {"ok": rc == 0, "output": (out + "\n" + err).strip()}


# --------------------------------------------------------------------------
# Deploy Agent install / recovery
#
# Bootstrap never re-implements Deploy Agent build/rollback logic. The
# uploaded package is the real installer package produced by
# deploy-agent/package_installer.sh (top-level install.sh +
# payload/mesflow-deploy-agent/{agent.py,VERSION.txt,docker/...}) -- the
# same artifact a human would run over SSH. Bootstrap only validates it,
# guards against accidental downgrade, runs it, and polls health itself.
# --------------------------------------------------------------------------
class PackageError(Exception):
    pass


def _safe_zip_extractall(zf: zipfile.ZipFile, dest: Path) -> None:
    dest_resolved = dest.resolve()
    for member in zf.infolist():
        target = (dest / member.filename).resolve()
        if not str(target).startswith(str(dest_resolved) + os.sep) and target != dest_resolved:
            raise PackageError(f"Unsafe path in package: {member.filename}")
    zf.extractall(dest)


def validate_and_stage_package(upload_path: Path, sha256_expected: str | None) -> dict:
    if sha256_expected:
        h = hashlib.sha256()
        with upload_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        actual = h.hexdigest()
        if not secrets.compare_digest(actual, sha256_expected.strip().lower()):
            raise PackageError(f"SHA256 mismatch: expected {sha256_expected}, got {actual}")

    if not zipfile.is_zipfile(upload_path):
        raise PackageError("Not a valid ZIP file.")

    stage_dir = Path(tempfile.mkdtemp(prefix="agent-install-", dir=str(UPLOAD_DIR)))
    with zipfile.ZipFile(upload_path) as zf:
        _safe_zip_extractall(zf, stage_dir)

    # Structure: exactly one top-level dir containing install.sh + payload/mesflow-deploy-agent/
    entries = [p for p in stage_dir.iterdir()]
    root = entries[0] if len(entries) == 1 and entries[0].is_dir() else stage_dir
    install_script = root / "install.sh"
    payload_dir = root / "payload" / "mesflow-deploy-agent"
    version_file = payload_dir / "VERSION.txt"
    agent_py = payload_dir / "agent.py"
    if not (install_script.is_file() and version_file.is_file() and agent_py.is_file()):
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise PackageError(
            "Package does not match the expected Deploy Agent installer structure "
            "(install.sh + payload/mesflow-deploy-agent/{agent.py,VERSION.txt})."
        )
    version = version_file.read_text(encoding="utf-8").strip()
    if not version:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise PackageError("VERSION.txt is empty.")
    return {"stage_dir": stage_dir, "install_root": root, "install_script": install_script, "version": version}


_SEMVER_RE = re.compile(r"(\d+)")


def version_key(v: str):
    return tuple(int(x) for x in _SEMVER_RE.findall(v)) or (0,)


def run_install_package(install_root: Path, install_script: Path) -> dict:
    # Held for the whole install (not just a point-in-time check) so a second
    # upload while one is running is rejected instead of racing it.
    lock_fd = open(INSTALL_LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_fd.close()
        return {"ok": False, "output": "Another install/recovery is already in progress."}
    try:
        install_script.chmod(0o755)
        env = dict(os.environ)
        env.setdefault("AGENT_BIND_IP", DEPLOY_AGENT_BIND_IP)
        env.setdefault("AGENT_PORT", str(DEPLOY_AGENT_PORT))
        rc, out, err = run(["bash", str(install_script)], timeout=INSTALL_TIMEOUT, env=env)
        text = (out + "\n" + err).strip()
        return {"ok": rc == 0, "rc": rc, "output": text[-MAX_OUTPUT_CHARS:]}
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def poll_deploy_agent_health(timeout_s: int = HEALTH_POLL_TIMEOUT) -> dict:
    deadline = time.time() + timeout_s
    last = {"reachable": False, "healthy": False, "version": None, "raw": None}
    while time.time() < deadline:
        last = deploy_agent_health()
        if last["healthy"]:
            return last
        time.sleep(2)
    return last


# --------------------------------------------------------------------------
# Deploy Agent update / rollback (consolidated from deploy-agent/updater/)
#
# Bootstrap loads install.sh's vendored, UNMODIFIED copy of
# deploy-agent/updater/updater.py for its already-tested artifact
# verification (checksums, image-id, unsafe-path guard), update/rollback
# state machine, downgrade guard and update lock -- see
# reports/BOOTSTRAP_AGENT_UPDATER_CONSOLIDATION.md. Only the module's
# config attributes are overridden to point at this host's real Deploy
# Agent location, the same technique deploy-agent/tests/test_updater.py
# itself uses to test the file in isolation.
# --------------------------------------------------------------------------
_agent_core_cache: dict = {"module": None, "error": None}


def _detect_dev_server_role() -> str:
    """Best-effort, read-only SERVER_ROLE lookup for THIS host's Deploy
    Agent, so _agent_compose_layout() can preserve an existing DEV install
    instead of silently falling back to compose.linux.yml's own
    PRODUCTION_TEST default. Checked in order: the Bootstrap-owned update
    env file (already captured by a prior _ensure_agent_update_env() call,
    if any), else the live container's real env (same `docker inspect`
    technique _ensure_agent_update_env() itself uses). Never touches Docker
    if the env file already answers the question -- keeps the common case
    (repeat update/rollback on an already-known host) free of any docker
    call, and callers only invoke this after already confirming
    compose.dev.override.yml exists, so a brand-new/PRODUCTION_TEST host
    with no such file never reaches here at all."""
    if AGENT_UPDATE_ENV_FILE.is_file():
        for line in AGENT_UPDATE_ENV_FILE.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k == "SERVER_ROLE":
                return v.strip()
    rc, out, _ = run(["docker", "inspect", DEPLOY_AGENT_CONTAINER, "--format",
                       "{{range .Config.Env}}{{println .}}{{end}}"], timeout=5)
    if rc == 0:
        for line in out.splitlines():
            k, _, v = line.partition("=")
            if k == "SERVER_ROLE":
                return v.strip()
    return ""


def _agent_compose_layout() -> tuple[list[str], Path]:
    """Mirrors deploy-agent/updater/install-updater.sh's own layout
    detection. Bootstrap keeps its own env file (AGENT_UPDATE_ENV_FILE)
    rather than writing into Deploy Agent's tree -- DEPLOY_AGENT_HOME's own
    compose/.env files are only ever read here, never edited.

    Always includes compose.bootstrap.override.yml (port binding) when
    present. Also includes compose.dev.override.yml when this host's
    Deploy Agent is already running as SERVER_ROLE=DEV -- without this, an
    update/rollback silently drops the DEV role/build-enabled/workspace
    bind-mount back to compose.linux.yml's PRODUCTION_TEST default. This is
    the same failure mode that made deploy-agent/installer/install.sh (the
    /install-agent first-install/repair path) flip a real local DEV host to
    PRODUCTION_TEST -- see docs/history or the incident report for details.
    """
    if (DEPLOY_AGENT_HOME / "compose.yml").is_file():
        return ["compose.yml"], AGENT_UPDATE_ENV_FILE
    files = ["docker/compose.linux.yml"]
    override = DEPLOY_AGENT_HOME / "docker" / "compose.bootstrap.override.yml"
    if override.is_file():
        files.append("docker/compose.bootstrap.override.yml")
    dev_override = DEPLOY_AGENT_HOME / "docker" / "compose.dev.override.yml"
    if dev_override.is_file() and _detect_dev_server_role() == "DEV":
        files.append("docker/compose.dev.override.yml")
    return files, AGENT_UPDATE_ENV_FILE


def agent_updater_core():
    """Lazily load+cache the vendored updater core module. Raises
    RuntimeError with an operator-actionable message if install.sh never
    vendored it (e.g. Bootstrap installed standalone, without the deploy-agent/
    sibling present) -- callers turn that into a flashed error, never a 500."""
    if _agent_core_cache["module"] is not None:
        return _agent_core_cache["module"]
    if _agent_core_cache["error"] is not None:
        raise RuntimeError(_agent_core_cache["error"])
    if not AGENT_UPDATER_CORE_FILE.is_file():
        _agent_core_cache["error"] = (
            f"{AGENT_UPDATER_CORE_FILE} not found. Re-run install.sh from a full workspace "
            f"checkout (it vendors deploy-agent/updater/updater.py) to enable Update/Rollback."
        )
        raise RuntimeError(_agent_core_cache["error"])
    import importlib.util
    spec = importlib.util.spec_from_file_location("mesflow_bootstrap_agent_updater_core", AGENT_UPDATER_CORE_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STATE_DIR = AGENT_UPDATE_STATE_DIR
    module.LOG_FILE = AGENT_UPDATE_LOG_FILE
    module.TARGET_DIR = DEPLOY_AGENT_HOME
    module.COMPOSE_FILES, module.ENV_FILE = _agent_compose_layout()
    module.HEALTH_POLL_TIMEOUT = HEALTH_POLL_TIMEOUT
    _agent_core_cache["module"] = module
    return module


def _ensure_agent_update_env() -> None:
    """Bootstrap-owned env file the vendored core's compose_up()/compose_env()
    read/write (AGENT_IMAGE, SERVER_ROLE, ...). Bootstrapped once from the
    currently-running container's actual environment -- same technique as
    install-updater.sh -- then left alone; a rollback/update only ever
    changes AGENT_IMAGE within it."""
    if AGENT_UPDATE_ENV_FILE.is_file():
        return
    env: dict[str, str] = {}
    rc, out, _ = run(["docker", "inspect", DEPLOY_AGENT_CONTAINER, "--format",
                       "{{range .Config.Env}}{{println .}}{{end}}"], timeout=5)
    if rc == 0:
        keep = {"AGENT_IMAGE", "SERVER_ROLE", "MESFLOW_BUILD_ENABLED", "MESFLOW_WORKSPACE_ROOT"}
        for line in out.splitlines():
            k, _, v = line.partition("=")
            if k in keep:
                env[k] = v
    if "AGENT_IMAGE" not in env:
        rc2, image_id, _ = run(["docker", "inspect", DEPLOY_AGENT_CONTAINER, "--format", "{{.Image}}"], timeout=5)
        if rc2 == 0 and image_id:
            env["AGENT_IMAGE"] = image_id
    env.setdefault("AGENT_BIND_IP", DEPLOY_AGENT_BIND_IP)
    env.setdefault("AGENT_PORT", str(DEPLOY_AGENT_PORT))
    env.setdefault("MESFLOW_AGENT_DATA_DIR", str(DEPLOY_AGENT_DATA_DIR))
    AGENT_UPDATE_ENV_FILE.write_text("\n".join(f"{k}={v}" for k, v in env.items()) + "\n", encoding="utf-8")
    AGENT_UPDATE_ENV_FILE.chmod(0o600)


def agent_do_update(zip_bytes: bytes, allow_downgrade: bool) -> dict:
    """Raises (ValueError/RuntimeError) on pre-mutation rejection (bad
    package, checksum mismatch, downgrade, concurrent update already
    running); returns a result dict with status SUCCESS/ROLLED_BACK/
    ROLLBACK_FAILED once a cutover was actually attempted."""
    core = agent_updater_core()
    _ensure_agent_update_env()
    # Recorded *before* mutating so a later manual Rollback always has a
    # target, even across a Bootstrap restart in between.
    prev = core.current_image_ref()
    if prev:
        st = load_state()
        st["agent_previous_image"] = prev
        save_state(st)
    return core.do_update(zip_bytes, allow_downgrade=allow_downgrade)


def agent_do_rollback(reason: str = "MANUAL_ROLLBACK") -> dict:
    core = agent_updater_core()
    _ensure_agent_update_env()
    prev = load_state().get("agent_previous_image") or ""
    if not prev:
        return {"status": "ROLLBACK_FAILED", "reason": reason, "detail": "no previous image recorded by Bootstrap"}
    prev_role = core.compose_env().get("SERVER_ROLE", "")
    return core._rollback(prev, prev_role, reason)


def _agent_bearer_ok() -> bool:
    token = load_state().get("agent_updater_token") or ""
    if not token:
        return False
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    return secrets.compare_digest(auth[7:].strip(), token)


# --------------------------------------------------------------------------
# Routes -- public
# --------------------------------------------------------------------------
@app.get("/health")
def health():
    """Bootstrap's own liveness. Must never require Docker/Deploy Agent/MESFlow."""
    return jsonify({
        "ok": True,
        "service": "mesflow-bootstrap",
        "version": BOOTSTRAP_VERSION,
        "setup_complete": load_state()["setup_complete"],
        "hostname": socket.gethostname(),
        "uptime": human_uptime(uptime_seconds()),
    })


@app.route("/setup", methods=["GET", "POST"])
def setup():
    state = load_state()
    if state["setup_complete"]:
        return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        if not check_csrf():
            error = "Invalid or expired form, please retry."
        else:
            token = request.form.get("token", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")
            real_token = SETUP_TOKEN_FILE.read_text(encoding="utf-8").strip() if SETUP_TOKEN_FILE.is_file() else None
            if not real_token:
                error = "Setup token already used or missing. Re-run install.sh to regenerate it."
            elif not secrets.compare_digest(token, real_token):
                error = "Setup token is incorrect."
            elif len(username) < 3:
                error = "Username must be at least 3 characters."
            elif len(password) < 10:
                error = "Password must be at least 10 characters."
            elif password != confirm:
                error = "Passwords do not match."
            else:
                state["admin_username"] = username
                state["admin_password_hash"] = generate_password_hash(password)
                state["setup_complete"] = True
                save_state(state)
                SETUP_TOKEN_FILE.unlink(missing_ok=True)
                audit("setup_complete", f"admin={username}")
                flash("Admin account created. Please sign in.", "success")
                return redirect(url_for("login"))
    return render_template("setup.html", error=error, token_exists=SETUP_TOKEN_FILE.is_file())


@app.route("/login", methods=["GET", "POST"])
def login():
    state = load_state()
    if not state["setup_complete"]:
        return redirect(url_for("setup"))
    error = None
    if request.method == "POST":
        if not check_csrf():
            error = "Invalid or expired form, please retry."
        else:
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if username == state.get("admin_username") and state.get("admin_password_hash") and \
                    check_password_hash(state["admin_password_hash"], password):
                session.clear()
                session["username"] = username
                session["_last_seen"] = time.time()
                session["_csrf"] = secrets.token_hex(16)
                session.permanent = True
                audit("login", "success")
                nxt = request.args.get("next") or url_for("overview")
                return redirect(nxt)
            error = "Invalid username or password."
            audit("login", f"failed username={username}", ok=False)
    return render_template("login.html", error=error)


@app.post("/logout")
@login_required
def logout():
    audit("logout")
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def index():
    return redirect(url_for("overview"))


# --------------------------------------------------------------------------
# Routes -- authenticated pages
# --------------------------------------------------------------------------
@app.get("/overview")
@login_required
def overview():
    return render_template("overview.html", snap=overview_snapshot())


@app.route("/install-agent", methods=["GET", "POST"])
@login_required
def install_agent():
    result = None
    if request.method == "POST":
        if not check_csrf():
            flash("Invalid or expired form, please retry.", "error")
            return redirect(url_for("install_agent"))
        f = request.files.get("package")
        sha256_expected = request.form.get("sha256", "").strip() or None
        allow_downgrade = request.form.get("allow_downgrade") == "on"
        if not f or not f.filename:
            flash("Choose a Deploy Agent installer ZIP to upload.", "error")
            return redirect(url_for("install_agent"))
        safe_name = secure_filename(f.filename) or "package.zip"
        upload_path = UPLOAD_DIR / f"{int(time.time())}_{safe_name}"
        f.save(upload_path)
        audit("agent_upload", f"file={safe_name} size={upload_path.stat().st_size}")
        stage = None
        try:
            stage = validate_and_stage_package(upload_path, sha256_expected)
            new_v = stage["version"]
            cur_v = deploy_agent_installed_version()
            if cur_v and not allow_downgrade and version_key(new_v) < version_key(cur_v):
                raise PackageError(f"Refusing downgrade: installed={cur_v}, uploaded={new_v}. "
                                    f"Check 'allow downgrade' to override explicitly.")
            audit("agent_install_start", f"version={new_v} previous={cur_v}")
            run_result = run_install_package(stage["install_root"], stage["install_script"])
            health = poll_deploy_agent_health()
            passed = run_result["ok"] and health["healthy"]
            result = {
                "version": new_v,
                "previous_version": cur_v,
                "run": run_result,
                "health": health,
                "pass": passed,
            }
            audit("agent_install_result", f"version={new_v} pass={passed}", ok=passed)
        except PackageError as e:
            audit("agent_install_rejected", str(e), ok=False)
            flash(str(e), "error")
        finally:
            if stage:
                shutil.rmtree(stage["stage_dir"], ignore_errors=True)
            upload_path.unlink(missing_ok=True)
    return render_template("install_agent.html", result=result, snap=overview_snapshot())


@app.route("/agent/update", methods=["GET", "POST"])
@login_required
def agent_update_page():
    """In-place Deploy Agent update: the AGENT_UPDATE_<version>.zip format
    (agent-release.json + image tar + checksums.txt), the same artifact DEV
    already builds via deploy-agent/scripts/build-agent-release.sh and the
    same one the retiring :8099 service accepts. Distinct from
    /install-agent's first-install/source-rebuild package -- see
    reports/BOOTSTRAP_AGENT_UPDATER_CONSOLIDATION.md."""
    result = None
    core_error = None
    try:
        agent_updater_core()
    except RuntimeError as e:
        core_error = str(e)
    if request.method == "POST":
        if not check_csrf():
            flash("Invalid or expired form, please retry.", "error")
            return redirect(url_for("agent_update_page"))
        f = request.files.get("package")
        sha256_expected = request.form.get("sha256", "").strip() or None
        allow_downgrade = request.form.get("allow_downgrade") == "on"
        if not f or not f.filename:
            flash("Choose an AGENT_UPDATE_<version>.zip to upload.", "error")
            return redirect(url_for("agent_update_page"))
        safe_name = secure_filename(f.filename) or "update.zip"
        upload_path = UPLOAD_DIR / f"{int(time.time())}_{safe_name}"
        f.save(upload_path)
        audit("agent_update_upload", f"file={safe_name} size={upload_path.stat().st_size}")
        try:
            data = upload_path.read_bytes()
            if sha256_expected:
                actual = hashlib.sha256(data).hexdigest()
                if not secrets.compare_digest(actual, sha256_expected.strip().lower()):
                    raise PackageError(f"SHA256 mismatch: expected {sha256_expected}, got {actual}")
            audit("agent_update_start", f"allow_downgrade={allow_downgrade}")
            result = agent_do_update(data, allow_downgrade)
            audit("agent_update_result", json.dumps(result)[:1000], ok=result.get("status") == "SUCCESS")
        except (PackageError, ValueError, RuntimeError) as e:
            audit("agent_update_rejected", str(e), ok=False)
            flash(str(e), "error")
        finally:
            upload_path.unlink(missing_ok=True)
    return render_template("agent_update.html", result=result, core_error=core_error, snap=overview_snapshot())


@app.post("/agent/rollback")
@login_required
def agent_rollback_route():
    if not check_csrf() or request.form.get("confirm") != "yes":
        flash("Rollback requires explicit confirmation.", "error")
        return redirect(url_for("overview"))
    try:
        result = agent_do_rollback()
        ok = result.get("status") == "ROLLED_BACK"
        audit("agent_rollback", json.dumps(result)[:1000], ok=ok)
        flash(f"Rollback: {result.get('status')} -- {result.get('detail', '')}".strip(" -"),
              "success" if ok else "error")
    except RuntimeError as e:
        audit("agent_rollback_error", str(e), ok=False)
        flash(str(e), "error")
    return redirect(url_for("overview"))


@app.get("/agent/logs")
@login_required
def agent_logs_page():
    updater_log = tail_file(AGENT_UPDATE_LOG_FILE, 300)
    rc, out, err = run(["docker", "logs", "--tail", "200", DEPLOY_AGENT_CONTAINER], timeout=10)
    container_log = (out + "\n" + err).strip() if rc == 0 else f"(unavailable: {err or 'container not found'})"
    return render_template("agent_logs.html", updater_log=updater_log, container_log=container_log)


# --------------------------------------------------------------------------
# Routes -- machine-to-machine (bearer token, wire-compatible with the
# retiring deploy-agent/updater/ :8099 service). Preserved on purpose so
# the existing DEV -> target push flow (deploy-agent/agent.py's
# _push_agent_update) can cut over by changing only its configured URL from
# http://target:8099 to http://target:8098 -- same env var names
# (MESFLOW_{PRODUCTION_TEST,PRODUCTION}_AGENT_UPDATER_URL/TOKEN), same
# path, same header/body contract, no code change and no credential
# hardcoded here. Never session/CSRF-gated -- the bearer token is this
# endpoint's whole auth+anti-forgery story, exactly as it was on :8099.
# --------------------------------------------------------------------------
@app.get("/updater/health")
def updater_health():
    return jsonify({"ok": True, "service": "mesflow-bootstrap", "updater_version": BOOTSTRAP_VERSION})


@app.get("/updater/status")
def updater_status():
    if not _agent_bearer_ok():
        return jsonify({"ok": False, "error": "AUTH_REQUIRED"}), 401
    try:
        core = agent_updater_core()
        _ensure_agent_update_env()
        env = core.compose_env()
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "target_dir": str(DEPLOY_AGENT_HOME), "agent_image": env.get("AGENT_IMAGE", ""),
                     "server_role": env.get("SERVER_ROLE", ""), "build_enabled": env.get("MESFLOW_BUILD_ENABLED", "")})


@app.post("/updater/update")
def updater_update_remote():
    if not _agent_bearer_ok():
        return jsonify({"ok": False, "error": "AUTH_REQUIRED"}), 401
    length = request.content_length or 0
    if length <= 0:
        return jsonify({"ok": False, "error": "INVALID_CONTENT_LENGTH"}), 400
    body = request.get_data()
    allow_downgrade = request.headers.get("X-MESFlow-Allow-Downgrade", "").strip().lower() in {"1", "true", "yes"}
    audit("agent_remote_update_start", f"bytes={len(body)} allow_downgrade={allow_downgrade}")
    try:
        result = agent_do_update(body, allow_downgrade)
    except Exception as ex:
        audit("agent_remote_update_rejected", f"{type(ex).__name__}: {ex}", ok=False)
        return jsonify({"ok": False, "error": f"{type(ex).__name__}: {ex}"}), 409
    ok = result.get("status") == "SUCCESS"
    audit("agent_remote_update_result", json.dumps(result)[:1000], ok=ok)
    return jsonify({"ok": ok, **result}), 200


@app.get("/docker")
@login_required
def docker_page():
    dstate = docker_state()
    ps = run_safe_command("docker_ps") if dstate["running"] else {"ok": False, "output": "Docker is not running."}
    ps_all = run_safe_command("docker_ps_all") if dstate["running"] else {"ok": False, "output": ""}
    images = run_safe_command("docker_images") if dstate["running"] else {"ok": False, "output": ""}
    compose_ls = run_safe_command("docker_compose_ls") if dstate["running"] else {"ok": False, "output": ""}
    return render_template("docker.html", docker=dstate, ps=ps, ps_all=ps_all, images=images, compose_ls=compose_ls,
                            container=docker_container_state(DEPLOY_AGENT_CONTAINER))


@app.post("/docker/container/<name>/<action>")
@login_required
def docker_container_action_route(name, action):
    if not check_csrf() or request.form.get("confirm") != "yes":
        flash("Action requires explicit confirmation.", "error")
        return redirect(url_for("docker_page"))
    result = docker_container_action(name, action)
    flash(f"{action} {name}: {'OK' if result['ok'] else 'FAILED'}", "success" if result["ok"] else "error")
    return redirect(url_for("docker_page"))


@app.get("/services")
@login_required
def services_page():
    snap = overview_snapshot()
    return render_template("services.html", snap=snap)


@app.post("/services/action")
@login_required
def services_action():
    if not check_csrf() or request.form.get("confirm") != "yes":
        flash("Action requires explicit confirmation.", "error")
        return redirect(url_for("services_page"))
    unit = request.form.get("unit", "")
    action = request.form.get("action", "")
    result = systemd_action(unit, action)
    flash(f"{action} {unit}: {'OK' if result['ok'] else 'FAILED'}", "success" if result["ok"] else "error")
    return redirect(url_for("services_page"))


@app.get("/logs")
@login_required
def logs_page():
    return render_template("logs.html", app_log=tail_file(APP_LOG, 300), audit_log=tail_file(AUDIT_LOG, 300))


@app.route("/commands", methods=["GET", "POST"])
@login_required
def commands_page():
    result = None
    selected = None
    if request.method == "POST":
        if not check_csrf():
            flash("Invalid or expired form, please retry.", "error")
        else:
            selected = request.form.get("key", "")
            result = run_safe_command(selected)
    return render_template("commands.html", commands=SAFE_COMMANDS.keys(), result=result, selected=selected)


@app.get("/guide/deployment")
@login_required
def guide_deployment():
    """Beginner-friendly deployment guide. Pure documentation -- reads no
    live state and performs no action, so it's safe to load even when
    Docker/Deploy Agent/MESFlow are all down. Content lives in
    guide_content.py (single source of truth shared with
    docs/MESFLOW_SERVER_DEPLOYMENT_GUIDE.md -- see
    scripts/generate_guide_doc.py)."""
    return render_template(
        "guide_deployment.html",
        guide_version=guide_content.GUIDE_VERSION,
        architecture_diagram=guide_content.ARCHITECTURE_DIAGRAM,
        architecture_explain=guide_content.ARCHITECTURE_EXPLAIN,
        server_role=guide_content.SERVER_ROLE,
        steps=guide_content.STEPS,
        failures=guide_content.FAILURES,
        recovery_access=guide_content.RECOVERY_ACCESS,
        recovery_access_env_warning=guide_content.RECOVERY_ACCESS_ENV_WARNING,
        mesflow_admin_password_warning=guide_content.MESFLOW_ADMIN_PASSWORD_WARNING,
        recovery_access_cli_fallback=guide_content.RECOVERY_ACCESS_CLI_FALLBACK,
        emergency_access_matrix=guide_content.EMERGENCY_ACCESS_MATRIX,
        lost_ssh_note=guide_content.LOST_SSH_NOTE,
        recovery_security_warnings=guide_content.RECOVERY_SECURITY_WARNINGS,
        recovery_tree=guide_content.RECOVERY_TREE,
        checklist_general=guide_content.CHECKLIST_GENERAL,
        checklist_production=guide_content.CHECKLIST_PRODUCTION,
        glossary=guide_content.GLOSSARY,
    )


def main():
    applog(f"mesflow-bootstrap {BOOTSTRAP_VERSION} starting on {BIND_HOST}:{BIND_PORT}")
    serve(app, host=BIND_HOST, port=BIND_PORT)


if __name__ == "__main__":
    main()

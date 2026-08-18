#!/usr/bin/env python3
"""Local-only Bootstrap admin credential reset.

Run via the sibling wrapper `bootstrap/bin/reset-admin-password` (root/sudo,
on the server itself, over SSH) -- never as a web route. An operator who is
locked out of Bootstrap by definition cannot use a route on the service
they are locked out of, so this deliberately requires the same local
root/sudo access `install.sh` already requires, nothing more.

Rewrites only `admin_username`/`admin_password_hash` in Bootstrap's real
`state.json`. Reuses the exact same layout, the atomic tmp-file-then-
`replace()` write pattern, and the audit-log line format that
`bootstrap/app.py`'s own `load_state()`/`save_state()`/`audit()` already
use, instead of inventing a second state format. Never touches
`secret_key`, `setup_complete`, `agent_updater_token`, or anything under
`/var/lib/mesflow-deploy-agent`.

No restart is required: `bootstrap/app.py`'s `/login` route calls
`load_state()` fresh on every request rather than trusting a cached
in-memory copy, so a password changed here takes effect on the very next
login attempt. (Restarting `mesflow-bootstrap` afterward is harmless if you
want to be extra sure, just unnecessary.)
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Pure, testable core -- no argparse/getpass/root-check here, so tests can
# call this directly without a TTY or root.
# --------------------------------------------------------------------------
class ResetError(Exception):
    """Raised for any expected failure (bad input, missing setup, ...).
    Caught by main() and turned into a clean error message -- never a
    traceback for an operator already having a bad day."""


def state_file_for(data_dir: Path) -> Path:
    return data_dir / "state.json"


def audit_log_for(data_dir: Path) -> Path:
    return data_dir / "logs" / "audit.log"


def load_state(data_dir: Path) -> dict:
    sf = state_file_for(data_dir)
    if not sf.is_file():
        raise ResetError(
            f"{sf} not found -- Bootstrap has never completed initial setup on this host. "
            f"This script only resets an EXISTING admin account; complete /setup first "
            f"(see bootstrap/README.md: sudo cat {data_dir}/SETUP_TOKEN.txt)."
        )
    try:
        return json.loads(sf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResetError(f"could not read/parse {sf}: {exc}") from exc


def save_state(data_dir: Path, state: dict) -> None:
    sf = state_file_for(data_dir)
    tmp = sf.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(sf)


def append_audit(data_dir: Path, action: str, detail: str) -> None:
    log = audit_log_for(data_dir)
    log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with log.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} OK {action} {detail}\n")
    try:
        log.chmod(0o600)
    except OSError:
        pass


def validate_username(username: str) -> str:
    username = (username or "").strip()
    if len(username) < 3:
        raise ResetError("username must be at least 3 characters.")
    return username


def validate_password(password: str, confirm: str) -> str:
    if len(password) < 10:
        raise ResetError("password must be at least 10 characters.")
    if password != confirm:
        raise ResetError("password confirmation does not match.")
    return password


def perform_reset(data_dir: Path, generate_password_hash, *, new_username: str | None,
                   password: str, confirm: str) -> dict:
    """The actual state mutation. `generate_password_hash` is injected
    (rather than imported at module scope) so this stays importable/
    testable without werkzeug on the host's bare system python3 -- only the
    CLI entry point below needs it, from the venv."""
    state = load_state(data_dir)
    if not state.get("setup_complete"):
        raise ResetError(
            "Bootstrap has not completed initial setup on this host yet. Use /setup with "
            "SETUP_TOKEN.txt for first-time provisioning -- this script is only for an "
            "EXISTING admin account whose password was forgotten."
        )
    username = validate_username(new_username if new_username is not None else state.get("admin_username") or "")
    validate_password(password, confirm)

    other_keys_before = {k: v for k, v in state.items() if k not in ("admin_username", "admin_password_hash")}

    state["admin_username"] = username
    state["admin_password_hash"] = generate_password_hash(password)
    save_state(data_dir, state)
    append_audit(data_dir, "admin_password_reset",
                 f"admin={username} via bin/reset-admin-password (local root)")

    other_keys_after = {k: v for k, v in state.items() if k not in ("admin_username", "admin_password_hash")}
    assert other_keys_before == other_keys_after, "reset touched fields beyond admin_username/admin_password_hash"
    return state


# --------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="reset-admin-password",
        description="Reset the Bootstrap admin account's password (local/root only, run on the server itself).",
    )
    parser.add_argument("--username", default=None,
                         help="Change the admin username too (optional; default: keep the existing one).")
    parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation prompt.")
    args = parser.parse_args(argv)

    if os.name != "nt" and os.geteuid() != 0:
        print("ERROR: run as root: sudo /opt/mesflow-bootstrap/bin/reset-admin-password", file=sys.stderr)
        return 1

    try:
        from werkzeug.security import generate_password_hash
    except ImportError:
        print("ERROR: werkzeug not importable under this interpreter. Run via the wrapper script "
              "(bin/reset-admin-password), which invokes the Bootstrap venv's python3 for you.",
              file=sys.stderr)
        return 1

    data_dir = Path(os.environ.get("MESFLOW_BOOTSTRAP_DATA_DIR", "/var/lib/mesflow-bootstrap"))

    try:
        state = load_state(data_dir)
    except ResetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    current_username = state.get("admin_username") or "(none yet)"
    print(f"Bootstrap admin hiện tại trên host này: {current_username}")
    target_username = args.username if args.username else current_username

    if not args.yes:
        confirm = input(f"Đặt lại mật khẩu cho tài khoản '{target_username}' trên host này? [y/N] ").strip().lower()
        if confirm != "y":
            print("Đã huỷ, không thay đổi gì.")
            return 1

    password = getpass.getpass("Mật khẩu mới (>= 10 ký tự, không hiện lên màn hình): ")
    confirm_password = getpass.getpass("Nhập lại mật khẩu mới: ")

    try:
        state = perform_reset(
            data_dir, generate_password_hash,
            new_username=args.username, password=password, confirm=confirm_password,
        )
    except ResetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        password = confirm_password = None  # drop references promptly; never logged/printed

    username = state["admin_username"]
    print(f"OK: đã đặt lại mật khẩu cho '{username}'.")
    print("Không cần restart mesflow-bootstrap -- /login đọc lại state.json ở mỗi lần đăng nhập.")
    print(f"Đăng nhập thử ngay để xác nhận, rồi kiểm tra dòng mới nhất trong "
          f"{audit_log_for(data_dir)} (hoặc trang Logs trong Bootstrap Web).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
TDD regression: the bootstrap admin password file must be written to
backend/logs/ (as documented in README + CLAUDE.md) regardless of the
launch working directory.

Repro (E2E boot verify 2026-08-06): launching uvicorn from the repo root
(as README instructs) writes ./logs/bootstrap_admin_password.txt at the
repo root, while operators read backend/logs/bootstrap_admin_password.txt
— which still holds a stale password from an earlier dev DB → login 401.
"""
import os
import sys

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

from core import admin_bootstrap


def test_password_file_defaults_to_backend_logs(tmp_path, monkeypatch):
    monkeypatch.delenv("ATOM_BOOTSTRAP_PASSWORD_FILE", raising=False)
    # Simulate launching from an arbitrary cwd (e.g. repo root):
    monkeypatch.setattr(os, "getcwd", lambda: "/tmp/launched_from_here")

    path = admin_bootstrap._write_password_to_secure_file("s3cret-pass")

    expected_dir = os.path.join(
        os.path.dirname(os.path.dirname(admin_bootstrap.__file__)), "logs"
    )
    assert os.path.dirname(path) == expected_dir, (
        f"password file landed in {os.path.dirname(path)} instead of backend/logs"
    )
    assert os.path.exists(path)
    with open(path) as f:
        assert f.read() == "s3cret-pass"


def test_password_file_honors_env_override(tmp_path, monkeypatch):
    override = str(tmp_path / "custom_pwd.txt")
    monkeypatch.setenv("ATOM_BOOTSTRAP_PASSWORD_FILE", override)

    path = admin_bootstrap._write_password_to_secure_file("other-pass")

    assert path == override
    assert os.path.exists(override)


def test_password_file_permissions_0600(tmp_path, monkeypatch):
    monkeypatch.delenv("ATOM_BOOTSTRAP_PASSWORD_FILE", raising=False)

    path = admin_bootstrap._write_password_to_secure_file("perm-check")

    mode = os.stat(path).st_mode & 0o777
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"

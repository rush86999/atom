"""Focused guards for the mounted (real) frontend auth used by browser runs.

These tests never launch a world, server or browser. They pin the two pure
decisions that let invoice run4 continue without a session:

* the isolated frontend copy must receive per-launch NextAuth signing material
  (the app refuses to issue a web session without it), and
* "not /login" alone must never count as a successful form sign-in — NextAuth's
  /api/auth/error failure redirect is also "not /login".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.orchestration_acceptance import (  # noqa: E402
    browser_verify as BV,
    case5_browser_recovery as C5,
)


def _base_env(**overrides):
    env = {"PATH": "/usr/bin", "HOME": "/tmp/operator-home"}
    env.update(overrides)
    return env


def test_frontend_env_mints_signing_material_when_absent():
    base = _base_env()
    env = C5._frontend_process_env(8037, 3137, base)

    secret = env["NEXTAUTH_SECRET"]
    assert isinstance(secret, str)
    assert len(secret) >= 32
    assert env["NEXTAUTH_URL"] == "http://localhost:3137"
    assert env["NEXT_PUBLIC_API_URL"] == "http://localhost:8037"
    assert env["PYTHON_API_SERVICE_BASE_URL"] == "http://localhost:8037"
    # The caller's operator environment is not modified by a launch.
    assert "NEXTAUTH_SECRET" not in base


def test_frontend_env_never_inherits_operator_signing_material():
    # The isolated copy is disposable and must not borrow the dev stack's
    # signing key (the same rule that excludes .env.local).
    for inherited in (
            "operator-secret-0123456789abcdef",
            "your-secret-key-change-in-production",
            "your-nextauth-secret-key-change-in-production-2024"):
        env = C5._frontend_process_env(
            8037, 3137, _base_env(NEXTAUTH_SECRET=inherited))
        assert env["NEXTAUTH_SECRET"] != inherited
        assert len(env["NEXTAUTH_SECRET"]) >= 32


def test_each_launch_mints_distinct_material_when_unset():
    first = C5._frontend_process_env(8037, 3137, _base_env())
    second = C5._frontend_process_env(8037, 3137, _base_env())
    assert first["NEXTAUTH_SECRET"] != second["NEXTAUTH_SECRET"]


@pytest.mark.parametrize(
    ("url", "token_present", "expected"),
    [
        # The real form's success: persisted bearer + ordinary app page.
        ("http://localhost:3137/dashboard", True, True),
        ("http://localhost:3137/assignments?run=x", True, True),
        # NextAuth failure redirects are not a landed app page (run4).
        ("http://localhost:3137/api/auth/error", False, False),
        ("http://localhost:3147/api/auth/error", True, False),
        ("http://localhost:3137/api/auth/signin", True, False),
        # Still on the form is not success, even with stale storage.
        ("http://localhost:3137/login", True, False),
        ("http://localhost:3137/login?callbackUrl=%2Fdashboard", True, False),
        # A landed page without the app's persisted bearer is not signed in.
        ("http://localhost:3137/dashboard", False, False),
        ("about:blank", False, False),
    ],
)
def test_login_landed_requires_bearer_and_app_page(url, token_present, expected):
    assert BV.login_landed(url, token_present) is expected

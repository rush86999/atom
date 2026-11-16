"""Scratch-DB regressions for the login TOTP durable replay fence.

Real SQLAlchemy scratch DB, real pyotp, real verify_login_totp_verified.
Only password hashing comparison, token minting, session inventory, audit
sink, and the login rate-limiter dependency are controlled seams.
"""
from __future__ import annotations

from unittest.mock import patch

import pyotp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auth import get_current_user
from core.auth_endpoints import router
from core.database import Base, get_db
from core.models import User, UserStatus
from core.security.auth_rate_limit import login_rate_limit

TEST_SECRET = "JBSWY3DPEHPK3PXP"


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(
        id="login-2fa-user", email="login2fa@example.com",
        hashed_password="hash", first_name="L", last_name="U",
        role="member", status=UserStatus.ACTIVE.value, is_active=True,
        two_factor_enabled=True, two_factor_secret=TEST_SECRET,
        two_factor_revision=0,
    )
    db.add(user)
    db.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[login_rate_limit] = lambda: None
    client = TestClient(app)
    with patch("core.auth_endpoints.verify_password", return_value=True), \
         patch("core.auth_endpoints.create_access_token", return_value="tok"), \
         patch("core.auth_endpoints.audit_service.log_event") as audit, \
         patch("core.session_registry.register_session"):
        yield db, user, client, audit


def _login(client, code=None):
    body = {"username": "login2fa@example.com", "password": "pw"}
    if code is not None:
        body["totp_code"] = code
    return client.post("/api/auth/login", json=body)


@freeze_time("2026-01-01 00:00:00")
def test_same_code_cannot_authorize_second_login(env):
    db, user, client, _audit = env
    code = pyotp.TOTP(TEST_SECRET).now()
    first = _login(client, code)
    assert first.status_code == 200 and first.json()["access_token"] == "tok"
    db.refresh(user)
    assert user.two_factor_last_totp_step is not None
    second = _login(client, code)
    assert second.status_code == 409
    assert "access_token" not in second.json()


@freeze_time("2026-01-01 00:00:00")
def test_enable_consumed_step_cannot_login(env):
    db, user, client, _audit = env
    user.two_factor_last_totp_step = 1767225600 // 30
    db.commit()
    resp = _login(client, pyotp.TOTP(TEST_SECRET).now())
    assert resp.status_code == 409
    assert "access_token" not in resp.json()


@freeze_time("2026-01-01 00:00:00")
def test_later_step_is_accepted_once(env):
    db, user, client, _audit = env
    user.two_factor_last_totp_step = (1767225600 // 30) - 1
    db.commit()
    code = pyotp.TOTP(TEST_SECRET).now()
    first = _login(client, code)
    assert first.status_code == 200
    second = _login(client, code)
    assert second.status_code == 409
    assert "access_token" not in second.json()


def test_helper_refusal_never_mints_token(env):
    db, user, client, audit = env
    with patch("core.auth_endpoints.verify_login_totp_verified", return_value={
        "status": "refused", "error_code": "INVALID_2FA_CODE",
        "http_status": 401, "error": "Invalid two-factor code",
    }):
        resp = _login(client, "000000")
    assert resp.status_code == 401
    assert "access_token" not in resp.json()
    audit.assert_called_once()


def test_helper_unknown_or_commit_failure_never_mints_token(env):
    db, user, client, audit = env
    with patch("core.auth_endpoints.verify_login_totp_verified", return_value={
        "status": "effect_unknown", "message": "uncertain",
    }):
        resp = _login(client, "123456")
    assert resp.status_code == 503
    assert "access_token" not in resp.json()
    audit.assert_called_once()
    with patch("core.auth_endpoints.verify_login_totp_verified",
               side_effect=RuntimeError("commit failed")):
        resp = _login(client, "123456")
    assert resp.status_code == 500
    assert "access_token" not in resp.json()


def test_no_factor_and_password_only_challenge_preserved(env):
    db, user, client, _audit = env
    challenge = _login(client)
    assert challenge.status_code == 200
    assert challenge.json()["two_factor_required"] is True
    assert "access_token" not in challenge.json()
    user.two_factor_enabled = False
    user.two_factor_secret = None
    db.commit()
    normal = _login(client)
    assert normal.status_code == 200
    assert normal.json()["access_token"] == "tok"

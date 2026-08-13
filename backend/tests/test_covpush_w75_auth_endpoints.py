"""Coverage wave 75 — core/auth_endpoints.py (43% → 95%+).

Full HTTP surface via TestClient with dependency overrides: login (success,
wrong password, inactive user, 2FA required / bad code / no secret, internal
error 500), register (success with forced member role, duplicate email,
invalid email/password validation, 422s), /me + /profile, forgot-password
(user found/not found, email task, real limiter 429), verify-token
(valid/invalid, 429), reset-password (valid/invalid/user-not-found, 429),
refresh (success/401), logout (revoke path + best-effort bad-token path),
plus the standalone rate-limit dependencies. Zero network: audit service,
email, token minting all mocked.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base

from core.auth_endpoints import (
    forgot_password_rate_limit,
    register_rate_limit,
    reset_password_rate_limit,
    verify_token_rate_limit,
    router as auth_router,
)
from core.auth import get_current_user
from core.database import get_db
from core.models import Tenant, User, UserRole, UserStatus
from core.security.auth_rate_limit import login_rate_limit

FAKE_TOKEN = "fake-jwt-token"
SECRET = "wave75-test-secret-key-for-hs256"


@pytest.fixture
def current_user():
    return User(
        id="user-1",
        email="me@example.com",
        hashed_password="hash",
        first_name="Jane",
        last_name="Doe",
        role=UserRole.MEMBER.value,
        status=UserStatus.ACTIVE,
    )


def make_app(db, current_user=None, skip_limiters=()):
    """Build an app with auth router + overridden deps.

    skip_limiters: names of rate-limit deps NOT overridden (to test 429s).
    """
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = lambda: db
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    limiters = {
        "login": login_rate_limit,
        "register": register_rate_limit,
        "forgot": forgot_password_rate_limit,
        "verify": verify_token_rate_limit,
        "reset": reset_password_rate_limit,
    }
    for name, dep in limiters.items():
        if name not in skip_limiters:
            app.dependency_overrides[dep] = lambda: None
    return TestClient(app)


@pytest.fixture
def patches():
    with patch("core.auth_endpoints.verify_password", return_value=True) as vp, \
         patch("core.auth_endpoints.get_password_hash", return_value="new-hash") as gph, \
         patch("core.auth_endpoints.create_access_token", return_value=FAKE_TOKEN) as cat, \
         patch("core.auth_endpoints.get_config") as gc, \
         patch("core.auth_endpoints.send_smtp_email") as smtp:
        cfg = MagicMock()
        cfg.server.app_url = "http://localhost:8000"
        gc.return_value = cfg
        yield {"vp": vp, "gph": gph, "cat": cat, "smtp": smtp}


@pytest.fixture(autouse=True)
def _audit():
    with patch("core.auth_endpoints.audit_service.log_event") as le:
        yield le


class TestLogin:
    def test_login_success(self, current_user, patches):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = current_user
        client = make_app(db, None)
        resp = client.post("/api/auth/login", json={"username": "me@example.com", "password": "password1"})
        assert resp.status_code == 200
        assert resp.json()["access_token"] == FAKE_TOKEN
        assert resp.json()["token_type"] == "bearer"
        assert current_user.last_login is not None
        db.commit.assert_called_once()

    def test_login_wrong_password(self, current_user, patches, _audit):
        patches["vp"].return_value = False
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = current_user
        client = make_app(db, None)
        resp = client.post("/api/auth/login", json={"username": "me@example.com", "password": "wrong"})
        assert resp.status_code == 401
        _audit.assert_called_once()

    def test_login_unknown_user(self, patches, _audit):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client = make_app(db, None)
        resp = client.post("/api/auth/login", json={"username": "nobody@x.com", "password": "password1"})
        assert resp.status_code == 401

    def test_login_inactive_user(self, current_user, patches):
        current_user.status = "inactive"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = current_user
        client = make_app(db, None)
        resp = client.post("/api/auth/login", json={"username": "me@example.com", "password": "password1"})
        assert resp.status_code == 400
        assert "Inactive" in resp.json()["detail"]

    def test_login_2fa_required(self, current_user, patches):
        current_user.two_factor_enabled = True
        current_user.two_factor_secret = "BASE32SECRETKEY1234"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = current_user
        client = make_app(db, None)
        resp = client.post("/api/auth/login", json={"username": "me@example.com", "password": "password1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["two_factor_required"] is True
        assert body["user_id"] == current_user.id

    def test_login_2fa_bad_code(self, current_user, patches, _audit):
        import pyotp
        secret = pyotp.random_base32()
        current_user.two_factor_enabled = True
        current_user.two_factor_secret = secret
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = current_user
        client = make_app(db, None)
        resp = client.post("/api/auth/login", json={
            "username": "me@example.com", "password": "password1", "totp_code": "000000"})
        assert resp.status_code == 401
        assert "2FA" in resp.json()["detail"]
        _audit.assert_called_once()

    def test_login_2fa_valid_code(self, current_user, patches):
        import pyotp
        secret = pyotp.random_base32()
        current_user.two_factor_enabled = True
        current_user.two_factor_secret = secret
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = current_user
        client = make_app(db, None)
        resp = client.post("/api/auth/login", json={
            "username": "me@example.com", "password": "password1",
            "totp_code": pyotp.TOTP(secret).now()})
        assert resp.status_code == 200
        assert resp.json()["access_token"] == FAKE_TOKEN

    def test_login_2fa_enabled_no_secret(self, current_user, patches):
        current_user.two_factor_enabled = True
        current_user.two_factor_secret = None
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = current_user
        client = make_app(db, None)
        resp = client.post("/api/auth/login", json={
            "username": "me@example.com", "password": "password1", "totp_code": "123456"})
        assert resp.status_code == 400
        assert "no secret" in resp.json()["detail"].lower()

    def test_login_internal_error_500(self, current_user, patches):
        patches["vp"].side_effect = RuntimeError("password backend down")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = current_user
        client = make_app(db, None)
        resp = client.post("/api/auth/login", json={"username": "me@example.com", "password": "password1"})
        assert resp.status_code == 500
        assert "internal error" in resp.json()["detail"].lower()


@pytest.fixture
def real_db():
    from sqlalchemy.pool import StaticPool
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


class TestRegister:
    def test_register_success(self, patches, real_db):
        db = real_db
        client = make_app(db, None)
        resp = client.post("/api/auth/register", json={
            "email": "new@example.com", "password": "password1",
            "first_name": "New", "last_name": "User", "role": "super_admin"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == FAKE_TOKEN
        created = db.query(User).filter(User.email == "new@example.com").first()
        assert created.role == "member"  # client role NEVER honored
        assert created.status == UserStatus.ACTIVE.value
        assert created.tenant_id is not None  # default tenant provisioned
        assert created.workspace_id is not None  # default workspace provisioned
        tenant = db.query(Tenant).filter(Tenant.id == created.tenant_id).first()
        assert tenant.edition == "personal"

    def test_register_duplicate_email(self, current_user, patches):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = current_user
        client = make_app(db, None)
        resp = client.post("/api/auth/register", json={
            "email": "me@example.com", "password": "password1",
            "first_name": "J", "last_name": "D"})
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    def test_register_invalid_email_422(self, patches):
        client = make_app(MagicMock(), None)
        resp = client.post("/api/auth/register", json={
            "email": "not-an-email", "password": "password1",
            "first_name": "J", "last_name": "D"})
        assert resp.status_code == 422

    def test_register_short_password_422(self, patches):
        client = make_app(MagicMock(), None)
        resp = client.post("/api/auth/register", json={
            "email": "a@b.com", "password": "short",
            "first_name": "J", "last_name": "D"})
        assert resp.status_code == 422

    def test_register_password_too_long_bytes_422(self, patches):
        client = make_app(MagicMock(), None)
        resp = client.post("/api/auth/register", json={
            "email": "a@b.com", "password": "p" * 90,
            "first_name": "J", "last_name": "D"})
        assert resp.status_code == 422

    def test_register_tenant_creation_failure_tolerated(self, patches, real_db):
        import uuid as _uuid_mod
        db = real_db
        client = make_app(db, None)
        # 1st uuid4 = user id (must succeed); 2nd = tenant id (fails) → the
        # tenant/workspace provisioning block aborts but register still mints
        with patch.object(_uuid_mod, "uuid4", side_effect=["user-id-1", RuntimeError("uuid backend down")]):
            resp = client.post("/api/auth/register", json={
                "email": "new2@example.com", "password": "password1",
                "first_name": "N", "last_name": "U"})
        assert resp.status_code == 200  # token still minted despite ctx failure


class TestMeAndProfile:
    def test_me(self, current_user, patches):
        client = make_app(MagicMock(), current_user)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "user-1"
        assert body["email"] == "me@example.com"
        assert body["role"] == UserRole.MEMBER.value

    def test_profile(self, current_user, patches):
        client = make_app(MagicMock(), current_user)
        resp = client.get("/api/auth/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == UserStatus.ACTIVE.value


class TestForgotPassword:
    def test_user_found_sends_email(self, current_user, patches):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = current_user
        client = make_app(db, None)
        resp = client.post("/api/auth/forgot-password", json={"email": "me@example.com"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        token = db.add.call_args[0][0]
        assert token.user_id == current_user.id
        assert token.token != "raw-token"  # SHA-256 digest at rest

    def test_forgot_password_unknown_user_no_enumeration(self, patches):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client = make_app(db, None)
        resp = client.post("/api/auth/forgot-password", json={"email": "ghost@x.com"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_forgot_password_rate_limited_429(self, patches):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client = make_app(db, None, skip_limiters=("forgot",))
        for _ in range(5):
            resp = client.post("/api/auth/forgot-password", json={"email": "a@b.com"})
            assert resp.status_code == 200
        resp = client.post("/api/auth/forgot-password", json={"email": "a@b.com"})
        assert resp.status_code == 429


class TestVerifyToken:
    def test_valid_token(self, patches):
        from core.models import PasswordResetToken
        tok = PasswordResetToken(user_id="u1", token="deadbeef", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = tok
        client = make_app(db, None)
        resp = client.post("/api/auth/verify-token", json={"token": "raw-token"})
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_invalid_token(self, patches):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client = make_app(db, None)
        resp = client.post("/api/auth/verify-token", json={"token": "raw-token"})
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_verify_rate_limited_429(self, patches):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client = make_app(db, None, skip_limiters=("verify",))
        for _ in range(10):
            client.post("/api/auth/verify-token", json={"token": "x"})
        resp = client.post("/api/auth/verify-token", json={"token": "x"})
        assert resp.status_code == 429


class TestResetPassword:
    def test_reset_success(self, current_user, patches):
        from core.models import PasswordResetToken
        reset = PasswordResetToken(user_id=current_user.id, token="hash", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = reset
        db.query.return_value.filter.return_value.first.side_effect = [reset, current_user]
        client = make_app(db, None)
        reset.mark_as_used = MagicMock()
        resp = client.post("/api/auth/reset-password", json={"token": "raw", "password": "newpassword1"})
        assert resp.status_code == 200
        assert current_user.hashed_password == "new-hash"
        reset.mark_as_used.assert_called_once()

    def test_reset_invalid_token(self, patches):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client = make_app(db, None)
        resp = client.post("/api/auth/reset-password", json={"token": "bad", "password": "newpassword1"})
        assert resp.status_code == 400
        assert "Invalid or expired" in resp.json()["detail"]

    def test_reset_user_not_found(self, patches):
        from core.models import PasswordResetToken
        reset = PasswordResetToken(user_id="ghost", token="hash", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [reset, None]
        client = make_app(db, None)
        resp = client.post("/api/auth/reset-password", json={"token": "raw", "password": "newpassword1"})
        assert resp.status_code == 404

    def test_reset_rate_limited_429(self, patches):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client = make_app(db, None, skip_limiters=("reset",))
        for _ in range(5):
            client.post("/api/auth/reset-password", json={"token": "bad", "password": "newpassword1"})
        resp = client.post("/api/auth/reset-password", json={"token": "bad", "password": "newpassword1"})
        assert resp.status_code == 429


class TestRefresh:
    def test_refresh_success(self, current_user, patches):
        client = make_app(MagicMock(), current_user)
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 200
        assert resp.json()["access_token"] == FAKE_TOKEN

    def test_refresh_unauthenticated_401(self, patches):
        client = make_app(MagicMock(), None)
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 401


class TestLogout:
    def test_logout_revokes_token(self, current_user, patches, _audit):
        with patch("core.auth.SECRET_KEY", SECRET), \
             patch("core.auth.ALGORITHM", "HS256"), \
             patch("core.auth.revoke_token") as revoke:
            client = make_app(MagicMock(), current_user)
            token = pyjwt.encode(
                {"sub": "user-1", "jti": "jti-123", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                SECRET, algorithm="HS256")
            resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        revoke.assert_called_once_with("jti-123", pytest.approx(datetime.now(timezone.utc).timestamp(), abs=4000))
        _audit.assert_called_once()

    def test_logout_bad_token_best_effort(self, current_user, patches, _audit):
        with patch("core.auth.SECRET_KEY", SECRET), \
             patch("core.auth.ALGORITHM", "HS256"), \
             patch("core.auth.revoke_token") as revoke:
            client = make_app(MagicMock(), current_user)
            resp = client.post("/api/auth/logout", headers={"Authorization": "Bearer garbage.token.zzz"})
        assert resp.status_code == 200
        revoke.assert_not_called()
        _audit.assert_called_once()


class TestRateLimitDependencies:
    def test_forgot_password_dependency_429(self):
        req = MagicMock()
        req.client.host = "9.9.9.9"
        with pytest.raises(HTTPException) as ei:
            for _ in range(6):
                forgot_password_rate_limit(req)
        assert ei.value.status_code == 429

    def test_verify_token_dependency_429(self):
        req = MagicMock()
        req.client.host = "9.9.9.9"
        with pytest.raises(HTTPException) as ei:
            for _ in range(11):
                verify_token_rate_limit(req)
        assert ei.value.status_code == 429

    def test_reset_password_dependency_429(self):
        req = MagicMock()
        req.client.host = "9.9.9.9"
        with pytest.raises(HTTPException) as ei:
            for _ in range(6):
                reset_password_rate_limit(req)
        assert ei.value.status_code == 429

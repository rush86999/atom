# -*- coding: utf-8 -*-
"""Coverage wave 89 — api/auth_2fa_routes.py (2FA setup/enable/disable,
backup-code verify, HITL action verify).

Real pyotp TOTP + real in-memory SQLite; audit service and HITL service
mocked. Completes the missing lines (backup/verify, verify-action, TOTP rate
limiter) and re-verifies auth on every endpoint.

Security regression surface checked this wave:
  * every endpoint rejects anonymous callers with 401,
  * /enable, /disable, /verify-action are rate-limited (5/min) against TOTP
    brute-force (429),
  * backup codes are single-use (consumed after verification — BUG-074),
  * /setup refuses to regenerate when 2FA already enabled (409).
"""
import pyotp
import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth_2fa_routes import router as auth_2fa_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import User

AUTH_HEADERS = {"Authorization": "Bearer test-token"}

TEST_SECRET = "JBSWY3DPEHPK3PXP"


@pytest.fixture(autouse=True)
def bypass_2fa_rate_limit():
    """Bypass the module-level TOTP rate limiter (5/min per IP)."""
    with patch("api.auth_2fa_routes._2fa_limiter.check", return_value=(True, 5)):
        yield


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_user(db, user_id="user-1", *, two_factor_enabled=False,
               two_factor_secret=None, two_factor_backup_codes=None):
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        first_name="T",
        last_name="U",
        role="admin",
        status="active",
        tenant_id="t1",
        two_factor_enabled=two_factor_enabled,
        two_factor_secret=two_factor_secret,
        two_factor_backup_codes=two_factor_backup_codes,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def client_factory(db):
    def _build(user_id="user-1"):
        user = _make_user(db, user_id)
        app = FastAPI()
        app.include_router(auth_2fa_router)

        def _override_db():
            yield db

        def _override_user():
            return user

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = _override_user
        return TestClient(app, raise_server_exceptions=False)
    return _build


@pytest.fixture()
def client(client_factory):
    return client_factory()


@pytest.fixture()
def anon_client(db):
    app = FastAPI()
    app.include_router(auth_2fa_router)

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


class TestAuthEnforcement:
    @pytest.mark.parametrize("method,path,body", [
        ("get", "/api/auth/2fa/status", None),
        ("post", "/api/auth/2fa/setup", None),
        ("post", "/api/auth/2fa/enable", {"code": "000000"}),
        ("post", "/api/auth/2fa/disable", {"code": "000000"}),
        ("post", "/api/auth/2fa/backup/verify", {"code": "X"}),
        ("post", "/api/auth/2fa/verify-action/action-1", {"code": "000000"}),
    ])
    def test_anonymous_requests_rejected(self, anon_client, method, path, body):
        kwargs = {"json": body} if body is not None else {}
        resp = getattr(anon_client, method)(path, **kwargs)
        assert resp.status_code == 401


class TestStatusAndSetup:
    def test_status_disabled(self, client):
        resp = client.get("/api/auth/2fa/status", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == {"enabled": False}

    def test_status_enabled(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True)
        client = client_factory("enabled-user")
        resp = client.get("/api/auth/2fa/status", headers=AUTH_HEADERS)
        assert resp.json() == {"enabled": True}

    def test_setup_success(self, client, db):
        resp = client.post("/api/auth/2fa/setup", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "secret" in body
        assert "otpauth_url" in body
        assert "Atom%20AI%20%28Upstream%29" in body["otpauth_url"]
        assert "user-1%40example.com" in body["otpauth_url"]
        user = db.query(User).filter(User.id == "user-1").first()
        assert user.two_factor_secret == body["secret"]

    def test_setup_when_already_enabled_409(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True)
        client = client_factory("enabled-user")
        resp = client.post("/api/auth/2fa/setup", headers=AUTH_HEADERS)
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "CONFLICT"


class TestEnableDisable:
    def _valid_code(self):
        return pyotp.TOTP(TEST_SECRET).now()

    def test_enable_success_generates_backup_codes(self, client_factory, db):
        _make_user(db, "setup-user", two_factor_secret=TEST_SECRET)
        client = client_factory("setup-user")
        with patch("api.auth_2fa_routes.audit_service") as audit:
            resp = client.post("/api/auth/2fa/enable",
                               json={"code": self._valid_code()},
                               headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        codes = body["data"]["backup_codes"]
        assert len(codes) == 5
        assert all(len(c) == 19 for c in codes)
        user = db.query(User).filter(User.id == "setup-user").first()
        assert user.two_factor_enabled is True
        audit.log_event.assert_called_once()

    def test_enable_already_enabled_409(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True,
                   two_factor_secret=TEST_SECRET)
        client = client_factory("enabled-user")
        resp = client.post("/api/auth/2fa/enable",
                           json={"code": self._valid_code()},
                           headers=AUTH_HEADERS)
        assert resp.status_code == 409

    def test_enable_without_setup_secret_422(self, client):
        resp = client.post("/api/auth/2fa/enable",
                           json={"code": "123456"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_enable_invalid_code_422(self, client_factory, db):
        _make_user(db, "setup-user", two_factor_secret=TEST_SECRET)
        client = client_factory("setup-user")
        resp = client.post("/api/auth/2fa/enable",
                           json={"code": "000000"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_enable_rate_limited_429(self, client_factory, db):
        _make_user(db, "setup-user", two_factor_secret=TEST_SECRET)
        client = client_factory("setup-user")
        with patch("api.auth_2fa_routes._2fa_limiter.check",
                   return_value=(False, 0)):
            resp = client.post("/api/auth/2fa/enable",
                               json={"code": "000000"}, headers=AUTH_HEADERS)
        assert resp.status_code == 429
        assert resp.headers["retry-after"] == "60"

    def test_disable_success(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True,
                   two_factor_secret=TEST_SECRET, two_factor_backup_codes=["X"])
        client = client_factory("enabled-user")
        with patch("api.auth_2fa_routes.audit_service") as audit:
            resp = client.post("/api/auth/2fa/disable",
                               json={"code": self._valid_code()},
                               headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        user = db.query(User).filter(User.id == "enabled-user").first()
        assert user.two_factor_enabled is False
        assert user.two_factor_secret is None
        assert user.two_factor_backup_codes is None
        audit.log_event.assert_called_once()

    def test_disable_not_enabled_422(self, client):
        resp = client.post("/api/auth/2fa/disable",
                           json={"code": "123456"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_disable_invalid_code_422(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True,
                   two_factor_secret=TEST_SECRET)
        client = client_factory("enabled-user")
        resp = client.post("/api/auth/2fa/disable",
                           json={"code": "000000"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_disable_rate_limited_429(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True,
                   two_factor_secret=TEST_SECRET)
        client = client_factory("enabled-user")
        with patch("api.auth_2fa_routes._2fa_limiter.check",
                   return_value=(False, 0)):
            resp = client.post("/api/auth/2fa/disable",
                               json={"code": "000000"}, headers=AUTH_HEADERS)
        assert resp.status_code == 429


class TestBackupCodeVerify:
    def test_verify_and_consume_success(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True,
                   two_factor_backup_codes=["ABCD-1234-EFGH-5678", "WXYZ-9999"])
        client = client_factory("enabled-user")
        with patch("api.auth_2fa_routes.audit_service") as audit:
            resp = client.post("/api/auth/2fa/backup/verify",
                               json={"code": "ABCD-1234-EFGH-5678"},
                               headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["remaining_codes"] == 1
        user = db.query(User).filter(User.id == "enabled-user").first()
        assert user.two_factor_backup_codes == ["WXYZ-9999"]
        audit.log_event.assert_called_once()

    def test_verify_invalid_code_422(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True,
                   two_factor_backup_codes=["ABCD-1234-EFGH-5678"])
        client = client_factory("enabled-user")
        resp = client.post("/api/auth/2fa/backup/verify",
                           json={"code": "BOGUS-CODE"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["details"]["field"] == "code"

    def test_verify_2fa_not_enabled_422(self, client):
        resp = client.post("/api/auth/2fa/backup/verify",
                           json={"code": "X"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_verify_missing_code_422(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True)
        client = client_factory("enabled-user")
        resp = client.post("/api/auth/2fa/backup/verify", json={},
                           headers=AUTH_HEADERS)
        assert resp.status_code == 422


class TestVerifyAction:
    def _approve(self, client, action_id="action-1"):
        """POST verify-action with a fresh TOTP code; retry once on a
        30s-window rollover (code computed just before the window flips)."""
        import time
        for _ in range(3):
            resp = client.post(f"/api/auth/2fa/verify-action/{action_id}",
                               json={"code": pyotp.TOTP(TEST_SECRET).now()},
                               headers=AUTH_HEADERS)
            if resp.status_code != 422:
                return resp
            time.sleep(1.1)
        return resp

    def test_verify_action_success(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True,
                   two_factor_secret=TEST_SECRET)
        client = client_factory("enabled-user")
        with patch("core.hitl_service.hitl_service.resolve_action",
                   new=AsyncMock(return_value={"status": "approved"})), \
             patch("api.auth_2fa_routes.audit_service") as audit:
            resp = self._approve(client)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == {"status": "approved"}
        audit.log_event.assert_called_once()

    def test_verify_action_2fa_not_enabled_422(self, client):
        resp = client.post("/api/auth/2fa/verify-action/action-1",
                           json={"code": "123456"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_verify_action_invalid_code_422(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True,
                   two_factor_secret=TEST_SECRET)
        client = client_factory("enabled-user")
        resp = client.post("/api/auth/2fa/verify-action/action-1",
                           json={"code": "000000"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_verify_action_resolve_failure_500(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True,
                   two_factor_secret=TEST_SECRET)
        client = client_factory("enabled-user")
        with patch("core.hitl_service.hitl_service.resolve_action",
                   new=AsyncMock(side_effect=Exception("hitl down"))):
            resp = self._approve(client)
        assert resp.status_code == 500
        assert "Failed to resolve action" in resp.json()["detail"]

    def test_verify_action_rate_limited_429(self, client_factory, db):
        _make_user(db, "enabled-user", two_factor_enabled=True,
                   two_factor_secret=TEST_SECRET)
        client = client_factory("enabled-user")
        with patch("api.auth_2fa_routes._2fa_limiter.check",
                   return_value=(False, 0)):
            resp = client.post("/api/auth/2fa/verify-action/action-1",
                               json={"code": "000000"}, headers=AUTH_HEADERS)
        assert resp.status_code == 429

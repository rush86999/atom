"""Tests for api/sso_oidc_routes.py — OIDC Single Sign-On.

The IdP (discovery, token, userinfo endpoints) is mocked by monkeypatching
httpx.AsyncClient inside the route module with a canned-response fake (same
style as the MagicMock/AsyncMock HTTP mocking used by the integration
service tests — respx is not a project dependency).
"""
import os
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.models  # noqa: F401
from api import sso_oidc_routes
from api.sso_oidc_routes import router
from core.auth import SECRET_KEY, create_access_token
from core.database import Base, get_db
from core.auth import get_current_user
from core.models import User

ISSUER = "https://idp.example.com"
DISCOVERY = {
    "issuer": ISSUER,
    "authorization_endpoint": f"{ISSUER}/authorize",
    "token_endpoint": f"{ISSUER}/token",
    "userinfo_endpoint": f"{ISSUER}/userinfo",
}

FAKE_IDP_TOKENS = {"access_token": "fake-access-token", "token_type": "Bearer"}
FAKE_USERINFO = {
    "sub": "idp-user-1",
    "email": "sso.user@example.com",
    "given_name": "Sso",
    "family_name": "User",
}


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Canned IdP: routes by (method, url) to preset payloads."""

    routes: dict = {}
    calls: list = []

    def __init__(self, timeout=None):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None):
        self.calls.append(("GET", url))
        return _FakeResponse(self.routes[("GET", url)])

    async def post(self, url, data=None, headers=None):
        self.calls.append(("POST", url, dict(data or {})))
        return _FakeResponse(self.routes[("POST", url)])


@pytest.fixture()
def fake_idp(monkeypatch):
    _FakeAsyncClient.routes = {
        ("GET", f"{ISSUER}/.well-known/openid-configuration"): DISCOVERY,
        ("POST", f"{ISSUER}/token"): FAKE_IDP_TOKENS,
        ("GET", f"{ISSUER}/userinfo"): FAKE_USERINFO,
    }
    _FakeAsyncClient.calls = []
    monkeypatch.setattr(sso_oidc_routes.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(sso_oidc_routes, "_discovery_cache", {})
    monkeypatch.setattr(sso_oidc_routes, "_pending_states", {})
    return _FakeAsyncClient


@pytest.fixture(scope="module")
def engine():
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()
    os.unlink(path)


@pytest.fixture()
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture()
def admin(db):
    u = User(
        id=f"admin-{uuid.uuid4().hex[:8]}",
        email="admin@example.com",
        hashed_password="h",
        first_name="Ad",
        last_name="Min",
        role="super_admin",
        status="active",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def client(db, admin):
    app = FastAPI()
    app.include_router(router)

    def _get_db():
        yield db

    def _get_current_user():
        return admin

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    return TestClient(app)


def _save_config(client, enabled=True, **overrides):
    payload = {
        "issuer_url": ISSUER,
        "client_id": "atom-client",
        "client_secret": "super-secret-value",
        "enabled": enabled,
        "default_role": "member",
        "allowed_domains": ["example.com"],
    }
    payload.update(overrides)
    return client.put("/api/auth/sso/oidc/config", json=payload)


def _start_login(client):
    resp = client.get("/api/auth/sso/oidc/login", follow_redirects=False)
    assert resp.status_code == 302
    return resp.headers["Location"]


def _extract_state(location):
    return parse_qs(urlparse(location).query)["state"][0]


# ============================================================================
# Config endpoints
# ============================================================================

def test_config_upsert_and_sanitized_get(client):
    resp = _save_config(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    # Secret must never come back, even on write echo.
    assert "super-secret-value" not in resp.text
    assert body["config"]["client_secret_configured"] is True
    assert body["config"]["issuer_url"] == ISSUER

    get_resp = client.get("/api/auth/sso/oidc/config")
    assert get_resp.status_code == 200
    assert get_resp.json()["config"]["enabled"] is True
    assert "client_secret" not in get_resp.json()["config"]
    assert "super-secret-value" not in get_resp.text


def test_config_requires_admin(db, engine):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: (yield db)
    # No get_current_user override -> unauthenticated.
    c = TestClient(app)
    assert c.get("/api/auth/sso/oidc/config").status_code in (401, 403)


# ============================================================================
# Login redirect
# ============================================================================

def test_login_redirect(client, fake_idp):
    _save_config(client, enabled=True)
    location = _start_login(client)
    parsed = urlparse(location)
    assert f"{ISSUER}/authorize" == f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    q = parse_qs(parsed.query)
    assert q["response_type"] == ["code"]
    assert q["scope"] == ["openid email profile"]
    assert q["client_id"] == ["atom-client"]
    assert q["redirect_uri"][0].endswith("/api/auth/sso/oidc/callback")
    assert len(q["state"][0]) >= 32


def test_login_disabled_returns_error(client, fake_idp):
    _save_config(client, enabled=False)
    resp = client.get("/api/auth/sso/oidc/login")
    assert resp.status_code == 503
    assert "disabled" in resp.json()["detail"].lower()


def test_login_unconfigured_returns_error(client, fake_idp, db):
    # No DB row and no env fallback.
    resp = client.get("/api/auth/sso/oidc/login")
    assert resp.status_code == 409


# ============================================================================
# Callback
# ============================================================================

def _decode(jwt_token):
    from jose import jwt as jjwt
    return jjwt.decode(jwt_token, SECRET_KEY, algorithms=["HS256"])


def test_callback_happy_path_existing_user(client, fake_idp, db):
    _save_config(client, enabled=True)
    existing = User(
        id=f"u-{uuid.uuid4().hex[:8]}",
        # Different case: lookup must be case-insensitive.
        email="SSO.User@Example.com",
        hashed_password="h",
        first_name="Old",
        last_name="Name",
        role="viewer",
        status="active",
    )
    db.add(existing)
    db.commit()

    state = _extract_state(_start_login(client))
    resp = client.get(
        "/api/auth/sso/oidc/callback",
        params={"code": "authz-code-1", "state": state},
    )
    assert resp.status_code == 200
    assert "auth_token" in resp.text  # HTML stores the token for the frontend
    # Token exchange happened against the mocked IdP.
    posted = [c[1] for c in fake_idp.calls if c[0] == "POST"]
    assert f"{ISSUER}/token" in posted
    assert f"{ISSUER}/userinfo" in [c[1] for c in fake_idp.calls if c[0] == "GET"]

    # Extract the serialized JWT from the HTML page.
    import json
    start = resp.text.index("var t = ") + len("var t = ")
    end = resp.text.index(";\n", start)
    payload = _decode(json.loads(resp.text[start:end]))
    assert payload["sub"] == existing.id
    # No duplicate user was provisioned.
    assert db.query(User).filter(User.email.ilike("sso.user@example.com")).count() == 1


def test_callback_auto_provisions_new_user(client, fake_idp, db):
    _save_config(client, enabled=True, default_role="member")
    state = _extract_state(_start_login(client))
    resp = client.get(
        "/api/auth/sso/oidc/callback",
        params={"code": "authz-code-2", "state": state},
    )
    assert resp.status_code == 200

    user = db.query(User).filter(User.email == "sso.user@example.com").one()
    assert user.role == "member"
    assert user.status == "active"
    assert user.hashed_password is None  # no local password for SSO users
    assert user.first_name == "Sso"

    import json
    start = resp.text.index("var t = ") + len("var t = ")
    end = resp.text.index(";\n", start)
    payload = _decode(json.loads(resp.text[start:end]))
    assert payload["sub"] == user.id


def test_callback_bad_state_rejected(client, fake_idp, db):
    _save_config(client, enabled=True)
    _start_login(client)  # a valid state exists, but we send a bogus one
    resp = client.get(
        "/api/auth/sso/oidc/callback",
        params={"code": "authz-code-3", "state": "bogus-state"},
    )
    assert resp.status_code == 401
    # No user provisioned on rejected callbacks.
    assert db.query(User).filter(User.email == "sso.user@example.com").count() == 0


def test_callback_state_single_use(client, fake_idp, db):
    _save_config(client, enabled=True)
    state = _extract_state(_start_login(client))
    first = client.get(
        "/api/auth/sso/oidc/callback",
        params={"code": "c1", "state": state},
    )
    assert first.status_code == 200
    replay = client.get(
        "/api/auth/sso/oidc/callback",
        params={"code": "c2", "state": state},
    )
    assert replay.status_code == 401

"""Tests for api/sso_oidc_routes.py — OIDC Single Sign-On.

The IdP is a real controlled HTTP provider (``scripts.controlled_oidc_provider``)
with discovery, JWKS, authorization redirect, token exchange and userinfo. The
tests therefore exercise the product's real network callback path, including
ID-token signature/issuer/audience/nonce verification.
"""
import json
import os
import tempfile
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.models  # noqa: F401
from api import sso_oidc_routes
from api.sso_oidc_routes import router
from core.auth import SECRET_KEY, get_current_user
from core.database import Base, get_db
from core.models import User
from scripts.controlled_oidc_provider import OIDCProvider

CLIENT_ID = "atom-acceptance-client"
CLIENT_SECRET = "atom-acceptance-secret"
CALLBACK = "http://testserver/api/auth/sso/oidc/callback"


@pytest.fixture(scope="module")
def engine():
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
    return TestClient(app, base_url="http://testserver")


@pytest.fixture()
def provider():
    p = OIDCProvider(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=CALLBACK,
        email="sso.user@example.com",
        given_name="Sso",
        family_name="User",
    ).start()
    try:
        yield p
    finally:
        p.stop()


@pytest.fixture(autouse=True)
def _clear_oidc_caches(monkeypatch):
    monkeypatch.setattr(sso_oidc_routes, "_discovery_cache", {})
    monkeypatch.setattr(sso_oidc_routes, "_jwks_cache", {})
    monkeypatch.setattr(sso_oidc_routes, "_pending_states", {})


def _save_config(client, provider, enabled=True, **overrides):
    payload = {
        "issuer_url": provider.base_url,
        "client_id": provider.client_id,
        "client_secret": provider.client_secret,
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


def _provider_redirect(location):
    """Follow the product's IdP redirect against the real provider."""
    resp = httpx.get(location, follow_redirects=False, timeout=10)
    assert resp.status_code == 302, resp.text
    return resp.headers["location"]


def _callback(client, callback_url):
    parsed = urlparse(callback_url)
    return client.get(parsed.path + ("?" + parsed.query if parsed.query else ""))


def _callback_token(resp):
    start = resp.text.index("var t = ") + len("var t = ")
    end = resp.text.index(";\n", start)
    return json.loads(resp.text[start:end])


def _decode(token):
    from jose import jwt as jjwt
    return jjwt.decode(token, SECRET_KEY, algorithms=["HS256"])


def _new_provider(mode="valid", **kwargs):
    defaults = dict(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        redirect_uri=CALLBACK, email="sso.user@example.com",
        given_name="Sso", family_name="User",
    )
    defaults.update(kwargs)
    return OIDCProvider(mode=mode, **defaults).start()


# ============================================================================
# Config endpoints
# ============================================================================

def test_config_upsert_and_sanitized_get(client, provider):
    resp = _save_config(client, provider)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert "super-secret-value" not in resp.text
    assert resp.json()["config"]["client_secret_configured"] is True
    assert resp.json()["config"]["issuer_url"] == provider.base_url

    get_resp = client.get("/api/auth/sso/oidc/config")
    assert get_resp.status_code == 200
    assert get_resp.json()["config"]["enabled"] is True
    assert "client_secret" not in get_resp.json()["config"]
    assert provider.client_secret not in get_resp.text


def test_config_requires_admin(db):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: (yield db)
    c = TestClient(app)
    assert c.get("/api/auth/sso/oidc/config").status_code in (401, 403)


# ============================================================================
# Login redirect
# ============================================================================

def test_login_redirect_carries_state_and_nonce(client, provider):
    _save_config(client, provider)
    location = _start_login(client)
    parsed = urlparse(location)
    assert f"{provider.base_url}/authorize" == (
        f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
    q = parse_qs(parsed.query)
    assert q["response_type"] == ["code"]
    assert q["scope"] == ["openid email profile"]
    assert q["client_id"] == [CLIENT_ID]
    assert q["redirect_uri"] == [CALLBACK]
    assert len(q["state"][0]) >= 32
    assert len(q["nonce"][0]) >= 32


def test_login_disabled_returns_error(client, provider):
    _save_config(client, provider, enabled=False)
    resp = client.get("/api/auth/sso/oidc/login")
    assert resp.status_code == 503
    assert "disabled" in resp.json()["detail"].lower()


def test_login_unconfigured_returns_error(client):
    resp = client.get("/api/auth/sso/oidc/login")
    assert resp.status_code == 409


def test_login_discovery_failure_is_502(client):
    _save_config(client, type("P", (), {
        "base_url": "http://127.0.0.1:1",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })())
    resp = client.get("/api/auth/sso/oidc/login")
    assert resp.status_code == 502


# ============================================================================
# Callback
# ============================================================================

def test_callback_happy_path_existing_user(client, provider, db):
    _save_config(client, provider)
    existing = User(
        id=f"u-{uuid.uuid4().hex[:8]}",
        email="SSO.User@Example.com",
        hashed_password="h",
        first_name="Old",
        last_name="Name",
        role="viewer",
        status="active",
    )
    db.add(existing)
    db.commit()

    login = _start_login(client)
    callback = _provider_redirect(login)
    resp = _callback(client, callback)
    assert resp.status_code == 200
    assert "auth_token" in resp.text

    payload = _decode(_callback_token(resp))
    assert payload["sub"] == existing.id
    assert db.query(User).filter(User.email.ilike("sso.user@example.com")).count() == 1
    # The real provider was used: authorization, token, JWKS and discovery.
    paths = [r["path"] for r in provider.records]
    assert any(p.startswith("/authorize") for p in paths)
    assert any(p == "/token" for p in paths)
    assert any(p == "/jwks" for p in paths)


def test_callback_auto_provisions_new_user(client, provider, db):
    _save_config(client, provider, default_role="member")
    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)
    assert resp.status_code == 200

    user = db.query(User).filter(User.email == "sso.user@example.com").one()
    assert user.role == "member"
    assert user.status == "active"
    assert user.hashed_password is None
    assert user.first_name == "Sso"
    assert _decode(_callback_token(resp))["sub"] == user.id


def test_callback_bad_state_rejected(client, provider, db):
    _save_config(client, provider)
    _start_login(client)
    resp = client.get(
        "/api/auth/sso/oidc/callback",
        params={"code": "authz-code-3", "state": "bogus-state"},
    )
    assert resp.status_code == 401
    assert db.query(User).filter(User.email == "sso.user@example.com").count() == 0


def test_callback_state_single_use(client, provider, db):
    _save_config(client, provider)
    callback = _provider_redirect(_start_login(client))
    first = _callback(client, callback)
    assert first.status_code == 200
    replay = _callback(client, callback)
    assert replay.status_code == 401


@pytest.mark.parametrize("mode", [
    "invalid_signature",
    "invalid_issuer",
    "invalid_audience",
    "invalid_nonce",
    "missing_id_token",
])
def test_callback_rejects_bad_id_tokens(client, db, mode):
    p = _new_provider(mode=mode)
    try:
        _save_config(client, p)
        callback = _provider_redirect(_start_login(client))
        resp = _callback(client, callback)
        assert resp.status_code == 401, resp.text
        assert db.query(User).filter(User.email == "sso.user@example.com").count() == 0
    finally:
        p.stop()


@pytest.mark.parametrize("mode,expected", [
    ("token_error", 502),
    ("callback_error", 400),
])
def test_callback_failure_paths(client, db, mode, expected):
    p = _new_provider(mode=mode)
    try:
        _save_config(client, p)
        callback = _provider_redirect(_start_login(client))
        resp = _callback(client, callback)
        assert resp.status_code == expected, resp.text
        assert db.query(User).filter(User.email == "sso.user@example.com").count() == 0
    finally:
        p.stop()


def test_callback_userinfo_failure_uses_verified_claims(client, db):
    p = _new_provider(mode="userinfo_error")
    try:
        _save_config(client, p)
        callback = _provider_redirect(_start_login(client))
        resp = _callback(client, callback)
        assert resp.status_code == 200
        assert db.query(User).filter(User.email == "sso.user@example.com").count() == 1
    finally:
        p.stop()


def test_callback_disallowed_domain_rejected(client, provider, db):
    _save_config(client, provider, allowed_domains=["other.example"])
    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)
    assert resp.status_code == 403
    assert db.query(User).filter(User.email == "sso.user@example.com").count() == 0


def test_discovery_issuer_mismatch_rejected(client, monkeypatch):
    class MismatchProvider(OIDCProvider):
        @property
        def discovery(self):
            metadata = super().discovery
            metadata["issuer"] = self.issuer + "/other"
            return metadata

    p = MismatchProvider(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        redirect_uri=CALLBACK,
    ).start()
    try:
        _save_config(client, p)
        resp = client.get("/api/auth/sso/oidc/login")
        assert resp.status_code == 502
    finally:
        p.stop()

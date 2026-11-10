"""Tests for api/sso_oidc_routes.py — OIDC Single Sign-On.

The IdP is a real controlled HTTP provider (``scripts.controlled_oidc_provider``)
with discovery, JWKS, authorization redirect, token exchange and userinfo. The
tests therefore exercise the product's real network callback path, including
ID-token signature/issuer/audience/nonce verification.
"""
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

import core.models  # noqa: F401
from api import sso_oidc_routes
from api.sso_oidc_routes import router
from core.auth import SECRET_KEY, get_current_user
from core.database import Base, get_db
from core.models import OAuthState, Tenant, User
from core.personal_scope import PERSONAL_TENANT_ID
from scripts.controlled_oidc_provider import OIDCProvider, _pem

CLIENT_ID = "atom-acceptance-client"
CLIENT_SECRET = "atom-acceptance-secret"
CALLBACK = "http://testserver/api/auth/sso/oidc/callback"


def _seed_tenant(db):
    tenant = Tenant(
        id=PERSONAL_TENANT_ID,
        name="Personal",
        subdomain="personal",
        edition="personal",
        is_active=True,
    )
    db.add(tenant)
    db.commit()
    return tenant


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
    _seed_tenant(session)
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


def _rewrite_id_token(monkeypatch, provider, mutate_claims):
    """Re-sign the controlled provider's real ID token with changed claims."""
    real_token = provider.token

    def token(form):
        status, body = real_token(form)
        if status == 200:
            claims = jose_jwt.get_unverified_claims(body["id_token"])
            mutate_claims(claims)
            body["id_token"] = jose_jwt.encode(
                claims,
                _pem(provider.signing_key),
                algorithm="RS256",
                headers={"kid": provider.jwk["kid"], "typ": "JWT"},
            )
        return status, body

    monkeypatch.setattr(provider, "token", token)


def _rewrite_userinfo(monkeypatch, provider, mutate_profile):
    real_userinfo = provider.userinfo

    def userinfo(authorization):
        status, body = real_userinfo(authorization)
        if status == 200:
            mutate_profile(body)
        return status, body

    monkeypatch.setattr(provider, "userinfo", userinfo)


def _drop_signed_email(claims):
    claims.pop("email", None)
    claims.pop("email_verified", None)


def _drop_signed_profile(claims):
    for key in (
            "email", "email_verified", "given_name", "family_name", "name"):
        claims.pop(key, None)


class _Missing:
    """Sentinel for a claim key that must be absent, not present as None."""


def _set_signed_email_verified(claims, marker):
    if marker is _Missing:
        claims.pop("email_verified", None)
    else:
        claims["email_verified"] = marker


def _set_userinfo_email_verified(profile, marker):
    if marker is _Missing:
        profile.pop("email_verified", None)
    else:
        profile["email_verified"] = marker


_MARKERS = [
    ("false", False),
    ("missing", _Missing),
    ("null", None),
    ("string-true", "true"),
    ("numeric-one", 1),
]


def _canonical_me_id(db, token):
    """Resolve a session through the canonical reader, without an override."""
    reader_app = FastAPI()

    @reader_app.get("/me")
    async def me(current_user: User = Depends(get_current_user)):
        return {"id": current_user.id}

    ReaderSession = sessionmaker(bind=db.get_bind())

    def _fresh_db():
        session = ReaderSession()
        try:
            yield session
        finally:
            session.close()

    reader_app.dependency_overrides[get_db] = _fresh_db
    reader = TestClient(reader_app, base_url="http://testserver")
    try:
        resp = reader.get(
            "/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        reader.close()
    assert resp.status_code == 200
    return resp.json()["id"]


def _existing_user(db, **overrides):
    values = dict(
        id=f"u-{uuid.uuid4().hex[:8]}",
        email="SSO.User@Example.com",
        hashed_password="existing-hash",
        first_name="Old",
        last_name="Name",
        role="viewer",
        status="active",
        is_active=True,
    )
    values.update(overrides)
    user = User(**values)
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def concurrency_client(tmp_path):
    """A real file-backed SQLite app with an independent connection pool.

    The module-level ``engine`` fixture uses ``StaticPool`` so the test can pass
    one in-memory session around. Concurrency assertions must not share that one
    connection: this fixture gives every Session its own SQLite connection so a
    peer commit is a genuinely separate transaction.
    """
    db_path = tmp_path / "sso_concurrency.db"
    eng = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 20},
        poolclass=NullPool,
    )
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    db = Session()
    _seed_tenant(db)
    admin = User(
        id=f"admin-{uuid.uuid4().hex[:8]}",
        email="admin@example.com",
        hashed_password="h",
        first_name="Ad",
        last_name="Min",
        role="super_admin",
        status="active",
    )
    db.add(admin)
    db.commit()

    app = FastAPI()
    app.include_router(router)

    def _get_db():
        yield db

    def _get_current_user():
        return admin

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    client = TestClient(app, base_url="http://testserver")
    try:
        yield client, eng, Session, db
    finally:
        client.close()
        db.close()
        eng.dispose()


_CHILD_CALLBACK_SCRIPT = '''\
import json
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.sso_oidc_routes import router
from core.database import get_db
from core.models import User

payload = json.load(open(sys.argv[1], encoding="utf-8"))
engine = create_engine(
    f"sqlite:///{payload['db_path']}",
    connect_args={"check_same_thread": False},
)
Session = sessionmaker(bind=engine)
db = Session()
app = FastAPI()
app.include_router(router)

def _get_db():
    yield db

app.dependency_overrides[get_db] = _get_db
client = TestClient(app, base_url="http://testserver")
client.cookies.set(
    payload["cookie_name"], payload["cookie_value"], path="/")
response = client.get(payload["callback"])
count = db.query(User).filter(User.email == payload["email"]).count()
print(json.dumps({"status": response.status_code, "created_rows": count}))
db.close()
'''


def _cookie_pair(client):
    for cookie in client.cookies.jar:
        return cookie.name, cookie.value
    raise AssertionError("SSO browser-binding cookie was not set")


def _set_browser_cookie(client, name, value, domain=None):
    if domain is None:
        client.cookies.set(name, value, path="/")
    else:
        client.cookies.set(name, value, domain=domain, path="/")


def _fresh_cookie_client(client, base_url="http://testserver"):
    return TestClient(client.app, base_url=base_url)


def _fresh_session_client(Session, base_url="http://testserver"):
    app = FastAPI()
    app.include_router(router)

    def _get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    return TestClient(app, base_url=base_url)


def _run_child_callback(
        tmp_path, db_path, callback_url, cookie_name, cookie_value, email):
    """Run one callback in a separate Python process over the same SQLite DB.

    This is a controlled process-API proof, not uvicorn/browser qualification.
    The child receives private input only and prints a safe status/row summary.
    """
    parsed = urlparse(callback_url)
    callback = parsed.path + ("?" + parsed.query if parsed.query else "")
    payload = {
        "db_path": str(db_path),
        "callback": callback,
        "cookie_name": cookie_name,
        "cookie_value": cookie_value,
        "email": email,
    }
    input_path = tmp_path / "child_callback_input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(input_path, 0o600)

    script_path = tmp_path / "child_callback.py"
    script_path.write_text(_CHILD_CALLBACK_SCRIPT, encoding="utf-8")
    os.chmod(script_path, 0o600)

    backend_dir = Path(sso_oidc_routes.__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(script_path), str(input_path)],
        cwd=str(backend_dir),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    child_log = tmp_path / "child_callback.private.log"
    child_log.write_text(
        (result.stdout or "") + "\n--- stderr ---\n" + (result.stderr or ""),
        encoding="utf-8",
    )
    os.chmod(child_log, 0o600)
    assert result.returncode == 0, {"child_exit": result.returncode}
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, {"child_exit": result.returncode, "child_output": "empty"}
    return json.loads(lines[-1])


def _before_claim_peer_write(engine, Session, user_id, changes):
    """Commit a peer mutation on a separate connection just before the claim.

    The listener runs on the callback's ``UPDATE users`` statement, before that
    statement is sent to SQLite. The peer Session checks out a different
    connection, commits, and closes; the callback's CAS must then match no row.
    """
    fired = {"done": False}

    def _listener(conn, cursor, statement, parameters, context, executemany):
        if fired["done"]:
            return
        if not statement.lstrip().lower().startswith("update users"):
            return
        fired["done"] = True
        peer = Session()
        try:
            row = peer.query(User).filter(User.id == user_id).one()
            for field, value in changes.items():
                setattr(row, field, value)
            peer.commit()
        finally:
            peer.close()

    event.listen(engine, "before_cursor_execute", _listener)
    return fired, _listener


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


# ============================================================================
# Existing-account admission
# ============================================================================

@pytest.mark.parametrize("status,is_active", [
    ("suspended", True),
    ("pending", True),
    ("deleted", True),
    ("inactive", True),
    ("disabled", True),
    ("quarantined", True),
    ("active", False),
], ids=[
    "status-suspended",
    "status-pending",
    "status-deleted",
    "status-inactive",
    "status-disabled",
    "status-unknown",
    "active-with-inactive-flag",
])
def test_callback_refuses_non_active_existing_user(
        client, provider, db, status, is_active):
    _save_config(client, provider)
    existing = _existing_user(db, status=status, is_active=is_active)

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 403
    db.expire_all()
    row = (
        db.query(User)
        .filter(User.id == existing.id)
        .populate_existing()
        .one()
    )
    assert row.status == status
    assert row.is_active is is_active
    assert row.role == "viewer"
    assert row.hashed_password == "existing-hash"
    assert row.first_name == "Old"
    assert row.last_name == "Name"
    assert row.email == "SSO.User@Example.com"
    assert row.last_login is None


def test_callback_admits_active_existing_user_without_changing_authority(
        client, provider, db):
    # A non-member default role must not rewrite an existing account's role.
    _save_config(client, provider, default_role="admin")
    existing = _existing_user(db)

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 200
    db.expire_all()
    row = (
        db.query(User)
        .filter(User.id == existing.id)
        .populate_existing()
        .one()
    )
    assert row.status == "active"
    assert row.is_active is True
    assert row.role == "viewer"
    assert row.hashed_password == "existing-hash"
    assert row.first_name == "Old"
    assert row.last_name == "Name"
    assert row.email == "SSO.User@Example.com"
    assert row.last_login is not None
    assert _decode(_callback_token(resp))["sub"] == existing.id


def test_callback_issued_session_authorizes_canonical_reader(client, provider, db):
    """The success test's admin override is config-only.

    This mounts a fresh canonical reader (``core.auth.get_current_user``) with
    only the database dependency overridden, so the returned bearer is proven
    to carry current account authority rather than an admin principal injected
    by the config fixture.
    """
    _save_config(client, provider)
    existing = _existing_user(db)

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)
    assert resp.status_code == 200
    token = _callback_token(resp)

    reader_app = FastAPI()

    @reader_app.get("/me")
    async def me(current_user: User = Depends(get_current_user)):
        return {"id": current_user.id}

    ReaderSession = sessionmaker(bind=db.get_bind())

    def _fresh_db():
        session = ReaderSession()
        try:
            yield session
        finally:
            session.close()

    reader_app.dependency_overrides[get_db] = _fresh_db
    reader = TestClient(reader_app, base_url="http://testserver")
    try:
        me_resp = reader.get(
            "/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        reader.close()

    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == existing.id


def test_callback_jit_twin_provisions_active_member(client, provider, db):
    _save_config(client, provider, default_role="member")

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 200
    user = (
        db.query(User)
        .filter(User.email == "sso.user@example.com")
        .populate_existing()
        .one()
    )
    assert user.status == "active"
    assert user.is_active is True
    assert user.role == "member"
    assert user.hashed_password is None
    assert user.tenant_id == PERSONAL_TENANT_ID
    assert user.first_name == "Sso"
    assert user.last_name == "User"
    assert user.last_login is not None
    assert _decode(_callback_token(resp))["sub"] == user.id


# ============================================================================
# Peer authority changes before the admission claim
# ============================================================================

_PEER_CHANGES = [
    ("deactivation-status", {"status": "suspended"}),
    ("deactivation-flag", {"is_active": False}),
    ("role-scope", {"role": "admin"}),
    ("password-material", {"hashed_password": "peer-reset-hash"}),
    ("tenant-workspace-scope", {
        "tenant_id": "tenant-b", "workspace_id": "workspace-b"}),
    ("email-identity", {"email": "changed@example.com"}),
]


@pytest.mark.parametrize(
    "changes", [case[1] for case in _PEER_CHANGES],
    ids=[case[0] for case in _PEER_CHANGES])
def test_callback_peer_authority_change_before_claim_refused(
        concurrency_client, provider, changes):
    client, engine, Session, db = concurrency_client
    _save_config(client, provider)
    existing = _existing_user(db)

    fired, listener = _before_claim_peer_write(
        engine, Session, existing.id, changes)
    try:
        callback = _provider_redirect(_start_login(client))
        resp = _callback(client, callback)
    finally:
        event.remove(engine, "before_cursor_execute", listener)

    assert fired["done"] is True
    assert resp.status_code == 409

    fresh = Session()
    try:
        row = fresh.query(User).filter(User.id == existing.id).one()
        expected = {
            "email": "SSO.User@Example.com",
            "hashed_password": "existing-hash",
            "role": "viewer",
            "status": "active",
            "is_active": True,
            "tenant_id": None,
            "workspace_id": None,
            "last_login": None,
        }
        expected.update(changes)
        for field, value in expected.items():
            assert getattr(row, field) == value
    finally:
        fresh.close()


# ============================================================================
# Database failure handling
# ============================================================================

def test_callback_admission_db_error_is_sanitized(
        client, provider, db, monkeypatch, caplog):
    _save_config(client, provider)
    existing = _existing_user(db)

    def _boom(*args, **kwargs):
        raise RuntimeError(
            "UPDATE users SET hashed_password='super-secret-hash' "
            "WHERE id='u-x'")

    monkeypatch.setattr(
        sso_oidc_routes, "_claim_existing_user_admission", _boom)

    callback = _provider_redirect(_start_login(client))
    with caplog.at_level(logging.INFO, logger=sso_oidc_routes.__name__):
        resp = _callback(client, callback)

    assert resp.status_code == 503
    db.expire_all()
    row = (
        db.query(User)
        .filter(User.id == existing.id)
        .populate_existing()
        .one()
    )
    assert row.status == "active"
    assert row.is_active is True
    assert row.role == "viewer"
    assert row.hashed_password == "existing-hash"
    assert row.last_login is None
    assert "super-secret-hash" not in caplog.text
    assert "hashed_password" not in caplog.text
    assert "UPDATE users" not in caplog.text


def test_callback_uncertain_commit_does_not_return_session(
        client, provider, db, monkeypatch):
    _save_config(client, provider)
    existing = _existing_user(db)
    callback = _provider_redirect(_start_login(client))
    real_commit = db.commit

    def _fail_second_commit():
        # First commit consumes the durable state; the second is the existing
        # account/session commit that must fail closed.
        if _fail_second_commit.calls == 0:
            _fail_second_commit.calls = 1
            return real_commit()
        raise RuntimeError(
            "commit failed for hashed_password='super-secret-hash'")

    _fail_second_commit.calls = 0
    monkeypatch.setattr(db, "commit", _fail_second_commit)
    try:
        resp = _callback(client, callback)
    finally:
        monkeypatch.setattr(db, "commit", real_commit)

    assert resp.status_code == 503
    fresh = sessionmaker(bind=db.get_bind())()
    try:
        row = fresh.query(User).filter(User.id == existing.id).one()
        assert row.status == "active"
        assert row.is_active is True
        assert row.role == "viewer"
        assert row.hashed_password == "existing-hash"
        assert row.last_login is None
    finally:
        fresh.close()


# ============================================================================
# Verified identity claims
# ============================================================================

@pytest.mark.parametrize(
    "marker", [case[1] for case in _MARKERS],
    ids=[case[0] for case in _MARKERS])
def test_signed_email_verification_marker_cannot_admit_existing(
        client, provider, db, monkeypatch, marker):
    _save_config(client, provider)
    existing = _existing_user(db)
    _rewrite_id_token(
        monkeypatch, provider,
        lambda claims: _set_signed_email_verified(claims, marker))

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 401
    db.expire_all()
    row = (
        db.query(User)
        .filter(User.id == existing.id)
        .populate_existing()
        .one()
    )
    assert row.email == "SSO.User@Example.com"
    assert row.status == "active"
    assert row.is_active is True
    assert row.role == "viewer"
    assert row.hashed_password == "existing-hash"
    assert row.last_login is None
    assert db.query(User).filter(User.id == existing.id).count() == 1


@pytest.mark.parametrize(
    "marker", [case[1] for case in _MARKERS],
    ids=[case[0] for case in _MARKERS])
def test_signed_email_verification_marker_cannot_provision_jit(
        client, provider, db, monkeypatch, marker):
    _save_config(client, provider)
    _rewrite_id_token(
        monkeypatch, provider,
        lambda claims: _set_signed_email_verified(claims, marker))

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 401
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 0


@pytest.mark.parametrize(
    "signed_email_present", [True, False],
    ids=["signed-email-present", "signed-email-omitted"])
def test_signed_unverified_email_does_not_borrow_userinfo_marker(
        client, provider, db, monkeypatch, signed_email_present):
    _save_config(client, provider)

    def mutate_claims(claims):
        if not signed_email_present:
            claims.pop("email", None)
        claims["email_verified"] = False

    _rewrite_id_token(monkeypatch, provider, mutate_claims)
    # The controlled profile still reports the same email/sub as verified.

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 401
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 0


@pytest.mark.parametrize("sub_mode", ["foreign", "missing"])
@pytest.mark.parametrize("precreate", [False, True], ids=["jit", "existing"])
def test_userinfo_subject_cannot_supply_email_identity(
        client, provider, db, monkeypatch, sub_mode, precreate):
    _save_config(client, provider)
    existing = _existing_user(db) if precreate else None
    _rewrite_id_token(monkeypatch, provider, _drop_signed_email)

    def mutate_profile(profile):
        if sub_mode == "foreign":
            profile["sub"] = "foreign-subject"
        else:
            profile.pop("sub", None)

    _rewrite_userinfo(monkeypatch, provider, mutate_profile)

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 401
    if existing is not None:
        db.expire_all()
        row = (
            db.query(User)
            .filter(User.id == existing.id)
            .populate_existing()
            .one()
        )
        assert row.email == "SSO.User@Example.com"
        assert row.role == "viewer"
        assert row.hashed_password == "existing-hash"
        assert row.last_login is None
        assert db.query(User).filter(User.id == existing.id).count() == 1
    else:
        assert db.query(User).filter(
            User.email == "sso.user@example.com").count() == 0


def test_profile_only_verified_email_admits_jit(
        client, provider, db, monkeypatch):
    _save_config(client, provider)
    _rewrite_id_token(monkeypatch, provider, _drop_signed_profile)

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 200
    user = (
        db.query(User)
        .filter(User.email == "sso.user@example.com")
        .populate_existing()
        .one()
    )
    assert user.first_name == "Sso"
    assert user.last_name == "User"
    assert user.role == "member"
    assert user.status == "active"
    assert user.is_active is True
    assert user.hashed_password is None
    assert user.last_login is not None


def test_profile_only_verified_email_admits_existing(
        client, provider, db, monkeypatch):
    _save_config(client, provider)
    existing = _existing_user(db)
    _rewrite_id_token(monkeypatch, provider, _drop_signed_email)

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 200
    db.expire_all()
    row = (
        db.query(User)
        .filter(User.id == existing.id)
        .populate_existing()
        .one()
    )
    assert row.email == "SSO.User@Example.com"
    assert row.role == "viewer"
    assert row.hashed_password == "existing-hash"
    assert row.last_login is not None


@pytest.mark.parametrize(
    "marker", [case[1] for case in _MARKERS],
    ids=[case[0] for case in _MARKERS])
def test_profile_only_email_requires_boolean_true_marker(
        client, provider, db, monkeypatch, marker):
    _save_config(client, provider)
    _rewrite_id_token(monkeypatch, provider, _drop_signed_email)
    _rewrite_userinfo(
        monkeypatch, provider,
        lambda profile: _set_userinfo_email_verified(profile, marker))

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 401
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 0


def test_foreign_userinfo_profile_is_not_copied_when_signed_email_suffices(
        client, provider, db, monkeypatch):
    _save_config(client, provider)

    def drop_signed_names(claims):
        for key in ("given_name", "family_name", "name"):
            claims.pop(key, None)

    _rewrite_id_token(monkeypatch, provider, drop_signed_names)

    def foreign_profile(profile):
        profile["sub"] = "foreign-subject"
        profile["email"] = "foreign@example.com"
        profile["given_name"] = "Foreign"
        profile["family_name"] = "Profile"
        profile["name"] = "Foreign Profile"

    _rewrite_userinfo(monkeypatch, provider, foreign_profile)

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 200
    user = (
        db.query(User)
        .filter(User.email == "sso.user@example.com")
        .populate_existing()
        .one()
    )
    assert user.first_name == "SSO"
    assert user.last_name == "User"
    assert db.query(User).filter(
        User.email == "foreign@example.com").count() == 0


@pytest.mark.parametrize("mutation", ["numeric-email", "numeric-subject"])
def test_signed_identity_claims_require_string_types(
        client, provider, db, monkeypatch, mutation):
    _save_config(client, provider)

    def mutate_claims(claims):
        if mutation == "numeric-email":
            claims["email"] = 12345
            claims["email_verified"] = True
        else:
            claims["sub"] = 12345

    _rewrite_id_token(monkeypatch, provider, mutate_claims)

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 401
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 0


_OPAQUE_SUBJECT_MISMATCHES = [
    ("whitespace", " subject ", "subject"),
    ("case", "Subject", "subject"),
    ("punctuation", "subject.", "subject"),
    ("profile-type", " subject ", 123),
]


@pytest.mark.parametrize(
    "signed_subject,profile_subject",
    [case[1:] for case in _OPAQUE_SUBJECT_MISMATCHES],
    ids=[case[0] for case in _OPAQUE_SUBJECT_MISMATCHES])
def test_opaque_subject_mismatch_cannot_supply_profile_email(
        client, provider, db, monkeypatch, signed_subject, profile_subject):
    _save_config(client, provider)

    def mutate_claims(claims):
        _drop_signed_email(claims)
        claims["sub"] = signed_subject

    _rewrite_id_token(monkeypatch, provider, mutate_claims)
    _rewrite_userinfo(
        monkeypatch, provider,
        lambda profile: profile.__setitem__("sub", profile_subject))

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 401
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 0


def test_exact_opaque_subject_pair_admits_profile_identity(
        client, provider, db, monkeypatch):
    _save_config(client, provider)
    opaque_subject = " subject "

    def mutate_claims(claims):
        _drop_signed_email(claims)
        claims["sub"] = opaque_subject

    _rewrite_id_token(monkeypatch, provider, mutate_claims)
    _rewrite_userinfo(
        monkeypatch, provider,
        lambda profile: profile.__setitem__("sub", opaque_subject))

    callback = _provider_redirect(_start_login(client))
    resp = _callback(client, callback)

    assert resp.status_code == 200
    user = (
        db.query(User)
        .filter(User.email == "sso.user@example.com")
        .populate_existing()
        .one()
    )
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 1
    assert _canonical_me_id(db, _callback_token(resp)) == user.id


# ============================================================================
# Durable browser-bound state
# ============================================================================

def test_login_requires_existing_authoritative_tenant(client, provider, db):
    _save_config(client, provider)
    db.query(Tenant).delete()
    db.commit()

    resp = client.get(
        "/api/auth/sso/oidc/login", follow_redirects=False)

    assert resp.status_code == 503
    assert db.query(OAuthState).count() == 0


def test_state_cookie_attributes_follow_environment(monkeypatch):
    request = SimpleNamespace(url=SimpleNamespace(scheme="http"))

    monkeypatch.setenv("ENVIRONMENT", "production")
    assert sso_oidc_routes._state_cookie_secure(request) is True
    assert (
        sso_oidc_routes._state_cookie_name(request)
        == "__Host-atom_oidc_state"
    )

    monkeypatch.setenv("ENVIRONMENT", "development")
    assert sso_oidc_routes._state_cookie_secure(request) is False
    assert sso_oidc_routes._state_cookie_name(request) == "atom_oidc_state"


def test_login_persists_state_digest_not_raw_url_state(
        client, provider, db):
    _save_config(client, provider)
    location = _start_login(client)
    raw_state = parse_qs(urlparse(location).query)["state"][0]
    _cookie_name, cookie_value = _cookie_pair(client)

    row = db.query(OAuthState).one()
    serialized_extra = json.dumps(row.extra_data)
    assert row.state == hashlib.sha256(
        raw_state.encode("utf-8")).hexdigest()
    assert raw_state not in serialized_extra
    assert cookie_value not in serialized_extra
    assert row.redirect_uri == CALLBACK
    assert row.provider == "oidc"
    assert row.tenant_id == PERSONAL_TENANT_ID


def test_process_restart_preserves_durable_state_and_cookie(
        client, provider, db, tmp_path):
    """Controlled process-API proof, not uvicorn/browser qualification."""
    _save_config(client, provider)
    callback = _provider_redirect(_start_login(client))
    cookie_name, cookie_value = _cookie_pair(client)
    db_path = db.get_bind().url.database

    summary = _run_child_callback(
        tmp_path,
        db_path,
        callback,
        cookie_name,
        cookie_value,
        "sso.user@example.com",
    )

    assert summary == {"status": 200, "created_rows": 1}
    db.expire_all()
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 1


@pytest.mark.parametrize("cookie_mode", ["missing", "wrong"])
def test_callback_requires_same_browser_cookie(
        client, provider, db, cookie_mode):
    _save_config(client, provider)
    callback = _provider_redirect(_start_login(client))
    cookie_name, cookie_value = _cookie_pair(client)

    other_browser = _fresh_cookie_client(client)
    try:
        if cookie_mode == "wrong":
            _set_browser_cookie(
                other_browser, cookie_name, "wrong-browser-binding")
        resp = _callback(other_browser, callback)
    finally:
        other_browser.close()

    assert resp.status_code == 401
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 0
    assert db.query(OAuthState).count() == 1
    assert not any(
        record["path"] == "/token" for record in provider.records)


def test_expired_durable_state_refused_before_exchange(
        client, provider, db):
    _save_config(client, provider)
    callback = _provider_redirect(_start_login(client))
    row = db.query(OAuthState).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    resp = _callback(client, callback)

    assert resp.status_code == 401
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 0
    assert db.query(OAuthState).count() == 1
    assert not any(
        record["path"] == "/token" for record in provider.records)


def test_durable_state_replay_refused_with_cookie(client, provider, db):
    _save_config(client, provider)
    callback = _provider_redirect(_start_login(client))
    cookie_name, cookie_value = _cookie_pair(client)

    first = _callback(client, callback)
    assert first.status_code == 200
    assert db.query(OAuthState).count() == 0

    _set_browser_cookie(client, cookie_name, cookie_value)
    replay = _callback(client, callback)

    assert replay.status_code == 401
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 1
    assert sum(
        1 for record in provider.records if record["path"] == "/token") == 1


@pytest.mark.parametrize(
    "change", ["issuer", "client", "config-generation"])
def test_callback_rejects_changed_config_before_exchange(
        client, provider, db, change):
    _save_config(client, provider)
    callback = _provider_redirect(_start_login(client))
    overrides = {
        "issuer": {"issuer_url": provider.base_url + "/changed"},
        "client": {"client_id": "other-client"},
        "config-generation": {"default_role": "admin"},
    }[change]
    assert _save_config(client, provider, **overrides).status_code == 200

    resp = _callback(client, callback)

    assert resp.status_code == 409
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 0
    assert db.query(OAuthState).count() == 1
    assert not any(
        record["path"] == "/token" for record in provider.records)


def test_callback_rejects_changed_callback_target(
        client, provider, db):
    _save_config(client, provider)
    callback = _provider_redirect(_start_login(client))
    cookie_name, cookie_value = _cookie_pair(client)

    other_origin = _fresh_cookie_client(client, base_url="http://otherserver")
    try:
        _set_browser_cookie(other_origin, cookie_name, cookie_value)
        resp = _callback(other_origin, callback)
    finally:
        other_origin.close()

    assert resp.status_code == 409
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 0
    assert db.query(OAuthState).count() == 1
    assert not any(
        record["path"] == "/token" for record in provider.records)


def test_callback_rejects_tampered_stored_redirect_target(
        client, provider, db):
    _save_config(client, provider)
    callback = _provider_redirect(_start_login(client))
    row = db.query(OAuthState).one()
    row.redirect_uri = "http://otherserver/api/auth/sso/oidc/callback"
    db.commit()

    resp = _callback(client, callback)

    assert resp.status_code == 409
    assert db.query(User).filter(
        User.email == "sso.user@example.com").count() == 0
    assert db.query(OAuthState).count() == 1
    assert not any(
        record["path"] == "/token" for record in provider.records)


def test_concurrent_durable_state_consume_single_use(
        concurrency_client, provider):
    client, engine, Session, _db = concurrency_client
    _save_config(client, provider)
    callback = _provider_redirect(_start_login(client))
    cookie_name, cookie_value = _cookie_pair(client)

    first = _fresh_session_client(Session)
    second = _fresh_session_client(Session)
    _set_browser_cookie(first, cookie_name, cookie_value)
    _set_browser_cookie(second, cookie_name, cookie_value)

    barrier = threading.Barrier(2)

    def _before_delete(conn, cursor, statement, parameters, context,
                       executemany):
        if not statement.lstrip().lower().startswith(
                "delete from oauth_states"):
            return
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            return

    event.listen(engine, "before_cursor_execute", _before_delete)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(_callback, candidate, callback)
                for candidate in (first, second)
            ]
            responses = [future.result(timeout=60) for future in futures]
    finally:
        event.remove(engine, "before_cursor_execute", _before_delete)
        first.close()
        second.close()

    assert sorted(response.status_code for response in responses) == [200, 401]

    fresh = Session()
    try:
        assert fresh.query(User).filter(
            User.email == "sso.user@example.com").count() == 1
        assert fresh.query(OAuthState).count() == 0
    finally:
        fresh.close()

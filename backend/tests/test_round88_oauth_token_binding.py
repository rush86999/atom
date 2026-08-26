"""R88 RED tests — OAuth state binding + credential fan-out.

Findings being locked down:

1. ``GET /{provider}/initiate`` mints a validly-signed consent state bound to
   ANY caller-supplied ``?user_id=`` when authentication fails (demo-user
   fallback), and ``callback`` resolves an unknown state user to the FIRST
   database row (the bootstrap admin). Together: an unauthenticated attacker
   completes the consent screen with THEIR provider account and the resulting
   provider tokens are stored under the victim admin's id.

2. Every successful connect fans the encrypted tokens out to ALL active
   users' IntegrationToken rows — attacker tokens become every user's
   stored integration credentials. Default must be connecting-user-only,
   legacy behavior behind ATOM_OAUTH_SHARED_INTEGRATION_TOKENS=true.

3. Callback failures return ``str(e)`` to the client (detail=f"...{str(e)}").
"""
import os
import tempfile
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import IntegrationToken, OAuthToken, User, UserRole, UserStatus


def _mk_user(uid, email):
    return User(
        id=uid,
        email=email,
        first_name="A",
        last_name="B",
        hashed_password="x",
        role=UserRole.SUPER_ADMIN.value if uid.endswith("1") else UserRole.MEMBER.value,
        status=UserStatus.ACTIVE.value,
    )


@pytest.fixture
def db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except exc.NoReferencedTableError:
            continue
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def users(db):
    # Insertion order matters: admin-user-1 is the FIRST row — the fallback
    # target of the pre-fix callback.
    u1 = _mk_user("admin-user-1", "admin@test.local")
    u2 = _mk_user("member-user-2", "member@test.local")
    db.add_all([u1, u2])
    db.commit()
    return {"admin": u1, "member": u2}


class _FakeOAuthHandler:
    """Stands in for OAuthHandler: deterministic consent URL + token exchange."""

    def __init__(self, config):
        self.config = config

    def get_authorization_url(self, state=None):
        return f"https://provider.example/consent?state={state}"

    async def exchange_code_for_tokens(self, code):
        return {
            "access_token": "attacker-or-test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600,
            "scope": "read write",
        }


@pytest.fixture
def client(db, users, monkeypatch):
    from api.oauth_routes import router
    import api.oauth_routes as oroutes
    from core.database import get_db as core_get_db

    monkeypatch.setattr(oroutes, "OAuthHandler", _FakeOAuthHandler)
    monkeypatch.setattr(
        "core.privsec.token_encryption.encrypt_token",
        lambda tok: f"enc:{tok}",
    )

    def _over_db():
        yield db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[core_get_db] = _over_db

    c = TestClient(app)
    c.atom_db = db
    yield c


def _bearer(uid):
    import core.auth as ca

    return {"Authorization": f"Bearer {ca.create_access_token({'sub': uid})}"}


def _state_from(location):
    return parse_qs(urlparse(location).query)["state"][0]


def _connect(client, provider, uid=None):
    """Drive initiate -> callback for `uid` (or unauthenticated when None).
    Returns (initiate_resp, callback_resp)."""
    headers = _bearer(uid) if uid else {}
    init = client.get(
        f"/api/v1/auth/oauth/{provider}/initiate",
        params={k: v for k, v in ({"token": headers["Authorization"][7:]} .items() if uid else {})},
        follow_redirects=False,
    )
    if init.status_code not in (301, 302, 307):
        return init, None
    state = _state_from(init.headers["Location"])
    cb = client.get(
        f"/api/v1/auth/oauth/{provider}/callback",
        params={"code": "auth-code-1", "state": state},
        headers=headers,
        follow_redirects=False,
    )
    return init, cb

# ---------------------------------------------------------------------------
# (a) initiate fail-closed
# ---------------------------------------------------------------------------

def test_initiate_without_auth_fails_closed(client):
    resp = client.get(
        "/api/v1/auth/oauth/google/initiate", follow_redirects=False
    )
    assert resp.status_code in (401, 403), (
        f"unauthenticated initiate returned {resp.status_code} and minted "
        f"state: {resp.headers.get('location', '')}"
    )


def test_initiate_cannot_bind_arbitrary_user_id_param(client):
    """The ?user_id= escape hatch must be gone: without a valid JWT, no
    victim-bound state may be minted."""
    resp = client.get(
        "/api/v1/auth/oauth/google/initiate",
        params={"user_id": "admin-user-1"},
        follow_redirects=False,
    )
    assert resp.status_code in (401, 403)


def test_initiate_with_token_binds_state_to_real_user(client):
    """Regression guard: the legitimate ?token=<JWT> navigation still mints
    state bound to the signed-in user (Round 86 contract)."""
    init = client.get(
        "/api/v1/auth/oauth/google/initiate",
        params={"token": _bearer("admin-user-1")["Authorization"][7:]},
        follow_redirects=False,
    )
    assert init.status_code in (301, 302, 307), init.text
    from api.oauth_routes import _get_user_id_from_state

    state = _state_from(init.headers["Location"])
    assert _get_user_id_from_state(state, "google") == "admin-user-1"


# ---------------------------------------------------------------------------
# (b) callback fails closed on unknown state user
# ---------------------------------------------------------------------------

def test_callback_unknown_state_user_fails_closed(client, db):
    """A validly-signed state for a user that does not exist must NOT fall
    back to the first DB row (bootstrap admin) — that is exactly how an
    attacker plants their provider tokens on the admin account."""
    from api.oauth_routes import _build_state

    state = _build_state("google", "ghost-user-that-does-not-exist")
    resp = client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "auth-code-1", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code < 500
    assert resp.status_code not in (200, 302), resp.text

    db.expire_all()
    assert db.query(IntegrationToken).count() == 0
    assert db.query(OAuthToken).count() == 0


# ---------------------------------------------------------------------------
# (c) credential fan-out
# ---------------------------------------------------------------------------

def test_connect_binds_tokens_only_to_connecting_user(client, db):
    """Connecting as member-user-2 must store credentials under member-user-2
    ONLY — not copy them into every other active user's rows."""
    init, cb = _connect(client, "google", "member-user-2")
    assert init.status_code in (301, 302, 307), init.text
    assert cb is not None and cb.status_code in (200, 301, 302, 307), getattr(cb, "text", "")

    db.expire_all()
    rows = db.query(IntegrationToken).filter(
        IntegrationToken.provider == "google"
    ).all()
    owners = sorted(r.user_id for r in rows)
    assert owners == ["member-user-2"], (
        f"tokens fanned out to {owners}; expected only the connecting user"
    )


def test_shared_token_flag_restores_legacy_fanout(client, db, monkeypatch):
    """Opt-in kill switch restores the pre-R88 shared-credential behavior."""
    monkeypatch.setenv("ATOM_OAUTH_SHARED_INTEGRATION_TOKENS", "true")
    init, cb = _connect(client, "google", "member-user-2")
    assert init.status_code in (301, 302, 307)
    assert cb is not None and cb.status_code in (200, 301, 302, 307)

    db.expire_all()
    owners = sorted(
        r.user_id
        for r in db.query(IntegrationToken).filter(
            IntegrationToken.provider == "google"
        ).all()
    )
    assert owners == ["admin-user-1", "member-user-2"]


def test_zoho_multi_provider_keys_scoped_to_connecting_user(client, db):
    """The legit Zoho one-grant→five-services fan-out stays, but per-user:
    all five provider rows belong to the connecting user only."""
    init, cb = _connect(client, "zoho", "member-user-2")
    assert init.status_code in (301, 302, 307), init.text
    assert cb is not None and cb.status_code in (200, 301, 302, 307)

    db.expire_all()
    rows = db.query(IntegrationToken).filter(
        IntegrationToken.provider.in_(
            ["zoho", "zoho_books", "zoho_inventory", "zoho_crm", "zoho_workdrive"]
        )
    ).all()
    providers = {r.provider for r in rows}
    assert providers == {
        "zoho", "zoho_books", "zoho_inventory", "zoho_crm", "zoho_workdrive",
    }
    assert all(r.user_id == "member-user-2" for r in rows)


# ---------------------------------------------------------------------------
# (d) error hygiene
# ---------------------------------------------------------------------------

def test_callback_failure_does_not_leak_exception_text(client, db, monkeypatch):
    """str(e) must stay server-side: a failing token exchange returns a
    generic error detail."""
    import asyncio

    import api.oauth_routes as oroutes

    class _ExplodingHandler(_FakeOAuthHandler):
        async def exchange_code_for_tokens(self, code):
            raise RuntimeError("SECRET-PROVIDER-INTERNAL abc123")

    monkeypatch.setattr(oroutes, "OAuthHandler", _ExplodingHandler)
    init, cb = _connect(client, "google", "member-user-2")
    assert init.status_code in (301, 302, 307)
    assert cb is not None
    assert "SECRET-PROVIDER-INTERNAL" not in (cb.text or "")

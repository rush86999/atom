"""RED tests — OAuth initiate must bind state to the REAL user from ?token=.

The frontend connect buttons navigate the browser to
``GET /api/v1/auth/oauth/{provider}/initiate?token=<JWT>`` (no Authorization
header is possible on a top-level navigation). oauth_initiate resolves the
user via core.auth.get_current_user(request=request) — but never passes a db
session, so the real resolver crashes on its user lookup, the broad except
silently falls back to "demo-user", and the consent state binds to the wrong
identity. The resulting IntegrationToken lands under demo-user: the launch
guide's /api/v1/auth/oauth/tokens check never shows the app connected.

Fix under test: initiate takes a get_db dependency and passes it through, so
?token= resolves the signed-in user and the HMAC state carries that user id.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.oauth_routes import _get_user_id_from_state


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv(
        "ZOHO_REDIRECT_URI",
        "http://localhost:8000/api/v1/auth/oauth/zoho/callback",
    )

    from api.oauth_routes import router
    import core.auth as ca

    calls = {"n": 0, "tokens": []}

    async def fake_get_current_user(request=None, token=None, db=None):
        # Mirror the real resolver contract:
        #   - no db session  -> it cannot look up the user -> error
        #   - no credentials -> 401 (the route's except then falls back)
        #   - otherwise      -> resolves the user from the JWT
        # The token MUST arrive as an explicit string: when called manually
        # with the Depends sentinel default, the real resolver decodes THAT
        # object, fails, and the route silently degrades to demo-user.
        calls["n"] += 1
        if db is None:
            raise RuntimeError("resolver requires a db session")
        if not isinstance(token, str):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="missing explicit token")
        calls["tokens"].append(token)
        return SimpleNamespace(id="user-42")

    monkeypatch.setattr(ca, "get_current_user", fake_get_current_user)

    app = FastAPI()
    app.include_router(router)
    yield TestClient(app), calls


def test_token_query_binds_state_to_real_user(client):
    test_client, calls = client
    resp = test_client.get(
        "/api/v1/auth/oauth/zoho/initiate",
        params={"token": "not-a-real-jwt-but-resolver-is-mocked"},
        follow_redirects=False,
    )
    assert resp.status_code == 307
    state = resp.headers["location"].split("state=")[-1]
    assert _get_user_id_from_state(state, "zoho") == "user-42"
    assert calls["n"] >= 1


def test_no_token_fails_closed(client):
    """R88 re-contract: an anonymous browser hit (no token param) must NOT
    mint a consent state at all. The old demo-user fallback produced a
    validly-signed state for a nonexistent user, which the callback then
    resolved to the first DB row (bootstrap admin) — planting attacker
    provider tokens on the admin account. Fail closed with 401 instead."""
    test_client, calls = client
    resp = test_client.get(
        "/api/v1/auth/oauth/zoho/initiate", follow_redirects=False
    )
    assert resp.status_code in (401, 403)
    assert "state=" not in (resp.headers.get("location") or "")
    assert calls["tokens"] == []


def test_bearer_header_binds_state_to_real_user(client):
    """API clients and the e2e journey suite authenticate the initiate
    navigation with an Authorization header instead of ?token=.
    get_current_user reads the header only through FastAPI dependency
    injection, never on the route's manual call — so oauth_initiate must
    extract the Bearer token itself (same contract as the module-level
    wrapper, B17)."""
    test_client, calls = client
    resp = test_client.get(
        "/api/v1/auth/oauth/zoho/initiate",
        headers={"Authorization": "Bearer header-jwt-resolved-by-mock"},
        follow_redirects=False,
    )
    assert resp.status_code == 307
    state = resp.headers["location"].split("state=")[-1]
    assert _get_user_id_from_state(state, "zoho") == "user-42"
    assert "header-jwt-resolved-by-mock" in calls["tokens"]


def test_non_bearer_authorization_header_fails_closed(client):
    """A non-Bearer Authorization header must not authenticate the initiate:
    it is not extracted, the anonymous fail-closed path applies."""
    test_client, calls = client
    resp = test_client.get(
        "/api/v1/auth/oauth/zoho/initiate",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
        follow_redirects=False,
    )
    assert resp.status_code in (401, 403)
    assert calls["tokens"] == []

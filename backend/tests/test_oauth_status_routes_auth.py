"""RED tests — Round 70 / Plan 315-01: OAuth status/authorize routes auth.

Expected to FAIL against the current code; go green in Plans 315-04/315-05.

Findings under test:
  B7 — /api/auth/* status/authorize/oauth-status endpoints have no auth and
       accept a client-supplied default user_id (`oauth_status_routes.py`).
  B8 — /{provider}/initiate alias accepts arbitrary/unvalidated providers
       (`oauth_status_routes.py:490-499`).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oauth_status_routes import router

# Explicit list of the unauthenticated surface (status + authorize ×10,
# oauth-status, plus the initiate alias with a known provider).
STATUS_ENDPOINTS = [
    "/api/auth/gmail/status",
    "/api/auth/outlook/status",
    "/api/auth/slack/status",
    "/api/auth/teams/status",
    "/api/auth/trello/status",
    "/api/auth/asana/status",
    "/api/auth/notion/status",
    "/api/auth/github/status",
    "/api/auth/dropbox/status",
    "/api/auth/gdrive/status",
    "/api/auth/oauth-status",
]
AUTHORIZE_ENDPOINTS = [
    "/api/auth/gmail/authorize",
    "/api/auth/outlook/authorize",
    "/api/auth/slack/authorize",
    "/api/auth/teams/authorize",
    "/api/auth/trello/authorize",
    "/api/auth/asana/authorize",
    "/api/auth/notion/authorize",
    "/api/auth/github/authorize",
    "/api/auth/dropbox/authorize",
    "/api/auth/gdrive/authorize",
]


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.mark.parametrize("path", STATUS_ENDPOINTS + AUTHORIZE_ENDPOINTS)
def test_oauth_endpoints_require_auth(client, path):
    """B7: without a valid token, every /api/auth/* endpoint must return
    401/403. Currently they return 200/307 (no auth dependency)."""
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code in (401, 403), (
        f"B7 regression: {path} returned {resp.status_code} without auth. "
        f"All /api/auth/* endpoints must require a valid token."
    )


def test_initiate_unknown_provider_rejected():
    """B8: an unvalidated provider must be rejected with 404/422, not blindly
    redirected. Currently any provider string maps through to a redirect.

    Authenticated here via a dependency override so the request actually
    reaches the provider allowlist (an unauthenticated request correctly
    returns 401 first — see test_oauth_initiate_known_provider_requires_auth).
    The property under test is the allowlist, not the auth gate."""
    from core.auth import get_current_user

    app = FastAPI()
    app.include_router(router)
    # Override auth: simulate an authenticated caller so the allowlist is reached.
    app.dependency_overrides[get_current_user] = lambda: {"id": "test_user"}
    authed_client = TestClient(app)

    resp = authed_client.get("/api/auth/not-a-real-provider/initiate", follow_redirects=False)
    assert resp.status_code in (404, 422), (
        f"B8 regression: unknown provider returned {resp.status_code} "
        f"(expected 404/422). Providers must be allowlisted."
    )


def test_oauth_initiate_known_provider_requires_auth(client):
    """B7: the initiate alias must also be authenticated."""
    resp = client.get("/api/auth/outlook/initiate", follow_redirects=False)
    assert resp.status_code in (401, 403), (
        f"B7 regression: /api/auth/outlook/initiate returned "
        f"{resp.status_code} without auth."
    )

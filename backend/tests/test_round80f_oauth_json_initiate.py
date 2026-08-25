"""Round 80o — JSON variant of the OAuth initiate endpoint for mobile.

The mobile app cannot follow a 302 into the provider's consent page; it needs
the authorization URL as data. GET /api/v1/auth/oauth/{provider}/initiate
gains ?format=json -> {"url": ...} (same state binding, same auth resolution),
while the default keeps the 302 RedirectResponse contract for web.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from core.auth import get_current_user
    from api.oauth_routes import router

    app = FastAPI()
    app.include_router(router)
    user = MagicMock()
    user.id = "mobile-user"
    app.dependency_overrides[get_current_user] = lambda: user
    # NOTE: oauth_initiate resolves the user from the REQUEST via
    # core.auth.get_current_user directly; override that path too.
    import core.auth as ca
    orig = app.dependency_overrides.copy()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _with_auth_request(monkeypatch):
    """Make the in-handler get_current_user resolve to a fixed user."""
    import core.auth as ca
    u = MagicMock()
    u.id = "mobile-user"
    monkeypatch.setattr(ca, "get_current_user",
                        __import__("asyncio").coroutine if False else None)


class TestJsonInitiate:
    def test_format_json_returns_url(self, monkeypatch):
        monkeypatch.setenv("SLACK_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("SLACK_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("SLACK_REDIRECT_URI", "http://localhost:8000/api/v1/auth/oauth/slack/callback")
        from api.oauth_routes import router
        from fastapi import FastAPI
        import core.auth as ca

        async def fake_get_current_user(request=None):
            u = MagicMock()
            u.id = "mobile-user"
            return u
        monkeypatch.setattr(ca, "get_current_user", fake_get_current_user)

        app = FastAPI()
        app.include_router(router)
        c = TestClient(app)
        resp = c.get("/api/v1/auth/oauth/slack/initiate?format=json")
        assert resp.status_code == 200, resp.text[:200]
        body = resp.json()
        assert "url" in body and "slack.com" in body["url"]

    def test_unknown_provider_400(self, monkeypatch):
        import core.auth as ca

        async def fake(request=None):
            u = MagicMock(); u.id = "u"; return u
        monkeypatch.setattr(ca, "get_current_user", fake)

        from api.oauth_routes import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        c = TestClient(app)
        assert c.get("/api/v1/auth/oauth/nope/initiate?format=json").status_code == 400

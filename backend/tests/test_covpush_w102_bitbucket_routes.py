"""Coverage wave 102 — integrations/bitbucket_routes.py (TDD, 0% baseline).

Fully mocked (BitbucketService methods patched on the module singleton, fake
get_current_user), zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): the data endpoints GET /workspaces,
GET /repositories and POST /search had NO authentication — anonymous users
could list workspaces/repositories and search code in the tenant's Bitbucket
account using a leaked access_token. The anonymous-401 tests below were RED
(200) before the fix; `get_current_user` is now required on all three.
(/auth/url, /auth/callback, /status and /health stay public, matching the
wave-93 dropbox OAuth-callback convention.)

Covers: /auth/url (success), /auth/callback (success, service failure -> 400,
missing code -> 422), /status (no token -> configured, token healthy -> ok,
token unhealthy -> ok False), /health (healthy), /workspaces (success, 500,
anon 401), /repositories (success with/without workspace, 500, anon 401),
/search (success, 500, anon 401, missing access_token -> 422).
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import bitbucket_routes as bbr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "bb102-user"
    u.email = "bb102@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(bbr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(bbr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    with patch.object(bbr.bitbucket_service, "get_authorization_url",
                      return_value="https://bitbucket.org/authorize?x=1"), \
            patch.object(bbr.bitbucket_service, "exchange_code_for_token",
                         return_value={"access_token": "at", "expires_in": 3600}), \
            patch.object(bbr.bitbucket_service, "get_health_status",
                         return_value={"status": "healthy", "user": "Rushi"}), \
            patch.object(bbr.bitbucket_service, "get_workspaces",
                         return_value=[{"slug": "ws1"}]), \
            patch.object(bbr.bitbucket_service, "get_repositories",
                         return_value=[{"full_name": "ws1/repo1"}]), \
            patch.object(bbr.bitbucket_service, "search_code",
                         return_value=[{"path": "src/main.py"}]):
        yield bbr.bitbucket_service


class TestAuthUrl:
    def test_success(self, anon_client):
        response = anon_client.get("/api/bitbucket/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert body["url"] == "https://bitbucket.org/authorize?x=1"
        assert body["service"] == "bitbucket"
        assert "timestamp" in body


class TestAuthCallback:
    def test_success(self, anon_client):
        response = anon_client.post("/api/bitbucket/auth/callback",
                                    json={"code": "auth-code-1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"]["access_token"] == "at"
        bbr.bitbucket_service.exchange_code_for_token.assert_called_once_with(
            "auth-code-1")

    def test_service_failure_400(self, anon_client):
        bbr.bitbucket_service.exchange_code_for_token.side_effect = \
            RuntimeError("bad code")
        response = anon_client.post("/api/bitbucket/auth/callback",
                                    json={"code": "bad"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Internal error"

    def test_missing_code_422(self, anon_client):
        response = anon_client.post("/api/bitbucket/auth/callback", json={})
        assert response.status_code == 422


class TestStatus:
    def test_no_token_configured(self, anon_client):
        response = anon_client.get("/api/bitbucket/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "configured"
        assert "Provide access_token" in body["message"]

    def test_with_token_healthy(self, anon_client):
        response = anon_client.get("/api/bitbucket/status",
                                   params={"access_token": "tok"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "healthy"
        assert body["user"] == "Rushi"
        bbr.bitbucket_service.get_health_status.assert_called_once_with("tok")

    def test_with_token_unhealthy(self, anon_client):
        bbr.bitbucket_service.get_health_status.return_value = {
            "status": "unhealthy", "user": None}
        response = anon_client.get("/api/bitbucket/status",
                                   params={"access_token": "tok"})
        assert response.status_code == 200
        assert response.json()["ok"] is False

    def test_health(self, anon_client):
        response = anon_client.get("/api/bitbucket/health")
        assert response.status_code == 200
        assert response.json()["status"] == "configured"


class TestWorkspaces:
    def test_success(self, client):
        response = client.get("/api/bitbucket/workspaces",
                              params={"access_token": "tok"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"] == [{"slug": "ws1"}]
        bbr.bitbucket_service.get_workspaces.assert_called_once_with("tok")

    def test_service_failure_500(self, client):
        bbr.bitbucket_service.get_workspaces.side_effect = HTTPException(
            status_code=403, detail="forbidden")
        response = client.get("/api/bitbucket/workspaces",
                              params={"access_token": "tok"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/bitbucket/workspaces",
                                   params={"access_token": "tok"})
        assert response.status_code == 401


class TestRepositories:
    def test_success_with_workspace(self, client):
        response = client.get("/api/bitbucket/repositories",
                              params={"access_token": "tok",
                                      "workspace": "ws1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"] == [{"full_name": "ws1/repo1"}]
        bbr.bitbucket_service.get_repositories.assert_called_once_with(
            "tok", "ws1")

    def test_success_without_workspace(self, client):
        response = client.get("/api/bitbucket/repositories",
                              params={"access_token": "tok"})
        assert response.status_code == 200
        bbr.bitbucket_service.get_repositories.assert_called_once_with(
            "tok", None)

    def test_service_failure_500(self, client):
        bbr.bitbucket_service.get_repositories.side_effect = \
            RuntimeError("boom")
        response = client.get("/api/bitbucket/repositories",
                              params={"access_token": "tok"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/bitbucket/repositories",
                                   params={"access_token": "tok"})
        assert response.status_code == 401


class TestSearch:
    def test_success(self, client):
        response = client.post(
            "/api/bitbucket/search",
            params={"access_token": "tok"},
            json={"query": "def main", "workspace": "ws1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["query"] == "def main"
        assert body["results"] == [{"path": "src/main.py"}]
        assert body["count"] == 1
        bbr.bitbucket_service.search_code.assert_called_once_with(
            "tok", "def main", "ws1")

    def test_success_without_workspace(self, client):
        response = client.post(
            "/api/bitbucket/search",
            params={"access_token": "tok"},
            json={"query": "TODO"})
        assert response.status_code == 200
        bbr.bitbucket_service.search_code.assert_called_once_with(
            "tok", "TODO", None)

    def test_service_failure_500(self, client):
        bbr.bitbucket_service.search_code.side_effect = RuntimeError("boom")
        response = client.post(
            "/api/bitbucket/search",
            params={"access_token": "tok"},
            json={"query": "TODO"})
        assert response.status_code == 500

    def test_missing_access_token_422(self, client):
        response = client.post("/api/bitbucket/search",
                               json={"query": "TODO"})
        assert response.status_code == 422

    def test_missing_query_422(self, client):
        response = client.post("/api/bitbucket/search",
                               params={"access_token": "tok"},
                               json={})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post(
            "/api/bitbucket/search",
            params={"access_token": "tok"},
            json={"query": "TODO"})
        assert response.status_code == 401

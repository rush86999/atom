"""Coverage wave 105 — integrations/mailchimp_routes.py (TDD, 0% baseline).

Fully mocked (mailchimp_service methods patched on the module singleton,
fake get_current_user), zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): the data endpoints GET /audiences,
GET /campaigns and GET /account had NO authentication — anonymous users
could query Mailchimp audience/campaign/account data with any leaked
access_token/server_prefix. The anonymous-401 tests below were RED (200)
before the fix; `get_current_user` is now required on all three.
(/auth/callback, /health and / stay public, matching the wave-98/102
dropbox/box convention for OAuth flow + status endpoints.)

Covers: /auth/callback (public success + dc metadata, service failure ->
400, missing code/redirect_uri -> 422), /audiences (success + count,
service failure -> 500, anon 401, missing server_prefix -> 422, limit
0/101 -> 422), /campaigns (success + count, status filter passthrough,
service failure -> 500, anon 401), /account (success, service failure ->
500, anon 401), /health (public), / (public).
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import mailchimp_routes as mr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "mailchimp105-user"
    u.email = "mailchimp105@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(mr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(mr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    with patch.object(mr.mailchimp_service, "exchange_token",
                      new=AsyncMock(return_value={"access_token": "at"})), \
            patch.object(mr.mailchimp_service, "get_metadata",
                         new=AsyncMock(return_value={"dc": "us1"})), \
            patch.object(mr.mailchimp_service, "get_audiences",
                         new=AsyncMock(return_value=[{"id": "a1"}])), \
            patch.object(mr.mailchimp_service, "get_campaigns",
                         new=AsyncMock(return_value=[{"id": "camp1"}])), \
            patch.object(mr.mailchimp_service, "get_account_info",
                         new=AsyncMock(return_value={"id": "acc1"})):
        yield mr.mailchimp_service


class TestAuthCallback:
    def test_success(self, anon_client):
        response = anon_client.post(
            "/api/mailchimp/auth/callback",
            json={"code": "c1", "redirect_uri": "http://localhost:8000/api/mailchimp/callback"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["access_token"] == "at"
        assert body["server_prefix"] == "us1"
        assert body["service"] == "mailchimp"
        mr.mailchimp_service.exchange_token.assert_awaited_once()
        mr.mailchimp_service.get_metadata.assert_awaited_once()

    def test_service_failure_400(self, anon_client):
        mr.mailchimp_service.exchange_token.side_effect = RuntimeError("boom")
        response = anon_client.post(
            "/api/mailchimp/auth/callback",
            json={"code": "c1", "redirect_uri": "http://localhost:8000/api/mailchimp/callback"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Internal error"

    def test_missing_code_422(self, anon_client):
        response = anon_client.post("/api/mailchimp/auth/callback",
                                    json={"redirect_uri": "http://x"})
        assert response.status_code == 422

    def test_missing_redirect_uri_422(self, anon_client):
        response = anon_client.post("/api/mailchimp/auth/callback", json={"code": "c1"})
        assert response.status_code == 422


class TestGetAudiences:
    def test_success(self, client):
        response = client.get("/api/mailchimp/audiences",
                              params={"access_token": "tok", "server_prefix": "us1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"] == [{"id": "a1"}]
        assert body["count"] == 1
        mr.mailchimp_service.get_audiences.assert_awaited_once_with("tok", "us1", 10)

    def test_custom_limit(self, client):
        response = client.get("/api/mailchimp/audiences",
                              params={"access_token": "tok", "server_prefix": "us1",
                                      "limit": 50})
        assert response.status_code == 200
        mr.mailchimp_service.get_audiences.assert_awaited_once_with("tok", "us1", 50)

    def test_service_failure_500(self, client):
        mr.mailchimp_service.get_audiences.side_effect = RuntimeError("boom")
        response = client.get("/api/mailchimp/audiences",
                              params={"access_token": "tok", "server_prefix": "us1"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/mailchimp/audiences",
                                   params={"access_token": "tok", "server_prefix": "us1"})
        assert response.status_code == 401

    def test_missing_server_prefix_422(self, client):
        response = client.get("/api/mailchimp/audiences",
                              params={"access_token": "tok"})
        assert response.status_code == 422

    def test_limit_zero_422(self, client):
        response = client.get("/api/mailchimp/audiences",
                              params={"access_token": "tok", "server_prefix": "us1",
                                      "limit": 0})
        assert response.status_code == 422

    def test_limit_too_high_422(self, client):
        response = client.get("/api/mailchimp/audiences",
                              params={"access_token": "tok", "server_prefix": "us1",
                                      "limit": 101})
        assert response.status_code == 422


class TestGetCampaigns:
    def test_success(self, client):
        response = client.get("/api/mailchimp/campaigns",
                              params={"access_token": "tok", "server_prefix": "us1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"] == [{"id": "camp1"}]
        assert body["count"] == 1
        mr.mailchimp_service.get_campaigns.assert_awaited_once_with("tok", "us1", 10, None)

    def test_status_filter(self, client):
        response = client.get("/api/mailchimp/campaigns",
                              params={"access_token": "tok", "server_prefix": "us1",
                                      "status": "sent"})
        assert response.status_code == 200
        mr.mailchimp_service.get_campaigns.assert_awaited_once_with("tok", "us1", 10, "sent")

    def test_service_failure_500(self, client):
        mr.mailchimp_service.get_campaigns.side_effect = RuntimeError("boom")
        response = client.get("/api/mailchimp/campaigns",
                              params={"access_token": "tok", "server_prefix": "us1"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/mailchimp/campaigns",
                                   params={"access_token": "tok", "server_prefix": "us1"})
        assert response.status_code == 401

    def test_missing_access_token_422(self, client):
        response = client.get("/api/mailchimp/campaigns",
                              params={"server_prefix": "us1"})
        assert response.status_code == 422


class TestGetAccountInfo:
    def test_success(self, client):
        response = client.get("/api/mailchimp/account",
                              params={"access_token": "tok", "server_prefix": "us1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"] == {"id": "acc1"}
        mr.mailchimp_service.get_account_info.assert_awaited_once_with("tok", "us1")

    def test_service_failure_500(self, client):
        mr.mailchimp_service.get_account_info.side_effect = RuntimeError("boom")
        response = client.get("/api/mailchimp/account",
                              params={"access_token": "tok", "server_prefix": "us1"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/mailchimp/account",
                                   params={"access_token": "tok", "server_prefix": "us1"})
        assert response.status_code == 401


class TestHealthRoot:
    def test_health(self, anon_client):
        response = anon_client.get("/api/mailchimp/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["service"] == "mailchimp"
        assert body["mode"] == "real"

    def test_root(self, anon_client):
        response = anon_client.get("/api/mailchimp/")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "mailchimp"
        assert "/audiences" in body["endpoints"]

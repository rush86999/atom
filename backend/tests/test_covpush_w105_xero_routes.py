"""Coverage wave 105 — integrations/xero_routes.py (TDD, 0% baseline).

Fully mocked (xero_service methods patched on the module singleton, fake
get_current_user), zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): the data endpoints GET /tenants,
GET /invoices and GET /contacts had NO authentication — anonymous users
could query Xero account data (invoices/contacts) with any leaked
access_token/tenant_id. The anonymous-401 tests below were RED (200) before
the fix; `get_current_user` is now required on all three. (/auth/url,
/auth/callback, /status and / stay public, matching the wave-98/102
dropbox/box convention for OAuth flow + status endpoints.)

Covers: /auth/url (public), /auth/callback (public success + service
failure -> 400, missing code/redirect_uri -> 422), /tenants (success,
service failure -> 500, anon 401, missing access_token -> 422),
/invoices (success + count, service failure -> 500, anon 401, missing
tenant_id -> 422, limit 0 -> 422, limit 101 -> 422), /contacts (success +
count, service failure -> 500, anon 401), /status (public), / (public).
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import xero_routes as xr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "xero105-user"
    u.email = "xero105@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(xr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(xr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    with patch.object(xr.xero_service, "exchange_token",
                      new=AsyncMock(return_value={
                          "access_token": "at", "refresh_token": "rt"})), \
            patch.object(xr.xero_service, "get_tenants",
                         new=AsyncMock(return_value=[{"id": "t1"}])), \
            patch.object(xr.xero_service, "get_invoices",
                         new=AsyncMock(return_value=[{"id": "inv1"}])), \
            patch.object(xr.xero_service, "get_contacts",
                         new=AsyncMock(return_value=[{"id": "c1"}])):
        yield xr.xero_service


class TestAuthUrl:
    def test_success(self, anon_client):
        response = anon_client.get("/api/xero/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert "url" in body and "timestamp" in body
        assert "login.xero.com" in body["url"]


class TestAuthCallback:
    def test_success(self, anon_client):
        response = anon_client.post(
            "/api/xero/auth/callback",
            json={"code": "c1", "redirect_uri": "http://localhost:8000/api/xero/callback"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["access_token"] == "at"
        assert body["refresh_token"] == "rt"
        assert body["tenants"] == [{"id": "t1"}]
        assert body["service"] == "xero"
        xr.xero_service.exchange_token.assert_awaited_once()
        xr.xero_service.get_tenants.assert_awaited_once()

    def test_service_failure_400(self, anon_client):
        xr.xero_service.exchange_token.side_effect = RuntimeError("boom")
        response = anon_client.post(
            "/api/xero/auth/callback",
            json={"code": "c1", "redirect_uri": "http://localhost:8000/api/xero/callback"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Internal error"

    def test_missing_code_422(self, anon_client):
        response = anon_client.post("/api/xero/auth/callback",
                                    json={"redirect_uri": "http://x"})
        assert response.status_code == 422

    def test_missing_redirect_uri_422(self, anon_client):
        response = anon_client.post("/api/xero/auth/callback", json={"code": "c1"})
        assert response.status_code == 422


class TestGetTenants:
    def test_success(self, client):
        response = client.get("/api/xero/tenants", params={"access_token": "tok"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"] == [{"id": "t1"}]
        xr.xero_service.get_tenants.assert_awaited_once_with("tok")

    def test_service_failure_500(self, client):
        xr.xero_service.get_tenants.side_effect = RuntimeError("boom")
        response = client.get("/api/xero/tenants", params={"access_token": "tok"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/xero/tenants",
                                   params={"access_token": "tok"})
        assert response.status_code == 401

    def test_missing_access_token_422(self, client):
        response = client.get("/api/xero/tenants")
        assert response.status_code == 422


class TestListInvoices:
    def test_success(self, client):
        response = client.get("/api/xero/invoices",
                              params={"access_token": "tok", "tenant_id": "t1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"] == [{"id": "inv1"}]
        assert body["count"] == 1
        xr.xero_service.get_invoices.assert_awaited_once_with("tok", "t1", 20)

    def test_custom_limit(self, client):
        response = client.get("/api/xero/invoices",
                              params={"access_token": "tok", "tenant_id": "t1",
                                      "limit": 50})
        assert response.status_code == 200
        xr.xero_service.get_invoices.assert_awaited_once_with("tok", "t1", 50)

    def test_service_failure_500(self, client):
        xr.xero_service.get_invoices.side_effect = RuntimeError("boom")
        response = client.get("/api/xero/invoices",
                              params={"access_token": "tok", "tenant_id": "t1"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/xero/invoices",
                                   params={"access_token": "tok", "tenant_id": "t1"})
        assert response.status_code == 401

    def test_missing_tenant_id_422(self, client):
        response = client.get("/api/xero/invoices", params={"access_token": "tok"})
        assert response.status_code == 422

    def test_limit_zero_422(self, client):
        response = client.get("/api/xero/invoices",
                              params={"access_token": "tok", "tenant_id": "t1",
                                      "limit": 0})
        assert response.status_code == 422

    def test_limit_too_high_422(self, client):
        response = client.get("/api/xero/invoices",
                              params={"access_token": "tok", "tenant_id": "t1",
                                      "limit": 101})
        assert response.status_code == 422


class TestListContacts:
    def test_success(self, client):
        response = client.get("/api/xero/contacts",
                              params={"access_token": "tok", "tenant_id": "t1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"] == [{"id": "c1"}]
        assert body["count"] == 1
        xr.xero_service.get_contacts.assert_awaited_once_with("tok", "t1", 20)

    def test_service_failure_500(self, client):
        xr.xero_service.get_contacts.side_effect = RuntimeError("boom")
        response = client.get("/api/xero/contacts",
                              params={"access_token": "tok", "tenant_id": "t1"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/xero/contacts",
                                   params={"access_token": "tok", "tenant_id": "t1"})
        assert response.status_code == 401

    def test_missing_access_token_422(self, client):
        response = client.get("/api/xero/contacts", params={"tenant_id": "t1"})
        assert response.status_code == 422


class TestStatusRoot:
    def test_status(self, anon_client):
        response = anon_client.get("/api/xero/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["service"] == "xero"
        assert body["status"] == "active"
        assert body["mode"] == "real"

    def test_root(self, anon_client):
        response = anon_client.get("/api/xero/")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "xero"
        assert "/invoices" in body["endpoints"]

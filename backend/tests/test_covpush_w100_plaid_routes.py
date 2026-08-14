"""Coverage wave 100 — integrations/plaid_routes.py (TDD, 0% baseline).

Fully mocked (PlaidService methods + client_id/secret/environment attrs),
zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): every data route (link/token/create,
item/public_token/exchange, accounts/get, accounts/balance/get,
transactions/get, identity/get, item/remove) had NO authentication — anyone
could burn the platform's Plaid quota, exchange stolen public tokens, and
read arbitrary linked accounts/transactions/identity by supplying an access
token. The anonymous-401 tests below were RED (200) before the fix;
`get_current_user` is now required on every data route. OAuth flow
(/auth/url, /callback) + /status + /health stay public (wave-98 dropbox
convention).

Covers: every route x {success, service-failure 500, anon 401, 422} as
applicable; /status both configured/not_configured branches; /health
healthy/unhealthy; legacy /auth/url; /callback success + error envelope.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi import HTTPException

from core.auth import get_current_user
from core.models import User

from integrations import plaid_routes as pr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "plaid100-user"
    u.email = "plaid100@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(pr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(pr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    """Patch every PlaidService method + attrs used by the routes."""
    with patch.multiple(
        pr.plaid_service,
        create_link_token=AsyncMock(return_value={"link_token": "lt-1"}),
        exchange_public_token=AsyncMock(return_value={"access_token": "at-1"}),
        get_accounts=AsyncMock(return_value={"accounts": [{"id": "a1"}]}),
        get_balance=AsyncMock(return_value={"accounts": [{"id": "a1"}]}),
        get_transactions=AsyncMock(return_value={"transactions": []}),
        get_identity=AsyncMock(return_value={"identity": {"names": ["A"]}}),
        remove_item=AsyncMock(return_value={"removed": True}),
        health_check=AsyncMock(return_value={"ok": True}),
        client_id="plaid-client-100",
        secret="plaid-secret-100",
        environment="sandbox",
    ):
        yield pr.plaid_service


class TestLinkToken:
    def test_success(self, client):
        response = client.post("/api/plaid/link/token/create",
                               json={"user_id": "u1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["link_token"] == "lt-1"
        assert "timestamp" in body
        pr.plaid_service.create_link_token.assert_awaited_once()
        assert pr.plaid_service.create_link_token.await_args.kwargs[
            "user_id"] == "u1"

    def test_custom_fields(self, client):
        response = client.post("/api/plaid/link/token/create", json={
            "user_id": "u2", "client_name": "Acme",
            "country_codes": ["US"], "products": ["transactions"]})
        assert response.status_code == 200
        kwargs = pr.plaid_service.create_link_token.await_args.kwargs
        assert kwargs["client_name"] == "Acme"
        assert kwargs["country_codes"] == ["US"]
        assert kwargs["products"] == ["transactions"]

    def test_missing_user_id_422(self, client):
        response = client.post("/api/plaid/link/token/create", json={})
        assert response.status_code == 422

    def test_http_exception_re_raised(self, client):
        pr.plaid_service.create_link_token.side_effect = \
            HTTPException(status_code=429, detail="rate limited")
        response = client.post("/api/plaid/link/token/create",
                               json={"user_id": "u1"})
        assert response.status_code == 429

    def test_service_failure_500(self, client):
        pr.plaid_service.create_link_token.side_effect = \
            RuntimeError("boom")
        response = client.post("/api/plaid/link/token/create",
                               json={"user_id": "u1"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/plaid/link/token/create",
                                    json={"user_id": "u1"})
        assert response.status_code == 401


class TestPublicTokenExchange:
    def test_success(self, client):
        response = client.post("/api/plaid/item/public_token/exchange",
                               json={"public_token": "pub-1"})
        assert response.status_code == 200
        assert response.json()["access_token"] == "at-1"
        pr.plaid_service.exchange_public_token.assert_awaited_once_with(
            "pub-1")

    def test_http_exception_re_raised(self, client):
        pr.plaid_service.exchange_public_token.side_effect = \
            HTTPException(status_code=403, detail="forbidden")
        response = client.post("/api/plaid/item/public_token/exchange",
                               json={"public_token": "pub-1"})
        assert response.status_code == 403
        assert response.json()["detail"] == "forbidden"

    def test_missing_public_token_422(self, client):
        response = client.post("/api/plaid/item/public_token/exchange",
                               json={})
        assert response.status_code == 422

    def test_service_failure_500(self, client):
        pr.plaid_service.exchange_public_token.side_effect = \
            RuntimeError("boom")
        response = client.post("/api/plaid/item/public_token/exchange",
                               json={"public_token": "pub-1"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/plaid/item/public_token/exchange",
                                    json={"public_token": "pub-1"})
        assert response.status_code == 401


class TestAccounts:
    def test_success(self, client):
        response = client.post("/api/plaid/accounts/get",
                               json={"access_token": "at-1"})
        assert response.status_code == 200
        assert response.json()["accounts"][0]["id"] == "a1"

    def test_service_failure_500(self, client):
        pr.plaid_service.get_accounts.side_effect = RuntimeError("boom")
        response = client.post("/api/plaid/accounts/get",
                               json={"access_token": "at-1"})
        assert response.status_code == 500

    def test_http_exception_re_raised(self, client):
        pr.plaid_service.get_accounts.side_effect = \
            HTTPException(status_code=403, detail="forbidden")
        response = client.post("/api/plaid/accounts/get",
                               json={"access_token": "at-1"})
        assert response.status_code == 403

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/plaid/accounts/get",
                                    json={"access_token": "at-1"})
        assert response.status_code == 401


class TestBalance:
    def test_success(self, client):
        response = client.post("/api/plaid/accounts/balance/get",
                               json={"access_token": "at-1"})
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_service_failure_500(self, client):
        pr.plaid_service.get_balance.side_effect = RuntimeError("boom")
        response = client.post("/api/plaid/accounts/balance/get",
                               json={"access_token": "at-1"})
        assert response.status_code == 500

    def test_http_exception_re_raised(self, client):
        pr.plaid_service.get_balance.side_effect = \
            HTTPException(status_code=403, detail="forbidden")
        response = client.post("/api/plaid/accounts/balance/get",
                               json={"access_token": "at-1"})
        assert response.status_code == 403

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/plaid/accounts/balance/get",
                                    json={"access_token": "at-1"})
        assert response.status_code == 401


class TestTransactions:
    def test_success(self, client):
        response = client.post("/api/plaid/transactions/get", json={
            "access_token": "at-1", "start_date": "2026-01-01",
            "end_date": "2026-02-01", "count": 50, "offset": 10})
        assert response.status_code == 200
        kwargs = pr.plaid_service.get_transactions.await_args.kwargs
        assert kwargs["count"] == 50
        assert kwargs["offset"] == 10

    def test_defaults(self, client):
        response = client.post("/api/plaid/transactions/get", json={
            "access_token": "at-1", "start_date": "2026-01-01",
            "end_date": "2026-02-01"})
        assert response.status_code == 200
        kwargs = pr.plaid_service.get_transactions.await_args.kwargs
        assert kwargs["count"] == 100
        assert kwargs["offset"] == 0

    def test_missing_dates_422(self, client):
        response = client.post("/api/plaid/transactions/get",
                               json={"access_token": "at-1"})
        assert response.status_code == 422

    def test_service_failure_500(self, client):
        pr.plaid_service.get_transactions.side_effect = RuntimeError("boom")
        response = client.post("/api/plaid/transactions/get", json={
            "access_token": "at-1", "start_date": "2026-01-01",
            "end_date": "2026-02-01"})
        assert response.status_code == 500

    def test_http_exception_re_raised(self, client):
        pr.plaid_service.get_transactions.side_effect = \
            HTTPException(status_code=403, detail="forbidden")
        response = client.post("/api/plaid/transactions/get", json={
            "access_token": "at-1", "start_date": "2026-01-01",
            "end_date": "2026-02-01"})
        assert response.status_code == 403

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/plaid/transactions/get", json={
            "access_token": "at-1", "start_date": "2026-01-01",
            "end_date": "2026-02-01"})
        assert response.status_code == 401


class TestIdentity:
    def test_success(self, client):
        response = client.post("/api/plaid/identity/get",
                               json={"access_token": "at-1"})
        assert response.status_code == 200
        assert response.json()["identity"]["names"] == ["A"]

    def test_service_failure_500(self, client):
        pr.plaid_service.get_identity.side_effect = RuntimeError("boom")
        response = client.post("/api/plaid/identity/get",
                               json={"access_token": "at-1"})
        assert response.status_code == 500

    def test_http_exception_re_raised(self, client):
        pr.plaid_service.get_identity.side_effect = \
            HTTPException(status_code=403, detail="forbidden")
        response = client.post("/api/plaid/identity/get",
                               json={"access_token": "at-1"})
        assert response.status_code == 403

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/plaid/identity/get",
                                    json={"access_token": "at-1"})
        assert response.status_code == 401


class TestRemoveItem:
    def test_success(self, client):
        response = client.post("/api/plaid/item/remove",
                               json={"access_token": "at-1"})
        assert response.status_code == 200
        assert response.json()["removed"] is True

    def test_service_failure_500(self, client):
        pr.plaid_service.remove_item.side_effect = RuntimeError("boom")
        response = client.post("/api/plaid/item/remove",
                               json={"access_token": "at-1"})
        assert response.status_code == 500

    def test_http_exception_re_raised(self, client):
        pr.plaid_service.remove_item.side_effect = \
            HTTPException(status_code=403, detail="forbidden")
        response = client.post("/api/plaid/item/remove",
                               json={"access_token": "at-1"})
        assert response.status_code == 403

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/plaid/item/remove",
                                    json={"access_token": "at-1"})
        assert response.status_code == 401


class TestStatusHealth:
    def test_status_configured(self, anon_client):
        response = anon_client.get("/api/plaid/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"
        assert body["environment"] == "sandbox"
        assert body["business_value"]["expense_tracking"] is True

    def test_status_not_configured(self, anon_client):
        with patch.object(pr.plaid_service, "client_id", None):
            response = anon_client.get("/api/plaid/status")
        assert response.status_code == 200
        assert response.json()["status"] == "not_configured"

    def test_health_healthy(self, anon_client):
        response = anon_client.get("/api/plaid/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["configured"] is True

    def test_health_unhealthy(self, anon_client):
        pr.plaid_service.health_check.return_value = {"ok": False}
        with patch.object(pr.plaid_service, "secret", None):
            response = anon_client.get("/api/plaid/health")
        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"
        assert response.json()["configured"] is False


class TestLegacyEndpoints:
    def test_auth_url(self, anon_client):
        response = anon_client.get("/api/plaid/auth/url")
        assert response.status_code == 200
        assert "link/token/create" in response.json()["message"]

    def test_callback_success(self, anon_client):
        response = anon_client.get("/api/plaid/callback",
                                   params={"public_token": "pub-1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "success"
        assert body["access_token"] == "at-1"

    def test_callback_service_error(self, anon_client):
        pr.plaid_service.exchange_public_token.side_effect = \
            RuntimeError("invalid public token")
        response = anon_client.get("/api/plaid/callback",
                                   params={"public_token": "bad"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["status"] == "error"
        assert "invalid public token" in body["message"]

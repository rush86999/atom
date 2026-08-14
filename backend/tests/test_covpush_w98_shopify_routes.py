"""Coverage wave 98 — integrations/shopify_routes.py (TDD, 0% baseline).

Fully mocked (ShopifyService methods, fake DB session, SSRF guard), zero
network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): every data route (/shop, /products,
/orders, /customers*, /fulfillments*, /refunds*, /draft-orders*,
/transactions, /analytics, /inventory, /locations, /webhooks/setup,
/auth/callback) had NO authentication — anyone could query arbitrary shop
domains with a stolen/leaked access token (token exposed in the URL, the
request would also land in proxy logs). The anonymous-401 tests below were
RED (200) before the fix; `get_current_user` is now required on every data
route (OAuth flow + status/root stay public, matching the wave-93 dropbox
convention).

Webhook HMAC fail-closed (SHOPIFY_WEBHOOK_SECRET missing -> 401) lives in
api/routes/webhooks/shopify_webhooks.py (already covered by waves 8/71c) —
the /webhooks/setup route in this module only REGISTERS webhooks, and its
SSRF guard is covered here.

Covers: /auth/url, /auth/callback (new store, existing store update, exchange
failure -> 400, missing access_token -> 400), /shop, /products, /orders,
/status, /webhooks/setup (success + SSRFError -> 400), /, /customers,
/customers/search, /customers/{id}, /fulfillments/{id} GET+POST,
/refunds/{id}, /draft-orders, /draft-orders/{id}/complete, /transactions/{id},
/analytics, /inventory, /locations (success + service-error 500 + anon 401),
limit validation 422.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db
from core.models import User

from integrations import shopify_routes as sr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "shopify98-user"
    u.email = "shopify98@x.com"
    return u


@pytest.fixture
def db_session():
    return MagicMock()


@pytest.fixture
def client(user, db_session):
    app = FastAPI()
    app.include_router(sr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(db_session):
    app = FastAPI()
    app.include_router(sr.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    """Patch every ShopifyService method used by the routes."""
    methods = [
        "exchange_token", "get_shop_info", "get_products", "get_orders",
        "register_webhooks", "get_customers", "search_customers",
        "get_customer", "get_fulfillments", "create_fulfillment",
        "get_refunds", "get_draft_orders", "complete_draft_order",
        "get_transactions", "get_shop_analytics", "get_inventory_levels",
        "get_locations",
    ]
    with patch.multiple(sr.shopify_service, **{
        m: AsyncMock(return_value=[]) for m in methods
    }):
        yield sr.shopify_service


def _q(params):
    return {"access_token": "tok-98", "shop": "my-shop.myshopify.com",
            **params}


class TestOAuthEndpoints:
    def test_auth_url(self, anon_client):
        response = anon_client.get("/api/shopify/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert body["url"].startswith("https://{shop}.myshopify.com")
        assert "timestamp" in body

    def test_callback_new_store(self, anon_client, db_session):
        sr.shopify_service.exchange_token.return_value = {
            "access_token": "tok-1", "scope": "read_products"}
        db_session.query.return_value.filter.return_value.first.\
            return_value = None
        response = anon_client.post("/api/shopify/auth/callback", json={
            "code": "code-1", "shop": "my-shop.myshopify.com",
            "workspace_id": "ws-1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["access_token"] == "tok-1"
        assert body["scope"] == "read_products"
        assert body["workspace_id"] == "ws-1"
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
        store = db_session.add.call_args[0][0]
        assert store.platform == "shopify"
        assert store.shop_domain == "my-shop.myshopify.com"
        assert store.access_token == "tok-1"

    def test_callback_existing_store(self, anon_client, db_session):
        sr.shopify_service.exchange_token.return_value = {
            "access_token": "tok-2", "scope": "write"}
        existing = MagicMock()
        existing.metadata_json = {"workspace_id": "ws-old"}
        db_session.query.return_value.filter.return_value.first.\
            return_value = existing
        response = anon_client.post("/api/shopify/auth/callback", json={
            "code": "code-2", "shop": "my-shop.myshopify.com",
            "workspace_id": "ws-2"})
        assert response.status_code == 200
        assert existing.access_token == "tok-2"
        assert existing.metadata_json["workspace_id"] == "ws-2"
        db_session.add.assert_not_called()
        db_session.commit.assert_called_once()

    def test_callback_exchange_failure_400(self, anon_client):
        sr.shopify_service.exchange_token.side_effect = \
            RuntimeError("invalid code")
        response = anon_client.post("/api/shopify/auth/callback", json={
            "code": "bad", "shop": "my-shop.myshopify.com"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Internal error"

    def test_callback_missing_access_token_400(self, anon_client):
        sr.shopify_service.exchange_token.return_value = {"scope": "x"}
        response = anon_client.post("/api/shopify/auth/callback", json={
            "code": "code-3", "shop": "my-shop.myshopify.com"})
        assert response.status_code == 400


class TestShopEndpoints:
    def test_shop_success(self, client):
        sr.shopify_service.get_shop_info.return_value = {
            "name": "ACME", "domain": "my-shop.myshopify.com"}
        response = client.get("/api/shopify/shop", params=_q({}))
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "ACME"

    def test_shop_error_500(self, client):
        sr.shopify_service.get_shop_info.side_effect = \
            RuntimeError("boom")
        response = client.get("/api/shopify/shop", params=_q({}))
        assert response.status_code == 500

    def test_shop_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/shop",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401

    def test_products_success(self, client):
        sr.shopify_service.get_products.return_value = [
            {"id": 1, "title": "Widget"}]
        response = client.get("/api/shopify/products", params=_q({"limit": 5}))
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert body["data"][0]["title"] == "Widget"

    def test_products_limit_validation_422(self, client):
        response = client.get(
            "/api/shopify/products", params=_q({"limit": 0}))
        assert response.status_code == 422
        response = client.get(
            "/api/shopify/products", params=_q({"limit": 101}))
        assert response.status_code == 422

    def test_products_error_500(self, client):
        sr.shopify_service.get_products.side_effect = \
            RuntimeError("boom")
        response = client.get("/api/shopify/products", params=_q({}))
        assert response.status_code == 500

    def test_products_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/products",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401

    def test_orders_success(self, client):
        sr.shopify_service.get_orders.return_value = [{"id": 10}]
        response = client.get("/api/shopify/orders", params=_q({}))
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_orders_error_500(self, client):
        sr.shopify_service.get_orders.side_effect = RuntimeError("boom")
        response = client.get("/api/shopify/orders", params=_q({}))
        assert response.status_code == 500

    def test_orders_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/orders",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401

    def test_status(self, anon_client):
        response = anon_client.get("/api/shopify/status")
        assert response.status_code == 200
        assert response.json()["mode"] == "real"

    def test_root(self, anon_client):
        response = anon_client.get("/api/shopify/")
        assert response.status_code == 200
        assert "endpoints" in response.json()


class TestWebhooksSetup:
    def test_success(self, client):
        sr.shopify_service.register_webhooks.return_value = [
            {"topic": "products/create", "id": 1}]
        response = client.post(
            "/api/shopify/webhooks/setup",
            params=_q({"webhook_base_url":
                       "https://hooks.example.com/api/webhooks/shopify"}))
        assert response.status_code == 200
        assert response.json()["results"][0]["topic"] == "products/create"

    def test_ssrf_blocked_400(self, client):
        from core.ssrf_guard import SSRFError

        with patch("core.ssrf_guard.validate_url",
                   side_effect=SSRFError("private ip")):
            response = client.post(
                "/api/shopify/webhooks/setup",
                params=_q({"webhook_base_url":
                           "http://169.254.169.254/latest/meta-data"}))
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid webhook configuration"
        sr.shopify_service.register_webhooks.assert_not_awaited()

    def test_error_500(self, client):
        sr.shopify_service.register_webhooks.side_effect = \
            RuntimeError("boom")
        response = client.post(
            "/api/shopify/webhooks/setup",
            params=_q({"webhook_base_url": "https://hooks.example.com/x"}))
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        response = anon_client.post(
            "/api/shopify/webhooks/setup",
            params={"access_token": "t", "shop": "s.myshopify.com",
                    "webhook_base_url": "https://h.example.com/x"})
        assert response.status_code == 401


class TestCustomers:
    def test_list_success(self, client):
        sr.shopify_service.get_customers.return_value = [
            {"id": 1, "email": "a@b.c"}]
        response = client.get("/api/shopify/customers", params=_q({}))
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_list_error_500(self, client):
        sr.shopify_service.get_customers.side_effect = RuntimeError("boom")
        response = client.get("/api/shopify/customers", params=_q({}))
        assert response.status_code == 500

    def test_list_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/customers",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401

    def test_search_success(self, client):
        sr.shopify_service.search_customers.return_value = [
            {"id": 2, "email": "x@y.z"}]
        response = client.get(
            "/api/shopify/customers/search",
            params=_q({"query": "a@b.c"}))
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_search_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/customers/search",
            params={"access_token": "t", "shop": "s.myshopify.com",
                    "query": "q"})
        assert response.status_code == 401

    def test_get_success(self, client):
        sr.shopify_service.get_customer.return_value = {
            "id": 1, "email": "a@b.c"}
        response = client.get(
            "/api/shopify/customers/1", params=_q({}))
        assert response.status_code == 200
        assert response.json()["data"]["id"] == 1

    def test_get_error_500(self, client):
        sr.shopify_service.get_customer.side_effect = RuntimeError("boom")
        response = client.get("/api/shopify/customers/1", params=_q({}))
        assert response.status_code == 500

    def test_get_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/customers/1",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401


class TestFulfillments:
    def test_get_success(self, client):
        sr.shopify_service.get_fulfillments.return_value = [{"id": 5}]
        response = client.get(
            "/api/shopify/fulfillments/10", params=_q({}))
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_get_error_500(self, client):
        sr.shopify_service.get_fulfillments.side_effect = \
            RuntimeError("boom")
        response = client.get(
            "/api/shopify/fulfillments/10", params=_q({}))
        assert response.status_code == 500

    def test_get_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/fulfillments/10",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401

    def test_create_success(self, client):
        sr.shopify_service.create_fulfillment.return_value = {
            "id": 7, "status": "success"}
        response = client.post(
            "/api/shopify/fulfillments/10",
            params=_q({"location_id": "loc-1", "tracking_number": "TN1",
                       "tracking_company": "UPS"}))
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "success"

    def test_create_no_tracking(self, client):
        sr.shopify_service.create_fulfillment.return_value = {"id": 8}
        response = client.post(
            "/api/shopify/fulfillments/10",
            params=_q({"location_id": "loc-1"}))
        assert response.status_code == 200

    def test_create_error_500(self, client):
        sr.shopify_service.create_fulfillment.side_effect = \
            RuntimeError("boom")
        response = client.post(
            "/api/shopify/fulfillments/10",
            params=_q({"location_id": "loc-1"}))
        assert response.status_code == 500

    def test_create_anonymous_401(self, anon_client):
        response = anon_client.post(
            "/api/shopify/fulfillments/10",
            params={"access_token": "t", "shop": "s.myshopify.com",
                    "location_id": "loc-1"})
        assert response.status_code == 401


class TestRefunds:
    def test_get_success(self, client):
        sr.shopify_service.get_refunds.return_value = [{"id": 3}]
        response = client.get("/api/shopify/refunds/10", params=_q({}))
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_get_error_500(self, client):
        sr.shopify_service.get_refunds.side_effect = RuntimeError("boom")
        response = client.get("/api/shopify/refunds/10", params=_q({}))
        assert response.status_code == 500

    def test_get_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/refunds/10",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401


class TestDraftOrders:
    def test_list_success(self, client):
        sr.shopify_service.get_draft_orders.return_value = [{"id": 4}]
        response = client.get("/api/shopify/draft-orders", params=_q({}))
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_list_error_500(self, client):
        sr.shopify_service.get_draft_orders.side_effect = \
            RuntimeError("boom")
        response = client.get("/api/shopify/draft-orders", params=_q({}))
        assert response.status_code == 500

    def test_list_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/draft-orders",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401

    def test_complete_success(self, client):
        sr.shopify_service.complete_draft_order.return_value = {
            "id": 4, "status": "completed"}
        response = client.post(
            "/api/shopify/draft-orders/4/complete", params=_q({}))
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "completed"

    def test_complete_error_500(self, client):
        sr.shopify_service.complete_draft_order.side_effect = \
            RuntimeError("boom")
        response = client.post(
            "/api/shopify/draft-orders/4/complete", params=_q({}))
        assert response.status_code == 500

    def test_complete_anonymous_401(self, anon_client):
        response = anon_client.post(
            "/api/shopify/draft-orders/4/complete",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401


class TestTransactions:
    def test_get_success(self, client):
        sr.shopify_service.get_transactions.return_value = [{"id": 9}]
        response = client.get(
            "/api/shopify/transactions/10", params=_q({}))
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_get_error_500(self, client):
        sr.shopify_service.get_transactions.side_effect = \
            RuntimeError("boom")
        response = client.get(
            "/api/shopify/transactions/10", params=_q({}))
        assert response.status_code == 500

    def test_get_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/transactions/10",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401


class TestAnalyticsInventoryLocations:
    def test_analytics_success(self, client):
        sr.shopify_service.get_shop_analytics.return_value = {
            "revenue": 1000}
        response = client.get("/api/shopify/analytics", params=_q({}))
        assert response.status_code == 200
        assert response.json()["data"]["revenue"] == 1000

    def test_analytics_error_500(self, client):
        sr.shopify_service.get_shop_analytics.side_effect = \
            RuntimeError("boom")
        response = client.get("/api/shopify/analytics", params=_q({}))
        assert response.status_code == 500

    def test_analytics_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/analytics",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401

    def test_inventory_success(self, client):
        sr.shopify_service.get_inventory_levels.return_value = [{"id": 1}]
        response = client.get(
            "/api/shopify/inventory", params=_q({"location_id": "loc-1"}))
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_inventory_no_location(self, client):
        sr.shopify_service.get_inventory_levels.return_value = []
        response = client.get("/api/shopify/inventory", params=_q({}))
        assert response.status_code == 200

    def test_inventory_error_500(self, client):
        sr.shopify_service.get_inventory_levels.side_effect = \
            RuntimeError("boom")
        response = client.get("/api/shopify/inventory", params=_q({}))
        assert response.status_code == 500

    def test_inventory_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/inventory",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401

    def test_locations_success(self, client):
        sr.shopify_service.get_locations.return_value = [{"id": 1}]
        response = client.get("/api/shopify/locations", params=_q({}))
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_locations_error_500(self, client):
        sr.shopify_service.get_locations.side_effect = RuntimeError("boom")
        response = client.get("/api/shopify/locations", params=_q({}))
        assert response.status_code == 500

    def test_locations_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/shopify/locations",
            params={"access_token": "t", "shop": "s.myshopify.com"})
        assert response.status_code == 401

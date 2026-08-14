# -*- coding: utf-8 -*-
"""Coverage wave 95 — integrations/shopify_service (ShopifyService).

Standalone, fully mocked (IntegrationHTTP + httpx.Response objects + in-memory
SQLite for sync), zero network, zero LLM spend.

Covers: __init__ (config + env fallbacks, empty), _get_base_url (with/without
.myshopify.com suffix), _get_headers, exchange_token (success, HTTPError ->
400), get_products / get_orders / get_shop_info / get_inventory_levels
(with/without location) / get_locations / get_customers / get_customer /
search_customers / get_fulfillments / create_fulfillment (with/without
tracking) / get_refunds / calculate_refund / get_draft_orders /
create_draft_order (with/without customer) / complete_draft_order /
get_transactions: success + 500 exception paths; get_order_count /
get_product_count / get_customer_count success + exception -> 0;
get_shop_analytics success + 500; get_capabilities; health_check
healthy/unhealthy/exception path -> generic message (NO str(e) leak);
execute_operation (all 12 ops, unknown op, inner exception -> generic
envelope); handle_webhook_event (orders/create + other); sync_to_postgres_cache
(missing creds, success with REAL IntegrationMetric model, update path, error
path generic); full_sync.

Bug found (TDD RED -> GREEN): health_check exception path leaked str(e).
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import IntegrationMetric  # noqa: F401 (register model)
from integrations.shopify_service import ShopifyService


_EMPTY = object()


def _svc(config=None):
    if config is _EMPTY:
        config = {}
    elif config is None:
        config = {"api_key": "k", "api_secret": "s", "shop_name": "my-shop.myshopify.com",
                  "access_token": "at"}
    svc = ShopifyService(tenant_id="t1", config=config)
    svc.http = MagicMock()
    return svc


def _resp(status=200, payload=None):
    return httpx.Response(status, json=payload if payload is not None else {},
                          request=httpx.Request("GET", "http://x"))


class TestInit:
    def test_config(self):
        svc = ShopifyService(config={"api_key": "k", "api_secret": "s",
                                     "shop_name": "shop"})
        assert svc.api_key == "k"
        assert svc.api_secret == "s"
        assert svc.shop_name == "shop"

    def test_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("SHOPIFY_API_KEY", "env-k")
        monkeypatch.setenv("SHOPIFY_API_SECRET", "env-s")
        monkeypatch.setenv("SHOPIFY_SHOP_NAME", "env-shop")
        svc = ShopifyService()
        assert svc.api_key == "env-k"
        assert svc.api_secret == "env-s"
        assert svc.shop_name == "env-shop"

    def test_empty(self, monkeypatch):
        monkeypatch.delenv("SHOPIFY_API_KEY", raising=False)
        monkeypatch.delenv("SHOPIFY_API_SECRET", raising=False)
        monkeypatch.delenv("SHOPIFY_SHOP_NAME", raising=False)
        svc = ShopifyService(config={})
        assert svc.api_key is None


class TestHelpers:
    def test_base_url_appends_domain(self):
        svc = _svc()
        assert svc._get_base_url("my-shop") == "https://my-shop.myshopify.com/admin/api/2023-10"

    def test_base_url_keeps_domain(self):
        svc = _svc()
        assert svc._get_base_url("other.myshopify.com") == \
            "https://other.myshopify.com/admin/api/2023-10"

    def test_get_headers(self):
        svc = _svc()
        h = svc._get_headers("tok")
        assert h["X-Shopify-Access-Token"] == "tok"
        assert h["Content-Type"] == "application/json"


class TestExchangeToken:
    async def test_success(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_resp(200, {"access_token": "at"}))
        out = await svc.exchange_token("code1", "shop.myshopify.com")
        assert out == {"access_token": "at"}
        url, kwargs = svc.http.post.call_args.args[1], svc.http.post.call_args.kwargs
        assert url.endswith("/admin/oauth/access_token")
        assert kwargs["json"]["client_id"] == "k"

    async def test_http_error_400(self):
        svc = _svc()
        svc.http.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(HTTPException) as ei:
            await svc.exchange_token("c", "shop")
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"


class TestProducts:
    async def test_success(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"products": [{"id": 1}]}))
        out = await svc.get_products("tok", "shop")
        assert out == [{"id": 1}]
        assert svc.http.get.call_args.kwargs["params"] == {"limit": 20}

    async def test_custom_limit(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"products": []}))
        await svc.get_products("tok", "shop", limit=5)
        assert svc.http.get.call_args.kwargs["params"] == {"limit": 5}

    async def test_missing_key_returns_empty(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {}))
        assert await svc.get_products("tok", "shop") == []

    async def test_error_500(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_products("tok", "shop")
        assert ei.value.status_code == 500


class TestOrders:
    async def test_success(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"orders": [{"id": 1}]}))
        out = await svc.get_orders("tok", "shop")
        assert out == [{"id": 1}]
        assert svc.http.get.call_args.kwargs["params"] == {"limit": 20, "status": "any"}

    async def test_error_500(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_orders("tok", "shop")
        assert ei.value.status_code == 500


class TestShopInfo:
    async def test_success(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"shop": {"name": "ACME"}}))
        assert await svc.get_shop_info("tok", "shop") == {"name": "ACME"}

    async def test_error_500(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_shop_info("tok", "shop")
        assert ei.value.status_code == 500


class TestWebhooks:
    async def test_all_registered(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_resp(201, {"webhook": {"id": 1}}))
        out = await svc.register_webhooks("tok", "shop", "https://cb.atom.io/hook")
        assert len(out) == 3
        assert all(r["status"] == "registered" for r in out)
        urls = [c.args[1] for c in svc.http.post.call_args_list]
        assert all(u.endswith("/webhooks.json") for u in urls)

    async def test_already_exists_422(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_resp(422, {}))
        out = await svc.register_webhooks("tok", "shop", "https://cb")
        assert all(r["status"] == "already_exists" for r in out)

    async def test_mixed_results(self):
        svc = _svc()
        responses = [_resp(201, {}), _resp(422, {}), _resp(500, {})]
        svc.http.post = AsyncMock(side_effect=responses)
        out = await svc.register_webhooks("tok", "shop", "https://cb")
        assert [r["status"] for r in out] == ["registered", "already_exists", "failed"]
        failed = out[2]
        assert failed["error"] == "Webhook registration failed"

    async def test_exception_per_topic(self):
        svc = _svc()
        def _boom(*a, **k):
            raise httpx.ConnectError("net")
        svc.http.post = AsyncMock(side_effect=_boom)
        out = await svc.register_webhooks("tok", "shop", "https://cb")
        assert all(r["status"] == "failed" for r in out)
        assert all("failed" in r["error"] for r in out)

    async def test_topic_addresses(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_resp(201, {}))
        await svc.register_webhooks("tok", "shop", "https://cb.atom.io")
        addresses = [c.kwargs["json"]["webhook"]["address"] for c in svc.http.post.call_args_list]
        assert addresses == [
            "https://cb.atom.io/orders-create",
            "https://cb.atom.io/orders-updated",
            "https://cb.atom.io/refunds-create",
        ]
        topics = [c.kwargs["json"]["webhook"]["topic"] for c in svc.http.post.call_args_list]
        assert topics == ["orders/create", "orders/updated", "refunds/create"]


class TestInventory:
    async def _s(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"inventory_levels": [{"id": 1}]}))
        return svc

    async def test_with_location(self):
        svc = await self._s()
        out = await svc.get_inventory_levels("tok", "shop", location_id="loc1")
        assert out == [{"id": 1}]
        assert svc.http.get.call_args.kwargs["params"] == {"location_ids": "loc1"}

    async def test_without_location(self):
        svc = await self._s()
        await svc.get_inventory_levels("tok", "shop")
        assert svc.http.get.call_args.kwargs["params"] == {}

    async def test_error_500(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_inventory_levels("tok", "shop")
        assert ei.value.status_code == 500

    async def test_get_locations(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"locations": [{"id": 1}]}))
        assert await svc.get_locations("tok", "shop") == [{"id": 1}]

    async def test_get_locations_error(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException):
            await svc.get_locations("tok", "shop")


class TestCustomers:
    async def test_get_customers(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"customers": [{"id": 1}]}))
        assert await svc.get_customers("tok", "shop") == [{"id": 1}]
        assert svc.http.get.call_args.kwargs["params"] == {"limit": 20}

    async def test_get_customers_error(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_customers("tok", "shop")
        assert ei.value.status_code == 500

    async def test_get_customer(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"customer": {"id": "c1"}}))
        assert await svc.get_customer("tok", "shop", "c1") == {"id": "c1"}
        assert svc.http.get.call_args.args[1].endswith("/customers/c1.json")

    async def test_get_customer_error(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_customer("tok", "shop", "c1")
        assert ei.value.status_code == 500

    async def test_search_customers(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"customers": [{"id": 1}]}))
        assert await svc.search_customers("tok", "shop", "ada@x.com") == [{"id": 1}]
        assert svc.http.get.call_args.kwargs["params"] == {"query": "ada@x.com"}

    async def test_search_customers_error(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException):
            await svc.search_customers("tok", "shop", "q")


class TestFulfillments:
    async def test_get_fulfillments(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"fulfillments": [{"id": 1}]}))
        assert await svc.get_fulfillments("tok", "shop", "o1") == [{"id": 1}]

    async def test_get_fulfillments_error(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_fulfillments("tok", "shop", "o1")
        assert ei.value.status_code == 500

    async def test_create_fulfillment_full(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_resp(201, {"fulfillment": {"id": 1}}))
        out = await svc.create_fulfillment("tok", "shop", "o1", "loc1",
                                           tracking_number="TN1", tracking_company="UPS")
        assert out == {"id": 1}
        body = svc.http.post.call_args.kwargs["json"]["fulfillment"]
        assert body == {"location_id": "loc1", "notify_customer": True,
                        "tracking_number": "TN1", "tracking_company": "UPS"}

    async def test_create_fulfillment_minimal(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_resp(201, {}))
        await svc.create_fulfillment("tok", "shop", "o1", "loc1")
        body = svc.http.post.call_args.kwargs["json"]["fulfillment"]
        assert "tracking_number" not in body
        assert "tracking_company" not in body

    async def test_create_fulfillment_error(self):
        svc = _svc()
        svc.http.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.create_fulfillment("tok", "shop", "o1", "loc1")
        assert ei.value.status_code == 500


class TestRefunds:
    async def test_get_refunds(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"refunds": [{"id": 1}]}))
        assert await svc.get_refunds("tok", "shop", "o1") == [{"id": 1}]

    async def test_get_refunds_error(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_refunds("tok", "shop", "o1")
        assert ei.value.status_code == 500

    async def test_calculate_refund(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_resp(200, {"refund": {"amount": 10}}))
        out = await svc.calculate_refund("tok", "shop", "o1", [{"line_item_id": 1}])
        assert out == {"amount": 10}
        assert svc.http.post.call_args.kwargs["json"] == {
            "refund": {"refund_line_items": [{"line_item_id": 1}]}}

    async def test_calculate_refund_error(self):
        svc = _svc()
        svc.http.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException):
            await svc.calculate_refund("tok", "shop", "o1", [])


class TestDraftOrders:
    async def test_get_draft_orders(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"draft_orders": [{"id": 1}]}))
        assert await svc.get_draft_orders("tok", "shop") == [{"id": 1}]

    async def test_get_draft_orders_error(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException):
            await svc.get_draft_orders("tok", "shop")

    async def test_create_draft_order_with_customer(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_resp(201, {"draft_order": {"id": 1}}))
        out = await svc.create_draft_order("tok", "shop", [{"variant_id": 1}], customer_id="c1")
        assert out == {"id": 1}
        body = svc.http.post.call_args.kwargs["json"]["draft_order"]
        assert body["customer"] == {"id": "c1"}

    async def test_create_draft_order_without_customer(self):
        svc = _svc()
        svc.http.post = AsyncMock(return_value=_resp(201, {}))
        await svc.create_draft_order("tok", "shop", [{"variant_id": 1}])
        body = svc.http.post.call_args.kwargs["json"]["draft_order"]
        assert "customer" not in body

    async def test_create_draft_order_error(self):
        svc = _svc()
        svc.http.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.create_draft_order("tok", "shop", [])
        assert ei.value.status_code == 500

    async def test_complete_draft_order(self):
        svc = _svc()
        svc.http.put = AsyncMock(return_value=_resp(200, {"draft_order": {"id": 1}}))
        out = await svc.complete_draft_order("tok", "shop", "d1")
        assert out == {"id": 1}
        assert svc.http.put.call_args.args[1].endswith("/draft_orders/d1/complete.json")

    async def test_complete_draft_order_error(self):
        svc = _svc()
        svc.http.put = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException):
            await svc.complete_draft_order("tok", "shop", "d1")


class TestTransactions:
    async def test_get_transactions(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"transactions": [{"id": 1}]}))
        assert await svc.get_transactions("tok", "shop", "o1") == [{"id": 1}]

    async def test_get_transactions_error(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException):
            await svc.get_transactions("tok", "shop", "o1")


class TestCounts:
    async def test_order_count(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"count": 42}))
        assert await svc.get_order_count("tok", "shop") == 42
        assert svc.http.get.call_args.kwargs["params"] == {"status": "any"}

    async def test_order_count_missing(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {}))
        assert await svc.get_order_count("tok", "shop") == 0

    async def test_order_count_error_returns_zero(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_order_count("tok", "shop") == 0

    async def test_product_count(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"count": 7}))
        assert await svc.get_product_count("tok", "shop") == 7

    async def test_product_count_error(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_product_count("tok", "shop") == 0

    async def test_customer_count(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"count": 3}))
        assert await svc.get_customer_count("tok", "shop") == 3

    async def test_customer_count_error(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_customer_count("tok", "shop") == 0


class TestShopAnalytics:
    async def test_success(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"count": 42}))
        svc.get_shop_info = AsyncMock(return_value={
            "name": "ACME", "domain": "acme.myshopify.com", "currency": "USD",
            "plan_name": "shopify_plus", "created_at": "2020-01-01"})
        out = await svc.get_shop_analytics("tok", "shop")
        assert out["shop_name"] == "ACME"
        assert out["metrics"] == {"total_orders": 42, "total_products": 42,
                                  "total_customers": 42}
        assert out["plan"] == "shopify_plus"
        assert out["created_at"] == "2020-01-01"

    async def test_defaults(self):
        svc = _svc()
        svc.get_shop_info = AsyncMock(return_value={})
        svc.get_order_count = AsyncMock(return_value=0)
        svc.get_product_count = AsyncMock(return_value=0)
        svc.get_customer_count = AsyncMock(return_value=0)
        out = await svc.get_shop_analytics("tok", "shop")
        assert out["shop_name"] == "shop"
        assert out["currency"] == "USD"
        assert out["plan"] == "unknown"

    async def test_error_500(self):
        svc = _svc()
        svc.get_order_count = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_shop_analytics("tok", "shop")
        assert ei.value.status_code == 500


class TestCapabilities:
    def test_operations(self):
        caps = _svc().get_capabilities()
        ops = {o["id"] for o in caps["operations"]}
        assert ops == {"get_products", "get_orders", "create_fulfillment",
                       "get_shop_analytics"}
        assert caps["supports_webhooks"] is True


class TestHealthCheck:
    async def test_healthy(self):
        svc = _svc()
        out = await svc.health_check()
        assert out["healthy"] is True
        assert out["message"] == "Connected"
        assert "timestamp" in out

    async def test_unhealthy(self):
        svc = _svc(_EMPTY)
        out = await svc.health_check()
        assert out["healthy"] is False
        assert out["message"] == "Missing API key"

    async def test_exception_generic_no_str_e(self):
        """RED: except path returned str(e) verbatim; must be generic."""
        svc = _svc()
        with patch("integrations.shopify_service.datetime") as dt:
            dt.now.side_effect = RuntimeError("clock broke")
            out = await svc.health_check()
        assert out["healthy"] is False
        assert "clock broke" not in out["message"]


class TestExecuteOperation:
    async def test_handle_webhook_event_op(self):
        svc = _svc()
        out = await svc.execute_operation("handle_webhook_event",
                                          {"payload": {"customer": {}}, "topic": "orders/create"})
        assert out["success"] is True
        assert out["result"]["platform"] == "shopify"

    async def test_get_products_op(self):
        svc = _svc()
        svc.get_products = AsyncMock(return_value=[{"id": 1}])
        out = await svc.execute_operation("get_products", {"access_token": "tok",
                                                           "shop": "s", "limit": 5})
        assert out == {"success": True, "result": [{"id": 1}]}
        svc.get_products.assert_awaited_once_with("tok", "s", limit=5)

    async def test_get_orders_op(self):
        svc = _svc()
        svc.get_orders = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_orders", {"access_token": "tok", "shop": "s"})
        assert out["success"] is True

    async def test_get_customers_op(self):
        svc = _svc()
        svc.get_customers = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_customers", {"access_token": "tok", "shop": "s"})
        assert out["success"] is True

    async def test_get_customer_op(self):
        svc = _svc()
        svc.get_customer = AsyncMock(return_value={})
        out = await svc.execute_operation("get_customer",
                                          {"access_token": "tok", "shop": "s", "customer_id": "c1"})
        assert out["success"] is True
        svc.get_customer.assert_awaited_once_with("tok", "s", customer_id="c1")

    async def test_search_customers_op(self):
        svc = _svc()
        svc.search_customers = AsyncMock(return_value=[])
        out = await svc.execute_operation("search_customers",
                                          {"access_token": "tok", "shop": "s", "query": "q"})
        assert out["success"] is True

    async def test_get_fulfillments_op(self):
        svc = _svc()
        svc.get_fulfillments = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_fulfillments",
                                          {"access_token": "tok", "shop": "s", "order_id": "o1"})
        assert out["success"] is True

    async def test_create_fulfillment_op(self):
        svc = _svc()
        svc.create_fulfillment = AsyncMock(return_value={})
        out = await svc.execute_operation("create_fulfillment", {
            "access_token": "tok", "shop": "s", "order_id": "o1", "location_id": "l1",
            "tracking_number": "T", "tracking_company": "U"})
        assert out["success"] is True
        svc.create_fulfillment.assert_awaited_once_with(
            "tok", "s", order_id="o1", location_id="l1",
            tracking_number="T", tracking_company="U")

    async def test_get_refunds_op(self):
        svc = _svc()
        svc.get_refunds = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_refunds",
                                          {"access_token": "tok", "shop": "s", "order_id": "o1"})
        assert out["success"] is True

    async def test_get_shop_analytics_op(self):
        svc = _svc()
        svc.get_shop_analytics = AsyncMock(return_value={"metrics": {}})
        out = await svc.execute_operation("get_shop_analytics",
                                          {"access_token": "tok", "shop": "s"})
        assert out["success"] is True

    async def test_full_sync_op(self):
        svc = _svc()
        svc.full_sync = AsyncMock(return_value={"success": True})
        out = await svc.execute_operation("full_sync", {"workspace_id": "ws-1"})
        assert out["success"] is True
        svc.full_sync.assert_awaited_once_with(workspace_id="ws-1")

    async def test_unknown_operation(self):
        svc = _svc()
        out = await svc.execute_operation("nope", {})
        assert out["success"] is False
        assert "Unknown operation" in out["error"]
        assert out["operation"] == "nope"

    async def test_inner_exception_generic(self):
        svc = _svc()
        svc.get_products = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_products", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Operation failed"


class TestHandleWebhook:
    async def test_orders_create(self):
        svc = _svc()
        out = await svc.handle_webhook_event({"customer": {"email": "a@x.com"},
                                              "order_number": 42, "id": "ord1"},
                                             "orders/create")
        assert out["success"] is True
        r = out["result"]
        assert r["platform"] == "shopify"
        assert r["sender_id"] == "a@x.com"
        assert r["recipient_id"] == "my-shop.myshopify.com"
        assert r["metadata"]["order_id"] == "ord1"
        assert "42" in r["text"]

    async def test_orders_create_anonymous(self):
        svc = _svc()
        out = await svc.handle_webhook_event({"order_number": 1, "id": "x"}, "orders/create")
        assert out["result"]["sender_id"] == "anonymous"

    async def test_other_topic(self):
        svc = _svc()
        out = await svc.handle_webhook_event({}, "products/update")
        assert out == {"success": True, "result": None}


@pytest.fixture()
def db_session_factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


class TestSyncToPostgresCache:
    async def test_missing_credentials(self, db_session_factory, monkeypatch):
        monkeypatch.delenv("SHOPIFY_API_KEY", raising=False)
        monkeypatch.delenv("SHOPIFY_API_SECRET", raising=False)
        monkeypatch.delenv("SHOPIFY_SHOP_NAME", raising=False)
        svc = _svc(_EMPTY)
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("ws-1")
        assert out["success"] is False
        assert "Missing Shopify credentials" in out["error"]

    async def test_success(self, db_session_factory):
        svc = _svc()
        svc.get_shop_analytics = AsyncMock(return_value={
            "metrics": {"total_orders": 3, "total_products": 4, "total_customers": 5}})
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("ws-1")
        assert out["success"] is True
        assert out["metrics_synced"] == 3
        db = db_session_factory()
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 3
        keys = {r.metric_key for r in rows}
        assert keys == {"shopify_total_orders", "shopify_total_products",
                        "shopify_total_customers"}
        assert all(r.workspace_id == "ws-1" for r in rows)
        db.close()

    async def test_existing_rows_updated(self, db_session_factory):
        svc = _svc()
        svc.get_shop_analytics = AsyncMock(return_value={
            "metrics": {"total_orders": 1, "total_products": 1, "total_customers": 1}})
        with patch("core.database.SessionLocal", db_session_factory):
            await svc.sync_to_postgres_cache("ws-1")
            await svc.sync_to_postgres_cache("ws-1")
        db = db_session_factory()
        assert len(db.query(IntegrationMetric).all()) == 3
        orders = db.query(IntegrationMetric).filter_by(
            metric_key="shopify_total_orders").first()
        assert orders.value == 1.0
        db.close()

    async def test_inner_error_generic(self, db_session_factory):
        svc = _svc()
        svc.get_shop_analytics = AsyncMock(return_value={
            "metrics": {"total_orders": 1, "total_products": 1, "total_customers": 1}})

        class Boom:
            def __init__(self, *a, **k):
                pass

            def query(self, *a, **k):
                raise RuntimeError("db explode detail")

            def rollback(self):
                pass

            def close(self):
                pass

        with patch("core.database.SessionLocal", Boom):
            out = await svc.sync_to_postgres_cache("ws-1")
        assert out["success"] is False
        assert "db explode detail" not in out["error"]
        assert out["error"] == "Shopify sync failed"

    async def test_outer_error_generic(self, db_session_factory):
        svc = _svc()
        svc.get_shop_analytics = AsyncMock(side_effect=RuntimeError("api secret"))
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("ws-1")
        assert out["success"] is False
        assert "api secret" not in out["error"]
        assert out["error"] == "Shopify sync failed"


class TestFullSync:
    async def test_success(self, db_session_factory):
        svc = _svc()
        svc.get_shop_analytics = AsyncMock(return_value={
            "metrics": {"total_orders": 0, "total_products": 0, "total_customers": 0}})
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.full_sync("ws-1")
        assert out["success"] is True
        assert out["workspace_id"] == "ws-1"
        assert out["postgres_cache"]["success"] is True
        assert "timestamp" in out

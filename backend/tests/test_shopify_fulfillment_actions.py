"""Agent-surface tests for the Shopify fulfillment actions (issue #621 follow-up).

``shopify_get_fulfillments`` / ``shopify_create_fulfillment`` are registered in
core/action_registry.py and reach agents through the governed MCP dispatch
(call_tool capability/sandbox gates → execute_tool step 0 → execute_action).
These tests pin the handlers' contract: workspace-scoped credential resolution,
payload threading into ShopifyService, and the fail-closed no-store guard.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.action_registry import action_registry


def _patch_store(monkeypatch, token="tok"):
    """Point _resolve_shopify_store at a connected (or missing) store."""
    monkeypatch.setattr(
        "core.action_registry._resolve_shopify_store",
        lambda ctx: (token, "shop.myshopify.com") if token else (None, None),
    )


def _patch_service_cls(monkeypatch) -> MagicMock:
    """Swap ShopifyService for a MagicMock; returns the instance mock."""
    service = MagicMock()
    monkeypatch.setattr(
        "integrations.shopify_service.ShopifyService", lambda: service
    )
    return service


class TestRegistryDefinition:
    def test_both_actions_registered(self):
        create_def = action_registry.get_action("shopify_create_fulfillment")
        list_def = action_registry.get_action("shopify_get_fulfillments")
        assert create_def is not None and list_def is not None
        assert create_def.parameters_schema["required"] == ["order_id"]
        assert list_def.parameters_schema["required"] == ["order_id"]

    def test_create_schema_advertises_optional_tracking(self):
        props = action_registry.get_action(
            "shopify_create_fulfillment").parameters_schema["properties"]
        for name in ("tracking_number", "tracking_company",
                     "location_id", "notify_customer"):
            assert name in props


class TestCreateFulfillmentAction:
    @pytest.mark.asyncio
    async def test_success_threads_args(self, monkeypatch):
        _patch_store(monkeypatch)
        service = _patch_service_cls(monkeypatch)
        service.create_fulfillment = AsyncMock(
            return_value={"id": 11, "status": "success"})

        result = await action_registry.execute_action(
            "shopify_create_fulfillment",
            {"order_id": "o1", "tracking_number": "TN1",
             "tracking_company": "UPS", "notify_customer": False},
            {"workspace_id": "ws"},
        )
        assert result == {"success": True,
                          "fulfillment": {"id": 11, "status": "success"}}
        service.create_fulfillment.assert_awaited_once_with(
            "tok", "shop.myshopify.com", order_id="o1", location_id=None,
            tracking_number="TN1", tracking_company="UPS",
            notify_customer=False,
        )

    @pytest.mark.asyncio
    async def test_notify_customer_defaults_true(self, monkeypatch):
        _patch_store(monkeypatch)
        service = _patch_service_cls(monkeypatch)
        service.create_fulfillment = AsyncMock(return_value={"id": 12})

        await action_registry.execute_action(
            "shopify_create_fulfillment", {"order_id": "o1"},
            {"workspace_id": "ws"},
        )
        assert service.create_fulfillment.call_args.kwargs["notify_customer"] is True

    @pytest.mark.asyncio
    async def test_no_store_fail_closed(self, monkeypatch):
        _patch_store(monkeypatch, token=None)
        service = _patch_service_cls(monkeypatch)

        result = await action_registry.execute_action(
            "shopify_create_fulfillment", {"order_id": "o1"},
            {"workspace_id": "ws"},
        )
        assert result["success"] is False
        assert result["error"] == "no_shopify_store"
        service.create_fulfillment.assert_not_called()


class TestGetFulfillmentsAction:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        _patch_store(monkeypatch)
        service = _patch_service_cls(monkeypatch)
        service.get_fulfillments = AsyncMock(
            return_value=[{"id": 5, "status": "success"}])

        result = await action_registry.execute_action(
            "shopify_get_fulfillments", {"order_id": "o1"},
            {"workspace_id": "ws"},
        )
        assert result == {"success": True,
                          "fulfillments": [{"id": 5, "status": "success"}]}
        service.get_fulfillments.assert_awaited_once_with(
            "tok", "shop.myshopify.com", order_id="o1")

    @pytest.mark.asyncio
    async def test_no_store_fail_closed(self, monkeypatch):
        _patch_store(monkeypatch, token=None)
        service = _patch_service_cls(monkeypatch)

        result = await action_registry.execute_action(
            "shopify_get_fulfillments", {"order_id": "o1"},
            {"workspace_id": "ws"},
        )
        assert result["success"] is False
        assert result["error"] == "no_shopify_store"
        service.get_fulfillments.assert_not_called()

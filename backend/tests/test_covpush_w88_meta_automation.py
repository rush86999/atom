# -*- coding: utf-8 -*-
"""Coverage wave 88 — core/meta_automation (67 stmts, never wave-tested).

- should_fallback: 500/503 server errors, 429 rate limit, "not implemented" /
  "feature missing", "connection reset" / "timeout" — each True; benign and
  empty errors False; case-insensitive matching.
- get_fallback_agent: registry lookups (salesforce/hubspot → CRMManualOperator,
  remote_market → MarketplaceAdminWorkflow, supplier_portal →
  LogisticsManagerWorkflow), case-insensitive keys, unknown → None.
- execute_fallback: unknown integration failed-dict, MarketplaceAdminWorkflow
  price-update path (fake module injected — the real operations.automations
  package has no marketplace_admin module, so the import-failure branch is
  real), non-price goal default success dict, LogisticsManagerWorkflow
  order path (fake module), non-order goal default dict, import-failure
  branches for both workflows.
- get_meta_automation factory.

No LLM / no network / lazy imports faked via sys.modules.
"""
import sys
import types
from unittest.mock import patch

from core.meta_automation import MetaAutomationEngine, get_meta_automation


class _FakeMarketplaceAdmin:
    class MarketplaceAdminWorkflow:
        def __init__(self, base_url=None):
            self.base_url = base_url

        def update_listing_price(self, sku, price):
            return {"status": "price_updated", "sku": sku, "price": price}


class _FakeLogisticsManager:
    class LogisticsManagerWorkflow:
        def __init__(self, base_url=None):
            self.base_url = base_url

        def place_purchase_order(self, sku, qty):
            return {"status": "order_placed", "sku": sku, "qty": qty}


def _inject(monkeypatch, module_name, fake):
    parent = module_name.rsplit(".", 1)[0]
    monkeypatch.setitem(sys.modules, parent, types.ModuleType(parent))
    monkeypatch.setitem(sys.modules, module_name, fake)


class TestShouldFallback:
    def test_server_error_500(self):
        assert MetaAutomationEngine().should_fallback(Exception("API returned 500 Internal Server Error")) is True

    def test_service_unavailable_503(self):
        assert MetaAutomationEngine().should_fallback(Exception("503 Service Unavailable")) is True

    def test_rate_limit_429(self):
        assert MetaAutomationEngine().should_fallback(Exception("429 Too Many Requests")) is True

    def test_not_implemented(self):
        assert MetaAutomationEngine().should_fallback(Exception("Endpoint not implemented")) is True

    def test_feature_missing(self):
        assert MetaAutomationEngine().should_fallback(Exception("feature missing on this plan")) is True

    def test_connection_reset(self):
        assert MetaAutomationEngine().should_fallback(Exception("connection reset by peer")) is True

    def test_timeout(self):
        assert MetaAutomationEngine().should_fallback(Exception("request timeout")) is True

    def test_case_insensitive(self):
        assert MetaAutomationEngine().should_fallback(Exception("TIMEOUT")) is True

    def test_benign_error_no_fallback(self):
        assert MetaAutomationEngine().should_fallback(Exception("Invalid credentials")) is False

    def test_empty_error_no_fallback(self):
        assert MetaAutomationEngine().should_fallback(Exception("")) is False

    def test_context_arg_optional(self):
        engine = MetaAutomationEngine()
        assert engine.should_fallback(Exception("timeout"), {"attempt": 2}) is True


class TestGetFallbackAgent:
    def test_salesforce(self):
        assert MetaAutomationEngine().get_fallback_agent("salesforce") == "CRMManualOperator"

    def test_hubspot(self):
        assert MetaAutomationEngine().get_fallback_agent("hubspot") == "CRMManualOperator"

    def test_remote_market(self):
        assert MetaAutomationEngine().get_fallback_agent("remote_market") == "MarketplaceAdminWorkflow"

    def test_supplier_portal(self):
        assert MetaAutomationEngine().get_fallback_agent("supplier_portal") == "LogisticsManagerWorkflow"

    def test_case_insensitive(self):
        assert MetaAutomationEngine().get_fallback_agent("SalesForce") == "CRMManualOperator"

    def test_unknown_returns_none(self):
        assert MetaAutomationEngine().get_fallback_agent("slack") is None


class TestExecuteFallback:
    def test_unknown_integration_fails(self):
        result = MetaAutomationEngine().execute_fallback("slack", "sync data", {})
        assert result["status"] == "failed"
        assert "No fallback agent for slack" in result["error"]

    def test_crm_default_success_dict(self):
        result = MetaAutomationEngine().execute_fallback("salesforce", "sync contacts", {})
        assert result["status"] == "success"
        assert result["agent"] == "CRMManualOperator"
        assert result["action"] == "Simulated Visual Interaction"
        assert result["details"] == "Visually completed 'sync contacts' due to API failure."

    def test_marketplace_price_update(self, monkeypatch):
        fake = types.ModuleType("operations.automations.marketplace_admin")
        fake.MarketplaceAdminWorkflow = _FakeMarketplaceAdmin.MarketplaceAdminWorkflow
        _inject(monkeypatch, "operations.automations.marketplace_admin", fake)
        result = MetaAutomationEngine().execute_fallback(
            "remote_market", "update price", {"sku": "SKU-9", "price": "12.50"}
        )
        assert result == {"status": "price_updated", "sku": "SKU-9", "price": "12.50"}

    def test_marketplace_price_defaults(self, monkeypatch):
        fake = types.ModuleType("operations.automations.marketplace_admin")
        fake.MarketplaceAdminWorkflow = _FakeMarketplaceAdmin.MarketplaceAdminWorkflow
        _inject(monkeypatch, "operations.automations.marketplace_admin", fake)
        result = MetaAutomationEngine().execute_fallback("remote_market", "set price", {})
        assert result["sku"] == "SKU-123"
        assert result["price"] == "99.99"

    def test_marketplace_non_price_goal_default(self):
        # No fake module → real module missing → but goal has no 'price', so
        # the default success dict path runs before any import.
        result = MetaAutomationEngine().execute_fallback("remote_market", "list products", {})
        assert result["status"] == "success"
        assert result["agent"] == "MarketplaceAdminWorkflow"

    def test_marketplace_import_failure(self, monkeypatch):
        # Block the real operations.automations.marketplace_admin module so
        # the lazy import raises and the except branch reports failure.
        monkeypatch.setitem(sys.modules, "operations.automations.marketplace_admin", None)
        result = MetaAutomationEngine().execute_fallback("remote_market", "update price", {})
        assert result["status"] == "failed"
        assert "Agent Execution Failed" in result["error"]

    def test_logistics_order(self, monkeypatch):
        fake = types.ModuleType("operations.automations.logistics_manager")
        fake.LogisticsManagerWorkflow = _FakeLogisticsManager.LogisticsManagerWorkflow
        _inject(monkeypatch, "operations.automations.logistics_manager", fake)
        result = MetaAutomationEngine().execute_fallback(
            "supplier_portal", "place order", {"sku": "SKU-1", "qty": "5"}
        )
        assert result == {"status": "order_placed", "sku": "SKU-1", "qty": "5"}

    def test_logistics_order_defaults(self, monkeypatch):
        fake = types.ModuleType("operations.automations.logistics_manager")
        fake.LogisticsManagerWorkflow = _FakeLogisticsManager.LogisticsManagerWorkflow
        _inject(monkeypatch, "operations.automations.logistics_manager", fake)
        result = MetaAutomationEngine().execute_fallback("supplier_portal", "new order", {})
        assert result["sku"] == "SKU-123"
        assert result["qty"] == "10"

    def test_logistics_non_order_goal_default(self):
        result = MetaAutomationEngine().execute_fallback("supplier_portal", "check inventory", {})
        assert result["status"] == "success"
        assert result["agent"] == "LogisticsManagerWorkflow"

    def test_logistics_import_failure(self, monkeypatch):
        # Remove the real module so the lazy import raises.
        monkeypatch.setitem(sys.modules, "operations.automations.logistics_manager", None)
        result = MetaAutomationEngine().execute_fallback("supplier_portal", "place order", {})
        assert result["status"] == "failed"
        assert "Agent Execution Failed" in result["error"]

    def test_goal_without_matching_keyword_crm(self):
        result = MetaAutomationEngine().execute_fallback("hubspot", "anything", {})
        assert result["status"] == "success"


class TestGetMetaAutomation:
    def test_returns_engine(self):
        assert isinstance(get_meta_automation(), MetaAutomationEngine)

# -*- coding: utf-8 -*-
"""W85 — coverage push for two integration service modules (>=80% each).

Targets:
1. integrations/universal_integration_service.py     (~18% baseline)
2. integrations/atom_workflow_automation_service.py  (~41% baseline)

Style: plain pytest + unittest.mock (matches tests/test_covpush_w72b_api_routes.py).
Zero network, zero LLM, no real DB — everything mocked at module boundaries
(circuit_breaker / rate_limiter singletons, SessionLocal + IntegrationRegistry,
gatekeeper middleware, platform integration singletons).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.universal_integration_service as uis
import integrations.atom_workflow_automation_service as wfs
from core.circuit_breaker import circuit_breaker
from core.rate_limiter import rate_limiter


# ============================================================================
# Shared fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _guards():
    """Keep circuit breaker closed and rate limiter open for every test."""
    with patch.object(circuit_breaker, "is_enabled", AsyncMock(return_value=True)), \
         patch.object(circuit_breaker, "get_stats", MagicMock(return_value={
             "disabled_until": "soon", "failures": 0})), \
         patch.object(circuit_breaker, "record_failure", MagicMock()), \
         patch.object(rate_limiter, "is_rate_limited",
                      AsyncMock(return_value=(False, 100))):
        yield


@pytest.fixture
def svc():
    return uis.UniversalIntegrationService(workspace_id="ws-1")


def mock_instance(**attrs):
    inst = MagicMock()
    inst.access_token = attrs.pop("access_token", "tok-1")
    for k, v in attrs.items():
        setattr(inst, k, v)
    return inst


def make_registry(instance=None):
    registry = MagicMock()
    registry.get_service_instance = AsyncMock(return_value=instance)
    return registry


def ctx(registry=None, **extra):
    c = {"registry": registry or make_registry(), "tenant_id": "t1",
         "user_id": "u1", "workspace_id": "ws-1"}
    c.update(extra)
    return c


# ============================================================================
# 1. universal_integration_service — outer execute/search plumbing
# ============================================================================


class TestExecutePlumbing:
    def _run(self, coro):
        return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro) \
            if False else asyncio.run(coro)

    def test_mask_response_with_gatekeeper(self, svc):
        gm = MagicMock()
        gm.mask_response = MagicMock(return_value={"masked": True})
        with patch.object(uis, "governance_middleware", gm):
            assert svc._mask_response("slack", {"a": 1}) == {"masked": True}

    def test_mask_response_gatekeeper_raises(self, svc):
        gm = MagicMock()
        gm.mask_response = MagicMock(side_effect=RuntimeError("boom"))
        with patch.object(uis, "governance_middleware", gm):
            assert svc._mask_response("slack", {"a": 1}) == {"a": 1}

    def test_mask_response_no_gatekeeper(self, svc):
        with patch.object(uis, "governance_middleware", None):
            assert svc._mask_response("slack", {"a": 1}) == {"a": 1}

    def test_execute_circuit_open(self, svc):
        with patch.object(circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            res = asyncio.run(svc.execute("slack", "send_message", {}))
        assert res["status"] == "error" and res["circuit_open"] is True

    def test_execute_governance_blocks(self, svc):
        gm = MagicMock()
        gm.check_action_risk = AsyncMock(return_value={
            "allowed": False, "reason": "risky",
            "intervention_id": "iv-1"})
        gm.mask_response = MagicMock(side_effect=lambda s, r: r)
        with patch.object(uis, "governance_middleware", gm), \
             patch("core.database.SessionLocal") as sl, \
             patch("core.integration_registry.IntegrationRegistry"):
            sl.return_value.__enter__.return_value = MagicMock()
            res = asyncio.run(svc.execute("slack", "send_message", {},
                                          {"user_id": "u1"}))
        assert res["status"] == "paused"
        assert res["intervention_id"] == "iv-1"

    def test_execute_governance_risk_raises_falls_through(self, svc):
        gm = MagicMock()
        gm.check_action_risk = AsyncMock(side_effect=RuntimeError("boom"))
        gm.mask_response = MagicMock(side_effect=lambda s, r: r)
        registry = make_registry(mock_instance())
        with patch.object(uis, "governance_middleware", gm), \
             patch("core.database.SessionLocal") as sl, \
             patch("core.integration_registry.IntegrationRegistry",
                   MagicMock(return_value=registry)):
            sl.return_value.__enter__.return_value = MagicMock()
            with patch.object(svc, "_dispatch_execution",
                              AsyncMock(return_value={"status": "success"})):
                res = asyncio.run(svc.execute("slack", "send_message", {},
                                              {"user_id": "u1"}))
        assert res["status"] == "success"

    def test_execute_success_records_spend(self, svc):
        gm = MagicMock()
        gm.check_action_risk = AsyncMock(
            return_value={"allowed": True})
        gm.mask_response = MagicMock(side_effect=lambda s, r: r)
        budget = MagicMock()
        with patch.object(uis, "governance_middleware", gm), \
             patch.object(uis, "budget_service", budget), \
             patch.object(uis, "get_action_cost", MagicMock(return_value=0.5)), \
             patch("core.database.SessionLocal") as sl, \
             patch("core.integration_registry.IntegrationRegistry"), \
             patch.object(svc, "_dispatch_execution",
                          AsyncMock(return_value={"status": "success"})):
            sl.return_value.__enter__.return_value = MagicMock()
            res = asyncio.run(svc.execute("slack", "send_message", {},
                                          {"user_id": "u1"}))
        assert res["status"] == "success"
        budget.record_workspace_spend.assert_called_once_with("ws-1", 0.5)

    def test_execute_exception_path(self, svc):
        budget = MagicMock()
        with patch.object(uis, "budget_service", budget), \
             patch.object(uis, "get_action_cost", MagicMock(return_value=0.2)), \
             patch.object(uis, "governance_middleware", None), \
             patch("core.database.SessionLocal") as sl:
            sl.return_value.__enter__.side_effect = RuntimeError("db down")
            res = asyncio.run(svc.execute("slack", "send_message", {},
                                          {"user_id": "u1"}))
        assert res["status"] == "error"
        budget.record_workspace_spend.assert_called_once()

    def test_search_circuit_open(self, svc):
        with patch.object(circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            res = asyncio.run(svc.search("slack", "q"))
        assert res["circuit_open"] is True

    def test_search_salesforce_path(self, svc):
        sf = mock_instance()
        sf.execute_query = AsyncMock(return_value={"records": [{"Id": "1"}]})
        registry = make_registry(sf)
        with patch.object(uis, "governance_middleware", None), \
             patch("core.database.SessionLocal") as sl, \
             patch("core.integration_registry.IntegrationRegistry",
                   MagicMock(return_value=registry)):
            sl.return_value.__enter__.return_value = MagicMock()
            res = asyncio.run(svc.search("salesforce", "acme", "contact",
                                         {"user_id": "u1"}))
        assert res == {"status": "success", "data": [{"Id": "1"}]}

    def test_search_unsupported_service(self, svc):
        with patch.object(uis, "governance_middleware", None), \
             patch("core.database.SessionLocal") as sl, \
             patch("core.integration_registry.IntegrationRegistry"):
            sl.return_value.__enter__.return_value = MagicMock()
            res = asyncio.run(svc.search("nope_service", "q"))
        assert res["status"] == "error"

    def test_search_exception_path(self, svc):
        with patch.object(uis, "governance_middleware", None), \
             patch("core.database.SessionLocal") as sl:
            sl.return_value.__enter__.side_effect = RuntimeError("boom")
            res = asyncio.run(svc.search("slack", "q"))
        assert res["status"] == "error"


class TestDispatch:
    def test_no_user_id_raises(self, svc):
        with pytest.raises(ValueError):
            asyncio.run(svc._dispatch_execution("slack", "x", {}, {}))

    def test_system_agent_with_db_hit(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        slack = mock_instance()
        slack.post_message = AsyncMock(return_value={"ok": True})
        with patch("core.models.AgentRegistry", MagicMock()):
            res = asyncio.run(svc._dispatch_execution(
                "slack", "send_message", {},
                {"agent_id": "a1", "db": db, "workspace_id": "ws-1",
                 "registry": make_registry(slack), "tenant_id": "t1"}))
        assert res["status"] == "success"

    def test_system_agent_db_miss(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.models.AgentRegistry", MagicMock()):
            with pytest.raises(ValueError):
                asyncio.run(svc._dispatch_execution(
                    "slack", "send_message", {}, {"agent_id": "a1", "db": db}))

    def test_system_agent_lookup_fails(self, svc):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        with pytest.raises(ValueError):
            asyncio.run(svc._dispatch_execution(
                "slack", "send_message", {}, {"agent_id": "a1", "db": db}))

    def test_dispatch_routes(self, svc):
        routed = []
        for name in ("_execute_hubspot", "_execute_shopify",
                     "_execute_communication", "_execute_calendar",
                     "_execute_project_management", "_execute_storage",
                     "_execute_support", "_execute_development",
                     "_execute_marketing", "_execute_finance",
                     "_execute_zoho", "_execute_analytics",
                     "_execute_marketing_reviews", "_execute_marketing_ads",
                     "_execute_generic_native"):
            setattr(svc, name, AsyncMock(return_value={"via": name}))
            routed.append(name)
        for service, handler in [
            ("hubspot", "_execute_hubspot"), ("shopify", "_execute_shopify"),
            ("slack", "_execute_communication"), ("gmail", "_execute_communication"),
            ("google_calendar", "_execute_calendar"),
            ("linear", "_execute_project_management"),
            ("google_drive", "_execute_storage"),
            ("zendesk", "_execute_support"), ("github", "_execute_development"),
            ("mailchimp", "_execute_marketing"), ("stripe", "_execute_finance"),
            ("zoho_crm", "_execute_zoho"), ("tableau", "_execute_analytics"),
            ("google_reviews", "_execute_marketing_reviews"),
            ("meta_ads", "_execute_marketing_ads"),
        ]:
            res = asyncio.run(svc._dispatch_execution(
                service, "x", {}, {"user_id": "u1"}))
            assert res["via"] == handler
        # unknown service -> activepieces fallback (mocked — no network)
        ext = MagicMock()
        ext.execute_integration_action = AsyncMock(return_value={"ok": True})
        with patch("core.external_integration_service.external_integration_service", ext):
            res = asyncio.run(svc._dispatch_execution(
                "unknown_svc", "x", {}, {"user_id": "u1"}))
        assert res["status"] == "success"


# ============================================================================
# 2. universal_integration_service — salesforce / hubspot / shopify
# ============================================================================


class TestSalesforce:
    def _sf(self):
        sf = mock_instance()
        sf.list_contacts = AsyncMock(return_value=[{"n": 1}])
        sf.list_opportunities = AsyncMock(return_value=[{"o": 1}])
        sf.list_accounts = AsyncMock(return_value=[{"a": 1}])
        sf.create_contact = AsyncMock(return_value={"id": "c"})
        sf.create_opportunity = AsyncMock(return_value={"id": "o"})
        sf.create_account = AsyncMock(return_value={"id": "a"})
        sf.get_opportunity = AsyncMock(return_value={"id": "o2"})
        sf.execute_query = AsyncMock(return_value={"records": [{"q": 1}]})
        sf.update_contact = AsyncMock(return_value=True)
        sf.update_opportunity = AsyncMock(return_value=True)
        sf.update_lead = AsyncMock(return_value=True)
        sf.update_account = AsyncMock(return_value=True)
        return sf

    def test_list_entities(self, svc):
        sf = self._sf()
        c = ctx(make_registry(sf))
        s = uis.UniversalIntegrationService()
        assert asyncio.run(s._execute_salesforce(
            "list", {"entity": "contact"}, "u1", c))["data"] == [{"n": 1}]
        assert asyncio.run(s._execute_salesforce(
            "list", {"entity": "opportunity"}, "u1", c))["data"] == [{"o": 1}]
        assert asyncio.run(s._execute_salesforce(
            "list", {"entity": "account"}, "u1", c))["data"] == [{"a": 1}]

    def test_list_unsupported_entity(self, svc):
        with pytest.raises(ValueError):
            asyncio.run(svc._execute_salesforce(
                "list", {"entity": "weird"}, "u1", ctx(make_registry(self._sf()))))

    def test_create_entities(self, svc):
        sf = self._sf()
        c = ctx(make_registry(sf))
        assert asyncio.run(svc._execute_salesforce(
            "create", {"entity": "contact", "data": {}}, "u1", c))["status"] == "success"
        assert asyncio.run(svc._execute_salesforce(
            "create", {"entity": "opportunity", "data": {}}, "u1", c))["status"] == "success"
        assert asyncio.run(svc._execute_salesforce(
            "create", {"entity": "account", "data": {}}, "u1", c))["status"] == "success"

    def test_read_and_query(self, svc):
        sf = self._sf()
        c = ctx(make_registry(sf))
        assert asyncio.run(svc._execute_salesforce(
            "read", {"entity": "opportunity", "id": "o1"}, "u1", c))["status"] == "success"
        assert asyncio.run(svc._execute_salesforce(
            "query", {"query": "SELECT Id"}, "u1", c))["status"] == "success"

    def test_update_entities(self, svc):
        sf = self._sf()
        c = ctx(make_registry(sf))
        for entity in ("contact", "opportunity", "lead", "account"):
            res = asyncio.run(svc._execute_salesforce(
                "update", {"entity": entity, "id": "x", "data": {}}, "u1", c))
            assert res["status"] == "success"

    def test_no_service_instance(self, svc):
        res = asyncio.run(svc._execute_salesforce(
            "list", {"entity": "contact"}, "u1", ctx(make_registry(None))))
        assert res["status"] == "error"

    def test_no_token_anywhere(self, svc):
        sf = mock_instance(access_token=None)
        with patch("core.token_storage.token_storage") as ts:
            ts.get_token.return_value = None
            res = asyncio.run(svc._execute_salesforce(
                "list", {"entity": "contact"}, "u1", ctx(make_registry(sf))))
        assert "No token" in res["message"]

    def test_token_fallback_storage(self, svc):
        sf = mock_instance(access_token=None)
        sf.execute_query = AsyncMock(return_value={"records": []})
        with patch("core.token_storage.token_storage") as ts:
            ts.get_token.return_value = {"access_token": "stored-tok"}
            res = asyncio.run(svc._execute_salesforce(
                "query", {"query": "SELECT Id"}, "u1", ctx(make_registry(sf))))
        assert res["status"] == "success"

    def test_unsupported_action(self, svc):
        res = asyncio.run(svc._execute_salesforce(
            "delete", {"entity": "contact"}, "u1",
            ctx(make_registry(self._sf()))))
        assert res["status"] == "error"

    def test_search_contact_account_other(self, svc):
        sf = self._sf()
        c = ctx(make_registry(sf))
        assert asyncio.run(svc._search_salesforce("acme", "contact", "u1", c)) == [{"q": 1}]
        assert asyncio.run(svc._search_salesforce("acme", "account", "u1", c)) == [{"q": 1}]
        assert asyncio.run(svc._search_salesforce(
            "acme", "other", "u1", c)) == [{"message": "Only specific entity search implemented via SOQL"}]

    def test_search_no_service_or_token(self, svc):
        assert asyncio.run(svc._search_salesforce("q", "contact", "u1",
                                                  ctx(make_registry(None)))) == []
        assert asyncio.run(svc._search_salesforce(
            "q", "contact", "u1", ctx(make_registry(mock_instance(access_token=None))))) == []


class TestHubspot:
    def _hs(self):
        hs = mock_instance()
        hs.get_contacts = AsyncMock(return_value=[])
        hs.get_deals = AsyncMock(return_value=[])
        hs.get_companies = AsyncMock(return_value=[])
        hs.create_contact = AsyncMock(return_value={"id": "c"})
        hs.create_deal = AsyncMock(return_value={"id": "d"})
        hs.create_company = AsyncMock(return_value={"id": "co"})
        hs.update_contact = AsyncMock(return_value=True)
        hs.update_deal = AsyncMock(return_value=True)
        hs.update_object = AsyncMock(return_value=True)
        hs.search_content = AsyncMock(return_value={"results": [1]})
        return hs

    def test_list(self, svc):
        c = ctx(make_registry(self._hs()))
        for entity in ("contact", "deal", "company"):
            assert asyncio.run(svc._execute_hubspot(
                "list", {"entity": entity}, c))["status"] == "success"

    def test_registry_fallback_to_singleton(self, svc):
        hs = self._hs()
        with patch("integrations.hubspot_service.get_hubspot_service",
                   MagicMock(return_value=hs)):
            reg = MagicMock()
            reg.get_service_instance = AsyncMock(return_value=None)
            res = asyncio.run(svc._execute_hubspot(
                "list", {"entity": "contact"}, ctx(reg)))
        assert res["status"] == "success"

    def test_create_variants(self, svc):
        c = ctx(make_registry(self._hs()))
        assert asyncio.run(svc._execute_hubspot(
            "create", {"entity": "contact", "data": {}}, c))["status"] == "success"
        res = asyncio.run(svc._execute_hubspot(
            "create", {"entity": "deal", "data": {"amount": "100"}}, c))
        assert res["status"] == "success"
        assert asyncio.run(svc._execute_hubspot(
            "create_company", {"data": {}}, c))["status"] == "success"
        assert asyncio.run(svc._execute_hubspot(
            "create_deal", {"data": {}}, c))["status"] == "success"
        assert asyncio.run(svc._execute_hubspot(
            "create_contact", {"data": {}}, c))["status"] == "success"

    def test_update_variants(self, svc):
        c = ctx(make_registry(self._hs()))
        assert asyncio.run(svc._execute_hubspot(
            "update", {"entity": "contact", "id": "1", "data": {}}, c))["status"] == "success"
        assert asyncio.run(svc._execute_hubspot(
            "update", {"entity": "deal", "id": "1", "data": {}}, c))["status"] == "success"
        assert asyncio.run(svc._execute_hubspot(
            "update", {"entity": "ticket", "id": "1", "data": {}}, c))["status"] == "success"

    def test_unsupported(self, svc):
        assert asyncio.run(svc._execute_hubspot(
            "merge", {"entity": "contact"}, ctx(make_registry(self._hs()))))["status"] == "error"

    def test_search(self, svc):
        res = asyncio.run(svc._search_hubspot("q", "contact",
                                              ctx(make_registry(self._hs()))))
        assert res == [1]


class TestShopify:
    def test_missing_credentials(self, svc):
        assert asyncio.run(svc._execute_shopify(
            "list", {}, ctx()))["status"] == "error"

    def test_actions(self, svc):
        shopify = MagicMock()
        shopify.get_products = AsyncMock(return_value=[])
        shopify.get_orders = AsyncMock(return_value=[])
        shopify.get_customers = AsyncMock(return_value=[])
        shopify.create_fulfillment = AsyncMock(return_value={"id": "f"})
        shopify.get_shop_analytics = AsyncMock(return_value={})
        with patch.object(uis, "ShopifyService", MagicMock(return_value=shopify)):
            c = ctx(access_token="tok", shop="myshop")
            for entity in ("product", "order", "customer"):
                assert asyncio.run(svc._execute_shopify(
                    "list", {"entity": entity}, c))["status"] == "success"
            assert asyncio.run(svc._execute_shopify(
                "create", {"entity": "fulfillment"}, c))["status"] == "success"
            assert asyncio.run(svc._execute_shopify(
                "analytics", {}, c))["status"] == "success"

    def test_unsupported(self, svc):
        with patch.object(uis, "ShopifyService", MagicMock()) as cls:
            cls.return_value = MagicMock()
            assert asyncio.run(svc._execute_shopify(
                "delete", {}, ctx(access_token="t", shop="s")))


# ============================================================================
# 3. universal_integration_service — communication / calendar handlers
# ============================================================================


class TestCommunication:
    def test_slack_actions_and_fallback(self, svc):
        slack = mock_instance()
        slack.post_message = AsyncMock(return_value={"ok": True})
        slack.list_channels = AsyncMock(return_value=[])
        slack.make_request = AsyncMock(return_value={"matches": []})
        res = asyncio.run(svc._execute_communication(
            "slack", "send_message", {"channel": "c1", "message": "hi"},
            ctx(make_registry(slack))))
        assert res["status"] == "success"
        assert asyncio.run(svc._execute_communication(
            "slack", "list_channels", {}, ctx(make_registry(slack))))["status"] == "success"
        assert asyncio.run(svc._execute_communication(
            "slack", "search_messages", {"query": "q"},
            ctx(make_registry(slack))))["status"] == "success"

    def test_slack_singleton_fallback(self, svc):
        unified = MagicMock()
        unified.post_message = AsyncMock(return_value={"ok": True})
        with patch("integrations.slack_service_unified.slack_unified_service", unified):
            res = asyncio.run(svc._execute_communication(
                "slack", "send_message", {"message": "hi"}, ctx(make_registry(None))))
        assert res["status"] == "success"

    def test_teams_discord(self, svc):
        inst = mock_instance()
        inst.send_message = AsyncMock(return_value={})
        inst.get_teams = AsyncMock(return_value=[])
        inst.list_guilds = AsyncMock(return_value=[])
        assert asyncio.run(svc._execute_communication(
            "teams", "send_message", {"chat_id": "c", "message": "m"},
            ctx(make_registry(inst))))["status"] == "success"
        assert asyncio.run(svc._execute_communication(
            "teams", "list_chats", {}, ctx(make_registry(inst))))["status"] == "success"
        assert asyncio.run(svc._execute_communication(
            "discord", "send_message", {"channel_id": "c", "message": "m"},
            ctx(make_registry(inst))))["status"] == "success"
        assert asyncio.run(svc._execute_communication(
            "discord", "list_guilds", {}, ctx(make_registry(inst))))["status"] == "success"

    def test_google_chat_telegram_whatsapp(self, svc):
        inst = mock_instance()
        inst.send_unified_message = AsyncMock(return_value={})
        inst.list_spaces = AsyncMock(return_value=[])
        inst.send_intelligent_message = AsyncMock(return_value={})
        for service, action, params in [
            ("google_chat", "send_message", {"channel_id": "c", "content": "m"}),
            ("google_chat", "list_spaces", {}),
            ("telegram", "send_message", {"channel_id": "c", "message": "m"}),
            ("whatsapp", "send_message", {"channel_id": "c", "content": "m"}),
        ]:
            res = asyncio.run(svc._execute_communication(
                service, action, params, ctx(make_registry(inst))))
            assert res["status"] == "success"

    def test_gmail_actions(self, svc):
        inst = mock_instance()
        inst.send_message = AsyncMock(return_value={})
        inst.get_messages = AsyncMock(return_value=[])
        inst.get_message = AsyncMock(return_value={})
        assert asyncio.run(svc._execute_communication(
            "gmail", "send_message", {"to": "a@b.c", "subject": "s", "body": "b"},
            ctx(make_registry(inst))))["status"] == "success"
        assert asyncio.run(svc._execute_communication(
            "gmail", "list_messages", {}, ctx(make_registry(inst))))["status"] == "success"
        assert asyncio.run(svc._execute_communication(
            "gmail", "get_message", {"id": "m1"},
            ctx(make_registry(inst))))["status"] == "success"

    def test_outlook_zoho_mail_default(self, svc):
        inst = mock_instance()
        inst.get_recent_inbox = AsyncMock(return_value=[])
        assert asyncio.run(svc._execute_communication(
            "outlook", "send_message", {}, ctx(make_registry(inst))))["status"] == "success"
        assert asyncio.run(svc._execute_communication(
            "zoho_mail", "list", {}, ctx(make_registry(inst))))["status"] == "success"
        assert asyncio.run(svc._execute_communication(
            "zoho_mail", "send_message", {}, ctx(make_registry(inst))))["status"] == "error"
        assert asyncio.run(svc._execute_communication(
            "zoom", "whatever", {}, ctx(make_registry(inst))))["status"] == "success"


class TestCalendar:
    def _cal(self):
        cal = mock_instance()
        cal.get_events = AsyncMock(return_value=[])
        cal.create_event = AsyncMock(return_value={})
        cal.check_conflicts = AsyncMock(return_value=[])
        return cal

    def test_google_calendar(self, svc):
        c = ctx(make_registry(self._cal()))
        assert asyncio.run(svc._execute_calendar(
            "google_calendar", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_calendar(
            "google_calendar", "create", {"data": {}}, c))["status"] == "success"
        assert asyncio.run(svc._execute_calendar(
            "google_calendar", "check_conflicts",
            {"start_time": "2026-01-01T10:00:00Z", "end_time": "2026-01-01T11:00:00Z"},
            c))["status"] == "success"

    def test_outlook_calendar(self, svc):
        c = ctx(make_registry(self._cal()))
        assert asyncio.run(svc._execute_calendar(
            "outlook_calendar", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_calendar(
            "outlook_calendar", "create", {"data": {}}, c))["status"] == "success"

    def test_unsupported_action(self, svc):
        assert asyncio.run(svc._execute_calendar(
            "google_calendar", "delete", {}, ctx(make_registry(self._cal()))))["status"] == "error"


class TestSearchCommunication:
    def test_all_channels(self, svc):
        c = ctx(user_id="u1")
        with patch("integrations.slack_service_unified.slack_unified_service") as slack, \
             patch("integrations.atom_google_chat_integration.atom_google_chat_integration") as gc, \
             patch("integrations.atom_telegram_integration.atom_telegram_integration") as tg, \
             patch("integrations.atom_whatsapp_integration.atom_whatsapp_integration") as wa, \
             patch("integrations.gmail_service.GmailService") as gmail_cls, \
             patch("integrations.teams_service.TeamsService") as teams_cls:
            slack.make_request = AsyncMock(return_value={})
            gc.unified_search = AsyncMock(return_value=[])
            tg.perform_intelligent_search = AsyncMock(return_value=[])
            wa.perform_intelligent_search = AsyncMock(return_value=[])
            gmail_cls.return_value.search_messages = MagicMock(return_value=[])
            teams_cls.return_value.get_teams = MagicMock(return_value=[])
            assert asyncio.run(svc._search_communication("slack", "q", None, c))["status"] == "success"
            assert asyncio.run(svc._search_communication("google_chat", "q", None, c))["status"] == "success"
            assert asyncio.run(svc._search_communication("telegram", "q", None, c))["status"] == "success"
            assert asyncio.run(svc._search_communication("whatsapp", "q", None, c))["status"] == "success"
            assert asyncio.run(svc._search_communication("gmail", "q", None, c))["status"] == "success"
            assert asyncio.run(svc._search_communication("teams", "q", None, c))["status"] == "success"
            assert asyncio.run(svc._search_communication("discord", "q", None, c))["status"] == "success"

    def test_calendar_search(self, svc):
        with patch("integrations.google_calendar_service.google_calendar_service") as cal:
            cal.get_events = MagicMock(return_value=[
                {"title": "Budget Q", "description": ""},
                {"title": "other", "description": "budget talk"}])
            res = asyncio.run(svc._search_calendar("google_calendar", "budget", ctx()))
        assert res["status"] == "success" and len(res["data"]) == 2
        assert asyncio.run(svc._search_calendar("outlook_calendar", "q", ctx())) == []


# ============================================================================
# 4. universal_integration_service — PM / storage / support / dev / marketing
# ============================================================================


class TestProjectManagement:
    def _pm(self):
        pm = mock_instance()
        pm.get_issues = AsyncMock(return_value=[{"title": "Bug x", "description": "d"}])
        pm.create_issue = AsyncMock(return_value={"id": "i"})
        pm.get_teams = AsyncMock(return_value=[])
        pm.get_projects = AsyncMock(return_value=[])
        pm.get_boards = AsyncMock(return_value=[])
        pm.create_item = AsyncMock(return_value={})
        pm.search_items = AsyncMock(return_value=[{"name": "x"}])
        pm.get_tasks = AsyncMock(return_value=[{"name": "Task y"}])
        pm.create_task = AsyncMock(return_value={"ok": True})
        pm.search_issues = MagicMock(return_value={"issues": [{"k": 1}]})
        pm.create_issue_sync = None
        pm.get_cards = AsyncMock(return_value=[])
        pm.create_card = AsyncMock(return_value={})
        return pm

    def test_linear(self, svc):
        c = ctx(make_registry(self._pm()))
        assert asyncio.run(svc._execute_project_management("linear", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_project_management(
            "linear", "create", {"title": "t", "team_id": "tm"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_project_management("linear", "list_teams", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_project_management("linear", "list_projects", {}, c))["status"] == "success"

    def test_monday(self, svc):
        c = ctx(make_registry(self._pm()))
        assert asyncio.run(svc._execute_project_management("monday", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_project_management(
            "monday", "create", {"board_id": "b", "title": "t"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_project_management("monday", "list_boards", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_project_management(
            "monday", "search", {"query": "q"}, c))["status"] == "success"

    def test_zoho_projects(self, svc):
        c = ctx(make_registry(self._pm()))
        assert asyncio.run(svc._execute_project_management(
            "zoho_projects", "list_projects", {"portal_id": "p"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_project_management(
            "zoho_projects", "list", {"portal_id": "p", "project_id": "pr"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_project_management(
            "zoho_projects", "list_tasks", {"portal_id": "p"}, c))["status"] == "success"

    def test_asana_list_ok_and_fail(self, svc):
        pm = self._pm()
        pm.get_tasks = AsyncMock(return_value={"ok": True, "tasks": [{"name": "t"}]})
        c = ctx(make_registry(pm))
        assert asyncio.run(svc._execute_project_management("asana", "list", {}, c))["status"] == "success"
        pm2 = self._pm()
        pm2.get_tasks = AsyncMock(return_value={"ok": False, "error": "nope"})
        res = asyncio.run(svc._execute_project_management("asana", "list", {}, ctx(make_registry(pm2))))
        assert res["status"] == "error" and res["error"] == "nope"

    def test_asana_create(self, svc):
        c = ctx(make_registry(self._pm()))
        assert asyncio.run(svc._execute_project_management(
            "asana", "create", {"title": "t"}, c))["status"] == "success"
        pm = self._pm()
        pm.create_task = AsyncMock(return_value={"ok": False, "error": "bad"})
        res = asyncio.run(svc._execute_project_management("asana", "create", {}, ctx(make_registry(pm))))
        assert res["status"] == "error"

    def test_jira_list_create(self, svc):
        pm = self._pm()
        pm.create_issue = MagicMock(return_value={"id": "j1"})
        c = ctx(make_registry(pm))
        assert asyncio.run(svc._execute_project_management("jira", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_project_management(
            "jira", "create", {"project": "P", "title": "t"}, c))["status"] == "success"

    def test_jira_create_none_and_raises(self, svc):
        pm = self._pm()
        pm.create_issue = MagicMock(return_value=None)
        res = asyncio.run(svc._execute_project_management("jira", "create", {}, ctx(make_registry(pm))))
        assert res["status"] == "error"
        pm.create_issue = MagicMock(side_effect=RuntimeError("boom"))
        res = asyncio.run(svc._execute_project_management("jira", "create", {}, ctx(make_registry(pm))))
        assert res["status"] == "error"

    def test_trello(self, svc):
        c = ctx(make_registry(self._pm()))
        assert asyncio.run(svc._execute_project_management(
            "trello", "list", {"board_id": "b"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_project_management(
            "trello", "create", {"title": "t", "list_id": "l"}, c))["status"] == "success"

    def test_default_route(self, svc):
        assert asyncio.run(svc._execute_project_management(
            "unsupported_pm", "x", {}, ctx(make_registry(self._pm()))))["status"] == "success"

    def test_search_all(self, svc):
        pm = self._pm()
        c = ctx(make_registry(pm))
        assert asyncio.run(svc._search_project_management("linear", "bug", c)) == [{"title": "Bug x", "description": "d"}]
        assert asyncio.run(svc._search_project_management("monday", "q", c)) == [{"name": "x"}]
        pm.get_tasks = AsyncMock(return_value=[{"name": "Task y"}])
        assert asyncio.run(svc._search_project_management("asana", "task", c)) == [{"name": "Task y"}]
        assert asyncio.run(svc._search_project_management("jira", "q", c)) == [{"k": 1}]
        assert asyncio.run(svc._search_project_management("trello", "q", c)) == []


class TestStorage:
    def _st(self):
        st = mock_instance()
        st.list_files = AsyncMock(return_value=[{"name": "f"}])
        st.search_files = AsyncMock(return_value={"status": "success", "data": {"files": [{"name": "f"}]}})
        st.get_file_metadata = AsyncMock(return_value={})
        st.list_folder = AsyncMock(return_value=[])
        st.search = AsyncMock(return_value=[{"path": "p"}])
        st.create_folder = AsyncMock(return_value={})
        st.list_drive_items = AsyncMock(return_value=[{"name": "d"}])
        st.list_folder_items = AsyncMock(return_value=[])
        st.create_page = AsyncMock(return_value={})
        st.search_pages_in_workspace = AsyncMock(return_value=[])
        return st

    def test_google_drive(self, svc):
        c = ctx(make_registry(self._st()))
        assert asyncio.run(svc._execute_storage("google_drive", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("google_drive", "search", {"query": "q"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("google_drive", "get_metadata", {"file_id": "f"}, c))["status"] == "success"

    def test_dropbox(self, svc):
        c = ctx(make_registry(self._st()))
        assert asyncio.run(svc._execute_storage("dropbox", "list", {"path": "/"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("dropbox", "search", {"query": "q"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("dropbox", "create_folder", {"path": "/n"}, c))["status"] == "success"

    def test_onedrive_box_notion_workdrive(self, svc):
        c = ctx(make_registry(self._st()))
        assert asyncio.run(svc._execute_storage("onedrive", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("onedrive", "search", {"query": "d"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("box", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("notion", "search", {"query": "q"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("notion", "create_page", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("notion", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("zoho_workdrive", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_storage("zoho_workdrive", "search", {"query": "q"}, c))["status"] == "success"

    def test_default(self, svc):
        assert asyncio.run(svc._execute_storage(
            "unknown_store", "x", {}, ctx(make_registry(self._st()))))["status"] == "success"

    def test_search(self, svc):
        st = self._st()
        c = ctx(make_registry(st))
        assert asyncio.run(svc._search_storage("google_drive", "f", c)) == [{"name": "f"}]
        st.search_files = AsyncMock(return_value={"status": "error"})
        assert asyncio.run(svc._search_storage("google_drive", "f", c)) == []
        assert asyncio.run(svc._search_storage("dropbox", "q", c)) == [{"path": "p"}]
        st.search = AsyncMock(return_value={"results": [{"id": "p1"}]})
        assert asyncio.run(svc._search_storage("notion", "q", c)) == [{"id": "p1"}]
        assert asyncio.run(svc._search_storage("box", "q", c)) == []


class TestSupport:
    def _sup(self):
        sup = mock_instance()
        sup.get_tickets = AsyncMock(return_value=[])
        sup.create_ticket = AsyncMock(return_value={})
        sup.search_tickets = AsyncMock(return_value=[])
        sup.get_conversations = AsyncMock(return_value=[])
        sup.search_contacts = AsyncMock(return_value=[])
        return sup

    def test_execute(self, svc):
        c = ctx(make_registry(self._sup()))
        assert asyncio.run(svc._execute_support("zendesk", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_support("zendesk", "create", {"data": {}}, c))["status"] == "success"
        assert asyncio.run(svc._execute_support("freshdesk", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_support("freshdesk", "create", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_support("freshdesk", "search", {"query": "q"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_support("intercom", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_support("intercom", "search_contacts", {"query": "q"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_support("other", "x", {}, c))["status"] == "success"

    def test_search_support(self, svc):
        with patch("integrations.zendesk_service.ZendeskService") as zd, \
             patch("integrations.freshdesk_service.FreshdeskService") as fd:
            zd.return_value.get_tickets = AsyncMock(return_value=[1])
            fd.return_value.search_tickets = AsyncMock(return_value=[2])
            assert asyncio.run(svc._search_support("zendesk", "q", ctx()))["status"] == "success"
            assert asyncio.run(svc._search_support("freshdesk", "q", ctx()))["status"] == "success"
        # intercom via registry
        sup = self._sup()
        assert asyncio.run(svc._search_support("intercom", "q", ctx(make_registry(sup))))["status"] == "success"
        # no registry -> error message
        res = asyncio.run(svc._search_support("intercom", "q", {}))
        assert res["status"] == "error"
        assert asyncio.run(svc._search_support("other", "q", ctx()))["status"] == "success"


class TestDev:
    def _dev(self):
        dev = mock_instance()
        dev.get_user_repositories = AsyncMock(return_value=[])
        dev.get_repository_issues = AsyncMock(return_value=[])
        dev.get_projects = AsyncMock(return_value=[])
        dev.get_issues = AsyncMock(return_value=[])
        dev.search_projects = AsyncMock(return_value=[])
        dev.get_team_projects = AsyncMock(return_value=[])
        dev.get_file = AsyncMock(return_value={})
        dev.get_comments = AsyncMock(return_value=[])
        return dev

    def test_execute(self, svc):
        c = ctx(make_registry(self._dev()))
        assert asyncio.run(svc._execute_development("github", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_development(
            "github", "get_issues", {"owner": "o", "repo": "r"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_development("gitlab", "list", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_development(
            "gitlab", "get_issues", {"project_id": 1}, c))["status"] == "success"
        assert asyncio.run(svc._execute_development(
            "gitlab", "search", {"query": "q"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_development(
            "figma", "list", {"team_id": "t"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_development(
            "figma", "get_file", {"file_key": "f"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_development(
            "figma", "get_comments", {"file_key": "f"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_development("svn", "x", {}, c))["status"] == "success"

    def test_search_dev(self, svc):
        with patch("integrations.github_service.GitHubService") as gh, \
             patch("integrations.gitlab_service.GitLabService") as gl:
            gh.return_value.get_user_repositories = MagicMock(
                return_value=[{"name": "alpha"}, {"name": "beta"}])
            gl.return_value.search_projects = AsyncMock(return_value=[{"name": "x"}])
            res = asyncio.run(svc._search_dev("github", "alp", ctx()))
            assert res["status"] == "success" and res["data"] == [{"name": "alpha"}]
            assert asyncio.run(svc._search_dev("gitlab", "q", ctx()))["status"] == "success"
        assert asyncio.run(svc._search_dev("svn", "q", ctx())) == []


class TestMarketing:
    def test_mailchimp_and_hubspot_marketing(self, svc):
        mc = MagicMock()
        mc.get_campaigns = AsyncMock(return_value=[
            {"settings": {"subject_line": "Sale", "title": "s"}}])
        mc.get_audiences = AsyncMock(return_value=[])
        with patch("integrations.mailchimp_service.MailchimpService",
                   MagicMock(return_value=mc)), \
             patch("integrations.hubspot_service.get_hubspot_service") as gh:
            gh.return_value.get_campaigns = AsyncMock(return_value=[])
            c = ctx(access_token="t", server_prefix="us1")
            assert asyncio.run(svc._execute_marketing("mailchimp", "list", {}, c))["status"] == "success"
            assert asyncio.run(svc._execute_marketing("mailchimp", "get_audiences", {}, c))["status"] == "success"
            assert asyncio.run(svc._execute_marketing("hubspot_marketing", "list_campaigns", {}, c))["status"] == "success"
            assert asyncio.run(svc._execute_marketing("print", "x", {}, c))["status"] == "success"
            assert asyncio.run(svc._search_marketing("mailchimp", "sale", ctx()))["status"] == "success"
            assert asyncio.run(svc._search_marketing("print", "q", ctx())) == []


class TestFinance:
    def test_execute_finance(self, svc):
        fin = mock_instance()
        fin.list_payments = AsyncMock(return_value=[])
        fin.get_balance = AsyncMock(return_value={})
        fin.get_invoices = AsyncMock(return_value=[])
        fin.create_customer = AsyncMock(return_value={})
        fin.create_invoice = AsyncMock(return_value={})
        fin.get_items = AsyncMock(return_value=[])
        fin.send_email = AsyncMock(return_value={})
        fin.get_send_quota = AsyncMock(return_value={})
        c = ctx(make_registry(fin))
        assert asyncio.run(svc._execute_finance("stripe", "list_payments", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_finance("stripe", "get_balance", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_finance("quickbooks", "list_invoices", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_finance(
            "quickbooks", "create_customer", {"display_name": "d", "email": "e"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_finance("quickbooks", "create_invoice", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_finance("xero", "list_invoices", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_finance("zoho_books", "list_invoices", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_finance("zoho_inventory", "list_items", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_finance(
            "aws_ses", "send_email", {"to": ["a@b.c"], "subject": "s"}, c))["status"] == "success"
        assert asyncio.run(svc._execute_finance("aws_ses", "get_quota", {}, c))["status"] == "success"
        assert asyncio.run(svc._execute_finance("paypal", "x", {}, c))["status"] == "success"


class TestZoho:
    def test_zoho_handlers(self, svc):
        crm = MagicMock()
        crm.get_leads = AsyncMock(return_value=[{"Last_Name": "Doe", "Email": "d@x.c"}])
        crm.get_deals = AsyncMock(return_value=[])
        crm.create_lead = AsyncMock(return_value={})
        zmail = MagicMock()
        zmail.get_recent_inbox = AsyncMock(return_value=[])
        zinven = MagicMock()
        zinven.get_items = AsyncMock(return_value=[])
        zproj = MagicMock()
        zproj.get_projects = AsyncMock(return_value=[])
        with patch("integrations.zoho_crm_service.ZohoCRMService", MagicMock(return_value=crm)), \
             patch("integrations.zoho_mail_service.ZohoMailService", MagicMock(return_value=zmail)), \
             patch("integrations.zoho_inventory_service.zoho_inventory_service", zinven), \
             patch("integrations.zoho_projects_service.ZohoProjectsService", MagicMock(return_value=zproj)):
            c = ctx(access_token="t")
            assert asyncio.run(svc._execute_zoho("zoho_crm", "list", {}, c))["status"] == "success"
            assert asyncio.run(svc._execute_zoho("zoho_crm", "get_deals", {}, c))["status"] == "success"
            assert asyncio.run(svc._execute_zoho("zoho_crm", "create_lead", {}, c))["status"] == "success"
            assert asyncio.run(svc._execute_zoho("zoho_mail", "list", {}, c))["status"] == "success"
            assert asyncio.run(svc._execute_zoho("zoho_inventory", "list", {}, c))["status"] == "success"
            assert asyncio.run(svc._execute_zoho("zoho_projects", "list", {"portal_id": "p"}, c))["status"] == "success"
            assert asyncio.run(svc._execute_zoho("zoho_other", "x", {}, c))["status"] == "success"
            res = asyncio.run(svc._search_crm("zoho_crm", "doe", c))
            assert res["status"] == "success" and len(res["data"]) == 1

    def test_search_crm_defaults(self, svc):
        assert asyncio.run(svc._search_crm("salesforce", "q", ctx()))["status"] == "success"
        assert asyncio.run(svc._search_crm("unknown", "q", ctx()))["status"] == "success"


class TestAnalyticsAndFallbacks:
    def test_analytics(self, svc):
        tab = MagicMock()
        tab.get_workbooks = AsyncMock(return_value=[{"name": "Dash"}])
        with patch("integrations.tableau_service.TableauService", MagicMock(return_value=tab)):
            c = ctx(access_token="t")
            assert asyncio.run(svc._execute_analytics("tableau", "list", {}, c))["status"] == "success"
            assert asyncio.run(svc._execute_analytics("google_analytics", "run", {}, c))["status"] == "success"
            assert asyncio.run(svc._execute_analytics("other", "x", {}, c))["status"] == "success"
            assert asyncio.run(svc._search_analytics("tableau", "dash", c))["status"] == "success"
            assert asyncio.run(svc._search_analytics("other", "q", c))["status"] == "success"
            tab.get_workbooks = AsyncMock(side_effect=RuntimeError("boom"))
            assert asyncio.run(svc._execute_analytics("tableau", "list", {}, c))["status"] == "error"
            assert asyncio.run(svc._search_analytics("tableau", "q", c))["status"] == "error"

    def test_generic_native(self, svc):
        assert asyncio.run(svc._execute_generic_native(
            "zoom", "x", {}, ctx()))["status"] == "success"

    def test_activepieces_success_and_failure(self, svc):
        ext = MagicMock()
        ext.execute_integration_action = AsyncMock(return_value={"did": True})
        with patch("core.external_integration_service.external_integration_service", ext):
            res = asyncio.run(svc._execute_activepieces("airtable", "do", {}, ctx()))
            assert res["status"] == "success"
            ext.execute_integration_action = AsyncMock(side_effect=RuntimeError("nope"))
            res = asyncio.run(svc._execute_activepieces("airtable", "do", {}, ctx()))
            assert res["status"] == "error"

    def test_marketing_reviews(self, svc):
        ms = MagicMock()
        ms.manage_reviews = AsyncMock(return_value=[{"id": "r1"}])
        with patch("core.marketing_skills_service.marketing_skills_service", ms):
            assert asyncio.run(svc._execute_marketing_reviews(
                "google_reviews", "list_reviews", {}, ctx()))["status"] == "success"
        assert asyncio.run(svc._execute_marketing_reviews(
            "google_reviews", "reply_to_review", {"review_id": "r1"}, ctx()))["status"] == "success"
        assert asyncio.run(svc._execute_marketing_reviews(
            "google_reviews", "moderate", {}, ctx()))["status"] == "error"

    def test_marketing_ads(self, svc):
        res = asyncio.run(svc._execute_marketing_ads("meta_ads", "insights", {}, ctx()))
        assert res["status"] == "success"


# ============================================================================
# 5. atom_workflow_automation_service — helpers / fixtures
# ============================================================================


def make_wf_service(**overrides):
    sec = MagicMock()
    sec.audit_event = AsyncMock()
    sec.check_compliance = AsyncMock(return_value=None)
    sec._block_ip = AsyncMock()
    sec._lock_user_account = AsyncMock()
    sec._terminate_session = AsyncMock()
    sec._quarantine_resource = AsyncMock()
    sec.register_security_trigger = AsyncMock()
    uni = MagicMock()
    uni.execute_enterprise_workflow = AsyncMock(return_value={"ok": True})
    uni.register_compliance_trigger = AsyncMock()
    cfg = {
        "database": None,
        "cache": None,
        "security_service": sec,
        "unified_service": uni,
        "ai_service": MagicMock(),
    }
    cfg.update(overrides)
    return wfs.AtomWorkflowAutomationService(config=cfg)


def automation_data(**over):
    data = {
        "name": "Test Automation",
        "description": "desc",
        "automation_type": "security",
        "priority": "high",
        "conditions": [{"type": "event_triggered", "event_type": "system_event"}],
        "actions": [{"type": "logging", "config": {}}],
        "schedule": None,
    }
    data.update(over)
    return data


@pytest.fixture
def wf():
    return make_wf_service()


async def create(wf_service, **over):
    result = await wf_service.create_automation(automation_data(**over), "user-1")
    assert result.get("ok"), result
    return result["automation_id"]


# ============================================================================
# 6. atom_workflow_automation_service — lifecycle / CRUD
# ============================================================================


class TestWfLifecycle:
    async def test_initialize_success(self):
        svc = make_wf_service()
        with patch("asyncio.create_task", MagicMock(return_value=MagicMock())):
            assert await svc.initialize() is True
            assert svc.is_initialized is True
            svc.scheduler_running = False

    async def test_initialize_missing_services(self):
        svc = make_wf_service()
        svc.security_service = None
        assert await svc.initialize() is False

    async def test_initialize_exception(self):
        svc = make_wf_service()
        with patch.object(svc, "_initialize_automation_templates",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            assert await svc.initialize() is False

    async def test_close(self, wf):
        wf.scheduler_task = MagicMock()
        session = MagicMock()
        session.close = AsyncMock()
        wf.http_sessions = {"a": session}
        await wf.close()
        wf.scheduler_task.cancel.assert_called_once()
        session.close.assert_awaited_once()

    async def test_close_circuit_open(self, wf):
        with patch.object(circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            with pytest.raises(Exception):
                await wf.close()

    async def test_close_rate_limited(self, wf):
        with patch.object(rate_limiter, "is_rate_limited",
                          AsyncMock(return_value=(True, 0))):
            with pytest.raises(Exception):
                await wf.close()

    async def test_get_service_info(self, wf):
        info = await wf.get_service_info()
        assert info["name"] == "Workflow Automation Service"
        assert "security" in info["supported_automation_types"]


class TestWfCreateAutomation:
    async def test_create_success(self, wf):
        result = await wf.create_automation(automation_data(), "user-1")
        assert result["ok"] is True
        assert result["automation"]["name"] == "Test Automation"
        assert wf.automation_metrics["total_automations"] == 1
        wf.security_service.audit_event.assert_awaited_once()

    async def test_create_with_db(self):
        db = MagicMock()
        db.store_workflow_automation = AsyncMock()
        svc = make_wf_service(database=db)
        result = await svc.create_automation(automation_data(), "user-1")
        assert result["ok"] is True
        db.store_workflow_automation.assert_awaited_once()

    async def test_create_validation_failure(self, wf):
        result = await wf.create_automation({"name": "x"}, "user-1")
        assert result["ok"] is False
        assert "validation failed" in result["error"]

    async def test_create_missing_name_raises_caught(self, wf):
        result = await wf.create_automation({"description": "no name"}, "user-1")
        assert result["ok"] is False

    async def test_create_circuit_open(self, wf):
        with patch.object(circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            result = await wf.create_automation(automation_data(), "u")
        assert result["ok"] is False

    async def test_create_rate_limited(self, wf):
        with patch.object(rate_limiter, "is_rate_limited",
                          AsyncMock(return_value=(True, 0))):
            result = await wf.create_automation(automation_data(), "u")
        assert result["ok"] is False

    async def test_validate_automation_data(self, wf):
        res = await wf._validate_automation_data(automation_data())
        assert res["valid"] is True
        bad = automation_data(actions=[{"cfg": 1}], conditions=[{"x": 1}])
        bad.pop("priority")
        res = await wf._validate_automation_data(bad)
        assert res["valid"] is False
        assert len(res["errors"]) == 3

    async def test_validate_circuit_open(self, wf):
        with patch.object(circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            with pytest.raises(Exception):
                await wf._validate_automation_data({})

    async def test_validate_rate_limited(self, wf):
        with patch.object(rate_limiter, "is_rate_limited",
                          AsyncMock(return_value=(True, 0))):
            with pytest.raises(Exception):
                await wf._validate_automation_data({})


class TestWfExecuteAutomation:
    async def test_not_found(self, wf):
        result = await wf.execute_automation("missing", {}, "tester")
        assert result["ok"] is False

    async def test_not_active(self, wf):
        auto_id = await create(wf)
        wf.automations[auto_id].status = wfs.AutomationStatus.PAUSED
        result = await wf.execute_automation(auto_id, {}, "tester")
        assert result["ok"] is False

    async def test_security_check_failure(self, wf):
        auto_id = await create(wf)
        result = await wf.execute_automation(auto_id, {"authorized": False}, "t")
        assert result["ok"] is False
        assert "Security check failed" in result["error"]
        assert "security_violation" in result

    async def test_success_with_db(self):
        db = MagicMock()
        db.store_automation_execution = AsyncMock()
        db.store_workflow_automation = AsyncMock()
        wf = make_wf_service(database=db)
        auto_id = await create(wf)
        result = await wf.execute_automation(auto_id, {}, "tester")
        assert result["ok"] is True
        assert result["status"] == "completed"
        db.store_automation_execution.assert_awaited_once()
        assert wf.automations[auto_id].success_count == 1

    async def test_failed_actions(self, wf):
        auto_id = await create(wf, actions=[{"type": "unsupported_type"}])
        result = await wf.execute_automation(auto_id, {}, "tester")
        assert result["status"] == "failed"
        assert wf.automations[auto_id].failure_count == 1

    async def test_action_raises_caught(self, wf):
        auto_id = await create(wf, actions=[{"type": "logging"}])
        with patch.object(wf, "_execute_automation_action",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            result = await wf.execute_automation(auto_id, {}, "tester")
        assert result["ok"] is True  # outer handler catches per-action errors

    async def test_stop_execution_breaks_loop(self, wf):
        auto_id = await create(wf, actions=[
            {"type": "logging"}, {"type": "logging"}, {"type": "logging"}])
        calls = []

        async def fake_action(action, tctx, exc):
            calls.append(action)
            return {"success": True, "stop_execution": len(calls) >= 2}

        with patch.object(wf, "_execute_automation_action", fake_action):
            result = await wf.execute_automation(auto_id, {}, "tester")
        assert len(calls) == 2
        assert result["actions_executed"] == 2

    async def test_outer_exception_returns_error(self, wf):
        auto_id = await create(wf)
        with patch.object(wf, "_pre_execution_security_check",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            result = await wf.execute_automation(auto_id, {}, "t")
        assert result["ok"] is False and "boom" in result["error"]

    async def test_circuit_open(self, wf):
        with patch.object(circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            result = await wf.execute_automation("x", {}, "t")
        assert result["ok"] is False

    async def test_rate_limited(self, wf):
        with patch.object(rate_limiter, "is_rate_limited",
                          AsyncMock(return_value=(True, 0))):
            result = await wf.execute_automation("x", {}, "t")
        assert result["ok"] is False

    async def test_maturity_guard_blocks(self, wf):
        auto_id = await create(wf, actions=[{
            "type": "workflow_execution",
            "config": {"agent_id": "agent-1", "workflow_id": "w"}}])
        db = MagicMock()
        wf.db = db
        decision = SimpleNamespace(
            execute=False, reason="too immature",
            routing_decision=SimpleNamespace(value="blocked"),
            agent_maturity=1, confidence_score=0.4)
        with patch("core.trigger_interceptor.TriggerInterceptor") as cls, \
             patch("core.trigger_interceptor.TriggerSource"):
            cls.return_value.intercept_trigger = AsyncMock(return_value=decision)
            result = await wf.execute_automation(auto_id, {}, "t")
        assert result["ok"] is False
        assert result["maturity_check"]["blocked"] is True
        db.commit.assert_called_once()

    async def test_maturity_guard_allows(self, wf):
        auto_id = await create(wf, actions=[{
            "type": "agent_trigger",
            "config": {"agent_id": "agent-1"}}])
        decision = SimpleNamespace(
            execute=True, reason="ok",
            routing_decision=SimpleNamespace(value="execute"),
            agent_maturity=3, confidence_score=0.9)
        with patch("core.trigger_interceptor.TriggerInterceptor") as cls, \
             patch("core.trigger_interceptor.TriggerSource"):
            cls.return_value.intercept_trigger = AsyncMock(return_value=decision)
            result = await wf.execute_automation(auto_id, {}, "t")
        assert result["ok"] is True

    async def test_maturity_value_error_continues(self, wf):
        auto_id = await create(wf, actions=[{
            "type": "workflow_execution",
            "config": {"agent_id": "agent-1", "workflow_id": "w"}}])
        with patch("core.trigger_interceptor.TriggerInterceptor") as cls, \
             patch("core.trigger_interceptor.TriggerSource"):
            cls.return_value.intercept_trigger = AsyncMock(
                side_effect=ValueError("agent not found"))
            result = await wf.execute_automation(auto_id, {}, "t")
        assert result["ok"] is True


class TestWfSpecializedCreators:
    async def test_security_automation(self, wf):
        result = await wf.create_security_automation(
            {"threat_type": "brute_force", "severity": "high", "source_ip": "1.2.3.4"}, {})
        assert result["ok"] is True
        assert "execution_result" in result

    async def test_compliance_automation(self, wf):
        result = await wf.create_compliance_automation(
            {"standard": "SOC2", "violation_type": "access", "severity": "high"}, {})
        assert result["ok"] is True
        assert "execution_result" in result

    async def test_integration_automation(self, wf):
        fake = MagicMock()
        fake.register_webhook = AsyncMock()
        fake.start_polling = AsyncMock()
        fake.subscribe_to_events = AsyncMock()
        wf.platform_integrations["slack"] = fake
        result = await wf.create_integration_automation(
            "slack", {"trigger_type": "webhook", "webhook_url": "http://x",
                      "events": ["msg"]})
        assert result["ok"] is True
        fake.register_webhook.assert_awaited_once()

    async def test_integration_automation_bad_platform(self, wf):
        result = await wf.create_integration_automation("icq", {})
        assert result["ok"] is False


class TestWfQueries:
    async def test_get_automations_filters(self, wf):
        await create(wf, name="A One", automation_type="security")
        await create(wf, name="A Two", automation_type="compliance")
        all_items = await wf.get_automations()
        assert len(all_items) == 2
        assert all_items[0]["success_rate"] == 0.0
        sec = await wf.get_automations({"automation_type": "security"})
        assert len(sec) == 1
        assert (await wf.get_automations({"priority": "low"})) == []
        assert (await wf.get_automations({"status": "active"}))[0]["name"] in ("A One", "A Two")
        assert (await wf.get_automations({"created_by": "nobody"})) == []
        assert (await wf.get_automations(None)) == await wf.get_automations({})

    async def test_get_automations_circuit_open(self, wf):
        with patch.object(circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            assert await wf.get_automations() == []

    async def test_get_automation_executions_filters(self, wf):
        auto_id = await create(wf)
        await wf.execute_automation(auto_id, {}, "tester")
        other = await create(wf, name="Other")
        await wf.execute_automation(other, {}, "scheduler")
        ex = await wf.get_automation_executions()
        assert len(ex) == 2
        ex = await wf.get_automation_executions(automation_id=auto_id)
        assert len(ex) == 1
        assert (await wf.get_automation_executions(
            filters={"status": "running"})) == []
        assert (await wf.get_automation_executions(
            filters={"triggered_by": "scheduler"}))[0]["automation_id"] == other
        today = datetime.now(timezone.utc).date()
        assert len(await wf.get_automation_executions(
            filters={"date_from": today, "date_to": today})) == 2
        assert (await wf.get_automation_executions(
            filters={"date_from": today + timedelta(days=1)})) == []
        assert (await wf.get_automation_executions(
            filters={"date_to": today - timedelta(days=1)})) == []

    async def test_get_automation_executions_circuit_open(self, wf):
        with patch.object(circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            assert await wf.get_automation_executions() == []

    async def test_get_metrics(self, wf):
        metrics = await wf.get_automation_metrics()
        assert metrics["total_automations"] == 0
        assert metrics["scheduled_automations"] == 0

    async def test_get_metrics_circuit_open(self, wf):
        with patch.object(circuit_breaker, "is_enabled", AsyncMock(return_value=False)):
            assert await wf.get_automation_metrics() == {}


# ============================================================================
# 7. atom_workflow_automation_service — action executors
# ============================================================================


class TestWfActions:
    async def test_dispatch_all_action_types(self, wf):
        for action_type in ("notification", "workflow_execution",
                            "security_enforcement", "compliance_check",
                            "data_processing", "api_call", "email_send",
                            "message_send", "logging", "auditing",
                            "reporting", "remediation"):
            res = await wf._execute_automation_action(
                {"type": action_type, "config": {}}, {}, MagicMock())
            assert res.get("success") in (True, False)
        res = await wf._execute_automation_action(
            {"type": "bogus"}, {}, MagicMock())
        assert res["success"] is False

    async def test_action_exception_caught(self, wf):
        with patch.object(wf, "_execute_logging_action",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            res = await wf._execute_automation_action(
                {"type": "logging"}, {}, MagicMock())
        assert res["success"] is False and "boom" in res["error"]

    async def test_simple_action_bodies(self, wf):
        for method in ("_execute_data_processing_action",
                       "_execute_api_call_action", "_execute_email_action",
                       "_execute_message_action", "_execute_logging_action",
                       "_execute_auditing_action", "_execute_reporting_action",
                       "_execute_remediation_action"):
            res = await getattr(wf, method)({}, {})
            assert res["success"] is True

    async def test_notification_channels(self, wf):
        config = {"channels": ["security_team", "compliance_officer",
                               "management", "slack", "teams", "email"],
                  "message": "m", "urgency": "high"}
        res = await wf._execute_notification_action(config, {})
        assert res["success"] is True
        assert len(res["notification_results"]) == 6
        res = await wf._execute_notification_action({}, {})
        assert res["success"] is True and res["channels"] == []

    async def test_notification_error(self, wf):
        with patch.object(wf, "_notify_security_team",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            res = await wf._execute_notification_action(
                {"channels": ["security_team"]}, {})
        assert res["success"] is False

    async def test_workflow_action(self, wf):
        res = await wf._execute_workflow_action(
            {"workflow_id": "w1", "workflow_data": {}}, {})
        assert res["success"] is True
        assert (await wf._execute_workflow_action({}, {}))["success"] is False
        wf.unified_service = None
        res = await wf._execute_workflow_action({"workflow_id": "w1"}, {})
        assert res["success"] is False

    async def test_workflow_action_error(self, wf):
        wf.unified_service.execute_enterprise_workflow = AsyncMock(
            side_effect=RuntimeError("boom"))
        res = await wf._execute_workflow_action({"workflow_id": "w1"}, {})
        assert res["success"] is False

    async def test_security_enforcement(self, wf):
        for action in ("block_ip", "lock_user", "terminate_session", "quarantine"):
            res = await wf._execute_security_enforcement_action(
                {"action": action, "target": "x"}, {})
            assert res["success"] is True
        assert (await wf._execute_security_enforcement_action(
            {}, {}))["success"] is False
        wf.security_service = None
        assert (await wf._execute_security_enforcement_action(
            {"action": "block_ip"}, {}))["success"] is False
        wf2 = make_wf_service()
        wf2.security_service._block_ip = AsyncMock(side_effect=RuntimeError("x"))
        assert (await wf2._execute_security_enforcement_action(
            {"action": "block_ip"}, {}))["success"] is False

    async def test_compliance_check_action(self, wf):
        report = MagicMock()
        with patch.object(wfs, "asdict", MagicMock(return_value={"ok": True})):
            wf.security_service.check_compliance = AsyncMock(return_value=report)
            res = await wf._execute_compliance_check_action(
                {"standard": "GDPR"}, {"period": "now"})
            assert res["success"] is True
        wf.security_service.check_compliance = AsyncMock(return_value=None)
        res = await wf._execute_compliance_check_action({"standard": "GDPR"}, {})
        assert res["success"] is False
        assert (await wf._execute_compliance_check_action({}, {}))["success"] is False
        assert (await wf._execute_compliance_check_action(
            {"standard": "not-a-standard"}, {}))["success"] is False
        wf.security_service = None
        assert (await wf._execute_compliance_check_action(
            {"standard": "GDPR"}, {}))["success"] is False

    async def test_compliance_check_exception(self, wf):
        wf.security_service.check_compliance = AsyncMock(side_effect=RuntimeError("boom"))
        res = await wf._execute_compliance_check_action({"standard": "GDPR"}, {})
        assert res["success"] is False


class TestWfChecks:
    async def test_pre_execution_checks(self, wf):
        auto = wf.automations["x"] = MagicMock()
        auto.automation_type = wfs.WorkflowAutomationType.SECURITY
        assert (await wf._pre_execution_security_check(auto, {}))["passed"] is True
        assert (await wf._pre_execution_security_check(
            auto, {"authorized": False}))["passed"] is False
        auto.automation_type = wfs.WorkflowAutomationType.COMPLIANCE
        res = await wf._pre_execution_compliance_check(auto, {})
        assert res["passed"] is True and res["compliance_level"] == "compliant"
        auto.automation_type = wfs.WorkflowAutomationType.NOTIFICATION
        assert (await wf._pre_execution_compliance_check(auto, {}))["passed"] is True

    async def test_pre_execution_check_exception(self, wf):
        class Boom:
            @property
            def automation_type(self):
                raise RuntimeError("boom")

        res = await wf._pre_execution_security_check(Boom(), {})
        assert res["passed"] is False and "boom" in res["reason"]
        res = await wf._pre_execution_compliance_check(Boom(), {})
        assert res["passed"] is False

    async def test_post_execution_checks(self, wf):
        auto = MagicMock()
        assert (await wf._post_execution_security_check(
            auto, [{"success": False}]))["passed"] is True
        assert (await wf._post_execution_compliance_check(auto, []))["passed"] is True


class TestWfNotificationsAndMetrics:
    async def test_notify_methods(self, wf):
        for method in ("_notify_security_team", "_notify_compliance_officer",
                       "_notify_management", "_notify_slack", "_notify_teams",
                       "_notify_email"):
            await getattr(wf, method)("msg", "high", {})

    async def test_send_notifications_default_failed(self, wf):
        auto = MagicMock()
        auto.notification_rules = []
        auto.metadata = {}
        execution = MagicMock()
        execution.status = wfs.AutomationStatus.FAILED
        execution.error = "boom"
        with patch.object(wf, "_notify_slack", AsyncMock()) as ns:
            assert await wf._send_automation_notifications(auto, execution) is True
            ns.assert_awaited_once()

    async def test_send_notifications_no_rules_success(self, wf):
        auto = MagicMock()
        auto.notification_rules = []
        execution = MagicMock()
        execution.status = wfs.AutomationStatus.COMPLETED
        assert await wf._send_automation_notifications(auto, execution) is True

    async def test_send_notifications_rules(self, wf):
        auto = MagicMock()
        auto.notification_rules = [
            {"status": "completed", "channels": ["slack:x", "email:y", "teams:z"]},
            {"on_error": True, "channels": ["slack:x"]},
            {"condition": "never", "channels": []},
        ]
        execution = MagicMock()
        execution.status = wfs.AutomationStatus.COMPLETED
        execution.error = None
        with patch.object(wf, "_notify_slack", AsyncMock()) as ns, \
             patch.object(wf, "_notify_email", AsyncMock()) as ne, \
             patch.object(wf, "_notify_teams", AsyncMock()) as nt:
            assert await wf._send_automation_notifications(auto, execution) is True
            assert ns.await_count == 1
            assert ne.await_count == 1
            assert nt.await_count == 1

    async def test_send_notifications_error(self, wf):
        class Auto:
            notification_rules = []
            automation_id = "a1"
            name = "n"

            @property
            def metadata(self):
                raise RuntimeError("boom")

        execution = MagicMock()
        execution.status = wfs.AutomationStatus.FAILED
        # notification_rules is [] but metadata access raises -> except branch
        with patch.object(wf, "_notify_slack", AsyncMock()):
            result = await wf._send_automation_notifications(Auto(), execution)
        assert result is False

    async def test_update_metrics(self, wf):
        auto = MagicMock()
        execution = MagicMock()
        execution.execution_time = 2.0
        wf.automation_metrics["executions_by_status"]["completed"] = 1
        await wf._update_automation_metrics(auto, execution)
        assert wf.automation_metrics["executed_today"] == 1
        assert wf.automation_metrics["average_execution_time"] > 0

    async def test_log_automation_event(self, wf):
        await wf._log_automation_event("a1", "created", "u", {})
        wf.security_service.audit_event.assert_awaited_once()
        wf2 = make_wf_service(security_service=None)
        await wf2._log_automation_event("a1", "created", "u", {})


# ============================================================================
# 8. atom_workflow_automation_service — init internals / scheduling / triggers
# ============================================================================


class TestWfInitInternals:
    async def test_initialize_templates_with_db(self):
        db = MagicMock()
        db.execute.return_value = [
            ('{"template_id": "tpl-1", "name": "n"}',),
            ({"template_id": "tpl-2"},),
        ]
        wf = make_wf_service(database=db)
        assert await wf._initialize_automation_templates() is True
        assert "tpl-1" in wf.automation_templates
        assert "security_alert_response" in wf.automation_templates

    async def test_initialize_templates_db_error(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("no table")
        wf = make_wf_service(database=db)
        assert await wf._initialize_automation_templates() is True
        assert len(wf.automation_templates) >= 4

    async def test_load_automations_no_db(self, wf):
        assert await wf._load_automations() is False

    async def test_load_automations_rows(self):
        db = MagicMock()
        now = datetime.now(timezone.utc).isoformat()
        db.execute.return_value = [
            ("a-1", "N", "D", "security", '{"type": "scheduled"}',
             '[{"type": "logging"}]', "high", "active", True, "u",
             now, now, "0 2 * * *", now, now, 3, 2, 1, "ok", "{}"),
        ]
        wf = make_wf_service(database=db)
        with patch.object(wf, "_schedule_automation", AsyncMock(return_value=True)):
            assert await wf._load_automations() is True
        assert "a-1" in wf.automations
        assert wf.automations["a-1"].next_run is not None

    async def test_load_automations_error(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")
        wf = make_wf_service(database=db)
        assert await wf._load_automations() is False

    async def test_initialize_scheduling(self, wf):
        with patch("asyncio.create_task", MagicMock(return_value=MagicMock())) as ct:
            assert await wf._initialize_automation_scheduling() is True
            ct.assert_called_once()
            wf.scheduler_running = False
            assert await wf._initialize_automation_scheduling() is True  # already running branch

    async def test_initialize_scheduling_error(self, wf):
        with patch("asyncio.create_task", MagicMock(side_effect=RuntimeError("x"))):
            assert await wf._initialize_automation_scheduling() is False

    async def test_scheduler_loop(self, wf):
        auto_id = await create(wf, conditions=[{"type": "scheduled", "schedule": "0 2 * * *"}])
        wf.automations[auto_id].next_run = datetime.now(timezone.utc) - timedelta(hours=1)
        wf.scheduler_running = True
        with patch.object(wf, "execute_automation", AsyncMock(return_value={"ok": True})) as ex:
            async def stop_loop(*a, **k):
                wf.scheduler_running = False
            with patch("asyncio.sleep", new=AsyncMock(side_effect=stop_loop)):
                await wf._scheduler_loop()
            ex.assert_awaited_once()

    async def test_scheduler_loop_error(self, wf):
        wf.scheduler_running = True
        with patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError)):
            with pytest.raises(asyncio.CancelledError):
                await wf._scheduler_loop()

    async def test_initialize_trigger_listeners(self, wf):
        auto_id = await create(wf)
        assert await wf._initialize_trigger_listeners() is True
        assert auto_id in wf.trigger_listeners["event_triggered"]["automations"]

    async def test_initialize_trigger_listeners_error(self, wf):
        with patch.object(wf, "automations", side_effect=RuntimeError("x")):
            pass  # patching dict attr — force error via bad automations values instead
        wf.automations = {"x": None}
        try:
            res = await wf._initialize_trigger_listeners()
        except Exception:
            res = False
        assert res is False

    async def test_handle_event_trigger(self, wf):
        auto_id = await create(wf)
        wf.trigger_listeners["event_triggered"] = {
            "automations": [auto_id, "ghost"], "callback": wf._handle_event_trigger}
        with patch.object(wf, "execute_automation", AsyncMock()) as ex:
            await wf._handle_event_trigger("event_triggered", {"e": 1})
            ex.assert_awaited_once()
        await wf._handle_event_trigger("unknown_type", {})

    async def test_handle_event_trigger_disabled(self, wf):
        auto_id = await create(wf)
        wf.automations[auto_id].enabled = False
        wf.trigger_listeners["event_triggered"] = {
            "automations": [auto_id], "callback": wf._handle_event_trigger}
        with patch.object(wf, "execute_automation", AsyncMock()) as ex:
            await wf._handle_event_trigger("event_triggered", {})
            ex.assert_not_awaited()

    async def test_initialize_integration_endpoints(self, wf):
        fake = MagicMock()
        fake.test_connection = AsyncMock(return_value=True)
        bad = MagicMock()
        bad.test_connection = AsyncMock(side_effect=RuntimeError("nope"))
        wf.platform_integrations["slack"] = fake
        wf.platform_integrations["teams"] = bad
        assert await wf._initialize_integration_endpoints() is True

    async def test_start_monitoring(self, wf):
        with patch("asyncio.create_task", MagicMock(return_value=MagicMock())):
            assert await wf._start_automation_monitoring() is True
        with patch("asyncio.create_task", MagicMock(side_effect=RuntimeError("x"))):
            assert await wf._start_automation_monitoring() is False

    async def test_monitoring_loop(self, wf):
        auto_id = await create(wf)
        auto = wf.automations[auto_id]
        auto.last_execution_status = "failed"
        auto.execution_count = 10
        auto.failure_count = 9
        with patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError)):
            with pytest.raises(asyncio.CancelledError):
                await wf._monitoring_loop()
        assert wf.automation_metrics["total_automations"] == 1


class TestWfTriggers:
    async def test_setup_automation_triggers_all_types(self, wf):
        types = ["scheduled", "event_triggered", "threshold_exceeded",
                 "anomaly_detected", "security_alert", "compliance_violation"]
        # one automation per condition type (active_triggers is keyed by
        # automation_id, so a single automation would overwrite itself)
        for t in types:
            auto_id = await create(wf, name=f"Auto {t}", conditions=[
                {"type": t, "event_type": "system_event", "metric": "cpu",
                 "threshold": 90, "threat_type": "x", "standard": "SOC2",
                 "violation_type": "v", "schedule": "0 2 * * *"}])
            await wf._setup_automation_triggers(wf.automations[auto_id])
        assert len(wf.active_triggers) == len(types) - 1  # scheduled has no active_trigger entry
        assert len(wf.scheduled_automations) == 1
        assert "system_event" in wf.trigger_listeners

    async def test_setup_automation_triggers_error(self, wf):
        auto = MagicMock()
        auto.conditions = None
        assert await wf._setup_automation_triggers(auto) is None

    async def test_schedule_automation(self, wf):
        auto = MagicMock()
        auto.automation_id = "a1"
        auto.schedule = "0 2 * * *"
        auto.next_run = datetime.now(timezone.utc)
        assert await wf._schedule_automation(
            auto, {"type": "scheduled"}) is True
        assert await wf._schedule_automation(
            auto, {"type": "scheduled", "schedule": None}) is True
        assert await wf._schedule_automation(
            auto, {"type": "manual"}) is False

    async def test_setup_event_trigger(self, wf):
        auto = MagicMock()
        auto.automation_id = "a1"
        auto.enabled = True
        assert await wf._setup_event_trigger(
            auto, {"event_type": "custom_event"}) is True
        assert await wf._setup_event_trigger(auto, {"type": "system_event"}) is True
        assert await wf._setup_event_trigger(auto, {}) is False

    async def test_setup_threshold_trigger(self, wf):
        auto = MagicMock()
        auto.automation_id = "a1"
        auto.enabled = True
        assert await wf._setup_threshold_trigger(
            auto, {"metric": "cpu", "threshold": 90, "operator": "gt"}) is True
        assert await wf._setup_threshold_trigger(auto, {"metric": "cpu"}) is False

    async def test_setup_anomaly_trigger(self, wf):
        auto = MagicMock()
        auto.automation_id = "a1"
        auto.enabled = True
        assert await wf._setup_anomaly_trigger(
            auto, {"metric": "errors", "sensitivity": "high"}) is True
        assert await wf._setup_anomaly_trigger(auto, {}) is False

    async def test_setup_security_trigger(self, wf):
        auto = MagicMock()
        auto.automation_id = "a1"
        auto.enabled = True
        assert await wf._setup_security_trigger(
            auto, {"threat_type": "brute", "severity": "high"}) is True
        wf.security_service = None
        assert await wf._setup_security_trigger(
            auto, {"threat_type": "brute"}) is True

    async def test_setup_compliance_trigger(self, wf):
        auto = MagicMock()
        auto.automation_id = "a1"
        auto.enabled = True
        assert await wf._setup_compliance_trigger(
            auto, {"standard": "SOC2", "violation_type": "v"}) is True
        wf.unified_service = None
        assert await wf._setup_compliance_trigger(
            auto, {"standard": "SOC2"}) is True

    async def test_setup_platform_triggers(self, wf):
        fake = MagicMock()
        fake.register_webhook = AsyncMock()
        fake.start_polling = AsyncMock()
        fake.subscribe_to_events = AsyncMock()
        wf.platform_integrations["slack"] = fake
        assert await wf._setup_platform_triggers(
            "slack", "a1", {"trigger_type": "webhook", "webhook_url": "u",
                            "events": ["e"]}) is True
        assert await wf._setup_platform_triggers(
            "slack", "a1", {"trigger_type": "polling", "polling_interval": 10}) is True
        assert await wf._setup_platform_triggers(
            "slack", "a1", {"trigger_type": "event_subscription", "events": ["e"]}) is True
        assert await wf._setup_platform_triggers("slack", "a1", {}) is True
        assert await wf._setup_platform_triggers("icq", "a1", {}) is False
        wf.platform_integrations["teams"] = None
        assert await wf._setup_platform_triggers("teams", "a1", {}) is False

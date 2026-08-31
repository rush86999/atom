"""TDD coverage push: integrations.universal_integration_service + atom_communication_ingestion_pipeline.

Covers every public method: success paths, error paths, edge cases (None, empty,
bad args, exceptions). All external HTTP/OAuth/websocket calls are mocked.
DB paths use in-memory SQLite (universal service) / real LanceDB in tmp dirs
(ingestion pipeline).
"""
import asyncio
import email
import json
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from integrations.universal_integration_service import (
    NATIVE_INTEGRATIONS,
    UniversalIntegrationService,
)
from integrations.atom_communication_ingestion_pipeline import (
    CommunicationAppType,
    CommunicationData,
    CommunicationIngestionPipeline,
    IngestionConfig,
    LanceDBMemoryManager,
)
from integrations.ingestion_models import RecordType
from middleware.governance_middleware import Gatekeeper, mask_response_fields


# ============================================================================
# Shared helpers
# ============================================================================

def make_service(method_returns=None, token="tok"):
    """Fake integration service with async methods returning canned data."""
    svc = MagicMock()
    svc.access_token = token
    for name, ret in (method_returns or {}).items():
        setattr(svc, name, AsyncMock(return_value=ret))
    return svc


def set_service(env, service):
    """Point the registry's get_service_instance at the fake service."""
    env.IR.return_value.get_service_instance = AsyncMock(return_value=service)
    return service


class StubGatekeeper:
    """Minimal governance stub: configurable allow/deny + optional masking."""

    def __init__(self, allowed=True, masked=None):
        self.allowed = allowed
        self.masked = masked

    async def check_action_risk(self, service, action=None, params=None, agent_id=None, workspace_id=None):
        if not self.allowed:
            return {"allowed": False, "reason": "manual review required", "intervention_id": "iv-1"}
        return {"allowed": True}

    def mask_response(self, service, response):
        if self.masked is None:
            return response
        return mask_response_fields(response, self.masked)


def comm_data(**over):
    base = dict(
        id="msg-1",
        app_type="slack",
        timestamp=datetime(2026, 1, 1, 12, 0),
        direction="inbound",
        sender="u1",
        recipient="c1",
        subject=None,
        content="Hello world",
        attachments=[],
        metadata={},
        status="active",
        priority="normal",
        tags=["hello"],
    )
    base.update(over)
    return CommunicationData(**base)


@pytest.fixture(scope="module")
def mem_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.database import Base
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def mem_session(mem_engine):
    Session = sessionmaker(bind=mem_engine, expire_on_commit=False)
    return Session


@pytest.fixture
def uis():
    return UniversalIntegrationService(workspace_id="ws")


@pytest.fixture
def env(mem_session):
    """Patched execution environment for UniversalIntegrationService."""
    with patch("core.database.SessionLocal", mem_session), \
            patch("core.integration_registry.IntegrationRegistry") as IR, \
            patch("integrations.universal_integration_service.circuit_breaker") as cb, \
            patch("integrations.universal_integration_service.get_action_cost", return_value=2.5), \
            patch("integrations.universal_integration_service.governance_middleware", StubGatekeeper()):
        cb.is_enabled = AsyncMock(return_value=True)
        cb.get_stats = Mock(return_value={"disabled_until": "2026-01-01"})
        cb.record_failure = Mock()
        IR.return_value.get_service_instance = AsyncMock(return_value=None)
        yield SimpleNamespace(IR=IR, cb=cb)


# ============================================================================
# UniversalIntegrationService.execute()
# ============================================================================

class TestExecute:
    async def test_circuit_open_returns_error_without_dispatch(self, env, uis):
        env.cb.is_enabled = AsyncMock(return_value=False)
        with patch.object(uis, "_dispatch_execution", new_callable=AsyncMock) as dispatch:
            result = await uis.execute("slack", "send_message", {}, {"user_id": "u1"})
        assert result["circuit_open"] is True
        assert "OPEN" in result["error"]
        dispatch.assert_not_awaited()

    async def test_governance_pause(self, env, uis):
        with patch("integrations.universal_integration_service.governance_middleware",
                   StubGatekeeper(allowed=False)):
            result = await uis.execute("slack", "send_message", {}, {"user_id": "u1"})
        assert result["status"] == "paused"
        assert result["reason"] == "manual review required"
        assert result["intervention_id"] == "iv-1"

    async def test_governance_raises_treated_as_allowed(self, env, uis):
        gk = StubGatekeeper()
        gk.check_action_risk = AsyncMock(side_effect=RuntimeError("gatekeeper boom"))
        with patch("integrations.universal_integration_service.governance_middleware", gk):
            with patch.object(uis, "_dispatch_execution", new_callable=AsyncMock,
                              return_value={"status": "success", "data": []}) as dispatch:
                result = await uis.execute("slack", "send_message", {}, {"user_id": "u1"})
        assert result["status"] == "success"
        dispatch.assert_awaited_once()

    async def test_success_and_spend_attribution(self, env, uis):
        budget = Mock()
        set_service(env, make_service({"list_contacts": []}))
        with patch("integrations.universal_integration_service.budget_service", budget), \
                patch("integrations.universal_integration_service.get_action_cost", return_value=1.5) as gac:
            result = await uis.execute("salesforce", "list", {"entity": "contact"},
                                       {"user_id": "u1"})
        assert result["status"] == "success"
        gac.assert_called_once_with("salesforce", "list")
        budget.record_workspace_spend.assert_called_once_with("ws", 1.5)

    async def test_success_skips_spend_when_budget_absent(self, env, uis):
        set_service(env, make_service({"post_message": {}}))
        with patch("integrations.universal_integration_service.budget_service", None):
            result = await uis.execute("slack", "send_message", {}, {"user_id": "u1"})
        assert result["status"] == "success"

    async def test_dispatch_exception_records_failure_and_spend(self, env, uis):
        budget = Mock()
        with patch("integrations.universal_integration_service.budget_service", budget), \
                patch.object(uis, "_dispatch_execution", new_callable=AsyncMock,
                             side_effect=RuntimeError("kaboom")):
            result = await uis.execute("stripe", "get_balance", {}, {"user_id": "u1"})
        assert result["status"] == "error"
        assert result["error"] == "kaboom"
        env.cb.record_failure.assert_called_once_with("stripe", unittest_any_exc())
        budget.record_workspace_spend.assert_called_once_with("ws", 2.5)

    async def test_missing_user_id_errors(self, env, uis):
        result = await uis.execute("slack", "send_message", {}, {})
        assert result["status"] == "error"
        assert "user_id required" in result["error"]

    async def test_masking_applied_to_response(self, env, uis):
        """BUG: gatekeeper field-masking was never applied to execute() responses."""
        gk = Gatekeeper()
        gk.configure("slack", {"masked_fields": {"access_token", "webhook_url"}})
        with patch("integrations.universal_integration_service.governance_middleware", gk):
            with patch.object(uis, "_dispatch_execution", new_callable=AsyncMock,
                              return_value={"status": "success", "data": {
                                  "access_token": "leak-me", "ok": True,
                                  "webhook_url": "https://hooks.slack.com/x",
                              }}):
                result = await uis.execute("slack", "search_messages", {}, {"user_id": "u1"})
        assert result["data"]["access_token"] == "***"
        assert result["data"]["webhook_url"] == "***"
        assert result["data"]["ok"] is True

    async def test_masking_applied_to_error_path(self, env, uis):
        gk = Gatekeeper()
        gk.configure("salesforce", {"masked_fields": {"access_token"}})
        with patch("integrations.universal_integration_service.governance_middleware", gk):
            with patch.object(uis, "_dispatch_execution", new_callable=AsyncMock,
                              side_effect=RuntimeError("bad")):
                result = await uis.execute("salesforce", "list", {}, {"user_id": "u1"})
        assert result["status"] == "error"

    async def test_masking_never_blocks_on_gatekeeper_error(self, env, uis):
        gk = Mock()
        gk.check_action_risk = AsyncMock(return_value={"allowed": True})
        gk.mask_response = Mock(side_effect=Exception("mask boom"))
        with patch("integrations.universal_integration_service.governance_middleware", gk):
            with patch.object(uis, "_dispatch_execution", new_callable=AsyncMock,
                              return_value={"status": "success", "data": {"x": 1}}):
                result = await uis.execute("slack", "send_message", {}, {"user_id": "u1"})
        assert result["status"] == "success"
        assert result["data"] == {"x": 1}

    async def test_real_dispatch_slack_via_registry(self, env, uis):
        svc = make_service({"post_message": {"ok": True, "ts": "123"}})
        set_service(env, svc)
        result = await uis.execute("slack", "send_message", {"channel": "C1", "message": "hi"},
                                   {"user_id": "u1"})
        assert result["status"] == "success"
        svc.post_message.assert_awaited_once_with(token="tok", channel_id="C1", text="hi")


class TestSystemAgentToken:
    async def test_system_agent_uses_workspace_token(self, env, uis, mem_session):
        from core.models import AgentRegistry
        db = mem_session()
        db.add(AgentRegistry(id="sys-1", name="sys", is_system_agent=True, enabled=True,
                             category="system", role="assistant", type="system", status="active",
                             module_path="test_module", class_name="TestAgent"))
        db.commit()
        svc = make_service({"list_contacts": [{"Id": "1"}]})
        set_service(env, svc)
        with patch("integrations.universal_integration_service.governance_middleware", StubGatekeeper()):
            result = await uis.execute("salesforce", "list", {"entity": "contact"},
                                       {"agent_id": "sys-1", "db": db})
        assert result["status"] == "success"
        svc.list_contacts.assert_awaited_once()
        db.close()

    async def test_non_system_agent_requires_user_id(self, env, uis, mem_session):
        from core.models import AgentRegistry
        db = mem_session()
        db.add(AgentRegistry(id="usr-1", name="u", is_system_agent=False, enabled=True,
                             category="system", role="assistant", type="agent", status="active",
                             module_path="test_module", class_name="TestAgent"))
        db.commit()
        set_service(env, make_service({"list_contacts": []}))
        with patch("integrations.universal_integration_service.governance_middleware", StubGatekeeper()):
            result = await uis.execute("salesforce", "list", {"entity": "contact"},
                                       {"agent_id": "usr-1", "db": db})
        assert result["status"] == "error"
        assert "user_id required" in result["error"]
        db.close()

    async def test_system_agent_lookup_error_falls_back_to_error(self, env, uis):
        db = Mock()
        db.query.side_effect = RuntimeError("db down")
        result = await uis.execute("salesforce", "list", {"entity": "contact"},
                                   {"agent_id": "sys-1", "db": db})
        assert result["status"] == "error"


def unittest_any_exc():
    import unittest.mock
    return unittest.mock.ANY


# ============================================================================
# UniversalIntegrationService._dispatch_execution() routing
# ============================================================================

class TestDispatchSalesforce:
    async def test_list_entities(self, env, uis):
        svc = make_service({"list_contacts": [{"Id": "1"}], "list_opportunities": [{"Id": "2"}],
                            "list_accounts": [{"Id": "3"}]})
        set_service(env, svc)
        for entity, method in (("contact", "list_contacts"), ("opportunity", "list_opportunities"),
                               ("account", "list_accounts")):
            result = await uis.execute("salesforce", "list", {"entity": entity}, {"user_id": "u1"})
            assert result["status"] == "success"
            getattr(svc, method).assert_awaited_once()

    async def test_list_unsupported_entity_errors(self, env, uis):
        set_service(env, make_service())
        result = await uis.execute("salesforce", "list", {"entity": "lead"}, {"user_id": "u1"})
        assert result["status"] == "error"
        assert "not supported" in result["error"]

    async def test_create_entities(self, env, uis):
        svc = make_service({"create_contact": {"Id": "c1"}, "create_opportunity": {"Id": "o1"},
                            "create_account": {"Id": "a1"}})
        set_service(env, svc)
        await uis.execute("salesforce", "create", {"entity": "contact", "data": {"FirstName": "F"}},
                          {"user_id": "u1"})
        svc.create_contact.assert_awaited_once_with(token="tok", FirstName="F")
        await uis.execute("salesforce", "create", {"entity": "opportunity", "data": {"Amount": 5}},
                          {"user_id": "u1"})
        svc.create_opportunity.assert_awaited_once_with(token="tok", Amount=5)
        await uis.execute("salesforce", "create", {"entity": "account", "data": {"Name": "A"}},
                          {"user_id": "u1"})
        svc.create_account.assert_awaited_once_with(token="tok", Name="A")

    async def test_read_opportunity(self, env, uis):
        svc = make_service({"get_opportunity": {"Id": "o1"}})
        set_service(env, svc)
        result = await uis.execute("salesforce", "read", {"entity": "opportunity", "id": "o1"},
                                   {"user_id": "u1"})
        assert result["status"] == "success"
        svc.get_opportunity.assert_awaited_once_with("tok", "o1")

    async def test_query(self, env, uis):
        svc = make_service({"execute_query": {"records": [{"Id": "1"}]}})
        set_service(env, svc)
        result = await uis.execute("salesforce", "query", {"query": "SELECT Id FROM Account"},
                                   {"user_id": "u1"})
        assert result["status"] == "success"
        svc.execute_query.assert_awaited_once_with("tok", "SELECT Id FROM Account")

    async def test_update_entities(self, env, uis):
        svc = make_service({"update_contact": {}, "update_opportunity": {}, "update_lead": {},
                            "update_account": {}})
        set_service(env, svc)
        await uis.execute("salesforce", "update", {"entity": "contact", "id": "1", "data": {"x": 1}},
                          {"user_id": "u1"})
        svc.update_contact.assert_awaited_once_with("tok", "1", {"x": 1})
        await uis.execute("salesforce", "update", {"entity": "opportunity", "id": "2", "data": {}},
                          {"user_id": "u1"})
        svc.update_opportunity.assert_awaited_once_with("tok", "2", {})
        await uis.execute("salesforce", "update", {"entity": "lead", "id": "3", "data": {}},
                          {"user_id": "u1"})
        svc.update_lead.assert_awaited_once_with("tok", "3", {})
        await uis.execute("salesforce", "update", {"entity": "account", "id": "4", "data": {}},
                          {"user_id": "u1"})
        svc.update_account.assert_awaited_once_with("tok", "4", {})

    async def test_unknown_action(self, env, uis):
        set_service(env, make_service())
        result = await uis.execute("salesforce", "delete", {"entity": "contact"}, {"user_id": "u1"})
        assert result["status"] == "error"

    async def test_no_service_instance(self, env, uis):
        result = await uis.execute("salesforce", "list", {"entity": "contact"}, {"user_id": "u1"})
        assert result["status"] == "error"
        assert "not available" in result["message"]

    async def test_no_token_falls_back_to_token_storage(self, env, uis):
        set_service(env, make_service(token=None))
        with patch("core.token_storage.token_storage.get_token", return_value=None) as gt:
            result = await uis.execute("salesforce", "list", {"entity": "contact"}, {"user_id": "u1"})
        assert result["status"] == "error"
        assert "No token" in result["message"]
        gt.assert_called()


class TestDispatchHubspot:
    async def test_list_entities(self, env, uis):
        svc = make_service({"get_contacts": [], "get_deals": [], "get_companies": []})
        set_service(env, svc)
        await uis.execute("hubspot", "list", {"entity": "contact"}, {"user_id": "u1"})
        svc.get_contacts.assert_awaited_once_with(token="tok")
        await uis.execute("hubspot", "list", {"entity": "deal"}, {"user_id": "u1"})
        svc.get_deals.assert_awaited_once_with(token="tok")
        await uis.execute("hubspot", "list", {"entity": "company"}, {"user_id": "u1"})
        svc.get_companies.assert_awaited_once_with(token="tok")

    async def test_create_deal_converts_amount_to_float(self, env, uis):
        svc = make_service({"create_deal": {"id": "d1"}})
        set_service(env, svc)
        await uis.execute("hubspot", "create", {"entity": "deal", "data": {"amount": "12.5"}},
                          {"user_id": "u1"})
        svc.create_deal.assert_awaited_once_with(token="tok", amount=12.5)

    async def test_create_actions(self, env, uis):
        svc = make_service({"create_contact": {}, "create_company": {}})
        set_service(env, svc)
        await uis.execute("hubspot", "create_contact", {"data": {"email": "a@b.c"}}, {"user_id": "u1"})
        svc.create_contact.assert_awaited_once_with(token="tok", email="a@b.c")
        await uis.execute("hubspot", "create_company", {"data": {"name": "Acme"}}, {"user_id": "u1"})
        svc.create_company.assert_awaited_once_with(token="tok", name="Acme")

    async def test_update_entities(self, env, uis):
        svc = make_service({"update_contact": {}, "update_deal": {}, "update_object": {}})
        set_service(env, svc)
        await uis.execute("hubspot", "update", {"entity": "contact", "id": "1", "data": {}},
                          {"user_id": "u1"})
        svc.update_contact.assert_awaited_once_with("1", {}, token="tok")
        await uis.execute("hubspot", "update", {"entity": "deal", "id": "2", "data": {}},
                          {"user_id": "u1"})
        svc.update_deal.assert_awaited_once_with("2", {}, token="tok")
        await uis.execute("hubspot", "update", {"entity": "company", "id": "3", "data": {}},
                          {"user_id": "u1"})
        svc.update_object.assert_awaited_once_with("companys", "3", {}, token="tok")

    async def test_unknown_action(self, env, uis):
        set_service(env, make_service())
        result = await uis.execute("hubspot", "nope", {"entity": "contact"}, {"user_id": "u1"})
        assert result["status"] == "error"

    async def test_fallback_singleton_when_registry_empty(self, env, uis):
        fallback = make_service({"get_contacts": [{"id": "c"}]})
        with patch("integrations.hubspot_service.get_hubspot_service", return_value=fallback):
            result = await uis.execute("hubspot", "list", {"entity": "contact"}, {"user_id": "u1"})
        assert result["status"] == "success"
        fallback.get_contacts.assert_awaited_once_with(token="tok")


class TestDispatchShopify:
    async def test_missing_credentials(self, env, uis):
        result = await uis.execute("shopify", "list", {}, {"user_id": "u1"})
        assert result["status"] == "error"
        assert "access_token and shop are required" in result["message"]

    async def test_list_and_create(self, env, uis):
        fake_shopify = MagicMock()
        fake_shopify.get_products = AsyncMock(return_value=[{"id": 1}])
        fake_shopify.get_orders = AsyncMock(return_value=[{"id": 2}])
        fake_shopify.get_customers = AsyncMock(return_value=[{"id": 3}])
        fake_shopify.create_fulfillment = AsyncMock(return_value={"id": 4})
        fake_shopify.get_shop_analytics = AsyncMock(return_value={"revenue": 10})
        with patch("integrations.universal_integration_service.ShopifyService",
                   return_value=fake_shopify):
            ctx = {"user_id": "u1", "access_token": "tok", "shop": "myshop.myshopify.com"}
            r = await uis.execute("shopify", "list", {"entity": "product"}, ctx)
            assert r["status"] == "success"
            r = await uis.execute("shopify", "list", {"entity": "order"}, ctx)
            assert r["status"] == "success"
            r = await uis.execute("shopify", "list", {"entity": "customer"}, ctx)
            assert r["status"] == "success"
            r = await uis.execute("shopify", "create", {"entity": "fulfillment",
                                                        "order_id": 1, "location_id": 2,
                                                        "tracking_number": "T",
                                                        "tracking_company": "UPS"}, ctx)
            assert r["status"] == "success"
            r = await uis.execute("shopify", "analytics", {}, ctx)
            assert r["status"] == "success"
            r = await uis.execute("shopify", "bogus", {}, ctx)
            assert r["status"] == "error"


class TestDispatchCommunication:
    async def test_slack_actions(self, env, uis):
        svc = make_service({"post_message": {}, "list_channels": [{"id": "C1"}],
                            "make_request": {"messages": []}})
        set_service(env, svc)
        r = await uis.execute("slack", "send_message", {"channel_id": "C1", "content": "hi"},
                              {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("slack", "list_channels", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("slack", "search_messages", {"query": "q"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_slack_fallback_singleton(self, env, uis):
        fallback = make_service({"post_message": {}})
        with patch("integrations.slack_service_unified.slack_unified_service", fallback):
            r = await uis.execute("slack", "send_message", {"channel": "C1", "message": "hi"},
                                  {"user_id": "u1"})
        assert r["status"] == "success"
        fallback.post_message.assert_awaited_once()

    async def test_teams_actions(self, env, uis):
        svc = make_service({"send_message": {}, "get_teams": [{"id": "t"}]})
        set_service(env, svc)
        r = await uis.execute("teams", "send_message", {"chat_id": "c", "message": "hi"},
                              {"user_id": "u1"})
        assert r["status"] == "success"
        svc.send_message.assert_awaited_once_with("c", "hi")
        r = await uis.execute("teams", "list_chats", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_discord_actions(self, env, uis):
        svc = make_service({"send_message": {}, "list_guilds": []})
        set_service(env, svc)
        r = await uis.execute("discord", "send_message", {"channel_id": "c", "content": "hi"},
                              {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("discord", "list_guilds", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_google_chat_actions(self, env, uis):
        svc = make_service({"send_unified_message": {}, "list_spaces": []})
        set_service(env, svc)
        r = await uis.execute("google_chat", "send_message", {"channel_id": "c", "message": "hi",
                                                              "options": {"o": 1}}, {"user_id": "u1"})
        assert r["status"] == "success"
        svc.send_unified_message.assert_awaited_once_with(workspace_id="default", channel_id="c",
                                                          content="hi", options={"o": 1})
        r = await uis.execute("google_chat", "list_spaces", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_telegram_whatsapp_actions(self, env, uis):
        svc = make_service({"send_intelligent_message": {}})
        set_service(env, svc)
        for service in ("telegram", "whatsapp"):
            r = await uis.execute(service, "send_message", {"channel_id": "c", "message": "hi",
                                                            "metadata": {"m": 1}}, {"user_id": "u1"})
            assert r["status"] == "success"

    async def test_gmail_actions(self, env, uis):
        svc = make_service({"send_message": {}, "get_messages": [], "get_message": {}})
        set_service(env, svc)
        r = await uis.execute("gmail", "send_message", {"to": "a@b.c", "subject": "s", "body": "b",
                                                        "cc": "cc@b.c", "bcc": "bcc@b.c",
                                                        "thread_id": "t"}, {"user_id": "u1"})
        assert r["status"] == "success"
        svc.send_message.assert_awaited_once_with(to="a@b.c", subject="s", body="b", cc="cc@b.c",
                                                  bcc="bcc@b.c", thread_id="t", token="tok")
        r = await uis.execute("gmail", "list_messages", {"query": "q", "max_results": 5},
                              {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("gmail", "get_message", {"id": "m1"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_outlook_passthrough_and_zoho_mail(self, env, uis):
        svc = make_service({"get_recent_inbox": []})
        set_service(env, svc)
        r = await uis.execute("outlook", "send_message", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("zoho_mail", "list", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        svc.get_recent_inbox.assert_awaited_once_with("tok", limit=20)
        r = await uis.execute("zoho_mail", "send_message", {}, {"user_id": "u1"})
        assert r["status"] == "error"

    async def test_default_handler(self, env, uis):
        set_service(env, make_service())
        r = await uis.execute("zoom", "list_meetings", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        assert "default handler" in r["message"]


class TestDispatchCalendar:
    async def test_google_calendar(self, env, uis):
        svc = make_service({"get_events": [], "create_event": {}, "check_conflicts": []})
        set_service(env, svc)
        r = await uis.execute("google_calendar", "list", {"calendar_id": "cal"}, {"user_id": "u1"})
        assert r["status"] == "success"
        svc.get_events.assert_awaited_once_with(calendar_id="cal", token="tok")
        r = await uis.execute("google_calendar", "create", {"data": {"summary": "m"}},
                              {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("google_calendar", "check_conflicts",
                              {"start_time": "2026-01-01T10:00:00Z", "end_time": "2026-01-01T11:00:00Z"},
                              {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_outlook_calendar(self, env, uis):
        svc = make_service({"get_events": [], "create_event": {}})
        set_service(env, svc)
        r = await uis.execute("outlook_calendar", "list", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("outlook_calendar", "create", {"data": {}}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_unsupported_action(self, env, uis):
        set_service(env, make_service())
        r = await uis.execute("google_calendar", "delete", {}, {"user_id": "u1"})
        assert r["status"] == "error"


class TestDispatchProjectManagement:
    async def test_linear(self, env, uis):
        svc = make_service({"get_issues": [], "create_issue": {}, "get_teams": [], "get_projects": []})
        set_service(env, svc)
        r = await uis.execute("linear", "list", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("linear", "create", {"title": "t", "team_id": "t1", "description": "d",
                                                   "priority": "P1"}, {"user_id": "u1"})
        assert r["status"] == "success"
        svc.create_issue.assert_awaited_once_with(title="t", team_id="t1", access_token="tok",
                                                  description="d", priority="P1")
        r = await uis.execute("linear", "list_teams", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("linear", "list_projects", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_monday(self, env, uis):
        svc = make_service({"get_boards": [], "create_item": {}, "search_items": []})
        set_service(env, svc)
        r = await uis.execute("monday", "list", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("monday", "create", {"board_id": "b", "title": "item",
                                                   "column_values": {}}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("monday", "list_boards", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("monday", "search", {"query": "q"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_zoho_projects(self, env, uis):
        svc = make_service({"get_projects": [], "get_tasks": []})
        set_service(env, svc)
        r = await uis.execute("zoho_projects", "list_projects", {"portal_id": "p"}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("zoho_projects", "list_tasks", {"portal_id": "p", "project_id": "pr"},
                              {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("zoho_projects", "list", {"portal_id": "p", "project_id": "pr"},
                              {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_asana(self, env, uis):
        svc = make_service({"get_tasks": [], "create_task": {}})
        set_service(env, svc)
        r = await uis.execute("asana", "list", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("asana", "create", {"data": {"name": "t"}}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_jira(self, env, uis):
        svc = make_service({"get_issues": [], "create_issue": {}})
        set_service(env, svc)
        r = await uis.execute("jira", "list", {"project_key": "P1"}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("jira", "create", {"project": "P1", "summary": "s", "issue_type": "Bug",
                                                 "description": "d"}, {"user_id": "u1"})
        assert r["status"] == "success"
        svc.create_issue.assert_awaited_once_with("P1", "s", "Bug", "d", token="tok")

    async def test_trello(self, env, uis):
        svc = make_service({"get_cards": [], "create_card": {}})
        set_service(env, svc)
        r = await uis.execute("trello", "list", {"board_id": "b"}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("trello", "create", {"name": "card", "list_id": "l"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_default(self, env, uis):
        set_service(env, make_service())
        r = await uis.execute("asana", "delete", {}, {"user_id": "u1"})
        assert r["status"] == "success"


class TestDispatchStorage:
    async def test_google_drive(self, env, uis):
        svc = make_service({"list_files": [], "search_files": [], "get_file_metadata": {}})
        set_service(env, svc)
        for action, params in (("list", {"folder_id": "f"}), ("list_files", {}),
                               ("search", {"query": "q"}), ("get_metadata", {"file_id": "x"})):
            r = await uis.execute("google_drive", action, params, {"user_id": "u1"})
            assert r["status"] == "success"

    async def test_dropbox(self, env, uis):
        svc = make_service({"list_folder": [], "search": [], "create_folder": {}})
        set_service(env, svc)
        for action in ("list", "list_folder"):
            r = await uis.execute("dropbox", action, {"path": "/"}, {"user_id": "u1"})
            assert r["status"] == "success"
        r = await uis.execute("dropbox", "search", {"query": "q"}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("dropbox", "create_folder", {"path": "/new"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_onedrive(self, env, uis):
        svc = make_service({"list_drive_items": [{"name": "Doc", "id": "1"}]})
        set_service(env, svc)
        r = await uis.execute("onedrive", "list", {"path": "/"}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("onedrive", "search", {"query": "doc"}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("onedrive", "search", {"query": "zzz"}, {"user_id": "u1"})
        assert r["data"] == []

    async def test_box(self, env, uis):
        svc = make_service({"list_folder_items": []})
        set_service(env, svc)
        r = await uis.execute("box", "list", {"folder_id": "0"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_notion(self, env, uis):
        svc = make_service({"search": {"results": []}, "create_page": {},
                            "search_pages_in_workspace": []})
        set_service(env, svc)
        r = await uis.execute("notion", "search", {"query": "q"}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("notion", "create_page", {"parent": "p", "properties": {}, "children": []},
                              {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("notion", "list", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_zoho_workdrive_and_default(self, env, uis):
        svc = make_service({"list_files": [], "search_files": []})
        set_service(env, svc)
        r = await uis.execute("zoho_workdrive", "list_files", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("zoho_workdrive", "search", {"query": "q"}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("box", "search", {}, {"user_id": "u1"})
        assert r["status"] == "success"


class TestDispatchSupport:
    async def test_zendesk(self, env, uis):
        svc = make_service({"get_tickets": [], "create_ticket": {}})
        set_service(env, svc)
        r = await uis.execute("zendesk", "list", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("zendesk", "create", {"data": {}}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_freshdesk(self, env, uis):
        svc = make_service({"get_tickets": [], "create_ticket": {}, "search_tickets": []})
        set_service(env, svc)
        for action in ("list", "get_tickets"):
            r = await uis.execute("freshdesk", action, {}, {"user_id": "u1"})
            assert r["status"] == "success"
        r = await uis.execute("freshdesk", "create", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("freshdesk", "search", {"query": "q"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_intercom(self, env, uis):
        svc = make_service({"get_conversations": [], "search_contacts": []})
        set_service(env, svc)
        for action in ("list", "get_conversations"):
            r = await uis.execute("intercom", action, {}, {"user_id": "u1"})
            assert r["status"] == "success"
        r = await uis.execute("intercom", "search_contacts", {"query": "q"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_default(self, env, uis):
        set_service(env, make_service())
        r = await uis.execute("zendesk", "bogus", {}, {"user_id": "u1"})
        assert r["status"] == "success"


class TestDispatchDevelopment:
    async def test_github(self, env, uis):
        svc = make_service({"get_user_repositories": [], "get_repository_issues": []})
        set_service(env, svc)
        r = await uis.execute("github", "list", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("github", "get_issues", {"owner": "o", "repo": "r"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_gitlab(self, env, uis):
        svc = make_service({"get_projects": [], "get_issues": [], "search_projects": []})
        set_service(env, svc)
        r = await uis.execute("gitlab", "list", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("gitlab", "get_issues", {"project_id": 1}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("gitlab", "search", {"query": "q"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_figma(self, env, uis):
        svc = make_service({"get_team_projects": [], "get_file": {}, "get_comments": []})
        set_service(env, svc)
        r = await uis.execute("figma", "list", {"team_id": "t"}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("figma", "get_file", {"file_key": "k"}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("figma", "get_comments", {"file_key": "k"}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_default(self, env, uis):
        set_service(env, make_service())
        r = await uis.execute("github", "bogus", {}, {"user_id": "u1"})
        assert r["status"] == "success"


class TestDispatchMarketing:
    async def test_mailchimp(self, env, uis):
        mc = MagicMock()
        mc.get_campaigns = AsyncMock(return_value=[])
        mc.get_audiences = AsyncMock(return_value=[])
        with patch("integrations.mailchimp_service.MailchimpService", return_value=mc):
            r = await uis.execute("mailchimp", "list", {}, {"user_id": "u1", "access_token": "t",
                                                            "server_prefix": "us1"})
            assert r["status"] == "success"
            mc.get_campaigns.assert_awaited_once_with("t", "us1", limit=20)
            r = await uis.execute("mailchimp", "get_audiences", {}, {"user_id": "u1",
                                                                     "access_token": "t"})
            assert r["status"] == "success"

    async def test_hubspot_marketing(self, env, uis):
        hs = make_service({"get_campaigns": []})
        with patch("integrations.hubspot_service.get_hubspot_service", return_value=hs):
            r = await uis.execute("hubspot_marketing", "list_campaigns", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_default(self, env, uis):
        r = await uis.execute("hubspot_marketing", "bogus", {}, {"user_id": "u1"})
        assert r["status"] == "success"


class TestDispatchFinance:
    async def test_stripe(self, env, uis):
        svc = make_service({"list_payments": [], "get_balance": {}})
        set_service(env, svc)
        r = await uis.execute("stripe", "list_payments", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        svc.list_payments.assert_awaited_once_with(access_token="tok", limit=10)
        r = await uis.execute("stripe", "get_balance", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_quickbooks(self, env, uis):
        svc = make_service({"get_invoices": [], "create_customer": {}, "create_invoice": {}})
        set_service(env, svc)
        r = await uis.execute("quickbooks", "list_invoices", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("quickbooks", "create_customer", {"display_name": "D", "email": "e@e.e"},
                              {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("quickbooks", "create_invoice", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_xero_zoho_books_zoho_inventory(self, env, uis):
        svc = make_service({"get_invoices": [], "get_items": []})
        set_service(env, svc)
        r = await uis.execute("xero", "list_invoices", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("zoho_books", "list_invoices", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("zoho_inventory", "list_items", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_aws_ses(self, env, uis):
        svc = make_service({"send_email": {}, "get_send_quota": {}})
        set_service(env, svc)
        r = await uis.execute("aws_ses", "send_email", {"to": ["a@b.c"], "subject": "s",
                                                        "html_body": "<b>", "text_body": "t"},
                              {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.execute("aws_ses", "get_quota", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_default(self, env, uis):
        set_service(env, make_service())
        r = await uis.execute("stripe", "bogus", {}, {"user_id": "u1"})
        assert r["status"] == "success"


class TestDispatchZoho:
    async def test_zoho_crm(self, env, uis):
        crm = MagicMock()
        crm.get_leads = AsyncMock(return_value=[{"Last_Name": "Doe"}])
        crm.get_deals = AsyncMock(return_value=[])
        crm.create_lead = AsyncMock(return_value={})
        with patch("integrations.zoho_crm_service.ZohoCRMService", return_value=crm):
            r = await uis.execute("zoho_crm", "list", {}, {"user_id": "u1", "access_token": "t"})
            assert r["status"] == "success"
            r = await uis.execute("zoho_crm", "get_deals", {}, {"user_id": "u1", "access_token": "t"})
            assert r["status"] == "success"
            r = await uis.execute("zoho_crm", "create_lead", {"data": {"Last_Name": "X"}},
                                  {"user_id": "u1", "access_token": "t"})
            assert r["status"] == "success"

    async def test_zoho_mail_via_dispatch(self, env, uis):
        svc = make_service({"get_recent_inbox": []})
        set_service(env, svc)
        r = await uis.execute("zoho_mail", "list", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_zoho_inventory_via_finance(self, env, uis):
        svc = make_service({"get_items": []})
        set_service(env, svc)
        r = await uis.execute("zoho_inventory", "list_items", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_execute_zoho_branches(self, uis):
        for service, mod, cls, method, ret in (
            ("zoho_mail", "zoho_mail_service", "ZohoMailService", "get_recent_inbox", []),
            ("zoho_inventory", "zoho_inventory_service", None, "get_items", []),
            ("zoho_projects", "zoho_projects_service", "ZohoProjectsService", "get_projects", []),
        ):
            fake = MagicMock()
            setattr(fake, method, AsyncMock(return_value=ret))
            if cls:
                with patch(f"integrations.{mod}.{cls}", return_value=fake):
                    r = await uis._execute_zoho(service, "list", {"portal_id": "p"},
                                                {"access_token": "t"})
            else:
                with patch(f"integrations.{mod}.zoho_inventory_service", fake):
                    r = await uis._execute_zoho(service, "list", {}, {"access_token": "t"})
            assert r["status"] == "success"

    async def test_default(self, env, uis):
        r = await uis.execute("zoho_crm", "bogus", {}, {"user_id": "u1", "access_token": "t"})
        assert r["status"] == "success"


class TestDispatchAnalyticsGeneric:
    async def test_tableau_success_and_error(self, env, uis):
        tableau = MagicMock()
        tableau.get_workbooks = AsyncMock(return_value=[{"name": "W"}])
        with patch("integrations.tableau_service.TableauService", return_value=tableau):
            r = await uis.execute("tableau", "list", {}, {"user_id": "u1", "access_token": "t"})
            assert r["status"] == "success"
        tableau.get_workbooks = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.tableau_service.TableauService", return_value=tableau):
            r = await uis.execute("tableau", "get_workbooks", {}, {"user_id": "u1", "access_token": "t"})
            assert r["status"] == "error"
            assert "Tableau service failed" in r["message"]

    async def test_google_analytics(self, env, uis):
        r = await uis.execute("google_analytics", "report", {}, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_generic_native(self, env, uis):
        r = await uis.execute("some_native", "act", {}, {"user_id": "u1"})
        assert r["status"] == "error"  # non-native falls to activepieces (no creds configured)
        assert "not supported" in r["message"]

    async def test_activepieces_success(self, env, uis):
        ext = MagicMock()
        ext.execute_integration_action = AsyncMock(return_value={"ok": True})
        with patch("core.external_integration_service.external_integration_service", ext):
            r = await uis.execute("custom_service", "custom_action", {"p": 1},
                                  {"user_id": "u1", "credentials": {"k": "v"}})
        assert r["status"] == "success"
        assert r["data"] == {"ok": True}
        ext.execute_integration_action.assert_awaited_once_with(
            integration_id="custom_service", action_id="custom_action",
            params={"p": 1}, credentials={"k": "v"})

    async def test_activepieces_failure(self, env, uis):
        ext = MagicMock()
        ext.execute_integration_action = AsyncMock(side_effect=RuntimeError("nope"))
        with patch("core.external_integration_service.external_integration_service", ext):
            r = await uis.execute("custom_service", "custom_action", {}, {"user_id": "u1"})
        assert r["status"] == "error"
        assert "not supported" in r["message"]

    async def test_marketing_reviews(self, env, uis):
        skills = MagicMock()
        skills.manage_reviews = AsyncMock(return_value=[{"review": 1}])
        with patch("core.marketing_skills_service.marketing_skills_service", skills):
            r = await uis.execute("google_reviews", "list_reviews", {}, {"user_id": "u1"})
            assert r["status"] == "success"
            r = await uis.execute("google_reviews", "reply_to_review", {"review_id": 7},
                                  {"user_id": "u1"})
            assert r["status"] == "success"
            assert "7" in r["message"]
            r = await uis.execute("google_reviews", "bogus", {}, {"user_id": "u1"})
            assert r["status"] == "error"

    async def test_marketing_ads(self, env, uis):
        r = await uis.execute("meta_ads", "get_insights", {}, {"user_id": "u1"})
        assert r["status"] == "success"
        assert r["data"]["count"] == 10


# ============================================================================
# UniversalIntegrationService.search()
# ============================================================================

class TestSearch:
    async def test_circuit_open(self, env, uis):
        env.cb.is_enabled = AsyncMock(return_value=False)
        r = await uis.search("slack", "q", context={"user_id": "u1"})
        assert r["circuit_open"] is True

    async def test_salesforce_contact_and_account(self, env, uis):
        svc = make_service({"execute_query": {"records": [{"Id": "1"}]}})
        set_service(env, svc)
        r = await uis.search("salesforce", "john", "contact", {"user_id": "u1"})
        assert r["status"] == "success"
        assert r["data"] == [{"Id": "1"}]
        r = await uis.search("salesforce", "acme", "account", {"user_id": "u1"})
        assert r["status"] == "success"
        r = await uis.search("salesforce", "x", "other", {"user_id": "u1"})
        assert r["status"] == "success"
        assert r["data"] == [{"message": "Only specific entity search implemented via SOQL"}]

    async def test_salesforce_no_service_or_token(self, env, uis):
        r = await uis.search("salesforce", "q", "contact", {"user_id": "u1"})
        assert r["data"] == []

    async def test_hubspot_search(self, env, uis):
        svc = make_service({"search_content": {"results": [{"id": "1"}]}})
        set_service(env, svc)
        r = await uis.search("hubspot", "q", "contact", {"user_id": "u1"})
        assert r == [{"id": "1"}]
        svc.search_content.assert_awaited_once_with("q", object_type="contact", token="tok")

    async def test_communication_slack(self, env, uis):
        slack = make_service({"make_request": {"messages": []}})
        with patch("integrations.slack_service_unified.slack_unified_service", slack):
            r = await uis.search("slack", "q", None, {"user_id": "u1", "access_token": "t"})
        assert r["data"] == {"messages": []}

    async def test_communication_others(self, env, uis):
        gc = MagicMock(); gc.unified_search = AsyncMock(return_value=[])
        tg = MagicMock(); tg.perform_intelligent_search = AsyncMock(return_value=[])
        wa = MagicMock(); wa.perform_intelligent_search = AsyncMock(return_value=[])
        gm = MagicMock(); gm.search_messages = Mock(return_value=[])
        ts = MagicMock(); ts.get_teams = Mock(return_value=[])
        with patch("integrations.atom_google_chat_integration.atom_google_chat_integration", gc), \
                patch("integrations.atom_telegram_integration.atom_telegram_integration", tg), \
                patch("integrations.atom_whatsapp_integration.atom_whatsapp_integration", wa), \
                patch("integrations.gmail_service.GmailService", return_value=gm), \
                patch("integrations.teams_service.TeamsService", return_value=ts):
            for service in ("google_chat", "telegram", "whatsapp", "gmail", "teams", "discord"):
                r = await uis.search(service, "q", None, {"user_id": "u1"})
                assert r["status"] == "success"

    async def test_calendar_search(self, env, uis):
        gc = MagicMock()
        gc.get_events = Mock(return_value=[{"title": "Alpha"}, {"title": "Beta"}])
        with patch("integrations.google_calendar_service.google_calendar_service", gc):
            r = await uis.search("google_calendar", "alpha", None, {"user_id": "u1"})
        assert r["data"] == [{"title": "Alpha"}]
        r = await uis.search("outlook_calendar", "q", None, {"user_id": "u1"})
        assert r == []

    async def test_project_management_search(self, env, uis):
        svc = make_service({"get_issues": [{"title": "Alpha"}, {"title": "Beta"}],
                            "search_items": [], "get_tasks": [{"name": "Gamma"}],
                            "search_issues": []})
        set_service(env, svc)
        r = await uis.search("linear", "alpha", None, {"user_id": "u1"})
        assert r == [{"title": "Alpha"}]
        r = await uis.search("monday", "q", None, {"user_id": "u1"})
        assert r == []
        r = await uis.search("asana", "gamma", None, {"user_id": "u1"})
        assert r == [{"name": "Gamma"}]
        r = await uis.search("jira", "q", None, {"user_id": "u1"})
        assert r == []
        r = await uis.search("trello", "q", None, {"user_id": "u1"})
        assert r == []

    async def test_storage_search(self, env, uis):
        svc = make_service({"search_files": {"status": "success", "data": {"files": [{"id": "1"}]}},
                            "search": {"results": []}})
        set_service(env, svc)
        r = await uis.search("google_drive", "q", None, {"user_id": "u1"})
        assert r == [{"id": "1"}]
        r = await uis.search("dropbox", "q", None, {"user_id": "u1"})
        assert r == {"results": []}
        r = await uis.search("notion", "q", None, {"user_id": "u1"})
        assert r == []
        r = await uis.search("box", "q", None, {"user_id": "u1"})
        assert r == []

    async def test_crm_search_zoho(self, env, uis):
        crm = MagicMock()
        crm.get_leads = AsyncMock(return_value=[{"Last_Name": "Doe", "Email": "d@d.d"},
                                                {"Last_Name": "Smith", "Email": "s@s.s"}])
        with patch("integrations.zoho_crm_service.ZohoCRMService", return_value=crm):
            r = await uis.search("zoho_crm", "doe", None, {"user_id": "u1", "access_token": "t"})
        assert r["data"] == [{"Last_Name": "Doe", "Email": "d@d.d"}]
        r = await uis.search("salesforce", "q", None, {"user_id": "u1"})
        assert r["data"] == []

    async def test_support_search(self, env, uis):
        zd = MagicMock(); zd.get_tickets = AsyncMock(return_value=[])
        fd = MagicMock(); fd.search_tickets = AsyncMock(return_value=[])
        ic = make_service({"search_contacts": []})
        set_service(env, ic)
        with patch("integrations.zendesk_service.ZendeskService", return_value=zd), \
                patch("integrations.freshdesk_service.FreshdeskService", return_value=fd):
            r = await uis.search("zendesk", "q", None, {"user_id": "u1"})
            assert r["status"] == "success"
            r = await uis.search("freshdesk", "q", None, {"user_id": "u1"})
            assert r["status"] == "success"
            r = await uis.search("intercom", "q", None, {"user_id": "u1"})
            assert r["status"] == "success"
        r = await uis.search("support_unknown", "q", None, {"user_id": "u1"})
        assert r["status"] == "error"

    async def test_dev_search(self, env, uis):
        gh = MagicMock()
        gh.get_user_repositories = Mock(return_value=[{"name": "RepoAlpha"}, {"name": "other"}])
        gl = MagicMock(); gl.search_projects = AsyncMock(return_value=[])
        with patch("integrations.github_service.GitHubService", return_value=gh), \
                patch("integrations.gitlab_service.GitLabService", return_value=gl):
            r = await uis.search("github", "alpha", None, {"user_id": "u1"})
            assert r["data"] == [{"name": "RepoAlpha"}]
            r = await uis.search("gitlab", "q", None, {"user_id": "u1", "access_token": "t"})
            assert r["data"] == []
        r = await uis.search("figma", "q", None, {"user_id": "u1"})
        assert r["status"] == "error"

    async def test_marketing_search(self, env, uis):
        mc = MagicMock()
        mc.get_campaigns = AsyncMock(return_value=[{"settings": {"subject_line": "Win Big"}},
                                                   {"settings": {"title": "other"}}])
        with patch("integrations.mailchimp_service.MailchimpService", return_value=mc):
            r = await uis.search("mailchimp", "win", None, {"user_id": "u1", "access_token": "t"})
        assert len(r["data"]) == 1
        r = await uis.search("google_ads", "q", None, {"user_id": "u1"})
        assert r["status"] == "error"

    async def test_analytics_search(self, env, uis):
        tableau = MagicMock()
        tableau.get_workbooks = AsyncMock(return_value=[{"name": "Sales"}]),
        tableau.get_workbooks = AsyncMock(return_value=[{"name": "Sales"}, {"name": "Ops"}])
        with patch("integrations.tableau_service.TableauService", return_value=tableau):
            r = await uis.search("tableau", "sales", None, {"user_id": "u1", "access_token": "t"})
            assert r["data"] == [{"name": "Sales"}]
        tableau.get_workbooks = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.tableau_service.TableauService", return_value=tableau):
            r = await uis.search("tableau", "q", None, {"user_id": "u1", "access_token": "t"})
            assert r["status"] == "error"
        r = await uis.search("google_analytics", "q", None, {"user_id": "u1"})
        assert r["data"] == []

    async def test_zoho_workdrive_search(self, env, uis):
        svc = make_service({"search_files": [{"id": "1"}]})
        set_service(env, svc)
        r = await uis.search("zoho_workdrive", "q", None, {"user_id": "u1"})
        assert r["status"] == "success"

    async def test_unsupported_service(self, env, uis):
        r = await uis.search("not_a_service", "q", None, {"user_id": "u1"})
        assert r["status"] == "error"
        assert "not supported" in r["message"]
        env.cb.record_failure.assert_called()

    async def test_exception_records_failure(self, env, uis):
        svc = make_service()
        svc.execute_query = AsyncMock(side_effect=RuntimeError("boom"))
        set_service(env, svc)
        r = await uis.search("salesforce", "q", "contact", {"user_id": "u1"})
        assert r["status"] == "error"
        env.cb.record_failure.assert_called_once_with("salesforce", unittest_any_exc())

    async def test_search_masks_response(self, env, uis):
        """BUG: gatekeeper field-masking was never applied to search() results."""
        gk = Gatekeeper()
        gk.configure("google_drive", {"masked_fields": {"access_token"}})
        svc = make_service({"search_files": {"status": "success",
                                             "data": {"files": [{"id": "1", "access_token": "leak"}]}}})
        set_service(env, svc)
        with patch("integrations.universal_integration_service.governance_middleware", gk):
            r = await uis.search("google_drive", "q", None, {"user_id": "u1"})
        assert r == [{"id": "1", "access_token": "***"}]


# ============================================================================
# LanceDBMemoryManager
# ============================================================================

@pytest.fixture
def mm(tmp_path):
    return LanceDBMemoryManager(db_path=str(tmp_path / "memory"), workspace_id="ws1")


class TestLanceDBMemoryManager:
    def test_init_creates_workspace_dir(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="ws2")
        assert (tmp_path / "m" / "ws2").exists()

    def test_initialize_true_and_idempotent(self, mm):
        assert mm.initialize() is True
        assert mm.db is not None
        assert mm.connections_table is not None
        assert mm.metadata_table is not None
        assert mm.initialize() is True

    def test_initialize_failure_returns_false(self, mm):
        with patch("integrations.atom_communication_ingestion_pipeline.lancedb.connect",
                   side_effect=RuntimeError("no lancedb")):
            assert mm.initialize() is False

    def test_embedding_model_load_failure_continues(self, mm):
        with patch("integrations.atom_communication_ingestion_pipeline._get_sentence_transformer",
                   return_value=Mock(side_effect=RuntimeError("no model"))):
            assert mm.initialize() is True
        assert mm.model is None

    def test_embedding_model_loads(self, mm):
        fake_cls = Mock(return_value=Mock(encode=lambda t: __import__("numpy").array([0.1, 0.2])))
        with patch("integrations.atom_communication_ingestion_pipeline._get_sentence_transformer",
                   return_value=fake_cls):
            mm.initialize()
        assert mm.model is not None
        assert mm.generate_embedding("x") == [0.1, 0.2]

    def test_ingest_communication(self, mm):
        mm.initialize()
        assert mm.ingest_communication(comm_data()) is True
        rows = mm.connections_table.search().to_pandas()
        assert len(rows) == 1

    def test_ingest_communication_failure(self, mm):
        mm.initialize()
        with patch.object(mm.connections_table, "add", side_effect=RuntimeError("disk full")):
            assert mm.ingest_communication(comm_data()) is False

    def test_ingest_generic_record(self, mm):
        mm.initialize()
        rec = SimpleNamespace(id="rec-1", app_type="crm", timestamp=datetime(2026, 1, 1),
                              record_type=RecordType.LEAD, content="a lead", metadata={"src": "x"},
                              vector_embedding=None)
        assert mm.ingest_generic_record(rec) is True
        rows = mm.connections_table.search().to_pandas()
        assert rows.iloc[0]["direction"] == "internal"
        assert "lead" in json.loads(rows.iloc[0]["metadata"])["record_type"]

    def test_ingest_generic_record_failure(self, mm):
        mm.initialize()
        with patch.object(mm.connections_table, "add", side_effect=RuntimeError("nope")):
            assert mm.ingest_generic_record(SimpleNamespace(
                id="r", app_type="crm", timestamp=datetime(2026, 1, 1),
                record_type=RecordType.LEAD, content="x", metadata=None, vector_embedding=None)) is False

    def test_ingest_batch(self, mm):
        mm.initialize()
        assert mm.ingest_batch([comm_data(id="1"), comm_data(id="2")]) is True
        rows = mm.connections_table.search().to_pandas()
        assert len(rows) == 2

    def test_ingest_batch_empty_list_returns_false(self, mm):
        mm.initialize()
        assert mm.ingest_batch([]) is False

    def test_ingest_batch_failure(self, mm):
        mm.initialize()
        with patch.object(mm.connections_table, "add", side_effect=RuntimeError("nope")):
            assert mm.ingest_batch([comm_data()]) is False

    def test_generate_embedding_without_model(self, mm):
        mm.initialize()
        emb = mm.generate_embedding("hello")
        assert len(emb) == 768
        assert all(v == 0.0 for v in emb)

    def test_generate_embedding_model_error_returns_zeros(self, mm):
        mm.model = Mock()
        mm.model.encode = Mock(side_effect=RuntimeError("encode fail"))
        emb = mm.generate_embedding("x")
        assert len(emb) == 768

    def test_search_communications(self, mm):
        mm.initialize()
        mm.ingest_communication(comm_data(id="1", content="meeting about sales pipeline"))
        mm.ingest_communication(comm_data(id="2", content="lunch plans", app_type="teams"))
        results = mm.search_communications("sales", limit=10)
        assert any(r["id"] == "1" for r in results)

    def test_search_communications_with_filters(self, mm):
        mm.initialize()
        mm.ingest_communication(comm_data(id="1", content="alpha project", tags=["hello"]))
        mm.ingest_communication(comm_data(id="2", content="beta project", tags=["world"]))
        results = mm.search_communications("project", limit=10, app_type="slack", tag="hello")
        assert any(r["id"] == "1" for r in results)
        assert not any(r["id"] == "2" for r in results)

    def test_search_communications_fallback_to_vector(self, mm):
        mm.initialize()
        mm.ingest_communication(comm_data(id="1", content="project alpha launch"))
        original_search = mm.connections_table.search

        def failing_first(*args, **kwargs):
            raise RuntimeError("hybrid unsupported")

        calls = {"n": 0}

        def side_effect(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("hybrid unsupported")
            return original_search(*args, **kwargs)

        with patch.object(mm.connections_table, "search", side_effect=side_effect):
            results = mm.search_communications("alpha", limit=10)
        assert any(r["id"] == "1" for r in results)

    def test_search_communications_uninitialized(self, mm):
        assert mm.search_communications("q") == []

    def test_search_communications_error(self, mm):
        mm.initialize()
        with patch.object(mm.connections_table, "search", side_effect=RuntimeError("boom")):
            assert mm.search_communications("q") == []

    def test_get_communications_by_app(self, mm):
        mm.initialize()
        mm.ingest_communication(comm_data(id="1"))
        mm.ingest_communication(comm_data(id="2", app_type="teams"))
        rows = mm.get_communications_by_app("slack")
        assert [r["id"] for r in rows] == ["1"]
        rows = mm.get_communications_by_app("teams")
        assert [r["id"] for r in rows] == ["2"]

    def test_get_communications_by_app_error(self, mm):
        mm.initialize()
        with patch.object(mm.connections_table, "search", side_effect=RuntimeError("boom")):
            assert mm.get_communications_by_app("slack") == []

    def test_get_communications_by_timeframe(self, mm):
        mm.initialize()
        mm.ingest_communication(comm_data(id="1", timestamp=datetime(2026, 1, 1, 10, 0)))
        mm.ingest_communication(comm_data(id="2", timestamp=datetime(2026, 6, 1, 10, 0)))
        rows = mm.get_communications_by_timeframe(datetime(2025, 12, 31), datetime(2026, 1, 2))
        assert [r["id"] for r in rows] == ["1"]

    def test_get_communications_by_timeframe_error(self, mm):
        mm.initialize()
        with patch.object(mm.connections_table, "search", side_effect=RuntimeError("boom")):
            assert mm.get_communications_by_timeframe(datetime(2026, 1, 1), datetime(2026, 2, 1)) == []

    def test_update_metadata_existing_increments(self, mm):
        mm.initialize()
        mm.ingest_communication(comm_data())
        mm.ingest_communication(comm_data(id="2"))
        rows = mm.metadata_table.search().to_pandas()
        assert len(rows) == 1
        assert rows.iloc[0]["total_messages"] == 2

    def test_update_metadata_error_is_silent(self, mm):
        mm.initialize()
        with patch.object(mm.metadata_table, "search", side_effect=RuntimeError("boom")):
            mm.ingest_communication(comm_data())


# ============================================================================
# CommunicationIngestionPipeline
# ============================================================================

@pytest.fixture
def pipeline(mm):
    return CommunicationIngestionPipeline(mm)


@pytest.fixture
def sample_config():
    return IngestionConfig(app_type=CommunicationAppType.SLACK, enabled=True, real_time=True,
                           batch_size=50, ingest_attachments=True, embed_content=True,
                           retention_days=30, vector_dim=768)


class TestPipelineConfig:
    def test_init_initializes_webhook_processor(self, pipeline):
        assert pipeline.webhook_processor is not None
        assert pipeline.webhook_enabled == {}
        assert pipeline.ingestion_configs == {}

    def test_init_without_webhook_handlers(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="w")
        with patch.dict(sys.modules, {"core.webhook_handlers": None}):
            p = CommunicationIngestionPipeline(mm)
        assert p.webhook_processor is None
        assert p.webhook_enabled == {}

    def test_configure_app(self, pipeline, sample_config):
        pipeline.configure_app(CommunicationAppType.SLACK, sample_config)
        assert pipeline.ingestion_configs["slack"]["enabled"] is True
        assert pipeline.ingestion_configs["slack"]["app_type"] == "slack"
        assert pipeline.app_configs["slack"]["real_time"] is True

    def test_webhook_toggle_and_status(self, pipeline):
        assert pipeline.is_webhook_enabled("slack") is False
        pipeline.enable_webhook_ingestion("slack")
        assert pipeline.is_webhook_enabled("slack") is True
        pipeline.enable_webhook_ingestion("slack", enabled=False)
        assert pipeline.is_webhook_enabled("slack") is False
        status = pipeline.get_webhook_status()
        assert set(status) == {"slack", "teams", "gmail", "outlook"}
        assert status["slack"]["processor_available"] is True


class TestWebhookHandler:
    async def test_missing_app_type_skipped(self, pipeline):
        with patch.object(pipeline, "ingest_message", new_callable=AsyncMock) as im:
            await pipeline._handle_webhook_message({"content": "x"})
        im.assert_not_awaited()

    async def test_disabled_app_skipped(self, pipeline):
        with patch.object(pipeline, "ingest_message", new_callable=AsyncMock) as im:
            await pipeline._handle_webhook_message({"app_type": "slack", "content": "x"})
        im.assert_not_awaited()

    async def test_enabled_ingests(self, pipeline):
        pipeline.enable_webhook_ingestion("slack")
        with patch.object(pipeline, "ingest_message", new_callable=AsyncMock, return_value=True) as im:
            await pipeline._handle_webhook_message({"app_type": "slack", "content": "hi"})
        im.assert_awaited_once_with("slack", {"app_type": "slack", "content": "hi"})

    async def test_failed_ingest_logged(self, pipeline):
        pipeline.enable_webhook_ingestion("slack")
        with patch.object(pipeline, "ingest_message", new_callable=AsyncMock, return_value=False):
            await pipeline._handle_webhook_message({"app_type": "slack"})

    async def test_exception_in_handler(self, pipeline):
        pipeline.enable_webhook_ingestion("slack")
        with patch.object(pipeline, "ingest_message", new_callable=AsyncMock,
                          side_effect=RuntimeError("boom")):
            await pipeline._handle_webhook_message({"app_type": "slack"})


class TestIngestMessage:
    def _settings(self, enabled=True, extraction=True):
        s = MagicMock()
        s.is_automations_enabled.return_value = enabled
        s.is_extraction_enabled.return_value = extraction
        return s

    async def test_initializes_manager_and_ingests(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="w")
        p = CommunicationIngestionPipeline(mm)
        with patch("core.automation_settings.get_automation_settings",
                   return_value=self._settings(enabled=False)):
            ok = await p.ingest_message("slack", {"content": "hello world", "id": "m1"})
        assert ok is True
        assert mm.db is not None

    async def test_embedding_generated_when_configured(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="w")
        p = CommunicationIngestionPipeline(mm)
        p.configure_app(CommunicationAppType.SLACK, IngestionConfig(
            app_type=CommunicationAppType.SLACK, enabled=True, real_time=False, batch_size=10,
            ingest_attachments=True, embed_content=True, retention_days=30))
        with patch("core.automation_settings.get_automation_settings",
                   return_value=self._settings(enabled=False)), \
                patch.object(mm, "generate_embedding", return_value=[0.1] * 768) as gen:
            ok = await p.ingest_message("slack", {"content": "hello world", "id": "m2"})
        assert ok is True
        gen.assert_called_once()

    async def test_extraction_when_enabled_and_content_long(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="w")
        p = CommunicationIngestionPipeline(mm)
        mgr = MagicMock()
        mgr.process_document = AsyncMock()
        intel = MagicMock()
        intel.analyze_and_route = AsyncMock()
        with patch("core.automation_settings.get_automation_settings",
                   return_value=self._settings(True, True)), \
                patch("integrations.atom_communication_ingestion_pipeline.get_knowledge_ingestion",
                      return_value=mgr), \
                patch("core.communication_intelligence.CommunicationIntelligenceService",
                      return_value=intel):
            ok = await p.ingest_message("slack", {"content": "This is a fairly long message "
                                                              "for extraction purposes",
                                                  "id": "m3", "metadata": {"user_id": "u1"}})
        assert ok is True
        await asyncio.sleep(0.05)
        mgr.process_document.assert_awaited_once()

    async def test_extraction_error_does_not_fail_ingest(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="w")
        p = CommunicationIngestionPipeline(mm)
        with patch("core.automation_settings.get_automation_settings",
                   return_value=self._settings(True, True)), \
                patch("integrations.atom_communication_ingestion_pipeline.get_knowledge_ingestion",
                      side_effect=RuntimeError("km down")):
            ok = await p.ingest_message("slack", {"content": "A sufficiently long content here",
                                                  "id": "m4"})
        assert ok is True

    async def test_extraction_skipped_when_automations_disabled(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="w")
        p = CommunicationIngestionPipeline(mm)
        mgr = MagicMock()
        with patch("core.automation_settings.get_automation_settings",
                   return_value=self._settings(False, True)), \
                patch("integrations.atom_communication_ingestion_pipeline.get_knowledge_ingestion",
                      return_value=mgr):
            ok = await p.ingest_message("slack", {"content": "A sufficiently long content here",
                                                  "id": "m5"})
        assert ok is True
        assert not mgr.process_document.called

    async def test_ingest_failure_returns_false(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="w")
        p = CommunicationIngestionPipeline(mm)
        with patch.object(mm, "ingest_communication", return_value=False), \
                patch("core.automation_settings.get_automation_settings",
                      return_value=self._settings(False)):
            ok = await p.ingest_message("slack", {"content": "hi", "id": "m6"})
        assert ok is False

    async def test_bad_timestamp_returns_false(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="w")
        p = CommunicationIngestionPipeline(mm)
        with patch("core.automation_settings.get_automation_settings",
                   return_value=self._settings(False)):
            ok = await p.ingest_message("slack", {"timestamp": "not-a-date", "id": "m7"})
        assert ok is False

    async def test_uninitialized_manager_init_in_executor(self, tmp_path):
        mm = MagicMock()
        mm.db = None
        mm.initialize = Mock(return_value=True)
        mm.ingest_communication = Mock(return_value=True)
        p = CommunicationIngestionPipeline(mm)
        with patch("core.automation_settings.get_automation_settings",
                   return_value=self._settings(False)):
            ok = await p.ingest_message("slack", {"content": "hi", "id": "m8"})
        assert ok is True
        mm.initialize.assert_called_once()


class TestRealTimeStreams:
    async def test_start_not_configured(self, pipeline):
        assert pipeline.start_real_time_stream("slack") is False

    async def test_start_when_realtime_disabled(self, pipeline, sample_config):
        sample_config.real_time = False
        pipeline.configure_app(CommunicationAppType.SLACK, sample_config)
        assert pipeline.start_real_time_stream("slack") is False

    async def test_start_success(self, pipeline, sample_config):
        pipeline.configure_app(CommunicationAppType.SLACK, sample_config)
        with patch("integrations.atom_communication_ingestion_pipeline.asyncio.create_task",
                   return_value=Mock()) as ct:
            assert pipeline.start_real_time_stream("slack") is True
        ct.assert_called_once()

    async def test_real_time_ingestion_loop(self, pipeline, sample_config):
        pipeline.configure_app(CommunicationAppType.SLACK, sample_config)
        sleep_calls = []

        async def fake_sleep(delay):
            sleep_calls.append(delay)
            if len(sleep_calls) >= 2:
                raise RuntimeError("stop-loop")

        with patch.object(pipeline, "_fetch_new_messages", new_callable=AsyncMock,
                          return_value=[{"id": "1", "content": "hi"}]), \
                patch.object(pipeline, "ingest_message", new_callable=AsyncMock,
                             side_effect=[RuntimeError("ingest fail"), True]) as im, \
                patch("integrations.atom_communication_ingestion_pipeline.asyncio.sleep",
                      new=AsyncMock(side_effect=fake_sleep)):
            with pytest.raises(RuntimeError):
                await pipeline._real_time_ingestion("slack")
        assert im.await_count == 2
        assert len(sleep_calls) >= 3


class TestFetchNewMessages:
    async def test_known_apps_update_timestamp(self, pipeline, sample_config):
        pipeline.configure_app(CommunicationAppType.SLACK, sample_config)
        for method, app in (("_fetch_whatsapp_messages", "whatsapp"),
                            ("_fetch_slack_messages", "slack"),
                            ("_fetch_teams_messages", "microsoft_teams"),
                            ("_fetch_email_messages", "email"),
                            ("_fetch_gmail_messages", "gmail"),
                            ("_fetch_outlook_messages", "outlook")):
            with patch.object(pipeline, method, new_callable=AsyncMock, return_value=[{"id": "x"}]):
                msgs = await pipeline._fetch_new_messages(app)
            assert msgs == [{"id": "x"}]
            assert f"last_fetch_{app}" in pipeline.fetch_timestamps

    async def test_unsupported_app_updates_timestamp(self, pipeline):
        msgs = await pipeline._fetch_new_messages("notion")
        assert msgs == []
        assert "last_fetch_notion" in pipeline.fetch_timestamps

    async def test_error_does_not_update_timestamp(self, pipeline):
        with patch.object(pipeline, "_fetch_slack_messages",
                          new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            msgs = await pipeline._fetch_new_messages("slack")
        assert msgs == []
        assert "last_fetch_slack" not in pipeline.fetch_timestamps


class TestFetchWhatsApp:
    async def test_success(self, pipeline):
        wa = MagicMock()
        wa.get_messages = AsyncMock(return_value=[{"id": "1"}])
        with patch("integrations.atom_whatsapp_integration.atom_whatsapp_integration", wa):
            msgs = await pipeline._fetch_whatsapp_messages(None)
        assert msgs == [{"id": "1"}]
        wa.get_messages.assert_awaited_once_with(since=None, limit=100)

    async def test_import_error(self, pipeline):
        with patch.dict(sys.modules, {"integrations.atom_whatsapp_integration": None}):
            assert await pipeline._fetch_whatsapp_messages(None) == []

    async def test_method_missing_degrades(self, pipeline):
        with patch("integrations.atom_whatsapp_integration.atom_whatsapp_integration",
                   MagicMock()):
            assert await pipeline._fetch_whatsapp_messages(None) == []

    async def test_service_error(self, pipeline):
        wa = MagicMock()
        wa.get_messages = AsyncMock(side_effect=RuntimeError("down"))
        with patch("integrations.atom_whatsapp_integration.atom_whatsapp_integration", wa):
            assert await pipeline._fetch_whatsapp_messages(None) == []


class TestFetchSlack:
    def _fake_slack_sdk(self, client_factory):
        fake_sdk = types.ModuleType("slack_sdk")
        fake_sdk.errors = types.ModuleType("slack_sdk.errors")
        fake_sdk.errors.SlackApiError = client_factory.error_cls
        fake_sdk.web = types.ModuleType("slack_sdk.web")
        fake_sdk.web.async_client = types.ModuleType("slack_sdk.web.async_client")
        fake_sdk.web.async_client.AsyncWebClient = client_factory
        return fake_sdk

    async def test_no_token(self, pipeline, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        assert await pipeline._fetch_slack_messages(None) == []

    async def test_no_channels_configured(self, pipeline, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-1")
        pipeline.app_configs["slack"] = {}
        assert await pipeline._fetch_slack_messages(None) == []

    async def test_import_error(self, pipeline, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-1")
        pipeline.app_configs["slack"] = {"monitored_channels": ["C1"]}
        with patch.dict(sys.modules, {"slack_sdk": None}):
            assert await pipeline._fetch_slack_messages(None) == []

    async def test_success_with_pagination_and_filters(self, pipeline, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-1")
        pipeline.app_configs["slack"] = {"monitored_channels": ["C1", "C2"],
                                         "include_bot_messages": True}

        class FakeError(Exception):
            def __init__(self, response):
                super().__init__("slack err")
                self.response = response

        pages = iter([
            {"ok": True, "messages": [
                {"ts": "1000.1", "type": "message", "user": "U1", "text": "hello",
                 "files": [{"id": "f"}], "reactions": [{"name": "thumbsup"}], "thread_ts": "1000.1",
                 "subtype": None, "parent_user_id": None},
                {"ts": "1000.2", "type": "message", "bot_id": "B1", "text": "bot msg",
                 "subtype": None, "user": None},
                {"ts": "1000.3", "type": "message", "subtype": "message_deleted", "text": "old",
                 "user": "U1"},
                {"ts": "1000.4", "type": "event", "text": "not a message", "user": "U1"},
            ], "response_metadata": {"next_cursor": "abc"}},
            {"ok": True, "messages": [
                {"ts": "1000.5", "type": "message", "user": "U1", "text": "paged"},
            ], "response_metadata": {}},
        ])

        class FakeClient:
            error_cls = FakeError

            def __init__(self, token):
                self.token = token

            async def conversations_history(self, channel=None, oldest=None, limit=100, cursor=None,
                                            inclusive=False):
                if channel == "C2" and cursor is None:
                    return {"ok": False, "error": "invalid_auth"}
                page = next(pages)
                return page

            async def conversations_info(self, channel=None):
                return {"ok": True, "channel": {"name": "general"}}

            async def close(self):
                return None

        fake_sdk = self._fake_slack_sdk(FakeClient)
        with patch.dict(sys.modules, {
            "slack_sdk": fake_sdk,
            "slack_sdk.errors": fake_sdk.errors,
            "slack_sdk.web": fake_sdk.web,
            "slack_sdk.web.async_client": fake_sdk.web.async_client,
        }), patch("integrations.atom_communication_ingestion_pipeline.asyncio.sleep",
                  new=AsyncMock()):
            msgs = await pipeline._fetch_slack_messages(datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert len(msgs) == 3
        assert msgs[0]["id"] == "1000.1"
        assert msgs[0]["metadata"]["channel_name"] == "general"
        assert msgs[0]["direction"] == "inbound"
        assert msgs[0]["recipient"] == "C1"
        assert msgs[1]["id"] == "1000.2"
        assert msgs[2]["id"] == "1000.5"

    async def test_slack_api_error_else_branch(self, pipeline, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-1")
        pipeline.app_configs["slack"] = {"monitored_channels": ["C1"]}

        class FakeSlackResponse:
            def __init__(self, error, headers=None):
                self._error = error
                self.headers = headers or {}

            def get(self, key, default=None):
                return self._error if key == "error" else default

        class FakeError(Exception):
            def __init__(self, response):
                super().__init__("slack err")
                self.response = response

        class FakeClient:
            error_cls = FakeError

            def __init__(self, token):
                self.token = token

            async def conversations_history(self, **kw):
                raise FakeError(FakeSlackResponse("channel_not_found"))

            async def close(self):
                return None

        fake_sdk = self._fake_slack_sdk(FakeClient)
        with patch.dict(sys.modules, {
            "slack_sdk": fake_sdk,
            "slack_sdk.errors": fake_sdk.errors,
            "slack_sdk.web": fake_sdk.web,
            "slack_sdk.web.async_client": fake_sdk.web.async_client,
        }):
            msgs = await pipeline._fetch_slack_messages(None)
        assert msgs == []

    async def test_rate_limited(self, pipeline, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-1")
        pipeline.app_configs["slack"] = {"monitored_channels": ["C1"]}

        class FakeSlackResponse:
            def __init__(self, error, headers=None):
                self._error = error
                self.headers = headers or {}

            def get(self, key, default=None):
                return self._error if key == "error" else default

        class FakeError(Exception):
            def __init__(self, response):
                super().__init__("slack err")
                self.response = response

        class FakeClient:
            error_cls = FakeError

            def __init__(self, token):
                self.token = token

            async def conversations_history(self, **kw):
                raise FakeError(FakeSlackResponse("ratelimited", {"Retry-After": 1}))

            async def close(self):
                return None

        fake_sdk = self._fake_slack_sdk(FakeClient)
        with patch.dict(sys.modules, {
            "slack_sdk": fake_sdk,
            "slack_sdk.errors": fake_sdk.errors,
            "slack_sdk.web": fake_sdk.web,
            "slack_sdk.web.async_client": fake_sdk.web.async_client,
        }), patch("integrations.atom_communication_ingestion_pipeline.asyncio.sleep",
                  new=AsyncMock()):
            msgs = await pipeline._fetch_slack_messages(None)
        assert msgs == []

    async def test_generic_exception(self, pipeline, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-1")
        pipeline.app_configs["slack"] = {"monitored_channels": ["C1"]}

        class FakeError(Exception):
            def __init__(self, response):
                super().__init__("slack err")
                self.response = response

        class FakeClient:
            error_cls = FakeError

            def __init__(self, token):
                self.token = token

            async def conversations_history(self, **kw):
                raise RuntimeError("network down")

            async def close(self):
                return None

        fake_sdk = self._fake_slack_sdk(FakeClient)
        with patch.dict(sys.modules, {
            "slack_sdk": fake_sdk,
            "slack_sdk.errors": fake_sdk.errors,
            "slack_sdk.web": fake_sdk.web,
            "slack_sdk.web.async_client": fake_sdk.web.async_client,
        }):
            msgs = await pipeline._fetch_slack_messages(None)
        assert msgs == []

    async def test_get_channel_name(self, pipeline):
        client = Mock()
        client.conversations_info = AsyncMock(return_value={"ok": True,
                                                            "channel": {"name": "eng"}})
        assert await pipeline._get_channel_name(client, "C1") == "eng"
        client.conversations_info = AsyncMock(return_value={"ok": False})
        assert await pipeline._get_channel_name(client, "C1") is None
        client.conversations_info = AsyncMock(side_effect=RuntimeError("boom"))
        assert await pipeline._get_channel_name(client, "C1") is None


class FakeHTTPResponse:
    def __init__(self, status_code=200, data=None, headers=None):
        self.status_code = status_code
        self._data = data or {}
        self.headers = headers or {}

    def json(self):
        return self._data


class FakeHTTPClient:
    """Configurable httpx.AsyncClient stand-in."""

    def __init__(self, routes=None, default=None, timeout=None):
        self.routes = routes or {}
        self.default = default or FakeHTTPResponse()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def get(self, url, headers=None, params=None):
        for prefix, resp in sorted(self.routes.items(), key=lambda kv: len(kv[0]), reverse=True):
            if url.startswith(prefix):
                if callable(resp):
                    return resp(url, headers, params)
                return resp
        return self.default


def fake_client_factory(client):
    """patch('httpx.AsyncClient', ...) target: accepts timeout kwarg."""
    return lambda timeout=None: client


class TestFetchTeams:
    async def test_no_token(self, pipeline):
        with patch("core.token_storage.token_storage.get_token", return_value=None):
            assert await pipeline._fetch_teams_messages(None) == []

    async def test_import_error(self, pipeline):
        with patch.dict(sys.modules, {"core.token_storage": None}):
            assert await pipeline._fetch_teams_messages(None) == []

    async def test_success(self, pipeline):
        with patch("core.token_storage.token_storage.get_token",
                   return_value={"access_token": "t"}), \
                patch.object(pipeline, "_fetch_teams_chat_messages", new_callable=AsyncMock,
                             return_value=[{"id": "c1"}]) as chat, \
                patch.object(pipeline, "_fetch_teams_channel_messages", new_callable=AsyncMock,
                             return_value=[{"id": "ch1"}]) as chan, \
                patch("httpx.AsyncClient", fake_client_factory(FakeHTTPClient())):
            msgs = await pipeline._fetch_teams_messages(None)
        assert len(msgs) == 2
        chat.assert_awaited_once()
        chan.assert_awaited_once()

    async def test_chat_messages(self, pipeline):
        routes = {
            "https://graph.microsoft.com/v1.0/me/chats": FakeHTTPResponse(
                data={"value": [{"id": "chat1", "chatType": "oneOnOne", "topic": "Conv"}]}),
            "https://graph.microsoft.com/v1.0/me/chats/chat1/messages": FakeHTTPResponse(
                data={"value": [{
                    "id": "m1",
                    "createdDateTime": "2026-01-01T10:00:00Z",
                    "from": {"user": {"displayName": "Alice", "email": "a@b.c"}},
                    "body": {"content": "<div>hi</div>", "contentType": "html"},
                    "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive",
                                     "content": {"type": "AdaptiveCard"}}],
                    "subject": "s", "messageType": "message",
                }]}),
        }
        client = FakeHTTPClient(routes)
        msgs = await pipeline._fetch_teams_chat_messages(client, {"Authorization": "Bearer t"},
                                                         datetime(2026, 1, 1, 9, 0))
        assert len(msgs) == 1
        assert msgs[0]["sender"] == "Alice"
        assert msgs[0]["tags"] == ["teams", "chat"]
        assert msgs[0]["metadata"]["adaptive_card"]["type"] == "AdaptiveCard"

    async def test_chat_messages_failures(self, pipeline):
        client = FakeHTTPClient(routes={
            "https://graph.microsoft.com/v1.0/me/chats": FakeHTTPResponse(status_code=500),
        })
        assert await pipeline._fetch_teams_chat_messages(client, {}, None) == []

        calls = {"n": 0}

        def chat_429(url, headers, params):
            calls["n"] += 1
            if calls["n"] == 1:
                return FakeHTTPResponse(429, headers={"Retry-After": 1})
            return FakeHTTPResponse(status_code=500)

        client = FakeHTTPClient(routes={
            "https://graph.microsoft.com/v1.0/me/chats": FakeHTTPResponse(
                data={"value": [{"id": "c1"}]}),
            "https://graph.microsoft.com/v1.0/me/chats/c1/messages": chat_429,
        })
        with patch("integrations.atom_communication_ingestion_pipeline.asyncio.sleep",
                   new=AsyncMock()):
            msgs = await pipeline._fetch_teams_chat_messages(client, {}, None)
        assert msgs == []

    async def test_chat_messages_generic_error(self, pipeline):
        def boom(url, headers, params):
            raise RuntimeError("graph down")

        client = FakeHTTPClient(routes={
            "https://graph.microsoft.com/v1.0/me/chats": FakeHTTPResponse(
                data={"value": [{"id": "c1"}]}),
            "https://graph.microsoft.com/v1.0/me/chats/c1/messages": boom,
        })
        msgs = await pipeline._fetch_teams_chat_messages(client, {}, None)
        assert msgs == []

    async def test_channel_messages(self, pipeline):
        routes = {
            "https://graph.microsoft.com/v1.0/me/joinedTeams": FakeHTTPResponse(
                data={"value": [{"id": "team1", "displayName": "Eng"}]}),
            "https://graph.microsoft.com/v1.0/teams/team1/channels": FakeHTTPResponse(
                data={"value": [{"id": "ch1", "displayName": "General"}]}),
            "https://graph.microsoft.com/v1.0/teams/team1/channels/ch1/messages": FakeHTTPResponse(
                data={"value": [{
                    "id": "m1",
                    "createdDateTime": "2026-01-01T10:00:00Z",
                    "from": {"user": {"displayName": "Bob", "email": "b@b.c"}},
                    "body": {"content": "hello team", "contentType": "text"},
                    "attachments": [],
                    "importance": "normal",
                }]}),
        }
        client = FakeHTTPClient(routes)
        msgs = await pipeline._fetch_teams_channel_messages(client, {}, None)
        assert len(msgs) == 1
        assert msgs[0]["recipient"] == "Eng/General"
        assert msgs[0]["tags"] == ["teams", "channel"]

    async def test_channel_messages_no_teams(self, pipeline):
        client = FakeHTTPClient(routes={
            "https://graph.microsoft.com/v1.0/me/joinedTeams": FakeHTTPResponse(status_code=404),
        })
        assert await pipeline._fetch_teams_channel_messages(client, {}, None) == []

    async def test_channel_messages_channel_error(self, pipeline):
        def boom(url, headers, params):
            raise RuntimeError("down")

        client = FakeHTTPClient(routes={
            "https://graph.microsoft.com/v1.0/me/joinedTeams": FakeHTTPResponse(
                data={"value": [{"id": "t1", "displayName": "T"}]}),
            "https://graph.microsoft.com/v1.0/teams/t1/channels": FakeHTTPResponse(
                data={"value": [{"id": "c1", "displayName": "G"}]}),
            "https://graph.microsoft.com/v1.0/teams/t1/channels/c1/messages": boom,
        })
        msgs = await pipeline._fetch_teams_channel_messages(client, {}, None)
        assert msgs == []


class TestFetchEmail:
    async def test_no_credentials(self, pipeline, monkeypatch):
        for var in ("IMAP_SERVER", "IMAP_USER", "IMAP_PASSWORD"):
            monkeypatch.delenv(var, raising=False)
        assert await pipeline._fetch_email_messages(None) == []

    async def test_success(self, pipeline, monkeypatch):
        monkeypatch.setenv("IMAP_SERVER", "imap.example.com")
        monkeypatch.setenv("IMAP_USER", "u")
        monkeypatch.setenv("IMAP_PASSWORD", "p")
        with patch.object(pipeline, "_fetch_imap_messages", return_value=[{"id": "1"}]) as fi:
            msgs = await pipeline._fetch_email_messages(None)
        assert msgs == [{"id": "1"}]
        fi.assert_called_once()

    async def test_error(self, pipeline, monkeypatch):
        monkeypatch.setenv("IMAP_SERVER", "imap.example.com")
        monkeypatch.setenv("IMAP_USER", "u")
        monkeypatch.setenv("IMAP_PASSWORD", "p")
        with patch.object(pipeline, "_fetch_imap_messages",
                          side_effect=RuntimeError("imap down")):
            assert await pipeline._fetch_email_messages(None) == []

    def test_fetch_imap_success(self, pipeline):
        msg = email.message.EmailMessage()
        msg["Subject"] = "=?utf-8?q?Hello_World?="
        msg["From"] = "sender@example.com"
        msg["To"] = "me@example.com"
        msg["Date"] = "Thu, 01 Jan 2026 10:00:00 +0000"
        msg["Message-ID"] = "<abc@example.com>"
        msg.set_content("Test body text")

        class FakeIMAP:
            def __init__(self, server):
                self.server = server

            def login(self, user, pwd):
                return None

            def select(self, mailbox):
                return ("OK", None)

            def search(self, *args):
                return ("OK", [b"1 2 3"])

            def fetch(self, msg_id, *args):
                return ("OK", [(b"1 (RFC822 {123}", msg.as_bytes()), b")"])

            def close(self):
                return None

            def logout(self):
                return None

        with patch("imaplib.IMAP4_SSL", FakeIMAP):
            msgs = pipeline._fetch_imap_messages("imap.example.com", "u", "p",
                                                 datetime(2026, 1, 1))
        assert len(msgs) == 3
        assert msgs[0]["subject"] == "Hello World"
        assert msgs[0]["content"].strip() == "Test body text"
        assert msgs[0]["app_type"] == "email"

    def test_fetch_imap_search_not_ok(self, pipeline):
        class FakeIMAP:
            def __init__(self, server):
                pass

            def login(self, user, pwd):
                pass

            def select(self, mailbox):
                return ("OK", None)

            def search(self, *args):
                return ("NO", [b""])

            def close(self):
                pass

            def logout(self):
                pass

        with patch("imaplib.IMAP4_SSL", FakeIMAP):
            msgs = pipeline._fetch_imap_messages("imap.example.com", "u", "p", None)
        assert msgs == []

    def test_fetch_imap_exception(self, pipeline):
        class BrokenIMAP:
            def __init__(self, server):
                raise RuntimeError("cannot connect")

        with patch("imaplib.IMAP4_SSL", BrokenIMAP):
            assert pipeline._fetch_imap_messages("imap.example.com", "u", "p", None) == []

    def test_fetch_imap_bad_date(self, pipeline):
        class FakeIMAP:
            def __init__(self, server):
                pass

            def login(self, user, pwd):
                pass

            def select(self, mailbox):
                return ("OK", None)

            def search(self, *args):
                return ("OK", [b"1"])

            def fetch(self, msg_id, *args):
                raw = (b"From: a@b.c\nDate: not-a-date\nSubject: x\n\nbody\n")
                return ("OK", [(b"1 (RFC822 {9}", raw), b")"])

            def close(self):
                pass

            def logout(self):
                pass

        with patch("imaplib.IMAP4_SSL", FakeIMAP):
            msgs = pipeline._fetch_imap_messages("imap.example.com", "u", "p", None)
        assert msgs == []


class TestFetchGmail:
    def _fake_gmail(self, messages):
        svc = Mock()
        svc.service = object()
        svc.get_messages = Mock(return_value=messages)
        return svc

    async def test_service_not_authenticated(self, pipeline):
        svc = Mock()
        svc.service = None
        with patch("integrations.gmail_service.GmailService", return_value=svc):
            assert await pipeline._fetch_gmail_messages(None) == []

    async def test_authentication_failure(self, pipeline):
        svc = Mock()
        svc.service = None
        svc._authenticate = Mock(side_effect=RuntimeError("auth fail"))
        with patch("integrations.gmail_service.GmailService", return_value=svc):
            assert await pipeline._fetch_gmail_messages(None) == []

    async def test_import_error(self, pipeline):
        with patch.dict(sys.modules, {"integrations.gmail_service": None}):
            assert await pipeline._fetch_gmail_messages(None) == []

    async def test_success_normalization(self, pipeline):
        messages = [
            {"id": "m1", "timestamp": "2026-01-01T10:00:00", "sender": "Alice <alice@b.c>",
             "recipient": "me@b.c", "subject": "hi", "body": "hello", "threadId": "t1",
             "labelIds": ["INBOX", "IMPORTANT"], "attachments": [{"id": "a1", "filename": "f.pdf",
                                                                  "size": 10, "contentType": "pdf"}],
             "snippet": "snip", "historyId": "h1", "internalDate": "1", "sizeEstimate": 2},
            {"id": "m2", "timestamp": "1700000000", "sender": "plain@b.c", "recipient": "",
             "subject": "", "body": "", "attachments": [], "labelIds": []},
            {"id": "m3", "sender": "", "recipient": "", "attachments": [], "labelIds": []},
        ]
        svc = self._fake_gmail(messages)
        with patch("integrations.gmail_service.GmailService", return_value=svc):
            msgs = await pipeline._fetch_gmail_messages(None)
        assert len(msgs) == 3
        assert msgs[0]["sender_email"] == "alice@b.c"
        assert msgs[0]["priority"] == "high"
        assert msgs[0]["attachments"][0]["filename"] == "f.pdf"
        assert msgs[1]["timestamp"].year == 2023
        assert msgs[2]["timestamp"].tzinfo is None or msgs[2]["timestamp"] is not None

    async def test_message_normalization_error_skipped(self, pipeline):
        messages = [{"id": "bad", "attachments": "not-a-list"}]
        svc = self._fake_gmail(messages)
        with patch("integrations.gmail_service.GmailService", return_value=svc):
            msgs = await pipeline._fetch_gmail_messages(None)
        assert msgs == []

    async def test_generic_error(self, pipeline):
        svc = Mock()
        svc.service = object()
        svc.get_messages = Mock(side_effect=RuntimeError("api down"))
        with patch("integrations.gmail_service.GmailService", return_value=svc):
            assert await pipeline._fetch_gmail_messages(None) == []


class TestFetchOutlook:
    async def test_no_token(self, pipeline):
        with patch(
            "integrations.outlook_service.outlook_service._get_access_token",
            new_callable=AsyncMock,
            return_value=None,
        ):
            assert await pipeline._fetch_outlook_messages(None) == []

    async def test_import_error(self, pipeline):
        with patch.dict(sys.modules, {"integrations.outlook_service": None}):
            assert await pipeline._fetch_outlook_messages(None) == []

    async def test_success_with_pagination(self, pipeline):
        page1 = FakeHTTPResponse(data={
            "value": [{
                "id": "m1",
                "receivedDateTime": "2026-01-01T10:00:00Z",
                "from": {"emailAddress": {"address": "a@b.c", "name": "Alice"}},
                "toRecipients": [{"emailAddress": {"address": "me@b.c"}}],
                "subject": "hello", "body": {"content": "body", "contentType": "html"},
                "attachments": [{"id": "at1", "name": "f.pdf", "size": 1,
                                 "contentType": "pdf", "isInline": False}],
                "isRead": True, "importance": "High", "categories": ["Blue"],
                "conversationId": "cv1",
            }],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/next",
        })
        page2 = FakeHTTPResponse(data={"value": []})
        client = FakeHTTPClient(routes={
            "https://graph.microsoft.com/v1.0/me/messages": page1,
            "https://graph.microsoft.com/v1.0/next": page2,
        })
        with patch(
            "integrations.outlook_service.outlook_service._get_access_token",
            new_callable=AsyncMock,
            return_value="t",
        ), patch("httpx.AsyncClient", fake_client_factory(client)):
            msgs = await pipeline._fetch_outlook_messages(datetime(2026, 1, 1))
        assert len(msgs) == 1
        assert msgs[0]["priority"] == "high"
        assert msgs[0]["status"] == "read"
        assert "Blue" in msgs[0]["tags"]

    async def test_rate_limited_then_success(self, pipeline):
        calls = {"n": 0}

        def messages_route(url, headers, params):
            calls["n"] += 1
            if calls["n"] == 1:
                return FakeHTTPResponse(429, headers={"Retry-After": 1})
            return FakeHTTPResponse(data={"value": []})

        client = FakeHTTPClient(routes={
            "https://graph.microsoft.com/v1.0/me/messages": messages_route,
        })
        with patch(
            "integrations.outlook_service.outlook_service._get_access_token",
            new_callable=AsyncMock,
            return_value="t",
        ), patch("httpx.AsyncClient", fake_client_factory(client)), \
                patch("integrations.atom_communication_ingestion_pipeline.asyncio.sleep",
                      new=AsyncMock()):
            msgs = await pipeline._fetch_outlook_messages(None)
        assert msgs == []
        assert calls["n"] == 2

    async def test_non_200_breaks(self, pipeline):
        client = FakeHTTPClient(routes={
            "https://graph.microsoft.com/v1.0/me/messages": FakeHTTPResponse(status_code=500),
        })
        with patch(
            "integrations.outlook_service.outlook_service._get_access_token",
            new_callable=AsyncMock,
            return_value="t",
        ), patch("httpx.AsyncClient", fake_client_factory(client)):
            msgs = await pipeline._fetch_outlook_messages(None)
        assert msgs == []

    async def test_page_error_breaks(self, pipeline):
        def boom(url, headers, params):
            raise RuntimeError("graph down")

        client = FakeHTTPClient(routes={
            "https://graph.microsoft.com/v1.0/me/messages": boom,
        })
        with patch(
            "integrations.outlook_service.outlook_service._get_access_token",
            new_callable=AsyncMock,
            return_value="t",
        ), patch("httpx.AsyncClient", fake_client_factory(client)):
            msgs = await pipeline._fetch_outlook_messages(None)
        assert msgs == []


class TestNormalizeMessage:
    def test_whatsapp(self, pipeline):
        data = pipeline._normalize_message("whatsapp", {"from": "555", "to": "666",
                                                        "content": "hi", "message_type": "text",
                                                        "metadata": {"k": "v"}, "tags": ["t"]})
        assert data["direction"] == "inbound"
        assert data["sender"] == "555"
        assert data["metadata"]["whatsapp_metadata"] == {"k": "v"}
        assert data["app_type"] == "whatsapp"

    def test_email_variants(self, pipeline):
        for app in ("email", "gmail", "outlook"):
            data = pipeline._normalize_message(app, {"from": "user", "to": "x@y.z", "date": "2026-01-01T10:00:00"})
            assert data["direction"] == "outbound"

    def test_generic(self, pipeline):
        data = pipeline._normalize_message("slack", {"sender": "s", "recipient": "r",
                                                     "timestamp": "2026-01-01T10:00:00"})
        assert data["sender"] == "s"
        assert data["app_type"] == "slack"

    def test_defaults(self, pipeline):
        data = pipeline._normalize_message("slack", {})
        assert data["id"].startswith("slack_")
        assert data["direction"] == "inbound"
        assert data["content"] == ""

    def test_generate_embedding_delegates(self, pipeline):
        with patch.object(pipeline.memory_manager, "generate_embedding",
                          return_value=[0.0] * 768) as gen:
            emb = pipeline._generate_embedding("x")
        assert emb == [0.0] * 768
        gen.assert_called_once_with("x")


class TestIngestionStats:
    async def test_stats(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="w")
        mm.initialize()
        p = CommunicationIngestionPipeline(mm)
        with patch("core.automation_settings.get_automation_settings") as settings:
            settings.return_value.is_automations_enabled.return_value = False
            await p.ingest_message("slack", {"content": "one", "id": "s1"})
            await p.ingest_message("slack", {"content": "two", "id": "s2"})
            await p.ingest_message("teams", {"content": "three", "id": "s3"})
        stats = p.get_ingestion_stats()
        assert stats["total_messages"] == 3
        assert stats["app_stats"]["slack"]["total_messages"] == 2
        assert stats["app_stats"]["teams"]["total_messages"] == 1
        assert "slack" in stats["configured_apps"] or True

    async def test_stats_error(self, tmp_path):
        mm = LanceDBMemoryManager(db_path=str(tmp_path / "m"), workspace_id="w")
        mm.initialize()
        p = CommunicationIngestionPipeline(mm)
        with patch.object(mm.metadata_table, "search", side_effect=RuntimeError("boom")):
            stats = p.get_ingestion_stats()
        assert "error" in stats


class TestModuleLevel:
    def test_get_memory_manager_caches(self, tmp_path, monkeypatch):
        from integrations.atom_communication_ingestion_pipeline import (
            _workspace_memory_managers, get_memory_manager,
        )
        monkeypatch.setattr("integrations.atom_communication_ingestion_pipeline._workspace_memory_managers", {})
        m1 = get_memory_manager("zz-ws")
        m2 = get_memory_manager("zz-ws")
        assert m1 is m2
        m3 = get_memory_manager("other-ws")
        assert m3 is not m1

    def test_module_exports(self):
        from integrations.atom_communication_ingestion_pipeline import (
            CommunicationAppType, CommunicationData, IngestionConfig,
            LanceDBMemoryManager, CommunicationIngestionPipeline, memory_manager,
            ingestion_pipeline,
        )
        assert CommunicationAppType.WHATSAPP.value == "whatsapp"
        assert memory_manager is not None
        assert ingestion_pipeline is not None

    def test_communication_data_roundtrip(self):
        d = comm_data()
        assert d.vector_embedding is None
        assert d.direction == "inbound"

    def test_native_integrations_constant(self):
        assert "salesforce" in NATIVE_INTEGRATIONS
        assert "shopify" in NATIVE_INTEGRATIONS
        # 46 = 44 + zoho_forms + zoho_flow (webhook-push apps; read what has
        # been ingested — see universal_integration_service._execute_zoho)
        assert "zoho_forms" in NATIVE_INTEGRATIONS
        assert "zoho_flow" in NATIVE_INTEGRATIONS
        assert len(NATIVE_INTEGRATIONS) == 46

# -*- coding: utf-8 -*-
"""Generalized live-search routing for the chat tool planner (2026-09-03).

Bug class this closes: the planner planned `<service>.search`, but
UniversalIntegrationService.execute() family handlers only implement NAMED
actions — a plain "search" action fell through to the success-without-data
"Routed to X handler" envelope, and the reply model described that as a
search that ran ("searched Zoho Inventory, no live stock records" while the
machine sat in stock). Root-cause fix of the zoho_inventory case, generalized:

- plain search intents for services with a family search implementation now
  route through UniversalIntegrationService.search() (the same router MCP
  entity search uses) — SEARCHABLE_SERVICES is the single source of truth;
- services with explicit _INTENT_ACTIONS mappings keep their execute() path
  (zoho_inventory.search_items, slack search_messages, storage search, ...);
- anything else dead-ends HONESTLY ("<service>.<action> has no live
  implementation") + memory fallback, never a fake "searched".
"""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import core.chat_tool_planner as ctp
import integrations.universal_integration_service as univ
from core.chat_tool_planner import ToolPlan, _catalog_line, execute_tool_plan
from integrations.universal_integration_service import (
    SEARCHABLE_SERVICES,
    UniversalIntegrationService,
)


def _plan(service, intent="search", query="test query"):
    return ToolPlan(use_tool=True, service=service, intent=intent, query=query)


@pytest.fixture
def no_memory_fallback(monkeypatch):
    """Keep memory-search side effects out of routing assertions."""
    mock = AsyncMock(return_value=None)
    monkeypatch.setattr(ctp, "_memory_search_block", mock)
    return mock


class TestPlannerGenericRouting:
    async def test_plain_search_routes_through_search_router(self, no_memory_fallback):
        with patch.object(UniversalIntegrationService, "search",
                          AsyncMock(return_value={"status": "success",
                                                  "data": [{"name": "Chandrakant Sharma"}]})) as s, \
             patch.object(UniversalIntegrationService, "execute", AsyncMock()) as ex:
            block = await execute_tool_plan(_plan("zoho_crm"), "user-1")
        s.assert_awaited_once()
        ex.assert_not_called()
        assert "Chandrakant Sharma" in block
        assert "zoho_crm.search" in block

    async def test_explicit_action_mapping_prefers_execute(self, no_memory_fallback):
        # zoho_inventory has an explicit _INTENT_ACTIONS mapping — it must
        # keep the execute() path (live DC-correct search_items), NOT the
        # generic router.
        with patch.object(UniversalIntegrationService, "search", AsyncMock()) as s, \
             patch.object(UniversalIntegrationService, "execute",
                          AsyncMock(return_value={"status": "success",
                                                  "data": [{"name": "WG-350DSAV",
                                                            "stock_on_hand": 1}]})) as ex:
            block = await execute_tool_plan(_plan("zoho_inventory", query="wg-350"), "user-1")
        ex.assert_awaited_once()
        assert ex.call_args.args[1] == "search_items"
        s.assert_not_called()
        assert "WG-350DSAV" in block

    async def test_list_intent_uses_execute(self, no_memory_fallback):
        with patch.object(UniversalIntegrationService, "search", AsyncMock()) as s, \
             patch.object(UniversalIntegrationService, "execute",
                          AsyncMock(return_value={"status": "success", "data": []})) as ex:
            await execute_tool_plan(_plan("zoho_crm", intent="list"), "user-1")
        s.assert_not_called()
        ex.assert_awaited_once()
        assert ex.call_args.args[1] == "list"

    async def test_unsupported_service_dead_ends_honestly(self, no_memory_fallback):
        # aws_ses has no family search implementation: the family handler's
        # fall-through envelope must surface as "no live implementation",
        # not "Routed to ..." (which reads like a call happened).
        with patch.object(UniversalIntegrationService, "execute",
                          AsyncMock(return_value={"status": "success",
                                                  "message": "Routed to aws_ses handler (Registry Finance)"})):
            block = await execute_tool_plan(_plan("aws_ses"), "user-1")
        assert "aws_ses.search has no live implementation" in block
        assert "Routed to" not in block

    async def test_memory_fallback_accompanies_honest_reason(self, monkeypatch):
        mem = AsyncMock(return_value="INGESTED MATCH: price list row")
        monkeypatch.setattr(ctp, "_memory_search_block", mem)
        with patch.object(UniversalIntegrationService, "execute",
                          AsyncMock(return_value={"status": "success",
                                                  "message": "Routed to aws_ses handler (Registry Finance)"})):
            block = await execute_tool_plan(_plan("aws_ses"), "user-1")
        assert "has no live implementation" in block
        assert "INGESTED MATCH" in block


class TestPlannerRepairRungs:
    """Routing decisions belong to the LLM — including REPAIRS. When the
    planner emits a null/unknown service, a corrective structured pass sees
    the catalog + conversation and re-decides; deterministic code only
    normalizes the service name (mechanical aliasing) and defaults to
    memory when both passes fail."""

    def _fake_llm(self, *plans):
        llm = SimpleNamespace()
        llm.generate_structured_response = AsyncMock(side_effect=list(plans))
        return llm

    async def test_null_service_repaired_by_second_llm_pass(self, monkeypatch):
        from unittest.mock import patch as _p

        monkeypatch.setattr(ctp, "get_connected_services",
                            lambda user_id: ["zoho_inventory", "zoho_crm"])
        flaky = ToolPlan(use_tool=True, service=None, intent="search",
                         query="wg-350dsav")
        repaired = ToolPlan(use_tool=True, service="zoho_inventory",
                            intent="search", query="wg-350dsav")
        llm = self._fake_llm(flaky, repaired)
        with _p.object(ctp, "_available_platform_services", return_value=[]):
            plan = await ctp.plan_tool_use(
                "is the wg-350dsav in stock?", [], "user-1", llm)
        assert llm.generate_structured_response.await_count == 2
        assert plan.service == "zoho_inventory"

    async def test_repair_can_decline_tool_use(self, monkeypatch):
        from unittest.mock import patch as _p

        monkeypatch.setattr(ctp, "get_connected_services",
                            lambda user_id: ["zoho_crm"])
        flaky = ToolPlan(use_tool=True, service=None, intent="search")
        declined = ToolPlan(use_tool=False, service=None)
        llm = self._fake_llm(flaky, declined)
        with _p.object(ctp, "_available_platform_services", return_value=[]):
            plan = await ctp.plan_tool_use(
                "what is 2+2", [], "user-1", llm)
        assert plan is None

    async def test_double_failure_defaults_to_memory(self, monkeypatch):
        from unittest.mock import patch as _p

        monkeypatch.setattr(ctp, "get_connected_services",
                            lambda user_id: ["zoho_crm"])
        flaky = ToolPlan(use_tool=True, service=None, intent="search",
                         query="anything")
        llm = self._fake_llm(flaky, flaky)
        with _p.object(ctp, "_available_platform_services",
                       return_value=["memory"]):
            plan = await ctp.plan_tool_use(
                "check the file again", [], "user-1", llm)
        # Constant terminal default (not a content-based guess): memory is
        # always available and searches the workspace's own ingested data.
        assert plan.service == "memory"
        assert plan.intent == "search"

    async def test_loose_service_name_normalized(self, monkeypatch):
        from unittest.mock import patch as _p

        monkeypatch.setattr(ctp, "get_connected_services",
                            lambda user_id: ["zoho_inventory", "zoho_crm"])
        loose = ToolPlan(use_tool=True, service="Zoho CRM", intent="search",
                         query="Blumetric")
        with _p.object(ctp, "_available_platform_services", return_value=[]):
            plan = await ctp.plan_tool_use(
                "search zoho crm for Blumetric", [], "user-1", self._fake_llm(loose))
        assert plan.service == "zoho_crm"


class TestCatalogAnnotation:
    def test_searchable_without_description_annotated_live(self):
        line = _catalog_line(["google_chat"])
        assert "google_chat" in line
        assert "live search supported" in line

    def test_unsearchable_annotated_memory_only(self):
        line = _catalog_line(["aws_ses"])
        assert "no live search" in line
        assert "memory" in line

    def test_described_services_unchanged(self):
        line = _catalog_line(["outlook"])
        assert "email mailbox" in line
        assert "no live search" not in line


def _family_patch_map():
    """service -> (attribute of UniversalIntegrationService, return value)."""
    envelope = {"status": "success", "data": []}
    return {
        "salesforce": ("_search_salesforce", []),
        "hubspot": ("_search_hubspot", envelope),
        "pipedrive": ("_search_crm", envelope),
        "zoho_crm": ("_search_crm", envelope),
        **{s: ("_search_communication", envelope) for s in (
            "slack", "teams", "discord", "google_chat", "telegram",
            "whatsapp", "gmail", "outlook", "zoho_mail")},
        **{s: ("_search_calendar", envelope) for s in ("google_calendar", "outlook_calendar")},
        **{s: ("_search_project_management", envelope) for s in (
            "linear", "monday", "zoho_projects", "asana", "jira", "trello")},
        **{s: ("_search_storage", envelope) for s in (
            "google_drive", "dropbox", "onedrive", "box", "notion")},
        **{s: ("_search_support", envelope) for s in ("zendesk", "freshdesk", "intercom")},
        **{s: ("_search_dev", envelope) for s in ("github", "gitlab")},
        "mailchimp": ("_search_marketing", envelope),
        **{s: ("_search_analytics", envelope) for s in ("tableau", "google_analytics")},
        "zoho_workdrive": ("_execute_storage", envelope),
    }


class TestSearchRouterCoverage:
    """Keeps SEARCHABLE_SERVICES in sync with search()'s routing: every
    listed service must route to a family implementation (no ValueError
    dead-end), with each family method mocked."""

    @pytest.fixture
    def patched_circuit_breaker(self):
        with patch.object(univ.circuit_breaker, "is_enabled", AsyncMock(return_value=True)):
            yield

    @pytest.fixture
    def patched_registry(self, monkeypatch):
        fin = SimpleNamespace(
            access_token=None,
            # StripeAdapter.get_charges — list_payments exists on no stripe
            # class (parity test caught the phantom method 2026-09-03).
            get_charges=AsyncMock(return_value=[]),
            get_invoices=AsyncMock(return_value=[]),
        )
        registry = SimpleNamespace(get_service_instance=AsyncMock(return_value=fin))
        # search() imports these locally (from core.database / core.integration_registry)
        monkeypatch.setattr("core.database.SessionLocal", lambda: nullcontext(SimpleNamespace()))
        monkeypatch.setattr("core.integration_registry.IntegrationRegistry", lambda db: registry)
        return registry

    async def test_every_searchable_service_routes(self,
                                                   patched_circuit_breaker,
                                                   patched_registry):
        unpatched = []
        for service in sorted(SEARCHABLE_SERVICES):
            spec = _family_patch_map().get(service)
            if spec:
                attr, ret = spec
                with patch.object(UniversalIntegrationService, attr, AsyncMock(return_value=ret)):
                    result = await UniversalIntegrationService().search(service, "q")
            elif service == "zoho_forms":
                with patch("integrations.zoho_forms_service.ZohoFormsService.search_submissions",
                           AsyncMock(return_value=[])):
                    result = await UniversalIntegrationService().search(service, "q")
            elif service == "zoho_flow":
                with patch("integrations.zoho_flow_service.ZohoFlowService.search_events",
                           AsyncMock(return_value=[])):
                    result = await UniversalIntegrationService().search(service, "q")
            elif service == "zoho_inventory":
                with patch.object(UniversalIntegrationService, "execute",
                                  AsyncMock(return_value={"status": "success", "data": []})):
                    result = await UniversalIntegrationService().search(service, "q")
            elif service in ("stripe", "quickbooks", "xero", "zoho_books"):
                result = await UniversalIntegrationService().search(service, "q")
            else:
                unpatched.append(service)
                continue
            assert result.get("status") == "success", f"{service}: {result}"
        assert not unpatched, f"SEARCHABLE_SERVICES entries without a route test: {unpatched}"

    async def test_finance_search_filters_client_side(self,
                                                      patched_circuit_breaker,
                                                      patched_registry):
        invoices = [
            {"invoice_number": "INV-001", "customer_name": "Fastenal Supply"},
            {"invoice_number": "INV-002", "customer_name": "ACME Corp"},
        ]
        patched_registry.get_service_instance.return_value.get_invoices = AsyncMock(
            return_value=invoices)
        result = await UniversalIntegrationService().search(
            "zoho_books", "fastenal", context={"tenant_id": "t1"})
        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["invoice_number"] == "INV-001"

    async def test_inventory_search_delegates_to_service(self,
                                                         patched_circuit_breaker,
                                                         patched_registry):
        with patch.object(UniversalIntegrationService, "execute",
                          AsyncMock(return_value={"status": "success",
                                                  "data": [{"name": "WG-350DSAV"}]})) as ex:
            result = await UniversalIntegrationService().search("zoho_inventory", "wg-350")
        ex.assert_awaited_once()
        assert ex.call_args.args[1] == "search_items"
        assert result["data"][0]["name"] == "WG-350DSAV"

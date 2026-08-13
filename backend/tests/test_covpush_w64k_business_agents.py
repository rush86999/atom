"""Coverage-push tests for core.business_agents (W64k, TDD, 0% baseline).

Target: >=95% statement coverage STANDALONE (this file alone).

Covers: BusinessAgent base init + abstract contract; the 8-agent registry
(Accounting/Sales/Marketing/Logistics/Tax/Purchasing/BusinessPlanning +
shipping alias); per-agent run() success with params / without params,
missing workspace_id, workspace-not-found, and exception paths; Marketing's
optional market-research branch (web_search success + failure); factory
get_specialized_agent (all registry names, case-insensitive, unknown).

No LLM spend, no network, no real DB: get_db_session is patched with a
context manager yielding a MagicMock session; mcp_service.web_search is
an AsyncMock.
"""

import sys
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import business_agents as ba
from integrations.mcp_service import mcp_service


@pytest.fixture
def db():
    """Context manager yielding a mocked session; db.query configured per test."""
    session = MagicMock()
    manager = contextmanager(lambda: (yield session))
    with patch.object(ba, "get_db_session", manager):
        yield session


def _workspace():
    ws = MagicMock()
    ws.id = "ws-1"
    return ws


@pytest.fixture
def workspace_found(db):
    db.query.return_value.filter.return_value.first.return_value = _workspace()
    return db


class TestBusinessAgentBase:
    async def test_init_sets_attributes(self):
        class Concrete(ba.BusinessAgent):
            async def run(self, workspace_id, params=None):
                return {"status": "ok"}

        agent = Concrete("agent-1", "Test Agent", "test")
        assert agent.agent_id == "agent-1"
        assert agent.name == "Test Agent"
        assert agent.domain == "test"
        assert agent.mcp is mcp_service

    async def test_abstract_run_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ba.BusinessAgent("a", "b", "c")

    async def test_subclass_must_implement_run(self):
        class Incomplete(ba.BusinessAgent):
            pass

        with pytest.raises(TypeError):
            Incomplete("a", "b", "c")


class TestAccountingAgent:
    async def test_init(self):
        a = ba.AccountingAgent()
        assert a.name == "Accounting Assistant"
        assert a.domain == "finance"
        assert a.agent_id.startswith("accounting-agent-")

    async def test_run_success_defaults(self, workspace_found):
        result = await ba.AccountingAgent().run("ws-1")
        assert result["status"] == "success"
        assert result["agent"] == "Accounting Assistant"
        assert result["workspace_id"] == "ws-1"
        r = result["results"]
        assert r["categorized"] == 12
        assert r["anomalies_detected"] == 1
        assert r["reconciliations_performed"] == 3
        assert len(r["logs"]) == 3
        assert "+12%" not in result["summary"]
        assert "12 transactions" in result["summary"]

    async def test_run_success_with_params(self, workspace_found):
        result = await ba.AccountingAgent().run(
            "ws-1", {"transaction_limit": 5, "perform_reconciliation": False})
        r = result["results"]
        assert r["categorized"] == 5
        assert r["reconciliations_performed"] == 0
        assert len(r["logs"]) == 2
        assert "0 reconciliations" in result["summary"]

    async def test_run_missing_workspace_id(self, db):
        result = await ba.AccountingAgent().run("")
        assert result["status"] == "error"
        assert result["error"] == "workspace_id is required"

    async def test_run_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        result = await ba.AccountingAgent().run("missing")
        assert result["status"] == "error"
        assert "not found" in result["error"]

    async def test_run_exception(self, db):
        db.query.side_effect = RuntimeError("db down")
        result = await ba.AccountingAgent().run("ws-1")
        assert result["status"] == "error"
        assert result["error"] == "db down"
        assert result["agent_id"].startswith("accounting-agent-")


class TestSalesAgent:
    async def test_init(self):
        a = ba.SalesAgent()
        assert a.name == "Sales Catalyst"
        assert a.domain == "sales"
        assert a.agent_id.startswith("sales-agent-")

    async def test_run_success_defaults(self, workspace_found):
        result = await ba.SalesAgent().run("ws-1")
        assert result["status"] == "success"
        r = result["results"]
        assert r["leads_scored"] == 45
        assert r["pipeline_health_score"] == 88
        assert r["stalled_deals_notified"] == 3
        assert "45 leads" in result["summary"]

    async def test_run_success_with_params(self, workspace_found):
        result = await ba.SalesAgent().run("ws-1", {"lead_limit": 10, "pipeline_stage": "proposal"})
        assert result["results"]["leads_scored"] == 10

    async def test_run_missing_workspace_id(self, db):
        result = await ba.SalesAgent().run(None)
        assert result["status"] == "error"
        assert result["error"] == "workspace_id is required"

    async def test_run_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        result = await ba.SalesAgent().run("missing")
        assert result["status"] == "error"

    async def test_run_exception(self, db):
        db.query.side_effect = ValueError("boom")
        result = await ba.SalesAgent().run("ws-1")
        assert result["status"] == "error"
        assert result["error"] == "boom"


class TestMarketingAgent:
    async def test_init(self):
        a = ba.MarketingAgent()
        assert a.name == "Growth Navigator"
        assert a.domain == "marketing"
        assert a.agent_id.startswith("marketing-agent-")

    async def test_run_success_no_research(self, workspace_found):
        result = await ba.MarketingAgent().run("ws-1")
        assert result["status"] == "success"
        r = result["results"]
        assert r["channels_analyzed"] == 5
        assert r["cac_reduction"] == "4.2%"
        assert r["top_channel"] == "Google Ads"
        assert r["review_requests_sent"] == 15
        assert "market_research" not in r
        assert result["summary"].endswith("CAC reduction: 4.2%. ")

    async def test_run_with_research_success(self, workspace_found):
        with patch.object(mcp_service, "web_search", AsyncMock(return_value={
                "answer": "AI agents are trending in 2026" * 30})) as search_mock:
            result = await ba.MarketingAgent().run(
                "ws-1", {"perform_research": True, "research_query": "AI trends"})
            assert result["results"]["market_research"][:20] == "AI agents are trendi"
            assert len(result["results"]["market_research"]) == 500
            assert "Market research:" in result["summary"]
            search_mock.assert_awaited_once_with("AI trends")

    async def test_run_with_research_no_answer(self, workspace_found):
        with patch.object(mcp_service, "web_search", AsyncMock(return_value={})):
            result = await ba.MarketingAgent().run("ws-1", {"perform_research": True})
            assert result["results"]["market_research"] == "No specific trends found."

    async def test_run_with_research_exception(self, workspace_found):
        with patch.object(mcp_service, "web_search", AsyncMock(side_effect=RuntimeError("nope"))):
            result = await ba.MarketingAgent().run("ws-1", {"perform_research": True})
            assert result["results"]["market_research"] == "Market research unavailable"
            assert "Market research:" not in result["summary"]

    async def test_run_custom_query_default(self, workspace_found):
        with patch.object(mcp_service, "web_search", AsyncMock(return_value={"answer": "x" * 60})):
            result = await ba.MarketingAgent().run("ws-1", {"perform_research": True})
            mcp_service.web_search.assert_awaited_once_with(
                "current marketing trends for small businesses")
            assert result["results"]["market_research"] == "x" * 60

    async def test_run_missing_workspace_id(self, db):
        result = await ba.MarketingAgent().run("")
        assert result["status"] == "error"

    async def test_run_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        result = await ba.MarketingAgent().run("missing")
        assert result["status"] == "error"

    async def test_run_exception(self, db):
        db.query.side_effect = RuntimeError("down")
        result = await ba.MarketingAgent().run("ws-1")
        assert result["status"] == "error"
        assert result["error"] == "down"


class TestLogisticsAgent:
    async def test_init(self):
        a = ba.LogisticsAgent()
        assert a.name == "Supply Chain Warden"
        assert a.domain == "logistics"
        assert a.agent_id.startswith("logistics-agent-")

    async def test_run_success(self, workspace_found):
        result = await ba.LogisticsAgent().run("ws-1")
        assert result["status"] == "success"
        r = result["results"]
        assert r["shipments_tracked"] == 120
        assert r["on_time_delivery_rate"] == "94.5%"
        assert "120 shipments tracked (94.5% on-time)" in result["summary"]

    async def test_run_missing_workspace_id(self, db):
        result = await ba.LogisticsAgent().run("")
        assert result["status"] == "error"

    async def test_run_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        assert (await ba.LogisticsAgent().run("missing"))["status"] == "error"

    async def test_run_exception(self, db):
        db.query.side_effect = RuntimeError("x")
        assert (await ba.LogisticsAgent().run("ws-1"))["status"] == "error"


class TestTaxAgent:
    async def test_init(self):
        a = ba.TaxAgent()
        assert a.name == "Compliance Sentinel"
        assert a.domain == "finance"
        assert a.agent_id.startswith("tax-agent-")

    async def test_run_success(self, workspace_found):
        result = await ba.TaxAgent().run("ws-1")
        assert result["status"] == "success"
        r = result["results"]
        assert r["estimated_liability"] == "$4,250.00"
        assert r["compliance_score"] == 87
        assert "$4,250.00" in result["summary"]

    async def test_run_missing_workspace_id(self, db):
        assert (await ba.TaxAgent().run(None))["status"] == "error"

    async def test_run_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        assert (await ba.TaxAgent().run("missing"))["status"] == "error"

    async def test_run_exception(self, db):
        db.query.side_effect = RuntimeError("x")
        assert (await ba.TaxAgent().run("ws-1"))["status"] == "error"


class TestPurchasingAgent:
    async def test_init(self):
        a = ba.PurchasingAgent()
        assert a.name == "Strategic Sourcing Bot"
        assert a.domain == "procurement"
        assert a.agent_id.startswith("purchasing-agent-")

    async def test_run_success(self, workspace_found):
        result = await ba.PurchasingAgent().run("ws-1")
        assert result["status"] == "success"
        r = result["results"]
        assert r["po_drafted"] == 1
        assert r["vendors_evaluated"] == 5
        assert "$320.00" in result["summary"]

    async def test_run_missing_workspace_id(self, db):
        assert (await ba.PurchasingAgent().run(""))["status"] == "error"

    async def test_run_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        assert (await ba.PurchasingAgent().run("missing"))["status"] == "error"

    async def test_run_exception(self, db):
        db.query.side_effect = RuntimeError("x")
        assert (await ba.PurchasingAgent().run("ws-1"))["status"] == "error"


class TestBusinessPlanningAgent:
    async def test_init(self):
        a = ba.BusinessPlanningAgent()
        assert a.name == "Strategy Oracle"
        assert a.domain == "strategy"
        assert a.agent_id.startswith("planning-agent-")

    async def test_run_success(self, workspace_found):
        result = await ba.BusinessPlanningAgent().run("ws-1")
        assert result["status"] == "success"
        r = result["results"]
        assert r["growth_forecast"] == "+12% YoY"
        assert r["confidence_level"] == 0.78
        assert "78% confidence" in result["summary"]
        assert "Sales Rep" in result["summary"]
        assert "Market saturation" in result["summary"]

    async def test_run_missing_workspace_id(self, db):
        assert (await ba.BusinessPlanningAgent().run(""))["status"] == "error"

    async def test_run_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        assert (await ba.BusinessPlanningAgent().run("missing"))["status"] == "error"

    async def test_run_exception(self, db):
        db.query.side_effect = RuntimeError("x")
        assert (await ba.BusinessPlanningAgent().run("ws-1"))["status"] == "error"


class TestAgentRegistry:
    @pytest.mark.parametrize("name,expected", [
        ("accounting", ba.AccountingAgent),
        ("sales", ba.SalesAgent),
        ("marketing", ba.MarketingAgent),
        ("logistics", ba.LogisticsAgent),
        ("shipping", ba.LogisticsAgent),
        ("tax", ba.TaxAgent),
        ("purchasing", ba.PurchasingAgent),
        ("planning", ba.BusinessPlanningAgent),
    ])
    async def test_suite_members(self, name, expected):
        assert ba.AGENT_SUITE[name] is expected

    async def test_registry_keys(self):
        assert set(ba.AGENT_SUITE.keys()) == {
            "accounting", "sales", "marketing", "logistics", "shipping",
            "tax", "purchasing", "planning"}

    @pytest.mark.parametrize("name", ["accounting", "sales", "marketing",
                                      "logistics", "shipping", "tax",
                                      "purchasing", "planning"])
    async def test_get_specialized_agent(self, name):
        agent = ba.get_specialized_agent(name)
        assert isinstance(agent, ba.BusinessAgent)
        assert agent.domain == ba.AGENT_SUITE[name]().domain

    async def test_get_specialized_agent_case_insensitive(self):
        assert isinstance(ba.get_specialized_agent("SALES"), ba.SalesAgent)
        assert isinstance(ba.get_specialized_agent("Accounting"), ba.AccountingAgent)

    async def test_get_specialized_agent_unknown(self):
        assert ba.get_specialized_agent("hr") is None
        assert ba.get_specialized_agent("") is None

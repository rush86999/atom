"""Coverage wave 46 — core/recruitment_intelligence_service (0 tests → 90%+).

- _build_domain_catalog
- analyze_goal_domains: LLM success with domain filtering, LLM failure →
  keyword fallback
- _fallback_domain_analysis: matched/truncated/empty
- orchestrate_recruitment: full success flow, missing specialists, governance
  block, budget path (chain limit + estimate), exception
- _estimate_fleet_cost: base + optimization premium
"""
import os
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.recruitment_intelligence_service import RecruitmentIntelligenceService


@pytest.fixture
def svc():
    m = RecruitmentIntelligenceService(
        db=MagicMock(),
        llm=MagicMock(),
        specialist_matcher=MagicMock(),
        analytics=MagicMock(),
        fleet_service=MagicMock(),
        optimizer=MagicMock(),
        governance=MagicMock(),
        budget=None,
    )
    return m


def _plan(**kw):
    class _P:
        def __init__(self, **k):
            self.__dict__.update(k)

        def dict(self):
            return self.__dict__

    return _P(
        goal_analysis="a",
        required_domains=kw.get("required_domains", ["finance"]),
        domain_rationale=kw.get("domain_rationale", {"finance": "needed"}),
        complexity_estimate="medium",
        estimated_parallelizable=False,
        suggested_specialist_count=1,
    )


class TestDomainCatalog:
    def test_build_catalog(self, svc):
        svc.matcher.get_all_available_domains.return_value = ["finance", "sales"]
        # the code uses a single filter(...) with two args, then .count()
        svc.db.query.return_value.filter.return_value.count.return_value = 2
        catalog = svc._build_domain_catalog("u1")
        assert "Finance" in catalog
        assert "2 specialist(s)" in catalog


class TestAnalyzeGoalDomains:
    async def test_llm_success_filters_domains(self, svc):
        plan = _plan(
            required_domains=["finance", "bogus_domain"],
            domain_rationale={"finance": "needed", "bogus_domain": "x"},
        )
        svc.llm.generate_structured_response = AsyncMock(return_value=plan)
        result = await svc.analyze_goal_domains("reconcile", "u1")
        assert result.required_domains == ["finance"]
        assert result.suggested_specialist_count == 1
        assert "bogus_domain" not in result.domain_rationale

    async def test_llm_failure_fallback(self, svc):
        svc.llm.generate_structured_response = AsyncMock(
            side_effect=RuntimeError("llm down")
        )
        svc.matcher.DOMAIN_ALIASES = {}
        result = await svc.analyze_goal_domains("no matching keywords here", "u1")
        assert isinstance(result.required_domains, list)
        assert result.complexity_estimate == "medium"

    async def test_fallback_matches_keywords(self, svc):
        svc.llm.generate_structured_response = AsyncMock(
            side_effect=RuntimeError("down")
        )
        svc.matcher.DOMAIN_ALIASES = {}
        result = await svc.analyze_goal_domains(
            "help with finance and sales reconciliation", "u1", max_specialists=3
        )
        assert "finance" in result.required_domains
        assert "sales" in result.required_domains

    async def test_fallback_truncates(self, svc):
        svc.llm.generate_structured_response = AsyncMock(
            side_effect=RuntimeError("down")
        )
        svc.matcher.DOMAIN_ALIASES = {}
        result = await svc.analyze_goal_domains(
            "finance sales marketing operations", "u1", max_specialists=2
        )
        assert len(result.required_domains) <= 2
        assert len(result.domain_rationale) <= 2


class TestOrchestrate:
    async def test_full_success(self, svc):
        svc.analyze_goal_domains = AsyncMock(return_value=_plan())
        svc.matcher.find_specialists_for_domains.return_value = {
            "finance": [{"agent_id": "a1", "name": "A1", "capability_score": 0.9}]
        }
        svc.governance.can_perform_action = AsyncMock(return_value=True)
        svc.optimizer.get_optimization_parameters = AsyncMock(return_value={"level": "low"})
        result = await svc.orchestrate_recruitment("reconcile", "u1", {}, chain_id="chain-1")
        assert result["success"] is True
        assert result["recruitment_roster"][0]["agent_id"] == "a1"
        svc.analytics.record_recruitment_decision.assert_called_once()

    async def test_missing_specialists(self, svc):
        svc.analyze_goal_domains = AsyncMock(return_value=_plan())
        svc.matcher.find_specialists_for_domains.return_value = {"finance": []}
        result = await svc.orchestrate_recruitment("reconcile", "u1", {})
        assert result["success"] is False
        assert "No specialists" in result["error"]

    async def test_governance_blocked(self, svc):
        svc.analyze_goal_domains = AsyncMock(return_value=_plan())
        svc.matcher.find_specialists_for_domains.return_value = {
            "finance": [{"agent_id": "a1", "name": "A1", "capability_score": 0.9}]
        }
        svc.governance.can_perform_action = AsyncMock(return_value=False)
        result = await svc.orchestrate_recruitment("reconcile", "u1", {})
        assert result["success"] is False
        assert "Governance" in result["error"]

    async def test_budget_exceeded(self, svc):
        svc.budget = MagicMock()
        svc.analyze_goal_domains = AsyncMock(return_value=_plan())
        svc.matcher.find_specialists_for_domains.return_value = {
            "finance": [{"agent_id": "a1", "name": "A1", "capability_score": 0.9}]
        }
        svc.governance.can_perform_action = AsyncMock(return_value=True)
        svc._estimate_fleet_cost = MagicMock(return_value=5.0)
        chain = SimpleNamespace(budget_limit_usd=1.0)
        svc.db.query.return_value.get.return_value = chain
        svc.fleet_service.get_fleet_spend.return_value = 0.0
        result = await svc.orchestrate_recruitment(
            "reconcile", "u1", {}, chain_id="chain-1"
        )
        assert result["success"] is False
        assert "budget exceeded" in result["error"].lower()

    async def test_exception_swallowed(self, svc):
        svc.analyze_goal_domains = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.orchestrate_recruitment("reconcile", "u1", {})
        assert result["success"] is False
        assert "boom" in result["error"]


class TestCostEstimate:
    def test_base_and_premium(self, svc):
        matches = {
            "finance": [{"optimization": {}}],
            "sales": [{"optimization": {"optimization_reason": "complex"}}],
        }
        cost = svc._estimate_fleet_cost(matches, "u1")
        assert cost == 0.10 + 0.15

    def test_empty(self, svc):
        assert svc._estimate_fleet_cost({}, "u1") == 0.0

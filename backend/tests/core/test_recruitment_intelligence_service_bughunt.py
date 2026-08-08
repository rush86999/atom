"""Bug-hunt tests for core.recruitment_intelligence_service.

Each test is named ``BUG: <desc>`` and documents a genuinely-new bug
(absent from HEAD) found via TDD. The fix lives in the module under test.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest
from unittest.mock import MagicMock, AsyncMock

from core.recruitment_intelligence_service import (
    RecruitmentIntelligenceService,
    RecruitmentPlan,
)


def _make_service():
    """Build a RecruitmentIntelligenceService with mocked collaborators."""
    svc = RecruitmentIntelligenceService.__new__(RecruitmentIntelligenceService)
    svc.db = MagicMock()
    svc.llm = MagicMock()
    svc.analytics = MagicMock()
    svc.fleet_service = MagicMock()
    svc.optimizer = MagicMock()
    svc.governance = MagicMock()
    svc.budget = None

    matcher = MagicMock()
    matcher.DOMAIN_ALIASES = {
        "finance": ["budget", "cost", "invoice"],
        "sales": ["crm", "lead", "deal"],
        "marketing": ["campaign", "ad"],
        "operations": ["logistics", "supply"],
        "legal": ["contract", "compliance"],
        "engineering": ["code", "build"],
        "hr": ["hiring", "payroll"],
        "procurement": ["vendor", "purchase"],
        "communications": ["pr", "press"],
        "intelligence": ["analytics", "insight"],
    }
    svc.matcher = matcher
    return svc


# ---------------------------------------------------------------------------
# BUG 1: _fallback_domain_analysis truncates required_domains but leaves
#         domain_rationale with stale entries for the truncated domains.
# ---------------------------------------------------------------------------
def test_fallback_truncates_rationale_consistently():
    """BUG: fallback truncates required_domains but not domain_rationale."""
    svc = _make_service()
    # Goal that matches ALL 10 domains
    goal = (
        "budget crm campaign logistics contract code hiring vendor pr analytics"
    )
    plan = svc._fallback_domain_analysis(goal, "user1", max_specialists=3)

    assert len(plan.required_domains) == 3  # truncated correctly
    # Rationale must only reference domains that are still in the plan
    assert set(plan.domain_rationale.keys()) == set(plan.required_domains), (
        f"domain_rationale keys {sorted(plan.domain_rationale)} do not match "
        f"required_domains {sorted(plan.required_domains)}"
    )
    assert plan.suggested_specialist_count == len(plan.required_domains)


# ---------------------------------------------------------------------------
# BUG 2: analyze_goal_domains filters invalid domains from required_domains
#         but leaves suggested_specialist_count and domain_rationale stale.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analyze_filters_keep_count_and_rationale_consistent():
    """BUG: analyze_goal_domains keeps stale count + rationale after filtering."""
    svc = _make_service()

    # LLM returns a plan with one invalid domain ("BOGUS") and stale count
    llm_plan = RecruitmentPlan(
        goal_analysis="x",
        required_domains=["finance", "sales", "BOGUS"],
        domain_rationale={"finance": "a", "sales": "b", "BOGUS": "c"},
        complexity_estimate="medium",
        estimated_parallelizable=False,
        suggested_specialist_count=3,
    )

    svc.llm.generate_structured_response = AsyncMock(return_value=llm_plan)

    result = await svc.analyze_goal_domains("goal", "user1", max_specialists=5)

    # Filtering removed BOGUS
    assert result.required_domains == ["finance", "sales"]
    # suggested_specialist_count must reflect the post-filter domain count
    assert result.suggested_specialist_count == len(result.required_domains), (
        f"stale count {result.suggested_specialist_count} != "
        f"{len(result.required_domains)}"
    )
    # domain_rationale must not retain filtered-out domains
    assert set(result.domain_rationale.keys()) == set(result.required_domains)
    assert "BOGUS" not in result.domain_rationale

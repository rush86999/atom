"""
Bug-hunt tests for BusinessHealthService.

Targets a net-new bug (absent from HEAD) in simulate_decision(): it crashes
when the optional `integrations.ai_enhanced_service` import is absent, because
it constructs an AIRequest unconditionally while sibling methods (e.g.
get_daily_priorities) correctly guard with `if ai_enhanced_service:`.

The test is annotated `BUG: <desc>` and was confirmed RED against HEAD before
the fix was applied.
"""

import asyncio

import pytest

import core.business_health_service as bhs_mod
from core.business_health_service import BusinessHealthService


class TestSimulateDecisionGracefulWhenAIServiceAbsent:
    """BUG: simulate_decision() builds AIRequest(...) unconditionally. When
    the optional ai_enhanced_service import failed (module sets AIRequest,
    AITaskType, AIModelType, AIServiceType all to None), accessing
    AITaskType.PREDICTIVE_ANALYTICS raises AttributeError BEFORE the
    try/except, so the method crashes instead of returning a graceful error
    dict like its own except-branch promises."""

    def test_returns_error_dict_when_ai_service_unavailable(self):
        """BUG: simulate_decision must degrade gracefully when the AI
        integration is not installed (matches get_daily_priorities)."""
        svc = BusinessHealthService()

        # Simulate the optional import being absent.
        prev = (
            bhs_mod.ai_enhanced_service,
            bhs_mod.AIRequest,
            bhs_mod.AITaskType,
            bhs_mod.AIModelType,
            bhs_mod.AIServiceType,
        )
        bhs_mod.ai_enhanced_service = None
        bhs_mod.AIRequest = None
        bhs_mod.AITaskType = None
        bhs_mod.AIModelType = None
        bhs_mod.AIServiceType = None
        try:
            result = asyncio.run(
                svc.simulate_decision("ws1", "HIRING", {"headcount": 1})
            )
        finally:
            (
                bhs_mod.ai_enhanced_service,
                bhs_mod.AIRequest,
                bhs_mod.AITaskType,
                bhs_mod.AIModelType,
                bhs_mod.AIServiceType,
            ) = prev

        # Must NOT raise; must return a dict (graceful degradation).
        assert isinstance(result, dict), (
            "simulate_decision should degrade to a dict when AI service is "
            "unavailable, not crash"
        )

# -*- coding: utf-8 -*-
"""Coverage wave 87 — core/reputation_service (standalone, zero LLM spend,
no network).

- determine_feedback_strategy: no AI service → static PUBLIC_REVIEW fallback;
  AI service present WITH the (optional) ai_enhanced_service module → builds
  an AIRequest (CONVERSATION_ANALYSIS/GPT-4O/OPENAI) and returns output_data;
  AI service present but the optional module is ABSENT (this repo) → graceful
  static fallback instead of crashing with ModuleNotFoundError (BUG 87-4).
- extract_operational_insights: empty review list → []; no AI → default
  insight; AI + module present → output_data list passthrough; AI + module
  present but non-list output → []; AI + module absent → graceful fallback.
"""
from contextlib import ExitStack
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.reputation_service import ReputationManager


def _run(coro):
    import asyncio
    return asyncio.run(coro)


@contextmanager
def _ai_surface():
    """Simulate integrations.ai_enhanced_service being importable: the guarded
    module-level import in reputation_service picks these up."""
    with ExitStack() as stack:
        for p in [
            patch("core.reputation_service.AIRequest",
                  MagicMock(side_effect=lambda **kw: SimpleNamespace(**kw))),
            patch("core.reputation_service.AIModelType",
                  MagicMock(GPT_4O="gpt-4o")),
            patch("core.reputation_service.AIServiceType",
                  MagicMock(OPENAI="openai")),
            patch("core.reputation_service.AITaskType",
                  MagicMock(CONVERSATION_ANALYSIS="conversation",
                            TOPIC_EXTRACTION="topic_extraction")),
        ]:
            stack.enter_context(p)
        yield


class TestDetermineFeedbackStrategy:
    def test_no_ai_service_returns_static_fallback(self):
        result = _run(ReputationManager().determine_feedback_strategy("loved it"))
        assert result["action"] == "PUBLIC_REVIEW"
        assert result["sentiment"] == "POSITIVE"

    def test_ai_service_without_module_falls_back_gracefully(self):
        """BUG 87-4 regression: with an AI service injected but the optional
        integrations.ai_enhanced_service module absent, the call must degrade
        to the static fallback, not raise ModuleNotFoundError (the marketing
        routes always pass a service, so every call previously crashed)."""
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(output_data={}))
        # Ensure the module-level guarded import resolved to None (absent).
        with patch("core.reputation_service.AIRequest", None):
            result = _run(
                ReputationManager(ai_service=ai).determine_feedback_strategy("meh")
            )
        assert result["action"] == "PUBLIC_REVIEW"
        ai.process_ai_request.assert_not_called()

    def test_ai_service_with_module_returns_output_data(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data={
                "action": "PRIVATE_FEEDBACK",
                "draft": "Please email us",
                "sentiment": "NEUTRAL",
            })
        )
        with _ai_surface():
            result = _run(
                ReputationManager(ai_service=ai).determine_feedback_strategy("it was ok")
            )
        assert result["action"] == "PRIVATE_FEEDBACK"
        request = ai.process_ai_request.await_args.args[0]
        assert request.task_type == "conversation"
        assert request.model_type == "gpt-4o"
        assert "customer sentiment" in request.input_data


class TestExtractOperationalInsights:
    def test_empty_reviews_returns_empty(self):
        assert _run(ReputationManager().extract_operational_insights([])) == []

    def test_no_ai_service_returns_default_insight(self):
        result = _run(ReputationManager().extract_operational_insights(["great"]))
        assert result[0]["category"] == "General"
        assert result[0]["sentiment"] == "PRO"

    def test_ai_service_without_module_falls_back(self):
        """BUG 87-4 same regression for insights extraction."""
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(output_data=[]))
        with patch("core.reputation_service.AIRequest", None):
            result = _run(
                ReputationManager(ai_service=ai).extract_operational_insights(["x"])
            )
        assert result[0]["category"] == "General"
        ai.process_ai_request.assert_not_called()

    def test_ai_service_with_module_returns_list(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(output_data=[
            {"category": "Pricing", "sentiment": "CON", "detail": "Too expensive"},
        ]))
        with _ai_surface():
            result = _run(
                ReputationManager(ai_service=ai).extract_operational_insights(["pricey"])
            )
        assert len(result) == 1
        assert result[0]["category"] == "Pricing"
        request = ai.process_ai_request.await_args.args[0]
        assert request.task_type == "topic_extraction"

    def test_ai_service_non_list_output_returns_empty(self):
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(output_data="not a list")
        )
        with _ai_surface():
            result = _run(
                ReputationManager(ai_service=ai).extract_operational_insights(["x"])
            )
        assert result == []

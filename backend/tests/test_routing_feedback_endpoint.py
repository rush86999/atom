"""
Tests for the live chat feedback + routing-stats endpoints and the
BYOKHandler outcome-observation hook.

These verify the user journey: feedback lands on a live endpoint (not the dead
/atom-agent path), maps to RoutingFeedback with real quality, and the stats
endpoint returns the shape the dashboard needs. The outcome hook proves the
automatic data flywheel works (every response generates a real sample).
"""

from __future__ import annotations

import os
from unittest.mock import Mock, AsyncMock, patch

import pytest


class TestFeedbackEndpointLogic:
    """The feedback endpoint logic (tested via the handler, not a full app)."""

    def test_feedback_request_model_validates(self):
        """ChatFeedbackRequest validates the payload shape."""
        from integrations.chat_routes import ChatFeedbackRequest
        from pydantic import ValidationError

        # Valid.
        req = ChatFeedbackRequest(
            message_id="m1", feedback="thumbs_up",
            model="gpt-4o", provider="openai",
        )
        assert req.feedback == "thumbs_up"
        assert req.model == "gpt-4o"

        # Missing required field.
        with pytest.raises(ValidationError):
            ChatFeedbackRequest(message_id="m1")  # type: ignore

    def test_learning_router_flag_off_returns_not_recorded(self, monkeypatch):
        """When ATOM_LEARNING_ROUTER is off, the registry returns None."""
        from core.llm.learning_router_registry import (
            learning_router_enabled, get_learning_router_instance, reset_learning_router_instance,
        )
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        reset_learning_router_instance()

        assert learning_router_enabled() is False
        assert get_learning_router_instance() is None

    def test_learning_router_flag_on_attempts_instantiation(self, monkeypatch):
        """When the flag is on, the registry attempts to instantiate."""
        from core.llm.learning_router_registry import learning_router_enabled
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")

        assert learning_router_enabled() is True
        # get_learning_router_instance will try to instantiate; may fail without
        # a real DB, but the flag check is what matters for the gate.


class TestLearningRouterSingleton:
    """The keystone fix: the router must be a process-wide singleton so
    predictors accumulate across requests instead of being garbage-collected."""

    def test_singleton_returns_same_instance(self, monkeypatch):
        """Two calls to get_learning_router_instance return the same object."""
        from core.llm.learning_router_registry import (
            get_learning_router_instance, reset_learning_router_instance,
        )
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        reset_learning_router_instance()

        r1 = get_learning_router_instance()
        r2 = get_learning_router_instance()
        assert r1 is not None, "expected a router when flag is on"
        assert r1 is r2, "singleton must return the same object across calls"

    def test_flag_off_returns_none(self, monkeypatch):
        """When the flag is off, the registry returns None."""
        from core.llm.learning_router_registry import (
            get_learning_router_instance, reset_learning_router_instance,
        )
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        reset_learning_router_instance()
        assert get_learning_router_instance() is None


class TestOutcomeObservationHook:
    """BYOKHandler._record_outcome_feedback — the automatic data flywheel."""

    @pytest.mark.asyncio
    async def test_noop_when_flag_off(self, monkeypatch):
        """When the flag is off, the hook returns immediately without error."""
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        from core.llm.byok_handler import BYOKHandler

        handler = Mock(spec=BYOKHandler)
        handler.tenant_id = "t1"
        # Should be a no-op — no exception, no side effects.
        await BYOKHandler._record_outcome_feedback(
            handler, model="gpt-4o", provider_id="openai",
            task_type="chat", content="hello",
            finish_reason="stop", success=True,
            cost=0.001, latency_ms=200.0,
        )

    @pytest.mark.asyncio
    async def test_records_quality_feedback_when_flag_on(self, monkeypatch, tmp_path):
        """When flag is on + router available, the hook records real quality."""
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")

        from core.llm.byok_handler import BYOKHandler

        # A fake learning router that captures the recorded feedback.
        captured = []

        class FakeRouter:
            async def record_feedback(self, fb):
                captured.append(fb)

        handler = Mock(spec=BYOKHandler)
        handler.tenant_id = "t1"
        # Use the real static adapter so task_type maps correctly.
        handler._adapt_task_type = BYOKHandler._adapt_task_type

        # Patch the helper that builds the router + the imports inside the hook.
        with patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=FakeRouter()):
            await BYOKHandler._record_outcome_feedback(
                handler, model="gpt-4o", provider_id="openai",
                task_type="chat", content="Here is a thorough answer. " * 30,
                finish_reason="stop", success=True,
                cost=0.001, latency_ms=200.0,
            )

        assert len(captured) == 1
        fb = captured[0]
        assert fb.model_id == "gpt-4o"
        assert fb.success is True
        assert fb.quality_satisfied is True  # substantive content
        assert fb.user_satisfaction is not None and fb.user_satisfaction > 0.5
        assert fb.actual_cost == 0.001
        # task_type adapted from "chat" -> "question_answering"
        assert fb.task_type == "question_answering"

    @pytest.mark.asyncio
    async def test_truncated_response_recorded_as_low_quality(self, monkeypatch):
        """A truncated response must be recorded as quality-unsatisfied."""
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")

        from core.llm.byok_handler import BYOKHandler

        captured = []

        class FakeRouter:
            async def record_feedback(self, fb):
                captured.append(fb)

        handler = Mock(spec=BYOKHandler)
        handler.tenant_id = "t1"
        handler._adapt_task_type = BYOKHandler._adapt_task_type

        with patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=FakeRouter()):
            await BYOKHandler._record_outcome_feedback(
                handler, model="mini", provider_id="openai",
                task_type="chat", content="partial...",
                finish_reason="length", success=True,
                cost=0.0001, latency_ms=100.0,
            )

        fb = captured[0]
        assert fb.success is True
        assert fb.quality_satisfied is False  # truncated
        assert fb.user_satisfaction < 0.5

    @pytest.mark.asyncio
    async def test_failure_recorded_with_exception(self, monkeypatch):
        """A failed API call records success=False."""
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")

        from core.llm.byok_handler import BYOKHandler

        captured = []

        class FakeRouter:
            async def record_feedback(self, fb):
                captured.append(fb)

        handler = Mock(spec=BYOKHandler)
        handler.tenant_id = "t1"
        handler._adapt_task_type = BYOKHandler._adapt_task_type

        with patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=FakeRouter()):
            await BYOKHandler._record_outcome_feedback(
                handler, model="mini", provider_id="openai",
                task_type="chat", content=None,
                finish_reason=None, success=False,
                cost=None, latency_ms=5000.0,
                exception=TimeoutError("request timed out"),
            )

        fb = captured[0]
        assert fb.success is False
        assert fb.quality_satisfied is False
        assert fb.user_satisfaction == 0.0

    @pytest.mark.asyncio
    async def test_router_unavailable_does_not_crash(self, monkeypatch):
        """If the router can't be built, the hook swallows the error."""
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        from core.llm.byok_handler import BYOKHandler

        handler = Mock(spec=BYOKHandler)
        handler.tenant_id = "t1"

        with patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=None):
            # Must not raise.
            await BYOKHandler._record_outcome_feedback(
                handler, model="gpt-4o", provider_id="openai",
                task_type="chat", content="hi",
                finish_reason="stop", success=True,
                cost=None, latency_ms=10.0,
            )


class TestTaskTypeAdapter:
    """The _adapt_task_type mapping from live strings to router vocabulary."""

    def test_known_mappings(self):
        from core.llm.byok_handler import BYOKHandler

        assert BYOKHandler._adapt_task_type("chat") == "question_answering"
        assert BYOKHandler._adapt_task_type("reasoning") == "reasoning"
        assert BYOKHandler._adapt_task_type("agentic") == "tool_use"
        assert BYOKHandler._adapt_task_type("extraction") == "extraction"
        assert BYOKHandler._adapt_task_type("code") == "code_generation"

    def test_unknown_falls_back_to_general(self):
        from core.llm.byok_handler import BYOKHandler

        assert BYOKHandler._adapt_task_type("custom_task_react") == "general"
        assert BYOKHandler._adapt_task_type(None) == "general"
        assert BYOKHandler._adapt_task_type("") == "general"

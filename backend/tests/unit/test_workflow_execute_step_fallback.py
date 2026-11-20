"""
TDD regression test: _execute_step raised ValueError when the primary service
was not in the registry AND generic catalog execution failed, never attempting
the configured fallback_service. A step with fallback_service must fall back
instead of crashing.
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest

from core.workflow_engine import (
    ModelStepTimeoutError,
    StepTimeoutError,
    WorkflowEngine,
)


@pytest.fixture
def engine():
    with patch("core.workflow_engine.get_state_manager", return_value=MagicMock()):
        eng = WorkflowEngine()
        # Bypass @async_retry_with_backoff (7s+ backoff on failures) so the
        # tests exercise the real dispatch logic without long retries.
        fn = WorkflowEngine._execute_step
        if hasattr(fn, "__wrapped__"):
            fn = fn.__wrapped__
        eng._execute_step = fn.__get__(eng)
        yield eng


@pytest.fixture
def decorated_engine():
    """Keep the real retry decorator installed for retry-behavior tests."""
    with patch("core.workflow_engine.get_state_manager", return_value=MagicMock()):
        yield WorkflowEngine()


@pytest.mark.asyncio
async def test_unknown_service_with_fallback_uses_fallback(engine):
    """Unknown primary service + generic failure must try fallback_service."""
    engine._execute_generic_action = AsyncMock(
        side_effect=ValueError("service not in catalog")
    )
    engine._execute_slack_action = AsyncMock(return_value={"ok": True, "ts": "1"})

    step = {
        "id": "s1",
        "service": "nonexistent_service",
        "action": "post",
        "fallback_service": "slack",
        "parameters": {"channel": "#general"},
    }
    result = await engine._execute_step(step, {"channel": "#general"})

    assert result["status"] == "success"
    assert result["service"] == "slack"
    assert result["execution_method"] == "fallback_service"
    engine._execute_slack_action.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_service_no_fallback_raises(engine):
    """Unknown service with no fallback must raise so the run loop marks the
    step FAILED — returning an error dict is treated as COMPLETED."""
    engine._execute_generic_action = AsyncMock(
        side_effect=ValueError("service not in catalog")
    )

    step = {
        "id": "s1",
        "service": "nonexistent_service",
        "action": "post",
        "parameters": {},
    }
    with pytest.raises(ValueError) as exc_info:
        await engine._execute_step(step, {})

    assert "Unknown service" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service,executor_attr",
    [
        ("main_agent", "_execute_main_agent_action"),
        ("ai", "_execute_ai_action"),
    ],
)
async def test_text_model_timeout_is_not_retried(
    decorated_engine, service, executor_attr
):
    """A model-step deadline is typed, retains its deadline, and is not
    automatically repeated while the provider worker may still be running."""
    executor = AsyncMock(side_effect=asyncio.TimeoutError)
    setattr(decorated_engine, executor_attr, executor)
    step = {
        "id": "model-1",
        "service": service,
        "action": "generate_content",
        "timeout": 75,
        "parameters": {},
    }

    with patch("core.auto_healing.asyncio.sleep", new=AsyncMock()) as sleep:
        with pytest.raises(ModelStepTimeoutError) as exc_info:
            await decorated_engine._execute_step(step, {})

    assert isinstance(exc_info.value, StepTimeoutError)
    assert exc_info.value.timeout == 75
    assert exc_info.value.retryable is False
    executor.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_timeout_still_uses_configured_fallback(decorated_engine):
    """Not repeating the same step must not disable a configured fallback."""
    primary = AsyncMock(side_effect=asyncio.TimeoutError)
    fallback = AsyncMock(return_value={"ok": True, "ts": "1"})
    decorated_engine._execute_main_agent_action = primary
    decorated_engine._execute_slack_action = fallback
    step = {
        "id": "model-2",
        "service": "main_agent",
        "action": "generate_content",
        "fallback_service": "slack",
        "timeout": 75,
        "parameters": {},
    }

    with patch("core.auto_healing.asyncio.sleep", new=AsyncMock()) as sleep:
        result = await decorated_engine._execute_step(step, {})

    assert result["status"] == "success"
    assert result["execution_method"] == "fallback_service"
    primary.assert_awaited_once()
    fallback.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_timeout_survives_failing_fallback_without_retry(
    decorated_engine,
):
    """The original actionable timeout is not masked by a fallback error and
    the step is not repeated after the fallback fails."""
    primary = AsyncMock(side_effect=asyncio.TimeoutError)
    fallback = AsyncMock(side_effect=RuntimeError("fallback down"))
    decorated_engine._execute_main_agent_action = primary
    decorated_engine._execute_slack_action = fallback
    step = {
        "id": "model-3",
        "service": "main_agent",
        "action": "generate_content",
        "fallback_service": "slack",
        "timeout": 75,
        "parameters": {},
    }

    with patch("core.auto_healing.asyncio.sleep", new=AsyncMock()) as sleep:
        with pytest.raises(ModelStepTimeoutError) as exc_info:
            await decorated_engine._execute_step(step, {})

    assert exc_info.value.timeout == 75
    primary.assert_awaited_once()
    fallback.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_fallback_model_timeout_is_typed_and_not_retried(
    decorated_engine,
):
    """A text-model timeout raised by the fallback keeps its own deadline and
    opts out of automatic repetition too."""
    primary = AsyncMock(side_effect=RuntimeError("primary down"))
    fallback = AsyncMock(side_effect=asyncio.TimeoutError)
    decorated_engine._execute_slack_action = primary
    decorated_engine._execute_ai_action = fallback
    step = {
        "id": "model-4",
        "service": "slack",
        "action": "generate_content",
        "fallback_service": "ai",
        "timeout": 40,
        "parameters": {},
    }

    with patch("core.auto_healing.asyncio.sleep", new=AsyncMock()) as sleep:
        with pytest.raises(ModelStepTimeoutError) as exc_info:
            await decorated_engine._execute_step(step, {})

    assert exc_info.value.timeout == 40
    primary.assert_awaited_once()
    fallback.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_ordinary_non_timeout_failure_still_retries(decorated_engine):
    """The retry opt-out applies only to typed model timeouts."""
    executor = AsyncMock(side_effect=RuntimeError("boom"))
    decorated_engine._execute_slack_action = executor
    step = {
        "id": "ordinary-1",
        "service": "slack",
        "action": "post",
        "timeout": 75,
        "parameters": {},
    }

    with patch("core.auto_healing.asyncio.sleep", new=AsyncMock()) as sleep:
        with pytest.raises(RuntimeError, match="boom"):
            await decorated_engine._execute_step(step, {})

    assert executor.await_count == 4  # initial attempt + max_retries=3
    assert sleep.await_count == 3


@pytest.mark.asyncio
async def test_other_service_timeout_still_retries(decorated_engine):
    """Non-model integration timeouts keep their existing retry behavior."""
    executor = AsyncMock(side_effect=asyncio.TimeoutError)
    decorated_engine._execute_slack_action = executor
    step = {
        "id": "ordinary-2",
        "service": "slack",
        "action": "post",
        "timeout": 75,
        "parameters": {},
    }

    with patch("core.auto_healing.asyncio.sleep", new=AsyncMock()) as sleep:
        with pytest.raises(StepTimeoutError) as exc_info:
            await decorated_engine._execute_step(step, {})

    assert not isinstance(exc_info.value, ModelStepTimeoutError)
    assert exc_info.value.timeout == 75
    assert executor.await_count == 4  # initial attempt + max_retries=3
    assert sleep.await_count == 3

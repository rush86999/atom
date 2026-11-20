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

from core.llm.byok_handler import _CallerDeadlineExceeded
from core.workflow_engine import (
    AI_EXECUTION_SCOPE_KEY,
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


def _scoped_db_session():
    """A DB context whose scoped agent lookup returns an enabled row."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = db
    # Do not let the test double swallow the exception under test.
    context.__exit__.return_value = False
    return context


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service,executor_attr",
    [
        ("main_agent", "_execute_main_agent_action"),
        ("ai", "_execute_ai_action"),
    ],
)
async def test_timed_model_step_passes_absolute_caller_deadline(
    engine, service, executor_attr
):
    """The configured step timeout becomes the provider's absolute deadline."""
    executor = AsyncMock(return_value={"ok": True})
    setattr(engine, executor_attr, executor)
    step = {
        "id": "deadline-1",
        "service": service,
        "action": "generate_content",
        "timeout": 30,
        "parameters": {},
    }

    with patch("core.workflow_engine.time.monotonic", return_value=1000.0):
        result = await engine._execute_step(step, {})

    assert result["status"] == "success"
    executor.assert_awaited_once()
    call_kwargs = executor.await_args.kwargs
    assert call_kwargs["caller_deadline"] == 1030.0
    assert call_kwargs["step"] is step


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service,executor_attr",
    [
        ("main_agent", "_execute_main_agent_action"),
        ("ai", "_execute_ai_action"),
    ],
)
async def test_untimed_model_step_omits_caller_deadline(
    engine, service, executor_attr
):
    """No configured timeout keeps the historical executor call unchanged."""
    executor = AsyncMock(return_value={"ok": True})
    setattr(engine, executor_attr, executor)
    step = {
        "id": "deadline-2",
        "service": service,
        "action": "generate_content",
        "parameters": {},
    }

    await engine._execute_step(step, {})

    executor.assert_awaited_once()
    assert "caller_deadline" not in executor.await_args.kwargs


@pytest.mark.asyncio
async def test_timed_non_model_step_never_receives_caller_deadline(engine):
    """Only text-model dispatches opt in; integration calls stay unchanged."""
    executor = AsyncMock(return_value={"status": "success"})
    engine._execute_slack_action = executor
    step = {
        "id": "deadline-3",
        "service": "slack",
        "action": "post",
        "timeout": 30,
        "parameters": {},
    }

    await engine._execute_step(step, {})

    executor.assert_awaited_once()
    assert "caller_deadline" not in executor.await_args.kwargs


@pytest.mark.asyncio
async def test_timed_fallback_model_step_receives_its_own_caller_deadline(
    engine,
):
    """The fallback's configured timeout is also an absolute provider bound."""
    primary = AsyncMock(side_effect=RuntimeError("primary down"))
    fallback = AsyncMock(return_value={"ok": True})
    engine._execute_slack_action = primary
    engine._execute_ai_action = fallback
    step = {
        "id": "deadline-4",
        "service": "slack",
        "action": "generate_content",
        "fallback_service": "ai",
        "timeout": 40,
        "parameters": {},
    }

    with patch("core.workflow_engine.time.monotonic", return_value=500.0):
        result = await engine._execute_step(step, {})

    assert result["execution_method"] == "fallback_service"
    assert "caller_deadline" not in primary.await_args.kwargs
    assert fallback.await_args.kwargs["caller_deadline"] == 540.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service,executor_attr",
    [
        ("main_agent", "_execute_main_agent_action"),
        ("ai", "_execute_ai_action"),
    ],
)
async def test_caller_deadline_exceeded_becomes_typed_model_timeout(
    decorated_engine, service, executor_attr
):
    """The pre-dispatch refusal reaches the boundary and is translated once."""
    executor = AsyncMock(
        side_effect=_CallerDeadlineExceeded(
            "caller deadline expired before provider dispatch")
    )
    setattr(decorated_engine, executor_attr, executor)
    step = {
        "id": "deadline-5",
        "service": service,
        "action": "generate_content",
        "timeout": 75,
        "parameters": {},
    }

    with patch("core.auto_healing.asyncio.sleep", new=AsyncMock()) as sleep:
        with pytest.raises(ModelStepTimeoutError) as exc_info:
            await decorated_engine._execute_step(step, {})

    assert exc_info.value.timeout == 75
    assert exc_info.value.retryable is False
    assert "timed out after 75" in str(exc_info.value)
    executor.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_caller_deadline_exceeded_still_uses_configured_fallback(
    decorated_engine,
):
    """A primary deadline refusal keeps the existing fallback attempt."""
    primary = AsyncMock(
        side_effect=_CallerDeadlineExceeded(
            "caller deadline expired before provider dispatch")
    )
    fallback = AsyncMock(return_value={"ok": True})
    decorated_engine._execute_main_agent_action = primary
    decorated_engine._execute_slack_action = fallback
    step = {
        "id": "deadline-6",
        "service": "main_agent",
        "action": "generate_content",
        "fallback_service": "slack",
        "timeout": 75,
        "parameters": {},
    }

    with patch("core.auto_healing.asyncio.sleep", new=AsyncMock()) as sleep:
        result = await decorated_engine._execute_step(step, {})

    assert result["execution_method"] == "fallback_service"
    primary.assert_awaited_once()
    fallback.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_ai_action_forwards_deadline_and_preserves_original_messages(
    engine,
):
    """The ai executor forwards the boundary and keeps the caller's messages."""
    llm_service = MagicMock()
    llm_service.generate_completion = AsyncMock(
        side_effect=_CallerDeadlineExceeded("expired before dispatch")
    )
    step = {
        "id": "deadline-7",
        "service": "ai",
        "action": "generate_content",
        AI_EXECUTION_SCOPE_KEY: {
            "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
        },
    }

    with patch(
        "core.database.get_db_session", return_value=_scoped_db_session()
    ), patch(
        "core.llm_service.get_llm_service", return_value=llm_service
    ):
        with pytest.raises(_CallerDeadlineExceeded):
            await engine._execute_ai_action(
                "generate_content",
                {"prompt": "hello"},
                step=step,
                caller_deadline=321.0,
            )

    call_kwargs = llm_service.generate_completion.await_args.kwargs
    assert call_kwargs["caller_deadline"] == 321.0
    assert call_kwargs["messages"] == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_main_agent_action_forwards_deadline_and_preserves_original_messages(
    engine,
):
    """The scoped main_agent completion receives the same deadline and input."""
    llm_service = MagicMock()
    llm_service.generate_completion = AsyncMock(
        side_effect=_CallerDeadlineExceeded("expired before dispatch")
    )
    action = "run"
    params = {"agent_id": "agent-1", "input_data": {"q": "hello"}}
    step = {
        "id": "deadline-8",
        "service": "main_agent",
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
    }
    expected_prompt = f"""You are executing action: {action}

Input data:
{str(params['input_data'])}

Return your response in a clear, structured format."""

    with patch(
        "core.database.get_db_session", return_value=_scoped_db_session()
    ), patch(
        "core.llm_service.get_llm_service", return_value=llm_service
    ):
        with pytest.raises(_CallerDeadlineExceeded):
            await engine._execute_main_agent_action(
                action,
                params,
                step=step,
                caller_deadline=654.0,
            )

    call_kwargs = llm_service.generate_completion.await_args.kwargs
    assert call_kwargs["caller_deadline"] == 654.0
    assert call_kwargs["messages"] == [
        {"role": "user", "content": expected_prompt}
    ]


@pytest.mark.asyncio
async def test_ai_action_without_deadline_keeps_legacy_completion_call(engine):
    """An untimed step does not add the provider deadline keyword at all."""
    llm_service = MagicMock()
    llm_service.generate_completion = AsyncMock(
        return_value={
            "success": True,
            "content": "ok",
            "provider": "test",
            "model": "test-model",
        }
    )
    step = {
        "id": "deadline-9",
        "service": "ai",
        "action": "generate_content",
        AI_EXECUTION_SCOPE_KEY: {
            "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
        },
    }

    with patch(
        "core.database.get_db_session", return_value=_scoped_db_session()
    ), patch(
        "core.llm_service.get_llm_service", return_value=llm_service
    ):
        result = await engine._execute_ai_action(
            "generate_content", {"prompt": "hello"}, step=step
        )

    assert result["status"] == "success"
    assert "caller_deadline" not in (
        llm_service.generate_completion.await_args.kwargs
    )


@pytest.mark.asyncio
async def test_ai_action_translates_structured_deadline_failure(
    engine,
):
    """The ai executor forwards the boundary and keeps the caller's messages."""
    llm_service = MagicMock()
    llm_service.generate_completion = AsyncMock(
        return_value={"success": False, "failure": {"reason": "deadline_exceeded"}}
    )
    step = {
        "id": "deadline-7",
        "service": "ai",
        "action": "generate_content",
        AI_EXECUTION_SCOPE_KEY: {
            "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
        },
    }

    with patch(
        "core.database.get_db_session", return_value=_scoped_db_session()
    ), patch(
        "core.llm_service.get_llm_service", return_value=llm_service
    ):
        with pytest.raises(_CallerDeadlineExceeded):
            await engine._execute_ai_action(
                "generate_content",
                {"prompt": "hello"},
                step=step,
                caller_deadline=321.0,
            )

    call_kwargs = llm_service.generate_completion.await_args.kwargs
    assert call_kwargs["caller_deadline"] == 321.0
    assert call_kwargs["messages"] == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_main_agent_action_translates_structured_deadline_failure(
    engine,
):
    """The scoped main_agent completion receives the same deadline and input."""
    llm_service = MagicMock()
    llm_service.generate_completion = AsyncMock(
        return_value={"success": False, "failure": {"reason": "deadline_exceeded"}}
    )
    action = "run"
    params = {"agent_id": "agent-1", "input_data": {"q": "hello"}}
    step = {
        "id": "deadline-8",
        "service": "main_agent",
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
    }
    expected_prompt = f"""You are executing action: {action}

Input data:
{str(params['input_data'])}

Return your response in a clear, structured format."""

    with patch(
        "core.database.get_db_session", return_value=_scoped_db_session()
    ), patch(
        "core.llm_service.get_llm_service", return_value=llm_service
    ):
        with pytest.raises(_CallerDeadlineExceeded):
            await engine._execute_main_agent_action(
                action,
                params,
                step=step,
                caller_deadline=654.0,
            )

    call_kwargs = llm_service.generate_completion.await_args.kwargs
    assert call_kwargs["caller_deadline"] == 654.0
    assert call_kwargs["messages"] == [
        {"role": "user", "content": expected_prompt}
    ]

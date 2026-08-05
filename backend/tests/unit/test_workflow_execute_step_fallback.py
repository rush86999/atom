"""
TDD regression test: _execute_step raised ValueError when the primary service
was not in the registry AND generic catalog execution failed, never attempting
the configured fallback_service. A step with fallback_service must fall back
instead of crashing.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest

from core.workflow_engine import WorkflowEngine


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
async def test_unknown_service_no_fallback_returns_error(engine):
    """Unknown service with no fallback should return an error dict, not raise."""
    engine._execute_generic_action = AsyncMock(
        side_effect=ValueError("service not in catalog")
    )

    step = {
        "id": "s1",
        "service": "nonexistent_service",
        "action": "post",
        "parameters": {},
    }
    result = await engine._execute_step(step, {})

    assert result["status"] == "error"
    assert result["service"] == "nonexistent_service"

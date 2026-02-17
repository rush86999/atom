"""
Test helper functions for common test operations.

These helpers reduce test boilerplate and ensure consistent patterns
across the test suite.
"""

import asyncio
import uuid
from typing import Optional, Callable, Any
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus, Episode, CanvasAudit
from core.governance_cache import get_governance_cache


def create_test_agent(
    db_session: Session,
    name: str = "TestAgent",
    maturity: str = "STUDENT",
    confidence: float = 0.5,
    category: str = "test"
) -> AgentRegistry:
    """
    Create a test agent with specified parameters.

    Args:
        db_session: Database session
        name: Agent name
        maturity: Maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        confidence: Confidence score (0.0-1.0)
        category: Agent category

    Returns:
        Created AgentRegistry instance

    Usage:
        agent = create_test_agent(db_session, maturity="AUTONOMOUS", confidence=0.95)
    """
    agent = AgentRegistry(
        name=name,
        category=category,
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus[maturity].value,
        confidence_score=confidence,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def create_test_episode(
    db_session: Session,
    agent_id: str,
    title: str = "Test Episode"
) -> Episode:
    """
    Create a test episode for an agent.

    Args:
        db_session: Database session
        agent_id: Agent ID
        title: Episode title

    Returns:
        Created Episode instance

    Usage:
        episode = create_test_episode(db_session, agent_id="abc-123")
    """
    episode = Episode(
        agent_id=agent_id,
        title=title,
        description="Test episode created by helper",
        segment_count=0,
        total_duration_ms=0,
    )
    db_session.add(episode)
    db_session.commit()
    db_session.refresh(episode)
    return episode


def create_test_canvas(
    db_session: Session,
    agent_id: str,
    canvas_type: str = "generic"
) -> CanvasAudit:
    """
    Create a test canvas audit entry.

    Args:
        db_session: Database session
        agent_id: Agent ID
        canvas_type: Type of canvas (generic, docs, sheets, etc.)

    Returns:
        Created CanvasAudit instance

    Usage:
        canvas = create_test_canvas(db_session, agent_id="abc-123", canvas_type="sheets")
    """
    canvas = CanvasAudit(
        agent_id=agent_id,
        canvas_id=str(uuid.uuid4()),
        action="present",
        canvas_type=canvas_type,
        component_count=1,
    )
    db_session.add(canvas)
    db_session.commit()
    db_session.refresh(canvas)
    return canvas


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_message: str = "Condition not met within timeout"
) -> None:
    """
    Wait for a condition to become true.

    Args:
        condition: Callable that returns bool
        timeout: Maximum wait time in seconds
        interval: Check interval in seconds
        error_message: Error message if timeout exceeded

    Raises:
        TimeoutError: If condition not met within timeout

    Usage:
        await wait_for_condition(
            lambda: agent.status == "completed",
            timeout=10.0,
            error_message="Agent did not complete"
        )
    """
    start = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start) < timeout:
        if condition():
            return
        await asyncio.sleep(interval)
    raise TimeoutError(error_message)


def mock_websocket():
    """
    Create a mock WebSocket for testing real-time features.

    Returns:
        MagicMock with async methods mocked

    Usage:
        ws = mock_websocket()
        await ws.send_text("message")
        assert ws.send_text.called
    """
    ws = MagicMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    return ws


def mock_byok_handler():
    """
    Create a mock BYOK handler for LLM operations.

    Returns:
        AsyncMock with common LLM methods

    Usage:
        handler = mock_byok_handler()
        response = await handler.complete("test prompt")
        assert response == "Mock LLM response"
    """
    handler = AsyncMock()
    handler.complete = AsyncMock(return_value="Mock LLM response")
    handler.stream = AsyncMock(return_value=["Mock", " response"])
    return handler


def clear_governance_cache(agent_id: Optional[str] = None) -> None:
    """
    Clear governance cache for an agent or all agents.

    Args:
        agent_id: Specific agent ID to clear, or None for all

    Usage:
        clear_governance_cache()  # Clear all
        clear_governance_cache(agent_id="abc-123")  # Clear specific agent
    """
    cache = get_governance_cache()
    if agent_id:
        cache.invalidate_agent(agent_id)
    else:
        # Clear all cache entries
        cache._cache.clear()
        cache._hits = 0
        cache._misses = 0

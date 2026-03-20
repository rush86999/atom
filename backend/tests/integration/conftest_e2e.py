"""
E2E test fixtures for agent execution workflow tests.

Provides specialized fixtures for end-to-end testing of agent execution
including LLM streaming mocks, WebSocket mocks, and database cleanup.
"""

import os
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session
from sqlalchemy import text

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.factories.agent_factory import (
    AgentFactory,
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)
from core.models import AgentRegistry, AgentExecution, AgentEpisode, EpisodeSegment


@pytest.fixture(scope="function")
def e2e_db_session(db_session: Session):
    """
    E2E database session with aggressive cleanup.

    Cleans up all E2E test data after each test to prevent cross-test contamination.
    """
    yield db_session

    # Aggressive cleanup for E2E tests
    try:
        # Clean up in order of dependencies
        db_session.execute(text("DELETE FROM episode_segments WHERE 1=1"))
        db_session.execute(text("DELETE FROM agent_episodes WHERE agent_id LIKE 'test-agent%'"))
        db_session.execute(text("DELETE FROM agent_executions WHERE agent_id LIKE 'test-agent%'"))
        db_session.execute(text("DELETE FROM agent_registry WHERE id LIKE 'test-agent%'"))
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        print(f"E2E cleanup error: {e}")


@pytest.fixture(scope="function")
def mock_llm_streaming():
    """
    Mock LLM streaming response for E2E tests.

    Returns an async generator that yields streaming chunks.
    """
    async def stream_completion(*args, **kwargs):
        """Mock streaming completion with test response."""
        chunks = [
            "Test ",
            "response ",
            "chunk 1",
            "Test ",
            "response ",
            "chunk 2",
            "Test ",
            "response ",
            "chunk 3"
        ]
        for chunk in chunks:
            yield {
                "choices": [{
                    "delta": {"content": chunk},
                    "finish_reason": None
                }],
                "usage": None
            }
        # Final chunk with finish_reason
        yield {
            "choices": [{
                "delta": {},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }

    return stream_completion


@pytest.fixture(scope="function")
def mock_llm_streaming_error():
    """
    Mock LLM streaming error for E2E error path tests.
    """
    async def stream_completion_error(*args, **kwargs):
        """Mock streaming completion with error."""
        yield {
            "choices": [{
                "delta": {"content": "Initial chunk"},
                "finish_reason": None
            }],
            "usage": None
        }
        # Simulate LLM API error
        raise Exception("LLM API error: rate limit exceeded")

    return stream_completion_error


@pytest.fixture(scope="function")
def mock_websocket():
    """
    Mock WebSocket manager for E2E tests.

    Mocks WebSocket notifications for agent status updates and execution events.
    """
    with patch('core.governance_cache.WebSocketManager') as mock_ws_class:
        mock_ws_instance = MagicMock()
        mock_ws_instance.notify_agent_status = MagicMock()
        mock_ws_instance.notify_execution_start = MagicMock()
        mock_ws_instance.notify_execution_complete = MagicMock()
        mock_ws_instance.notify_execution_failed = MagicMock()
        mock_ws_class.return_value = mock_ws_instance
        yield mock_ws_instance


@pytest.fixture(scope="function")
def e2e_client(client, e2e_db_session, mock_websocket):
    """
    E2E test client with all necessary mocks.

    Combines TestClient with database session, WebSocket mocks,
    and authentication bypass for comprehensive E2E testing.
    """
    yield client


@pytest.fixture(scope="function")
def execution_id():
    """
    Generate unique execution ID for E2E tests.
    """
    return str(uuid.uuid4())


# E2E Test Helpers

def assert_episode_created(db_session: Session, agent_id: str, expected_count: int = 1):
    """
    Assert that episodes were created for agent execution.

    Args:
        db_session: Database session
        agent_id: Agent ID to check
        expected_count: Expected number of episodes (default: 1)
    """
    episodes = db_session.query(AgentEpisode).filter(
        AgentEpisode.agent_id == agent_id
    ).all()
    assert len(episodes) == expected_count, f"Expected {expected_count} episodes, got {len(episodes)}"
    return episodes


def assert_execution_logged(db_session: Session, execution_id: str, expected_status: str = "completed"):
    """
    Assert that execution was logged with expected status.

    Args:
        db_session: Database session
        execution_id: Execution ID to check
        expected_status: Expected execution status (default: "completed")
    """
    execution = db_session.query(AgentExecution).filter(
        AgentExecution.id == execution_id
    ).first()
    assert execution is not None, f"Execution {execution_id} not found"
    assert execution.status == expected_status, f"Expected status {expected_status}, got {execution.status}"
    return execution


def assert_segments_created(db_session: Session, episode_id: str, min_count: int = 1):
    """
    Assert that episode segments were created.

    Args:
        db_session: Database session
        episode_id: Episode ID to check
        min_count: Minimum number of segments expected (default: 1)
    """
    segments = db_session.query(EpisodeSegment).filter(
        EpisodeSegment.episode_id == episode_id
    ).all()
    assert len(segments) >= min_count, f"Expected at least {min_count} segments, got {len(segments)}"
    return segments

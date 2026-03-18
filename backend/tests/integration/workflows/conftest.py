"""
Shared fixtures for workflow integration tests.

Provides database sessions, mock LLM providers, mock WebSocket managers,
and sample workflow/episode data for integration testing.

Key principles:
- Real database (SQLite in-memory) for persistence testing
- Mocked external services (LLM providers, WebSocket) to prevent flakiness
- Transaction rollback after each test for isolation
"""

import os
import pytest
import tempfile
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.database import Base
from core.models import (
    WorkflowExecution, WorkflowExecutionStatus,
    AgentEpisode, EpisodeSegment, EpisodeOutcome,
    ChatSession, CanvasAudit, AgentFeedback
)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for each test.

    Uses SQLite in-memory database with transaction rollback for test isolation.
    All tables are created before the test and cleaned up after.
    """
    # Use in-memory SQLite for tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create all tables
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception as e:
        # If create_all fails, create tables individually
        for table in Base.metadata.tables.values():
            try:
                table.create(engine, checkfirst=True)
            except Exception:
                continue

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()


@pytest.fixture(scope="function")
def mock_llm_provider():
    """
    AsyncMock for LLM provider calls.

    Mocks both call_llm() and stream_llm() methods to prevent
    external API calls during testing.
    """
    mock_provider = AsyncMock()

    # Mock call_llm to return success response
    async def mock_call_llm(*args, **kwargs):
        return {
            "result": "success",
            "content": "Mock LLM response",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }

    # Mock stream_llm to return async generator
    async def mock_stream_llm(*args, **kwargs):
        chunks = [
            {"choices": [{"delta": {"content": "Mock "}, "finish_reason": None}], "usage": None},
            {"choices": [{"delta": {"content": "streaming "}, "finish_reason": None}], "usage": None},
            {"choices": [{"delta": {"content": "response"}, "finish_reason": None}], "usage": None},
            {"choices": [{"delta": {}, "finish_reason": "stop"}],
             "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}
        ]
        for chunk in chunks:
            yield chunk

    mock_provider.call_llm = mock_call_llm
    mock_provider.stream_llm = mock_stream_llm

    return mock_provider


@pytest.fixture(scope="function")
def mock_websocket_manager():
    """
    MagicMock for WebSocket notifications.

    Tracks all WebSocket calls for verification in tests.
    """
    mock_ws = MagicMock()

    # Mock notification methods
    mock_ws.notify_workflow_status = AsyncMock()
    mock_ws.broadcast_message = AsyncMock()
    mock_ws.send_message = AsyncMock()

    # Track calls for verification
    mock_ws.reset_mock()

    return mock_ws


@pytest.fixture(scope="function")
def sample_workflow():
    """
    Valid workflow definitions for tests.

    Returns a dict with three workflow variations:
    - simple: 2-step linear execution
    - branching: if/else conditional logic
    - error_handling: try/catch error recovery
    """
    return {
        "simple": {
            "id": "simple_workflow",
            "nodes": [
                {
                    "id": "step1",
                    "title": "First Step",
                    "type": "action",
                    "config": {
                        "action": "collect_data",
                        "service": "data_service",
                        "parameters": {"source": "api"}
                    }
                },
                {
                    "id": "step2",
                    "title": "Second Step",
                    "type": "action",
                    "config": {
                        "action": "process_data",
                        "service": "processing_service",
                        "parameters": {"mode": "batch"}
                    }
                }
            ],
            "connections": [
                {"source": "step1", "target": "step2"}
            ]
        },
        "branching": {
            "id": "branching_workflow",
            "nodes": [
                {
                    "id": "step1",
                    "title": "Evaluate Condition",
                    "type": "action",
                    "config": {
                        "action": "evaluate",
                        "service": "logic_service",
                        "parameters": {}
                    }
                },
                {
                    "id": "true_branch",
                    "title": "True Branch",
                    "type": "action",
                    "config": {
                        "action": "handle_true",
                        "service": "logic_service",
                        "parameters": {"branch": "true"}
                    }
                },
                {
                    "id": "false_branch",
                    "title": "False Branch",
                    "type": "action",
                    "config": {
                        "action": "handle_false",
                        "service": "logic_service",
                        "parameters": {"branch": "false"}
                    }
                }
            ],
            "connections": [
                {"source": "step1", "target": "true_branch", "condition": "${step1.result} == true"},
                {"source": "step1", "target": "false_branch", "condition": "${step1.result} == false"}
            ]
        },
        "error_handling": {
            "id": "error_handling_workflow",
            "nodes": [
                {
                    "id": "step1",
                    "title": "Risky Step",
                    "type": "action",
                    "config": {
                        "action": "risky_operation",
                        "service": "risky_service",
                        "parameters": {"continue_on_error": True}
                    }
                },
                {
                    "id": "step2",
                    "title": "Recovery Step",
                    "type": "action",
                    "config": {
                        "action": "recover",
                        "service": "recovery_service",
                        "parameters": {}
                    }
                }
            ],
            "connections": [
                {"source": "step1", "target": "step2"}
            ]
        }
    }


@pytest.fixture(scope="function")
def sample_episode_context(db_session: Session):
    """
    Episode context for segmentation tests.

    Creates a realistic episode context with:
    - ChatSession with messages
    - Canvas presentation events
    - User feedback data
    """
    # Create ChatSession with messages
    chat_session = ChatSession(
        id=str(uuid.uuid4()),
        agent_id="test_agent",
        user_id="test_user",
        title="Test Episode Session",
        status="active"
    )
    db_session.add(chat_session)

    # Create sample canvas presentation
    canvas_audit = CanvasAudit(
        id=str(uuid.uuid4()),
        canvas_id="test_canvas_123",
        canvas_type="line_chart",
        agent_id="test_agent",
        user_id="test_user",
        session_id=chat_session.id,
        title="Sales Performance Chart",
        config={"data": [1, 2, 3, 4, 5]},
        status="presented"
    )
    db_session.add(canvas_audit)

    # Create sample user feedback
    agent_feedback = AgentFeedback(
        id=str(uuid.uuid4()),
        agent_id="test_agent",
        user_id="test_user",
        session_id=chat_session.id,
        feedback_type="thumbs_up",
        feedback_value=1.0,
        comment="Great analysis!"
    )
    db_session.add(agent_feedback)

    db_session.commit()

    return {
        "chat_session": chat_session,
        "canvas_audit": canvas_audit,
        "agent_feedback": agent_feedback,
        "messages": [
            {
                "role": "user",
                "content": "Show me the sales data",
                "timestamp": datetime.utcnow() - timedelta(minutes=10)
            },
            {
                "role": "assistant",
                "content": "Here's the sales performance chart",
                "timestamp": datetime.utcnow() - timedelta(minutes=9),
                "canvas_id": canvas_audit.canvas_id
            },
            {
                "role": "user",
                "content": "Great analysis!",
                "timestamp": datetime.utcnow() - timedelta(minutes=8),
                "feedback_id": agent_feedback.id
            }
        ]
    }


@pytest.fixture(scope="function")
def sample_episode(db_session: Session):
    """
    Create a sample AgentEpisode with segments for testing.

    Returns an episode with 3 segments representing a simple workflow.
    """
    episode_id = str(uuid.uuid4())

    episode = AgentEpisode(
        id=episode_id,
        agent_id="test_agent",
        user_id="test_user",
        workflow_id="test_workflow",
        outcome=EpisodeOutcome.SUCCESS,
        title="Test Episode",
        summary="Test episode with multiple segments",
        start_time=datetime.utcnow() - timedelta(minutes=10),
        end_time=datetime.utcnow()
    )
    db_session.add(episode)

    # Create segments
    segment1 = EpisodeSegment(
        id=str(uuid.uuid4()),
        episode_id=episode_id,
        segment_type="action",
        title="Data Collection",
        content="Collected data from API",
        start_time=datetime.utcnow() - timedelta(minutes=10),
        end_time=datetime.utcnow() - timedelta(minutes=8),
        metadata={"action": "collect_data", "source": "api"}
    )
    db_session.add(segment1)

    segment2 = EpisodeSegment(
        id=str(uuid.uuid4()),
        episode_id=episode_id,
        segment_type="action",
        title="Data Processing",
        content="Processed data in batch mode",
        start_time=datetime.utcnow() - timedelta(minutes=8),
        end_time=datetime.utcnow() - timedelta(minutes=5),
        metadata={"action": "process_data", "mode": "batch"}
    )
    db_session.add(segment2)

    segment3 = EpisodeSegment(
        id=str(uuid.uuid4()),
        episode_id=episode_id,
        segment_type="result",
        title="Result Presentation",
        content="Presented results to user",
        start_time=datetime.utcnow() - timedelta(minutes=5),
        end_time=datetime.utcnow(),
        metadata={"action": "present_results"}
    )
    db_session.add(segment3)

    db_session.commit()

    return {
        "episode": episode,
        "segments": [segment1, segment2, segment3]
    }

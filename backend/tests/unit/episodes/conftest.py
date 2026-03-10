"""
Episode service test fixtures.

Provides fixtures for comprehensive episode creation flow testing.
"""

import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import Session, sessionmaker

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.database import Base
from core.models import (
    AgentExecution,
    AgentFeedback,
    AgentRegistry,
    AgentStatus,
    CanvasAudit,
    ChatMessage,
    ChatSession,
    Episode,
    EpisodeSegment,
    SupervisionSession,
    SupervisionStatus,
    User,
)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for each test.

    This ensures complete isolation between test runs by using a
    temporary SQLite database file that is deleted after each test.
    Each test gets its own database, preventing UNIQUE constraint violations
    and state leakage between tests.
    """
    # Use file-based temp SQLite for tests to ensure all connections see the same database
    # In-memory SQLite (:memory:) creates a separate database for each connection
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)  # Close the file descriptor, we just need the path

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create all tables, handling missing foreign key references from optional modules
    # Same approach as property_tests conftest.py
    tables_created = 0
    tables_skipped = 0
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
            tables_created += 1
        except exc.NoReferencedTableError:
            # Skip tables with missing FK references (from optional modules)
            tables_skipped += 1
            continue
        except (exc.CompileError, exc.UnsupportedCompilationError):
            # Skip tables with unsupported types (JSONB in SQLite)
            tables_skipped += 1
            continue
        except Exception as e:
            # Ignore duplicate table/index errors
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                continue
            else:
                raise

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    # Delete temp database file
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except Exception:
            pass  # File might already be deleted


@pytest.fixture
def episode_test_user(db_session):
    """Test user fixture for episode testing."""
    user_id = "test_user"
    user = User(
        id=user_id,
        email="test@example.com",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def episode_test_session(db_session, episode_test_user):
    """Test chat session fixture for episode testing."""
    session_id = str(uuid.uuid4())
    session = ChatSession(
        id=session_id,
        user_id=episode_test_user.id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    db_session.add(session)
    db_session.commit()
    return session


@pytest.fixture
def episode_test_messages(episode_test_session):
    """Test messages fixture with varying timestamps (no gaps > 30 min)."""
    now = datetime.now(timezone.utc)
    session_id = episode_test_session.id

    messages = [
        ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=session_id,
            role="user",
            content="Hello, I need help with data analysis",
            created_at=now - timedelta(minutes=55)
        ),
        ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=session_id,
            role="assistant",
            content="I can help you with that. What data do you have?",
            created_at=now - timedelta(minutes=50)
        ),
        ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=session_id,
            role="user",
            content="I have sales data for Q4 2025",
            created_at=now - timedelta(minutes=45)
        ),
        ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=session_id,
            role="assistant",
            content="Great! Let's analyze your sales data",
            created_at=now - timedelta(minutes=40)
        ),
        ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=session_id,
            role="user",
            content="Please create a chart showing revenue trends",
            created_at=now - timedelta(minutes=35)
        ),
    ]
    return messages


@pytest.fixture
def episode_test_executions(episode_test_session):
    """Test agent executions fixture for episode testing."""
    now = datetime.now(timezone.utc)
    agent_id = str(uuid.uuid4())

    executions = [
        AgentExecution(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            status="completed",
            task_description="Analyze sales data",
            result_summary="Analysis completed successfully",
            started_at=now - timedelta(minutes=48),
            completed_at=now - timedelta(minutes=45)
        ),
        AgentExecution(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            status="completed",
            task_description="Create revenue chart",
            result_summary="Chart generated",
            started_at=now - timedelta(minutes=38),
            completed_at=now - timedelta(minutes=35)
        ),
    ]
    return executions


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler for episode testing."""
    lancedb = MagicMock()
    lancedb.embed_text = MagicMock(return_value=[0.1, 0.2, 0.3])
    lancedb.search = MagicMock(return_value=[])
    lancedb.add_document = MagicMock()
    lancedb.create_table = MagicMock()
    lancedb.db = MagicMock()
    lancedb.db.table_names = MagicMock(return_value=[])
    return lancedb


@pytest.fixture
def mock_byok_handler():
    """Mock BYOK handler for episode testing."""
    handler = MagicMock()
    return handler


@pytest.fixture
def segmentation_service(db_session, mock_lancedb, mock_byok_handler):
    """EpisodeSegmentationService fixture with mocked dependencies."""
    with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb):
        with patch('core.episode_segmentation_service.CanvasSummaryService'):
            from core.episode_segmentation_service import EpisodeSegmentationService

            service = EpisodeSegmentationService(db_session, mock_byok_handler)
            service.lancedb = mock_lancedb
            return service


@pytest.fixture
def segmentation_service_mocked(db_session, mock_lancedb, mock_byok_handler):
    """EpisodeSegmentationService with mocked CanvasSummaryService."""
    with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb):
        with patch('core.episode_segmentation_service.CanvasSummaryService') as mock_canvas_svc:
            from core.episode_segmentation_service import EpisodeSegmentationService

            # Mock generate_summary to return test summary
            mock_canvas_svc.return_value.generate_summary = AsyncMock(return_value="Test canvas summary")

            service = EpisodeSegmentationService(db_session, mock_byok_handler)
            service.lancedb = mock_lancedb
            return service


@pytest.fixture
def episode_test_canvas_audit(episode_test_session):
    """Test canvas audit fixture for episode testing."""
    now = datetime.now(timezone.utc)
    canvas = CanvasAudit(
        id=str(uuid.uuid4()),
        session_id=episode_test_session.id,
        canvas_type="sheets",
        action="present",
        component_name="sales_table",
        audit_metadata={
            "revenue": 1000000,
            "approval_status": "approved"
        },
        created_at=now - timedelta(minutes=42)
    )
    return canvas


@pytest.fixture
def episode_test_feedback(episode_test_session, episode_test_executions):
    """Test agent feedback fixture for episode testing."""
    now = datetime.now(timezone.utc)
    execution_id = episode_test_executions[0].id

    feedback = AgentFeedback(
        id=str(uuid.uuid4()),
        agent_id=episode_test_executions[0].agent_id,
        agent_execution_id=execution_id,
        user_id="test_user",
        original_output="Analysis complete",
        user_correction="Great analysis",
        feedback_type="thumbs_up",
        thumbs_up_down=True,
        rating=5,
        created_at=now - timedelta(minutes=44)
    )
    return feedback


@pytest.fixture
def episode_test_supervision_session():
    """SupervisionSession instance for testing"""
    now = datetime.now(timezone.utc)
    session = SupervisionSession(
        id=str(uuid.uuid4()),
        agent_id="test_agent",
        agent_name="TestAgent",
        supervisor_id="test_supervisor",
        workspace_id="default",
        status=SupervisionStatus.COMPLETED.value,
        supervisor_rating=4,
        intervention_count=2,
        interventions=[
            {
                "type": "human_correction",
                "timestamp": "2026-03-10T10:00:00Z",
                "guidance": "Fix the calculation error"
            },
            {
                "type": "guidance",
                "timestamp": "2026-03-10T10:05:00Z",
                "guidance": "Use proper validation"
            }
        ],
        supervisor_feedback="Good performance overall",
        started_at=now - timedelta(hours=1),
        completed_at=now,
        duration_seconds=3600,
        trigger_context={},
        tenant_id="test_tenant"
    )
    return session


@pytest.fixture
def episode_test_agent_execution():
    """AgentExecution instance for testing"""
    execution = AgentExecution(
        id=str(uuid.uuid4()),
        agent_id="test_agent",
        status="completed",
        input_summary="Dataset: sales_2024.csv, Format: json",
        result_summary="Total: $1,000,000, Records: 500",
        started_at=datetime.now(timezone.utc) - timedelta(hours=1),
        completed_at=datetime.now(timezone.utc),
        duration_seconds=3600,
        triggered_by="manual"
    )
    return execution


@pytest.fixture
def episode_test_skill_execution():
    """Dict representing successful skill execution"""
    return {
        "skill_name": "data_analyzer",
        "inputs": {
            "dataset": "sales_2024.csv",
            "format": "json"
        },
        "result": {
            "total": 1000000,
            "records": 500
        },
        "error": None,
        "execution_time": 1.5
    }


@pytest.fixture
def episode_test_failed_skill_execution():
    """Dict representing failed skill execution"""
    return {
        "skill_name": "email_sender",
        "inputs": {
            "to": "user@example.com",
            "subject": "Test"
        },
        "result": None,
        "error": Exception("SMTP connection failed"),
        "execution_time": 0.5
    }


@pytest.fixture
def episode_test_supervision_session_multiple_interventions():
    """SupervisionSession with multiple intervention types"""
    now = datetime.now(timezone.utc)
    session = SupervisionSession(
        id=str(uuid.uuid4()),
        agent_id="test_agent",
        agent_name="TestAgent",
        supervisor_id="test_supervisor",
        workspace_id="default",
        status=SupervisionStatus.COMPLETED.value,
        supervisor_rating=3,
        intervention_count=3,
        interventions=[
            {
                "type": "human_correction",
                "timestamp": "2026-03-10T10:00:00Z",
                "guidance": "Fix the error"
            },
            {
                "type": "guidance",
                "timestamp": "2026-03-10T10:05:00Z",
                "guidance": "Improve formatting"
            },
            {
                "type": "termination",
                "timestamp": "2026-03-10T10:10:00Z",
                "guidance": "Stop execution"
            }
        ],
        supervisor_feedback="Too many interventions needed",
        started_at=now - timedelta(hours=1),
        completed_at=now,
        duration_seconds=3600,
        trigger_context={},
        tenant_id="test_tenant"
    )
    return session


@pytest.fixture
def episode_test_agent():
    """
    Create a test agent for episode service tests.

    Returns an AgentRegistry instance with AUTONOMOUS status
    for use in episode creation and retrieval tests.
    """
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name="TestAgent",
        description="Test agent for episode service tests",
        category="Testing",
        status=AgentStatus.AUTONOMOUS.value,
        tenant_id="default",
        module_path="tests.test_agent",
        class_name="TestAgent",
        created_at=datetime.now(timezone.utc)
    )
    return agent


@pytest.fixture
def lifecycle_service(db_session, mock_lancedb):
    """
    EpisodeLifecycleService fixture with mocked LanceDB.

    Patches get_lancedb_handler to return mock_lancedb fixture.
    Use for tests that need lifecycle service with mocked dependencies.
    """
    from core.episode_lifecycle_service import EpisodeLifecycleService

    with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=mock_lancedb):
        service = EpisodeLifecycleService(db_session)
        # Note: lancedb is assigned in __init__, but we patch the getter
        return service


@pytest.fixture
def lifecycle_service_mocked(db_session, mock_lancedb):
    """
    EpisodeLifecycleService fixture with directly assigned mock LanceDB.

    Use for tests that need to override mock_lancedb return values
    (e.g., custom search results, embedding vectors).
    """
    from core.episode_lifecycle_service import EpisodeLifecycleService

    service = EpisodeLifecycleService(db_session)
    service.lancedb = mock_lancedb
    return service

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
            input_summary="Analyze sales data",
            result_summary="Analysis completed successfully",
            started_at=now - timedelta(minutes=48),
            completed_at=now - timedelta(minutes=45)
        ),
        AgentExecution(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            status="completed",
            input_summary="Create revenue chart",
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
        canvas_id=str(uuid.uuid4()),  # FK to canvases.id
        tenant_id="default",
        action_type="present",
        user_id=episode_test_session.user_id,
        details_json={
            "canvas_type": "sheets",
            "component_name": "sales_table",
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


@pytest.fixture
def retrieval_service(db_session, mock_lancedb):
    """
    EpisodeRetrievalService fixture with mocked dependencies.

    Patches get_lancedb_handler to return mock_lancedb and patches
    AgentGovernanceService to return governance check with allowed=True.
    """
    from core.episode_retrieval_service import EpisodeRetrievalService

    with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=mock_lancedb):
        with patch('core.episode_retrieval_service.AgentGovernanceService') as mock_gov:
            # Mock governance to always allow
            mock_gov_instance = MagicMock()
            mock_gov_instance.can_perform_action = MagicMock(return_value={"allowed": True})
            mock_gov.return_value = mock_gov_instance

            service = EpisodeRetrievalService(db_session)
            service.lancedb = mock_lancedb
            service.governance = mock_gov_instance
            return service


@pytest.fixture
def retrieval_service_mocked(db_session, mock_lancedb):
    """
    EpisodeRetrievalService fixture with directly assigned mock LanceDB.

    Same as retrieval_service but assigns service.lancedb = mock_lancedb
    for tests that need to override mock return values.
    """
    from core.episode_retrieval_service import EpisodeRetrievalService

    with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=mock_lancedb):
        with patch('core.episode_retrieval_service.AgentGovernanceService') as mock_gov:
            # Mock governance to always allow
            mock_gov_instance = MagicMock()
            mock_gov_instance.can_perform_action = MagicMock(return_value={"allowed": True})
            mock_gov.return_value = mock_gov_instance

            service = EpisodeRetrievalService(db_session)
            service.lancedb = mock_lancedb
            service.governance = mock_gov_instance
            return service


@pytest.fixture
def episode_test_data(db_session, episode_test_agent):
    """
    Creates test episode with segments for retrieval testing.

    Returns:
        dict: Episode ID, agent ID, and list of segment IDs
    """
    now = datetime.now(timezone.utc)
    agent_id = episode_test_agent.id

    # Create episode
    episode = Episode(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        tenant_id="default",
        task_description="Test episode for retrieval",
        status="completed",
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
        maturity_at_time="INTERN",
        human_intervention_count=0,
        constitutional_score=0.85,
        decay_score=1.0,
        access_count=1,
        canvas_action_count=2,
        canvas_ids=[],
        feedback_ids=[]
    )
    db_session.add(episode)
    db_session.commit()

    # Create 3 segments
    segments = []
    for i in range(3):
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=i,
            content=f"Segment {i} content",
            content_summary=f"Segment {i} summary",
            source_type="chat_message",
            source_id=f"msg_{i}",
            created_at=now - timedelta(hours=2) + timedelta(minutes=i*10)
        )
        db_session.add(segment)
        segments.append(segment)

    # Create 2 CanvasAudit records with episode_id
    canvas_ids = []
    for i in range(2):
        canvas = CanvasAudit(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            session_id=str(uuid.uuid4()),
            canvas_type="sheets" if i == 0 else "charts",
            component_type="table" if i == 0 else "chart",
            component_name=f"component_{i}",
            action="present",
            audit_metadata={"test": f"data_{i}"},
            created_at=now - timedelta(hours=1) + timedelta(minutes=i*15)
        )
        db_session.add(canvas)
        canvas_ids.append(canvas.id)

    # Create 1 AgentFeedback record with episode_id
    feedback = AgentFeedback(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        user_id="test_user",
        feedback_type="thumbs_up",
        thumbs_up_down=True,
        rating=5,
        created_at=now - timedelta(minutes=30)
    )
    db_session.add(feedback)

    db_session.commit()

    return {
        "episode_id": episode.id,
        "agent_id": agent_id,
        "segment_ids": [s.id for s in segments],
        "canvas_ids": canvas_ids,
        "feedback_id": feedback.id
    }


@pytest.fixture
def episode_with_canvas_context(db_session, episode_test_agent):
    """
    Creates episode with canvas context for retrieval testing.

    Returns:
        Episode: Episode with canvas_action_count and canvas_context
    """
    now = datetime.now(timezone.utc)

    episode = Episode(
        id=str(uuid.uuid4()),
        agent_id=episode_test_agent.id,
        tenant_id="default",
        task_description="Episode with canvas context",
        status="completed",
        started_at=now - timedelta(hours=1),
        completed_at=now,
        maturity_at_time="INTERN",
        human_intervention_count=0,
        constitutional_score=0.9,
        decay_score=1.0,
        access_count=2,
        canvas_action_count=2,
        canvas_ids=[],
        feedback_ids=[]
    )

    # Create CanvasAudit with canvas_type="sheets"
    canvas = CanvasAudit(
        id=str(uuid.uuid4()),
        episode_id=episode.id,
        session_id=str(uuid.uuid4()),
        canvas_type="sheets",
        component_type="table",
        component_name="sales_table",
        action="submit",
        audit_metadata={"revenue": 1000000, "approval": "approved"},
        created_at=now - timedelta(minutes=30)
    )
    db_session.add(canvas)
    db_session.add(episode)
    db_session.commit()

    # Create EpisodeSegment with canvas_context dict
    segment = EpisodeSegment(
        id=str(uuid.uuid4()),
        episode_id=episode.id,
        segment_type="canvas_presentation",
        sequence_order=0,
        content="Presented sales data",
        content_summary="Sales table presentation",
        source_type="canvas",
        source_id=canvas.id,
        canvas_context={
            "canvas_type": "sheets",
            "presentation_summary": "Sales data for Q4 2025",
            "critical_data_points": {"revenue": 1000000, "approval_status": "approved"},
            "visual_elements": {"rows": 100, "columns": 5}
        },
        created_at=now - timedelta(minutes=30)
    )
    db_session.add(segment)
    db_session.commit()

    return episode


@pytest.fixture
def episode_with_supervision(db_session, episode_test_agent):
    """
    Creates episode with supervision context for retrieval testing.

    Returns:
        Episode: Episode with supervision fields populated
    """
    now = datetime.now(timezone.utc)

    episode = Episode(
        id=str(uuid.uuid4()),
        agent_id=episode_test_agent.id,
        tenant_id="default",
        task_description="Supervised episode",
        status="completed",
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
        maturity_at_time="SUPERVISED",
        human_intervention_count=1,
        constitutional_score=0.85,
        decay_score=0.95,
        access_count=3,
        canvas_action_count=0,
        canvas_ids=[],
        feedback_ids=[],
        # Supervision fields
        supervisor_id="supervisor_123",
        supervisor_rating=4,
        intervention_count=1,
        intervention_types=["human_correction"],
        supervision_feedback="Good performance, minor corrections needed"
    )

    db_session.add(episode)
    db_session.commit()

    return episode

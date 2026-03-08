"""
Integration test fixtures for LLM service coverage tests.

Provides BYOK handler fixtures for testing provider routing,
cognitive tier classification, and token counting.
"""

import os
import pytest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
import tempfile

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.llm.byok_handler import BYOKHandler


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for each test.

    Simplified version that avoids sorted_tables to prevent NoReferencedTableError
    when running multiple tests in sequence.
    """
    # Use file-based temp SQLite for tests
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create ONLY the tables we need for governance testing
    # This avoids SQLAlchemy mapper configuration issues with unrelated models
    from core.database import Base

    tables_to_create = [
        'users',
        'agent_registry',
        'agent_feedback',
        'hitl_actions',
    ]

    for table_name in tables_to_create:
        if table_name in Base.metadata.tables:
            try:
                Base.metadata.tables[table_name].create(engine, checkfirst=True)
            except Exception as e:
                print(f"Warning: Could not create table {table_name}: {e}")

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
            pass


@pytest.fixture(scope="function")
def byok_handler(db_session: Session):
    """
    Create BYOKHandler instance for testing.

    Mocks environment variables for API keys to avoid external dependencies.
    Returns handler instance with test workspace_id.
    """
    # Mock environment variables for API keys (not actually used in tests)
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'sk-test-openai',
        'ANTHROPIC_API_KEY': 'sk-test-anthropic',
        'DEEPSEEK_API_KEY': 'sk-test-deepseek',
    }):
        # Create handler instance
        handler = BYOKHandler(workspace_id="test")

        yield handler

        # Cleanup if needed
        if hasattr(handler, 'db_session') and handler.db_session:
            try:
                handler.db_session.close()
            except Exception:
                pass


@pytest.fixture(scope="function")
def sample_prompt():
    """Sample prompt for testing."""
    return "What is the capital of France?"


@pytest.fixture(scope="function")
def sample_code_prompt():
    """Sample code prompt for testing."""
    return "Write a Python function to calculate fibonacci numbers"


@pytest.fixture(scope="function")
def sample_complex_prompt():
    """Sample complex prompt for testing."""
    return "Analyze the economic implications of quantum computing on cryptocurrency markets"


# =============================================================================
# Episode Service Fixtures
# =============================================================================

from datetime import datetime, timezone, timedelta
from uuid import uuid4
from core.database import SessionLocal
from core.episode_segmentation_service import EpisodeSegmentationService
from core.episode_retrieval_service import EpisodeRetrievalService
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import (
    AgentEpisode,  # Use AgentEpisode instead of Episode
    EpisodeSegment,
    ChatSession,
    ChatMessage,
    CanvasAudit,
    AgentFeedback,
    AgentRegistry,
    User,
)

# Alias for compatibility with service code that imports Episode
Episode = AgentEpisode


@pytest.fixture(scope="function")
def episode_db_session():
    """
    Create fresh database session for episode tests.

    Uses SessionLocal with automatic rollback to ensure test isolation.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(scope="function")
def segmentation_service_mocked(episode_db_session):
    """
    Create EpisodeSegmentationService instance with mocked LanceDB.

    Mocks embed_text to return test vectors for semantic similarity testing.
    """
    # Mock LanceDB handler
    mock_lancedb = Mock()
    mock_lancedb.embed_text.return_value = [0.9, 0.1, 0.0]  # Default test vector
    mock_lancedb.search.return_value = []  # Default empty search results
    mock_lancedb.db = Mock()  # Mock database connection
    mock_lancedb.table_names = Mock(return_value=[])

    # Mock BYOK handler
    with patch('core.episode_segmentation_service.BYOKHandler') as mock_byok:
        with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb):
            with patch('core.episode_segmentation_service.CanvasSummaryService') as mock_canvas:
                service = EpisodeSegmentationService(episode_db_session)
                service.lancedb = mock_lancedb
                yield service


@pytest.fixture(scope="function")
def retrieval_service_mocked(episode_db_session):
    """
    Create EpisodeRetrievalService instance with mocked LanceDB.

    Mocks search to return test episodes for semantic retrieval testing.
    """
    # Mock LanceDB handler
    mock_lancedb = Mock()
    mock_lancedb.search.return_value = []  # Default empty search results

    with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=mock_lancedb):
        service = EpisodeRetrievalService(episode_db_session)
        service.lancedb = mock_lancedb
        yield service


@pytest.fixture(scope="function")
def lifecycle_service_mocked(episode_db_session):
    """
    Create EpisodeLifecycleService instance with mocked LanceDB.

    Mocks archival operations for lifecycle testing.
    """
    # Mock LanceDB handler
    mock_lancedb = Mock()
    mock_lancedb.search.return_value = []

    with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=mock_lancedb):
        service = EpisodeLifecycleService(episode_db_session)
        service.lancedb = mock_lancedb
        yield service


@pytest.fixture(scope="function")
def test_episode(episode_db_session):
    """
    Create test episode with segments for integration tests.

    Returns Episode instance with:
    - user_id, agent_id, started_at
    - 3-5 test segments with different types
    - Configured metadata for retrieval tests
    """
    episode_id = f"test_episode_{uuid4().hex[:8]}"
    episode = Episode(
        id=episode_id,
        agent_id=f"test_agent_{uuid4().hex[:8]}",
        tenant_id="default",
        task_description="Test episode for integration testing",
        maturity_at_time="AUTONOMOUS",
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
        topics=["test", "integration"],
        entities=["test_entity"],
        human_intervention_count=0,
        importance_score=0.8,
        decay_score=0.0,
        access_count=5,
        outcome="success",
        success=True
    )
    episode_db_session.add(episode)
    episode_db_session.flush()

    # Create 3-5 segments
    segments_data = [
        {
            "segment_type": "conversation",
            "content": "User: Hello\nAgent: Hi there!",
            "content_summary": "Greeting exchange",
        },
        {
            "segment_type": "execution",
            "content": "Task: Test execution\nStatus: completed",
            "content_summary": "Test task completed",
        },
        {
            "segment_type": "conversation",
            "content": "User: Goodbye\nAgent: See you!",
            "content_summary": "Closing exchange",
        },
        {
            "segment_type": "reflection",
            "content": "Session completed successfully",
            "content_summary": "Session reflection",
        },
        {
            "segment_type": "intervention",
            "content": "No human interventions needed",
            "content_summary": "Autonomous execution",
        },
    ]

    for i, segment_data in enumerate(segments_data):
        segment = EpisodeSegment(
            id=f"segment_{uuid4().hex[:8]}",
            episode_id=episode.id,
            segment_type=segment_data["segment_type"],
            sequence_order=i,
            content=segment_data["content"],
            content_summary=segment_data["content_summary"],
            source_type="test",
            source_id=f"source_{i}",
            canvas_context=None
        )
        episode_db_session.add(segment)

    episode_db_session.commit()
    episode_db_session.refresh(episode)
    return episode


@pytest.fixture(scope="function")
def test_messages(episode_db_session):
    """
    Create test ChatMessage instances with timestamps for segmentation testing.

    Includes:
    - Time gaps (>30min) for time-based segmentation
    - Topic changes for semantic segmentation
    - Various message types (user, assistant, system)
    """
    session_id = f"test_session_{uuid4().hex[:8]}"
    base_time = datetime.now(timezone.utc) - timedelta(hours=3)

    messages = []

    # Messages in first segment (no gaps)
    messages.append(ChatMessage(
        id=f"msg_{uuid4().hex[:8]}",
        conversation_id=session_id,
        role="user",
        content="Let's discuss Python programming",
        created_at=base_time
    ))

    messages.append(ChatMessage(
        id=f"msg_{uuid4().hex[:8]}",
        conversation_id=session_id,
        role="assistant",
        content="Python is great for web development",
        created_at=base_time + timedelta(minutes=10)
    ))

    # Time gap > 30 minutes (triggers segmentation)
    messages.append(ChatMessage(
        id=f"msg_{uuid4().hex[:8]}",
        conversation_id=session_id,
        role="user",
        content="Now let's talk about cooking recipes",
        created_at=base_time + timedelta(minutes=45)  # 35-min gap
    ))

    messages.append(ChatMessage(
        id=f"msg_{uuid4().hex[:8]}",
        conversation_id=session_id,
        role="assistant",
        content="I love Italian pasta dishes",
        created_at=base_time + timedelta(minutes=50)
    ))

    # Another time gap
    messages.append(ChatMessage(
        id=f"msg_{uuid4().hex[:8]}",
        conversation_id=session_id,
        role="system",
        content="Session summary generated",
        created_at=base_time + timedelta(minutes=90)  # 40-min gap
    ))

    # Add all messages to database
    for msg in messages:
        episode_db_session.add(msg)

    episode_db_session.commit()
    return messages


@pytest.fixture(scope="function")
def episode_test_user(episode_db_session):
    """Create test user for episode tests."""
    user_id = f"test_user_{uuid4().hex[:8]}"
    user = User(
        id=user_id,
        email=f"test_{uuid4().hex[:8]}@example.com",
        role="member"
    )
    episode_db_session.add(user)
    episode_db_session.commit()
    return user


@pytest.fixture(scope="function")
def episode_test_agent(episode_db_session):
    """Create test agent for episode tests."""
    agent_id = f"test_agent_{uuid4().hex[:8]}"
    agent = AgentRegistry(
        id=agent_id,
        name="Test Agent",
        status="AUTONOMOUS",
        category="testing",
        module_path="test.module",
        class_name="TestAgent",
        description="Test agent for episode service tests",
        confidence_score=0.9
    )
    episode_db_session.add(agent)
    episode_db_session.commit()
    return agent


@pytest.fixture(scope="function")
def episode_test_session(episode_db_session, episode_test_user):
    """Create test chat session for episode tests."""
    session_id = f"test_session_{uuid4().hex[:8]}"
    session = ChatSession(
        id=session_id,
        user_id=episode_test_user.id,
        created_at=datetime.now(timezone.utc)
    )
    episode_db_session.add(session)
    episode_db_session.commit()
    return session


@pytest.fixture(scope="function")
def mock_lancedb_embeddings():
    """
    Provide mock LanceDB embedding responses for topic change testing.

    Returns mock configured with:
    - High similarity for same-topic messages
    - Low similarity for different-topic messages
    """
    mock_db = Mock()

    def mock_embed_fn(text):
        """Mock embedding function that returns similarity-based vectors"""
        if "Python" in text or "programming" in text:
            return [0.9, 0.1, 0.0]  # Python topic vector
        elif "cooking" in text or "recipes" in text or "pasta" in text:
            return [0.1, 0.9, 0.0]  # Cooking topic vector
        else:
            return [0.5, 0.5, 0.0]  # Neutral vector

    mock_db.embed_text.side_effect = mock_embed_fn
    return mock_db


# =============================================================================
# Governance Service Fixtures
# =============================================================================

from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import GovernanceCache
from core.models import (
    AgentRegistry,
    AgentStatus,
    User,
    UserRole,
    UserStatus,
    Workspace,
)


@pytest.fixture(scope="function")
def governance_cache():
    """
    Create a GovernanceCache instance with short TTL for testing.

    Uses 1-second TTL to test expiration behavior without long waits.

    Yields:
        GovernanceCache: Cache instance with short TTL
    """
    cache = GovernanceCache(max_size=100, ttl_seconds=1)
    yield cache
    cache.clear()


@pytest.fixture(scope="function")
def governance_service(db_session: Session):
    """
    Create an AgentGovernanceService instance with test database session.

    Yields:
        AgentGovernanceService: Service instance for testing
    """
    service = AgentGovernanceService(db_session)
    yield service


@pytest.fixture(scope="function")
def governance_test_agent(db_session: Session):
    """
    Factory fixture for creating test agents for governance tests.

    Usage:
        agent = governance_test_agent(name="Test Agent", status=AgentStatus.INTERN)
        agent = governance_test_agent(confidence_score=0.8)

    Yields:
        callable: Factory function that creates and returns an AgentRegistry
    """
    created_agents = []

    def _create_agent(
        name: str = "Test Agent",
        category: str = "Testing",
        module_path: str = "test.module",
        class_name: str = "TestAgent",
        status: AgentStatus = AgentStatus.STUDENT,
        confidence_score: float = 0.5,
        enabled: bool = True
    ) -> AgentRegistry:
        """Create a test agent in the database."""
        agent = AgentRegistry(
            name=name,
            description=f"Test agent for {name}",
            category=category,
            module_path=module_path,
            class_name=class_name,
            status=status.value if isinstance(status, AgentStatus) else status,
            confidence_score=confidence_score,
            enabled=enabled,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)
        created_agents.append(agent)
        return agent

    yield _create_agent

    # Cleanup is handled by db_session rollback


@pytest.fixture(scope="function")
def governance_test_user(db_session: Session):
    """
    Factory fixture for creating test users for governance tests.

    Usage:
        user = governance_test_user(email="test@example.com")
        user = governance_test_user(role=UserRole.ADMIN)

    Yields:
        callable: Factory function that creates and returns a User
    """
    created_users = []

    def _create_user(
        email: str = "test@example.com",
        role: UserRole = UserRole.MEMBER,
        specialty: str = None,
        reputation: float = 0.5
    ) -> User:
        """Create a test user in the database."""
        user = User(
            email=email,
            name="Test User",
            role=role.value if isinstance(role, UserRole) else role,
            status=UserStatus.ACTIVE.value,
            specialty=specialty,
            reputation_score=reputation,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        created_users.append(user)
        return user

    yield _create_user

    # Cleanup is handled by db_session rollback

"""
Deep Links Routes Test Coverage

Target: api/deeplinks.py (402 lines, 4 endpoints)
Goal: 75%+ line coverage with TestClient-based integration tests

Endpoints Covered:
- POST /api/deeplinks/execute - Execute a deep link
- GET /api/deeplinks/audit - Get deep link audit log
- POST /api/deeplinks/generate - Generate a deep link
- GET /api/deeplinks/stats - Get deep link statistics
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import DeepLinkAudit, AgentRegistry
from api.deeplinks import router


@pytest.fixture(scope="function")
def test_db():
    """
    In-memory SQLite database with StaticPool for deep link testing.
    Uses StaticPool to prevent threading/locking issues with test isolation.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        # Drop all tables for cleanup
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_execute_deep_link():
    """
    AsyncMock for execute_deep_link function in core.deeplinks.
    Returns dict with success=True and execution details.
    """
    mock = AsyncMock(return_value={
        "success": True,
        "agent_id": "agent-123",
        "agent_name": "Test Agent",
        "execution_id": "exec-456",
        "resource_type": "agent",
        "resource_id": "agent-123",
        "action": "trigger",
        "source": "external"
    })
    return mock


@pytest.fixture
def mock_generate_deep_link():
    """Mock for generate_deep_link function."""
    mock = MagicMock(return_value="atom://agent/123")
    return mock


@pytest.fixture
def mock_parse_deep_link():
    """Mock for parse_deep_link function."""
    mock = MagicMock(return_value={
        "resource_type": "agent",
        "resource_id": "123",
        "action": "trigger",
        "parameters": {}
    })
    return mock


@pytest.fixture
def deeplink_client(test_db, mock_execute_deep_link):
    """
    TestClient with DB override for deep link routes.
    Overrides get_db to yield test_db.
    Patches execute_deep_link at api.deeplinks module level.
    """
    from api.deeplinks import router

    app = FastAPI()
    app.include_router(router)

    # Override get_db dependency
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    from api.deeplinks import get_db
    app.dependency_overrides[get_db] = override_get_db

    # Patch execute_deep_link
    with patch('api.deeplinks.execute_deep_link', mock_execute_deep_link):
        yield TestClient(app)

    # Clean up dependency overrides
    app.dependency_overrides.clear()


@pytest.fixture
def sample_execute_request():
    """Factory for valid DeepLinkExecuteRequest."""
    return {
        "deeplink_url": "atom://agent/123",
        "user_id": "user-456",
        "source": "external"
    }


@pytest.fixture
def sample_generate_request():
    """Factory for valid DeepLinkGenerateRequest."""
    return {
        "resource_type": "agent",
        "resource_id": "123",
        "parameters": {}
    }


@pytest.fixture
def sample_audit_entries(test_db):
    """Factory for DeepLinkAudit database objects."""
    entries = []

    # Create 5 audit entries with different attributes
    for i in range(5):
        entry = DeepLinkAudit(
            id=f"audit-{i}",
            user_id=f"user-{i % 2}",  # Alternating users
            agent_id=f"agent-{i % 3}" if i < 3 else None,  # Some with agents
            agent_execution_id=f"exec-{i}" if i < 3 else None,
            resource_type=["agent", "workflow", "canvas", "tool"][i % 4],
            resource_id=f"resource-{i}",
            action="trigger",
            source="external",
            deeplink_url=f"atom://agent/{i}",
            parameters={},
            status="success",
            error_message=None,
            governance_check_passed=True,
            created_at=datetime.now() - timedelta(hours=i)
        )
        test_db.add(entry)
        entries.append(entry)

    test_db.commit()
    return entries


@pytest.fixture
def sample_execution_response():
    """Expected execute response structure."""
    return {
        "success": True,
        "agent_id": "agent-123",
        "agent_name": "Test Agent",
        "execution_id": "exec-456",
        "resource_type": "agent",
        "resource_id": "agent-123",
        "action": "trigger",
        "source": "external"
    }


@pytest.fixture
def sample_agent(test_db):
    """Create a sample agent for stats testing."""
    agent = AgentRegistry(
        id="agent-123",
        name="Test Agent",
        description="A test agent",
        maturity_level="AUTONOMOUS",
        enabled=True
    )
    test_db.add(agent)
    test_db.commit()
    return agent

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


class TestDeepLinkExecute:
    """Test deep link execution endpoint."""

    def test_execute_deeplink_agent_success(self, deeplink_client, sample_execute_request):
        """Test POST /api/deeplinks/execute with atom://agent/{id}."""
        response = deeplink_client.post(
            "/api/deeplinks/execute",
            json=sample_execute_request
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_id"] == "agent-123"
        assert data["agent_name"] == "Test Agent"
        assert data["execution_id"] == "exec-456"
        assert data["resource_type"] == "agent"
        assert data["resource_id"] == "agent-123"
        assert data["action"] == "trigger"
        assert data["source"] == "external"

    def test_execute_deeplink_workflow_success(self, deeplink_client):
        """Test POST /api/deeplinks/execute with atom://workflow/{id}."""
        # Configure mock to return workflow result
        with patch('api.deeplinks.execute_deep_link',
                   new_callable=AsyncMock,
                   return_value={
                       "success": True,
                       "resource_type": "workflow",
                       "resource_id": "workflow-123",
                       "action": "trigger",
                       "source": "external"
                   }):
            response = deeplink_client.post(
                "/api/deeplinks/execute",
                json={
                    "deeplink_url": "atom://workflow/123",
                    "user_id": "user-456",
                    "source": "external"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["resource_type"] == "workflow"
            assert data["resource_id"] == "workflow-123"

    def test_execute_deeplink_canvas_success(self, deeplink_client):
        """Test POST /api/deeplinks/execute with atom://canvas/{id}."""
        # Configure mock to return canvas result
        with patch('api.deeplinks.execute_deep_link',
                   new_callable=AsyncMock,
                   return_value={
                       "success": True,
                       "resource_type": "canvas",
                       "resource_id": "canvas-123",
                       "action": "open",
                       "source": "external"
                   }):
            response = deeplink_client.post(
                "/api/deeplinks/execute",
                json={
                    "deeplink_url": "atom://canvas/123",
                    "user_id": "user-456",
                    "source": "external"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["resource_type"] == "canvas"
            assert data["resource_id"] == "canvas-123"
            assert data["action"] == "open"

    def test_execute_deeplink_with_source(self, deeplink_client):
        """Test POST /api/deeplinks/execute with source parameter."""
        with patch('api.deeplinks.execute_deep_link',
                   new_callable=AsyncMock,
                   return_value={
                       "success": True,
                       "agent_id": "agent-123",
                       "agent_name": "Test Agent",
                       "resource_type": "agent",
                       "resource_id": "agent-123",
                       "action": "trigger",
                       "source": "mobile_app"
                   }):
            response = deeplink_client.post(
                "/api/deeplinks/execute",
                json={
                    "deeplink_url": "atom://agent/123",
                    "user_id": "user-456",
                    "source": "mobile_app"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["source"] == "mobile_app"

    def test_execute_deeplink_custom_params(self, deeplink_client):
        """Test POST /api/deeplinks/execute with query parameters."""
        with patch('api.deeplinks.execute_deep_link',
                   new_callable=AsyncMock,
                   return_value={
                       "success": True,
                       "agent_id": "agent-123",
                       "agent_name": "Test Agent",
                       "resource_type": "agent",
                       "resource_id": "agent-123",
                       "action": "trigger",
                       "source": "external"
                   }):
            response = deeplink_client.post(
                "/api/deeplinks/execute",
                json={
                    "deeplink_url": "atom://agent/123?message=hello&param=value",
                    "user_id": "user-456",
                    "source": "external"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.parametrize("resource_type,resource_id,action", [
        ("agent", "agent-123", "trigger"),
        ("workflow", "workflow-456", "start"),
        ("canvas", "canvas-789", "open"),
        ("tool", "tool-101", "execute")
    ])
    def test_execute_deeplink_all_resource_types(self, deeplink_client, resource_type, resource_id, action):
        """Parametrized test for all 4 resource types."""
        with patch('api.deeplinks.execute_deep_link',
                   new_callable=AsyncMock,
                   return_value={
                       "success": True,
                       "resource_type": resource_type,
                       "resource_id": resource_id,
                       "action": action,
                       "source": "external"
                   }):
            response = deeplink_client.post(
                "/api/deeplinks/execute",
                json={
                    "deeplink_url": f"atom://{resource_type}/{resource_id.split('-')[-1]}",
                    "user_id": "user-456",
                    "source": "external"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["resource_type"] == resource_type


class TestDeepLinkAudit:
    """Test deep link audit log endpoint."""

    def test_get_deeplink_audit_success(self, deeplink_client, sample_audit_entries):
        """Test GET /api/deeplinks/audit returns all entries."""
        response = deeplink_client.get("/api/deeplinks/audit")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 5

    def test_get_audit_filter_by_user(self, deeplink_client, sample_audit_entries):
        """Test GET /api/deeplinks/audit?user_id={id} filters by user."""
        response = deeplink_client.get("/api/deeplinks/audit?user_id=user-0")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should only return entries with user_id=user-0
        assert all(entry["user_id"] == "user-0" for entry in data)

    def test_get_audit_filter_by_agent(self, deeplink_client, sample_audit_entries):
        """Test GET /api/deeplinks/audit?agent_id={id} filters by agent."""
        response = deeplink_client.get("/api/deeplinks/audit?agent_id=agent-1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should only return entries with agent_id=agent-1
        assert all(entry["agent_id"] == "agent-1" for entry in data)

    def test_get_audit_filter_by_resource_type(self, deeplink_client, sample_audit_entries):
        """Test GET /api/deeplinks/audit?resource_type=agent filters by resource type."""
        response = deeplink_client.get("/api/deeplinks/audit?resource_type=agent")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should only return entries with resource_type=agent
        assert all(entry["resource_type"] == "agent" for entry in data)

    def test_get_audit_pagination(self, deeplink_client):
        """Test GET /api/deeplinks/audit with limit and offset."""
        # Create 20+ entries for pagination test
        from core.models import DeepLinkAudit
        from api.deeplinks import get_db
        from sqlalchemy.orm import Session

        # Need to access the test_db from the fixture
        # We'll create entries directly in the test
        app = deeplink_client.app

        # Get the test_db session from dependency override
        db_gen = app.dependency_overrides[get_db]()
        db = next(db_gen)

        try:
            # Create 20 entries
            for i in range(20):
                entry = DeepLinkAudit(
                    id=f"audit-pagination-{i}",
                    user_id=f"user-{i}",
                    resource_type="agent",
                    resource_id=f"resource-{i}",
                    action="trigger",
                    source="external",
                    deeplink_url=f"atom://agent/{i}",
                    parameters={},
                    status="success"
                )
                db.add(entry)
            db.commit()

            # Test pagination
            response = deeplink_client.get("/api/deeplinks/audit?limit=5&offset=10")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) <= 5
        finally:
            # Clean up
            try:
                for i in range(20):
                    entry = db.query(DeepLinkAudit).filter(
                        DeepLinkAudit.id == f"audit-pagination-{i}"
                    ).first()
                    if entry:
                        db.delete(entry)
                db.commit()
            except:
                pass
            try:
                db_gen.close()
            except:
                pass

    def test_get_audit_empty(self, deeplink_client, test_db):
        """Test GET /api/deeplinks/audit with no entries returns empty list."""
        # Clear all audit entries
        test_db.query(DeepLinkAudit).delete()
        test_db.commit()

        response = deeplink_client.get("/api/deeplinks/audit")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

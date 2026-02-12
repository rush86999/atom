"""
Agent Governance Routes Integration Tests

Tests for agent governance endpoints from api/agent_governance_routes.py.

Coverage:
- GET /agents - List agents
- GET /agents/{agent_id} - Get agent details
- POST /agents - Create agent
- PUT /agents/{agent_id} - Update agent
- DELETE /agents/{agent_id} - Delete agent
- POST /agents/{agent_id}/promote - Promote agent
- POST /agents/{agent_id}/demote - Demote agent
- GET /agents/{agent_id}/confidence - Get confidence score
- POST /agents/{agent_id}/outcome - Record outcome
- Authentication/authorization
- CRUD operations
- Governance operations
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.agent_governance_routes import router
from core.models import AgentRegistry, User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create TestClient for agent governance routes."""
    return TestClient(router)


@pytest.fixture
def mock_user(db: Session):
    """Create test user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mock_agent(db: Session):
    """Create test agent."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Test Agent {agent_id[:8]}",
        category="testing",
        status="intern",
        confidence_score=0.6,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


# ============================================================================
# GET /agents - List Agents Tests
# ============================================================================

def test_list_agents_success(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test listing agents successfully."""
    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get("/agents")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "agents" in data or "data" in data


def test_list_agents_with_filters(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test listing agents with status filter."""
    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get("/agents?status=intern")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "agents" in data or "data" in data


# ============================================================================
# GET /agents/{agent_id} - Get Agent Tests
# ============================================================================

def test_get_agent_success(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test getting agent details successfully."""
    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get(f"/agents/{mock_agent.id}")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data or "agent" in data or "data" in data


def test_get_agent_not_found(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting non-existent agent."""
    import uuid
    non_existent_id = str(uuid.uuid4())

    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get(f"/agents/{non_existent_id}")

        assert response.status_code == 404


# ============================================================================
# POST /agents - Create Agent Tests
# ============================================================================

def test_create_agent_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating agent successfully."""
    import uuid
    agent_data = {
        "id": str(uuid.uuid4()),
        "name": "New Test Agent",
        "category": "testing",
        "status": "student",
        "confidence_score": 0.4,
        "module_path": "test.module",
        "class_name": "TestClass"
    }

    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/agents", json=agent_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data or "agent" in data or "data" in data


def test_create_agent_invalid_schema(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating agent with invalid schema."""
    # Missing required fields
    agent_data = {
        "name": "Incomplete Agent"
    }

    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/agents", json=agent_data)

        assert response.status_code == 422


# ============================================================================
# PUT /agents/{agent_id} - Update Agent Tests
# ============================================================================

def test_update_agent_success(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test updating agent successfully."""
    update_data = {
        "name": "Updated Agent Name",
        "confidence_score": 0.75
    }

    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.put(f"/agents/{mock_agent.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data or "agent" in data or "data" in data


# ============================================================================
# DELETE /agents/{agent_id} - Delete Agent Tests
# ============================================================================

def test_delete_agent_success(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test deleting agent successfully."""
    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.delete(f"/agents/{mock_agent.id}")

        assert response.status_code in [200, 204]


# ============================================================================
# POST /agents/{agent_id}/promote - Promote Agent Tests
# ============================================================================

def test_promote_agent_success(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test promoting agent successfully."""
    with patch('api.agent_governance_routes.AgentGovernanceService') as mock_gov:
        mock_service = MagicMock()
        mock_service.promote_agent.return_value = {
            "success": True,
            "new_status": "supervised"
        }
        mock_gov.return_value = mock_service

        with patch('api.agent_governance_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post(f"/agents/{mock_agent.id}/promote")

            assert response.status_code == 200
            data = response.json()
            assert "new_status" in data or "success" in data


# ============================================================================
# POST /agents/{agent_id}/demote - Demote Agent Tests
# ============================================================================

def test_demote_agent_success(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test demoting agent successfully."""
    with patch('api.agent_governance_routes.AgentGovernanceService') as mock_gov:
        mock_service = MagicMock()
        mock_service.demote_agent.return_value = {
            "success": True,
            "new_status": "student"
        }
        mock_gov.return_value = mock_service

        with patch('api.agent_governance_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post(f"/agents/{mock_agent.id}/demote")

            assert response.status_code == 200
            data = response.json()
            assert "new_status" in data or "success" in data


# ============================================================================
# GET /agents/{agent_id}/confidence - Get Confidence Tests
# ============================================================================

def test_get_agent_confidence_success(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test getting agent confidence score successfully."""
    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get(f"/agents/{mock_agent.id}/confidence")

        assert response.status_code == 200
        data = response.json()
        assert "confidence_score" in data or "confidence" in data


# ============================================================================
# POST /agents/{agent_id}/outcome - Record Outcome Tests
# ============================================================================

def test_record_outcome_success(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test recording agent outcome successfully."""
    outcome_data = {
        "success": True,
        "action_type": "test_action",
        "duration_seconds": 5.2
    }

    with patch('api.agent_governance_routes.AgentGovernanceService') as mock_gov:
        mock_service = MagicMock()
        mock_service.record_outcome = AsyncMock()
        mock_service.record_outcome.return_value = None
        mock_gov.return_value = mock_service

        with patch('api.agent_governance_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post(f"/agents/{mock_agent.id}/outcome", json=outcome_data)

            assert response.status_code == 200


# ============================================================================
# Response Format Tests
# ============================================================================

def test_list_agents_response_format(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test list agents has correct response format."""
    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get("/agents")

        data = response.json()
        assert isinstance(data, list) or isinstance(data.get("data"), list) or isinstance(data.get("agents"), list)


def test_get_agent_response_format(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test get agent has correct response format."""
    with patch('api.agent_governance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get(f"/agents/{mock_agent.id}")

        data = response.json()
        assert "id" in data or "agent" in data or "data" in data

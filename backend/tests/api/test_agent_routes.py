"""
Agent Routes API Tests

Comprehensive tests for agent management endpoints from api/agent_routes.py.
Tests cover agent CRUD, lifecycle, status tracking, permissions, and meta-agent operations.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, BackgroundTasks
from sqlalchemy.orm import Session

from api.agent_routes import router
from core.models import AgentRegistry, AgentJob, AgentFeedback, HITLAction, HITLActionStatus, User


# ============================================================================
# Fixtures
# ============================================================================

_current_test_user = None


@pytest.fixture
def client(db: Session):
    """Create TestClient for agent routes with database override."""
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.security_dependencies import get_current_user
    from core.rbac_service import Permission

    def override_get_db():
        yield db

    def override_get_current_user():
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def mock_admin_user(db: Session):
    """Create admin user with all permissions."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"admin-{user_id}@example.com",
        first_name="Admin",
        last_name="User",
        role="admin",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mock_member_user(db: Session):
    """Create regular member user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"member-{user_id}@example.com",
        first_name="Member",
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
        description="Test agent for testing",
        category="testing",
        status="idle",
        confidence_score=0.75,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def mock_agent_job(db: Session, mock_agent: AgentRegistry):
    """Create test agent job."""
    import uuid
    job = AgentJob(
        id=str(uuid.uuid4()),
        agent_id=mock_agent.id,
        status="completed",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow()
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ============================================================================
# GET / - List Agents Tests
# ============================================================================

def test_list_agents_success(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test list agents successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get("/api/agents/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_list_agents_with_category_filter(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test list agents with category filter."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get(f"/api/agents/?category={mock_agent.category}")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# ============================================================================
# POST /{agent_id}/run - Run Agent Tests
# ============================================================================

def test_run_agent_success(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test run agent successfully."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "parameters": {
            "test_param": "test_value"
        }
    }

    response = client.post(f"/api/agents/{mock_agent.id}/run", json=request_data)

    # Should return success (background task started)
    assert response.status_code in [200, 202]


def test_run_agent_sync_mode(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test run agent in synchronous mode."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "parameters": {
            "sync": True,
            "test_input": "test"
        }
    }

    with patch('api.agent_routes.execute_agent_task') as mock_exec:
        mock_exec.return_value = {"result": "test output"}

        response = client.post(f"/api/agents/{mock_agent.id}/run", json=request_data)

        # Should execute synchronously
        assert response.status_code in [200, 202]


def test_run_agent_not_found(
    client: TestClient,
    db: Session,
    mock_member_user: User
):
    """Test run non-existent agent."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "parameters": {}
    }

    response = client.post("/api/agents/nonexistent-agent/run", json=request_data)

    assert response.status_code == 404


# ============================================================================
# POST /{agent_id}/feedback - Submit Feedback Tests
# ============================================================================

def test_submit_agent_feedback(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test submit agent feedback successfully."""
    global _current_test_user
    _current_test_user = mock_member_user

    feedback_data = {
        "original_output": "Agent output",
        "user_correction": "Corrected output",
        "input_context": "Task context"
    }

    with patch('core.agent_governance_service.AgentGovernanceService.submit_feedback') as mock_feedback:
        mock_feedback.return_value = Mock(
            id="feedback-123",
            status="pending",
            ai_reasoning="Processing feedback"
        )

        response = client.post(f"/api/agents/{mock_agent.id}/feedback", json=feedback_data)

        assert response.status_code == 200
        data = response.json()
        assert "feedback_id" in data or "success" in data


# ============================================================================
# POST /{agent_id}/promote - Promote Agent Tests
# ============================================================================

def test_promote_agent_to_autonomous(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test promote agent to autonomous successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    with patch('core.agent_governance_service.AgentGovernanceService.promote_to_autonomous') as mock_promote:
        mock_promote.return_value = mock_agent

        response = client.post(f"/api/agents/{mock_agent.id}/promote")

        assert response.status_code == 200
        data = response.json()
        assert "agent_status" in data or "success" in data


# ============================================================================
# GET /approvals/pending - List Pending Approvals Tests
# ============================================================================

def test_list_pending_approvals(
    client: TestClient,
    db: Session,
    mock_admin_user: User
):
    """Test list pending approvals successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get("/api/agents/approvals/pending")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# ============================================================================
# POST /approvals/{action_id} - Decide HITL Action Tests
# ============================================================================

def test_approve_hitl_action(
    client: TestClient,
    db: Session,
    mock_admin_user: User
):
    """Test approve HITL action successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    import uuid
    action_id = str(uuid.uuid4())

    approval_data = {
        "decision": "approved",
        "feedback": "Looks good"
    }

    # Create mock HITL action
    mock_action = Mock()
    mock_action.id = action_id
    mock_action.status = HITLActionStatus.PENDING.value

    with patch('core.models.HITLAction') as mock_hitl:
        mock_hitl.query.return_value.filter.return_value.first.return_value = mock_action

        with patch('core.websockets.manager.broadcast') as mock_ws:
            response = client.post(f"/api/agents/approvals/{action_id}", json=approval_data)

            assert response.status_code == 200


def test_reject_hitl_action(
    client: TestClient,
    db: Session,
    mock_admin_user: User
):
    """Test reject HITL action successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    import uuid
    action_id = str(uuid.uuid4())

    approval_data = {
        "decision": "rejected",
        "feedback": "Needs correction"
    }

    mock_action = Mock()
    mock_action.id = action_id
    mock_action.status = HITLActionStatus.PENDING.value

    with patch('core.models.HITLAction') as mock_hitl:
        mock_hitl.query.return_value.filter.return_value.first.return_value = mock_action

        with patch('core.websockets.manager.broadcast') as mock_ws:
            response = client.post(f"/api/agents/approvals/{action_id}", json=approval_data)

            assert response.status_code == 200


# ============================================================================
# POST /atom/execute - Execute Meta-Agent Tests
# ============================================================================

def test_execute_atom_meta_agent(
    client: TestClient,
    db: Session,
    mock_member_user: User
):
    """Test execute Atom meta-agent successfully."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "request": "Analyze sales data",
        "context": {}
    }

    with patch('core.atom_meta_agent.handle_manual_trigger') as mock_trigger:
        mock_trigger.return_value = {
            "result": "Analysis complete"
        }

        response = client.post("/api/agents/atom/execute", json=request_data)

        assert response.status_code == 200


# ============================================================================
# POST /spawn - Spawn Agent Tests
# ============================================================================

def test_spawn_custom_agent(
    client: TestClient,
    db: Session,
    mock_admin_user: User
):
    """Test spawn custom agent successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "template": "finance_analyst",
        "custom_params": {},
        "persist": False
    }

    mock_agent = Mock()
    mock_agent.id = "spawned-agent-123"
    mock_agent.name = "Spawned Agent"
    mock_agent.category = "finance"

    with patch('core.atom_meta_agent.get_atom_agent') as mock_atom:
        mock_atom_instance = Mock()
        mock_atom_instance.spawn_agent.return_value = mock_agent
        mock_atom.return_value = mock_atom_instance

        response = client.post("/api/agents/spawn", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "agent_id" in data or "success" in data


# ============================================================================
# POST /atom/trigger - Trigger with Data Tests
# ============================================================================

def test_trigger_atom_with_data(
    client: TestClient,
    db: Session,
    mock_member_user: User
):
    """Test trigger Atom with data event."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "event_type": "webhook",
        "data": {"key": "value"}
    }

    with patch('core.atom_meta_agent.handle_data_event_trigger') as mock_trigger:
        mock_trigger.return_value = {
            "result": "Event processed"
        }

        response = client.post("/api/agents/atom/trigger", json=request_data)

        assert response.status_code == 200


# ============================================================================
# POST /custom - Create Custom Agent Tests
# ============================================================================

def test_create_custom_agent(
    client: TestClient,
    db: Session,
    mock_admin_user: User
):
    """Test create custom agent successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Custom Test Agent",
        "description": "A custom test agent",
        "category": "custom",
        "configuration": {
            "model": "gpt-4",
            "temperature": 0.7
        },
        "schedule_config": None
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert "agent_id" in data or "success" in data


# ============================================================================
# PUT /{agent_id} - Update Agent Tests
# ============================================================================

def test_update_agent(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test update agent successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Updated Agent Name",
        "description": "Updated description",
        "category": "testing",
        "configuration": {
            "model": "gpt-4"
        },
        "schedule_config": None
    }

    response = client.put(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert "agent_id" in data or "success" in data


def test_update_agent_not_found(
    client: TestClient,
    db: Session,
    mock_admin_user: User
):
    """Test update non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Updated Name",
        "description": "Updated",
        "category": "testing",
        "configuration": {},
        "schedule_config": None
    }

    response = client.put("/api/agents/nonexistent-agent", json=request_data)

    assert response.status_code == 404


# ============================================================================
# POST /{agent_id}/stop - Stop Agent Tests
# ============================================================================

def test_stop_running_agent(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test stop running agent successfully."""
    global _current_test_user
    _current_test_user = mock_member_user

    with patch('core.agent_task_registry.agent_task_registry') as mock_registry:
        mock_registry.cancel_agent_agent_tasks.return_value = 2

        response = client.post(f"/api/agents/{mock_agent.id}/stop")

        assert response.status_code == 200
        data = response.json()
        assert "cancelled_tasks" in data or "success" in data


def test_stop_agent_no_tasks(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test stop agent with no running tasks."""
    global _current_test_user
    _current_test_user = mock_member_user

    with patch('core.agent_task_registry.agent_task_registry') as mock_registry:
        mock_registry.cancel_agent_agent_tasks.return_value = 0

        response = client.post(f"/api/agents/{mock_agent.id}/stop")

        assert response.status_code == 200

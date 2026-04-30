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
def client(db_session: Session):
    """Create TestClient for agent routes with database override."""
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.security_dependencies import get_current_user
    from core.rbac_service import Permission

    def override_get_db():
        yield db_session

    def override_get_current_user():
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def mock_admin_user(db_session: Session):
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
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_member_user(db_session: Session):
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
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_agent(db_session: Session):
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
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def mock_agent_job(db_session: Session, mock_agent: AgentRegistry):
    """Create test agent job."""
    import uuid
    job = AgentJob(
        id=str(uuid.uuid4()),
        agent_id=mock_agent.id,
        status="completed",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow()
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


# ============================================================================
# GET / - List Agents Tests
# ============================================================================

def test_list_agents_success(
    client: TestClient,
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
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
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test stop agent with no running tasks."""
    global _current_test_user
    _current_test_user = mock_member_user

    with patch('core.agent_task_registry.agent_task_registry') as mock_registry:
        mock_registry.cancel_agent_tasks.return_value = 0

        response = client.post(f"/api/agents/{mock_agent.id}/stop")

        assert response.status_code == 200


# ============================================================================
# GET /{agent_id} - Get Agent Tests
# ============================================================================

def test_get_agent_success(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test get agent by ID successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get(f"/api/agents/{mock_agent.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["id"] == mock_agent.id
    assert data["data"]["name"] == mock_agent.name


def test_get_agent_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test get non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get("/api/agents/nonexistent-agent")

    assert response.status_code == 404


def test_get_agent_with_last_run(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_agent_job: AgentJob,
    mock_admin_user: User
):
    """Test get agent includes last run time."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get(f"/api/agents/{mock_agent.id}")

    assert response.status_code == 200
    data = response.json()
    assert "last_run" in data["data"]


# ============================================================================
# GET /{agent_id}/status - Get Agent Status Tests
# ============================================================================

def test_get_agent_status_success(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test get agent status successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get(f"/api/agents/{mock_agent.id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["agent_id"] == mock_agent.id
    assert "status" in data["data"]
    assert "is_running" in data["data"]


def test_get_agent_status_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test get status for non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get("/api/agents/nonexistent-agent/status")

    assert response.status_code == 404


# ============================================================================
# DELETE /{agent_id} - Delete Agent Tests
# ============================================================================

def test_delete_agent_success(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test delete agent successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.delete(f"/api/agents/{mock_agent.id}")

    assert response.status_code == 200
    data = response.json()
    assert "agent_id" in data["data"]

    # Verify agent is deleted
    deleted_agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == mock_agent.id).first()
    assert deleted_agent is None


def test_delete_agent_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test delete non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.delete("/api/agents/nonexistent-agent")

    assert response.status_code == 404


def test_delete_agent_with_running_tasks(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test delete agent with running tasks fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    with patch('core.agent_task_registry.agent_task_registry') as mock_registry:
        mock_registry.get_active_tasks.return_value = [Mock()]

        response = client.delete(f"/api/agents/{mock_agent.id}")

        assert response.status_code == 400


# ============================================================================
# PATCH /{agent_id} - Update Agent Tests (Partial Update)
# ============================================================================

def test_patch_agent_name(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test update agent name via PATCH."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Updated Name"
    }

    response = client.patch(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["name"] == "Updated Name"


def test_patch_agent_description(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test update agent description via PATCH."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "description": "Updated description"
    }

    response = client.patch(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["description"] == "Updated description"


def test_patch_agent_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test patch non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Updated Name"
    }

    response = client.patch("/api/agents/nonexistent-agent", json=request_data)

    assert response.status_code == 404


# ============================================================================
# POST /custom - Create Custom Agent Validation Tests
# ============================================================================

def test_create_custom_agent_invalid_name_empty(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create custom agent with empty name fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "",
        "category": "test",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 422  # Validation error


def test_create_custom_agent_invalid_name_whitespace(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create custom agent with whitespace-only name fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "   ",
        "category": "test",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 422  # Validation error


def test_create_custom_agent_invalid_category(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create custom agent with invalid category fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Test Agent",
        "category": "",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 422  # Validation error


def test_create_custom_agent_with_schedule(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create custom agent with schedule configuration."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Scheduled Agent",
        "category": "scheduled",
        "configuration": {},
        "schedule_config": {
            "active": True,
            "cron": "0 9 * * *"
        }
    }

    with patch('core.scheduler.AgentScheduler.get_instance') as mock_scheduler:
        mock_sched_instance = Mock()
        mock_scheduler.return_value = mock_sched_instance

        response = client.post("/api/agents/custom", json=request_data)

        assert response.status_code == 200


# ============================================================================
# PUT /{agent_id} - Replace Agent Tests (Full Replacement)
# ============================================================================

def test_replace_agent_success(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test full agent replacement via PUT."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Replaced Agent",
        "description": "Fully replaced",
        "category": "replacement",
        "configuration": {"model": "gpt-4"},
        "schedule_config": None
    }

    response = client.put(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["agent_id"] == mock_agent.id


def test_replace_agent_missing_required_field(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test PUT without required fields fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    # Missing 'category' (required field)
    request_data = {
        "name": "Incomplete Agent"
    }

    response = client.put(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 422  # Validation error


def test_replace_agent_invalid_name(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test PUT with invalid name fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "",  # Invalid: empty
        "category": "test"
    }

    response = client.put(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 422


def test_replace_agent_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test replace non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "New Agent",
        "category": "test"
    }

    response = client.put("/api/agents/nonexistent-agent", json=request_data)

    assert response.status_code == 404


# ============================================================================
# POST /{agent_id}/run - Agent Execution Edge Cases
# ============================================================================

def test_run_agent_deprecated_state(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test run deprecated agent fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    # Update agent to deprecated
    mock_agent.status = "deprecated"
    db_session.commit()

    request_data = {"parameters": {}}

    response = client.post(f"/api/agents/{mock_agent.id}/run", json=request_data)

    assert response.status_code == 400


def test_run_agent_paused_state(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test run paused agent fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    # Update agent to paused
    mock_agent.status = "paused"
    db_session.commit()

    request_data = {"parameters": {}}

    response = client.post(f"/api/agents/{mock_agent.id}/run", json=request_data)

    assert response.status_code == 400


def test_run_agent_already_running(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test run agent that's already running fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    # Update agent to running
    mock_agent.status = "running"
    db_session.commit()

    request_data = {"parameters": {}}

    response = client.post(f"/api/agents/{mock_agent.id}/run", json=request_data)

    assert response.status_code == 409  # Conflict


# ============================================================================
# POST /{agent_id}/feedback - Feedback Edge Cases
# ============================================================================

def test_submit_feedback_minimal_data(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test submit feedback with minimal required data."""
    global _current_test_user
    _current_test_user = mock_member_user

    feedback_data = {
        "original_output": "Output",
        "user_correction": "Correction"
        # input_context is optional
    }

    with patch('core.agent_governance_service.AgentGovernanceService.submit_feedback') as mock_feedback:
        mock_feedback.return_value = Mock(
            id="feedback-123",
            status="pending",
            ai_reasoning="Processing"
        )

        response = client.post(f"/api/agents/{mock_agent.id}/feedback", json=feedback_data)

        assert response.status_code == 200


# ============================================================================
# POST /approvals/{action_id} - Approval Decision Edge Cases
# ============================================================================

def test_approve_action_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test approve non-existent action."""
    global _current_test_user
    _current_test_user = mock_admin_user

    approval_data = {
        "decision": "approved",
        "feedback": "Approved"
    }

    response = client.post("/api/agents/approvals/nonexistent-action", json=approval_data)

    assert response.status_code == 404


def test_reject_action_with_feedback(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test reject action with feedback."""
    global _current_test_user
    _current_test_user = mock_admin_user

    import uuid
    action_id = str(uuid.uuid4())

    approval_data = {
        "decision": "rejected",
        "feedback": "Needs work"
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
# POST /atom/execute - Meta-Agent Edge Cases
# ============================================================================

def test_execute_atom_with_context(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test execute Atom meta-agent with context."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "request": "Analyze data",
        "context": {
            "workspace": "test",
            "user_id": "user123"
        }
    }

    with patch('core.atom_meta_agent.handle_manual_trigger') as mock_trigger:
        mock_trigger.return_value = {
            "result": "Analysis complete with context"
        }

        response = client.post("/api/agents/atom/execute", json=request_data)

        assert response.status_code == 200


def test_execute_atom_empty_request(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test execute Atom with empty request."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "request": "",
        "context": {}
    }

    with patch('core.atom_meta_agent.handle_manual_trigger') as mock_trigger:
        mock_trigger.return_value = {
            "result": "Empty request handled"
        }

        response = client.post("/api/agents/atom/execute", json=request_data)

        # Should still process, even with empty request
        assert response.status_code == 200


# ============================================================================
# POST /spawn - Spawn Agent Edge Cases
# ============================================================================

def test_spawn_agent_persist_true(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test spawn agent with persist=True."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "template": "finance_analyst",
        "custom_params": {"specialty": "stocks"},
        "persist": True
    }

    mock_agent = Mock()
    mock_agent.id = "persisted-agent-123"
    mock_agent.name = "Persisted Agent"
    mock_agent.category = "finance"

    with patch('core.atom_meta_agent.get_atom_agent') as mock_atom:
        mock_atom_instance = Mock()
        mock_atom_instance.spawn_agent.return_value = mock_agent
        mock_atom.return_value = mock_atom_instance

        response = client.post("/api/agents/spawn", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["persisted"] is True


def test_spawn_agent_unknown_template(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test spawn agent with unknown template."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "template": "unknown_template",
        "persist": False
    }

    # Should handle gracefully
    with patch('core.atom_meta_agent.get_atom_agent') as mock_atom:
        mock_atom_instance = Mock()
        mock_atom_instance.spawn_agent.side_effect = Exception("Template not found")
        mock_atom.return_value = mock_atom_instance

        response = client.post("/api/agents/spawn", json=request_data)

        # Should return error
        assert response.status_code in [400, 500]


# ============================================================================
# POST /atom/trigger - Trigger Edge Cases
# ============================================================================

def test_trigger_atom_with_complex_data(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test trigger Atom with complex event data."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "event_type": "webhook_received",
        "data": {
            "source": "external_api",
            "payload": {
                "nested": {
                    "data": "value"
                },
                "items": [1, 2, 3]
            }
        }
    }

    with patch('core.atom_meta_agent.handle_data_event_trigger') as mock_trigger:
        mock_trigger.return_value = {
            "result": "Complex data processed"
        }

        response = client.post("/api/agents/atom/trigger", json=request_data)

        assert response.status_code == 200


def test_trigger_atom_empty_data(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test trigger Atom with empty data."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "event_type": "test_event",
        "data": {}
    }

    with patch('core.atom_meta_agent.handle_data_event_trigger') as mock_trigger:
        mock_trigger.return_value = {
            "result": "Empty data processed"
        }

        response = client.post("/api/agents/atom/trigger", json=request_data)

        assert response.status_code == 200


# ============================================================================
# POST /{agent_id}/stop - Stop Agent Edge Cases
# ============================================================================

def test_stop_agent_not_found(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test stop non-existent agent."""
    global _current_test_user
    _current_test_user = mock_member_user

    with patch('core.agent_task_registry.agent_task_registry') as mock_registry:
        mock_registry.cancel_agent_tasks.return_value = 0

        response = client.post("/api/agents/nonexistent-agent/stop")

        assert response.status_code == 404


def test_stop_agent_multiple_tasks(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test stop agent with multiple running tasks."""
    global _current_test_user
    _current_test_user = mock_member_user

    with patch('core.agent_task_registry.agent_task_registry') as mock_registry:
        mock_registry.cancel_agent_tasks.return_value = 5

        response = client.post(f"/api/agents/{mock_agent.id}/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["cancelled_tasks"] == 5


# ============================================================================
# Permission Tests
# ============================================================================

def test_list_agents_unauthorized(
    client: TestClient,
    db_session: Session
):
    """Test list agents without authentication fails."""
    global _current_test_user
    _current_test_user = None

    response = client.get("/api/agents/")

    # Should fail without auth
    assert response.status_code in [401, 403]


def test_create_custom_agent_member_forbidden(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test create custom agent without admin permission fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "name": "Unauthorized Agent",
        "category": "test",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    # Members should not be able to create agents
    assert response.status_code in [401, 403]


def test_delete_agent_member_forbidden(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test delete agent without admin permission fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    response = client.delete(f"/api/agents/{mock_agent.id}")

    # Members should not be able to delete agents
    assert response.status_code in [401, 403]


def test_promote_agent_member_forbidden(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test promote agent without admin permission fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    response = client.post(f"/api/agents/{mock_agent.id}/promote")

    # Members should not be able to promote agents
    assert response.status_code in [401, 403]


# ============================================================================
# Integration Tests
# ============================================================================

def test_agent_crud_end_to_end(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test full CRUD lifecycle for agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    # Create
    create_data = {
        "name": "E2E Agent",
        "category": "e2e",
        "configuration": {}
    }
    create_response = client.post("/api/agents/custom", json=create_data)
    assert create_response.status_code == 200
    agent_id = create_response.json()["data"]["agent_id"]

    # Read
    get_response = client.get(f"/api/agents/{agent_id}")
    assert get_response.status_code == 200

    # Update
    update_data = {
        "name": "Updated E2E Agent",
        "description": "Updated"
    }
    update_response = client.patch(f"/api/agents/{agent_id}", json=update_data)
    assert update_response.status_code == 200

    # Delete
    delete_response = client.delete(f"/api/agents/{agent_id}")
    assert delete_response.status_code == 200

    # Verify deleted
    verify_response = client.get(f"/api/agents/{agent_id}")
    assert verify_response.status_code == 404


def test_list_agents_with_pagination(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test list agents with multiple agents."""
    global _current_test_user
    _current_test_user = mock_admin_user

    # Create multiple agents
    from tests.fixtures.agent_fixtures import create_agent_batch
    agents = create_agent_batch(db, count=3)

    response = client.get("/api/agents/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3


def test_run_agent_with_large_parameters(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test run agent with large parameter payload."""
    global _current_test_user
    _current_test_user = mock_member_user

    large_params = {
        "data": "x" * 10000,  # 10KB of data
        "nested": {
            "items": list(range(1000))
        }
    }

    request_data = {"parameters": large_params}

    with patch('api.agent_routes.execute_agent_task') as mock_exec:
        mock_exec.return_value = {"result": "processed large params"}

        response = client.post(f"/api/agents/{mock_agent.id}/run", json=request_data)

        assert response.status_code in [200, 202]


# ============================================================================
# Performance Tests
# ============================================================================

def test_list_agents_performance(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test list agents response time is acceptable."""
    global _current_test_user
    _current_test_user = mock_admin_user

    import time

    start_time = time.time()
    response = client.get("/api/agents/")
    elapsed = time.time() - start_time

    assert response.status_code == 200
    # Should respond in < 1 second
    assert elapsed < 1.0


def test_get_agent_performance(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test get agent response time is acceptable."""
    global _current_test_user
    _current_test_user = mock_admin_user

    import time

    start_time = time.time()
    response = client.get(f"/api/agents/{mock_agent.id}")
    elapsed = time.time() - start_time

    assert response.status_code == 200
    # Should respond in < 500ms
    assert elapsed < 0.5


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_agent_with_unicode_name(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create agent with Unicode characters in name."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Agent 测试 🚀",
        "category": "unicode",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 200


def test_agent_with_special_characters(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create agent with special characters in description."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Special Agent",
        "category": "test",
        "description": "Agent with <script> & 'quotes' and \"double quotes\"",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 200


def test_agent_with_very_long_description(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create agent with very long description."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Verbose Agent",
        "category": "test",
        "description": "x" * 10000,  # 10KB description
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 200

# ============================================================================
# GET /{agent_id} - Get Agent Tests
# ============================================================================

def test_get_agent_success(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test get agent by ID successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get(f"/api/agents/{mock_agent.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["id"] == mock_agent.id
    assert data["data"]["name"] == mock_agent.name


def test_get_agent_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test get non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get("/api/agents/nonexistent-agent")

    assert response.status_code == 404


def test_get_agent_with_last_run(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_agent_job: AgentJob,
    mock_admin_user: User
):
    """Test get agent includes last run time."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get(f"/api/agents/{mock_agent.id}")

    assert response.status_code == 200
    data = response.json()
    assert "last_run" in data["data"]


# ============================================================================
# GET /{agent_id}/status - Get Agent Status Tests
# ============================================================================

def test_get_agent_status_success(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test get agent status successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get(f"/api/agents/{mock_agent.id}/status")

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["agent_id"] == mock_agent.id
    assert "status" in data["data"]
    assert "is_running" in data["data"]


def test_get_agent_status_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test get status for non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.get("/api/agents/nonexistent-agent/status")

    assert response.status_code == 404


# ============================================================================
# DELETE /{agent_id} - Delete Agent Tests
# ============================================================================

def test_delete_agent_success(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test delete agent successfully."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.delete(f"/api/agents/{mock_agent.id}")

    assert response.status_code == 200
    data = response.json()
    assert "agent_id" in data["data"]

    # Verify agent is deleted
    deleted_agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == mock_agent.id).first()
    assert deleted_agent is None


def test_delete_agent_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test delete non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    response = client.delete("/api/agents/nonexistent-agent")

    assert response.status_code == 404


def test_delete_agent_with_running_tasks(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test delete agent with running tasks fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    with patch('core.agent_task_registry.agent_task_registry') as mock_registry:
        mock_registry.get_active_tasks.return_value = [Mock()]

        response = client.delete(f"/api/agents/{mock_agent.id}")

        assert response.status_code == 400


# ============================================================================
# PATCH /{agent_id} - Update Agent Tests (Partial Update)
# ============================================================================

def test_patch_agent_name(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test update agent name via PATCH."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Updated Name"
    }

    response = client.patch(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["name"] == "Updated Name"


def test_patch_agent_description(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test update agent description via PATCH."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "description": "Updated description"
    }

    response = client.patch(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["description"] == "Updated description"


def test_patch_agent_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test patch non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Updated Name"
    }

    response = client.patch("/api/agents/nonexistent-agent", json=request_data)

    assert response.status_code == 404


# ============================================================================
# POST /custom - Create Custom Agent Validation Tests
# ============================================================================

def test_create_custom_agent_invalid_name_empty(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create custom agent with empty name fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "",
        "category": "test",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 422  # Validation error


def test_create_custom_agent_invalid_name_whitespace(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create custom agent with whitespace-only name fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "   ",
        "category": "test",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 422  # Validation error


def test_create_custom_agent_invalid_category(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create custom agent with invalid category fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Test Agent",
        "category": "",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 422  # Validation error


def test_create_custom_agent_with_schedule(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create custom agent with schedule configuration."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Scheduled Agent",
        "category": "scheduled",
        "configuration": {},
        "schedule_config": {
            "active": True,
            "cron": "0 9 * * *"
        }
    }

    with patch('core.scheduler.AgentScheduler.get_instance') as mock_scheduler:
        mock_sched_instance = Mock()
        mock_scheduler.return_value = mock_sched_instance

        response = client.post("/api/agents/custom", json=request_data)

        assert response.status_code == 200


# ============================================================================
# PUT /{agent_id} - Replace Agent Tests (Full Replacement)
# ============================================================================

def test_replace_agent_success(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test full agent replacement via PUT."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Replaced Agent",
        "description": "Fully replaced",
        "category": "replacement",
        "configuration": {"model": "gpt-4"},
        "schedule_config": None
    }

    response = client.put(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["agent_id"] == mock_agent.id


def test_replace_agent_missing_required_field(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test PUT without required fields fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    # Missing 'category' (required field)
    request_data = {
        "name": "Incomplete Agent"
    }

    response = client.put(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 422  # Validation error


def test_replace_agent_invalid_name(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test PUT with invalid name fails."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "",  # Invalid: empty
        "category": "test"
    }

    response = client.put(f"/api/agents/{mock_agent.id}", json=request_data)

    assert response.status_code == 422


def test_replace_agent_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test replace non-existent agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "New Agent",
        "category": "test"
    }

    response = client.put("/api/agents/nonexistent-agent", json=request_data)

    assert response.status_code == 404


# ============================================================================
# POST /{agent_id}/run - Agent Execution Edge Cases
# ============================================================================

def test_run_agent_deprecated_state(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test run deprecated agent fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    # Update agent to deprecated
    mock_agent.status = "deprecated"
    db_session.commit()

    request_data = {"parameters": {}}

    response = client.post(f"/api/agents/{mock_agent.id}/run", json=request_data)

    assert response.status_code == 400


def test_run_agent_paused_state(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test run paused agent fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    # Update agent to paused
    mock_agent.status = "paused"
    db_session.commit()

    request_data = {"parameters": {}}

    response = client.post(f"/api/agents/{mock_agent.id}/run", json=request_data)

    assert response.status_code == 400


def test_run_agent_already_running(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test run agent that's already running fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    # Update agent to running
    mock_agent.status = "running"
    db_session.commit()

    request_data = {"parameters": {}}

    response = client.post(f"/api/agents/{mock_agent.id}/run", json=request_data)

    assert response.status_code == 409  # Conflict


# ============================================================================
# POST /{agent_id}/feedback - Feedback Edge Cases
# ============================================================================

def test_submit_feedback_minimal_data(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test submit feedback with minimal required data."""
    global _current_test_user
    _current_test_user = mock_member_user

    feedback_data = {
        "original_output": "Output",
        "user_correction": "Correction"
        # input_context is optional
    }

    with patch('core.agent_governance_service.AgentGovernanceService.submit_feedback') as mock_feedback:
        mock_feedback.return_value = Mock(
            id="feedback-123",
            status="pending",
            ai_reasoning="Processing"
        )

        response = client.post(f"/api/agents/{mock_agent.id}/feedback", json=feedback_data)

        assert response.status_code == 200


# ============================================================================
# POST /approvals/{action_id} - Approval Decision Edge Cases
# ============================================================================

def test_approve_action_not_found(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test approve non-existent action."""
    global _current_test_user
    _current_test_user = mock_admin_user

    approval_data = {
        "decision": "approved",
        "feedback": "Approved"
    }

    response = client.post("/api/agents/approvals/nonexistent-action", json=approval_data)

    assert response.status_code == 404


def test_reject_action_with_feedback(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test reject action with feedback."""
    global _current_test_user
    _current_test_user = mock_admin_user

    import uuid
    action_id = str(uuid.uuid4())

    approval_data = {
        "decision": "rejected",
        "feedback": "Needs work"
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
# POST /atom/execute - Meta-Agent Edge Cases
# ============================================================================

def test_execute_atom_with_context(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test execute Atom meta-agent with context."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "request": "Analyze data",
        "context": {
            "workspace": "test",
            "user_id": "user123"
        }
    }

    with patch('core.atom_meta_agent.handle_manual_trigger') as mock_trigger:
        mock_trigger.return_value = {
            "result": "Analysis complete with context"
        }

        response = client.post("/api/agents/atom/execute", json=request_data)

        assert response.status_code == 200


def test_execute_atom_empty_request(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test execute Atom with empty request."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "request": "",
        "context": {}
    }

    with patch('core.atom_meta_agent.handle_manual_trigger') as mock_trigger:
        mock_trigger.return_value = {
            "result": "Empty request handled"
        }

        response = client.post("/api/agents/atom/execute", json=request_data)

        # Should still process, even with empty request
        assert response.status_code == 200


# ============================================================================
# POST /spawn - Spawn Agent Edge Cases
# ============================================================================

def test_spawn_agent_persist_true(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test spawn agent with persist=True."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "template": "finance_analyst",
        "custom_params": {"specialty": "stocks"},
        "persist": True
    }

    mock_agent = Mock()
    mock_agent.id = "persisted-agent-123"
    mock_agent.name = "Persisted Agent"
    mock_agent.category = "finance"

    with patch('core.atom_meta_agent.get_atom_agent') as mock_atom:
        mock_atom_instance = Mock()
        mock_atom_instance.spawn_agent.return_value = mock_agent
        mock_atom.return_value = mock_atom_instance

        response = client.post("/api/agents/spawn", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["persisted"] is True


def test_spawn_agent_unknown_template(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test spawn agent with unknown template."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "template": "unknown_template",
        "persist": False
    }

    # Should handle gracefully
    with patch('core.atom_meta_agent.get_atom_agent') as mock_atom:
        mock_atom_instance = Mock()
        mock_atom_instance.spawn_agent.side_effect = Exception("Template not found")
        mock_atom.return_value = mock_atom_instance

        response = client.post("/api/agents/spawn", json=request_data)

        # Should return error
        assert response.status_code in [400, 500]


# ============================================================================
# POST /atom/trigger - Trigger Edge Cases
# ============================================================================

def test_trigger_atom_with_complex_data(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test trigger Atom with complex event data."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "event_type": "webhook_received",
        "data": {
            "source": "external_api",
            "payload": {
                "nested": {
                    "data": "value"
                },
                "items": [1, 2, 3]
            }
        }
    }

    with patch('core.atom_meta_agent.handle_data_event_trigger') as mock_trigger:
        mock_trigger.return_value = {
            "result": "Complex data processed"
        }

        response = client.post("/api/agents/atom/trigger", json=request_data)

        assert response.status_code == 200


def test_trigger_atom_empty_data(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test trigger Atom with empty data."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "event_type": "test_event",
        "data": {}
    }

    with patch('core.atom_meta_agent.handle_data_event_trigger') as mock_trigger:
        mock_trigger.return_value = {
            "result": "Empty data processed"
        }

        response = client.post("/api/agents/atom/trigger", json=request_data)

        assert response.status_code == 200


# ============================================================================
# POST /{agent_id}/stop - Stop Agent Edge Cases
# ============================================================================

def test_stop_agent_not_found(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test stop non-existent agent."""
    global _current_test_user
    _current_test_user = mock_member_user

    with patch('core.agent_task_registry.agent_task_registry') as mock_registry:
        mock_registry.cancel_agent_tasks.return_value = 0

        response = client.post("/api/agents/nonexistent-agent/stop")

        assert response.status_code == 404


def test_stop_agent_multiple_tasks(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test stop agent with multiple running tasks."""
    global _current_test_user
    _current_test_user = mock_member_user

    with patch('core.agent_task_registry.agent_task_registry') as mock_registry:
        mock_registry.cancel_agent_tasks.return_value = 5

        response = client.post(f"/api/agents/{mock_agent.id}/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["cancelled_tasks"] == 5


# ============================================================================
# Permission Tests
# ============================================================================

def test_list_agents_unauthorized(
    client: TestClient,
    db_session: Session
):
    """Test list agents without authentication fails."""
    global _current_test_user
    _current_test_user = None

    response = client.get("/api/agents/")

    # Should fail without auth
    assert response.status_code in [401, 403]


def test_create_custom_agent_member_forbidden(
    client: TestClient,
    db_session: Session,
    mock_member_user: User
):
    """Test create custom agent without admin permission fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    request_data = {
        "name": "Unauthorized Agent",
        "category": "test",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    # Members should not be able to create agents
    assert response.status_code in [401, 403]


def test_delete_agent_member_forbidden(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test delete agent without admin permission fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    response = client.delete(f"/api/agents/{mock_agent.id}")

    # Members should not be able to delete agents
    assert response.status_code in [401, 403]


def test_promote_agent_member_forbidden(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test promote agent without admin permission fails."""
    global _current_test_user
    _current_test_user = mock_member_user

    response = client.post(f"/api/agents/{mock_agent.id}/promote")

    # Members should not be able to promote agents
    assert response.status_code in [401, 403]


# ============================================================================
# Integration Tests
# ============================================================================

def test_agent_crud_end_to_end(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test full CRUD lifecycle for agent."""
    global _current_test_user
    _current_test_user = mock_admin_user

    # Create
    create_data = {
        "name": "E2E Agent",
        "category": "e2e",
        "configuration": {}
    }
    create_response = client.post("/api/agents/custom", json=create_data)
    assert create_response.status_code == 200
    agent_id = create_response.json()["data"]["agent_id"]

    # Read
    get_response = client.get(f"/api/agents/{agent_id}")
    assert get_response.status_code == 200

    # Update
    update_data = {
        "name": "Updated E2E Agent",
        "description": "Updated"
    }
    update_response = client.patch(f"/api/agents/{agent_id}", json=update_data)
    assert update_response.status_code == 200

    # Delete
    delete_response = client.delete(f"/api/agents/{agent_id}")
    assert delete_response.status_code == 200

    # Verify deleted
    verify_response = client.get(f"/api/agents/{agent_id}")
    assert verify_response.status_code == 404


def test_list_agents_with_pagination(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test list agents with multiple agents."""
    global _current_test_user
    _current_test_user = mock_admin_user

    # Create multiple agents
    from tests.fixtures.agent_fixtures import create_agent_batch
    agents = create_agent_batch(db, count=3)

    response = client.get("/api/agents/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3


def test_run_agent_with_large_parameters(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_member_user: User
):
    """Test run agent with large parameter payload."""
    global _current_test_user
    _current_test_user = mock_member_user

    large_params = {
        "data": "x" * 10000,  # 10KB of data
        "nested": {
            "items": list(range(1000))
        }
    }

    request_data = {"parameters": large_params}

    with patch('api.agent_routes.execute_agent_task') as mock_exec:
        mock_exec.return_value = {"result": "processed large params"}

        response = client.post(f"/api/agents/{mock_agent.id}/run", json=request_data)

        assert response.status_code in [200, 202]


# ============================================================================
# Performance Tests
# ============================================================================

def test_list_agents_performance(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test list agents response time is acceptable."""
    global _current_test_user
    _current_test_user = mock_admin_user

    import time

    start_time = time.time()
    response = client.get("/api/agents/")
    elapsed = time.time() - start_time

    assert response.status_code == 200
    # Should respond in < 1 second
    assert elapsed < 1.0


def test_get_agent_performance(
    client: TestClient,
    db_session: Session,
    mock_agent: AgentRegistry,
    mock_admin_user: User
):
    """Test get agent response time is acceptable."""
    global _current_test_user
    _current_test_user = mock_admin_user

    import time

    start_time = time.time()
    response = client.get(f"/api/agents/{mock_agent.id}")
    elapsed = time.time() - start_time

    assert response.status_code == 200
    # Should respond in < 500ms
    assert elapsed < 0.5


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_agent_with_unicode_name(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create agent with Unicode characters in name."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Agent 测试 🚀",
        "category": "unicode",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 200


def test_agent_with_special_characters(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create agent with special characters in description."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Special Agent",
        "category": "test",
        "description": "Agent with <script> & 'quotes' and \"double quotes\"",
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 200


def test_agent_with_very_long_description(
    client: TestClient,
    db_session: Session,
    mock_admin_user: User
):
    """Test create agent with very long description."""
    global _current_test_user
    _current_test_user = mock_admin_user

    request_data = {
        "name": "Verbose Agent",
        "category": "test",
        "description": "x" * 10000,  # 10KB description
        "configuration": {}
    }

    response = client.post("/api/agents/custom", json=request_data)

    assert response.status_code == 200

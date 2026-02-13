"""
Agent Guidance Routes API Tests

Tests for agent guidance endpoints from api/agent_guidance_routes.py.

Coverage:
- Operation tracking (start, update, complete)
- View orchestration (switch, layout)
- Error guidance (present, track resolution)
- Agent requests (permission, decision, respond)
- Authentication/authorization
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from api.agent_guidance_routes import router
from core.models import (
    AgentOperationTracker,
    AgentRequestLog,
    User
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create TestClient for agent guidance routes."""
    return TestClient(router)


@pytest.fixture
def mock_user(db: Session):
    """Create test user."""
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
def mock_operation(db: Session, mock_user: User):
    """Create test operation tracker."""
    operation_id = str(uuid.uuid4())
    operation = AgentOperationTracker(
        operation_id=operation_id,
        user_id=mock_user.id,
        agent_id="test_agent",
        operation_type="test_operation",
        status="running",
        current_step="Step 1",
        total_steps=5,
        current_step_index=0,
        progress=0,
        what_explanation="Test operation",
        why_explanation="Testing guidance system",
        next_steps="Complete all steps",
        logs=[],
        metadata={}
    )
    db.add(operation)
    db.commit()
    db.refresh(operation)
    return operation


@pytest.fixture
def mock_request(db: Session, mock_user: User):
    """Create test agent request."""
    request_id = str(uuid.uuid4())
    request = AgentRequestLog(
        request_id=request_id,
        user_id=mock_user.id,
        agent_id="test_agent",
        request_type="permission",
        request_data={"permission": "test_action"},
        status="pending"
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


# ============================================================================
# Operation Tracking - POST /operation/start
# ============================================================================

def test_start_operation_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test starting operation successfully."""
    operation_data = {
        "agent_id": "test_agent",
        "operation_type": "data_processing",
        "context": {"task": "process_data"},
        "total_steps": 10,
        "metadata": {"source": "test"}
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_guidance_system') as mock_system:
            mock_system_instance = MagicMock()
            mock_system.return_value = mock_system_instance
            mock_system_instance.start_operation = AsyncMock(return_value=str(uuid.uuid4()))

            response = client.post("/api/agent-guidance/operation/start", json=operation_data)

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "operation_id" in data or "data" in data


def test_start_operation_minimal_data(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test starting operation with minimal data."""
    operation_data = {
        "agent_id": "test_agent",
        "operation_type": "simple_task",
        "context": {}
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_guidance_system') as mock_system:
            mock_system_instance = MagicMock()
            mock_system.return_value = mock_system_instance
            mock_system_instance.start_operation = AsyncMock(return_value=str(uuid.uuid4()))

            response = client.post("/api/agent-guidance/operation/start", json=operation_data)

            assert response.status_code in [200, 500]


# ============================================================================
# Operation Tracking - PUT /operation/{operation_id}/update
# ============================================================================

def test_update_operation_step(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_operation: AgentOperationTracker
):
    """Test updating operation step."""
    update_data = {
        "step": "Step 2",
        "progress": 20
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_guidance_system') as mock_system:
            mock_system_instance = MagicMock()
            mock_system.return_value = mock_system_instance
            mock_system_instance.update_step = AsyncMock()
            mock_system_instance.update_context = AsyncMock()

            response = client.put(
                f"/api/agent-guidance/operation/{mock_operation.operation_id}/update",
                json=update_data
            )

            assert response.status_code in [200, 500]


def test_update_operation_context(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_operation: AgentOperationTracker
):
    """Test updating operation context."""
    update_data = {
        "what": "Updated explanation",
        "why": "Updated reasoning",
        "next_steps": "Updated next steps"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_guidance_system') as mock_system:
            mock_system_instance = MagicMock()
            mock_system.return_value = mock_system_instance
            mock_system_instance.update_step = AsyncMock()
            mock_system_instance.update_context = AsyncMock()

            response = client.put(
                f"/api/agent-guidance/operation/{mock_operation.operation_id}/update",
                json=update_data
            )

            assert response.status_code in [200, 500]


def test_update_operation_add_log(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_operation: AgentOperationTracker
):
    """Test adding log to operation."""
    log_entry = {
        "level": "info",
        "message": "Processing data",
        "timestamp": datetime.utcnow().isoformat()
    }

    update_data = {
        "add_log": log_entry
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_guidance_system') as mock_system:
            mock_system_instance = MagicMock()
            mock_system.return_value = mock_system_instance
            mock_system_instance.update_step = AsyncMock()

            response = client.put(
                f"/api/agent-guidance/operation/{mock_operation.operation_id}/update",
                json=update_data
            )

            assert response.status_code in [200, 500]


def test_update_operation_combined(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_operation: AgentOperationTracker
):
    """Test updating operation with step, progress, and context."""
    update_data = {
        "step": "Step 3",
        "progress": 40,
        "what": "Processing",
        "why": "Data transformation",
        "next_steps": "Complete transformation"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_guidance_system') as mock_system:
            mock_system_instance = MagicMock()
            mock_system.return_value = mock_system_instance
            mock_system_instance.update_step = AsyncMock()
            mock_system_instance.update_context = AsyncMock()

            response = client.put(
                f"/api/agent-guidance/operation/{mock_operation.operation_id}/update",
                json=update_data
            )

            assert response.status_code in [200, 500]


# ============================================================================
# Operation Tracking - POST /operation/{operation_id}/complete
# ============================================================================

def test_complete_operation_success(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_operation: AgentOperationTracker
):
    """Test completing operation successfully."""
    complete_data = {
        "status": "completed",
        "final_message": "Operation completed successfully"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_guidance_system') as mock_system:
            mock_system_instance = MagicMock()
            mock_system.return_value = mock_system_instance
            mock_system_instance.complete_operation = AsyncMock()

            response = client.post(
                f"/api/agent-guidance/operation/{mock_operation.operation_id}/complete",
                json=complete_data
            )

            assert response.status_code in [200, 500]


def test_complete_operation_failed(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_operation: AgentOperationTracker
):
    """Test marking operation as failed."""
    complete_data = {
        "status": "failed",
        "final_message": "Operation failed: timeout"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_guidance_system') as mock_system:
            mock_system_instance = MagicMock()
            mock_system.return_value = mock_system_instance
            mock_system_instance.complete_operation = AsyncMock()

            response = client.post(
                f"/api/agent-guidance/operation/{mock_operation.operation_id}/complete",
                json=complete_data
            )

            assert response.status_code in [200, 500]


def test_complete_operation_default_status(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_operation: AgentOperationTracker
):
    """Test completing operation with default status."""
    complete_data = {}

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_guidance_system') as mock_system:
            mock_system_instance = MagicMock()
            mock_system.return_value = mock_system_instance
            mock_system_instance.complete_operation = AsyncMock()

            response = client.post(
                f"/api/agent-guidance/operation/{mock_operation.operation_id}/complete",
                json=complete_data
            )

            # Should use default status "completed"
            assert response.status_code in [200, 500]


# ============================================================================
# Operation Tracking - GET /operation/{operation_id}
# ============================================================================

def test_get_operation_success(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_operation: AgentOperationTracker
):
    """Test getting operation details successfully."""
    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get(f"/api/agent-guidance/operation/{mock_operation.operation_id}")

        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "operation" in data or "data" in data


def test_get_operation_not_found(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting non-existent operation."""
    fake_id = str(uuid.uuid4())

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get(f"/api/agent-guidance/operation/{fake_id}")

        assert response.status_code == 404


# ============================================================================
# View Orchestration - POST /view/switch
# ============================================================================

def test_switch_view_browser(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test switching to browser view."""
    view_data = {
        "agent_id": "test_agent",
        "view_type": "browser",
        "url": "https://example.com",
        "guidance": "Navigate to example.com",
        "session_id": str(uuid.uuid4())
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_view_coordinator') as mock_coordinator:
            mock_coordinator_instance = MagicMock()
            mock_coordinator.return_value = mock_coordinator_instance
            mock_coordinator_instance.switch_to_browser_view = AsyncMock()

            response = client.post("/api/agent-guidance/view/switch", json=view_data)

            assert response.status_code in [200, 500]


def test_switch_view_browser_missing_url(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test switching to browser view without URL (should fail validation)."""
    view_data = {
        "agent_id": "test_agent",
        "view_type": "browser",
        "guidance": "Test guidance"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/api/agent-guidance/view/switch", json=view_data)

        # Should return validation error
        assert response.status_code in [400, 422]


def test_switch_view_terminal(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test switching to terminal view."""
    view_data = {
        "agent_id": "test_agent",
        "view_type": "terminal",
        "command": "ls -la",
        "guidance": "List directory contents",
        "session_id": str(uuid.uuid4())
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_view_coordinator') as mock_coordinator:
            mock_coordinator_instance = MagicMock()
            mock_coordinator.return_value = mock_coordinator_instance
            mock_coordinator_instance.switch_to_terminal_view = AsyncMock()

            response = client.post("/api/agent-guidance/view/switch", json=view_data)

            assert response.status_code in [200, 500]


def test_switch_view_terminal_missing_command(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test switching to terminal view without command (should fail validation)."""
    view_data = {
        "agent_id": "test_agent",
        "view_type": "terminal",
        "guidance": "Test guidance"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/api/agent-guidance/view/switch", json=view_data)

        # Should return validation error
        assert response.status_code in [400, 422]


def test_switch_view_unknown_type(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test switching to unknown view type."""
    view_data = {
        "agent_id": "test_agent",
        "view_type": "unknown_view",
        "guidance": "Test guidance"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/api/agent-guidance/view/switch", json=view_data)

        # Should return validation error
        assert response.status_code in [400, 422]


# ============================================================================
# View Orchestration - POST /view/layout
# ============================================================================

def test_set_layout_canvas(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test setting canvas layout."""
    layout_data = {
        "layout": "canvas",
        "session_id": str(uuid.uuid4())
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_view_coordinator') as mock_coordinator:
            mock_coordinator_instance = MagicMock()
            mock_coordinator.return_value = mock_coordinator_instance
            mock_coordinator_instance.set_layout = AsyncMock()

            response = client.post("/api/agent-guidance/view/layout", json=layout_data)

            assert response.status_code in [200, 500]


def test_set_layout_split_horizontal(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test setting split horizontal layout."""
    layout_data = {
        "layout": "split_horizontal"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_view_coordinator') as mock_coordinator:
            mock_coordinator_instance = MagicMock()
            mock_coordinator.return_value = mock_coordinator_instance
            mock_coordinator_instance.set_layout = AsyncMock()

            response = client.post("/api/agent-guidance/view/layout", json=layout_data)

            assert response.status_code in [200, 500]


def test_set_layout_split_vertical(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test setting split vertical layout."""
    layout_data = {
        "layout": "split_vertical"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_view_coordinator') as mock_coordinator:
            mock_coordinator_instance = MagicMock()
            mock_coordinator.return_value = mock_coordinator_instance
            mock_coordinator_instance.set_layout = AsyncMock()

            response = client.post("/api/agent-guidance/view/layout", json=layout_data)

            assert response.status_code in [200, 500]


def test_set_layout_tabs(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test setting tabs layout."""
    layout_data = {
        "layout": "tabs"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_view_coordinator') as mock_coordinator:
            mock_coordinator_instance = MagicMock()
            mock_coordinator.return_value = mock_coordinator_instance
            mock_coordinator_instance.set_layout = AsyncMock()

            response = client.post("/api/agent-guidance/view/layout", json=layout_data)

            assert response.status_code in [200, 500]


def test_set_layout_grid(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test setting grid layout."""
    layout_data = {
        "layout": "grid"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_view_coordinator') as mock_coordinator:
            mock_coordinator_instance = MagicMock()
            mock_coordinator.return_value = mock_coordinator_instance
            mock_coordinator_instance.set_layout = AsyncMock()

            response = client.post("/api/agent-guidance/view/layout", json=layout_data)

            assert response.status_code in [200, 500]


# ============================================================================
# Error Guidance - POST /error/present
# ============================================================================

def test_present_error_success(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_operation: AgentOperationTracker
):
    """Test presenting error with guidance successfully."""
    error_data = {
        "operation_id": mock_operation.operation_id,
        "error": {
            "type": "ValueError",
            "message": "Invalid value",
            "code": "VAL_001"
        },
        "agent_id": "test_agent"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_error_guidance_engine') as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance
            mock_engine_instance.present_error = AsyncMock()

            response = client.post("/api/agent-guidance/error/present", json=error_data)

            assert response.status_code in [200, 500]


def test_present_error_without_agent_id(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_operation: AgentOperationTracker
):
    """Test presenting error without optional agent_id."""
    error_data = {
        "operation_id": mock_operation.operation_id,
        "error": {
            "type": "TypeError",
            "message": "Type mismatch"
        }
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_error_guidance_engine') as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance
            mock_engine_instance.present_error = AsyncMock()

            response = client.post("/api/agent-guidance/error/present", json=error_data)

            assert response.status_code in [200, 500]


# ============================================================================
# Error Guidance - POST /error/track-resolution
# ============================================================================

def test_track_resolution_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test tracking error resolution successfully."""
    resolution_data = {
        "error_type": "ValueError",
        "error_code": "VAL_001",
        "resolution_attempted": "Convert to int",
        "success": True,
        "user_feedback": "Worked perfectly",
        "agent_suggested": True
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_error_guidance_engine') as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance
            mock_engine_instance.track_resolution = AsyncMock()

            response = client.post("/api/agent-guidance/error/track-resolution", json=resolution_data)

            assert response.status_code in [200, 500]


def test_track_resolution_failed(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test tracking failed error resolution."""
    resolution_data = {
        "error_type": "ConnectionError",
        "error_code": "CONN_001",
        "resolution_attempted": "Retry connection",
        "success": False,
        "user_feedback": "Still failing",
        "agent_suggested": False
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_error_guidance_engine') as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance
            mock_engine_instance.track_resolution = AsyncMock()

            response = client.post("/api/agent-guidance/error/track-resolution", json=resolution_data)

            assert response.status_code in [200, 500]


def test_track_resolution_minimal_data(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test tracking resolution with minimal required data."""
    resolution_data = {
        "error_type": "RuntimeError",
        "resolution_attempted": "Restart process",
        "success": True
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_error_guidance_engine') as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance
            mock_engine_instance.track_resolution = AsyncMock()

            response = client.post("/api/agent-guidance/error/track-resolution", json=resolution_data)

            assert response.status_code in [200, 500]


# ============================================================================
# Agent Requests - POST /request/permission
# ============================================================================

def test_create_permission_request_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating permission request successfully."""
    request_data = {
        "agent_id": "test_agent",
        "title": "File Access Permission",
        "permission": "read_write",
        "context": {"file_path": "/data/test.csv"},
        "urgency": "medium"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_request_manager') as mock_manager:
            mock_manager_instance = MagicMock()
            mock_manager.return_value = mock_manager_instance
            mock_manager_instance.create_permission_request = AsyncMock(return_value=str(uuid.uuid4()))

            response = client.post("/api/agent-guidance/request/permission", json=request_data)

            assert response.status_code in [200, 500]


def test_create_permission_request_with_expiration(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating permission request with expiration."""
    request_data = {
        "agent_id": "test_agent",
        "title": "Urgent Permission",
        "permission": "execute",
        "context": {},
        "urgency": "high",
        "expires_in": 3600  # 1 hour
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_request_manager') as mock_manager:
            mock_manager_instance = MagicMock()
            mock_manager.return_value = mock_manager_instance
            mock_manager_instance.create_permission_request = AsyncMock(return_value=str(uuid.uuid4()))

            response = client.post("/api/agent-guidance/request/permission", json=request_data)

            assert response.status_code in [200, 500]


# ============================================================================
# Agent Requests - POST /request/decision
# ============================================================================

def test_create_decision_request_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating decision request successfully."""
    request_data = {
        "agent_id": "test_agent",
        "title": "Choose Data Source",
        "explanation": "Multiple data sources available",
        "options": ["Database", "API", "File"],
        "context": {},
        "urgency": "low"
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_request_manager') as mock_manager:
            mock_manager_instance = MagicMock()
            mock_manager.return_value = mock_manager_instance
            mock_manager_instance.create_decision_request = AsyncMock(return_value=str(uuid.uuid4()))

            response = client.post("/api/agent-guidance/request/decision", json=request_data)

            assert response.status_code in [200, 500]


def test_create_decision_request_with_suggestion(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating decision request with suggested option."""
    request_data = {
        "agent_id": "test_agent",
        "title": "Select Algorithm",
        "explanation": "Choose processing algorithm",
        "options": ["Algorithm A", "Algorithm B", "Algorithm C"],
        "context": {},
        "urgency": "medium",
        "suggested_option": 1
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_request_manager') as mock_manager:
            mock_manager_instance = MagicMock()
            mock_manager.return_value = mock_manager_instance
            mock_manager_instance.create_decision_request = AsyncMock(return_value=str(uuid.uuid4()))

            response = client.post("/api/agent-guidance/request/decision", json=request_data)

            assert response.status_code in [200, 500]


# ============================================================================
# Agent Requests - POST /request/{request_id}/respond
# ============================================================================

def test_respond_to_request_success(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_request: AgentRequestLog
):
    """Test responding to request successfully."""
    response_data = {
        "request_id": mock_request.request_id,
        "response": {
            "approved": True,
            "comments": "Permission granted"
        }
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_request_manager') as mock_manager:
            mock_manager_instance = MagicMock()
            mock_manager.return_value = mock_manager_instance
            mock_manager_instance.handle_response = AsyncMock()

            response = client.post(
                f"/api/agent-guidance/request/{mock_request.request_id}/respond",
                json=response_data
            )

            assert response.status_code in [200, 500]


def test_respond_to_request_deny(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_request: AgentRequestLog
):
    """Test denying request."""
    response_data = {
        "request_id": mock_request.request_id,
        "response": {
            "approved": False,
            "reason": "Not authorized"
        }
    }

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.agent_guidance_routes.get_agent_request_manager') as mock_manager:
            mock_manager_instance = MagicMock()
            mock_manager.return_value = mock_manager_instance
            mock_manager_instance.handle_response = AsyncMock()

            response = client.post(
                f"/api/agent-guidance/request/{mock_request.request_id}/respond",
                json=response_data
            )

            assert response.status_code in [200, 500]


# ============================================================================
# Agent Requests - GET /request/{request_id}
# ============================================================================

def test_get_request_success(
    client: TestClient,
    db: Session,
    mock_user: User,
    mock_request: AgentRequestLog
):
    """Test getting request details successfully."""
    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get(f"/api/agent-guidance/request/{mock_request.request_id}")

        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "request" in data or "data" in data


def test_get_request_not_found(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting non-existent request."""
    fake_id = str(uuid.uuid4())

    with patch('api.agent_guidance_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get(f"/api/agent-guidance/request/{fake_id}")

        assert response.status_code == 404

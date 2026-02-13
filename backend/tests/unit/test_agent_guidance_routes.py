"""
Unit tests for Agent Guidance API Routes

Tests cover:
- Operation tracking (start, update, complete, get)
- View orchestration (switch, layout)
- Error guidance (present, track resolution)
- Permission/decision requests (create, respond, get)
- Request/response validation
- Error handling

Note: Production file has typo: agent_guidance_routes.py (not guidance)
This test imports from the actual production file path.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi.testclient import TestClient

# Import from actual production file (note: typo in production filename)
from api.agent_guidance_routes import router
from core.models import AgentOperationTracker, AgentRequestLog, User


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def mock_user():
    """Mock current user."""
    user = MagicMock()
    user.id = "test_user_123"
    user.email = "test@example.com"
    user.username = "testuser"
    return user


@pytest.fixture
def mock_agent_guidance_system():
    """Mock agent guidance system."""
    system = MagicMock()
    system.start_operation = AsyncMock(return_value="op_test_123")
    system.update_step = AsyncMock(return_value=True)
    system.update_context = AsyncMock(return_value=True)
    system.complete_operation = AsyncMock(return_value=True)
    return system


@pytest.fixture
def mock_view_coordinator():
    """Mock view coordinator."""
    coordinator = MagicMock()
    coordinator.switch_to_browser_view = AsyncMock(return_value=True)
    coordinator.switch_to_terminal_view = AsyncMock(return_value=True)
    coordinator.set_layout = AsyncMock(return_value=True)
    return coordinator


@pytest.fixture
def mock_error_guidance_engine():
    """Mock error guidance engine."""
    engine = MagicMock()
    engine.present_error = AsyncMock(return_value=True)
    engine.track_resolution = AsyncMock(return_value=True)
    return engine


@pytest.fixture
def mock_agent_request_manager():
    """Mock agent request manager."""
    manager = MagicMock()
    manager.create_permission_request = AsyncMock(return_value="req_perm_123")
    manager.create_decision_request = AsyncMock(return_value="req_dec_123")
    manager.handle_response = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def client(
    mock_db,
    mock_user,
    mock_agent_guidance_system,
    mock_view_coordinator,
    mock_error_guidance_engine,
    mock_agent_request_manager
):
    """Test client with mocked dependencies using patch."""
    with patch('api.agent_guidance_routes.get_db', return_value=mock_db), \
         patch('api.agent_guidance_routes.get_current_user', return_value=mock_user), \
         patch('tools.agent_guidance_canvas_tool.get_agent_guidance_system', return_value=mock_agent_guidance_system), \
         patch('core.view_coordinator.get_view_coordinator', return_value=mock_view_coordinator), \
         patch('core.error_guidance_engine.get_error_guidance_engine', return_value=mock_error_guidance_engine), \
         patch('core.agent_request_manager.get_agent_request_manager', return_value=mock_agent_request_manager):

        yield TestClient(router)


@pytest.fixture
def sample_agent_id():
    """Sample agent ID for testing."""
    return "agent_test_123"


@pytest.fixture
def sample_operation_id():
    """Sample operation ID for testing."""
    return "op_test_123"


@pytest.fixture
def sample_request_id():
    """Sample request ID for testing."""
    return "req_test_123"


# =============================================================================
# Operation Tracking Tests
# =============================================================================

class TestOperationTracking:
    """Tests for operation tracking endpoints."""

    def test_start_operation_basic(self, client, mock_agent_guidance_system, sample_agent_id):
        """Test starting a basic operation."""
        request = {
            "agent_id": sample_agent_id,
            "operation_type": "test_operation",
            "context": {"key": "value"}
        }

        response = client.post("/api/agent-guidance/operation/start", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "operation_id" in data["data"]
        mock_agent_guidance_system.start_operation.assert_called_once()

    def test_start_operation_with_total_steps(self, client, mock_agent_guidance_system, sample_agent_id):
        """Test starting operation with total steps."""
        request = {
            "agent_id": sample_agent_id,
            "operation_type": "multi_step_operation",
            "context": {},
            "total_steps": 10
        }

        response = client.post("/api/agent-guidance/operation/start", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_agent_guidance_system.start_operation.assert_called_once()

    def test_update_operation_progress(self, client, mock_agent_guidance_system, sample_operation_id):
        """Test updating operation progress."""
        request = {
            "step": "Processing data",
            "progress": 50,
            "what": "Analyzing user input",
            "why": "To determine next action"
        }

        response = client.put(f"/api/agent-guidance/operation/{sample_operation_id}/update", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_agent_guidance_system.update_step.assert_called_once()
        mock_agent_guidance_system.update_context.assert_called_once()

    def test_complete_operation_success(self, client, mock_agent_guidance_system, sample_operation_id):
        """Test completing operation successfully."""
        request = {
            "status": "completed",
            "final_message": "Operation completed successfully"
        }

        response = client.post(f"/api/agent-guidance/operation/{sample_operation_id}/complete", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_agent_guidance_system.complete_operation.assert_called_once()

    def test_get_operation_success(self, client, mock_db, sample_operation_id):
        """Test getting operation details."""
        mock_operation = MagicMock()
        mock_operation.operation_id = sample_operation_id
        mock_operation.agent_id = "agent_123"
        mock_operation.operation_type = "test_operation"
        mock_operation.status = "running"
        mock_operation.current_step = "Processing"
        mock_operation.total_steps = 10
        mock_operation.current_step_index = 5
        mock_operation.progress = 50
        mock_operation.what_explanation = "What"
        mock_operation.why_explanation = "Why"
        mock_operation.next_steps = "Next"
        mock_operation.logs = []
        mock_operation.metadata = {}
        mock_operation.started_at = datetime.now()
        mock_operation.completed_at = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation

        response = client.get(f"/api/agent-guidance/operation/{sample_operation_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "operation" in data["data"]

    def test_get_operation_not_found(self, client, mock_db, sample_operation_id):
        """Test getting non-existent operation."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.get(f"/api/agent-guidance/operation/{sample_operation_id}")

        assert response.status_code == 404


# =============================================================================
# View Orchestration Tests
# =============================================================================

class TestViewOrchestration:
    """Tests for view orchestration endpoints."""

    def test_switch_view_to_browser(self, client, mock_view_coordinator, sample_agent_id):
        """Test switching to browser view."""
        request = {
            "agent_id": sample_agent_id,
            "view_type": "browser",
            "url": "https://example.com",
            "guidance": "Navigate to example.com",
            "session_id": "session_123"
        }

        response = client.post("/api/agent-guidance/view/switch", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_view_coordinator.switch_to_browser_view.assert_called_once()

    def test_switch_view_to_browser_no_url(self, client, mock_view_coordinator, sample_agent_id):
        """Test switching to browser view without URL fails."""
        request = {
            "agent_id": sample_agent_id,
            "view_type": "browser",
            "guidance": "Test"
        }

        response = client.post("/api/agent-guidance/view/switch", json=request)

        assert response.status_code == 400

    def test_switch_view_to_terminal(self, client, mock_view_coordinator, sample_agent_id):
        """Test switching to terminal view."""
        request = {
            "agent_id": sample_agent_id,
            "view_type": "terminal",
            "command": "ls -la",
            "guidance": "List directory contents"
        }

        response = client.post("/api/agent-guidance/view/switch", json=request)

        assert response.status_code == 200
        mock_view_coordinator.switch_to_terminal_view.assert_called_once()

    def test_set_layout_canvas(self, client, mock_view_coordinator):
        """Test setting canvas layout."""
        request = {
            "layout": "canvas",
            "session_id": "session_123"
        }

        response = client.post("/api/agent-guidance/view/layout", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_view_coordinator.set_layout.assert_called_once()

    def test_set_layout_split_horizontal(self, client, mock_view_coordinator):
        """Test setting split horizontal layout."""
        request = {
            "layout": "split_horizontal"
        }

        response = client.post("/api/agent-guidance/view/layout", json=request)

        assert response.status_code == 200

    def test_set_layout_grid(self, client, mock_view_coordinator):
        """Test setting grid layout."""
        request = {
            "layout": "grid"
        }

        response = client.post("/api/agent-guidance/view/layout", json=request)

        assert response.status_code == 200


# =============================================================================
# Error Guidance Tests
# =============================================================================

class TestErrorGuidance:
    """Tests for error guidance endpoints."""

    def test_present_error_basic(self, client, mock_error_guidance_engine):
        """Test presenting basic error."""
        request = {
            "operation_id": "op_123",
            "error": {
                "type": "ValidationError",
                "message": "Invalid input",
                "details": {"field": "email", "issue": "Invalid format"}
            }
        }

        response = client.post("/api/agent-guidance/error/present", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_error_guidance_engine.present_error.assert_called_once()

    def test_track_resolution_success(self, client, mock_error_guidance_engine):
        """Test tracking successful resolution."""
        request = {
            "error_type": "ValidationError",
            "error_code": "INVALID_EMAIL",
            "resolution_attempted": "Fixed email format",
            "success": True
        }

        response = client.post("/api/agent-guidance/error/track-resolution", json=request)

        assert response.status_code == 200
        mock_error_guidance_engine.track_resolution.assert_called_once()

    def test_track_resolution_failure(self, client, mock_error_guidance_engine):
        """Test tracking failed resolution."""
        request = {
            "error_type": "NetworkError",
            "resolution_attempted": "Retried immediately",
            "success": False
        }

        response = client.post("/api/agent-guidance/error/track-resolution", json=request)

        assert response.status_code == 200


# =============================================================================
# Permission/Decision Request Tests
# =============================================================================

class TestPermissionDecisionRequests:
    """Tests for permission and decision request endpoints."""

    def test_request_permission_basic(self, client, mock_agent_request_manager, sample_agent_id):
        """Test requesting basic permission."""
        request = {
            "agent_id": sample_agent_id,
            "title": "Camera Access",
            "permission": "camera",
            "context": {"reason": "To scan document"}
        }

        response = client.post("/api/agent-guidance/request/permission", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "request_id" in data["data"]
        mock_agent_request_manager.create_permission_request.assert_called_once()

    def test_request_permission_with_urgency(self, client, mock_agent_request_manager, sample_agent_id):
        """Test requesting permission with urgency."""
        request = {
            "agent_id": sample_agent_id,
            "title": "Location Access",
            "permission": "location",
            "context": {},
            "urgency": "high"
        }

        response = client.post("/api/agent-guidance/request/permission", json=request)

        assert response.status_code == 200

    def test_request_decision_basic(self, client, mock_agent_request_manager, sample_agent_id):
        """Test requesting basic decision."""
        request = {
            "agent_id": sample_agent_id,
            "title": "Choose Integration",
            "explanation": "Which CRM should I connect to?",
            "options": ["Salesforce", "HubSpot", "Pipedrive"],
            "context": {"integrations": ["all"]}
        }

        response = client.post("/api/agent-guidance/request/decision", json=request)

        assert response.status_code == 200
        mock_agent_request_manager.create_decision_request.assert_called_once()

    def test_respond_to_request(self, client, mock_agent_request_manager, sample_request_id):
        """Test responding to a request."""
        request = {
            "request_id": sample_request_id,
            "response": {"approved": True, "comment": "Granted"}
        }

        response = client.post(f"/api/agent-guidance/request/{sample_request_id}/respond", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_agent_request_manager.handle_response.assert_called_once()

    def test_get_request_success(self, client, mock_db, sample_request_id):
        """Test getting request details."""
        mock_request = MagicMock()
        mock_request.request_id = sample_request_id
        mock_request.agent_id = "agent_123"
        mock_request.request_type = "permission"
        mock_request.request_data = {"permission": "camera"}
        mock_request.user_response = None
        mock_request.created_at = datetime.now()
        mock_request.responded_at = None
        mock_request.expires_at = None
        mock_request.revoked = False

        mock_db.query.return_value.filter.return_value.first.return_value = mock_request

        response = client.get(f"/api/agent-guidance/request/{sample_request_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "request" in data["data"]

    def test_get_request_not_found(self, client, mock_db, sample_request_id):
        """Test getting non-existent request."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.get(f"/api/agent-guidance/request/{sample_request_id}")

        assert response.status_code == 404


# =============================================================================
# Request Validation Tests
# =============================================================================

class TestRequestValidation:
    """Tests for request validation."""

    def test_start_operation_missing_agent_id(self, client):
        """Test start operation fails without agent_id."""
        request = {
            "operation_type": "test"
        }

        response = client.post("/api/agent-guidance/operation/start", json=request)

        assert response.status_code == 422  # Validation error

    def test_start_operation_missing_operation_type(self, client):
        """Test start operation fails without operation_type."""
        request = {
            "agent_id": "agent_123"
        }

        response = client.post("/api/agent-guidance/operation/start", json=request)

        assert response.status_code == 422

    def test_request_permission_missing_title(self, client):
        """Test request permission fails without title."""
        request = {
            "agent_id": "agent_123",
            "permission": "camera",
            "context": {}
        }

        response = client.post("/api/agent-guidance/request/permission", json=request)

        assert response.status_code == 422

    def test_request_decision_missing_options(self, client):
        """Test request decision fails without options."""
        request = {
            "agent_id": "agent_123",
            "title": "Choose",
            "explanation": "Pick one",
            "context": {}
        }

        response = client.post("/api/agent-guidance/request/decision", json=request)

        assert response.status_code == 422


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_start_operation_exception(self, client, mock_agent_guidance_system, sample_agent_id):
        """Test handling exception when starting operation."""
        mock_agent_guidance_system.start_operation.side_effect = Exception("Database error")

        request = {
            "agent_id": sample_agent_id,
            "operation_type": "test",
            "context": {}
        }

        response = client.post("/api/agent-guidance/operation/start", json=request)

        assert response.status_code == 500

    def test_update_operation_exception(self, client, mock_agent_guidance_system, sample_operation_id):
        """Test handling exception when updating operation."""
        mock_agent_guidance_system.update_step.side_effect = Exception("Update failed")

        request = {
            "step": "Test",
            "progress": 50
        }

        response = client.put(f"/api/agent-guidance/operation/{sample_operation_id}/update", json=request)

        assert response.status_code == 500

    def test_switch_view_exception(self, client, mock_view_coordinator, sample_agent_id):
        """Test handling exception when switching view."""
        mock_view_coordinator.switch_to_browser_view.side_effect = Exception("View error")

        request = {
            "agent_id": sample_agent_id,
            "view_type": "browser",
            "url": "https://example.com",
            "guidance": "Test"
        }

        response = client.post("/api/agent-guidance/view/switch", json=request)

        assert response.status_code == 500

    def test_present_error_exception(self, client, mock_error_guidance_engine):
        """Test handling exception when presenting error."""
        mock_error_guidance_engine.present_error.side_effect = Exception("Error engine failed")

        request = {
            "operation_id": "op_123",
            "error": {"type": "Test", "message": "Test error"}
        }

        response = client.post("/api/agent-guidance/error/present", json=request)

        assert response.status_code == 500

    def test_create_permission_request_exception(self, client, mock_agent_request_manager, sample_agent_id):
        """Test handling exception when creating permission request."""
        mock_agent_request_manager.create_permission_request.side_effect = Exception("Request failed")

        request = {
            "agent_id": sample_agent_id,
            "title": "Test",
            "permission": "camera",
            "context": {}
        }

        response = client.post("/api/agent-guidance/request/permission", json=request)

        assert response.status_code == 500

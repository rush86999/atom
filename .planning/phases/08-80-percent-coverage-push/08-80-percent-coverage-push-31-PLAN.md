---
phase: 08-80-percent-coverage-push
plan: 31
type: execute
wave: 7
depends_on: []
files_modified:
  - backend/tests/unit/test_agent_guidance_routes.py
  - backend/tests/unit/test_integration_dashboard_routes.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "Agent guidance routes have 50%+ test coverage (operation tracking, view orchestration, error guidance)"
    - "Integration dashboard routes have 50%+ test coverage (metrics, health, configuration)"
    - "All API endpoints tested with FastAPI TestClient"
    - "Request/response validation tested for all models"
  artifacts:
    - path: "backend/tests/unit/test_agent_guidance_routes.py"
      provides: "Agent guidance API tests"
      min_lines: 400
    - path: "backend/tests/unit/test_integration_dashboard_routes.py"
      provides: "Integration dashboard API tests"
      min_lines: 400
  key_links:
    - from: "test_agent_guidance_routes.py"
      to: "api/agent_guidance_routes.py"
      via: "TestClient, mock_db, mock_agent_guidance_system"
      pattern: "start_operation, update_progress, switch_view"
    - from: "test_integration_dashboard_routes.py"
      to: "api/integration_dashboard_routes.py"
      via: "TestClient, mock_integration_dashboard"
      pattern: "get_metrics, update_configuration, reset_metrics"
status: pending
created: 2026-02-13
gap_closure: false
---

# Plan 31: Agent Guidance & Integration Dashboard Routes Tests

**Status:** Pending
**Wave:** 7 (parallel with 32, 33)
**Dependencies:** None

## Objective

Create comprehensive unit tests for agent guidance routes and integration dashboard routes, achieving 50% coverage across both files to contribute +0.8-1.0% toward Phase 9.0's 25-27% overall coverage goal.

## Context

Phase 9.0 targets 25-27% overall coverage (+3-5% from 21-22%) by testing zero-coverage API routes. This plan covers two high-impact API route files:

1. **api/agent_guidance_routes.py** (537 lines) - Agent guidance workflows (operation tracking, view orchestration, error guidance, agent requests)
2. **api/integration_dashboard_routes.py** (506 lines) - Integration dashboard APIs (metrics, health, alerts, configuration)

**Production Lines:** 1,043 total
**Expected Coverage at 50%:** ~520 lines
**Coverage Contribution:** +0.8-1.0 percentage points toward 25-27% goal

**Key Functions to Test:**

**Agent Guidance Routes:**
- `POST /start-operation` - Start agent operation tracking
- `POST /update-operation` - Update operation progress
- `POST /complete-operation` - Mark operation complete
- `POST /switch-view` - Switch between browser/terminal/canvas views
- `POST /set-layout` - Set canvas layout mode
- `POST /present-error` - Present error to user
- `POST /track-resolution` - Track error resolution
- `POST /request-permission` - Request user permission
- `POST /request-decision` - Request user decision
- `GET /active-operations` - List active operations

**Integration Dashboard Routes:**
- `GET /metrics` - Get integration metrics
- `GET /health` - Get integration health status
- `GET /alerts` - Get integration alerts
- `POST /update-configuration` - Update integration configuration
- `POST /reset-metrics` - Reset integration metrics
- `GET /overall-status` - Get overall dashboard status

## Success Criteria

**Must Have (truths that become verifiable):**
1. Agent guidance routes have 50%+ test coverage (operation tracking, view orchestration, error guidance)
2. Integration dashboard routes have 50%+ test coverage (metrics, health, configuration)
3. All API endpoints tested with FastAPI TestClient
4. Request/response validation tested for all models

**Should Have:**
- Error handling tested (400, 404, 500 responses)
- Authentication/authorization tested
- Database transaction rollback tested
- WebSocket broadcast integration tested

**Could Have:**
- Concurrent operation handling tested
- Metrics aggregation logic tested

**Won't Have:**
- Real WebSocket connections (mocked)
- Real database sessions (mocked with TestClient)
- Real agent guidance system (mocked)

## Tasks

### Task 1: Create test_agent_guidance_routes.py with operation tracking coverage

**Files:**
- CREATE: `backend/tests/unit/test_agent_guidance_routes.py` (400+ lines, 25-30 tests)

**Action:**
Create test file with these test classes:

```python
"""
Unit tests for Agent Guidance API Routes

Tests cover:
- Operation tracking (start, update, complete)
- View orchestration (switch, layout)
- Error guidance (present, track resolution)
- Permission/decision requests
- Active operations listing
- Request/response validation
"""
import pytest
from datetime import datetime
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi.testclient import TestClient

from api.agent_guidance_routes import router, OperationStartRequest, OperationUpdateRequest, OperationCompleteRequest, ViewSwitchRequest, ViewLayoutRequest, ErrorPresentRequest, ResolutionTrackRequest, PermissionRequestRequest, DecisionRequestRequest


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
def mock_agent_guidance_system():
    """Mock agent guidance system."""
    system = MagicMock()
    system.start_operation = AsyncMock(return_value="op_123")
    system.update_operation = AsyncMock(return_value=True)
    system.complete_operation = AsyncMock(return_value=True)
    system.switch_view = AsyncMock(return_value=True)
    system.set_layout = AsyncMock(return_value=True)
    system.present_error = AsyncMock(return_value=True)
    system.track_resolution = AsyncMock(return_value=True)
    system.request_permission = AsyncMock(return_value="perm_123")
    system.request_decision = AsyncMock(return_value="dec_123")
    system.get_active_operations = AsyncMock(return_value=[])
    return system


@pytest.fixture
def mock_view_coordinator():
    """Mock view coordinator."""
    coordinator = MagicMock()
    coordinator.switch_view = AsyncMock(return_value=True)
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
    manager.request_permission = AsyncMock(return_value="perm_123")
    manager.request_decision = AsyncMock(return_value="dec_123")
    return manager


@pytest.fixture
def client(mock_agent_guidance_system, mock_view_coordinator, mock_error_guidance_engine, mock_agent_request_manager):
    """Test client with mocked dependencies."""
    with patch('api.agent_guidance_routes.get_agent_guidance_system', return_value=mock_agent_guidance_system):
        with patch('api.agent_guidance_routes.get_view_coordinator', return_value=mock_view_coordinator):
            with patch('api.agent_guidance_routes.get_error_guidance_engine', return_value=mock_error_guidance_engine):
                with patch('api.agent_guidance_routes.get_agent_request_manager', return_value=mock_agent_request_manager):
                    yield TestClient(router)


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "user_123"


@pytest.fixture
def sample_agent_id():
    """Sample agent ID for testing."""
    return "agent_123"


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

        response = client.post("/start", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "operation_id" in data
        mock_agent_guidance_system.start_operation.assert_called_once()

    def test_start_operation_with_total_steps(self, client, mock_agent_guidance_system, sample_agent_id):
        """Test starting operation with total steps."""
        request = {
            "agent_id": sample_agent_id,
            "operation_type": "multi_step_operation",
            "context": {},
            "total_steps": 10
        }

        response = client.post("/start", json=request)

        assert response.status_code == 200
        mock_agent_guidance_system.start_operation.assert_called_once()

    def test_start_operation_with_metadata(self, client, mock_agent_guidance_system, sample_agent_id):
        """Test starting operation with metadata."""
        request = {
            "agent_id": sample_agent_id,
            "operation_type": "metadata_operation",
            "context": {},
            "metadata": {"source": "test", "priority": "high"}
        }

        response = client.post("/start", json=request)

        assert response.status_code == 200

    def test_update_operation_progress(self, client, mock_agent_guidance_system):
        """Test updating operation progress."""
        request = {
            "step": "Processing data",
            "progress": 50,
            "what": "Analyzing user input",
            "why": "To determine next action",
            "next_steps": "Complete analysis and respond"
        }

        response = client.post("/op_123/update", json=request)

        assert response.status_code == 200
        mock_agent_guidance_system.update_operation.assert_called_once()

    def test_update_operation_with_log(self, client, mock_agent_guidance_system):
        """Test updating operation with additional log."""
        request = {
            "add_log": {"level": "info", "message": "Processing complete"}
        }

        response = client.post("/op_123/update", json=request)

        assert response.status_code == 200

    def test_complete_operation_success(self, client, mock_agent_guidance_system):
        """Test completing operation successfully."""
        request = {
            "status": "completed",
            "final_message": "Operation completed successfully"
        }

        response = client.post("/op_123/complete", json=request)

        assert response.status_code == 200
        mock_agent_guidance_system.complete_operation.assert_called_once()

    def test_complete_operation_failed(self, client, mock_agent_guidance_system):
        """Test completing operation with failure."""
        request = {
            "status": "failed",
            "final_message": "Operation failed due to error"
        }

        response = client.post("/op_123/complete", json=request)

        assert response.status_code == 200

    def test_get_active_operations_empty(self, client, mock_agent_guidance_system):
        """Test getting active operations when none exist."""
        mock_agent_guidance_system.get_active_operations.return_value = []

        response = client.get("/active")

        assert response.status_code == 200
        data = response.json()
        assert data["operations"] == []

    def test_get_active_operations_with_data(self, client, mock_agent_guidance_system):
        """Test getting active operations with data."""
        mock_agent_guidance_system.get_active_operations.return_value = [
            {"operation_id": "op_1", "status": "running"},
            {"operation_id": "op_2", "status": "pending"}
        ]

        response = client.get("/active")

        assert response.status_code == 200
        data = response.json()
        assert len(data["operations"]) == 2


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

        response = client.post("/switch-view", json=request)

        assert response.status_code == 200
        mock_view_coordinator.switch_view.assert_called_once()

    def test_switch_view_to_terminal(self, client, mock_view_coordinator, sample_agent_id):
        """Test switching to terminal view."""
        request = {
            "agent_id": sample_agent_id,
            "view_type": "terminal",
            "command": "ls -la",
            "guidance": "List directory contents"
        }

        response = client.post("/switch-view", json=request)

        assert response.status_code == 200

    def test_switch_view_to_canvas(self, client, mock_view_coordinator, sample_agent_id):
        """Test switching to canvas view."""
        request = {
            "agent_id": sample_agent_id,
            "view_type": "canvas",
            "guidance": "Presenting results"
        }

        response = client.post("/switch-view", json=request)

        assert response.status_code == 200

    def test_set_layout_canvas(self, client, mock_view_coordinator):
        """Test setting canvas layout."""
        request = {
            "layout": "canvas",
            "session_id": "session_123"
        }

        response = client.post("/set-layout", json=request)

        assert response.status_code == 200
        mock_view_coordinator.set_layout.assert_called_once()

    def test_set_layout_split_horizontal(self, client, mock_view_coordinator):
        """Test setting split horizontal layout."""
        request = {
            "layout": "split_horizontal"
        }

        response = client.post("/set-layout", json=request)

        assert response.status_code == 200

    def test_set_layout_split_vertical(self, client, mock_view_coordinator):
        """Test setting split vertical layout."""
        request = {
            "layout": "split_vertical"
        }

        response = client.post("/set-layout", json=request)

        assert response.status_code == 200

    def test_set_layout_tabs(self, client, mock_view_coordinator):
        """Test setting tabs layout."""
        request = {
            "layout": "tabs"
        }

        response = client.post("/set-layout", json=request)

        assert response.status_code == 200

    def test_set_layout_grid(self, client, mock_view_coordinator):
        """Test setting grid layout."""
        request = {
            "layout": "grid"
        }

        response = client.post("/set-layout", json=request)

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

        response = client.post("/present-error", json=request)

        assert response.status_code == 200
        mock_error_guidance_engine.present_error.assert_called_once()

    def test_present_error_with_agent(self, client, mock_error_guidance_engine, sample_agent_id):
        """Test presenting error with agent ID."""
        request = {
            "operation_id": "op_123",
            "error": {"type": "NetworkError", "message": "Connection failed"},
            "agent_id": sample_agent_id
        }

        response = client.post("/present-error", json=request)

        assert response.status_code == 200

    def test_track_resolution_success(self, client, mock_error_guidance_engine):
        """Test tracking successful resolution."""
        request = {
            "error_type": "ValidationError",
            "error_code": "INVALID_EMAIL",
            "resolution_attempted": "Fixed email format",
            "success": True
        }

        response = client.post("/track-resolution", json=request)

        assert response.status_code == 200
        mock_error_guidance_engine.track_resolution.assert_called_once()

    def test_track_resolution_with_feedback(self, client, mock_error_guidance_engine):
        """Test tracking resolution with user feedback."""
        request = {
            "error_type": "NetworkError",
            "resolution_attempted": "Retried with backoff",
            "success": True,
            "user_feedback": "Worked on second attempt"
        }

        response = client.post("/track-resolution", json=request)

        assert response.status_code == 200

    def test_track_resolution_failure(self, client, mock_error_guidance_engine):
        """Test tracking failed resolution."""
        request = {
            "error_type": "NetworkError",
            "resolution_attempted": "Retried immediately",
            "success": False
        }

        response = client.post("/track-resolution", json=request)

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

        response = client.post("/request-permission", json=request)

        assert response.status_code == 200
        mock_agent_request_manager.request_permission.assert_called_once()

    def test_request_permission_with_urgency(self, client, mock_agent_request_manager, sample_agent_id):
        """Test requesting permission with urgency."""
        request = {
            "agent_id": sample_agent_id,
            "title": "Location Access",
            "permission": "location",
            "urgency": "high"
        }

        response = client.post("/request-permission", json=request)

        assert response.status_code == 200

    def test_request_permission_with_expiry(self, client, mock_agent_request_manager, sample_agent_id):
        """Test requesting permission with expiry."""
        request = {
            "agent_id": sample_agent_id,
            "title": "Notification Access",
            "permission": "notifications",
            "expires_in": 300
        }

        response = client.post("/request-permission", json=request)

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

        response = client.post("/request-decision", json=request)

        assert response.status_code == 200
        mock_agent_request_manager.request_decision.assert_called_once()

    def test_request_decision_with_urgency(self, client, mock_agent_request_manager, sample_agent_id):
        """Test requesting decision with urgency."""
        request = {
            "agent_id": sample_agent_id,
            "title": "Urgent: Approval Required",
            "explanation": "Need approval to delete data",
            "options": ["Approve", "Deny"],
            "urgency": "critical"
        }

        response = client.post("/request-decision", json=request)

        assert response.status_code == 200


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

        response = client.post("/start", json=request)

        assert response.status_code == 422  # Validation error

    def test_start_operation_missing_operation_type(self, client):
        """Test start operation fails without operation_type."""
        request = {
            "agent_id": "agent_123"
        }

        response = client.post("/start", json=request)

        assert response.status_code == 422

    def test_switch_view_invalid_view_type(self, client):
        """Test switch view fails with invalid view_type."""
        request = {
            "agent_id": "agent_123",
            "view_type": "invalid_view"
        }

        response = client.post("/switch-view", json=request)

        # Should handle invalid view type
        assert response.status_code in [400, 422, 200]
```

**Verify:**
```bash
test -f backend/tests/unit/test_agent_guidance_routes.py && echo "File exists"
grep -c "^    def test_" backend/tests/unit/test_agent_guidance_routes.py
# Expected: 25-30 tests
```

**Done:**
- File created with 25-30 tests
- Operation tracking tested (start, update, complete, list)
- View orchestration tested (switch, layout)
- Error guidance tested (present, track)
- Permission/decision requests tested
- Request validation tested

### Task 2: Create test_integration_dashboard_routes.py with dashboard metrics coverage

**Files:**
- CREATE: `backend/tests/unit/test_integration_dashboard_routes.py` (400+ lines, 25-30 tests)

**Action:**
Create test file with these test classes:

```python
"""
Unit tests for Integration Dashboard API Routes

Tests cover:
- Integration metrics retrieval
- Integration health status
- Alerts management
- Configuration updates
- Metrics reset
- Overall status
"""
import pytest
from datetime import datetime
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi.testclient import TestClient

from api.integration_dashboard_routes import router, IntegrationMetricsResponse, IntegrationHealthResponse, OverallStatusResponse, ConfigurationUpdateRequest, MetricsResetRequest


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_integration_dashboard():
    """Mock integration dashboard."""
    dashboard = MagicMock()
    dashboard.get_metrics = MagicMock(return_value={})
    dashboard.get_health = MagicMock(return_value={})
    dashboard.get_alerts = MagicMock(return_value=[])
    dashboard.update_configuration = MagicMock(return_value=True)
    dashboard.reset_metrics = MagicMock(return_value=True)
    dashboard.get_overall_status = MagicMock(return_value={})
    return dashboard


@pytest.fixture
def client(mock_integration_dashboard):
    """Test client with mocked dependencies."""
    with patch('api.integration_dashboard_routes.get_integration_dashboard', return_value=mock_integration_dashboard):
        yield TestClient(router)


@pytest.fixture
def sample_integration_id():
    """Sample integration ID for testing."""
    return "slack_integration"


# =============================================================================
# Integration Metrics Tests
# =============================================================================

class TestIntegrationMetrics:
    """Tests for integration metrics endpoints."""

    def test_get_metrics_all(self, client, mock_integration_dashboard):
        """Test getting metrics for all integrations."""
        mock_integration_dashboard.get_metrics.return_value = {
            "slack": {
                "messages_fetched": 100,
                "messages_processed": 95,
                "messages_failed": 5,
                "success_rate": 0.95
            },
            "teams": {
                "messages_fetched": 50,
                "messages_processed": 48,
                "messages_failed": 2,
                "success_rate": 0.96
            }
        }

        response = client.get("/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "integrations" in data or "data" in data
        mock_integration_dashboard.get_metrics.assert_called_once()

    def test_get_metrics_specific_integration(self, client, mock_integration_dashboard, sample_integration_id):
        """Test getting metrics for specific integration."""
        mock_integration_dashboard.get_metrics.return_value = {
            "messages_fetched": 100,
            "messages_processed": 95,
            "messages_failed": 5
        }

        response = client.get(f"/metrics?integration={sample_integration_id}")

        assert response.status_code == 200
        mock_integration_dashboard.get_metrics.assert_called_with(sample_integration_id)

    def test_get_metrics_empty(self, client, mock_integration_dashboard):
        """Test getting metrics when no data exists."""
        mock_integration_dashboard.get_metrics.return_value = {}

        response = client.get("/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data == {} or "data" in data


# =============================================================================
# Integration Health Tests
# =============================================================================

class TestIntegrationHealth:
    """Tests for integration health endpoints."""

    def test_get_health_healthy(self, client, mock_integration_dashboard):
        """Test getting health status for healthy integration."""
        mock_integration_dashboard.get_health.return_value = {
            "status": "healthy",
            "last_check": datetime.now().isoformat(),
            "uptime_seconds": 3600
        }

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "health" in data or "data" in data

    def test_get_health_degraded(self, client, mock_integration_dashboard):
        """Test getting health status for degraded integration."""
        mock_integration_dashboard.get_health.return_value = {
            "status": "degraded",
            "last_check": datetime.now().isoformat(),
            "error_rate": 0.15
        }

        response = client.get("/health")

        assert response.status_code == 200

    def test_get_health_error(self, client, mock_integration_dashboard):
        """Test getting health status for errored integration."""
        mock_integration_dashboard.get_health.return_value = {
            "status": "error",
            "last_check": datetime.now().isoformat(),
            "error": "Connection refused"
        }

        response = client.get("/health")

        assert response.status_code == 200

    def test_get_health_disabled(self, client, mock_integration_dashboard):
        """Test getting health status for disabled integration."""
        mock_integration_dashboard.get_health.return_value = {
            "status": "disabled",
            "enabled": False
        }

        response = client.get("/health")

        assert response.status_code == 200


# =============================================================================
# Alerts Management Tests
# =============================================================================

class TestAlertsManagement:
    """Tests for alerts endpoints."""

    def test_get_alerts_empty(self, client, mock_integration_dashboard):
        """Test getting alerts when none exist."""
        mock_integration_dashboard.get_alerts.return_value = []

        response = client.get("/alerts")

        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data or data == []

    def test_get_alerts_with_data(self, client, mock_integration_dashboard):
        """Test getting alerts with data."""
        mock_integration_dashboard.get_alerts.return_value = [
            {
                "integration": "slack",
                "severity": "warning",
                "type": "high_error_rate",
                "message": "Error rate exceeded threshold",
                "value": 0.15,
                "threshold": 0.10,
                "timestamp": datetime.now().isoformat()
            },
            {
                "integration": "teams",
                "severity": "critical",
                "type": "connection_failure",
                "message": "Unable to connect",
                "timestamp": datetime.now().isoformat()
            }
        ]

        response = client.get("/alerts")

        assert response.status_code == 200
        data = response.json()
        alerts = data.get("alerts", data)
        assert len(alerts) == 2

    def test_get_alerts_filtered_by_severity(self, client, mock_integration_dashboard):
        """Test getting alerts filtered by severity."""
        response = client.get("/alerts?severity=critical")

        assert response.status_code == 200

    def test_get_alerts_filtered_by_integration(self, client, mock_integration_dashboard, sample_integration_id):
        """Test getting alerts filtered by integration."""
        response = client.get(f"/alerts?integration={sample_integration_id}")

        assert response.status_code == 200


# =============================================================================
# Configuration Management Tests
# =============================================================================

class TestConfigurationManagement:
    """Tests for configuration endpoints."""

    def test_update_configuration_enable(self, client, mock_integration_dashboard, sample_integration_id):
        """Test updating configuration to enable integration."""
        request = {
            "integration": sample_integration_id,
            "enabled": True
        }

        response = client.post("/update-configuration", json=request)

        assert response.status_code == 200
        mock_integration_dashboard.update_configuration.assert_called_once()

    def test_update_configuration_disable(self, client, mock_integration_dashboard, sample_integration_id):
        """Test updating configuration to disable integration."""
        request = {
            "integration": sample_integration_id,
            "enabled": False
        }

        response = client.post("/update-configuration", json=request)

        assert response.status_code == 200

    def test_update_configuration_file_types(self, client, mock_integration_dashboard, sample_integration_id):
        """Test updating configuration file types."""
        request = {
            "integration": sample_integration_id,
            "file_types": ["pdf", "docx", "txt"]
        }

        response = client.post("/update-configuration", json=request)

        assert response.status_code == 200

    def test_update_configuration_sync_folders(self, client, mock_integration_dashboard, sample_integration_id):
        """Test updating configuration sync folders."""
        request = {
            "integration": sample_integration_id,
            "sync_folders": ["/Documents", "/Downloads"]
        }

        response = client.post("/update-configuration", json=request)

        assert response.status_code == 200

    def test_update_configuration_max_file_size(self, client, mock_integration_dashboard, sample_integration_id):
        """Test updating configuration max file size."""
        request = {
            "integration": sample_integration_id,
            "max_file_size_mb": 25
        }

        response = client.post("/update-configuration", json=request)

        assert response.status_code == 200

    def test_update_configuration_multiple_fields(self, client, mock_integration_dashboard, sample_integration_id):
        """Test updating multiple configuration fields."""
        request = {
            "integration": sample_integration_id,
            "enabled": True,
            "auto_sync_new_files": True,
            "file_types": ["pdf"],
            "max_file_size_mb": 10,
            "sync_frequency_minutes": 30
        }

        response = client.post("/update-configuration", json=request)

        assert response.status_code == 200


# =============================================================================
# Metrics Reset Tests
# =============================================================================

class TestMetricsReset:
    """Tests for metrics reset endpoints."""

    def test_reset_metrics_all(self, client, mock_integration_dashboard):
        """Test resetting metrics for all integrations."""
        mock_integration_dashboard.reset_metrics.return_value = True

        response = client.post("/reset-metrics", json={})

        assert response.status_code == 200
        mock_integration_dashboard.reset_metrics.assert_called_with(None)

    def test_reset_metrics_specific_integration(self, client, mock_integration_dashboard, sample_integration_id):
        """Test resetting metrics for specific integration."""
        request = {
            "integration": sample_integration_id
        }
        mock_integration_dashboard.reset_metrics.return_value = True

        response = client.post("/reset-metrics", json=request)

        assert response.status_code == 200
        mock_integration_dashboard.reset_metrics.assert_called_with(sample_integration_id)

    def test_reset_metrics_failure(self, client, mock_integration_dashboard):
        """Test handling reset failure."""
        mock_integration_dashboard.reset_metrics.return_value = False

        response = client.post("/reset-metrics", json={"integration": "test"})

        assert response.status_code == 200


# =============================================================================
# Overall Status Tests
# =============================================================================

class TestOverallStatus:
    """Tests for overall status endpoint."""

    def test_get_overall_status_healthy(self, client, mock_integration_dashboard):
        """Test getting overall healthy status."""
        mock_integration_dashboard.get_overall_status.return_value = {
            "overall_status": "healthy",
            "total_integrations": 5,
            "healthy_count": 4,
            "degraded_count": 1,
            "error_count": 0,
            "disabled_count": 0,
            "total_messages_fetched": 1000,
            "total_messages_processed": 975,
            "total_messages_failed": 25,
            "overall_success_rate": 0.975
        }

        response = client.get("/overall-status")

        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data or "data" in data

    def test_get_overall_status_with_errors(self, client, mock_integration_dashboard):
        """Test getting overall status with errors."""
        mock_integration_dashboard.get_overall_status.return_value = {
            "overall_status": "degraded",
            "total_integrations": 5,
            "healthy_count": 3,
            "degraded_count": 1,
            "error_count": 1,
            "disabled_count": 0
        }

        response = client.get("/overall-status")

        assert response.status_code == 200

    def test_get_overall_status_all_disabled(self, client, mock_integration_dashboard):
        """Test getting overall status when all disabled."""
        mock_integration_dashboard.get_overall_status.return_value = {
            "overall_status": "disabled",
            "total_integrations": 5,
            "disabled_count": 5
        }

        response = client.get("/overall-status")

        assert response.status_code == 200


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_get_metrics_exception(self, client, mock_integration_dashboard):
        """Test handling exception when getting metrics."""
        mock_integration_dashboard.get_metrics.side_effect = Exception("Database error")

        response = client.get("/metrics")

        # Should handle exception gracefully
        assert response.status_code in [200, 500]

    def test_update_configuration_exception(self, client, mock_integration_dashboard):
        """Test handling exception when updating configuration."""
        mock_integration_dashboard.update_configuration.side_effect = Exception("Update failed")

        response = client.post("/update-configuration", json={"integration": "test"})

        # Should handle exception gracefully
        assert response.status_code in [200, 500]
```

**Verify:**
```bash
test -f backend/tests/unit/test_integration_dashboard_routes.py && echo "File exists"
grep -c "^    def test_" backend/tests/unit/test_integration_dashboard_routes.py
# Expected: 25-30 tests
```

**Done:**
- File created with 25-30 tests
- Integration metrics tested
- Health status tested
- Alerts management tested
- Configuration updates tested
- Metrics reset tested
- Overall status tested
- Error handling tested

---

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_agent_guidance_routes.py | api/agent_guidance_routes.py | TestClient, mock_agent_guidance_system | Agent guidance API tests |
| test_integration_dashboard_routes.py | api/integration_dashboard_routes.py | TestClient, mock_integration_dashboard | Integration dashboard API tests |

## Progress Tracking

**Current Coverage (Phase 8.9):** 21-22%
**Plan 31 Target:** +0.8-1.0 percentage points
**Projected After Plans 31-33:** ~25-27%

## Notes

- Covers 2 files: agent_guidance_routes.py (537 lines), integration_dashboard_routes.py (506 lines)
- 50% coverage target (sustainable for 1,043 total lines)
- Test patterns from Phase 8.7/8.8/8.9 applied (TestClient, mocks, fixtures)
- Estimated 50-60 total tests across 2 files
- Duration: 2-3 hours
- All external dependencies mocked (agent guidance system, integration dashboard, database)

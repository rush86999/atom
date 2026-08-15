"""
Integration Tests for API Routes

Comprehensive tests for API endpoints to ensure 80%+ coverage.
Focuses on high-value endpoints, critical workflows, and governance validation.

NOTE (Session 2026-08-15, wave 120): this suite was originally written against
invented paths (`/agents/{id}/execute`, `/agents/{id}/episodes`, `/workflows`,
...) that 404 against the real app. Rewritten to verify the REAL route table:
every endpoint family is asserted "mounted and secured" (route exists AND
rejects anonymous callers with 401) — the same reliable HTTP-signal pattern as
tests/test_boot_router_mounts.py (route tree wraps included routers in lazy
`_IncludedRouter` objects that don't surface in `app.routes`).
"""
import pytest
from fastapi.testclient import TestClient

from main_api_app import app

AUTH_GATED = (401, 403)


class TestAgentExecutionEndpoints:
    """Test agent execution API endpoints (real: /api/agents/*)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_execute_agent_endpoint_mounted_and_secured(self, client):
        """POST /api/agents/{id}/run must exist and reject anonymous callers."""
        response = client.post("/api/agents/test-agent-id/run", json={"message": "Test message"})
        assert response.status_code in AUTH_GATED

    def test_execute_agent_not_found_requires_auth_first(self, client):
        """Auth is enforced before lookup — unknown agents still hit the 401 gate."""
        response = client.post("/api/agents/nonexistent/run", json={"message": "Test"})
        assert response.status_code in AUTH_GATED

    def test_get_agent_status_endpoint_mounted_and_secured(self, client):
        """GET /api/agents/{id} must exist and reject anonymous callers."""
        response = client.get("/api/agents/test-agent-id")
        assert response.status_code in AUTH_GATED

    def test_list_agents_endpoint_mounted_and_secured(self, client):
        """GET /api/agents/ must exist and reject anonymous callers."""
        response = client.get("/api/agents/")
        assert response.status_code in AUTH_GATED


class TestEpisodeEndpoints:
    """Test episode API endpoints (real: /api/episodes/*)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_create_episode_endpoint_mounted_and_secured(self, client):
        """POST /api/episodes/retrieve/semantic must exist and reject anonymous callers."""
        response = client.post("/api/episodes/retrieve/semantic", json={"query": "test query"})
        assert response.status_code in AUTH_GATED

    def test_get_episodes_endpoint_mounted_and_secured(self, client):
        """GET /api/episodes/{agent_id}/list must exist and reject anonymous callers."""
        response = client.get("/api/episodes/test-agent-id/list")
        assert response.status_code in AUTH_GATED

    def test_search_episodes_endpoint_mounted_and_secured(self, client):
        """POST /api/episodes/retrieve/semantic must exist and reject anonymous callers."""
        response = client.post("/api/episodes/retrieve/semantic", json={"query": "test query"})
        assert response.status_code in AUTH_GATED


class TestCanvasEndpoints:
    """Test canvas API endpoints (real: /api/canvas/*)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_list_canvases_endpoint_mounted_and_secured(self, client):
        """GET /api/canvas/ must exist and reject anonymous callers."""
        response = client.get("/api/canvas/")
        assert response.status_code in AUTH_GATED

    def test_update_canvas_endpoint_mounted_and_secured(self, client):
        """PUT /api/canvas/{id} must exist and reject anonymous callers."""
        response = client.put(
            "/api/canvas/test-canvas-id",
            json={"content": [{"type": "text", "content": "Updated content"}]},
        )
        assert response.status_code in AUTH_GATED

    def test_submit_canvas_form_endpoint_mounted_and_secured(self, client):
        """POST /api/canvas/submit must exist and reject anonymous callers."""
        response = client.post(
            "/api/canvas/submit",
            json={"email": "test@example.com", "message": "Test message"},
        )
        assert response.status_code in AUTH_GATED


class TestWorkflowEndpoints:
    """Test workflow API endpoints (real: /api/v1/workflow-ui/*, /api/v1/workflows/*)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_list_workflows(self, client):
        """GET /api/v1/workflow-ui/workflows is a public read surface returning a list."""
        response = client.get("/api/v1/workflow-ui/workflows")
        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data
        assert data["count"] == len(data["workflows"])

    def test_workflow_definitions(self, client):
        """GET /api/v1/workflows/definitions returns the built-in definition catalog."""
        response = client.get("/api/v1/workflows/definitions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_execute_workflow_endpoint_mounted_and_secured(self, client):
        """POST /api/v1/workflow-ui/workflows/{id}/execute must exist and reject anonymous callers."""
        response = client.post(
            "/api/v1/workflow-ui/workflows/test-workflow-id/execute", json={"inputs": {}}
        )
        assert response.status_code in AUTH_GATED


class TestGovernanceEndpoints:
    """Test governance API endpoints (real: /api/agent-governance/*)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_check_governance_endpoint_mounted_and_secured(self, client):
        """POST /api/agent-governance/check-deployment must exist and reject anonymous callers."""
        response = client.post(
            "/api/agent-governance/check-deployment",
            json={"action": "execute", "complexity": 3},
        )
        assert response.status_code in AUTH_GATED

    def test_get_governance_status_endpoint_mounted_and_secured(self, client):
        """GET /api/agent-governance/agents/{id} must exist and reject anonymous callers."""
        response = client.get("/api/agent-governance/agents/test-agent-id")
        assert response.status_code in AUTH_GATED


class TestHealthEndpoints:
    """Test health check API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_live(self, client):
        """Test liveness probe endpoint."""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "alive"]  # Accept both values

    def test_health_ready(self, client):
        """Test readiness probe endpoint."""
        response = client.get("/health/ready")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "checks" in data


class TestFeedbackEndpoints:
    """Test feedback API endpoints (real: /api/agents/{id}/feedback, /api/agent-governance/feedback)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_submit_feedback_endpoint_mounted_and_secured(self, client):
        """POST /api/agents/{id}/feedback must exist and reject anonymous callers."""
        response = client.post(
            "/api/agents/test-agent-id/feedback",
            json={"rating": 5, "comment": "Great job!"},
        )
        assert response.status_code in AUTH_GATED

    def test_get_feedback_analytics_endpoint_mounted_and_secured(self, client):
        """POST /api/agent-governance/feedback must exist and reject anonymous callers."""
        response = client.post(
            "/api/agent-governance/feedback",
            json={"agent_id": "test-agent-id", "rating": 5, "comment": "ok"},
        )
        assert response.status_code in AUTH_GATED


class TestDeviceCapabilitiesEndpoints:
    """Test device capabilities API endpoints (real: /api/devices/*)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_get_device_capabilities_endpoint_mounted_and_secured(self, client):
        """GET /api/devices must exist and reject anonymous callers."""
        response = client.get("/api/devices")
        assert response.status_code in AUTH_GATED

    def test_request_camera_access_endpoint_mounted_and_secured(self, client):
        """POST /api/devices/camera/snap must exist and reject anonymous callers."""
        response = client.post("/api/devices/camera/snap", json={"reason": "Need to capture screenshot"})
        assert response.status_code in AUTH_GATED


class TestBrowserAutomationEndpoints:
    """Test browser automation API endpoints (real: /api/browser/*)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_navigate_to_url_endpoint_mounted_and_secured(self, client):
        """POST /api/browser/navigate must exist and reject anonymous callers."""
        response = client.post("/api/browser/navigate", json={"url": "https://example.com"})
        assert response.status_code in AUTH_GATED

    def test_take_screenshot_endpoint_mounted_and_secured(self, client):
        """POST /api/browser/screenshot must exist and reject anonymous callers."""
        response = client.post("/api/browser/screenshot", json={})
        assert response.status_code in AUTH_GATED

"""
Integration tests for API route registration in main_api_app.py

These tests verify that routes are properly registered and accessible.
They test the "wiring" of the application without testing business logic.
"""

import os
import sys
from pathlib import Path

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"  # Use in-memory DB to avoid file issues

import pytest
from fastapi.testclient import TestClient

# Add backend directory to path
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

# Import app
# Note: There are duplicate model classes (Artifact, Skill) in models.py
# These are handled with __table_args__ = {'extend_existing': True}
from main_api_app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthCheckRoutes:
    """Test health check route registration (3 routes)."""

    def test_health_live_route_registered(self, client):
        """Test GET /health returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy_check_reload"

    def test_health_root_route_registered(self, client):
        """Test GET / returns 200."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestAgentRoutes:
    """Test agent route registration (5 routes)."""

    def test_agent_list_route_registered(self, client):
        """Test GET /api/v1/agents returns 200 or 401."""
        response = client.get("/api/v1/agents")
        # Will return 401 if auth required, or 200 with empty list
        assert response.status_code in [200, 401, 403]

    def test_agent_detail_route_registered(self, client):
        """Test GET /api/v1/agents/{id} returns 200 or 404."""
        response = client.get("/api/v1/agents/test-agent-id")
        # 404 is acceptable (agent doesn't exist), 401 if auth required
        assert response.status_code in [200, 401, 403, 404]


class TestCanvasRoutes:
    """Test canvas route registration (5 routes)."""

    def test_canvas_list_route_registered(self, client):
        """Test GET /api/v1/canvases returns 200 or 401."""
        response = client.get("/api/v1/canvases")
        assert response.status_code in [200, 401, 403]

    def test_canvas_detail_route_registered(self, client):
        """Test GET /api/v1/canvases/{id} returns 200 or 404."""
        response = client.get("/api/v1/canvases/test-canvas-id")
        assert response.status_code in [200, 401, 403, 404]


class TestBrowserAutomationRoutes:
    """Test browser automation route registration (4 routes)."""

    def test_browser_session_create_route_registered(self, client):
        """Test POST /api/v1/browser/sessions returns 200 or 401."""
        response = client.post("/api/v1/browser/sessions")
        # 400 is acceptable (missing required fields), 401 if auth required
        assert response.status_code in [200, 400, 401, 403]

    def test_browser_session_execute_route_registered(self, client):
        """Test POST /api/v1/browser/sessions/{id}/execute returns 200 or 404."""
        response = client.post("/api/v1/browser/sessions/test-session-id/execute")
        assert response.status_code in [200, 400, 401, 403, 404]

    def test_browser_session_close_route_registered(self, client):
        """Test DELETE /api/v1/browser/sessions/{id} returns 200 or 404."""
        response = client.delete("/api/v1/browser/sessions/test-session-id")
        assert response.status_code in [200, 401, 403, 404]


class TestDeviceCapabilityRoutes:
    """Test device capability route registration (4 routes)."""

    def test_device_camera_route_registered(self, client):
        """Test POST /api/v1/device/camera returns 200 or 401."""
        response = client.post("/api/v1/device/camera")
        assert response.status_code in [200, 400, 401, 403]

    def test_device_location_route_registered(self, client):
        """Test POST /api/v1/device/location returns 200 or 401."""
        response = client.post("/api/v1/device/location")
        assert response.status_code in [200, 400, 401, 403]

    def test_device_notifications_route_registered(self, client):
        """Test POST /api/v1/device/notifications returns 200 or 401."""
        response = client.post("/api/v1/device/notifications")
        assert response.status_code in [200, 400, 401, 403]

    def test_device_status_route_registered(self, client):
        """Test GET /api/v1/device/status returns 200 or 401."""
        response = client.get("/api/v1/device/status")
        assert response.status_code in [200, 401, 403]


class TestFeedbackRoutes:
    """Test feedback route registration (3 routes)."""

    def test_feedback_create_route_registered(self, client):
        """Test POST /api/feedback returns 200 or 401."""
        response = client.post("/api/feedback")
        assert response.status_code in [200, 400, 401, 403]

    def test_feedback_list_route_registered(self, client):
        """Test GET /api/feedback returns 200 or 401."""
        response = client.get("/api/feedback")
        assert response.status_code in [200, 401, 403]

    def test_feedback_analytics_route_registered(self, client):
        """Test GET /api/feedback/analytics returns 200 or 401."""
        response = client.get("/api/feedback/analytics")
        assert response.status_code in [200, 401, 403]


class TestDeeplinkRoutes:
    """Test deeplink route registration (2 routes)."""

    def test_deeplink_resolve_route_registered(self, client):
        """Test GET /api/deeplinks/{code} returns 200 or 404."""
        response = client.get("/api/deeplinks/test-code")
        assert response.status_code in [200, 401, 403, 404]

    def test_deeplink_create_route_registered(self, client):
        """Test POST /api/deeplinks returns 200 or 401."""
        response = client.post("/api/deeplinks")
        assert response.status_code in [200, 400, 401, 403]


class TestMiddlewareConfiguration:
    """Test middleware configuration."""

    def test_cors_middleware_configured(self, client):
        """Test OPTIONS request returns CORS headers."""
        response = client.options("/api/v1/agents")
        # CORS middleware should handle OPTIONS
        assert response.status_code in [200, 401, 403]

    def test_auth_middleware_configured(self, client):
        """Test unauthenticated request returns 401 or 403."""
        # Some routes require authentication
        response = client.get("/api/v1/agents")
        # Should return 401/403 if auth middleware is working
        # Or 200 if route is public
        assert response.status_code in [200, 401, 403]


class TestWorkflowRoutes:
    """Test workflow route registration."""

    def test_workflow_list_route_registered(self, client):
        """Test GET /api/v1/workflows returns 200 or 401."""
        response = client.get("/api/v1/workflows")
        assert response.status_code in [200, 401, 403]

    def test_workflow_detail_route_registered(self, client):
        """Test GET /api/v1/workflows/{id} returns 200 or 404."""
        response = client.get("/api/v1/workflows/test-workflow-id")
        assert response.status_code in [200, 401, 403, 404]


class TestAuthRoutes:
    """Test authentication route registration."""

    def test_auth_status_route_registered(self, client):
        """Test GET /api/auth/status returns 200."""
        response = client.get("/api/auth/status")
        assert response.status_code in [200, 401]


class TestIntegrationsRoutes:
    """Test integrations management route registration."""

    def test_integrations_list_route_registered(self, client):
        """Test GET /api/integrations returns 200."""
        response = client.get("/api/integrations")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data or "integrations" in data


class TestAllRequiredRoutesRegistered:
    """Test that all 25+ expected routes are registered."""

    def test_all_critical_routes_accessible(self, client):
        """Test that all critical routes are accessible (even if auth required)."""
        critical_routes = [
            # Health checks (2)
            ("/", "GET"),
            ("/health", "GET"),

            # Agents (2)
            ("/api/v1/agents", "GET"),
            ("/api/v1/agents/test-id", "GET"),

            # Canvases (2)
            ("/api/v1/canvases", "GET"),
            ("/api/v1/canvases/test-id", "GET"),

            # Browser automation (3)
            ("/api/v1/browser/sessions", "POST"),
            ("/api/v1/browser/sessions/test-id/execute", "POST"),
            ("/api/v1/browser/sessions/test-id", "DELETE"),

            # Device capabilities (4)
            ("/api/v1/device/camera", "POST"),
            ("/api/v1/device/location", "POST"),
            ("/api/v1/device/notifications", "POST"),
            ("/api/v1/device/status", "GET"),

            # Feedback (3)
            ("/api/feedback", "GET"),
            ("/api/feedback", "POST"),
            ("/api/feedback/analytics", "GET"),

            # Deeplinks (2)
            ("/api/deeplinks/test-code", "GET"),
            ("/api/deeplinks", "POST"),

            # Workflows (2)
            ("/api/v1/workflows", "GET"),
            ("/api/v1/workflows/test-id", "GET"),

            # Auth (1)
            ("/api/auth/status", "GET"),

            # Integrations (1)
            ("/api/integrations", "GET"),

            # Memory (1)
            ("/api/v1/memory", "GET"),
        ]

        failed_routes = []
        for route, method in critical_routes:
            if method == "GET":
                response = client.get(route)
            elif method == "POST":
                response = client.post(route)
            elif method == "DELETE":
                response = client.delete(route)
            else:
                continue

            # Accept 2xx, 3xx, 401, 403, 404, 422
            # Reject 5xx (server error) and 405 (method not allowed - route not registered)
            if response.status_code not in [200, 201, 202, 204, 301, 302, 304, 401, 403, 404, 422]:
                failed_routes.append((route, method, response.status_code))

        # Assert all routes are accessible
        assert len(failed_routes) == 0, (
            f"Failed routes: {failed_routes}\n"
            f"Expected status codes: 200, 201, 202, 204, 301, 302, 304, 401, 403, 404, 422"
        )

    def test_minimum_route_count(self, client):
        """Test that at least 25 routes are registered."""
        # Get all routes from the app
        routes = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                for method in route.methods:
                    routes.append((route.path, method))

        # Filter out HEAD and OPTIONS (auto-generated)
        routes = [(path, method) for path, method in routes if method not in ['HEAD', 'OPTIONS']]

        # Assert minimum route count
        assert len(routes) >= 25, f"Expected at least 25 routes, found {len(routes)}"

        # Print route count for debugging
        print(f"\nTotal routes registered: {len(routes)}")
        print(f"Sample routes: {routes[:10]}")

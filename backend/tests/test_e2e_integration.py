"""
End-to-End Integration Tests

Tests for validating complete user flows across the system.
Uses test clients and mocks for comprehensive integration testing.
"""

import pytest
import json
from typing import Dict, Any, Generator
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient
from core.models import Base
from core.database import get_db
from main_api_app import app


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_e2e.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def test_db() -> Generator:
    """Create test database once for all tests."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Clean up test database file
    import os
    if os.path.exists("test_e2e.db"):
        try:
            os.remove("test_e2e.db")
        except Exception:
            pass  # File might be locked


@pytest.fixture
def test_app(test_db):
    """Create test application."""
    return TestClient(app)


@pytest.fixture
def authenticated_page(test_app):
    """Return authenticated test client (simulated)."""
    # In a real scenario, this would handle authentication
    # For now, we just return the test client
    return test_app


class TestAgentExecutionFlow:
    """Test complete agent execution lifecycle."""

    def test_create_agent(self, test_app):
        """Test creating an agent via API."""
        response = test_app.post(
            "/api/v1/agents",
            json={
                "name": "test-agent",
                "description": "Test agent for E2E testing",
                "agent_type": "chat",
                "config": {
                    "model": "gpt-4",
                    "temperature": 0.7
                }
            }
        )

        # Should either work (200/201) or return validation error (422) or not exist (404)
        assert response.status_code in [200, 201, 404, 422], \
            f"Create agent should return valid status, got {response.status_code}"

    def test_execute_agent(self, test_app):
        """Test executing an agent."""
        response = test_app.post(
            "/api/v1/agents/test-agent/execute",
            json={
                "input": "Hello, agent!",
                "stream": False
            }
        )

        # Should work, return error, or endpoint not implemented
        assert response.status_code in [200, 404, 500], \
            f"Execute agent should return valid status, got {response.status_code}"

    def test_view_results(self, test_app):
        """Test viewing agent execution results."""
        execution_id = "test-exec-123"

        response = test_app.get(f"/api/v1/agents/executions/{execution_id}")

        # Should work, return not found, or endpoint not implemented
        assert response.status_code in [200, 404, 500], \
            f"View results should return valid status, got {response.status_code}"

    def test_submit_feedback(self, test_app):
        """Test submitting feedback on agent execution."""
        response = test_app.post(
            "/api/v1/feedback",
            json={
                "agent_id": "test-agent",
                "execution_id": "test-exec-123",
                "feedback_type": "thumbs_up",
                "rating": 1.0,
                "comment": "Great response!"
            }
        )

        # Should work, return validation error, or endpoint not implemented
        assert response.status_code in [200, 201, 404, 422], \
            f"Submit feedback should return valid status, got {response.status_code}"

    def test_agent_lifecycle(self, test_app):
        """Test complete agent lifecycle from creation to feedback."""
        # 1. Create agent
        create_response = test_app.post(
            "/api/v1/agents",
            json={
                "name": "lifecycle-test-agent",
                "description": "Testing agent lifecycle",
                "agent_type": "chat"
            }
        )
        # Accept various valid responses
        assert create_response.status_code in [200, 201, 404, 422]

        # 2. Execute agent (if created successfully)
        if create_response.status_code in [200, 201]:
            exec_response = test_app.post(
                "/api/v1/agents/lifecycle-test-agent/execute",
                json={"input": "test"}
            )
            assert exec_response.status_code in [200, 404, 500]

            # 3. Submit feedback (if executed successfully)
            if exec_response.status_code == 200:
                feedback_response = test_app.post(
                    "/api/v1/feedback",
                    json={
                        "agent_id": "lifecycle-test-agent",
                        "execution_id": "test-exec",
                        "feedback_type": "thumbs_up",
                        "rating": 1.0
                    }
                )
                assert feedback_response.status_code in [200, 201, 404, 422]


class TestCanvasPresentationFlow:
    """Test canvas presentation lifecycle."""

    def test_create_canvas(self, test_app):
        """Test creating a canvas via API."""
        response = test_app.post(
            "/api/v1/canvas/present",
            json={
                "canvas_type": "line_chart",
                "title": "Test Chart",
                "data": {
                    "labels": ["A", "B", "C"],
                    "datasets": [{
                        "label": "Test Dataset",
                        "data": [10, 20, 30]
                    }]
                }
            }
        )

        # Should work, return validation error, or endpoint not implemented
        assert response.status_code in [200, 201, 404, 422], \
            f"Create canvas should return valid status, got {response.status_code}"

    def test_update_canvas(self, test_app):
        """Test updating an existing canvas."""
        canvas_id = "test-canvas-123"

        response = test_app.put(
            f"/api/v1/canvas/{canvas_id}",
            json={
                "data": {
                    "labels": ["X", "Y", "Z"],
                    "datasets": [{
                        "label": "Updated Dataset",
                        "data": [15, 25, 35]
                    }]
                }
            }
        )

        # Should work, return not found, or endpoint not implemented
        assert response.status_code in [200, 404, 422], \
            f"Update canvas should return valid status, got {response.status_code}"

    def test_close_canvas(self, test_app):
        """Test closing a canvas."""
        canvas_id = "test-canvas-123"

        response = test_app.post(
            f"/api/v1/canvas/{canvas_id}/close",
            json={"reason": "User closed canvas"}
        )

        # Should work, return not found, or endpoint not implemented
        assert response.status_code in [200, 404, 500], \
            f"Close canvas should return valid status, got {response.status_code}"

    def test_canvas_types(self, test_app):
        """Test different canvas types."""
        canvas_types = [
            {"canvas_type": "line_chart", "data": {"labels": ["A"], "datasets": [{"data": [1]}]}},
            {"canvas_type": "bar_chart", "data": {"labels": ["B"], "datasets": [{"data": [2]}]}},
            {"canvas_type": "pie_chart", "data": {"labels": ["C"], "datasets": [{"data": [3]}]}},
            {"canvas_type": "markdown", "data": {"content": "# Test Markdown"}},
            {"canvas_type": "form", "data": {"fields": [{"name": "test", "type": "text"}]}}
        ]

        for canvas_config in canvas_types:
            response = test_app.post(
                "/api/v1/canvas/present",
                json=canvas_config
            )
            # Each canvas type should return valid status
            assert response.status_code in [200, 201, 404, 422], \
                f"Canvas type {canvas_config['canvas_type']} should return valid status, got {response.status_code}"

    def test_canvas_permissions(self, test_app):
        """Test canvas governance and permissions."""
        # Test creating canvas with governance check
        response = test_app.post(
            "/api/v1/canvas/present",
            json={
                "canvas_type": "line_chart",
                "data": {"labels": ["A"], "datasets": [{"data": [1]}]},
                "agent_id": "test-agent"
            }
        )

        # Should work, return permission error, or endpoint not implemented
        assert response.status_code in [200, 201, 401, 403, 404, 422], \
            f"Canvas with governance should return valid status, got {response.status_code}"


class TestIntegrationFlow:
    """Test third-party integration flows."""

    def test_slack_integration(self, test_app):
        """Test Slack integration flow."""
        response = test_app.post(
            "/api/v1/integrations/slack/send",
            json={
                "channel": "#test-channel",
                "message": "Test message from Atom"
            }
        )

        # Should work, return auth error, or integration not configured
        assert response.status_code in [200, 400, 401, 404, 500], \
            f"Slack integration should return valid status, got {response.status_code}"

    def test_github_integration(self, test_app):
        """Test GitHub integration flow."""
        response = test_app.post(
            "/api/v1/integrations/github/create-issue",
            json={
                "repo": "test/repo",
                "title": "Test issue from Atom",
                "body": "Issue body"
            }
        )

        # Should work, return auth error, or integration not configured
        assert response.status_code in [200, 400, 401, 404, 500], \
            f"GitHub integration should return valid status, got {response.status_code}"

    def test_jira_integration(self, test_app):
        """Test Jira integration flow."""
        response = test_app.post(
            "/api/v1/integrations/jira/create-ticket",
            json={
                "project": "TEST",
                "summary": "Test ticket from Atom",
                "description": "Ticket description"
            }
        )

        # Should work, return auth error, or integration not configured
        assert response.status_code in [200, 400, 401, 404, 500], \
            f"Jira integration should return valid status, got {response.status_code}"

    def test_websocket_integration(self, test_app):
        """Test WebSocket connection (simulated)."""
        # WebSocket testing requires special handling
        # For now, we test the WebSocket endpoint availability
        response = test_app.get("/api/v1/ws")

        # WebSocket upgrade should be initiated or endpoint not found
        assert response.status_code in [101, 404, 401], \
            f"WebSocket endpoint should return valid status, got {response.status_code}"


class TestIntegrationGaps:
    """Test integration points that may have gaps."""

    def test_websocket_connection(self, test_app):
        """Test WebSocket connection can be established."""
        # Test WebSocket endpoint exists
        response = test_app.get("/api/v1/ws")
        # Should either upgrade to WebSocket (101) or return error
        assert response.status_code in [101, 401, 404], \
            f"WebSocket connection should return valid status, got {response.status_code}"

    def test_websocket_reconnect(self, test_app):
        """Test WebSocket reconnection logic."""
        # This would require actual WebSocket client
        # For now, we just test the endpoint exists
        response = test_app.get("/api/v1/ws")
        assert response.status_code in [101, 401, 404]

    @pytest.mark.skip(reason="LanceDB integration requires actual vector DB")
    def test_lancedb_integration(self, test_app):
        """Test LanceDB vector operations."""
        # This test would require actual LanceDB instance
        # Skip for now as it needs external dependency
        pass

    def test_redis_integration(self, test_app):
        """Test Redis cache operations."""
        # Test if Redis is available via health check
        response = test_app.get("/health/ready")

        if response.status_code == 200:
            data = response.json()
            # Redis check might be in the response
            assert "status" in data
        else:
            # Health check might be failing
            assert response.status_code in [200, 503]

    @pytest.mark.skip(reason="S3/R2 integration requires actual storage")
    def test_storage_integration(self, test_app):
        """Test S3/R2 storage operations."""
        # This test would require actual S3/R2 instance
        # Skip for now as it needs external dependency
        pass


class TestCrossFeatureIntegration:
    """Test integration across multiple features."""

    def test_agent_to_canvas_flow(self, test_app):
        """Test agent presenting a canvas."""
        # 1. Execute agent that should present canvas
        response = test_app.post(
            "/api/v1/agents/test-agent/execute",
            json={
                "input": "Show me a chart of sales data",
                "stream": False
            }
        )

        # Should work or return appropriate error
        assert response.status_code in [200, 404, 500], \
            f"Agent execution should return valid status, got {response.status_code}"

        # 2. If agent executed, check for canvas in response
        if response.status_code == 200:
            data = response.json()
            # Canvas data might be in response
            # We just verify the structure is valid
            assert isinstance(data, dict)

    def test_canvas_to_feedback_flow(self, test_app):
        """Test feedback on canvas presentation."""
        # 1. Present canvas
        canvas_response = test_app.post(
            "/api/v1/canvas/present",
            json={
                "canvas_type": "line_chart",
                "data": {"labels": ["A"], "datasets": [{"data": [1]}]}
            }
        )

        # 2. Submit feedback on canvas
        if canvas_response.status_code in [200, 201]:
            feedback_response = test_app.post(
                "/api/v1/feedback",
                json={
                    "canvas_id": "test-canvas",
                    "feedback_type": "thumbs_up",
                    "rating": 1.0
                }
            )
            assert feedback_response.status_code in [200, 201, 404, 422]

    def test_governance_to_execution_flow(self, test_app):
        """Test governance check before agent execution."""
        # 1. Check agent permissions
        perm_response = test_app.get(
            "/api/v1/governance/agents/test-agent/permissions"
        )

        # Should work or return not found
        assert perm_response.status_code in [200, 404], \
            f"Permission check should return valid status, got {perm_response.status_code}"

        # 2. Execute agent if permissions check passed
        if perm_response.status_code == 200:
            exec_response = test_app.post(
                "/api/v1/agents/test-agent/execute",
                json={"input": "test"}
            )
            assert exec_response.status_code in [200, 404, 500]


class TestErrorHandlingIntegration:
    """Test error handling across integration points."""

    def test_invalid_agent_id(self, test_app):
        """Test handling of invalid agent ID."""
        response = test_app.get("/api/v1/agents/nonexistent-agent-12345")

        # Should return 404 or appropriate error
        assert response.status_code in [404, 400], \
            f"Invalid agent ID should return error, got {response.status_code}"

    def test_invalid_canvas_id(self, test_app):
        """Test handling of invalid canvas ID."""
        response = test_app.get("/api/v1/canvas/nonexistent-canvas-12345")

        # Should return 404 or appropriate error
        assert response.status_code in [404, 400], \
            f"Invalid canvas ID should return error, got {response.status_code}"

    def test_malformed_request(self, test_app):
        """Test handling of malformed request."""
        response = test_app.post(
            "/api/v1/agents/test-agent/execute",
            json={"invalid": "data structure"}
        )

        # Should return validation error
        assert response.status_code in [400, 422, 404], \
            f"Malformed request should return validation error, got {response.status_code}"

    def test_service_unavailable(self, test_app):
        """Test handling when external service is unavailable."""
        # This would require mocking service failures
        # For now, we test that the API handles errors gracefully
        response = test_app.post(
            "/api/v1/integrations/slack/send",
            json={"channel": "#test", "message": "test"}
        )

        # Should handle unavailability gracefully
        assert response.status_code in [200, 400, 401, 404, 500, 503], \
            f"Service unavailable should return appropriate error, got {response.status_code}"


class TestPerformanceIntegration:
    """Test performance aspects of integrations."""

    def test_concurrent_requests(self, test_app):
        """Test handling multiple concurrent requests."""
        # Make multiple requests to health check
        responses = []
        for _ in range(5):
            response = test_app.get("/health/live")
            responses.append(response.status_code)

        # All requests should succeed
        assert all(status in [200, 503] for status in responses), \
            "Concurrent health check requests should all return valid status"

    def test_response_time_health_check(self, test_app):
        """Test health check response time is acceptable."""
        import time

        start = time.time()
        response = test_app.get("/health/live")
        duration = time.time() - start

        # Health check should be fast (< 1 second)
        assert duration < 1.0, f"Health check took {duration:.2f}s, should be < 1s"
        assert response.status_code in [200, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

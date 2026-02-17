"""
Integration Tests for API Routes

Comprehensive tests for API endpoints to ensure 80%+ coverage.
Focuses on high-value endpoints, critical workflows, and governance validation.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from main_api_app import app
from core.models import AgentRegistry, AgentExecution, User
from tests.factories import AgentFactory


class TestAgentExecutionEndpoints:
    """Test agent execution API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(
            name="TestAgent",
            status="autonomous"
        )
        db_session.commit()
        return agent

    def test_execute_agent_success(self, client, agent):
        """Test successful agent execution."""
        response = client.post(
            f"/agents/{agent.id}/execute",
            json={"message": "Test message"}
        )

        assert response.status_code in [200, 202]
        data = response.json()
        assert "execution_id" in data or "status" in data

    def test_execute_agent_not_found(self, client):
        """Test execution with non-existent agent."""
        response = client.post(
            "/agents/nonexistent/execute",
            json={"message": "Test"}
        )

        assert response.status_code == 404

    def test_get_agent_status(self, client, agent):
        """Test retrieving agent status."""
        response = client.get(f"/agents/{agent.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == agent.id
        assert data["name"] == "TestAgent"

    def test_list_agents(self, client):
        """Test listing all agents."""
        response = client.get("/agents")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestEpisodeEndpoints:
    """Test episode API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(
            name="TestAgent",
            status="autonomous"
        )
        db_session.commit()
        return agent

    def test_create_episode(self, client, agent):
        """Test episode creation."""
        response = client.post(
            f"/agents/{agent.id}/episodes",
            json={
                "content": "Test episode content",
                "operation_type": "test_operation",
                "outcome": "success"
            }
        )

        assert response.status_code in [200, 201]
        data = response.json()
        assert "episode_id" in data or "id" in data

    def test_get_episodes(self, client, agent):
        """Test retrieving episodes."""
        response = client.get(f"/agents/{agent.id}/episodes")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_episodes(self, client, agent):
        """Test semantic episode search."""
        response = client.post(
            f"/agents/{agent.id}/episodes/search",
            json={"query": "test query", "top_k": 10}
        )

        assert response.status_code in [200, 202]
        data = response.json()
        assert "results" in data or "episodes" in data


class TestCanvasEndpoints:
    """Test canvas API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(
            name="TestAgent",
            status="autonomous"
        )
        db_session.commit()
        return agent

    def test_create_canvas(self, client, agent):
        """Test canvas creation."""
        response = client.post(
            f"/agents/{agent.id}/canvas",
            json={
                "type": "generic",
                "title": "Test Canvas",
                "content": [{"type": "text", "content": "Test content"}]
            }
        )

        assert response.status_code in [200, 201]
        data = response.json()
        assert "canvas_id" in data or "id" in data

    def test_update_canvas(self, client, agent):
        """Test canvas update."""
        # First create a canvas
        create_response = client.post(
            f"/agents/{agent.id}/canvas",
            json={
                "type": "generic",
                "title": "Test Canvas",
                "content": [{"type": "text", "content": "Test content"}]
            }
        )
        canvas_id = create_response.json().get("canvas_id") or create_response.json().get("id")

        # Update the canvas
        response = client.put(
            f"/agents/{agent.id}/canvas/{canvas_id}",
            json={"content": [{"type": "text", "content": "Updated content"}]}
        )

        assert response.status_code == 200

    def test_submit_canvas_form(self, client, agent):
        """Test canvas form submission."""
        # First create a canvas with a form
        create_response = client.post(
            f"/agents/{agent.id}/canvas",
            json={
                "type": "form",
                "title": "Test Form",
                "content": [{
                    "type": "form",
                    "fields": [
                        {"name": "email", "type": "email", "label": "Email"},
                        {"name": "message", "type": "text", "label": "Message"}
                    ]
                }]
            }
        )
        canvas_id = create_response.json().get("canvas_id") or create_response.json().get("id")

        # Submit the form
        response = client.post(
            f"/agents/{agent.id}/canvas/{canvas_id}/submit",
            json={"email": "test@example.com", "message": "Test message"}
        )

        assert response.status_code in [200, 202]
        data = response.json()
        assert "submission_id" in data or "success" in data


class TestWorkflowEndpoints:
    """Test workflow API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_list_workflows(self, client):
        """Test listing workflows."""
        response = client.get("/workflows")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_workflow(self, client):
        """Test workflow creation."""
        response = client.post(
            "/workflows",
            json={
                "name": "Test Workflow",
                "description": "Test description",
                "steps": [
                    {"action": "test_action", "params": {}}
                ]
            }
        )

        assert response.status_code in [200, 201]
        data = response.json()
        assert "workflow_id" in data or "id" in data

    def test_execute_workflow(self, client):
        """Test workflow execution."""
        # First create a workflow
        create_response = client.post(
            "/workflows",
            json={
                "name": "Test Workflow",
                "steps": [
                    {"action": "test_action", "params": {}}
                ]
            }
        )
        workflow_id = create_response.json().get("workflow_id") or create_response.json().get("id")

        # Execute the workflow
        response = client.post(
            f"/workflows/{workflow_id}/execute",
            json={"inputs": {}}
        )

        assert response.status_code in [200, 202]
        data = response.json()
        assert "execution_id" in data or "status" in data


class TestGovernanceEndpoints:
    """Test governance API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(
            name="TestAgent",
            status="autonomous"
        )
        db_session.commit()
        return agent

    def test_check_governance(self, client, agent):
        """Test governance check."""
        response = client.post(
            f"/agents/{agent.id}/governance/check",
            json={
                "action": "execute",
                "complexity": 3
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "allowed" in data or "permitted" in data

    def test_get_governance_status(self, client, agent):
        """Test retrieving governance status."""
        response = client.get(f"/agents/{agent.id}/governance")

        assert response.status_code == 200
        data = response.json()
        assert "maturity_level" in data or "permissions" in data


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
    """Test feedback API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(
            name="TestAgent",
            status="autonomous"
        )
        db_session.commit()
        return agent

    def test_submit_feedback(self, client, agent):
        """Test feedback submission."""
        response = client.post(
            f"/agents/{agent.id}/feedback",
            json={
                "rating": 5,
                "comment": "Great job!"
            }
        )

        assert response.status_code in [200, 201]
        data = response.json()
        assert "feedback_id" in data or "id" in data

    def test_get_feedback_analytics(self, client, agent):
        """Test retrieving feedback analytics."""
        response = client.get(f"/agents/{agent.id}/feedback/analytics")

        assert response.status_code == 200
        data = response.json()
        assert "analytics" in data or "summary" in data


class TestDeviceCapabilitiesEndpoints:
    """Test device capabilities API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(
            name="TestAgent",
            status="autonomous"
        )
        db_session.commit()
        return agent

    def test_get_device_capabilities(self, client, agent):
        """Test retrieving device capabilities."""
        response = client.get(f"/agents/{agent.id}/capabilities")

        assert response.status_code == 200
        data = response.json()
        assert "capabilities" in data or "features" in data

    def test_request_camera_access(self, client, agent):
        """Test camera access request."""
        response = client.post(
            f"/agents/{agent.id}/capabilities/camera",
            json={"reason": "Need to capture screenshot"}
        )

        assert response.status_code in [200, 403]  # 403 if not permitted
        data = response.json()
        assert "permitted" in data or "allowed" in data


class TestBrowserAutomationEndpoints:
    """Test browser automation API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(
            name="TestAgent",
            status="autonomous"
        )
        db_session.commit()
        return agent

    def test_navigate_to_url(self, client, agent):
        """Test browser navigation."""
        response = client.post(
            f"/agents/{agent.id}/browser/navigate",
            json={"url": "https://example.com"}
        )

        assert response.status_code in [200, 202]
        data = response.json()
        assert "session_id" in data or "success" in data

    def test_take_screenshot(self, client, agent):
        """Test taking screenshot."""
        response = client.post(
            f"/agents/{agent.id}/browser/screenshot",
            json={}
        )

        assert response.status_code in [200, 202, 403]  # 403 if not permitted
        data = response.json()
        assert "screenshot_id" in data or "success" in data or "error" in data

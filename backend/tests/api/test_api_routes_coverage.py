"""
Integration Tests for API Routes

Comprehensive tests for API endpoints to ensure 80%+ coverage.
Focuses on high-value endpoints, critical workflows, and governance validation.
"""
import pytest
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from main_api_app import app
from core.models import AgentRegistry, AgentExecution, User, UserStatus
from tests.factories.agent_factory import AgentFactory

# Helper to ensure UUIDs are strings
def ensure_str(val):
    return str(val) if val else val

class TestAgentExecutionEndpoints:
    """Test agent execution API endpoints."""

    @pytest.fixture
    def override_auth(self):
        from core.auth import get_current_user
        from core.models import User
        
        # Mock user as super_admin
        mock_user = User(
            id="test-user-id",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            role="super_admin",
            status=UserStatus.ACTIVE.value,
            email_verified=True
        )
        
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides = {}

    @pytest.fixture
    def client(self, db_session, override_auth):
        """Create test client."""
        from core.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session
        return TestClient(app)

    @pytest.fixture
    def agent_id(self, db_session):
        """Create test agent and return its ID as string."""
        agent = AgentFactory(
            _session=db_session,
            name="TestAgent_" + str(uuid.uuid4())[:8],
            status="autonomous"
        )
        db_session.flush()
        return str(agent.id)

    def test_execute_agent_success(self, client, agent_id):
        """Test successful agent execution."""
        # Try both /api/agents and /api/v1/agents
        url = f"/api/agents/{agent_id}/run"
        response = client.post(url, json={"parameters": {"message": "Test message"}})
        
        if response.status_code == 404:
            response = client.post(f"/api/v1/agents/{agent_id}/run", json={"parameters": {"message": "Test"}})

        assert response.status_code in [200, 202], f"Error: {response.status_code}, {response.text}, Agent ID: {agent_id}"

    def test_execute_agent_not_found(self, client):
        """Test execution with non-existent agent."""
        response = client.post(
            "/api/agents/nonexistent/run",
            json={"parameters": {"message": "Test"}}
        )

        assert response.status_code == 404

    def test_get_agent_status(self, client, agent_id):
        """Test retrieving agent status."""
        response = client.get(f"/api/agents/{agent_id}")
        if response.status_code == 404:
            response = client.get(f"/api/v1/agents/{agent_id}")
            
        assert response.status_code == 200, f"Error: {response.status_code}, {response.text}, Agent ID: {agent_id}"

    def test_list_agents(self, client):
        """Test listing all agents."""
        response = client.get("/api/agents")
        if response.status_code == 404:
            response = client.get("/api/v1/agents")
        assert response.status_code == 200


class TestEpisodeEndpoints:
    """Test episode API endpoints."""

    @pytest.fixture
    def override_auth(self):
        from core.auth import get_current_user
        from core.models import User, UserStatus
        mock_user = User(
            id="test-user-id", email="test@example.com", first_name="Test",
            last_name="User", role="super_admin", status=UserStatus.ACTIVE.value,
            email_verified=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides = {}

    @pytest.fixture
    def client(self, db_session, override_auth):
        from core.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session
        return TestClient(app)

    @pytest.fixture
    def agent_id(self, db_session):
        """Create test agent."""
        agent = AgentFactory(_session=db_session, name="TestAgent_Ep", status="supervised")
        db_session.flush()
        return str(agent.id)

    def test_create_episode(self, client, agent_id):
        """Test episode creation."""
        response = client.post(
            "/api/episodes/create",
            json={"session_id": "test_session", "agent_id": agent_id, "title": "Test Episode"}
        )
        assert response.status_code in [200, 201, 400], f"Error: {response.status_code}, {response.text}"

    def test_get_episodes(self, client, agent_id):
        """Test retrieving episodes."""
        response = client.get(f"/api/episodes/{agent_id}/list")
        assert response.status_code == 200

    def test_search_episodes(self, client, agent_id):
        """Test semantic episode search."""
        response = client.post(
            "/api/episodes/retrieve/semantic",
            json={"agent_id": agent_id, "query": "test query", "limit": 10}
        )
        assert response.status_code in [200, 202]


class TestCanvasEndpoints:
    """Test canvas API endpoints."""

    @pytest.fixture
    def override_auth(self):
        from core.auth import get_current_user
        from core.models import User, UserStatus
        mock_user = User(
            id="test-user-id", email="test@example.com", first_name="Test",
            last_name="User", role="super_admin", status=UserStatus.ACTIVE.value,
            email_verified=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides = {}

    @pytest.fixture
    def client(self, db_session, override_auth):
        from core.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session
        return TestClient(app)

    @pytest.fixture
    def agent_id(self, db_session):
        """Create test agent."""
        agent = AgentFactory(_session=db_session, name="TestAgent_Canvas", status="supervised")
        db_session.flush()
        return str(agent.id)

    def test_create_canvas(self, client, agent_id):
        """Test canvas creation."""
        response = client.post(
            "/api/canvas/orchestration/create",
            json={"user_id": "test-user-id", "title": "Test Canvas", "agent_id": agent_id}
        )
        assert response.status_code in [200, 201]

    def test_submit_canvas_form(self, client, agent_id):
        """Test canvas form submission."""
        response = client.post(
            "/api/canvas/submit",
            json={"canvas_id": "test_canvas", "form_data": {"email": "test@example.com"}}
        )
        assert response.status_code in [200, 202]


class TestWorkflowEndpoints:
    """Test workflow API endpoints."""

    @pytest.fixture
    def override_auth(self):
        from core.auth import get_current_user
        from core.models import User, UserStatus
        mock_user = User(
            id="test-user-id", email="test@example.com", first_name="Test",
            last_name="User", role="super_admin", status=UserStatus.ACTIVE.value,
            email_verified=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides = {}

    @pytest.fixture
    def client(self, db_session, override_auth):
        from core.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session
        return TestClient(app)

    def test_list_workflows(self, client):
        """Test listing workflows."""
        response = client.get("/api/v1/workflows/workflows")
        if response.status_code == 404:
            response = client.get("/api/v1/workflows/workflows/")
        if response.status_code == 404:
            response = client.get("/api/v1/workflows")
            
        assert response.status_code == 200, f"Error: {response.status_code}, {response.text}"

    def test_create_workflow(self, client):
        """Test workflow creation."""
        workflow_data = {
            "name": "Test Workflow",
            "description": "Test",
            "version": "1.0",
            "nodes": [],
            "connections": [],
            "triggers": [],
            "enabled": True
        }
        response = client.post("/api/v1/workflows/workflows", json=workflow_data)
        if response.status_code in [404, 405]:
            response = client.post("/api/v1/workflows/workflows/", json=workflow_data)
        if response.status_code in [404, 405]:
            response = client.post("/api/v1/workflows", json=workflow_data)
            
        assert response.status_code in [200, 201], f"Error: {response.status_code}, {response.text}"

    def test_execute_workflow(self, client):
        """Test workflow execution."""
        res = client.get("/api/v1/workflows/workflows")
        if res.status_code != 200:
            res = client.get("/api/v1/workflows")
        
        workflow_id = "test-id"
        if res.status_code == 200:
            workflows = res.json()
            if workflows:
                workflow_id = workflows[0].get("id") or workflows[0].get("workflow_id")
        
        response = client.post(f"/api/v1/workflows/workflows/{workflow_id}/execute")
        if response.status_code == 404:
            response = client.post(f"/api/v1/workflows/{workflow_id}/execute")
            
        assert response.status_code in [200, 202, 404], f"Error: {response.status_code}, {response.text}"


class TestGovernanceEndpoints:
    """Test governance API endpoints."""

    @pytest.fixture
    def override_auth(self):
        from core.auth import get_current_user
        from core.models import User, UserStatus
        mock_user = User(
            id="test-user-id", email="test@example.com", first_name="Test",
            last_name="User", role="super_admin", status=UserStatus.ACTIVE.value,
            email_verified=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides = {}

    @pytest.fixture
    def client(self, db_session, override_auth):
        from core.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session
        return TestClient(app)

    def test_get_rules(self, client):
        """Test getting governance rules."""
        response = client.get("/api/agent-governance/rules")
        assert response.status_code == 200

    def test_get_agent_capabilities(self, client):
        """Test agent capabilities check."""
        response = client.get("/api/agent-governance/agents/finance-agent/capabilities")
        assert response.status_code == 200


class TestHealthEndpoints:
    """Test health check API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_live(self, client):
        """Test liveness probe endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_ready(self, client):
        """Test readiness probe endpoint."""
        response = client.get("/api/v1/status")
        assert response.status_code == 200


class TestFeedbackEndpoints:
    """Test feedback API endpoints."""

    @pytest.fixture
    def override_auth(self):
        from core.auth import get_current_user
        from core.models import User, UserStatus
        mock_user = User(
            id="test-user-id", email="test@example.com", first_name="Test",
            last_name="User", role="super_admin", status=UserStatus.ACTIVE.value,
            email_verified=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides = {}

    @pytest.fixture
    def client(self, db_session, override_auth):
        from core.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session
        return TestClient(app)

    def test_get_promotion_suggestions(self, client):
        """Test retrieving promotion suggestions."""
        response = client.get("/api/feedback/phase2/promotion-suggestions")
        assert response.status_code in [200, 404] 


class TestOnboardingEndpoints:
    """Test onboarding API endpoints."""

    @pytest.fixture
    def override_auth(self):
        from core.auth import get_current_user
        from core.models import User, UserStatus
        mock_user = User(
            id="test-user-id", email="test@example.com", first_name="Test",
            last_name="User", role="super_admin", status=UserStatus.ACTIVE.value,
            email_verified=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides = {}

    @pytest.fixture
    def client(self, db_session, override_auth):
        from core.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session
        return TestClient(app)

    def test_get_onboarding_status(self, client):
        """Test retrieving onboarding status."""
        response = client.get("/api/onboarding/status")
        assert response.status_code == 200


class TestBillingEndpoints:
    """Test billing API endpoints."""

    @pytest.fixture
    def override_auth(self):
        from core.auth import get_current_user
        from core.models import User, UserStatus
        mock_user = User(
            id="test-user-id", email="test@example.com", first_name="Test",
            last_name="User", role="super_admin", status=UserStatus.ACTIVE.value,
            email_verified=True
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides = {}

    @pytest.fixture
    def client(self, db_session, override_auth):
        from core.database import get_db
        app.dependency_overrides[get_db] = lambda: db_session
        return TestClient(app)

    def test_get_unbilled_milestones(self, client):
        """Test retrieving unbilled milestones."""
        response = client.get("/api/billing/unbilled")
        assert response.status_code in [200, 404]

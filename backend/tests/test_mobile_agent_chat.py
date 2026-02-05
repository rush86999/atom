"""
Mobile Agent Chat Tests

Tests for mobile agent chat API endpoints:
- Agent list with filtering
- Agent chat with streaming
- Episode context integration
- Agent feedback submission
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentFeedback, User
from fastapi.testclient import TestClient


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_user(db_session: Session):
    """Create a test user."""
    user = User(
        email="mobile_agent@test.com",
        first_name="Mobile",
        last_name="Agent User",
        password_hash="$2b$12$test_hashed_password",
        role="MEMBER"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def test_agents(db_session: Session, test_user):
    """Create test agents with different maturity levels."""
    agents = []

    maturity_configs = {
        'AUTONOMOUS': {
            'capabilities': ['web_automation', 'data_analysis', 'file_operations'],
            'can_execute_automated_triggers': True,
        },
        'SUPERVISED': {
            'capabilities': ['web_automation', 'data_analysis'],
            'can_execute_automated_triggers': False,
        },
        'INTERN': {
            'capabilities': ['data_analysis'],
            'can_execute_automated_triggers': False,
        },
        'STUDENT': {
            'capabilities': ['read_only'],
            'can_execute_automated_triggers': False,
        },
    }

    for i, (maturity, config) in enumerate(maturity_configs.items()):
        agent = AgentRegistry(
            name=f"Test Agent {maturity}",
            description=f"Test agent for {maturity} maturity level",
            category="automation" if i % 2 == 0 else "analytics",
            module_path="test.module",
            class_name="TestAgent",
            configuration=config,
            status=maturity,  # This sets the maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
            user_id=str(test_user.id),
        )
        db_session.add(agent)
        agents.append(agent)

    db_session.commit()

    for agent in agents:
        db_session.refresh(agent)

    return agents


# ============================================================================
# Mobile Agent List Tests
# ============================================================================

class TestMobileAgentList:
    """Tests for mobile agent list endpoint."""

    def test_list_all_agents(self, client: TestClient, test_agents):
        """Test listing all agents without filters."""
        response = client.get("/api/agents/mobile/list")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "total" in data
        assert len(data["agents"]) == len(test_agents)

    def test_list_agents_by_category(self, client: TestClient, test_agents):
        """Test filtering agents by category."""
        response = client.get("/api/agents/mobile/list?category=automation")

        assert response.status_code == 200
        data = response.json()
        automation_agents = [a for a in test_agents if a.category == "automation"]
        assert len(data["agents"]) == len(automation_agents)

    def test_list_agents_by_maturity(self, client: TestClient, test_agents):
        """Test filtering agents by maturity level."""
        response = client.get("/api/agents/mobile/list?status=AUTONOMOUS")

        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) == 1
        assert data["agents"][0]["status"] == "AUTONOMOUS"

    def test_list_agents_by_capability(self, client: TestClient, test_agents):
        """Test filtering agents by capability."""
        response = client.get("/api/agents/mobile/list?capability=web_automation")

        assert response.status_code == 200
        data = response.json()
        # Only AUTONOMOUS and SUPERVISED have web_automation
        assert len(data["agents"]) == 2

    def test_list_agents_with_search(self, client: TestClient, test_agents):
        """Test searching agents by name/description."""
        response = client.get("/api/agents/mobile/list?search=AUTONOMOUS")

        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) == 1
        assert "AUTONOMOUS" in data["agents"][0]["name"]

    def test_list_agents_pagination(self, client: TestClient, test_agents):
        """Test pagination of agent list."""
        response = client.get("/api/agents/mobile/list?limit=2&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) == 2
        assert data["total"] == len(test_agents)

    def test_agent_availability(self, client: TestClient, test_agents):
        """Test that agent availability is correctly calculated."""
        response = client.get("/api/agents/mobile/list")

        assert response.status_code == 200
        data = response.json()

        # AUTONOMOUS agent should be available
        autonomous = next((a for a in data["agents"] if a["status"] == "AUTONOMOUS"), None)
        assert autonomous is not None
        assert autonomous["is_available"] is True

        # STUDENT agent should not be available for direct execution
        student = next((a for a in data["agents"] if a["status"] == "STUDENT"), None)
        assert student is not None
        assert student["is_available"] is False


# ============================================================================
# Mobile Agent Chat Tests
# ============================================================================

class TestMobileAgentChat:
    """Tests for mobile agent chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_with_autonomous_agent(self, client: TestClient, test_agents, test_user):
        """Test sending chat message to AUTONOMOUS agent."""
        autonomous_agent = next((a for a in test_agents if a.status == "AUTONOMOUS"))

        response = client.post(
            f"/api/agents/mobile/{autonomous_agent.id}/chat",
            json={
                "message": "Test message",
                "include_episode_context": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "message_id" in data
        assert "agent_id" in data
        assert "content" in data
        assert "governance" in data
        assert data["governance"]["maturity_level"] == "AUTONOMOUS"

    @pytest.mark.asyncio
    async def test_chat_with_student_agent_forbidden(self, client: TestClient, test_agents):
        """Test that STUDENT agent chat is forbidden."""
        student_agent = next((a for a in test_agents if a.status == "STUDENT"))

        response = client.post(
            f"/api/agents/mobile/{student_agent.id}/chat",
            json={
                "message": "Test message",
                "include_episode_context": False
            }
        )

        assert response.status_code == 403  # Forbidden

    @pytest.mark.asyncio
    async def test_chat_with_episode_context(self, client: TestClient, test_agents):
        """Test chat with episode context retrieval."""
        autonomous_agent = next((a for a in test_agents if a.status == "AUTONOMOUS"))

        with patch('core.episode_retrieval_service.EpisodeRetrievalService') as mock_retrieval:
            # Mock episode retrieval
            mock_service = AsyncMock()
            mock_service.retrieve_episodes.return_value = []
            mock_retrieval.return_value = mock_service

            response = client.post(
                f"/api/agents/mobile/{autonomous_agent.id}/chat",
                json={
                    "message": "Test message about previous work",
                    "include_episode_context": True,
                    "episode_retrieval_mode": "semantic",
                    "max_episodes": 5
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "episode_context" in data

    @pytest.mark.asyncio
    async def test_chat_with_invalid_agent(self, client: TestClient):
        """Test chat with non-existent agent."""
        response = client.post(
            "/api/agents/mobile/nonexistent_id/chat",
            json={
                "message": "Test message",
                "include_episode_context": False
            }
        )

        assert response.status_code == 404

    def test_chat_governance_metadata(self, client: TestClient, test_agents):
        """Test that governance metadata is included."""
        supervised_agent = next((a for a in test_agents if a.status == "SUPERVISED"))

        response = client.post(
            f"/api/agents/mobile/{supervised_agent.id}/chat",
            json={
                "message": "Test message",
                "include_episode_context": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "governance" in data
        assert data["governance"]["maturity_level"] == "SUPERVISED"
        assert data["governance"]["supervised"] is True


# ============================================================================
# Agent Episodes Tests
# ============================================================================

class TestAgentEpisodes:
    """Tests for agent episodes endpoint."""

    def test_get_agent_episodes(self, client: TestClient, test_agents):
        """Test retrieving episodes for an agent."""
        agent = test_agents[0]

        with patch('core.episode_retrieval_service.EpisodeRetrievalService') as mock_retrieval:
            # Mock episode retrieval
            mock_service = AsyncMock()
            mock_service.retrieve_episodes.return_value = []
            mock_retrieval.return_value = mock_service

            response = client.get(f"/api/agents/mobile/{agent.id}/episodes")

            assert response.status_code == 200
            data = response.json()
            assert "episodes" in data
            assert "agent_id" in data
            assert "agent_name" in data

    def test_get_agent_episodes_pagination(self, client: TestClient, test_agents):
        """Test pagination of agent episodes."""
        agent = test_agents[0]

        response = client.get(f"/api/agents/mobile/{agent.id}/episodes?limit=5&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert "episodes" in data

    def test_get_agent_episodes_invalid_agent(self, client: TestClient):
        """Test getting episodes for non-existent agent."""
        response = client.get("/api/agents/mobile/nonexistent_id/episodes")

        assert response.status_code == 404


# ============================================================================
# Categories and Capabilities Tests
# ============================================================================

class TestCategoriesAndCapabilities:
    """Tests for categories and capabilities endpoints."""

    def test_list_categories(self, client: TestClient, test_agents):
        """Test listing agent categories."""
        response = client.get("/api/agents/mobile/categories")

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert len(data["categories"]) > 0
        # Should have automation and analytics
        category_names = [c["name"] for c in data["categories"]]
        assert "automation" in category_names
        assert "analytics" in category_names

    def test_list_capabilities(self, client: TestClient, test_agents):
        """Test listing agent capabilities."""
        response = client.get("/api/agents/mobile/capabilities")

        assert response.status_code == 200
        data = response.json()
        assert "capabilities" in data
        assert len(data["capabilities"]) > 0
        # Should have capabilities from test agents
        capability_names = [c["name"] for c in data["capabilities"]]
        assert "web_automation" in capability_names
        assert "data_analysis" in capability_names


# ============================================================================
# Agent Feedback Tests
# ============================================================================

class TestAgentFeedback:
    """Tests for agent feedback submission."""

    def test_submit_feedback(self, client: TestClient, test_agents, db_session: Session):
        """Test submitting feedback for an agent."""
        agent = test_agents[0]

        response = client.post(
            f"/api/agents/mobile/{agent.id}/feedback",
            json={
                "feedback": "Great response!",
                "rating": 5
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

        # Verify feedback was created
        feedback = db_session.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent.id
        ).first()
        assert feedback is not None
        assert feedback.feedback == "Great response!"
        assert feedback.rating == 5
        assert feedback.source == "mobile"

    def test_submit_feedback_without_rating(self, client: TestClient, test_agents):
        """Test submitting feedback without rating."""
        agent = test_agents[0]

        response = client.post(
            f"/api/agents/mobile/{agent.id}/feedback",
            json={
                "feedback": "Helpful response"
            }
        )

        assert response.status_code == 200

    def test_submit_feedback_invalid_agent(self, client: TestClient):
        """Test submitting feedback for non-existent agent."""
        response = client.post(
            "/api/agents/mobile/nonexistent_id/feedback",
            json={
                "feedback": "Test feedback",
                "rating": 3
            }
        )

        assert response.status_code == 404


# ============================================================================
# Performance Tests
# ============================================================================

class TestMobileAgentPerformance:
    """Performance tests for mobile agent endpoints."""

    def test_agent_list_performance(self, client: TestClient, test_agents):
        """Test agent list response time."""
        import time

        start = time.time()
        response = client.get("/api/agents/mobile/list")
        end = time.time()

        assert response.status_code == 200
        # Should respond in less than 500ms
        assert (end - start) < 0.5

    def test_chat_response_performance(self, client: TestClient, test_agents):
        """Test chat response time."""
        import time

        agent = test_agents[0]

        start = time.time()
        response = client.post(
            f"/api/agents/mobile/{agent.id}/chat",
            json={
                "message": "Test message",
                "include_episode_context": False
            }
        )
        end = time.time()

        assert response.status_code == 200
        # Should respond in less than 1 second
        assert (end - start) < 1.0

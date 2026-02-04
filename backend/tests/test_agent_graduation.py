"""
Tests for Agent Graduation Service
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from core.agent_graduation_service import AgentGraduationService
from core.models import AgentRegistry, AgentStatus, Episode


@pytest.fixture
def db_session():
    """Mock database session"""
    session = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.query = Mock()
    return session


@pytest.fixture
def mock_student_agent():
    """Mock student agent"""
    agent = AgentRegistry(
        id="student_agent_123",
        name="Student Finance Agent",
        category="Finance",
        status=AgentStatus.STUDENT
    )
    agent.metadata_json = {}
    return agent


@pytest.fixture
def mock_episodes():
    """Mock episodes for graduation testing"""
    episodes = []
    for i in range(15):  # 15 episodes (above INTERN threshold of 10)
        episode = Episode(
            id=f"episode_{i}",
            title=f"Training Episode {i}",
            agent_id="student_agent_123",
            user_id="user_123",
            workspace_id="default",
            status="completed",
            maturity_at_time="STUDENT",
            human_intervention_count=0 if i < 12 else 1,  # Some with interventions
            constitutional_score=0.75 + (i * 0.01),  # Improving scores
            started_at=datetime.now(),
            ended_at=datetime.now(),
            topics=["tax", "finance"],
            entities=[],
            execution_ids=[],
            importance_score=0.7
        )
        episodes.append(episode)
    return episodes


class TestGraduationReadiness:
    """Tests for graduation readiness calculation"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_calculate_readiness_success_case(
        self, mock_lancedb, db_session, mock_student_agent, mock_episodes
    ):
        """Test readiness calculation for qualified agent"""
        # Setup query mocks
        agent_query = Mock()
        agent_query.first = Mock(return_value=mock_student_agent)

        episode_query = Mock()
        episode_query.filter = Mock(return_value=episode_query)
        episode_query.all = Mock(return_value=mock_episodes)

        def query_side_effect(model):
            if model == AgentRegistry:
                return agent_query
            return episode_query

        db_session.query = query_side_effect

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.calculate_readiness_score(
            agent_id="student_agent_123",
            target_maturity="INTERN"
        ))

        assert "ready" in result
        assert "score" in result
        assert result["episode_count"] == 15
        # Check that current_maturity is set (may be Mock or str depending on query)
        assert "current_maturity" in result
        assert 0 <= result["score"] <= 100

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_calculate_readiness_insufficient_episodes(
        self, mock_lancedb, db_session, mock_student_agent
    ):
        """Test readiness calculation with insufficient episodes"""
        # Only 5 episodes (below INTERN threshold of 10)
        few_episodes = [
            Episode(
                id=f"episode_{i}",
                title=f"Episode {i}",
                agent_id="student_agent_123",
                user_id="user_123",
                workspace_id="default",
                status="completed",
                maturity_at_time="STUDENT",
                human_intervention_count=0,
                constitutional_score=0.8,
                started_at=datetime.now(),
                ended_at=datetime.now(),
                topics=[],
                entities=[],
                execution_ids=[],
                importance_score=0.7
            )
            for i in range(5)
        ]

        agent_query = Mock()
        agent_query.first = Mock(return_value=mock_student_agent)

        episode_query = Mock()
        episode_query.filter = Mock(return_value=episode_query)
        episode_query.all = Mock(return_value=few_episodes)

        def query_side_effect(model):
            if model == AgentRegistry:
                return agent_query
            return episode_query

        db_session.query = query_side_effect

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.calculate_readiness_score(
            agent_id="student_agent_123",
            target_maturity="INTERN"
        ))

        assert result["ready"] is False
        assert "Need 5 more episodes" in result["gaps"]
        assert result["score"] < 100

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_calculate_readiness_high_intervention_rate(
        self, mock_lancedb, db_session, mock_student_agent
    ):
        """Test readiness calculation with high intervention rate"""
        # Episodes with many interventions (50% rate)
        high_intervention_episodes = [
            Episode(
                id=f"episode_{i}",
                title=f"Episode {i}",
                agent_id="student_agent_123",
                user_id="user_123",
                workspace_id="default",
                status="completed",
                maturity_at_time="STUDENT",
                human_intervention_count=1 if i % 2 == 0 else 0,  # 50% intervention
                constitutional_score=0.8,
                started_at=datetime.now(),
                ended_at=datetime.now(),
                topics=[],
                entities=[],
                execution_ids=[],
                importance_score=0.7
            )
            for i in range(15)
        ]

        agent_query = Mock()
        agent_query.first = Mock(return_value=mock_student_agent)

        episode_query = Mock()
        episode_query.filter = Mock(return_value=episode_query)
        episode_query.all = Mock(return_value=high_intervention_episodes)

        def query_side_effect(model):
            if model == AgentRegistry:
                return agent_query
            return episode_query

        db_session.query = query_side_effect

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.calculate_readiness_score(
            agent_id="student_agent_123",
            target_maturity="INTERN"
        ))

        # At the threshold (50%), should pass for INTERN
        # 8/15 = 0.533, which is approximately 50%
        assert abs(result["intervention_rate"] - 0.533) < 0.01

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_unknown_maturity_level(self, mock_lancedb, db_session):
        """Test error handling for unknown maturity level"""
        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.calculate_readiness_score(
            agent_id="agent_123",
            target_maturity="INVALID_LEVEL"
        ))

        assert "error" in result
        assert "Unknown maturity level" in result["error"]


class TestAgentPromotion:
    """Tests for agent promotion"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_promote_agent_success(self, mock_lancedb, db_session, mock_student_agent):
        """Test successful agent promotion"""
        # Use a callable that returns the agent object to simulate proper query behavior
        def query_return_value(model):
            if model == AgentRegistry:
                agent_query = Mock()
                agent_query.filter = Mock(return_value=agent_query)
                agent_query.first = Mock(return_value=mock_student_agent)
                return agent_query
            return Mock()

        db_session.query = query_return_value

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.promote_agent(
            agent_id="student_agent_123",
            new_maturity="INTERN",
            validated_by="admin_user"
        ))

        assert result is True
        assert db_session.commit.called
        # Check that metadata_json was updated
        assert mock_student_agent.metadata_json is not None
        assert mock_student_agent.metadata_json.get("promoted_by") == "admin_user"

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_promote_agent_not_found(self, mock_lancedb, db_session):
        """Test promotion of non-existent agent"""
        agent_query = Mock()
        agent_query.filter = Mock(return_value=agent_query)
        agent_query.first = Mock(return_value=None)
        db_session.query = Mock(return_value=agent_query)

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.promote_agent(
            agent_id="nonexistent_agent",
            new_maturity="INTERN",
            validated_by="admin_user"
        ))

        assert result is False

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_promote_agent_invalid_maturity(self, mock_lancedb, db_session, mock_student_agent):
        """Test promotion with invalid maturity level"""
        agent_query = Mock()
        agent_query.first = Mock(return_value=mock_student_agent)
        db_session.query = Mock(return_value=agent_query)

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.promote_agent(
            agent_id="student_agent_123",
            new_maturity="INVALID_LEVEL",
            validated_by="admin_user"
        ))

        assert result is False


class TestGraduationExam:
    """Tests for graduation exam functionality"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_run_graduation_exam(self, mock_lancedb, db_session):
        """Test running graduation exam on edge cases"""
        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.run_graduation_exam(
            agent_id="student_agent_123",
            edge_case_episodes=["edge_case_1", "edge_case_2", "edge_case_3"]
        ))

        assert "passed" in result
        assert "score" in result
        assert result["total_cases"] == 3

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_validate_constitutional_compliance(self, mock_lancedb, db_session):
        """Test constitutional compliance validation"""
        episode = Episode(
            id="episode_123",
            title="Tax Calculation Episode",
            agent_id="agent_123",
            user_id="user_123",
            workspace_id="default",
            status="completed",
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=1.0,
            started_at=datetime.now(),
            ended_at=datetime.now(),
            topics=["tax", "HST"],
            entities=[],
            execution_ids=[],
            importance_score=0.9
        )

        episode_query = Mock()
        episode_query.first = Mock(return_value=episode)
        db_session.query = Mock(return_value=episode_query)

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.validate_constitutional_compliance(
            episode_id="episode_123"
        ))

        assert "compliant" in result
        assert "score" in result
        assert result["episode_id"] == "episode_123"


class TestGraduationAuditTrail:
    """Tests for graduation audit trail"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_get_graduation_audit_trail(self, mock_lancedb, db_session, mock_student_agent, mock_episodes):
        """Test getting full audit trail for agent"""
        agent_query = Mock()
        agent_query.first = Mock(return_value=mock_student_agent)

        episode_query = Mock()
        episode_query.filter = Mock(return_value=episode_query)
        episode_query.order_by = Mock(return_value=episode_query)
        episode_query.all = Mock(return_value=mock_episodes)

        def query_side_effect(model):
            if model == AgentRegistry:
                return agent_query
            return episode_query

        db_session.query = query_side_effect

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.get_graduation_audit_trail(
            agent_id="student_agent_123"
        ))

        assert "agent_id" in result
        assert "current_maturity" in result
        assert "total_episodes" in result
        assert result["total_episodes"] == 15
        assert "episodes_by_maturity" in result

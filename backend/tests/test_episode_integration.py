"""
Integration tests for Episode System
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from core.episode_segmentation_service import EpisodeSegmentationService
from core.episode_retrieval_service import EpisodeRetrievalService
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.agent_graduation_service import AgentGraduationService
from core.models import Episode, EpisodeSegment, AgentRegistry, AgentStatus


@pytest.fixture
def db_session():
    """Mock database session"""
    session = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.query = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def mock_agent(db_session):
    """Mock agent"""
    agent = AgentRegistry(
        id="agent_123",
        name="Test Agent",
        category="Finance",
        status=AgentStatus.STUDENT
    )
    return agent


@pytest.fixture
def mock_episode():
    """Mock episode"""
    episode = Episode(
        id="episode_123",
        title="Test Episode",
        agent_id="agent_123",
        user_id="user_123",
        workspace_id="default",
        status="completed",
        maturity_at_time="STUDENT",
        human_intervention_count=0,
        constitutional_score=0.85,
        importance_score=0.7
    )
    episode.created_at = datetime.now()
    return episode


class TestEpisodeRetrievalIntegration:
    """Integration tests for episode retrieval"""

    @patch('core.episode_retrieval_service.AgentGovernanceService')
    @patch('core.episode_retrieval_service.get_lancedb_handler')
    def test_temporal_retrieval(self, mock_lancedb, mock_governance, db_session):
        """Test temporal episode retrieval"""
        # Setup mocks
        mock_gov_service = Mock()
        mock_gov_service.can_perform_action = Mock(return_value={"allowed": True, "agent_maturity": "STUDENT"})
        mock_governance.return_value = mock_gov_service

        # Create mock episodes
        mock_episodes = [
            Episode(
                id="ep_1",
                title="Episode 1",
                agent_id="agent_123",
                user_id="user_123",
                workspace_id="default",
                status="completed",
                maturity_at_time="STUDENT",
                human_intervention_count=0,
                constitutional_score=0.85,
                importance_score=0.7,
                started_at=datetime.now(),
                topics=[],
                entities=[],
                execution_ids=[]
            )
        ]

        # Mock query chain properly - each method returns a query-like object
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.order_by = Mock(return_value=mock_query)
        # limit() should return an object with all() method
        mock_result_set = Mock()
        mock_result_set.all = Mock(return_value=mock_episodes)
        mock_query.limit = Mock(return_value=mock_result_set)
        db_session.query = Mock(return_value=mock_query)

        service = EpisodeRetrievalService(db_session)

        import asyncio
        result = asyncio.run(service.retrieve_temporal(
            agent_id="agent_123",
            time_range="7d"
        ))

        assert "episodes" in result
        assert "governance_check" in result
        assert len(result["episodes"]) == 1

    @patch('core.episode_retrieval_service.AgentGovernanceService')
    @patch('core.episode_retrieval_service.get_lancedb_handler')
    def test_sequential_retrieval(self, mock_lancedb, mock_governance, db_session, mock_episode):
        """Test sequential episode retrieval with segments"""
        # Setup mocks
        mock_gov_service = Mock()
        mock_governance.return_value = mock_gov_service

        # Mock segment
        mock_segment = EpisodeSegment(
            id="segment_1",
            episode_id="episode_123",
            segment_type="conversation",
            sequence_order=1,
            content="Test content",
            source_type="chat_message",
            created_at=datetime.now()
        )

        # Track which query is being called
        query_count = [0]

        def query_side_effect(model):
            query_count[0] += 1
            if query_count[0] == 1:
                # First query: Episode
                mock_episode_query = Mock()
                mock_episode_query.first = Mock(return_value=mock_episode)
                return mock_episode_query
            else:
                # Second query: EpisodeSegment
                mock_segment_query = Mock()
                mock_segment_query.order_by = Mock(return_value=mock_segment_query)
                mock_segment_query.all = Mock(return_value=[mock_segment])
                return mock_segment_query

        db_session.query = query_side_effect

        service = EpisodeRetrievalService(db_session)

        import asyncio
        result = asyncio.run(service.retrieve_sequential(
            episode_id="episode_123",
            agent_id="agent_123"
        ))

        assert "episode" in result
        assert "segments" in result
        assert len(result["segments"]) == 1


class TestEpisodeLifecycle:
    """Integration tests for episode lifecycle"""

    @patch('core.episode_lifecycle_service.get_lancedb_handler')
    def test_update_importance_scores(self, mock_lancedb, db_session):
        """Test importance score update"""
        # Create a mock episode that we can modify
        mock_episode = Episode(
            id="episode_123",
            title="Test Episode",
            agent_id="agent_123",
            user_id="user_123",
            workspace_id="default",
            status="completed",
            maturity_at_time="STUDENT",
            human_intervention_count=0,
            constitutional_score=0.85,
            importance_score=0.5,  # Start at 0.5
            started_at=datetime.now(),
            topics=[],
            entities=[],
            execution_ids=[]
        )

        # Mock episode query to return our mock episode
        mock_query = Mock()
        mock_query.first = Mock(return_value=mock_episode)
        db_session.query.return_value = mock_query

        service = EpisodeLifecycleService(db_session)

        import asyncio
        result = asyncio.run(service.update_importance_scores(
            episode_id="episode_123",
            user_feedback=0.8
        ))

        assert result is True
        # The importance score should be updated (0.5 * 0.8 + 0.8/2 * 0.2 = 0.56)
        assert mock_episode.importance_score > 0.5


class TestAgentGraduation:
    """Integration tests for agent graduation"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_calculate_readiness_score(self, mock_lancedb, db_session, mock_agent):
        """Test readiness score calculation"""
        # Mock episodes query
        mock_episode = Episode(
            id="ep_1",
            agent_id="agent_123",
            status="completed",
            maturity_at_time="STUDENT",
            human_intervention_count=1,
            constitutional_score=0.8,
            started_at=datetime.now(),
            ended_at=datetime.now(),
            title="Test",
            topics=[],
            entities=[],
            execution_ids=[],
            user_id="user_123",
            workspace_id="default"
        )

        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.all = Mock(return_value=[mock_episode] * 15)  # 15 episodes
        db_session.query.return_value = mock_query

        # Mock agent query
        def query_side_effect(model):
            if model == AgentRegistry:
                agent_query = Mock()
                agent_query.first = Mock(return_value=mock_agent)
                return agent_query
            return mock_query

        db_session.query = query_side_effect

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.calculate_readiness_score(
            agent_id="agent_123",
            target_maturity="INTERN"
        ))

        assert "ready" in result
        assert "score" in result
        assert "episode_count" in result
        assert result["episode_count"] == 15

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_promote_agent(self, mock_lancedb, db_session, mock_agent):
        """Test agent promotion"""
        mock_query = Mock()
        mock_query.first = Mock(return_value=mock_agent)
        db_session.query.return_value = mock_query

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.promote_agent(
            agent_id="agent_123",
            new_maturity="INTERN",
            validated_by="user_123"
        ))

        assert result is True
        assert db_session.commit.called


@pytest.mark.integration
class TestFullEpisodeLifecycle:
    """Full integration tests for episode lifecycle"""

    @patch('core.episode_segmentation_service.get_lancedb_handler')
    def test_create_to_retrieve_workflow(self, mock_lancedb, db_session):
        """Test full workflow: create episode -> retrieve -> decay"""
        # This would be a more complex test with real DB interactions
        # For now, it's a placeholder showing the intended flow
        pass

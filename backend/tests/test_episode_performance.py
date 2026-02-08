"""
Performance tests for Episode System
"""

import pytest
import time
from unittest.mock import Mock, patch

from core.episode_retrieval_service import EpisodeRetrievalService
from core.models import Episode


@pytest.fixture
def db_session():
    """Mock database session"""
    session = Mock()
    session.add = Mock()
    session.commit = Mock()
    return session


@pytest.fixture
def mock_episodes():
    """Generate mock episodes for performance testing"""
    episodes = []
    for i in range(100):
        episode = Episode(
            id=f"episode_{i}",
            title=f"Episode {i}",
            agent_id="agent_123",
            user_id="user_123",
            workspace_id="default",
            status="completed",
            maturity_at_time="STUDENT",
            human_intervention_count=0,
            constitutional_score=0.8,
            importance_score=0.7
        )
        episodes.append(episode)
    return episodes


class TestEpisodeRetrievalPerformance:
    """Performance tests for episode retrieval"""

    @patch('core.episode_retrieval_service.AgentGovernanceService')
    @patch('core.episode_retrieval_service.get_lancedb_handler')
    def test_temporal_retrieval_performance(
        self, mock_lancedb, mock_governance, db_session, mock_episodes
    ):
        """Test temporal retrieval performance < 100ms"""
        # Setup mocks
        mock_gov_service = Mock()
        mock_gov_service.can_perform_action = Mock(return_value={"allowed": True, "agent_maturity": "STUDENT"})
        mock_governance.return_value = mock_gov_service

        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.order_by = Mock(return_value=mock_query)
        # limit() should return an object with all() method
        mock_result_set = Mock()
        mock_result_set.all = Mock(return_value=mock_episodes[:50])
        mock_query.limit = Mock(return_value=mock_result_set)
        db_session.query = Mock(return_value=mock_query)

        service = EpisodeRetrievalService(db_session)

        import asyncio
        start = time.time()
        result = asyncio.run(service.retrieve_temporal(
            agent_id="agent_123",
            time_range="7d"
        ))
        duration = (time.time() - start) * 1000  # Convert to ms

        assert duration < 100, f"Temporal retrieval took {duration:.2f}ms, expected < 100ms"

    @patch('core.episode_retrieval_service.AgentGovernanceService')
    @patch('core.episode_retrieval_service.get_lancedb_handler')
    def test_semantic_retrieval_performance(
        self, mock_lancedb, mock_governance, db_session
    ):
        """Test semantic retrieval performance < 100ms"""
        # Setup mocks
        mock_gov_service = Mock()
        mock_gov_service.can_perform_action = Mock(return_value={"allowed": True})
        mock_governance.return_value = mock_gov_service

        mock_handler = Mock()
        mock_handler.search = Mock(return_value=[])
        mock_lancedb.return_value = mock_handler

        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.all = Mock(return_value=[])
        db_session.query.return_value = mock_query

        service = EpisodeRetrievalService(db_session)

        import asyncio
        start = time.time()
        result = asyncio.run(service.retrieve_semantic(
            agent_id="agent_123",
            query="tax calculations"
        ))
        duration = (time.time() - start) * 1000

        assert duration < 100, f"Semantic retrieval took {duration:.2f}ms, expected < 100ms"

    @patch('core.episode_retrieval_service.AgentGovernanceService')
    @patch('core.episode_retrieval_service.get_lancedb_handler')
    def test_contextual_retrieval_performance(
        self, mock_lancedb, mock_governance, db_session, mock_episodes
    ):
        """Test contextual retrieval performance < 100ms"""
        # Setup mocks
        mock_gov_service = Mock()
        mock_gov_service.can_perform_action = Mock(return_value={"allowed": True, "agent_maturity": "STUDENT"})
        mock_governance.return_value = mock_gov_service

        mock_handler = Mock()
        mock_handler.search = Mock(return_value=[])
        mock_lancedb.return_value = mock_handler

        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.order_by = Mock(return_value=mock_query)
        # limit() should return an object with all() method
        mock_result_set = Mock()
        mock_result_set.all = Mock(return_value=mock_episodes[:50])
        mock_query.limit = Mock(return_value=mock_result_set)
        # For semantic query
        mock_query.all = Mock(return_value=[])
        mock_query.first = Mock(return_value=None)
        db_session.query = Mock(return_value=mock_query)

        service = EpisodeRetrievalService(db_session)

        import asyncio
        start = time.time()
        result = asyncio.run(service.retrieve_contextual(
            agent_id="agent_123",
            current_task="Calculate HST for invoices"
        ))
        duration = (time.time() - start) * 1000

        assert duration < 100, f"Contextual retrieval took {duration:.2f}ms, expected < 100ms"


class TestEpisodeSegmentationPerformance:
    """Performance tests for episode segmentation"""

    @patch('core.episode_segmentation_service.get_lancedb_handler')
    def test_episode_creation_performance(self, mock_lancedb, db_session):
        """Test episode creation performance < 5s"""
        from core.episode_segmentation_service import EpisodeSegmentationService

        # This is a basic performance test
        # In real scenarios, you'd have actual chat data
        start = time.time()

        service = EpisodeSegmentationService(db_session)

        # Generate title performance
        from core.models import ChatMessage
        from datetime import datetime

        messages = [
            ChatMessage(
                id=f"msg_{i}",
                content=f"Message {i}: Discussing tax calculations and HST",
                role="user",
                created_at=datetime.now()
            )
            for i in range(50)
        ]

        title = service._generate_title(messages, [])

        duration = time.time() - start

        assert duration < 1.0, f"Title generation took {duration:.2f}s, expected < 1s"
        assert "Discussing tax calculations" in title


class TestEpisodeScalability:
    """Scalability tests for episode system"""

    @patch('core.episode_retrieval_service.AgentGovernanceService')
    @patch('core.episode_retrieval_service.get_lancedb_handler')
    def test_large_dataset_performance(
        self, mock_lancedb, mock_governance, db_session
    ):
        """Test performance with large dataset (1000+ episodes)"""
        # Generate large number of mock episodes
        mock_gov_service = Mock()
        mock_gov_service.can_perform_action = Mock(return_value={"allowed": True, "agent_maturity": "STUDENT"})
        mock_governance.return_value = mock_gov_service

        from datetime import datetime
        large_episode_list = [
            Episode(
                id=f"episode_{i}",
                title=f"Episode {i}",
                agent_id="agent_123",
                user_id="user_123",
                workspace_id="default",
                status="completed",
                maturity_at_time="STUDENT",
                human_intervention_count=0,
                constitutional_score=0.8,
                importance_score=0.7,
                started_at=datetime.now(),
                topics=[],
                entities=[],
                execution_ids=[]
            )
            for i in range(1000)
        ]

        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.order_by = Mock(return_value=mock_query)
        # limit() should return an object with all() method
        mock_result_set = Mock()
        mock_result_set.all = Mock(return_value=large_episode_list[:50])
        mock_query.limit = Mock(return_value=mock_result_set)
        db_session.query.return_value = mock_query

        service = EpisodeRetrievalService(db_session)

        import asyncio
        start = time.time()
        result = asyncio.run(service.retrieve_temporal(
            agent_id="agent_123",
            time_range="90d",
            limit=50
        ))
        duration = (time.time() - start) * 1000

        # Should still be fast even with 1000+ episodes
        assert duration < 100, f"Large dataset retrieval took {duration:.2f}ms, expected < 100ms"

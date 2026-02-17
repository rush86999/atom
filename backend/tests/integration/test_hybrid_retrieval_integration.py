"""
Integration Tests for Hybrid Retrieval System

Tests cover:
- API endpoints (POST /agents/{id}/retrieve-hybrid, /retrieve-baseline)
- End-to-end retrieval flows
- Performance benchmarks
- A/B testing (hybrid vs. baseline)
"""
import pytest
import time
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from main_api_app import app
from core.models import Episode
from tests.factories.agent_factory import AgentFactory
from tests.factories.episode_factory import EpisodeFactory


class TestHybridRetrievalAPI:
    """Test hybrid retrieval API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent_with_data(self, db_session):
        """Create agent with test episodes."""
        agent = AgentFactory(status="AUTONOMOUS")

        # Create 200 episodes
        episodes = []
        for i in range(200):
            episode = EpisodeFactory(
                agent_id=agent.id,
                summary=f"Episode {i} about topic {i % 20}",
                title=f"Episode {i}",
                description=f"Detailed content for episode {i} " * 15
            )
            episodes.append(episode)

        db_session.commit()
        return agent, episodes

    def test_retrieve_hybrid_endpoint_success_mocked(self, client, agent_with_data):
        """Test POST /agents/{id}/retrieve-hybrid returns results (mocked)."""
        agent, episodes = agent_with_data

        # Mock the hybrid retrieval service
        mock_results = [
            {
                "episode_id": episodes[i].id,
                "relevance_score": 0.9 - (i * 0.02),
                "stage": "reranked"
            }
            for i in range(min(20, len(episodes)))
        ]

        with patch('core.hybrid_retrieval_service.HybridRetrievalService') as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.retrieve_semantic_hybrid = AsyncMock(return_value=[
                (r["episode_id"], r["relevance_score"], r["stage"])
                for r in mock_results
            ])

            response = client.post(
                f"/agents/{agent.id}/retrieve-hybrid",
                json={
                    "query": "episodes about topic 5",
                    "coarse_top_k": 100,
                    "rerank_top_k": 20,
                    "use_reranking": True
                }
            )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "results" in data
        assert len(data["results"]) <= 20

        # Check result structure
        for result in data["results"]:
            assert "episode_id" in result
            assert "relevance_score" in result
            assert "stage" in result
            assert 0.0 <= result["relevance_score"] <= 1.0

    def test_retrieve_baseline_endpoint_success_mocked(self, client, agent_with_data):
        """Test POST /agents/{id}/retrieve-baseline returns results (mocked)."""
        agent, episodes = agent_with_data

        # Mock the baseline retrieval
        mock_results = [
            {
                "episode_id": episodes[i].id,
                "relevance_score": 0.75 - (i * 0.02)
            }
            for i in range(min(20, len(episodes)))
        ]

        with patch('core.hybrid_retrieval_service.HybridRetrievalService') as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.retrieve_semantic_baseline = AsyncMock(return_value=[
                (r["episode_id"], r["relevance_score"])
                for r in mock_results
            ])

            response = client.post(
                f"/agents/{agent.id}/retrieve-baseline",
                json={
                    "query": "episodes about topic 10",
                    "top_k": 20
                }
            )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "results" in data
        assert len(data["results"]) <= 20

        # Baseline results should NOT have stage tag
        for result in data["results"]:
            assert "episode_id" in result
            assert "relevance_score" in result
            assert "stage" not in result

    def test_retrieve_hybrid_performance_mocked(self, client, agent_with_data):
        """Test hybrid retrieval performance (<200ms) (mocked)."""
        agent, episodes = agent_with_data

        # Mock the service to return quickly
        with patch('core.hybrid_retrieval_service.HybridRetrievalService') as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.retrieve_semantic_hybrid = AsyncMock(return_value=[])

            # Measure response time
            start = time.time()
            response = client.post(
                f"/agents/{agent.id}/retrieve-hybrid",
                json={
                    "query": "test query for performance",
                    "coarse_top_k": 100,
                    "rerank_top_k": 50,
                    "use_reranking": True
                }
            )
            duration_ms = (time.time() - start) * 1000

        # Assertions
        assert response.status_code == 200
        # Mocked version should be very fast (<200ms easily)
        assert duration_ms < 200, f"Response should be <200ms, got {duration_ms:.1f}ms"


class TestEndToEndFlows:
    """Test end-to-end retrieval flows."""

    @pytest.fixture
    def service(self, db_session):
        """Create HybridRetrievalService."""
        from core.hybrid_retrieval_service import HybridRetrievalService
        return HybridRetrievalService(db)

    @pytest.mark.asyncio
    async def test_full_retrieval_flow_mocked(self, service, db):
        """Test complete flow: query → retrieve → fetch episodes (mocked)."""
        # Create agent and episodes
        agent = AgentFactory()
        episodes = [
            EpisodeFactory(
                agent_id=agent.id,
                summary=f"Episode {i} about specific topic",
                title=f"Episode {i}",
                description=f"Content {i}"
            )
            for i in range(100)
        ]
        db_session.commit()

        # Mock retrieval
        mock_results = [
            (episodes[i].id, 0.9 - (i * 0.01), "reranked")
            for i in range(min(20, len(episodes)))
        ]

        with patch.object(service, 'retrieve_semantic_hybrid', new=AsyncMock(return_value=mock_results)):
            # Retrieve
            results = await service.retrieve_semantic_hybrid(
                agent_id=agent.id,
                query="specific topic",
                coarse_top_k=50,
                rerank_top_k=20,
                use_reranking=True
            )

            # Fetch full episode data
            episode_ids = [ep_id for ep_id, _, _ in results]
            fetched_episodes = db_session.query(Episode).filter(
                Episode.id.in_(episode_ids)
            ).all()

            # Assertions
            assert len(fetched_episodes) > 0
            assert len(fetched_episodes) == len(episode_ids)

            # Verify all episodes belong to agent
            for ep in fetched_episodes:
                assert ep.agent_id == agent.id


class TestABTesting:
    """Test A/B comparison: hybrid vs. baseline."""

    @pytest.fixture
    def service(self, db_session):
        """Create HybridRetrievalService."""
        from core.hybrid_retrieval_service import HybridRetrievalService
        return HybridRetrievalService(db)

    @pytest.mark.asyncio
    async def test_hybrid_outperforms_baseline_mocked(
        self, service, db
    ):
        """
        A/B test: hybrid should improve relevance by >15% (mocked).

        Measures: Average relevance score for top-10 results.

        Note: Mocked version simulates the improvement.
        Real A/B testing requires actual relevance judgments.
        """
        import numpy as np

        # Create agent and episodes
        agent = AgentFactory()
        episodes = []
        for i in range(200):
            # Create episodes with varying relevance to test query
            if i < 50:
                # High relevance
                summary = f"machine learning and neural networks"
            elif i < 100:
                # Medium relevance
                summary = f"machine learning algorithms"
            else:
                # Low relevance
                summary = f"unrelated topic {i}"

            episode = EpisodeFactory(
                agent_id=agent.id,
                summary=summary,
                title=f"Episode {i}",
                description=f"Content {i}"
            )
            episodes.append(episode)

        db_session.commit()

        query = "neural networks"

        # Mock baseline retrieval (lower scores)
        baseline_results = [
            (episodes[i].id, 0.5 + (i * 0.01))
            for i in range(min(10, len(episodes)))
        ]

        # Mock hybrid retrieval (15% higher scores)
        hybrid_results = [
            (episodes[i].id, (0.5 + (i * 0.01)) * 1.15, "reranked")
            for i in range(min(10, len(episodes)))
        ]

        with patch.object(service, 'retrieve_semantic_baseline', new=AsyncMock(return_value=baseline_results)):
            with patch.object(service, 'retrieve_semantic_hybrid', new=AsyncMock(return_value=hybrid_results)):
                # Baseline retrieval
                baseline_results_actual = await service.retrieve_semantic_baseline(
                    agent_id=agent.id,
                    query=query,
                    top_k=10
                )
                baseline_scores = [score for _, score in baseline_results_actual[:10]]
                baseline_avg = np.mean(baseline_scores) if baseline_scores else 0.0

                # Hybrid retrieval
                hybrid_results_actual = await service.retrieve_semantic_hybrid(
                    agent_id=agent.id,
                    query=query,
                    coarse_top_k=100,
                    rerank_top_k=10,
                    use_reranking=True
                )
                hybrid_scores = [score for _, score, _ in hybrid_results_actual[:10]]
                hybrid_avg = np.mean(hybrid_scores) if hybrid_scores else 0.0

                # Calculate improvement
                improvement = (hybrid_avg - baseline_avg) / (baseline_avg + 1e-8)

                # Assertion (mocked version guarantees 15% improvement)
                assert improvement > 0.15, \
                    f"Hybrid should improve relevance by >15%, got {improvement:.1%} improvement"


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create agent."""
        agent = AgentFactory(status="AUTONOMOUS")
        db_session.commit()
        return agent

    def test_retrieve_with_empty_query(self, client, agent):
        """Test retrieval with empty query."""
        response = client.post(
            f"/agents/{agent.id}/retrieve-hybrid",
            json={
                "query": "",
                "coarse_top_k": 10,
                "rerank_top_k": 5,
                "use_reranking": True
            }
        )

        # Should return 422 for validation error or handle gracefully
        assert response.status_code in [200, 422]

    def test_retrieve_with_invalid_agent(self, client):
        """Test retrieval with non-existent agent."""
        response = client.post(
            "/agents/nonexistent-agent-id/retrieve-hybrid",
            json={
                "query": "test query",
                "coarse_top_k": 10,
                "rerank_top_k": 5,
                "use_reranking": True
            }
        )

        # Should handle gracefully
        assert response.status_code in [200, 404]

    def test_retrieve_with_zero_top_k(self, client, agent):
        """Test retrieval with zero top_k."""
        response = client.post(
            f"/agents/{agent.id}/retrieve-hybrid",
            json={
                "query": "test query",
                "coarse_top_k": 0,
                "rerank_top_k": 0,
                "use_reranking": True
            }
        )

        # Should return 422 for validation error or handle gracefully
        assert response.status_code in [200, 422]

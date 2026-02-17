"""
Unit Tests for Hybrid Retrieval System

Tests cover:
- HybridRetrievalService methods
- Cross-encoder reranking
- FastEmbed coarse search
- Fallback behavior
- Embedding consistency
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from core.hybrid_retrieval_service import HybridRetrievalService
from core.embedding_service import EmbeddingService
from core.models import Episode
from tests.factories.agent_factory import AgentFactory
from tests.factories.episode_factory import EpisodeFactory


class TestHybridRetrievalService:
    """Test HybridRetrievalService orchestration."""

    @pytest.fixture
    def service(self, db):
        """Create HybridRetrievalService instance."""
        return HybridRetrievalService(db)

    @pytest.fixture
    def agent_with_episodes(self, db):
        """Create agent with test episodes."""
        agent = AgentFactory(status="AUTONOMOUS")

        # Create 100 episodes with varied content
        episodes = []
        for i in range(100):
            episode = EpisodeFactory(
                agent_id=agent.id,
                summary=f"Test episode {i} about topic {i % 10}",
                title=f"Episode {i}",
                description=f"Detailed description for episode {i} " * 5
            )
            episodes.append(episode)

        db.commit()
        return agent, episodes

    @pytest.mark.asyncio
    async def test_retrieve_semantic_hybrid_with_reranking(
        self, service, agent_with_episodes
    ):
        """Test hybrid retrieval with reranking enabled."""
        agent, episodes = agent_with_episodes

        # Mock the embedding service to avoid actual FastEmbed calls
        with patch.object(service.embedding_service, 'coarse_search_fastembed', new=AsyncMock()) as mock_coarse:
            # Return mock coarse results
            mock_coarse.return_value = [
                (episodes[i].id, 0.8 - (i * 0.01)) for i in range(min(50, len(episodes)))
            ]

            # Mock reranker to return sorted results
            with patch.object(service, '_rerank_cross_encoder', new=AsyncMock()) as mock_rerank:
                mock_rerank.return_value = [
                    (episodes[i].id, 0.9 - (i * 0.015)) for i in range(min(20, len(episodes)))
                ]

                # Search for specific topic
                results = await service.retrieve_semantic_hybrid(
                    agent_id=agent.id,
                    query="episodes about topic 5",
                    coarse_top_k=100,
                    rerank_top_k=50,
                    use_reranking=True
                )

                # Assertions
                assert len(results) > 0, "Should return results"
                assert len(results) <= 50, "Should return at most rerank_top_k results"

                # Check result structure
                for ep_id, score, stage in results:
                    assert isinstance(ep_id, str)
                    assert 0.0 <= score <= 1.0, f"Score should be in [0, 1], got {score}"
                    assert stage in ["reranked", "coarse_fallback", "coarse_only"]

    @pytest.mark.asyncio
    async def test_retrieve_semantic_hybrid_without_reranking(
        self, service, agent_with_episodes
    ):
        """Test hybrid retrieval with reranking disabled (coarse only)."""
        agent, episodes = agent_with_episodes

        # Mock the embedding service
        with patch.object(service.embedding_service, 'coarse_search_fastembed', new=AsyncMock()) as mock_coarse:
            mock_coarse.return_value = [
                (episodes[i].id, 0.8 - (i * 0.01)) for i in range(min(20, len(episodes)))
            ]

            results = await service.retrieve_semantic_hybrid(
                agent_id=agent.id,
                query="episodes about topic 3",
                coarse_top_k=50,
                rerank_top_k=20,
                use_reranking=False
            )

            # Assertions
            assert len(results) > 0
            assert len(results) <= 20

            # All results should be coarse_only
            for ep_id, score, stage in results:
                assert stage == "coarse_only"

    @pytest.mark.asyncio
    async def test_retrieve_semantic_baseline(
        self, service, agent_with_episodes
    ):
        """Test baseline retrieval (FastEmbed only)."""
        agent, episodes = agent_with_episodes

        # Mock the embedding service
        with patch.object(service.embedding_service, 'coarse_search_fastembed', new=AsyncMock()) as mock_coarse:
            mock_coarse.return_value = [
                (episodes[i].id, 0.75 - (i * 0.01)) for i in range(min(20, len(episodes)))
            ]

            results = await service.retrieve_semantic_baseline(
                agent_id=agent.id,
                query="episodes about topic 7",
                top_k=20
            )

            # Assertions
            assert len(results) > 0
            assert len(results) <= 20

            # Check result structure (no stage tag in baseline)
            for ep_id, score in results:
                assert isinstance(ep_id, str)
                assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_fallback_on_reranking_failure(
        self, service, agent_with_episodes
    ):
        """Test fallback to coarse results when reranking fails."""
        agent, episodes = agent_with_episodes

        # Mock coarse search to succeed
        with patch.object(service.embedding_service, 'coarse_search_fastembed', new=AsyncMock()) as mock_coarse:
            mock_coarse.return_value = [
                (episodes[i].id, 0.7 - (i * 0.01)) for i in range(min(20, len(episodes)))
            ]

            # Mock reranker to raise exception
            with patch.object(service, '_rerank_cross_encoder', new=AsyncMock()) as mock_rerank:
                mock_rerank.side_effect = Exception("Reranking failed")

                results = await service.retrieve_semantic_hybrid(
                    agent_id=agent.id,
                    query="test query",
                    coarse_top_k=50,
                    rerank_top_k=20,
                    use_reranking=True
                )

                # Assertions
                assert len(results) > 0, "Should fallback to coarse results"

                # All results should be tagged as coarse_fallback
                for ep_id, score, stage in results:
                    assert stage == "coarse_fallback"

    @pytest.mark.asyncio
    async def test_reranker_lazy_loading(self, service):
        """Test that reranker model is lazy loaded."""
        # Initially, reranker should be None
        assert service._reranker_model is None

        # Mock the coarse search and reranker loading
        with patch.object(service.embedding_service, 'coarse_search_fastembed', new=AsyncMock(return_value=[])):
            with patch.object(service, '_rerank_cross_encoder', new=AsyncMock(return_value=[])):
                # Call retrieve with reranking enabled
                await service.retrieve_semantic_hybrid(
                    agent_id="test_agent",
                    query="test",
                    use_reranking=True
                )

                # Reranker should be loaded (or False if import failed)
                # We don't assert the exact value since it depends on sentence_transformers availability
                assert service._reranker_model is not None


class TestEmbeddingServiceExtensions:
    """Test EmbeddingService extensions for hybrid retrieval."""

    @pytest.fixture
    def embedding_service(self):
        """Create EmbeddingService instance."""
        return EmbeddingService(provider="fastembed")

    @pytest.mark.asyncio
    async def test_create_fastembed_embedding_mocked(self, embedding_service):
        """Test FastEmbed embedding creation (mocked)."""
        # Mock the actual embedding generation to return numpy array
        import numpy as np

        mock_embedding = np.array([0.1] * 384, dtype=np.float32)

        with patch.object(embedding_service, '_fastembed_model', create=True) as mock_model:
            # Mock the embed method to return our test array
            mock_model.embed = Mock(return_value=[mock_embedding])

            text = "This is a test episode about machine learning"
            embedding = await embedding_service.create_fastembed_embedding(text)

            # Assertions
            assert embedding is not None
            assert embedding.shape == (384,), f"Expected 384-dim, got {embedding.shape}"

    @pytest.mark.asyncio
    async def test_fastembed_embedding_consistency_mocked(self, embedding_service):
        """Test that same input produces same embedding (mocked)."""
        import numpy as np

        mock_embedding = np.array([0.2] * 384, dtype=np.float32)

        # Mock the model
        with patch.object(embedding_service, '_fastembed_model', create=True) as mock_model:
            mock_model.embed = Mock(return_value=[mock_embedding])

            text = "Consistent test input"

            embedding1 = await embedding_service.create_fastembed_embedding(text)
            embedding2 = await embedding_service.create_fastembed_embedding(text)

            # Should be identical
            np.testing.assert_array_almost_equal(
                embedding1, embedding2,
                decimal=5,
                err_msg="Same input should produce identical embeddings"
            )

    @pytest.mark.asyncio
    async def test_coarse_search_performance_mocked(self, embedding_service, db):
        """Test FastEmbed coarse search performance (<20ms) - mocked."""
        # Create test data
        agent = AgentFactory()
        episodes = [EpisodeFactory(agent_id=agent.id) for _ in range(100)]
        db.commit()

        # Mock lancedb_handler module to avoid actual LanceDB calls
        mock_lancedb = MagicMock()
        mock_lancedb.search_vector_fastembed = AsyncMock(return_value=[
            (episodes[i].id, 0.8 - (i * 0.005)) for i in range(min(100, len(episodes)))
        ])

        with patch('core.embedding_service.lancedb_handler', mock_lancedb):
            # Measure search time
            start = datetime.utcnow()
            results = await embedding_service.coarse_search_fastembed(
                agent_id=agent.id,
                query="test query",
                top_k=100,
                db=db
            )
            duration_ms = (datetime.utcnow() - start).total_seconds() * 1000

            # Assertions
            assert duration_ms < 20, f"Coarse search should be <20ms, got {duration_ms}ms"
            assert len(results) <= 100


class TestCrossEncoderReranking:
    """Test cross-encoder reranking."""

    @pytest.fixture
    def embedding_service(self):
        """Create EmbeddingService instance."""
        return EmbeddingService(provider="fastembed")

    @pytest.mark.asyncio
    async def test_rerank_cross_encoder_mocked(self, embedding_service, db):
        """Test cross-encoder reranking (mocked)."""
        # Create test data
        agent = AgentFactory()
        episodes = [
            EpisodeFactory(
                agent_id=agent.id,
                summary=f"Episode {i} about specific topic",
                description=f"Content {i} " * 20,
                title=f"Episode {i}"
            )
            for i in range(50)
        ]
        db.commit()

        episode_ids = [ep.id for ep in episodes]

        # Mock the CrossEncoder class
        with patch('core.embedding_service.CrossEncoder') as mock_ce_class:
            mock_model = Mock()
            mock_model.predict = Mock(return_value=[0.9 - (i * 0.01) for i in range(50)])
            mock_ce_class.return_value = mock_model

            # Rerank
            results = await embedding_service.rerank_cross_encoder(
                query="specific topic",
                episode_ids=episode_ids,
                agent_id=agent.id,
                db=db
            )

            # Assertions
            assert len(results) > 0
            assert len(results) <= 50

            # Scores should be in [0, 1]
            for ep_id, score in results:
                assert 0.0 <= score <= 1.0, f"Score should be in [0, 1], got {score}"

            # Results should be sorted by score (descending)
            scores = [score for _, score in results]
            assert scores == sorted(scores, reverse=True), "Results should be sorted by score"

    @pytest.mark.asyncio
    async def test_reranking_performance_mocked(self, embedding_service, db):
        """Test reranking performance (<150ms for 50 candidates) - mocked."""
        # Create test data
        agent = AgentFactory()
        episodes = [EpisodeFactory(agent_id=agent.id) for _ in range(50)]
        db.commit()

        episode_ids = [ep.id for ep in episodes]

        # Mock the CrossEncoder class
        with patch('core.embedding_service.CrossEncoder') as mock_ce_class:
            mock_model = Mock()
            mock_model.predict = Mock(return_value=[0.8] * 50)
            mock_ce_class.return_value = mock_model

            # Measure reranking time
            start = datetime.utcnow()
            results = await embedding_service.rerank_cross_encoder(
                query="test query",
                episode_ids=episode_ids,
                agent_id=agent.id,
                db=db
            )
            duration_ms = (datetime.utcnow() - start).total_seconds() * 1000

            # Assertions (mocked version should be very fast)
            assert duration_ms < 150, f"Reranking should be <150ms, got {duration_ms}ms"

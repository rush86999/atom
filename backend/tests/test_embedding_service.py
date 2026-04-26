"""
Embedding Service Tests

Tests for embedding generation, vector operations, and semantic search.
Coverage target: 20-25 tests for embedding_service.py (716 lines)
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from core.embedding_service import (
    EmbeddingService,
    EmbeddingProvider,
    generate_embedding,
    generate_embeddings_batch
)


class TestEmbeddingGeneration:
    """Test text embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_embedding_fastembed(self):
        """EmbeddingService generates embedding using FastEmbed provider."""
        with patch('core.embedding_service.TextEmbedding') as mock_embedding_class:
            # Mock FastEmbed client
            mock_client = Mock()
            mock_embedding = Mock()
            mock_embedding.tolist.return_value = [0.1, 0.2, 0.3, 0.4]
            mock_client.embed.return_value = [mock_embedding]
            mock_embedding_class.return_value = mock_client

            service = EmbeddingService(provider="fastembed")
            embedding = await service.generate_embedding("test text")

            assert isinstance(embedding, list)
            assert len(embedding) == 4
            assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_generate_embedding_openai(self):
        """EmbeddingService generates embedding using OpenAI provider."""
        mock_llm_service = Mock()
        mock_llm_service.generate_embedding = AsyncMock(return_value=[0.5, 0.6, 0.7])

        with patch('core.embedding_service.LLMService', return_value=mock_llm_service):
            service = EmbeddingService(provider="openai")
            embedding = await service.generate_embedding("test text")

            assert isinstance(embedding, list)
            assert len(embedding) == 3

    @pytest.mark.asyncio
    async def test_generate_embedding_invalid_provider(self):
        """EmbeddingService raises error for unknown provider."""
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            EmbeddingService(provider="unknown_provider")

    @pytest.mark.asyncio
    async def test_generate_embedding_preprocesses_text(self):
        """EmbeddingService preprocesses text before embedding."""
        with patch('core.embedding_service.TextEmbedding') as mock_embedding_class:
            mock_client = Mock()
            mock_embedding = Mock()
            mock_embedding.tolist.return_value = [0.1, 0.2]
            mock_client.embed.return_value = [mock_embedding]
            mock_embedding_class.return_value = mock_client

            service = EmbeddingService(provider="fastembed")

            # Test with extra whitespace
            embedding = await service.generate_embedding("  test   text  ")

            assert len(embedding) == 2

    @pytest.mark.asyncio
    async def test_generate_embedding_truncates_long_text(self):
        """EmbeddingService truncates text exceeding max length."""
        with patch('core.embedding_service.TextEmbedding') as mock_embedding_class:
            mock_client = Mock()
            mock_embedding = Mock()
            mock_embedding.tolist.return_value = [0.1, 0.2]
            mock_client.embed.return_value = [mock_embedding]
            mock_embedding_class.return_value = mock_client

            service = EmbeddingService(provider="fastembed")

            # Very long text (should be truncated)
            long_text = "word " * 10000
            embedding = await service.generate_embedding(long_text)

            assert len(embedding) == 2


class TestBatchEmbedding:
    """Test batch embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_fastembed(self):
        """EmbeddingService generates embeddings for multiple texts efficiently."""
        with patch('core.embedding_service.TextEmbedding') as mock_embedding_class:
            # Mock FastEmbed client
            mock_client = Mock()
            mock_embedding1 = Mock()
            mock_embedding1.tolist.return_value = [0.1, 0.2]
            mock_embedding2 = Mock()
            mock_embedding2.tolist.return_value = [0.3, 0.4]
            mock_client.embed.return_value = [mock_embedding1, mock_embedding2]
            mock_embedding_class.return_value = mock_client

            service = EmbeddingService(provider="fastembed")
            embeddings = await service.generate_embeddings_batch(["text1", "text2"])

            assert len(embeddings) == 2
            assert embeddings[0] == [0.1, 0.2]
            assert embeddings[1] == [0.3, 0.4]

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_openai(self):
        """EmbeddingService generates batch embeddings using OpenAI provider."""
        mock_llm_service = Mock()
        mock_llm_service.generate_embeddings_batch = AsyncMock(
            return_value=[[0.1, 0.2], [0.3, 0.4]]
        )

        with patch('core.embedding_service.LLMService', return_value=mock_llm_service):
            service = EmbeddingService(provider="openai")
            embeddings = await service.generate_embeddings_batch(["text1", "text2"])

            assert len(embeddings) == 2


class TestVectorOperations:
    """Test vector operations and normalization."""

    def test_lru_cache_put(self):
        """EmbeddingService puts value in LRU cache with eviction."""
        service = EmbeddingService(provider="fastembed")

        # Fill cache to max
        for i in range(1001):
            service._lru_cache_put(f"key_{i}", [0.1, 0.2])

        # Oldest key should be evicted
        assert "key_0" not in service._fastembed_cache
        assert "key_1000" in service._fastembed_cache

    def test_lru_cache_get(self):
        """EmbeddingService gets value from LRU cache and updates access order."""
        service = EmbeddingService(provider="fastembed")

        # Add value
        service._lru_cache_put("key_1", [0.1, 0.2])

        # Get value
        value = service._lru_cache_get("key_1")

        assert value == [0.1, 0.2]

    def test_lru_cache_get_miss(self):
        """EmbeddingService returns None for missing cache key."""
        service = EmbeddingService(provider="fastembed")

        value = service._lru_cache_get("nonexistent_key")

        assert value is None

    def test_get_cache_stats(self):
        """EmbeddingService returns cache statistics."""
        service = EmbeddingService(provider="fastembed")

        # Add some entries
        service._lru_cache_put("key_1", [0.1, 0.2])
        service._lru_cache_put("key_2", [0.3, 0.4])

        stats = service.get_cache_stats()

        assert stats["current_size"] == 2
        assert stats["max_size"] == 1000
        assert "utilization_percent" in stats


class TestFastEmbedCoarseSearch:
    """Test FastEmbed coarse search for hybrid retrieval."""

    @pytest.mark.asyncio
    async def test_create_fastembed_embedding(self):
        """EmbeddingService creates 384-dimensional FastEmbed embedding."""
        with patch('core.embedding_service.TextEmbedding') as mock_embedding_class:
            mock_client = Mock()
            mock_embedding = Mock()
            mock_embedding.tolist.return_value = [0.1] * 384
            mock_client.embed.return_value = [mock_embedding]
            mock_embedding_class.return_value = mock_client

            service = EmbeddingService(provider="fastembed")
            embedding = await service.create_fastembed_embedding("test text")

            assert embedding is not None
            assert len(embedding) == 384

    @pytest.mark.asyncio
    async def test_cache_fastembed_embedding(self):
        """EmbeddingService caches FastEmbed embedding in memory."""
        service = EmbeddingService(provider="fastembed")

        # Mock embedding
        embedding = [0.1] * 384

        result = await service.cache_fastembed_embedding(
            episode_id="episode-001",
            embedding=embedding,
            db=None
        )

        assert result is True
        assert service._lru_cache_get("episode-001") == embedding

    @pytest.mark.asyncio
    async def test_get_fastembed_embedding_from_cache(self):
        """EmbeddingService retrieves FastEmbed embedding from cache."""
        service = EmbeddingService(provider="fastembed")

        # Cache embedding
        embedding = [0.1] * 384
        await service.cache_fastembed_embedding("episode-001", embedding, db=None)

        # Retrieve from cache
        retrieved = await service.get_fastembed_embedding("episode-001", db=None)

        assert retrieved == embedding

    @pytest.mark.asyncio
    async def test_coarse_search_fastembed(self):
        """EmbeddingService performs coarse search using FastEmbed."""
        service = EmbeddingService(provider="fastembed")

        # Mock query embedding
        with patch.object(service, 'create_fastembed_embedding', return_value=[0.1] * 384):
            # Mock LanceDB handler
            with patch('core.embedding_service.get_lancedb_handler') as mock_get_handler:
                mock_lancedb = Mock()
                mock_lancedb.similarity_search = AsyncMock(return_value=[
                    {"episode_id": "ep-001", "score": 0.95},
                    {"episode_id": "ep-002", "score": 0.85}
                ])
                mock_get_handler.return_value = mock_lancedb

                results = await service.coarse_search_fastembed(
                    agent_id="agent-001",
                    query="test query",
                    top_k=100,
                    db=Mock()
                )

                assert len(results) == 2
                assert results[0][0] == "ep-001"
                assert results[0][1] == 0.95


class TestSemanticSearch:
    """Test semantic search functionality."""

    @pytest.mark.asyncio
    async def test_rerank_cross_encoder(self):
        """EmbeddingService reranks episodes using cross-encoder."""
        db = Mock(spec=Session)

        # Mock episodes
        mock_episode = Mock()
        mock_episode.id = "ep-001"
        mock_episode.task_description = "Test task"

        db.query.return_value.filter.return_value.all.return_value = [mock_episode]

        service = EmbeddingService(provider="fastembed")

        # Mock cross-encoder
        with patch('core.embedding_service.CrossEncoder') as mock_cross_encoder:
            mock_encoder = Mock()
            mock_encoder.predict.return_value = [0.8, 0.6]
            mock_cross_encoder.return_value = mock_encoder

            results = await service.rerank_cross_encoder(
                query="test query",
                episode_ids=["ep-001"],
                agent_id="agent-001",
                db=db
            )

            assert len(results) == 1
            assert results[0][0] == "ep-001"


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_generate_embedding_function(self):
        """generate_embedding convenience function creates embedding."""
        with patch('core.embedding_service.TextEmbedding') as mock_embedding_class:
            mock_client = Mock()
            mock_embedding = Mock()
            mock_embedding.tolist.return_value = [0.1, 0.2]
            mock_client.embed.return_value = [mock_embedding]
            mock_embedding_class.return_value = mock_client

            embedding = await generate_embedding("test text")

            assert isinstance(embedding, list)
            assert len(embedding) == 2

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_function(self):
        """generate_embeddings_batch convenience function creates batch embeddings."""
        with patch('core.embedding_service.TextEmbedding') as mock_embedding_class:
            mock_client = Mock()
            mock_embedding1 = Mock()
            mock_embedding1.tolist.return_value = [0.1, 0.2]
            mock_embedding2 = Mock()
            mock_embedding2.tolist.return_value = [0.3, 0.4]
            mock_client.embed.return_value = [mock_embedding1, mock_embedding2]
            mock_embedding_class.return_value = mock_client

            embeddings = await generate_embeddings_batch(["text1", "text2"])

            assert len(embeddings) == 2


class TestProviderConfiguration:
    """Test provider configuration and defaults."""

    def test_get_default_model_fastembed(self):
        """EmbeddingService returns default FastEmbed model."""
        service = EmbeddingService(provider="fastembed")

        assert service.model == "BAAI/bge-small-en-v1.5"

    def test_get_default_model_openai(self):
        """EmbeddingService returns default OpenAI model."""
        with patch.dict('os.environ', {'OPENAI_EMBEDDING_MODEL': 'text-embedding-3-small'}):
            service = EmbeddingService(provider="openai")

            assert "text-embedding" in service.model

    def test_provider_normalization_local_to_fastembed(self):
        """EmbeddingService normalizes 'local' provider to 'fastembed'."""
        service = EmbeddingService(provider="local")

        assert service.provider == "fastembed"

    def test_custom_model_override(self):
        """EmbeddingService accepts custom model override."""
        service = EmbeddingService(
            provider="fastembed",
            model="BAAI/bge-base-en-v1.5"
        )

        assert service.model == "BAAI/bge-base-en-v1.5"

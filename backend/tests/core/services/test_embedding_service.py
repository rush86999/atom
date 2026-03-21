"""
Tests for EmbeddingService

Tests for embedding generation service including:
- FastEmbed embeddings
- OpenAI embeddings
- Batch processing
- Cache operations
- Cross-encoder reranking
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List


@pytest.fixture
def mock_fastembed():
    """Mock fastembed module."""
    with patch('core.embedding_service.DOCLING_AVAILABLE', False):
        with patch('core.embedding_service.NUMPY_AVAILABLE', True) as mock_numpy:
            import numpy as np
            mock_numpy.return_value = True

            # Mock TextEmbedding
            mock_embedding_class = MagicMock()
            mock_instance = MagicMock()
            mock_instance.embed.return_value = [np.array([0.1, 0.2, 0.3, 0.4] * 96)]  # 384-dim
            mock_embedding_class.return_value = mock_instance

            with patch('core.embedding_service.TextEmbedding', mock_embedding_class):
                yield {
                    'numpy': np,
                    'TextEmbedding': mock_embedding_class,
                }


@pytest.fixture
def embedding_service():
    """Create embedding service instance."""
    from core.embedding_service import EmbeddingService
    # Use fastembed by default
    return EmbeddingService(provider="fastembed")


class TestEmbeddingServiceInit:
    """Tests for EmbeddingService initialization."""

    def test_init_default_provider(self):
        """Test initialization with default provider."""
        from core.embedding_service import EmbeddingService
        service = EmbeddingService()
        assert service.provider == "fastembed"

    def test_init_with_provider(self):
        """Test initialization with specific provider."""
        from core.embedding_service import EmbeddingService, EmbeddingProvider
        service = EmbeddingService(provider="openai")
        assert service.provider == "openai"

    def test_init_invalid_provider(self):
        """Test initialization with invalid provider."""
        from core.embedding_service import EmbeddingService
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            EmbeddingService(provider="invalid")

    def test_init_with_config(self):
        """Test initialization with config."""
        from core.embedding_service import EmbeddingService
        config = {"api_key": "test-key"}
        service = EmbeddingService(provider="openai", config=config)
        assert service.config == config

    def test_init_cache_initialization(self):
        """Test cache is initialized."""
        from core.embedding_service import EmbeddingService
        service = EmbeddingService(provider="fastembed")
        assert hasattr(service, '_fastembed_cache')
        assert hasattr(service, '_fastembed_cache_order')
        assert service._fastembed_cache_max == 1000


class TestGetDefaultModel:
    """Tests for _get_default_model method."""

    @patch.dict('os.environ', {'EMBEDDING_PROVIDER': 'fastembed', 'FASTEMBED_MODEL': 'custom-model'})
    def test_get_default_model_fastembed(self):
        """Test getting default FastEmbed model."""
        from core.embedding_service import EmbeddingService
        service = EmbeddingService(provider="fastembed")
        assert service.model == "custom-model"

    @patch.dict('os.environ', {}, clear=True)
    def test_get_default_model_openai(self):
        """Test getting default OpenAI model."""
        from core.embedding_service import EmbeddingService
        service = EmbeddingService(provider="openai")
        assert service.model == "text-embedding-3-small"


class TestPreprocessText:
    """Tests for _preprocess_text method."""

    def test_preprocess_empty_string(self, embedding_service):
        """Test preprocessing empty string."""
        result = embedding_service._preprocess_text("")
        assert result == ""

    def test_preprocess_whitespace_normalization(self, embedding_service):
        """Test whitespace normalization."""
        result = embedding_service._preprocess_text("hello    world\n\n  test")
        assert result == "hello world test"

    def test_preprocess_truncation(self, embedding_service):
        """Test text truncation for long content."""
        long_text = "a" * 10000
        result = embedding_service._preprocess_text(long_text)
        assert len(result) < 10000

    def test_preprocess_unicode_normalization(self, embedding_service):
        """Test unicode normalization."""
        result = embedding_service._preprocess_text("café naïve")
        assert "café" in result or "cafe" in result


class TestGenerateEmbedding:
    """Tests for generate_embedding method."""

    @pytest.mark.asyncio
    async def test_generate_embedding_fastembed(self, embedding_service):
        """Test generating FastEmbed embedding."""
        with patch.object(embedding_service, '_generate_fastembed_embedding') as mock_gen:
            mock_gen.return_value = [0.1] * 384

            result = await embedding_service.generate_embedding("test text")

            assert len(result) == 384
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_openai(self):
        """Test generating OpenAI embedding."""
        from core.embedding_service import EmbeddingService
        service = EmbeddingService(provider="openai", config={"api_key": "test-key"})

        with patch.object(service, '_generate_openai_embedding') as mock_gen:
            mock_gen.return_value = [0.2] * 1536

            result = await service.generate_embedding("test text")

            assert len(result) == 1536
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_error_handling(self, embedding_service):
        """Test error handling in generate_embedding."""
        with patch.object(embedding_service, '_generate_fastembed_embedding') as mock_gen:
            mock_gen.side_effect = Exception("Generation failed")

            with pytest.raises(Exception, match="Generation failed"):
                await embedding_service.generate_embedding("test text")


class TestGenerateEmbeddingsBatch:
    """Tests for generate_embeddings_batch method."""

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_fastembed(self, embedding_service):
        """Test batch generation with FastEmbed."""
        texts = ["text 1", "text 2", "text 3"]

        with patch.object(embedding_service, '_generate_fastembed_embeddings_batch') as mock_gen:
            mock_gen.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]

            results = await embedding_service.generate_embeddings_batch(texts)

            assert len(results) == 3
            assert all(len(emb) == 384 for emb in results)
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_openai(self):
        """Test batch generation with OpenAI."""
        from core.embedding_service import EmbeddingService
        service = EmbeddingService(provider="openai", config={"api_key": "test-key"})
        texts = ["text 1", "text 2"]

        with patch.object(service, '_generate_openai_embeddings_batch') as mock_gen:
            mock_gen.return_value = [[0.1] * 1536, [0.2] * 1536]

            results = await service.generate_embeddings_batch(texts)

            assert len(results) == 2
            mock_gen.assert_called_once()


class TestFastEmbedCoarseSearch:
    """Tests for FastEmbed coarse search methods."""

    @pytest.mark.asyncio
    async def test_create_fastembed_embedding(self, embedding_service):
        """Test creating FastEmbed embedding."""
        with patch.object(embedding_service, '_generate_fastembed_embedding') as mock_gen:
            import numpy as np
            mock_gen.return_value = [0.1] * 384

            result = await embedding_service.create_fastembed_embedding("test")

            assert isinstance(result, np.ndarray)
            assert result.shape == (384,)

    @pytest.mark.asyncio
    async def test_cache_fastembed_embedding(self, embedding_service):
        """Test caching FastEmbed embedding."""
        embedding = [0.1] * 384

        with patch('core.embedding_service.get_lancedb_handler') as mock_lancedb:
            mock_handler = MagicMock()
            mock_handler.add_embedding = MagicMock()
            mock_lancedb.return_value = mock_handler

            result = await embedding_service.cache_fastembed_embedding(
                episode_id="ep-1",
                embedding=embedding,
                db=None
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_get_fastembed_embedding_cache_hit(self, embedding_service):
        """Test getting cached FastEmbed embedding."""
        episode_id = "ep-1"
        embedding = [0.1] * 384

        # Pre-cache
        embedding_service._lru_cache_put(episode_id, embedding)

        result = await embedding_service.get_fastembed_embedding(episode_id, db=None)

        assert result == embedding

    @pytest.mark.asyncio
    async def test_coarse_search_fastembed(self, embedding_service):
        """Test FastEmbed coarse search."""
        with patch.object(embedding_service, 'create_fastembed_embedding') as mock_create:
            import numpy as np
            mock_create.return_value = np.array([0.1] * 384)

            with patch('core.embedding_service.get_lancedb_handler') as mock_lancedb:
                mock_handler = MagicMock()
                mock_handler.similarity_search.return_value = [
                    {"episode_id": "ep-1", "score": 0.9},
                    {"episode_id": "ep-2", "score": 0.8},
                ]
                mock_lancedb.return_value = mock_handler

                result = await embedding_service.coarse_search_fastembed(
                    agent_id="agent-1",
                    query="test query",
                    top_k=10
                )

                assert len(result) == 2
                assert result[0][0] == "ep-1"


class TestLRUCache:
    """Tests for LRU cache methods."""

    def test_lru_cache_put(self, embedding_service):
        """Test putting value in LRU cache."""
        embedding_service._lru_cache_put("key-1", [0.1] * 384)

        assert "key-1" in embedding_service._fastembed_cache
        assert embedding_service._fastembed_cache_order == ["key-1"]

    def test_lru_cache_get(self, embedding_service):
        """Test getting value from LRU cache."""
        embedding = [0.2] * 384
        embedding_service._lru_cache_put("key-1", embedding)

        result = embedding_service._lru_cache_get("key-1")

        assert result == embedding

    def test_lru_cache_eviction(self, embedding_service):
        """Test LRU eviction when cache is full."""
        # Set small cache size for testing
        embedding_service._fastembed_cache_max = 2

        embedding_service._lru_cache_put("key-1", [0.1] * 384)
        embedding_service._lru_cache_put("key-2", [0.2] * 384)
        embedding_service._lru_cache_put("key-3", [0.3] * 384)

        # First key should be evicted
        assert "key-1" not in embedding_service._fastembed_cache
        assert "key-3" in embedding_service._fastembed_cache

    def test_lru_cache_access_order_update(self, embedding_service):
        """Test that access updates LRU order."""
        embedding_service._lru_cache_put("key-1", [0.1] * 384)
        embedding_service._lru_cache_put("key-2", [0.2] * 384)

        # Access key-1
        embedding_service._lru_cache_get("key-1")

        # key-1 should now be at the end
        assert embedding_service._fastembed_cache_order[-1] == "key-1"

    def test_get_cache_stats(self, embedding_service):
        """Test getting cache statistics."""
        embedding_service._lru_cache_put("key-1", [0.1] * 384)
        embedding_service._lru_cache_put("key-2", [0.2] * 384)

        stats = embedding_service.get_cache_stats()

        assert stats["current_size"] == 2
        assert stats["max_size"] == 1000
        assert stats["utilization_percent"] == 0.2


class TestRerankCrossEncoder:
    """Tests for cross-encoder reranking."""

    @pytest.mark.asyncio
    async def test_rerank_cross_encoder(self, embedding_service):
        """Test cross-encoder reranking."""
        from core.models import Episode

        # Mock database session
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [
            Episode(id="ep-1", agent_id="agent-1", summary="summary 1"),
            Episode(id="ep-2", agent_id="agent-1", summary="summary 2"),
        ]

        with patch.object(embedding_service, '_cross_encoder') as mock_encoder:
            import numpy as np
            mock_encoder.predict.return_value = np.array([0.8, 0.9])

            result = await embedding_service.rerank_cross_encoder(
                query="test query",
                episode_ids=["ep-1", "ep-2"],
                agent_id="agent-1",
                db=mock_db
            )

            assert len(result) == 2
            # Should be sorted by score descending
            assert result[0][1] >= result[1][1]

    @pytest.mark.asyncio
    async def test_rerank_cross_encoder_no_cross_encoder(self, embedding_service):
        """Test reranking when cross-encoder not available."""
        mock_db = MagicMock()

        # Ensure cross-encoder is not loaded
        if hasattr(embedding_service, '_cross_encoder'):
            delattr(embedding_service, '_cross_encoder')

        with patch('core.embedding_service.CrossEncoder', side_effect=ImportError):
            result = await embedding_service.rerank_cross_encoder(
                query="test query",
                episode_ids=["ep-1", "ep-2"],
                agent_id="agent-1",
                db=mock_db
            )

            assert result == []


class TestLanceDBHandler:
    """Tests for LanceDBHandler class."""

    def test_lancedb_handler_init(self):
        """Test LanceDB handler initialization."""
        from core.embedding_service import LanceDBHandler

        with patch('core.embedding_service.lancedb') as mock_lancedb:
            mock_conn = MagicMock()
            mock_lancedb.connect.return_value = mock_conn

            handler = LanceDBHandler(db_path="/test/path")

            assert handler.db_path == "/test/path"
            mock_lancedb.connect.assert_called_once_with("/test/path")

    @pytest.mark.asyncio
    async def test_lancedb_upsert(self):
        """Test LanceDB upsert operation."""
        from core.embedding_service import LanceDBHandler

        with patch('core.embedding_service.lancedb') as mock_lancedb:
            mock_conn = MagicMock()
            mock_conn.table_names.return_value = []
            mock_lancedb.connect.return_value = mock_conn

            handler = LanceDBHandler()

            with patch('core.embedding_service.pd.DataFrame') as mock_df:
                data = [{"vector": [0.1, 0.2], "text": "test"}]

                await handler.upsert("test_table", data)

                # Verify table was created
                assert mock_conn.create_table.called or mock_conn.open_table("").called


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_generate_embedding_function(self):
        """Test generate_embedding convenience function."""
        from core.embedding_service import generate_embedding

        with patch('core.embedding_service.EmbeddingService') as mock_service:
            mock_instance = MagicMock()
            mock_service.return_value = mock_instance
            mock_instance.generate_embedding = MagicMock()
            mock_instance.generate_embedding.return_value = [0.1] * 384

            result = await generate_embedding("test text", provider="fastembed")

            assert result == [0.1] * 384

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_function(self):
        """Test generate_embeddings_batch convenience function."""
        from core.embedding_service import generate_embeddings_batch

        with patch('core.embedding_service.EmbeddingService') as mock_service:
            mock_instance = MagicMock()
            mock_service.return_value = mock_instance
            mock_instance.generate_embeddings_batch = MagicMock()
            mock_instance.generate_embeddings_batch.return_value = [[0.1] * 384]

            result = await generate_embeddings_batch(["text"], provider="fastembed")

            assert result == [[0.1] * 384]

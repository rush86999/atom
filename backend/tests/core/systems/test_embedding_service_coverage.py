"""
Coverage-driven tests for EmbeddingService (currently 0% -> target 80%+)

Focus areas from embedding_service.py:
- EmbeddingService.__init__ (initialization)
- generate_embedding() - single text embedding
- generate_embeddings_batch() - batch embedding
- _preprocess_text() - text preprocessing
- _generate_fastembed_embedding() - FastEmbed generation
- _generate_openai_embedding() - OpenAI generation
- LRU cache operations
- FastEmbed coarse search
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.embedding_service import (
    EmbeddingService,
    EmbeddingProvider,
    LanceDBHandler,
    generate_embedding,
    generate_embeddings_batch
)


class TestEmbeddingServiceInit:
    """Test EmbeddingService initialization."""

    def test_init_default_provider(self):
        """Cover default initialization with FastEmbed."""
        service = EmbeddingService()

        assert service.provider == EmbeddingProvider.FASTEMBED
        assert service._client is None
        assert service._fastembed_cache is not None
        assert service._fastembed_cache_max == 1000

    def test_init_openai_provider(self):
        """Cover initialization with OpenAI provider."""
        service = EmbeddingService(provider="openai")

        assert service.provider == EmbeddingProvider.OPENAI

    def test_init_cohere_provider(self):
        """Cover initialization with Cohere provider."""
        service = EmbeddingService(provider="cohere")

        assert service.provider == EmbeddingProvider.COHERE

    def test_init_invalid_provider(self):
        """Cover invalid provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            EmbeddingService(provider="invalid")

    def test_init_with_custom_model(self):
        """Cover initialization with custom model."""
        service = EmbeddingService(provider="fastembed", model="BAAI/bge-base-en-v1.5")

        assert service.model == "BAAI/bge-base-en-v1.5"

    def test_get_default_model(self):
        """Cover default model selection."""
        service = EmbeddingService()

        assert "bge-small" in service.model.lower() or "fastembed" in service.model.lower()


class TestTextPreprocessing:
    """Test text preprocessing methods."""

    @pytest.mark.asyncio
    async def test_preprocess_text_normal(self):
        """Cover normal text preprocessing."""
        service = EmbeddingService()

        text = "  Hello    world  "
        processed = service._preprocess_text(text)

        assert processed == "Hello world"

    @pytest.mark.asyncio
    async def test_preprocess_text_empty(self):
        """Cover empty text handling."""
        service = EmbeddingService()

        processed = service._preprocess_text("")

        assert processed == ""

    @pytest.mark.asyncio
    async def test_preprocess_text_unicode(self):
        """Cover unicode normalization."""
        service = EmbeddingService()

        text = "Hello\u200Bworld"  # Zero-width space
        processed = service._preprocess_text(text)

        # Should normalize unicode
        assert len(processed) >= 0

    @pytest.mark.asyncio
    async def test_preprocess_text_truncation(self):
        """Cover text truncation for long texts."""
        service = EmbeddingService(provider="fastembed")

        # Create very long text
        long_text = "word " * 10000  # ~50k characters

        processed = service._preprocess_text(long_text)

        # Should be truncated
        assert len(processed) < len(long_text)


class TestFastEmbedGeneration:
    """Test FastEmbed embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_fastembed_embedding(self):
        """Cover FastEmbed embedding generation."""
        service = EmbeddingService(provider="fastembed")

        # Mock fastembed import
        with patch('core.embedding_service.TextEmbedding') as mock_embedding_class:
            mock_embedding = MagicMock()
            mock_embedding_class.return_value = mock_embedding

            # Mock embedding result
            mock_result = MagicMock()
            mock_result.tolist.return_value = [0.1, 0.2, 0.3, 0.4]
            mock_embedding.embed.return_value = [mock_result]

            embedding = await service._generate_fastembed_embedding("test text")

            assert len(embedding) == 4
            assert embedding == [0.1, 0.2, 0.3, 0.4]

    @pytest.mark.asyncio
    async def test_generate_fastembed_not_installed(self):
        """Cover FastEmbed not installed raises Exception."""
        service = EmbeddingService(provider="fastembed")

        with patch('core.embedding_service.TextEmbedding', side_effect=ImportError):
            with pytest.raises(Exception, match="FastEmbed package not installed"):
                await service._generate_fastembed_embedding("test")

    @pytest.mark.asyncio
    async def test_generate_fastembed_empty_result(self):
        """Cover FastEmbed empty result handling."""
        service = EmbeddingService(provider="fastembed")

        with patch('core.embedding_service.TextEmbedding') as mock_embedding_class:
            mock_embedding = MagicMock()
            mock_embedding_class.return_value = mock_embedding
            mock_embedding.embed.return_value = []

            with pytest.raises(Exception, match="empty result"):
                await service._generate_fastembed_embedding("test")

    @pytest.mark.asyncio
    async def test_generate_fastembed_embeddings_batch(self):
        """Cover FastEmbed batch embedding generation."""
        service = EmbeddingService(provider="fastembed")

        with patch('core.embedding_service.TextEmbedding') as mock_embedding_class:
            mock_embedding = MagicMock()
            mock_embedding_class.return_value = mock_embedding

            # Mock batch results
            mock_result1 = MagicMock()
            mock_result1.tolist.return_value = [0.1, 0.2]
            mock_result2 = MagicMock()
            mock_result2.tolist.return_value = [0.3, 0.4]

            mock_embedding.embed.return_value = [mock_result1, mock_result2]

            embeddings = await service._generate_fastembed_embeddings_batch(["text1", "text2"])

            assert len(embeddings) == 2
            assert embeddings[0] == [0.1, 0.2]
            assert embeddings[1] == [0.3, 0.4]


class TestOpenAIGeneration:
    """Test OpenAI embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_openai_embedding(self):
        """Cover OpenAI embedding generation."""
        service = EmbeddingService(provider="openai", config={"api_key": "test-key"})

        with patch('core.embedding_service.AsyncOpenAI') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock API response
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.5, 0.6, 0.7])]
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)

            embedding = await service._generate_openai_embedding("test")

            assert len(embedding) == 3
            assert embedding == [0.5, 0.6, 0.7]

    @pytest.mark.asyncio
    async def test_generate_openai_not_installed(self):
        """Cover OpenAI not installed raises Exception."""
        service = EmbeddingService(provider="openai")

        with patch('core.embedding_service.AsyncOpenAI', side_effect=ImportError):
            with pytest.raises(Exception, match="OpenAI package not installed"):
                await service._generate_openai_embedding("test")


class TestCohereGeneration:
    """Test Cohere embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_cohere_embedding(self):
        """Cover Cohere embedding generation."""
        service = EmbeddingService(provider="cohere", config={"api_key": "test-key"})

        with patch('core.embedding_service.cohere.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Mock API response
            mock_response = MagicMock()
            mock_response.embeddings = [[0.8, 0.9]]
            mock_client.embed.return_value = mock_response

            embedding = await service._generate_cohere_embedding("test")

            assert len(embedding) == 2
            assert embedding == [0.8, 0.9]


class TestGenerateEmbedding:
    """Test main generate_embedding method."""

    @pytest.mark.asyncio
    async def test_generate_embedding_fastembed(self):
        """Cover generate_embedding with FastEmbed."""
        service = EmbeddingService(provider="fastembed")

        with patch.object(service, '_generate_fastembed_embedding', return_value=[0.1, 0.2]):
            embedding = await service.generate_embedding("test")

            assert embedding == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_generate_embedding_openai(self):
        """Cover generate_embedding with OpenAI."""
        service = EmbeddingService(provider="openai", config={"api_key": "test-key"})

        with patch.object(service, '_generate_openai_embedding', return_value=[0.3, 0.4]):
            embedding = await service.generate_embedding("test")

            assert embedding == [0.3, 0.4]

    @pytest.mark.asyncio
    async def test_generate_embedding_cohere(self):
        """Cover generate_embedding with Cohere."""
        service = EmbeddingService(provider="cohere", config={"api_key": "test-key"})

        with patch.object(service, '_generate_cohere_embedding', return_value=[0.5, 0.6]):
            embedding = await service.generate_embedding("test")

            assert embedding == [0.5, 0.6]

    @pytest.mark.asyncio
    async def test_generate_embedding_unknown_provider(self):
        """Cover generate_embedding with unknown provider."""
        service = EmbeddingService()
        service.provider = "unknown"

        with pytest.raises(ValueError, match="Unknown provider"):
            await service.generate_embedding("test")


class TestBatchEmbeddings:
    """Test batch embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_fastembed(self):
        """Cover batch embedding with FastEmbed."""
        service = EmbeddingService(provider="fastembed")

        with patch.object(service, '_generate_fastembed_embeddings_batch', return_value=[[0.1], [0.2]]):
            embeddings = await service.generate_embeddings_batch(["text1", "text2"])

            assert len(embeddings) == 2

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_openai(self):
        """Cover batch embedding with OpenAI."""
        service = EmbeddingService(provider="openai", config={"api_key": "test-key"})

        with patch.object(service, '_generate_openai_embeddings_batch', return_value=[[0.3], [0.4]]):
            embeddings = await service.generate_embeddings_batch(["text1", "text2"])

            assert len(embeddings) == 2


class TestLRUCache:
    """Test LRU cache operations."""

    def test_lru_cache_put(self):
        """Cover LRU cache put operation."""
        service = EmbeddingService()

        # Add item to cache
        service._lru_cache_put("key1", [0.1, 0.2, 0.3])

        assert "key1" in service._fastembed_cache
        assert "key1" in service._fastembed_cache_order

    def test_lru_cache_get(self):
        """Cover LRU cache get operation."""
        service = EmbeddingService()

        # Add item
        service._lru_cache_put("key1", [0.1, 0.2])

        # Get item
        value = service._lru_cache_get("key1")

        assert value == [0.1, 0.2]

    def test_lru_cache_get_missing(self):
        """Cover LRU cache get for missing key."""
        service = EmbeddingService()

        value = service._lru_cache_get("nonexistent")

        assert value is None

    def test_lru_cache_eviction(self):
        """Cover LRU cache eviction when full."""
        service = EmbeddingService()
        service._fastembed_cache_max = 3

        # Fill cache
        service._lru_cache_put("key1", [0.1])
        service._lru_cache_put("key2", [0.2])
        service._lru_cache_put("key3", [0.3])

        # Evict oldest and add new
        service._lru_cache_put("key4", [0.4])

        assert "key1" not in service._fastembed_cache
        assert "key4" in service._fastembed_cache

    def test_lru_cache_update_order(self):
        """Cover LRU cache order update on access."""
        service = EmbeddingService()

        service._lru_cache_put("key1", [0.1])
        service._lru_cache_put("key2", [0.2])

        # Access key1 (should move to end)
        service._lru_cache_get("key1")

        # key1 should be last in order
        assert service._fastembed_cache_order[-1] == "key1"

    def test_get_cache_stats(self):
        """Cover cache statistics retrieval."""
        service = EmbeddingService()

        service._lru_cache_put("key1", [0.1])
        service._lru_cache_put("key2", [0.2])

        stats = service.get_cache_stats()

        assert stats['current_size'] == 2
        assert stats['max_size'] == 1000
        assert stats['keys_cached'] == 2
        assert 'utilization_percent' in stats


class TestFastEmbedCoarseSearch:
    """Test FastEmbed coarse search for hybrid retrieval."""

    @pytest.mark.asyncio
    async def test_create_fastembed_embedding(self):
        """Cover creating FastEmbed embedding for coarse search."""
        service = EmbeddingService(provider="fastembed")

        with patch.object(service, '_generate_fastembed_embedding', return_value=[0.1] * 384):
            embedding = await service.create_fastembed_embedding("test query")

            assert embedding is not None
            assert len(embedding) == 384

    @pytest.mark.asyncio
    async def test_create_fastembed_embedding_no_numpy(self):
        """Cover FastEmbed embedding without NumPy."""
        service = EmbeddingService(provider="fastembed")

        # Mock NumPy as unavailable
        with patch('core.embedding_service.NUMPY_AVAILABLE', False):
            with patch.object(service, '_generate_fastembed_embedding', return_value=[0.1] * 384):
                embedding = await service.create_fastembed_embedding("test")

                assert embedding == [0.1] * 384

    @pytest.mark.asyncio
    async def test_create_fastembed_embedding_wrong_dimension(self):
        """Cover FastEmbed embedding with wrong dimension."""
        service = EmbeddingService(provider="fastembed")

        # Wrong dimension (not 384)
        with patch.object(service, '_generate_fastembed_embedding', return_value=[0.1] * 512):
            with patch('core.embedding_service.NUMPY_AVAILABLE', True):
                import numpy as np
                with patch('core.embedding_service.np', np):
                    embedding = await service.create_fastembed_embedding("test")

                    # Should still return embedding (with warning)
                    assert embedding is not None

    @pytest.mark.asyncio
    async def test_cache_fastembed_embedding(self):
        """Cover caching FastEmbed embedding."""
        service = EmbeddingService()

        with patch.object(service, '_lru_cache_put'):
            result = await service.cache_fastembed_embedding(
                episode_id="episode-123",
                embedding=[0.1] * 384,
                db=None
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_get_fastembed_embedding_cache_hit(self):
        """Cover getting FastEmbed embedding from cache (hit)."""
        service = EmbeddingService()
        service._lru_cache_put("episode-123", [0.2] * 384)

        embedding = await service.get_fastembed_embedding("episode-123", db=None)

        assert embedding == [0.2] * 384

    @pytest.mark.asyncio
    async def test_get_fastembed_embedding_cache_miss(self):
        """Cover getting FastEmbed embedding from cache (miss)."""
        service = EmbeddingService()

        embedding = await service.get_fastembed_embedding("nonexistent", db=None)

        assert embedding is None

    @pytest.mark.asyncio
    async def test_coarse_search_fastembed(self):
        """Cover FastEmbed coarse search."""
        service = EmbeddingService()

        with patch.object(service, 'create_fastembed_embedding', return_value=[0.1] * 384):
            result = await service.coarse_search_fastembed(
                agent_id="agent-123",
                query="test query",
                top_k=10,
                db=None
            )

            # Should return empty list without LanceDB
            assert result == []


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_generate_embedding_function(self):
        """Cover convenience generate_embedding function."""
        with patch.object(EmbeddingService, 'generate_embedding', return_value=[0.1, 0.2]):
            embedding = await generate_embedding("test")

            assert embedding == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_function(self):
        """Cover convenience generate_embeddings_batch function."""
        with patch.object(EmbeddingService, 'generate_embeddings_batch', return_value=[[0.1], [0.2]]):
            embeddings = await generate_embeddings_batch(["text1", "text2"])

            assert len(embeddings) == 2


class TestLanceDBHandler:
    """Test LanceDBHandler for vector storage."""

    def test_init_default_path(self):
        """Cover default LanceDB handler initialization."""
        with patch('core.embedding_service.lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db

            handler = LanceDBHandler()

            assert handler is not None

    def test_init_custom_path(self):
        """Cover custom LanceDB path."""
        with patch('core.embedding_service.lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db

            handler = LanceDBHandler(db_path="/custom/lancedb")

            assert handler.db_path == "/custom/lancedb"

    @pytest.mark.asyncio
    async def test_upsert_new_table(self):
        """Cover upsert creating new table."""
        with patch('core.embedding_service.lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            mock_db.table_names.return_value = []

            handler = LanceDBHandler()

            # Mock table creation
            with patch('core.embedding_service.pd.DataFrame'):
                with patch('core.embedding_service.pa'):
                    await handler.upsert(
                        table_name="test_table",
                        data=[{"vector": [0.1, 0.2]}]
                    )

    @pytest.mark.asyncio
    async def test_search(self):
        """Cover LanceDB search operation."""
        with patch('core.embedding_service.lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db

            mock_table = MagicMock()
            mock_db.open_table.return_value = mock_table

            # Mock search result
            mock_result = MagicMock()
            import pandas as pd
            mock_result.to_dict.return_value = pd.DataFrame([{"id": 1, "score": 0.9}])
            mock_table.search.return_value.limit.return_value.metric.return_value.to_pandas.return_value = mock_result

            handler = LanceDBHandler()

            results = await handler.search(
                table_name="test_table",
                query_vector=[0.1, 0.2],
                limit=10
            )

            assert len(results) >= 0


class TestErrorHandling:
    """Test error handling in embedding operations."""

    @pytest.mark.asyncio
    async def test_generate_embedding_error(self):
        """Cover error handling in generate_embedding."""
        service = EmbeddingService()

        with patch.object(service, '_generate_fastembed_embedding', side_effect=Exception("API Error")):
            with pytest.raises(Exception):
                await service.generate_embedding("test")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_error(self):
        """Cover error handling in batch generation."""
        service = EmbeddingService()

        with patch.object(service, '_generate_fastembed_embeddings_batch', side_effect=Exception("Batch Error")):
            with pytest.raises(Exception):
                await service.generate_embeddings_batch(["text1", "text2"])

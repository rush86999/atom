"""
Coverage-push tests for LLM infrastructure: embedding providers + LLM registry service.

TDD: bug tests written first (red), then minimal fixes in the source modules.
"""

import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from core.llm.embedding.base import (
    EmbeddingContextLimitError,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
)
from core.llm.embedding.providers import (
    CohereEmbeddingProvider,
    JinaEmbeddingProvider,
    NomicEmbeddingProvider,
    OpenAIEmbeddingProvider,
    VoyageEmbeddingProvider,
)
from core.llm.registry.models import LLMModel
from core.llm.registry.service import LLMRegistryService, get_registry_service


# ============================================================================
# Fixtures
# ============================================================================

def _openai_response(vectors):
    return SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in vectors])


@pytest.fixture
def openai_provider():
    mock_client = AsyncMock()
    with patch("core.llm.embedding.providers.AsyncOpenAI") as mock_openai:
        mock_openai.return_value = mock_client
        yield OpenAIEmbeddingProvider(api_key="test_key"), mock_client


@pytest.fixture
def mock_db():
    db = Mock()
    db.query = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.flush = Mock()
    db.refresh = Mock()
    db.delete = Mock()
    return db


@pytest.fixture
def registry_service(mock_db):
    with patch("core.llm.registry.service.RegistryCacheService"):
        with patch("core.llm.registry.service.ModelMetadataFetcher"):
            service = LLMRegistryService(mock_db, use_cache=False)
            return service


# ============================================================================
# PROVIDERS: OpenAI
# ============================================================================

class TestOpenAIEmbeddingProvider:
    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, openai_provider):
        provider, client = openai_provider
        client.embeddings.create = AsyncMock(return_value=_openai_response([[0.1, 0.2, 0.3]]))
        embedding = await provider.generate_embedding("hello world", "text-embedding-3-small")
        assert embedding == [0.1, 0.2, 0.3]
        client.embeddings.create.assert_called_once_with(
            input="hello world", model="text-embedding-3-small", encoding_format="float"
        )

    @pytest.mark.asyncio
    async def test_generate_embedding_rate_limit(self, openai_provider):
        provider, client = openai_provider
        client.embeddings.create = AsyncMock(
            side_effect=Exception("Rate limit reached for text-embedding-3-small")
        )
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embedding("hello", "text-embedding-3-small")

    @pytest.mark.asyncio
    async def test_generate_embedding_api_error(self, openai_provider):
        provider, client = openai_provider
        client.embeddings.create = AsyncMock(side_effect=Exception("connection reset"))
        with pytest.raises(EmbeddingProviderError):
            await provider.generate_embedding("hello", "text-embedding-3-small")

    @pytest.mark.asyncio
    async def test_generate_embedding_unknown_model(self, openai_provider):
        provider, _ = openai_provider
        with pytest.raises(ValueError):
            await provider.generate_embedding("hello", "not-a-model")

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text(self, openai_provider):
        provider, _ = openai_provider
        with pytest.raises(ValueError):
            await provider.generate_embedding("", "text-embedding-3-small")
        with pytest.raises(ValueError):
            await provider.generate_embedding("   ", "text-embedding-3-small")
        with pytest.raises(ValueError):
            await provider.generate_embedding(None, "text-embedding-3-small")  # type: ignore

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_success(self, openai_provider):
        provider, client = openai_provider
        client.embeddings.create = AsyncMock(
            return_value=_openai_response([[0.1], [0.2], [0.3]])
        )
        vectors = await provider.generate_embeddings_batch(["a", "b", "c"], "text-embedding-3-small")
        assert vectors == [[0.1], [0.2], [0.3]]
        client.embeddings.create.assert_called_once_with(
            input=["a", "b", "c"], model="text-embedding-3-small", encoding_format="float"
        )

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty(self, openai_provider):
        provider, client = openai_provider
        assert await provider.generate_embeddings_batch([], "text-embedding-3-small") == []
        client.embeddings.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_rate_limit(self, openai_provider):
        provider, client = openai_provider
        client.embeddings.create = AsyncMock(side_effect=Exception("429 rate limit"))
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embeddings_batch(["a"], "text-embedding-3-small")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_api_error(self, openai_provider):
        provider, client = openai_provider
        client.embeddings.create = AsyncMock(side_effect=Exception("boom"))
        with pytest.raises(EmbeddingProviderError):
            await provider.generate_embeddings_batch(["a"], "text-embedding-3-small")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_invalid_text(self, openai_provider):
        provider, _ = openai_provider
        with pytest.raises(ValueError):
            await provider.generate_embeddings_batch(["ok", ""], "text-embedding-3-small")

    def test_get_model_name(self, openai_provider):
        provider, _ = openai_provider
        assert provider.get_model_name("text-embedding-3-small") == "OpenAI text-embedding-3-small"
        assert provider.get_model_name("text-embedding-3-large") == "OpenAI text-embedding-3-large"
        assert provider.get_model_name("text-embedding-ada-002") == "OpenAI text-embedding-ada-002"
        assert provider.get_model_name("custom-model") == "custom-model"

    def test_estimate_cost(self, openai_provider):
        provider, _ = openai_provider
        # "hello" -> 1 token (5 chars // 4)
        assert provider.estimate_cost("hello", "text-embedding-3-small") == pytest.approx(1 / 1e6 * 0.02)
        assert provider.estimate_cost("hello", "text-embedding-3-large") == pytest.approx(1 / 1e6 * 0.13)
        assert provider.estimate_cost("hello", "text-embedding-ada-002") == pytest.approx(1 / 1e6 * 0.10)
        with pytest.raises(ValueError):
            provider.estimate_cost("hello", "nope")

    def test_get_context_limit(self, openai_provider):
        provider, _ = openai_provider
        assert provider.get_context_limit("text-embedding-3-small") == 8191
        with pytest.raises(ValueError):
            provider.get_context_limit("nope")

    def test_get_provider_name(self, openai_provider):
        provider, _ = openai_provider
        assert provider.get_provider_name() == "OpenAI"

    def test_init_without_package(self):
        with patch("core.llm.embedding.providers.AsyncOpenAI", None):
            with pytest.raises(EmbeddingProviderError):
                OpenAIEmbeddingProvider(api_key="k")


# ============================================================================
# PROVIDERS: Cohere
# ============================================================================

class TestCohereEmbeddingProvider:
    def _make(self, response):
        mock_cohere = MagicMock()
        client = AsyncMock()
        client.embed = AsyncMock(return_value=response)
        mock_cohere.AsyncClient.return_value = client
        return mock_cohere, client

    def test_init(self):
        mock_cohere, _ = self._make(SimpleNamespace(embeddings=[[0.1]]))
        with patch("core.llm.embedding.providers.cohere", mock_cohere):
            provider = CohereEmbeddingProvider(api_key="k")
        assert provider.get_provider_name() == "Cohere"
        assert provider.get_model_name("embed-english-v3.0") == "Cohere embed-english-v3.0"
        assert provider.get_model_name("unknown") == "unknown"

    def test_init_without_package(self):
        with patch("core.llm.embedding.providers.cohere", None):
            with pytest.raises(EmbeddingProviderError):
                CohereEmbeddingProvider(api_key="k")

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self):
        mock_cohere, client = self._make(SimpleNamespace(embeddings=[[0.1, 0.2]]))
        with patch("core.llm.embedding.providers.cohere", mock_cohere):
            provider = CohereEmbeddingProvider(api_key="k")
        vector = await provider.generate_embedding("hello", "embed-english-v3.0")
        assert vector == [0.1, 0.2]
        client.embed.assert_called_once_with(
            texts=["hello"], model="embed-english-v3.0", input_type="search_document"
        )

    @pytest.mark.asyncio
    async def test_generate_embedding_rate_limit(self):
        mock_cohere, client = self._make(None)
        client.embed = AsyncMock(side_effect=Exception("429 rate limit"))
        with patch("core.llm.embedding.providers.cohere", mock_cohere):
            provider = CohereEmbeddingProvider(api_key="k")
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embedding("hello", "embed-english-v3.0")

    @pytest.mark.asyncio
    async def test_generate_embedding_api_error(self):
        mock_cohere, client = self._make(None)
        client.embed = AsyncMock(side_effect=Exception("server error"))
        with patch("core.llm.embedding.providers.cohere", mock_cohere):
            provider = CohereEmbeddingProvider(api_key="k")
        with pytest.raises(EmbeddingProviderError):
            await provider.generate_embedding("hello", "embed-english-v3.0")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self):
        mock_cohere, client = self._make(SimpleNamespace(embeddings=[[0.1], [0.2]]))
        with patch("core.llm.embedding.providers.cohere", mock_cohere):
            provider = CohereEmbeddingProvider(api_key="k")
        vectors = await provider.generate_embeddings_batch(["a", "b"], "embed-english-v3.0")
        assert vectors == [[0.1], [0.2]]

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty(self):
        mock_cohere, client = self._make(None)
        with patch("core.llm.embedding.providers.cohere", mock_cohere):
            provider = CohereEmbeddingProvider(api_key="k")
        assert await provider.generate_embeddings_batch([], "embed-english-v3.0") == []
        client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_error(self):
        mock_cohere, client = self._make(None)
        client.embed = AsyncMock(side_effect=Exception("Rate limit"))
        with patch("core.llm.embedding.providers.cohere", mock_cohere):
            provider = CohereEmbeddingProvider(api_key="k")
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embeddings_batch(["a"], "embed-english-v3.0")

    def test_estimate_cost_and_context(self):
        mock_cohere, _ = self._make(SimpleNamespace(embeddings=[[0.1]]))
        with patch("core.llm.embedding.providers.cohere", mock_cohere):
            provider = CohereEmbeddingProvider(api_key="k")
        assert provider.estimate_cost("hello", "embed-english-v3.0") == pytest.approx(1 / 1e6 * 0.10)
        assert provider.estimate_cost("hello", "embed-multilingual-v3.0") == pytest.approx(1 / 1e6 * 0.15)
        assert provider.estimate_cost("hello", "embed-english-light-v3.0") == pytest.approx(1 / 1e6 * 0.05)
        assert provider.get_context_limit("embed-english-v3.0") == 512
        with pytest.raises(ValueError):
            provider.estimate_cost("hello", "nope")
        with pytest.raises(ValueError):
            provider.get_context_limit("nope")


# ============================================================================
# PROVIDERS: Voyage
# ============================================================================

class TestVoyageEmbeddingProvider:
    def _make(self, embed_return):
        mock_voyage = MagicMock()
        client = Mock()
        client.embed = Mock(return_value=embed_return)
        mock_voyage.Client.return_value = client
        return mock_voyage, client

    def test_init(self):
        mock_voyage, _ = self._make(SimpleNamespace(embeddings=[[0.1]]))
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            provider = VoyageEmbeddingProvider(api_key="k")
        assert provider.get_provider_name() == "Voyage"
        assert provider.get_model_name("voyage-2") == "Voyage voyage-2"
        assert provider.get_model_name("nope") == "nope"

    def test_init_without_package(self):
        with patch("core.llm.embedding.providers.voyageai", None):
            with pytest.raises(EmbeddingProviderError):
                VoyageEmbeddingProvider(api_key="k")

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self):
        # VoyageAI SDK returns an EmbeddingsResult object with .embeddings (not a list)
        mock_voyage, client = self._make(SimpleNamespace(embeddings=[[0.1, 0.2, 0.3]]))
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            provider = VoyageEmbeddingProvider(api_key="k")
        vector = await provider.generate_embedding("hello", "voyage-2")
        assert vector == [0.1, 0.2, 0.3]
        client.embed.assert_called_once_with("hello", model="voyage-2", input_type="document")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_success(self):
        mock_voyage, client = self._make(SimpleNamespace(embeddings=[[0.1], [0.2]]))
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            provider = VoyageEmbeddingProvider(api_key="k")
        vectors = await provider.generate_embeddings_batch(["a", "b"], "voyage-2")
        assert vectors == [[0.1], [0.2]]
        client.embed.assert_called_once_with(["a", "b"], model="voyage-2", input_type="document")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty(self):
        mock_voyage, client = self._make(None)
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            provider = VoyageEmbeddingProvider(api_key="k")
        assert await provider.generate_embeddings_batch([], "voyage-2") == []
        client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_embedding_rate_limit(self):
        mock_voyage, client = self._make(None)
        client.embed = Mock(side_effect=Exception("429 rate limit"))
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            provider = VoyageEmbeddingProvider(api_key="k")
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embedding("hello", "voyage-2")

    @pytest.mark.asyncio
    async def test_generate_embedding_api_error(self):
        mock_voyage, client = self._make(None)
        client.embed = Mock(side_effect=Exception("connection failed"))
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            provider = VoyageEmbeddingProvider(api_key="k")
        with pytest.raises(EmbeddingProviderError):
            await provider.generate_embedding("hello", "voyage-2")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_rate_limit(self):
        mock_voyage, client = self._make(None)
        client.embed = Mock(side_effect=Exception("rate"))
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            provider = VoyageEmbeddingProvider(api_key="k")
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embeddings_batch(["a"], "voyage-2")

    @pytest.mark.asyncio
    async def test_generate_embedding_unknown_model(self):
        mock_voyage, _ = self._make(None)
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            provider = VoyageEmbeddingProvider(api_key="k")
        with pytest.raises(ValueError):
            await provider.generate_embedding("hello", "nope")

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text(self):
        mock_voyage, _ = self._make(None)
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            provider = VoyageEmbeddingProvider(api_key="k")
        with pytest.raises(ValueError):
            await provider.generate_embedding("", "voyage-2")

    def test_estimate_cost_and_context(self):
        mock_voyage, _ = self._make(None)
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            provider = VoyageEmbeddingProvider(api_key="k")
        assert provider.estimate_cost("hello", "voyage-2") == pytest.approx(1 / 1e6 * 0.10)
        assert provider.estimate_cost("hello", "voyage-large-2") == pytest.approx(1 / 1e6 * 0.25)
        assert provider.estimate_cost("hello", "voyage-code-2") == pytest.approx(1 / 1e6 * 0.15)
        assert provider.get_context_limit("voyage-2") == 128
        with pytest.raises(ValueError):
            provider.estimate_cost("hello", "nope")
        with pytest.raises(ValueError):
            provider.get_context_limit("nope")


# ============================================================================
# PROVIDERS: Nomic
# ============================================================================

class TestNomicEmbeddingProvider:
    def _make(self, embed_return):
        mock_nomic = MagicMock()
        embedder = Mock()
        embedder.embed = Mock(return_value=embed_return)
        mock_nomic.Embedding.return_value = embedder
        return mock_nomic, embedder

    def test_init(self):
        mock_nomic, _ = self._make({"embeddings": [[0.1]]})
        with patch("core.llm.embedding.providers.nomic", mock_nomic):
            provider = NomicEmbeddingProvider(api_key="k")
        assert provider.get_provider_name() == "Nomic"
        assert provider.get_model_name("nomic-embed-text-v1.5") == "Nomic nomic-embed-text-v1.5"
        assert provider.get_model_name("nope") == "nope"

    def test_init_without_package(self):
        with patch("core.llm.embedding.providers.nomic", None):
            with pytest.raises(EmbeddingProviderError):
                NomicEmbeddingProvider(api_key="k")

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self):
        mock_nomic, embedder = self._make({"embeddings": [[0.1, 0.2]]})
        with patch("core.llm.embedding.providers.nomic", mock_nomic):
            provider = NomicEmbeddingProvider(api_key="k")
        vector = await provider.generate_embedding("hello", "nomic-embed-text-v1.5")
        assert vector == [0.1, 0.2]
        embedder.embed.assert_called_once_with(
            texts=["hello"], model="nomic-embed-text-v1.5", task_type="search_document"
        )

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_success(self):
        mock_nomic, embedder = self._make({"embeddings": [[0.1], [0.2]]})
        with patch("core.llm.embedding.providers.nomic", mock_nomic):
            provider = NomicEmbeddingProvider(api_key="k")
        vectors = await provider.generate_embeddings_batch(["a", "b"], "nomic-embed-text-v1.5")
        assert vectors == [[0.1], [0.2]]

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty(self):
        mock_nomic, embedder = self._make(None)
        with patch("core.llm.embedding.providers.nomic", mock_nomic):
            provider = NomicEmbeddingProvider(api_key="k")
        assert await provider.generate_embeddings_batch([], "nomic-embed-text-v1.5") == []
        embedder.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_embedding_rate_limit(self):
        mock_nomic, embedder = self._make(None)
        embedder.embed = Mock(side_effect=Exception("rate limit"))
        with patch("core.llm.embedding.providers.nomic", mock_nomic):
            provider = NomicEmbeddingProvider(api_key="k")
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embedding("hello", "nomic-embed-text-v1.5")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_api_error(self):
        mock_nomic, embedder = self._make(None)
        embedder.embed = Mock(side_effect=Exception("failure"))
        with patch("core.llm.embedding.providers.nomic", mock_nomic):
            provider = NomicEmbeddingProvider(api_key="k")
        with pytest.raises(EmbeddingProviderError):
            await provider.generate_embeddings_batch(["a"], "nomic-embed-text-v1.5")

    @pytest.mark.asyncio
    async def test_generate_embedding_unknown_model(self):
        mock_nomic, _ = self._make(None)
        with patch("core.llm.embedding.providers.nomic", mock_nomic):
            provider = NomicEmbeddingProvider(api_key="k")
        with pytest.raises(ValueError):
            await provider.generate_embedding("hello", "nope")

    def test_estimate_cost_and_context(self):
        mock_nomic, _ = self._make(None)
        with patch("core.llm.embedding.providers.nomic", mock_nomic):
            provider = NomicEmbeddingProvider(api_key="k")
        assert provider.estimate_cost("hello", "nomic-embed-text-v1.5") == pytest.approx(1 / 1e6 * 0.08)
        assert provider.estimate_cost("hello", "nomic-embed-text-v1") == pytest.approx(1 / 1e6 * 0.10)
        assert provider.get_context_limit("nomic-embed-text-v1.5") == 8192
        with pytest.raises(ValueError):
            provider.estimate_cost("hello", "nope")
        with pytest.raises(ValueError):
            provider.get_context_limit("nope")


# ============================================================================
# PROVIDERS: Jina
# ============================================================================

class TestJinaEmbeddingProvider:
    @pytest.mark.asyncio
    async def test_generate_embedding_success(self):
        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=_openai_response([[0.5, 0.6]]))
        with patch("core.llm.embedding.providers.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client
            provider = JinaEmbeddingProvider(api_key="k")
            mock_openai.assert_called_once_with(api_key="k", base_url="https://api.jina.ai/v1")
        vector = await provider.generate_embedding("hello", "jina-embeddings-v2")
        assert vector == [0.5, 0.6]
        mock_client.embeddings.create.assert_called_once_with(input="hello", model="jina-embeddings-v2")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_success(self):
        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=_openai_response([[0.1], [0.2]]))
        with patch("core.llm.embedding.providers.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client
            provider = JinaEmbeddingProvider(api_key="k")
        vectors = await provider.generate_embeddings_batch(["a", "b"], "jina-embeddings-v3")
        assert vectors == [[0.1], [0.2]]

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty(self):
        mock_client = AsyncMock()
        with patch("core.llm.embedding.providers.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client
            provider = JinaEmbeddingProvider(api_key="k")
        assert await provider.generate_embeddings_batch([], "jina-embeddings-v2") == []
        mock_client.embeddings.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_embedding_rate_limit(self):
        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(side_effect=Exception("rate limit exceeded"))
        with patch("core.llm.embedding.providers.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client
            provider = JinaEmbeddingProvider(api_key="k")
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embedding("hello", "jina-embeddings-v2")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_api_error(self):
        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(side_effect=Exception("boom"))
        with patch("core.llm.embedding.providers.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client
            provider = JinaEmbeddingProvider(api_key="k")
        with pytest.raises(EmbeddingProviderError):
            await provider.generate_embeddings_batch(["a"], "jina-embeddings-v2")

    @pytest.mark.asyncio
    async def test_generate_embedding_unknown_model(self):
        with patch("core.llm.embedding.providers.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = AsyncMock()
            provider = JinaEmbeddingProvider(api_key="k")
        with pytest.raises(ValueError):
            await provider.generate_embedding("hello", "nope")

    def test_init_without_package(self):
        with patch("core.llm.embedding.providers.AsyncOpenAI", None):
            with pytest.raises(EmbeddingProviderError):
                JinaEmbeddingProvider(api_key="k")

    def test_estimate_cost_and_context(self):
        with patch("core.llm.embedding.providers.AsyncOpenAI"):
            provider = JinaEmbeddingProvider(api_key="k")
        assert provider.get_provider_name() == "Jina"
        assert provider.get_model_name("jina-embeddings-v2") == "Jina jina-embeddings-v2"
        assert provider.get_model_name("jina-embeddings-v3") == "Jina jina-embeddings-v3"
        assert provider.get_model_name("nope") == "nope"
        assert provider.estimate_cost("hello", "jina-embeddings-v2") == pytest.approx(1 / 1e6 * 0.02)
        assert provider.estimate_cost("hello", "jina-embeddings-v3") == pytest.approx(1 / 1e6 * 0.03)
        assert provider.get_context_limit("jina-embeddings-v3") == 8191
        with pytest.raises(ValueError):
            provider.estimate_cost("hello", "nope")
        with pytest.raises(ValueError):
            provider.get_context_limit("nope")


# ============================================================================
# REGISTRY SERVICE: fetch_and_store
# ============================================================================

class TestFetchAndStore:
    def _service_with_cache(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService") as mock_cache_cls:
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = LLMRegistryService(mock_db, use_cache=True)
                return service, mock_cache_cls.return_value

    @pytest.mark.asyncio
    async def test_fetch_and_store_full_flow(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        service.fetcher.fetch_all = AsyncMock(return_value={
            "litellm": {"gpt-4": {"name": "gpt-4"}},
            "openrouter": {"or-1": {"name": "or-1"}},
        })
        with patch("core.llm.registry.service.transform_litellm_model", side_effect=[
            {"provider": "openai", "model_name": "gpt-4"},
        ]) as tl:
            with patch("core.llm.registry.service.transform_openrouter_model", side_effect=[
                {"provider": "openrouter", "model_name": "or-1"},
            ]) as to:
                with patch("core.llm.registry.service.merge_duplicate_models", side_effect=[
                    [
                        {"provider": "openai", "model_name": "gpt-4"},
                        {"provider": "openrouter", "model_name": "or-1"},
                    ]
                ]):
                    now = datetime.now(timezone.utc)
                    created = Mock(spec=LLMModel, provider="openai", model_name="gpt-4",
                                   created_at=now, updated_at=now,
                                   context_window=8192, input_price_per_token=0.00003,
                                   output_price_per_token=0.00006, capabilities=["tools"],
                                   provider_metadata={})
                    updated = Mock(spec=LLMModel, provider="openrouter", model_name="or-1",
                                   created_at=now, updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                                   context_window=8192, input_price_per_token=0.00003,
                                   output_price_per_token=0.00006, capabilities=["tools"],
                                   provider_metadata={})
                    with patch.object(service, "upsert_model", side_effect=[created, updated]):
                        cache.warm_cache = AsyncMock()
                        mock_query = Mock()
                        mock_query.filter.return_value.filter.return_value.all.return_value = []
                        mock_db.query.return_value = mock_query

                        assert (await service.list_models("tenant-1", use_cache=False)) == []

                        stats = await service.fetch_and_store("tenant-1")

        assert stats == {"created": 1, "updated": 1, "failed": 0, "total": 2}
        tl.assert_called_once_with({"name": "gpt-4"}, "gpt-4")
        to.assert_called_once_with({"name": "or-1"})
        cache.warm_cache.assert_awaited_once()
        assert cache.warm_cache.call_args[0][0] == "tenant-1"

    @pytest.mark.asyncio
    async def test_fetch_and_store_upsert_failure(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        service.fetcher.fetch_all = AsyncMock(return_value={
            "litellm": {"gpt-4": {}},
            "openrouter": {},
        })
        with patch("core.llm.registry.service.transform_litellm_model", side_effect=[
            {"provider": "openai", "model_name": "gpt-4"},
        ]):
            with patch("core.llm.registry.service.transform_openrouter_model", side_effect=[None]):
                with patch("core.llm.registry.service.merge_duplicate_models", side_effect=[
                    [{"provider": "openai", "model_name": "gpt-4"}]
                ]):
                    with patch.object(service, "upsert_model", side_effect=Exception("db down")):
                        stats = await service.fetch_and_store("tenant-1")

        assert stats == {"created": 0, "updated": 0, "failed": 1, "total": 1}

    @pytest.mark.asyncio
    async def test_fetch_and_store_cache_warm_failure(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        service.fetcher.fetch_all = AsyncMock(return_value={"litellm": {}, "openrouter": {}})
        with patch("core.llm.registry.service.transform_litellm_model", side_effect=[]):
            with patch("core.llm.registry.service.transform_openrouter_model", side_effect=[]):
                with patch("core.llm.registry.service.merge_duplicate_models", side_effect=[[]]):
                    cache.warm_cache = AsyncMock(side_effect=Exception("redis down"))
                    mock_query = Mock()
                    mock_query.filter.return_value.filter.return_value.all.return_value = []
                    mock_db.query.return_value = mock_query

                    stats = await service.fetch_and_store("tenant-1")

        assert stats == {"created": 0, "updated": 0, "failed": 0, "total": 0}

    @pytest.mark.asyncio
    async def test_fetch_and_store_no_cache(self, mock_db, registry_service):
        registry_service.fetcher.fetch_all = AsyncMock(return_value={"litellm": {}, "openrouter": {}})
        with patch("core.llm.registry.service.transform_litellm_model", side_effect=[]):
            with patch("core.llm.registry.service.transform_openrouter_model", side_effect=[]):
                with patch("core.llm.registry.service.merge_duplicate_models", side_effect=[[]]):
                    stats = await registry_service.fetch_and_store("tenant-1")

        assert stats == {"created": 0, "updated": 0, "failed": 0, "total": 0}


# ============================================================================
# REGISTRY SERVICE: get_model / list_models cache paths
# ============================================================================

class TestRegistryCachePaths:
    def _service_with_cache(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService") as mock_cache_cls:
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = LLMRegistryService(mock_db, use_cache=True)
                return service, mock_cache_cls.return_value

    @pytest.mark.asyncio
    async def test_get_model_cache_hit(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        cache.get_model = AsyncMock(return_value={
            "provider": "openai", "model_name": "gpt-4", "context_window": 8192,
            "input_price_per_token": 0.00003, "output_price_per_token": 0.00006,
            "capabilities": ["tools"], "provider_metadata": {"source": "litellm"},
        })
        model = await service.get_model("tenant-1", "openai", "gpt-4")
        assert model is not None
        assert model.model_name == "gpt-4"
        assert model.capabilities == ["tools"]
        mock_db.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_model_cache_error_falls_back_to_db(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        cache.get_model = AsyncMock(side_effect=Exception("cache down"))
        db_model = Mock(spec=LLMModel, provider="openai", model_name="gpt-4",
                        context_window=8192, input_price_per_token=None,
                        output_price_per_token=None, capabilities=[], provider_metadata={})
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = db_model
        mock_db.query.return_value = mock_query
        cache.set_model = AsyncMock()
        model = await service.get_model("tenant-1", "openai", "gpt-4")
        assert model is db_model
        cache.set_model.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_model_cache_set_failure(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        cache.get_model = AsyncMock(return_value=None)
        db_model = Mock(spec=LLMModel, provider="openai", model_name="gpt-4",
                        context_window=8192, input_price_per_token=None,
                        output_price_per_token=None, capabilities=[], provider_metadata={})
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = db_model
        mock_db.query.return_value = mock_query
        cache.set_model = AsyncMock(side_effect=Exception("write failed"))
        model = await service.get_model("tenant-1", "openai", "gpt-4")
        assert model is db_model

    @pytest.mark.asyncio
    async def test_get_model_include_deprecated_bypasses_cache(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        db_model = Mock(spec=LLMModel, is_deprecated=True)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = db_model
        mock_db.query.return_value = mock_query
        model = await service.get_model("tenant-1", "openai", "gpt-4", include_deprecated=True)
        assert model is db_model
        cache.get_model.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_models_cache_hit(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        cache.get_models_list = AsyncMock(return_value=[
            {"provider": "openai", "model_name": "gpt-4", "context_window": 8192,
             "input_price_per_token": None, "output_price_per_token": None,
             "capabilities": [], "provider_metadata": {}},
        ])
        models = await service.list_models("tenant-1", provider="openai")
        assert len(models) == 1
        assert models[0].provider == "openai"
        mock_db.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_models_cache_error_falls_back(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        cache.get_models_list = AsyncMock(side_effect=Exception("cache down"))
        db_models = [Mock(spec=LLMModel, provider="openai", model_name="gpt-4",
                          context_window=8192, input_price_per_token=None,
                          output_price_per_token=None, capabilities=[], provider_metadata={})]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = db_models
        mock_db.query.return_value = mock_query
        cache.set_models_list = AsyncMock()
        models = await service.list_models("tenant-1", provider="openai")
        assert models == db_models
        cache.set_models_list.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_models_no_warm_when_empty(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        cache.get_models_list = AsyncMock(return_value=None)
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query
        cache.set_models_list = AsyncMock()
        models = await service.list_models("tenant-1")
        assert models == []
        cache.set_models_list.assert_not_called()


# ============================================================================
# REGISTRY SERVICE: LUX / computer-use / lifecycle
# ============================================================================

class TestLuxAndLifecycle:
    @pytest.mark.asyncio
    async def test_register_lux_model_success(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService"):
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = LLMRegistryService(mock_db, use_cache=False)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        model = service.register_lux_model("tenant-1")
        assert model is not None
        assert model.provider == "anthropic"
        assert model.model_name == "claude-3-5-sonnet-20241022"
        assert "computer_use" in model.capabilities
        assert model.supports_computer_use is True
        assert model.context_window == 200000
        mock_db.flush.assert_called()

    def test_register_lux_model_disabled(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService"):
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = LLMRegistryService(mock_db, use_cache=False)
        assert service.register_lux_model("tenant-1", enabled=False) is None

    def test_register_lux_model_failure(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService"):
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = LLMRegistryService(mock_db, use_cache=False)
        mock_db.flush.side_effect = Exception("db error")
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        assert service.register_lux_model("tenant-1") is None

    def test_get_computer_use_models(self, mock_db, registry_service):
        models = [Mock(spec=LLMModel, model_name="lux")]
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = models
        mock_db.query.return_value = mock_query
        assert registry_service.get_computer_use_models("tenant-1") == models

    @pytest.mark.asyncio
    async def test_mark_model_deprecated_not_found(self, mock_db, registry_service):
        async def no_model(*args, **kwargs):
            return None
        with patch.object(registry_service, "get_model", no_model):
            assert await registry_service.mark_model_deprecated("t", "p", "m") is None

    def test_restore_deprecated_model_not_found(self, mock_db, registry_service):
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        assert registry_service.restore_deprecated_model("t", "p", "m") is None

    @pytest.mark.asyncio
    async def test_close_and_context_manager(self, mock_db):
        with patch("core.llm.registry.service.ModelMetadataFetcher") as fetcher_cls:
            with patch("core.llm.registry.service.RegistryCacheService"):
                service = LLMRegistryService(mock_db, use_cache=False)
        fetcher_cls.return_value.close = AsyncMock()
        await service.close()
        fetcher_cls.return_value.close.assert_awaited_once()
        async with service as ctx:
            assert ctx is service
        assert fetcher_cls.return_value.close.await_count == 2

    def test_get_registry_service_factory(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService"):
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = get_registry_service(mock_db)
        assert isinstance(service, LLMRegistryService)
        assert service.db is mock_db


# ============================================================================
# REGISTRY SERVICE: invalidate / refresh cache
# ============================================================================

class TestCacheOps:
    def _service_with_cache(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService") as mock_cache_cls:
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = LLMRegistryService(mock_db, use_cache=True)
                return service, mock_cache_cls.return_value

    @pytest.mark.asyncio
    async def test_invalidate_cache_success(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        cache.invalidate_tenant = AsyncMock(return_value=5)
        assert await service.invalidate_cache("tenant-1") == 5

    @pytest.mark.asyncio
    async def test_invalidate_cache_disabled(self, mock_db, registry_service):
        assert await registry_service.invalidate_cache("tenant-1") == 0

    @pytest.mark.asyncio
    async def test_invalidate_cache_error(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        cache.invalidate_tenant = AsyncMock(side_effect=Exception("redis down"))
        assert await service.invalidate_cache("tenant-1") == 0

    @pytest.mark.asyncio
    async def test_refresh_cache_success(self, mock_db):
        service, cache = self._service_with_cache(mock_db)
        models = [Mock(spec=LLMModel, provider="openai", model_name="gpt-4",
                       context_window=8192, input_price_per_token=None,
                       output_price_per_token=None, capabilities=[], provider_metadata={})]
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.all.return_value = models
        mock_db.query.return_value = mock_query
        cache.atomic_swap_registry = AsyncMock(return_value=True)
        stats = await service.refresh_cache("tenant-1")
        assert stats == {"swapped": 1, "failed": 0}
        cache.atomic_swap_registry.assert_awaited_once()


# ============================================================================
# REGISTRY SERVICE: new / deprecated model detection
# ============================================================================

class TestModelDetection:
    @pytest.mark.asyncio
    async def test_detect_and_add_new_models(self, mock_db, registry_service):
        existing = [
            Mock(spec=LLMModel, provider="openai", model_name="gpt-4"),
        ]
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = existing
        mock_db.query.return_value = mock_query

        fetched = [
            {"provider": "openai", "model_name": "gpt-4"},
            {"provider": "anthropic", "model_name": "claude-3"},
            {"provider": "openai", "model_name": "gpt-4o"},
        ]
        with patch.object(registry_service, "upsert_model", side_effect=[
            Mock(spec=LLMModel, provider="anthropic", model_name="claude-3"),
            Mock(spec=LLMModel, provider="openai", model_name="gpt-4o"),
        ]) as upsert:
            result = await registry_service.detect_and_add_new_models("tenant-1", fetched)

        assert upsert.call_count == 2
        assert result["new_models"] == 2
        assert result["existing_models"] == 1
        assert result["added"] == ["anthropic/claude-3", "openai/gpt-4o"]
        assert result["skipped"] == [("openai", "gpt-4")]

    @pytest.mark.asyncio
    async def test_detect_and_add_new_models_upsert_failure(self, mock_db, registry_service):
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        fetched = [{"provider": "openai", "model_name": "gpt-5"}]
        with patch.object(registry_service, "upsert_model", side_effect=Exception("db error")):
            result = await registry_service.detect_and_add_new_models("tenant-1", fetched)

        assert result["new_models"] == 1
        assert result["added"] == []

    def test_get_new_models_since(self, mock_db, registry_service):
        models = [Mock(spec=LLMModel, model_name="gpt-4o")]
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = models
        mock_db.query.return_value = mock_query
        result = registry_service.get_new_models_since("tenant-1", datetime.now(timezone.utc))
        assert result == models
        mock_query.filter.return_value.order_by.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_deprecated_models_with_cache(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService") as mock_cache_cls:
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = LLMRegistryService(mock_db, use_cache=True)
        cache = mock_cache_cls.return_value
        cache.delete_model = AsyncMock()

        existing = [
            Mock(spec=LLMModel, provider="openai", model_name="gpt-4"),
            Mock(spec=LLMModel, provider="anthropic", model_name="claude-3"),
        ]
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = existing
        mock_db.query.return_value = mock_query

        fetched = [{"provider": "openai", "model_name": "gpt-4"}]
        with patch.object(service, "mark_model_deprecated") as mark:
            result = await service.detect_deprecated_models("tenant-1", fetched)

        mark.assert_called_once_with("tenant-1", "anthropic", "claude-3", reason="removed_from_api")
        cache.delete_model.assert_awaited_once()
        assert result["deprecated"] == 1
        assert result["still_active"] == 1
        assert result["deprecated_models"] == ["anthropic/claude-3"]
        assert result["reason"] == "removed_from_api"

    @pytest.mark.asyncio
    async def test_detect_deprecated_models_no_cache(self, mock_db, registry_service):
        existing = [Mock(spec=LLMModel, provider="openai", model_name="gpt-4")]
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = existing
        mock_db.query.return_value = mock_query

        fetched = [{"provider": "openai", "model_name": "gpt-4"}]
        with patch.object(registry_service, "mark_model_deprecated") as mark:
            result = await registry_service.detect_deprecated_models("tenant-1", fetched)

        mark.assert_not_called()
        assert result["deprecated"] == 0
        assert result["still_active"] == 1


# ============================================================================
# REGISTRY SERVICE: quality scores
# ============================================================================

class TestQualityScores:
    @pytest.mark.asyncio
    async def test_update_quality_scores_from_lmsys(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService") as mock_cache_cls:
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = LLMRegistryService(mock_db, use_cache=True)
        cache = mock_cache_cls.return_value
        cache.invalidate_tenant = AsyncMock(return_value=3)

        gpt4 = Mock(spec=LLMModel, model_name="gpt-4", quality_score=None)
        claude = Mock(spec=LLMModel, model_name="claude-3", quality_score=None)
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.all.return_value = [gpt4, claude]
        mock_db.query.return_value = mock_query

        mock_client = MagicMock()
        mock_client.fetch_leaderboard = AsyncMock(return_value={"gpt-4o": 1200.0, "some-model": 900.0})
        mock_client.map_scores_to_registry = AsyncMock(return_value={"gpt-4": 1200.0})
        mock_client.elo_to_quality_score = Mock(return_value=66.7)
        mock_client.close = AsyncMock()

        with patch("core.llm.registry.service.LMSYSClient", return_value=mock_client):
            result = await service.update_quality_scores_from_lmsys("tenant-1")

        assert gpt4.quality_score == 66.7
        assert claude.quality_score is None
        mock_db.commit.assert_called()
        cache.invalidate_tenant.assert_awaited_once()
        mock_client.close.assert_awaited_once()
        assert result["updated"] == 1
        assert result["not_found"] == 1
        assert result["skipped"] == 1
        assert result["scores"] == {"gpt-4": 66.7}

    def test_assign_heuristic_quality_scores(self, mock_db, registry_service):
        gpt4 = Mock(spec=LLMModel, model_name="gpt-4", quality_score=None,
                    context_window=8192, provider="openai")
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [gpt4]
        mock_query.count.return_value = 7
        mock_db.query.return_value = mock_query

        mock_scorer = Mock()
        mock_scorer.calculate_score.return_value = 88.5

        with patch("core.llm.registry.service.HeuristicScorer", return_value=mock_scorer):
            result = registry_service.assign_heuristic_quality_scores("tenant-1")

        assert gpt4.quality_score == 88.5
        assert result == {"assigned": 1, "skipped": 7, "scores": {"gpt-4": 88.5}}
        mock_db.commit.assert_called()
        mock_scorer.calculate_score.assert_called_once_with(
            model_name="gpt-4", context_window=8192, provider="openai"
        )

    def test_assign_heuristic_quality_scores_overwrite(self, mock_db, registry_service):
        model = Mock(spec=LLMModel, model_name="gpt-4", quality_score=90.0,
                     context_window=8192, provider="openai")
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [model]
        mock_db.query.return_value = mock_query

        mock_scorer = Mock()
        mock_scorer.calculate_score.return_value = 91.0

        with patch("core.llm.registry.service.HeuristicScorer", return_value=mock_scorer):
            result = registry_service.assign_heuristic_quality_scores("tenant-1", overwrite_existing=True)

        assert result == {"assigned": 1, "skipped": 0, "scores": {"gpt-4": 91.0}}

    @pytest.mark.asyncio
    async def test_get_top_models_by_quality(self, mock_db, registry_service):
        models = [Mock(spec=LLMModel, model_name="gpt-4", quality_score=95.0)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = models
        mock_db.query.return_value = mock_query

        result = await registry_service.get_top_models_by_quality("tenant-1", limit=5, min_quality=80.0)
        assert result == models


# ============================================================================
# BUG: upsert_model does not sync hybrid capability flag columns
# ============================================================================

class TestCapabilitySyncBug:
    def test_upsert_new_model_syncs_hybrid_capabilities(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService"):
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = LLMRegistryService(mock_db, use_cache=False)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        model = service.upsert_model("tenant-1", {
            "provider": "anthropic",
            "model_name": "claude-3-computer",
            "capabilities": ["vision", "tools", "computer_use"],
        })

        assert model.supports_vision is True
        assert model.supports_tools is True
        assert model.supports_computer_use is True
        assert model.supports_function_calling is False

    def test_upsert_existing_model_syncs_hybrid_capabilities(self, mock_db):
        with patch("core.llm.registry.service.RegistryCacheService"):
            with patch("core.llm.registry.service.ModelMetadataFetcher"):
                service = LLMRegistryService(mock_db, use_cache=False)
        existing = LLMModel(
            tenant_id="tenant-1", provider="anthropic", model_name="claude-3-computer",
            capabilities=["vision"],
        )
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = existing
        mock_db.query.return_value = mock_query

        model = service.upsert_model("tenant-1", {
            "provider": "anthropic",
            "model_name": "claude-3-computer",
            "capabilities": ["computer_use", "audio"],
        })

        assert model.supports_computer_use is True
        assert model.supports_audio is True
        assert model.supports_vision is False

    def test_upsert_model_missing_fields_raises(self, mock_db, registry_service):
        with pytest.raises(ValueError):
            registry_service.upsert_model("tenant-1", {"provider": "openai"})
        with pytest.raises(ValueError):
            registry_service.upsert_model("tenant-1", {"model_name": "gpt-4"})

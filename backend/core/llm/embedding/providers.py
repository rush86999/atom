"""
Multi-provider embedding implementations.

This module provides concrete implementations of BaseEmbeddingProvider for:
- OpenAI (text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002)
- Cohere (embed-english-v3.0, embed-multilingual-v3.0, embed-english-light-v3.0)
- Voyage (voyage-2, voyage-large-2, voyage-code-2)
- Nomic (nomic-embed-text-v1.5, nomic-embed-text-v1)
- Jina (jina-embeddings-v2, jina-embeddings-v3)
"""

import asyncio
from typing import List, Dict, Any
from .base import (
    BaseEmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    EmbeddingContextLimitError,
)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    OpenAI embedding provider using text-embedding-3 models.

    Models:
    - text-embedding-3-small: 1536 dimensions, $0.02/1M tokens
    - text-embedding-3-large: 3072 dimensions, $0.13/1M tokens
    - text-embedding-ada-002: 1536 dimensions, $0.10/1M tokens
    """

    # Model specifications
    MODELS = {
        "text-embedding-3-small": {
            "dimensions": 1536,
            "context_limit": 8191,
            "cost_per_1m_tokens": 0.02,
        },
        "text-embedding-3-large": {
            "dimensions": 3072,
            "context_limit": 8191,
            "cost_per_1m_tokens": 0.13,
        },
        "text-embedding-ada-002": {
            "dimensions": 1536,
            "context_limit": 8191,
            "cost_per_1m_tokens": 0.10,
        },
    }

    def __init__(self, api_key: str = None):
        super().__init__(api_key)
        try:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=api_key)
        except ImportError:
            raise EmbeddingProviderError(
                "OpenAI package not installed. Install with: pip install openai"
            )

    async def generate_embedding(self, text: str, model: str) -> List[float]:
        self._validate_text_input(text)

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        try:
            response = await self._client.embeddings.create(
                input=text, model=model, encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            if "rate" in str(e).lower():
                raise EmbeddingRateLimitError(f"OpenAI rate limit: {e}")
            raise EmbeddingProviderError(f"OpenAI API error: {e}")

    async def generate_embeddings_batch(
        self, texts: List[str], model: str
    ) -> List[List[float]]:
        if not texts:
            return []

        for text in texts:
            self._validate_text_input(text)

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        try:
            response = await self._client.embeddings.create(
                input=texts, model=model, encoding_format="float"
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            if "rate" in str(e).lower():
                raise EmbeddingRateLimitError(f"OpenAI rate limit: {e}")
            raise EmbeddingProviderError(f"OpenAI API error: {e}")

    def get_model_name(self, model_id: str) -> str:
        names = {
            "text-embedding-3-small": "OpenAI text-embedding-3-small",
            "text-embedding-3-large": "OpenAI text-embedding-3-large",
            "text-embedding-ada-002": "OpenAI text-embedding-ada-002",
        }
        return names.get(model_id, model_id)

    def estimate_cost(self, text: str, model: str) -> float:
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        tokens = self._estimate_tokens(text)
        cost_per_1m = self.MODELS[model]["cost_per_1m_tokens"]
        return (tokens / 1_000_000) * cost_per_1m

    def get_context_limit(self, model: str) -> int:
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")
        return self.MODELS[model]["context_limit"]

    def get_provider_name(self) -> str:
        return "OpenAI"


class CohereEmbeddingProvider(BaseEmbeddingProvider):
    """
    Cohere embedding provider using embed-v3 models.

    Models:
    - embed-english-v3.0: 1024 dimensions, $0.10/1M tokens
    - embed-multilingual-v3.0: 1024 dimensions, $0.15/1M tokens
    - embed-english-light-v3.0: 384 dimensions, $0.05/1M tokens
    """

    MODELS = {
        "embed-english-v3.0": {
            "dimensions": 1024,
            "context_limit": 512,
            "cost_per_1m_tokens": 0.10,
        },
        "embed-multilingual-v3.0": {
            "dimensions": 1024,
            "context_limit": 512,
            "cost_per_1m_tokens": 0.15,
        },
        "embed-english-light-v3.0": {
            "dimensions": 384,
            "context_limit": 512,
            "cost_per_1m_tokens": 0.05,
        },
    }

    def __init__(self, api_key: str = None):
        super().__init__(api_key)
        try:
            import cohere

            self._client = cohere.AsyncClient(api_key=api_key)
        except ImportError:
            raise EmbeddingProviderError(
                "Cohere package not installed. Install with: pip install cohere"
            )

    async def generate_embedding(self, text: str, model: str) -> List[float]:
        self._validate_text_input(text)

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        try:
            response = await self._client.embed(
                texts=[text], model=model, input_type="search_document"
            )
            return response.embeddings[0]
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise EmbeddingRateLimitError(f"Cohere rate limit: {e}")
            raise EmbeddingProviderError(f"Cohere API error: {e}")

    async def generate_embeddings_batch(
        self, texts: List[str], model: str
    ) -> List[List[float]]:
        if not texts:
            return []

        for text in texts:
            self._validate_text_input(text)

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        try:
            response = await self._client.embed(
                texts=texts, model=model, input_type="search_document"
            )
            return response.embeddings
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise EmbeddingRateLimitError(f"Cohere rate limit: {e}")
            raise EmbeddingProviderError(f"Cohere API error: {e}")

    def get_model_name(self, model_id: str) -> str:
        names = {
            "embed-english-v3.0": "Cohere embed-english-v3.0",
            "embed-multilingual-v3.0": "Cohere embed-multilingual-v3.0",
            "embed-english-light-v3.0": "Cohere embed-english-light-v3.0",
        }
        return names.get(model_id, model_id)

    def estimate_cost(self, text: str, model: str) -> float:
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        tokens = self._estimate_tokens(text)
        cost_per_1m = self.MODELS[model]["cost_per_1m_tokens"]
        return (tokens / 1_000_000) * cost_per_1m

    def get_context_limit(self, model: str) -> int:
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")
        return self.MODELS[model]["context_limit"]

    def get_provider_name(self) -> str:
        return "Cohere"


class VoyageEmbeddingProvider(BaseEmbeddingProvider):
    """
    Voyage AI embedding provider.

    Models:
    - voyage-2: 1024 dimensions, $0.10/1M tokens
    - voyage-large-2: 1536 dimensions, $0.25/1M tokens
    - voyage-code-2: 1536 dimensions, $0.15/1M tokens
    """

    MODELS = {
        "voyage-2": {
            "dimensions": 1024,
            "context_limit": 128,
            "cost_per_1m_tokens": 0.10,
        },
        "voyage-large-2": {
            "dimensions": 1536,
            "context_limit": 128,
            "cost_per_1m_tokens": 0.25,
        },
        "voyage-code-2": {
            "dimensions": 1536,
            "context_limit": 128,
            "cost_per_1m_tokens": 0.15,
        },
    }

    def __init__(self, api_key: str = None):
        super().__init__(api_key)
        try:
            import voyageai

            self._client = voyageai.Client(api_key=api_key)
        except ImportError:
            raise EmbeddingProviderError(
                "VoyageAI package not installed. Install with: pip install voyageai"
            )

    async def generate_embedding(self, text: str, model: str) -> List[float]:
        self._validate_text_input(text)

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        try:
            # Voyage AI doesn't have native async, use thread pool
            result = await asyncio.to_thread(
                self._client.embed, text, model=model, input_type="document"
            )
            return result[0]
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise EmbeddingRateLimitError(f"Voyage rate limit: {e}")
            raise EmbeddingProviderError(f"Voyage API error: {e}")

    async def generate_embeddings_batch(
        self, texts: List[str], model: str
    ) -> List[List[float]]:
        if not texts:
            return []

        for text in texts:
            self._validate_text_input(text)

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        try:
            result = await asyncio.to_thread(
                self._client.embed, texts, model=model, input_type="document"
            )
            return result
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise EmbeddingRateLimitError(f"Voyage rate limit: {e}")
            raise EmbeddingProviderError(f"Voyage API error: {e}")

    def get_model_name(self, model_id: str) -> str:
        names = {
            "voyage-2": "Voyage voyage-2",
            "voyage-large-2": "Voyage voyage-large-2",
            "voyage-code-2": "Voyage voyage-code-2",
        }
        return names.get(model_id, model_id)

    def estimate_cost(self, text: str, model: str) -> float:
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        tokens = self._estimate_tokens(text)
        cost_per_1m = self.MODELS[model]["cost_per_1m_tokens"]
        return (tokens / 1_000_000) * cost_per_1m

    def get_context_limit(self, model: str) -> int:
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")
        return self.MODELS[model]["context_limit"]

    def get_provider_name(self) -> str:
        return "Voyage"


class NomicEmbeddingProvider(BaseEmbeddingProvider):
    """
    Nomic AI embedding provider.

    Models:
    - nomic-embed-text-v1.5: 768 dimensions, $0.08/1M tokens
    - nomic-embed-text-v1: 768 dimensions, $0.10/1M tokens
    """

    MODELS = {
        "nomic-embed-text-v1.5": {
            "dimensions": 768,
            "context_limit": 8192,
            "cost_per_1m_tokens": 0.08,
        },
        "nomic-embed-text-v1": {
            "dimensions": 768,
            "context_limit": 8192,
            "cost_per_1m_tokens": 0.10,
        },
    }

    def __init__(self, api_key: str = None):
        super().__init__(api_key)
        try:
            import nomic

            self._client = nomic.Embedding(api_key=api_key)
        except ImportError:
            raise EmbeddingProviderError(
                "Nomic package not installed. Install with: pip install nomic"
            )

    async def generate_embedding(self, text: str, model: str) -> List[float]:
        self._validate_text_input(text)

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        try:
            result = await asyncio.to_thread(
                self._client.embed, texts=[text], model=model, task_type="search_document"
            )
            return result["embeddings"][0]
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise EmbeddingRateLimitError(f"Nomic rate limit: {e}")
            raise EmbeddingProviderError(f"Nomic API error: {e}")

    async def generate_embeddings_batch(
        self, texts: List[str], model: str
    ) -> List[List[float]]:
        if not texts:
            return []

        for text in texts:
            self._validate_text_input(text)

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        try:
            result = await asyncio.to_thread(
                self._client.embed, texts=texts, model=model, task_type="search_document"
            )
            return result["embeddings"]
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise EmbeddingRateLimitError(f"Nomic rate limit: {e}")
            raise EmbeddingProviderError(f"Nomic API error: {e}")

    def get_model_name(self, model_id: str) -> str:
        names = {
            "nomic-embed-text-v1.5": "Nomic nomic-embed-text-v1.5",
            "nomic-embed-text-v1": "Nomic nomic-embed-text-v1",
        }
        return names.get(model_id, model_id)

    def estimate_cost(self, text: str, model: str) -> float:
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        tokens = self._estimate_tokens(text)
        cost_per_1m = self.MODELS[model]["cost_per_1m_tokens"]
        return (tokens / 1_000_000) * cost_per_1m

    def get_context_limit(self, model: str) -> int:
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")
        return self.MODELS[model]["context_limit"]

    def get_provider_name(self) -> str:
        return "Nomic"


class JinaEmbeddingProvider(BaseEmbeddingProvider):
    """
    Jina AI embedding provider using OpenAI-compatible API.

    Models:
    - jina-embeddings-v2: 768 dimensions, $0.02/1M tokens
    - jina-embeddings-v3: 1024 dimensions, $0.03/1M tokens
    """

    MODELS = {
        "jina-embeddings-v2": {
            "dimensions": 768,
            "context_limit": 8192,
            "cost_per_1m_tokens": 0.02,
        },
        "jina-embeddings-v3": {
            "dimensions": 1024,
            "context_limit": 8191,
            "cost_per_1m_tokens": 0.03,
        },
    }

    BASE_URL = "https://api.jina.ai/v1"

    def __init__(self, api_key: str = None):
        super().__init__(api_key)
        try:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=api_key, base_url=self.BASE_URL
            )
        except ImportError:
            raise EmbeddingProviderError(
                "OpenAI package not installed. Install with: pip install openai"
            )

    async def generate_embedding(self, text: str, model: str) -> List[float]:
        self._validate_text_input(text)

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        try:
            response = await self._client.embeddings.create(
                input=text, model=model
            )
            return response.data[0].embedding
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise EmbeddingRateLimitError(f"Jina rate limit: {e}")
            raise EmbeddingProviderError(f"Jina API error: {e}")

    async def generate_embeddings_batch(
        self, texts: List[str], model: str
    ) -> List[List[float]]:
        if not texts:
            return []

        for text in texts:
            self._validate_text_input(text)

        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        try:
            response = await self._client.embeddings.create(
                input=texts, model=model
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                raise EmbeddingRateLimitError(f"Jina rate limit: {e}")
            raise EmbeddingProviderError(f"Jina API error: {e}")

    def get_model_name(self, model_id: str) -> str:
        names = {
            "jina-embeddings-v2": "Jina jina-embeddings-v2",
            "jina-embeddings-v3": "Jina jina-embeddings-v3",
        }
        return names.get(model_id, model_id)

    def estimate_cost(self, text: str, model: str) -> float:
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")

        tokens = self._estimate_tokens(text)
        cost_per_1m = self.MODELS[model]["cost_per_1m_tokens"]
        return (tokens / 1_000_000) * cost_per_1m

    def get_context_limit(self, model: str) -> int:
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")
        return self.MODELS[model]["context_limit"]

    def get_provider_name(self) -> str:
        return "Jina"


__all__ = [
    "OpenAIEmbeddingProvider",
    "CohereEmbeddingProvider",
    "VoyageEmbeddingProvider",
    "NomicEmbeddingProvider",
    "JinaEmbeddingProvider",
]

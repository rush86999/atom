"""
Embedding provider module for multi-provider embedding generation.

This module provides a unified interface for generating embeddings using
multiple providers (OpenAI, Cohere, Voyage, Nomic, Jina).

Purpose: Enable enterprise-grade reliability through provider diversity
and fallback capabilities.
"""

from .base import (
    BaseEmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    EmbeddingContextLimitError)
from .providers import (
    OpenAIEmbeddingProvider,
    CohereEmbeddingProvider,
    VoyageEmbeddingProvider,
    NomicEmbeddingProvider,
    JinaEmbeddingProvider)

__all__ = [
    "BaseEmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingRateLimitError",
    "EmbeddingContextLimitError",
    "OpenAIEmbeddingProvider",
    "CohereEmbeddingProvider",
    "VoyageEmbeddingProvider",
    "NomicEmbeddingProvider",
    "JinaEmbeddingProvider",
]

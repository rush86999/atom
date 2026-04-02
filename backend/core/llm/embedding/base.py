"""
Base interface for embedding providers.

Defines the abstract contract that all embedding providers must implement,
ensuring consistency across different provider implementations.
"""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProviderError(Exception):
    """Base exception for embedding provider errors."""

    pass


class EmbeddingRateLimitError(EmbeddingProviderError):
    """Raised when provider rate limit is exceeded."""

    pass


class EmbeddingContextLimitError(EmbeddingProviderError):
    """Raised when input text exceeds model's context limit."""

    pass


class BaseEmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.

    All embedding providers must inherit from this class and implement
    the abstract methods to ensure consistent behavior across providers.

    Example:
        >>> provider = OpenAIEmbeddingProvider(api_key="sk-...")
        >>> embedding = await provider.generate_embedding("Hello world", "text-embedding-3-small")
        >>> len(embedding)
        1536
    """

    def __init__(self, api_key: str = None):
        """
        Initialize the embedding provider.

        Args:
            api_key: Optional API key for the provider. If not provided,
                    will attempt to use environment variable.
        """
        self._api_key = api_key
        self._client = None

    @abstractmethod
    async def generate_embedding(
        self, text: str, model: str
    ) -> List[float]:
        """
        Generate a single embedding for the given text.

        Args:
            text: The input text to embed
            model: The model identifier to use

        Returns:
            List of floats representing the embedding vector

        Raises:
            EmbeddingProviderError: If the API call fails
            EmbeddingRateLimitError: If rate limit is exceeded
            EmbeddingContextLimitError: If text exceeds context limit
        """
        pass

    @abstractmethod
    async def generate_embeddings_batch(
        self, texts: List[str], model: str
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a single batch call.

        Args:
            texts: List of input texts to embed
            model: The model identifier to use

        Returns:
            List of embedding vectors (one per input text)

        Raises:
            EmbeddingProviderError: If the API call fails
            EmbeddingRateLimitError: If rate limit is exceeded
            EmbeddingContextLimitError: If any text exceeds context limit
        """
        pass

    @abstractmethod
    def get_model_name(self, model_id: str) -> str:
        """
        Get a human-readable display name for a model.

        Args:
            model_id: The internal model identifier

        Returns:
            Human-readable model name
        """
        pass

    @abstractmethod
    def estimate_cost(self, text: str, model: str) -> float:
        """
        Estimate the cost in USD for embedding the given text.

        Args:
            text: The input text
            model: The model identifier

        Returns:
            Estimated cost in USD
        """
        pass

    @abstractmethod
    def get_context_limit(self, model: str) -> int:
        """
        Get the maximum token limit for a model.

        Args:
            model: The model identifier

        Returns:
            Maximum number of tokens supported
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of this embedding provider.

        Returns:
            Provider name (e.g., "OpenAI", "Cohere")
        """
        pass

    def _validate_text_input(self, text: str) -> None:
        """
        Validate text input before processing.

        Args:
            text: The input text to validate

        Raises:
            ValueError: If text is empty, None, or not a string
        """
        if not isinstance(text, str):
            raise ValueError(f"Text must be a string, got {type(text).__name__}")

        if not text or not text.strip():
            raise ValueError("Text cannot be empty or whitespace only")

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses heuristic: 1 token ≈ 4 characters (average for English text).

        Args:
            text: The input text

        Returns:
            Estimated token count
        """
        return len(text) // 4

    def _truncate_to_fit(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within the token limit.

        Args:
            text: The input text
            max_tokens: Maximum allowed tokens

        Returns:
            Truncated text that fits within the limit
        """
        estimated_tokens = self._estimate_tokens(text)

        if estimated_tokens <= max_tokens:
            return text

        # Truncate to fit (with some buffer for safety)
        target_chars = max_tokens * 4
        return text[:target_chars]

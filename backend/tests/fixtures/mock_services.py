"""
Mock service instances for testing.

Provides mock implementations of common services to eliminate external dependencies.
"""

from typing import Any, Dict, Optional, AsyncIterator
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime
import asyncio


class MockLLMProvider:
    """Mock LLM provider for testing.

    Simulates responses from OpenAI, Anthropic, etc.
    """

    def __init__(self):
        self._call_count = 0
        self._error_mode = None
        self._responses = {}
        self._delay_ms = 0

    def set_response(self, prompt: str, response: str):
        """Set a custom response for a specific prompt."""
        self._responses[prompt] = response

    def complete(self, prompt: str, **kwargs) -> str:
        """Return a mock completion response."""
        self._call_count += 1

        if self._error_mode == "rate_limited":
            raise Exception("Rate limit exceeded")
        elif self._error_mode == "timeout":
            raise asyncio.TimeoutError("LLM timeout")

        # Check for custom response
        if prompt in self._responses:
            return self._responses[prompt]

        # Default deterministic response
        return f"Mock LLM response {self._call_count} for: {prompt[:50]}"

    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Return a mock streaming response."""
        self._call_count += 1

        if self._error_mode:
            if self._error_mode == "rate_limited":
                raise Exception("Rate limit exceeded")
            elif self._error_mode == "timeout":
                raise asyncio.TimeoutError("LLM timeout")

        response = f"Mock streaming response {self._call_count}"
        for char in response:
            if self._delay_ms > 0:
                await asyncio.sleep(self._delay_ms / 1000)
            yield char

    def set_error_mode(self, mode: Optional[str]):
        """Set error mode for testing failure scenarios.

        Args:
            mode: One of "rate_limited", "timeout", or None
        """
        self._error_mode = mode

    def set_delay(self, delay_ms: int):
        """Set simulated network delay."""
        self._delay_ms = delay_ms

    def reset(self):
        """Reset call count and error mode."""
        self._call_count = 0
        self._error_mode = None
        self._responses = {}
        self._delay_ms = 0

    @property
    def call_count(self) -> int:
        """Get total call count."""
        return self._call_count


class MockEmbeddingService:
    """Mock embedding service for testing.

    Simulates vector embeddings without requiring actual models.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension
        self._call_count = 0

    def embed(self, text: str) -> list[float]:
        """Generate deterministic mock embedding vector."""
        self._call_count += 1
        import hashlib

        # Use hash for determinism
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()

        # Convert to floats in [-1, 1]
        values = []
        for i in range(self._dimension):
            byte_idx = i % len(hash_bytes)
            byte_val = hash_bytes[byte_idx]
            float_val = (byte_val - 128) / 128.0
            values.append(float_val)

        return values

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return [self.embed(text) for text in texts]

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot_product / (mag1 * mag2)

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension

    @property
    def call_count(self) -> int:
        """Get total call count."""
        return self._call_count


class MockStorageService:
    """Mock storage service for testing.

    Simulates file storage operations without requiring actual storage.
    """

    def __init__(self):
        self._files = {}
        self._call_count = 0

    def store(self, key: str, data: bytes) -> str:
        """Store data and return URL."""
        self._call_count += 1
        self._files[key] = data
        return f"https://mock-storage.example.com/{key}"

    def retrieve(self, key: str) -> Optional[bytes]:
        """Retrieve stored data."""
        self._call_count += 1
        return self._files.get(key)

    def delete(self, key: str) -> bool:
        """Delete stored data."""
        self._call_count += 1
        return self._files.pop(key, None) is not None

    def exists(self, key: str) -> bool:
        """Check if data exists."""
        return key in self._files

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys with optional prefix."""
        return [k for k in self._files.keys() if k.startswith(prefix)]

    @property
    def call_count(self) -> int:
        """Get total call count."""
        return self._call_count

    def reset(self):
        """Clear all stored data."""
        self._files = {}
        self._call_count = 0


class MockCacheService:
    """Mock cache service for testing.

    Simulates cache operations without requiring actual cache backend.
    """

    def __init__(self):
        self._cache = {}
        self._call_count = 0
        self._ttl = {}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        self._call_count += 1

        # Check TTL
        if key in self._ttl:
            if datetime.utcnow() > self._ttl[key]:
                del self._cache[key]
                del self._ttl[key]
                return None

        return self._cache.get(key)

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Set value in cache with optional TTL."""
        self._call_count += 1
        self._cache[key] = value

        if ttl_seconds:
            expires_at = datetime.utcnow() + __import__('datetime').timedelta(seconds=ttl_seconds)
            self._ttl[key] = expires_at

    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        self._call_count += 1
        if key in self._cache:
            del self._cache[key]
            if key in self._ttl:
                del self._ttl[key]
            return True
        return False

    def clear(self):
        """Clear all cache entries."""
        self._call_count += 1
        self._cache.clear()
        self._ttl.clear()

    @property
    def call_count(self) -> int:
        """Get total call count."""
        return self._call_count

    @property
    def size(self) -> int:
        """Get cache size."""
        return len(self._cache)


class MockWebSocket:
    """Mock WebSocket for testing.

    Simulates WebSocket connections without actual network.
    """

    def __init__(self):
        self._messages = []
        self._closed = False
        self._call_count = 0

    async def send(self, message: Any):
        """Send a message."""
        self._call_count += 1
        if self._closed:
            raise Exception("WebSocket is closed")
        self._messages.append(message)

    async def receive(self) -> Any:
        """Receive a message."""
        self._call_count += 1
        if self._closed:
            raise Exception("WebSocket is closed")
        if self._messages:
            return self._messages.pop(0)
        # Simulate waiting
        await asyncio.sleep(0.1)
        return None

    async def close(self):
        """Close the connection."""
        self._closed = True

    @property
    def call_count(self) -> int:
        """Get total call count."""
        return self._call_count

    @property
    def is_closed(self) -> bool:
        """Check if connection is closed."""
        return self._closed

    def reset(self):
        """Reset WebSocket state."""
        self._messages = []
        self._closed = False
        self._call_count = 0


# Convenience instances for pytest fixtures
mock_llm = MockLLMProvider()
mock_embeddings = MockEmbeddingService()
mock_storage = MockStorageService()
mock_cache = MockCacheService()
mock_websocket = MockWebSocket()

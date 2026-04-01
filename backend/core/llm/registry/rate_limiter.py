"""Rate limiting and retry logic for API requests.

Provides exponential backoff for handling rate limits (HTTP 429) and
transient errors when fetching model metadata from external APIs.
"""

import asyncio
import logging
import random
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import httpx

from core.cache import UniversalCacheService

logger = logging.getLogger(__name__)



# Rate limit configuration
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 60.0  # seconds
BACKOFF_MULTIPLIER = 2.0
JITTER_FACTOR = 0.1  # Add 10% random jitter to prevent thundering herd

# Rate limit state TTL (how long to remember rate limit state)
RATE_LIMIT_TTL = 300  # 5 minutes



class RateLimiter:
    """Tracks rate limit state per provider using Redis."""

    RATE_LIMIT_KEY_PREFIX = "llm_registry_rate_limit"

    def __init__(self, cache_service: Optional[UniversalCacheService] = None):
        self.cache = cache_service or UniversalCacheService()

    def _get_key(self, provider: str) -> str:
        """Build rate limit state key for a provider."""
        return f"{self.RATE_LIMIT_KEY_PREFIX}:{provider}"

    async def is_rate_limited(self, provider: str) -> bool:
        """Check if a provider is currently rate limited.

        Args:
            provider: Provider name (e.g., 'litellm', 'openrouter')

        Returns:
            True if provider is rate limited, False otherwise
        """
        key = self._get_key(provider)
        state = await self.cache.get_async(key)
        return state is not None

    async def mark_rate_limited(self, provider: str, retry_after: int = 60):
        """Mark a provider as rate limited.

        Args:
            provider: Provider name
            retry_after: Seconds before retry (from Retry-After header or default)
        """
        key = self._get_key(provider)
        ttl = min(retry_after, RATE_LIMIT_TTL)
        await self.cache.set_async(key, "rate_limited", ttl)

    async def clear_rate_limit(self, provider: str):
        """Clear rate limit state for a provider.

        Called after successful request to allow future requests.
        """
        key = self._get_key(provider)
        await self.cache.delete_async(key)



class APIClientWithRetry:
    """HTTP client with exponential backoff for rate limit handling.

    Wraps httpx.AsyncClient with automatic retry logic for:
    - HTTP 429 (Too Many Requests)
    - HTTP 5xx (Server errors)
    - Network timeouts

    Usage:
        client = APIClientWithRetry()
        response = await client.get("https://api.example.com/data")
        await client.close()
    """

    def __init__(
        self,
        max_retries: int = MAX_RETRIES,
        initial_delay: float = INITIAL_RETRY_DELAY,
        max_delay: float = MAX_RETRY_DELAY,
        rate_limiter: Optional[RateLimiter] = None
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.rate_limiter = rate_limiter or RateLimiter()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _calculate_delay(self, attempt: int, retry_after: Optional[int] = None) -> float:
        """Calculate delay before next retry with exponential backoff and jitter.

        Args:
            attempt: Retry attempt number (0-indexed)
            retry_after: Seconds from Retry-After header (if present)

        Returns:
            Delay in seconds
        """
        if retry_after is not None:
            # Use server-provided retry delay, capped at max
            delay = min(retry_after, self.max_delay)
        else:
            # Exponential backoff: initial * (2 ^ attempt)
            exponential_delay = self.initial_delay * (BACKOFF_MULTIPLIER ** attempt)
            delay = min(exponential_delay, self.max_delay)

        # Add jitter to prevent thundering herd
        jitter = delay * JITTER_FACTOR
        delay += random.uniform(-jitter, jitter)

        return max(0, delay)  # Ensure non-negative

    async def get(
        self,
        url: str,
        provider: str = "default",
        **kwargs
    ) -> httpx.Response:
        """GET request with automatic retry on rate limits and errors.

        Args:
            url: Request URL
            provider: Provider name for rate limit tracking
            **kwargs: Additional arguments passed to httpx.get()

        Returns:
            httpx.Response

        Raises:
            httpx.HTTPError: After max retries exhausted
        """
        client = await self._get_client()

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.get(url, **kwargs)

                # Rate limited (429)
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            retry_after = int(retry_after)
                        except ValueError:
                            retry_after = None

                    await self.rate_limiter.mark_rate_limited(provider, retry_after or 60)

                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt, retry_after)
                        logger.warning(
                            f"Rate limited by {provider} (429), "
                            f"retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Max retries exhausted - raise error
                        raise httpx.HTTPError(f"Max retries ({self.max_retries}) exceeded for {url}")

                # Successful response - clear rate limit state and return
                if response.status_code < 500:
                    await self.rate_limiter.clear_rate_limit(provider)
                    return response

                # Server error (5xx)
                if 500 <= response.status_code < 600:
                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt)
                        logger.warning(
                            f"Server error {response.status_code} from {provider}, "
                            f"retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue

                # Other errors - return response
                return response

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Network error from {provider}: {e}, "
                        f"retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        raise httpx.HTTPError(f"Max retries ({self.max_retries}) exceeded for {url}")

"""
Rate Limiter - Prevent API quota exhaustion with exponential backoff

Single-tenant version for upstream (no tenant isolation).
Supports optional Redis for distributed coordination.
Falls back to in-memory tracking when Redis is unavailable.

Ported from atom-saas with SaaS patterns removed (tenant isolation, tenant-scoped limits).
"""
import logging
import time
import asyncio
from typing import Dict, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter for integration services (single-tenant).
    Supports optional Redis for distributed coordination.
    Falls back to in-memory state when Redis is not available.

    Uses fixed window approach for simplicity.
    """

    def __init__(self, redis_client=None):
        # Default limits per integration (requests per minute)
        self.default_limits = {
            "slack": 100,      # 100 requests per minute
            "salesforce": 50,
            "hubspot": 50,
            "jira": 50,
            "gmail": 60,
            "outlook": 60,
            "zoom": 100,
            "stripe": 100,
            "openai": 60,
            "whatsapp": 30,
            "google_drive": 60,
            "box": 60,
            "default": 30      # Fallback for others
        }

        self.redis = redis_client

        # In-memory fallback: {connector_id: {"count": int, "window_start": float}}
        self._tracking: Dict[str, Dict[str, any]] = defaultdict(
            lambda: {"count": 0, "window_start": 0}
        )

    async def is_rate_limited(
        self,
        connector_id: str,
        limit: Optional[int] = None,
        window: int = 60
    ) -> Tuple[bool, int]:
        """
        Check if the request should be rate limited.

        Args:
            connector_id: The integration identifier
            limit: Optional override for the limit
            window: Time window in seconds (default 60s)

        Returns:
            Tuple of (is_limited, remaining_requests)
        """
        # Determine limit: override -> default -> global fallback
        effective_limit = limit or self.default_limits.get(
            connector_id,
            self.default_limits["default"]
        )

        # Try Redis first
        if self.redis:
            try:
                cache_key = f"rate_limit:{connector_id}"
                current_count = await self.redis.get(cache_key)

                if current_count is None:
                    # First request in window
                    await self.redis.set(cache_key, 1, ex=window)
                    return False, effective_limit - 1

                count = int(current_count)
                if count >= effective_limit:
                    logger.warning(
                        f"Rate limit exceeded for {connector_id}: "
                        f"{count}/{effective_limit}"
                    )
                    return True, 0

                # Increment
                new_count = count + 1
                await self.redis.set(cache_key, new_count, ex=window)

                return False, effective_limit - new_count
            except Exception as e:
                logger.warning(f"Redis rate limit check failed, falling back to in-memory: {e}")

        # Fallback to in-memory tracking
        current_time = time.time()
        tracking = self._tracking[connector_id]

        # Check if window has expired
        if current_time - tracking["window_start"] >= window:
            # Reset window
            tracking["count"] = 0
            tracking["window_start"] = current_time

        # Check if limit exceeded
        if tracking["count"] >= effective_limit:
            logger.warning(
                f"Rate limit exceeded for {connector_id}: "
                f"{tracking['count']}/{effective_limit}"
            )
            return True, 0

        # Increment counter
        tracking["count"] += 1
        remaining = effective_limit - tracking["count"]

        return False, remaining

    async def reset(self, connector_id: Optional[str] = None):
        """
        Reset rate limit tracking.

        Args:
            connector_id: Specific connector to reset, or None to reset all
        """
        # Reset Redis state
        if self.redis:
            if connector_id:
                await self.redis.delete(f"rate_limit:{connector_id}")
            else:
                # Delete all rate limit keys
                try:
                    if hasattr(self.redis, 'scan_iter'):
                        async for key in self.redis.scan_iter(match="rate_limit:*"):
                            await self.redis.delete(key)
                except Exception as e:
                    logger.error(f"Failed to reset rate limiter in Redis: {e}")

        # Reset in-memory state
        if connector_id:
            if connector_id in self._tracking:
                del self._tracking[connector_id]
            logger.info(f"Rate limiter reset for {connector_id}")
        else:
            self._tracking.clear()
            logger.info("Rate limiter reset for all connectors")


# Global rate limiter instance (no Redis by default in open-source)
rate_limiter = RateLimiter()


def rate_limiter_decorator(integration: str, limit: Optional[int] = None, window: int = 60):
    """
    Decorator to apply rate limiting to a function.

    Usage:
        @rate_limiter_decorator(integration="gmail", limit=100, window=60)
        async def send_email(**params):
            # ... implementation
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            limiter = kwargs.get('rate_limiter', rate_limiter)

            # Check rate limit
            is_limited, remaining = await limiter.is_rate_limited(
                integration,
                limit,
                window
            )

            if is_limited:
                logger.warning(f"Rate limit exceeded for {integration}, blocking call")
                return {
                    "success": False,
                    "error": f"Rate limit exceeded for {integration}. Please try again later."
                }

            # Execute function
            return await func(*args, **kwargs)

        return wrapper
    return decorator


# =============================================================================
# Retry Logic Helper Functions
# =============================================================================

def should_retry(status_code: int) -> bool:
    """
    Determine if a request should be retried based on HTTP status code.

    Retryable errors:
    - 429 Too Many Requests (rate limit)
    - 500 Internal Server Error
    - 502 Bad Gateway
    - 503 Service Unavailable
    - 504 Gateway Timeout

    Non-retryable errors:
    - 400 Bad Request (client error)
    - 401 Unauthorized (auth error, won't fix with retry)
    - 403 Forbidden (permission error)
    - 404 Not Found (resource doesn't exist)

    Args:
        status_code: HTTP status code

    Returns:
        True if request should be retried, False otherwise
    """
    retryable_codes = {429, 500, 502, 503, 504}
    return status_code in retryable_codes


def calculate_backoff(retry_attempt: int, max_backoff: float = 60.0) -> float:
    """
    Calculate exponential backoff delay for retry attempts.

    Backoff formula: min(2^(attempt-1), max_backoff)
    - Attempt 1: 1s
    - Attempt 2: 2s
    - Attempt 3: 4s
    - Attempt 4: 8s (capped at max_backoff if lower)

    Args:
        retry_attempt: Retry attempt number (1-indexed)
        max_backoff: Maximum backoff duration in seconds

    Returns:
        Backoff delay in seconds
    """
    if retry_attempt < 1:
        return 0.0

    backoff = 2.0 ** (retry_attempt - 1)
    return min(backoff, max_backoff)

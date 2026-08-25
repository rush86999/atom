"""
Coverage tests for core/rate_limiter.py.

Covers:
- RateLimiter.is_rate_limited (in-memory + Redis paths + fallbacks)
- RateLimiter.reset (single + all, Redis + in-memory)
- rate_limiter_decorator (allow + block paths)
- should_retry (retryable + non-retryable codes)
- calculate_backoff (boundaries: <1, 1, large, capped)
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.rate_limiter import (
    RateLimiter,
    calculate_backoff,
    rate_limiter_decorator,
    rate_limiter,
    should_retry,
)


# ---------------------------------------------------------------------------
# Fake Redis client (async, mimics aioredis surface used by RateLimiter)
# ---------------------------------------------------------------------------
class FakeRedis:
    """Minimal async Redis stub: get/set/delete/scan_iter with TTL tracking."""

    def __init__(self):
        self.store = {}  # key -> (value, expiry_monotonic_or_None)

    async def get(self, key):
        if key not in self.store:
            return None
        value, expiry = self.store[key]
        if expiry is not None and time.monotonic() > expiry:
            del self.store[key]
            return None
        return value

    async def set(self, key, value, ex=None):
        expiry = time.monotonic() + ex if ex else None
        self.store[key] = (value, expiry)

    async def delete(self, key):
        self.store.pop(key, None)

    def scan_iter(self, match=None):
        import fnmatch

        keys = list(self.store.keys())
        if match:
            keys = [k for k in keys if fnmatch.fnmatch(k, match)]

        async def gen():
            for k in keys:
                yield k

        return gen()


class BrokenRedis(FakeRedis):
    """Redis whose get always raises to exercise fallback."""

    async def get(self, key):
        raise RuntimeError("redis down")

    async def set(self, key, value, ex=None):
        raise RuntimeError("redis down")


class NoScanRedis:
    """Redis-like client WITHOUT scan_iter to cover the hasattr branch in reset."""

    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def delete(self, key):
        self.store.pop(key, None)


# ---------------------------------------------------------------------------
# is_rate_limited - in-memory
# ---------------------------------------------------------------------------
class TestIsRateLimitedInMemory:
    @pytest.mark.asyncio
    async def test_first_request_succeeds(self):
        rl = RateLimiter()
        limited, remaining = await rl.is_rate_limited("slack", limit=5, window=60)
        assert limited is False
        assert remaining == 4

    @pytest.mark.asyncio
    async def test_default_limit_used_when_none(self):
        rl = RateLimiter()
        # slack default is 100
        limited, remaining = await rl.is_rate_limited("slack")
        assert limited is False
        assert remaining == 99

    @pytest.mark.asyncio
    async def test_unknown_connector_uses_global_default(self):
        rl = RateLimiter()
        limited, remaining = await rl.is_rate_limited("unknown_xyz")
        assert limited is False
        assert remaining == 29  # default=30

    @pytest.mark.asyncio
    async def test_limit_exceeded(self):
        rl = RateLimiter()
        for _ in range(3):
            await rl.is_rate_limited("c", limit=3, window=60)
        limited, remaining = await rl.is_rate_limited("c", limit=3, window=60)
        assert limited is True
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_window_expiry_resets_counter(self):
        rl = RateLimiter()
        await rl.is_rate_limited("c", limit=2, window=0.05)  # tiny window
        await rl.is_rate_limited("c", limit=2, window=0.05)
        # now exhausted
        limited, _ = await rl.is_rate_limited("c", limit=2, window=0.05)
        assert limited is True
        # wait for window to expire
        await asyncio.sleep(0.06)
        limited, remaining = await rl.is_rate_limited("c", limit=2, window=0.05)
        assert limited is False
        assert remaining == 1

    @pytest.mark.asyncio
    async def test_explicit_limit_zero_blocks_all_requests(self):
        """BUG: explicit limit=0 was silently replaced with the default (30)
        because `limit or self.default_limits.get(...)` treats 0 as falsy.
        An explicit limit of 0 means "block everything" and must be honored.
        """
        rl = RateLimiter()
        limited, remaining = await rl.is_rate_limited("z", limit=0, window=60)
        assert limited is True
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_explicit_limit_zero_in_redis_path(self):
        """Same BUG, Redis code path: effective_limit uses the same `or`.
        After the seed request, the next call must be blocked with remaining=0."""
        rl = RateLimiter(redis_client=FakeRedis())
        # First request seeds counter to 1.
        await rl.is_rate_limited("z", limit=0, window=60)
        # Now count=1 >= effective_limit(0) -> blocked
        limited, remaining = await rl.is_rate_limited("z", limit=0, window=60)
        assert limited is True
        assert remaining == 0


# ---------------------------------------------------------------------------
# is_rate_limited - Redis paths
# ---------------------------------------------------------------------------
class TestIsRateLimitedRedis:
    @pytest.mark.asyncio
    async def test_redis_first_request(self):
        redis = FakeRedis()
        rl = RateLimiter(redis_client=redis)
        limited, remaining = await rl.is_rate_limited("slack", limit=5, window=60)
        assert limited is False
        assert remaining == 4
        # key created
        assert "rate_limit:slack" in redis.store

    @pytest.mark.asyncio
    async def test_redis_increment_until_limit(self):
        redis = FakeRedis()
        rl = RateLimiter(redis_client=redis)
        for _ in range(3):
            await rl.is_rate_limited("s", limit=3, window=60)
        limited, remaining = await rl.is_rate_limited("s", limit=3, window=60)
        assert limited is True
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_redis_falls_back_on_error(self):
        redis = BrokenRedis()
        rl = RateLimiter(redis_client=redis)
        limited, remaining = await rl.is_rate_limited("slack", limit=2, window=60)
        # falls back to in-memory after BrokenRedis raises
        assert limited is False
        assert remaining == 1
        # in-memory state was updated
        assert rl._tracking["slack"]["count"] == 1


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------
class TestReset:
    @pytest.mark.asyncio
    async def test_reset_single_connector_in_memory(self):
        rl = RateLimiter()
        await rl.is_rate_limited("a", limit=5, window=60)
        await rl.reset("a")
        assert "a" not in rl._tracking

    @pytest.mark.asyncio
    async def test_reset_all_in_memory(self):
        rl = RateLimiter()
        await rl.is_rate_limited("a", limit=5, window=60)
        await rl.is_rate_limited("b", limit=5, window=60)
        await rl.reset()
        assert len(rl._tracking) == 0

    @pytest.mark.asyncio
    async def test_reset_single_redis(self):
        redis = FakeRedis()
        rl = RateLimiter(redis_client=redis)
        await rl.is_rate_limited("a", limit=5, window=60)
        await rl.reset("a")
        assert "rate_limit:a" not in redis.store

    @pytest.mark.asyncio
    async def test_reset_all_redis_with_scan(self):
        redis = FakeRedis()
        rl = RateLimiter(redis_client=redis)
        await rl.is_rate_limited("a", limit=5, window=60)
        await rl.is_rate_limited("b", limit=5, window=60)
        await rl.reset()
        assert len(redis.store) == 0

    @pytest.mark.asyncio
    async def test_reset_all_redis_without_scan_iter(self):
        redis = NoScanRedis()
        rl = RateLimiter(redis_client=redis)
        await rl.is_rate_limited("a", limit=5, window=60)
        # Should not raise even though scan_iter is missing (hasattr False);
        # any warning escalates to an error (pytest.warns(None) is gone).
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            await rl.reset()
        # nothing deleted but no crash
        assert "rate_limit:a" in redis.store

    @pytest.mark.asyncio
    async def test_reset_all_redis_scan_raises_handled(self):
        redis = FakeRedis()
        rl = RateLimiter(redis_client=redis)

        async def boom(match=None):
            raise RuntimeError("scan failed")
            yield  # noqa: make it an async generator

        redis.scan_iter = lambda match=None: boom(match)
        await rl.reset()  # should not raise


# ---------------------------------------------------------------------------
# rate_limiter_decorator
# ---------------------------------------------------------------------------
class TestRateLimiterDecorator:
    @pytest.mark.asyncio
    async def test_decorator_allows_when_under_limit(self):
        @rate_limiter_decorator("gmail", limit=5, window=60)
        async def send(**kwargs):
            return {"success": True, "sent": True}

        result = await send()
        assert result == {"success": True, "sent": True}

    @pytest.mark.asyncio
    async def test_decorator_blocks_when_over_limit(self):
        # Use a dedicated limiter injected via kwargs
        limiter = RateLimiter()
        for _ in range(3):
            await limiter.is_rate_limited("gmail", limit=3, window=60)

        @rate_limiter_decorator("gmail", limit=3, window=60)
        async def send(**kwargs):
            return {"success": True}

        result = await send(rate_limiter=limiter)
        assert result["success"] is False
        assert "Rate limit exceeded" in result["error"]


# ---------------------------------------------------------------------------
# should_retry / calculate_backoff
# ---------------------------------------------------------------------------
class TestShouldRetry:
    @pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
    def test_retryable(self, code):
        assert should_retry(code) is True

    @pytest.mark.parametrize("code", [200, 400, 401, 403, 404, 301, 0])
    def test_non_retryable(self, code):
        assert should_retry(code) is False


class TestCalculateBackoff:
    def test_below_one_returns_zero(self):
        assert calculate_backoff(0) == 0.0
        assert calculate_backoff(-5) == 0.0

    def test_sequence(self):
        assert calculate_backoff(1) == 1.0
        assert calculate_backoff(2) == 2.0
        assert calculate_backoff(3) == 4.0
        assert calculate_backoff(4) == 8.0

    def test_capped_at_max(self):
        # attempt 10 -> 2^9 = 512, capped at default 60
        assert calculate_backoff(10) == 60.0
        # custom cap
        assert calculate_backoff(5, max_backoff=10.0) == 10.0
        # cap above actual
        assert calculate_backoff(3, max_backoff=100.0) == 4.0


class TestGlobalInstance:
    def test_global_rate_limiter_exists(self):
        assert rate_limiter is not None
        assert isinstance(rate_limiter, RateLimiter)

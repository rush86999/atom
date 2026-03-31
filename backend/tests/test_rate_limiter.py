"""
Tests for Rate Limiter

Tests rate limiter functionality:
- Rate limiter allows requests within limit
- Rate limiter blocks requests over limit
- Rate limiter resets after window
- Decorator applies rate limiter
- Exponential backoff on rate limit
"""
import asyncio
import pytest
import time
from core.rate_limiter import RateLimiter, rate_limiter_decorator, should_retry, calculate_backoff


@pytest.fixture
def rate_limiter_instance():
    """Create a fresh rate limiter instance for each test"""
    # No Redis for tests (use in-memory)
    rl = RateLimiter(redis_client=None)
    yield rl
    # Reset after test
    asyncio.run(rl.reset())


class TestRateLimiter:
    """Test rate limiter core functionality"""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_within_limit(self, rate_limiter_instance):
        """Test that rate limiter allows requests within the limit"""
        # Make 5 requests (limit is 30 for default, but we'll test with 10)
        for i in range(5):
            is_limited, remaining = await rate_limiter_instance.is_rate_limited(
                "test_integration",
                limit=10,
                window=60
            )
            assert is_limited is False
            assert remaining == (10 - i - 1)

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_requests_over_limit(self, rate_limiter_instance):
        """Test that rate limiter blocks requests over the limit"""
        # Exhaust the limit (10 requests)
        for _ in range(10):
            await rate_limiter_instance.is_rate_limited("test_integration", limit=10, window=60)

        # Next request should be blocked
        is_limited, remaining = await rate_limiter_instance.is_rate_limited(
            "test_integration",
            limit=10,
            window=60
        )
        assert is_limited is True
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_resets_after_window(self, rate_limiter_instance):
        """Test that rate limiter resets after time window expires"""
        # Exhaust the limit (5 requests with 1 second window)
        for _ in range(5):
            await rate_limiter_instance.is_rate_limited("test_integration", limit=5, window=1)

        # Next request should be blocked
        is_limited, _ = await rate_limiter_instance.is_rate_limited(
            "test_integration",
            limit=5,
            window=1
        )
        assert is_limited is True

        # Wait for window to expire
        await asyncio.sleep(1.1)

        # Next request should be allowed (new window)
        is_limited, remaining = await rate_limiter_instance.is_rate_limited(
            "test_integration",
            limit=5,
            window=1
        )
        assert is_limited is False
        assert remaining == 4

    @pytest.mark.asyncio
    async def test_rate_limiter_uses_default_limits(self, rate_limiter_instance):
        """Test that rate limiter uses default limits when no override provided"""
        # Gmail has default limit of 60
        for i in range(60):
            is_limited, _ = await rate_limiter_instance.is_rate_limited("gmail")
            assert is_limited is False, f"Request {i+1} should be allowed"

        # 61st request should be blocked
        is_limited, _ = await rate_limiter_instance.is_rate_limited("gmail")
        assert is_limited is True

    @pytest.mark.asyncio
    async def test_rate_limiter_reset_clears_state(self, rate_limiter_instance):
        """Test that reset clears rate limiter state"""
        # Make some requests
        for _ in range(5):
            await rate_limiter_instance.is_rate_limited("test_integration", limit=10, window=60)

        # Reset
        await rate_limiter_instance.reset("test_integration")

        # Should be able to make requests again
        is_limited, remaining = await rate_limiter_instance.is_rate_limited(
            "test_integration",
            limit=10,
            window=60
        )
        assert is_limited is False
        assert remaining == 9


class TestRateLimiterDecorator:
    """Test rate limiter decorator"""

    @pytest.mark.asyncio
    async def test_decorator_applies_rate_limiter(self):
        """Test that decorator applies rate limiter to function"""
        rl = RateLimiter(redis_client=None)
        call_count = [0]

        @rate_limiter_decorator(integration="test_decorator", limit=3, window=60)
        async def test_function(rate_limiter=rl):
            call_count[0] += 1
            return {"success": True}

        # Call function 3 times (within limit)
        for _ in range(3):
            result = await test_function()
            assert result["success"] is True
            assert call_count[0] == _ + 1

        # 4th call should be blocked
        result = await test_function()
        assert result["success"] is False
        assert "Rate limit exceeded" in result["error"]
        assert call_count[0] == 3  # Function should not have been called

    @pytest.mark.asyncio
    async def test_decorator_allows_within_limit(self):
        """Test that decorator allows calls within rate limit"""
        rl = RateLimiter(redis_client=None)

        @rate_limiter_decorator(integration="test_allow", limit=5, window=60)
        async def test_function(rate_limiter=rl):
            return {"success": True}

        # All 5 calls should succeed
        for _ in range(5):
            result = await test_function()
            assert result["success"] is True


class TestRetryLogic:
    """Test retry logic helper functions"""

    def test_should_retry_with_retryable_codes(self):
        """Test that should_retry returns True for retryable status codes"""
        retryable_codes = [429, 500, 502, 503, 504]
        for code in retryable_codes:
            assert should_retry(code) is True

    def test_should_not_retry_with_non_retryable_codes(self):
        """Test that should_retry returns False for non-retryable status codes"""
        non_retryable_codes = [400, 401, 403, 404, 422]
        for code in non_retryable_codes:
            assert should_retry(code) is False

    def test_calculate_backoff_increments_exponentially(self):
        """Test that backoff increases exponentially"""
        backoff_1 = calculate_backoff(1)
        backoff_2 = calculate_backoff(2)
        backoff_3 = calculate_backoff(3)
        backoff_4 = calculate_backoff(4)

        assert backoff_1 == 1.0
        assert backoff_2 == 2.0
        assert backoff_3 == 4.0
        assert backoff_4 == 8.0

    def test_calculate_backoff_respects_max_backoff(self):
        """Test that backoff is capped at max_backoff"""
        max_backoff = 10.0

        # Without cap, attempt 10 would be 512 seconds
        backoff_10 = calculate_backoff(10, max_backoff=max_backoff)

        assert backoff_10 == max_backoff

    def test_calculate_backoff_returns_zero_for_invalid_attempt(self):
        """Test that backoff returns 0 for invalid attempt numbers"""
        assert calculate_backoff(0) == 0.0
        assert calculate_backoff(-1) == 0.0

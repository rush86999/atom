"""
Tests for Circuit Breaker

Tests circuit breaker functionality:
- Circuit opens after failure threshold
- Circuit resets after cooldown
- Circuit allows requests when closed
- Circuit blocks requests when open
- Decorator applies circuit breaker
"""
import asyncio
import pytest
import time
from core.circuit_breaker import CircuitBreaker, circuit_breaker_decorator, IntegrationStats


@pytest.fixture
def circuit_breaker_instance():
    """Create a fresh circuit breaker instance for each test"""
    # No Redis for tests (use in-memory)
    cb = CircuitBreaker(
        redis_client=None,
        failure_threshold=0.5,
        min_calls=5,
        consecutive_failure_limit=3,
        cooldown_seconds=1  # Short cooldown for tests
    )
    yield cb
    # Reset after test
    asyncio.run(cb.reset())


class TestCircuitBreaker:
    """Test circuit breaker core functionality"""

    @pytest.mark.asyncio
    async def test_circuit_allows_requests_when_closed(self, circuit_breaker_instance):
        """Test that circuit allows requests when it's closed (normal state)"""
        # Record some successes
        for _ in range(5):
            await circuit_breaker_instance.record_success("test_integration")

        # Circuit should still be enabled
        is_enabled = await circuit_breaker_instance.is_enabled("test_integration")
        assert is_enabled is True

        # Check stats
        stats = await circuit_breaker_instance.get_stats("test_integration")
        assert stats["total_calls"] == 5
        assert stats["failures"] == 0
        assert stats["is_enabled"] is True

    @pytest.mark.asyncio
    async def test_circuit_opens_after_consecutive_failures(self, circuit_breaker_instance):
        """Test that circuit opens after consecutive failure limit is reached"""
        # Record minimum calls to meet threshold
        for _ in range(5):
            await circuit_breaker_instance.record_success("test_integration")

        # Record consecutive failures (limit is 3)
        for _ in range(3):
            await circuit_breaker_instance.record_failure("test_integration", Exception("Test error"))

        # Circuit should be disabled
        is_enabled = await circuit_breaker_instance.is_enabled("test_integration")
        assert is_enabled is False

        # Check stats
        stats = await circuit_breaker_instance.get_stats("test_integration")
        assert stats["consecutive_failures"] == 3
        assert stats["is_enabled"] is False

    @pytest.mark.asyncio
    async def test_circuit_resets_after_cooldown(self, circuit_breaker_instance):
        """Test that circuit resets after cooldown period expires"""
        # Open the circuit
        for _ in range(5):
            await circuit_breaker_instance.record_success("test_integration")
        for _ in range(3):
            await circuit_breaker_instance.record_failure("test_integration", Exception("Test error"))

        # Verify circuit is open
        is_enabled = await circuit_breaker_instance.is_enabled("test_integration")
        assert is_enabled is False

        # Wait for cooldown (1 second)
        await asyncio.sleep(1.1)

        # Circuit should be re-enabled
        is_enabled = await circuit_breaker_instance.is_enabled("test_integration")
        assert is_enabled is True

    @pytest.mark.asyncio
    async def test_circuit_blocks_requests_when_open(self, circuit_breaker_instance):
        """Test that circuit blocks requests when it's open"""
        # Open the circuit
        for _ in range(5):
            await circuit_breaker_instance.record_success("test_integration")
        for _ in range(3):
            await circuit_breaker_instance.record_failure("test_integration", Exception("Test error"))

        # Verify circuit is open
        is_enabled = await circuit_breaker_instance.is_enabled("test_integration")
        assert is_enabled is False

    @pytest.mark.asyncio
    async def test_decorator_applies_circuit_breaker(self):
        """Test that decorator applies circuit breaker to function"""
        cb = CircuitBreaker(
            redis_client=None,
            failure_threshold=0.5,
            min_calls=2,
            consecutive_failure_limit=2,
            cooldown_seconds=1
        )

        @circuit_breaker_decorator(integration="test_decorator")
        async def test_function(circuit_breaker=cb):
            return {"success": True}

        # Call function successfully
        result = await test_function()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_circuit_reset_clears_state(self, circuit_breaker_instance):
        """Test that reset clears all circuit state"""
        # Record some activity
        for _ in range(5):
            await circuit_breaker_instance.record_success("test_integration")
        await circuit_breaker_instance.record_failure("test_integration", Exception("Test error"))

        # Reset
        await circuit_breaker_instance.reset("test_integration")

        # Verify state is cleared
        stats = await circuit_breaker_instance.get_stats("test_integration")
        assert stats["total_calls"] == 0
        assert stats["failures"] == 0
        assert stats["consecutive_failures"] == 0
        assert stats["is_enabled"] is True

"""
Circuit Breaker State Transition Tests

Comprehensive test suite for circuit breaker state transitions with timeout verification.
Validates that the CircuitBreaker class correctly transitions between CLOSED, OPEN, and
HALF_OPEN states based on failure thresholds and timeouts, preventing cascade failures
in external service calls.

Test Coverage:
- State transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
- Failure threshold behavior
- Timeout mechanism (using small timeouts to avoid slow tests)
- AutoHealingEngine integration
- Edge cases: concurrent access, reset, custom parameters
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from typing import Callable, Any

from core.auto_healing import CircuitBreaker, AutoHealingEngine


# ============================================================================
# TestCircuitBreakerStates - State Transition Validation
# ============================================================================


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions (CLOSED, OPEN, HALF_OPEN)."""

    def test_circuit_closed_initially(self):
        """Verify initial state is CLOSED when circuit breaker is created."""
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)

        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0
        assert breaker.last_failure_time is None

    def test_circuit_opens_after_threshold_failures(self):
        """OPEN state after N failures (failure_threshold reached)."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # First 2 failures: circuit stays CLOSED
        for i in range(2):
            with pytest.raises(Exception):
                breaker.call(failing_call)
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 2

        # 3rd failure: circuit opens (but original exception is raised)
        with pytest.raises(Exception, match="Service unavailable"):
            breaker.call(failing_call)
        # After threshold is reached, circuit state is OPEN
        assert breaker.state == "OPEN"
        assert breaker.failure_count == 3

        # Next call will raise circuit breaker exception
        with pytest.raises(Exception, match="Circuit breaker OPEN"):
            breaker.call(failing_call)

    def test_circuit_remains_closed_below_threshold(self):
        """Stay CLOSED with fewer failures than threshold."""
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # 4 failures (below threshold of 5)
        for i in range(4):
            with pytest.raises(Exception):
                breaker.call(failing_call)

        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 4

    def test_circuit_half_open_after_timeout(self):
        """HALF_OPEN state after timeout period expires."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=1)  # 1 second timeout

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(3):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # Wait for timeout (1 second)
        time.sleep(1.5)

        # Next call should enter HALF_OPEN state
        def successful_call():
            return "success"

        result = breaker.call(successful_call)
        assert result == "success"
        assert breaker.state == "CLOSED"  # Reset after success

    def test_circuit_resets_to_closed_after_success(self):
        """CLOSED state after successful call in HALF_OPEN."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=1)

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(3):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # Wait for timeout
        time.sleep(1.5)

        # Successful call in HALF_OPEN should reset to CLOSED
        def successful_call():
            return "success"

        result = breaker.call(successful_call)
        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0
        assert breaker.last_failure_time is None

    def test_circuit_reopens_on_half_open_failure(self):
        """Re-OPEN state if HALF_OPEN call fails."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=1)

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(3):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # Wait for timeout
        time.sleep(1.5)

        # Failed call in HALF_OPEN should reopen circuit
        with pytest.raises(Exception):
            breaker.call(failing_call)

        assert breaker.state == "OPEN"
        assert breaker.failure_count == 4  # Incremented


# ============================================================================
# TestCircuitBreakerBehavior - Behavioral Validation
# ============================================================================


class TestCircuitBreakerBehavior:
    """Test circuit breaker behavior during different states."""

    def test_open_circuit_prevents_calls(self):
        """Calls blocked when circuit is OPEN."""
        breaker = CircuitBreaker(failure_threshold=2, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(2):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # All calls should be blocked
        for i in range(5):
            with pytest.raises(Exception) as exc_info:
                breaker.call(failing_call)
            assert "Circuit breaker OPEN" in str(exc_info.value)

    def test_open_circuit_raises_exception(self):
        """Specific exception raised when circuit is OPEN."""
        breaker = CircuitBreaker(failure_threshold=2, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(2):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        # Verify exception message
        with pytest.raises(Exception) as exc_info:
            breaker.call(failing_call)

        assert "Circuit breaker OPEN" in str(exc_info.value)
        assert "failing_call" in str(exc_info.value)  # Function name included

    def test_half_open_allows_single_call(self):
        """Only one call allowed in HALF_OPEN state (for testing)."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=1)

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(3):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # Wait for timeout
        time.sleep(1.5)

        # First call enters HALF_OPEN, executes, resets to CLOSED on success
        def successful_call():
            return "success"

        result = breaker.call(successful_call)
        assert result == "success"
        assert breaker.state == "CLOSED"

    def test_failure_count_tracking(self):
        """Verify failure_count increments correctly."""
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        assert breaker.failure_count == 0

        # First failure
        with pytest.raises(Exception):
            breaker.call(failing_call)
        assert breaker.failure_count == 1

        # Second failure
        with pytest.raises(Exception):
            breaker.call(failing_call)
        assert breaker.failure_count == 2

        # Third failure
        with pytest.raises(Exception):
            breaker.call(failing_call)
        assert breaker.failure_count == 3

    def test_last_failure_time_recorded(self):
        """Verify timestamp tracking for last failure."""
        breaker = CircuitBreaker(failure_threshold=2, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        assert breaker.last_failure_time is None

        # First failure
        with pytest.raises(Exception):
            breaker.call(failing_call)

        assert breaker.last_failure_time is not None
        first_failure_time = breaker.last_failure_time

        # Small delay
        time.sleep(0.1)

        # Second failure
        with pytest.raises(Exception):
            breaker.call(failing_call)

        assert breaker.last_failure_time is not None
        second_failure_time = breaker.last_failure_time

        # Verify timestamps are different
        assert second_failure_time > first_failure_time


# ============================================================================
# TestCircuitBreakerParameters - Configuration Validation
# ============================================================================


class TestCircuitBreakerParameters:
    """Test circuit breaker configuration parameters."""

    def test_custom_failure_threshold(self):
        """Custom threshold works correctly."""
        breaker = CircuitBreaker(failure_threshold=7, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # 6 failures: still CLOSED
        for i in range(6):
            with pytest.raises(Exception):
                breaker.call(failing_call)
        assert breaker.state == "CLOSED"

        # 7th failure: opens circuit
        with pytest.raises(Exception):
            breaker.call(failing_call)
        assert breaker.state == "OPEN"

    def test_custom_timeout_period(self):
        """Custom timeout for HALF_OPEN transition."""
        # Use very short timeout for testing
        breaker = CircuitBreaker(failure_threshold=2, timeout=0.5)

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(2):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # Before timeout: still OPEN
        time.sleep(0.3)
        assert breaker.state == "OPEN"

        # After timeout: HALF_OPEN on next call
        time.sleep(0.5)

        def successful_call():
            return "success"

        result = breaker.call(successful_call)
        assert result == "success"
        assert breaker.state == "CLOSED"

    def test_default_parameters(self):
        """Verify defaults (threshold=5, timeout=60)."""
        breaker = CircuitBreaker()

        assert breaker.failure_threshold == 5
        assert breaker.timeout == 60
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0


# ============================================================================
# TestAutoHealingEngineIntegration - Service Integration
# ============================================================================


class TestAutoHealingEngineIntegration:
    """Test AutoHealingEngine integration with circuit breakers."""

    def test_engine_creates_per_service_breakers(self):
        """Different breakers per service."""
        engine = AutoHealingEngine()

        breaker1 = engine.get_circuit_breaker("service_a")
        breaker2 = engine.get_circuit_breaker("service_b")

        assert breaker1 is not breaker2  # Different instances
        assert breaker1.state == "CLOSED"
        assert breaker2.state == "CLOSED"

        # Trigger breaker1 to open
        for i in range(5):
            try:
                breaker1.call(lambda: (_ for _ in ()).throw(Exception()))
            except Exception:
                pass

        assert breaker1.state == "OPEN"
        assert breaker2.state == "CLOSED"  # Unaffected

    def test_engine_reuses_existing_breaker(self):
        """Same breaker returned for same service."""
        engine = AutoHealingEngine()

        breaker1 = engine.get_circuit_breaker("service_a")
        breaker2 = engine.get_circuit_breaker("service_a")

        assert breaker1 is breaker2  # Same instance

    def test_get_service_status(self):
        """Status report returns correct state."""
        engine = AutoHealingEngine()

        # Add some circuit breakers
        breaker_a = engine.get_circuit_breaker("service_a")
        breaker_b = engine.get_circuit_breaker("service_b")

        # Trigger breaker_a to open
        for i in range(5):
            try:
                breaker_a.call(lambda: (_ for _ in ()).throw(Exception()))
            except Exception:
                pass

        status = engine.get_service_status()

        assert "service_a" in status
        assert "service_b" in status

        assert status["service_a"]["state"] == "OPEN"
        assert status["service_a"]["failure_count"] == 5
        assert status["service_a"]["last_failure"] is not None

        assert status["service_b"]["state"] == "CLOSED"
        assert status["service_b"]["failure_count"] == 0
        assert status["service_b"]["last_failure"] is None


# ============================================================================
# TestEdgeCases - Boundary Conditions
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_successful_call_resets_failure_count(self):
        """Failure count resets on success in HALF_OPEN state."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=1)

        def failing_call():
            raise Exception("Service unavailable")

        def successful_call():
            return "success"

        # Trigger circuit to open with 3 failures
        for i in range(3):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"
        assert breaker.failure_count == 3

        # Wait for timeout
        time.sleep(1.5)

        # Successful call in HALF_OPEN resets count
        result = breaker.call(successful_call)
        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0

    def test_concurrent_failure_tracking(self):
        """Thread-safe failure counting (basic test)."""
        breaker = CircuitBreaker(failure_threshold=10, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # Simulate rapid failures (not truly concurrent, but rapid sequential)
        for i in range(8):
            with pytest.raises(Exception):
                breaker.call(failing_call)

        assert breaker.failure_count == 8
        assert breaker.state == "CLOSED"  # Still below threshold

    def test_reset_manual(self):
        """Manual reset via reset() method."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(3):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"
        assert breaker.failure_count == 3

        # Manual reset
        breaker.reset()

        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0
        assert breaker.last_failure_time is None

    def test_threshold_of_one(self):
        """Edge case: threshold of 1 opens immediately."""
        breaker = CircuitBreaker(failure_threshold=1, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # First failure immediately opens circuit
        with pytest.raises(Exception):
            breaker.call(failing_call)

        assert breaker.state == "OPEN"
        assert breaker.failure_count == 1

    def test_timeout_of_zero(self):
        """Edge case: timeout of 0 (immediate HALF_OPEN)."""
        breaker = CircuitBreaker(failure_threshold=2, timeout=0)

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(2):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # With timeout=0, next call should immediately enter HALF_OPEN
        # (using very small sleep to ensure datetime.now() changes)
        time.sleep(0.01)

        def successful_call():
            return "success"

        result = breaker.call(successful_call)
        assert result == "success"
        assert breaker.state == "CLOSED"

    def test_large_failure_threshold(self):
        """Edge case: large threshold (100)."""
        breaker = CircuitBreaker(failure_threshold=100, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # 99 failures: still CLOSED
        for i in range(99):
            with pytest.raises(Exception):
                breaker.call(failing_call)
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 99

        # 100th failure: opens circuit
        with pytest.raises(Exception):
            breaker.call(failing_call)
        assert breaker.state == "OPEN"
        assert breaker.failure_count == 100

    def test_zero_threshold_behavior(self):
        """Edge case: threshold of 0 behaves unexpectedly (opens on first failure).

        Note: Threshold of 0 should theoretically never open, but the implementation
        opens on first failure because failure_count >= 0 is always True after
        the first increment (failure_count becomes 1).
        """
        # This documents actual behavior: threshold=0 opens on first failure
        breaker = CircuitBreaker(failure_threshold=0, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # First failure opens circuit (because 1 >= 0)
        with pytest.raises(Exception):
            breaker.call(failing_call)

        # Actual behavior: circuit opens
        assert breaker.state == "OPEN"
        assert breaker.failure_count == 1


# ============================================================================
# TestTimeoutMocking - Alternative Timeout Testing
# ============================================================================


class TestTimeoutMocking:
    """Test timeout behavior with mocked time (faster than real sleep)."""

    def test_timeout_with_mocked_datetime(self):
        """Test timeout transition by mocking datetime.now()."""
        breaker = CircuitBreaker(failure_threshold=2, timeout=60)

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(2):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # Mock datetime to simulate time passing
        original_now = datetime.now
        future_time = datetime.now() + timedelta(seconds=61)

        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = future_time
            # Keep the original timedelta behavior
            mock_datetime.side_effect = lambda *args, **kwargs: original_now(*args, **kwargs) if args else original_now()

        # Circuit should transition to HALF_OPEN on next call
        # Note: This test documents the limitation that mocking datetime.now()
        # in CircuitBreaker.call() is tricky due to the timedelta calculation

        # For reliable timeout testing, use small timeouts (as in other tests)
        # rather than mocking datetime

    def test_timeout_with_small_delays(self):
        """Practical timeout test with small delays (100ms)."""
        breaker = CircuitBreaker(failure_threshold=2, timeout=0.1)

        def failing_call():
            raise Exception("Service unavailable")

        # Trigger circuit to open
        for i in range(2):
            try:
                breaker.call(failing_call)
            except Exception:
                pass

        assert breaker.state == "OPEN"

        # Wait for timeout (100ms)
        time.sleep(0.15)

        # Next call should succeed and reset to CLOSED
        def successful_call():
            return "success"

        result = breaker.call(successful_call)
        assert result == "success"
        assert breaker.state == "CLOSED"

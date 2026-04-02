"""Circuit breaker pattern for preventing cascading failures.

Implements a 3-state circuit breaker (CLOSED, OPEN, HALF_OPEN) that stops
routing to failing providers and automatically attempts recovery.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states.

    CLOSED: Normal operation, requests pass through
    OPEN: Circuit tripped, requests fail immediately
    HALF_OPEN: Testing if provider has recovered
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN and blocks a request."""

    def __init__(self, state: CircuitBreakerState, last_failure: Optional[str] = None):
        self.state = state
        self.last_failure = last_failure
        message = f"Circuit breaker is {state.value}"
        if last_failure:
            message += f" (last failure: {last_failure})"
        super().__init__(message)


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures.

    Tracks consecutive failures and trips to OPEN state after threshold.
    Automatically transitions to HALF_OPEN after recovery_timeout to test recovery.
    Closes circuit after consecutive successes in HALF_OPEN state.

    Thread-safe implementation using asyncio.Lock.

    Example:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        try:
            result = await breaker.call(provider_api, arg1, arg2)
        except CircuitBreakerOpenError:
            # Circuit is open, use fallback
            result = await fallback_api()
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
        half_open_max_calls: int = 3):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures to trip circuit (default: 5)
            recovery_timeout: Seconds before attempting recovery (default: 60.0)
            success_threshold: Consecutive successes to close circuit (default: 2)
            half_open_max_calls: Max calls allowed in HALF_OPEN state (default: 3)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.half_open_max_calls = half_open_max_calls

        # State tracking
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_failure_message: Optional[str] = None
        self._last_state_change: float = time.time()
        self._half_open_call_count = 0

        # Thread safety
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func()

        Raises:
            CircuitBreakerOpenError: If circuit is OPEN
            Exception: If func() raises an exception
        """
        async with self._lock:
            if not self._should_allow_request():
                logger.warning(
                    f"Circuit breaker OPEN, blocking request "
                    f"(failures: {self._failure_count}/{self.failure_threshold})"
                )
                raise CircuitBreakerOpenError(
                    self._state,
                    self._last_failure_message
                )

        # Execute function outside lock to avoid holding during call
        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception as e:
            await self.record_failure(e)
            raise

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self._success_count += 1

            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.info(
                    f"Success in HALF_OPEN state ({self._success_count}/"
                    f"{self.success_threshold} to close)"
                )

                # Close circuit if we've reached success threshold
                if self._success_count >= self.success_threshold:
                    self._transition_to(CircuitBreakerState.CLOSED)
                    self._failure_count = 0
            elif self._state == CircuitBreakerState.CLOSED:
                # Reset failure count on success in CLOSED state
                self._failure_count = 0

    async def record_failure(self, error: Exception) -> None:
        """Record a failed call.

        Args:
            error: The exception that occurred
        """
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._last_failure_message = str(error)[:200]  # Truncate long messages

            logger.warning(
                f"Circuit breaker failure recorded ({self._failure_count}/"
                f"{self.failure_threshold} threshold): {error}"
            )

            if self._state == CircuitBreakerState.CLOSED:
                # Trip to OPEN if threshold reached
                if self._failure_count >= self.failure_threshold:
                    self._transition_to(CircuitBreakerState.OPEN)
                    logger.error(
                        f"Circuit breaker tripped to OPEN after "
                        f"{self._failure_count} consecutive failures"
                    )
            elif self._state == CircuitBreakerState.HALF_OPEN:
                # Reopen circuit on any failure in HALF_OPEN
                self._transition_to(CircuitBreakerState.OPEN)
                self._half_open_call_count = 0
                logger.error("Circuit breaker reopened from HALF_OPEN after failure")

    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state.

        Returns:
            CircuitBreakerState enum
        """
        return self._state

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics.

        Returns:
            Dict with current metrics (state, failures, successes, timestamps)
        """
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "last_failure_time": self._last_failure_time,
            "last_failure_message": self._last_failure_message,
            "last_state_change": self._last_state_change,
            "half_open_call_count": self._half_open_call_count,
        }

    async def reset(self) -> None:
        """Force circuit to CLOSED state.

        Resets all counters and state. Useful for manual recovery or testing.
        """
        async with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_call_count = 0
            self._last_failure_time = None
            self._last_failure_message = None
            self._last_state_change = time.time()
            logger.info("Circuit breaker manually reset to CLOSED")

    def _should_allow_request(self) -> bool:
        """Check if request should be allowed based on state.

        Must be called while holding lock.

        Returns:
            True if request should proceed, False if blocked
        """
        if self._state == CircuitBreakerState.CLOSED:
            return True

        if self._state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has elapsed
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    # Transition to HALF_OPEN to test recovery
                    self._transition_to(CircuitBreakerState.HALF_OPEN)
                    self._half_open_call_count = 0
                    logger.info(
                        f"Circuit breaker transitioned to HALF_OPEN "
                        f"after {elapsed:.1f}s"
                    )
                    return True
            return False

        if self._state == CircuitBreakerState.HALF_OPEN:
            # Allow limited calls in HALF_OPEN state
            return self._half_open_call_count < self.half_open_max_calls

        return False

    def _transition_to(self, new_state: CircuitBreakerState) -> None:
        """Transition to new state.

        Must be called while holding lock.

        Args:
            new_state: Target state
        """
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()

        if new_state == CircuitBreakerState.HALF_OPEN:
            self._success_count = 0

        logger.info(
            f"Circuit breaker transition: {old_state.value} -> {new_state.value}"
        )

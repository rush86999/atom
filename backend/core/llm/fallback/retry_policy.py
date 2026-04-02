"""Retry policy with exponential backoff for resilient LLM operations.

Implements intelligent retry logic with exponential backoff and jitter
to handle transient errors while preventing thundering herd problems.
"""

import asyncio
import logging
import random
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)


class RetryableError(Enum):
    """Types of errors that should trigger retries.

    RATE_LIMIT: HTTP 429 (rate limit exceeded)
    TIMEOUT: Request timeout
    SERVER_ERROR: HTTP 5xx (server errors)
    NETWORK_ERROR: Connection errors
    RETRYABLE: Explicitly marked for retry
    """
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    RETRYABLE = "retryable"


class ExponentialBackoffStrategy:
    """Exponential backoff with jitter for retry delays.

    Calculates delays using: initial_delay * base^attempt + jitter
    Jitter is ±25% of calculated delay to prevent thundering herd.

    Example:
        strategy = ExponentialBackoffStrategy(
            max_retries=3,
            initial_delay=1.0,
            max_delay=60.0,
            jitter=True
        )

        # Delays: ~1.0s, ~2.0s, ~4.0s (with jitter)
        for attempt in range(3):
            delay = strategy.get_delay(attempt)
            print(f"Attempt {attempt}: {delay:.2f}s delay")
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True):
        """Initialize exponential backoff strategy.

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            initial_delay: Initial delay in seconds (default: 1.0)
            max_delay: Maximum delay cap in seconds (default: 60.0)
            exponential_base: Multiplier for each attempt (default: 2.0)
            jitter: Add random jitter to prevent thundering herd (default: True)
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Calculate exponential backoff
        delay = self.initial_delay * (self.exponential_base ** attempt)

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter if enabled
        if self.jitter:
            delay = self._add_jitter(delay)

        return delay

    async def sleep_with_backoff(self, attempt: int) -> None:
        """Async sleep with calculated backoff delay.

        Args:
            attempt: Attempt number (0-indexed)
        """
        delay = self.get_delay(attempt)
        logger.debug(f"Backing off for {delay:.2f}s before attempt {attempt + 1}")
        await asyncio.sleep(delay)

    def _add_jitter(self, delay: float) -> float:
        """Add random jitter to delay (±25%).

        Args:
            delay: Base delay in seconds

        Returns:
            Delay with jitter applied
        """
        # Jitter: ±25% of delay
        jitter_range = delay * 0.25
        jitter = random.uniform(-jitter_range, jitter_range)
        return delay + jitter


class RetryPolicy:
    """Retry policy with exponential backoff for resilient operations.

    Executes functions with configurable retry logic for transient errors.
    Classifies exceptions and applies backoff strategy for retryable errors.

    Example:
        strategy = ExponentialBackoffStrategy(max_retries=3, jitter=True)
        policy = RetryPolicy(
            strategy=strategy,
            retryable_errors={
                RetryableError.TIMEOUT,
                RetryableError.RATE_LIMIT,
                RetryableError.SERVER_ERROR,
            }
        )

        try:
            result = await policy.execute(provider_api, arg1, arg2)
        except Exception as e:
            # All retries exhausted
            logger.error(f"Failed after {policy.max_retries} retries: {e}")
    """

    def __init__(
        self,
        strategy: ExponentialBackoffStrategy,
        retryable_errors: Optional[Set[RetryableError]] = None):
        """Initialize retry policy.

        Args:
            strategy: Exponential backoff strategy
            retryable_errors: Set of retryable error types (default: all except RETRYABLE)
        """
        self.strategy = strategy
        self.retryable_errors = retryable_errors or {
            RetryableError.RATE_LIMIT,
            RetryableError.TIMEOUT,
            RetryableError.SERVER_ERROR,
            RetryableError.NETWORK_ERROR,
        }

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func()

        Raises:
            Exception: Last exception if all retries exhausted
        """
        last_exception = None

        for attempt in range(self.strategy.max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(
                        f"Retry attempt {attempt}/{self.strategy.max_retries} "
                        f"after {self.strategy.get_delay(attempt - 1):.2f}s delay"
                    )

                result = await func(*args, **kwargs)

                if attempt > 0:
                    logger.info(f"Success on attempt {attempt}")

                return result

            except Exception as e:
                last_exception = e

                # Check if error is retryable
                if not self.is_retryable(e):
                    logger.warning(f"Non-retryable error: {e}")
                    raise

                # Check if we should retry
                if attempt < self.strategy.max_retries:
                    retryable_type = self._map_exception_to_error(e)
                    logger.warning(
                        f"Retryable error ({retryable_type.value if retryable_type else 'unknown'}): {e}"
                    )

                    # Sleep with backoff before next attempt
                    await self.strategy.sleep_with_backoff(attempt)
                else:
                    logger.error(
                        f"All {self.strategy.max_retries} retry attempts exhausted"
                    )

        # All retries exhausted, raise last exception
        raise last_exception

    def is_retryable(self, error: Exception) -> bool:
        """Check if error should trigger retry.

        Args:
            error: Exception to check

        Returns:
            True if error is retryable
        """
        retryable_type = self._map_exception_to_error(error)
        return retryable_type in self.retryable_errors

    def _map_exception_to_error(self, error: Exception) -> Optional[RetryableError]:
        """Map exception to RetryableError type.

        Args:
            error: Exception to classify

        Returns:
            RetryableError type or None
        """
        error_message = str(error).lower()
        error_type = type(error).__name__.lower()

        # Check for rate limit errors
        if "429" in error_message or "rate" in error_message:
            return RetryableError.RATE_LIMIT

        # Check for timeout errors
        if "timeout" in error_message or "timed out" in error_message:
            return RetryableError.TIMEOUT

        # Check for server errors (5xx)
        if any(code in error_message for code in ["500", "502", "503", "504"]):
            return RetryableError.SERVER_ERROR

        # Check for network errors
        if any(term in error_message or term in error_type for term in
               ["connection", "network", "dns", "unreachable", "refused"]):
            return RetryableError.NETWORK_ERROR

        # Check if explicitly marked as retryable
        if hasattr(error, "retryable") and getattr(error, "retryable"):
            return RetryableError.RETRYABLE

        return None

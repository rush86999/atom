"""Fallback systems for resilient LLM operations.

This module provides circuit breaker and retry policy patterns to prevent
cascading failures and enable graceful degradation when providers are unhealthy.
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerOpenError)
from .retry_policy import (
    RetryPolicy,
    ExponentialBackoffStrategy,
    RetryableError)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerState",
    "CircuitBreakerOpenError",
    "RetryPolicy",
    "ExponentialBackoffStrategy",
    "RetryableError",
]

"""
Auto-Healing Engine

Provides decorators and utilities for:
- Automatic retries with exponential backoff
- Circuit breaker pattern for failing services
- Error classification and handling
"""

import asyncio
import functools
import logging
import time
from typing import Callable, Any, Type, Union, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open"""
    pass

class CircuitBreaker:
    """
    Circuit Breaker pattern implementation.
    Prevents cascading failures by stopping requests to a failing service.
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN

    def record_failure(self):
        """Record a failure and potentially open the circuit"""
        self.failures += 1
        self.last_failure_time = datetime.now()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker OPENED after {self.failures} failures")

    def record_success(self):
        """Record a success and reset the circuit"""
        self.failures = 0
        self.state = "CLOSED"
        self.last_failure_time = None

    def allow_request(self) -> bool:
        """Check if request should be allowed"""
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = "HALF-OPEN"
                logger.info("Circuit breaker HALF-OPEN - testing service recovery")
                return True
            return False
            
        if self.state == "HALF-OPEN":
            # Allow one request to test recovery
            return True
            
        return True

# Global registry of circuit breakers by service name
_circuit_breakers = {}

def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker()
    return _circuit_breakers[service_name]

def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exceptions: tuple = (Exception,),
    service_name: Optional[str] = None
):
    """
    Decorator for async functions to add retry logic and circuit breaker.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Tuple of exceptions to catch and retry
        service_name: Name of service for circuit breaker (optional)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Check circuit breaker if service name provided
            if service_name:
                cb = get_circuit_breaker(service_name)
                if not cb.allow_request():
                    logger.warning(f"Circuit breaker open for {service_name}, skipping request")
                    raise CircuitBreakerOpen(f"Service {service_name} is currently unavailable")

            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    if service_name:
                        get_circuit_breaker(service_name).record_success()
                    return result
                except exceptions as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {str(e)}")
                    
                    if service_name:
                        get_circuit_breaker(service_name).record_failure()
                    
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
                        raise last_exception
        return wrapper
    return decorator

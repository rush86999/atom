"""
Resource Guards - Timeouts and limits for integrations
"""
import asyncio
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class IntegrationTimeoutError(Exception):
    """Raised when an integration operation times out"""
    pass


class ResourceGuard:
    """Enforces resource limits on integration operations"""
    
    @staticmethod
    async def with_timeout(coro, timeout_sec: int = 10, operation_name: str = "operation"):
        """
        Execute coroutine with timeout
        
        Args:
            coro: Coroutine to execute
            timeout_sec: Timeout in seconds
            operation_name: Name for logging
            
        Returns:
            Result of coroutine
            
        Raises:
            IntegrationTimeoutError: If timeout exceeded
        """
        try:
            return await asyncio.wait_for(coro, timeout=timeout_sec)
        except asyncio.TimeoutError:
            logger.error(f"Timeout: {operation_name} exceeded {timeout_sec}s")
            raise IntegrationTimeoutError(f"{operation_name} timeout after {timeout_sec}s")
    
    @staticmethod
    def timeout_decorator(timeout_sec: int = 10):
        """
        Decorator to add timeout to async functions
        
        Usage:
            @ResourceGuard.timeout_decorator(5)
            async def my_function():
                ...
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await ResourceGuard.with_timeout(
                    func(*args, **kwargs),
                    timeout_sec=timeout_sec,
                    operation_name=func.__name__
                )
            return wrapper
        return decorator
    
    @staticmethod
    async def with_retry(
        coro_func: Callable,
        max_retries: int = 3,
        backoff_sec: float = 1.0,
        operation_name: str = "operation"
    ) -> Any:
        """
        Execute coroutine with retry logic
        
        Args:
            coro_func: Function that returns a coroutine
            max_retries: Maximum number of retries
            backoff_sec: Seconds to wait between retries (exponential)
            operation_name: Name for logging
            
        Returns:
            Result of coroutine
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return await coro_func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = backoff_sec * (2 ** attempt)
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"{operation_name} failed after {max_retries} attempts: {e}"
                    )
        
        raise last_exception


class MemoryGuard:
    """Monitor and limit memory usage"""
    
    @staticmethod
    def get_memory_usage_mb() -> float:
        """Get current process memory usage in MB"""
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            logger.warning("psutil not installed, cannot monitor memory")
            return 0.0
    
    @staticmethod
    def check_memory_limit(max_mb: int = 1024) -> bool:
        """
        Check if memory usage is within limit
        
        Args:
            max_mb: Maximum memory in MB
            
        Returns:
            True if within limit, False otherwise
        """
        current_mb = MemoryGuard.get_memory_usage_mb()
        if current_mb > max_mb:
            logger.warning(f"Memory usage {current_mb:.1f}MB exceeds limit {max_mb}MB")
            return False
        return True

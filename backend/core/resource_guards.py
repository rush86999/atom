"""
Resource Guards - Timeouts and limits for integrations
"""
import asyncio
from functools import wraps
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class IntegrationTimeoutError(Exception):
    """Raised when an integration operation times out"""

    def __init__(self, message: str, timeout_seconds: float = 0, operation: str = ""):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
        self.operation = operation
        self.message = message


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
            import os
            import psutil
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


class CPUGuard:
    """Monitor and limit CPU usage"""

    @staticmethod
    def get_cpu_usage_percent(interval: float = 0.1) -> float:
        """
        Get current process CPU usage as percentage

        Args:
            interval: Time interval to measure CPU usage

        Returns:
            CPU usage percentage (0-100)
        """
        try:
            import os
            import psutil
            process = psutil.Process(os.getpid())
            return process.cpu_percent(interval=interval)
        except ImportError:
            logger.warning("psutil not installed, cannot monitor CPU")
            return 0.0
        except Exception as e:
            logger.warning(f"Failed to get CPU usage: {e}")
            return 0.0

    @staticmethod
    def check_cpu_limit(max_percent: float = 80.0) -> bool:
        """
        Check if CPU usage is within limit

        Args:
            max_percent: Maximum CPU usage percentage

        Returns:
            True if within limit, False otherwise
        """
        current_percent = CPUGuard.get_cpu_usage_percent()
        if current_percent > max_percent:
            logger.warning(f"CPU usage {current_percent:.1f}% exceeds limit {max_percent}%")
            return False
        return True


class DiskSpaceGuard:
    """Monitor disk space usage"""

    @staticmethod
    def get_available_disk_mb(path: str = "/") -> float:
        """
        Get available disk space in MB

        Args:
            path: Path to check disk space for

        Returns:
            Available disk space in MB
        """
        try:
            import psutil
            disk = psutil.disk_usage(path)
            return disk.free / 1024 / 1024
        except ImportError:
            logger.warning("psutil not installed, cannot monitor disk space")
            return 0.0
        except Exception as e:
            logger.warning(f"Failed to get disk space: {e}")
            return 0.0

    @staticmethod
    def check_disk_space(min_free_mb: float = 1024) -> bool:
        """
        Check if disk space is above minimum

        Args:
            min_free_mb: Minimum required free disk space in MB

        Returns:
            True if enough space, False otherwise
        """
        available_mb = DiskSpaceGuard.get_available_disk_mb()
        if available_mb < min_free_mb:
            logger.warning(f"Available disk space {available_mb:.1f}MB below minimum {min_free_mb}MB")
            return False
        return True


class ConnectionPoolGuard:
    """Monitor and limit database/API connection pool usage"""

    @staticmethod
    def check_pool_limit(pool, max_connections: int = 100) -> bool:
        """
        Check if connection pool is within limits

        Args:
            pool: SQLAlchemy connection pool or similar
            max_connections: Maximum allowed connections

        Returns:
            True if within limit, False otherwise
        """
        try:
            # Try to get pool size for SQLAlchemy engine
            if hasattr(pool, 'pool'):
                active = pool.pool.status().checkout_count
            elif hasattr(pool, 'size'):
                active = pool.size()
            else:
                logger.warning("Cannot determine pool size")
                return True

            if active > max_connections:
                logger.warning(f"Connection pool {active} exceeds limit {max_connections}")
                return False
            return True

        except Exception as e:
            logger.warning(f"Failed to check connection pool: {e}")
            return True


class RateLimiter:
    """Rate limiting for API calls and operations"""

    def __init__(self, max_calls: int = 100, time_window_seconds: int = 60):
        """
        Initialize rate limiter

        Args:
            max_calls: Maximum number of calls allowed
            time_window_seconds: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window_seconds = time_window_seconds
        self.calls = []

    def check_rate_limit(self) -> bool:
        """
        Check if call is within rate limit

        Returns:
            True if within limit, False if rate limited
        """
        import time

        current_time = time.time()

        # Remove old calls outside time window
        self.calls = [call_time for call_time in self.calls
                      if current_time - call_time < self.time_window_seconds]

        if len(self.calls) >= self.max_calls:
            logger.warning(f"Rate limit exceeded: {len(self.calls)} calls in {self.time_window_seconds}s")
            return False

        self.calls.append(current_time)
        return True

    def get_remaining_calls(self) -> int:
        """Get number of remaining calls in current time window"""
        import time
        current_time = time.time()
        self.calls = [call_time for call_time in self.calls
                      if current_time - call_time < self.time_window_seconds]
        return max(0, self.max_calls - len(self.calls))

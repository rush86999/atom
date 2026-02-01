"""
Performance Optimization Utilities for ATOM Platform
Provides caching, memoization, and performance monitoring utilities
"""

import functools
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata"""

    value: Any
    created_at: float
    expires_at: float
    access_count: int = 0
    last_accessed: float = None

    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at


class LRUCache:
    """
    Least Recently Used cache with TTL support
    Thread-safe implementation
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, returns None if not found or expired"""
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check if expired
            if time.time() > entry.expires_at:
                del self._cache[key]
                return None

            # Update access metadata
            entry.access_count += 1
            entry.last_accessed = time.time()

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        with self._lock:
            current_time = time.time()
            ttl = ttl or self.default_ttl

            entry = CacheEntry(
                value=value,
                created_at=current_time,
                expires_at=current_time + ttl,
                last_accessed=current_time,
            )

            # If key exists, remove it first
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self.max_size:
                # Remove least recently used item
                self._cache.popitem(last=False)

            self._cache[key] = entry

    def delete(self, key: str) -> bool:
        """Delete key from cache, returns True if key was present"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()

    def cleanup_expired(self) -> int:
        """Remove expired entries, returns number of removed entries"""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if current_time > entry.expires_at
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            current_time = time.time()
            total_size = len(self._cache)
            expired_count = sum(
                1 for entry in self._cache.values() if current_time > entry.expires_at
            )
            total_accesses = sum(entry.access_count for entry in self._cache.values())

            return {
                "total_entries": total_size,
                "expired_entries": expired_count,
                "max_size": self.max_size,
                "total_accesses": total_accesses,
                "memory_usage_estimate": total_size * 100,  # Rough estimate
            }


def memoize(ttl: Optional[int] = None, max_size: int = 1000):
    """
    Memoization decorator with TTL and cache size limits
    """
    cache = LRUCache(max_size=max_size, default_ttl=ttl or 300)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Create cache key from function name and arguments
            cache_key = (
                f"{func.__module__}.{func.__name__}:{args}:{frozenset(kwargs.items())}"
            )

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Compute and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        # Add cache management methods to wrapper
        wrapper.clear_cache = cache.clear
        wrapper.cache_stats = cache.stats
        wrapper.cache_cleanup = cache.cleanup_expired

        return wrapper

    return decorator


class PerformanceMonitor:
    """
    Performance monitoring and metrics collection
    """

    def __init__(self):
        self._metrics: Dict[str, list] = {}
        self._lock = threading.RLock()

    def record_metric(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ):
        """Record a performance metric"""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = []

            metric_entry = {
                "value": value,
                "timestamp": datetime.utcnow(),
                "tags": tags or {},
            }
            self._metrics[name].append(metric_entry)

            # Keep only last 1000 entries per metric
            if len(self._metrics[name]) > 1000:
                self._metrics[name] = self._metrics[name][-1000:]

    def time_function(
        self, func: Callable[..., T], metric_name: Optional[str] = None
    ) -> Callable[..., T]:
        """Decorator to time function execution"""
        metric_name = metric_name or f"function.{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def timed_wrapper(*args, **kwargs) -> T:
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                duration_ms = (end_time - start_time) * 1000
                self.record_metric(metric_name, duration_ms)

        return timed_wrapper

    def get_metrics_summary(self, name: str, window_minutes: int = 5) -> Dict[str, Any]:
        """Get summary statistics for a metric over time window"""
        with self._lock:
            if name not in self._metrics:
                return {}

            cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
            recent_metrics = [
                m for m in self._metrics[name] if m["timestamp"] >= cutoff_time
            ]

            if not recent_metrics:
                return {}

            values = [m["value"] for m in recent_metrics]
            return {
                "count": len(values),
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "p95": sorted(values)[int(len(values) * 0.95)],
                "p99": sorted(values)[int(len(values) * 0.99)],
                "window_minutes": window_minutes,
            }

    def clear_metrics(self, name: Optional[str] = None):
        """Clear metrics, optionally for a specific name"""
        with self._lock:
            if name:
                if name in self._metrics:
                    del self._metrics[name]
            else:
                self._metrics.clear()


class QueryOptimizer:
    """
    Database query optimization utilities
    """

    @staticmethod
    def optimize_select_query(
        table: str,
        columns: list,
        filters: Dict[str, Any],
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
    ) -> Tuple[str, list]:
        """
        Optimize SELECT query construction
        Returns (query, parameters)
        """
        # Select specific columns instead of *
        column_list = ", ".join(columns) if columns else "*"

        # Build WHERE clause
        where_clauses = []
        parameters = []
        for column, value in filters.items():
            if value is not None:
                where_clauses.append(f"{column} = ?")
                parameters.append(value)

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Build ORDER BY clause
        order_clause = f"ORDER BY {order_by}" if order_by else ""

        # Build LIMIT clause
        limit_clause = f"LIMIT {limit}" if limit else ""

        query = f"SELECT {column_list} FROM {table} {where_clause} {order_clause} {limit_clause}".strip()

        return query, parameters

    @staticmethod
    def batch_operations(operations: list, batch_size: int = 100) -> list:
        """
        Split operations into batches for better performance
        """
        return [
            operations[i : i + batch_size]
            for i in range(0, len(operations), batch_size)
        ]


class BundleOptimizer:
    """
    Frontend bundle optimization utilities
    """

    @staticmethod
    def analyze_bundle_dependencies(dependencies: Dict[str, str]) -> Dict[str, Any]:
        """
        Analyze npm dependencies for optimization opportunities
        """
        large_packages = []
        duplicate_dependencies = []
        outdated_packages = []

        # Common large packages that could be lazy-loaded
        large_package_patterns = [
            "react-",
            "chart",
            "map",
            "editor",
            "pdf",
            "spreadsheet",
            "video",
            "audio",
            "3d",
            "graph",
            "visualization",
        ]

        for package, version in dependencies.items():
            # Check for large packages
            if any(pattern in package.lower() for pattern in large_package_patterns):
                large_packages.append(
                    {
                        "package": package,
                        "version": version,
                        "suggestion": "Consider lazy loading",
                    }
                )

            # Check for common duplication patterns
            if any(
                package.startswith(prefix)
                for prefix in ["@types/", "eslint-", "babel-"]
            ):
                duplicate_dependencies.append(
                    {
                        "package": package,
                        "version": version,
                        "suggestion": "Check for duplicate type definitions",
                    }
                )

        return {
            "total_dependencies": len(dependencies),
            "large_packages": large_packages,
            "duplicate_dependencies": duplicate_dependencies,
            "optimization_suggestions": [
                "Use dynamic imports for large packages",
                "Implement code splitting for routes",
                "Tree-shake unused code",
                "Compress assets and enable gzip",
            ],
        }

    @staticmethod
    def generate_optimization_config() -> Dict[str, Any]:
        """
        Generate Next.js optimization configuration
        """
        return {
            "compression": True,
            "minification": True,
            "treeShaking": True,
            "codeSplitting": True,
            "lazyLoading": True,
            "imageOptimization": True,
            "fontOptimization": True,
        }


# Global performance monitor instance
performance_monitor = PerformanceMonitor()

# Global cache instances
api_cache = LRUCache(max_size=2000, default_ttl=300)  # API responses
integration_cache = LRUCache(max_size=1000, default_ttl=600)  # Integration data
user_session_cache = LRUCache(max_size=5000, default_ttl=1800)  # User sessions


def track_performance(metric_name: Optional[str] = None):
    """
    Decorator to track function performance
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        return performance_monitor.time_function(func, metric_name)

    return decorator


def get_performance_summary() -> Dict[str, Any]:
    """
    Get overall performance summary
    """
    summary = {}

    # API performance
    api_perf = performance_monitor.get_metrics_summary("api.request_duration")
    if api_perf:
        summary["api"] = api_perf

    # Database performance
    db_perf = performance_monitor.get_metrics_summary("database.query_duration")
    if db_perf:
        summary["database"] = db_perf

    # Cache performance
    summary["cache"] = {
        "api_cache": api_cache.stats(),
        "integration_cache": integration_cache.stats(),
        "user_session_cache": user_session_cache.stats(),
    }

    return summary


# Initialize performance monitoring on module import
performance_monitor.record_metric("system.startup_time", time.perf_counter())

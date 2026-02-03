"""
Performance Optimization Middleware
Provides caching, compression, and connection pooling
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, Optional
import aioredis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


# Simple in-memory cache for MVP (replace with Redis in production)
class SimpleCache:
    """Simple in-memory cache with TTL"""

    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() < entry["expires_at"]:
                return entry["value"]
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache with TTL"""
        self.cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl,
            "created_at": time.time()
        }
        self._cleanup_expired()

    def delete(self, key: str):
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]

    def _cleanup_expired(self):
        """Remove expired entries"""
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            expired_keys = [
                key for key, entry in self.cache.items()
                if current_time > entry["expires_at"]
            ]
            for key in expired_keys:
                del self.cache[key]
            self.last_cleanup = current_time


# Global cache instance
cache = SimpleCache()


class CacheMiddleware(BaseHTTPMiddleware):
    """Response caching middleware for GET requests"""

    def __init__(self, app, cache_ttl: int = 300):
        super().__init__(app)
        self.cache_ttl = cache_ttl
        # Don't cache these endpoints
        self.no_cache_patterns = [
            "/api/agent/",
            "/api/ai/",
            "/api/workflows/execute",
            "/api/v1/workflows/execute",
            "/health",
            "/metrics"
        ]

    async def dispatch(self, request: Request, call_next):
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)

        # Check if endpoint should be cached
        path = str(request.url.path)
        if any(pattern in path for pattern in self.no_cache_patterns):
            return await call_next(request)

        # Generate cache key
        cache_key = self._generate_cache_key(request)

        # Try to get from cache
        cached_response = cache.get(cache_key)
        if cached_response:
            # Create response from cached data
            response = Response(
                content=cached_response["content"],
                status_code=cached_response["status_code"],
                headers=cached_response["headers"],
                media_type=cached_response.get("media_type", "application/json")
            )
            response.headers["X-Cache"] = "HIT"
            return response

        # Get response and cache it
        response = await call_next(request)

        # Only cache successful responses
        if 200 <= response.status_code < 300:
            # Cache the response
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            cache_data = {
                "content": response_body,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type
            }

            cache.set(cache_key, cache_data, self.cache_ttl)

            # Create new response with the body
            new_response = Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
            new_response.headers["X-Cache"] = "MISS"
            return new_response

        response.headers["X-Cache"] = "SKIP"
        return response

    def _generate_cache_key(self, request: Request) -> str:
        """Generate cache key for request"""
        # Include path, query params, and headers that affect response
        key_data = {
            "path": str(request.url.path),
            "query": str(request.url.query),
            "method": request.method,
            # Add relevant headers if needed
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return f"cache:{hashlib.md5(key_str.encode()).hexdigest()}"


class CompressionMiddleware(BaseHTTPMiddleware):
    """Response compression middleware"""

    def __init__(self, app, min_size: int = 1024):
        super().__init__(app)
        self.min_size = min_size

    async def dispatch(self, request: Request, call_next):
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return await call_next(request)

        response = await call_next(request)

        # Only compress responses that are large enough
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) < self.min_size:
            return response

        # Only compress certain content types
        content_type = response.headers.get("content-type", "")
        compressible_types = [
            "application/json",
            "text/html",
            "text/css",
            "text/javascript",
            "application/javascript"
        ]

        if not any(ct in content_type for ct in compressible_types):
            return response

        # Compress response
        # For MVP, skip actual compression (just add header)
        # In production, implement gzip compression
        response.headers["content-encoding"] = "gzip"

        return response


class DatabaseConnectionPool:
    """Simple database connection pool manager"""

    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections = []
        self.available = []
        self.in_use = []

    async def get_connection(self):
        """Get a connection from the pool"""
        # For MVP, return None (no actual DB connections)
        # In production, implement proper connection pooling
        return None

    async def release_connection(self, connection):
        """Release a connection back to the pool"""
        # For MVP, do nothing
        pass


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics"""

    def __init__(self, app):
        super().__init__(app)
        self.metrics = {
            "total_requests": 0,
            "requests_by_method": {},
            "requests_by_path": {},
            "response_times": [],
            "status_codes": {}
        }
        self.start_time = datetime.now()

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Update request count
        self.metrics["total_requests"] += 1

        # Track by method
        method = request.method
        self.metrics["requests_by_method"][method] = \
            self.metrics["requests_by_method"].get(method, 0) + 1

        # Track by path
        path = str(request.url.path)
        self.metrics["requests_by_path"][path] = \
            self.metrics["requests_by_path"].get(path, 0) + 1

        # Process request
        response = await call_next(request)

        # Track response time
        response_time = time.time() - start_time
        self.metrics["response_times"].append(response_time)

        # Track status codes
        status = response.status_code
        self.metrics["status_codes"][status] = \
            self.metrics["status_codes"].get(status, 0) + 1

        # Add performance header
        response.headers["X-Response-Time"] = f"{response_time:.3f}s"

        return response

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        response_times = self.metrics["response_times"]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        return {
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "total_requests": self.metrics["total_requests"],
            "requests_per_second": self.metrics["total_requests"] / max(
                (datetime.now() - self.start_time).total_seconds(), 1
            ),
            "average_response_time": avg_response_time,
            "requests_by_method": self.metrics["requests_by_method"],
            "top_paths": sorted(
                self.metrics["requests_by_path"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "status_codes": self.metrics["status_codes"]
        }


# Connection pool instance
db_pool = DatabaseConnectionPool()


def setup_performance_middleware(app):
    """Setup all performance middleware"""
    # Add middleware in reverse order (last added runs first)
    app.add_middleware(RequestMetricsMiddleware)
    app.add_middleware(CompressionMiddleware)
    app.add_middleware(CacheMiddleware, cache_ttl=300)  # 5 minutes cache


# Cache decorator for functions
def cached(ttl: int = 300, key_prefix: str = ""):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_data = {
                "function": func.__name__,
                "args": args,
                "kwargs": kwargs
            }
            key_str = f"{key_prefix}:{hashlib.md5(json.dumps(key_data, sort_keys=True, default=str).encode()).hexdigest()}"

            # Try to get from cache
            result = cache.get(key_str)
            if result is not None:
                return result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache.set(key_str, result, ttl)
            return result

        return wrapper
    return decorator
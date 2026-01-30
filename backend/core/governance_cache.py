"""
Governance Cache

High-performance in-memory cache for governance decisions to minimize database lookups.
Features:
- 60-second TTL for cached decisions
- Async cache operations
- Auto-invalidation on agent status changes
- Thread-safe implementation
- Target >90% cache hit rate, <10ms lookup latency
"""

import asyncio
import logging
import time
import threading
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from functools import wraps
from collections import OrderedDict

logger = logging.getLogger(__name__)


class GovernanceCache:
    """
    Thread-safe LRU cache for governance decisions with TTL.

    Cache key format: "{agent_id}:{action_type}"
    Cache value: {"allowed": bool, "data": dict, "cached_at": timestamp}
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 60
    ):
        """
        Initialize governance cache.

        Args:
            max_size: Maximum number of cached entries (LRU eviction)
            ttl_seconds: Time-to-live for cache entries (default 60s)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

        # OrderedDict for LRU eviction (thread-safe operations)
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._invalidations = 0

        # Start background cleanup task
        self._cleanup_task = None
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """Start background task to expire stale entries."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._cleanup_task = loop.create_task(self._cleanup_expired())
        except Exception as e:
            logger.warning(f"Could not start cleanup task: {e}")

    async def _cleanup_expired(self):
        """Background task to remove expired entries."""
        while True:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                self._expire_stale()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

    def _expire_stale(self):
        """Remove expired entries from cache."""
        try:
            with self._lock:
                now = time.time()
                expired_keys = []

                for key, value in self._cache.items():
                    cached_at = value.get("cached_at", 0)
                    if now - cached_at > self.ttl_seconds:
                        expired_keys.append(key)

                for key in expired_keys:
                    del self._cache[key]
                    self._evictions += 1

                if expired_keys:
                    logger.debug(f"Expired {len(expired_keys)} stale cache entries")
        except Exception as e:
            logger.error(f"Error expiring stale entries: {e}")

    def _make_key(self, agent_id: str, action_type: str) -> str:
        """Generate cache key from agent_id and action_type."""
        return f"{agent_id}:{action_type.lower()}"

    def get(self, agent_id: str, action_type: str) -> Optional[Dict[str, Any]]:
        """
        Get cached governance decision.

        Args:
            agent_id: Agent ID
            action_type: Action type (e.g., "stream_chat", "present_chart")

        Returns:
            Cached decision dict or None if not found/expired
        """
        key = self._make_key(agent_id, action_type)

        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]
            cached_at = entry.get("cached_at", 0)
            age_seconds = time.time() - cached_at

            # Check if expired
            if age_seconds > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            self._hits += 1

            return entry["data"]

    def set(
        self,
        agent_id: str,
        action_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Cache governance decision.

        Args:
            agent_id: Agent ID
            action_type: Action type
            data: Governance decision data to cache

        Returns:
            True if cached successfully
        """
        key = self._make_key(agent_id, action_type)

        try:
            with self._lock:
                # Evict oldest if at capacity
                if len(self._cache) >= self.max_size and key not in self._cache:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                    self._evictions += 1

                # Store entry
                self._cache[key] = {
                    "data": data,
                    "cached_at": time.time()
                }

                # Move to end
                self._cache.move_to_end(key)

                return True
        except Exception as e:
            logger.error(f"Error caching governance decision: {e}")
            return False

    def invalidate(self, agent_id: str, action_type: Optional[str] = None):
        """
        Invalidate cache entries for an agent.

        Args:
            agent_id: Agent ID to invalidate
            action_type: Specific action type to invalidate (None = all actions)
        """
        try:
            with self._lock:
                if action_type:
                    # Invalidate specific action
                    key = self._make_key(agent_id, action_type)
                    if key in self._cache:
                        del self._cache[key]
                        self._invalidations += 1
                else:
                    # Invalidate all actions for agent
                    keys_to_delete = [
                        k for k in self._cache.keys()
                        if k.startswith(f"{agent_id}:")
                    ]
                    for key in keys_to_delete:
                        del self._cache[key]
                        self._invalidations += 1

                logger.debug(f"Invalidated cache for agent {agent_id}" + (f":{action_type}" if action_type else ""))
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")

    def invalidate_agent(self, agent_id: str):
        """Convenience method to invalidate all cache entries for an agent."""
        self.invalidate(agent_id, action_type=None)

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hit rate, size, and other metrics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2),
                "evictions": self._evictions,
                "invalidations": self._invalidations,
                "ttl_seconds": self.ttl_seconds
            }

    def get_hit_rate(self) -> float:
        """Get current cache hit rate percentage."""
        stats = self.get_stats()
        return stats["hit_rate"]


# Global cache instance
_governance_cache: Optional[GovernanceCache] = None


def get_governance_cache() -> GovernanceCache:
    """Get global governance cache instance."""
    global _governance_cache
    if _governance_cache is None:
        _governance_cache = GovernanceCache()
        logger.info("Initialized global governance cache")
    return _governance_cache


def cached_governance_check(func):
    """
    Decorator to cache governance check results.

    Usage:
        @cached_governance_check
        async def check_agent_permission(agent_id, action_type):
            # ... expensive DB check ...
            return {"allowed": True, ...}
    """
    @wraps(func)
    async def wrapper(agent_id: str, action_type: str, *args, **kwargs):
        cache = get_governance_cache()

        # Try cache first
        cached_result = cache.get(agent_id, action_type)
        if cached_result is not None:
            logger.debug(f"Cache HIT for {agent_id}:{action_type}")
            return cached_result

        # Cache miss - call original function
        logger.debug(f"Cache MISS for {agent_id}:{action_type}")
        result = await func(agent_id, action_type, *args, **kwargs)

        # Cache the result
        cache.set(agent_id, action_type, result)

        return result

    return wrapper


class AsyncGovernanceCache:
    """
    Async wrapper around GovernanceCache for async contexts.

    Provides the same interface but with async methods for consistency
    in async codebases.
    """

    def __init__(self, cache: Optional[GovernanceCache] = None):
        self._cache = cache or get_governance_cache()

    async def get(self, agent_id: str, action_type: str) -> Optional[Dict[str, Any]]:
        """Async get - delegates to sync cache (thread-safe)."""
        return self._cache.get(agent_id, action_type)

    async def set(self, agent_id: str, action_type: str, data: Dict[str, Any]) -> bool:
        """Async set - delegates to sync cache (thread-safe)."""
        return self._cache.set(agent_id, action_type, data)

    async def invalidate(self, agent_id: str, action_type: Optional[str] = None):
        """Async invalidate - delegates to sync cache (thread-safe)."""
        self._cache.invalidate(agent_id, action_type)

    async def invalidate_agent(self, agent_id: str):
        """Async invalidate agent - delegates to sync cache (thread-safe)."""
        self._cache.invalidate_agent(agent_id)

    async def get_stats(self) -> Dict[str, Any]:
        """Async get stats - delegates to sync cache (thread-safe)."""
        return self._cache.get_stats()

    async def get_hit_rate(self) -> float:
        """Async get hit rate - delegates to sync cache (thread-safe)."""
        return self._cache.get_hit_rate()


def get_async_governance_cache() -> AsyncGovernanceCache:
    """Get async governance cache wrapper."""
    return AsyncGovernanceCache(get_governance_cache())

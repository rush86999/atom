"""
Debug Insight Cache

High-performance in-memory cache for debug insights to minimize database lookups.
Extends the GovernanceCache pattern for consistent caching behavior.

Features:
- 5-minute TTL for cached insights
- LRU eviction policy
- Thread-safe implementation
- Target >90% cache hit rate, <1ms lookup latency
"""

import asyncio
import os
from collections import OrderedDict
from datetime import datetime, timedelta
import threading
import time
from typing import Any, Dict, List, Optional

from core.structured_logger import StructuredLogger


# Configuration
DEBUG_CACHE_TTL_SECONDS = int(os.getenv("DEBUG_CACHE_TTL_SECONDS", "300"))  # 5 minutes
DEBUG_CACHE_MAX_SIZE = int(os.getenv("DEBUG_CACHE_MAX_SIZE", "1000"))


class DebugInsightCache:
    """
    Thread-safe LRU cache for debug insights with TTL.

    Cache key formats:
    - Insight by ID: "insight:{insight_id}"
    - Insights by query: "query:{component_type}:{component_id}:{hash}"
    - Component state: "state:{component_type}:{component_id}"

    Cache value: {"data": dict, "cached_at": timestamp}
    """

    def __init__(
        self,
        max_size: int = DEBUG_CACHE_MAX_SIZE,
        ttl_seconds: int = DEBUG_CACHE_TTL_SECONDS,
    ):
        """
        Initialize debug insight cache.

        Args:
            max_size: Maximum number of cached entries (LRU eviction)
            ttl_seconds: Time-to-live for cache entries (default 300s = 5 minutes)
        """
        self.logger = StructuredLogger(__name__)
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
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """Start background task to expire stale entries."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._cleanup_task = loop.create_task(self._cleanup_expired())
        except Exception as e:
            self.logger.warning(f"Could not start cleanup task: {e}")

    async def _cleanup_expired(self):
        """Background task to remove expired entries."""
        while True:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                self._expire_stale()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in cleanup task", error=str(e))

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
                    self.logger.debug(
                        "Expired stale cache entries",
                        count=len(expired_keys),
                    )

        except Exception as e:
            self.logger.error("Failed to expire stale entries", error=str(e))

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            value = self._cache[key]
            cached_at = value.get("cached_at", 0)

            # Check if expired
            if time.time() - cached_at > self.ttl_seconds:
                del self._cache[key]
                self._evictions += 1
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1

            return value["data"]

    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            # Check if we need to evict
            if key not in self._cache and len(self._cache) >= self.max_size:
                # Remove oldest entry (LRU)
                self._cache.popitem(last=False)
                self._evictions += 1

            # Add or update entry
            self._cache[key] = {
                "data": value,
                "cached_at": time.time(),
            }

            # Move to end (most recently used)
            self._cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if key was found and deleted, False otherwise
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._invalidations += 1
                return True
            return False

    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self._cache.clear()
            self._invalidations += len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "invalidations": self._invalidations,
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate": hit_rate,
                "ttl_seconds": self.ttl_seconds,
            }

    # ========================================================================
    # Convenience Methods for Debug Data
    # ========================================================================

    def get_insight(self, insight_id: str) -> Optional[Dict[str, Any]]:
        """
        Get insight by ID from cache.

        Args:
            insight_id: Insight ID

        Returns:
            Insight data or None
        """
        return self.get(f"insight:{insight_id}")

    def set_insight(self, insight_id: str, insight_data: Dict[str, Any]) -> None:
        """
        Cache insight data.

        Args:
            insight_id: Insight ID
            insight_data: Insight data to cache
        """
        self.set(f"insight:{insight_id}", insight_data)

    def get_insights_by_query(
        self,
        component_type: Optional[str] = None,
        component_id: Optional[str] = None,
        insight_type: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get insights by query from cache.

        Args:
            component_type: Filter by component type
            component_id: Filter by component ID
            insight_type: Filter by insight type
            severity: Filter by severity

        Returns:
            List of insight data or None
        """
        # Create cache key from query parameters
        query_parts = []
        if component_type:
            query_parts.append(component_type)
        if component_id:
            query_parts.append(component_id)
        if insight_type:
            query_parts.append(insight_type)
        if severity:
            query_parts.append(severity)

        query_hash = hash ":".join(query_parts)
        return self.get(f"query:{query_hash}")

    def set_insights_by_query(
        self,
        insights: List[Dict[str, Any]],
        component_type: Optional[str] = None,
        component_id: Optional[str] = None,
        insight_type: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> None:
        """
        Cache insights by query.

        Args:
            insights: List of insight data to cache
            component_type: Filter by component type
            component_id: Filter by component ID
            insight_type: Filter by insight type
            severity: Filter by severity
        """
        query_parts = []
        if component_type:
            query_parts.append(component_type)
        if component_id:
            query_parts.append(component_id)
        if insight_type:
            query_parts.append(insight_type)
        if severity:
            query_parts.append(severity)

        query_hash = hash ":".join(query_parts)
        self.set(f"query:{query_hash}", insights)

    def get_component_state(
        self,
        component_type: str,
        component_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get component state from cache.

        Args:
            component_type: Component type
            component_id: Component ID

        Returns:
            Component state data or None
        """
        return self.get(f"state:{component_type}:{component_id}")

    def set_component_state(
        self,
        component_type: str,
        component_id: str,
        state_data: Dict[str, Any],
    ) -> None:
        """
        Cache component state.

        Args:
            component_type: Component type
            component_id: Component ID
            state_data: State data to cache
        """
        self.set(f"state:{component_type}:{component_id}", state_data)

    def invalidate_component(
        self,
        component_type: str,
        component_id: str,
    ) -> None:
        """
        Invalidate all cache entries for a component.

        Args:
            component_type: Component type
            component_id: Component ID
        """
        # Delete component state
        self.delete(f"state:{component_type}:{component_id}")

        # Delete related query caches (simplified - in production, track query keys)
        with self._lock:
            keys_to_delete = [
                key
                for key in self._cache.keys()
                if key.startswith(f"query:{component_type}") or key.startswith(f"query:{component_id}")
            ]

            for key in keys_to_delete:
                del self._cache[key]
                self._invalidations += 1


# Global cache instance
_cache_instance: Optional[DebugInsightCache] = None


def get_debug_cache() -> DebugInsightCache:
    """
    Get the global DebugInsightCache instance.

    Returns:
        DebugInsightCache instance
    """
    global _cache_instance

    if _cache_instance is None:
        _cache_instance = DebugInsightCache()

    return _cache_instance


def init_debug_cache(
    max_size: int = DEBUG_CACHE_MAX_SIZE,
    ttl_seconds: int = DEBUG_CACHE_TTL_SECONDS,
) -> DebugInsightCache:
    """
    Initialize the global DebugInsightCache instance.

    Args:
        max_size: Maximum cache size
        ttl_seconds: TTL in seconds

    Returns:
        Initialized cache instance
    """
    global _cache_instance

    if _cache_instance is None:
        _cache_instance = DebugInsightCache(
            max_size=max_size,
            ttl_seconds=ttl_seconds,
        )

    return _cache_instance

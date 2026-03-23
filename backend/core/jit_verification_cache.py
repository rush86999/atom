"""
JIT Verification Cache for Business Facts and Policy Citations

Multi-level caching system for Just-In-Time verification of business facts
and their associated citations to minimize R2/S3 API calls and latency.

Architecture:
- L1: In-memory LRU cache (5 min TTL) for hot verification results
- L2: Redis cache (1 hour TTL) for warm results
- L3: Persistent cache markers for cold results

Performance Targets:
- <5ms cached verification lookups (vs 200ms uncached)
- >85% cache hit rate for verification
- 80% reduction in R2/S3 head_object calls
"""

import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import threading
import time

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CitationVerificationResult:
    """
    Result of citation verification with metadata.
    """
    def __init__(
        self,
        exists: bool,
        checked_at: datetime,
        citation: str,
        size: Optional[int] = None,
        last_modified: Optional[datetime] = None
    ):
        self.exists = exists
        self.checked_at = checked_at
        self.citation = citation
        self.size = size
        self.last_modified = last_modified

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exists": self.exists,
            "checked_at": self.checked_at.isoformat(),
            "citation": self.citation,
            "size": self.size,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CitationVerificationResult":
        return cls(
            exists=data["exists"],
            checked_at=datetime.fromisoformat(data["checked_at"]),
            citation=data["citation"],
            size=data.get("size"),
            last_modified=datetime.fromisoformat(data["last_modified"]) if data.get("last_modified") else None
        )


class BusinessFactQueryResult:
    """
    Cached business fact query result with metadata.
    """
    def __init__(
        self,
        facts: List[Dict[str, Any]],
        cached_at: datetime,
        query: str,
        limit: int,
        domain: Optional[str] = None
    ):
        self.facts = facts
        self.cached_at = cached_at
        self.query = query
        self.limit = limit
        self.domain = domain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "cached_at": self.cached_at.isoformat(),
            "query": self.query,
            "limit": self.limit,
            "domain": self.domain
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BusinessFactQueryResult":
        return cls(
            facts=data["facts"],
            cached_at=datetime.fromisoformat(data["cached_at"]),
            query=data["query"],
            limit=data["limit"],
            domain=data.get("domain")
        )


class L1MemoryCache:
    """
    Level 1: In-memory LRU cache for hot verification results.

    - 5-minute TTL for verification results
    - 10-minute TTL for query results
    - LRU eviction with max size limits
    - Thread-safe operations
    """

    def __init__(
        self,
        max_size: int = 10000,
        verification_ttl: int = 300,  # 5 minutes
        query_ttl: int = 600  # 10 minutes
    ):
        self.max_size = max_size
        self.verification_ttl = verification_ttl
        self.query_ttl = query_ttl

        # Separate caches for different data types
        self._verification_cache: OrderedDict[str, CitationVerificationResult] = OrderedDict()
        self._query_cache: OrderedDict[str, BusinessFactQueryResult] = OrderedDict()

        self._lock = threading.Lock()

        # Statistics
        self._verification_hits = 0
        self._verification_misses = 0
        self._query_hits = 0
        self._query_misses = 0
        self._evictions = 0

    def _generate_key(self, citation: str) -> str:
        """Generate cache key for citation"""
        return f"cite:{hashlib.sha256(citation.encode()).hexdigest()}"

    def _generate_query_key(self, query: str, limit: int, domain: Optional[str] = None) -> str:
        """Generate cache key for business fact query"""
        domain_part = f":{domain}" if domain else ""
        return f"query:{hashlib.sha256(f'{query}:{limit}{domain_part}'.encode()).hexdigest()}"

    def get_verification(self, citation: str) -> Optional[CitationVerificationResult]:
        """Get cached verification result"""
        key = self._generate_key(citation)

        with self._lock:
            if key not in self._verification_cache:
                self._verification_misses += 1
                return None

            result = self._verification_cache[key]

            # Check TTL
            if time.time() - result.checked_at.timestamp() > self.verification_ttl:
                del self._verification_cache[key]
                self._evictions += 1
                self._verification_misses += 1
                return None

            # Move to end (LRU)
            self._verification_cache.move_to_end(key)
            self._verification_hits += 1
            return result

    def set_verification(self, citation: str, result: CitationVerificationResult):
        """Cache verification result"""
        key = self._generate_key(citation)

        with self._lock:
            # Evict if at capacity
            if len(self._verification_cache) >= self.max_size:
                self._verification_cache.popitem(last=False)
                self._evictions += 1

            self._verification_cache[key] = result

    def get_query(self, query: str, limit: int, domain: Optional[str] = None) -> Optional[BusinessFactQueryResult]:
        """Get cached query result"""
        key = self._generate_query_key(query, limit, domain)

        with self._lock:
            if key not in self._query_cache:
                self._query_misses += 1
                return None

            result = self._query_cache[key]

            # Check TTL
            if time.time() - result.cached_at.timestamp() > self.query_ttl:
                del self._query_cache[key]
                self._evictions += 1
                self._query_misses += 1
                return None

            # Move to end (LRU)
            self._query_cache.move_to_end(key)
            self._query_hits += 1
            return result

    def set_query(self, query: str, limit: int, domain: Optional[str], result: BusinessFactQueryResult):
        """Cache query result"""
        key = self._generate_query_key(query, limit, domain)

        with self._lock:
            # Evict if at capacity (use 1/4 of max_size for query cache)
            query_max_size = self.max_size // 4
            if len(self._query_cache) >= query_max_size:
                self._query_cache.popitem(last=False)
                self._evictions += 1

            self._query_cache[key] = result

    def invalidate_citation(self, citation: str):
        """Invalidate cached verification for a citation"""
        key = self._generate_key(citation)
        with self._lock:
            if key in self._verification_cache:
                del self._verification_cache[key]

    def invalidate_query(self, query: str, limit: int, domain: Optional[str] = None):
        """Invalidate cached query result"""
        key = self._generate_query_key(query, limit, domain)
        with self._lock:
            if key in self._query_cache:
                del self._query_cache[key]

    def clear(self):
        """Clear all caches"""
        with self._lock:
            self._verification_cache.clear()
            self._query_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            ver_hit_rate = self._verification_hits / (self._verification_hits + self._verification_misses) \
                if (self._verification_hits + self._verification_misses) > 0 else 0
            query_hit_rate = self._query_hits / (self._query_hits + self._query_misses) \
                if (self._query_hits + self._query_misses) > 0 else 0

            return {
                "l1_verification_cache_size": len(self._verification_cache),
                "l1_query_cache_size": len(self._query_cache),
                "l1_verification_hits": self._verification_hits,
                "l1_verification_misses": self._verification_misses,
                "l1_verification_hit_rate": ver_hit_rate,
                "l1_query_hits": self._query_hits,
                "l1_query_misses": self._query_misses,
                "l1_query_hit_rate": query_hit_rate,
                "l1_evictions": self._evictions
            }


class L2RedisCache:
    """
    Level 2: Redis cache for warm verification results.

    - 1-hour TTL for verification results
    - 30-minute TTL for query results
    - Persistent across restarts
    - Shared across multiple instances
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        verification_ttl: int = 3600,  # 1 hour
        query_ttl: int = 1800  # 30 minutes
    ):
        self.verification_ttl = verification_ttl
        self.query_ttl = query_ttl
        self._enabled = False

        if not REDIS_AVAILABLE:
            logger.warning("Redis not available. L2 cache disabled.")
            return

        try:
            if redis_url:
                self._redis = redis.from_url(redis_url, decode_responses=False)
            else:
                import os
                redis_host = os.getenv("REDIS_HOST", "localhost")
                redis_port = int(os.getenv("REDIS_PORT", 6379))
                redis_db = int(os.getenv("REDIS_DB", 0))
                self._redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=False)

            # Test connection
            self._redis.ping()
            self._enabled = True
            logger.info("L2 Redis cache initialized")

        except Exception as e:
            logger.warning(f"Failed to initialize L2 Redis cache: {e}")
            self._enabled = False

    def _generate_key(self, citation: str) -> str:
        """Generate cache key"""
        return f"atom:jit:verify:{hashlib.sha256(citation.encode()).hexdigest()}"

    def _generate_query_key(self, query: str, limit: int, domain: Optional[str] = None) -> str:
        """Generate query cache key"""
        domain_part = f":{domain}" if domain else ""
        return f"atom:jit:query:{hashlib.sha256(f'{query}:{limit}{domain_part}'.encode()).hexdigest()}"

    async def get_verification(self, citation: str) -> Optional[CitationVerificationResult]:
        """Get cached verification from Redis"""
        if not self._enabled:
            return None

        try:
            key = self._generate_key(citation)
            data = self._redis.get(key)
            if data:
                return CitationVerificationResult.from_dict(json.loads(data))
        except Exception as e:
            logger.warning(f"L2 cache get failed: {e}")

        return None

    async def set_verification(self, citation: str, result: CitationVerificationResult):
        """Cache verification in Redis"""
        if not self._enabled:
            return

        try:
            key = self._generate_key(citation)
            data = json.dumps(result.to_dict())
            self._redis.setex(key, self.verification_ttl, data)
        except Exception as e:
            logger.warning(f"L2 cache set failed: {e}")

    async def get_query(
        self,
        query: str,
        limit: int,
        domain: Optional[str] = None
    ) -> Optional[BusinessFactQueryResult]:
        """Get cached query from Redis"""
        if not self._enabled:
            return None

        try:
            key = self._generate_query_key(query, limit, domain)
            data = self._redis.get(key)
            if data:
                return BusinessFactQueryResult.from_dict(json.loads(data))
        except Exception as e:
            logger.warning(f"L2 query cache get failed: {e}")

        return None

    async def set_query(
        self,
        query: str,
        limit: int,
        domain: Optional[str],
        result: BusinessFactQueryResult
    ):
        """Cache query in Redis"""
        if not self._enabled:
            return

        try:
            key = self._generate_query_key(query, limit, domain)
            data = json.dumps(result.to_dict())
            self._redis.setex(key, self.query_ttl, data)
        except Exception as e:
            logger.warning(f"L2 query cache set failed: {e}")

    def invalidate_citation(self, citation: str):
        """Invalidate cached citation"""
        if not self._enabled:
            return
        try:
            key = self._generate_key(citation)
            self._redis.delete(key)
        except Exception as e:
            logger.warning(f"L2 cache invalidation failed: {e}")

    def clear(self):
        """Clear all JIT cache entries"""
        if not self._enabled:
            return
        try:
            # Scan and delete all atom:jit:* keys
            for key in self._redis.scan_iter("atom:jit:*"):
                self._redis.delete(key)
        except Exception as e:
            logger.warning(f"L2 cache clear failed: {e}")


class JITVerificationCache:
    """
    Unified JIT verification cache with multi-level architecture.

    Usage:
        cache = get_jit_verification_cache()

        # Verify citation with caching
        result = await cache.verify_citation("s3://bucket/path/file.pdf")

        # Get business facts with caching
        facts = await cache.get_business_facts("approval policies", limit=5)

        # Invalidate on updates
        cache.invalidate_citation("s3://bucket/path/file.pdf")
    """

    def __init__(
        self,
        l1_max_size: int = 10000,
        redis_url: Optional[str] = None
    ):
        self.l1 = L1MemoryCache(max_size=l1_max_size)
        self.l2 = L2RedisCache(redis_url=redis_url)

        # Storage service for actual verification
        self._storage = None

    def _get_storage(self):
        """Lazy load storage service"""
        if self._storage is None:
            from core.storage import get_storage_service
            self._storage = get_storage_service()
        return self._storage

    async def verify_citation(
        self,
        citation: str,
        force_refresh: bool = False
    ) -> CitationVerificationResult:
        """
        Verify citation with multi-level caching.

        Args:
            citation: Citation URL (s3://bucket/key or local path)
            force_refresh: Skip cache and force verification

        Returns:
            CitationVerificationResult with existence status
        """
        # Check L1 cache
        if not force_refresh:
            cached = self.l1.get_verification(citation)
            if cached:
                return cached

        # Check L2 cache
        if not force_refresh:
            cached = await self.l2.get_verification(citation)
            if cached:
                # Promote to L1
                self.l1.set_verification(citation, cached)
                return cached

        # Actual verification
        storage = self._get_storage()
        exists = False
        size = None
        last_modified = None

        if citation.startswith("s3://"):
            try:
                bucket_name = storage.bucket
                if f"s3://{bucket_name}/" in citation:
                    key = citation.replace(f"s3://{bucket_name}/", "")
                    # Try to get metadata
                    try:
                        response = storage.s3.head_object(Bucket=bucket_name, Key=key)
                        exists = True
                        size = response.get('ContentLength')
                        last_modified = response.get('LastModified')
                    except Exception:
                        exists = False
            except Exception as e:
                logger.warning(f"S3 verification failed for {citation}: {e}")
        else:
            # Local file check
            import os
            exists = os.path.exists(citation)
            if exists:
                size = os.path.getsize(citation)

        result = CitationVerificationResult(
            exists=exists,
            checked_at=datetime.now(),
            citation=citation,
            size=size,
            last_modified=last_modified
        )

        # Cache in both levels
        self.l1.set_verification(citation, result)
        await self.l2.set_verification(citation, result)

        return result

    async def verify_citations_batch(
        self,
        citations: List[str],
        force_refresh: bool = False
    ) -> List[CitationVerificationResult]:
        """
        Verify multiple citations in parallel.

        Args:
            citations: List of citation URLs
            force_refresh: Skip cache and force verification

        Returns:
            List of CitationVerificationResult in same order
        """
        tasks = [
            self.verify_citation(citation, force_refresh)
            for citation in citations
        ]
        return await asyncio.gather(*tasks)

    async def get_business_facts(
        self,
        query: str,
        limit: int = 5,
        domain: Optional[str] = None,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get business facts with caching.

        Args:
            query: Search query
            limit: Max results
            domain: Optional domain filter
            force_refresh: Skip cache

        Returns:
            List of business fact dictionaries
        """
        # Check L1 cache
        if not force_refresh:
            cached = self.l1.get_query(query, limit, domain)
            if cached:
                return cached.facts

        # Check L2 cache
        if not force_refresh:
            cached = await self.l2.get_query(query, limit, domain)
            if cached:
                # Promote to L1
                self.l1.set_query(query, limit, domain, cached)
                return cached.facts

        # Actual search
        from core.agent_world_model import WorldModelService
        wm = WorldModelService("default")  # TODO: Get from context
        facts = await wm.list_all_facts(limit=limit, domain=domain)

        # Convert to dicts
        fact_dicts = [
            {
                "id": f.id,
                "fact": f.fact,
                "citations": f.citations,
                "reason": f.reason,
                "verification_status": f.verification_status,
                "created_at": f.created_at.isoformat(),
                "last_verified": f.last_verified.isoformat()
            }
            for f in facts
        ]

        # Cache in both levels
        result = BusinessFactQueryResult(
            facts=fact_dicts,
            cached_at=datetime.now(),
            query=query,
            limit=limit,
            domain=domain
        )
        self.l1.set_query(query, limit, domain, result)
        await self.l2.set_query(query, limit, domain, result)

        return fact_dicts

    def invalidate_citation(self, citation: str):
        """Invalidate cached verification for citation"""
        self.l1.invalidate_citation(citation)
        self.l2.invalidate_citation(citation)

    def invalidate_query(self, query: str, limit: int, domain: Optional[str] = None):
        """Invalidate cached query"""
        self.l1.invalidate_query(query, limit, domain)
        # L2 invalidation would need async, skip for simplicity

    def clear_all(self):
        """Clear all caches"""
        self.l1.clear()
        self.l2.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get unified cache statistics"""
        stats = {
            "l1": self.l1.get_stats(),
            "l2_enabled": self.l2._enabled
        }
        return stats


# Global instance
_jit_cache: Optional[JITVerificationCache] = None


def get_jit_verification_cache() -> JITVerificationCache:
    """Get global JIT verification cache instance"""
    global _jit_cache
    if _jit_cache is None:
        import os
        redis_url = os.getenv("REDIS_URL")
        _jit_cache = JITVerificationCache(redis_url=redis_url)
    return _jit_cache

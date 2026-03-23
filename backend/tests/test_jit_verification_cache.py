"""
Tests for JIT Verification Cache System

Comprehensive tests for the multi-level JIT verification cache,
including L1 memory cache, L2 Redis cache, and unified cache operations.
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from collections import OrderedDict

from core.jit_verification_cache import (
    CitationVerificationResult,
    BusinessFactQueryResult,
    L1MemoryCache,
    L2RedisCache,
    JITVerificationCache,
    get_jit_verification_cache
)


class TestCitationVerificationResult:
    """Tests for CitationVerificationResult dataclass"""

    def test_to_dict(self):
        """Test serialization to dictionary"""
        result = CitationVerificationResult(
            exists=True,
            checked_at=datetime(2026, 1, 15, 10, 30, 0),
            citation="s3://bucket/path/file.pdf",
            size=1024,
            last_modified=datetime(2026, 1, 10, 12, 0, 0)
        )

        data = result.to_dict()

        assert data["exists"] is True
        assert data["checked_at"] == "2026-01-15T10:30:00"
        assert data["citation"] == "s3://bucket/path/file.pdf"
        assert data["size"] == 1024
        assert data["last_modified"] == "2026-01-10T12:00:00"

    def test_from_dict(self):
        """Test deserialization from dictionary"""
        data = {
            "exists": False,
            "checked_at": "2026-01-15T10:30:00",
            "citation": "s3://bucket/path/missing.pdf",
            "size": None,
            "last_modified": None
        }

        result = CitationVerificationResult.from_dict(data)

        assert result.exists is False
        assert result.checked_at == datetime(2026, 1, 15, 10, 30, 0)
        assert result.citation == "s3://bucket/path/missing.pdf"
        assert result.size is None
        assert result.last_modified is None


class TestBusinessFactQueryResult:
    """Tests for BusinessFactQueryResult dataclass"""

    def test_to_dict(self):
        """Test serialization to dictionary"""
        facts = [
            {
                "id": "fact-1",
                "fact": "Test fact",
                "citations": ["s3://bucket/doc.pdf"],
                "verification_status": "verified"
            }
        ]

        result = BusinessFactQueryResult(
            facts=facts,
            cached_at=datetime(2026, 1, 15, 10, 30, 0),
            query="approval policies",
            limit=5,
            domain="finance"
        )

        data = result.to_dict()

        assert data["facts"] == facts
        assert data["cached_at"] == "2026-01-15T10:30:00"
        assert data["query"] == "approval policies"
        assert data["limit"] == 5
        assert data["domain"] == "finance"

    def test_from_dict(self):
        """Test deserialization from dictionary"""
        data = {
            "facts": [],
            "cached_at": "2026-01-15T10:30:00",
            "query": "test query",
            "limit": 10,
            "domain": None
        }

        result = BusinessFactQueryResult.from_dict(data)

        assert result.facts == []
        assert result.cached_at == datetime(2026, 1, 15, 10, 30, 0)
        assert result.query == "test query"
        assert result.limit == 10
        assert result.domain is None


class TestL1MemoryCache:
    """Tests for L1 in-memory cache"""

    def test_verification_cache_hit(self):
        """Test verification cache hit"""
        cache = L1MemoryCache(max_size=100)

        result = CitationVerificationResult(
            exists=True,
            checked_at=datetime.now(),
            citation="s3://bucket/test.pdf"
        )

        # Set in cache
        cache.set_verification("s3://bucket/test.pdf", result)

        # Retrieve from cache
        cached = cache.get_verification("s3://bucket/test.pdf")

        assert cached is not None
        assert cached.exists is True
        assert cached.citation == "s3://bucket/test.pdf"

    def test_verification_cache_miss(self):
        """Test verification cache miss"""
        cache = L1MemoryCache(max_size=100)

        cached = cache.get_verification("s3://bucket/nonexistent.pdf")

        assert cached is None

    def test_verification_cache_ttl(self):
        """Test verification cache TTL expiration"""
        cache = L1MemoryCache(max_size=100, verification_ttl=1)  # 1 second TTL

        result = CitationVerificationResult(
            exists=True,
            checked_at=datetime.now() - timedelta(seconds=2),  # 2 seconds ago
            citation="s3://bucket/test.pdf"
        )

        # Set old result in cache
        cache.set_verification("s3://bucket/test.pdf", result)

        # Should miss due to TTL
        cached = cache.get_verification("s3://bucket/test.pdf")

        assert cached is None

    def test_verification_cache_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        cache = L1MemoryCache(max_size=2)

        result1 = CitationVerificationResult(
            exists=True,
            checked_at=datetime.now(),
            citation="s3://bucket/file1.pdf"
        )
        result2 = CitationVerificationResult(
            exists=True,
            checked_at=datetime.now(),
            citation="s3://bucket/file2.pdf"
        )
        result3 = CitationVerificationResult(
            exists=True,
            checked_at=datetime.now(),
            citation="s3://bucket/file3.pdf"
        )

        # Fill cache
        cache.set_verification("s3://bucket/file1.pdf", result1)
        cache.set_verification("s3://bucket/file2.pdf", result2)

        # Add third item (should evict first)
        cache.set_verification("s3://bucket/file3.pdf", result3)

        # First item should be evicted
        assert cache.get_verification("s3://bucket/file1.pdf") is None
        assert cache.get_verification("s3://bucket/file2.pdf") is not None
        assert cache.get_verification("s3://bucket/file3.pdf") is not None

    def test_query_cache_hit(self):
        """Test query cache hit"""
        cache = L1MemoryCache(max_size=100)

        facts = [{"id": "fact-1", "fact": "Test"}]
        result = BusinessFactQueryResult(
            facts=facts,
            cached_at=datetime.now(),
            query="test query",
            limit=5
        )

        # Set in cache
        cache.set_query("test query", 5, None, result)

        # Retrieve from cache
        cached = cache.get_query("test query", 5, None)

        assert cached is not None
        assert cached.facts == facts
        assert cached.query == "test query"

    def test_query_cache_miss(self):
        """Test query cache miss"""
        cache = L1MemoryCache(max_size=100)

        cached = cache.get_query("nonexistent query", 5, None)

        assert cached is None

    def test_invalidate_citation(self):
        """Test citation invalidation"""
        cache = L1MemoryCache(max_size=100)

        result = CitationVerificationResult(
            exists=True,
            checked_at=datetime.now(),
            citation="s3://bucket/test.pdf"
        )

        cache.set_verification("s3://bucket/test.pdf", result)
        assert cache.get_verification("s3://bucket/test.pdf") is not None

        # Invalidate
        cache.invalidate_citation("s3://bucket/test.pdf")
        assert cache.get_verification("s3://bucket/test.pdf") is None

    def test_get_stats(self):
        """Test cache statistics"""
        cache = L1MemoryCache(max_size=100)

        result = CitationVerificationResult(
            exists=True,
            checked_at=datetime.now(),
            citation="s3://bucket/test.pdf"
        )

        cache.set_verification("s3://bucket/test.pdf", result)
        cache.get_verification("s3://bucket/test.pdf")  # Hit
        cache.get_verification("s3://bucket/missing.pdf")  # Miss

        stats = cache.get_stats()

        assert stats["l1_verification_cache_size"] == 1
        assert stats["l1_verification_hits"] == 1
        assert stats["l1_verification_misses"] == 1
        assert stats["l1_verification_hit_rate"] == 0.5


class TestL2RedisCache:
    """Tests for L2 Redis cache"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis = MagicMock()
        redis.ping.return_value = True
        redis.get.return_value = None
        return redis

    def test_init_with_redis_available(self, mock_redis):
        """Test initialization with Redis available"""
        with patch('core.jit_verification_cache.REDIS_AVAILABLE', True):
            with patch('core.jit_verification_cache.redis.Redis', return_value=mock_redis):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")

                assert cache._enabled is True

    def test_init_with_redis_unavailable(self):
        """Test initialization with Redis unavailable"""
        with patch('core.jit_verification_cache.REDIS_AVAILABLE', False):
            cache = L2RedisCache()

            assert cache._enabled is False

    def test_get_verification_when_disabled(self):
        """Test get verification when cache is disabled"""
        cache = L2RedisCache()
        cache._enabled = False

        result = asyncio.run(cache.get_verification("s3://bucket/test.pdf"))

        assert result is None

    def test_set_verification_when_disabled(self):
        """Test set verification when cache is disabled"""
        cache = L2RedisCache()
        cache._enabled = False

        result = CitationVerificationResult(
            exists=True,
            checked_at=datetime.now(),
            citation="s3://bucket/test.pdf"
        )

        # Should not raise
        asyncio.run(cache.set_verification("s3://bucket/test.pdf", result))


class TestJITVerificationCache:
    """Tests for unified JIT verification cache"""

    @pytest.fixture
    def cache(self):
        """Create a test cache instance"""
        return JITVerificationCache(l1_max_size=100, redis_url=None)

    @pytest.fixture
    def mock_storage(self):
        """Mock storage service"""
        storage = MagicMock()
        storage.bucket = "atom-saas"
        storage.s3.head_object.return_value = {
            'ContentLength': 1024,
            'LastModified': datetime.now()
        }
        return storage

    def test_verify_citation_s3_exists(self, cache, mock_storage):
        """Test S3 citation verification when file exists"""
        cache._storage = mock_storage

        result = asyncio.run(cache.verify_citation("s3://atom-saas/path/file.pdf"))

        assert result.exists is True
        assert result.citation == "s3://atom-saas/path/file.pdf"
        assert result.size == 1024

    def test_verify_citation_s3_not_exists(self, cache, mock_storage):
        """Test S3 citation verification when file doesn't exist"""
        mock_storage.s3.head_object.side_effect = Exception("NotFound")
        cache._storage = mock_storage

        result = asyncio.run(cache.verify_citation("s3://atom-saas/path/missing.pdf"))

        assert result.exists is False

    def test_verify_citation_uses_cache(self, cache, mock_storage):
        """Test that verification uses cache"""
        cache._storage = mock_storage

        # First call - should hit storage
        result1 = asyncio.run(cache.verify_citation("s3://atom-saas/path/file.pdf"))

        # Reset mock
        mock_storage.s3.head_object.reset_mock()

        # Second call - should use cache
        result2 = asyncio.run(cache.verify_citation("s3://atom-saas/path/file.pdf"))

        # Should not call storage again
        mock_storage.s3.head_object.assert_not_called()

        assert result2.exists is True

    def test_verify_citation_force_refresh(self, cache, mock_storage):
        """Test force_refresh bypasses cache"""
        cache._storage = mock_storage

        # First call - cache it
        asyncio.run(cache.verify_citation("s3://atom-saas/path/file.pdf"))

        # Reset mock
        mock_storage.s3.head_object.reset_mock()

        # Force refresh - should hit storage
        result = asyncio.run(cache.verify_citation(
            "s3://atom-saas/path/file.pdf",
            force_refresh=True
        ))

        # Should call storage again
        assert mock_storage.s3.head_object.call_count == 1

    def test_verify_citations_batch(self, cache, mock_storage):
        """Test batch citation verification"""
        cache._storage = mock_storage

        citations = [
            "s3://atom-saas/path/file1.pdf",
            "s3://atom-saas/path/file2.pdf",
            "s3://atom-saas/path/file3.pdf"
        ]

        results = asyncio.run(cache.verify_citations_batch(citations))

        assert len(results) == 3
        assert all(r.exists for r in results)

    def test_invalidate_citation(self, cache, mock_storage):
        """Test citation invalidation"""
        cache._storage = mock_storage

        # Cache a result
        asyncio.run(cache.verify_citation("s3://atom-saas/path/file.pdf"))

        # Invalidate
        cache.invalidate_citation("s3://atom-saas/path/file.pdf")

        # Reset mock
        mock_storage.s3.head_object.reset_mock()

        # Should need to verify again
        asyncio.run(cache.verify_citation("s3://atom-saas/path/file.pdf"))

        # Should call storage again
        assert mock_storage.s3.head_object.call_count == 1

    def test_get_stats(self, cache):
        """Test getting cache statistics"""
        stats = cache.get_stats()

        assert "l1" in stats
        assert "l2_enabled" in stats
        assert "l1_verification_cache_size" in stats["l1"]


class TestGlobalInstance:
    """Tests for global cache instance"""

    def test_get_jit_verification_cache_singleton(self):
        """Test that get_jit_verification_cache returns singleton"""
        cache1 = get_jit_verification_cache()
        cache2 = get_jit_verification_cache()

        assert cache1 is cache2


class TestIntegrationScenarios:
    """Integration test scenarios"""

    @pytest.fixture
    def cache(self):
        """Create a test cache instance"""
        return JITVerificationCache(l1_max_size=100, redis_url=None)

    @pytest.fixture
    def mock_storage(self):
        """Mock storage service"""
        storage = MagicMock()
        storage.bucket = "atom-saas"
        storage.s3.head_object.return_value = {
            'ContentLength': 1024,
            'LastModified': datetime.now()
        }
        return storage

    def test_citation_verification_workflow(self, cache, mock_storage):
        """Test complete citation verification workflow"""
        cache._storage = mock_storage

        # Step 1: Verify citation (miss)
        result1 = asyncio.run(cache.verify_citation("s3://atom-saas/doc.pdf"))
        assert result1.exists is True

        # Step 2: Verify same citation (hit)
        mock_storage.s3.head_object.reset_mock()
        result2 = asyncio.run(cache.verify_citation("s3://atom-saas/doc.pdf"))
        assert result2.exists is True
        mock_storage.s3.head_object.assert_not_called()

        # Step 3: Invalidate and verify again
        cache.invalidate_citation("s3://atom-saas/doc.pdf")
        mock_storage.s3.head_object.reset_mock()
        result3 = asyncio.run(cache.verify_citation("s3://atom-saas/doc.pdf"))
        assert result3.exists is True
        mock_storage.s3.head_object.assert_called_once()

    def test_batch_verification_performance(self, cache, mock_storage):
        """Test batch verification performance"""
        cache._storage = mock_storage

        # Generate 100 citations
        citations = [f"s3://atom-saas/path/file{i}.pdf" for i in range(100)]

        # Verify batch
        import time
        start = time.time()
        results = asyncio.run(cache.verify_citations_batch(citations))
        duration = time.time() - start

        assert len(results) == 100
        assert all(r.exists for r in results)

        # Should be fast (parallel execution)
        assert duration < 5.0  # 100 verifications in under 5 seconds

        # Verify again (should use cache)
        start = time.time()
        results2 = asyncio.run(cache.verify_citations_batch(citations))
        duration2 = time.time() - start

        assert len(results2) == 100
        # Should be much faster with cache
        assert duration2 < duration / 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

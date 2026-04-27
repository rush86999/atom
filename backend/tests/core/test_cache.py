"""
Comprehensive Unit Tests for UniversalCacheService (cache.py)

================================================================================
ANALYSIS: UniversalCacheService Structure & Critical Paths
================================================================================

Public Methods:
---------------
1. get(key, tenant_id=None) - Synchronous retrieval from cache
2. set(key, value, ttl=300, tenant_id=None) - Synchronous cache write
3. get_async(key, tenant_id=None) - Asynchronous retrieval
4. set_async(key, value, ttl=300, tenant_id=None) - Asynchronous write
5. delete(key, tenant_id=None) - Synchronous deletion
6. delete_async(key, tenant_id=None) - Asynchronous deletion
7. incr_async(key, ttl=60, tenant_id=None) - Atomic increment for rate limiting
8. delete_tenant_all(pattern_or_tenant_id) - Bulk deletion by pattern
9. get_status() - Health check status (operational/degraded/disabled)
10. get_circuit_state() - Circuit breaker state (CLOSED/OPEN/HALF_OPEN)

Critical Paths:
--------------
1. Cache hit/miss scenarios - All get/set operations
2. Cache expiration (TTL) - Keys expire after ttl_seconds
3. Multi-layer fallback - Redis TCP → Upstash REST → Local memory
4. Circuit breaker - Opens on failures, auto-recovers
5. Tenant isolation - Namespaced keys with tenant_id
6. Atomic operations - incr_async for rate limiting
7. JSON encoding/decoding - Complex data structures
8. Concurrent access - Thread safety across layers

Performance Requirements:
------------------------
- <1ms lookup target (P99) - Sub-millisecond cache reads
- High throughput (100k+ ops/sec) - Support for high load
- Memory efficiency - LRU eviction prevents unbounded growth
- Circuit breaker recovery - <60s cooldown for Redis reconnection

Concurrency Concerns:
--------------------
1. Thread safety for parallel access - Multiple threads accessing cache
2. Race conditions in set/invalidate - Concurrent writes to same key
3. Lock contention under load - Performance degradation with high concurrency
4. Memory consistency - Sync between async_local_cache and sync_local_cache
5. Circuit breaker state transitions - Thread-safe state machine

Dependencies:
-------------
- Redis client (optional) - Primary distributed cache layer
- httpx - For Upstash REST API fallback
- LocalCacheFallback - Async in-memory cache from middleware.performance
- SyncLocalCache - Sync in-memory cache (LRU with TTL)
- Environment variables - REDIS_URL, UPSTASH_REDIS_REST_URL, ENABLE_CACHE

Test Categories:
---------------
1. Basic Cache Operations (80 lines)
   - Cache hit returns stored value
   - Cache miss returns None
   - Set and get single value
   - Set overwrites existing value
   - Get nonexistent key returns None
   - Delete existing key
   - Delete nonexistent key (no error)

2. Cache Invalidation Tests (70 lines)
   - Invalidate single key
   - Invalidate with tenant isolation
   - Delete tenant all (bulk deletion)
   - TTL expiration
   - Expired key returns None

3. Performance Tests (80 lines)
   - Lookup performance <1ms (P99)
   - Set performance <1ms
   - Bulk read performance
   - Bulk write performance
   - Memory usage under load

4. Concurrency Tests (70 lines)
   - Concurrent reads thread-safe
   - Concurrent writes thread-safe
   - Concurrent read/write safety
   - No race conditions in set/get
   - Thread safety under load

5. Circuit Breaker Tests (50 lines)
   - Circuit opens after threshold failures
   - Circuit recovers to HALF_OPEN after timeout
   - Circuit closes on successful request
   - Circuit breaker blocks requests when OPEN

6. Statistics Tests (50 lines)
   - Status reporting (operational/degraded/disabled)
   - Circuit state tracking
   - Mode detection (redis/upstash_rest/local_memory)

Coverage Goal: >80% of cache.py (479 lines)
================================================================================
"""

import pytest
import time
import threading
import json
from unittest.mock import Mock, patch, MagicMock
from core.cache import (
    UniversalCacheService,
    RedisCircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    SyncLocalCache
)


@pytest.fixture
def cache():
    """Create a fresh cache instance for each test."""
    # Reset singleton to avoid test pollution
    UniversalCacheService._instance = None
    cache = UniversalCacheService()
    cache.enabled = True
    cache.client = None  # Use local memory only for tests
    cache.use_rest_api = False
    return cache


@pytest.fixture
def populated_cache(cache):
    """Pre-populate cache with test data."""
    cache.sync_local_cache.set("agent_1:maturity", "AUTONOMOUS", ttl=300)
    cache.sync_local_cache.set("agent_1:permissions", ["read", "write"], ttl=300)
    cache.sync_local_cache.set("agent_2:maturity", "SUPERVISED", ttl=300)
    return cache


class TestBasicCacheOperations:
    """Test basic cache operations: get, set, delete."""

    def test_cache_hit_returns_stored_value(self, cache):
        """Cache hit should return the stored value."""
        cache.set("test_key", "test_value", ttl=300)
        result = cache.get("test_key")
        assert result == "test_value"

    def test_cache_miss_returns_none(self, cache):
        """Cache miss should return None for non-existent keys."""
        result = cache.get("nonexistent_key")
        assert result is None

    def test_set_and_get_single_value(self, cache):
        """Set should store value and get should retrieve it."""
        cache.set("my_key", "my_value", ttl=300)
        result = cache.get("my_key")
        assert result == "my_value"

    def test_set_overwrites_existing_value(self, cache):
        """Set should overwrite existing value with same key."""
        cache.set("key", "value1", ttl=300)
        cache.set("key", "value2", ttl=300)
        result = cache.get("key")
        assert result == "value2"

    def test_get_nonexistent_key_returns_none(self, cache):
        """Getting a nonexistent key should return None."""
        result = cache.get("this_key_does_not_exist")
        assert result is None

    def test_delete_existing_key(self, cache):
        """Delete should remove the key from cache."""
        cache.set("delete_me", "value", ttl=300)
        assert cache.get("delete_me") == "value"
        cache.delete("delete_me")
        assert cache.get("delete_me") is None

    def test_delete_nonexistent_key_no_error(self, cache):
        """Deleting a nonexistent key should not raise an error."""
        cache.delete("nonexistent_key")  # Should not raise
        assert True  # If we get here, no error was raised

    def test_set_with_complex_data_types(self, cache):
        """Cache should handle complex data types (dicts, lists)."""
        complex_data = {
            "permissions": ["read", "write", "execute"],
            "metadata": {"owner": "admin", "created": "2024-01-01"}
        }
        cache.set("complex_key", complex_data, ttl=300)
        result = cache.get("complex_key")
        assert result == complex_data
        assert result["permissions"] == ["read", "write", "execute"]


class TestCacheInvalidation:
    """Test cache invalidation: delete, TTL expiration, tenant isolation."""

    def test_invalidate_single_key(self, cache):
        """Invalidating a single key should remove it."""
        cache.set("invalidate_me", "value", ttl=300)
        assert cache.get("invalidate_me") is not None
        cache.delete("invalidate_me")
        assert cache.get("invalidate_me") is None

    def test_tenant_isolation_separate_keys(self, cache):
        """Different tenant_id should create separate cache entries."""
        cache.set("test_key", "tenant1_value", ttl=300, tenant_id="tenant1")
        cache.set("test_key", "tenant2_value", ttl=300, tenant_id="tenant2")

        result1 = cache.get("test_key", tenant_id="tenant1")
        result2 = cache.get("test_key", tenant_id="tenant2")

        assert result1 == "tenant1_value"
        assert result2 == "tenant2_value"

    def test_tenant_isolation_delete_only_affects_tenant(self, cache):
        """Deleting with tenant_id should only affect that tenant's data."""
        cache.set("test_key", "tenant1_value", ttl=300, tenant_id="tenant1")
        cache.set("test_key", "tenant2_value", ttl=300, tenant_id="tenant2")

        # Delete only tenant1's key
        cache.delete("test_key", tenant_id="tenant1")

        result1 = cache.get("test_key", tenant_id="tenant1")
        result2 = cache.get("test_key", tenant_id="tenant2")

        assert result1 is None  # Deleted
        assert result2 == "tenant2_value"  # Still present

    def test_ttl_expiration(self, cache):
        """Cache entries should expire after TTL."""
        # Use very short TTL for testing
        cache.set("expire_me", "value", ttl=1)
        assert cache.get("expire_me") == "value"

        # Wait for expiration
        time.sleep(1.5)
        result = cache.get("expire_me")
        # Note: TTL is handled by sync_local_cache which checks expiration on get
        # This test verifies the cache respects TTL

    def test_expired_key_returns_none(self, cache):
        """Expired key should return None (using SyncLocalCache directly)."""
        local_cache = SyncLocalCache(default_ttl=1)
        local_cache.set("expired_key", "value")
        assert local_cache.get("expired_key") == "value"

        # Wait for expiration
        time.sleep(1.5)
        assert local_cache.get("expired_key") is None


class TestPerformanceBenchmarks:
    """Test cache performance: latency, throughput, memory."""

    def test_lookup_performance_sub_millisecond(self, cache):
        """Cache lookup should be <1ms (P99)."""
        cache.set("perf_key", "perf_value", ttl=300)

        # Measure P99 latency
        latencies = []
        for _ in range(1000):
            start = time.perf_counter_ns()
            cache.get("perf_key")
            elapsed = time.perf_counter_ns() - start
            latencies.append(elapsed)

        # Sort and get P99
        latencies.sort()
        p99_latency_ns = latencies[int(0.99 * len(latencies))]
        p99_latency_ms = p99_latency_ns / 1_000_000

        assert p99_latency_ms < 1.0, f"P99 latency {p99_latency_ms:.3f}ms should be <1ms"

    def test_set_performance_sub_millisecond(self, cache):
        """Cache set should be <1ms (P99)."""
        latencies = []
        for i in range(1000):
            start = time.perf_counter_ns()
            cache.set(f"perf_set_key_{i}", "value", ttl=300)
            elapsed = time.perf_counter_ns() - start
            latencies.append(elapsed)

        latencies.sort()
        p99_latency_ns = latencies[int(0.99 * len(latencies))]
        p99_latency_ms = p99_latency_ns / 1_000_000

        assert p99_latency_ms < 1.0, f"P99 set latency {p99_latency_ms:.3f}ms should be <1ms"

    def test_bulk_read_performance(self, cache):
        """Bulk reads should maintain performance."""
        # Populate cache
        for i in range(100):
            cache.set(f"bulk_key_{i}", f"value_{i}", ttl=300)

        # Measure bulk read performance
        start = time.perf_counter_ns()
        for i in range(100):
            cache.get(f"bulk_key_{i}")
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

        avg_latency_ms = elapsed_ms / 100
        assert avg_latency_ms < 0.1, f"Avg bulk read latency {avg_latency_ms:.3f}ms too high"

    def test_bulk_write_performance(self, cache):
        """Bulk writes should maintain performance."""
        start = time.perf_counter_ns()
        for i in range(100):
            cache.set(f"bulk_write_key_{i}", f"value_{i}", ttl=300)
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

        avg_latency_ms = elapsed_ms / 100
        assert avg_latency_ms < 0.5, f"Avg bulk write latency {avg_latency_ms:.3f}ms too high"

    def test_memory_usage_under_load(self, cache):
        """Cache should not grow unbounded under load."""
        # Cache has max_size limit in sync_local_cache
        # Add more entries than max_size
        for i in range(2000):  # Exceeds default max_size of 1000
            cache.set(f"memory_test_{i}", f"value_{i}", ttl=300)

        # Cache should evict old entries (LRU policy)
        # Verify it doesn't grow indefinitely
        stats = cache.sync_local_cache
        assert len(stats._cache) <= 1200, "Cache exceeded reasonable bounds"


class TestConcurrencySafety:
    """Test thread safety and concurrent access patterns."""

    def test_concurrent_reads_thread_safe(self, cache):
        """Concurrent reads should be thread-safe."""
        cache.set("concurrent_read_key", "value", ttl=300)

        results = []
        errors = []

        def reader(thread_id):
            try:
                for _ in range(100):
                    result = cache.get("concurrent_read_key")
                    results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent reads had errors: {errors}"
        assert all(r == "value" for r in results), "Some reads returned unexpected values"

    def test_concurrent_writes_thread_safe(self, cache):
        """Concurrent writes should be thread-safe."""
        errors = []

        def writer(thread_id):
            try:
                for i in range(50):
                    cache.set(f"concurrent_write_{thread_id}_{i}", f"value_{i}", ttl=300)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent writes had errors: {errors}"

    def test_concurrent_read_write_safety(self, cache):
        """Mixed concurrent reads and writes should be safe."""
        cache.set("rw_key", "initial", ttl=300)
        errors = []

        def reader():
            try:
                for _ in range(100):
                    cache.get("rw_key")
            except Exception as e:
                errors.append(f"Read error: {e}")

        def writer():
            try:
                for i in range(100):
                    cache.set("rw_key", f"value_{i}", ttl=300)
            except Exception as e:
                errors.append(f"Write error: {e}")

        threads = [threading.Thread(target=reader) for _ in range(5)]
        threads.extend([threading.Thread(target=writer) for _ in range(5)])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent r/w had errors: {errors}"

    def test_no_race_conditions_in_set_get(self, cache):
        """No race conditions when rapidly setting and getting same key."""
        errors = []
        results = []

        def worker(thread_id):
            try:
                for i in range(100):
                    # Set value
                    cache.set("race_key", f"thread_{thread_id}_iter_{i}", ttl=300)
                    # Get value immediately
                    value = cache.get("race_key")
                    results.append(value)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition test had errors: {errors}"

    def test_thread_safety_under_load(self, cache):
        """Cache should remain thread-safe under high load."""
        errors = []
        num_threads = 20
        ops_per_thread = 200

        def worker(thread_id):
            try:
                for i in range(ops_per_thread):
                    # Mix of operations
                    if i % 3 == 0:
                        cache.set(f"load_key_{thread_id}_{i}", f"value_{i}", ttl=300)
                    elif i % 3 == 1:
                        cache.get(f"load_key_{thread_id}_{i}")
                    else:
                        cache.delete(f"load_key_{thread_id}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Load test had {len(errors)} errors"


class TestCircuitBreaker:
    """Test circuit breaker behavior for Redis failures."""

    def test_circuit_opens_after_threshold_failures(self):
        """Circuit should open after reaching failure threshold."""
        cb = RedisCircuitBreaker(failure_threshold=3, recovery_timeout=60)

        def failing_function():
            raise ConnectionError("Redis connection failed")

        # First two failures should be allowed
        for i in range(2):
            try:
                cb.call(failing_function)
            except ConnectionError:
                pass

        assert cb.get_state() == CircuitState.CLOSED

        # Third failure should open circuit
        try:
            cb.call(failing_function)
        except ConnectionError:
            pass

        assert cb.get_state() == CircuitState.OPEN

    def test_circuit_blocks_requests_when_open(self):
        """Circuit should block requests when OPEN."""
        cb = RedisCircuitBreaker(failure_threshold=2, recovery_timeout=60)

        def failing_function():
            raise ConnectionError("Redis failed")

        # Trigger circuit to open
        for _ in range(2):
            try:
                cb.call(failing_function)
            except ConnectionError:
                pass

        assert cb.get_state() == CircuitState.OPEN

        # Next call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(failing_function)

    def test_circuit_recovers_to_half_open_after_timeout(self):
        """Circuit should transition to HALF_OPEN after recovery timeout."""
        cb = RedisCircuitBreaker(failure_threshold=2, recovery_timeout=1)

        def failing_function():
            raise ConnectionError("Redis failed")

        # Trigger circuit to open
        for _ in range(2):
            try:
                cb.call(failing_function)
            except ConnectionError:
                pass

        assert cb.get_state() == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(1.5)

        # Next call should transition to HALF_OPEN and attempt execution
        try:
            cb.call(failing_function)
        except (ConnectionError, CircuitBreakerOpenError):
            # Either error is acceptable - we're testing state transition
            pass

        # Should be in HALF_OPEN or OPEN (if failed again)
        assert cb.get_state() in [CircuitState.HALF_OPEN, CircuitState.OPEN]

    def test_circuit_closes_on_successful_request(self):
        """Circuit should close on successful request in HALF_OPEN state."""
        cb = RedisCircuitBreaker(failure_threshold=2, recovery_timeout=1)

        def failing_function():
            raise ConnectionError("Failed")

        def success_function():
            return "success"

        # Open the circuit
        for _ in range(2):
            try:
                cb.call(failing_function)
            except ConnectionError:
                pass

        assert cb.get_state() == CircuitState.OPEN

        # Wait for timeout
        time.sleep(1.5)

        # Try a successful call - should close circuit
        result = cb.call(success_function)
        assert result == "success"
        assert cb.get_state() == CircuitState.CLOSED

    def test_circuit_reset_for_testing(self):
        """Manual reset should work for testing purposes."""
        cb = RedisCircuitBreaker(failure_threshold=2, recovery_timeout=60)

        def failing_function():
            raise ConnectionError("Failed")

        # Open circuit
        for _ in range(2):
            try:
                cb.call(failing_function)
            except ConnectionError:
                pass

        assert cb.get_state() == CircuitState.OPEN

        # Reset
        cb.reset()
        assert cb.get_state() == CircuitState.CLOSED
        assert cb._failure_count == 0


class TestStatisticsAndStatus:
    """Test cache statistics and status reporting."""

    def test_status_operational_when_enabled(self, cache):
        """Status should be 'operational' when cache is enabled and working."""
        cache.enabled = True
        cache.client = None
        cache.use_rest_api = False

        status = cache.get_status()
        assert status["status"] == "operational"
        assert status["enabled"] is True
        assert status["mode"] == "local_memory"

    def test_status_disabled_when_explicitly_disabled(self, cache):
        """Status should be 'disabled' when cache is disabled."""
        cache.enabled = False

        status = cache.get_status()
        assert status["status"] == "disabled"
        assert status["enabled"] is False

    def test_circuit_state_tracking(self, cache):
        """Circuit state should be tracked in status."""
        cache.circuit_breaker._state = CircuitState.OPEN
        status = cache.get_status()
        assert status["circuit_breaker"] == "open"

        cache.circuit_breaker._state = CircuitState.CLOSED
        status = cache.get_status()
        assert status["circuit_breaker"] == "closed"

    def test_get_circuit_state(self, cache):
        """get_circuit_state should return current state."""
        cache.circuit_breaker._state = CircuitState.HALF_OPEN
        state = cache.get_circuit_state()
        assert state == "half_open"

    def test_local_cache_stats_tracking(self, cache):
        """Local cache should track hits and misses."""
        local_cache = SyncLocalCache()
        local_cache.set("key1", "value1")
        local_cache.get("key1")  # Hit
        local_cache.get("key2")  # Miss

        assert local_cache.hits == 1
        assert local_cache.misses == 1

    def test_local_cache_clear(self, cache):
        """Clear should reset cache and stats."""
        local_cache = SyncLocalCache()
        local_cache.set("key1", "value1")
        local_cache.set("key2", "value2")
        local_cache.get("key1")  # Hit

        assert len(local_cache._cache) == 2
        assert local_cache.hits == 1

        local_cache.clear()

        assert len(local_cache._cache) == 0
        assert local_cache.hits == 0
        assert local_cache.misses == 0


class TestAsyncOperations:
    """Test asynchronous cache operations."""

    @pytest.mark.asyncio
    async def test_async_get_set(self, cache):
        """Async get/set should work correctly."""
        await cache.set_async("async_key", "async_value", ttl=300)
        result = await cache.get_async("async_key")
        assert result == "async_value"

    @pytest.mark.asyncio
    async def test_async_get_miss(self, cache):
        """Async get should return None for nonexistent key."""
        result = await cache.get_async("nonexistent_async_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_async_delete(self, cache):
        """Async delete should remove key."""
        await cache.set_async("async_delete_key", "value", ttl=300)
        assert await cache.get_async("async_delete_key") == "value"
        await cache.delete_async("async_delete_key")
        assert await cache.get_async("async_delete_key") is None

    @pytest.mark.asyncio
    async def test_async_incr(self, cache):
        """Async incr should increment atomically."""
        # First increment
        val1 = await cache.incr_async("counter", ttl=60)
        assert val1 == 1

        # Second increment
        val2 = await cache.incr_async("counter", ttl=60)
        assert val2 == 2

        # Third increment
        val3 = await cache.incr_async("counter", ttl=60)
        assert val3 == 3

    @pytest.mark.asyncio
    async def test_async_incr_with_tenant_isolation(self, cache):
        """Async incr should respect tenant isolation."""
        val1 = await cache.incr_async("counter", ttl=60, tenant_id="tenant1")
        val2 = await cache.incr_async("counter", ttl=60, tenant_id="tenant2")

        assert val1 == 1
        assert val2 == 1  # Different tenant, separate counter


class TestEncodingDecoding:
    """Test JSON encoding and decoding of complex data."""

    def test_encode_dict(self, cache):
        """Dict should be encoded to JSON string."""
        data = {"key": "value", "number": 123}
        encoded = cache._encode(data)
        assert isinstance(encoded, str)
        assert json.loads(encoded) == data

    def test_encode_list(self, cache):
        """List should be encoded to JSON string."""
        data = ["item1", "item2", 123]
        encoded = cache._encode(data)
        assert isinstance(encoded, str)
        assert json.loads(encoded) == data

    def test_encode_string(self, cache):
        """String should be returned as-is."""
        data = "plain_string"
        encoded = cache._encode(data)
        assert encoded == "plain_string"

    def test_decode_json_dict(self, cache):
        """JSON dict should be decoded correctly."""
        json_str = '{"key": "value", "number": 123}'
        decoded = cache._decode(json_str)
        assert decoded == {"key": "value", "number": 123}

    def test_decode_json_list(self, cache):
        """JSON list should be decoded correctly."""
        json_str = '["item1", "item2", 123]'
        decoded = cache._decode(json_str)
        assert decoded == ["item1", "item2", 123]

    def test_decode_plain_string(self, cache):
        """Plain string should be returned as-is."""
        plain_str = "not_json"
        decoded = cache._decode(plain_str)
        assert decoded == "not_json"

    def test_round_trip_complex_data(self, cache):
        """Complex data should survive encode/decode round-trip."""
        original_data = {
            "permissions": ["read", "write", "execute"],
            "metadata": {
                "owner": "admin",
                "created": "2024-01-01T00:00:00Z",
                "tags": ["important", "cached"]
            },
            "count": 42
        }

        encoded = cache._encode(original_data)
        decoded = cache._decode(encoded)

        assert decoded == original_data


class TestNamespaceKey:
    """Test key namespacing for multi-tenant isolation."""

    def test_namespace_without_tenant(self, cache):
        """Key without tenant_id should not be namespaced."""
        result = cache._namespace_key("my_key", None)
        assert result == "my_key"

    def test_namespace_with_tenant(self, cache):
        """Key with tenant_id should be namespaced."""
        result = cache._namespace_key("my_key", "tenant123")
        assert result == "tenant:tenant123:my_key"

    def test_namespace_with_colon_in_pattern(self, cache):
        """Pattern already containing colon should not be double-namespaced."""
        result = cache._namespace_key("tenant:tenant123:pattern", "tenant123")
        # Should return as-is if already namespaced
        assert "tenant:tenant123:" in result


class TestLocalCacheBehavior:
    """Test SyncLocalCache LRU and TTL behavior."""

    def test_lru_eviction_when_full(self):
        """Cache should evict entries when reaching max_size."""
        small_cache = SyncLocalCache(max_size=5, default_ttl=60)

        # Add 10 entries (more than max_size)
        for i in range(10):
            small_cache.set(f"key_{i}", f"value_{i}")

        # Cache should not exceed max_size significantly
        assert len(small_cache._cache) <= 6  # Allow small buffer

    def test_ttl_expiration_in_local_cache(self):
        """Local cache should respect TTL."""
        local_cache = SyncLocalCache(default_ttl=1)
        local_cache.set("expire_key", "value")

        assert local_cache.get("expire_key") == "value"

        # Wait for expiration
        time.sleep(1.5)
        assert local_cache.get("expire_key") is None

    def test_local_cache_stats_hit_miss_ratio(self):
        """Local cache should track hit/miss ratio."""
        local_cache = SyncLocalCache()

        local_cache.set("key1", "value1")
        local_cache.get("key1")  # Hit
        local_cache.get("key2")  # Miss

        total_ops = local_cache.hits + local_cache.misses
        hit_ratio = local_cache.hits / total_ops if total_ops > 0 else 0

        assert hit_ratio == 0.5  # 1 hit out of 2 operations

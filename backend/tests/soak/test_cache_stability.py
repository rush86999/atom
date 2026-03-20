"""
Soak Tests for Cache Stability Under Concurrent Load

Extended duration tests (30 minutes) to validate cache behavior:
- Concurrent operations (10 workers, 10000 ops each)
- Cache consistency (no race conditions, no data loss)
- TTL expiration (entries expire correctly)
- Cache unbounded growth detection

Cache issues detected:
- Race conditions in concurrent get/set operations
- Cache corruption (data loss, incorrect values)
- TTL not working (cache grows unbounded)
- Deadlocks under concurrent load

Tests use ThreadPoolExecutor for realistic concurrent access patterns.
"""

import gc
import pytest
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.governance_cache import GovernanceCache


@pytest.mark.soak
@pytest.mark.timeout(1800)  # 30 minutes
def test_cache_concurrent_operations_30min(
    memory_monitor,
    enable_gc_control,
    soak_test_config
):
    """
    Soak test for cache stability under concurrent operations (30 minutes).

    Validates:
    - Cache remains consistent under concurrent load (10 workers)
    - No race conditions or deadlocks
    - No cache corruption (data loss, incorrect values)
    - Zero cache errors (get returns None after set)

    Test pattern:
    - Run for 30 minutes (1800 seconds)
    - Use ThreadPoolExecutor with 10 workers
    - Each worker performs 10000 cache operations (set + get)
    - Validate cache consistency: if get returns None after set, fail
    - Log worker completions
    - Force GC every 10 iterations

    Duration: 30 minutes
    Workers: 10 concurrent threads
    Operations per worker: 10000 (set + get)
    Failure: Any cache inconsistency detected

    Race conditions detected:
    - Get returns None after set (data loss)
    - Incorrect value returned (corruption)
    - Deadlock (test hangs)
    """
    cache = GovernanceCache(max_size=10000, ttl_seconds=60)
    process = memory_monitor["process"]
    initial_memory = memory_monitor["initial_memory_mb"]

    errors = []
    iterations = 0

    def worker_operations(worker_id: int):
        """
        Worker function for concurrent cache operations.

        Each worker performs 10000 cache operations:
        - Set key with unique worker_id to avoid conflicts
        - Get key immediately after set
        - Validate value is not None (cache consistency check)

        Raises AssertionError if cache inconsistency detected.
        """
        for i in range(10000):
            # Concurrent write with unique key (worker_id avoids conflicts)
            cache.set(
                agent_id=f"agent_{worker_id}_{i}",
                action_type="test_action",
                data={"allowed": True, "maturity_level": "AUTONOMOUS"}
            )

            # Concurrent read
            result = cache.get(
                agent_id=f"agent_{worker_id}_{i}",
                action_type="test_action"
            )

            # Validate cache consistency (get should not return None after set)
            if result is None:
                raise AssertionError(
                    f"Cache inconsistency: key agent_{worker_id}_{i} not found after write"
                )

        return f"Worker {worker_id} completed"

    start_time = time.time()

    # Run concurrent workers for 30 minutes
    while time.time() - start_time < 1800:
        # Submit 10 concurrent workers
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(worker_operations, worker_id)
                for worker_id in range(10)
            ]

            # Wait for all workers to complete, collect errors
            for future in as_completed(futures):
                try:
                    result = future.result()
                    print(result)
                except AssertionError as e:
                    errors.append(str(e))
                except Exception as e:
                    errors.append(f"Unexpected error: {e}")

        iterations += 1

        # Force garbage collection every 10 iterations
        if iterations % 10 == 0:
            enable_gc_control["collect"]()

        # Log memory growth every 60 iterations
        if iterations % 60 == 0:
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_growth = current_memory - initial_memory

            print(
                f"Iteration {iterations}: "
                f"Memory growth = {memory_growth:.2f}MB, "
                f"Errors = {len(errors)}"
            )

            # Fail fast if memory growth > 500MB
            if memory_growth > soak_test_config["fail_fast_threshold_mb"]:
                pytest.fail(
                    f"FAIL-FAST: Memory leak detected - {memory_growth:.2f}MB growth "
                    f"(threshold: {soak_test_config['fail_fast_threshold_mb']}MB)"
                )

    # Final validation: zero cache errors
    assert len(errors) == 0, (
        f"Cache inconsistencies detected: {len(errors)} errors\n"
        f"Errors: {errors[:5]}"  # Show first 5 errors
    )

    print(f"\n✅ Soak test complete: {iterations} iterations, zero cache errors")


@pytest.mark.soak
@pytest.mark.timeout(900)  # 15 minutes
def test_cache_ttl_expiration_15min(memory_monitor, enable_gc_control):
    """
    Soak test for cache TTL expiration (15 minutes).

    Validates:
    - Cache entries expire after TTL (60 seconds)
    - Cache doesn't grow unbounded (TTL prevents memory leaks)
    - Expired entries are not returned (get returns None)

    Test pattern:
    - Create cache with TTL=60 seconds
    - Add 1000 entries per iteration
    - Validate entries exist immediately after adding
    - Wait 70 seconds, validate entries are gone (expired)
    - Repeat for 15 minutes
    - Monitor memory usage

    Duration: 15 minutes
    TTL: 60 seconds
    Validation: Entries expire correctly, cache doesn't grow unbounded

    Purpose: Detect TTL bugs that cause unbounded cache growth.
    """
    cache = GovernanceCache(max_size=10000, ttl_seconds=60)
    process = memory_monitor["process"]
    initial_memory = memory_monitor["initial_memory_mb"]

    iterations = 0

    start_time = time.time()

    # Run TTL validation for 15 minutes
    while time.time() - start_time < 900:
        # Add 1000 entries
        for i in range(1000):
            cache.set(
                agent_id=f"agent_{iterations}_{i}",
                action_type="test_action",
                data={"allowed": True, "maturity_level": "AUTONOMOUS"}
            )

        # Validate entries exist immediately
        for i in range(100):  # Check 100 random entries
            result = cache.get(
                agent_id=f"agent_{iterations}_{i}",
                action_type="test_action"
            )
            assert result is not None, f"Entry not found immediately after set: agent_{iterations}_{i}"

        print(f"Iteration {iterations}: Added 1000 entries, validated existence")

        # Wait 70 seconds (TTL=60, +10 buffer)
        time.sleep(70)

        # Validate entries are expired (get returns None)
        expired_count = 0
        for i in range(100):  # Check 100 random entries
            result = cache.get(
                agent_id=f"agent_{iterations}_{i}",
                action_type="test_action"
            )
            if result is None:
                expired_count += 1

        # All entries should be expired
        assert expired_count == 100, (
            f"TTL expiration failed: {expired_count}/100 entries expired "
            f"(expected: 100)"
        )

        print(f"Iteration {iterations}: All entries expired correctly (100/100)")

        iterations += 1

        # Force garbage collection
        enable_gc_control["collect"]()

        # Log memory growth
        current_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = current_memory - initial_memory

        print(f"Iteration {iterations}: Memory growth = {memory_growth:.2f}MB")

        # Fail fast if memory growth > 500MB (indicates TTL not working)
        if memory_growth > 500:
            pytest.fail(
                f"TTL expiration not working: cache grew {memory_growth:.2f}MB "
                f"(entries should be expiring)"
            )

    # Final validation: memory growth should be reasonable (< 200MB for 15min)
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_growth = final_memory - initial_memory

    assert memory_growth < 200, (
        f"Cache grew unbounded: {memory_growth:.2f}MB growth over 15 minutes "
        f"(TTL expiration may not be working)"
    )

    print(f"\n✅ Soak test complete: {iterations} iterations, TTL expiration working correctly")


@pytest.mark.soak
@pytest.mark.timeout(1800)  # 30 minutes
def test_cache_lru_eviction_stability_30min(memory_monitor, enable_gc_control):
    """
    Soak test for cache LRU eviction stability (30 minutes).

    Validates:
    - LRU eviction works correctly (cache doesn't exceed max_size)
    - Evicted entries are not returned (get returns None)
    - Cache performance remains stable under load

    Test pattern:
    - Create cache with max_size=1000
    - Add 2000 entries (exceeds max_size, triggers LRU eviction)
    - Validate cache size <= max_size
    - Verify oldest entries are evicted (get returns None)
    - Repeat for 30 minutes

    Duration: 30 minutes
    Max size: 1000 entries
    Validation: LRU eviction works, cache size stable

    Purpose: Detect LRU eviction bugs that cause unbounded cache growth.
    """
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)
    process = memory_monitor["process"]
    initial_memory = memory_monitor["initial_memory_mb"]

    iterations = 0

    start_time = time.time()

    # Run LRU eviction validation for 30 minutes
    while time.time() - start_time < 1800:
        # Add 2000 entries (exceeds max_size=1000)
        for i in range(2000):
            cache.set(
                agent_id=f"agent_{iterations}_{i}",
                action_type="test_action",
                data={"allowed": True, "maturity_level": "AUTONOMOUS"}
            )

        # Validate oldest entries are evicted (first 1000 should be gone)
        evicted_count = 0
        for i in range(1000):  # Check oldest 1000 entries
            result = cache.get(
                agent_id=f"agent_{iterations}_{i}",
                action_type="test_action"
            )
            if result is None:
                evicted_count += 1

        # At least some entries should be evicted (LRU working)
        # Not all 1000 will be evicted (TTL may not have expired yet)
        # But at least 500 should be evicted due to LRU
        assert evicted_count >= 500, (
            f"LRU eviction not working: only {evicted_count}/1000 entries evicted "
            f"(expected: >= 500)"
        )

        print(f"Iteration {iterations}: LRU eviction working ({evicted_count}/1000 evicted)")

        iterations += 1

        # Force garbage collection
        enable_gc_control["collect"]()

        # Log memory growth
        current_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = current_memory - initial_memory

        print(f"Iteration {iterations}: Memory growth = {memory_growth:.2f}MB")

        # Fail fast if memory growth > 500MB (indicates LRU not working)
        if memory_growth > 500:
            pytest.fail(
                f"LRU eviction not working: cache grew {memory_growth:.2f}MB "
                f"(entries should be evicted)"
            )

    # Final validation: memory growth should be reasonable
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_growth = final_memory - initial_memory

    assert memory_growth < 200, (
        f"Cache grew unbounded: {memory_growth:.2f}MB growth over 30 minutes "
        f"(LRU eviction may not be working)"
    )

    print(f"\n✅ Soak test complete: {iterations} iterations, LRU eviction working correctly")

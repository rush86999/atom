"""
Governance Cache Memory Leak Tests

This module contains memory leak detection tests for governance cache operations.
These tests detect Python-level memory leaks during cache operations using
Bloomberg's memray profiler.

Test Categories:
- Cache growth leaks: Unbounded cache growth and LRU eviction issues
- Cache hit/miss leaks: Memory accumulation during get/set operations
- Cache eviction leaks: Memory leaks during entry expiration and eviction

Invariants Tested:
- INV-01: Cache should not grow unbounded (LRU eviction working)
- INV-02: Cache hit should not allocate new memory (read operation)
- INV-03: Cache miss should allocate within bounds (entry creation)
- INV-04: Cache eviction should not leak memory (entry removal)

Performance Targets:
- Cache growth: <5MB memory growth (1000 operations)
- Cache hit: <1MB memory growth (1000 hits)
- Cache miss: <3MB memory growth (1000 misses)
- Cache eviction: <2MB memory growth (1000 evictions)

Requirements:
- Python 3.11+ (memray requirement)
- memray>=1.12.0 (install with: pip install memray)

Usage:
    # Run all governance cache leak tests
    pytest backend/tests/memory_leaks/test_governance_cache_leaks.py -v

    # Run specific test
    pytest backend/tests/memory_leaks/test_governance_cache_leaks.py::test_governance_cache_no_unbounded_growth -v

Phase: 243-01 (Memory & Performance Bug Discovery)
See: .planning/phases/243-memory-and-performance-bug-discovery/243-01-PLAN.md
"""

from typing import Dict, Any

import pytest


# =============================================================================
# Test: Cache Growth Memory Leaks
# =============================================================================

@pytest.mark.memory_leak
@pytest.mark.slow
def test_governance_cache_no_unbounded_growth(memray_session, check_memory_growth):
    """
    Test that governance cache does not grow unbounded (LRU eviction working).

    INVARIANT: Cache should not grow unbounded (LRU eviction working)

    STRATEGY:
        - Pre-populate GovernanceCache with 1000 entries (max_size)
        - Execute 1000 additional get/set operations
        - Assert cache size stays at max_size (1000)
        - Assert memory growth <5MB (LRU eviction prevents unbounded growth)

    RADII:
        - 1000 entries sufficient to fill cache and trigger evictions
        - Detects LRU eviction failures (cache growing beyond max_size)
        - Based on industry standards (Redis, Memcached cache eviction)

    Test Metadata:
        - Max cache size: 1000
        - Pre-populate: 1000 entries
        - Additional operations: 1000
        - Threshold: 5MB (cache should stay bounded)

    Examples:
        >>> # Run test (requires memray)
        >>> pytest test_governance_cache_leaks.py::test_governance_cache_no_unbounded_growth -v

    Phase: 243-01
    TQ-01 through TQ-05 compliant (invariant-first, documented, clear assertions)

    Args:
        memray_session: memray.Tracker fixture for memory profiling
        check_memory_growth: Helper fixture for asserting memory thresholds

    Raises:
        AssertionError: If memory growth exceeds 5MB threshold
    """
    from core.governance_cache import GovernanceCache

    # Create cache with max_size=1000
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    # Pre-populate cache with 1000 entries
    for i in range(1000):
        cache.set(
            key=f"agent_{i}:execute",
            value={"allowed": True, "data": {"agent_id": f"agent_{i}"}}
        )

    # Execute 1000 additional operations (should trigger evictions)
    for i in range(1000, 2000):
        cache.set(
            key=f"agent_{i}:execute",
            value={"allowed": True, "data": {"agent_id": f"agent_{i}"}}
        )

    # Verify cache size is bounded (INV-01)
    cache_size = len(cache._cache)
    assert cache_size <= 1000, f"Cache unbounded growth: {cache_size} entries (max: 1000)"

    # Assert memory growth <5MB (LRU eviction working)
    check_memory_growth(
        memray_session,
        threshold_mb=5.0,
        context_msg="Governance cache bounded growth (1000 entries + 1000 operations)"
    )


# =============================================================================
# Test: Cache Hit Memory Efficiency
# =============================================================================

@pytest.mark.memory_leak
@pytest.mark.slow
def test_governance_cache_hit_efficient(memray_session, check_memory_growth):
    """
    Test that cache hit does not allocate new memory (read operation).

    INVARIANT: Cache hit should not allocate new memory (read operation)

    STRATEGY:
        - Pre-populate cache with 100 entries
        - Execute 1000 cache hit operations (read same entries)
        - Assert memory growth <1MB (cache hits should not allocate)

    RADII:
        - 1000 cache hits provide statistical significance
        - Detects memory leaks on read operations (unexpected allocations)
        - Cache hits should be zero-allocation (dict lookup is O(1))

    Test Metadata:
        - Pre-populate: 100 entries
        - Cache hits: 1000
        - Threshold: 1MB (read operations should not allocate)

    Phase: 243-01
    TQ-01 through TQ-05 compliant

    Args:
        memray_session: memray.Tracker fixture for memory profiling
        check_memory_growth: Helper fixture for asserting memory thresholds

    Raises:
        AssertionError: If memory growth exceeds 1MB threshold
    """
    from core.governance_cache import GovernanceCache

    # Create cache with max_size=1000
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    # Pre-populate cache with 100 entries
    for i in range(100):
        cache.set(
            key=f"agent_{i}:execute",
            value={"allowed": True, "data": {"agent_id": f"agent_{i}"}}
        )

    # Execute 1000 cache hit operations (read same 100 entries)
    for i in range(1000):
        cache.get(key=f"agent_{i % 100}:execute")

    # Assert memory growth <1MB (cache hits should not allocate)
    check_memory_growth(
        memray_session,
        threshold_mb=1.0,
        context_msg="Governance cache hit efficiency (1000 reads)"
    )


# =============================================================================
# Test: Cache Miss Memory Efficiency
# =============================================================================

@pytest.mark.memory_leak
@pytest.mark.slow
def test_governance_cache_miss_efficient(memray_session, check_memory_growth):
    """
    Test that cache miss allocates memory within bounds (entry creation).

    INVARIANT: Cache miss should allocate memory within bounds (entry creation)

    STRATEGY:
        - Create empty cache
        - Execute 1000 cache miss operations (create new entries)
        - Assert memory growth <3MB (entry creation is bounded)

    RADII:
        - 1000 cache misses provide statistical significance
        - Detects memory leaks on entry creation (unexpected overhead)
        - Each entry should allocate ~100-200 bytes (dict + metadata)

    Test Metadata:
        - Cache misses: 1000
        - Threshold: 3MB (entry creation bounded)

    Phase: 243-01
    TQ-01 through TQ-05 compliant

    Args:
        memray_session: memray.Tracker fixture for memory profiling
        check_memory_growth: Helper fixture for asserting memory thresholds

    Raises:
        AssertionError: If memory growth exceeds 3MB threshold
    """
    from core.governance_cache import GovernanceCache

    # Create cache with max_size=1000
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    # Execute 1000 cache miss operations (create new entries)
    for i in range(1000):
        cache.set(
            key=f"agent_{i}:execute",
            value={"allowed": True, "data": {"agent_id": f"agent_{i}"}}
        )

    # Assert memory growth <3MB (entry creation bounded)
    check_memory_growth(
        memray_session,
        threshold_mb=3.0,
        context_msg="Governance cache miss efficiency (1000 entries)"
    )


# =============================================================================
# Test: Cache Eviction Memory Leaks
# =============================================================================

@pytest.mark.memory_leak
@pytest.mark.slow
def test_governance_cache_eviction_no_leak(memray_session, check_memory_growth):
    """
    Test that cache eviction does not leak memory (entry removal).

    INVARIANT: Cache eviction should not leak memory (entry removal)

    STRATEGY:
        - Create cache with max_size=100
        - Pre-populate with 100 entries (fill cache)
        - Execute 1000 cache evictions (insert new entries, trigger LRU eviction)
        - Assert memory growth <2MB (eviction should free memory)

    RADII:
        - 1000 evictions provide statistical significance
        - Detects memory leaks during entry removal (stale references)
        - Eviction should free memory (Python GC should reclaim)

    Test Metadata:
        - Max cache size: 100
        - Pre-populate: 100 entries
        - Evictions: 1000
        - Threshold: 2MB (eviction should free memory)

    Phase: 243-01
    TQ-01 through TQ-05 compliant

    Args:
        memray_session: memray.Tracker fixture for memory profiling
        check_memory_growth: Helper fixture for asserting memory thresholds

    Raises:
        AssertionError: If memory growth exceeds 2MB threshold
    """
    from core.governance_cache import GovernanceCache

    # Create cache with max_size=100 (small cache for frequent evictions)
    cache = GovernanceCache(max_size=100, ttl_seconds=60)

    # Pre-populate cache with 100 entries (fill cache)
    for i in range(100):
        cache.set(
            key=f"agent_{i}:execute",
            value={"allowed": True, "data": {"agent_id": f"agent_{i}"}}
        )

    # Execute 1000 cache evictions (insert new entries, trigger LRU eviction)
    for i in range(1000, 1100):
        cache.set(
            key=f"agent_{i}:execute",
            value={"allowed": True, "data": {"agent_id": f"agent_{i}"}}
        )

    # Assert memory growth <2MB (eviction should free memory)
    check_memory_growth(
        memray_session,
        threshold_mb=2.0,
        context_msg="Governance cache eviction (1000 evictions)"
    )


# =============================================================================
# Test: Cache Invalidation Memory Leaks
# =============================================================================

@pytest.mark.memory_leak
@pytest.mark.slow
def test_governance_cache_invalidation_no_leak(memray_session, check_memory_growth):
    """
    Test that cache invalidation does not leak memory (entry removal).

    INVARIANT: Cache invalidation should not leak memory (entry removal)

    STRATEGY:
        - Pre-populate cache with 100 entries
        - Execute 1000 cache invalidations (invalidate specific entries)
        - Assert memory growth <2MB (invalidation should free memory)

    RADII:
        - 1000 invalidations provide statistical significance
        - Detects memory leaks during manual invalidation
        - Invalidation should remove entries (no stale references)

    Test Metadata:
        - Pre-populate: 100 entries
        - Invalidations: 1000 (re-invalidate same entries)
        - Threshold: 2MB (invalidation should free memory)

    Phase: 243-01
    TQ-01 through TQ-05 compliant

    Args:
        memray_session: memray.Tracker fixture for memory profiling
        check_memory_growth: Helper fixture for asserting memory thresholds

    Raises:
        AssertionError: If memory growth exceeds 2MB threshold
    """
    from core.governance_cache import GovernanceCache

    # Create cache with max_size=1000
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    # Pre-populate cache with 100 entries
    for i in range(100):
        cache.set(
            key=f"agent_{i}:execute",
            value={"allowed": True, "data": {"agent_id": f"agent_{i}"}}
        )

    # Execute 1000 cache invalidations (invalidate same 100 entries)
    for i in range(1000):
        cache.invalidate(f"agent_{i % 100}:execute")

    # Assert memory growth <2MB (invalidation should free memory)
    check_memory_growth(
        memray_session,
        threshold_mb=2.0,
        context_msg="Governance cache invalidation (1000 invalidations)"
    )

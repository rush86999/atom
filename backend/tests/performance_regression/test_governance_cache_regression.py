"""
Governance Cache Regression Tests

Detects performance regressions in governance cache operations by comparing
current benchmark results against historical baselines.

Tests:
- Cache hit rate with 100 entries (target: >95%)
- Cache get latency (target: <1ms)
- Cache set latency (target: <1ms)

Uses pytest-benchmark for historical tracking and check_regression fixture
to fail tests when performance degrades beyond 20% threshold.

Baselines stored in performance_baseline.json:
- cache_hit_rate: 0.95 (95%)
- cache_get_latency: 0.001s (1ms)
- cache_set_latency: 0.001s (1ms)

Reference: Phase 243 Plan 02 - Performance Regression Detection
"""

import pytest
from uuid import uuid4

from core.governance_cache import GovernanceCache

# Try to import pytest_benchmark, but don't fail if not available
try:
    import pytest_benchmark
    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False

# Skip all tests if pytest-benchmark is not available
pytestmark = pytest.mark.skipif(
    not BENCHMARK_AVAILABLE,
    reason="pytest-benchmark plugin not installed. Install with: pip install pytest-benchmark"
)

pytestmark = pytest.mark.performance_regression


@pytest.mark.benchmark(group="governance-cache")
def test_governance_cache_hit_rate(benchmark, check_regression):
    """
    Benchmark governance cache hit rate.

    Target: >95% hit rate (cache should be effective)
    Operation: 100 cache.set() followed by 100 cache.get()
    Baseline: cache_hit_rate (0.95)
    Threshold: 20% regression (hit rate should not drop below 76%)

    Test Quality Standards (TQ-01):
    - Clear objective: Measure cache hit rate for effective caching
    - Documented target: >95% hit rate
    - Baseline value: 0.95 (95%)
    - Benchmark grouping: @pytest.mark.benchmark(group="governance-cache")
    - Pre-populated cache: 100 entries for realistic load
    """
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    # Pre-populate cache with 100 entries
    for i in range(100):
        cache.set(f"agent_{i}", "action", {"allowed": True, "data": {"test": i}})

    def measure_hit_rate():
        hits = 0
        total = 100

        for i in range(total):
            result = cache.get(f"agent_{i}", "action")
            if result is not None:
                hits += 1

        hit_rate = hits / total
        return hit_rate

    hit_rate = benchmark(measure_hit_rate)

    # Check regression: hit rate should not drop >20% from baseline
    # Note: For hit rates, higher is better, so check_regression inverts the logic
    check_regression(hit_rate, "cache_hit_rate", threshold=0.2)

    # Verify high hit rate
    assert hit_rate >= 0.76  # 95% * (1 - 0.2) = 76% minimum


@pytest.mark.benchmark(group="governance-cache")
def test_governance_cache_get_latency(benchmark, check_regression):
    """
    Benchmark governance cache get() operation latency.

    Target: <1ms P50 (cache lookups must be instant)
    Operation: cache.get() for existing key
    Baseline: cache_get_latency (0.001s)
    Threshold: 20% regression

    Test Quality Standards (TQ-01):
    - Clear objective: Measure cache get latency (critical for performance)
    - Documented target: <1ms P50
    - Baseline value: 0.001s (1ms)
    - Benchmark grouping: @pytest.mark.benchmark(group="governance-cache")
    - Pre-populated cache: Ensures cache hits (not misses)
    """
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    # Pre-populate cache
    cache.set("agent_test", "action", {"allowed": True, "data": {"test": "value"}})

    def cache_get():
        result = cache.get("agent_test", "action")
        assert result is not None
        assert result["allowed"] is True
        return result

    result = benchmark(cache_get)

    # Check regression: should not be >20% slower than baseline
    check_regression(benchmark.stats.stats.mean, "cache_get_latency", threshold=0.2)

    # Verify cache hit
    assert result is not None
    assert result["allowed"] is True


@pytest.mark.benchmark(group="governance-cache")
def test_governance_cache_set_latency(benchmark, check_regression):
    """
    Benchmark governance cache set() operation latency.

    Target: <1ms P50 (cache writes must be fast)
    Operation: cache.set() for new key
    Baseline: cache_set_latency (0.001s)
    Threshold: 20% regression

    Test Quality Standards (TQ-01):
    - Clear objective: Measure cache set latency (critical for write performance)
    - Documented target: <1ms P50
    - Baseline value: 0.001s (1ms)
    - Benchmark grouping: @pytest.mark.benchmark(group="governance-cache")
    - Unique keys: Avoids cache eviction during benchmark
    """
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    # Use unique key for each benchmark iteration to avoid eviction
    def cache_set():
        unique_key = f"agent_{uuid4()}"
        result = cache.set(unique_key, "action", {"allowed": True, "data": {"test": "value"}})
        assert result is True
        return result

    result = benchmark(cache_set)

    # Check regression: should not be >20% slower than baseline
    check_regression(benchmark.stats.stats.mean, "cache_set_latency", threshold=0.2)

    # Verify cache write succeeded
    assert result is True


@pytest.mark.benchmark(group="governance-cache")
def test_governance_cache_statistics(benchmark):
    """
    Benchmark governance cache statistics retrieval.

    Target: <1ms P50 (statistics must be cheap to retrieve)
    Operation: cache.get_statistics()
    Verify: Statistics include hits, misses, hit_rate

    Note: No baseline check for this test (statistics is a diagnostic operation,
    not a critical path).
    """
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    # Populate cache with some activity
    for i in range(50):
        cache.set(f"agent_{i}", "action", {"allowed": True})
    for i in range(50):
        cache.get(f"agent_{i}", "action")

    def get_stats():
        stats = cache.get_statistics()
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        return stats

    stats = benchmark(get_stats)

    # Verify statistics are available
    assert stats["hits"] >= 0
    assert stats["misses"] >= 0
    assert 0 <= stats["hit_rate"] <= 1


class TestGovernanceCacheQualityTargets:
    """
    Verify governance cache quality targets are documented and achievable.

    These tests validate that the performance targets are reasonable
    and that the baseline values are correctly defined.
    """

    def test_cache_hit_rate_baseline_exists(self, performance_baseline):
        """Verify cache_hit_rate baseline is defined."""
        assert "cache_hit_rate" in performance_baseline
        assert performance_baseline["cache_hit_rate"] == 0.95

    def test_cache_get_latency_baseline_exists(self, performance_baseline):
        """Verify cache_get_latency baseline is defined."""
        assert "cache_get_latency" in performance_baseline
        assert performance_baseline["cache_get_latency"] == 0.001

    def test_cache_set_latency_baseline_exists(self, performance_baseline):
        """Verify cache_set_latency baseline is defined."""
        assert "cache_set_latency" in performance_baseline
        assert performance_baseline["cache_set_latency"] == 0.001

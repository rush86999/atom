# Soak Testing Guide

## Overview

Soak tests are extended duration tests (1-4 hours) that validate system stability under continuous load. Unlike load tests (short duration, high concurrency), soak tests run for hours to detect **memory leaks**, **connection pool exhaustion**, and **resource leaks** that only appear over time.

**Why soak tests matter:**
- Memory leaks are slow (10-50 MB/hour) and don't appear in 5-minute load tests
- Connection pool exhaustion only happens after thousands of operations
- Cache unbounded growth causes OOM crashes after 24-48 hours in production
- Production systems run for days/weeks, not minutes

**What soak tests detect:**
- Memory leaks (unbounded growth)
- Connection pool leaks (connections not returned)
- Cache stability issues (race conditions, TTL not working)
- Resource exhaustion (file descriptors, sockets)

## Running Soak Tests

### Quick Start

```bash
# Run all soak tests
cd backend
pytest tests/soak/ -v

# Run with timeout override (default: 1 hour)
pytest tests/soak/ -v --timeout=7200  # 2 hours

# Run only soak tests (using marker)
pytest -m soak -v

# Run specific test file
pytest tests/soak/test_memory_stability.py -v

# Run specific test
pytest tests/soak/test_memory_stability.py::test_governance_cache_memory_stability_1hr -v

# Run with verbose output (see memory growth logs)
pytest tests/soak/ -v -s
```

### Test Duration Table

| Test | Duration | Memory Threshold | Purpose |
|------|----------|------------------|---------|
| `test_governance_cache_memory_stability_1hr` | 1 hour | <100MB growth | Detect cache memory leaks |
| `test_episode_service_memory_stability_30min` | 30 min | <50MB growth | Detect episode service leaks |
| `test_connection_pool_no_leaks_2hr` | 2 hours | Pool size stable | Detect connection pool leaks |
| `test_connection_pool_rapid_operations_1hr` | 1 hour | Pool size stable | Detect pool performance issues |
| `test_cache_concurrent_operations_30min` | 30 min | Zero errors | Detect cache race conditions |
| `test_cache_ttl_expiration_15min` | 15 min | <200MB growth | Detect TTL not working |
| `test_cache_lru_eviction_stability_30min` | 30 min | <200MB growth | Detect LRU not working |

### Prerequisites

```bash
# Install dependencies
pip install -r requirements-testing.txt

# Ensure psutil is installed (memory monitoring)
pip show psutil  # Should show version 5.9+

# Ensure pytest-timeout is installed (test timeout enforcement)
pip show pytest-timeout  # Should show version 2.1+
```

### Running Soak Tests in CI/CD

**WARNING:** Soak tests are too long for CI/CD (1-2 hours). Run on schedule instead.

```yaml
# .github/workflows/soak-tests.yml
name: Soak Tests

on:
  schedule:
    # Run soak tests daily at 3 AM UTC
    - cron: '0 3 * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  soak-test:
    name: Run Soak Tests
    runs-on: ubuntu-large
    timeout-minutes: 150  # 2.5 hours (includes setup time)

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install -r requirements-testing.txt

      - name: Run soak tests
        run: |
          cd backend
          pytest tests/soak/ -v --timeout=7200

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: soak-test-results
          path: backend/tests/soak/.pytest_cache/
```

### Running Soak Tests Locally

```bash
# Run in background (for long-running tests)
nohup pytest tests/soak/test_memory_stability.py -v > soak_test.log 2>&1 &

# Monitor progress
tail -f soak_test.log

# Check if test is still running
ps aux | grep pytest

# Check memory usage of test process
ps aux | grep pytest | awk '{print $6}'  # RSS in KB
```

## Interpreting Results

### Memory Growth

**What it means:** Memory growth indicates a memory leak or unbounded cache growth.

**Thresholds:**
- <50MB over 30 min: Acceptable (normal cache warming)
- <100MB over 1 hour: Acceptable (some growth expected)
- <200MB over 2 hours: Acceptable (connection pool overhead)
- >500MB: **FAIL-FAST** (immediate failure, severe leak)

**Example output:**
```
Iteration 60: Memory = 245.32MB, Growth = +45.23MB
Iteration 120: Memory = 267.89MB, Growth = +67.80MB
Iteration 180: Memory = 289.12MB, Growth = +89.03MB
Iteration 240: Memory = 312.45MB, Growth = +112.36MB
```

**In this example:** Memory growth is ~112MB over 240 iterations (~40 minutes). This is **passing** (threshold: 100MB over 1 hour), but growing. If it continues linear growth, it will fail at ~60 minutes.

### Connection Pool Status

**What it means:** Connection pool size and checked-in connections indicate connection leaks.

**Healthy output:**
```
Initial pool state: size=5, checked_in=5
Iteration 300: Pool size=5, Checked in=5
Iteration 600: Pool size=5, Checked in=5
Final pool state: size=5, checked_in=5
```

**Leak detected:**
```
Initial pool state: size=5, checked_in=5
Iteration 300: Pool size=8, Checked in=3  # 3 connections leaked!
Iteration 600: Pool size=12, Checked in=1  # 1 connection leaked!
FAIL: Connection pool grown: 5 -> 12 (threshold: +10)
```

**In this example:** Pool size grew from 5 to 12, checked-in dropped from 5 to 1. This indicates **11 connections not returned to pool** (connection leak).

### Cache Consistency Errors

**What it means:** Cache consistency errors indicate race conditions or cache corruption.

**Healthy output:**
```
Worker 0 completed
Worker 1 completed
...
Worker 9 completed
Iteration 1: Memory growth = +12.34MB, Errors = 0
```

**Errors detected:**
```
Worker 0 completed
Worker 1 completed
ERROR: Cache inconsistency: key agent_2_3456 not found after write
ERROR: Cache inconsistency: key agent_5_7890 not found after write
Iteration 1: Memory growth = +15.67MB, Errors = 2
FAIL: Cache inconsistencies detected: 2 errors
```

**In this example:** 2 cache inconsistencies detected (get returned None after set). This indicates **race condition** in concurrent cache operations.

## Troubleshooting

### False Positives

**Issue:** Test fails but no actual leak (GC hasn't run yet).

**Solution:** Check if GC is running. If memory growth is small (<50MB) and test fails, increase GC frequency or threshold.

**Example:**
```python
# Force GC more frequently (every 5 iterations instead of 10)
if iterations % 5 == 0:
    enable_gc_control["collect"]()
```

### GC Behavior

**Issue:** Memory grows then drops (GC cycle).

**Solution:** This is normal. Python's GC is lazy. Memory grows until GC runs, then drops. Look at **trend** (linear growth = leak, sawtooth pattern = normal).

**Example:**
```
Iteration 60: Memory = 245.32MB, Growth = +45.23MB
Iteration 70: GC collected
Iteration 120: Memory = 230.15MB, Growth = +30.06MB  # Dropped after GC
Iteration 180: Memory = 235.78MB, Growth = +35.69MB  # Stable (OK)
```

**In this example:** Memory growth is stable (+30-35MB) after GC. This is **normal** (not a leak).

### External Factors

**Issue:** Test fails intermittently (flaky).

**Solution:** Check external factors:
- Other processes using memory (close Chrome, IDE)
- Database connection pool size (increase if exhausted)
- System load (run on dedicated machine)
- Network latency (use localhost for tests)

**Example:**
```bash
# Check system memory before running test
free -h  # Linux
vm_stat  # macOS

# Close memory-heavy processes
chrome --quit
```

### SQLite vs PostgreSQL

**Issue:** Connection pool tests skip on SQLite (StaticPool vs QueuePool).

**Solution:** This is expected. SQLite uses StaticPool (single connection), PostgreSQL uses QueuePool (connection pool). Connection pool tests only apply to QueuePool.

**Example:**
```
SKIP: Connection pool test requires QueuePool (SQLite uses StaticPool)
```

## CI/CD Considerations

### Too Long for CI

**Issue:** Soak tests take 1-2 hours, blocking CI pipeline.

**Solution:** Run soak tests on schedule (daily/weekly), not on every commit.

**Example:**
```yaml
# Run on schedule (daily at 3 AM)
on:
  schedule:
    - cron: '0 3 * * *'
```

### Timeout Errors

**Issue:** CI timeout kills soak test (default: 60 minutes).

**Solution:** Increase CI job timeout to 150 minutes (2.5 hours).

**Example:**
```yaml
jobs:
  soak-test:
    timeout-minutes: 150  # 2.5 hours
```

### Resource Limits

**Issue:** CI runner has limited resources (CPU, memory).

**Solution:** Use larger CI runner (ubuntu-large vs ubuntu-latest).

**Example:**
```yaml
jobs:
  soak-test:
    runs-on: ubuntu-large  # More CPU/memory
```

## Test Development

### Adding New Soak Tests

**Template:**
```python
@pytest.mark.soak
@pytest.mark.timeout(3600)  # 1 hour
def test_your_component_stability(memory_monitor, enable_gc_control, soak_test_config):
    """
    Soak test for your component (1 hour).

    Validates:
    - Your component doesn't leak memory
    - Memory growth < 100MB over 1 hour

    Duration: 1 hour
    Threshold: < 100MB memory growth
    """
    process = memory_monitor["process"]
    initial_memory = memory_monitor["initial_memory_mb"]

    start_time = time.time()
    iterations = 0

    while time.time() - start_time < 3600:
        # Your operations here
        iterations += 1

        # Force GC every 10 iterations
        if iterations % 10 == 0:
            enable_gc_control["collect"]()

        # Log memory every 60 iterations
        if iterations % 60 == 0:
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_growth = current_memory - initial_memory
            print(f"Iteration {iterations}: Memory growth = {memory_growth:.2f}MB")

            # Fail fast if > 500MB growth
            if memory_growth > soak_test_config["fail_fast_threshold_mb"]:
                pytest.fail(f"Memory leak detected: {memory_growth:.2f}MB")

    # Final validation
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_growth = final_memory - initial_memory

    assert memory_growth < soak_test_config["memory_threshold_1hr_mb"], (
        f"Memory leak detected: {memory_growth:.2f}MB growth over 1 hour"
    )

    print(f"✅ Soak test complete: {iterations} iterations, {memory_growth:.2f}MB growth")
```

### Best Practices

1. **Use realistic operations:** Test actual component behavior, not synthetic loops.
2. **Force GC periodically:** Call `gc.collect()` every 10 iterations to distinguish leaks from cached data.
3. **Log memory growth:** Print memory usage every 60 iterations for monitoring.
4. **Fail fast:** Abort test if memory growth > 500MB (severe leak).
5. **Use appropriate thresholds:** 100MB for 1hr, 200MB for 2hr (industry standard).
6. **Validate consistency:** For concurrent tests, validate data integrity (not just memory).

## References

- **Phase 209 Research:** `.planning/phases/209-load-stress-testing/209-RESEARCH.md`
- **psutil Documentation:** https://psutil.readthedocs.io/
- **pytest-timeout Documentation:** https://github.com/pytest-dev/pytest-timeout
- **Python Garbage Collection:** https://docs.python.org/3/library/gc.html

## Support

For questions or issues with soak tests:
1. Check this README for common issues
2. Review Phase 209 research for methodology
3. Check test output for specific error messages
4. Verify environment (dependencies, database, system resources)

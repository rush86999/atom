# Stress Testing Guide

This directory contains stress tests for Atom to identify system capacity limits, breaking points, and behavior under extreme load (beyond normal operation).

## What is Stress Testing?

**Stress testing** vs **Load testing** vs **Performance testing**:

- **Performance testing**: Validates system meets performance targets under normal load (single-user or small concurrent load)
- **Load testing**: Validates system behavior under expected concurrent user load (e.g., 100 concurrent users)
- **Stress testing**: Identifies breaking points by testing beyond expected load (e.g., 1000 concurrent users)

**Stress tests answer:**
- What is the system's breaking point?
- How does the system degrade when overwhelmed?
- What are the capacity limits for production?
- Are there deadlocks or race conditions under concurrent load?

## Running Stress Tests

### Run All Stress Tests

```bash
# From backend directory
pytest tests/stress/ -v

# With detailed output
pytest tests/stress/ -v -s

# Run specific test file
pytest tests/stress/test_concurrent_users.py -v

# Run specific test
pytest tests/stress/test_concurrent_users.py::test_concurrent_health_checks_100_users -v
```

### Run Stress Tests in CI/CD

```bash
# Quick smoke test (subset of tests)
pytest tests/stress/ -k "test_concurrent_health_checks" -v

# Full stress test suite (run in staging only)
pytest tests/stress/ -v --timeout=300
```

## Test Categories

### 1. Concurrent Users (`test_concurrent_users.py`)

Tests system capacity under concurrent user load to identify breaking points.

**Tests:**
- `test_concurrent_health_checks_100_users`: 100 concurrent health check requests
- `test_concurrent_agent_requests_ramp_up`: Ramp from 10 to 500 users to find breaking point
- `test_concurrent_workflow_executions`: 50 concurrent workflow executions
- `test_concurrent_governance_checks`: 200 concurrent governance cache lookups
- `test_mixed_concurrent_load`: 100 concurrent requests with realistic user patterns

**What it measures:**
- Success rate (% of requests that succeed)
- Average latency (ms)
- P95/P99 latency (ms)
- Breaking point (where success_rate drops below 90%)

**Capacity targets:**
- Target: 100 concurrent users (SaaS industry standard)
- Stretch: 500-1000 concurrent users
- Failure rate: Should remain <1% until breaking point

### 2. Rate Limiting (`test_rate_limiting.py`)

Tests rate limiting behavior under extreme load.

**Tests:**
- `test_rate_limiting_enforcement`: 100 rapid requests to trigger rate limiting
- `test_rate_limit_per_user`: Validates per-user rate limiting (not global)
- `test_rate_limit_recovery`: Tests backoff behavior after rate limit
- `test_rate_limit_burst_traffic`: Burst traffic pattern (3 bursts of 20 requests)
- `test_rate_limit_different_endpoints`: Cross-endpoint rate limiting validation

**What it validates:**
- 429 (Too Many Requests) responses appear after threshold
- Retry-After header is present
- Rate limiting is per-user, not global
- System recovers after waiting for Retry-After period

### 3. Connection Exhaustion (`test_connection_exhaustion.py`)

Tests database and HTTP connection pool limits.

**Tests:**
- `test_database_pool_exhaustion`: 50 concurrent database sessions
- `test_database_connection_reuse`: 100 iterations to validate connection reuse
- `test_websocket_connection_limits`: 100 concurrent WebSocket connections
- `test_http_connection_pool_stress`: 1000 requests over 10 connections
- `test_database_pool_timeout`: Connection timeout behavior when pool is exhausted

**What it validates:**
- No connection leaks (all sessions closed)
- Pool size remains stable
- Connections are reused efficiently
- Graceful rejection after connection limit

**Pool configuration (from `core/database.py`):**
```python
# PostgreSQL
pool_size = 20
max_overflow = 30
pool_timeout = 30

# SQLite
# Single connection (no pooling)
```

### 4. Concurrency Safety (`test_concurrency_safety.py`)

Explicitly validates zero deadlocks and zero race conditions (LOAD-04 requirement).

**Tests:**
- `test_concurrent_database_operations_no_deadlocks`: 100 concurrent DB operations with 60s timeout
- `test_concurrent_cache_operations_no_races`: 50 workers × 100 increments to detect lost updates
- `test_concurrent_governance_checks_no_hangs`: 200 concurrent lookups with 30s timeout
- `test_concurrent_atomic_operations`: Validates atomic database transactions
- `test_concurrent_session_management_no_leaks`: 100 concurrent session operations

**What it validates:**
- **Deadlock detection**: Tests complete within timeout (hanging = deadlock)
- **Race condition detection**: Exact final value after concurrent increments (lost updates = race)
- **Lock contention**: No hangs during concurrent cache lookups
- **Connection leaks**: All sessions closed, connections returned to pool

## Interpreting Results

### Breaking Point

The breaking point is where the system's success rate drops below 90%.

**Example:**
```
Ramp-Up Test Summary:
  10 users: 100.00% success, 45.23ms avg
  50 users: 100.00% success, 89.12ms avg
 100 users:  98.50% success, 156.78ms avg
 500 users:  72.30% success, 456.12ms avg

⚠️  BREAKING POINT DETECTED at 500 users
```

**What this means:**
- System can handle up to ~100 users with <1% failure rate
- Beyond 100 users, performance degrades
- At 500 users, system is overwhelmed (72% success rate)

### Capacity Limits

**Breaking point:** 500 concurrent users (where success_rate < 90%)

From breaking point, derive:
- **Safe capacity (50%)**: 250 users - recommended for production
- **Target capacity (70%)**: 350 users - acceptable for normal operation
- **Warning threshold (90%)**: 450 users - alert threshold

**Recommendation:**
```yaml
production_capacity:
  safe: 250 concurrent users
  target: 350 concurrent users
  warning: 450 concurrent users
  breaking_point: 500 concurrent users
```

### Graceful Degradation

**Good degradation:** System returns 503 (Service Unavailable) or 429 (Too Many Requests)
- Clients receive clear error messages
- System doesn't crash or hang
- Recovery is automatic after load decreases

**Bad degradation:** System times out, crashes, or hangs
- Clients experience unpredictable failures
- System may require manual restart
- Could lead to cascade failures

### Deadlock Detection

**How deadlocks are detected:**
- Tests use `asyncio.timeout()` to set maximum execution time
- If operations don't complete within timeout, test fails with "Deadlock detected"
- Timeout values: 30-60 seconds (reasonable for concurrent operations)

**Example:**
```python
async def run_concurrent_operations(operations, timeout_seconds=60):
    try:
        async with asyncio.timeout(timeout_seconds):
            results = await asyncio.gather(*operations)
            return True
    except asyncio.TimeoutError:
        pytest.fail(f"Deadlock detected: operations did not complete within {timeout_seconds}s")
```

**What to do if deadlock detected:**
1. Check database transaction isolation levels
2. Review lock acquisition order (consistency prevents deadlocks)
3. Add timeouts to all database operations
4. Use proper session management (context managers)

### Race Condition Detection

**How race conditions are detected:**
- Multiple workers increment same counter concurrently
- Expected: 50 workers × 100 increments = 5000
- Actual: If <5000, lost updates indicate race condition

**Example:**
```python
# 50 workers, each incrementing 100 times
# Expected final value: 5000
# If final <5000: lost updates = race condition

assert final_value == expected_value, \
    f"Race condition detected: expected {expected_value}, got {final_value}"
```

**What to do if race condition detected:**
1. Use atomic operations (database UPDATE with increment)
2. Add locking/semaphores for critical sections
3. Use thread-safe data structures
4. Implement proper transaction isolation

## Production Capacity Planning

### Step 1: Run Stress Tests in Staging

```bash
# In staging environment with production-like data
pytest tests/stress/ -v -s
```

### Step 2: Identify Breaking Point

Look for where success rate drops below 90% in test output:
```
Breaking point: 500 concurrent users
```

### Step 3: Calculate Capacity Limits

```python
breaking_point = 500  # From test results

safe_capacity = breaking_point * 0.5      # 250 users (50%)
target_capacity = breaking_point * 0.7    # 350 users (70%)
warning_threshold = breaking_point * 0.9  # 450 users (90%)
```

### Step 4: Set Monitoring Alerts

```yaml
alerts:
  - name: High Concurrent Users
    condition: concurrent_users > warning_threshold
    severity: warning
    message: "Approaching capacity limit (350/450 users)"

  - name: Capacity Limit Exceeded
    condition: concurrent_users > target_capacity
    severity: critical
    message: "Exceeded capacity limit (400/350 users)"
```

### Step 5: Plan Scaling Strategy

**If approaching target capacity (350 users):**
- Enable horizontal autoscaling
- Add more application servers
- Scale database read replicas

**If approaching warning threshold (450 users):**
- Alert on-call engineering
- Prepare emergency scaling
- Consider rate limiting new users

## CI/CD Integration

### Run Quick Smoke Tests in CI

```yaml
# .github/workflows/test.yml
- name: Run stress test smoke tests
  run: |
    pytest tests/stress/ -k "test_concurrent_health_checks" -v
```

### Run Full Stress Tests Before Releases

```yaml
# .github/workflows/load-test.yml
on:
  release:
    types: [published]

jobs:
  stress-test:
    runs-on: ubuntu-large
    steps:
      - name: Run stress tests
        run: pytest tests/stress/ -v --timeout=300
```

### Compare to Baseline (Performance Regression)

```bash
# After running stress tests, compare results to baseline
python tests/scripts/compare_performance.py \
  baseline.json \
  current_results.json \
  --threshold=15
```

## Test Requirements

### Dependencies

```bash
# Install test dependencies
pip install -r requirements-testing.txt

# Stress test specific
pip install pytest-asyncio psutil
```

### Test Environment

**Required:**
- PostgreSQL database (for connection pool tests)
- Running application server (`python -m uvicorn main:app`)
- Sufficient system resources (CPU, memory)

**Recommended:**
- Dedicated staging environment
- Production-like data volume
- Monitoring enabled (Prometheus)

## Troubleshooting

### Test Failures

**"Connection pool exhausted"**
- Increase pool size in `core/database.py`
- Reduce concurrent user count
- Check for connection leaks (unclosed sessions)

**"Deadlock detected"**
- Check database transaction logs
- Review lock acquisition order
- Reduce concurrent operation count
- Increase timeout value

**"Race condition detected"**
- Verify atomic operations are used
- Check transaction isolation level
- Review critical section locking

**"Test timeout"**
- Check application is running
- Verify database connectivity
- Review system resources (CPU/memory)
- Increase timeout value

### Performance Issues

**Tests are slow:**
- Reduce concurrent user count for development
- Use `pytest -k` to run specific tests
- Run tests on faster hardware

**High latency:**
- Check database query performance
- Review cache hit rates
- Verify network latency
- Profile application code

## Best Practices

1. **Run stress tests in staging, not production**
   - Stress tests can overwhelm production systems
   - Use production-like data in staging

2. **Run stress tests before releases**
   - Catch performance regressions early
   - Validate capacity limits

3. **Monitor system during stress tests**
   - CPU, memory, disk usage
   - Database connection pool
   - Application logs

4. **Document breaking points**
   - Track breaking points over time
   - Alert if breaking point decreases (regression)

5. **Use stress test results for capacity planning**
   - Set safe operating limits
   - Configure autoscaling thresholds
   - Plan infrastructure scaling

## Related Documentation

- **Load Testing:** `../load/README.md` - Load testing with Locust
- **Performance Benchmarks:** `../integration/performance/` - Single-user performance targets
- **Monitoring:** `backend/docs/MONITORING_SETUP.md` - Prometheus metrics and alerting

## References

- **Plan:** `.planning/phases/209-load-stress-testing/209-04-PLAN.md`
- **Research:** `.planning/phases/209-load-stress-testing/209-RESEARCH.md`
- **Phase 208 Performance Metrics:** Single-user benchmarks (53 targets)

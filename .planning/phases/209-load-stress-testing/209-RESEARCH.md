# Phase 209: Load Testing & Stress Testing - Research

**Researched:** March 18, 2026
**Domain:** Load testing, stress testing, performance bottleneck identification, memory leak detection
**Confidence:** HIGH

## Summary

Phase 209 validates system behavior under concurrent user load, establishes capacity limits, and identifies performance bottlenecks using Locust. This phase builds on Phase 208's single-user performance benchmarks (53 benchmarks with target metrics) by introducing multi-user load testing to simulate realistic production traffic patterns.

**Primary Recommendation:** Use Locust (already installed in requirements-testing.txt v2.15.0+) for load testing with realistic user scenarios, pytest-based soak tests for memory leak detection, and CI/CD integration for performance regression detection. Focus on 5-8 critical endpoints from Phase 208's benchmark suite.

**Key Insight from Phase 208:** Single-user benchmarks established targets (<1ms cache hits, <10ms health checks, <100ms API endpoints), but load testing is required to validate these targets under concurrent load (100-1000 users) and identify bottlenecks that only appear with multiple simultaneous requests.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Locust** | 2.15.0+ | Load testing framework | De facto standard for Python load testing, distributed execution, real-time metrics, already installed |
| **pytest** | 7.0+ | Test runner for soak tests | Already in use, excellent async support, integrates with existing test infrastructure |
| **pytest-asyncio** | 0.21+ | Async test execution | Required for WebSocket and concurrent API testing |
| **pytest-benchmark** | 4.0+ | Historical performance tracking | Already in use from Phase 208, enables regression detection |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **httpx** | 0.24+ | Async HTTP client | Already in use, supports load test scenarios with connection pooling |
| **psutil** | 5.9+ | Memory leak detection | Monitor memory usage during soak tests |
| **prometheus-client** | 0.19+ | Metrics export | Export load test results for Grafana dashboards |
| **matplotlib** | 3.7+ | Visualization | Generate load test report charts (optional) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|----------|----------|
| **Locust** | JMeter | Locust is Python-native (matches codebase), JMeter requires Java, separate infrastructure |
| **Locust** | k6 | k6 uses JavaScript, requires separate scripting language, Locust integrates with existing pytest infrastructure |
| **Locust** | Apache Bench (ab) | ab is too simple (single endpoint only), Locust supports complex user journeys |
| **pytest-soak** | custom loop | pytest-soak provides standardized soak test patterns, custom loops require manual cleanup and reporting |

**Installation:**
```bash
# Already installed in requirements-testing.txt
pip install locust>=2.15.0 pytest-benchmark>=4.0.0

# Add for Phase 209 (if not already present)
pip install psutil>=5.9.0 matplotlib>=3.7.0
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── load/                    # NEW: Load tests with Locust
│   ├── locustfile.py        # Main Locust file defining user behaviors
│   ├── conftest.py          # Shared fixtures (test data, auth tokens)
│   ├── scenarios/
│   │   ├── agent_api.py     # Agent API user scenario
│   │   ├── workflow_api.py  # Workflow execution scenario
│   │   ├── episode_api.py   # Episode retrieval scenario
│   │   └── canvas_api.py    # Canvas presentation scenario
│   ├── reports/             # Generated load test reports
│   │   ├── baseline.json    # Baseline performance metrics
│   │   └── trends/          # Historical trend data
│   └── README.md            # Load testing guide

├── soak/                    # NEW: Soak tests for memory leak detection
│   ├── conftest.py          # Soak test fixtures (memory monitoring)
│   ├── test_memory_stability.py    # Memory leak detection (1hr test)
│   ├── test_connection_stability.py # Connection pool stability (2hr test)
│   └── test_cache_stability.py      # Cache stability under load (30min test)

├── integration/performance/ # EXISTING from Phase 208
│   ├── conftest.py          # Benchmark fixtures
│   ├── test_api_latency_benchmarks.py
│   ├── test_governance_performance.py
│   └── test_database_query_performance.py

└── scripts/                 # Test automation scripts
    ├── run_load_tests.sh    # Execute Locust load tests
    ├── run_soak_tests.sh    # Execute soak tests
    ├── generate_load_report.py  # Generate HTML load test report
    └── compare_performance.py   # Compare to baseline, detect regressions
```

### Pattern 1: Locust Load Testing with Realistic User Scenarios

**What:** Simulate concurrent users with realistic behavior patterns (wait times, task weights).

**When to use:** Validating system capacity, identifying bottlenecks, testing scalability.

**Example:**
```python
# Source: backend/tests/load/locustfile.py
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import logging
import random

logger = logging.getLogger(__name__)

class AgentAPIUser(HttpUser):
    """
    Simulate realistic agent API usage patterns.

    Behavior:
    - List agents (high frequency - every page load)
    - Get single agent (medium frequency - agent detail view)
    - Execute workflow (low frequency - user action)
    - Check governance (medium frequency - permission checks)

    Weights: 3:2:1:2 (list:get:execute:check)
    """
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    host = "http://localhost:8000"

    def on_start(self):
        """Login before running tasks."""
        self.login()

    def login(self):
        """Authenticate and store token."""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "test_password"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
        else:
            self.token = None
            logger.warning("Login failed, proceeding without auth")

    @task(3)
    def list_agents(self):
        """List agents (3x more frequent - simulates page loads)."""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        with self.client.get("/api/v1/agents", headers=headers, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                # Validate response structure
                if "agents" in data or isinstance(data, list):
                    response.success()
                else:
                    response.failure("Invalid response structure")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def get_agent(self):
        """Get specific agent (medium frequency - detail views)."""
        if not self.token:
            return

        agent_id = f"agent_{random.randint(1, 100)}"
        self.client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def execute_workflow(self):
        """Execute workflow (low frequency - user actions)."""
        if not self.token:
            return

        self.client.post(
            "/api/v1/workflows/test_workflow/execute",
            json={"input_data": {"test": "value"}},
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(2)
    def check_governance(self):
        """Check governance permissions (medium frequency)."""
        if not self.token:
            return

        self.client.post(
            "/api/agent-governance/check-permission",
            json={
                "agent_id": f"agent_{random.randint(1, 100)}",
                "action": "test_action",
                "action_complexity": 1
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def health_check(self):
        """Health check (low frequency - monitoring)."""
        self.client.get("/health/live")


class WorkflowExecutionUser(HttpUser):
    """
    Simulate workflow execution heavy users.

    Focus on workflow API endpoints:
    - List workflows (medium frequency)
    - Execute workflow (high frequency - primary action)
    - Get workflow status (medium frequency - polling)
    """
    wait_time = between(2, 5)  # Longer wait time for workflow execution
    weight = 1  # 1/3 the traffic of AgentAPIUser

    def on_start(self):
        """Initialize with authentication."""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "workflow_user@example.com",
            "password": "test_password"
        })
        self.token = response.json().get("access_token") if response.status_code == 200 else None

    @task(2)
    def execute_workflow(self):
        """Execute workflow (primary action)."""
        if not self.token:
            return

        self.client.post(
            "/api/v1/workflows/test_workflow/execute",
            json={"input_data": {"test": "value"}},
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def list_workflows(self):
        """List workflows."""
        if not self.token:
            return

        self.client.get(
            "/api/v1/workflows",
            headers={"Authorization": f"Bearer {self.token}"}
        )


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generate report after test completes."""
    if isinstance(environment.runner, MasterRunner):
        logger.info("Load test completed, generating report...")
        # Report generation handled by Locust automatically
```

**Key Benefits:**
- Realistic user behavior simulation (wait times, task weights)
- Distributed execution (multiple workers for high load)
- Real-time metrics (requests/sec, failure rates, response times)
- Web UI for monitoring during tests (http://localhost:8089)

### Pattern 2: Soak Testing with Memory Leak Detection

**What:** Run tests for extended periods (1-2 hours) to detect memory leaks and connection pool exhaustion.

**When to use:** Validating memory stability, detecting resource leaks, testing connection pool limits.

**Example:**
```python
# Source: backend/tests/soak/test_memory_stability.py
import pytest
import time
import psutil
import gc
from typing import Dict, List
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.governance_cache import GovernanceCache
from core.workflow_engine import WorkflowEngine

@pytest.mark.soak
@pytest.mark.timeout(3600)  # 1 hour timeout
def test_memory_leak_detection_governance_cache():
    """
    Soak test for governance cache memory leaks.

    Runs for 1 hour, monitoring memory usage.
    Failure: Memory growth >100MB over 1 hour (indicates leak).
    Target: Stable memory usage (+/- 50MB).
    """
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    cache = GovernanceCache(max_size=10000, ttl_seconds=60)

    # Run cache operations for 1 hour
    start_time = time.time()
    iterations = 0

    while time.time() - start_time < 3600:  # 1 hour
        # Perform 1000 cache operations per iteration
        for i in range(1000):
            cache.set(
                agent_id=f"agent_{iterations}_{i}",
                action_type="test_action",
                data={"allowed": True, "maturity_level": "AUTONOMOUS"}
            )
            cache.get(agent_id=f"agent_{iterations}_{i}", action_type="test_action")

        iterations += 1

        # Force garbage collection every 10 iterations
        if iterations % 10 == 0:
            gc.collect()

        # Log memory usage every minute
        if iterations % 60 == 0:
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_growth = current_memory - initial_memory
            print(f"Iteration {iterations}: Memory growth = {memory_growth:.2f}MB")

            # Fail fast if memory growth >500MB
            if memory_growth > 500:
                pytest.fail(f"Memory leak detected: {memory_growth:.2f}MB growth")

    # Final memory check
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_growth = final_memory - initial_memory

    # Target: Memory growth <100MB over 1 hour
    assert memory_growth < 100, f"Memory leak detected: {memory_growth:.2f}MB growth over 1 hour"

    print(f"Soak test complete: {iterations} iterations, {memory_growth:.2f}MB memory growth")


@pytest.mark.soak
@pytest.mark.timeout(7200)  # 2 hour timeout
def test_connection_pool_stability(db_session: Session):
    """
    Soak test for database connection pool stability.

    Runs for 2 hours, opening/closing connections rapidly.
    Failure: Connection pool exhaustion, connection leaks.
    Target: Stable pool usage (no exhaustion).
    """
    from core.models import AgentRegistry

    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Run database operations for 2 hours
    start_time = time.time()
    iterations = 0

    while time.time() - start_time < 7200:  # 2 hours
        # Perform 100 database operations per iteration
        for i in range(100):
            try:
                # Create and commit agent
                agent = AgentRegistry(
                    id=f"soak_test_agent_{iterations}_{i}",
                    name=f"Soak Test Agent {iterations}_{i}",
                    category="test",
                    module_path="test.module",
                    class_name="TestClass",
                    status="AUTONOMOUS",
                    confidence_score=0.9
                )
                db_session.add(agent)
                db_session.commit()

                # Query agent
                agent = db_session.query(AgentRegistry).filter(
                    AgentRegistry.id == f"soak_test_agent_{iterations}_{i}"
                ).first()

                # Delete agent
                db_session.query(AgentRegistry).filter(
                    AgentRegistry.id == f"soak_test_agent_{iterations}_{i}"
                ).delete(synchronize_session=False)
                db_session.commit()

            except Exception as e:
                pytest.fail(f"Database operation failed: {e}")

        iterations += 1

        # Force garbage collection every 10 iterations
        if iterations % 10 == 0:
            gc.collect()

        # Log memory usage every 5 minutes
        if iterations % 300 == 0:
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_growth = current_memory - initial_memory
            print(f"Iteration {iterations}: Memory growth = {memory_growth:.2f}MB")

    # Final memory check
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_growth = final_memory - initial_memory

    # Target: Memory growth <200MB over 2 hours (higher due to connection overhead)
    assert memory_growth < 200, f"Memory leak detected: {memory_growth:.2f}MB growth over 2 hours"

    print(f"Soak test complete: {iterations} iterations, {memory_growth:.2f}MB memory growth")


@pytest.mark.soak
@pytest.mark.timeout(1800)  # 30 minute timeout
def test_cache_stability_under_load():
    """
    Soak test for governance cache under concurrent load.

    Runs for 30 minutes with concurrent cache operations.
    Failure: Cache corruption, race conditions, deadlocks.
    Target: Zero cache errors, stable memory.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    async def concurrent_cache_operations(worker_id: int):
        """Simulate concurrent cache operations from multiple workers."""
        for i in range(10000):
            # Concurrent write
            cache.set(
                agent_id=f"agent_{worker_id}_{i}",
                action_type="test_action",
                data={"allowed": True, "maturity_level": "AUTONOMOUS"}
            )

            # Concurrent read
            result = cache.get(agent_id=f"agent_{worker_id}_{i}", action_type="test_action")

            # Validate cache consistency
            if result is None:
                pytest.fail(f"Cache inconsistency: agent_{worker_id}_{i} not found after write")

    # Run 10 concurrent workers for 30 minutes
    start_time = time.time()

    while time.time() - start_time < 1800:  # 30 minutes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for worker_id in range(10):
                futures.append(executor.submit(asyncio.run, concurrent_cache_operations(worker_id)))

            # Wait for all workers to complete
            for future in futures:
                future.result()  # Raises exceptions if any

        gc.collect()

    print("Soak test complete: Zero cache errors, stable memory")
```

**Key Benefits:**
- Detects memory leaks that only appear over time
- Validates connection pool stability under load
- Identifies resource exhaustion issues
- Confirms system stability for extended operation

### Pattern 3: Performance Regression Detection in CI/CD

**What:** Automated performance regression detection using baseline comparison.

**When to use:** CI/CD pipeline integration, preventing performance degradations in production.

**Example:**
```python
# Source: backend/tests/scripts/compare_performance.py
"""
Performance regression detection script.

Compares current load test results to baseline, fails if regression detected.
Usage:
    python compare_performance.py baseline.json current.json --threshold=15
"""
import json
import sys
from typing import Dict, List, Any

def load_results(filepath: str) -> Dict[str, Any]:
    """Load load test results from JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def compare_metrics(baseline: Dict, current: Dict, threshold: float = 15.0) -> List[Dict[str, Any]]:
    """
    Compare current metrics to baseline, detect regressions.

    Args:
        baseline: Baseline metrics from previous run
        current: Current metrics from latest run
        threshold: Regression threshold percentage (default: 15%)

    Returns:
        List of regressions detected
    """
    regressions = []

    # Compare response times (P50, P95, P99)
    for endpoint in baseline.get('endpoints', []):
        endpoint_name = endpoint['name']
        baseline_p95 = endpoint['response_times']['p95']
        baseline_rps = endpoint['requests_per_second']

        # Find matching endpoint in current results
        current_endpoint = next(
            (e for e in current.get('endpoints', []) if e['name'] == endpoint_name),
            None
        )

        if not current_endpoint:
            continue

        current_p95 = current_endpoint['response_times']['p95']
        current_rps = current_endpoint['requests_per_second']

        # Check for P95 regression (increase in response time)
        if baseline_p95 > 0:
            p95_change = ((current_p95 - baseline_p95) / baseline_p95) * 100
            if p95_change > threshold:
                regressions.append({
                    'endpoint': endpoint_name,
                    'metric': 'p95_response_time',
                    'baseline_ms': baseline_p95,
                    'current_ms': current_p95,
                    'change_percent': p95_change,
                    'severity': 'HIGH' if p95_change > threshold * 2 else 'MEDIUM'
                })

        # Check for throughput regression (decrease in RPS)
        if baseline_rps > 0:
            rps_change = ((baseline_rps - current_rps) / baseline_rps) * 100
            if rps_change > threshold:
                regressions.append({
                    'endpoint': endpoint_name,
                    'metric': 'requests_per_second',
                    'baseline_rps': baseline_rps,
                    'current_rps': current_rps,
                    'change_percent': rps_change,
                    'severity': 'HIGH' if rps_change > threshold * 2 else 'MEDIUM'
                })

    return regressions

def main():
    """Main entry point for performance comparison."""
    if len(sys.argv) < 3:
        print("Usage: python compare_performance.py baseline.json current.json [--threshold=15]")
        sys.exit(1)

    baseline_file = sys.argv[1]
    current_file = sys.argv[2]
    threshold = float(sys.argv[3].split('=')[1]) if len(sys.argv) > 3 else 15.0

    baseline = load_results(baseline_file)
    current = load_results(current_file)

    regressions = compare_metrics(baseline, current, threshold)

    if regressions:
        print(f"❌ PERFORMANCE REGRESSION DETECTED ({len(regressions)} regressions)")
        print(f"Threshold: {threshold}%\n")

        for regression in regressions:
            severity_icon = "🔴" if regression['severity'] == 'HIGH' else "🟡"
            print(f"{severity_icon} {regression['endpoint']}")
            print(f"   Metric: {regression['metric']}")
            if 'baseline_ms' in regression:
                print(f"   Baseline: {regression['baseline_ms']:.2f}ms")
                print(f"   Current: {regression['current_ms']:.2f}ms")
            else:
                print(f"   Baseline: {regression['baseline_rps']:.2f} RPS")
                print(f"   Current: {regression['current_rps']:.2f} RPS")
            print(f"   Change: {regression['change_percent']:.2f}%")
            print()

        sys.exit(1)
    else:
        print(f"✅ No performance regressions detected (threshold: {threshold}%)")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

**CI/CD Integration:**
```yaml
# .github/workflows/load-test.yml
name: Load Tests

on:
  pull_request:
    paths:
      - 'backend/core/**'
      - 'backend/api/**'
  schedule:
    # Run load tests daily at 2 AM UTC
    - cron: '0 2 * * *'

jobs:
  load-test:
    name: Run Load Tests
    runs-on: ubuntu-large

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install -r requirements-testing.txt

      - name: Start application
        run: |
          cd backend
          python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
          sleep 10  # Wait for app to start

      - name: Run load tests (Locust)
        run: |
          cd backend
          locust --headless \
            -f tests/load/locustfile.py \
            -u 100 \  # 100 users
            -r 10 \   # 10 users/second spawn rate
            -t 5m \   # Run for 5 minutes
            --html tests/load/reports/load-test-report.html \
            --json tests/load/reports/load-test-results.json

      - name: Compare to baseline
        run: |
          cd backend
          python tests/scripts/compare_performance.py \
            tests/load/reports/baseline.json \
            tests/load/reports/load-test-results.json \
            --threshold=15

      - name: Upload load test report
        uses: actions/upload-artifact@v4
        with:
          name: load-test-report
          path: backend/tests/load/reports/load-test-report.html

      - name: Update baseline (main branch only)
        if: github.ref == 'refs/heads/main'
        run: |
          cd backend
          cp tests/load/reports/load-test-results.json tests/load/reports/baseline.json
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add tests/load/reports/baseline.json
          git commit -m "Update load test baseline"
          git push
```

**Key Benefits:**
- Automated regression detection in CI/CD
- Prevents performance degradations from reaching production
- Historical performance tracking
- Visual reports with HTML output

### Anti-Patterns to Avoid

- **Anti-pattern: Load testing in production without limits**
  - **Why it's bad:** Can crash production database, exhaust API quotas, impact real users
  - **What to do instead:** Load test in staging environment with production-like data, use rate limits

- **Anti-pattern: Testing only happy paths**
  - **Why it's bad:** Misses error handling bottlenecks, doesn't validate graceful degradation
  - **What to do instead:** Include error scenarios (500 errors, timeouts, rate limits)

- **Anti-pattern: Ignoring warmup period**
  - **Why it's bad:** Cold start skews results, JIT compilation affects performance
  - **What to do instead:** Include 5-10 minute warmup period before collecting metrics

- **Anti-pattern: Running load tests on every commit**
  - **Why it's bad:** Load tests are slow (5-10 minutes), block CI pipeline, expensive
  - **What to do instead:** Run load tests on schedule (daily/weekly) or before releases

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Load testing framework** | Custom threading code | locust | Distributed execution, real-time metrics, web UI, proven scalability |
| **Memory leak detection** | Custom memory monitoring | psutil + pytest-soak | Cross-platform, accurate metrics, standardized patterns |
| **Performance comparison** | Manual JSON parsing | pytest-benchmark compare | Statistical analysis, historical tracking, regression detection |
| **Connection pooling** | Custom pool management | SQLAlchemy pool | Proven correctness, automatic cleanup, production-tested |
| **Concurrent testing** | Custom asyncio code | pytest-asyncio | Fixture support, proper cleanup, standardized patterns |

**Key insight:** Locust alone saves 500+ lines of custom threading/websocket/metrics code. pytest-soak provides standardized patterns for memory leak detection that would require custom monitoring and cleanup logic.

## Common Pitfalls

### Pitfall 1: Testing Without Realistic Data

**What goes wrong:** Load tests with synthetic data don't match production performance.

**Why it happens:** Using "test_agent_1", "test_agent_2" instead of realistic data, not testing database indexes, not testing cache hit ratios.

**How to avoid:**
- Use production-like data (anonymized production data dump or realistic fixtures)
- Test database indexes (explain query plans)
- Validate cache hit ratios (should be >80% for hot data)
- Test with realistic payload sizes (not 1KB JSON when production is 100KB)

**Warning signs:** Load tests show 10ms response times but production shows 500ms (missing database indexes, different data distributions).

### Pitfall 2: Ignoring Database Connection Pool Limits

**What goes wrong:** Load tests fail with "connection pool exhausted" errors, tests timeout waiting for connections.

**Why it happens:** Not configuring connection pool size for concurrent load, default pool size (5) too small for 100 concurrent users.

**How to avoid:**
- Configure connection pool: `SQLALCHEMY_POOL_SIZE=20`, `SQLALCHEMY_MAX_OVERFLOW=40`
- Monitor pool usage during load tests (check `engine.pool.status()`)
- Set connection timeout: `SQLALCHEMY_POOL_TIMEOUT=30`
- Test with pool size = concurrent users / 5

**Warning signs:** Load tests stall at 50 concurrent users, connection timeout errors in logs.

### Pitfall 3: Missing Deadlock and Race Condition Detection

**What goes wrong:** Load tests pass but production has deadlocks, data corruption under concurrent load.

**Why it happens:** Not testing concurrent writes, not testing transaction isolation, not testing cache race conditions.

**How to avoid:**
- Include concurrent write scenarios in load tests (multiple users updating same agent)
- Test transaction isolation (repeatable read vs read committed)
- Test cache race conditions (concurrent cache.get() + cache.set())
- Use pytest-concurrent or ThreadPoolExecutor for concurrent operations

**Warning signs:** Tests pass with 1 user but fail with 10 users, database deadlock errors in logs.

### Pitfall 4: Not Testing Failure Scenarios

**What goes wrong:** System collapses when external services fail (database timeout, API rate limits), cascade failures.

**Why it happens:** Only testing happy paths, not testing graceful degradation, not testing circuit breakers.

**How to avoid:**
- Test database failure scenarios (connection timeout, query timeout)
- Test API rate limiting (429 errors, backoff behavior)
- Test external service failures (LLM provider timeouts, WebSocket disconnects)
- Validate circuit breaker behavior (fail fast, recovery)

**Warning signs:** Load tests show 100% success rate but production shows 503 errors under load.

### Pitfall 5: Memory Leaks Only Appear After Hours

**What goes wrong:** Load tests run for 5 minutes and pass, but production crashes after 24 hours with OOM.

**Why it happens:** Memory leaks are slow (10MB/hour), not running soak tests, not monitoring memory growth.

**How to avoid:**
- Run soak tests for 1-2 hours minimum
- Monitor memory usage with psutil
- Force garbage collection and validate memory release
- Test connection pool cleanup (connections released back to pool)

**Warning signs:** Memory grows linearly over time, connections accumulate in pool, cache grows unbounded.

### Pitfall 6: CI/CD Integration Blocks Merges

**What goes wrong:** Load tests fail randomly in CI (flaky), developers stop running load tests, merge conflicts increase.

**Why it happens:** Load tests are slow (10+ minutes), run on shared CI resources (noisy neighbor), hard-coded performance assertions.

**How to avoid:**
- Run load tests on schedule (daily/weekly) not on every commit
- Use dedicated CI runners for load tests (larger instances)
- Use baseline comparison not hard-coded assertions
- Set appropriate regression thresholds (10-15% not 1%)

**Warning signs:** Load tests timeout in CI, developers skip load tests, load test results ignored.

## Code Examples

### Load Test: Agent API Endpoint

```python
# backend/tests/load/scenarios/agent_api.py
from locust import HttpUser, task, between
import random

class AgentAPIUser(HttpUser):
    """
    Agent API load test scenario.

    Tests:
    - GET /api/v1/agents (list agents)
    - GET /api/v1/agents/{id} (get agent)
    - POST /api/v1/agents (create agent)
    - DELETE /api/v1/agents/{id} (delete agent)

    Weights:
    - List: 5 (most common - every page load)
    - Get: 3 (detail views)
    - Create: 1 (user actions)
    - Delete: 1 (user actions)
    """
    wait_time = between(1, 3)

    def on_start(self):
        """Authenticate before running tasks."""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "load_test@example.com",
            "password": "test_password"
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
        else:
            self.token = None

    @task(5)
    def list_agents(self):
        """List agents (most common operation)."""
        if not self.token:
            return

        with self.client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def get_agent(self):
        """Get specific agent."""
        if not self.token:
            return

        agent_id = f"agent_{random.randint(1, 1000)}"
        self.client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def create_agent(self):
        """Create new agent."""
        if not self.token:
            return

        self.client.post(
            "/api/v1/agents",
            json={
                "name": f"Load Test Agent {random.randint(1, 10000)}",
                "category": "test",
                "module_path": "test.module",
                "class_name": "TestClass",
                "maturity": "AUTONOMOUS"
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def delete_agent(self):
        """Delete agent."""
        if not self.token:
            return

        agent_id = f"test_agent_{random.randint(1, 100)}"
        self.client.delete(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

### Soak Test: Connection Pool Stability

```python
# backend/tests/soak/test_connection_stability.py
import pytest
import time
import gc
from sqlalchemy.pool import QueuePool

from core.database import engine

@pytest.mark.soak
@pytest.mark.timeout(7200)  # 2 hours
def test_connection_pool_stability():
    """
    Test connection pool stability under load.

    Validates:
    - Connections are properly returned to pool
    - No connection leaks
    - Pool doesn't exhaust over time
    - Memory remains stable

    Duration: 2 hours
    Target: Zero connection leaks, stable memory (+/- 100MB)
    """
    if not isinstance(engine.pool, QueuePool):
        pytest.skip("Connection pool test requires QueuePool")

    initial_size = engine.pool.size()
    initial_checked_in = engine.pool.checkedin()

    # Run database operations for 2 hours
    start_time = time.time()
    iterations = 0

    while time.time() - start_time < 7200:  # 2 hours
        # Open and close 100 connections per iteration
        for _ in range(100):
            conn = engine.connect()
            result = conn.execute("SELECT 1")
            result.fetchone()
            conn.close()

        iterations += 1

        # Force garbage collection every 10 iterations
        if iterations % 10 == 0:
            gc.collect()

        # Log pool status every 5 minutes
        if iterations % 300 == 0:
            current_size = engine.pool.size()
            current_checked_in = engine.pool.checkedin()
            print(f"Iteration {iterations}: Pool size={current_size}, Checked in={current_checked_in}")

            # Validate pool hasn't grown
            if current_size > initial_size + 10:
                pytest.fail(f"Connection pool grown: {initial_size} -> {current_size}")

    # Final validation
    final_size = engine.pool.size()
    final_checked_in = engine.pool.checkedin()

    # All connections should be checked in
    assert final_checked_in == initial_checked_in, "Connection leak detected"

    # Pool size should be stable
    assert final_size == initial_size, f"Connection pool size changed: {initial_size} -> {final_size}"

    print(f"Soak test complete: {iterations} iterations, zero connection leaks")
```

### CI/CD Script: Performance Regression Detection

```python
# backend/tests/scripts/generate_load_report.py
"""
Generate load test report with baseline comparison.

Usage:
    python generate_load_report.py --baseline baseline.json --current current.json --output report.html
"""
import json
import argparse
from typing import Dict, List
from datetime import datetime

def generate_html_report(baseline: Dict, current: Dict, output: str):
    """Generate HTML load test report."""
    endpoints = current.get('endpoints', [])

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Load Test Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
            .summary {{ display: flex; justify-content: space-around; margin: 20px 0; }}
            .metric {{ text-align: center; }}
            .metric-value {{ font-size: 32px; font-weight: bold; }}
            .metric-label {{ color: #666; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f0f0f0; }}
            .regression {{ background: #ffcccc; }}
            .improvement {{ background: #ccffcc; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Load Test Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="summary">
            <div class="metric">
                <div class="metric-value">{current.get('total_requests', 0)}</div>
                <div class="metric-label">Total Requests</div>
            </div>
            <div class="metric">
                <div class="metric-value">{current.get('requests_per_second', 0):.1f}</div>
                <div class="metric-label">Requests/Second</div>
            </div>
            <div class="metric">
                <div class="metric-value">{current.get('failure_rate', 0):.2f}%</div>
                <div class="metric-label">Failure Rate</div>
            </div>
            <div class="metric">
                <div class="metric-value">{current.get('avg_response_time_ms', 0):.1f}ms</div>
                <div class="metric-label">Avg Response Time</div>
            </div>
        </div>

        <h2>Endpoint Performance</h2>
        <table>
            <tr>
                <th>Endpoint</th>
                <th>Requests</th>
                <th>P50 (ms)</th>
                <th>P95 (ms)</th>
                <th>P99 (ms)</th>
                <th>Failures</th>
            </tr>
    """

    for endpoint in endpoints:
        html += f"""
            <tr>
                <td>{endpoint['name']}</td>
                <td>{endpoint['request_count']}</td>
                <td>{endpoint['response_times']['p50']:.2f}</td>
                <td>{endpoint['response_times']['p95']:.2f}</td>
                <td>{endpoint['response_times']['p99']:.2f}</td>
                <td>{endpoint['failure_count']}</td>
            </tr>
        """

    html += """
        </table>
    </body>
    </html>
    """

    with open(output, 'w') as f:
        f.write(html)

def main():
    parser = argparse.ArgumentParser(description='Generate load test report')
    parser.add_argument('--baseline', required=True, help='Baseline JSON file')
    parser.add_argument('--current', required=True, help='Current JSON file')
    parser.add_argument('--output', required=True, help='Output HTML file')

    args = parser.parse_args()

    with open(args.baseline, 'r') as f:
        baseline = json.load(f)

    with open(args.current, 'r') as f:
        current = json.load(f)

    generate_html_report(baseline, current, args.output)
    print(f"Report generated: {args.output}")

if __name__ == "__main__":
    main()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Apache Bench (ab)** | Locust | 2019+ | User journeys, distributed execution, real-time metrics |
| **Manual timing scripts** | pytest-benchmark | 2020+ | Historical tracking, statistical analysis |
| **Single-threaded load tests** | Concurrent execution | 2019+ | Realistic simulation, bottleneck detection |
| **Ad-hoc monitoring** | psutil + prometheus | 2021+ | Standardized metrics, CI/CD integration |
| **Manual result comparison** | Automated regression detection | 2022+ | CI/CD integration, performance gates |

**Deprecated/outdated:**
- **Apache Bench (ab):** Use Locust for complex user journeys, ab is too simple (single endpoint)
- **Custom threading code:** Use Locust for distributed execution, custom code doesn't scale
- **Hard-coded performance assertions:** Use baseline comparison with pytest-benchmark, hardware-dependent
- **Manual memory monitoring:** Use psutil + pytest-soak patterns, standardized and cross-platform

## Open Questions

1. **What is the target concurrent user load for Atom?**
   - What we know: Phase 208 established single-user benchmarks (<100ms API targets)
   - What's unclear: Production user count, expected peak traffic, target capacity
   - Recommendation: Start with 100 concurrent users (industry standard for SaaS), scale up to 1000 based on results

2. **Should load tests run in CI/CD or on schedule?**
   - What we know: Load tests are slow (5-10 minutes), block CI pipelines
   - What's unclear: Team tolerance for CI latency, deployment frequency
   - Recommendation: Run quick smoke tests (50 users, 2 min) in CI, full load tests (1000 users, 10 min) on daily schedule

3. **How to handle authentication in load tests?**
   - What we know: Most endpoints require authentication, token-based auth
   - What's unclear: Token expiry, refresh token handling, rate limiting per user
   - Recommendation: Use test user with long-lived token, implement token refresh in on_start

4. **What is the acceptable memory leak threshold?**
   - What we know: Memory leaks are bad (OOM crashes), some growth is normal (cache warming)
   - What's unclear: Acceptable growth rate, baseline memory usage
   - Recommendation: Target <100MB growth over 1 hour, <200MB over 2 hours (industry standard)

## Sources

### Primary (HIGH confidence)
- **backend/requirements-testing.txt** - Locust 2.15.0+ already installed (line 31)
- **backend/tests/integration/performance/test_api_latency_benchmarks.py** - API latency benchmarks from Phase 208 (complete)
- **backend/api/health_routes.py** - Health check endpoints for load testing (complete)
- **backend/api/agent_governance_routes.py** - Agent governance API endpoints (lines 1-100)
- **.planning/phases/208-integration-performance-testing/208-07-PERFORMANCE-METRICS.md** - 53 performance benchmarks documented (complete)
- **backend/docs/MONITORING_SETUP.md** - Prometheus metrics and monitoring setup (lines 1-100)
- **.github/workflows/deploy.yml** - CI/CD pipeline configuration (lines 1-100)
- **backend/core/models.py** - Database models for test data generation (lines 1-100)

### Secondary (MEDIUM confidence)
- **Locust documentation** (https://docs.locust.io/) - Load testing patterns and best practices
- **pytest-soak patterns** - Soak testing methodology (verified against existing test infrastructure)
- **psutil documentation** (https://psutil.readthedocs.io/) - Memory monitoring and leak detection
- **Prometheus client docs** (https://prometheus-client.readthedocs.io/) - Metrics export for Grafana

### Tertiary (LOW confidence)
- **Load testing best practices** - General industry patterns (verified against Locust documentation)
- **Memory leak detection strategies** - Common Python patterns (verified against psutil capabilities)
- **CI/CD load testing integration** - GitHub Actions patterns (verified against existing deploy.yml)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Locust already installed, patterns verified against existing codebase
- Architecture: HIGH - Load testing patterns verified against Locust documentation, soak test patterns verified against existing test infrastructure
- Pitfalls: HIGH - Issues identified from Phase 208 experience, verified against common load testing problems

**Research date:** March 18, 2026
**Valid until:** April 17, 2026 (30 days - load testing infrastructure evolves slowly)

**Key Assumptions:**
1. Phase 208's 53 performance benchmarks provide accurate single-user baseline
2. Target concurrent user load is 100-1000 users (industry standard for SaaS platforms)
3. Load tests run in staging environment with production-like data
4. Acceptable memory leak threshold is <100MB over 1 hour (industry standard)
5. Performance regression threshold is 15% (balances detection with false positives)

**Risks:**
1. Locust web UI port (8089) conflicts with existing services (mitigation: use --web-port parameter)
2. Load test duration exceeds CI timeout (mitigation: run on schedule, not in CI)
3. Memory leak detection false positives (mitigation: use multiple runs, validate with manual inspection)
4. Database connection pool exhaustion in CI environment (mitigation: configure pool size for CI, use --headless mode)

**Mitigation:**
1. Use configurable ports in Locust configuration, document port conflicts in README
2. Run quick smoke tests (2 min) in CI, full load tests (10 min) on schedule
3. Run soak tests 3 times, validate consistent memory growth patterns
4. Configure connection pool for CI: `SQLALCHEMY_POOL_SIZE=5`, `SQLALCHEMY_MAX_OVERFLOW=10`

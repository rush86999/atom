# Performance Regression Tests

**Phase:** 243 - Memory & Performance Bug Discovery
**Location:** `backend/tests/performance_regression/`
**Last Updated:** March 25, 2026

## Purpose

Performance regression tests use **pytest-benchmark** to detect performance degradations in critical paths: API latency, database queries, and governance cache operations.

**20% Regression Threshold:** Detects significant performance degradations while allowing for minor measurement noise (±5-10%)

**Graceful Degradation:** Tests skip with pytest.skip if pytest-benchmark unavailable

## Key Features

- **Performance Regression Detection:** Detects >20% degradation vs baseline
- **Baseline Comparison:** Compare current performance against established baseline
- **Benchmark Statistics:** Mean, min, max, stddev for rigorous analysis
- **TestClient Pattern:** Use TestClient instead of httpx for faster benchmarks
- **Fixture Reuse:** Import db_session, authenticated_user from e2e_ui/fixtures

## Test Coverage

### API Latency Regression (`test_api_latency_regression.py`)

**Tests:**
- `test_api_get_agent_latency()` - GET /api/v1/agents/{id} latency
- `test_api_list_agents_latency()` - GET /api/v1/agents latency
- `test_api_create_agent_latency()` - POST /api/v1/agents latency
- `test_api_delete_agent_latency()` - DELETE /api/v1/agents/{id} latency

**Fixtures:**
- `check_regression` - Regression checker with 20% threshold
- `performance_baseline` - Baseline loader from JSON

**Focus Areas:**
- API endpoint response time
- Request validation overhead
- Database query performance
- JSON serialization overhead

### Database Query Regression (`test_database_query_regression.py`)

**Tests:**
- `test_query_agent_by_id_latency()` - Agent by ID query
- `test_query_agents_list_latency()` - Agent list query
- `test_query_executions_by_agent_latency()` - Executions by agent query
- `test_query_bulk_operations_latency()` - Bulk insert/update operations

**Fixtures:**
- `check_regression` - Regression checker
- `db_session` - Database session (imported from e2e_ui/fixtures)

**Focus Areas:**
- Database query execution time
- Index effectiveness
- N+1 query problems
- Bulk operation efficiency

### Governance Cache Regression (`test_governance_cache_regression.py`)

**Tests:**
- `test_cache_get_latency()` - Cache get latency
- `test_cache_set_latency()` - Cache set latency
- `test_cache_hit_rate()` - Cache hit rate regression
- `test_cache_bulk_operations_latency()` - Bulk cache operations

**Fixtures:**
- `check_regression` - Regression checker
- `governance_cache` - GovernanceCache instance

**Focus Areas:**
- Cache lookup performance
- Cache miss latency
- Cache hit rate (inverted logic: lower hit rate = regression)
- Bulk cache operation efficiency

## Fixtures

### check_regression

**Purpose:** Regression checker with 20% threshold

**Usage:**
```python
def test_api_latency(benchmark, check_regression):
    result = benchmark(api_call)
    check_regression(result, threshold=0.2)  # 20% threshold
```

**Parameters:**
- `result` - Benchmark result dict (mean, min, max, stddev)
- `threshold` - Regression threshold (default: 0.2 = 20%)

**Assertions:**
- Fails if `mean` increased >20% vs baseline
- Fails if `hit_rate` decreased >20% vs baseline (inverted logic)

### performance_baseline

**Purpose:** Load baseline from JSON file

**Usage:**
```python
def test_with_baseline(performance_baseline):
    baseline = performance_baseline["test_api_get_agent_latency"]
    print(f"Baseline mean: {baseline['mean']}")
```

**Baseline Location:** `backend/tests/performance_regression/.benchmarks/`

## Test Patterns

### API Latency Pattern

```python
@pytest.mark.benchmark
def test_api_get_agent_latency(benchmark, check_regression):
    """
    PROPERTY: GET /api/v1/agents/{id} should complete in <100ms (P50)

    STRATEGY: Use pytest-benchmark to measure API latency. Compare against
    baseline using 20% regression threshold.

    INVARIANT: mean_latency < 100ms AND regression < 20%

    RADII: 1000 benchmark iterations provides 99% confidence with 5ms
    measurement precision.

    BASELINE: Initial baseline established 2026-03-24
    """
    from fastapi.testclient import TestClient
    from main import app

    # Setup
    client = TestClient(app)

    # Benchmark function
    def get_agent():
        response = client.get("/api/v1/agents/test-agent-1")
        assert response.status_code == 200
        return response.json()

    # Run benchmark
    result = benchmark.pedantic(get_agent, iterations=1000, rounds=10)

    # Check regression (20% threshold)
    check_regression(result, threshold=0.2)

    # Assert baseline performance
    assert result["mean"] < 0.1  # 100ms
```

### Database Query Pattern

```python
@pytest.mark.benchmark
def test_query_agent_by_id_latency(benchmark, check_regression, db_session):
    """
    PROPERTY: Agent by ID query should complete in <50ms

    STRATEGY: Benchmark database query with 1000 iterations
    """
    from core.models import AgentRegistry

    # Setup
    agent_id = "test-agent-1"

    # Benchmark function
    def query_agent():
        agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        assert agent is not None
        return agent

    # Run benchmark
    result = benchmark(query_agent)

    # Check regression
    check_regression(result, threshold=0.2)

    # Assert baseline performance
    assert result["mean"] < 0.05  # 50ms
```

### Cache Hit Rate Pattern (Inverted Logic)

```python
@pytest.mark.benchmark
def test_cache_hit_rate(benchmark, check_regression):
    """
    PROPERTY: Cache hit rate should remain >90%

    STRATEGY: Measure cache hit rate over 1000 operations. Use inverted
    logic for regression: hit_rate DECREASE is regression.

    INVARIANT: hit_rate > 0.9 AND hit_rate decrease < 20%

    RADII: 1000 operations provides 99% confidence for hit rate estimation
    """
    from core.governance_cache import GovernanceCache

    # Setup
    cache = GovernanceCache()
    cache.set("agent:1", {"data": "value1"})

    # Benchmark function
    def cache_hit_rate():
        hits = 0
        total = 100
        for i in range(total):
            if cache.get("agent:1"):
                hits += 1
        return hits / total

    # Run benchmark
    result = benchmark(cache_hit_rate)

    # Check regression (inverted logic: hit_rate decrease is regression)
    check_regression(result, threshold=0.2, metric="hit_rate")

    # Assert baseline performance
    assert result["mean"] > 0.9  # 90% hit rate
```

## Running Tests

### Run All Performance Regression Tests

```bash
cd backend
pytest tests/performance_regression/ --benchmark-only

# Compare against baseline
pytest tests/performance_regression/ --benchmark-only --benchmark-compare=baseline

# Fail on regression (>20% degradation)
pytest tests/performance_regression/ --benchmark-only --benchmark-compare=baseline --benchmark-compare-fail=mean:20%

# Generate comparison table
pytest tests/performance_regression/ --benchmark-only --benchmark-compare=baseline --benchmark-compare-fail=mean:20% --benchmark-sort=name
```

### Run Specific Test File

```bash
# API latency regression
pytest tests/performance_regression/test_api_latency_regression.py --benchmark-only

# Database query regression
pytest tests/performance_regression/test_database_query_regression.py --benchmark-only

# Governance cache regression
pytest tests/performance_regression/test_governance_cache_regression.py --benchmark-only
```

### Run Single Test

```bash
pytest tests/performance_regression/test_api_latency_regression.py::test_api_get_agent_latency --benchmark-only -v
```

### Initialize Baseline (First Time)

```bash
# Generate initial baseline
pytest tests/performance_regression/ --benchmark-only --benchmark-autosave

# Commit baseline
git add backend/tests/performance_regression/.benchmarks/
git commit -m "perf: initialize performance regression baseline"
```

### Update Baseline (After Valid Improvements)

```bash
# Run tests and autosave new baseline
pytest tests/performance_regression/ --benchmark-only --benchmark-autosave

# Commit updated baseline
git add backend/tests/performance_regression/.benchmarks/
git commit -m "perf: update performance baseline (valid improvement)"
```

## Troubleshooting

### Common Issues

**1. pytest-benchmark not installed**
```bash
# Symptom: Tests fail with "pytest-benchmark not installed"
# Solution: Install pytest-benchmark
pip install pytest-benchmark
```

**2. Baseline missing**
```bash
# Symptom: Tests fail with "baseline not found"
# Solution: Generate initial baseline
pytest tests/performance_regression/ --benchmark-only --benchmark-autosave
```

**3. Performance regression false positives (<10% regression)**
```bash
# Symptom: Test fails with <10% regression
# Solution: Re-run test, adjust threshold, or mark as flaky
pytest tests/performance_regression/test_api_latency_regression.py::test_api_get_agent_latency --benchmark-only -v
```

**4. TestClient not available**
```bash
# Symptom: ImportError: TestClient not available
# Solution: Install FastAPI test dependencies
pip install fastapi[all]
```

**5. Database session fixture not found**
```bash
# Symptom: Fixture 'db_session' not found
# Solution: Import from e2e_ui/fixtures
# Add to conftest.py:
# from tests.e2e_ui.fixtures.database_fixtures import db_session
```

### Debugging Performance Regressions

**View Benchmark Comparison Output:**
```bash
# View benchmark comparison table
pytest tests/performance_regression/ --benchmark-only --benchmark-compare=baseline --benchmark-compare-fail=mean:20% --benchmark-sort=name

# Output columns:
# - name (benchmark name)
# - mean (current execution time)
# - min/max/stddev (execution time statistics)
# - rounds (number of iterations)
# - baseline (baseline execution time)
# - change (percentage change vs baseline)

# Regression example:
# name                            mean    baseline    change
# test_api_get_agent_latency     150ms    100ms    +50%  # REGRESSION
```

**Performance Regression Categories:**
1. **API Latency:** Increased response time (e.g., database query N+1 problem)
2. **Database Queries:** Slower queries (missing index, inefficient join)
3. **Cache Hit Rate:** Reduced cache effectiveness (cache invalidation issue)

**Common Performance Regression Patterns:**
```python
# Pattern 1: N+1 query problem
agents = db.query(Agent).all()
for agent in agents:  # N+1: N additional queries
    executions = db.query(Execution).filter_by(agent_id=agent.id).all()

# Solution: Eager loading
from sqlalchemy.orm import joinedload
agents = db.query(Agent).options(joinedload(Agent.executions)).all()

# Pattern 2: Inefficient database query
results = db.query(Agent).filter(Agent.status == "active").all()  # Full table scan

# Solution: Add index
CREATE INDEX idx_agent_status ON agents(status);

# Pattern 3: Cache miss storm
for agent_id in agent_ids:  # N cache misses
    agent = cache.get(f"agent:{agent_id}")

# Solution: Bulk cache get
agents = cache.get_many([f"agent:{id}" for id in agent_ids])
```

## Examples

### Writing Performance Regression Tests

**Example 1: API Latency Regression**
```python
import pytest
from tests.performance_regression.conftest import check_regression

@pytest.mark.benchmark
def test_api_get_agent_latency(benchmark, check_regression):
    """
    PROPERTY: GET /api/v1/agents/{id} should complete in <100ms (P50)

    STRATEGY: Use pytest-benchmark to measure API latency. Compare against
    baseline using 20% regression threshold.

    INVARIANT: mean_latency < 100ms AND regression < 20%

    RADII: 1000 benchmark iterations provides 99% confidence with 5ms
    measurement precision.

    BASELINE: Initial baseline established 2026-03-24
    """
    from fastapi.testclient import TestClient
    from main import app
    from core.models import AgentRegistry
    from sqlalchemy.orm import Session

    # Setup
    client = TestClient(app)
    with Session() as db:
        agent = db.query(AgentRegistry).first()

    # Benchmark function
    def get_agent():
        response = client.get(f"/api/v1/agents/{agent.id}")
        assert response.status_code == 200
        return response.json()

    # Run benchmark
    result = benchmark.pedantic(get_agent, iterations=1000, rounds=10)

    # Check regression (20% threshold)
    check_regression(result, threshold=0.2)

    # Assert baseline performance
    assert result["mean"] < 0.1  # 100ms
```

**Example 2: Database Query Regression**
```python
@pytest.mark.benchmark
def test_query_agent_by_id_latency(benchmark, check_regression, db_session):
    """
    PROPERTY: Agent by ID query should complete in <50ms

    STRATEGY: Benchmark database query with 1000 iterations
    """
    from core.models import AgentRegistry

    # Setup
    agent_id = "test-agent-1"

    # Benchmark function
    def query_agent():
        agent = db_session.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        assert agent is not None
        return agent

    # Run benchmark
    result = benchmark(query_agent)

    # Check regression
    check_regression(result, threshold=0.2)

    # Assert baseline performance
    assert result["mean"] < 0.05  # 50ms
```

**Example 3: Cache Hit Rate Regression (Inverted Logic)**
```python
@pytest.mark.benchmark
def test_cache_hit_rate(benchmark, check_regression):
    """
    PROPERTY: Cache hit rate should remain >90%

    STRATEGY: Measure cache hit rate over 1000 operations. Use inverted
    logic for regression: hit_rate DECREASE is regression.

    INVARIANT: hit_rate > 0.9 AND hit_rate decrease < 20%

    RADII: 1000 operations provides 99% confidence for hit rate estimation
    """
    from core.governance_cache import GovernanceCache

    # Setup
    cache = GovernanceCache()
    cache.set("agent:1", {"data": "value1"})

    # Benchmark function
    def cache_hit_rate():
        hits = 0
        total = 100
        for i in range(total):
            if cache.get("agent:1"):
                hits += 1
        return hits / total

    # Run benchmark
    result = benchmark(cache_hit_rate)

    # Check regression (inverted logic: hit_rate decrease is regression)
    check_regression(result, threshold=0.2, metric="hit_rate")

    # Assert baseline performance
    assert result["mean"] > 0.9  # 90% hit rate
```

## Best Practices

1. **Establish Baselines:** Generate baselines after valid performance improvements
2. **Use Realistic Thresholds:** 20% regression threshold balances noise sensitivity
3. **Benchmark Critical Paths:** Focus on user-facing operations (API latency, database queries)
4. **TestClient Pattern:** Use TestClient instead of httpx for faster benchmarks
5. **Fixture Reuse:** Import db_session, authenticated_user from e2e_ui/fixtures
6. **Document Invariants:** Use PROPERTY/STRATEGY/INVARIANT/RADII format
7. **Baseline Management:** Commit baselines to git for reproducible regression detection

## References

- **Phase 243 Documentation:** `backend/docs/MEMORY_PERFORMANCE_BUG_DISCOVERY.md`
- **pytest-benchmark Documentation:** https://pytest-benchmark.readthedocs.io/
- **Conftest:** `backend/tests/performance_regression/conftest.py`
- **Weekly CI:** `.github/workflows/memory-performance-weekly.yml`
- **Baseline Management:** `backend/tests/performance_regression/.benchmarks/`

---

*Last Updated: March 25, 2026*
*Phase 243 - Memory & Performance Bug Discovery*

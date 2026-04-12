# Memory & Performance Bug Discovery

**Phase:** 243 - Memory & Performance Bug Discovery
**Last Updated:** March 25, 2026
**Status:** Production Ready

## Overview

Atom's memory and performance bug discovery infrastructure enables automated detection of memory leaks, performance regressions, and browser performance issues through memray (Python memory profiler), pytest-benchmark (performance regression), and Lighthouse CI (browser performance).

**Key Features:**
- **Memory leak detection** using Bloomberg's memray profiler for Python heap analysis
- **Performance regression detection** using pytest-benchmark with 20% degradation threshold
- **Lighthouse CI integration** for automated browser performance testing
- **Weekly CI pipeline** running Sunday 3 AM UTC (separate from bug-discovery-weekly)
- **Automated bug filing** via MemoryPerformanceFilingService extending BugFilingService
- **Flame graph generation** for memory leak visualization and analysis
- **Baseline management** for performance regression detection
- **Graceful degradation** when dependencies unavailable (memray, pytest-benchmark)

## Architecture

### Discovery Methods

```
Memory & Performance Bug Discovery
├── 1. Memory Leak Detection (memray)
│   ├── Python heap leak detection
│   ├── Amplification loops (100 iterations)
│   ├── Flame graph generation
│   └── Threshold assertions (>10MB leak)
├── 2. Performance Regression (pytest-benchmark)
│   ├── API latency benchmarks
│   ├── Database query benchmarks
│   ├── Governance cache benchmarks
│   ├── Baseline comparison (--benchmark-compare=baseline)
│   └── 20% degradation threshold
└── 3. Lighthouse CI (Browser Performance)
    ├── Performance score > 90
    ├── Core Web Vitals (FCP, LCP, TBT, CLS)
    ├── Automated baseline updates
    └── Regression detection (--threshold 0.2)
```

### CI/CD Pipeline

**Weekly Pipeline:** `.github/workflows/memory-performance-weekly.yml`
- **Schedule:** Sunday 3 AM UTC (1 hour after bug-discovery-weekly to avoid overlap)
- **Jobs:**
  - `memory-leaks`: Runs memray tests sequentially (`-n 1`) with 60min timeout
  - `performance-regression`: Runs pytest-benchmark with 30min timeout
  - `lighthouse-ci`: Runs Lighthouse CI with regression check
  - `weekly-report`: Aggregates results, files bugs, generates HTML report

**Fast PR Tests:** Memory/performance tests excluded from PR pipelines (weekly only to avoid CI bloat)

## Setup

### Requirements

**Python 3.11+ Required for memray**

```bash
# Verify Python version
python --version  # Should be 3.11+

# Install memray (Python 3.11+ only)
pip install memray

# Install pytest-benchmark
pip install pytest-benchmark

# Install development dependencies
cd backend
pip install -e .
pip install -r requirements-testing.txt
```

### Memory Leak Detection Setup

```bash
# Install memray (Python 3.11+ only)
pip install memray

# Verify installation
python -c "import memray; print(memray.__version__)"
```

**Graceful Degradation:** If memray not installed, tests skip with pytest.skip

### Performance Regression Setup

```bash
# Install pytest-benchmark
pip install pytest-benchmark

# Verify installation
python -c "import pytest_benchmark; print(pytest_benchmark.__version__)"

# Initialize baseline (first time only)
cd backend
pytest tests/performance_regression/ --benchmark-only --benchmark-autosave
```

### Lighthouse CI Setup

```bash
# Install Lighthouse CLI globally
npm install -g lighthouse

# Verify installation
lighthouse --version

# Initialize Lighthouse baseline (first time only)
# Run Lighthouse CI pipeline, baseline auto-updated on main branch
```

## Usage

### Running Memory Leak Tests

```bash
# Run all memory leak tests
cd backend
pytest tests/memory_leaks/ -v -m memory_leak

# Run with sequential execution (required for memray)
pytest tests/memory_leaks/ -v -m memory_leak -n 1

# Run specific test file
pytest tests/memory_leaks/test_agent_execution_leaks.py -v

# Generate flame graphs
pytest tests/memory_leaks/ -v -m memory_leak --memray
# Flame graphs saved to: backend/tests/memory_leaks/artifacts/
```

### Running Performance Regression Tests

```bash
# Run all performance regression tests
cd backend
pytest tests/performance_regression/ --benchmark-only

# Compare against baseline
pytest tests/performance_regression/ --benchmark-only --benchmark-compare=baseline

# Fail on regression (>20% degradation)
pytest tests/performance_regression/ --benchmark-only --benchmark-compare=baseline --benchmark-compare-fail=mean:20%

# Update baseline (after valid performance improvements)
pytest tests/performance_regression/ --benchmark-only --benchmark-autosave

# Generate benchmark comparison table
pytest tests/performance_regression/ --benchmark-only --benchmark-compare=baseline --benchmark-compare-fail=mean:20% --benchmark-sort=name
```

### Running Lighthouse CI

```bash
# Start servers
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
cd frontend-nextjs
npm run build
npm start &

# Run Lighthouse manually
lighthouse http://localhost:3001/ --headless --output json --output html
lighthouse http://localhost:3001/dashboard --headless --output json --output html
lighthouse http://localhost:3001/agents --headless --output json --output html

# Check for regression
python backend/tests/scripts/check_lighthouse_regression.py \
  --current .lighthouseci/lhr-report.json \
  --baseline backend/tests/performance_regression/lighthouse_baseline.json \
  --threshold 0.2
```

### Running Full Memory & Performance Discovery

```bash
# Use orchestration function
cd backend
python -c "
from tests.bug_discovery.core import run_memory_performance_discovery
import os
result = run_memory_performance_discovery(
    github_token=os.getenv('GITHUB_TOKEN'),
    github_repository=os.getenv('GITHUB_REPOSITORY'),
    upload_artifacts=True
)
print(f'Bugs found: {result[\"bugs_found\"]}')
print(f'Memory leaks: {result[\"memory_leaks\"][\"bugs_found\"]}')
print(f'Performance regressions: {result[\"performance_regressions\"][\"bugs_found\"]}')
print(f'Lighthouse issues: {result[\"lighthouse\"][\"bugs_found\"]}')
print(f'Bugs filed: {result[\"filed_bugs\"]}')
print(f'Report: {result[\"report_path\"]}')
"
```

## CI/CD Integration

### Weekly Pipeline

**Workflow:** `.github/workflows/memory-performance-weekly.yml`

**Schedule:**
```yaml
schedule:
  - cron: '0 3 * * 0'  # Sunday 3 AM UTC
```

**Jobs:**

1. **memory-leaks** (60min timeout)
   - Runs memray tests sequentially: `pytest tests/memory_leaks/ -v -m memory_leak -n 1`
   - Uploads flame graphs as artifacts
   - Graceful degradation if memray unavailable

2. **performance-regression** (30min timeout)
   - Runs pytest-benchmark with comparison: `pytest tests/performance_regression/ --benchmark-only --benchmark-compare=baseline --benchmark-compare-fail=mean:20%`
   - Uploads benchmark JSON results
   - Fails pipeline on >20% performance regression

3. **lighthouse-ci** (30min timeout)
   - Starts backend and frontend servers
   - Runs Lighthouse CI on critical pages
   - Checks for regression using `check_lighthouse_regression.py`
   - Uploads Lighthouse reports

4. **weekly-report** (runs after all jobs, even if failures)
   - Downloads all artifacts
   - Runs `run_memory_performance_discovery()` orchestration
   - Files bugs to GitHub via BugFilingService
   - Generates weekly HTML report

**Artifacts:**
- `memray-flame-graphs`: Flame graph HTML files from memray
- `benchmark-results`: Benchmark JSON files from pytest-benchmark
- `lighthouse-reports`: Lighthouse JSON/HTML reports
- `memory-performance-weekly-report`: Aggregated weekly HTML report

**Retention:** 30 days

### Bug Filing Integration

**MemoryPerformanceFilingService** extends BugFilingService with specialized severity classification:

```python
# Severity classification for memory leaks
LEAK_SIZE_CRITICAL = 50 * 1024 * 1024  # 50MB
LEAK_SIZE_HIGH = 10 * 1024 * 1024     # 10MB

# Severity classification for performance regressions
REGRESSION_CRITICAL = 1.0  # 100% degradation
REGRESSION_HIGH = 0.5      # 50% degradation
```

**Bug Metadata:**
```python
{
    "test_type": "memory_leak" | "performance_regression" | "lighthouse",
    "severity": "critical" | "high" | "medium" | "low",
    "leak_size_bytes": 12345678,
    "regression_percent": 25.5,
    "lighthouse_score": 75,
    "flame_graph_path": "backend/tests/memory_leaks/artifacts/flamegraph.html"
}
```

## Baseline Management

### Performance Regression Baselines

**Location:** `backend/tests/performance_regression/.benchmarks/`

**Update Baseline (after valid improvements):**
```bash
# Run tests and autosave new baseline
pytest tests/performance_regression/ --benchmark-only --benchmark-autosave

# Commit updated baseline
git add backend/tests/performance_regression/.benchmarks/
git commit -m "perf: update performance baseline (valid improvement)"
```

**Baseline Comparison:**
```bash
# Compare against baseline
pytest tests/performance_regression/ --benchmark-only --benchmark-compare=baseline

# Fail on regression
pytest tests/performance_regression/ --benchmark-only --benchmark-compare=baseline --benchmark-compare-fail=mean:20%
```

**20% Threshold Rationale:**
- Detects significant performance degradations
- Allows for minor measurement noise (±5-10%)
- Prevents false positives from CI environment variability
- Aligns with industry best practices for performance regression detection

### Lighthouse Baseline

**Location:** `backend/tests/performance_regression/lighthouse_baseline.json`

**Automatic Updates:**
- Baseline auto-updated on main branch pushes
- Handled by `.github/workflows/lighthouse-ci.yml`
- Requires manual verification of performance improvements

**Manual Update:**
```bash
# Run Lighthouse CI
npm run lighthouse:ci

# Update baseline
cp .lighthouseci/lhr-report.json backend/tests/performance_regression/lighthouse_baseline.json

# Commit updated baseline
git add backend/tests/performance_regression/lighthouse_baseline.json
git commit -m "chore: update Lighthouse baseline (valid improvement)"
```

## Troubleshooting

### Common Issues

**1. memray not installed (Python 3.11+ required)**
```bash
# Symptom: Tests skip with "memray not installed"
# Solution: Install memray (Python 3.11+ only)
pip install memray
```

**2. pytest-benchmark not installed**
```bash
# Symptom: Tests fail with "pytest-benchmark not installed"
# Solution: Install pytest-benchmark
pip install pytest-benchmark
```

**3. Baseline missing for performance regression**
```bash
# Symptom: Tests fail with "baseline not found"
# Solution: Generate initial baseline
pytest tests/performance_regression/ --benchmark-only --benchmark-autosave
```

**4. Lighthouse baseline missing**
```bash
# Symptom: Regression check fails with "baseline file not found"
# Solution: Run Lighthouse CI and generate baseline
npm run lighthouse:ci
cp .lighthouseci/lhr-report.json backend/tests/performance_regression/lighthouse_baseline.json
```

**5. Memory leak test false positives (GC delay)**
```bash
# Symptom: Test fails with small leak (<1MB)
# Solution: Increase threshold or add gc.collect() delay
pytest tests/memory_leaks/test_agent_execution_leaks.py -v -k "test_agent_execution_no_memory_leak"
```

**6. Performance regression false positives (CI noise)**
```bash
# Symptom: Test fails with <10% regression
# Solution: Re-run test, adjust threshold, or mark as flaky
pytest tests/performance_regression/test_api_latency_regression.py -v --benchmark-only
```

**7. Lighthouse CI frontend not available**
```bash
# Symptom: Lighthouse tests fail with "frontend not available"
# Solution: Start frontend server manually
cd frontend-nextjs
npm run build
npm start &
```

### Debugging Memory Leaks

**View Flame Graphs:**
```bash
# Open flame graph in browser
open backend/tests/memory_leaks/artifacts/test_agent_execution_no_memory_leak.html

# Flame graph shows:
# - Function call stacks
# - Memory allocation hotspots
# - Leak locations (tall towers)
```

**Memory Leak Categories:**
1. **Python Heap Leaks:** Uncollected objects (circular references, global caches)
2. **C Extension Leaks:** Native memory leaks (e.g., SQLAlchemy connection pools)
3. **Amplification Leaks:** Small leaks multiplied over iterations

**Common Memory Leak Patterns:**
```python
# Pattern 1: Global list growing unbounded
GLOBAL_CACHE = []  # LEAK: Never cleared

# Pattern 2: Circular references
class Agent:
    def __init__(self):
        self.parent = None
        self.children = []
        # Circular reference: parent <-> children

# Pattern 3: Unclosed database connections
from sqlalchemy.orm import Session
session = Session()  # LEAK: Never closed
```

### Debugging Performance Regressions

**Benchmark Comparison Output:**
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

### Debugging Lighthouse Issues

**Lighthouse Categories:**
- **Performance:** Overall score (target > 90)
- **Accessibility:** WCAG 2.1 compliance (target > 90)
- **Best Practices:** Web best practices (target > 90)
- **SEO:** Search engine optimization (target > 80)

**Core Web Vitals:**
- **FCP (First Contentful Paint):** Target < 1.5s
- **LCP (Largest Contentful Paint):** Target < 2.5s
- **TBT (Total Blocking Time):** Target < 300ms
- **CLS (Cumulative Layout Shift):** Target < 0.1

**Common Lighthouse Issues:**
1. **Large JavaScript bundles:** Code splitting, tree shaking
2. **Unoptimized images:** Use WebP, lazy loading, responsive images
3. **Render-blocking resources:** Async/defer scripts, inline critical CSS
4. **Excessive DOM size:** Virtual scrolling, pagination
5. **Unused CSS:** PurgeCSS, critical CSS extraction

## Examples

### Writing Memory Leak Tests

```python
import pytest
from tests.memory_leaks.conftest import memray_session

@pytest.mark.memory_leak
def test_agent_execution_no_memory_leak(memray_session):
    """
    PROPERTY: Agent execution should not leak memory over 100 iterations

    STRATEGY: Use memray to track Python heap allocations during repeated
    agent execution operations. Amplify potential leaks by running 100
    iterations.

    INVARIANT: max_memory_increase < LEAK_THRESHOLD (10MB)

    RADII: 100 iterations provides 99% confidence for detecting leaks
    with 1MB amplification (100 * 10KB per execution).
    """
    from core.agent_governance_service import AgentGovernanceService
    from core.models import AgentRegistry

    # Setup
    service = AgentGovernanceService()

    with memray_session:
        # Amplification loop: 100 iterations
        for i in range(100):
            agent = AgentRegistry(
                id=f"test-agent-{i}",
                name=f"Test Agent {i}",
                category="testing",
                module_path="core.agent_governance_service",
                class_name="AgentGovernanceService",
                status="AUTONOMOUS"
            )

            # Execute agent (potential leak point)
            service.execute_agent(agent.id)

        # Assertion: No memory leak
        assert memray_session.get_max_memory_increase() < 10 * 1024 * 1024  # 10MB
```

### Writing Performance Regression Tests

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
    result = benchmark(get_agent)

    # Check regression (20% threshold)
    check_regression(result, threshold=0.2)

    # Assert baseline performance
    assert result["mean"] < 0.1  # 100ms
```

## Best Practices

### Memory Leak Testing

1. **Use Amplification Loops:** Run operations 100-1000x to amplify small leaks
2. **Set Realistic Thresholds:** 10MB for Python heap leaks (allows for GC delay)
3. **Generate Flame Graphs:** Essential for debugging complex leaks
4. **Test Sequential Execution:** Use `-n 1` to avoid interference from parallel tests
5. **Graceful Degradation:** Skip tests if memray unavailable (Python 3.11+ required)

### Performance Regression Testing

1. **Establish Baselines:** Generate baselines after valid performance improvements
2. **Use Realistic Thresholds:** 20% regression threshold balances noise sensitivity
3. **Benchmark Critical Paths:** Focus on user-facing operations (API latency, database queries)
4. **TestClient Pattern:** Use TestClient instead of httpx for faster benchmarks
5. **Fixture Reuse:** Import db_session, authenticated_user from e2e_ui/fixtures

### Lighthouse CI Testing

1. **Automate Baseline Updates:** Auto-update on main branch pushes
2. **Set Realistic Budgets:** Performance > 90, FCP < 1.5s, LCP < 2.5s, TBT < 300ms, CLS < 0.1
3. **Test Critical Pages:** Homepage, dashboard, agents list, workflows
4. **Regression Detection:** Use check_lighthouse_regression.py with 20% threshold
5. **Server Startup:** Ensure backend/frontend servers running before Lighthouse tests

## References

- **Phase 243 Research:** `.planning/phases/243-memory-and-performance-bug-discovery/243-RESEARCH.md`
- **Bug Discovery Infrastructure:** `docs/testing/BUG_DISCOVERY_INFRASTRUCTURE.md`
- **Memory Leak Tests:** `backend/tests/memory_leaks/README.md`
- **Performance Regression Tests:** `backend/tests/performance_regression/README.md`
- **Lighthouse Regression Script:** `backend/tests/scripts/check_lighthouse_regression.py`
- **Weekly CI Workflow:** `.github/workflows/memory-performance-weekly.yml`
- **Bug Filing Service:** `backend/tests/bug_discovery/bug_filing_service.py`
- **Discovery Coordinator:** `backend/tests/bug_discovery/core/discovery_coordinator.py`

---

*Last Updated: March 25, 2026*
*Phase 243 - Memory & Performance Bug Discovery*

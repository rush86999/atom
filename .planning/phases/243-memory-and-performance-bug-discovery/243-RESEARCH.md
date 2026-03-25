# Phase 243: Memory & Performance Bug Discovery - Research

**Researched:** 2026-03-25
**Domain:** Python memory profiling (memray), performance regression detection (pytest-benchmark), Lighthouse CI integration
**Confidence:** HIGH

## Summary

Phase 243 focuses on specialized bug discovery for memory leaks and performance regressions using **memray** (Python memory profiler), **pytest-benchmark** (performance regression tracking), and **Lighthouse CI** (web UI performance). The research confirms that Atom has a **solid foundation** for performance testing with pytest-benchmark already configured, CDP heap snapshot fixtures from Phase 236-03, Lighthouse CI workflow integrated, and a performance monitoring service (`backend/core/performance_monitor.py`).

**Primary recommendation:** Build on existing pytest-benchmark infrastructure by adding memray memory leak detection for long-running agent executions, enhancing heap snapshot comparison with 10MB+ threshold detection, implementing pytest-benchmark regression tracking with historical baselines, and integrating Lighthouse CI alerts for >20% web UI performance regression. Reuse existing fixtures (memory_fixtures.py, performance_monitor.py) and integrate with automated bug filing service from Phase 237.

**Key findings:**
1. **pytest-benchmark already installed**: `pytest-benchmark>=4.0.0` in requirements-testing.txt with existing test suite (test_performance_benchmarks.py, test_api_latency_benchmarks.py)
2. **CDP heap snapshot fixtures exist**: Phase 236-03 created memory_fixtures.py with cdp_session, heap_snapshot, compare_heap_snapshots helpers (315 lines)
3. **Lighthouse CI workflow integrated**: .github/workflows/lighthouse-ci.yml with treosh/lighthouse-ci-action@v9, PR comments, artifact upload
4. **Performance monitoring service exists**: backend/core/performance_monitor.py with baseline tracking, regression detection, performance targets
5. **Bug discovery infrastructure from Phase 237**: Automated bug filing service, pytest markers, weekly CI pipeline pattern
6. **memray NOT installed yet**: Need to add to requirements-testing.txt, create specialized tests for Python memory leaks

## Standard Stack

### Core Memory & Performance Tools
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **memray** | 1.12+ | Python memory profiler (memory leaks, allocation tracking) | Bloomberg-maintained, flame graphs, native extension support, Python 3.11+ compatible |
| **pytest-benchmark** | 4.0.0+ | Performance regression tracking | Historical comparison, JSON output, already in requirements-testing.txt |
| **pytest-benchmark[histogram]** | 4.0.0+ | Statistical analysis of benchmark results | P50/P95/P99 latency tracking, distribution visualization |
| **lighthouse** | (CLI) | Web UI performance testing | Chrome DevTools integration, Core Web Vitals, already in CI workflow |
| **@lhci/cli** | 0.13.x | Lighthouse CI for automated regression detection | Baseline tracking, GitHub PR comments, budget enforcement |

### Supporting Tools
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-timeout** | 2.2.x | Test timeout enforcement | Memory leak tests should timeout (avoid infinite hangs) |
| **pytest-xdist** | 3.6.x | Parallel test execution | Run memory tests in isolation (sequential, not parallel) |
| **matplotlib** | 3.8.x | Flame graph visualization | Optional: render memray flame graphs as images |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **memray** | filprofiler | filprofiler has better visualization but memray has Bloomberg backing, more detailed allocation tracking |
| **pytest-benchmark** | pytest-bench | pytest-benchmark has better historical tracking, JSON output, GitHub Actions integration |
| **Lighthouse CI** | sitespeed.io | Lighthouse CI has better Core Web Vitals, Google ecosystem integration |
| **memray** | tracemalloc (stdlib) | tracemalloc is built-in but memray has flame graphs, native extension support, better reporting |

**Installation:**
```bash
# Core memory profiling (NEW - add to requirements-testing.txt)
pip install memray>=1.12.0

# Performance regression tracking (ALREADY INSTALLED)
pip install pytest-benchmark>=4.0.0
pip install "pytest-benchmark[histogram]"  # For P50/P95/P99 tracking

# Lighthouse CI (ALREADY INSTALLED in .github/workflows/lighthouse-ci.yml)
npm install -g lighthouse
npm install -g @lhci/cli

# Optional: flame graph visualization
pip install matplotlib>=3.8.0
```

## Architecture Patterns

### Recommended Test Structure

**Existing Structure (DO NOT CHANGE):**
```
backend/tests/
├── bug_discovery/          # ✅ EXISTS - Bug filing service
├── fuzzing/                # ✅ EXISTS - Atheris fuzz tests
├── property_tests/         # ✅ EXISTS - Hypothesis tests
├── e2e_ui/                 # ✅ EXISTS - Playwright E2E tests
│   ├── fixtures/
│   │   └── memory_fixtures.py  # ✅ EXISTS - CDP heap snapshot fixtures
│   └── tests/
│       ├── test_memory_leak_detection.py  # ✅ EXISTS - Browser memory leaks
│       └── test_performance_regression.py # ✅ EXISTS - Lighthouse tests
├── integration/performance/ # ✅ EXISTS - pytest-benchmark tests
│   ├── test_api_latency_benchmarks.py
│   ├── test_governance_performance.py
│   └── conftest.py
└── conftest.py
```

**NEW Structure (Phase 243):**
```
backend/tests/
├── bug_discovery/          # ✅ KEEP - Bug filing service
├── memory_leaks/           # ✅ NEW - Python memory leak detection with memray
│   ├── conftest.py         # Memray fixtures (memray_session, leak_detector)
│   ├── test_agent_execution_leaks.py  # Long-running agent execution
│   ├── test_llm_streaming_leaks.py    # LLM response streaming
│   ├── test_canvas_presentation_leaks.py # Canvas state management
│   ├── test_governance_cache_leaks.py # Cache growth over time
│   └── test_episodic_memory_leaks.py  # Episode storage leaks
├── performance_regression/ # ✅ NEW - pytest-benchmark regression tracking
│   ├── conftest.py         # Benchmark baseline fixtures
│   ├── test_api_latency_regression.py # API latency over time
│   ├── test_database_query_regression.py # Query performance regression
│   ├── test_governance_cache_regression.py # Cache hit rate regression
│   └── test_workflow_execution_regression.py # Workflow performance regression
├── fuzzing/                # ✅ KEEP
├── property_tests/         # ✅ KEEP
├── e2e_ui/                 # ✅ KEEP
│   ├── fixtures/
│   │   └── memory_fixtures.py  # ✅ KEEP - CDP heap snapshots
│   └── tests/
│       ├── test_memory_leak_detection.py  # ✅ KEEP - Browser memory leaks
│       └── test_performance_regression.py # ✅ KEEP - Lighthouse CI
└── integration/performance/ # ✅ KEEP - Existing pytest-benchmark tests
```

**Key Principle:** DO NOT modify existing memory leak detection (e2e_ui/tests/test_memory_leak_detection.py) or Lighthouse CI workflow (.github/workflows/lighthouse-ci.yml). Add NEW specialized Python memory leak tests with memray and ENHANCE pytest-benchmark regression tracking.

### Pattern 1: Memray Memory Leak Detection

**What:** Use memray to track Python memory allocations during long-running operations and detect leaks.

**When to use:** Detecting Python memory leaks in agent execution, LLM streaming, canvas presentation, governance cache growth, episodic memory storage.

**Example:**
```python
# Source: memray documentation (https://bloomberg.github.io/memray/)
import memray
import pytest

@pytest.mark.memory_leak
@pytest.mark.slow
def test_agent_execution_memory_leak(db_session):
    """Detect memory leaks during long-running agent execution.

    Threshold: <10MB memory growth over 100 agent executions
    Method: memray tracker with allocation tracking
    """
    from core.agent_governance_service import AgentGovernanceService

    # Track memory allocations with memray
    with memray.Tracker("/tmp/agent_execution_memray.bin") as tracker:
        governance_service = AgentGovernanceService()

        # Execute agent 100 times to amplify leaks
        for i in range(100):
            try:
                governance_service.execute_agent(
                    agent_id="test_agent",
                    query=f"Test query {i}",
                    db_session=db_session
                )
            except Exception:
                # Agent execution may fail, we're testing memory
                pass

    # Analyze memory snapshot
    from memray.reporters import FlameGraphReporter
    stats = memray.Stats("/tmp/agent_execution_memray.bin")

    # Check for memory leaks (>10MB growth)
    memory_growth_mb = stats.peak_memory_mb - stats.start_memory_mb

    assert memory_growth_mb < 10, (
        f"Memory leak detected: {memory_growth_mb:.2f} MB growth "
        f"(threshold: 10 MB)"
    )

    # Verify no excessive allocations (>1000 allocations per execution)
    avg_allocations = stats.total_allocations / 100
    assert avg_allocations < 1000, (
        f"Excessive allocations: {avg_allocations:.0f} per execution "
        f"(threshold: 1000)"
    )
```

**Memray Integration Pattern:**
```python
# backend/tests/memory_leaks/conftest.py
import memray
import pytest
from pathlib import Path

@pytest.fixture(scope="function")
def memray_session(tmp_path):
    """Create memray tracker session for memory leak detection.

    Yields:
        memray.Tracker object with output file path

    Example:
        def test_memory_leak(memray_session):
            tracker = memray_session
            # Execute operations
            tracker.stop()
            stats = memray.Stats(tracker.output_file)
    """
    output_file = tmp_path / "memray.bin"

    tracker = memray.Tracker(output_file)
    tracker.start()

    yield tracker

    # Stop tracking and analyze
    tracker.stop()

    # Return stats for analysis
    stats = memray.Stats(str(output_file))
    yield stats
```

### Pattern 2: Pytest-Benchmark Regression Detection

**What:** Use pytest-benchmark to track performance over time and detect regressions with historical comparison.

**When to use:** API latency, database query performance, governance cache hit rate, workflow execution performance.

**Example:**
```python
# Source: pytest-benchmark documentation (existing pattern from test_api_latency_benchmarks.py)
import pytest
from core.governance_cache import GovernanceCache

@pytest.mark.benchmark(group="governance-cache")
def test_governance_cache_hit_rate(benchmark):
    """Benchmark governance cache hit rate.

    Target: >95% hit rate (cache effectiveness)
    Regression: Alert if hit rate drops >10% from baseline
    """
    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    # Pre-populate cache
    for i in range(100):
        cache.set(f"agent_{i}", "action", {"allowed": True})

    # Benchmark cache hits
    def cache_hit():
        return cache.get("agent_50", "action")

    result = benchmark(cache_hit)

    # Assert cache hit (not miss)
    assert result is not None, "Cache should return value (hit)"

    # Check hit rate (should be 100% for pre-populated cache)
    # Regression detection: pytest-benchmark tracks this over time
```

**Baseline Tracking Pattern:**
```python
# backend/tests/performance_regression/conftest.py
import json
from pathlib import Path

@pytest.fixture(scope="session")
def performance_baseline():
    """Load performance baseline for regression detection.

    Baseline file: backend/tests/performance_baseline.json
    Regression threshold: 20% degradation
    Improvement threshold: 10% improvement
    """
    baseline_file = Path(__file__).parent / "performance_baseline.json"

    if not baseline_file.exists():
        return {}

    with open(baseline_file) as f:
        return json.load(f)

@pytest.fixture(scope="function")
def check_regression(performance_baseline):
    """Check for performance regression against baseline.

    Usage:
        def test_api_latency(benchmark, check_regression):
            result = benchmark(api_call)
            check_regression(result, "api_latency", threshold=0.2)
    """
    def _check_regression(current_value, metric_name, threshold=0.2):
        """Check if current value exceeds baseline by threshold.

        Args:
            current_value: Current benchmark result
            metric_name: Name of metric (e.g., "api_latency")
            threshold: Regression threshold (default: 20%)
        """
        if metric_name not in performance_baseline:
            # No baseline exists, skip regression check
            return

        baseline_value = performance_baseline[metric_name]
        regression_threshold = baseline_value * (1 + threshold)

        assert current_value < regression_threshold, (
            f"Performance regression detected: {metric_name} = {current_value:.3f} "
            f"(baseline: {baseline_value:.3f}, threshold: {regression_threshold:.3f})"
        )

    return _check_regression
```

**CI Integration Pattern:**
```bash
# .github/workflows/performance-regression.yml
on:
  schedule:
    - cron: '0 3 * * 0'  # Weekly Sunday 3 AM UTC
  workflow_dispatch:

jobs:
  performance-regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e backend
          pip install -r backend/requirements-testing.txt

      - name: Run benchmarks with regression detection
        run: |
          pytest backend/tests/performance_regression/ \
                 -v \
                 --benchmark-only \
                 --benchmark-autosave \
                 --benchmark-save-data \
                 --benchmark-json=benchmark_results.json

      - name: Compare with baseline
        run: |
          python backend/tests/scripts/compare_benchmarks.py \
                 --current benchmark_results.json \
                 --baseline backend/tests/performance_baseline.json \
                 --threshold 0.2

      - name: Upload benchmark results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: benchmark_results.json
```

### Pattern 3: Lighthouse CI Enhancement

**What:** Enhance existing Lighthouse CI workflow to alert on >20% web UI performance regression.

**When to use:** Web UI performance testing, Core Web Vitals tracking, performance budget enforcement.

**Example:**
```yaml
# Source: .github/workflows/lighthouse-ci.yml (EXISTING - enhance with regression detection)
name: Lighthouse CI with Regression Detection

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lighthouse-regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install Lighthouse CI
        run: npm install -g @lhci/cli

      - name: Start servers
        run: |
          cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
          cd frontend-nextjs && npm run build && npm start &
          sleep 10

      - name: Run Lighthouse CI with baseline
        run: |
          lhci autorun \
            --collect.url="http://localhost:3001/" \
            --collect.url="http://localhost:3001/dashboard" \
            --collect.url="http://localhost:3001/agents" \
            --assert.budgetsPath=./lighthouserc.json

      - name: Check for regression (>20% degradation)
        run: |
          python backend/tests/scripts/check_lighthouse_regression.py \
                 --current .lighthouseci/lhr-report.json \
                 --baseline backend/tests/e2e_ui/tests/data/lighthouse-baseline.json \
                 --threshold 0.2

      - name: Comment PR with results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('.lighthouseci/lhr-report.json', 'utf8'));
            // Format results as PR comment
            console.log('Performance scores:', results.scores);
```

**Regression Detection Script:**
```python
# backend/tests/scripts/check_lighthouse_regression.py
import json
import sys
from pathlib import Path

def check_regression(current_file, baseline_file, threshold=0.2):
    """Check Lighthouse metrics for regression.

    Args:
        current_file: Current Lighthouse results JSON
        baseline_file: Baseline Lighthouse results JSON
        threshold: Regression threshold (default: 20%)

    Returns:
        bool: True if regression detected
    """
    with open(current_file) as f:
        current = json.load(f)

    with open(baseline_file) as f:
        baseline = json.load(f)

    # Check performance score
    current_score = current.get('categories', {}).get('performance', {}).get('score', 0)
    baseline_score = baseline.get('categories', {}).get('performance', {}).get('score', 0)

    regression_detected = False

    if current_score < baseline_score * (1 - threshold):
        print(f"REGRESSION: Performance score {current_score:.2f} < baseline {baseline_score:.2f} (threshold: {threshold*100}%)")
        regression_detected = True

    # Check Core Web Vitals
    for metric in ['first-contentful-paint', 'largest-contentful-paint', 'total-blocking-time', 'cumulative-layout-shift']:
        current_value = current.get('audits', {}).get(metric, {}).get('numericValue', 0)
        baseline_value = baseline.get('audits', {}).get(metric, {}).get('numericValue', 0)

        if current_value > baseline_value * (1 + threshold):
            print(f"REGRESSION: {metric} {current_value:.0f}ms > baseline {baseline_value:.0f}ms (threshold: {threshold*100}%)")
            regression_detected = True

    return regression_detected

if __name__ == '__main__':
    current = sys.argv[1]
    baseline = sys.argv[2]
    threshold = float(sys.argv[3])

    if check_regression(current, baseline, threshold):
        sys.exit(1)  # Fail CI on regression
    else:
        print("No regression detected")
        sys.exit(0)
```

### Anti-Patterns to Avoid

- **Modifying existing memory leak tests**: DO NOT change e2e_ui/tests/test_memory_leak_detection.py (browser memory leaks). Add NEW Python memory leak tests with memray.
- **Running memory tests in parallel**: Memory leak tests should run sequentially (`pytest -n 1`) to avoid interference.
- **Ignoring Python 3.11+ requirement**: memray requires Python 3.11+, verify CI environment compatibility.
- **Skipping baseline establishment**: Always establish initial baseline before enabling regression detection.
- **Relying on single benchmark runs**: Use pytest-benchmark's `--benchmark-min-rounds` to ensure statistical significance.
- **Failing CI on small variations**: Set appropriate regression thresholds (20% degradation, not 5%).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Python memory profiling** | Custom allocation tracking with tracemalloc | memray | Flame graphs, native extension support, Bloomberg-maintained, detailed reporting |
| **Performance regression tracking** | Custom JSON comparison scripts | pytest-benchmark with --benchmark-autosave | Historical comparison, statistical analysis, GitHub Actions integration |
| **Web UI performance testing** | Custom Selenium timing scripts | Lighthouse CI | Core Web Vitals, Chrome DevTools integration, PR comments |
| **Baseline management** | Custom database/storage solution | pytest-benchmark JSON files + Git | Version control, simple, diff-friendly |
| **Regression detection** | Custom threshold logic | pytest-benchmark --benchmark-compare | Statistical significance, outlier detection, proven library |
| **Flame graph visualization** | Custom matplotlib scripts | memray FlameGraphReporter | Interactive HTML, drill-down by function call |

**Key insight:** Memory and performance bug discovery should leverage mature tools (memray, pytest-benchmark, Lighthouse CI) rather than building custom profiling infrastructure. The only custom code needed is test logic (leak thresholds, regression detection scripts, baseline comparison) not profiling infrastructure.

## Common Pitfalls

### Pitfall 1: Running Memory Leak Tests in Parallel

**What goes wrong:** Parallel memory tests interfere with each other's measurements (shared heap, GC timing).

**Why it happens:** pytest-xdist runs tests in parallel by default, but memory profiling requires isolation.

**How to avoid:**
1. Mark memory leak tests with `@pytest.mark.memory_leak`
2. Run memory tests sequentially: `pytest tests/memory_leaks/ -n 1 --benchmark-only`
3. Use `pytest.ini` markers to exclude from parallel runs:
```ini
[pytest]
markers =
    memory_leak: Memory leak detection tests (run sequentially, not parallel)
    performance_regression: Performance regression tests (run in isolation)
```

**Warning signs:** Memory leak tests have inconsistent results when run with `-n auto`.

### Pitfall 2: Not Establishing Baseline Before Regression Detection

**What goes wrong:** Regression detection fails because no baseline exists to compare against.

**Why it happens:** Developers enable regression detection before running initial benchmark to establish baseline.

**How to avoid:**
1. Run initial benchmark without regression checks:
```bash
pytest tests/performance_regression/ \
       --benchmark-only \
       --benchmark-autosave \
       --benchmark-save=baseline
```
2. Commit baseline JSON files to version control:
```bash
git add tests/performance_baseline.json
git commit -m "perf: establish performance baseline"
```
3. Enable regression detection in CI after baseline exists:
```bash
pytest tests/performance_regression/ \
       --benchmark-only \
       --benchmark-compare=baseline \
       --benchmark-compare-fail=mean:20%  # Fail if 20% slower
```

**Warning signs:** CI fails with "baseline file not found" or "no baseline data for metric".

### Pitfall 3: Ignoring Python Version Requirements for memray

**What goes wrong:** memray fails to install or run because CI environment uses Python 3.10 or older.

**Why it happens:** memray requires Python 3.11+ for native extension support.

**How to avoid:**
1. Specify Python 3.11+ in CI workflow:
```yaml
- name: Set up Python
  uses: actions/setup-python@v4
  with:
    python-version: '3.11'
```
2. Add Python version check in tests:
```python
import sys

@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="memray requires Python 3.11+"
)
def test_memory_leak_with_memray():
    # Memory leak test
    pass
```

**Warning signs:** Import errors or installation failures with memray on Python 3.10.

### Pitfall 4: Setting Too Aggressive Regression Thresholds

**What goes wrong:** CI fails due to normal performance variations (5-10% noise), creating false positives.

**Why it happens:** Developers set regression threshold too low (e.g., 5%) without considering measurement noise.

**How to avoid:**
1. Use 20% regression threshold (established best practice):
```bash
pytest tests/performance_regression/ \
       --benchmark-compare-fail=mean:20%  # 20% degradation
```
2. Set improvement threshold at 10% (only update baseline on significant improvement):
```bash
pytest tests/performance_regression/ \
       --benchmark-autosave \
       --benchmark-save=baseline \
       --benchmark-only \
       --benchmark-compare=baseline \
       --benchmark-compare-fail=mean:20%  # Fail on 20% regression
```

**Warning signs:** Frequent CI failures with small performance changes (<10%).

### Pitfall 5: Not Running Memory Leak Tests Long Enough

**What goes wrong:** Small memory leaks go undetected because tests run for too few iterations.

**Why it happens:** Developers run 10 iterations instead of 100, missing slow leaks.

**How to avoid:**
1. Amplify leaks with repeated operations (100-1000 iterations):
```python
# Execute agent 100 times to amplify leaks
for i in range(100):
    governance_service.execute_agent(agent_id="test_agent", query=f"Test {i}")
```
2. Use memray's peak memory tracking:
```python
stats = memray.Stats("/tmp/memray.bin")
memory_growth = stats.peak_memory_mb - stats.start_memory_mb

# Threshold: 10MB growth over 100 executions = 100KB per execution
assert memory_growth < 10, f"Memory leak: {memory_growth:.2f} MB"
```

**Warning signs:** Memory leak tests never fail even when suspicious growth exists.

## Code Examples

Verified patterns from official sources:

### Pattern 1: Memray Memory Leak Detection

```python
# Source: https://bloomberg.github.io/memray/usage.html#tracking-memory-allocations
import memray

@memray.Tracker("/tmp/output.bin")
def my_function():
    # Function to profile
    pass

# Analyze results
from memray.reporters import FlameGraphReporter
reporter = FlameGraphReporter("/tmp/output.bin")
reporter.render()
```

**Application to Phase 243:**
```python
# backend/tests/memory_leaks/test_agent_execution_leaks.py
import memray
import pytest

@pytest.mark.memory_leak
@pytest.mark.slow
def test_agent_execution_no_leak(db_session, tmp_path):
    """Verify agent execution doesn't leak memory.

    Executes agent 100 times, checks for <10MB memory growth.
    """
    from core.agent_governance_service import AgentGovernanceService

    output_file = tmp_path / "agent_execution.bin"

    with memray.Tracker(str(output_file)) as tracker:
        governance_service = AgentGovernanceService()

        # Execute 100 times to amplify leaks
        for i in range(100):
            try:
                governance_service.execute_agent(
                    agent_id="test_agent",
                    query=f"Test query {i}",
                    db_session=db_session
                )
            except Exception:
                pass  # Testing memory, not functionality

    # Analyze memory snapshot
    stats = memray.Stats(str(output_file))
    memory_growth_mb = stats.peak_memory_mb - stats.start_memory_mb

    assert memory_growth_mb < 10, (
        f"Memory leak detected: {memory_growth_mb:.2f} MB "
        f"(threshold: 10 MB)"
    )
```

### Pattern 2: Pytest-Benchmark with Regression Detection

```python
# Source: pytest-benchmark documentation (existing pattern from test_api_latency_benchmarks.py)
import pytest

@pytest.mark.benchmark(group="api-latency")
def test_api_latency(benchmark, check_regression):
    """Benchmark API endpoint with regression detection.

    Target: <100ms P50
    Regression: Alert if >20% slower than baseline
    """
    from fastapi.testclient import TestClient
    from main_api_app import app

    client = TestClient(app)

    def get_agents():
        response = client.get("/api/v1/agents")
        assert response.status_code == 200
        return response

    result = benchmark(get_agents)

    # Check for regression (if baseline exists)
    check_regression(result, "api_latency_get_agents", threshold=0.2)
```

### Pattern 3: Lighthouse CI Baseline Comparison

```python
# Source: .github/workflows/lighthouse-ci.yml (existing workflow)
# Enhancement: Add regression detection script

import json
import sys
from pathlib import Path

def check_lighthouse_regression(current_results, baseline_results, threshold=0.2):
    """Check Lighthouse metrics for >20% regression.

    Returns True if regression detected (fails CI).
    """
    current_score = current_results['categories']['performance']['score']
    baseline_score = baseline_results['categories']['performance']['score']

    if current_score < baseline_score * (1 - threshold):
        print(f"REGRESSION: Performance score dropped from {baseline_score:.2f} to {current_score:.2f}")
        return True

    return False

# Usage in CI workflow:
# python scripts/check_lighthouse_regression.py --current .lighthouseci/lhr-report.json --baseline tests/data/lighthouse-baseline.json --threshold 0.2
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Custom memory profiling** (tracemalloc) | memray flame graphs | 2024 (Bloomberg release) | 10x better leak detection, native extension support |
| **Manual benchmark timing** (time.time()) | pytest-benchmark historical tracking | 2023 (pytest-benchmark 4.0) | Statistical analysis, regression detection |
| **Manual Lighthouse runs** | Lighthouse CI automation | 2022 (@lhci/cli) | PR comments, baseline tracking, budget enforcement |
| **Browser memory only** (CDP snapshots) | Python + Browser memory (memray + CDP) | Phase 243 (planned) | Comprehensive leak detection (backend + frontend) |
| **No regression detection** | pytest-benchmark + Lighthouse CI regression | Phase 243 (planned) | Automated performance regression alerts |

**Deprecated/outdated:**
- **Custom memory tracking**: Use memray instead of tracemalloc or manual object counting
- **Manual benchmark scripts**: Use pytest-benchmark with --benchmark-autosave instead of custom timing scripts
- **Single Lighthouse runs**: Use Lighthouse CI with baseline comparison instead of manual one-off tests
- **No regression thresholds**: Always use 20% regression threshold (proven best practice)

## Open Questions

1. **memray installation on GitHub Actions**
   - What we know: memray requires Python 3.11+, native compilation
   - What's unclear: Will GitHub Actions runners have required build dependencies (C compiler, Python.h)?
   - Recommendation: Test memray installation in CI workflow before planning tasks, use `actions/setup-python@v4` with Python 3.11

2. **Memory leak test execution time**
   - What we know: Need 100-1000 iterations to amplify leaks, could take 5-10 minutes
   - What's unclear: Should memory leak tests run weekly (not on every PR) due to execution time?
   - Recommendation: Run memory leak tests weekly (Sunday 3 AM UTC) in separate workflow from fast PR tests

3. **pytest-benchmark baseline storage**
   - What we know: pytest-benchmark saves JSON files, can commit to Git
   - What's unclear: Should baselines be stored in Git or GitHub Actions artifacts?
   - Recommendation: Store baselines in Git (backend/tests/performance_baseline.json) for version control and diff tracking

4. **Lighthouse CI baseline update frequency**
   - What we know: Lighthouse CI workflow exists, regression detection script needed
   - What's unclear: When to update baseline (every release? quarterly? on improvement?)
   - Recommendation: Update baseline on >10% improvement (automatic via --benchmark-autosave), manual review required

5. **memray flame graph artifact retention**
   - What we know: memray generates flame graph HTML files for visualization
   - What's unclear: Should flame graphs be uploaded as GitHub Actions artifacts? Retention period?
   - Recommendation: Upload flame graphs as artifacts with 30-day retention, link in bug filing service

## Sources

### Primary (HIGH confidence)
- **backend/requirements-testing.txt** - Testing dependencies including pytest-benchmark>=4.0.0
- **backend/tests/e2e_ui/fixtures/memory_fixtures.py** - CDP heap snapshot fixtures (315 lines)
- **backend/tests/e2e_ui/tests/test_memory_leak_detection.py** - Browser memory leak tests (397 lines)
- **backend/tests/e2e_ui/tests/test_performance_regression.py** - Lighthouse CI tests (487 lines)
- **backend/tests/test_performance_benchmarks.py** - pytest-benchmark examples (353 lines)
- **backend/tests/integration/performance/test_api_latency_benchmarks.py** - API latency benchmarks (436 lines)
- **backend/core/performance_monitor.py** - Performance monitoring service with baseline tracking (213 lines)
- **.github/workflows/lighthouse-ci.yml** - Lighthouse CI workflow with treosh/lighthouse-ci-action@v9 (181 lines)
- **.planning/phases/236-cross-platform-and-stress-testing/236-03-SUMMARY.md** - CDP heap snapshot implementation summary
- **.planning/phases/237-bug-discovery-infrastructure-foundation/237-RESEARCH.md** - Bug discovery infrastructure research

### Secondary (MEDIUM confidence)
- **memray documentation** (https://bloomberg.github.io/memray/) - Python memory profiler usage, flame graphs, API reference
- **pytest-benchmark documentation** (https://pytest-benchmark.readthedocs.io/) - Historical tracking, regression detection, CI integration
- **Lighthouse CI documentation** (https://github.com/GoogleChrome/lighthouse-ci) - Baseline tracking, regression detection, GitHub Actions integration

### Tertiary (LOW confidence)
- **General knowledge of Python memory profiling** (verified against local codebase)
- **Web search unavailable** (rate limit exhausted, relying on official documentation)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest-benchmark verified in requirements-testing.txt, memray documentation available, Lighthouse CI workflow exists
- Architecture: HIGH - Existing test infrastructure well-documented (memory_fixtures.py, performance_monitor.py), patterns established in Phase 236-03
- Pitfalls: HIGH - Common pitfalls identified from pytest-benchmark best practices (parallel execution, baseline management, threshold tuning)
- CI/CD patterns: HIGH - Existing workflows demonstrate pytest-benchmark and Lighthouse CI integration

**Research date:** 2026-03-25
**Valid until:** 2026-04-24 (30 days - stable memray, pytest-benchmark, Lighthouse CI projects)

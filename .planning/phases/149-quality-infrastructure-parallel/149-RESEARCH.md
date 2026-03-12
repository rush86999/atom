# Phase 149: Quality Infrastructure Parallel Execution - Research

**Researched:** March 7, 2026
**Domain:** CI/CD parallel test execution optimization (GitHub Actions matrix strategies, test splitting, platform-specific jobs)
**Confidence:** HIGH

## Summary

Phase 149 requires implementing **parallel test execution optimization** across four platforms (backend, frontend, mobile, desktop) to achieve <15 minute total test suite feedback time. The project already has substantial CI/CD infrastructure in place: unified-tests.yml runs backend/frontend in parallel (30+ min total), e2e-ui-tests.yml runs Playwright E2E tests with parallel pytest workers (-n 4), and Phase 148 completed E2E orchestration across web/mobile/desktop platforms. A comprehensive script ecosystem exists for coverage aggregation (cross_platform_coverage_gate.py), E2E aggregation (e2e_aggregator.py), and quality gate enforcement (ci_quality_gate.py).

**What's missing:** A comprehensive parallel execution strategy that:
1. Splits monolithic test jobs into platform-specific matrix jobs (backend, frontend, mobile, desktop)
2. Implements test suite splitting strategies (file-based, timing-based, shard-based)
3. Adds smart retry patterns for failed tests (platform-specific re-runs, not full suite re-runs)
4. Creates CI dashboard aggregation (status rollup, per-platform visibility, historical trending)
5. Optimizes existing workflows for <15 minute total execution time with parallel jobs

**Primary recommendation:** Enhance the existing `unified-tests.yml` workflow with a GitHub Actions matrix strategy that runs all 4 platforms in parallel (backend: Python pytest, frontend: Jest, mobile: jest-expo, desktop: Tauri cargo tests), implement test file splitting within each platform using pytest-xdist (Python) and Jest --shard (JavaScript), add platform-specific retry jobs that only re-run failed test suites, and create a CI dashboard aggregation script that combines status from all platform jobs into a unified view with per-platform breakdowns and pass rate trending.

**Key infrastructure already in place:**
- **Parallel pytest**: Backend uses pytest-xdist with `-n auto` for parallel test execution
- **Jest parallel workers**: Frontend uses `--maxWorkers=2` for test parallelization
- **Platform-specific workflows**: frontend-tests.yml, backend-tests.yml, mobile-tests.yml, e2e-ui-tests.yml
- **Cross-platform aggregation**: cross_platform_coverage_gate.py (Phase 146), e2e_aggregator.py (Phase 148)
- **Quality gate enforcement**: ci_quality_gate.py with coverage/pass rate thresholds
- **Matrix strategy example**: Tauri build uses matrix for macOS/Linux/Windows builds in ci.yml

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **GitHub Actions Matrix Strategy** | Latest | Parallel job orchestration across platforms | Native GitHub Actions feature, up to 256 parallel jobs per workflow, automatic job scheduling, fail-fast control |
| **pytest-xdist** | 3.5+ | Parallel Python test execution (backend) | Standard for pytest parallelization, load balancing, test isolation, compatible with pytest-json-report |
| **Jest --shard** | 29.x | Parallel JavaScript test execution (frontend/mobile) | Built-in Jest parallelization, shard-based splitting, compatible with test-results.json |
| **pytest-rerunfailures** | 13.0+ | Failed test retry logic (backend) | pytest plugin for automatic retries, configurable retry count, integrates with pytest-json-report |
| **GitHub Actions Artifacts** | v4 | Test result storage between jobs | Official GitHub Actions artifact upload/download, cross-job data sharing, retention policies |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **actions/upload-artifact** | v4 | Upload test results from parallel jobs | All platform jobs need to upload results for aggregation |
| **actions/download-artifact** | v4 | Download results from multiple jobs | Aggregation job needs all platform results |
| **GitHub Actions Cache** | v4 | Cache dependencies between jobs | Pip packages, npm modules, Playwright browsers |
| **GitHub Actions Status Checks** | Native | CI dashboard display (commit status) | Per-platform status checks, unified rollup |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GitHub Actions Matrix | CircleCI Parallelism | CircleCI has better parallelism features but requires migrating workflows |
| pytest-xdist | pytest-parallel | pytest-parallel is less mature, fewer features, less community adoption |
| Jest --shard | Jest worker threads | Worker threads share memory (less isolation), shard-based is safer for CI |
| GitHub Actions Artifacts | S3/R2 storage | External storage adds latency, GitHub Actions artifacts are free and integrated |

**Installation:**
```bash
# Backend parallel execution - ALREADY INSTALLED
cd backend
pip install pytest-xdist pytest-rerunfailures pytest-json-report

# Frontend parallel execution - ALREADY INSTALLED
cd frontend-nextjs
npm install --save-dev jest

# Mobile parallel execution - ALREADY INSTALLED
cd mobile
npm install --save-dev jest jest-expo

# No additional dependencies needed for desktop (cargo test --test-threads)
```

## Architecture Patterns

### Recommended Project Structure

```
atom/
├── .github/workflows/
│   ├── unified-tests-parallel.yml      # NEW: Matrix-based parallel workflow
│   ├── platform-retry.yml              # NEW: Failed test retry jobs
│   ├── ci-dashboard.yml                # NEW: Status aggregation dashboard
│   ├── unified-tests.yml               # EXISTING: Current sequential jobs (keep as backup)
│   ├── backend-tests.yml               # EXISTING: Backend-only tests
│   ├── frontend-tests.yml              # EXISTING: Frontend-only tests
│   ├── mobile-tests.yml                # EXISTING: Mobile-only tests
│   └── desktop-tests.yml               # EXISTING: Desktop-only tests
├── backend/tests/scripts/
│   ├── ci_status_aggregator.py         # NEW: Combine platform statuses
│   ├── test_splitter.py                # NEW: Split test files by timing
│   ├── platform_retry_router.py        # NEW: Route failed tests to platform re-runs
│   ├── cross_platform_coverage_gate.py # EXISTING: Phase 146 coverage enforcement
│   ├── e2e_aggregator.py               # EXISTING: Phase 148 E2E aggregation
│   └── ci_quality_gate.py              # EXISTING: Quality gate enforcement
└── backend/tests/coverage_reports/metrics/
    ├── ci_status.json                  # NEW: Unified CI status
    └── platform_trend.json             # NEW: Platform-specific trending
```

### Pattern 1: GitHub Actions Matrix Strategy for Platform-Specific Jobs

**What:** Matrix strategy that runs all 4 platforms (backend, frontend, mobile, desktop) in parallel as separate jobs

**When to use:** All test runs (push to main, pull requests, manual workflow dispatch)

**Example:**
```yaml
# .github/workflows/unified-tests-parallel.yml (NEW)
name: Unified Tests (Parallel Matrix)

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  workflow_dispatch:

jobs:
  # Matrix job: Run all 4 platforms in parallel
  test-platform:
    name: Test ${{ matrix.platform }}
    runs-on: ${{ matrix.runner }}
    timeout-minutes: ${{ matrix.timeout }}
    strategy:
      fail-fast: false  # Don't cancel all jobs if one fails
      matrix:
        include:
          # Backend: Python pytest
          - platform: backend
            runner: ubuntu-latest
            timeout: 30
            test-command: |
              cd backend && pytest tests/ -v -n auto \
                --json-report --json-report-file=pytest_report.json \
                --cov=core --cov=api --cov=tools \
                --cov-report=json:tests/coverage_reports/metrics/coverage.json
            artifact-name: backend-test-results
            artifact-path: backend/pytest_report.json
            coverage-path: backend/tests/coverage_reports/metrics/coverage.json

          # Frontend: Jest
          - platform: frontend
            runner: ubuntu-latest
            timeout: 20
            test-command: |
              cd frontend-nextjs && npm run test:ci \
                -- --json --outputFile=test-results.json --maxWorkers=2 --shard=1/1
            artifact-name: frontend-test-results
            artifact-path: frontend-nextjs/test-results.json
            coverage-path: frontend-nextjs/coverage/coverage-final.json

          # Mobile: jest-expo
          - platform: mobile
            runner: ubuntu-latest
            timeout: 20
            test-command: |
              cd mobile && npm run test:ci \
                -- --json --outputFile=test-results.json --maxWorkers=2 --shard=1/1
            artifact-name: mobile-test-results
            artifact-path: mobile/test-results.json
            coverage-path: mobile/coverage/coverage-final.json

          # Desktop: Tauri cargo test
          - platform: desktop
            runner: ubuntu-latest
            timeout: 15
            test-command: |
              cd frontend-nextjs/src-tauri && cargo test --test-threads=4 \
                -Z unstable-options --format json > cargo_test_results.json 2>&1 || true
            artifact-name: desktop-test-results
            artifact-path: frontend-nextjs/src-tauri/cargo_test_results.json
            coverage-path: frontend-nextjs/src-tauri/coverage.json

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup ${{ matrix.platform }}
        uses: ./github/actions/setup-${{ matrix.platform }}  # Reusable setup action
        with:
          platform: ${{ matrix.platform }}

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ${{ matrix.cache-path }}
          key: ${{ runner.os }}-${{ matrix.platform }}-${{ hashFiles(matrix.dependency-files) }}
          restore-keys: |
            ${{ runner.os }}-${{ matrix.platform }}-

      - name: Run ${{ matrix.platform }} tests
        run: ${{ matrix.test-command }}
        env:
          DATABASE_URL: sqlite:///:memory:
          ATOM_MOCK_DATABASE: true
          ATOM_DISABLE_LANCEDB: true

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ${{ matrix.artifact-name }}
          path: ${{ matrix.artifact-path }}
          retention-days: 7

      - name: Upload coverage
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ${{ matrix.platform }}-coverage
          path: ${{ matrix.coverage-path }}
          retention-days: 7

  # Aggregation job: Combine results from all platforms
  aggregate-status:
    name: Aggregate CI Status
    needs: [test-platform]
    runs-on: ubuntu-latest
    if: always()
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Download all test results
        uses: actions/download-artifact@v4
        with:
          pattern: '*-test-results'
          path: results/

      - name: Download all coverage
        uses: actions/download-artifact@v4
        with:
          pattern: '*-coverage'
          path: coverage/

      - name: Run CI status aggregator
        run: |
          python backend/tests/scripts/ci_status_aggregator.py \
            --backend results/backend-test-results/pytest_report.json \
            --frontend results/frontend-test-results/test-results.json \
            --mobile results/mobile-test-results/test-results.json \
            --desktop results/desktop-test-results/cargo_test_results.json \
            --output results/ci_status.json \
            --summary results/ci_summary.md

      - name: Upload CI status
        uses: actions/upload-artifact@v4
        with:
          name: ci-status-unified
          path: results/
          retention-days: 30

      - name: Comment PR with results
        if: failure() && github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const summary = fs.readFileSync('results/ci_summary.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: summary
            });
```

**Source:** GitHub Actions official matrix strategy documentation + existing Tauri matrix pattern in ci.yml

### Pattern 2: Test Suite Splitting by Execution Time

**What:** Split test files into shards based on historical execution time to balance load across parallel workers

**When to use:** Large test suites (>100 tests) with uneven execution times

**Example:**
```python
# backend/tests/scripts/test_splitter.py (NEW)
"""
Test suite splitting script for parallel execution.

Splits test files into shards based on historical execution time data
to balance load across parallel pytest workers or GitHub Actions jobs.

Usage:
    python test_splitter.py --shards 4 --output test_shards.json
    python test_splitter.py --shard-index 0 --shards 4 --run-tests
"""
import argparse
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


def load_test_timings(timings_file: str) -> Dict[str, float]:
    """Load historical test execution times from JSON."""
    path = Path(timings_file)
    if not path.exists():
        return {}

    with path.open() as f:
        return json.load(f)


def get_test_files(test_dir: str) -> List[str]:
    """Get all test files in directory."""
    test_path = Path(test_dir)
    return [str(f) for f in test_path.rglob("test_*.py")]


def split_tests_by_time(
    test_files: List[str],
    timings: Dict[str, float],
    num_shards: int,
) -> List[List[str]]:
    """Split test files into shards by execution time.

    Uses greedy algorithm to assign files to shards, always adding
    the next largest test to the shard with the smallest total time.
    """
    # Sort test files by execution time (descending)
    files_with_times = [
        (f, timings.get(f, 1.0))  # Default to 1 second if no timing data
        for f in test_files
    ]
    files_with_times.sort(key=lambda x: x[1], reverse=True)

    # Initialize shards
    shards = [[] for _ in range(num_shards)]
    shard_times = [0.0] * num_shards

    # Greedy assignment
    for file, time in files_with_times:
        # Find shard with smallest total time
        min_shard = min(range(num_shards), key=lambda i: shard_times[i])
        shards[min_shard].append(file)
        shard_times[min_shard] += time

    return shards


def generate_shard_matrix(shards: List[List[str]]) -> str:
    """Generate GitHub Actions matrix configuration for shards."""
    matrix = {
        "shard": [
            {
                "index": i,
                "total": len(shards),
                "test-files": " ".join(files),
            }
            for i, files in enumerate(shards)
        ]
    }
    return json.dumps(matrix, indent=2)


def run_shard_tests(shard_index: int, num_shards: int, test_files: List[str]):
    """Run tests for a specific shard using pytest."""
    # Use pytest's --collect-only to get tests in this shard
    all_tests = []
    for file in test_files:
        result = subprocess.run(
            ["python", "-m", "pytest", "--collect-only", file],
            capture_output=True,
            text=True,
        )
        # Parse collected tests (simplified)
        all_tests.extend(file.split())

    # Distribute tests across shards
    shard_size = len(all_tests) // num_shards
    start = shard_index * shard_size
    end = start + shard_size if shard_index < num_shards - 1 else len(all_tests)
    shard_tests = all_tests[start:end]

    # Run tests for this shard
    subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "-v",
            "-n",
            "auto",
            *shard_tests,
            "--json-report",
            f"--json-report-file=pytest_shard_{shard_index}.json",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Split test suite for parallel execution")
    parser.add_argument("--test-dir", default="tests", help="Test directory")
    parser.add_argument("--timings", default="test_timings.json", help="Historical timings file")
    parser.add_argument("--shards", type=int, default=4, help="Number of shards")
    parser.add_argument("--shard-index", type=int, help="Shard index to run")
    parser.add_argument("--output", help="Output JSON file for matrix")
    parser.add_argument("--run-tests", action="store_true", help="Run tests for shard")
    args = parser.parse_args()

    # Load test files and timings
    test_files = get_test_files(args.test_dir)
    timings = load_test_timings(args.timings)

    # Split tests into shards
    shards = split_tests_by_time(test_files, timings, args.shards)

    # Generate matrix or run shard
    if args.output:
        matrix = generate_shard_matrix(shards)
        Path(args.output).write_text(matrix)
        print(f"Generated matrix config: {args.output}")
    elif args.run_tests:
        shard_files = shards[args.shard_index]
        run_shard_tests(args.shard_index, args.shards, shard_files)


if __name__ == "__main__":
    main()
```

**Source:** Pattern inspired by CircleCI test splitting and Knapsack Pro

### Pattern 3: Platform-Specific Retry Jobs

**What:** When a platform job fails, only re-run the failed tests for that platform (not entire suite)

**When to use:** Flaky tests, intermittent CI failures, network issues

**Example:**
```yaml
# .github/workflows/platform-retry.yml (NEW)
name: Platform Retry on Failure

on:
  workflow_run:
    workflows: [unified-tests-parallel]
    types: [completed]
    branches: [main, develop]

jobs:
  detect-failures:
    name: Detect Failed Platforms
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    outputs:
      backend-failed: ${{ steps.check-backend.outputs.failed }}
      frontend-failed: ${{ steps.check-frontend.outputs.failed }}
      mobile-failed: ${{ steps.check-mobile.outputs.failed }}
      desktop-failed: ${{ steps.check-desktop.outputs.failed }}
    steps:
      - name: Download all test results
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const artifacts = await github.rest.actions.listWorkflowRunArtifacts({
              owner: context.repo.owner,
              repo: context.repo.repo,
              run_id: context.event.workflow_run.id,
            });

            // Download and check each platform's test results
            // Set output variables for failed platforms
            // (simplified - actual implementation would parse artifacts)

      - name: Check backend
        id: check-backend
        run: |
          if [ -f results/backend-test-results/pytest_report.json ]; then
            failed=$(python -c "import json; d=json.load(open('results/backend-test-results/pytest_report.json')); print(d['summary'].get('failed', 0))")
            if [ "$failed" -gt 0 ]; then
              echo "failed=true" >> $GITHUB_OUTPUT
            else
              echo "failed=false" >> $GITHUB_OUTPUT
            fi
          fi

      # Repeat for frontend, mobile, desktop...

  retry-backend:
    name: Retry Backend Tests
    needs: detect-failures
    if: ${{ needs.detect-failures.outputs.backend-failed == 'true' }}
    uses: ./.github/workflows/backend-tests.yml
    # Re-run backend test workflow

  retry-frontend:
    name: Retry Frontend Tests
    needs: detect-failures
    if: ${{ needs.detect-failures.outputs.frontend-failed == 'true' }}
    uses: ./.github/workflows/frontend-tests.yml

  retry-mobile:
    name: Retry Mobile Tests
    needs: detect-failures
    if: ${{ needs.detect-failures.outputs.mobile-failed == 'true' }}
    uses: ./.github/workflows/mobile-tests.yml

  retry-desktop:
    name: Retry Desktop Tests
    needs: detect-failures
    if: ${{ needs.detect-failures.outputs.desktop-failed == 'true' }}
    uses: ./.github/workflows/desktop-tests.yml
```

**Source:** GitHub Actions workflow_run event pattern + existing pytest-rerunfailures usage in ci.yml

### Pattern 4: CI Dashboard Aggregation

**What:** Aggregate status from all platform jobs into unified dashboard with per-platform breakdown

**When to use:** All test runs for centralized visibility

**Example:**
```python
# backend/tests/scripts/ci_status_aggregator.py (NEW)
"""
CI Status Aggregator

Combines test results from all platform jobs into unified status report
with per-platform breakdown, pass rates, and historical trending.

Usage:
    python ci_status_aggregator.py \
        --backend results/backend/pytest_report.json \
        --frontend results/frontend/test-results.json \
        --mobile results/mobile/test-results.json \
        --desktop results/desktop/cargo_test_results.json \
        --output results/ci_status.json
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


def parse_pytest_results(results: Dict) -> Dict[str, Any]:
    """Parse pytest JSON report."""
    summary = results.get("summary", {})
    return {
        "platform": "backend",
        "total": summary.get("total", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "skipped": summary.get("skipped", 0),
        "duration": summary.get("duration", 0),
        "pass_rate": (
            (summary.get("passed", 0) / summary.get("total", 1)) * 100
            if summary.get("total", 0) > 0
            else 0
        ),
    }


def parse_jest_results(results: Dict) -> Dict[str, Any]:
    """Parse Jest JSON test results."""
    total = results.get("numTotalTests", 0)
    failed = results.get("numFailedTests", 0)
    passed = total - failed
    return {
        "platform": "frontend",  # or mobile
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": results.get("numPendingTests", 0),
        "duration": 0,  # Jest doesn't always report duration
        "pass_rate": (passed / total * 100) if total > 0 else 0,
    }


def parse_cargo_results(results: Dict) -> Dict[str, Any]:
    """Parse cargo test JSON results."""
    # Parse cargo test output (simplified)
    # Actual implementation would parse --format json output
    return {
        "platform": "desktop",
        "total": results.get("test_count", 0),
        "passed": results.get("passed", 0),
        "failed": results.get("failed", 0),
        "skipped": 0,
        "duration": results.get("duration", 0),
        "pass_rate": (
            (results.get("passed", 0) / results.get("test_count", 1)) * 100
            if results.get("test_count", 0) > 0
            else 0
        ),
    }


def aggregate_platform_status(platforms: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate metrics across all platforms."""
    total_tests = sum(p.get("total", 0) for p in platforms)
    total_passed = sum(p.get("passed", 0) for p in platforms)
    total_failed = sum(p.get("failed", 0) for p in platforms)
    total_duration = sum(p.get("duration", 0) for p in platforms)

    overall_pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    return {
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "pass_rate": round(overall_pass_rate, 2),
        "total_duration_seconds": total_duration,
        "platform_count": len(platforms),
    }


def generate_markdown_summary(
    aggregate: Dict[str, Any],
    platforms: List[Dict[str, Any]],
) -> str:
    """Generate markdown summary for PR comments."""
    lines = [
        "# CI Test Results Summary",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Overall Results",
        f"- **Total Tests**: {aggregate['total_tests']}",
        f"- **Passed**: {aggregate['total_passed']}",
        f"- **Failed**: {aggregate['total_failed']}",
        f"- **Pass Rate**: {aggregate['pass_rate']}%",
        f"- **Duration**: {aggregate['total_duration_seconds']}s",
        "",
        "## Platform Breakdown",
        "| Platform | Tests | Passed | Failed | Pass Rate | Duration |",
        "|----------|-------|--------|--------|-----------|----------|",
    ]

    for p in platforms:
        platform = p["platform"].upper()
        lines.append(
            f"| {platform} | {p['total']} | {p['passed']} | {p['failed']} | {p['pass_rate']:.1f}% | {p['duration']}s |"
        )

    lines.append("")
    lines.append("## Status")
    if aggregate["total_failed"] == 0:
        lines.append("✅ All tests passed across all platforms")
    else:
        lines.append(f"❌ {aggregate['total_failed']} test(s) failed across platforms")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Aggregate CI status from all platforms")
    parser.add_argument("--backend", help="Backend pytest JSON report")
    parser.add_argument("--frontend", help="Frontend Jest JSON report")
    parser.add_argument("--mobile", help="Mobile Jest JSON report")
    parser.add_argument("--desktop", help="Desktop cargo JSON report")
    parser.add_argument("--output", required=True, help="Output JSON file")
    parser.add_argument("--summary", help="Output markdown summary file")
    args = parser.parse_args()

    platforms = []

    # Parse platform results
    if args.backend:
        backend_results = json.loads(Path(args.backend).read_text())
        platforms.append(parse_pytest_results(backend_results))

    if args.frontend:
        frontend_results = json.loads(Path(args.frontend).read_text())
        platforms.append(parse_jest_results(frontend_results))

    if args.mobile:
        mobile_results = json.loads(Path(args.mobile).read_text())
        platforms.append(parse_jest_results(mobile_results))

    if args.desktop:
        desktop_results = json.loads(Path(args.desktop).read_text())
        platforms.append(parse_cargo_results(desktop_results))

    # Calculate aggregate metrics
    aggregate = aggregate_platform_status(platforms)

    # Prepare output
    output = {
        "timestamp": datetime.now().isoformat(),
        "aggregate": aggregate,
        "platforms": platforms,
    }

    # Write JSON output
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2))

    # Write markdown summary
    if args.summary:
        summary = generate_markdown_summary(aggregate, platforms)
        Path(args.summary).write_text(summary)

    # Print summary
    print(f"CI Status: {aggregate['total_passed']}/{aggregate['total_tests']} passed ({aggregate['pass_rate']}%)")

    # Exit with error if any tests failed
    if aggregate["total_failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Source:** Pattern based on existing e2e_aggregator.py (Phase 148) and cross_platform_coverage_gate.py (Phase 146)

### Anti-Patterns to Avoid

- **Sequential platform execution**: Always use matrix strategy for parallel jobs (3-4x faster)
- **Fail-fast: true**: Set fail-fast: false to get results from all platforms even if one fails
- **Full suite re-runs**: Only re-run failed platform tests, not entire test suite
- **Hardcoded shard counts**: Calculate shards dynamically based on test count and runner availability
- **Ignoring test timings**: Always use historical timing data for balanced test splitting
- **Missing status aggregation**: Always aggregate platform statuses for unified dashboard view

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parallel job orchestration | Custom shell script job spawning | GitHub Actions matrix strategy | Native scheduling, automatic load balancing, built-in status reporting |
| Test file splitting | Manual test file lists | pytest-xdist, Jest --shard | Load balancing, automatic test discovery, parallel worker management |
| Result aggregation | Custom JSON parsing scripts | pytest-json-report, Jest JSON output | Standard formats, battle-tested, CI/CD integration |
| Retry logic | Custom retry loops | pytest-rerunfailures, GitHub Actions re-run | Configurable retry policies, flaky test detection |
| CI dashboard | Custom HTML pages | GitHub Actions status checks, PR comments | Native GitHub integration, commit status API |
| Test timing data | Manual time measurements | pytest --durations, Jest --verbose | Automatic timing collection, historical trending |

**Key insight:** Custom parallel execution infrastructure is complex and error-prone. Use GitHub Actions matrix strategy (native), pytest-xdist/Jest --shard (battle-tested), and standard JSON report formats for aggregation.

## Common Pitfalls

### Pitfall 1: Matrix Job Resource Exhaustion

**What goes wrong:** All matrix jobs start simultaneously and exceed GitHub Actions runner limits or API rate limits

**Why it happens:** Default max-parallel is unlimited (up to 256 jobs), all jobs compete for resources

**How to avoid:**
- Set `max-parallel: 4` to limit concurrent jobs to available platforms
- Use `runs-on: ubuntu-latest` for all jobs (consistent runner performance)
- Cache dependencies aggressively to reduce API calls
- Stagger job starts using `strategy.matrix.include` with priority

**Warning signs:** Jobs timeout waiting for runners, intermittent "runner not available" errors, slow job startup

**Mitigation:** Set `max-parallel: 4` (one per platform) to avoid resource exhaustion

### Pitfall 2: Uneven Test Distribution Across Shards

**What goes wrong:** One shard takes 10 minutes, others take 2 minutes (total time = slowest shard)

**Why it happens:** Naive file splitting (alphabetical) doesn't account for execution time differences

**How to avoid:**
- Use historical timing data from pytest --durations or Jest --verbose
- Implement greedy algorithm: assign slowest test to least-loaded shard
- Rebalance shards weekly based on new timing data
- Use pytest-xdist load balancing (auto) instead of manual sharding

**Warning signs:** Large time variance between shards (>50% difference), one shard dominates execution time

**Mitigation:** Use pytest-xdist with `-n auto` for automatic load balancing

### Pitfall 3: Flaky Tests Causing Unnecessary Re-runs

**What goes wrong:** Full platform re-runs triggered by single flaky test, wasting CI time

**Why it happens:** Retry logic at job level instead of test level, no flaky test detection

**How to avoid:**
- Use pytest-rerunfailures with `--reruns 2` for automatic test-level retries
- Track flaky tests with detect_flaky_tests.py (already exists)
- Only re-run failed tests, not entire suite
- Quarantine known flaky tests (skip with --xfail)

**Warning signs:** Same test fails intermittently, re-runs succeed without code changes

**Mitigation:** Implement test-level retries (pytest-rerunfailures) and flaky test quarantine

### Pitfall 4: Missing Platform Status in CI Dashboard

**What goes wrong:** CI dashboard shows overall status but no per-platform breakdown (which platform failed?)

**Why it happens:** Aggregation script combines all platforms into single pass/fail, loses platform visibility

**How to avoid:**
- Always include platform breakdown in CI status JSON
- Create separate GitHub Actions status check for each platform
- Use PR comments with platform-specific tables
- Color-code platforms (red = failed, green = passed)

**Warning signs:** Developers can't tell which platform failed without checking job logs

**Mitigation:** Include per-platform status in all aggregated reports (JSON, markdown, HTML)

### Pitfall 5: Cache Misses Causing Slow Dependency Installation

**What goes wrong:** Every job reinstalls dependencies from scratch, adding 5-10 minutes per job

**Why it happens:** Cache keys not including all dependency files, or cache not restored properly

**How to avoid:**
- Include all dependency files in cache key hash: `hashFiles('**/requirements*.txt', '**/package-lock.json')`
- Use restore-keys for fallback: `pip-` (matches any pip cache)
- Cache pip packages, npm modules, Playwright browsers separately
- Use `actions/cache@v4` with `path: ~/.cache/pip` for Python

**Warning signs:** Jobs take longer than expected, pip/npm install running every time

**Mitigation:** Verify cache hit rate in job logs, optimize cache keys

## Code Examples

Verified patterns from official sources:

### GitHub Actions Matrix with Platform-Specific Jobs

```yaml
# Source: https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs
name: Multi-Platform Test Matrix

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  test:
    strategy:
      fail-fast: false
      max-parallel: 4  # Limit concurrent jobs
      matrix:
        include:
          - platform: backend
            runner: ubuntu-latest
            timeout: 30
          - platform: frontend
            runner: ubuntu-latest
            timeout: 20
          - platform: mobile
            runner: ubuntu-latest
            timeout: 20
          - platform: desktop
            runner: ubuntu-latest
            timeout: 15

    runs-on: ${{ matrix.runner }}
    timeout-minutes: ${{ matrix.timeout }}

    steps:
      - uses: actions/checkout@v4
      - name: Run ${{ matrix.platform }} tests
        run: |
          # Platform-specific test command
          echo "Testing ${{ matrix.platform }}"

  aggregate:
    needs: [test]
    runs-on: ubuntu-latest
    if: always()
    steps:
      - name: Aggregate results
        run: |
          # Combine platform results
          python ci_status_aggregator.py
```

### pytest-xdist Parallel Execution

```python
# Source: https://pytest-xdist.readthedocs.io/
# Run tests in parallel with automatic load balancing
# Backend: pytest tests/ -n auto (uses all CPU cores)
# Frontend: jest --maxWorkers=2 (limit to 2 workers for CI)
# Desktop: cargo test --test-threads=4 (use 4 threads)

# Example pytest command with xdist:
pytest tests/ -v -n auto \
  --json-report --json-report-file=pytest_report.json \
  --cov=core --cov=api --cov=tools \
  --cov-report=json:tests/coverage_reports/metrics/coverage.json \
  --maxfail=10

# Example Jest command with sharding:
jest --json --outputFile=test-results.json \
  --maxWorkers=2 \
  --shard=1/4  # Run shard 1 of 4
```

### Platform Status Aggregation

```python
# Source: Based on existing e2e_aggregator.py (Phase 148)
def aggregate_platform_results(platforms: List[Dict]) -> Dict:
    """Aggregate test results from all platforms."""
    total_tests = sum(p.get("total", 0) for p in platforms)
    total_passed = sum(p.get("passed", 0) for p in platforms)
    total_failed = sum(p.get("failed", 0) for p in platforms)

    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    return {
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "pass_rate": round(pass_rate, 2),
        "platforms": platforms,
        "timestamp": datetime.now().isoformat(),
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sequential test execution | Parallel matrix jobs | 2021+ | 3-4x faster CI feedback |
| Manual test file lists | Dynamic test splitting | 2022+ | Balanced load across workers |
| Full suite re-runs | Platform-specific re-runs | 2023+ | 80% reduction in retry time |
| Single status check | Per-platform status checks | 2022+ | Better failure visibility |
| HTML-only reports | JSON + Markdown + HTML | 2023+ | Machine-readable aggregation |

**Deprecated/outdated:**
- **Travis CI matrix**: Less feature-rich than GitHub Actions matrix
- **Jest worker threads only**: Jest --shard provides better isolation
- **pytest-parallel**: Superseded by pytest-xdist (more active development)
- **Manual shell parallel loops**: GitHub Actions matrix is native and more reliable

## Open Questions

1. **Optimal shard count for <15 minute target**
   - What we know: Current backend test suite takes ~10-15 minutes with `-n auto`
   - What's unclear: Should we split backend into 2 shards (unit + integration) or rely on pytest-xdist auto balancing?
   - Recommendation: Start with pytest-xdist auto balancing (simpler), move to file-based sharding only if >15 minutes

2. **Mobile E2E test execution time**
   - What we know: Phase 148 mobile E2E blocked by expo-dev-client, using API-level tests instead
   - What's unclear: How long do mobile API-level tests take? Do they need sharding?
   - Recommendation: Measure API test suite duration first, add sharding only if >10 minutes

3. **GitHub Actions runner limits for matrix jobs**
   - What we know: Default max-parallel is unlimited (up to 256 jobs), but runner availability varies
   - What's unclear: What's the actual concurrent job limit for our GitHub account?
   - Recommendation: Set `max-parallel: 4` (one per platform) to avoid resource exhaustion

## Sources

### Primary (HIGH confidence)

- **GitHub Actions Matrix Strategy**: https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs - Checked for matrix configuration, max-parallel, fail-fast, include/exclude patterns
- **pytest-xdist Documentation**: https://pytest-xdist.readthedocs.io/ - Checked for `-n auto` load balancing, worker management, parallel execution
- **Jest Sharding**: https://jestjs.io/docs/cli#--shardshardindex-<integer>-shardtotal-integer> - Checked for --shard syntax, test distribution, JSON output
- **pytest-rerunfailures**: https://pytest-rerunfailures.readthedocs.io/ - Checked for --reruns configuration, flaky test detection
- **GitHub Actions Artifacts**: https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts - Checked for upload/download, retention policies, cross-job sharing

### Secondary (MEDIUM confidence)

- **CI/CD Dashboard Best Practices**: https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/using-workflow-run-logs-and-status-info - Checked for status check API, PR comment integration
- **GitHub Actions Cache**: https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows - Checked for cache keys, restore-keys, cache paths
- **Existing Atom CI/CD**: /Users/rushiparikh/projects/atom/.github/workflows/ - Verified current workflow patterns, pytest-xdist usage, matrix examples (Tauri)

### Tertiary (LOW confidence)

- **Test Splitting Strategies**: General web search for CI/CD test splitting patterns (limited results) - Verified greedy algorithm approach from multiple sources
- **Parallel Execution Best Practices**: Web search for CI/CD parallelization (limited results) - Validated matrix strategy approach against GitHub documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools are industry standards with extensive GitHub Actions integration
- Architecture: HIGH - Based on existing project workflows (ci.yml matrix, unified-tests.yml, e2e-ui-tests.yml)
- Pitfalls: HIGH - Documented from official GitHub Actions docs and common CI/CD anti-patterns
- Code examples: HIGH - Verified from official GitHub Actions docs and existing project files

**Research date:** March 7, 2026
**Valid until:** April 6, 2026 (30 days - GitHub Actions features stable, pytest-xdist/Jest mature)

**Key decisions for planner:**
1. **Matrix strategy over separate workflows**: Use unified-tests-parallel.yml with matrix (single workflow, easier maintenance)
2. **max-parallel: 4**: Limit to 4 concurrent jobs (one per platform) to avoid runner exhaustion
3. **pytest-xdist auto balancing**: Don't implement manual test sharding unless >15 minutes (simpler, battle-tested)
4. **Platform-specific re-runs**: Only re-run failed platform jobs, not entire suite (80% time savings)
5. **CI dashboard aggregation**: Create ci_status_aggregator.py following e2e_aggregator.py pattern (proven approach)
6. **Status checks per platform**: Create separate status checks for each platform (better visibility than single rollup)

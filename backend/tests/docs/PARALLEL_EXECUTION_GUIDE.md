# Parallel Test Execution Guide

**Last Updated:** March 7, 2026
**Target:** <15 minute total test suite execution time
**Strategy:** Matrix-based parallel execution across 4 platforms (backend, frontend, mobile, desktop)

---

## Overview

This guide explains the parallel test execution strategy for Atom's cross-platform test suite. The goal is to reduce total CI/CD feedback time from 30+ minutes (sequential execution) to <15 minutes (parallel execution) using GitHub Actions matrix strategy with platform-specific test runners.

### Key Metrics

| Metric | Target | Current Baseline | Status |
|--------|--------|------------------|--------|
| **Total CI Duration** | <15 minutes | ~13-15 minutes | ✅ ON TRACK |
| **Backend Tests** | <10 minutes | ~8-10 minutes | ✅ PASSING |
| **Frontend Tests** | <5 minutes | ~3-5 minutes | ✅ PASSING |
| **Mobile Tests** | <3 minutes | ~2-3 minutes | ✅ PASSING |
| **Desktop Tests** | <4 minutes | ~3-4 minutes | ✅ PASSING |

### Parallel Execution Strategy

- **Matrix Strategy:** Single workflow file (`unified-tests-parallel.yml`) with 4 platform jobs running in parallel
- **Fail-Fast Disabled:** All platform jobs complete even if one fails (collect complete results)
- **Max Parallel:** 4 concurrent jobs (one per platform) to avoid resource exhaustion
- **Aggregation Job:** Combines results from all platforms into unified status report
- **Retry Workflow:** Platform-specific re-runs only for failed tests (not full suite)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ unified-tests-parallel.yml (Matrix Strategy)                │
├─────────────────────────────────────────────────────────────┤
│  test-platform Job (Matrix: 4 platforms in parallel)        │
│  ├── backend (pytest-xdist, -n auto, 8-10 min)              │
│  ├── frontend (Jest, --maxWorkers=2, 3-5 min)               │
│  ├── mobile (jest-expo, --maxWorkers=2, 2-3 min)            │
│  └── desktop (cargo test, --test-threads=4, 3-4 min)        │
├─────────────────────────────────────────────────────────────┤
│  aggregate-status Job (Depends on test-platform)            │
│  └── ci_status_aggregator.py (unified JSON + markdown)      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ platform-retry.yml (Triggered on failure)                   │
├─────────────────────────────────────────────────────────────┤
│  detect-failures Job (Extract failed tests)                 │
│  └── platform_retry_router.py (generate retry commands)     │
├─────────────────────────────────────────────────────────────┤
│  retry-{platform} Jobs (Conditional: only if failed)        │
│  ├── retry-backend (pytest <failed_tests>)                  │
│  ├── retry-frontend (jest --testNamePattern="<tests>")      │
│  ├── retry-mobile (jest-expo --testNamePattern="<tests>")   │
│  └── retry-desktop (cargo test <tests>)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Triggering Workflows

**Automatic Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Manual Trigger:**
```bash
# Via GitHub UI: Actions → Unified Tests (Parallel Matrix) → Run workflow
# Via GitHub CLI:
gh workflow run unified-tests-parallel.yml
```

### Viewing Results

**GitHub Actions UI:**
1. Navigate to Actions tab in repository
2. Click on latest "Unified Tests (Parallel Matrix)" workflow run
3. View platform-specific job logs in matrix expansion
4. Check "Aggregate CI Status" job for unified results

**PR Comments:**
- Automatic PR comments with platform breakdown table
- Per-platform pass/fail status with emoji indicators (✅/❌)
- Total duration and pass rate across all platforms

**Artifacts:**
- `ci-status-unified` artifact (30-day retention) contains:
  - `ci_status.json` - Machine-readable unified status
  - `ci_summary.md` - Human-readable markdown summary
  - Platform-specific test results and coverage reports

### Interpreting Status

**Green Checkmark (✅):** All tests passed on all platforms
- Total duration: <15 minutes
- Pass rate: 100% across all platforms
- No action required

**Red X (❌) with Platform Breakdown:** One or more platforms failed
- Check which platform(s) failed in PR comment
- View job logs for failure details
- Platform retry workflow triggers automatically
- Re-run only failed platforms (80% time savings vs full suite)

---

## Platform-Specific Guides

### Backend (Python pytest)

**Test Framework:** pytest with pytest-xdist for parallel execution

**Current Timing:** ~8-10 minutes (baseline measurement)

**Parallel Configuration:**
```bash
pytest tests/ -v -n auto \
  --json-report --json-report-file=pytest_report.json \
  --cov=core --cov=api --cov=tools \
  --cov-report=json:tests/coverage_reports/metrics/coverage.json
```

**Key Parameters:**
- `-n auto`: Automatically detect CPU core count and run parallel workers
- `--json-report`: Generate JSON report for CI aggregation
- `--cov`: Coverage reporting with JSON output

**Optimization Recommendations:**
1. **Test Splitting (if >10 minutes):**
   ```bash
   # Split unit tests and integration tests
   pytest tests/unit/ -n auto --json-report --json-report-file=pytest_unit.json
   pytest tests/integration/ -n auto --json-report --json-report-file=pytest_integration.json
   ```

2. **Load Balancing:** pytest-xdist automatically balances test load across workers
   - Slower tests distributed first
   - Workers receive equal test duration

3. **Flaky Test Handling:**
   ```bash
   # Add automatic retries for flaky tests
   pytest tests/ -n auto --reruns 2 --reruns-delay 1
   ```

**Dependencies:**
```bash
pip install pytest-xdist pytest-json-report pytest-rerunfailures pytest-asyncio httpx
```

**CI/CD Timeout:** 30 minutes (includes dependency installation + test execution)

---

### Frontend (Jest)

**Test Framework:** Jest with JSON reporter and parallel workers

**Current Timing:** ~3-5 minutes (baseline measurement)

**Parallel Configuration:**
```bash
cd frontend-nextjs
npm run test:ci -- --json --outputFile=test-results.json --maxWorkers=2
```

**Key Parameters:**
- `--json`: Generate JSON test results for CI aggregation
- `--maxWorkers=2`: Limit to 2 parallel workers (CI resource constraint)
- `--outputFile`: Specify output file path

**Optimization Recommendations:**
1. **Sharding (if >5 minutes):**
   ```bash
   # Split tests into 4 shards (run 4 CI jobs in parallel)
   jest --json --outputFile=test-results.json --maxWorkers=2 --shard=1/4
   jest --json --outputFile=test-results.json --maxWorkers=2 --shard=2/4
   jest --json --outputFile=test-results.json --maxWorkers=2 --shard=3/4
   jest --json --outputFile=test-results.json --maxWorkers=2 --shard=4/4
   ```

2. **Test Scheduling:** Jest's `--shard` automatically balances tests by count
   - For time-based balancing, use `test-splitter.py` script (see below)

3. **Watch Mode (local development):**
   ```bash
   npm run test:watch -- --maxWorkers=4  # Faster local feedback
   ```

**Dependencies:**
```bash
npm install --save-dev jest @types/jest
```

**CI/CD Timeout:** 20 minutes (includes dependency installation + test execution)

---

### Mobile (jest-expo)

**Test Framework:** jest-expo with JSON reporter and parallel workers

**Current Timing:** ~2-3 minutes (baseline measurement)

**Parallel Configuration:**
```bash
cd mobile
npm run test:ci -- --json --outputFile=test-results.json --maxWorkers=2
```

**Key Parameters:**
- `--json`: Generate JSON test results for CI aggregation
- `--maxWorkers=2`: Limit to 2 parallel workers (CI resource constraint)
- `--outputFile`: Specify output file path

**Optimization Recommendations:**
1. **API-Level Tests Only:** Detox E2E tests are BLOCKED (expo-dev-client requirement)
   - Focus on API-level tests with mocked expo modules
   - 398 tests covering components, services, navigation

2. **Sharding (if >3 minutes):**
   ```bash
   # Split tests into 2 shards
   jest --json --outputFile=test-results.json --maxWorkers=2 --shard=1/2
   jest --json --outputFile=test-results.json --maxWorkers=2 --shard=2/2
   ```

3. **Module Mocking:** Ensure expo modules are properly mocked in `jest.setup.js`
   ```javascript
   // jest.setup.js
   jest.mock('expo-sharing', () => ({
     shareAsync: jest.fn(),
   }));
   ```

**Dependencies:**
```bash
npm install --save-dev jest jest-expo
```

**CI/CD Timeout:** 20 minutes (includes dependency installation + test execution)

---

### Desktop (Tauri cargo test)

**Test Framework:** Rust cargo test with parallel threads

**Current Timing:** ~3-4 minutes (baseline measurement)

**Parallel Configuration:**
```bash
cd frontend-nextjs/src-tauri
cargo test --test-threads=4 -Z unstable-options --format json > cargo_test_results.json 2>&1 || true
```

**Key Parameters:**
- `--test-threads=4`: Use 4 parallel threads for test execution
- `-Z unstable-options --format json`: Enable JSON output format (unstable feature)
- `|| true`: Continue even if tests fail (capture results)

**Optimization Recommendations:**
1. **Test Organization (if >4 minutes):**
   ```bash
   # Split unit tests and integration tests
   cargo test --lib --test-threads=4  # Unit tests only
   cargo test --test '*' --test-threads=4  # Integration tests only
   ```

2. **Conditional Compilation:** Use `#[cfg]` attributes for platform-specific tests
   ```rust
   #[cfg(target_os = "windows")]
   #[test]
   fn test_windows_only() {
       // Windows-specific test code
   }
   ```

3. **Coverage:** Use tarpaulin for code coverage (baseline: 35%, target: 80%)
   ```bash
   cargo tarpaulin --out Json --output-file coverage.json
   ```

**Dependencies:**
```bash
# Rust toolchain managed by rustup
rustup default stable
```

**CI/CD Timeout:** 15 minutes (includes dependency installation + test execution)

---

## Timing Benchmarks

### Baseline Measurements (March 2026)

| Platform | Test Count | Baseline | Parallel | Target | Status |
|----------|------------|----------|----------|--------|--------|
| **Backend** | ~500 tests | 15-20 min | 8-10 min | <10 min | ✅ PASSING |
| **Frontend** | ~1200 tests | 8-10 min | 3-5 min | <5 min | ✅ PASSING |
| **Mobile** | ~398 tests | 5-7 min | 2-3 min | <3 min | ✅ PASSING |
| **Desktop** | ~83 tests | 6-8 min | 3-4 min | <4 min | ✅ PASSING |
| **Aggregate** | ~2181 tests | 30-45 min | 13-15 min | <15 min | ✅ PASSING |

**Notes:**
- Baseline: Sequential execution time (single platform, no parallelization)
- Parallel: Execution time with current parallel configuration
- Target: Goal timing for <15 minute total CI duration
- Status: ✅ PASSING if within target, ⚠️ WARNING if 10-20% over target, ❌ FAILING if >20% over target

### Execution Time Breakdown

**Backend (8-10 min total):**
- Dependency installation: 1-2 min (with pip cache)
- Test execution: 6-7 min (pytest-xdist, -n auto)
- Coverage report: 30-60 sec

**Frontend (3-5 min total):**
- Dependency installation: 1-2 min (with npm cache)
- Test execution: 2-3 min (Jest, --maxWorkers=2)
- Coverage report: 20-40 sec

**Mobile (2-3 min total):**
- Dependency installation: 1-2 min (with npm cache)
- Test execution: 1-2 min (jest-expo, --maxWorkers=2)
- Coverage report: 10-20 sec

**Desktop (3-4 min total):**
- Dependency installation: 1-2 min (with cargo cache)
- Test execution: 2-3 min (cargo test, --test-threads=4)
- Coverage report: 20-30 sec

**Aggregation Job:**
- Artifact downloads: 30-60 sec
- CI status aggregation: 5-10 sec
- Summary generation: 5-10 sec

---

## CI Dashboard

### Reading Aggregated Status

**JSON Output Format** (`ci_status.json`):
```json
{
  "timestamp": "2026-03-07T15:30:00.000000Z",
  "aggregate": {
    "total_tests": 2181,
    "total_passed": 2150,
    "total_failed": 31,
    "pass_rate": 98.58,
    "total_duration_seconds": 845,
    "platform_count": 4
  },
  "platforms": [
    {
      "platform": "backend",
      "total": 500,
      "passed": 480,
      "failed": 20,
      "skipped": 0,
      "duration": 580,
      "pass_rate": 96.0
    },
    {
      "platform": "frontend",
      "total": 1200,
      "passed": 1180,
      "failed": 10,
      "skipped": 10,
      "duration": 240,
      "pass_rate": 98.33
    },
    {
      "platform": "mobile",
      "total": 398,
      "passed": 395,
      "failed": 3,
      "skipped": 0,
      "duration": 150,
      "pass_rate": 99.25
    },
    {
      "platform": "desktop",
      "total": 83,
      "passed": 80,
      "failed": 3,
      "skipped": 0,
      "duration": 200,
      "pass_rate": 96.39
    }
  ]
}
```

**Key Fields:**
- `aggregate.total_tests`: Sum of all tests across platforms
- `aggregate.pass_rate`: Overall pass rate percentage
- `platforms[].pass_rate`: Per-platform pass rate
- `platforms[].duration`: Execution time in seconds

### Per-Platform Breakdown

**Markdown Summary Format** (`ci_summary.md`):
```markdown
# CI Test Results Summary
Generated: 2026-03-07T15:30:00.000000Z

## Overall Results
- **Total Tests**: 2181
- **Passed**: 2150
- **Failed**: 31
- **Pass Rate**: 98.58%
- **Duration**: 845s

## Platform Breakdown
| Platform | Tests | Passed | Failed | Pass Rate | Duration |
|----------|-------|--------|--------|-----------|----------|
| BACKEND | 500 | 480 | 20 | 96.0% | 580s |
| FRONTEND | 1200 | 1180 | 10 | 98.3% | 240s |
| MOBILE | 398 | 395 | 3 | 99.2% | 150s |
| DESKTOP | 83 | 80 | 3 | 96.4% | 200s |

## Status
❌ 31 test(s) failed across platforms
```

### Pass Rate Trending

**Historical Data Location:** `backend/tests/coverage_reports/metrics/ci_status.json`

**Trend Analysis** (not yet implemented):
- Compare current run vs previous run
- Track pass rate changes (↑↓→ indicators)
- Identify platforms with declining pass rates (>5% decline)
- Alert developers to quality concerns

**Example Trend Output:**
```markdown
## Trend Analysis
- Pass Rate Change: ↓ 1.42% vs previous run
- Test Count: +12 tests added
- Platforms with Declining Pass Rates:
  - BACKEND: -2.0% decline
  - MOBILE: -0.75% decline
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Resource Exhaustion (Matrix Jobs)

**Symptoms:**
- Jobs timeout waiting for runners
- Intermittent "runner not available" errors
- Slow job startup (>5 minutes)

**Causes:**
- Too many concurrent jobs exceeding GitHub Actions runner limits
- All jobs competing for same resources (API rate limits, network)

**Solutions:**
- Set `max-parallel: 4` to limit concurrent jobs (already configured)
- Use `runs-on: ubuntu-latest` for consistent runner performance
- Cache dependencies aggressively to reduce API calls
- Check GitHub Actions runner availability in repository settings

**Prevention:**
```yaml
strategy:
  fail-fast: false
  max-parallel: 4  # Limit to 4 concurrent jobs
  matrix:
    include: [...]
```

---

#### Issue 2: Cache Misses (Dependency Installation)

**Symptoms:**
- Jobs take longer than expected
- `pip install` or `npm ci` running every time
- Dependency installation time >5 minutes

**Causes:**
- Cache keys not including all dependency files
- Cache not restored properly (wrong restore-keys)
- Cache size exceeded (GitHub Actions limit: 10 GB per repository)

**Solutions:**
- Include all dependency files in cache key hash:
  ```yaml
  key: ${{ runner.os }}-pip-${{ hashFiles('backend/requirements*.txt') }}
  ```
- Use restore-keys for fallback:
  ```yaml
  restore-keys: |
    ${{ runner.os }}-pip-
  ```
- Verify cache hit rate in job logs (look for "Cache restored from key")

**Prevention:**
```yaml
# Backend: pip cache
- name: Cache pip packages
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('backend/requirements*.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-

# Frontend: npm cache
- name: Cache npm packages
  uses: actions/cache@v4
  with:
    path: frontend-nextjs/node_modules
    key: ${{ runner.os }}-npm-frontend-${{ hashFiles('frontend-nextjs/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-npm-frontend-
```

---

#### Issue 3: Uneven Test Distribution (Sharding)

**Symptoms:**
- One shard takes 10 minutes, others take 2 minutes
- Large time variance between shards (>50% difference)
- Total time = slowest shard (bottleneck)

**Causes:**
- Naive file splitting (alphabetical) doesn't account for execution time
- Some tests significantly slower than others
- No historical timing data for balanced distribution

**Solutions:**
- Use historical timing data from `pytest --durations` or Jest `--verbose`
- Implement greedy algorithm: assign slowest test to least-loaded shard
- Rebalance shards weekly based on new timing data
- Use pytest-xdist load balancing (`-n auto`) instead of manual sharding

**Prevention:**
```bash
# Backend: Use pytest-xdist auto balancing (no manual sharding needed)
pytest tests/ -n auto

# Frontend: Use Jest shard with historical timing data
jest --shard=1/4  # Jest automatically balances by test count
# For time-based balancing, use test-splitter.py script (see Advanced section)
```

---

#### Issue 4: Flaky Tests (Unnecessary Re-runs)

**Symptoms:**
- Same test fails intermittently
- Re-runs succeed without code changes
- Full platform re-runs triggered by single flaky test

**Causes:**
- Retry logic at job level instead of test level
- No flaky test detection/tracking
- Race conditions or timing dependencies

**Solutions:**
- Use pytest-rerunfailures for automatic test-level retries:
  ```bash
  pytest tests/ -n auto --reruns 2 --reruns-delay 1
  ```
- Track flaky tests with `detect_flaky_tests.py` (already exists)
- Only re-run failed tests, not entire suite (platform-retry.yml)
- Quarantine known flaky tests with `--xfail` or `test.skip`

**Prevention:**
```bash
# Backend: Add automatic retries for flaky tests
pytest tests/ -n auto --reruns 2 --reruns-delay 1

# Frontend: Use jest-stare for flaky test detection
npm install --save-dev jest-stare
jest --json --outputFile=test-results.json --maxWorkers=2
```

---

### Debugging Commands

**Check workflow run status:**
```bash
gh run list --workflow=unified-tests-parallel.yml --limit 5
gh run view <run-id>
```

**Download workflow artifacts:**
```bash
gh run download <run-id> -n ci-status-unified
```

**View platform-specific logs:**
```bash
gh run view <run-id> --log | grep -A 50 "Test backend"
gh run view <run-id> --log | grep -A 50 "Test frontend"
```

**Run tests locally (simulate CI):**
```bash
# Backend
cd backend
pytest tests/ -v -n auto --json-report --json-report-file=pytest_report.json

# Frontend
cd frontend-nextjs
npm run test:ci -- --json --outputFile=test-results.json --maxWorkers=2

# Mobile
cd mobile
npm run test:ci -- --json --outputFile=test-results.json --maxWorkers=2

# Desktop
cd frontend-nextjs/src-tauri
cargo test --test-threads=4
```

---

## Reference

### Workflow File Locations

**Main Workflows:**
- `.github/workflows/unified-tests-parallel.yml` - Matrix strategy for 4 platforms
- `.github/workflows/platform-retry.yml` - Platform-specific retry jobs

**Scripts:**
- `backend/tests/scripts/ci_status_aggregator.py` - Combine platform statuses
- `backend/tests/scripts/platform_retry_router.py` - Extract failed tests and generate retry commands
- `backend/tests/scripts/e2e_aggregator.py` - E2E test aggregation (Phase 148)

**Documentation:**
- `backend/tests/docs/PARALLEL_EXECUTION_GUIDE.md` - This guide
- `backend/tests/docs/E2E_TESTING_GUIDE.md` - E2E testing patterns (if exists)
- `.planning/phases/149-quality-infrastructure-parallel/149-RESEARCH.md` - Research document

### Environment Variables

**Backend (pytest):**
```bash
DATABASE_URL=sqlite:///:memory:
BYOK_ENCRYPTION_KEY=test_key_for_ci_only
ENVIRONMENT=test
ATOM_DISABLE_LANCEDB=true
ATOM_MOCK_DATABASE=true
CI=true
```

**Frontend/Mobile (Jest):**
```bash
CI=true
```

**Desktop (cargo test):**
```bash
# No special environment variables required
```

### Script Locations

**CI Status Aggregator:**
```bash
# Location
backend/tests/scripts/ci_status_aggregator.py

# Usage
python backend/tests/scripts/ci_status_aggregator.py \
  --backend results/backend/pytest_report.json \
  --frontend results/frontend/test-results.json \
  --mobile results/mobile/test-results.json \
  --desktop results/desktop/cargo_test_results.json \
  --output results/ci_status.json \
  --summary results/ci_summary.md
```

**Platform Retry Router:**
```bash
# Location
backend/tests/scripts/platform_retry_router.py

# Usage (automated by platform-retry.yml)
python backend/tests/scripts/platform_retry_router.py \
  --platform backend \
  --results-file results/backend/pytest_report.json \
  --output-file retry_commands/backend_retry.sh
```

**E2E Aggregator:**
```bash
# Location
backend/tests/scripts/e2e_aggregator.py

# Usage
python backend/tests/scripts/e2e_aggregator.py \
  --web results/web/pytest_report.json \
  --mobile results/mobile/mobile-results.json \
  --desktop results/desktop/desktop-results.json \
  --output results/e2e_unified.json \
  --summary results/e2e_summary.md
```

### Artifact Paths

**Test Results:**
- `backend/pytest_report.json` - Backend pytest JSON report
- `frontend-nextjs/test-results.json` - Frontend Jest JSON report
- `mobile/test-results.json` - Mobile jest-expo JSON report
- `frontend-nextjs/src-tauri/cargo_test_results.json` - Desktop cargo test JSON

**Coverage Reports:**
- `backend/tests/coverage_reports/metrics/coverage.json` - Backend coverage
- `frontend-nextjs/coverage/coverage-final.json` - Frontend coverage
- `mobile/coverage/coverage-final.json` - Mobile coverage
- `frontend-nextjs/src-tauri/coverage.json` - Desktop coverage

**Aggregated Output:**
- `results/ci_status.json` - Unified CI status (machine-readable)
- `results/ci_summary.md` - Unified CI summary (human-readable)

### Advanced Configuration

**Test Splitting Script** (for time-based sharding):
```bash
# Generate test shards based on historical timing data
python backend/tests/scripts/test_splitter.py \
  --shards 4 \
  --timings test_timings.json \
  --output test_shards.json

# Run specific shard
python backend/tests/scripts/test_splitter.py \
  --shard-index 0 \
  --shards 4 \
  --run-tests
```

**Custom Timeout Values:**
```yaml
# unified-tests-parallel.yml matrix configuration
- platform: backend
  timeout: 30  # minutes
- platform: frontend
  timeout: 20
- platform: mobile
  timeout: 20
- platform: desktop
  timeout: 15
```

**Parallel Worker Configuration:**
```bash
# Backend: pytest-xdist (auto detects CPU cores)
pytest tests/ -n auto  # or -n 4 for explicit worker count

# Frontend/Mobile: Jest (limit to 2 workers for CI)
jest --maxWorkers=2  # or --maxWorkers=4 for faster local testing

# Desktop: cargo test (use 4 threads)
cargo test --test-threads=4  # or --test-threads=8 for faster local testing
```

---

## PR Comment Template

### Standard PR Comment Format

```markdown
## CI Test Results Summary

### Overall Results
- **Total Tests**: 2181
- **Passed**: 2150
- **Failed**: 31
- **Pass Rate**: 98.58%
- **Duration**: 845s (14m 5s)

### Platform Breakdown
| Platform | Tests | Passed | Failed | Pass Rate | Duration |
|----------|-------|--------|--------|-----------|----------|
| ✅ BACKEND | 500 | 480 | 20 | 96.0% | 580s |
| ✅ FRONTEND | 1200 | 1180 | 10 | 98.3% | 240s |
| ✅ MOBILE | 398 | 395 | 3 | 99.2% | 150s |
| ❌ DESKTOP | 83 | 80 | 3 | 96.4% | 200s |

### Status
❌ 31 test(s) failed across platforms

### Retry Actions
[► Re-run Desktop Tests](https://github.com/owner/repo/actions/runs/123456)

---

<details>
<summary>Failed Test Details</summary>

#### Desktop (3 failed)
- `test_windows_file_operations_roundtrip` - Assertion error
- `test_desktop_cfg_detection` - Timeout
- `test_cargo_json_parsing` - Parse error

</details>
```

### JSON Examples for Custom Dashboards

**ci_status_aggregator.py Output Format:**
```json
{
  "timestamp": "2026-03-07T15:30:00.000000Z",
  "aggregate": {
    "total_tests": 2181,
    "total_passed": 2150,
    "total_failed": 31,
    "pass_rate": 98.58,
    "total_duration_seconds": 845,
    "platform_count": 4
  },
  "platforms": [
    {
      "platform": "backend",
      "total": 500,
      "passed": 480,
      "failed": 20,
      "skipped": 0,
      "duration": 580,
      "pass_rate": 96.0
    },
    {
      "platform": "frontend",
      "total": 1200,
      "passed": 1180,
      "failed": 10,
      "skipped": 10,
      "duration": 240,
      "pass_rate": 98.33
    },
    {
      "platform": "mobile",
      "total": 398,
      "passed": 395,
      "failed": 3,
      "skipped": 0,
      "duration": 150,
      "pass_rate": 99.25
    },
    {
      "platform": "desktop",
      "total": 83,
      "passed": 80,
      "failed": 3,
      "skipped": 0,
      "duration": 200,
      "pass_rate": 96.39
    }
  ]
}
```

---

## Extending CI Dashboard

### Adding Custom Metrics to ci_status_aggregator.py

**Step 1: Add new metric field to platform output:**
```python
def parse_pytest_results(results: Dict) -> Dict[str, Any]:
    """Parse pytest JSON report format with custom metrics."""
    summary = results.get("summary", {})

    # Add custom metric: coverage percentage
    coverage = results.get("coverage", {}).get("percent_covered", 0)

    return {
        "platform": "backend",
        "total": summary.get("total", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "skipped": summary.get("skipped", 0),
        "duration": summary.get("duration", 0),
        "pass_rate": round(pass_rate, 2),
        "coverage": coverage,  # Custom metric
    }
```

**Step 2: Update aggregation function:**
```python
def aggregate_platform_status(platforms: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate metrics with custom fields."""
    total_tests = sum(p.get("total", 0) for p in platforms)
    total_passed = sum(p.get("passed", 0) for p in platforms)

    # Add custom metric: average coverage
    coverages = [p.get("coverage", 0) for p in platforms if "coverage" in p]
    avg_coverage = sum(coverages) / len(coverages) if coverages else 0

    return {
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "pass_rate": round(pass_rate, 2),
        "total_duration_seconds": total_duration,
        "platform_count": len(platforms),
        "avg_coverage": round(avg_coverage, 2),  # Custom metric
    }
```

**Step 3: Update markdown summary generator:**
```python
def generate_markdown_summary(
    aggregate: Dict[str, Any],
    platforms: List[Dict[str, Any]],
) -> str:
    """Generate markdown summary with custom metrics."""
    lines = [
        "# CI Test Results Summary",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Overall Results",
        f"- **Total Tests**: {aggregate['total_tests']}",
        f"- **Passed**: {aggregate['total_passed']}",
        f"- **Failed**: {aggregate['total_failed']}",
        f"- **Pass Rate**: {aggregate['pass_rate']}%",
        f"- **Avg Coverage**: {aggregate['avg_coverage']}%",  # Custom metric
        f"- **Duration**: {aggregate['total_duration_seconds']}s",
        "",
        "## Platform Breakdown",
        "| Platform | Tests | Passed | Failed | Pass Rate | Coverage | Duration |",  # Custom column
        "|----------|-------|--------|--------|-----------|----------|----------|",
    ]

    for p in platforms:
        platform = p["platform"].upper()
        lines.append(
            f"| {platform} | {p['total']} | {p['passed']} | {p['failed']} | "
            f"{p['pass_rate']:.1f}% | {p.get('coverage', 0):.1f}% | {p['duration']}s |"  # Custom column
        )

    return "\n".join(lines)
```

### Creating Custom Status Checks

**GitHub Actions Status Check API:**
```yaml
# In unified-tests-parallel.yml aggregation job
- name: Create per-platform status checks
  uses: actions/github-script@v7
  with:
    script: |
      const fs = require('fs');
      const unified = JSON.parse(fs.readFileSync('results/ci_status.json', 'utf8'));

      // Create status check for each platform
      for (const platform of unified.platforms) {
        const context = `ci/${platform.platform}-tests`;
        const state = platform.failed === 0 ? 'success' : 'failure';
        const description = `${platform.passed}/${platform.total} passed (${platform.pass_rate}%)`;

        await github.rest.repos.createCommitStatus({
          owner: context.repo.owner,
          repo: context.repo.repo,
          sha: context.sha,
          context: context,
          state: state,
          description: description,
          target_url: `https://github.com/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`,
        });
      }
```

### Integrating with External Dashboards

**Grafana Integration:**
```python
# Add to ci_status_aggregator.py
import requests

def send_to_grafana(aggregate: Dict[str, Any]):
    """Send metrics to Grafana via Loki or Prometheus."""
    grafana_url = os.getenv("GRAFANA_URL")
    if not grafana_url:
        return

    metrics = {
        "pass_rate": aggregate["pass_rate"],
        "total_tests": aggregate["total_tests"],
        "total_failed": aggregate["total_failed"],
        "duration": aggregate["total_duration_seconds"],
    }

    requests.post(grafana_url, json=metrics)
```

**Datadog Integration:**
```python
# Add to ci_status_aggregator.py
from datadog import DogStatsd

def send_to_datadog(aggregate: Dict[str, Any]):
    """Send metrics to Datadog."""
    statsd = DogStatsd()
    statsd.gauge('ci.pass_rate', aggregate["pass_rate"])
    statsd.gauge('ci.total_tests', aggregate["total_tests"])
    statsd.gauge('ci.total_failed', aggregate["total_failed"])
    statsd.gauge('ci.duration', aggregate["total_duration_seconds"])
```

### Trending Data Storage

**Historical Data Location:** `backend/tests/coverage_reports/metrics/ci_status.json`

**Trend File Structure:**
```json
[
  {
    "timestamp": "2026-03-07T15:30:00.000000Z",
    "aggregate": {
      "total_tests": 2181,
      "total_passed": 2150,
      "total_failed": 31,
      "pass_rate": 98.58
    },
    "platforms": [
      {
        "platform": "backend",
        "total": 500,
        "passed": 480,
        "failed": 20,
        "duration": 580
      }
    ]
  },
  {
    "timestamp": "2026-03-07T16:00:00.000000Z",
    "aggregate": {
      "total_tests": 2185,
      "total_passed": 2160,
      "total_failed": 25,
      "pass_rate": 98.86
    },
    "platforms": [...]
  }
]
```

**Loading Historical Data:**
```python
import json
from pathlib import Path

def load_trend_history(trend_file: str) -> List[Dict[str, Any]]:
    """Load historical trend data from JSON."""
    path = Path(trend_file)
    if not path.exists():
        return []

    try:
        history = json.loads(path.read_text())
        history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return history
    except (json.JSONDecodeError, KeyError):
        return []
```

---

## Platform Retry Flow

### When Retries Trigger

**Trigger Condition:**
- `unified-tests-parallel` workflow completes with `conclusion: 'failure'`
- `platform-retry.yml` workflow_run trigger activates automatically
- Only runs on `main` and `develop` branches

**Retry Workflow:**
1. **detect-failures job** downloads artifacts from failed workflow run
2. **platform_retry_router.py** extracts failed tests for each platform
3. **Conditional retry jobs** run only for platforms with failures
4. **Retry results** uploaded as artifacts (30-day retention)

### How platform_retry_router.py Extracts Failed Tests

**Backend (pytest format):**
```python
def extract_failed_tests(results: Dict, platform: str) -> List[str]:
    """Extract failed test names from pytest JSON report."""
    if platform == "backend":
        # pytest format: summary.failed + test results
        failed_tests = []
        for test in results.get("tests", []):
            if test.get("outcome") == "failed":
                failed_tests.append(test["name"])
        return failed_tests
```

**Frontend/Mobile (Jest format):**
```python
def extract_failed_tests(results: Dict, platform: str) -> List[str]:
    """Extract failed test names from Jest JSON results."""
    if platform in ["frontend", "mobile"]:
        # Jest format: testResults with status
        failed_tests = []
        for suite in results.get("testResults", []):
            for test in suite.get("assertionResults", []):
                if test.get("status") == "failed":
                    failed_tests.append(test["fullName"])
        return failed_tests
```

**Desktop (cargo test format):**
```python
def extract_failed_tests(results: Dict, platform: str) -> List[str]:
    """Extract failed test names from cargo test JSON."""
    if platform == "desktop":
        # Cargo format: testResults with passed field
        failed_tests = []
        for test in results.get("testResults", []):
            if not test.get("passed", False):
                failed_tests.append(test["name"])
        return failed_tests
```

### Retry Job Execution Flow

**1. detect-failures job:**
```yaml
- name: Check backend failures
  id: check-backend
  run: |
    python backend/tests/scripts/platform_retry_router.py \
      --platform backend \
      --results-file results/backend/pytest_report.json \
      --output-file retry_commands/backend_retry.sh

    if [ $? -eq 0 ]; then
      echo "failed=true" >> $GITHUB_OUTPUT
    else
      echo "failed=false" >> $GITHUB_OUTPUT
    fi
```

**2. Conditional retry job:**
```yaml
retry-backend:
  name: Retry Backend Tests
  needs: [detect-failures]
  if: ${{ needs.detect-failures.outputs.backend-failed == 'true' }}
  steps:
    - name: Run backend retry tests
      run: |
        bash ../retry_commands/backend_retry.sh
```

**3. Retry result aggregation:**
```yaml
- name: Upload retry results
  uses: actions/upload-artifact@v4
  with:
    name: backend-retry-results
    path: backend/pytest_report.json
    retention-days: 7
```

### Retry Result Aggregation

**Current State:** Retry results uploaded as artifacts, but not aggregated into unified status

**Future Enhancement:** Add retry aggregation to ci_status_aggregator.py
```python
def aggregate_retry_results(
    original_results: Dict[str, Any],
    retry_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Aggregate original and retry results."""
    # Combine original + retry metrics
    # Update platform status with retry pass rate
    # Generate summary with retry information
    pass
```

---

## Best Practices

### Development Workflow

**1. Run tests locally before pushing:**
```bash
# Backend
cd backend && pytest tests/ -v -n auto

# Frontend
cd frontend-nextjs && npm run test:ci -- --maxWorkers=2

# Mobile
cd mobile && npm run test:ci -- --maxWorkers=2

# Desktop
cd frontend-nextjs/src-tauri && cargo test --test-threads=4
```

**2. Use PR drafts for experimental changes:**
- Create draft PR to trigger CI without blocking others
- Review CI results before marking PR as ready for review
- Fix failing tests before requesting review

**3. Monitor CI duration trends:**
- Check ci_status.json for pass rate trends
- Identify platforms with declining pass rates
- Optimize slow tests (target: <15 minutes total)

### CI/CD Maintenance

**1. Update baseline timings quarterly:**
- Measure actual execution time for each platform
- Update PARALLEL_EXECUTION_GUIDE.md timing benchmarks table
- Adjust timeout values if needed

**2. Review cache hit rates monthly:**
- Check job logs for cache hit/miss messages
- Optimize cache keys if hit rate <80%
- Clean up old cache entries if approaching 10 GB limit

**3. Audit test suite growth:**
- Track new test additions in ci_status.json
- Remove obsolete or duplicate tests
- Ensure test count growth aligns with feature development

### Performance Optimization

**1. Optimize slowest platform first:**
- Identify slowest platform in CI dashboard
- Focus optimization efforts on bottleneck (max(platform_durations))
- Target: All platforms <15 minutes

**2. Use test splitting strategically:**
- Only split if platform duration >15 minutes
- Start with pytest-xdist auto balancing (simpler)
- Move to manual sharding only if auto balancing insufficient

**3. Leverage caching aggressively:**
- Cache pip packages, npm modules, cargo registry
- Use restore-keys for fallback cache keys
- Verify cache hit rate in job logs

---

## Glossary

- **Matrix Strategy:** GitHub Actions feature for running multiple jobs in parallel with different configurations
- **Fail-Fast:** Workflow setting that cancels all jobs if one job fails (disabled in our workflow)
- **Max-Parallel:** Limit on concurrent matrix jobs (set to 4 for our 4 platforms)
- **Aggregation Job:** Job that combines results from multiple platform jobs into unified report
- **Retry Workflow:** Separate workflow that re-runs only failed platform tests (not full suite)
- **pytest-xdist:** pytest plugin for parallel test execution with automatic load balancing
- **Jest Sharding:** Built-in Jest feature for splitting test suite across multiple jobs
- **cargo test --test-threads:** Rust cargo test option for parallel thread execution
- **Cache Hit Rate:** Percentage of time CI cache is successfully restored (target: >80%)
- **Flaky Test:** Test that passes/fails intermittently without code changes
- **Platform-Specific Retry:** Re-run only failed tests for a specific platform (80% time savings vs full suite)

---

## Additional Resources

**Internal Documentation:**
- `.planning/phases/149-quality-infrastructure-parallel/149-RESEARCH.md` - Research document
- `backend/tests/docs/E2E_TESTING_GUIDE.md` - E2E testing patterns
- `backend/tests/docs/COVERAGE_GUIDE.md` - Coverage reporting guide
- `backend/tests/docs/FLAKY_TEST_GUIDE.md` - Flaky test handling guide

**External References:**
- [GitHub Actions Matrix Strategy](https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs)
- [pytest-xdist Documentation](https://pytest-xdist.readthedocs.io/)
- [Jest CLI Options](https://jestjs.io/docs/cli)
- [cargo test Documentation](https://doc.rust-lang.org/cargo/commands/cargo-test.html)

**Related Workflows:**
- `.github/workflows/unified-tests.yml` - Sequential test execution (backup)
- `.github/workflows/e2e-unified.yml` - E2E test orchestration (Phase 148)
- `.github/workflows/platform-retry.yml` - Platform-specific retry jobs

---

**Document Version:** 1.0
**Last Updated:** March 7, 2026
**Maintainer:** Atom CI/CD Team
**Feedback:** Open issue or PR for improvements to this guide

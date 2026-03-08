# Flaky Test Quarantine Guide

**Purpose**: Track and manage flaky tests across all platforms with automated detection, quarantine tracking, and auto-removal policies.

**Last Updated**: March 7, 2026

---

## Overview

**Flaky Test Quarantine**: A systematic approach to tracking, managing, and eventually fixing flaky tests across all platforms (backend pytest, frontend Jest, mobile jest-expo, desktop cargo test).

**Scope**: This guide applies to all platforms in the Atom codebase:
- **Backend**: Python pytest tests in `backend/tests/`
- **Frontend**: Jest tests in `frontend-nextjs/src/__tests__/`
- **Mobile**: jest-expo tests in `mobile/src/__tests__/`
- **Desktop**: Rust tests in `frontend-nextjs/src-tauri/tests/`

**Goal**: Reduce flaky tests to <5% of total test suite through systematic tracking, quarantine, and fixing.

**Key Components**:
1. **Detection**: Multi-run verification (10 runs, 30% flaky threshold)
2. **Recording**: SQLite database (`flaky_tests.db`) with failure history
3. **Classification**: stable (0% failures), flaky (1-99% failures), broken (100% failures)
4. **Auto-Quarantine**: Tests with flaky_rate > 0.3 automatically marked
5. **Auto-Removal**: Weekly cron job re-runs quarantined tests, auto-removes if stable

---

## Quarantine Workflow

### 1. Detection

**Multi-Run Verification**: Run tests multiple times to detect intermittent failures.

**Backend (Python)**:
```bash
# Run flaky detection on backend tests
cd backend
python3 tests/scripts/flaky_test_detector.py \
  --platform backend \
  --runs 10 \
  --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \
  --output tests/coverage_reports/metrics/backend_flaky_tests.json
```

**Frontend (Jest)**:
```bash
# Run flaky detection on frontend tests
cd frontend-nextjs
node scripts/jest-retry-wrapper.js \
  --platform frontend \
  --runs 10 \
  --output coverage/frontend_flaky_tests.json
```

**Mobile (jest-expo)**:
```bash
# Run flaky detection on mobile tests
cd mobile
node scripts/jest-retry-wrapper.js \
  --platform mobile \
  --runs 10 \
  --output test-results/mobile_flaky_tests.json
```

**Detection Parameters**:
- `--runs 10`: Run each test 10 times (configurable via retry_policy.py)
- `--quarantine-db`: SQLite database path for persistent tracking
- `--output`: JSON output file with flaky test results

### 2. Recording

**SQLite Database Schema**:
```sql
CREATE TABLE flaky_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_path TEXT NOT NULL,
    platform TEXT NOT NULL,
    first_detected TEXT NOT NULL,
    last_detected TEXT NOT NULL,
    total_runs INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    flaky_rate REAL NOT NULL DEFAULT 0.0,
    classification TEXT NOT NULL,  -- 'stable', 'flaky', 'broken'
    failure_history TEXT NOT NULL,  -- JSON array of failure timestamps
    quarantine_reason TEXT,
    issue_url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Indexes for Fast Lookup**:
```sql
CREATE INDEX idx_test_path ON flaky_tests(test_path, platform);
CREATE INDEX idx_flaky_rate ON flaky_tests(flaky_rate DESC);
```

**Recording Process**:
1. Flaky test detector runs test N times (default: 10)
2. Calculates flaky_rate = failure_count / total_runs
3. Classifies test: stable (0%), flaky (1-99%), broken (100%)
4. Records in SQLite database with failure history JSON array
5. Updates existing record if test_path already exists

### 3. Classification

**Stable Test** (0% failures):
```json
{
  "test_path": "tests/test_agent.py::test_create_agent",
  "total_runs": 10,
  "failures": 0,
  "flaky_rate": 0.0,
  "classification": "stable"
}
```

**Flaky Test** (1-99% failures):
```json
{
  "test_path": "tests/test_episode.py::test_retrieval_async",
  "total_runs": 10,
  "failures": 4,
  "flaky_rate": 0.4,
  "classification": "flaky",
  "failure_history": [
    {"run": 1, "failed": false, "timestamp": "2026-03-07T10:00:00Z"},
    {"run": 2, "failed": true, "timestamp": "2026-03-07T10:00:05Z"},
    {"run": 3, "failed": false, "timestamp": "2026-03-07T10:00:10Z"},
    {"run": 4, "failed": true, "timestamp": "2026-03-07T10:00:15Z"}
  ]
}
```

**Broken Test** (100% failures):
```json
{
  "test_path": "tests/test_workflow.py::test_delete_workflow",
  "total_runs": 10,
  "failures": 10,
  "flaky_rate": 1.0,
  "classification": "broken",
  "quarantine_reason": "Consistent failure (100%), likely broken test or production bug"
}
```

### 4. Auto-Quarantine

**Threshold**: Tests with flaky_rate > 0.3 (30%) are automatically quarantined.

**Configuration** (via `retry_policy.py`):
```python
# Default flaky threshold
DEFAULT_RETRY_POLICY = RetryPolicy(
    flaky_threshold=0.3,  # 30% failure rate
    platform_overrides={
        "frontend": {
            "flaky_threshold": 0.2,  # 20% (more strict for MSW/axios issues)
        }
    }
)
```

**Auto-Quarantine Process**:
1. Flaky detector identifies test with flaky_rate > threshold
2. Records test in SQLite database with classification='flaky'
3. CI/CD workflow posts PR comment with reliability score
4. Test marked for weekly re-evaluation

### 5. Weekly Re-Run & Auto-Removal

**Cron Job Schedule**: Weekly (every Sunday at 2 AM UTC)

**Re-Run Process**:
```bash
# Weekly cron job (pseudo-code)
for each quarantined_test in flaky_tests.db:
    run test 20 times
    if pass_rate == 100%:
        remove from quarantine
        notify developers via PR
        log to fixed_flaky_tests table
```

**Auto-Removal Criteria**:
- 20 consecutive passes (no failures)
- Pass rate = 100% (0% flaky rate)
- Test marked as 'stable' in database

**Auto-Removal Notification**:
```markdown
## Flaky Test Fixed 🎉

**Test**: `tests/test_episode.py::test_retrieval_async`
**Platform**: Backend
**First Detected**: 2026-02-01
**Fixed**: 2026-03-07
**Duration**: 34 days in quarantine

**Verification**: 20 consecutive passes (100% pass rate)
**Action**: Removed from quarantine automatically

Please review and close associated issue: #1234
```

---

## Retry Configuration

**Centralized Retry Policy**: Platform-specific retry policies configured in `backend/tests/scripts/retry_policy.py`.

**View Policy for Platform**:
```bash
# Backend policy
python3 backend/tests/scripts/retry_policy.py --platform backend

# Mobile policy
python3 backend/tests/scripts/retry_policy.py --platform mobile
```

**Platform-Specific Settings**:

| Platform | max_retries | retry_delay | test_timeout | flaky_threshold | detection_runs |
|----------|-------------|-------------|--------------|-----------------|----------------|
| **Backend** | 2 | 1.0s | 60.0s | 0.3 (30%) | 10 |
| **Frontend** | 3 | 1.0s | 30.0s | 0.2 (20%) | 15 |
| **Mobile** | 5 | 2.0s | 30.0s | 0.3 (30%) | 10 |
| **Desktop** | 2 | 0.5s | 15.0s | 0.3 (30%) | 10 |

**Rationale**:
- **Backend**: Longer timeout (60s) for async tests, fewer retries (2) to avoid masking real failures
- **Frontend**: Lower flaky threshold (20%) due to MSW/axios flakiness, more detection runs (15)
- **Mobile**: More retries (5) and longer delay (2s) for network flakiness (React Native testing)
- **Desktop**: Faster retries (0.5s) and shorter timeout (15s) because Rust tests are fast

**Environment Variable Overrides**:
```bash
# Override flaky threshold
FLAKY_THRESHOLD=0.5 python3 backend/tests/scripts/flaky_test_detector.py --platform backend

# Override max retries
MAX_RETRIES=5 python3 backend/tests/scripts/flaky_test_detector.py --platform mobile
```

---

## Developer Guide

### How to Check if a Test is Quarantined

**Query SQLite Database**:
```bash
# Check specific test
sqlite3 backend/tests/coverage_reports/metrics/flaky_tests.db \
  "SELECT * FROM flaky_tests WHERE test_path LIKE '%test_create_agent%'"

# Check all quarantined tests for a platform
sqlite3 backend/tests/coverage_reports/metrics/flaky_tests.db \
  "SELECT test_path, flaky_rate, first_detected FROM flaky_tests WHERE platform='backend' AND classification='flaky'"

# Check most frequently failing tests
sqlite3 backend/tests/coverage_reports/metrics/flaky_tests.db \
  "SELECT test_path, flaky_rate FROM flaky_tests WHERE classification='flaky' ORDER BY flaky_rate DESC LIMIT 10"
```

**Read JSON Export**:
```bash
# View flaky test report
cat backend/tests/coverage_reports/metrics/backend_flaky_tests.json | jq '.flaky_tests[] | select(.classification == "flaky")'
```

### How to Fix a Flaky Test

**Step 1: Analyze Failure History**:
```bash
# Get failure history from database
sqlite3 backend/tests/coverage_reports/metrics/flaky_tests.db \
  "SELECT failure_history FROM flaky_tests WHERE test_path='tests/test_episode.py::test_retrieval_async'"
```

**Step 2: Identify Root Cause**:
Common flaky test patterns (from `FLAKY_TEST_GUIDE.md`):
- **Race conditions**: Add explicit synchronization (events, barriers)
- **Shared state**: Use `db_session` or `unique_resource_name` fixtures
- **External dependencies**: Mock APIs, databases, services
- **Time dependencies**: Use `freezegun` to mock time
- **Resource contention**: Use unique resource names or ephemeral ports

**Step 3: Apply Fix**:
```python
# Before (Flaky)
def test_episode_retrieval():
    episode = create_episode()
    results = search_service.search(episode.id)
    # May not be indexed yet (race condition)
    assert episode.id in results

# After (Fixed)
def test_episode_retrieval():
    episode = create_episode()
    # Explicit wait for indexing
    search_service.wait_for_indexing(episode.id, timeout=5.0)
    results = search_service.search(episode.id)
    assert episode.id in results
```

**Step 4: Verify Fix**:
```bash
# Run test 100 times to verify stability
for i in {1..100}; do
  pytest tests/test_episode.py::test_retrieval_async -v
done

# Should pass 100/100 times
```

**Step 5: Remove from Quarantine**:
```bash
# Option 1: Wait for weekly auto-removal (if test passes 20 consecutive runs)
# Option 2: Manual removal (only after fix is verified)
sqlite3 backend/tests/coverage_reports/metrics/flaky_tests.db \
  "UPDATE flaky_tests SET classification='stable' WHERE test_path='tests/test_episode.py::test_retrieval_async'"
```

### How to Remove from Quarantine

**Auto-Removal (Recommended)**:
1. Fix the flaky test
2. Push fix to main branch
3. Weekly cron job will re-run quarantined tests
4. If test passes 20 consecutive times, auto-removed from quarantine
5. PR notification posted automatically

**Manual Removal (Not Recommended)**:
```bash
# Only use manual removal if you've verified fix with 100 consecutive passes
sqlite3 backend/tests/coverage_reports/metrics/flaky_tests.db \
  "UPDATE flaky_tests SET classification='stable', updated_at=datetime('now') WHERE test_path='tests/test_episode.py::test_retrieval_async'"
```

**WARNING**: Do not manually remove tests from quarantine without proper verification. This leads to false positives and erodes confidence in the quarantine system.

### How to Verify Fix

**Run Flaky Detector**:
```bash
# Run detector on specific test (will update database)
cd backend
python3 tests/scripts/flaky_test_detector.py \
  --platform backend \
  --runs 20 \
  --test-path tests/test_episode.py::test_retrieval_async \
  --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \
  --output tests/coverage_reports/metrics/verify_fix.json
```

**Check Result**:
```bash
# Should show classification='stable' and flaky_rate=0.0
cat tests/coverage_reports/metrics/verify_fix.json | jq '.flaky_tests[]'
```

---

## CI/CD Integration

### unified-tests-parallel.yml

**Flaky Detection Steps** (after test execution):
```yaml
- name: Run flaky detection (backend)
  if: matrix.platform == 'backend'
  working-directory: ./backend
  run: |
    python3 tests/scripts/flaky_test_detector.py \
      --platform backend \
      --runs 3 \
      --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \
      --output tests/coverage_reports/metrics/backend_flaky_tests.json
  continue-on-error: true
```

**Reliability Score Aggregation**:
```yaml
- name: Calculate reliability scores
  if: always()
  working-directory: ./backend
  run: |
    python3 tests/scripts/reliability_scorer.py \
      --backend-flaky ../flaky-reports/backend/backend_flaky_tests.json \
      --frontend-flaky ../flaky-reports/frontend/frontend_flaky_tests.json \
      --mobile-flaky ../flaky-reports/mobile/mobile_flaky_tests.json \
      --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \
      --output ../results/reliability_score.json
  continue-on-error: true
```

**PR Comments**:
```yaml
- name: Comment reliability score on PR
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v7
  with:
    script: |
      const reliability = JSON.parse(fs.readFileSync('backend/tests/coverage_reports/metrics/reliability_score.json', 'utf8'));
      const score = (reliability.overall_score * 100).toFixed(1);
      const icon = score >= 90 ? '🟢' : score >= 80 ? '🟡' : '🔴';
      const comment = `## Test Reliability Report\n\n${icon} Overall Score: ${score}%\n\n...`;
      github.rest.issues.createComment({ ...context.issue, body: comment });
```

### Artifact Retention

**Flaky Test Reports**: 30-day retention
- `backend_flaky_tests.json`
- `frontend_flaky_tests.json`
- `mobile_flaky_tests.json`
- `flaky_tests.db` (SQLite database)

**Reliability Scores**: 30-day retention
- `reliability_score.json` (overall + platform breakdown)

### PR Comment Format

```markdown
## Test Reliability Report

🟢 Overall Score: 94.5% ↑ 2.3%

### Platform Breakdown
- **Backend**: 96.2% ↑ 1.5%
- **Frontend**: 92.8% ↑ 3.1%
- **Mobile**: 94.1% ↓ 0.5%
- **Desktop**: 95.0% ↑ 2.0%

### Least Reliable Tests
- `tests/test_episode.py::test_retrieval_async`: 45.0% flaky
- `frontend/src/__tests__/api.test.ts`: 38.2% flaky
- `mobile/src/__tests__/agent.test.tsx`: 32.1% flaky

[Full Report](https://github.com/user/repo/actions/runs/123456)
```

---

## Troubleshooting

### False Positive Flaky Detection

**Symptom**: Test flagged as flaky but actually stable

**Diagnosis**:
```bash
# Check detection runs count
sqlite3 backend/tests/coverage_reports/metrics/flaky_tests.db \
  "SELECT total_runs, failure_count, flaky_rate FROM flaky_tests WHERE test_path='tests/test_agent.py::test_create_agent'"

# If total_runs < 10, increase detection_runs
```

**Fix**: Increase detection runs or check test isolation
```bash
# Run with more runs for statistical significance
python3 tests/scripts/flaky_test_detector.py \
  --platform backend \
  --runs 20 \
  --test-path tests/test_agent.py::test_create_agent
```

**Root Cause**: Detection runs too low (e.g., 3 runs) for statistical significance. Use 10+ runs.

### Database Bloat

**Symptom**: SQLite database >100MB, slow queries (>1s)

**Diagnosis**:
```bash
# Check database size
ls -lh backend/tests/coverage_reports/metrics/flaky_tests.db

# Check record count
sqlite3 backend/tests/coverage_reports/metrics/flaky_tests.db \
  "SELECT COUNT(*) FROM flaky_tests"
```

**Fix**: Prune old records
```sql
-- Archive records older than 90 days
CREATE TABLE flaky_tests_archive AS
SELECT * FROM flaky_tests WHERE updated_at < datetime('now', '-90 days');

-- Delete old records
DELETE FROM flaky_tests WHERE updated_at < datetime('now', '-90 days');

-- Vacuum database to reclaim space
VACUUM;
```

**Prevention**: Set up monthly cron job to prune old records.

### Slow Detection

**Symptom**: Flaky detection takes >30 minutes

**Diagnosis**:
```bash
# Check detection runs
python3 backend/tests/scripts/retry_policy.py --platform backend
# If detection_runs=50, reduce to 10
```

**Fix**: Use tiered detection approach
```bash
# Quick check (3 runs) on every PR
python3 tests/scripts/flaky_test_detector.py --runs 3 --platform backend

# Deep analysis (10 runs) nightly via cron
python3 tests/scripts/flaky_test_detector.py --runs 10 --platform backend
```

### Test Isolation Issues

**Symptom**: Tests fail when run in parallel but pass sequentially

**Diagnosis**:
```bash
# Run tests sequentially
pytest tests/ -v

# Run tests in parallel
pytest tests/ -n auto -v

# Compare results
```

**Fix**: Use unique resource names or `db_session` fixture
```python
# Before (shared state)
def test_create_agent():
    agent = Agent(id="test-agent", ...)  # Collision in parallel

# After (isolated)
def test_create_agent(unique_resource_name):
    agent = AgentFactory.create(id=unique_resource_name)  # Unique per test
```

---

## Related Documentation

- **[FLAKY_TEST_GUIDE.md](./FLAKY_TEST_GUIDE.md)** - Comprehensive flaky test prevention guide
- **[retry_policy.py](../scripts/retry_policy.py)** - Centralized retry policy configuration
- **[flaky_test_detector.py](../scripts/flaky_test_detector.py)** - Multi-run flaky detection script
- **[flaky_test_tracker.py](../scripts/flaky_test_tracker.py)** - SQLite quarantine database manager
- **[reliability_scorer.py](../scripts/reliability_scorer.py)** - Cross-platform reliability scoring

---

## Summary

**Key Takeaways**:
1. **Detection**: Multi-run verification (10 runs, 30% threshold) identifies flaky tests
2. **Recording**: SQLite database tracks failure history with JSON arrays
3. **Classification**: stable (0%), flaky (1-99%), broken (100%)
4. **Auto-Quarantine**: Tests with flaky_rate > 0.3 automatically marked
5. **Auto-Removal**: Weekly cron job re-runs tests, removes if 20 consecutive passes
6. **Retry Policy**: Platform-specific settings (backend: 60s timeout, frontend: 20% threshold, mobile: 5 retries, desktop: 0.5s delay)
7. **CI/CD Integration**: unified-tests-parallel.yml runs detection, posts PR comments, uploads artifacts (30-day retention)

**Quick Reference**:
```bash
# Check quarantined tests
sqlite3 backend/tests/coverage_reports/metrics/flaky_tests.db \
  "SELECT test_path, flaky_rate FROM flaky_tests WHERE classification='flaky'"

# Run flaky detection
python3 backend/tests/scripts/flaky_test_detector.py --platform backend --runs 10

# View retry policy
python3 backend/tests/scripts/retry_policy.py --platform backend
```

**Next Steps**:
1. Run flaky detection on all platforms to establish baseline
2. Fix top 10 most frequently failing tests
3. Set up weekly cron job for auto-removal
4. Monitor reliability score trends in CI/CD
5. Aim for <5% flaky test rate across all platforms

## See Also

- [Testing Documentation Index](../../docs/TESTING_INDEX.md) - Central hub for all testing documentation
- [Testing Onboarding Guide](../../docs/TESTING_ONBOARDING.md) - 15-minute quick start for all platforms
- [Flaky Test Guide](FLAKY_TEST_GUIDE.md) - Comprehensive flaky test patterns
- [Parallel Execution Guide](PARALLEL_EXECUTION_GUIDE.md) - CI/CD integration for flaky detection
- [Coverage Trending Guide](COVERAGE_TRENDING_GUIDE.md) - Track reliability trends over time

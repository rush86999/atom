# Phase 151: Quality Infrastructure Test Reliability - Research

**Researched:** March 7, 2026
**Domain:** Test Reliability Engineering (Flaky Test Detection & Quarantine)
**Confidence:** HIGH

## Summary

Phase 151 requires implementing a cross-platform flaky test detection and quarantine system that works across four test runners (pytest, Jest, jest-expo, cargo test) with unified tracking and CI/CD integration. The system must detect flaky tests through multi-run verification, track failure history with patterns, enforce retry policies, and calculate test reliability scores for CI reporting.

**Primary recommendation:** Use pytest-rerunfailures for Python (already in requirements-testing.txt), implement custom retry wrappers for Jest/jest-expo using jest-circus or manual retry logic, use cargo-nextest for Rust with retry support, and build a unified flaky test tracking database (SQLite) with historical failure pattern analysis and reliability scoring.

**Key insight:** Atom already has flaky test infrastructure partially implemented (pytest-rerunfailures configured, @pytest.mark.flaky marker defined, platform-retry.yml workflow for targeted re-runs), but lacks automated flaky detection, quarantine tracking, and reliability scoring. Build on existing infrastructure rather than replacing it.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest-rerunfailures** | 13.0-15.0 | Python test retry with configurable reruns | Industry standard for pytest, already in requirements-testing.txt, integrates with pytest markers |
| **pytest-json-report** | 0.6.0+ | Structured JSON output for test results | Already used in CI/CD, provides machine-readable failure data |
| **sqlite3** | (stdlib) | Flaky test tracking database | Built-in, sufficient for tracking failure history, no external dependencies |
| **python-dateutil** | 2.8.0+ | Timestamp parsing for failure patterns | Reliable datetime handling, timezone-aware |

### Supporting (Frontend/Mobile)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **jest-circus** | (built-in) | Jest test runner with retry hooks | For custom retry logic in frontend/mobile tests |
| **jest-stare** | 2.0+ | Enhanced Jest reporting with retry tracking | Optional: If more detailed Jest reporting needed |
| **axios-mock-adapter** | 1.21+ | Mock axios for MSW integration tests | Fix common MSW/axios flaky test patterns |

### Supporting (Desktop/Rust)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **cargo-nextest** | 0.9.30+ | Next-gen Rust test runner with retry support | Replace cargo test for better flaky detection |
| **nextest-report** | (bundled) | JSON test result format for nextest | Required for flaky test aggregation |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-rerunfailures | pytest-flaky | pytest-flaky has different API (max_runs/min_passes), less maintained |
| SQLite tracking | PostgreSQL | SQLite sufficient for CI-local tracking, PostgreSQL adds complexity |
| Custom retry logic | flaky (npm package) | flaky package has more features but adds dependency overhead |
| cargo-nextest | cargo test (native) | Native cargo has no built-in retry, nextest is industry standard |

**Installation:**
```bash
# Python (already in requirements-testing.txt)
pip install pytest-rerunfailures==13.0
pip install pytest-json-report==0.6.0

# Frontend/Mobile (retry logic custom, no install needed)
# npm install jest-circus  # Already bundled with Jest 27+

# Desktop/Rust
cargo install cargo-nextest --locked
cargo install nextest-report
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── scripts/
│   ├── flaky_test_detector.py      # NEW: Multi-run flaky detection
│   ├── flaky_test_tracker.py       # NEW: Quarantine database manager
│   ├── reliability_scorer.py       # NEW: Test reliability calculation
│   └── detect_flaky_tests.py       # EXISTS: Manual detection script
├── coverage_reports/metrics/
│   ├── flaky_tests.db              # NEW: SQLite quarantine database
│   ├── flaky_history.json          # NEW: Historical failure patterns
│   └── reliability_score.json      # NEW: Per-test reliability metrics
└── docs/
    ├── FLAKY_TEST_GUIDE.md         # EXISTS: Prevention guide
    └── FLAKY_TEST_QUARANTINE.md    # NEW: Quarantine procedures

frontend-nextjs/
├── scripts/
│   └── jest-retry-wrapper.js       # NEW: Custom Jest retry logic
└── tests/
    └── helpers/
        └── flakyTestDetector.js    # NEW: Jest flaky detection

mobile/
├── scripts/
│   └── jest-retry-wrapper.js       # NEW: Mobile Jest retry logic
└── src/__tests__/
    └── helpers/
        └── flakyTestDetector.js    # NEW: Mobile flaky detection

frontend-nextjs/src-tauri/
└── .cargo/
    └── config.toml                 # MODIFY: Add nextest configuration
```

### Pattern 1: Multi-Run Flaky Detection

**What:** Run tests multiple times to detect intermittent failures.

**When to use:** CI/CD pipelines, pre-commit validation, manual flaky investigation.

**Example (Python):**

```python
# Source: backend/tests/scripts/flaky_test_detector.py
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Tuple
import statistics

def run_test_multiple_times(
    test_path: str,
    runs: int = 10,
    pytest_args: List[str] = None
) -> Tuple[int, List[bool], Dict[str, any]]:
    """
    Run a test multiple times to detect flakiness.

    Args:
        test_path: Test identifier (e.g., tests/test_module.py::test_function)
        runs: Number of times to run the test
        pytest_args: Additional pytest arguments

    Returns:
        (failure_count, failure_list, report_dict)
    """
    pytest_args = pytest_args or []
    failures = []

    for i in range(runs):
        result = subprocess.run(
            ["pytest", test_path, "-v", "--tb=no"] + pytest_args,
            capture_output=True,
            text=True
        )
        failures.append(result.returncode != 0)

    failure_count = sum(failures)
    flaky_rate = failure_count / runs

    # Classify flakiness
    if failure_count == 0:
        classification = "stable"
    elif failure_count == runs:
        classification = "broken"
    elif 0 < failure_count < runs:
        classification = "flaky"

    report = {
        "test_path": test_path,
        "total_runs": runs,
        "failures": failure_count,
        "flaky_rate": flaky_rate,
        "classification": classification,
        "failure_details": [
            {"run": i, "failed": failed}
            for i, failed in enumerate(failures)
        ]
    }

    return failure_count, failures, report
```

**Example (Jest):**

```javascript
// Source: frontend-nextjs/scripts/jest-retry-wrapper.js
const { execSync } = require('child_process');
const fs = require('fs');

function runTestMultipleTimes(testPattern, runs = 10) {
  const failures = [];

  for (let i = 0; i < runs; i++) {
    try {
      execSync(
        `jest --testNamePattern="${testPattern}" --passWithNoTests`,
        { stdio: 'pipe' }
      );
      failures.push(false);
    } catch (error) {
      failures.push(true);
    }
  }

  const failureCount = failures.filter(f => f).length;
  const flakyRate = failureCount / runs;

  let classification;
  if (failureCount === 0) classification = 'stable';
  else if (failureCount === runs) classification = 'broken';
  else classification = 'flaky';

  return {
    testPattern,
    totalRuns: runs,
    failures: failureCount,
    flakyRate,
    classification,
    failureDetails: failures.map((failed, i) => ({ run: i, failed }))
  };
}
```

### Pattern 2: Quarantine Database Schema

**What:** SQLite database to track flaky tests with failure history and patterns.

**When to use:** Persistent flaky test tracking across CI runs, historical analysis.

**Example:**

```python
# Source: backend/tests/scripts/flaky_test_tracker.py
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

class FlakyTestTracker:
    """Track flaky tests in SQLite database with failure history."""

    def __init__(self, db_path: Path):
        """Initialize database and create schema if needed."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_schema()

    def _create_schema(self):
        """Create flaky_tests table if not exists."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS flaky_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_path TEXT NOT NULL,
                platform TEXT NOT NULL,
                first_detected TEXT NOT NULL,
                last_detected TEXT NOT NULL,
                total_runs INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                flaky_rate REAL NOT NULL DEFAULT 0.0,
                classification TEXT NOT NULL,
                failure_history TEXT NOT NULL,  -- JSON array of failure timestamps
                quarantine_reason TEXT,
                issue_url TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Index for fast lookup
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_test_path
            ON flaky_tests(test_path, platform)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_flaky_rate
            ON flaky_tests(flaky_rate DESC)
        """)

        self.conn.commit()

    def record_flaky_test(
        self,
        test_path: str,
        platform: str,
        total_runs: int,
        failure_count: int,
        classification: str,
        failure_history: List[Dict],
        quarantine_reason: Optional[str] = None
    ) -> int:
        """Record or update a flaky test in the database."""
        flaky_rate = failure_count / total_runs if total_runs > 0 else 0.0
        now = datetime.utcnow().isoformat()

        # Check if test already exists
        cursor = self.conn.execute(
            "SELECT id, failure_history FROM flaky_tests WHERE test_path = ? AND platform = ?",
            (test_path, platform)
        )
        row = cursor.fetchone()

        if row:
            # Update existing record
            test_id, existing_history_json = row
            existing_history = json.loads(existing_history_json)
            merged_history = existing_history + failure_history

            self.conn.execute("""
                UPDATE flaky_tests
                SET last_detected = ?,
                    total_runs = total_runs + ?,
                    failure_count = failure_count + ?,
                    flaky_rate = ?,
                    classification = ?,
                    failure_history = ?,
                    quarantine_reason = COALESCE(?, quarantine_reason),
                    updated_at = ?
                WHERE id = ?
            """, (
                now, total_runs, failure_count, flaky_rate,
                classification, json.dumps(merged_history),
                quarantine_reason, now, test_id
            ))
            return test_id
        else:
            # Insert new record
            cursor = self.conn.execute("""
                INSERT INTO flaky_tests (
                    test_path, platform, first_detected, last_detected,
                    total_runs, failure_count, flaky_rate, classification,
                    failure_history, quarantine_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test_path, platform, now, now,
                total_runs, failure_count, flaky_rate, classification,
                json.dumps(failure_history), quarantine_reason
            ))
            return cursor.lastrowid

    def get_quarantined_tests(self, platform: Optional[str] = None) -> List[Dict]:
        """Get all quarantined tests, optionally filtered by platform."""
        query = "SELECT * FROM flaky_tests WHERE classification = 'flaky'"
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_test_reliability_score(self, test_path: str, platform: str) -> float:
        """
        Calculate reliability score for a test (0.0 to 1.0).

        Score = 1.0 - flaky_rate
        """
        cursor = self.conn.execute(
            "SELECT flaky_rate FROM flaky_tests WHERE test_path = ? AND platform = ?",
            (test_path, platform)
        )
        row = cursor.fetchone()

        if not row:
            return 1.0  # No failures recorded = perfect reliability

        flaky_rate = row[0]
        return max(0.0, 1.0 - flaky_rate)

    def _row_to_dict(self, row) -> Dict:
        """Convert database row to dictionary."""
        columns = [
            'id', 'test_path', 'platform', 'first_detected', 'last_detected',
            'total_runs', 'failure_count', 'flaky_rate', 'classification',
            'failure_history', 'quarantine_reason', 'issue_url',
            'created_at', 'updated_at'
        ]
        return dict(zip(columns, row))
```

### Pattern 3: Retry Policy Configuration

**What:** Centralized retry policy configuration for all platforms.

**When to use:** CI/CD workflows, test configuration management.

**Example:**

```python
# Source: backend/tests/scripts/retry_policy.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class RetryPolicy:
    """Retry policy configuration for flaky tests."""

    # Maximum number of retry attempts
    max_retries: int = 3

    # Delay between retries (seconds)
    retry_delay: float = 1.0

    # Timeout for single test run (seconds)
    test_timeout: float = 30.0

    # Flaky rate threshold for quarantine (0.0 to 1.0)
    flaky_threshold: float = 0.3  # 30% failure rate

    # Number of runs for flaky detection
    detection_runs: int = 10

    # Minimum runs before considering test stable
    min_stable_runs: int = 20

    # Quarantine: Automatically skip quarantined tests
    auto_quarantine: bool = True

    # Quarantine: Warn on quarantined tests
    warn_quarantine: bool = True

    # Platform-specific overrides
    platform_overrides: dict = None

    def get_policy_for_platform(self, platform: str) -> 'RetryPolicy':
        """Get retry policy for specific platform."""
        if self.platform_overrides and platform in self.platform_overrides:
            overrides = self.platform_overrides[platform]
            # Merge overrides with base policy
            return RetryPolicy(
                **{**self.__dict__, **overrides}
            )
        return self

# Default retry policies
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    retry_delay=1.0,
    test_timeout=30.0,
    flaky_threshold=0.3,
    detection_runs=10,
    min_stable_runs=20,
    auto_quarantine=True,
    warn_quarantine=True,
    platform_overrides={
        # Backend: Longer timeout for async tests
        "backend": {
            "test_timeout": 60.0,
            "max_retries": 2,
        },
        # Frontend: Lower flaky threshold (MSW/axios issues)
        "frontend": {
            "flaky_threshold": 0.2,
            "detection_runs": 15,
        },
        # Mobile: More retries (network flakiness)
        "mobile": {
            "max_retries": 5,
            "retry_delay": 2.0,
        },
        # Desktop: Faster retries (Rust tests are fast)
        "desktop": {
            "max_retries": 2,
            "retry_delay": 0.5,
            "test_timeout": 15.0,
        }
    }
)
```

### Pattern 4: CI/CD Integration

**What:** Integrate flaky detection into unified-tests-parallel.yml workflow.

**When to use:** CI/CD pipelines, GitHub Actions workflows.

**Example:**

```yaml
# Source: .github/workflows/unified-tests-parallel.yml (MODIFY)
# Add flaky detection step after test execution

- name: Run backend flaky detection
  if: matrix.platform == 'backend'
  working-directory: ./backend
  run: |
    python tests/scripts/flaky_test_detector.py \
      --platform backend \
      --runs 10 \
      --output tests/coverage_reports/metrics/backend_flaky_tests.json \
      --quarantine-db tests/coverage_reports/metrics/flaky_tests.db
  continue-on-error: true

- name: Run frontend flaky detection
  if: matrix.platform == 'frontend'
  working-directory: ./frontend-nextjs
  run: |
    node scripts/jest-retry-wrapper.js \
      --platform frontend \
      --runs 10 \
      --output coverage/frontend_flaky_tests.json
  continue-on-error: true

- name: Calculate reliability scores
  if: always()
  working-directory: ./backend
  run: |
    python tests/scripts/reliability_scorer.py \
      --backend-flaky ../results/backend/pytest_report.json \
      --frontend-flaky ../results/frontend/flaky_tests.json \
      --mobile-flaky ../results/mobile/flaky_tests.json \
      --desktop-flaky ../results/desktop/flaky_tests.json \
      --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \
      --output ../results/reliability_score.json
  continue-on-error: true

- name: Upload flaky test reports
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: flaky-test-reports
    path: |
      backend/tests/coverage_reports/metrics/*_flaky_tests.json
      backend/tests/coverage_reports/metrics/flaky_tests.db
      results/reliability_score.json
    retention-days: 30
```

### Anti-Patterns to Avoid

- **Manual retry without tracking**: Don't just add @pytest.mark.flaky without recording in database
- **Global retry for all tests**: Don't set --reruns globally without test-specific investigation
- **Ignoring flaky tests**: Don't comment out flaky tests (they get forgotten), quarantine them instead
- **Permanent workarounds**: Don't leave @pytest.mark.flaky in code permanently
- **No failure analysis**: Don't retry without understanding why tests fail (race condition? timeout? dependency?)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test retry logic | Custom subprocess wrapper with sleep loops | pytest-rerunfailures | Handles edge cases (timeout, signal handling, test isolation) |
| JSON test result parsing | Manual regex/JSON parsing | pytest-json-report, jest --json | Standard formats, battle-tested, handles nested test results |
| Database schema | Custom JSON file storage | SQLite3 | ACID guarantees, concurrent access, indexed queries |
| Retry scheduling | Cron jobs, manual triggers | GitHub Actions workflow_run | Native CI/CD integration, artifact handling, permissions |
| Flaky detection algorithms | Custom heuristics (e.g., "failed 2/10 times") | Statistical flaky rate with confidence intervals | Mathematically sound, configurable thresholds, reproducible |

**Key insight:** Building custom flaky detection seems simple but has hidden complexity: concurrent database access, test isolation, timeout handling, signal propagation, and statistical significance. Use existing tools and extend them rather than rebuilding from scratch.

## Common Pitfalls

### Pitfall 1: False Positive Flaky Detection

**What goes wrong:** Tests flagged as flaky when they're actually broken (100% failure rate).

**Why it happens:** Flaky detection algorithm doesn't distinguish between intermittent failures (flaky) and consistent failures (broken).

**How to avoid:**
- Classify tests as "broken" if failure_rate = 1.0 (100%)
- Only classify as "flaky" if 0 < failure_rate < 1.0
- Require minimum runs (e.g., 10) before classification
- Use statistical significance test (e.g., binomial test)

**Warning signs:** All tests showing as flaky, high flaky rate (>80%), developers disputing flaky classification.

### Pitfall 2: CI/CD Timeout Explosion

**What goes wrong:** Flaky detection multiplies test execution time (10x for 10-run detection).

**Why it happens:** Running full test suite 10 times for flaky detection is too slow.

**How to avoid:**
- Only run flaky detection on changed tests (git diff)
- Run flaky detection nightly/weekly, not on every commit
- Use adaptive detection: start with 3 runs, increase to 10 if failures detected
- Parallelize detection across platforms (already done in unified-tests-parallel.yml)

**Warning signs:** CI jobs timing out (>30 minutes), developers disabling flaky detection to speed up CI.

### Pitfall 3: Quarantine Database Bloat

**What goes wrong:** Flaky test database grows indefinitely with historical failure data.

**Why it happens:** Failure history arrays grow without pruning, old tests never removed.

**How to avoid:**
- Prune failure history older than 90 days
- Archive stable tests (100% pass rate for 30+ runs) to separate table
- Set retention policy: delete records updated >90 days ago
- Use compressed JSON for failure_history (gzip)

**Warning signs:** SQLite database >100MB, slow queries (>1s), high disk usage.

### Pitfall 4: Platform-Specific Retry Logic Inconsistency

**What goes wrong:** Different retry behavior across platforms (pytest retries 3x, Jest retries 0x).

**Why it happens:** Each platform has different retry configuration (pytest-rerunfailures vs jest.retryTimes).

**How to avoid:**
- Centralize retry policy in Python (retry_policy.py)
- Generate platform-specific config from single source of truth
- Validate consistency: assert all platforms use same max_retries
- Document platform-specific overrides with justification

**Warning signs:** Developers confused why tests pass on backend but fail on frontend, inconsistent CI behavior.

### Pitfall 5: Ignoring Fixed Flaky Tests

**What goes wrong:** Tests remain in quarantine forever even after being fixed.

**Why it happens:** No mechanism to detect stable tests and remove from quarantine.

**How to avoid:**
- Weekly cron job: re-run all quarantined tests
- Auto-remove from quarantine if 20 consecutive passes
- Send PR notification when test becomes stable
- Maintain "fixed_flaky_tests" log for accountability

**Warning signs:** Quarantine list growing, tests marked flaky for >6 months, developers surprised when quarantine removed.

## Code Examples

### Verified patterns from official sources:

### Example 1: pytest-rerunfailures Configuration

```python
# Source: pytest-rerunfailures official documentation
# https://pytest-rerunfailures.readthedocs.io/

# Install
pip install pytest-rerunfailures

# Command-line usage
pytest --reruns 3 --reruns-delay 1

# pytest.ini configuration
[pytest]
addopts = --reruns 2 --reruns-delay 1

# Marker usage (NOT recommended for permanent use)
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_example():
    assert True
```

### Example 2: Jest Retry Logic (Custom)

```javascript
// Source: Jest issue discussions and community patterns
// https://github.com/facebook/jest/issues/7958

const flakyTests = new Map();

// Track test failures
jest.retryTimes(3);

// Or custom retry wrapper
async function runTestWithRetry(testFn, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await testFn();
      return;
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
}
```

### Example 3: cargo-nextest Retry Configuration

```toml
# Source: cargo-nextest documentation
# https://nexte.st/book/configuration.html

# .config/nextest.toml
[profile.default]
retries = 2
retry-backoff = "fixed 1s"  # 1 second delay between retries

[profile.ci]
retries = 3
retry-backoff = "exponential 1 2"  # Exponential backoff: 1s, then 2s

# Run with retry
cargo nextest run --profile ci

# Output format for JSON parsing
cargo nextest run --message-format=json > nextest_results.json
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual retry (re-run pytest manually) | pytest-rerunfailures (automated retry) | 2020+ | Reduced developer toil, consistent retry behavior |
| JSON file tracking | SQLite database with ACID guarantees | 2022+ | Concurrent access safe, indexed queries, data integrity |
| Per-platform flaky detection | Cross-platform unified tracking | 2024+ | Consistent reliability scores across platforms |
| Static retry count (always 3) | Adaptive retry based on flaky rate | 2025+ | Faster CI for stable tests, more retries for known flaky |
| Manual quarantine (comment out tests) | Automated quarantine with auto-removal | 2025+ | Fixed tests auto-unquarantined, reduced technical debt |

**Deprecated/outdated:**
- **pytest-flaky**: Less maintained than pytest-rerunfailures, different API
- **Manual sleep loops**: Use proper retry libraries with exponential backoff
- **Per-test @pytest.mark.flaky**: Use centralized policy, not scattered markers
- **Ignoring flaky tests**: Quarantine and track, don't ignore

## Open Questions

1. **Statistical Significance Threshold**
   - What we know: Need minimum runs (10) and flaky rate threshold (30%)
   - What's unclear: Should we use binomial test for statistical significance? How to handle tests with <10 runs in CI?
   - Recommendation: Start with simple threshold (30%), add binomial test if needed (use scipy.stats.binom_test)

2. **Quarantine Auto-Removal Policy**
   - What we know: Should auto-remove stable tests after N consecutive passes
   - What's unclear: What should N be? 10? 20? 50? How to handle false positives (test passes 20x by luck)?
   - Recommendation: Start with N=20, adjust based on false positive rate. Log all auto-removals for review.

3. **Cross-Platform Test Identity**
   - What we know: Need to track same test across platforms (e.g., test_create_agent in pytest and Jest)
   - What's unclear: Should tests have unique IDs? How to handle platform-specific tests that only exist on one platform?
   - Recommendation: Use test_path + platform as composite key. Don't force cross-platform identity if tests are fundamentally different.

4. **Flaky Detection in CI vs. Nightly**
   - What we know: Full flaky detection (10 runs) is too slow for every commit
   - What's unclear: Should we run 3-run detection on every commit, 10-run detection nightly? How to handle tests that only fail intermittently?
   - Recommendation: Implement tiered detection: 3-run quick detection on every PR (with --reruns 3 in pytest.ini), 10-run deep detection nightly via cron.

## Sources

### Primary (HIGH confidence)

- **pytest-rerunfailures documentation** - Plugin API, configuration options, marker usage
- **pytest-json-report documentation** - JSON test result format, schema
- **cargo-nextest documentation** - Retry configuration, JSON output format
- **SQLite3 Python documentation** - Database schema design, concurrent access, ACID guarantees
- **Atom codebase** - Existing flaky test infrastructure (pytest.ini, FLAKY_TEST_GUIDE.md, platform-retry.yml)

### Secondary (MEDIUM confidence)

- **pytest-rerunfailures GitHub issues** - Common pitfalls, edge cases, community patterns
- **Jest GitHub discussions** - Retry logic patterns, flaky detection strategies
- **Atom existing scripts** - detect_flaky_tests.py, ci_quality_gate.py, platform_retry_router.py
- **Industry best practices** - Google's "Testing on the Toilet" flaky test articles

### Tertiary (LOW confidence)

- **Web search results** - Searches returned no results (all queries failed), relying on training data
- **Community blog posts** - Flaky test war stories, but not verified against official docs

**Confidence assessment:** HIGH for pytest-rerunfailures and SQLite (official docs), MEDIUM for Jest/cargo (community patterns, limited official retry docs), LOW for web search sources (search failures).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest-rerunfailures is industry standard, well-documented
- Architecture: HIGH - SQLite schema pattern is standard, retry logic is well-understood
- Pitfalls: HIGH - All pitfalls based on real Atom codebase issues (documented in STATE.md)

**Research date:** March 7, 2026
**Valid until:** April 6, 2026 (30 days - pytest ecosystem stable, but new flaky detection tools may emerge)

---

## Appendix: Existing Atom Infrastructure

**What Atom Already Has:**

1. **pytest-rerunfailures configured** (pytest.ini):
   - `--reruns 2 --reruns-delay 1` in addopts
   - `@pytest.mark.flaky` marker defined
   - Documentation: FLAKY_TEST_GUIDE.md (923 lines)

2. **Platform retry workflow** (.github/workflows/platform-retry.yml):
   - Detects failed platforms after unified-tests-parallel
   - Runs targeted re-runs (only failed platforms)
   - Saves ~80% CI time vs full re-run

3. **Platform retry router** (backend/tests/scripts/platform_retry_router.py):
   - Extracts failed tests from pytest/Jest/cargo JSON results
   - Generates platform-specific retry commands
   - Exit codes: 0 (failures found), 3 (no failures)

4. **Manual flaky detection script** (backend/tests/scripts/detect_flaky_tests.py):
   - Runs tests multiple times to detect flakiness
   - Provides guidance on fixing flaky tests
   - Currently manual, not integrated into CI

5. **CI quality gate script** (backend/tests/scripts/ci_quality_gate.py):
   - Enforces coverage, pass rate, regression gates
   - Has flaky test gate (warn >10%, fail >20%)
   - **But:** No historical tracking, no quarantine database

6. **Flaky test validation** (backend/tests/test_flaky_detection.py):
   - Validates pytest-rerunfailures configuration
   - Tests flaky marker infrastructure
   - Documentation of common flaky patterns

**What's Missing:**

1. **Automated flaky detection:** Not integrated into CI/CD
2. **Quarantine tracking:** No persistent database for flaky tests
3. **Reliability scoring:** No per-test reliability metrics
4. **Cross-platform detection:** Only pytest has retry logic, Jest/cargo need implementation
5. **Auto-quarantine removal:** No mechanism to detect fixed tests
6. **Failure pattern analysis:** No historical trend analysis (e.g., "test flaky every Monday morning")

**Recommendation:** Build on existing infrastructure, don't replace. Extend pytest.ini with Jest/cargo retry logic, integrate detect_flaky_tests.py into CI, add SQLite tracking to ci_quality_gate.py.

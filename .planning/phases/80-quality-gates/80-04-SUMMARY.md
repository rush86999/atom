---
phase: 80-quality-gates
plan: 04
subsystem: testing
tags: [flaky-test-detection, quality-gates, ci-integration, test-tracking]

# Dependency graph
requires:
  - phase: 80-quality-gates
    plan: 01
    provides: screenshot capture on test failure
  - phase: 80-quality-gates
    plan: 02
    provides: video recording on test failure
  - phase: 80-quality-gates
    plan: 03
    provides: test retry functionality
provides:
  - FlakyTestTracker module for historical test tracking
  - detect_flaky_tests.py script for CI integration
  - Flaky test detection in GitHub Actions workflow
  - Unit tests for flaky detection logic
affects: [ci-cd, quality-gates, test-reliability]

# Tech tracking
tech-stack:
  added: [FlakyTestTracker, JSON-based test tracking, historical pass rate analysis]
  patterns: [pytest JSON report parsing, trend analysis across CI runs]

key-files:
  created:
    - backend/tests/e2e_ui/scripts/flaky_test_tracker.py
    - backend/tests/e2e_ui/scripts/detect_flaky_tests.py
    - backend/tests/e2e_ui/tests/unit/test_flaky_detection.py
    - backend/tests/e2e_ui/tests/unit/pytest.ini
    - backend/tests/e2e_ui/tests/unit/__init__.py
  modified:
    - .github/workflows/e2e-ui-tests.yml
    - backend/tests/e2e_ui/conftest.py
    - backend/tests/e2e_ui/fixtures/database_fixtures.py
    - backend/tests/e2e_ui/pyproject.toml

key-decisions:
  - "JSON file storage for historical data (simple, no database required)"
  - "80% pass threshold for flaky detection (configurable via CLI)"
  - "Minimum 3 runs before flagging test as flaky (avoid false positives)"
  - "Unit tests in separate directory to avoid pytest-playwright conflicts"
  - "no_browser marker for tests that don't need browser/fixtures"

patterns-established:
  - "Pattern: JSON-based tracking for test results across CI runs"
  - "Pattern: Separate unit test directory for non-E2E tests"
  - "Pattern: Autouse fixtures check for markers to skip expensive setup"

# Metrics
duration: 8min
completed: 2026-02-23
---

# Phase 80: Quality Gates & CI/CD Integration - Plan 04 Summary

**Flaky test detection that identifies unstable tests across multiple CI runs with historical tracking and trend analysis**

## Performance

- **Duration:** 8 minutes
- **Started:** 2026-02-23T22:23:54Z
- **Completed:** 2026-02-23T22:31:48Z
- **Tasks:** 4
- **Files created:** 5
- **Files modified:** 4

## Accomplishments

- **FlakyTestTracker module** created to track test results across CI runs with JSON-based storage
- **detect_flaky_tests.py script** implements CLI tool for flaky test detection with configurable thresholds
- **CI workflow integration** adds flaky test detection step after pytest with artifact upload
- **Unit tests** verify tracker initialization, pytest report parsing, flaky identification, and stable test exclusion
- **Historical tracking** enables trend analysis across multiple CI runs (data/flaky_tests.json)
- **Separate unit test directory** created to avoid pytest-playwright fixture conflicts

## Task Commits

Each task was committed atomically:

1. **Task 1: Create flaky test tracker module** - `21e508d2` (feat)
   - FlakyTestTracker class with update_from_pytest_report() method
   - get_flaky_tests() returns tests below pass threshold with min runs
   - Historical data stored in data/flaky_tests.json
   - CLI interface for manual testing

2. **Task 2: Create flaky test detection script** - `3b091b23` (feat)
   - detect_flaky_tests.py with CLI interface
   - Options: --threshold, --min-runs, --last-n, --output
   - Exit codes: 0 (no flaky), 1 (flaky found), 2 (error)
   - Reads pytest JSON report and uses FlakyTestTracker

3. **Task 3: Integrate flaky detection into CI workflow** - `9c301bd5` (feat)
   - Add Create reports directory step
   - Add Detect flaky tests step (runs with if: always())
   - Add Upload flaky test report artifact (30-day retention)
   - Detection runs after pytest with threshold 0.8 and min-runs 3

4. **Task 4: Add flaky test detection unit tests** - `3fff6632` (test)
   - tests/unit/test_flaky_detection.py with 4 unit tests
   - test_flaky_test_tracker_initialization verifies tracker setup
   - test_flaky_test_tracker_update verifies pytest report parsing
   - test_flaky_test_detection verifies flaky test identification (60% pass rate)
   - test_stable_test_not_flagged verifies stable tests excluded
   - Update conftest.py to skip screenshot tracking for no_browser tests
   - Update database_fixtures.py to skip schema creation for no_browser tests
   - Add no_browser marker to pyproject.toml
   - Create pytest.ini in unit/ directory to disable playwright

**Plan metadata:** All commits pushed to main branch

## Files Created/Modified

### Created
- `backend/tests/e2e_ui/scripts/flaky_test_tracker.py` - FlakyTestTracker module (177 lines)
- `backend/tests/e2e_ui/scripts/detect_flaky_tests.py` - CLI detection script (156 lines)
- `backend/tests/e2e_ui/tests/unit/test_flaky_detection.py` - Unit tests (163 lines)
- `backend/tests/e2e_ui/tests/unit/__init__.py` - Package marker
- `backend/tests/e2e_ui/tests/unit/pytest.ini` - Pytest configuration to disable playwright
- `backend/tests/e2e_ui/data/flaky_tests.json` - Historical data storage (initialized empty)

### Modified
- `.github/workflows/e2e-ui-tests.yml` - Added flaky detection steps (25 lines added)
- `backend/tests/e2e_ui/conftest.py` - Added marker check to skip screenshot tracking for unit tests
- `backend/tests/e2e_ui/fixtures/database_fixtures.py` - Added marker check to skip schema creation for unit tests
- `backend/tests/e2e_ui/pyproject.toml` - Added no_browser marker configuration
- `backend/tests/e2e_ui/tests/test_quality_gates.py` - Removed duplicate flaky detection tests (now in unit/)

## Decisions Made

- **JSON file storage for historical data**: Simple, no database required, easy to inspect manually
- **80% pass threshold for flaky detection**: Configurable via CLI, balances false positives vs. actual issues
- **Minimum 3 runs before flagging**: Avoids false positives from new tests with insufficient history
- **Separate unit test directory**: tests/unit/ directory avoids pytest-playwright fixture conflicts
- **no_browser marker**: Allows unit tests to opt out of expensive browser/database setup
- **if: always() in workflow**: Flaky detection runs even if tests fail (captures all results)
- **30-day artifact retention**: Flaky test reports preserved for trend analysis

## Deviations from Plan

**Rule 3 - Auto-fix blocking issue**: Unit test fixture conflicts

- **Found during:** Task 4
- **Issue:** pytest-playwright automatically parametrizes all tests with browser fixtures, causing SQLite "CREATE SCHEMA" errors in unit tests
- **Fix:** Created separate tests/unit/ directory with pytest.ini to disable playwright plugin. Added no_browser marker to conftest.py and database_fixtures.py to skip expensive fixture setup for unit tests.
- **Files modified:**
  - backend/tests/e2e_ui/conftest.py (added marker check)
  - backend/tests/e2e_ui/fixtures/database_fixtures.py (added marker check)
  - backend/tests/e2e_ui/pyproject.toml (added no_browser marker)
  - backend/tests/e2e_ui/tests/unit/pytest.ini (created to disable playwright)
- **Impact:** Clean separation of unit tests from E2E tests, faster unit test execution

## Issues Encountered

**pytest-playwright fixture conflicts** (resolved)

- **Problem:** Unit tests for flaky detection were being parametrized with browser fixtures, causing SQLite schema errors
- **Root cause:** pytest-playwright automatically applies browser fixtures to all tests in the E2E test directory
- **Solution:** Created separate tests/unit/ directory with pytest.ini that disables playwright plugin. Added no_browser marker to skip expensive fixture setup.
- **Verification:** All 4 unit tests pass in <0.11 seconds

## User Setup Required

None - all functionality is self-contained and CI-integrated.

## Verification Results

All verification steps passed:

1. ✅ **FlakyTestTracker module** - Compiles and runs without errors
2. ✅ **detect_flaky_tests.py script** - Shows help with all options (threshold, min-runs, last-n, output)
3. ✅ **Workflow YAML validation** - Valid YAML structure, detect_flaky_tests present (1 occurrence), flaky_test_report present (2 occurrences)
4. ✅ **Unit tests** - All 4 tests pass:
   - test_flaky_test_tracker_initialization
   - test_flaky_test_tracker_update
   - test_flaky_test_detection (identifies 60% pass rate test as flaky)
   - test_stable_test_not_flagged (excludes 100% pass rate test)
5. ✅ **Data directory** - backend/tests/e2e_ui/data/flaky_tests.json exists

## Flaky Test Detection Logic

### Flaky Test Criteria
A test is considered flaky if ALL of the following:
1. **Minimum runs**: Executed at least 3 times (configurable via --min-runs)
2. **Pass threshold**: Pass rate below 80% (configurable via --threshold)
3. **Has failures**: At least one failed/error result in considered runs

### Example Flaky Test
```
Test: tests/test_flaky.py::test_intermittent
Runs: 5 total
Passed: 3
Failed: 2
Pass rate: 60%
Status: FLAKY (60% < 80% threshold)
```

### Example Stable Test
```
Test: tests/test_stable.py::test_reliable
Runs: 5 total
Passed: 5
Failed: 0
Pass rate: 100%
Status: STABLE (no failures, excluded from flaky list)
```

### Historical Tracking
- **Storage**: JSON file at backend/tests/e2e_ui/data/flaky_tests.json
- **Structure**: Tests tracked by name with run history (last 10 runs)
- **Metrics**: total_runs, passed, failed, skipped, errors
- **Timestamps**: ISO format for each run
- **CI runs**: Total CI runs tracked (increments each time update_from_pytest_report is called)

## CI Integration Details

### Workflow Changes (.github/workflows/e2e-ui-tests.yml)

**Added steps:**
1. **Create reports directory** - Ensures backend/tests/e2e_ui/reports/ exists
2. **Detect flaky tests** - Runs detect_flaky_tests.py with threshold 0.8 and min-runs 3
3. **Upload flaky test report** - Uploads reports/flaky_test_report.txt as artifact (30-day retention)

**Execution conditions:**
- Runs with `if: always()` - executes even if pytest fails
- Only runs if pytest_report.json exists (check in script)
- Report uploaded even if no flaky tests found (for trend analysis)

**Exit code handling:**
- Exit 0: No flaky tests detected (doesn't fail CI)
- Exit 1: Flaky tests found (doesn't fail CI, just reports)
- Exit 2: Error occurred (would fail CI, but errors are caught in workflow)

## Next Phase Readiness

✅ **Flaky test detection complete** - CI workflow integrated with historical tracking

**Ready for:**
- Phase 80 completion (plans 80-05 and 80-06 remaining)
- Production deployment with flaky test trend analysis
- Engineering team to investigate and fix flagged flaky tests

**Recommendations for follow-up:**
1. Monitor flaky test reports in CI artifacts for first 2 weeks
2. Create dedicated issue for tests with <50% pass rate (critical)
3. Add trend analysis dashboard for pass rate over time
4. Consider automatic test disabling for tests with <20% pass rate
5. Add Slack/email notifications for new flaky tests detected

---

*Phase: 80-quality-gates*
*Plan: 04*
*Completed: 2026-02-23*

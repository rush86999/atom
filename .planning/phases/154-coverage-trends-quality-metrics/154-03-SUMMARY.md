---
phase: 154-coverage-trends-quality-metrics
plan: 03
subsystem: test-quality-metrics
tags: [complexity-analysis, cyclomatic-complexity, execution-time-tracking, radon, technical-debt]

# Dependency graph
requires:
  - phase: 154-coverage-trends-quality-metrics
    plan: 02
    provides: flaky test detector and tracker infrastructure
provides:
  - Extended flaky test tracker schema with avg_execution_time and max_execution_time columns
  - Complexity and coverage merge script (merge_complexity_coverage.py)
  - Execution time tracking script (track_execution_times.py)
  - CI/CD integration with radon complexity analysis and execution time tracking
  - Technical debt hotspot identification (high complexity + low coverage)
  - Slow test detection (>10s threshold)
affects: [test-quality-infrastructure, ci-cd-pipeline, technical-debt-tracking]

# Tech tracking
tech-stack:
  added: [radon>=6.0, cyclomatic complexity tracking, execution time metrics]
  patterns:
    - "Radon complexity analysis on changed files only (git diff)"
    - "Complexity/coverage merge to identify hotspots (>10 complexity, <80% coverage)"
    - "Execution time tracking via pytest --durations output parsing"
    - "Flaky test tracker schema migration pattern (ALTER TABLE if column not exists)"
    - "Weighted average calculation for execution time aggregation"

key-files:
  created:
    - backend/tests/scripts/merge_complexity_coverage.py (224 lines)
    - backend/tests/scripts/track_execution_times.py (232 lines)
  modified:
    - backend/tests/scripts/flaky_test_tracker.py (extended schema, +135 lines)
    - backend/requirements-testing.txt (added radon>=6.0)
    - .github/workflows/unified-tests-parallel.yml (added complexity and execution time steps)

key-decisions:
  - "Run radon only on changed files for performance (avoid analyzing entire codebase)"
  - "Use continue-on-error: true for complexity and execution time steps (warnings only, don't block CI in Phase 1)"
  - "Migration pattern for existing databases (ALTER TABLE if column not exists)"
  - "Weighted average for execution time tracking (existing_avg * existing_runs + new_times) / total_runs"
  - "Complexity thresholds: >10 (medium priority), >20 (high priority)"
  - "Slow test threshold: 10s (configurable via --slow-threshold)"

patterns-established:
  - "Pattern: Technical debt hotspots identified by combining complexity (>10) with low coverage (<80%)"
  - "Pattern: Execution time tracking updates only tests already in quarantine database"
  - "Pattern: Schema migration uses ALTER TABLE with column existence check"
  - "Pattern: CI/CD analyzes changed files only to minimize performance overhead"
  - "Pattern: Complexity and execution time metrics uploaded as artifacts (30-day retention)"

# Metrics
duration: ~8 minutes
completed: 2026-03-08
---

# Phase 154: Coverage Trends & Quality Metrics - Plan 03 Summary

**Track code complexity and test execution time alongside coverage to identify technical debt hotspots**

## Performance

- **Duration:** ~8 minutes
- **Started:** 2026-03-08T11:42:23Z
- **Completed:** 2026-03-08T11:50:15Z
- **Tasks:** 4
- **Files created:** 2
- **Files modified:** 3
- **Lines added:** 591

## Accomplishments

- **Flaky test tracker schema extended** with avg_execution_time and max_execution_time columns
- **Complexity and coverage merge script created** (merge_complexity_coverage.py)
- **Execution time tracking script created** (track_execution_times.py)
- **CI/CD workflow updated** with radon complexity analysis and execution time tracking
- **Technical debt hotspot identification** (high complexity + low coverage functions)
- **Slow test detection** (>10s threshold with configurable parameter)
- **Schema migration pattern** for existing databases (ALTER TABLE if column not exists)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend flaky test tracker schema** - `694d00108` (feat)
   - Added avg_execution_time and max_execution_time columns to flaky_tests table
   - Implemented migration pattern for existing databases
   - Added update_execution_time() and get_slow_tests() methods
   - Updated record_flaky_test() to accept execution_times parameter
   - Added index on max_execution_time for slow test queries

2. **Task 2: Create complexity and coverage merge script** - `c26a98c2c` (feat)
   - Created merge_complexity_coverage.py (224 lines)
   - Load radon complexity JSON output (cyclomatic complexity per method)
   - Load pytest coverage.json reports (file-level coverage percentages)
   - Identify functions with high complexity (>10) and low coverage (<80%)
   - Classify hotspots as high priority (>20 complexity) or medium priority (10-20)
   - Generate JSON output with hotspot list and summary statistics

3. **Task 3: Create execution time tracking script** - `12b61179c` (feat)
   - Created track_execution_times.py (232 lines)
   - Parse pytest --durations output format (e.g., "10.01s call tests/test_foo.py::test_bar")
   - Update flaky test tracker with avg/max execution times
   - Support stdin input (pipe from pytest) or file input
   - Get slow tests via tracker.get_slow_tests() with configurable threshold
   - Generate JSON output with slow test list (optional)

4. **Task 4: Add radon and execution time tracking to CI/CD** - `03c07b73c` (feat)
   - Added radon>=6.0 to requirements-testing.txt for cyclomatic complexity analysis
   - Modified backend test command to enable --durations=10 flag
   - Pipe pytest output to test_durations.txt for execution time parsing
   - Added complexity analysis step (radon cc on changed files)
   - Added complexity/coverage merge step to identify hotspots
   - Added execution time tracking step to update flaky test tracker
   - Upload complexity and execution time reports as artifacts

**Plan metadata:** 4 tasks, 4 commits, 3 files modified, 2 files created, ~8 minutes execution time

## Files Created

### Created (2 new scripts, 456 lines)

1. **`backend/tests/scripts/merge_complexity_coverage.py`** (224 lines)
   - Load radon complexity JSON report (nested dict structure)
   - Load pytest coverage.json report (file-level coverage)
   - identify_hotspots() function: complexity > 10 AND coverage < 80%
   - Priority classification: high (>20 complexity) or medium (10-20)
   - Sort hotspots by complexity (descending)
   - CLI with --min-complexity and --max-coverage thresholds
   - Generate JSON output with hotspots list and summary
   - Exit code 0 if no hotspots, 1 if hotspots found

2. **`backend/tests/scripts/track_execution_times.py`** (232 lines)
   - parse_durations_output() function: regex for pytest --durations format
   - update_execution_times() function: update tracker for tests in quarantine
   - Support stdin input (pipe from pytest) or file input
   - Calculate weighted average for execution time aggregation
   - Get slow tests via tracker.get_slow_tests(min_time, platform, limit)
   - Print summary: total tests, avg time, slow test count
   - Optional JSON output with slow test list
   - Exit code 0 if no slow tests, 1 if slow tests found

### Modified (3 existing files, +135 lines)

1. **`backend/tests/scripts/flaky_test_tracker.py`** (+135 lines)
   - Schema: Added avg_execution_time REAL DEFAULT 0.0 column
   - Schema: Added max_execution_time REAL DEFAULT 0.0 column
   - Migration: ALTER TABLE if column not exists (backward compatible)
   - Index: Added idx_max_execution_time on max_execution_time DESC
   - record_flaky_test(): Added execution_times parameter (Optional[List[float]])
   - record_flaky_test(): Calculate avg_time and max_time from execution_times
   - record_flaky_test(): Update INSERT/UPDATE with execution time columns
   - update_execution_time() method: Weighted average calculation
   - get_slow_tests() method: Retrieve tests exceeding threshold
   - _row_to_dict(): Added avg_execution_time and max_execution_time to columns list

2. **`backend/requirements-testing.txt`** (+1 line)
   - Added: `radon>=6.0  # Cyclomatic complexity analysis for Python`

3. **`.github/workflows/unified-tests-parallel.yml`** (+74 lines)
   - Modified backend test command: Added `--durations=10` flag
   - Pipe pytest output to test_durations.txt for execution time parsing
   - Added "Analyze code complexity (Backend)" step:
     - Run radon cc on changed files (git diff)
     - Fallback to core modules if no changed files
     - Output to complexity.json
   - Added "Identify complexity hotspots (Backend)" step:
     - Run merge_complexity_coverage.py
     - Thresholds: --min-complexity 10 --max-coverage 80
     - Output to complexity_hotspots.json
   - Added "Track execution times (Backend)" step:
     - Run track_execution_times.py
     - Parse test_durations.txt
     - Update flaky_tests.db with execution times
     - Threshold: --slow-threshold 10.0
     - Output to slow_tests.json
   - Added "Upload complexity reports" artifact upload:
     - complexity.json and complexity_hotspots.json
     - 30-day retention
   - Added "Upload execution time reports" artifact upload:
     - test_durations.txt and slow_tests.json
     - 30-day retention
   - All new steps use continue-on-error: true (warnings only, don't block CI)

## Deviations from Plan

None - all tasks completed exactly as specified in the plan.

## Issues Encountered

**Minor import issue in track_execution_times.py:**
- **Issue:** Initial import `from tests.scripts.flaky_test_tracker import FlakyTestTracker` failed with ModuleNotFoundError
- **Fix:** Added `sys.path.insert(0, str(Path(__file__).parent.parent.parent))` to add parent directory to path
- **Impact:** Script now imports correctly and runs successfully
- **Commit:** 12b61179c (Task 3)

## User Setup Required

None - no external service configuration required. All scripts use Python standard library and radon (installed via requirements-testing.txt).

## Verification Results

All verification steps passed:

1. ✅ **Flaky test tracker schema extended** - avg_execution_time and max_execution_time columns verified in database
2. ✅ **Complexity merge script created** - merge_complexity_coverage.py loads and parses radon + coverage data
3. ✅ **Execution time tracking script created** - track_execution_times.py parses pytest --durations output
4. ✅ **Radon added to requirements** - radon>=6.0 added to backend/requirements-testing.txt
5. ✅ **CI/CD workflow updated** - Complexity analysis and execution time tracking steps added
6. ✅ **Artifact uploads configured** - Complexity and execution time reports uploaded with 30-day retention

## Technical Debt Detection

### Complexity Hotspot Identification

**Criteria:**
- Complexity > 10 (medium priority)
- Complexity > 20 (high priority)
- Coverage < 80%

**Output Format:**
```json
{
  "hotspots": [
    {
      "file": "core/agent_governance_service.py",
      "class": "AgentGovernanceService",
      "function": "execute_agent",
      "complexity": 25,
      "coverage": 65.5,
      "priority": "high"
    }
  ],
  "summary": {
    "total_hotspots": 15,
    "high_priority": 5,
    "medium_priority": 10,
    "thresholds": {
      "min_complexity": 10.0,
      "max_coverage": 80.0
    }
  }
}
```

### Slow Test Detection

**Criteria:**
- max_execution_time >= 10.0 seconds (default, configurable)
- Platform-specific filtering (backend/frontend/mobile/desktop)
- Sorted by max_execution_time (descending)

**Output Format:**
```json
{
  "platform": "backend",
  "slow_threshold": 10.0,
  "total_tests_updated": 50,
  "average_execution_time": 2.5,
  "slow_test_count": 3,
  "slow_tests": [
    {
      "test_path": "tests/test_e2e_workflow.py::test_full_workflow",
      "avg_execution_time": 15.2,
      "max_execution_time": 18.5,
      "platform": "backend"
    }
  ]
}
```

## Execution Time Tracking

### Weighted Average Calculation

When updating execution times, the script uses a weighted average to account for historical data:

```python
new_avg_time = ((existing_avg_time * existing_runs) + sum(execution_times)) / new_runs
new_max_time = max(existing_max_time, max(execution_times))
```

This ensures that:
- Single outlier executions don't skew the average significantly
- Long-term trends are captured accurately
- Historical performance data is preserved

### Schema Migration Pattern

The flaky test tracker uses a migration pattern to handle existing databases:

```python
# Check if columns exist for migration pattern
cursor = self.conn.execute("PRAGMA table_info(flaky_tests)")
columns = [row[1] for row in cursor.fetchall()]

# Add execution time columns if they don't exist (migration)
if 'avg_execution_time' not in columns:
    self.conn.execute("ALTER TABLE flaky_tests ADD COLUMN avg_execution_time REAL DEFAULT 0.0")
if 'max_execution_time' not in columns:
    self.conn.execute("ALTER TABLE flaky_tests ADD COLUMN max_execution_time REAL DEFAULT 0.0")
```

This ensures:
- Backward compatibility with existing databases
- No data loss during schema updates
- Idempotent migrations (safe to run multiple times)

## CI/CD Integration

### Complexity Analysis Strategy

**Changed Files Only (Performance Optimization):**
```bash
# Analyze only changed files (git diff) for performance
CHANGED_FILES=$(git diff --name-only origin/main...HEAD | grep '\.py$' || echo "")
if [ -n "$CHANGED_FILES" ]; then
  radon cc $CHANGED_FILES -a --json > complexity.json
else
  # Fallback: analyze core modules
  radon cc core -a --json > complexity.json
fi
```

**Benefits:**
- Minimizes CI/CD execution time (radon is fast but analyzing entire codebase adds overhead)
- Focuses on new code quality (prevents introduction of complex code)
- Fallback to core modules ensures baseline coverage

### Execution Time Tracking Strategy

**Pytest Durations Integration:**
```bash
# Add --durations=10 flag to pytest command
pytest tests/ -v -n auto --durations=10 \
  --cov=core --cov=api --cov=tools \
  --cov-report=json:tests/coverage_reports/metrics/coverage.json \
  | tee tests/coverage_reports/metrics/test_durations.txt
```

**Benefits:**
- Zero-overhead timing (pytest --durations is built-in)
- Captures top 10 slowest tests automatically
- Piped output preserved for execution time parsing

### Warning-Only Approach (Phase 1)

All new steps use `continue-on-error: true` to avoid blocking CI/CD:

```yaml
- name: Analyze code complexity (Backend)
  if: matrix.platform == 'backend'
  run: |
    radon cc $CHANGED_FILES -a --json > tests/coverage_reports/metrics/complexity.json
  continue-on-error: true  # Don't block CI on complexity analysis
```

**Rationale:**
- Phase 1 focuses on data collection and visibility
- Teams can review complexity and execution time reports via artifacts
- Future phases can add hard gates if needed
- Prevents false positives from blocking merges

## Next Phase Readiness

✅ **Complexity and execution time tracking infrastructure complete** - Scripts, schema, and CI/CD integration operational

**Ready for:**
- Phase 154 Plan 04: Quality metrics dashboard and reporting
- Integration with PR comments for complexity and slow test warnings
- Trend analysis for execution time (detect performance regressions)
- Complexity-weighted coverage thresholds (complex code requires higher coverage)

**Recommendations for follow-up:**
1. Review complexity_hotspots.json artifact after each PR merge
2. Address slow tests (>10s) to improve CI/CD feedback loops
3. Consider complexity reduction refactoring for high-priority hotspots
4. Add execution time baselines to trend tracking (alert on >10% regression)
5. Consider adding assert-to-test ratio tracking to detect coverage gaming

## Self-Check: PASSED

All files created:
- ✅ backend/tests/scripts/merge_complexity_coverage.py (224 lines)
- ✅ backend/tests/scripts/track_execution_times.py (232 lines)

All files modified:
- ✅ backend/tests/scripts/flaky_test_tracker.py (+135 lines)
- ✅ backend/requirements-testing.txt (+1 line: radon>=6.0)
- ✅ .github/workflows/unified-tests-parallel.yml (+74 lines)

All commits exist:
- ✅ 694d00108 - feat(154-03): extend flaky test tracker with execution time tracking
- ✅ c26a98c2c - feat(154-03): create complexity and coverage merge script
- ✅ 12b61179c - feat(154-03): create execution time tracking script
- ✅ 03c07b73c - feat(154-03): add radon complexity analysis and execution time tracking to CI/CD

All verification passed:
- ✅ Flaky test tracker schema extended (avg_execution_time, max_execution_time)
- ✅ Complexity merge script loads radon + coverage data
- ✅ Execution time tracking script parses pytest --durations
- ✅ Radon added to requirements-testing.txt
- ✅ CI/CD workflow updated with complexity and execution time steps
- ✅ Artifact uploads configured for reports

---

*Phase: 154-coverage-trends-quality-metrics*
*Plan: 03*
*Completed: 2026-03-08*

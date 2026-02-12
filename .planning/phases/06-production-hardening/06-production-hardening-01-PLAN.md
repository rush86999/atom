---
phase: 06-production-hardening
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/test_performance_baseline.py
  - backend/tests/test_flaky_detection.py
  - backend/tests/test_isolation_validation.py
  - backend/tests/coverage_reports/metrics/performance_baseline.json
  - backend/tests/coverage_reports/metrics/bug_triage_report.md
autonomous: true

must_haves:
  truths:
    - "Full test suite executes without blocking errors"
    - "All failing tests are documented with error details"
    - "Performance baseline is measured and documented"
    - "Flaky tests are identified and categorized by root cause"
    - "Bug triage report is generated with severity levels"
  artifacts:
    - path: "backend/tests/coverage_reports/metrics/performance_baseline.json"
      provides: "Execution time metrics for full test suite"
    - path: "backend/tests/coverage_reports/metrics/bug_triage_report.md"
      provides: "Documented bugs with P0/P1/P2/P3 severity"
    - path: "backend/tests/test_performance_baseline.py"
      provides: "Performance baseline validation tests"
    - path: "backend/tests/test_flaky_detection.py"
      provides: "Flaky test detection validation"
    - path: "backend/tests/test_isolation_validation.py"
      provides: "Test isolation validation"
  key_links:
    - from: "pytest tests/ -n auto --durations=20"
      to: "performance_baseline.json"
      via: "test execution measurement"
      pattern: "pytest.*--durations"
    - from: "bug_triage_report.md"
      to: "06-production-hardening-02-PLAN.md"
      via: "prioritized bug fixes"
      pattern: "P0|P1|P2|P3"
---

<objective>
Run full test suite to discover all blocking issues, establish performance baseline, and create bug triage report with severity-based prioritization.

**Purpose:** Phase 6 is production hardening - we need to run the complete test suite (property + integration + platform) to identify all bugs, measure execution time for performance baselining, and create a comprehensive bug triage report with severity levels (P0/P1/P2/P3) and SLA targets.

**Output:**
- `performance_baseline.json` - Test suite execution time metrics
- `bug_triage_report.md` - Documented bugs with severity and priority
- Updated baseline tests with actual execution metrics
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/06-production-hardening/06-RESEARCH.md

# Only reference prior plan SUMMARYs if genuinely needed
@/Users/rushiparikh/projects/atom/backend/pytest.ini
@/Users/rushiparikh/projects/atom/backend/tests/README.md
@/Users/rushiparikh/projects/atom/backend/tests/property_tests/INVARIANTS.md
</context>

<tasks>

<task type="auto">
  <name>Run Full Test Suite with Performance Measurement</name>
  <files>backend/tests/coverage_reports/metrics/performance_baseline.json</files>
  <action>
Execute full test suite with performance profiling:

1. From backend directory, run: `time pytest tests/ -v -n auto --durations=20 --tb=short 2>&1 | tee tests/coverage_reports/metrics/test_execution.log`
2. Capture execution time metrics:
   - Total suite execution time
   - Top 20 slowest tests with durations
   - Pass/fail counts by test category
   - Flaky test retry count (from pytest-rerunfailures output)
3. Create `performance_baseline.json` with structure:
   ```json
   {
     "timestamp": "2026-02-11T...Z",
     "execution_time_seconds": <total>,
     "test_count": <total>,
     "passed": <passed>,
     "failed": <failed>,
     "flaky_retries": <count>,
     "slowest_tests": [
       {"test": "path::test_name", "duration": 1.234},
       ...
     ],
     "target_full_suite": 300,
     "target_property_test": 1.0,
     "targets_met": {
       "full_suite_under_5min": <boolean>,
       "property_tests_under_1s": <boolean>
     }
   }
   ```

4. Update `test_performance_baseline.py` with actual measured values:
   - Replace skip() placeholders with real assertions using measured data
   - Document which tests exceed 1s threshold
   - Document serial vs parallel speedup achieved

**DO NOT**: Exit on test failures - continue to capture all bugs
  </action>
  <verify>File exists at backend/tests/coverage_reports/metrics/performance_baseline.json with valid JSON containing execution_time_seconds, test_count, slowest_tests array</verify>
  <done>Full test suite executed with documented execution time, slowest tests identified, and performance targets compared against baseline (<5min full suite, <1s per property test)</done>
</task>

<task type="auto">
  <name>Create Bug Triage Report with Severity Levels</name>
  <files>backend/tests/coverage_reports/metrics/bug_triage_report.md</files>
  <action>
Parse test execution log and create comprehensive bug triage report:

1. Extract all test failures from `test_execution.log`
2. Categorize each failure by severity per RESEARCH.md:

**P0 (Critical) - SLA <24h:**
- Security vulnerabilities (JWT bypass, SQL injection, path traversal)
- Data loss/corruption (database transaction failures, rollback issues)
- Cost leaks (unbounded API calls, infinite loops)

**P1 (High) - SLA <72h:**
- Financial incorrectness (wrong calculations, accounting errors)
- System crashes (unhandled exceptions, OOM errors)
- Data integrity (constraint violations, foreign key errors)

**P2 (Medium) - SLA <1 week:**
- Test gaps (missing coverage for edge cases)
- Incorrect behavior (wrong return values, state mismatches)
- Performance issues (tests >1s, slow queries)

**P3 (Low) - SLA <2 weeks:**
- Code quality (non-idiomatic patterns, inconsistent naming)
- Documentation (missing docstrings, unclear test names)

3. Create `bug_triage_report.md` with:
```markdown
# Bug Triage Report - Phase 6
**Generated:** 2026-02-11
**Test Suite Execution:** <N> tests, <P> passed, <F> failed

## Severity Summary
| Severity | Count | SLA Target |
|----------|-------|-------------|
| P0 (Critical) | X | <24h |
| P1 (High) | X | <72h |
| P2 (Medium) | X | <1 week |
| P3 (Low) | X | <2 weeks |

## P0 Bugs (Fix Immediately)

### BUG-001: <Title>
- **Severity:** P0 - <Category>
- **SLA:** Fix by <datetime>
- **Test:** tests/path/to/test_file.py::test_function
- **Error:** <Assertion/Exception message>
- **Root Cause:** <Analysis>
- **Reproduction:**
  ```bash
  pytest tests/path/to/test_file.py::test_function -v
  ```
- **Fix Strategy:** <What needs to be done>

[... repeat for each P0 bug]

## P1 Bugs (High Priority)

[... same structure for P1 bugs]
```

4. Cross-reference with existing VALIDATED_BUG sections in INVARIANTS.md to identify if failures are new or known issues
  </action>
  <verify>File exists at backend/tests/coverage_reports/metrics/bug_triage_report.md with P0/P1/P2/P3 sections, bug count summary table, and at least one entry per failed test</verify>
  <done>All test failures documented with severity levels (P0-P3), SLA targets assigned, reproduction steps provided, and fix strategies outlined for critical bugs</done>
</task>

<task type="auto">
  <name>Update Baseline Tests with Actual Metrics</name>
  <files>backend/tests/test_performance_baseline.py</files>
  <action>
Enhance baseline test file with real measured data:

1. Update `test_full_suite_execution_time`:
   - Replace skip() with: `assert measured_time < 300, f"Full suite took {measured_time}s, target <300s"`
   - Add test data load from performance_baseline.json

2. Update `test_property_test_performance`:
   - Parse slowest_tests from baseline
   - Assert all property tests <1s or document why slower

3. Add new test class `TestPerformanceRegressionDetection`:
   ```python
   class TestPerformanceRegressionDetection:
       """Detect performance regressions from baseline."""

       def test_no_regression_from_baseline(self):
           """Test that execution time hasn't regressed >20% from baseline."""
           baseline = load_baseline()
           current = measure_current_suite_time()

           regression_threshold = baseline["execution_time_seconds"] * 1.2
           assert current < regression_threshold,
               f"Performance regression: {current}s > {regression_threshold}s"
   ```

4. Update documentation examples with actual measured values
  </action>
  <verify>test_performance_baseline.py updated with real assertions (not skip placeholders), loads data from performance_baseline.json, and includes regression detection test</verify>
  <done>Baseline tests use actual measured values, performance regression detection implemented, and documentation reflects real execution characteristics</done>
</task>

</tasks>

<verification>
Run `pytest tests/test_performance_baseline.py -v` to verify baseline tests pass with real metrics. Run `pytest tests/test_flaky_detection.py -v` to verify flaky detection infrastructure. Check `bug_triage_report.md` exists and contains all failed tests with severity levels.
</verification>

<success_criteria>
1. Full test suite executed with comprehensive logging (time pytest tests/ -v -n auto --durations=20)
2. Performance baseline JSON created with execution time, slowest tests, and target comparisons
3. Bug triage report created with P0/P1/P2/P3 severity classification
4. All blocking errors documented with reproduction steps
5. Performance baseline tests updated with real measured values (not skip placeholders)
</success_criteria>

<output>
After completion, create `.planning/phases/06-production-hardening/06-production-hardening-01-SUMMARY.md` with:
- Total execution time measured
- Number of bugs discovered by severity
- Slowest tests identified
- Performance targets met or not
- Bug triage report summary
</output>

---
phase: 10-fix-tests
plan: 04
type: execute
wave: 2
depends_on: ["10-fix-tests-01", "10-fix-tests-02", "10-fix-tests-03"]
files_modified:
  - .planning/phases/10-fix-tests/10-fix-tests-04-SUMMARY.md
autonomous: true

must_haves:
  truths:
    - Full test suite executes in <60 minutes (TQ-03 requirement)
    - No flaky tests detected across 3 consecutive runs (TQ-04 requirement)
    - Test execution time is documented and measured
  artifacts:
    - path: ".planning/phases/10-fix-tests/10-fix-tests-04-SUMMARY.md"
      provides: "Test suite execution time and flakiness report"
      contains: "execution_time"
  key_links:
    - from: "pytest"
      to: "test suite"
      via: "test execution"
      pattern: "pytest tests/"
---

<objective>
Verify test suite performance and stability (TQ-03 and TQ-04)

**Purpose**: Phase 10 requirements state that (TQ-03) the test suite must run in <60 minutes and (TQ-04) have no flaky tests across 3 consecutive runs. This plan measures and verifies both requirements.

**TQ-03**: Test suite runs successfully in <60 minutes
**TQ-04**: No flaky tests across 3 consecutive runs

**Output**: Documented test execution time and flakiness report
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@.planning/ROADMAP.md
</execution_context>

<context>
@.planning/ROADMAP.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Measure full test suite execution time (TQ-03)</name>
  <files>tests/</files>
  <action>
Run the full test suite and measure execution time:

1. Start timer
2. Run: `PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ -v --tb=short`
3. Record execution time from pytest output (look for "X.XXs" or similar timing)
4. Count total tests passed/failed/skipped

**Command**:
```bash
time PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ -v --tb=short --maxfail=50 2>&1 | tee /tmp/test_run_1.txt
```

**Expected**: All tests complete, execution time recorded
**Acceptance**: Time < 60 minutes (3600 seconds)

**If >60 minutes**:
- Note which test modules take longest
- Identify potential optimizations (e.g., better parallelization, skipping slow tests)
- Document findings for future improvement
</action>
  <verify>
# Check execution time from pytest output
grep -E "collected|passed|failed|in [0-9]" /tmp/test_run_1.txt | tail -5
Expected: "in XXX.XXs" where XXX < 60.00 (minutes) or total time < 3600 seconds
</verify>
  <done>
Full test suite execution measured and documented. Time is <60 minutes or optimization plan documented.
</done>
</task>

<task type="auto">
  <name>Task 2: Run test suite 3 times to detect flaky tests (TQ-04)</name>
  <files>tests/</files>
  <action>
Run the test suite 3 times and compare results to detect flakiness:

1. **Run 1**: Already completed in Task 1, save results
2. **Run 2**: `PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ --tb=no -q 2>&1 | tee /tmp/test_run_2.txt`
3. **Run 3**: `PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ --tb=no -q 2>&1 | tee /tmp/test_run_3.txt`

**Compare results**:
```bash
# Extract test counts
echo "Run 1:" && grep -E "passed|failed" /tmp/test_run_1.txt | tail -1
echo "Run 2:" && grep -E "passed|failed" /tmp/test_run_2.txt | tail -1
echo "Run 3:" && grep -E "passed|failed" /tmp/test_run_3.txt | tail -1
```

**Flaky test definition**:
- Test passes in some runs but fails in others
- Test fails intermittently with same code

**If flaky tests found**:
- List which tests are flaky
- Identify the pattern (timing, resource contention, etc.)
- Document for resolution

**Acceptance**: All 3 runs have identical pass/fail counts
</action>
  <verify>
# Compare results across 3 runs
grep -h "passed.*failed" /tmp/test_run_*.txt | sort | uniq -c
Expected: All 3 runs show identical results (3 occurrences of same count)
</verify>
  <done>
Test suite run 3 times with consistent results. No flaky tests detected, or flaky tests documented.
</done>
</task>

<task type="auto">
  <name>Task 3: Document test suite performance and stability report</name>
  <files>.planning/phases/10-fix-tests/10-fix-tests-04-SUMMARY.md</files>
  <action>
Create summary report with execution time and flakiness findings:

**Report contents**:
1. **Execution Time** (TQ-03):
   - Total time for full test suite
   - Pass/fail/skip counts
   - Meets <60 minute requirement: YES/NO

2. **Flakiness Analysis** (TQ-04):
   - Results from 3 consecutive runs
   - Consistent results: YES/NO
   - Flaky tests identified (if any): list

3. **Recommendations**:
   - If >60 minutes: suggestions for optimization
   - If flaky tests found: suggestions for fixing

4. **Test Suite Health**: Overall assessment (HEALTHY/NEEDS ATTENTION)
</action>
  <verify>
cat .planning/phases/10-fix-tests/10-fix-tests-04-SUMMARY.md | grep -E "Execution Time|Flakiness|HEALTHY"
Expected: Report exists with all required sections
</verify>
  <done>
Test suite performance and stability report created with clear TQ-03 and TQ-04 status.
</done>
</task>

</tasks>

<verification>
1. Execution time measured and <60 minutes confirmed (or optimization plan documented)
2. 3 test runs completed with consistent results (no flakiness)
3. Summary report documents all findings clearly
</verification>

<success_criteria>
- TQ-03: Test suite runs in <60 minutes OR clear path to <60 minutes documented
- TQ-04: No flaky tests across 3 runs OR all flaky tests identified and documented
- Report created with clear PASS/FAIL status for each requirement
</success_criteria>

<output>
After completion, `.planning/phases/10-fix-tests/10-fix-tests-04-SUMMARY.md` contains:
- TQ-03 status: PASS/FAIL with execution time
- TQ-04 status: PASS/FAIL with flakiness analysis
- Recommendations for any failures
</output>

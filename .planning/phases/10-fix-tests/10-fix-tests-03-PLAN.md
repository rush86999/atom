---
phase: 10-fix-tests
plan: 03
type: execute
wave: 2
depends_on: ["10-fix-tests-01", "10-fix-tests-02"]
files_modified:
  - .planning/phases/10-fix-tests/10-fix-tests-03-SUMMARY.md
autonomous: true

must_haves:
  truths:
    - Full test suite run 3 times with >= 98% pass rate each time (TQ-02 requirement)
    - Pass rate calculated as (passed / (passed + failed)) * 100
    - Skipped tests excluded from pass rate calculation
  artifacts:
    - path: ".planning/phases/10-fix-tests/10-fix-tests-03-SUMMARY.md"
      provides: "Pass rate verification report"
      contains: "pass_rate"
  key_links:
    - from: "pytest"
      to: "test suite"
      via: "test execution"
      pattern: "pytest tests/"
---

<objective>
Verify 98%+ test pass rate (TQ-02)

**Purpose**: Phase 10 requirement TQ-02 states the test suite must achieve >= 98% pass rate. This plan runs the full test suite 3 times and verifies the pass rate meets the requirement.

**TQ-02**: Test suite achieves >= 98% pass rate across 3 consecutive runs

**Calculation**: pass_rate = (passed / (passed + failed)) * 100

**Output**: Documented pass rate verification report
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
  <name>Task 1: Run full test suite 3 times and collect pass/fail counts</name>
  <files>tests/</files>
  <action>
Run the full test suite 3 times to measure consistent pass rate:

**Note**: Property test collection errors (from Plan 01) and other test fixes (from Plan 02) must be complete first.

**Commands**:
```bash
# Run 1
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ --tb=no -q 2>&1 | tee /tmp/pass_rate_run_1.txt

# Run 2
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ --tb=no -q 2>&1 | tee /tmp/pass_rate_run_2.txt

# Run 3
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ --tb=no -q 2>&1 | tee /tmp/pass_rate_run_3.txt
```

**Extract metrics**:
```bash
# Get counts from each run
for i in 1 2 3; do
  echo "Run $i:"
  grep -E "passed|failed|skipped" /tmp/pass_rate_run_$i.txt | tail -1
done
```
</action>
  <verify>
# Verify we have 3 complete test runs
ls -la /tmp/pass_rate_run_*.txt 2>&1 | wc -l
Expected: 3 files exist
</verify>
  <done>
Full test suite run 3 times with results saved to /tmp/pass_rate_run_*.txt
</done>
</task>

<task type="auto">
  <name>Task 2: Calculate pass rate for each run</name>
  <files>.planning/phases/10-fix-tests/10-fix-tests-03-SUMMARY.md</files>
  <action>
Calculate pass rate for each run using the formula:
pass_rate = (passed / (passed + failed)) * 100

**Parse each run output**:
```bash
# Example output: "10176 passed, 50 failed, 100 skipped"
# Extract counts and calculate:
# pass_rate = 10176 / (10176 + 50) * 100 = 99.51%
```

**For each run**:
1. Extract passed count (e.g., 10176)
2. Extract failed count (e.g., 50)
3. Calculate: (passed / (passed + failed)) * 100
4. Document result

**Acceptance criteria**:
- Each run must have pass_rate >= 98.0%
- If any run is below 98%, the requirement fails
</action>
  <verify>
# Manual calculation check:
# If run has 10176 passed, 50 failed:
# echo "scale=2; 10176 / (10176 + 50) * 100" | bc
# Expected: ~99.51% (above 98% threshold)
</verify>
  <done>
Pass rates calculated for all 3 runs. Each run verified against 98% threshold.
</done>
</task>

<task type="auto">
  <name>Task 3: Document pass rate verification report</name>
  <files>.planning/phases/10-fix-tests/10-fix-tests-03-SUMMARY.md</files>
  <action>
Create pass rate verification report with:

**Report contents**:
1. **Run 1 Results**:
   - Passed: X
   - Failed: Y
   - Skipped: Z
   - Pass Rate: XX.XX%

2. **Run 2 Results**:
   - Passed: X
   - Failed: Y
   - Skipped: Z
   - Pass Rate: XX.XX%

3. **Run 3 Results**:
   - Passed: X
   - Failed: Y
   - Skipped: Z
   - Pass Rate: XX.XX%

4. **Overall Assessment**:
   - Average Pass Rate: XX.XX%
   - Meets 98% threshold: YES/NO
   - Consistency: Variance between runs

5. **If below 98%**:
   - List failing tests
   - Identify patterns (module, test type)
   - Recommend fixes

6. **TQ-02 Status**: PASS/FAIL
</action>
  <verify>
cat .planning/phases/10-fix-tests/10-fix-tests-03-SUMMARY.md | grep -E "Pass Rate|TQ-02|PASS|FAIL"
Expected: Report exists with pass rates for all 3 runs and final TQ-02 status
</verify>
  <done>
Pass rate verification report created with clear TQ-02 PASS/FAIL status.
</done>
</task>

</tasks>

<verification>
1. All 3 test runs completed successfully
2. Pass rate calculated for each run using formula: (passed / (passed + failed)) * 100
3. Report documents TQ-02 status clearly
</verification>

<success_criteria>
- TQ-02: PASS if all 3 runs have >= 98% pass rate
- TQ-02: FAIL if any run has < 98% pass rate (with failing tests documented)
- Report created with detailed breakdown
</success_criteria>

<output>
After completion, `.planning/phases/10-fix-tests/10-fix-tests-03-SUMMARY.md` contains:
- Pass rate for each of 3 runs
- Average pass rate
- TQ-02 status: PASS or FAIL
- List of failing tests if below threshold
</output>

---
phase: 10-fix-tests
plan: 08
type: execute
wave: 2
depends_on:
  - phase: 10-fix-tests
    plan: 06
    provides: Fixed agent task cancellation tests
  - phase: 10-fix-tests
    plan: 07
    provides: Fixed security config and governance runtime tests
files_modified:
  - pytest.ini
  - .planning/phases/10-fix-tests/10-fix-tests-08-SUMMARY.md
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Test suite completes in <60 minutes (TQ-03 requirement)"
    - "Test suite has no flaky tests across 3 consecutive runs (TQ-04 requirement)"
    - "pytest.ini optimized for execution speed (removed --reruns, -q instead of -v)"
    - "All 5 previously flaky tests pass consistently without RERUN loops"
  artifacts:
    - path: "pytest.ini"
      provides: "Optimized pytest configuration for fast execution"
      contains: "addopts = -q --tb=line --maxfail=10"
    - path: ".planning/phases/10-fix-tests/10-fix-tests-08-SUMMARY.md"
      provides: "TQ-03/TQ-04 validation report"
      contains: "Test execution time|Flaky test variance"
  key_links:
    - from: "pytest.ini"
      to: "pytest command line"
      via: "addopts configuration"
      pattern: "addopts.*-q.*--maxfail"
    - from: "tests/test_agent_cancellation.py"
      to: "pytest test runner"
      via: "test collection"
      pattern: "collected.*items"
    - from: ".planning/phases/10-fix-tests/10-fix-tests-08-SUMMARY.md"
      to: "Phase 10 verification"
      via: "validation results"
      pattern: "TQ-03|TQ-04"
---

<objective>
Validate TQ-03 (<60 minute execution time) and TQ-04 (no flaky tests across 3 runs) requirements after fixing all identified flaky tests.

**Purpose:** Plans 06 and 07 fixed 5 flaky tests. This plan validates that those fixes enable the test suite to meet quality requirements:
- TQ-03: Test suite completes in <60 minutes
- TQ-04: No flaky tests across 3 consecutive runs

**Root Causes Addressed (from Plans 06-07):**
1. AgentTaskRegistry singleton now resets between tests (Plan 06)
2. Environment variables isolated via monkeypatch fixture (Plan 07)
3. BYOK client and governance cache mocked (Plan 07)
4. UUID-based test IDs prevent collisions (Plan 06)

**Output:**
- Optimized pytest.ini configuration for faster execution
- Validation report with execution time and flakiness metrics
- Confirmation that TQ-03 and TQ-04 requirements are met
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/10-fix-tests/10-fix-tests-06-PLAN.md
@.planning/phases/10-fix-tests/10-fix-tests-07-PLAN.md
@.planning/phases/10-fix-tests/10-fix-tests-05-SUMMARY.md

# Quality Requirements (from ROADMAP.md)

**TQ-03:** Test suite completes in <60 minutes
- Target: <60 minutes for full test suite
- Current baseline: 60-120 minutes with flaky tests (Plan 05)
- Goal: <60 minutes after flaky test fixes

**TQ-04:** No flaky tests across 3 runs
- Target: 0 variance in pass/fail counts across 3 consecutive runs
- Current baseline: 5+ flaky tests with RERUN loops (Plan 05)
- Goal: 0 flaky tests after fixes

# Current pytest.ini Configuration (inefficient)

```ini
addopts = -v --strict-markers --tb=short --reruns 3 --reruns-delay 1 --ignore=... --cov=... --showlocals
```

Issues:
- `-v` (verbose) adds overhead for 10K+ tests
- `--reruns 3` masks flaky tests instead of fixing them
- `--showlocals` increases memory footprint
- Coverage collection during test run slows execution

# Expected Improvement After Plans 06-07

Previously flaky tests (should now pass consistently):
- test_unregister_task (Plan 06: UUID IDs, registry reset)
- test_register_task (Plan 06: UUID IDs, registry reset)
- test_get_all_running_agents (Plan 06: registry cleanup via fixture)
- test_default_secret_key_in_development (Plan 07: monkeypatch fixture)
- test_agent_governance_gating (Plan 07: mocked BYOK and cache)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Optimize pytest.ini configuration for speed</name>
  <files>pytest.ini</files>
  <action>
    Update pytest.ini addopts to remove slow options while maintaining test quality.

    Current addopts (line 55):
    ```ini
    addopts = -v --strict-markers --tb=short --reruns 3 --reruns-delay 1 --ignore=... --cov=... --showlocals
    ```

    New addopts (optimized for speed):
    ```ini
    addopts = -q --strict-markers --tb=line --maxfail=10 --ignore=tests/integration/episodes/test_lancedb_integration.py --ignore=tests/integration/episodes/test_graduation_validation.py --ignore=tests/integration/episodes/test_episode_lifecycle_lancedb.py --ignore=tests/integration/governance/test_graduation_exams.py --ignore=tests/unit/test_agent_integration_gateway.py
    ```

    Changes:
    1. `-v` → `-q` (quiet mode, much faster for 10K+ tests)
    2. `--tb=short` → `--tb=line` (one line per failure, faster)
    3. Remove `--reruns 3 --reruns-delay 1` (flaky tests fixed in Plans 06-07)
    4. Add `--maxfail=10` (stop early after 10 failures to save time)
    5. Remove `--showlocals` (reduce memory)
    6. Remove `--cov=... --cov-report=...` from addopts (run coverage separately)

    Keep:
- `--strict-markers` (catch typos in marker names)
- All `--ignore` patterns (tests that require special setup)

    DO NOT:
    - Remove any --ignore patterns (those tests need special setup)
    - Change asyncio_mode, testpaths, or other sections
    - Modify marker definitions
  </action>
  <verify>
    Run: `PYTHONPATH=. pytest --collect-only | tail -1`
    Expected: Still collects 10,513 tests (optimization shouldn't change collection)
  </verify>
  <done>
    pytest.ini uses -q mode, no --reruns, --maxfail=10 for faster execution
  </done>
</task>

<task type="auto">
  <name>Task 2: Validate previously flaky tests pass consistently</name>
  <files>.planning/phases/10-fix-tests/10-fix-tests-08-SUMMARY.md</files>
  <action>
    Run the 5 previously flaky tests 3 times to verify they now pass consistently.

    Execute:
    ```bash
    cd /Users/rushiparikh/projects/atom/backend

    # Run 3 times, capturing output
    for run in 1 2 3; do
      echo "=== Run $run ==="
      PYTHONPATH=. pytest \
        tests/test_agent_cancellation.py::TestTaskCleanup::test_unregister_task \
        tests/test_agent_cancellation.py::TestAgentTaskRegistry::test_register_task \
        tests/test_agent_cancellation.py::TestTaskCancellation::test_get_all_running_agents \
        tests/test_security_config.py::TestSecurityConfig::test_default_secret_key_in_development \
        tests/test_agent_governance_runtime.py::test_agent_governance_gating \
        -v --tb=short
    done
    ```

    Record in SUMMARY.md:
    1. Pass/fail count for each run
    2. Any RERUN messages (should be 0)
    3. Total execution time for each run
    4. Variance calculation: (max_count - min_count) / expected_count

    DO NOT:
    - Proceed to full test suite if any test fails (fix first)
    - Count warnings as failures (only actual test failures)
  </action>
  <verify>
    Check SUMMARY.md contains:
    - "Run 1: 5 passed"
    - "Run 2: 5 passed"
    - "Run 3: 5 passed"
    - "Variance: 0%"
  </verify>
  <done>
    All 5 previously flaky tests pass 3 times consecutively with 0% variance
  </done>
</task>

<task type="auto">
  <name>Task 3: Measure full test suite execution time (TQ-03 validation)</name>
  <files>.planning/phases/10-fix-tests/10-fix-tests-08-SUMMARY.md</files>
  <action>
    Run the full test suite with optimized configuration and measure execution time.

    Execute with timeout:
    ```bash
    cd /Users/rushiparikh/projects/atom/backend

    # Run with timeout and timing
    start_time=$(date +%s)
    PYTHONPATH=. pytest tests/ -q --tb=line --maxfail=10 \
      --ignore=tests/integration/episodes/test_lancedb_integration.py \
      --ignore=tests/integration/episodes/test_graduation_validation.py \
      --ignore=tests/integration/episodes/test_episode_lifecycle_lancedb.py \
      --ignore=tests/integration/governance/test_graduation_exams.py \
      --ignore=tests/unit/test_agent_integration_gateway.py \
      2>&1 | tee /tmp/pytest_run.log
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    echo "Execution time: $duration seconds"
    ```

    Record in SUMMARY.md:
    1. Total execution time in minutes and seconds
    2. Pass/fail/skip counts
    3. Percentage of TQ-03 requirement: `min(60, duration) / 60 * 100`
    4. If >60 minutes: document how much over and identify bottlenecks

    If duration <60 minutes: TQ-03 ✅ MET
    If duration >60 minutes: TQ-03 ❌ NOT MET (but note improvement from Plan 05 baseline)

    DO NOT:
    - Run coverage during this measurement (adds significant overhead)
    - Stop early if <60 minutes elapsed (let it complete for accurate measurement)
    - Include ignored tests in scope calculation
  </action>
  <verify>
    Check SUMMARY.md contains:
    - "Execution time: XX minutes YY seconds"
    - "TQ-03 (<60 min): ✅ MET" or "❌ NOT MET"
    - Pass/fail/skip counts
  </verify>
  <done>
    Full test suite execution time measured and compared against TQ-03 requirement
  </done>
</task>

</tasks>

<verification>
After completion, verify:

1. pytest.ini is optimized:
   ```bash
   grep "^addopts" pytest.ini
   ```
   Expected: Contains `-q`, `--tb=line`, `--maxfail=10`, no `--reruns`

2. Previously flaky tests are stable:
   ```bash
   PYTHONPATH=. pytest tests/test_agent_cancellation.py tests/test_security_config.py tests/test_agent_governance_runtime.py -q --tb=line
   ```
   Expected: All 19 tests pass, no RERUN messages

3. SUMMARY.md documents TQ-03 and TQ-04 results with:
   - Execution time in minutes
   - Flaky test variance percentage
   - Clear PASS/FAIL status for each requirement
</verification>

<success_criteria>
1. pytest.ini optimized (no --reruns, -q mode, --maxfail=10)
2. All 5 previously flaky tests pass 3 consecutive runs (0% variance)
3. Full test suite execution time measured
4. TQ-03 and TQ-04 status clearly documented (MET or NOT MET)
5. If TQ-03 not met, documented improvement from baseline (60-120 min → actual)
</success_criteria>

<output>
After completion, create `.planning/phases/10-fix-tests/10-fix-tests-08-SUMMARY.md`

Include:
- TQ-03 validation result (execution time, PASS/FAIL)
- TQ-04 validation result (flaky test variance, PASS/FAIL)
- pytest.ini optimization changes
- Comparison to Plan 05 baseline
- Recommendations if requirements not met (e.g., separate test suites, tiering)
</output>

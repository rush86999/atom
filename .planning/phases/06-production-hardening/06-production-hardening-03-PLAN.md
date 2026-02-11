---
phase: 06-production-hardening
plan: 03
type: execute
wave: 3
depends_on: [06-production-hardening-01]
files_modified:
  - backend/tests/property_tests/test_event_handling_invariants.py
  - backend/tests/property_tests/test_state_management_invariants.py
  - backend/tests/property_tests/test_episode_segmentation_invariants.py
  - backend/tests/property_tests/test_api_contracts_invariants.py
  - backend/tests/integration/test_websocket_integration.py
  - backend/tests/integration/test_api_integration.py
  - backend/pytest.ini
autonomous: true

must_haves:
  truths:
    - "All flaky tests are identified and categorized by root cause"
    - "Flaky tests have root cause fixes applied"
    - "@pytest.mark.flaky markers are removed after fixes"
    - "Tests run consistently 10 times without failures"
    - "Parallel execution produces same results as serial"
  artifacts:
    - path: "backend/tests/flaky_test_audit.md"
      provides: "Categorized flaky tests with root causes"
    - path: "backend/tests/property_tests/test_event_handling_invariants.py"
      provides: "Fixed flaky event handling tests"
    - path: "backend/tests/integration/test_websocket_integration.py"
      provides: "Fixed flaky WebSocket tests"
    - path: "backend/pytest.ini"
      provides: "Updated flaky test marker count (should be zero)"
  key_links:
    - from: "06-production-hardening-01-PLAN.md"
      to: "06-production-hardening-03-PLAN.md"
      via: "flaky tests identified"
      pattern: "flaky|intermittent|race"
    - from: "backend/tests"
      to: "backend/tests"
      via: "async coordination fixes"
      pattern: "asyncio\\.gather|await.*async"
    - from: "pytest.ini"
      to: "backend/tests"
      via: "pytest.mark.flaky removal"
      pattern: "@pytest\\.mark\\.flaky"
---

<objective>
Eliminate all flaky tests by identifying root causes and fixing them, achieving zero @pytest.mark.flaky markers and stable test execution across 10 consecutive runs.

**Purpose:** Flaky tests mask real issues and cause CI unreliability. This plan addresses the root causes (race conditions, async issues, shared state, time dependencies) rather than masking with retries, ensuring test suite reliability for production deployment.

**Output:**
- Fixed flaky tests with root cause corrections
- Zero @pytest.mark.flaky markers in codebase
- `flaky_test_audit.md` documenting fixes
- Stable test execution (10 consecutive runs produce identical results)
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/06-production-hardening/06-RESEARCH.md
@.planning/phases/06-production-hardening/06-production-hardening-01-SUMMARY.md
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Existing flaky test documentation
@/Users/rushiparikh/projects/atom/backend/tests/docs/FLAKY_TEST_GUIDE.md
@/Users/rushiparikh/projects/atom/backend/tests/test_flaky_detection.py
@/Users/rushiparikh/projects/atom/backend/pytest.ini
</context>

<tasks>

<task type="auto">
  <name>Audit and Categorize Flaky Tests</name>
  <files>backend/tests/flaky_test_audit.md</files>
  <action>
Audit all @pytest.mark.flaky markers and categorize by root cause:

1. Search for all flaky markers:
   ```bash
   grep -r "@pytest.mark.flaky" backend/tests/ --include="*.py"
   ```

2. For each flaky test, categorize root cause:
   - **Race condition**: Parallel execution conflicts, shared state
   - **Async issue**: Missing await, incorrect asyncio usage
   - **Time dependency**: Depends on current time, not mocked
   - **External dependency**: Real network/database calls not mocked
   - **Non-deterministic data**: Random values without fixed seed
   - **Fixture issue**: Improper setup/teardown

3. Create `flaky_test_audit.md`:
   ```markdown
   # Flaky Test Audit - Phase 6
   **Generated:** 2026-02-11
   **Total Flaky Tests:** <N>

   ## By Root Cause

   ### Race Conditions (<N>)
   | Test | Path | Issue |
   |-------|------|-------|
   | test_name | tests/path.py | Description |

   ### Async Coordination Issues (<N>)
   [... same structure ...]

   ### Time Dependencies (<N>)
   [...]

   ## Fix Plan
   1. Race conditions: Add unique_resource_name, use proper locking
   2. Async: Add missing await, use asyncio.gather
   3. Time: Mock with freezegun, use fixed timestamps
   4. External: Mock HTTP/database, use fixtures
   5. Data: Fix seeds, use hypothesis deterministic settings
   ```

4. Prioritize fixes by impact (most frequent failures first)
  </action>
  <verify>flaky_test_audit.md exists with categorized list of all flaky tests by root cause (race/async/time/external/data/fixture)</verify>
  <done>All @pytest.mark.flaky tests audited and categorized by root cause, fix plan prioritized by failure frequency</done>
</task>

<task type="auto">
  <name>Fix Race Condition Flaky Tests</name>
  <files>backend/tests/property_tests/test_event_handling_invariants.py, backend/tests/integration/test_api_integration.py</files>
  <action>
Fix flaky tests caused by race conditions:

Common race condition patterns from FLAKY_TEST_GUIDE.md:
1. **Shared global state** - Use unique_resource_name fixture
2. **Database collisions** - Use db_session with transaction rollback
3. **Parallel test conflicts** - Ensure test data is worker-specific
4. **Fixture state leakage** - Use function-scoped fixtures with cleanup

For each race condition flaky test:
1. Add unique_resource_name fixture parameter:
   ```python
   def test_event_batching_race_condition(self, unique_resource_name):
       """Test event batching with parallel-safe resources."""
       batch_id = f"batch_{unique_resource_name}"
       # ... use batch_id instead of hardcoded "test_batch"
   ```

2. Ensure db_session usage for database operations:
   ```python
   def test_database_operation(self, db_session, unique_resource_name):
       """Test with proper database isolation."""
       agent = AgentFactory.create(_session=db_session, id=unique_resource_name)
       # Transaction auto-rolls back after test
   ```

3. Add proper synchronization for concurrent operations:
   ```python
   async def test_concurrent_operation(self):
       """Test with proper async coordination."""
       results = await asyncio.gather(
           operation1(),
           operation2(),
       )
       # Properly waits for all to complete
   ```

4. Remove @pytest.mark.flaky marker after fix

5. Verify by running 10 times:
   ```bash
   for i in {1..10}; do
       pytest tests/path/test_file.py::test_name -v
   done
   ```
  </action>
  <verify>For each race condition test: (1) unique_resource_name fixture used, (2) db_session for database ops, (3) @pytest.mark.flaky removed, (4) 10 consecutive runs all pass</verify>
  <done>All race condition flaky tests fixed with proper isolation, @pytest.mark.flaky markers removed, tests verified stable across 10 runs</done>
</task>

<task type="auto">
  <name>Fix Async Coordination Flaky Tests</name>
  <files>backend/tests/integration/test_websocket_integration.py, backend/tests/integration/test_api_integration.py</files>
  <action>
Fix flaky tests caused by async coordination issues:

Common async patterns from test_flaky_detection.py:
1. **Missing await** - Coroutine returned but not awaited
2. **Missing asyncio.gather** - Concurrent ops not properly coordinated
3. **Missing timeout** - Async operations without timeout handling
4. **Event loop issues** - Wrong loop usage, not closed properly

For each async flaky test:
1. Fix missing await:
   ```python
   # BAD - returns coroutine
   result = async_function()

   # GOOD - awaits coroutine
   result = await async_function()
   ```

2. Fix concurrent operations:
   ```python
   # BAD - sequential async calls
   result1 = await operation1()
   result2 = await operation2()

   # GOOD - parallel async calls
   results = await asyncio.gather(operation1(), operation2())
   ```

3. Add timeout handling:
   ```python
   async def test_with_timeout(self):
       """Test with proper timeout handling."""
       try:
           result = await asyncio.wait_for(
               async_operation(),
               timeout=5.0
           )
       except asyncio.TimeoutError:
           pytest.fail("Operation timed out")
   ```

4. Use pytest-asyncio properly:
   ```python
   @pytest.mark.asyncio
   async def test_async_operation(self):
       """Proper async test declaration."""
       result = await async_function()
       assert result == expected
   ```

5. Remove @pytest.mark.flaky marker after fix

6. Verify with 10 consecutive runs
  </action>
  <verify>For each async flaky test: (1) All async calls properly awaited, (2) Concurrent ops use asyncio.gather, (3) Timeouts added where appropriate, (4) @pytest.mark.flaky removed, (5) 10 runs stable</verify>
  <done>All async coordination flaky tests fixed with proper async patterns, @pytest.mark.flaky markers removed, tests verified stable across 10 runs</done>
</task>

</tasks>

<verification>
1. Check for zero @pytest.mark.flaky markers: `grep -r "@pytest.mark.flaky" backend/tests/ --include="*.py"` should return empty
2. Run flaky test audit: `pytest tests/test_flaky_detection.py -v` - should pass
3. Verify isolation: `pytest tests/test_isolation_validation.py -v` - should pass
4. Stability check: Run full suite 3 times - results should be identical
</verification>

<success_criteria>
1. Zero @pytest.mark.flaky markers remain in codebase
2. flaky_test_audit.md documents all fixes with root causes
3. All previously flaky tests now pass consistently (10 runs)
4. Parallel execution produces same results as serial
5. Test isolation validation passes
</success_criteria>

<output>
After completion, create `.planning/phases/06-production-hardening/06-production-hardening-03-SUMMARY.md` with:
- Flaky tests fixed count
- Root cause categories addressed
- @pytest.mark.flaky markers removed (should be zero)
- Stability verification results (10-run consistency)
</output>

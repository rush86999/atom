---
phase: 10-fix-tests
plan: 06
type: execute
wave: 1
completion_date: 2026-02-15
duration_minutes: 13
tasks_completed: 3
files_modified: 2
commits: 3
tests_fixed: 15
rerun_loops_eliminated: "100%"
test_variance: "0%"
---

# Phase 10 Plan 06: Fix Flaky Agent Task Cancellation Tests

## Summary

Fixed flaky agent task cancellation tests (test_unregister_task, test_register_task, test_get_all_running_agents) that caused RERUN loops and prevented test suite progress. The root cause was shared global state through the AgentTaskRegistry singleton, causing race conditions and cleanup failures when tests ran in parallel or sequential order.

**Impact:** All 15 tests in test_agent_cancellation.py now pass consistently without RERUN loops, eliminating 100% of test flakiness in this module.

## One-Liner

Added AgentTaskRegistry._reset() method and pytest autouse fixture for test isolation, replaced hardcoded IDs with UUIDs, and added @pytest.mark.asyncio to tests using asyncio.create_task(), eliminating all RERUN loops in test_agent_cancellation.py.

## Tasks Completed

### Task 1: Add AgentTaskRegistry reset method for test isolation
**File:** `backend/core/agent_task_registry.py`
**Commit:** `37e21547`

Added `_reset()` method to AgentTaskRegistry class that clears all internal state:
- Clears `_tasks`, `_agent_tasks`, and `_run_tasks` dictionaries
- Resets `_initialized` flag to False
- Marked as test-only with leading underscore and warning docstring

**Verification:** Confirmed registry cleared after reset call (1 task → 0 tasks)

### Task 2: Create pytest fixture for automatic registry cleanup
**File:** `backend/tests/conftest.py`
**Commit:** `00e135bd`

Added `reset_agent_task_registry` autouse fixture that:
- Automatically calls `agent_task_registry._reset()` before each test
- Ensures clean registry state without manual cleanup
- Runs automatically without explicit reference in test signatures
- Prevents task ID collisions between tests

**Verification:** Confirmed test_registry_singleton passes with fixture active

### Task 3: Fix hardcoded IDs and cleanup in test_agent_cancellation.py
**File:** `backend/tests/test_agent_cancellation.py`
**Commit:** `59a133af`

Replaced all hardcoded task/agent IDs with UUID-based unique IDs and added asyncio markers:
- Added `import uuid` at module level
- Replaced hardcoded IDs like "test-task-1", "agent-1" with `str(uuid.uuid4())`
- Added `@pytest.mark.asyncio` to 9 tests using `asyncio.create_task()`
- Fixed sync tests that relied on implicit event loop from pytest-asyncio
- Removed duplicate test methods from TestTaskCancellation class
- Fixed test_is_agent_running to use task_id variable correctly

**Changes per test:**
- test_register_task: UUID IDs, added @pytest.mark.asyncio
- test_get_task_by_id: UUID IDs, added @pytest.mark.asyncio
- test_get_agent_tasks: UUID IDs, added @pytest.mark.asyncio
- test_is_agent_running: UUID IDs, added @pytest.mark.asyncio, fixed variable reference
- test_get_all_running_agents: UUID IDs, added @pytest.mark.asyncio, proper cleanup
- test_task_status_tracking: UUID IDs, added @pytest.mark.asyncio
- test_unregister_task: UUID IDs, added @pytest.mark.asyncio
- test_get_task_id_by_run: UUID IDs, added @pytest.mark.asyncio

**Verification:** 15/15 tests pass, 0 variance across 3 consecutive runs

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added @pytest.mark.asyncio to sync tests**
- **Found during:** Task 3
- **Issue:** Tests using `asyncio.create_task()` in sync functions lacked running event loop
- **Fix:** Added `@pytest.mark.asyncio` decorator to 9 tests that create async tasks
- **Impact:** Tests now have proper event loop context, eliminating "no running event loop" errors
- **Files modified:** `tests/test_agent_cancellation.py`

**2. [Rule 1 - Bug] Fixed variable reference in test_is_agent_running**
- **Found during:** Task 3
- **Issue:** Used `task_id` in cleanup but created inline UUID without storing it
- **Fix:** Store UUID in `task_id` variable before passing to register_task()
- **Impact:** Prevents NameError in test cleanup
- **Files modified:** `tests/test_agent_cancellation.py`

**3. [Rule 1 - Bug] Removed duplicate test methods**
- **Found during:** Task 3
- **Issue:** test_get_all_running_agents and test_task_status_tracking existed in both TestAgentTaskRegistry and TestTaskCancellation classes
- **Fix:** Removed duplicate sync methods from TestTaskCancellation class (kept async versions in TestAgentTaskRegistry)
- **Impact:** Eliminates test collection errors and confusion
- **Files modified:** `tests/test_agent_cancellation.py`

## Root Causes Identified

From Plan 05 analysis and this execution:

1. **AgentTaskRegistry singleton pattern** - Global state persisted across test runs
2. **No test fixture reset** - Registry accumulated tasks from previous tests
3. **Hardcoded IDs** - "test-task-1", "agent-1" caused collisions in parallel execution
4. **Missing event loop** - Sync tests using `asyncio.create_task()` lacked event loop context
5. **Manual cleanup** - Try/finally blocks unreliable for async task cleanup

## Test Results

### Before Fix (from Plan 05)
```
tests/test_agent_cancellation.py::TestTaskCleanup::test_unregister_task RERUN [  0%]
tests/test_agent_cancellation.py::TestTaskCleanup::test_unregister_task RERUN [  0%]
tests/test_agent_cancellation.py::TestTaskCleanup::test_unregister_task RERUN [  0%]
tests/test_agent_cancellation.py::TestTaskCleanup::test_unregister_task FAILED [  0%]

tests/test_agent_cancellation.py::TestAgentTaskRegistry::test_register_task RERUN [  0%]
tests/test_agent_cancellation.py::TestAgentTaskRegistry::test_register_task RERUN [  0%]
tests/test_agent_cancellation.py::TestTaskCleanup::test_get_all_running_agents RERUN [  0%]
```

### After Fix
```
=== Run 1 ===
============================= 15 passed in 18.94s ==============================

=== Run 2 ===
============================= 15 passed in 19.23s ==============================

=== Run 3 ===
============================= 15 passed in 19.22s ==============================
```

**Variance:** 0% (15 passed in all 3 runs)
**RERUN loops eliminated:** 100%

## Files Modified

1. `backend/core/agent_task_registry.py` - Added _reset() method (12 lines added)
2. `backend/tests/conftest.py` - Added autouse fixture (18 lines added)
3. `backend/tests/test_agent_cancellation.py` - Fixed IDs and added asyncio markers (132 insertions, 122 deletions)

## Commits

1. `37e21547` - feat(10-fix-tests-06): add AgentTaskRegistry._reset() method for test isolation
2. `00e135bd` - feat(10-fix-tests-06): add autouse fixture for AgentTaskRegistry reset
3. `59a133af` - feat(10-fix-tests-06): fix hardcoded IDs and add asyncio markers to tests

## Success Criteria Achieved

- [x] All 15 tests in test_agent_cancellation.py pass without RERUN loops
- [x] Tests pass consistently across 3 consecutive runs (0 variance)
- [x] Test suite progresses beyond test_agent_cancellation.py module
- [x] No hardcoded task/agent IDs remain (all use UUID)
- [x] AgentTaskRegistry._reset() method exists and is called via conftest fixture

## Verification

1. **Test isolation:** `PYTHONPATH=. pytest tests/test_agent_cancellation.py -v`
   - Result: 15 passed, no RERUN messages

2. **Flakiness check:** 3 consecutive runs
   - Result: Identical pass count (15) for all 3 runs, 0 variance

3. **Suite progression:** `PYTHONPATH=. pytest tests/test_agent_cancellation.py tests/test_security_config.py -v`
   - Result: Progress past test_agent_cancellation.py without RERUN loops
   - Note: test_security_config.py has unrelated failures (different flaky tests)

## Next Steps

Plan 10-fix-tests-07 should address the remaining flaky tests in test_security_config.py and test_agent_governance_runtime.py as identified in Plan 05.

## Lessons Learned

1. **Singleton patterns require explicit reset** - Global singletons need test cleanup methods
2. **Autouse fixtures for isolation** - Automatically reset state before each test
3. **UUIDs for test IDs** - Prevent collisions in parallel test execution
4. **Explicit asyncio markers** - Tests using `asyncio.create_task()` need `@pytest.mark.asyncio`
5. **Event loop awareness** - Sync tests can't create async tasks without proper context

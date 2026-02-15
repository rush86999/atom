---
phase: 10-fix-tests
plan: 06
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/test_agent_cancellation.py
  - core/agent_task_registry.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Agent task cancellation tests pass without RERUN loops (test_unregister_task, test_register_task, test_get_all_running_agents)"
    - "Agent task registry properly isolates state between test runs (singleton initialized per test session)"
    - "Async task cleanup handles race conditions in concurrent test execution"
    - "Test suite can progress beyond test_agent_cancellation.py module without repeated retries"
  artifacts:
    - path: "tests/test_agent_cancellation.py"
      provides: "Isolated agent task registry tests"
      min_lines: 400
    - path: "tests/conftest.py"
      provides: "Agent task registry fixture for test isolation"
      exports: ["agent_task_registry"]
  key_links:
    - from: "tests/test_agent_cancellation.py"
      to: "core/agent_task_registry.py"
      via: "AgentTaskRegistry singleton reset"
      pattern: "agent_task_registry._reset|_tasks.clear"
    - from: "tests/conftest.py"
      to: "tests/test_agent_cancellation.py"
      via: "autouse fixture"
      pattern: "@pytest.fixture(autouse=True)"
---

<objective>
Fix flaky agent task cancellation tests (test_unregister_task, test_register_task, test_get_all_running_agents) that cause RERUN loops and prevent test suite progress.

**Purpose:** These tests share global state through the AgentTaskRegistry singleton, causing race conditions and cleanup failures when tests run in parallel or sequential order. The registry accumulates tasks from previous tests, leading to "task already exists" errors and inconsistent state.

**Root Causes (from Plan 05 analysis):**
1. AgentTaskRegistry is a singleton that persists across test runs
2. Tests create tasks but cleanup is unreliable (tasks may complete before unregistration)
3. No test fixture resets registry state between tests
4. ID collisions from hardcoded test IDs ("test-task-1", "task-running", etc.)
5. Async task cancellation race conditions (task.cancel() vs task.done())

**Output:**
- Fixed test_agent_cancellation.py with proper test isolation
- AgentTaskRegistry reset method for test cleanup
- pytest fixture for automatic registry cleanup
- All 3 flaky tests passing without RERUN loops
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/10-fix-tests/10-fix-tests-05-SUMMARY.md
@.planning/phases/10-fix-tests/10-fix-tests-VERIFICATION.md

# Flaky Test Evidence (from Plan 05)

```
tests/test_agent_cancellation.py::TestTaskCleanup::test_unregister_task RERUN [  0%]
tests/test_agent_cancellation.py::TestTaskCleanup::test_unregister_task RERUN [  0%]
tests/test_agent_cancellation.py::TestTaskCleanup::test_unregister_task RERUN [  0%]
tests/test_agent_cancellation.py::TestTaskCleanup::test_unregister_task FAILED [  0%]

tests/test_agent_cancellation.py::TestAgentTaskRegistry::test_register_task RERUN [  0%]
tests/test_agent_cancellation.py::TestAgentTaskRegistry::test_register_task RERUN [  0%]
tests/test_agent_cancellation.py::TestTaskCleanup::test_get_all_running_agents RERUN [  0%]
```

# Current Implementation Issues

**File: core/agent_task_registry.py**
- Singleton pattern with `_instance` and `_initialized` flags
- No reset/cleanup method for testing
- Global `agent_task_registry` instance created at import time

**File: tests/test_agent_cancellation.py**
- Uses hardcoded IDs: "test-task-1", "task-running", "agent-1"
- Manual cleanup in try/finally blocks (unreliable)
- Tests share the same global `agent_task_registry` instance
- No fixture-based isolation

# Reference Implementation Pattern

From tests/conftest.py, the `unique_resource_name` fixture pattern for test isolation:
```python
@pytest.fixture(scope="function")
def unique_resource_name():
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    unique_id = str(uuid.uuid4())[:8]
    return f"test_{worker_id}_{unique_id}"
```
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add AgentTaskRegistry reset method for test isolation</name>
  <files>core/agent_task_registry.py</files>
  <action>
    Add a `_reset()` method to AgentTaskRegistry class that clears all internal state. This method should ONLY be used in tests.

    Implementation:
    1. Add method signature: `def _reset(self) -> None`
    2. Clear all dictionaries: `self._tasks.clear()`, `self._agent_tasks.clear()`, `self._run_tasks.clear()`
    3. Reset initialization flag: `self._initialized = False`
    4. Add docstring warning: "WARNING: Only for test use. Clears all registry state."
    5. Mark as test-only with leading underscore

    Location: Add after `get_all_running_agents()` method, before the global instance creation

    DO NOT:
    - Modify any production methods (register_task, cancel_task, etc.)
    - Change the singleton pattern logic
    - Add any public API methods
  </action>
  <verify>
    Run: `python -c "from core.agent_task_registry import agent_task_registry; agent_task_registry.register_task('t1', 'a1', 'r1', None, 'u1'); agent_task_registry._reset(); print(len(agent_task_registry._tasks))"`
    Expected output: "0" (registry empty after reset)
  </verify>
  <done>
    AgentTaskRegistry has _reset() method that clears all internal state
  </done>
</task>

<task type="auto">
  <name>Task 2: Create pytest fixture for automatic registry cleanup</name>
  <files>tests/conftest.py</files>
  <action>
    Add an autouse pytest fixture that resets the AgentTaskRegistry before each test. This ensures tests start with clean registry state.

    Implementation:
    1. Import at top: `from core.agent_task_registry import agent_task_registry`
    2. Add fixture after `ensure_numpy_available` fixture:
       ```python
       @pytest.fixture(autouse=True)
       def reset_agent_task_registry():
           """Reset agent task registry before each test for isolation."""
           agent_task_registry._reset()
           yield
           # No cleanup needed - each test gets fresh state
       ```
    3. Add docstring explaining purpose: prevents task ID collisions between tests

    DO NOT:
    - Make this fixture scoped anything other than "function" (default)
    - Add any logic beyond reset() call
    - Modify existing fixtures
  </action>
  <verify>
    Run: `PYTHONPATH=. pytest tests/test_agent_cancellation.py::TestAgentTaskRegistry::test_registry_singleton -v`
    Expected: Test passes without errors
  </verify>
  <done>
    tests/conftest.py has autouse fixture that calls agent_task_registry._reset() before each test
  </done>
</task>

<task type="auto">
  <name>Task 3: Fix hardcoded IDs and cleanup in test_agent_cancellation.py</name>
  <files>tests/test_agent_cancellation.py</files>
  <action>
    Replace all hardcoded task/agent IDs with UUID-based unique IDs to prevent collisions. Improve async task cleanup reliability.

    Changes for each test method:
    1. Replace hardcoded IDs like "test-task-1", "agent-1" with `str(uuid.uuid4())`
    2. Add `import uuid` at top (not already present)
    3. For tests using `asyncio.create_task()`, add proper task cleanup:
       - Use `try/finally` to ensure tasks are cancelled
       - Check `task.done()` before accessing results
       - Use `asyncio.wait_for(task, timeout=1.0)` with try/except for timeout
    4. Remove manual registry cleanup calls (now handled by conftest fixture)
    5. Keep test assertions unchanged (verify behavior, not implementation)

    Specific fixes:
    - `test_register_task`: Use `uuid.uuid4()` for task_id, agent_id
    - `test_unregister_task`: Add `asyncio.sleep(0.1)` before assertion to allow cleanup
    - `test_get_all_running_agents`: Remove manual cleanup loop (fixture handles it)
    - `test_get_task_by_run`: Use UUID for agent_run_id
    - `test_get_agent_tasks`: Use unique agent_id per iteration
    - `test_is_agent_running`: Use UUID for agent_id, task_id
    - `test_cancel_single_task`: Keep cancellation logic, use UUID for IDs
    - `test_cancel_agent_tasks`: Use unique task_ids per iteration
    - `test_task_status_tracking`: Ensure task is cancelled before status check

    DO NOT:
    - Change test class structure or method names
    - Remove test assertions
    - Mock AgentTaskRegistry (test the real implementation)
  </action>
  <verify>
    Run: `PYTHONPATH=. pytest tests/test_agent_cancellation.py -v --tb=short`
    Expected: All tests pass, no RERUN messages, no FAILED status
  </verify>
  <done>
    All agent task cancellation tests pass with UUID-based IDs and reliable async cleanup
  </done>
</task>

</tasks>

<verification>
After completion, verify:

1. Run test_agent_cancellation.py in isolation:
   ```bash
   PYTHONPATH=. pytest tests/test_agent_cancellation.py -v --tb=short
   ```
   Expected: All 15 tests pass, no RERUN messages

2. Run tests 3 times to verify no flakiness:
   ```bash
   for i in 1 2 3; do PYTHONPATH=. pytest tests/test_agent_cancellation.py -q; done
   ```
   Expected: Identical pass count (15 passed) for all 3 runs

3. Run subset of full test suite including test_agent_cancellation.py:
   ```bash
   PYTHONPATH=. pytest tests/test_agent_cancellation.py tests/test_security_config.py -v --tb=short
   ```
   Expected: Progress past test_agent_cancellation.py without RERUN loops
</verification>

<success_criteria>
1. All 15 tests in test_agent_cancellation.py pass without RERUN loops
2. Tests pass consistently across 3 consecutive runs (0 variance)
3. Test suite progresses beyond test_agent_cancellation.py module
4. No hardcoded task/agent IDs remain (all use UUID)
5. AgentTaskRegistry._reset() method exists and is called via conftest fixture
</success_criteria>

<output>
After completion, create `.planning/phases/10-fix-tests/10-fix-tests-06-SUMMARY.md`

Include:
- Flaky tests fixed (test_unregister_task, test_register_task, test_get_all_running_agents)
- Number of RERUN loops eliminated (target: 0)
- Test run variance across 3 runs (target: 0% variance)
- Files modified with commit references
</output>

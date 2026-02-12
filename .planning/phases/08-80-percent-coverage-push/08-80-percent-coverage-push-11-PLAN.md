---
phase: 08-80-percent-coverage-push
plan: 11
type: execute
wave: 2
depends_on:
  - 08-80-percent-coverage-push-08
  - 08-80-percent-coverage-push-09
  - 08-80-percent-coverage-push-10
files_modified:
  - backend/tests/unit/test_workflow_engine.py
  - backend/tests/unit/test_canvas_tool.py
  - backend/tests/unit/test_browser_tool.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "workflow_engine.py coverage increases from 24.53% to 50%+"
    - "canvas_tool.py coverage increases from 29.51% to 50%+"
    - "browser_tool.py coverage increases from 75.72% to 80%+"
    - "All existing tests continue to pass"
    - "New tests achieve 100% pass rate"
  artifacts:
    - path: "backend/tests/unit/test_workflow_engine.py"
      provides: "Extended unit tests for WorkflowEngine"
      contains: "Additional tests for parallel execution, service executors, timeout/retry"
    - path: "backend/tests/unit/test_canvas_tool.py"
      provides: "Extended unit tests for canvas tool"
      contains: "Additional tests for complex canvas operations"
    - path: "backend/tests/unit/test_browser_tool.py"
      provides: "Extended unit tests for browser tool"
      contains: "Additional tests to reach 80% target"
  key_links:
    - from: "test_workflow_engine.py"
      to: "core/workflow_engine.py"
      via: "import"
      pattern: "from core.workflow_engine import"
    - from: "test_canvas_tool.py"
      to: "tools/canvas_tool.py"
      via: "import"
      pattern: "from tools.canvas_tool import"
    - from: "test_browser_tool.py"
      to: "tools/browser_tool.py"
      via: "import"
      pattern: "from tools.browser_tool import"
---

<objective>
Extend coverage on 3 key modules that are below their 80% targets: workflow_engine (24.53% -> 50%), canvas_tool (29.51% -> 50%), and browser_tool (75.72% -> 80%). This addresses the "Core module coverage" and "Tools module coverage" gaps.

Purpose: Add targeted tests to push coverage toward 80% goal on high-impact files that previously received only baseline testing.

Output: Extended test files with additional test classes covering parallel execution, service executors, timeout/retry, and complex operations.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-VERIFICATION.md
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-02-SUMMARY.md
@backend/tests/unit/test_workflow_engine.py
@backend/tests/unit/test_canvas_tool.py
@backend/tests/unit/test_browser_tool.py

Gap context from VERIFICATION.md:
- "Core module coverage increases to 80%+" - status: partial, average ~25-35%
- "Additional tests needed for workflow engine parallel execution, service executors, timeout/retry logic"
- "canvas_tool.py coverage 72.82% (complete test), 29.51% (unit test) - below 80%"
- "browser_tool.py coverage 75.72% - below 80%"

Current state:
- test_workflow_engine.py: 708 lines, 53 tests, 24.53% coverage
- test_canvas_tool.py: 459 lines, 19 tests, 29.51% coverage
- test_browser_tool_complete.py: 2086 lines, 75.72% coverage
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extend workflow_engine.py tests to 50% coverage</name>
  <files>backend/tests/unit/test_workflow_engine.py</files>
  <action>
    Extend test_workflow_engine.py with additional test classes to reach 50% coverage:

    1. Read existing test_workflow_engine.py to understand current coverage
    2. Read core/workflow_engine.py to identify uncovered code paths
    3. Add TestParallelExecution class with 4-5 tests:
       - test_execute_parallel_steps_independent
       - test_execute_parallel_steps_with_dependencies
       - test_max_concurrent_steps_limit
       - test_parallel_execution_with_failures
    4. Add TestServiceExecutors class with 5-6 tests:
       - test_execute_slack_action
       - test_execute_asana_action
       - test_execute_email_action
       - test_execute_http_action
       - test_service_executor_error_handling
    5. Add TestTimeoutAndRetry class with 3-4 tests:
       - test_step_timeout_handling
       - test_step_retry_logic
       - test_max_retries_exceeded

    Use AsyncMock for all service executor calls
    Mock external service clients (Slack, Asana, email)
    Test timeout and retry logic with mocked time

    Target: Add 200-300 lines, 12-15 new tests, achieve 50%+ coverage

    DO NOT modify existing test classes - only add new ones
  </action>
  <verify>pytest backend/tests/unit/test_workflow_engine.py -v --cov=backend.core.workflow_engine --cov-report=term-missing | grep -E "(PASSED|FAILED|coverage)"</verify>
  <done>12-15 new tests added, workflow_engine.py coverage 50%+, all existing tests still pass</done>
</task>

<task type="auto">
  <name>Task 2: Extend canvas_tool.py tests to 50% coverage</name>
  <files>backend/tests/unit/test_canvas_tool.py</files>
  <action>
    Extend test_canvas_tool.py with additional test classes to reach 50% coverage:

    1. Read existing test_canvas_tool.py to understand current coverage
    2. Read tools/canvas_tool.py to identify uncovered code paths
    3. Add TestCanvasTypeSpecificOperations class with 5-6 tests:
       - test_create_sheets_canvas
       - test_create_email_canvas
       - test_create_docs_canvas
       - test_create_terminal_canvas
       - test_create_orchestration_canvas
    4. Add TestCanvasValidation class with 3-4 tests:
       - test_validate_canvas_schema
       - test_validate_component_security
       - test_validation_error_handling
    5. Add TestCanvasErrorHandling class with 3-4 tests:
       - test_canvas_creation_failure
       - test_invalid_canvas_type
       - test_governance_block_handling

    Mock canvas database operations
    Test type-specific canvas creation logic
    Test validation and error handling

    Target: Add 150-200 lines, 11-14 new tests, achieve 50%+ coverage

    DO NOT modify existing test classes
  </action>
  <verify>pytest backend/tests/unit/test_canvas_tool.py -v --cov=backend.tools.canvas_tool --cov-report=term-missing | grep -E "(PASSED|FAILED|coverage)"</verify>
  <done>11-14 new tests added, canvas_tool.py coverage 50%+, all existing tests still pass</done>
</task>

<task type="auto">
  <name>Task 3: Extend browser_tool.py tests to 80% coverage</name>
  <files>backend/tests/unit/test_browser_tool.py</files>
  <action>
    First, check if test_browser_tool.py exists or only test_browser_tool_complete.py exists:

    1. List existing browser tool tests: ls backend/tests/unit/test_browser*.py backend/tests/tools/test_browser*.py
    2. If test_browser_tool.py (unit) doesn't exist, create it first with baseline tests
    3. If test_browser_tool.py exists, extend it to reach 80% coverage

    Add tests for uncovered code paths:
    4. Add TestBrowserNavigation class with 3-4 tests:
       - test_navigate_to_url
       - test_navigate_with_wait
       - test_navigation_error_handling
    5. Add TestBrowserInteraction class with 4-5 tests:
       - test_click_element
       - test_fill_form
       - test_select_dropdown
       - test_upload_file
    6. Add TestBrowserAdvancedOperations class with 3-4 tests:
       - test_execute_script
       - test_screenshot_with_options
       - test_pdf_generation

    Mock Playwright CDP operations
    Test browser interaction logic
    Test error handling

    Target: Add 150-200 lines, 10-12 new tests, achieve 80%+ coverage

    Focus on the unit test file (backend/tests/unit/) not the complete test file (backend/tests/tools/)
  </action>
  <verify>pytest backend/tests/unit/test_browser_tool.py -v --cov=backend.tools.browser_tool --cov-report=term-missing | grep -E "(PASSED|FAILED|coverage)"</verify>
  <done>10-12 new tests added, browser_tool.py coverage 80%+, all existing tests still pass</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run pytest on all three extended test files:
   ```bash
   pytest backend/tests/unit/test_workflow_engine.py backend/tests/unit/test_canvas_tool.py backend/tests/unit/test_browser_tool.py -v
   ```

2. Verify ALL tests pass (existing + new, no regressions)

3. Run coverage report:
   ```bash
   pytest backend/tests/unit/test_workflow_engine.py backend/tests/unit/test_canvas_tool.py backend/tests/unit/test_browser_tool.py --cov=backend.core.workflow_engine --cov=backend.tools.canvas_tool --cov=backend.tools.browser_tool --cov-report=term-missing
   ```

4. Verify targets met:
   - workflow_engine.py: 50%+ coverage (from 24.53%)
   - canvas_tool.py: 50%+ coverage (from 29.51%)
   - browser_tool.py: 80%+ coverage (from 75.72%)

5. Update coverage_reports/metrics/coverage.json with new metrics
</verification>

<success_criteria>
- 33-41 new tests added across the three files
- 100% test pass rate (existing and new tests)
- workflow_engine.py coverage 50%+ (+25 percentage points)
- canvas_tool.py coverage 50%+ (+20 percentage points)
- browser_tool.py coverage 80%+ (+4 percentage points)
- No regressions in existing tests
- All tests execute in under 60 seconds
- coverage.json updated with new metrics
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-11-SUMMARY.md`
</output>

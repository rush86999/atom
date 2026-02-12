---
phase: 08-80-percent-coverage-push
plan: 12
type: execute
wave: 2
depends_on: []
files_modified:
  - backend/tests/api/test_canvas_routes.py
  - backend/tests/api/test_browser_routes.py
  - backend/tests/api/test_device_capabilities.py
  - backend/tests/api/test_atom_agent_endpoints.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "All API tests pass with 100% success rate"
    - "WebSocket mocks work correctly for real-time endpoints"
    - "Governance service mocks work correctly for protected endpoints"
    - "Service dependency mocks work correctly for all API routes"
    - "API module coverage increases measurably"
  artifacts:
    - path: "backend/tests/api/test_canvas_routes.py"
      provides: "Fixed and passing API integration tests for canvas routes"
      min_lines: 718
    - path: "backend/tests/api/test_browser_routes.py"
      provides: "Fixed and passing API integration tests for browser routes"
      min_lines: 603
    - path: "backend/tests/api/test_device_capabilities.py"
      provides: "Fixed and passing API integration tests for device capabilities"
      min_lines: 542
    - path: "backend/tests/api/test_atom_agent_endpoints.py"
      provides: "Fixed and passing API integration tests for agent endpoints"
      min_lines: 400
  key_links:
    - from: "tests/api/*"
      to: "api/*"
      via: "TestClient"
      pattern: "from fastapi.testclient import TestClient"
---

<objective>
Refine mocks for existing API integration tests to achieve 100% pass rate. Current pass rate is ~75% due to WebSocket, governance, and service dependency mocking issues.

Purpose: Fix failing API tests so they provide accurate coverage measurements and catch regressions. Without passing tests, coverage data is unreliable.

Output: All existing API test files fixed with refined mocks, 100% pass rate achieved.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-VERIFICATION.md
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-06-SUMMARY.md
@backend/tests/api/test_canvas_routes.py
@backend/tests/api/test_browser_routes.py
@backend/tests/api/test_device_capabilities.py

Gap context from VERIFICATION.md:
- "API module coverage increases to 80%+" - status: partial
- "Mock refinement needed for WebSocket, governance, and service dependencies"
- "Tests require mock refinement for full execution"
- "Actual coverage increase not measured due to test execution issues"

Current state:
- test_canvas_routes.py: 718 lines, 17 tests - requires mock refinement
- test_browser_routes.py: 603 lines, 9 tests - requires mock refinement
- test_device_capabilities.py: 542 lines, 8 tests - requires mock refinement
</context>

<tasks>

<task type="auto">
  <name>Task 1: Refine mocks for test_canvas_routes.py</name>
  <files>backend/tests/api/test_canvas_routes.py</files>
  <action>
    Fix mock refinement issues in test_canvas_routes.py:

    1. Run the test file to identify failing tests:
       ```bash
       pytest backend/tests/api/test_canvas_routes.py -v --tb=short
       ```
    2. Analyze failure patterns (WebSocket mocks, governance mocks, service mocks)
    3. Fix WebSocket mock issues:
       - Replace websocket mocks with AsyncMock patterns
       - Mock connection manager methods properly
       - Ensure async context managers are mocked
    4. Fix governance service mocks:
       - Use AsyncMock for governance checks
       - Mock agent_governance_service.check_permission
       - Mock governance_cache.get_cached_governance_data
    5. Fix service dependency mocks:
       - Properly patch canvas_tool functions
       - Mock database session with AsyncMock
       - Ensure all dependencies return appropriate values

    DO NOT change test logic or add new tests - only fix mocks
    DO NOT remove tests - fix the mocks to make them pass

    Target: All 17 tests pass
  </action>
  <verify>pytest backend/tests/api/test_canvas_routes.py -v | grep -E "passed|failed|ERROR" | tail -1</verify>
  <done>All 17 canvas routes tests pass, no errors</done>
</task>

<task type="auto">
  <name>Task 2: Refine mocks for test_browser_routes.py</name>
  <files>backend/tests/api/test_browser_routes.py</files>
  <action>
    Fix mock refinement issues in test_browser_routes.py:

    1. Run the test file to identify failing tests:
       ```bash
       pytest backend/tests/api/test_browser_routes.py -v --tb=short
       ```
    2. Analyze failure patterns
    3. Fix WebSocket mocks for browser session management
    4. Fix governance mocks for browser permission checks (INTERN+ required)
    5. Fix browser_tool mocks:
       - Mock Playwright CDP operations
       - Mock browser session creation/termination
       - Ensure proper async handling

    DO NOT change test logic or add new tests - only fix mocks

    Target: All 9 tests pass
  </action>
  <verify>pytest backend/tests/api/test_browser_routes.py -v | grep -E "passed|failed|ERROR" | tail -1</verify>
  <done>All 9 browser routes tests pass, no errors</done>
</task>

<task type="auto">
  <name>Task 3: Refine mocks for test_device_capabilities.py</name>
  <files>backend/tests/api/test_device_capabilities.py</files>
  <action>
    Fix mock refinement issues in test_device_capabilities.py:

    1. Run the test file to identify failing tests:
       ```bash
       pytest backend/tests/api/test_device_capabilities.py -v --tb=short
       ```
    2. Analyze failure patterns
    3. Fix device_tool mocks for different capabilities:
       - Camera (INTERN+)
       - Screen Recording (SUPERVISED+)
       - Location (INTERN+)
       - Notifications (INTERN+)
       - Command Execution (AUTONOMOUS only)
    4. Fix governance mocks for maturity-based permission checks
    5. Fix WebSocket mocks for real-time device updates

    DO NOT change test logic or add new tests - only fix mocks

    Target: All 8 tests pass
  </action>
  <verify>pytest backend/tests/api/test_device_capabilities.py -v | grep -E "passed|failed|ERROR" | tail -1</verify>
  <done>All 8 device capabilities tests pass, no errors</done>
</task>

<task type="auto">
  <name>Task 4: Run API coverage with fixed mocks</name>
  <files>backend/tests/coverage_reports/metrics/coverage.json</files>
  <action>
    After fixing all API test mocks, run coverage report to measure actual API module coverage:

    1. Run all API tests with coverage:
       ```bash
       pytest backend/tests/api/ -v --cov=backend.api --cov-report=term-missing --cov-report=html
       ```
    2. Collect coverage metrics for:
       - api/canvas_routes.py
       - api/browser_routes.py
       - api/device_capabilities.py
       - Overall api/ module
    3. Update coverage_reports/metrics/coverage.json with new API coverage data
    4. Document which API endpoints still need coverage

    This task creates the baseline measurement for API module coverage gap.
  </action>
  <verify>pytest backend/tests/api/ --cov=backend.api --cov-report=term | grep -E "TOTAL|api/"</verify>
  <done>API coverage measured and documented in coverage.json, all API tests passing</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run all API tests and verify 100% pass rate:
   ```bash
   pytest backend/tests/api/ -v --tb=short
   ```

2. Verify specific test files:
   ```bash
   pytest backend/tests/api/test_canvas_routes.py -v | grep "passed"
   pytest backend/tests/api/test_browser_routes.py -v | grep "passed"
   pytest backend/tests/api/test_device_capabilities.py -v | grep "passed"
   ```

3. Run coverage report:
   ```bash
   pytest backend/tests/api/ --cov=backend.api --cov-report=term-missing
   ```

4. Verify:
   - 34+ tests pass (17 + 9 + 8)
   - No failed tests
   - No ERROR states
   - API module coverage measured

5. Check coverage.json updated with API metrics
</verification>

<success_criteria>
- All 34 API tests pass (100% pass rate)
- No failed or error tests
- WebSocket mocks working correctly
- Governance mocks working correctly
- Service dependency mocks working correctly
- API module coverage measured and documented
- coverage.json updated with API metrics
- Clear baseline established for API coverage gap closure
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-12-SUMMARY.md`
</output>

---
phase: 08-80-percent-coverage-push
plan: 07
type: execute
wave: 2
depends_on:
  - 08-80-percent-coverage-01
files_modified:
  - backend/tests/tools/test_canvas_tool_complete.py
  - backend/tests/tools/test_browser_tool_complete.py
  - backend/tests/tools/test_device_tool_complete.py
  - backend/tests/tools/test_other_tools.py
autonomous: true

must_haves:
  truths:
    - "Tools module has comprehensive tests for all tool functions"
    - "Governance checks are tested for tool execution permissions"
    - "External service mocking prevents real API calls"
    - "Error handling and timeout scenarios are covered"
  artifacts:
    - path: "backend/tests/tools/test_canvas_tool_complete.py"
      provides: "Comprehensive tests for canvas_tool.py"
      min_lines: 500
    - path: "backend/tests/tools/test_browser_tool_complete.py"
      provides: "Comprehensive tests for browser_tool.py"
      min_lines: 400
    - path: "backend/tests/tools/test_device_tool_complete.py"
      provides: "Comprehensive tests for device_tool.py"
      min_lines: 350
  key_links:
    - from: "backend/tests/tools"
      to: "backend/tools"
      via: "import tool modules for testing"
      pattern: "from tools."
    - from: "backend/tests/tools"
      to: "backend/tests/factories"
      via: "use factories for test data"
      pattern: "from tests.factories"
---

<objective>
Create comprehensive tests for the tools module, covering canvas_tool.py (379 uncovered lines), browser_tool.py, device_tool.py, and other tool files. Tests should verify tool execution, governance checks, error handling, and external service mocking.

Purpose: Ensure reliable tool execution for agent capabilities with proper governance enforcement and error handling.
Output: Test suites for tools module achieving 80%+ coverage
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@backend/tests/coverage_reports/COVERAGE_PRIORITY_ANALYSIS.md
@backend/tests/conftest.py
@backend/tools/canvas_tool.py
@backend/tools/browser_tool.py
@backend/tools/device_tool.py
@backend/tests/test_browser_automation.py
@backend/tests/test_device_tool.py
@backend/tests/factories/agent_factory.py
@backend/tests/factories/user_factory.py
</context>

<tasks>

<task type="auto">
  <name>Create comprehensive canvas_tool.py tests</name>
  <files>backend/tests/tools/test_canvas_tool_complete.py</files>
  <action>
    Create backend/tests/tools/test_canvas_tool_complete.py:

    This is a comprehensive test file that expands on the unit tests from plan 01.
    Target 80%+ coverage of tools/canvas_tool.py (379 uncovered lines).

    Test all canvas functions:
    1. present_chart() - 15 tests covering:
       - Valid chart types (line, bar, pie)
       - Invalid chart types (error handling)
       - Governance allow (INTERN+)
       - Governance block (STUDENT)
       - WebSocket broadcast
       - Audit entry creation
       - Agent execution tracking
       - Session isolation
       - Empty data handling
       - Large data handling

    2. present_markdown() - 12 tests covering:
       - Content rendering
       - Title handling
       - Agent governance
       - Audit creation
       - Session isolation
       - Empty content
       - Long content
       - Special characters
       - Markdown parsing

    3. present_form() - 15 tests covering:
       - Form schema validation
       - Field definitions
       - Agent governance (INTERN+)
       - Form submission tracking
       - Canvas ID generation
       - Session isolation
       - Invalid schemas
       - Missing fields
       - Field validation rules

    4. present_status_panel() - 10 tests covering:
       - Status item rendering
       - Trend display
       - Multiple items
       - Empty items
       - Agent governance

    5. update_canvas() - 12 tests covering:
       - Canvas update (INTERN+ governance)
       - Partial updates
       - Multiple fields
       - Non-existent canvas
       - Wrong user
       - Session isolation

    6. close_canvas() - 8 tests covering:
       - Canvas closing
       - Session-specific close
       - Broadcast to correct channel

    7. canvas_execute_javascript() - 15 tests covering:
       - AUTONOMOUS-only enforcement
       - JavaScript validation
       - Dangerous pattern detection
       - Timeout handling
       - Empty JavaScript
       - Valid JavaScript
       - Audit trail

    8. present_specialized_canvas() - 15 tests covering:
       - Canvas type validation (docs, email, sheets, etc.)
       - Component validation
       - Layout validation
       - Maturity requirements
       - Type-specific data
       - Invalid types
       - Invalid components
       - Invalid layouts

    Use pytest.mark.asyncio for all async tests.
    Mock WebSocketManager with AsyncMock.
    Mock AgentContextResolver and AgentGovernanceService.
    Use factories for user and agent data.

    Test patterns:
    ```python
    @pytest.mark.asyncio
    async def test_present_chart_success():
        with patch('tools.canvas_tool.ws_manager') as mock_ws:
            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                # Setup mocks
                # Call function
                # Assert WebSocket broadcast called
                # Assert audit entry created
    ```
  </action>
  <verify>pytest backend/tests/tools/test_canvas_tool_complete.py -v --cov=backend/tools/canvas_tool --cov-report=term-missing</verify>
  <done>All canvas_tool tests pass (100+ tests), 80%+ coverage</done>
</task>

<task type="auto">
  <name>Create comprehensive browser_tool.py tests</name>
  <files>backend/tests/tools/test_browser_tool_complete.py</files>
  <action>
    Create backend/tests/tools/test_browser_tool_complete.py:

    This expands on the existing test_browser_automation.py.
    Target 80%+ coverage of tools/browser_tool.py.

    Test all browser functions:
    1. BrowserSession class - 10 tests:
       - Initialization with all parameters
       - Session ID uniqueness
       - User ownership
       - Agent association
       - Browser type selection (chromium, firefox, webkit)

    2. BrowserSessionManager class - 15 tests:
       - Session creation
       - Session retrieval
       - Session closure
       - Session cleanup (expired)
       - Concurrent session limits
       - Session timeout tracking

    3. browser_create_session() - 12 tests:
       - Basic session creation
       - With governance (allowed)
       - With governance (blocked)
       - Headless vs headed
       - Browser type selection
       - Session timeout configuration

    4. browser_navigate() - 10 tests:
       - Valid URL navigation
       - Session not found
       - Wrong user ownership
       - Invalid URL handling
       - Navigation timeout

    5. browser_screenshot() - 10 tests:
       - Base64 screenshot
       - PNG format
       - Full page vs element
       - Session validation
       - User ownership

    6. browser_fill_form() - 15 tests:
       - Single field fill
       - Multiple fields
       - Input types (text, email, password, checkbox)
       - Submit option
       - Selector not found
       - Form validation

    7. browser_click() - 10 tests:
       - Element click
       - Selector not found
       - Wait for selector
       - Click timeout

    8. browser_extract_text() - 10 tests:
       - Full page extraction
       - Element extraction
       - Selector not found
       - Empty page

    9. browser_execute_script() - 10 tests:
       - JavaScript execution
       - Return value handling
       - Script errors
       - Security validation

    10. browser_close_session() - 8 tests:
        - Session closure
        - Session not found
        - Wrong user

    11. browser_get_page_info() - 8 tests:
        - URL retrieval
        - Title retrieval
        - Meta tags

    Mock Playwright operations:
    ```python
    @pytest.fixture
    def mock_playwright():
        with patch('tools.browser_tool.async_playwright') as mock:
            yield mock
    ```

    Test governance:
    - INTERN+ required for browser actions
    - STUDENT agents blocked
  </action>
  <verify>pytest backend/tests/tools/test_browser_tool_complete.py -v --cov=backend/tools/browser_tool --cov-report=term-missing</verify>
  <done>All browser_tool tests pass (100+ tests), 80%+ coverage</done>
</task>

<task type="auto">
  <name>Create comprehensive device_tool.py tests</name>
  <files>backend/tests/tools/test_device_tool_complete.py</files>
  <action>
    Create backend/tests/tools/test_device_tool_complete.py:

    This expands on the existing test_device_tool.py.
    Target 80%+ coverage of tools/device_tool.py.

    Test all device functions:
    1. device_camera_capture() - 12 tests:
       - Camera capture (INTERN+)
       - Image base64 encoding
       - Camera permissions
       - Camera not available
       - Governance blocked

    2. device_start_recording() - 10 tests:
       - Screen recording start (SUPERVISED+)
       - Recording options (audio, cursor)
       - Permissions
       - Already recording
       - Governance enforcement

    3. device_stop_recording() - 8 tests:
       - Recording stop
       - Video data return
       - Not recording
       - File save

    4. device_get_location() - 10 tests:
       - Location retrieval (INTERN+)
       - Coordinates accuracy
       - Permissions
       - Location services disabled
       - Governance

    5. device_send_notification() - 10 tests:
       - Notification send (INTERN+)
       - Payload validation
       - Permissions
       - Notification priority
       - Sound/vibration options

    6. device_execute_command() - 15 tests:
       - Command execution (AUTONOMOUS only!)
       - Command validation
       - Whitelist enforcement
       - Output capture
       - Error handling
       - Blocked commands
       - Timeout handling

    7. device_list_capabilities() - 8 tests:
       - List available capabilities
       - Per-platform capabilities
       - Permission status

    8. device_request_permissions() - 10 tests:
       - Request camera permission
       - Request location permission
       - Request notification permission
       - Permission grant
       - Permission denial
       - Request pending

    Mock device operations:
    ```python
    @pytest.fixture
    def mock_device_manager():
        with patch('tools.device_tool.get_device_manager') as mock:
            yield mock
    ```

    Test platform-specific behavior:
    - macOS vs Linux vs Windows
    - Mobile vs Desktop
    - Permission model differences
  </action>
  <verify>pytest backend/tests/tools/test_device_tool_complete.py -v --cov=backend/tools/device_tool --cov-report=term-missing</verify>
  <done>All device_tool tests pass (80+ tests), 80%+ coverage</done>
</task>

<task type="auto">
  <name>Create tests for remaining tool files</name>
  <files>backend/tests/tools/test_other_tools.py</files>
  <action>
    Create backend/tests/tools/test_other_tools.py:

    Test other tool files in backend/tools/:
    1. Test any remaining tools with low coverage
    2. Test tool registry functionality
    3. Test tool factory patterns
    4. Test tool governance integration

    First, identify tools needing coverage:
    ```bash
    pytest --cov=backend/tools --cov-report=term-missing
    ```

    Create tests for uncovered tools.
    Each tool should have:
    - Initialization tests
    - Execution tests
    - Error handling tests
    - Governance tests

    Common test patterns for tools:
    - Test with valid inputs
    - Test with invalid inputs
    - Test governance enforcement
    - Test external service mocking
    - Test error recovery
  </action>
  <verify>pytest backend/tests/tools/ -v --cov=backend/tools --cov-report=term-missing</verify>
  <done>All tools module tests pass, 80%+ coverage overall</done>
</task>

</tasks>

<verification>
1. Run pytest backend/tests/tools/ -v to verify all tool tests pass
2. Run pytest --cov=backend/tools backend/tests/tools/ to verify coverage
3. Check coverage.json shows 80%+ coverage for tools/ module
4. Verify all external API calls are mocked (Playwright, device APIs)
5. Confirm governance tests cover all maturity levels
6. Verify error handling tests are comprehensive
</verification>

<success_criteria>
- test_canvas_tool_complete.py created with 100+ tests
- test_browser_tool_complete.py created with 100+ tests
- test_device_tool_complete.py created with 80+ tests
- test_other_tools.py created for remaining tools
- Tools module coverage increases from 7.6% to 80%+
- All governance maturity levels tested
- All error scenarios covered
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-07-SUMMARY.md`
</output>

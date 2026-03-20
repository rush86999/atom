---
phase: 212-80pct-coverage-clean-slate
plan: WAVE2A
type: execute
wave: 2
depends_on: ["212-WAVE1A", "212-WAVE1B"]
files_modified:
  - backend/tests/test_canvas_tool.py
  - backend/tests/test_browser_tool.py
  - backend/tests/test_device_tool.py
autonomous: true

must_haves:
  truths:
    - "tools/canvas_tool.py achieves 80%+ line coverage"
    - "tools/browser_tool.py achieves 80%+ line coverage"
    - "tools/device_tool.py achieves 80%+ line coverage"
  artifacts:
    - path: "backend/tests/test_canvas_tool.py"
      provides: "Unit tests for CanvasTool"
      min_lines: 400
      exports: ["TestCanvasTool", "TestCanvasPresentation"]
    - path: "backend/tests/test_browser_tool.py"
      provides: "Unit tests for BrowserTool"
      min_lines: 350
      exports: ["TestBrowserTool", "TestBrowserAutomation"]
    - path: "backend/tests/test_device_tool.py"
      provides: "Unit tests for DeviceTool"
      min_lines: 300
      exports: ["TestDeviceTool", "TestDeviceCapabilities"]
  key_links:
    - from: "backend/tests/test_canvas_tool.py"
      to: "backend/tools/canvas_tool.py"
      via: "Direct imports and mocking"
    - from: "backend/tests/test_browser_tool.py"
      to: "backend/tools/browser_tool.py"
      via: "Direct imports and mocking"
    - from: "backend/tests/test_device_tool.py"
      to: "backend/tools/device_tool.py"
      via: "Direct imports and mocking"
---

<objective>
Increase backend coverage from 25% to 35% by testing core tool services (canvas, browser, device).

Purpose: Core tools provide agent capabilities for presentations, automation, and device access. These are foundational to agent operations. High coverage ensures reliable agent-tool interactions.

Output: 3 test files with 1,050+ total lines, achieving backend 35%+ coverage.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md
@backend/tools/canvas_tool.py
@backend/tools/browser_tool.py
@backend/tools/device_tool.py

# Test Pattern Reference
From Phase 216: Use AsyncMock for async methods, patch services at import location, mock database sessions with SessionLocal fixtures.

# Target Files Analysis

## 1. canvas_tool.py (~400 lines)
Key methods:
- present_canvas(): Create canvas presentation
- update_canvas(): Update canvas content
- close_canvas(): Close canvas session
- get_canvas_state(): Get current canvas state
- validate_canvas_permissions(): Check maturity permissions

Canvas types: CHART, MARKDOWN, FORM, SHEETS, CODING, TERMINAL, DOCS

## 2. browser_tool.py (~350 lines)
Key methods:
- navigate_to(): Navigate to URL
- click_element(): Click element
- fill_form(): Fill form fields
- take_screenshot(): Capture screenshot
- extract_content(): Extract page content
- execute_script(): Execute JavaScript

Playwright CDP integration

## 3. device_tool.py (~300 lines)
Key methods:
- get_camera(): Access camera (INTERN+)
- get_location(): Get location (INTERN+)
- record_screen(): Screen recording (SUPERVISED+)
- send_notification(): Send notification (INTERN+)
- execute_command(): Execute shell (AUTONOMOUS only)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create tests for canvas_tool</name>
  <files>backend/tests/test_canvas_tool.py</files>
  <action>
Create backend/tests/test_canvas_tool.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from tools.canvas_tool import CanvasTool

2. Fixtures:
   - mock_canvas_tool(): Returns CanvasTool with mocked dependencies
   - mock_canvas_state(): Returns test canvas state

3. Class TestCanvasPresentation:
   - test_present_chart_canvas(): Creates chart canvas
   - test_present_markdown_canvas(): Creates markdown canvas
   - test_present_form_canvas(): Creates form canvas
   - test_present_sheets_canvas(): Creates sheets canvas
   - test_presentation_requires_permission(): Checks maturity

4. Class TestCanvasUpdates:
   - test_update_canvas_content(): Updates content
   - test_update_canvas_metadata(): Updates metadata
   - test_update_canvas_preserves_audit(): Preserves audit trail

5. Class TestCanvasClosure:
   - test_close_canvas(): Closes canvas session
   - test_close_canvas_records_outcome(): Records user outcome
   - test_close_canvas_feedback(): Links to feedback

6. Class TestCanvasPermissions:
   - test_student_can_view_markdown(): STUDENT can view markdown
   - test_intern_can_stream(): INTERN can use streaming
   - test_supervised_can_submit(): SUPERVISED can submit forms
   - test_autonomous_full_access(): AUTONOMOUS has full access

7. Use parametrize for all canvas types (7 types)
  </action>
  <verify>
pytest backend/tests/test_canvas_tool.py -v
pytest backend/tests/test_canvas_tool.py --cov=tools.canvas_tool --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All canvas_tool tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 2: Create tests for browser_tool</name>
  <files>backend/tests/test_browser_tool.py</files>
  <action>
Create backend/tests/test_browser_tool.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from tools.browser_tool import BrowserTool

2. Fixtures:
   - mock_browser_tool(): Returns BrowserTool with mocked Playwright
   - mock_page(): Mock Playwright page

3. Class TestBrowserNavigation:
   - test_navigate_to_url(): Navigates to URL
   - test_navigate_to_invalid_url(): Handles invalid URL
   - test_wait_for_load(): Waits for page load
   - test_navigation_timeout(): Handles timeout

4. Class TestBrowserInteraction:
   - test_click_element(): Clicks element by selector
   - test_click_element_not_found(): Handles missing element
   - test_fill_form(): Fills form fields
   - test_fill_form_validation(): Validates form data

5. Class TestBrowserContent:
   - test_extract_text(): Extracts text content
   - test_extract_links(): Extracts all links
   - test_extract_images(): Extracts images
   - test_take_screenshot(): Captures screenshot
   - test_execute_script(): Executes JavaScript

6. Class TestBrowserPermissions:
   - test_intern_can_navigate(): INTERN can navigate
   - test_supervised_can_interact(): SUPERVISED can interact
   - test_autonomous_full_access(): AUTONOMOUS has full access
   - test_student_blocked(): STUDENT is blocked

7. Mock Playwright CDP interface
  </action>
  <verify>
pytest backend/tests/test_browser_tool.py -v
pytest backend/tests/test_browser_tool.py --cov=tools.browser_tool --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All browser_tool tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 3: Create tests for device_tool</name>
  <files>backend/tests/test_device_tool.py</files>
  <action>
Create backend/tests/test_device_tool.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from tools.device_tool import DeviceTool

2. Fixtures:
   - mock_device_tool(): Returns DeviceTool with mocked device APIs

3. Class TestCameraCapability:
   - test_get_camera(): Access camera (INTERN+)
   - test_camera_permission_check(): Checks maturity
   - test_student_blocked_camera(): STUDENT blocked

4. Class TestLocationCapability:
   - test_get_location(): Get location (INTERN+)
   - test_location_coordinates(): Returns lat/long
   - test_student_blocked_location(): STUDENT blocked

5. Class TestScreenRecording:
   - test_start_recording(): Start recording (SUPERVISED+)
   - test_stop_recording(): Stop recording
   - test_recording_permission_check(): Checks maturity
   - test_internet_blocked_recording(): INTERN blocked

6. Class TestNotifications:
   - test_send_notification(): Send notification (INTERN+)
   - test_notification_payload(): Includes title/body
   - test_student_blocked_notification(): STUDENT blocked

7. Class TestCommandExecution:
   - test_execute_command(): Execute shell (AUTONOMOUS only)
   - test_command_whitelist(): Checks whitelist
   - test_non_autonomous_blocked(): Other maturity blocked

8. Use parametrize for all device capabilities
  </action>
  <verify>
pytest backend/tests/test_device_tool.py -v
pytest backend/tests/test_device_tool.py --cov=tools.device_tool --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All device_tool tests passing, 80%+ coverage achieved
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all tests:
   pytest backend/tests/test_canvas_tool.py \
          backend/tests/test_browser_tool.py \
          backend/tests/test_device_tool.py -v

2. Verify coverage per module (all should be 80%+):
   pytest backend/tests/ --cov=tools.canvas_tool \
                         --cov=tools.browser_tool \
                         --cov=tools.device_tool \
                         --cov-report=term-missing

3. Verify overall backend coverage increase:
   pytest backend/tests/ --cov=core --cov=tools --cov-report=json
   # Backend should be 35%+ (from 25% baseline)

4. Verify no regression in existing tests:
   pytest backend/tests/ -v
</verification>

<success_criteria>
1. All 3 test files pass (100% pass rate)
2. Each of 3 modules achieves 80%+ coverage
3. Backend overall coverage >= 35%
4. No regression in existing test coverage
5. All tests execute in <30 seconds
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE2A-SUMMARY.md`
</output>

---
phase: 212-80pct-coverage-clean-slate
plan: WAVE2
type: execute
wave: 2
depends_on: ["212-WAVE1"]
files_modified:
  - backend/tests/test_canvas_tool.py
  - backend/tests/test_browser_tool.py
  - backend/tests/test_device_tool.py
  - backend/tests/test_skill_adapter.py
  - backend/tests/test_skill_composition_engine.py
  - backend/tests/test_skill_dynamic_loader.py
  - backend/tests/test_student_training_service.py
  - backend/tests/test_supervision_service.py
  - frontend/tests/components/integrations/Slack.test.tsx
  - frontend/tests/components/integrations/Jira.test.tsx
  - frontend/tests/components/integrations/GitHub.test.tsx
  - frontend/tests/components/agents/AgentManager.test.tsx
  - frontend/tests/hooks/useAgentState.test.ts
  - frontend/tests/hooks/useCanvasState.test.ts
autonomous: true

must_haves:
  truths:
    - "tools/canvas_tool.py achieves 80%+ line coverage"
    - "tools/browser_tool.py achieves 80%+ line coverage"
    - "tools/device_tool.py achieves 80%+ line coverage"
    - "skill_adapter.py achieves 80%+ line coverage"
    - "skill_composition_engine.py achieves 80%+ line coverage"
    - "skill_dynamic_loader.py achieves 80%+ line coverage"
    - "student_training_service.py achieves 80%+ line coverage"
    - "supervision_service.py achieves 80%+ line coverage"
    - "Frontend integration components achieve 45%+ coverage"
    - "Frontend state management hooks achieve 60%+ coverage"
    - "Backend coverage increases from 25% to 45%+"
    - "Frontend coverage increases from 13.42% to 45%+"
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
    - path: "backend/tests/test_skill_adapter.py"
      provides: "Unit tests for SkillAdapter"
      min_lines: 400
      exports: ["TestSkillAdapter", "TestSkillExecution"]
    - path: "backend/tests/test_skill_composition_engine.py"
      provides: "Unit tests for SkillCompositionEngine"
      min_lines: 350
      exports: ["TestSkillComposition", "TestDAGValidation"]
    - path: "frontend/tests/components/integrations/Slack.test.tsx"
      provides: "React component tests for Slack integration"
      min_lines: 250
    - path: "frontend/tests/hooks/useAgentState.test.ts"
      provides: "Hook tests for agent state management"
      min_lines: 200
  key_links:
    - from: "backend/tests/test_canvas_tool.py"
      to: "backend/tools/canvas_tool.py"
      via: "Direct imports and mocking"
    - from: "backend/tests/test_skill_adapter.py"
      to: "backend/core/skill_adapter.py"
      via: "Direct imports and mocking"
    - from: "frontend/tests/components/integrations/Slack.test.tsx"
      to: "frontend-nextjs/components/integrations/Slack.tsx"
      via: "Jest component testing"
---

<objective>
Increase backend coverage from 25% to 45% and frontend coverage from 13.42% to 45% by testing core services (canvas, browser, device, skills, training) and critical frontend components.

Purpose: Core tools provide agent capabilities (presentations, automation, device access). Frontend components are the primary user interface. High coverage ensures reliable agent-user interactions.

Output: 12 test files (8 backend, 4 frontend) with 3,500+ total lines, achieving backend 45%+ and frontend 45%+ coverage.
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
@backend/core/skill_adapter.py
@backend/core/skill_composition_engine.py
@backend/core/skill_dynamic_loader.py
@backend/core/student_training_service.py
@backend/core/supervision_service.py

# Frontend Test Pattern Reference
From Phase 130: Use React Testing Library, mock API calls, test user interactions, state changes, and accessibility.

# Target Backend Files Analysis

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

## 4. skill_adapter.py (~400 lines)
Key methods:
- load_skill(): Load OpenClaw/ClawHub skill
- validate_skill(): Validate SKILL.md
- execute_skill(): Execute skill function
- sandbox_execution(): Hazard sandbox
- parse_skill_metadata(): Extract metadata

## 5. skill_composition_engine.py (~350 lines)
Key methods:
- create_dag(): Create workflow DAG
- validate_dag(): Detect cycles
- execute_dag(): Execute workflow
- resolve_dependencies(): Resolve skill dependencies
- parallel_execution(): Execute independent skills

NetworkX-based DAG validation

## 6. skill_dynamic_loader.py (~300 lines)
Key methods:
- hot_reload(): Watch for file changes
- load_skill_module(): Dynamic importlib loading
- unload_skill(): Unload skill module
- list_loaded_skills(): List active skills

Watchdog file monitoring

## 7. student_training_service.py (~350 lines)
Key methods:
- estimate_training_duration(): AI-based estimation
- create_training_session(): Create training
- track_progress(): Track training progress
- complete_training(): Mark complete
- get_training_proposals(): Get proposals

## 8. supervision_service.py (~300 lines)
Key methods:
- start_supervision(): Start supervision session
- monitor_execution(): Real-time monitoring
- pause_execution(): Pause agent
- correct_execution(): Correct agent action
- terminate_execution(): Stop agent

# Frontend Target Files

## Integration Components
- Slack.tsx: Slack integration UI
- Jira.tsx: Jira integration UI
- GitHub.tsx: GitHub integration UI

## Agent Components
- AgentManager.tsx: Agent management UI

## State Management Hooks
- useAgentState.ts: Agent state hook
- useCanvasState.ts: Canvas state hook
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

<task type="auto">
  <name>Task 4: Create tests for skill_adapter</name>
  <files>backend/tests/test_skill_adapter.py</files>
  <action>
Create backend/tests/test_skill_adapter.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.skill_adapter import SkillAdapter

2. Fixtures:
   - mock_adapter(): Returns SkillAdapter
   - mock_skill_metadata(): Returns test SKILL.md parsed data

3. Class TestSkillLoading:
   - test_load_skill_success(): Loads valid skill
   - test_load_skill_invalid_path(): Handles invalid path
   - test_load_skill_missing_metadata(): Handles missing SKILL.md
   - test_load_skill_parse_error(): Handles parse errors

4. Class TestSkillValidation:
   - test_validate_skill_valid(): Validates valid skill
   - test_validate_skill_missing_name(): Requires name
   - test_validate_skill_missing_description(): Requires description
   - test_validate_skill_missing_python(): Requires Python for backend skills

5. Class TestSkillExecution:
   - test_execute_skill_success(): Executes skill function
   - test_execute_skill_with_args(): Passes arguments
   - test_execute_skill_handles_error(): Handles skill errors
   - test_execute_skill_timeout(): Handles timeout

6. Class TestSandboxExecution:
   - test_sandbox_python(): Sandboxes Python execution
   - test_sandbox_network_disabled(): Network disabled in sandbox
   - test_sandbox_resource_limits(): Enforces resource limits
   - test_sandbox_readonly_fs(): Read-only filesystem

7. Class TestSecurityValidation:
   - test_detect_typosquatting(): Detects typosquat packages
   - test_detect_dependency_confusion(): Detects dependency confusion
   - test_scan_vulnerabilities(): Scans with pip-audit
   - test_block_unsafe_skills(): Blocks unsafe skills

8. Mock file system, subprocess, pip-audit
  </action>
  <verify>
pytest backend/tests/test_skill_adapter.py -v
pytest backend/tests/test_skill_adapter.py --cov=core.skill_adapter --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All skill_adapter tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 5: Create tests for skill_composition_engine</name>
  <files>backend/tests/test_skill_composition_engine.py</files>
  <action>
Create backend/tests/test_skill_composition_engine.py with comprehensive tests:

1. Imports: pytest, from core.skill_composition_engine import SkillCompositionEngine

2. Fixtures:
   - mock_engine(): Returns SkillCompositionEngine
   - mock_dag(): Returns NetworkX DAG

3. Class TestDAGCreation:
   - test_create_simple_dag(): Creates simple workflow
   - test_create_parallel_dag(): Creates parallel branches
   - test_create_sequential_dag(): Creates sequential flow
   - test_create_conditional_dag(): Creates conditional branches

4. Class TestDAGValidation:
   - test_validate_valid_dag(): Passes valid DAG
   - test_detect_cycle(): Detects circular dependency
   - test_detect_orphan(): Detects orphan nodes
   - test_validate_missing_dependencies(): Detects missing deps

5. Class TestDAGExecution:
   - test_execute_sequential(): Executes sequentially
   - test_execute_parallel(): Executes in parallel
   - test_execute_with_failure(): Continues on failure
   - test_execute_timeout(): Handles timeout

6. Class TestDependencyResolution:
   - test_resolve_dependencies(): Resolves skill deps
   - test_detect_version_conflict(): Detects version conflicts
   - test_detect_cycle_dependencies(): Detects cycles
   - test_install_missing_deps(): Installs missing deps

7. Use NetworkX for DAG operations
  </action>
  <verify>
pytest backend/tests/test_skill_composition_engine.py -v
pytest backend/tests/test_skill_composition_engine.py --cov=core.skill_composition_engine --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All skill_composition_engine tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 6: Create tests for skill_dynamic_loader</name>
  <files>backend/tests/test_skill_dynamic_loader.py</files>
  <action>
Create backend/tests/test_skill_dynamic_loader.py with comprehensive tests:

1. Imports: pytest, from core.skill_dynamic_loader import SkillDynamicLoader

2. Fixtures:
   - mock_loader(): Returns SkillDynamicLoader
   - mock_skill_module(): Returns test skill module

3. Class TestSkillLoading:
   - test_load_skill_module(): Loads skill with importlib
   - test_load_skill_reload(): Reloads existing skill
   - test_load_skill_import_error(): Handles import errors
   - test_load_skill_syntax_error(): Handles syntax errors

4. Class TestSkillUnloading:
   - test_unload_skill(): Unloads skill module
   - test_unload_nonexistent(): Handles nonexistent skill
   - test_unload_cleanup(): Cleans up resources

5. Class TestHotReload:
   - test_watch_file_changes(): Uses watchdog to watch files
   - test_reload_on_change(): Reloads on file change
   - test_reload_debounce(): Debounces rapid changes
   - test_reload_preserves_state(): Preserves state during reload

6. Class TestSkillListing:
   - test_list_loaded_skills(): Lists all loaded skills
   - test_list_skills_by_category(): Groups by category
   - test_list_skill_metadata(): Returns metadata

7. Mock importlib, watchdog, file system
  </action>
  <verify>
pytest backend/tests/test_skill_dynamic_loader.py -v
pytest backend/tests/test_skill_dynamic_loader.py --cov=core.skill_dynamic_loader --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All skill_dynamic_loader tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 7: Create tests for student_training_service</name>
  <files>backend/tests/test_student_training_service.py</files>
  <action>
Create backend/tests/test_student_training_service.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.student_training_service import StudentTrainingService

2. Fixtures:
   - mock_service(): Returns StudentTrainingService
   - mock_training_session(): Returns test training session

3. Class TestTrainingEstimation:
   - test_estimate_duration(): Estimates training time
   - test_estimate_based_on_history(): Uses historical data
   - test_estimate_for_new_agent(): Uses default for new agent
   - test_estimate_with_override(): Allows user override

4. Class TestTrainingSessions:
   - test_create_training_session(): Creates session
   - test_start_training(): Starts training
   - test_track_progress(): Tracks progress
   - test_complete_training(): Marks complete
   - test_training_modules_required(): Requires specific modules

5. Class TestTrainingProposals:
   - test_get_proposals(): Gets training proposals
   - test_proposal_includes_modules(): Includes required modules
   - test_proposal_estimated_duration(): Includes time estimate
   - test_accept_proposal(): Accepts proposal
   - test_reject_proposal(): Rejects proposal

6. Class TestTrainingProgress:
   - test_update_progress(): Updates progress
   - test_progress_percentage(): Calculates percentage
   - test_complete_all_modules(): Requires all modules
   - test_incomplete_modules(): Tracks incomplete

7. Mock database sessions, historical data
  </action>
  <verify>
pytest backend/tests/test_student_training_service.py -v
pytest backend/tests/test_student_training_service.py --cov=core.student_training_service --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All student_training_service tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 8: Create tests for supervision_service</name>
  <files>backend/tests/test_supervision_service.py</files>
  <action>
Create backend/tests/test_supervision_service.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.supervision_service import SupervisionService

2. Fixtures:
   - mock_service(): Returns SupervisionService
   - mock_supervision_session(): Returns test session

3. Class TestSupervisionSessions:
   - test_start_supervision(): Starts supervision
   - test_start_for_supervised_agent(): Only for SUPERVISED agents
   - test_monitor_execution(): Monitors agent execution
   - test_stop_supervision(): Stops supervision

4. Class TestRealTimeMonitoring:
   - test_pause_execution(): Pauses agent
   - test_resume_execution(): Resumes agent
   - test_correct_execution(): Corrects agent action
   - test_terminate_execution(): Terminates agent

5. Class TestSupervisionEvents:
   - test_log_event(): Logs supervision event
   - test_event_intervention(): Logs intervention
   - test_event_auto_approval(): Logs auto-approval
   - test_get_events(): Retrieves events

6. Class TestSupervisionPermissions:
   - test_supervisor_can_pause(): Supervisor can pause
   - test_supervisor_can_terminate(): Supervisor can terminate
   - test_supervisor_can_correct(): Supervisor can correct
   - test_non_supervisor_blocked(): Non-supervisors blocked

7. Mock WebSocket events, database sessions
  </action>
  <verify>
pytest backend/tests/test_supervision_service.py -v
pytest backend/tests/test_supervision_service.py --cov=core.supervision_service --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All supervision_service tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 9: Create frontend tests for Slack integration</name>
  <files>frontend-nextjs/tests/components/integrations/Slack.test.tsx</files>
  <action>
Create frontend-nextjs/tests/components/integrations/Slack.test.tsx:

1. Imports: @testing-library/react, @testing-library/user-event, render, screen
2. Import Slack component

3. Describe 'Slack Integration Component':
   - test_renders_slack_connect_button(): Renders connect button
   - test_click_connect_opens_oauth(): Opens OAuth flow
   - test_renders_connected_state(): Shows connected state
   - test_renders_channels_list(): Lists channels
   - test_send_message(): Sends message to channel
   - test_disconnect(): Disconnects integration

4. Mock API calls (MSW or fetch mock)

5. Test user interactions: click, type, submit

6. Test accessibility: ARIA labels, keyboard navigation
  </action>
  <verify>
cd frontend-nextjs && npm test -- Slack.test.tsx --coverage
# Coverage should be 45%+
  </verify>
  <done>
All Slack integration tests passing, 45%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 10: Create frontend tests for Jira integration</name>
  <files>frontend-nextjs/tests/components/integrations/Jira.test.tsx</files>
  <action>
Create frontend-nextjs/tests/components/integrations/Jira.test.tsx:

1. Imports: @testing-library/react, @testing-library/user-event

2. Describe 'Jira Integration Component':
   - test_renders_jira_connect_button(): Renders connect button
   - test_renders_projects_list(): Lists Jira projects
   - test_create_issue(): Opens create issue dialog
   - test_submit_issue(): Submits new issue
   - test_view_issues(): Lists existing issues
   - test_search_issues(): Searches issues

3. Mock Jira API responses

4. Test form validation

5. Test error handling
  </action>
  <verify>
cd frontend-nextjs && npm test -- Jira.test.tsx --coverage
# Coverage should be 45%+
  </verify>
  <done>
All Jira integration tests passing, 45%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 11: Create frontend tests for GitHub integration</name>
  <files>frontend-nextjs/tests/components/integrations/GitHub.test.tsx</files>
  <action>
Create frontend-nextjs/tests/components/integrations/GitHub.test.tsx:

1. Imports: @testing-library/react, @testing-library/user-event

2. Describe 'GitHub Integration Component':
   - test_renders_github_connect_button(): Renders connect button
   - test_renders_repositories_list(): Lists repos
   - test_create_issue(): Creates GitHub issue
   - test_view_issues(): Lists issues
   - test_create_pull_request(): Creates PR
   - test_merge_pull_request(): Merges PR

3. Mock GitHub API responses

4. Test OAuth flow
  </action>
  <verify>
cd frontend-nextjs && npm test -- GitHub.test.tsx --coverage
# Coverage should be 45%+
  </verify>
  <done>
All GitHub integration tests passing, 45%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 12: Create frontend tests for AgentManager and hooks</name>
  <files>frontend-nextjs/tests/components/agents/AgentManager.test.tsx frontend-nextjs/tests/hooks/useAgentState.test.ts frontend-nextjs/tests/hooks/useCanvasState.test.ts</files>
  <action>
Create frontend tests for agent components and hooks:

1. frontend-nextjs/tests/components/agents/AgentManager.test.tsx:
   - test_renders_agent_list(): Lists all agents
   - test_renders_agent_maturity(): Shows maturity level
   - test_renders_agent_confidence(): Shows confidence score
   - test_promote_agent(): Promotes agent maturity
   - test_demote_agent(): Demotes agent maturity
   - test_delete_agent(): Deletes agent

2. frontend-nextjs/tests/hooks/useAgentState.test.ts:
   - test_initial_state(): Initializes with empty state
   - test_fetch_agents(): Fetches agents from API
   - test_update_agent(): Updates agent state
   - test_delete_agent(): Removes from state
   - test_filter_by_maturity(): Filters agents

3. frontend-nextjs/tests/hooks/useCanvasState.test.ts:
   - test_initial_canvas_state(): Initializes state
   - test_subscribe_to_canvas(): Subscribes to canvas updates
   - test_unsubscribe_from_canvas(): Unsubscribes
   - test_get_canvas_state(): Gets current state
   - test_get_all_canvas_states(): Gets all states

4. Use @testing-library/react-hooks for hook tests

5. Mock API responses
  </action>
  <verify>
cd frontend-nextjs && npm test -- AgentManager.test.tsx useAgentState.test.ts useCanvasState.test.ts --coverage
# Coverage should be 60%+ for hooks
  </verify>
  <done>
All agent component and hook tests passing, 60%+ coverage achieved
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all backend tests:
   pytest backend/tests/test_canvas_tool.py \
          backend/tests/test_browser_tool.py \
          backend/tests/test_device_tool.py \
          backend/tests/test_skill_adapter.py \
          backend/tests/test_skill_composition_engine.py \
          backend/tests/test_skill_dynamic_loader.py \
          backend/tests/test_student_training_service.py \
          backend/tests/test_supervision_service.py -v

2. Verify backend coverage (target 45%+):
   pytest backend/tests/ --cov=core --cov=tools --cov-report=json
   # Backend should be 45%+

3. Run all frontend tests:
   cd frontend-nextjs
   npm test -- --coverage --watchAll=false

4. Verify frontend coverage (target 45%+):
   cat coverage/coverage-summary.json | jq '.total.lines.pct'
   # Frontend should be 45%+

5. Verify no regressions
</verification>

<success_criteria>
1. All 8 backend test files pass (100% pass rate)
2. All 4 frontend test files pass (100% pass rate)
3. Backend coverage >= 45%
4. Frontend coverage >= 45%
5. All tools/canvas_tool.py tests achieve 80%+
6. All core/skill_* tests achieve 80%+
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE2-SUMMARY.md`
</output>

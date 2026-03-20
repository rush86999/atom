---
phase: 212-80pct-coverage-clean-slate
plan: WAVE2C
type: execute
wave: 2
depends_on: ["212-WAVE1A", "212-WAVE1B"]
files_modified:
  - backend/tests/test_student_training_service.py
  - backend/tests/test_supervision_service.py
  - frontend/tests/components/integrations/Slack.test.tsx
  - frontend/tests/components/integrations/Jira.test.tsx
  - frontend/tests/components/integrations/GitHub.test.tsx
  - frontend/tests/components/agents/AgentManager.test.tsx
autonomous: true

must_haves:
  truths:
    - "student_training_service.py achieves 80%+ line coverage"
    - "supervision_service.py achieves 80%+ line coverage"
    - "Frontend integration components achieve 40%+ coverage"
    - "Backend coverage increases from 25% to 45%+"
    - "Frontend coverage increases from 13.42% to 30%+"
  artifacts:
    - path: "backend/tests/test_student_training_service.py"
      provides: "Unit tests for StudentTrainingService"
      min_lines: 350
      exports: ["TestTrainingEstimation", "TestTrainingSessions"]
    - path: "backend/tests/test_supervision_service.py"
      provides: "Unit tests for SupervisionService"
      min_lines: 300
      exports: ["TestSupervisionSessions", "TestRealTimeMonitoring"]
    - path: "frontend/tests/components/integrations/Slack.test.tsx"
      provides: "React component tests for Slack integration"
      min_lines: 250
    - path: "frontend/tests/components/agents/AgentManager.test.tsx"
      provides: "React component tests for AgentManager"
      min_lines: 250
  key_links:
    - from: "backend/tests/test_student_training_service.py"
      to: "backend/core/student_training_service.py"
      via: "Direct imports and mock database"
    - from: "backend/tests/test_supervision_service.py"
      to: "backend/core/supervision_service.py"
      via: "Direct imports and mock WebSocket"
    - from: "frontend/tests/components/integrations/Slack.test.tsx"
      to: "frontend-nextjs/components/integrations/Slack.tsx"
      via: "Jest component testing"
---

<objective>
Increase backend coverage to 45% and frontend coverage to 30% by testing training/supervision services and integration components.

Purpose: Student training and supervision services enable agent maturity progression. Frontend integration components are the primary user interface for third-party connections.

Output: 5 test files (2 backend, 3 frontend) with 1,400+ total lines, achieving backend 45%+ and frontend 30%+ coverage.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md
@backend/core/student_training_service.py
@backend/core/supervision_service.py

# Frontend Test Pattern Reference
From Phase 130: Use React Testing Library, mock API calls, test user interactions, state changes, and accessibility.

# Target Backend Files Analysis

## 1. student_training_service.py (~350 lines)
Key methods:
- estimate_training_duration(): AI-based estimation
- create_training_session(): Create training
- track_progress(): Track training progress
- complete_training(): Mark complete
- get_training_proposals(): Get proposals

## 2. supervision_service.py (~300 lines)
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
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create tests for student_training_service</name>
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
  <name>Task 2: Create tests for supervision_service</name>
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
  <name>Task 3: Create frontend tests for integrations</name>
  <files>frontend-nextjs/tests/components/integrations/Slack.test.tsx frontend-nextjs/tests/components/integrations/Jira.test.tsx frontend-nextjs/tests/components/integrations/GitHub.test.tsx</files>
  <action>
Create React component tests for integration components:

1. frontend-nextjs/tests/components/integrations/Slack.test.tsx:
   - test_renders_slack_connect_button(): Renders connect button
   - test_click_connect_opens_oauth(): Opens OAuth flow
   - test_renders_connected_state(): Shows connected state
   - test_renders_channels_list(): Lists channels
   - test_send_message(): Sends message to channel
   - test_disconnect(): Disconnects integration

2. frontend-nextjs/tests/components/integrations/Jira.test.tsx:
   - test_renders_jira_connect_button(): Renders connect button
   - test_renders_projects_list(): Lists Jira projects
   - test_create_issue(): Opens create issue dialog
   - test_submit_issue(): Submits new issue
   - test_view_issues(): Lists existing issues
   - test_search_issues(): Searches issues

3. frontend-nextjs/tests/components/integrations/GitHub.test.tsx:
   - test_renders_github_connect_button(): Renders connect button
   - test_renders_repositories_list(): Lists repos
   - test_create_issue(): Creates GitHub issue
   - test_view_issues(): Lists issues
   - test_create_pull_request(): Creates PR
   - test_merge_pull_request(): Merges PR

4. Mock API calls (MSW or fetch mock)

5. Test user interactions: click, type, submit

6. Test accessibility: ARIA labels, keyboard navigation
  </action>
  <verify>
cd frontend-nextjs && npm test -- Slack.test.tsx Jira.test.tsx GitHub.test.tsx --coverage
# Frontend coverage should be 30%+
  </verify>
  <done>
All integration component tests passing, 30%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 4: Create frontend tests for AgentManager</name>
  <files>frontend-nextjs/tests/components/agents/AgentManager.test.tsx</files>
  <action>
Create frontend-nextjs/tests/components/agents/AgentManager.test.tsx:

1. Test agent management:
   - test_renders_agent_list(): Lists all agents
   - test_renders_agent_maturity(): Shows maturity level
   - test_renders_agent_confidence(): Shows confidence score
   - test_promote_agent(): Promotes agent maturity
   - test_demote_agent(): Demotes agent maturity
   - test_delete_agent(): Deletes agent
   - test_create_new_agent(): Opens create dialog
   - test_filter_by_maturity(): Filters agents

2. Use @testing-library/react

3. Mock API responses

4. Test state updates and user interactions
  </action>
  <verify>
cd frontend-nextjs && npm test -- AgentManager.test.tsx --coverage
# Frontend coverage should be 30%+
  </verify>
  <done>
All AgentManager tests passing, 30%+ coverage achieved
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all backend tests:
   pytest backend/tests/test_student_training_service.py \
          backend/tests/test_supervision_service.py -v

2. Verify backend coverage (target 45%+):
   pytest backend/tests/ --cov=core --cov=tools --cov-report=json
   # Backend should be 45%+

3. Run all frontend tests:
   cd frontend-nextjs
   npm test -- --coverage --watchAll=false

4. Verify frontend coverage (target 30%+):
   cat coverage/coverage-summary.json | jq '.total.lines.pct'
   # Frontend should be 30%+

5. Verify no regressions
</verification>

<success_criteria>
1. All 2 backend test files pass (100% pass rate)
2. All 4 frontend test files pass (100% pass rate)
3. Backend coverage >= 45%
4. Frontend coverage >= 30%
5. All backend modules tested achieve 80%+
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE2C-SUMMARY.md`
</output>

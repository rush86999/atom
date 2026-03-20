---
phase: 212-80pct-coverage-clean-slate
plan: WAVE3
type: execute
wave: 3
depends_on: ["212-WAVE2"]
files_modified:
  - backend/tests/test_episode_lifecycle_service.py
  - backend/tests/test_agent_world_model.py
  - backend/tests/test_policy_fact_extractor.py
  - backend/tests/test_atom_cli_skill_wrapper.py
  - backend/tests/test_models.py
  - mobile/src/components/__tests__/Camera.test.tsx
  - mobile/src/components/__tests__/Location.test.tsx
  - mobile/src/components/__tests__/Notifications.test.tsx
  - mobile/src/storage/__tests__/AsyncStorage.test.ts
  - mobile/src/navigation/__tests__/Navigation.test.tsx
  - desktop-app/src-tauri/tests/core_logic_test.rs
  - desktop-app/src-tauri/tests/ipc_handlers_test.rs
  - desktop-app/src/components/__tests__/WindowManager.test.tsx
  - backend/tests/test_api_contracts.py
  - backend/tests/test_e2e_integration.py
autonomous: true

must_haves:
  truths:
    - "episode_lifecycle_service.py achieves 80%+ coverage"
    - "agent_world_model.py achieves 80%+ coverage"
    - "policy_fact_extractor.py achieves 80%+ coverage"
    - "atom_cli_skill_wrapper.py achieves 80%+ coverage"
    - "models.py achieves 80%+ coverage"
    - "Backend coverage increases from 45% to 80%+"
    - "Mobile coverage increases from 0% to 70%+"
    - "Desktop Rust backend achieves 70%+ coverage"
    - "Desktop Tauri frontend achieves 70%+ coverage"
    - "API contract tests validate OpenAPI spec"
    - "E2E integration tests pass"
  artifacts:
    - path: "backend/tests/test_episode_lifecycle_service.py"
      provides: "Unit tests for EpisodeLifecycleService"
      min_lines: 350
      exports: ["TestEpisodeLifecycle", "TestEpisodeDecay"]
    - path: "backend/tests/test_agent_world_model.py"
      provides: "Unit tests for WorldModelService"
      min_lines: 400
      exports: ["TestWorldModelService", "TestBusinessFacts"]
    - path: "backend/tests/test_policy_fact_extractor.py"
      provides: "Unit tests for PolicyFactExtractor"
      min_lines: 300
      exports: ["TestPolicyFactExtractor", "TestPDFExtraction"]
    - path: "mobile/src/components/__tests__/Camera.test.tsx"
      provides: "React Native tests for Camera component"
      min_lines: 200
    - path: "desktop-app/src-tauri/tests/core_logic_test.rs"
      provides: "Rust tests for desktop core logic"
      min_lines: 300
      exports: ["test_core_logic", "test_file_operations"]
  key_links:
    - from: "backend/tests/test_episode_lifecycle_service.py"
      to: "backend/core/episode_lifecycle_service.py"
      via: "Direct imports and mock database"
    - from: "backend/tests/test_agent_world_model.py"
      to: "backend/core/agent_world_model.py"
      via: "Direct imports and mock LanceDB"
    - from: "backend/tests/test_api_contracts.py"
      to: "backend/api/**/*.py"
      via: "OpenAPI spec validation (schemathesis)"
---

<objective>
Complete backend coverage (45% -> 80%), establish mobile testing foundation (0% -> 70%), and establish desktop testing (0% -> 70%) with API contract and E2E integration tests.

Purpose: This wave completes the critical mass of coverage across all platforms. Backend reaches 80% target. Mobile and desktop establish their test infrastructure. API contracts ensure integration reliability.

Output: 13 test files (5 backend, 4 mobile, 2 desktop, 2 integration) with 4,000+ total lines, achieving backend 80%+, mobile 70%+, desktop 70%+.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md
@backend/core/episode_lifecycle_service.py
@backend/core/agent_world_model.py
@backend/core/policy_fact_extractor.py
@backend/tools/atom_cli_skill_wrapper.py
@backend/core/models.py

# Mobile Testing Pattern Reference
React Native Testing Library: @testing-library/react-native
Mock native modules: react-native-mock-render
Async storage mock: @react-native-async-storage/async-storage/jest/async-storage-mock

# Desktop Testing Pattern Reference
Rust: cargo test, tarpaulin for coverage
Tauri: @tauri-apps/api mock

# Target Backend Files Analysis

## 1. episode_lifecycle_service.py (~300 lines)
Key methods:
- create_episode(): Create new episode
- decay_episode(): Decay old episodes
- consolidate_episode(): Merge related episodes
- archive_episode(): Archive to cold storage
- get_episode_stats(): Get episode statistics

## 2. agent_world_model.py (~500 lines)
Key methods:
- record_experience(): Record agent experience
- retrieve_experiences(): Retrieve relevant experiences
- create_business_fact(): Create business fact
- verify_citation(): Verify fact citation
- semantic_search(): Semantic fact search

## 3. policy_fact_extractor.py (~300 lines)
Key methods:
- extract_facts_from_document(): Extract facts from PDF
- parse_policy_document(): Parse policy structure
- detect_citations(): Detect citations in text
- validate_citation_format(): Validate citation format

## 4. atom_cli_skill_wrapper.py (~250 lines)
Key methods:
- execute_cli_command(): Execute CLI command
- parse_cli_output(): Parse command output
- handle_timeout(): Handle command timeout
- validate_command(): Validate command against whitelist

## 5. models.py (~4,200 lines)
Key models:
- AgentRegistry: Agent registration
- AgentExecution: Execution tracking
- AgentFeedback: Feedback tracking
- Episode: Episode data
- EpisodeSegment: Segment data
- BusinessFact: Business facts
- CanvasAudit: Canvas audit trail
- 20+ other models

# Mobile Target Files

## Device Features
- Camera.test.tsx: Camera component tests
- Location.test.tsx: Location component tests
- Notifications.test.tsx: Notification tests

## State Management
- AsyncStorage.test.ts: Storage tests
- Navigation.test.tsx: Navigation tests

# Desktop Target Files

## Rust Backend
- core_logic_test.rs: Core logic tests
- ipc_handlers_test.rs: IPC handler tests

## Tauri Frontend
- WindowManager.test.tsx: Window management tests
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create tests for episode_lifecycle_service</name>
  <files>backend/tests/test_episode_lifecycle_service.py</files>
  <action>
Create backend/tests/test_episode_lifecycle_service.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.episode_lifecycle_service import EpisodeLifecycleService

2. Fixtures:
   - mock_service(): Returns EpisodeLifecycleService
   - mock_episode(): Returns test Episode

3. Class TestEpisodeCreation:
   - test_create_episode(): Creates new episode
   - test_create_episode_with_segments(): Includes segments
   - test_create_episode_auto_title(): Auto-generates title
   - test_create_episode_links_to_agent(): Links to agent

4. Class TestEpisodeDecay:
   - test_decay_old_episode(): Decays episodes older than threshold
   - test_decay_preserves_recent(): Preserves recent episodes
   - test_decay_reduces_access_score(): Reduces access score
   - test_no_decay_below_threshold(): Stops at minimum score

5. Class TestEpisodeConsolidation:
   - test_consolidate_related_episodes(): Merges related episodes
   - test_consolidation_preserves_segments(): Preserves all segments
   - test_consolidation_updates_metadata(): Updates metadata
   - test_no_consolidation_unrelated(): Rejects unrelated episodes

6. Class TestEpisodeArchival:
   - test_archive_episode(): Archives to LanceDB
   - test_archive_batch(): Archives batch of episodes
   - test_archive_removes_from_hot(): Removes from PostgreSQL
   - test_archive_preserves_indexing(): Preserves search index

7. Class TestEpisodeStatistics:
   - test_get_episode_stats(): Returns episode statistics
   - test_stats_by_agent(): Groups by agent
   - test_stats_by_time_range(): Filters by time
   - test_stats_includes_feedback(): Includes feedback metrics

8. Mock database sessions, LanceDB client
  </action>
  <verify>
pytest backend/tests/test_episode_lifecycle_service.py -v
pytest backend/tests/test_episode_lifecycle_service.py --cov=core.episode_lifecycle_service --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All episode_lifecycle_service tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 2: Create tests for agent_world_model</name>
  <files>backend/tests/test_agent_world_model.py</files>
  <action>
Create backend/tests/test_agent_world_model.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.agent_world_model import WorldModelService, AgentExperience, BusinessFact

2. Fixtures:
   - mock_service(): Returns WorldModelService
   - mock_experience(): Returns test AgentExperience
   - mock_business_fact(): Returns test BusinessFact

3. Class TestExperienceRecording:
   - test_record_experience(): Records agent experience
   - test_record_experience_with_outcome(): Includes outcome
   - test_record_experience_with_learnings(): Includes learnings
   - test_experience_vector_embedding(): Creates vector embedding

4. Class TestExperienceRetrieval:
   - test_retrieve_by_agent(): Retrieves by agent_id
   - test_retrieve_by_task_type(): Filters by task type
   - test_retrieve_by_time_range(): Filters by time
   - test_retrieve_semantic(): Semantic similarity search
   - test_retrieve_top_k(): Returns top K results

5. Class TestBusinessFacts:
   - test_create_business_fact(): Creates business fact
   - test_fact_with_citation(): Includes citation
   - test_fact_verification(): Verifies citation
   - test_fact_semantic_search(): Semantic fact search
   - test_fact_by_id(): Retrieves by ID

6. Class TestCitationVerification:
   - test_verify_citation_valid(): Verifies valid citation
   - test_verify_citation_invalid(): Rejects invalid citation
   - test_verify_s3_citation(): Verifies S3 URI
   - test_verify_r2_citation(): Verifies R2 URI
   - test_verify_local_file(): Verifies local file

7. Mock LanceDB client, S3/R2 storage, PDF parser
  </action>
  <verify>
pytest backend/tests/test_agent_world_model.py -v
pytest backend/tests/test_agent_world_model.py --cov=core.agent_world_model --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All agent_world_model tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 3: Create tests for policy_fact_extractor</name>
  <files>backend/tests/test_policy_fact_extractor.py</files>
  <action>
Create backend/tests/test_policy_fact_extractor.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.policy_fact_extractor import PolicyFactExtractor

2. Fixtures:
   - mock_extractor(): Returns PolicyFactExtractor
   - mock_pdf_content(): Returns test PDF bytes

3. Class TestPDFExtraction:
   - test_extract_from_pdf(): Extracts facts from PDF
   - test_extract_handles_encrypted_pdf(): Handles encrypted PDFs
   - test_extract_handles_corrupt_pdf(): Handles corrupt PDFs
   - test_extract_multi_page(): Handles multi-page PDFs

4. Class TestFactDetection:
   - test_detect_rules(): Detects rule statements
   - test_detect_policies(): Detects policy statements
   - test_detect_requirements(): Detects requirements
   - test_extract_confidence(): Extracts confidence score

5. Class TestCitationDetection:
   - test_detect_citations(): Detects in-text citations
   - test_parse_page_citation(): Parses "page:N" format
   - test_parse_section_citation(): Parses "section:N" format
   - test_validate_citation_format(): Validates format

6. Class TestFactStructuring:
   - test_structure_fact(): Structures fact with metadata
   - test_fact_with_source(): Includes source document
   - test_fact_with_context(): Includes surrounding context
   - test_fact_aggregation(): Aggregates related facts

7. Mock PyPDF2, pdfplumber, LLM extraction
  </action>
  <verify>
pytest backend/tests/test_policy_fact_extractor.py -v
pytest backend/tests/test_policy_fact_extractor.py --cov=core.policy_fact_extractor --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All policy_fact_extractor tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 4: Create tests for atom_cli_skill_wrapper</name>
  <files>backend/tests/test_atom_cli_skill_wrapper.py</files>
  <action>
Create backend/tests/test_atom_cli_skill_wrapper.py with comprehensive tests:

1. Imports: pytest, from tools.atom_cli_skill_wrapper import AtomCliSkillWrapper

2. Fixtures:
   - mock_wrapper(): Returns AtomCliSkillWrapper
   - mock_subprocess_result(): Returns subprocess result

3. Class TestCommandExecution:
   - test_execute_daemon_command(): Executes daemon command
   - test_execute_status_command(): Executes status command
   - test_execute_start_command(): Executes start command
   - test_execute_stop_command(): Executes stop command
   - test_execute_config_command(): Executes config command

4. Class TestCommandValidation:
   - test_validate_whitelisted_command(): Allows whitelisted
   - test_validate_blocked_command(): Blocks non-whitelisted
   - test_validate_maturity_check(): Checks maturity level
   - test_autonomous_only_commands(): AUTONOMOUS only for some commands

5. Class TestOutputParsing:
   - test_parse_json_output(): Parses JSON output
   - test_parse_text_output(): Parses text output
   - test_parse_error_output(): Parses error output
   - test_handle_malformed_output(): Handles malformed output

6. Class TestTimeoutHandling:
   - test_timeout_after_30_seconds(): Times out after 30s
   - test_timeout_custom_duration(): Uses custom timeout
   - test_timeout_kills_process(): Kills process on timeout
   - test_timeout_returns_error(): Returns error on timeout

7. Mock subprocess.run, subprocess.Popen
  </action>
  <verify>
pytest backend/tests/test_atom_cli_skill_wrapper.py -v
pytest backend/tests/test_atom_cli_skill_wrapper.py --cov=tools.atom_cli_skill_wrapper --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All atom_cli_skill_wrapper tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 5: Create tests for database models</name>
  <files>backend/tests/test_models.py</files>
  <action>
Create backend/tests/test_models.py with comprehensive model tests:

1. Imports: pytest, from core.models import [all models]

2. Class TestAgentRegistry:
   - test_create_agent(): Creates agent with defaults
   - test_agent_maturity_enum(): Validates maturity values
   - test_agent_confidence_range(): Validates 0-1 range
   - test_agent_relationships(): Tests relationships

3. Class TestAgentExecution:
   - test_create_execution(): Creates execution record
   - test_execution_status_enum(): Validates status values
   - test_execution_timestamps(): Validates timestamps
   - test_execution_feedback_link(): Links to feedback

4. Class TestEpisode:
   - test_create_episode(): Creates episode
   - test_episode_segments(): Has many segments
   - test_episode_feedback_links(): Links to feedback
   - test_episode_canvas_links(): Links to canvas

5. Class TestEpisodeSegment:
   - test_create_segment(): Creates segment
   - test_segment_belongs_to_episode(): Belongs to episode
   - test_segment_embedding(): Has vector embedding

6. Class TestBusinessFact:
   - test_create_fact(): Creates business fact
   - test_fact_citations(): Has many citations
   - test_fact_verified(): Has verified flag
   - test_fact_embedding(): Has vector embedding

7. Class TestCanvasAudit:
   - test_create_audit(): Creates audit record
   - test_audit_links_to_canvas(): Links to canvas
   - test_audit_links_to_agent(): Links to agent

8. Use pytest fixtures for database sessions, test models
  </action>
  <verify>
pytest backend/tests/test_models.py -v
pytest backend/tests/test_models.py --cov=core.models --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All models tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 6: Create mobile tests for device features</name>
  <files>mobile/src/components/__tests__/Camera.test.tsx mobile/src/components/__tests__/Location.test.tsx mobile/src/components/__tests__/Notifications.test.tsx</files>
  <action>
Create React Native tests for mobile device features:

1. mobile/src/components/__tests__/Camera.test.tsx:
   - test_renders_camera_view(): Renders camera component
   - test_request_camera_permission(): Requests permission
   - test_take_picture(): Takes picture
   - test_handle_permission_denied(): Handles denial
   - test_camera_error(): Handles camera errors

2. mobile/src/components/__tests__/Location.test.tsx:
   - test_renders_location_view(): Renders location component
   - test_request_location_permission(): Requests permission
   - test_get_current_location(): Gets current location
   - test_watch_location(): Watches location changes
   - test_location_error(): Handles location errors

3. mobile/src/components/__tests__/Notifications.test.tsx:
   - test_renders_notification_view(): Renders notifications
   - test_request_notification_permission(): Requests permission
   - test_send_local_notification(): Sends notification
   - test_schedule_notification(): Schedules notification
   - test_notification_error(): Handles errors

Use @testing-library/react-native, react-native-mock-render
  </action>
  <verify>
cd mobile && npm test -- --coverage
# Mobile coverage should be 70%+
  </verify>
  <done>
All mobile device feature tests passing, 70%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 7: Create mobile tests for state and navigation</name>
  <files>mobile/src/storage/__tests__/AsyncStorage.test.ts mobile/src/navigation/__tests__/Navigation.test.tsx</files>
  <action>
Create React Native tests for state management and navigation:

1. mobile/src/storage/__tests__/AsyncStorage.test.ts:
   - test_set_item(): Stores item
   - test_get_item(): Retrieves item
   - test_remove_item(): Removes item
   - test_clear(): Clears all items
   - test_persistence(): Survives app restart
   - test_json_serialization(): Handles JSON data

2. mobile/src/navigation/__tests__/Navigation.test.tsx:
   - test_navigate_to_screen(): Navigates to screen
   - test_navigate_with_params(): Passes params
   - test_go_back(): Goes back
   - test_navigate_replace(): Replaces screen
   - test_deep_link(): Handles deep links
   - test_tab_navigation(): Tests tab navigation

Use @testing-library/react-native, @react-navigation/native mock
  </action>
  <verify>
cd mobile && npm test -- --coverage
# Mobile coverage should be 70%+
  </verify>
  <done>
All mobile state and navigation tests passing, 70%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 8: Create desktop tests for Rust backend</name>
  <files>desktop-app/src-tauri/tests/core_logic_test.rs desktop-app/src-tauri/tests/ipc_handlers_test.rs</files>
  <action>
Create Rust tests for desktop backend:

1. desktop-app/src-tauri/tests/core_logic_test.rs:
   #[cfg(test)]
   mod tests {
       use super::*;

       #[test]
       fn test_core_logic_initialization() {
           // Test core logic initialization
       }

       #[test]
       fn test_file_operations() {
           // Test file read/write
       }

       #[test]
       fn test_state_management() {
           // Test state persistence
       }

       #[test]
       fn test_error_handling() {
           // Test error cases
       }
   }

2. desktop-app/src-tauri/tests/ipc_handlers_test.rs:
   #[cfg(test)]
   mod tests {
       use super::*;

       #[test]
       fn test_ipc_command_registration() {
           // Test command registration
       }

       #[test]
       fn test_ipc_handler_execution() {
           // Test handler execution
       }

       #[test]
       fn test_ipc_error_handling() {
           // Test error handling
       }
   }

Use cargo test, tarpaulin for coverage
  </action>
  <verify>
cd desktop-app/src-tauri && cargo test
cd desktop-app/src-tauri && cargo tarpaulin --out Html
# Rust coverage should be 70%+
  </verify>
  <done>
All desktop Rust tests passing, 70%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 9: Create desktop tests for Tauri frontend</name>
  <files>desktop-app/src/components/__tests__/WindowManager.test.tsx</files>
  <action>
Create Tauri frontend tests:

1. desktop-app/src/components/__tests__/WindowManager.test.tsx:
   - test_renders_main_window(): Renders main window
   - test_create_window(): Creates new window
   - test_close_window(): Closes window
   - test_minimize_window(): Minimizes window
   - test_maximize_window(): Maximizes window
   - test_window_focus(): Handles focus events

2. Use @testing-library/react, mock @tauri-apps/api

3. Mock Tauri invoke API
  </action>
  <verify>
cd desktop-app && npm test -- --coverage
# Desktop frontend coverage should be 70%+
  </verify>
  <done>
All desktop Tauri tests passing, 70%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 10: Create API contract tests</name>
  <files>backend/tests/test_api_contracts.py</files>
  <action>
Create backend/tests/test_api_contracts.py for API contract validation:

1. Imports: pytest, schemathesis, from fastapi.testclient import TestClient

2. Load OpenAPI spec:
   spec = load_openapi_spec("backend/openapi.json")

3. Class TestAPIContractValidation:
   - test_all_endpoints_have_schema(): All endpoints documented
   - test_all_schemas_valid(): All schemas valid
   - test_response_match_schema(): Responses match schema
   - test_request_validation(): Request validation works

4. Use schemathesis for property-based API testing:
   @schema.parametrize()
   def test_api_contracts(case):
       response = case.call()
       case.validate_response(response)

5. Class TestCriticalEndpoints:
   - test_agent_execution_contract(): Agent execution endpoint
   - test_canvas_presentation_contract(): Canvas endpoint
   - test_feedback_submission_contract(): Feedback endpoint
   - test_health_check_contract(): Health check endpoint

6. Mock external dependencies
  </action>
  <verify>
pytest backend/tests/test_api_contracts.py -v
# All contract tests should pass
  </verify>
  <done>
All API contract tests passing
  </done>
</task>

<task type="auto">
  <name>Task 11: Create E2E integration tests</name>
  <files>backend/tests/test_e2e_integration.py</files>
  <action>
Create backend/tests/test_e2e_integration.py for end-to-end testing:

1. Imports: pytest, from playwright.sync_api import Page

2. Fixtures:
   - test_app(): Starts test app
   - test_db(): Creates test database
   - authenticated_page(): Returns authenticated page

3. Class TestAgentExecutionFlow:
   - test_create_agent(): Creates agent via UI
   - test_execute_agent(): Executes agent
   - test_view_results(): Views execution results
   - test_submit_feedback(): Submits feedback

4. Class TestCanvasPresentationFlow:
   - test_create_canvas(): Creates canvas via UI
   - test_update_canvas(): Updates canvas
   - test_close_canvas(): Closes canvas

5. Class TestIntegrationFlow:
   - test_slack_integration(): Tests Slack integration
   - test_github_integration(): Tests GitHub integration
   - test_jira_integration(): Tests Jira integration

6. Use Playwright for browser automation
  </action>
  <verify>
pytest backend/tests/test_e2e_integration.py -v
# All E2E tests should pass
  </verify>
  <done>
All E2E integration tests passing
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all backend tests:
   pytest backend/tests/test_episode_lifecycle_service.py \
          backend/tests/test_agent_world_model.py \
          backend/tests/test_policy_fact_extractor.py \
          backend/tests/test_atom_cli_skill_wrapper.py \
          backend/tests/test_models.py \
          backend/tests/test_api_contracts.py \
          backend/tests/test_e2e_integration.py -v

2. Verify backend coverage (target 80%+):
   pytest backend/tests/ --cov=core --cov=api --cov=tools --cov-report=json
   # Backend should be 80%+

3. Run mobile tests:
   cd mobile && npm test -- --coverage --watchAll=false
   # Mobile should be 70%+

4. Run desktop Rust tests:
   cd desktop-app/src-tauri && cargo tarpaulin --out Html
   # Rust should be 70%+

5. Run desktop frontend tests:
   cd desktop-app && npm test -- --coverage
   # Desktop frontend should be 70%+

6. Verify all platforms meet targets
</verification>

<success_criteria>
1. Backend coverage >= 80%
2. Mobile coverage >= 70%
3. Desktop Rust coverage >= 70%
4. Desktop frontend coverage >= 70%
5. All API contract tests pass
6. All E2E tests pass
7. No regression in existing tests
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE3-SUMMARY.md`
</output>

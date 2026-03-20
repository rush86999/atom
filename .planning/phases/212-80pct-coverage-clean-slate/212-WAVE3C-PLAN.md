---
phase: 212-80pct-coverage-clean-slate
plan: WAVE3C
type: execute
wave: 3
depends_on: ["212-WAVE2A", "212-WAVE2B", "212-WAVE2C", "212-WAVE2D"]
files_modified:
  - backend/tests/test_api_contracts.py
  - backend/tests/test_e2e_integration.py
autonomous: true

must_haves:
  truths:
    - "API contracts validated against OpenAPI spec"
    - "E2E integration tests pass"
    - "Critical endpoints tested (agent execution, canvas, feedback, health)"
    - "Integration gaps covered (WebSocket, LanceDB, Redis, S3/R2)"
  artifacts:
    - path: "backend/tests/test_api_contracts.py"
      provides: "API contract validation tests"
      min_lines: 300
      exports: ["TestAPIContractValidation", "TestCriticalEndpoints"]
    - path: "backend/tests/test_e2e_integration.py"
      provides: "End-to-end integration tests"
      min_lines: 350
      exports: ["TestAgentExecutionFlow", "TestCanvasPresentationFlow", "TestIntegrationFlow"]
  key_links:
    - from: "backend/tests/test_api_contracts.py"
      to: "backend/api/**/*.py"
      via: "OpenAPI spec validation (schemathesis)"
    - from: "backend/tests/test_e2e_integration.py"
      to: "backend/api/**/*.py"
      via: "Playwright browser automation"
---

<objective>
Validate API contracts and establish E2E integration testing for critical flows.

Purpose: API contract tests ensure OpenAPI spec accuracy and integration reliability. E2E tests validate complete user flows across the system.

Output: 2 test files with 650+ total lines, validating API contracts and E2E flows.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md
@backend/api/**/*.py

# Integration Testing Pattern Reference
Schemathesis: Property-based API testing
Playwright: Browser automation for E2E flows
Test containers: Isolated test environment

# Target Files Analysis

## API Contracts
- OpenAPI spec: backend/openapi.json
- Critical endpoints: agent execution, canvas, feedback, health
- Integration endpoints: Slack, GitHub, Jira

## E2E Flows
- Agent execution flow: Create agent, execute, view results, submit feedback
- Canvas presentation flow: Create canvas, update, close
- Integration flow: Test third-party integrations
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create API contract tests</name>
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
   - test_status_codes_valid(): Status codes are valid

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
   - test_auth_contract(): Authentication endpoint
   - test_governance_contract(): Governance endpoint

6. Class TestIntegrationEndpoints:
   - test_slack_integration_contract(): Slack integration
   - test_github_integration_contract(): GitHub integration
   - test_jira_integration_contract(): Jira integration

7. Mock external dependencies
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
  <name>Task 2: Create E2E integration tests</name>
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
   - test_agent_lifecycle(): Complete agent lifecycle

4. Class TestCanvasPresentationFlow:
   - test_create_canvas(): Creates canvas via UI
   - test_update_canvas(): Updates canvas
   - test_close_canvas(): Closes canvas
   - test_canvas_types(): Tests all canvas types
   - test_canvas_permissions(): Tests governance

5. Class TestIntegrationFlow:
   - test_slack_integration(): Tests Slack integration
   - test_github_integration(): Tests GitHub integration
   - test_jira_integration(): Tests Jira integration
   - test_websocket_integration(): Tests WebSocket connection

6. Class TestIntegrationGaps:
   - test_websocket_connection(): WebSocket connects
   - test_websocket_reconnect(): WebSocket reconnects
   - test_lancedb_integration(): LanceDB vector operations
   - test_redis_integration(): Redis cache operations
   - test_storage_integration(): S3/R2 storage operations

7. Use Playwright for browser automation

8. Mock external services where not available
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

1. Run API contract tests:
   pytest backend/tests/test_api_contracts.py -v
   # Verify all contracts pass

2. Run E2E integration tests:
   pytest backend/tests/test_e2e_integration.py -v
   # Verify all E2E tests pass

3. Verify integration gaps covered:
   pytest backend/tests/test_e2e_integration.py -k integration_gaps -v

4. Verify no regressions in existing tests
</verification>

<success_criteria>
1. All API contract tests pass
2. All E2E tests pass
3. All critical endpoints validated
4. All integration gaps covered
5. No regression in existing tests
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE3C-SUMMARY.md`
</output>

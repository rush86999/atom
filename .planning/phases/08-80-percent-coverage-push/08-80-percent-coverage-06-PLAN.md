---
phase: 08-80-percent-coverage-push
plan: 06
type: execute
wave: 2
depends_on:
  - 08-80-percent-coverage-01
files_modified:
  - backend/tests/api/test_canvas_routes.py
  - backend/tests/api/test_browser_routes.py
  - backend/tests/api/test_device_capabilities.py
  - backend/tests/api/test_agent_governance_routes.py
  - backend/tests/api/test_auth_routes.py
  - backend/tests/api/test_analytics_routes.py
  - backend/tests/api/test_episode_routes.py
  - backend/tests/api/test_integration_routes.py
autonomous: true

must_haves:
  truths:
    - "API endpoints have integration tests using FastAPI TestClient"
    - "Authentication and authorization are tested across protected routes"
    - "Request/response validation is verified"
    - "Error handling returns correct status codes"
  artifacts:
    - path: "backend/tests/api/test_canvas_routes.py"
      provides: "Tests for canvas presentation endpoints"
      min_lines: 400
    - path: "backend/tests/api/test_browser_routes.py"
      provides: "Tests for browser automation endpoints"
      min_lines: 350
    - path: "backend/tests/api/test_device_capabilities.py"
      provides: "Tests for device capability endpoints"
      min_lines: 300
    - path: "backend/tests/api/test_agent_governance_routes.py"
      provides: "Tests for agent governance endpoints"
      min_lines: 350
    - path: "backend/tests/api/test_auth_routes.py"
      provides: "Tests for authentication endpoints"
      min_lines: 300
    - path: "backend/tests/api/test_episode_routes.py"
      provides: "Tests for episode management endpoints"
      min_lines: 300
  key_links:
    - from: "backend/tests/api"
      to: "backend/api"
      via: "import FastAPI route modules"
      pattern: "from api."
    - from: "backend/tests/api"
      to: "backend/tests/factories"
      via: "use factories for test data"
      pattern: "from tests.factories"
    - from: "backend/tests/api"
      to: "backend/core"
      via: "mock core services and models"
      pattern: "patch\\('core."
---

<objective>
Create comprehensive API integration tests for the 115 files in the api/ module, focusing on high-impact endpoints including canvas, browser automation, device capabilities, agent governance, authentication, analytics, and episodes. Use FastAPI TestClient with dependency overrides for realistic testing.

Purpose: Ensure API endpoints function correctly with proper authentication, authorization, request validation, error handling, and response formatting.
Output: Integration test suites for major API modules achieving 80%+ coverage
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
@backend/api/canvas_routes.py
@backend/api/browser_routes.py
@backend/api/device_capabilities.py
@backend/api/agent_governance_routes.py
@backend/api/auth_routes.py
@backend/api/episode_routes.py
@backend/tests/test_browser_automation.py
@backend/tests/factories/agent_factory.py
@backend/tests/factories/user_factory.py
@backend/tests/factories/canvas_factory.py
</context>

<tasks>

<task type="auto">
  <name>Create canvas routes integration tests</name>
  <files>backend/tests/api/test_canvas_routes.py</files>
  <action>
    Create backend/tests/api/test_canvas_routes.py:

    Test canvas API endpoints from api/canvas_routes.py:
    1. test_present_canvas() - POST /canvas/present
    2. test_close_canvas() - POST /canvas/close
    3. test_update_canvas() - PUT /canvas/{canvas_id}
    4. test_get_canvas() - GET /canvas/{canvas_id}
    5. test_list_canvases() - GET /canvas/list
    6. test_submit_form() - POST /canvas/{canvas_id}/submit
    7. test_present_specialized() - POST /canvas/specialized
    8. test_execute_javascript() - POST /canvas/{canvas_id}/execute (AUTONOMOUS only)

    Use FastAPI TestClient:
    ```python
    from fastapi.testclient import TestClient
    from api.canvas_routes import router

    @pytest.fixture
    def client():
        return TestClient(router)
    ```

    Mock WebSocket broadcasts and database:
    ```python
    with patch('api.canvas_routes.ws_manager') as mock_ws:
        with patch('api.canvas_routes.get_db_session') as mock_db:
            response = client.post("/canvas/present", json={...})
    ```

    Test authentication:
    - Valid token: 200 response
    - Missing token: 401 response
    - Invalid token: 401 response

    Test governance:
    - STUDENT agent blocked: 403
    - INTERN+ allowed: 200
    - AUTONOMOUS required for JavaScript: 403 for lower maturity

    Test request validation:
    - Valid schema: 200
    - Invalid schema: 422
    - Missing required fields: 422

    Use CanvasFactory for test data.
  </action>
  <verify>pytest backend/tests/api/test_canvas_routes.py -v</verify>
  <done>All canvas routes tests pass (8+ tests), 50%+ coverage</done>
</task>

<task type="auto">
  <name>Create browser routes integration tests</name>
  <files>backend/tests/api/test_browser_routes.py</files>
  <action>
    Create backend/tests/api/test_browser_routes.py:

    Test browser API endpoints from api/browser_routes.py:
    1. test_create_session() - POST /browser/session
    2. test_navigate() - POST /browser/{session_id}/navigate
    3. test_screenshot() - GET /browser/{session_id}/screenshot
    4. test_fill_form() - POST /browser/{session_id}/fill
    5. test_click() - POST /browser/{session_id}/click
    6. test_extract_text() - GET /browser/{session_id}/text
    7. test_execute_script() - POST /browser/{session_id}/script
    8. test_close_session() - DELETE /browser/{session_id}
    9. test_get_page_info() - GET /browser/{session_id}/info

    Use TestClient with mocked browser operations:
    ```python
    @pytest.fixture
    def client():
        from api.browser_routes import router
        return TestClient(router)

    @pytest.fixture
    def mock_browser_manager():
        with patch('api.browser_routes.get_browser_manager') as mock:
            yield mock
    ```

    Test governance:
    - INTERN+ required for browser actions
    - STUDENT agents blocked

    Test error handling:
    - Session not found: 404
    - Wrong user ownership: 403
    - Invalid URL: 400

    Test response formats:
    - Success: {"success": True, "data": {...}}
    - Error: {"success": False, "error": "message"}
  </action>
  <verify>pytest backend/tests/api/test_browser_routes.py -v</verify>
  <done>All browser routes tests pass (9+ tests), 50%+ coverage</done>
</task>

<task type="auto">
  <name>Create device capabilities integration tests</name>
  <files>backend/tests/api/test_device_capabilities.py</files>
  <action>
    Create backend/tests/api/test_device_capabilities.py:

    Test device API endpoints from api/device_capabilities.py:
    1. test_camera_capture() - POST /device/camera
    2. test_start_screen_recording() - POST /device/record/start
    3. test_stop_screen_recording() - POST /device/record/stop
    4. test_get_location() - GET /device/location
    5. test_send_notification() - POST /device/notify
    6. test_execute_command() - POST /device/execute (AUTONOMOUS only)
    7. test_list_capabilities() - GET /device/capabilities
    8. test_request_permissions() - POST /device/permissions

    Test maturity requirements:
    - Camera: INTERN+
    - Screen recording: SUPERVISED+
    - Command execution: AUTONOMOUS only

    Test permission checks:
    - Permission granted: 200
    - Permission denied: 403
    - Permission pending: 202

    Mock device operations:
    ```python
    with patch('api.device_capabilities.camera_capture') as mock_camera:
        mock_camera.return_value = {"image_data": "base64..."}
    ```
  </action>
  <verify>pytest backend/tests/api/test_device_capabilities.py -v</verify>
  <done>All device capability tests pass (8+ tests), 50%+ coverage</done>
</task>

<task type="auto">
  <name>Create agent governance routes integration tests</name>
  <files>backend/tests/api/test_agent_governance_routes.py</files>
  <action>
    Create backend/tests/api/test_agent_governance_routes.py:

    Test governance API endpoints from api/agent_governance_routes.py:
    1. test_list_agents() - GET /agents
    2. test_get_agent() - GET /agents/{agent_id}
    3. test_create_agent() - POST /agents
    4. test_update_agent() - PUT /agents/{agent_id}
    5. test_delete_agent() - DELETE /agents/{agent_id}
    6. test_promote_agent() - POST /agents/{agent_id}/promote
    7. test_demote_agent() - POST /agents/{agent_id}/demote
    8. test_get_agent_confidence() - GET /agents/{agent_id}/confidence
    9. test_record_outcome() - POST /agents/{agent_id}/outcome

    Test CRUD operations:
    - Create: 201 with agent object
    - Read: 200 with agent details
    - Update: 200 with updated agent
    - Delete: 204 or 200

    Test governance operations:
    - Promotion: maturity level increases
    - Demotion: maturity level decreases
    - Confidence tracking: scores recorded

    Mock AgentGovernanceService:
    ```python
    with patch('api.agent_governance_routes.AgentGovernanceService') as mock_gov:
        mock_gov.return_value.can_perform_action.return_value = {"allowed": True}
    ```
  </action>
  <verify>pytest backend/tests/api/test_agent_governance_routes.py -v</verify>
  <done>All governance routes tests pass (9+ tests), 50%+ coverage</done>
</task>

<task type="auto">
  <name>Create authentication routes integration tests</name>
  <files>backend/tests/api/test_auth_routes.py</files>
  <action>
    Create backend/tests/api/test_auth_routes.py:

    Test authentication API endpoints from api/auth_routes.py:
    1. test_register() - POST /auth/register
    2. test_login() - POST /auth/login
    3. test_logout() - POST /auth/logout
    4. test_refresh_token() - POST /auth/refresh
    5. test_verify_token() - GET /auth/verify
    6. test_forgot_password() - POST /auth/forgot-password
    7. test_reset_password() - POST /auth/reset-password
    8. test_change_password() - POST /auth/change-password

    Test authentication flow:
    - Register: creates user, returns tokens
    - Login: validates credentials, returns tokens
    - Refresh: validates refresh token, returns new access token
    - Logout: invalidates tokens

    Test error handling:
    - Duplicate email: 400 or 409
    - Invalid credentials: 401
    - Expired token: 401
    - Missing fields: 422

    Test token formats:
    - Access token: JWT with short expiry
    - Refresh token: JWT with long expiry
    - Token structure: header.payload.signature

    Mock auth service:
    ```python
    with patch('api.auth_routes.hash_password') as mock_hash:
        with patch('api.auth_routes.verify_password') as mock_verify:
            response = client.post("/auth/login", json={...})
    ```
  </action>
  <verify>pytest backend/tests/api/test_auth_routes.py -v</verify>
  <done>All auth routes tests pass (8+ tests), 50%+ coverage</done>
</task>

<task type="auto">
  <name>Create episode routes integration tests</name>
  <files>backend/tests/api/test_episode_routes.py</files>
  <action>
    Create backend/tests/api/test_episode_routes.py:

    Test episode API endpoints:
    1. test_create_episode() - POST /episodes
    2. test_get_episode() - GET /episodes/{episode_id}
    3. test_list_episodes() - GET /episodes
    4. test_search_episodes() - POST /episodes/search
    5. test_update_episode() - PUT /episodes/{episode_id}
    6. test_delete_episode() - DELETE /episodes/{episode_id}
    7. test_add_segment() - POST /episodes/{episode_id}/segments
    8. test_get_segments() - GET /episodes/{episode_id}/segments

    Test episode CRUD:
    - Create: episode with segments
    - Read: episode with canvas/feedback context
    - Update: episode metadata
    - Delete: cascade to segments

    Test search functionality:
    - Temporal search: time range filters
    - Semantic search: vector similarity
    - Canvas type filter: filter by canvas type
    - Feedback filter: filter by feedback score

    Test pagination:
    - List episodes with limit/offset
    - Search results with limit/offset

    Mock episode services:
    ```python
    with patch('api.episode_routes.EpisodeSegmentationService') as mock_seg:
        with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
            response = client.post("/episodes", json={...})
    ```
  </action>
  <verify>pytest backend/tests/api/test_episode_routes.py -v</verify>
  <done>All episode routes tests pass (8+ tests), 50%+ coverage</done>
</task>

<task type="auto">
  <name>Create analytics and workflow routes integration tests</name>
  <files>backend/tests/api/test_analytics_routes.py</files>
  <action>
    Create backend/tests/api/test_analytics_routes.py:

    Test analytics API endpoints:
    1. test_get_workflow_analytics() - GET /analytics/workflows
    2. test_get_step_analytics() - GET /analytics/steps
    3. test_get_error_report() - GET /analytics/errors
    4. test_get_performance_metrics() - GET /analytics/performance
    5. test_export_analytics() - GET /analytics/export
    6. test_get_workflow_status() - GET /workflows/{execution_id}/status
    7. test_pause_workflow() - POST /workflows/{execution_id}/pause
    8. test_resume_workflow() - POST /workflows/{execution_id}/resume
    9. test_cancel_workflow() - POST /workflows/{execution_id}/cancel

    Test analytics queries:
    - Time range filtering
    - Workflow type filtering
    - Aggregation (avg, sum, count)
    - Percentile calculations

    Test workflow control:
    - Pause: workflow paused, state saved
    - Resume: workflow continues from pause
    - Cancel: workflow terminated

    Test export formats:
    - CSV export
    - JSON export

    Mock analytics engine:
    ```python
    with patch('api.analytics_routes.get_analytics_engine') as mock_analytics:
        mock_analytics.return_value.get_workflow_statistics.return_value = {...}
    ```
  </action>
  <verify>pytest backend/tests/api/test_analytics_routes.py -v</verify>
  <done>All analytics routes tests pass (9+ tests), 50%+ coverage</done>
</task>

<task type="auto">
  <name>Create additional API routes tests for remaining endpoints</name>
  <files>
    backend/tests/api/test_ab_testing_routes.py
    backend/tests/api/test_agent_routes.py
    backend/tests/api/test_integration_routes.py
    backend/tests/api/test_webhook_routes.py
  </files>
  <action>
    Create tests for remaining API endpoints:

    Test AB Testing Routes:
    1. test_create_experiment() - POST /ab-testing/experiments
    2. test_get_experiment() - GET /ab-testing/experiments/{id}
    3. test_record_exposure() - POST /ab-testing/exposure
    4. test_record_conversion() - POST /ab-testing/conversion

    Test Agent Routes:
    1. test_chat() - POST /agents/{agent_id}/chat
    2. test_stream_chat() - WebSocket /agents/{agent_id}/stream
    3. test_execute_tool() - POST /agents/{agent_id}/tools/{tool}

    Test Integration Routes:
    1. test_oauth_start() - GET /integrations/{service}/oauth
    2. test_oauth_callback() - GET /integrations/{service}/callback
    3. test_webhook_receive() - POST /integrations/webhook/{service}

    Each test file should have 8-10 tests covering:
    - Success cases
    - Authentication/authorization
    - Request validation
    - Error handling
    - Response format

    Use existing test patterns as reference.
  </action>
  <verify>pytest backend/tests/api/ -v --tb=short</verify>
  <done>All additional API routes tests pass (30+ tests total)</done>
</task>

</tasks>

<verification>
1. Run pytest backend/tests/api/ -v to verify all API tests pass
2. Run pytest --cov=backend/api backend/tests/api/ to verify coverage
3. Check coverage.json shows increased coverage for api/ module
4. Verify all tests use TestClient properly
5. Confirm authentication/authorization tests are comprehensive
6. Verify error response codes are correct (400, 401, 403, 404, 422, 500)
</verification>

<success_criteria>
- 8+ API test files created
- 100+ total API tests
- API module coverage increases from 30.3% to 50%+
- All high-impact endpoints tested
- Authentication flows verified
- Governance enforcement tested
- Error handling validated
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-06-SUMMARY.md`
</output>

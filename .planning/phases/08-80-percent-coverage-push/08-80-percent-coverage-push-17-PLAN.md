---
phase: 08-80-percent-coverage-push
plan: 17
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/api/test_mobile_agent_routes.py
  - backend/tests/api/test_canvas_sharing.py
  - backend/tests/api/test_canvas_favorites.py
  - backend/tests/api/test_device_messaging.py
autonomous: true
gap_closure: false

must_haves:
  truths:
    - "Mobile agent routes have 70%+ test coverage"
    - "Canvas sharing routes have 70%+ test coverage"
    - "Canvas favorites routes have 70%+ test coverage"
    - "Device messaging routes have 70%+ test coverage"
    - "Tests cover all HTTP methods (GET, POST, PUT, DELETE)"
    - "Tests cover authentication and authorization"
    - "Tests cover error responses and edge cases"
  artifacts:
    - path: "backend/tests/api/test_mobile_agent_routes.py"
      provides: "Integration tests for mobile agent API"
      min_lines: 600
      tests_count: 20
    - path: "backend/tests/api/test_canvas_sharing.py"
      provides: "Integration tests for canvas sharing API"
      min_lines: 500
      tests_count: 16
    - path: "backend/tests/api/test_canvas_favorites.py"
      provides: "Integration tests for canvas favorites API"
      min_lines: 400
      tests_count: 13
    - path: "backend/tests/api/test_device_messaging.py"
      provides: "Integration tests for device messaging API"
      min_lines: 450
      tests_count: 14
  key_links:
    - from: "test_mobile_agent_routes.py"
      to: "api/mobile_agent_routes.py"
      via: "FastAPI TestClient"
      pattern: "client\\.(get|post|put|delete)"
    - from: "test_canvas_sharing.py"
      to: "api/canvas_sharing.py"
      via: "TestClient with auth"
      pattern: "client\\.post.*headers"
    - from: "test_canvas_favorites.py"
      to: "api/canvas_favorites.py"
      via: "TestClient with user context"
      pattern: "mock_user"
    - from: "test_device_messaging.py"
      to: "api/device_messaging.py"
      via: "TestClient with device mocking"
      pattern: "mock_device"
---

<objective>
Create comprehensive integration tests for 4 API zero-coverage files to achieve 70%+ coverage per file.

Purpose: These API files (225+175+158+156 = 714 lines) represent mobile agent, canvas sharing/favorites, and device messaging endpoints. Testing them will add ~500 lines of coverage and improve overall project coverage by ~0.9%.

Output: 4 test files with 63 total tests covering mobile agent routes, canvas sharing, canvas favorites, and device messaging APIs.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-12-SUMMARY.md
@backend/api/mobile_agent_routes.py
@backend/api/canvas_sharing.py
@backend/api/canvas_favorites.py
@backend/api/device_messaging.py

Test patterns from Phase 8.5:
- FastAPI TestClient for API integration tests
- Mock authentication/authorization
- AsyncMock for database operations
- Input validation and error response tests
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create integration tests for mobile agent routes</name>
  <files>backend/tests/api/test_mobile_agent_routes.py</files>
  <action>
    Create test_mobile_agent_routes.py with comprehensive tests for api/mobile_agent_routes.py (225 lines):

    1. Import and setup:
       ```python
       import pytest
       from fastapi.testclient import TestClient
       from unittest.mock import AsyncMock, MagicMock, patch
       from api.mobile_agent_routes import router

       @pytest.fixture
       def client():
           return TestClient(router)

       @pytest.fixture
       def mock_auth():
           with patch('api.mobile_agent_routes.get_current_user') as mock:
               mock.return_value = MagicMock(id="test_user", role="MEMBER")
               yield mock

       @pytest.fixture
       def mock_db():
           return AsyncMock()
       ```

    2. Test POST /api/mobile/agents/register:
       - test_register_agent_success (valid registration)
       - test_register_agent_invalid_device (400 error)
       - test_register_agent_duplicate (409 conflict)
       - test_register_agent_unauthorized (403 error)

    3. Test GET /api/mobile/agents:
       - test_list_agents_success (list all agents)
       - test_list_agents_with_filters (by status, type)
       - test_list_agents_paginated (pagination)
       - test_list_agents_empty (no agents)

    4. Test GET /api/mobile/agents/{agent_id}:
       - test_get_agent_success (found agent)
       - test_get_agent_not_found (404 error)
       - test_get_agent_unauthorized (403 error)

    5. Test PUT /api/mobile/agents/{agent_id}:
       - test_update_agent_success (valid update)
       - test_update_agent_invalid_data (400 error)
       - test_update_agent_not_found (404 error)
       - test_update_agent_unauthorized (403 error)

    6. Test DELETE /api/mobile/agents/{agent_id}:
       - test_delete_agent_success (valid delete)
       - test_delete_agent_not_found (404 error)
       - test_delete_agent_unauthorized (403 error)

    7. Test POST /api/mobile/agents/{agent_id}/sync:
       - test_sync_agent_success (successful sync)
       - test_sync_agent_with_changes (incremental sync)
       - test_sync_agent_not_found (404 error)
       - test_sync_agent_conflict (409 conflict)

    Target: 600+ lines, 20 tests
    Use TestClient for all endpoint tests
    Mock authentication and database
    Test all HTTP methods and error paths
  </action>
  <verify>pytest backend/tests/api/test_mobile_agent_routes.py -v</verify>
  <done>20 tests created, all passing, 70%+ coverage on mobile_agent_routes.py</done>
</task>

<task type="auto">
  <name>Task 2: Create integration tests for canvas sharing routes</name>
  <files>backend/tests/api/test_canvas_sharing.py</files>
  <action>
    Create test_canvas_sharing.py with comprehensive tests for api/canvas_sharing.py (175 lines):

    1. Import and setup:
       ```python
       import pytest
       from fastapi.testclient import TestClient
       from unittest.mock import AsyncMock, MagicMock, patch
       from api.canvas_sharing import router

       @pytest.fixture
       def client():
           return TestClient(router)

       @pytest.fixture
       def mock_user():
           user = MagicMock()
           user.id = "test_user"
           user.email = "test@example.com"
           return user

       @pytest.fixture
       def mock_db():
           return AsyncMock()
       ```

    2. Test POST /api/canvas/{canvas_id}/share:
       - test_share_canvas_success (valid share)
       - test_share_canvas_with_permissions (permission levels)
       - test_share_canvas_multiple_users (bulk share)
       - test_share_canvas_invalid_user (400 error)
       - test_share_canvas_not_found (404 error)

    3. Test GET /api/canvas/{canvas_id}/shares:
       - test_list_shares_success (list all shares)
       - test_list_shares_with_filters (by permission)
       - test_list_shares_empty (no shares)
       - test_list_shares_unauthorized (403 error)

    4. Test PUT /api/canvas/{canvas_id}/shares/{share_id}:
       - test_update_share_success (valid update)
       - test_update_share_permissions (permission change)
       - test_update_share_not_found (404 error)
       - test_update_share_unauthorized (403 error)

    5. Test DELETE /api/canvas/{canvas_id}/shares/{share_id}:
       - test_revoke_share_success (valid revoke)
       - test_revoke_share_not_found (404 error)
       - test_revoke_share_unauthorized (403 error)

    6. Test GET /api/canvas/shared-with-me:
       - test_list_shared_canvases_success (list shared)
       - test_list_shared_with_filters (by owner, date)
       - test_list_shared_paginated (pagination)
       - test_list_shared_empty (no shared canvases)

    Target: 500+ lines, 16 tests
    Test sharing permissions and access control
    Test all CRUD operations for shares
    Test authorization scenarios
  </action>
  <verify>pytest backend/tests/api/test_canvas_sharing.py -v</verify>
  <done>16 tests created, all passing, 70%+ coverage on canvas_sharing.py</done>
</task>

<task type="auto">
  <name>Task 3: Create integration tests for canvas favorites routes</name>
  <files>backend/tests/api/test_canvas_favorites.py</files>
  <action>
    Create test_canvas_favorites.py with comprehensive tests for api/canvas_favorites.py (158 lines):

    1. Import and setup:
       ```python
       import pytest
       from fastapi.testclient import TestClient
       from unittest.mock import AsyncMock, MagicMock, patch
       from api.canvas_favorites import router

       @pytest.fixture
       def client():
           return TestClient(router)

       @pytest.fixture
       def mock_user():
           user = MagicMock()
           user.id = "test_user"
           return user

       @pytest.fixture
       def mock_db():
           return AsyncMock()
       ```

    2. Test POST /api/canvas/{canvas_id}/favorite:
       - test_add_favorite_success (valid add)
       - test_add_favorite_already_exists (idempotent)
       - test_add_favorite_not_found (404 error)
       - test_add_favorite_unauthorized (403 error)

    3. Test DELETE /api/canvas/{canvas_id}/favorite:
       - test_remove_favorite_success (valid remove)
       - test_remove_favorite_not_found (404 error)
       - test_remove_favorite_not_a_favorite (400 error)
       - test_remove_favorite_unauthorized (403 error)

    4. Test GET /api/canvas/{canvas_id}/favorite:
       - test_check_favorite_success (is favorite)
       - test_check_favorite_not_favorite (false)
       - test_check_favorite_not_found (404 error)

    5. Test GET /api/canvas/favorites:
       - test_list_favorites_success (list all)
       - test_list_favorites_with_filters (by type, date)
       - test_list_favorites_paginated (pagination)
       - test_list_favorites_empty (no favorites)

    6. Test PUT /api/canvas/favorites/reorder:
       - test_reorder_favorites_success (valid reorder)
       - test_reorder_favorites_invalid_order (400 error)
       - test_reorder_favorites_partial (partial reordering)

    Target: 400+ lines, 13 tests
    Test favorite CRUD operations
    Test filtering and pagination
    Test reordering logic
  </action>
  <verify>pytest backend/tests/api/test_canvas_favorites.py -v</verify>
  <done>13 tests created, all passing, 70%+ coverage on canvas_favorites.py</done>
</task>

<task type="auto">
  <name>Task 4: Create integration tests for device messaging routes</name>
  <files>backend/tests/api/test_device_messaging.py</files>
  <action>
    Create test_device_messaging.py with comprehensive tests for api/device_messaging.py (156 lines):

    1. Import and setup:
       ```python
       import pytest
       from fastapi.testclient import TestClient
       from unittest.mock import AsyncMock, MagicMock, patch
       from api.device_messaging import router

       @pytest.fixture
       def client():
           return TestClient(router)

       @pytest.fixture
       def mock_device():
           device = MagicMock()
           device.id = "test_device"
           device.user_id = "test_user"
           return device

       @pytest.fixture
       def mock_db():
           return AsyncMock()
       ```

    2. Test POST /api/devices/messages/send:
       - test_send_message_success (valid message)
       - test_send_message_to_multiple_devices (broadcast)
       - test_send_message_invalid_payload (400 error)
       - test_send_message_device_not_found (404 error)

    3. Test GET /api/devices/{device_id}/messages:
       - test_list_messages_success (list all)
       - test_list_messages_with_filters (by status, type)
       - test_list_messages_paginated (pagination)
       - test_list_messages_empty (no messages)

    4. Test GET /api/devices/messages/{message_id}:
       - test_get_message_success (found message)
       - test_get_message_not_found (404 error)
       - test_get_message_unauthorized (403 error)

    5. Test PUT /api/devices/messages/{message_id}/status:
       - test_update_message_status_success (valid update)
       - test_update_message_status_invalid (400 error)
       - test_update_message_not_found (404 error)

    6. Test DELETE /api/devices/messages/{message_id}:
       - test_delete_message_success (valid delete)
       - test_delete_message_not_found (404 error)
       - test_delete_message_unauthorized (403 error)

    7. Test POST /api/devices/{device_id}/commands:
       - test_send_command_success (valid command)
       - test_send_command_with_parameters (complex command)
       - test_send_command_invalid_command (400 error)
       - test_send_command_device_offline (503 error)

    Target: 450+ lines, 14 tests
    Test messaging and command endpoints
    Test device communication scenarios
    Test error handling for offline devices
  </action>
  <verify>pytest backend/tests/api/test_device_messaging.py -v</verify>
  <done>14 tests created, all passing, 70%+ coverage on device_messaging.py</done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run all new tests:
   ```bash
   pytest backend/tests/api/test_mobile_agent_routes.py -v
   pytest backend/tests/api/test_canvas_sharing.py -v
   pytest backend/tests/api/test_canvas_favorites.py -v
   pytest backend/tests/api/test_device_messaging.py -v
   ```

2. Run tests with coverage:
   ```bash
   pytest backend/tests/api/test_mobile_agent_routes.py --cov=backend.api.mobile_agent_routes --cov-report=term-missing
   pytest backend/tests/api/test_canvas_sharing.py --cov=backend.api.canvas_sharing --cov-report=term-missing
   pytest backend/tests/api/test_canvas_favorites.py --cov=backend.api.canvas_favorites --cov-report=term-missing
   pytest backend/tests/api/test_device_messaging.py --cov=backend.api.device_messaging --cov-report=term-missing
   ```

3. Verify:
   - 63 tests total (20+16+13+14)
   - All tests pass
   - Each file achieves 70%+ coverage
   - Overall project coverage increases by ~0.9%
</verification>

<success_criteria>
- 4 test files created
- 63 total tests (20+16+13+14)
- 100% pass rate
- Each target file achieves 70%+ coverage
- Overall project coverage increases from 21.7% toward 22.6%
- Tests use TestClient patterns from Phase 8.5
- All tests complete in under 60 seconds
</success_criteria>

<output>
After completion, create `.planning/phases/08-80-percent-coverage-push/08-80-percent-coverage-push-17-SUMMARY.md`
</output>

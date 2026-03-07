# Mobile API-Level Testing

This directory contains API-level tests for mobile workflows (agent spawn, navigation, device features). These tests validate mobile API contracts without requiring full Detox E2E setup.

## Overview

**Why API-Level Testing?**

Detox E2E tests are **BLOCKED** because:
- `expo-dev-client` requirement adds ~15 minutes to CI/CD execution time
- Development build configuration is complex and not currently installed
- iOS simulator setup requires macOS and applesimutils

**API-level testing provides:**
✅ **ROADMAP Compliant**: Satisfies "mobile workflows (navigation, device features)" requirement
✅ **Faster Feedback**: Tests run in seconds vs minutes for full E2E
✅ **Simpler Setup**: No iOS simulators, Detox configuration, or expo-dev-client needed
✅ **Better Coverage**: Tests API contracts, error handling, and authentication thoroughly

**Technology Stack:**
- **pytest**: Test framework
- **httpx.AsyncClient**: Async HTTP client for API calls
- **pytest-asyncio**: Async test support

## Quick Commands

### Run All Mobile API Tests
```bash
# Run all mobile API tests
pytest backend/tests/e2e_api/ -v

# Run with coverage
pytest backend/tests/e2e_api/ -v --cov=api/mobile

# Run with JSON output (for CI/CD aggregation)
pytest backend/tests/e2e_api/ -v --json-report --json-report-file=mobile_api_report.json
```

### Run Specific Test Files
```bash
# Run mobile endpoint tests
pytest backend/tests/e2e_api/test_mobile_endpoints.py -v

# Run specific test
pytest backend/tests/e2e_api/test_mobile_endpoints.py::test_mobile_agent_spawn_api -v

# Run with verbose output
pytest backend/tests/e2e_api/ -v -s
```

### Run with Filters
```bash
# Run only agent tests
pytest backend/tests/e2e_api/ -v -k "agent"

# Run only navigation tests
pytest backend/tests/e2e_api/ -v -k "navigation"

# Run only device tests
pytest backend/tests/e2e_api/ -v -k "device"
```

## Test Organization

### Agent Tests (test_mobile_endpoints.py)

**test_mobile_agent_spawn_api**: Tests agent spawn via mobile API
- Validates agent creation with valid parameters
- Checks response includes agentId, agentName, status
- Uses unique agent names for test isolation

**test_mobile_agent_chat_api**: Tests agent chat via mobile API
- Spawns agent first
- Sends chat message via mobile API
- Validates response includes streaming text

**test_mobile_agent_list_api**: Tests agent list retrieval via mobile API
- Spawns multiple agents
- Validates agent list includes all created agents
- Checks agent metadata (name, type, status)

### Navigation Tests (test_mobile_endpoints.py)

**test_mobile_navigation_screens_api**: Tests mobile navigation screens endpoint
- Validates response includes available screens (Home, Agents, Canvas)
- Checks screen metadata (title, route, icon)

**test_mobile_navigation_navigate_api**: Tests mobile navigation navigate endpoint
- Navigates to specific screen
- Validates navigation history is updated
- Checks screen parameters are passed correctly

**test_mobile_navigation_history_api**: Tests mobile navigation history endpoint
- Performs multiple navigation actions
- Validates history includes all navigated screens
- Checks history order and timestamps

### Device Tests (test_mobile_endpoints.py)

**test_mobile_device_capabilities_api**: Tests mobile device capabilities endpoint
- Validates response includes available capabilities (camera, location, notifications)
- Checks capability metadata (permission status, availability)

**test_mobile_device_permission_request_api**: Tests mobile permission request endpoint
- Requests camera permission
- Validates permission grant response
- Checks permission is persisted

**test_mobile_device_camera_api**: Tests mobile camera API endpoint
- Requests camera access
- Validates camera is available
- Checks camera stream URL (mocked in tests)

## Writing API Tests

### Test Structure

Mobile API tests use `httpx.AsyncClient` for async API calls:

```python
import pytest
import httpx
from typing import Dict

@pytest.mark.e2e
async def test_mobile_agent_spawn_api(authenticated_mobile_client: httpx.AsyncClient):
    """Test agent spawn via mobile API."""
    response = await authenticated_mobile_client.post(
        "/api/v1/mobile/agents/spawn",
        json={
            "agentName": "TestAgent-mobile",
            "agentType": "AUTONOMOUS",
            "systemPrompt": "You are a helpful assistant"
        }
    )

    # Assert success
    assert response.status_code == 200
    data = response.json()
    assert data["agentId"] is not None
    assert data["agentName"] == "TestAgent-mobile"
    assert data["status"] == "active"
```

### Test Isolation

Use unique IDs for test data to avoid constraint violations:

```python
import uuid

@pytest.mark.e2e
async def test_agent_spawn_with_unique_id(authenticated_mobile_client: httpx.AsyncClient):
    """Test agent spawn with unique ID."""
    # Use UUID suffix for unique agent name
    agent_name = f"TestAgent-{uuid.uuid4().hex[:8]}"

    response = await authenticated_mobile_client.post(
        "/api/v1/mobile/agents/spawn",
        json={"agentName": agent_name, "agentType": "AUTONOMOUS"}
    )

    assert response.status_code == 200
    assert response.json()["agentName"] == agent_name
```

### Test Both Success and Error Paths

```python
@pytest.mark.e2e
async def test_mobile_agent_spawn_success(authenticated_mobile_client: httpx.AsyncClient):
    """Test successful agent spawn."""
    response = await authenticated_mobile_client.post(
        "/api/v1/mobile/agents/spawn",
        json={"agentName": "TestAgent", "agentType": "AUTONOMOUS"}
    )
    assert response.status_code == 200

@pytest.mark.e2e
async def test_mobile_agent_spawn_invalid_type(authenticated_mobile_client: httpx.AsyncClient):
    """Test agent spawn with invalid agent type."""
    response = await authenticated_mobile_client.post(
        "/api/v1/mobile/agents/spawn",
        json={"agentName": "TestAgent", "agentType": "INVALID_TYPE"}
    )
    assert response.status_code == 400
    assert "Invalid agent type" in response.json()["error"]
```

### Use E2E Marker for CI/CD

```python
@pytest.mark.e2e
async def test_mobile_workflow(authenticated_mobile_client: httpx.AsyncClient):
    """Test complete mobile workflow (marked for CI/CD)."""
    # This test will be included in CI/CD E2E runs
    pass
```

## Common Issues

### Endpoint Not Found (404)

**Issue**: `404 Not Found` when calling mobile API endpoints

**Cause**: Mobile routes not registered in FastAPI app

**Solution**:
1. Verify mobile routes are included in `backend/main.py`:
   ```python
   from api.mobile_routes import app as mobile_app
   app.mount("/api/v1/mobile", mobile_app)
   ```

2. Check route registration:
   ```python
   @app.get("/api/v1/mobile/health")
   async def mobile_health():
       return {"status": "ok"}
   ```

3. Use backend API routes as fallback if mobile-specific routes don't exist

### Missing Mobile-Specific Routes

**Issue**: Mobile endpoint returns `405 Method Not Allowed`

**Cause**: Route method not implemented for mobile API

**Solution**:
- Use backend API routes as fallback (e.g., `/api/v1/agents/spawn` instead of `/api/v1/mobile/agents/spawn`)
- Implement mobile-specific route if different behavior is needed

### Permission Denials (403)

**Issue**: Device capability tests fail with permission denied

**Cause**: Device capability mock not configured in test setup

**Solution**:
1. Check `backend/tests/e2e_api/conftest.py` for device mock setup
2. Ensure mock device capabilities are registered:
   ```python
   @pytest.fixture
   async def mock_device_capabilities():
       return {
           "camera": {"available": True, "permission": "granted"},
           "location": {"available": True, "permission": "granted"},
           "notifications": {"available": True, "permission": "granted"}
       }
   ```

### Test Isolation Failures

**Issue**: Tests fail when run in parallel due to shared agent IDs

**Cause**: Tests using hard-coded agent IDs without UUID suffixes

**Solution**:
- Use UUID suffixes for all test data:
  ```python
  agent_name = f"TestAgent-{uuid.uuid4().hex[:8]}"
  agent_id = f"agent-{uuid.uuid4().hex}"
  ```

- Cleanup after test:
  ```python
  @pytest.fixture(autouse=True)
   async def cleanup_test_data(db_session):
       yield
       await db_session.execute(
           "DELETE FROM agents WHERE agent_name LIKE 'TestAgent-%'"
       )
       await db_session.commit()
   ```

## Performance Targets

- **Per test**: <5 seconds (API calls are fast)
- **Full suite**: <2 minutes (8 tests, no parallelization needed)
- **Authentication**: <100ms (JWT tokens in test fixtures)

## CI/CD Integration

Mobile API tests are included in the E2E unified workflow (`.github/workflows/e2e-unified.yml`):

```yaml
e2e-mobile:
  runs-on: ubuntu-latest
  steps:
    - name: Run mobile API tests
      run: |
        pytest backend/tests/e2e_api/ -v \
          --json-report --json-report-file=mobile_api_report.json

    - name: Upload results
      uses: actions/upload-artifact@v4
      with:
        name: e2e-mobile-report
        path: backend/tests/e2e_api/mobile_api_report.json
```

**Note**: Mobile API tests run on Ubuntu (no macOS required) since they don't use Detox/iOS simulators.

## Additional Resources

- **[Comprehensive E2E Testing Guide](../../../../docs/E2E_TESTING_GUIDE.md)** - Detailed documentation covering mobile API testing patterns
- **httpx Documentation**: https://www.python-httpx.org/
- **pytest-asyncio**: https://pytest-asyncio.readthedocs.io/

## Status

**Phase**: 148 - Cross-Platform E2E Orchestration
**Plan**: 148-03 - E2E Testing Documentation
**Status**: ✅ COMPLETE

**Test Coverage**:
- Agent API tests: Spawn, chat, list (8 tests)
- Navigation API tests: Screens, navigate, history (included in endpoint tests)
- Device API tests: Capabilities, permissions, camera (included in endpoint tests)

**Next Steps**:
- Phase 148-04: E2E test execution and CI/CD integration
- Future (Phase 150+): Full Detox E2E tests when expo-dev-client is available

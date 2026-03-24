# Mobile API Testing

## Overview

Mobile API testing provides API-level test coverage for mobile app functionality without the overhead of UI automation. Tests use FastAPI's TestClient for in-memory API testing, making them 10-100x faster than browser-based tests.

### Key Benefits

- **API-First Approach**: Direct API calls (no browser or mobile device needed)
- **Fast Execution**: <10ms per request with TestClient (no network overhead)
- **Consistency**: Response structure matches web API for cross-platform compatibility
- **Governance**: Tests verify agent maturity and permission enforcement
- **CI/CD Friendly**: Graceful skip when device hardware not available

## Prerequisites

- Python 3.11+
- FastAPI TestClient (included with FastAPI)
- Test database (SQLite or PostgreSQL)
- Authentication fixtures (from `mobile_api.fixtures.mobile_fixtures`)

## Running Tests

### Run All Mobile API Tests

```bash
# From project root
pytest backend/tests/mobile_api/ -v

# With coverage
pytest backend/tests/mobile_api/ --cov=backend/api --cov-report=html

# With detailed output
pytest backend/tests/mobile_api/ -v -s
```

### Run Specific Test Files

```bash
# Authentication tests
pytest backend/tests/mobile_api/test_mobile_auth.py -v

# Agent execution tests
pytest backend/tests/mobile_api/test_mobile_agent_execution.py -v

# Workflow execution tests
pytest backend/tests/mobile_api/test_mobile_workflow_execution.py -v

# Device features tests
pytest backend/tests/mobile_api/test_mobile_device_features.py -v
```

### Run Specific Test Classes or Tests

```bash
# Run specific test class
pytest backend/tests/mobile_api/test_mobile_auth.py::TestMobileLogin -v

# Run specific test
pytest backend/tests/mobile_api/test_mobile_auth.py::TestMobileLogin::test_mobile_login_success -v

# Run tests matching pattern
pytest backend/tests/mobile_api/ -k "login" -v
```

## Test Categories

### 1. Authentication Tests (`test_mobile_auth.py`)

Tests for authentication endpoints:

- **Login Success**: Valid credentials return access token
- **Login Failure**: Invalid credentials return 401 error
- **Token Refresh**: Returns new access token
- **Token Validation**: `/api/auth/me` returns user data
- **Logout**: Invalidates token (client-side)

**Coverage**:
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `GET /api/auth/me`
- `POST /api/auth/logout`

### 2. Agent Execution Tests (`test_mobile_agent_execution.py`)

Tests for agent execution endpoints:

- **Agent Execute**: Sync execution with query
- **Agent Execute with Params**: Custom parameters passed correctly
- **Agent Stream**: Streaming execution via WebSocket
- **Agent Governance**: Maturity level enforcement (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
- **Agent History**: Execution history listing

**Coverage**:
- `GET /api/v1/agents`
- `POST /api/v1/agents/{agent_id}/execute`
- `POST /api/atom-agent/chat`
- `POST /api/atom-agent/chat/stream`
- `GET /api/v1/agents/executions`

### 3. Workflow Execution Tests (`test_mobile_workflow_execution.py`)

Tests for workflow execution endpoints:

- **Workflow Create**: Create new workflow
- **Workflow Add Skill**: Add skills to workflow
- **Workflow Execute**: Run workflow with input
- **Workflow DAG Validation**: Detect cyclic dependencies
- **Workflow History**: Execution history with pagination

**Coverage**:
- `GET /api/v1/workflows`
- `POST /api/v1/workflows`
- `POST /api/v1/workflows/{workflow_id}/skills`
- `POST /api/v1/workflows/{workflow_id}/execute`
- `POST /api/v1/workflows/validate`
- `GET /api/v1/workflows/executions`

### 4. Device Features Tests (`test_mobile_device_features.py`)

Tests for device hardware access:

- **Camera Capture**: Image capture with quality settings
- **Location**: GPS coordinates with accuracy
- **Notifications**: Push notifications
- **Device Capabilities**: List available features
- **Device Permissions**: Permission status (granted/denied)
- **Screen Recording**: Start/stop recording (SUPERVISED+ required)

**Coverage**:
- `POST /api/v1/device/capture`
- `GET /api/v1/device/location`
- `POST /api/v1/device/notifications`
- `GET /api/v1/device/capabilities`
- `GET /api/v1/device/permissions`
- `POST /api/v1/device/screen-record/start`
- `POST /api/v1/device/screen-record/stop`

## Fixtures

Mobile API tests use these fixtures from `mobile_api.fixtures.mobile_fixtures`:

### `mobile_test_user`

Creates a test user with UUID v4 email for uniqueness.

```python
def test_with_user(mobile_test_user):
    assert mobile_test_user.email.endswith("@example.com")
    assert mobile_test_user.status == "active"
```

### `mobile_auth_token`

Returns JWT access token for authenticated requests.

```python
def test_with_token(mobile_auth_token):
    headers = {"Authorization": f"Bearer {mobile_auth_token}"}
    # Make authenticated request
```

### `mobile_auth_headers`

Returns Authorization headers dict with Bearer token.

```python
def test_authenticated(mobile_api_client, mobile_auth_headers):
    response = mobile_api_client.get("/api/v1/agents", headers=mobile_auth_headers)
    assert response.status_code == 200
```

### `mobile_api_client`

FastAPI TestClient for in-memory API testing (no server startup).

```python
def test_api_call(mobile_api_client):
    response = mobile_api_client.post("/api/auth/login", json={
        "username": "test@example.com",
        "password": "password"
    })
    assert response.status_code == 200
```

### `mobile_authenticated_client`

Helper function that makes authenticated requests automatically.

```python
def test_auth_call(mobile_authenticated_client):
    response = mobile_authenticated_client("GET", "/api/v1/agents")
    assert response.status_code == 200
```

### `mobile_admin_user`

Creates admin user with superuser privileges.

```python
def test_admin_endpoint(mobile_admin_user):
    admin, token = mobile_admin_user
    assert admin.role == "super_admin"
```

## Consistency with Web API

Mobile API responses match web API responses for consistency:

### Authentication Response

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Agent Execution Response

```json
{
  "execution_id": "exec_abc123",
  "agent_id": "agent_xyz",
  "status": "completed",
  "response": {
    "message": "Task completed successfully"
  }
}
```

### Workflow Execution Response

```json
{
  "execution_id": "wf_exec_456",
  "workflow_id": "workflow_789",
  "status": "running",
  "started_at": "2026-03-24T14:30:00Z"
}
```

## Example API Calls

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test@example.com",
    "password": "password"
  }'
```

### Execute Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/agent_id/execute \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Create a workflow for daily reports"
  }'
```

### Create Workflow

```bash
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Reports",
    "description": "Generate daily reports",
    "category": "automation"
  }'
```

### Get Location

```bash
curl -X GET http://localhost:8000/api/v1/device/location \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Governance Enforcement

Mobile API tests verify governance enforcement:

### Agent Maturity Levels

- **STUDENT**: Cannot execute automated triggers (blocked)
- **INTERN**: Can execute with proposal approval
- **SUPERVISED**: Executes under real-time supervision
- **AUTONOMOUS**: Full execution without oversight

### Device Feature Permissions

- **Camera**: INTERN+ maturity required
- **Location**: INTERN+ maturity required
- **Notifications**: INTERN+ maturity required
- **Screen Recording**: SUPERVISED+ maturity required
- **Command Execution**: AUTONOMOUS only

### Example Governance Test

```python
def test_mobile_device_camera_governance(mobile_api_client, mobile_auth_headers):
    response = mobile_api_client.post(
        "/api/v1/device/capture",
        headers=mobile_auth_headers,
        json={"type": "image", "quality": "high"}
    )

    # Should enforce governance (not succeed silently)
    if response.status_code == 403:
        # Governance blocked - verify error message
        assert "detail" in response.json()
```

## Troubleshooting

### Common Issues

#### 1. Import Errors

```
ImportError: No module named 'core.models'
```

**Solution**: Ensure backend directory is in PYTHONPATH:

```bash
export PYTHONPATH=/Users/rushiparikh/projects/atom/backend:$PYTHONPATH
```

#### 2. Database Session Missing

```
fixture 'mobile_test_user' not found
```

**Solution**: Ensure `db_session` fixture is available from parent conftest:

```python
# In backend/tests/mobile_api/conftest.py
from fixtures.database_fixtures import db_session
```

#### 3. Authentication Failures

```
AssertionError: 401 != 200
```

**Solution**: Verify auth token is correctly set in headers:

```python
headers = {"Authorization": f"Bearer {token}"}
```

#### 4. Endpoint Not Available

```
pytest.skip: Endpoint not implemented
```

**Solution**: This is expected behavior. Tests gracefully skip when endpoints are not available.

#### 5. Device Hardware Not Available

```
pytest.skip: Camera not available in test environment
```

**Solution**: Expected in CI/CD. Tests use graceful skip when hardware unavailable.

### Debug Mode

Run tests with verbose output and print statements:

```bash
pytest backend/tests/mobile_api/ -v -s --tb=short
```

### Stop on First Failure

```bash
pytest backend/tests/mobile_api/ -v -x
```

### Run Failed Tests Only

```bash
pytest backend/tests/mobile_api/ -v --lf
```

## Performance

### TestClient vs Real HTTP

| Method | Latency | Use Case |
|--------|---------|----------|
| TestClient (in-memory) | <10ms | Unit tests, CI/CD |
| Real HTTP (localhost) | ~50ms | Integration tests |
| Real HTTP (remote) | ~200ms | End-to-end tests |

### Optimization Tips

1. **Use TestClient**: Fastest option for API testing
2. **Reuse Fixtures**: Fixtures cache expensive operations
3. **Parallel Execution**: Use `pytest-xdist` for parallel tests
4. **Skip Slow Tests**: Use markers for slow integration tests

```bash
# Run tests in parallel
pytest backend/tests/mobile_api/ -n auto

# Skip slow tests
pytest backend/tests/mobile_api/ -v -m "not slow"
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Mobile API Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run mobile API tests
        run: |
          pytest backend/tests/mobile_api/ -v --cov=backend/api
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Further Reading

- [Backend API Documentation](../../docs/API_DOCUMENTATION.md)
- [Agent Governance System](../../docs/AGENT_GOVERNANCE_SYSTEM.md)
- [Device Capabilities](../../docs/DEVICE_CAPABILITIES.md)
- [Testing Best Practices](../../docs/CODE_QUALITY_STANDARDS.md)

## Contributing

When adding new mobile API tests:

1. Use API-first approach (TestClient, no browser)
2. Follow existing test structure (classes and test names)
3. Add graceful skip for missing endpoints/hardware
4. Verify response structure matches web API
5. Test both success and failure cases
6. Include governance tests where applicable

## License

Internal testing framework for Atom platform.

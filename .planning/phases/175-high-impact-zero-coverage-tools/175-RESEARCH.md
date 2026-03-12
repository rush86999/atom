# Phase 175: High-Impact Zero Coverage (Tools) - Research

**Researched:** March 12, 2026
**Domain:** API Route Testing (Browser, Device, Canvas), FastAPI Integration Testing
**Confidence:** HIGH

## Summary

Phase 175 focuses on achieving 75%+ line coverage on three high-impact API route files that currently have **zero or low coverage**:
- `api/browser_routes.py` (789 lines) - Browser automation endpoints
- `api/device_capabilities.py` (711 lines) - Device hardware access endpoints
- `api/canvas_routes.py` (229 lines) - Canvas presentation and form submission endpoints

**Critical context from Phase 169:** The underlying tools (`browser_tool.py`, `device_tool.py`) achieved 92-95% coverage in Phase 169 with 280 tests. However, the **API routes layer remains untested** - this is the gap Phase 175 must address.

**Key findings:**
1. **Existing test infrastructure exists** - Three test files already present (1391 + 1076 + 950 = 3417 lines total)
2. **Test files use proven patterns** - FastAPI TestClient, dependency overrides, AsyncMock for external services
3. **Three-layer testing strategy** - Mock tool functions, mock governance services, mock WebSocket/Playwright
4. **Routes are thin wrappers** - Most logic delegated to tool functions (already tested at 92-95%), focus on routing logic
5. **Governance integration critical** - All routes enforce maturity levels (INTERN+, SUPERVISED+, AUTONOMOUS)

**Primary recommendation:** Leverage existing test infrastructure and Phase 169 patterns. Focus API route tests on:
- Request/response validation (Pydantic models)
- Governance enforcement (maturity level checks)
- Error handling and HTTP status codes
- Audit trail creation
- Database session management
- Dependency injection overrides

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.0+ | Test runner and fixtures | Industry standard for Python testing, async support via pytest-asyncio |
| **FastAPI TestClient** | Built-in | API endpoint testing | Official FastAPI testing utility, handles dependency overrides |
| **unittest.mock** | Built-in | Mocking AsyncMock, MagicMock, patch | Python standard library, AsyncMock for async functions |
| **SQLAlchemy ORM** | 2.0+ | Database session mocking | Test database sessions for integration tests |

### Testing Dependencies
| Library | Purpose | When to Use |
|---------|---------|-------------|
| **pytest-asyncio** | Async test execution | Required for testing async route handlers |
| **pytest-cov** | Coverage reporting | Generate coverage reports for 75%+ target verification |
| **factory_boy** | Test data factories | Create User, Agent, DeviceNode, BrowserSession instances |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI TestClient | requests + manually | TestClient handles dependency overrides, auth, context |
| pytest | unittest | pytest has superior async/fixture support, widely adopted |
| AsyncMock | asynctest | AsyncMock is built-in since Python 3.8, asynctest deprecated |

**Installation:**
```bash
# Core testing dependencies
pip install pytest pytest-asyncio pytest-cov

# Test data factories
pip install factory-boy
```

## Architecture Patterns

### Recommended Project Structure
```
backend/tests/
├── test_api_browser_routes.py      # EXISTING - 1391 lines, needs review/updates
├── test_api_device_routes.py       # EXISTING - 1076 lines, needs review/updates
├── test_api_canvas_routes.py       # EXISTING - 950 lines, needs review/updates
├── tools/
│   ├── test_browser_tool.py        # COMPLETE - 92% coverage from Phase 169
│   └── test_device_tool.py         # COMPLETE - 95% coverage from Phase 169
└── conftest.py                     # Shared fixtures for TestClient, DB, auth
```

### Pattern 1: FastAPI TestClient with Dependency Overrides
**What:** Override database and auth dependencies for isolated testing
**When to use:** All API route tests need test database and bypassed auth
**Example:**
```python
# Source: backend/tests/test_api_browser_routes.py (lines 45-97)
@pytest.fixture(scope="function")
def client(db_session: Session):
    """Create TestClient with dependency override for test database."""
    from main_api_app import app
    from core.auth import get_current_user
    from core.database import get_db

    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db

    # Override get_current_user to bypass auth
    def _mock_get_current_user():
        user = AdminUserFactory(email="test@example.com", _session=db_session)
        db_session.commit()
        return user

    app.dependency_overrides[get_current_user] = _mock_get_current_user

    test_client = TestClient(app, base_url="http://testserver")
    yield test_client

    app.dependency_overrides.clear()
```

### Pattern 2: Mock Tool Functions (Focus on Routing Logic)
**What:** Mock underlying tool functions that already have 92-95% coverage
**When to use:** Test route behavior without re-testing tool logic
**Example:**
```python
@pytest.mark.asyncio
async def test_browser_navigate_success(client, db_session):
    """Test successful navigation endpoint."""
    with patch('api.browser_routes.browser_navigate') as mock_navigate:
        # Mock tool function (already tested in Phase 169)
        mock_navigate.return_value = {
            "success": True,
            "url": "https://example.com",
            "title": "Example",
            "status": 200
        }

        response = client.post("/api/browser/navigate", json={
            "session_id": "session-123",
            "url": "https://example.com"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["url"] == "https://example.com"
```

### Pattern 3: Governance Service Mocking for Maturity Enforcement
**What:** Mock AgentContextResolver and ServiceFactory for governance checks
**When to use:** Testing all route endpoints that enforce maturity levels
**Example:**
```python
@pytest.fixture
def intern_agent(db_session):
    """Create INTERN agent for governance testing."""
    agent = AgentRegistry(
        id="intern-agent-123",
        name="Test Intern Agent",
        maturity_level="intern",  # INTERN+ required for browser actions
        status="active"
    )
    db_session.add(agent)
    db_session.commit()
    return agent

@pytest.mark.asyncio
async def test_browser_navigate_intern_allowed(client, intern_agent):
    """Test browser navigation allowed for INTERN agent."""
    with patch('api.browser_routes.browser_navigate') as mock_navigate:
        mock_navigate.return_value = {"success": True, "url": "https://example.com"}

        response = client.post("/api/browser/navigate", json={
            "session_id": "session-123",
            "url": "https://example.com",
            "agent_id": "intern-agent-123"
        })

        assert response.status_code == 200
```

### Pattern 4: Audit Trail Verification
**What:** Verify that routes create proper audit entries
**When to use:** All routes should create BrowserAudit, DeviceAudit, or CanvasAudit records
**Example:**
```python
@pytest.mark.asyncio
async def test_browser_navigate_creates_audit(client, db_session):
    """Test that navigation creates audit entry."""
    with patch('api.browser_routes.browser_navigate') as mock_navigate:
        mock_navigate.return_value = {"success": True, "url": "https://example.com"}

        response = client.post("/api/browser/navigate", json={
            "session_id": "session-123",
            "url": "https://example.com"
        })

        # Verify audit created
        audit = db_session.query(BrowserAudit).filter(
            BrowserAudit.action_type == "navigate"
        ).first()

        assert audit is not None
        assert audit.success is True
        assert audit.action_target == "https://example.com"
```

### Anti-Patterns to Avoid
- **Re-testing tool logic:** Don't test browser_navigate() internals - focus on route wrapper
- **Missing dependency cleanup:** Always call app.dependency_overrides.clear() in fixture teardown
- **Hardcoded user IDs:** Use fixtures for User, Agent creation
- **Ignoring audit trails:** Every route should create audit entries
- **Forgetting governance checks:** All routes enforce maturity levels
- **Real Playwright/WebSocket:** Use mocks, not real browsers/devices

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| API testing | Custom HTTP client | FastAPI TestClient | Handles dependency overrides, auth, context |
| Mock objects | Custom mock classes | unittest.mock.AsyncMock | Built-in, battle-tested |
| Test data | Manual object creation | factory_boy factories | Consistent test data, easy maintenance |
| Auth bypass | Custom auth logic | dependency_overrides[get_current_user] | Official FastAPI pattern |
| Database isolation | In-memory DB | SQLite test database | Same ORM, faster than PostgreSQL |

**Key insight:** API route tests are integration tests, not unit tests. Use TestClient to test the full request/response cycle, but mock external dependencies (Playwright, WebSocket) that are already tested elsewhere.

## Common Pitfalls

### Pitfall 1: Re-testing Already Covered Tool Logic
**What goes wrong:** Duplicating tests from Phase 169 (browser_tool.py, device_tool.py at 92-95% coverage)
**Why it happens:** Routes are thin wrappers around tool functions, tempting to test deeply
**How to avoid:**
1. Mock tool functions with patch()
2. Focus on route-specific logic (request parsing, response formatting, error handling)
3. Verify tool functions are called with correct arguments
4. Don't test tool internals (already covered)
**Warning signs:** Tests mirror tool test structure, testing Playwright/WebSocket mocking

### Pitfall 2: Forgetting Dependency Override Cleanup
**What goes wrong:** Dependency overrides leak between tests, causing flaky failures
**Why it happens:** TestClient fixtures don't automatically clean up dependency_overrides
**How to avoid:**
```python
@pytest.fixture(scope="function")
def client(db_session: Session):
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _mock_user

    yield test_client

    app.dependency_overrides.clear()  # CRITICAL: cleanup
```
**Warning signs:** Tests pass individually but fail in suite, auth errors in random tests

### Pitfall 3: Not Testing Audit Trail Creation
**What goes wrong:** Routes work but don't create audit entries (governance requirement)
**Why it happens:** Focus on happy path, forget audit is critical for compliance
**How to avoid:**
1. Every route test should query audit table after call
2. Verify audit.action_type, audit.success, audit.agent_id
3. Test audit creation on both success and failure paths
**Warning signs:** Coverage high but governance requirements unverified

### Pitfall 4: Ignoring Governance Enforcement
**What goes wrong:** Routes don't check agent maturity levels
**Why it happens:** Mocking governance service, forgetting to verify it's called
**How to avoid:**
1. Create agents at different maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
2. Test that STUDENT agents are blocked
3. Test that INTERN/SUPERVISED/AUTONOMOUS agents are allowed (as appropriate)
4. Verify governance_check_passed in audit entries
**Warning signs:** All agents allowed regardless of maturity level

### Pitfall 5: Missing Error Path Testing
**What goes wrong:** Coverage shows 50% when you expected 75%
**Why it happens:** Only testing success paths, not error handling
**How to avoid:**
Test all error branches:
- Invalid request data (Pydantic validation errors)
- Resource not found (session doesn't exist)
- Governance blocked (wrong maturity level)
- Tool function failure (returns success=False)
- Database errors (constraint violations)
**Warning signs:** Large gaps in if/else branches in coverage report

### Pitfall 6: Async/Sync Mismatch in Route Testing
**What goes wrong:** Tests hang or fail with "coroutine not awaited"
**Why it happens:** Routes are async but test client expects sync, or vice versa
**How to avoid:**
```python
# WRONG: Mixing async/sync
@pytest.mark.asyncio
async def test_route(client):  # client is sync TestClient
    result = await client.post(...)  # ERROR

# CORRECT: Use sync TestClient
def test_route(client):
    response = client.post(...)  # OK - TestClient handles async internally

# CORRECT: For truly async tests, use httpx directly
@pytest.mark.asyncio
async def test_route_async():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(...)
```
**Warning signs:** "RuntimeWarning: coroutine was never awaited", tests hanging indefinitely

## Code Examples

Verified patterns from existing test files:

### Browser Route Navigation with Governance
```python
# Source: backend/tests/test_api_browser_routes.py (pattern)
def test_browser_navigate_with_agent(client, db_session):
    """Test browser navigation with agent governance."""
    # Create INTERN agent
    agent = AgentRegistry(
        id="agent-123",
        name="Test Agent",
        maturity_level="intern",
        status="active"
    )
    db_session.add(agent)
    db_session.commit()

    with patch('api.browser_routes.browser_navigate') as mock_navigate:
        mock_navigate.return_value = {
            "success": True,
            "url": "https://example.com",
            "title": "Example"
        }

        response = client.post("/api/browser/navigate", json={
            "session_id": "session-123",
            "url": "https://example.com",
            "agent_id": "agent-123"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify governance check was performed
        audit = db_session.query(BrowserAudit).first()
        assert audit.agent_id == "agent-123"
```

### Device Camera Snap with WebSocket Mocking
```python
# Source: backend/tests/test_api_device_routes.py (pattern)
@pytest.mark.asyncio
async def test_device_camera_snap_success(client, db_session):
    """Test camera snap endpoint."""
    with patch('api.device_capabilities.device_camera_snap') as mock_camera:
        mock_camera.return_value = {
            "success": True,
            "file_path": "/tmp/photo.jpg",
            "base64_data": "base64encoded"
        }

        response = client.post("/api/devices/camera/snap", json={
            "device_node_id": "device-123",
            "resolution": "1920x1080"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["file_path"] == "/tmp/photo.jpg"

        # Verify audit created
        audit = db_session.query(DeviceAudit).filter(
            DeviceAudit.action_type == "camera_snap"
        ).first()
        assert audit.success is True
```

### Canvas Form Submission with Agent Tracking
```python
# Source: backend/tests/test_api_canvas_routes.py (pattern)
@pytest.mark.asyncio
async def test_canvas_submit_form_with_agent(client, db_session):
    """Test canvas form submission with agent."""
    agent = AgentRegistry(
        id="agent-123",
        maturity_level="supervised",  # SUPERVISED+ required for form submit
        status="active"
    )
    db_session.add(agent)
    db_session.commit()

    with patch('api.canvas_routes.ws_manager') as mock_ws:
        mock_ws.broadcast = AsyncMock()

        response = client.post("/api/canvas/submit", json={
            "canvas_id": "canvas-123",
            "form_data": {"field1": "value1"},
            "agent_id": "agent-123"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "submission_id" in data["data"]

        # Verify agent execution created
        execution = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == "agent-123"
        ).first()
        assert execution is not None
        assert execution.status == "completed"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| requests + manual setup | FastAPI TestClient | FastAPI 0.100+ | Official testing utility, dependency overrides built-in |
| Mock everything | Mock only external deps | 2023+ | Test more of the actual routing logic |
| Integration tests only | Unit + Integration | Always | Phase 169 did unit (tools), Phase 175 does integration (routes) |
| No audit verification | Audit required | Governance enforcement | Compliance requirement, all routes must audit |

**Deprecated/outdated:**
- **requests library for FastAPI testing:** Use TestClient instead (handles async, dependencies, context)
- **Mocking database:** Use actual test database with SQLite (faster, more realistic)
- **Skipping auth tests:** Always test auth/governance in integration tests

## Open Questions

1. **Current test file status?**
   - What we know: Three test files exist (3417 lines total)
   - What's unclear: Are tests passing? What's current coverage?
   - Recommendation: Run pytest on existing tests first, fix failures, then add coverage gaps

2. **Tool function mocking strategy?**
   - What we know: Tools have 92-95% coverage, shouldn't re-test
   - What's unclear: Should we mock entire tool module or individual functions?
   - Recommendation: Mock individual functions (browser_navigate, device_camera_snap) for finer control

3. **WebSocket/Playwright in route tests?**
   - What we know: Tools already mock these dependencies (Phase 169)
   - What's unclear: Do routes need additional WebSocket/Playwright mocking?
   - Recommendation: No - routes call tool functions, tool functions handle WebSocket/Playwright

4. **Coverage target feasibility?**
   - What we know: Target is 75%+ for all three route files
   - What's unclear: Are there untestable code paths (defensive programming)?
   - Recommendation: Achieve 75%+, accept remaining gaps if defensive/error handlers

## Sources

### Primary (HIGH confidence)
- **backend/tests/test_api_browser_routes.py** - 1391 lines, existing browser route tests
- **backend/tests/test_api_device_routes.py** - 1076 lines, existing device route tests
- **backend/tests/test_api_canvas_routes.py** - 950 lines, existing canvas route tests
- **backend/api/browser_routes.py** - 789 lines, target for coverage (session, navigate, screenshot, etc.)
- **backend/api/device_capabilities.py** - 711 lines, target for coverage (camera, location, notification, execute)
- **backend/api/canvas_routes.py** - 229 lines, target for coverage (submit, status)
- **Phase 169 RESEARCH.md** - Proven patterns for browser/device testing (92-95% coverage achieved)
- **Phase 169 SUMMARIES** - 280 tests created, governance integration, edge cases covered

### Secondary (MEDIUM confidence)
- **FastAPI Testing Documentation** - TestClient usage, dependency overrides (verified against codebase examples)
- **pytest documentation** - Async testing with pytest-asyncio (verified against codebase patterns)
- **SQLAlchemy ORM Testing** - Database session mocking, test database setup (verified against conftest.py)

### Tertiary (LOW confidence)
- **API testing best practices** - General patterns (not verified against official docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - FastAPI TestClient, pytest, AsyncMock are industry standards
- Architecture: HIGH - Existing test files show proven patterns (3417 lines of tests already written)
- Pitfalls: HIGH - Common issues observed in integration testing (dependency leaks, audit gaps)
- Coverage targets: MEDIUM - 75%+ is reasonable but untestable code may exist (error handlers)

**Research date:** March 12, 2026
**Valid until:** 30 days (stable testing patterns, FastAPI API unlikely to change)

**Files analyzed:**
- backend/api/browser_routes.py (789 lines, 11 endpoints)
- backend/api/device_capabilities.py (711 lines, 10 endpoints)
- backend/api/canvas_routes.py (229 lines, 2 endpoints)
- backend/tests/test_api_browser_routes.py (1391 lines, existing tests)
- backend/tests/test_api_device_routes.py (1076 lines, existing tests)
- backend/tests/test_api_canvas_routes.py (950 lines, existing tests)
- backend/tools/browser_tool.py (92% coverage from Phase 169)
- backend/tools/device_tool.py (95% coverage from Phase 169)

**Phase dependencies:**
- Requires: Phase 169 (Tools & Integrations Coverage) - provides 92-95% tool coverage, test patterns
- Provides: API route coverage (browser, device, canvas) - governance enforcement, audit verification

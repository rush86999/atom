# Phase 178: API Routes Coverage (Admin & System) - Research

**Researched:** March 12, 2026
**Domain:** FastAPI Route Testing with TestClient
**Confidence:** HIGH

## Summary

Phase 178 focuses on achieving 75%+ line coverage on admin and system management API routes using pytest with TestClient. This phase covers four primary route groups: (1) Admin skill routes (`api/admin/skill_routes.py`), (2) Admin business facts routes (`api/admin/business_facts_routes.py`), (3) System health routes (`api/admin/system_health_routes.py` and `api/health_routes.py`), and (4) Admin endpoints (`api/admin_routes.py` and `api/sync_admin_routes.py`).

**Key finding:** Based on analysis of Phase 177 (Analytics & Reporting) patterns and existing admin routes test structure, this phase requires 3-4 plans using the established TestClient + per-file FastAPI app pattern with AsyncMock for external services. The admin routes have unique characteristics: governance enforcement (AUTONOMOUS maturity required), super_admin role checks, file upload handling, and integration with external services (LanceDB, R2/S3, Redis).

**Primary recommendation:** Create test files for each route group following Phase 177 patterns: use per-file FastAPI apps to avoid SQLAlchemy session conflicts, mock external services (WorldModelService, StorageService, RatingSyncService, ConflictResolutionService) with AsyncMock, and test both happy paths and error paths (401 unauthorized, 404 not found, 409 conflict, 500 server errors, validation errors).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test runner and fixtures | Industry standard for Python testing with powerful fixture system |
| **FastAPI TestClient** | 0.104+ | API route testing | Official FastAPI testing approach, provides async support |
| **AsyncMock** | Python 3.11+ | Async service mocking | Built-in mocking for async services, no dependencies |
| **SQLite in-memory** | 3.40+ | Test database | Fast, isolated database for each test, no external dependencies |
| **coverage.py** | 7.3+ | Line coverage measurement | Standard Python coverage tool with pytest-cov integration |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-asyncio** | 0.21+ | Async test support | Required for testing async route handlers |
| **sqlalchemy** | 2.0+ | ORM for test setup | Used for creating test data fixtures with Session |
| **pydantic** | 2.0+ | Request/response validation | Verify response models match route definitions |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TestClient | httpx.AsyncClient | Lower-level, more manual setup required |
| AsyncMock | MagicMock with async wrappers | More verbose, AsyncMock handles async/await correctly |
| In-memory SQLite | PostgreSQL test database | Slower test execution, requires external database |

**Installation:**
```bash
# All required packages already installed
pip install pytest pytest-asyncio pytest-cov fastapi sqlalchemy pydantic
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/api/
├── conftest.py                      # Shared fixtures (auth, db, clients)
├── test_admin_skill_routes.py       # NEW: Admin skill routes tests
├── test_admin_business_facts_routes.py  # NEW: Business facts routes tests
├── test_admin_system_health_routes.py   # NEW: System health routes tests
├── test_admin_endpoints_routes.py   # NEW: Admin endpoints (Part 3: remaining)
└── test_health_routes.py            # EXISTS: Extend with error path tests
```

### Pattern 1: Per-File FastAPI App with TestClient

**What:** Create isolated FastAPI app for each router to avoid SQLAlchemy session conflicts and dependency injection pollution between tests.

**When to use:** All API route testing. Proven pattern from Phase 167, 172, 177.

**Example:**
```python
# Source: Phase 177-01-SUMMARY.md, backend/tests/api/test_analytics_dashboard_routes.py

@pytest.fixture(scope="function")
def test_app(test_db: Session):
    """Create FastAPI app with admin routes for testing."""
    app = FastAPI()
    app.include_router(router)  # Include only the router being tested

    # Override get_db dependency to use test database
    from core.database import get_db

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield app

    # Clean up overrides
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def client(test_app: FastAPI):
    """Create TestClient for testing."""
    return TestClient(test_app)
```

**Why this pattern:** Prevents SQLAlchemy session conflicts when multiple routers use the same database dependency. Each test file gets an isolated FastAPI app with its own dependency overrides.

### Pattern 2: AsyncMock for External Services

**What:** Mock external service calls using AsyncMock to control return values and test error paths.

**When to use:** Routes that depend on external services (WorldModelService, StorageService, RatingSyncService, ConflictResolutionService, LanceDBHandler).

**Example:**
```python
# Source: Phase 172-01-SUMMARY.md, backend/tests/api/conftest.py

from unittest.mock import AsyncMock

@pytest.fixture(scope="function")
def mock_world_model_service():
    """AsyncMock for WorldModelService with deterministic return values."""
    mock = AsyncMock()

    # Configure deterministic return values
    mock.list_all_facts.return_value = [
        BusinessFact(
            id="fact-1",
            fact="Invoices over $500 require VP approval",
            citations=["s3://bucket/policies/ap-policy.pdf:page4"],
            reason="Extracted from AP policy",
            verification_status="verified",
            created_at=datetime.now()
        )
    ]

    mock.get_fact_by_id.return_value = BusinessFact(...)
    mock.record_business_fact.return_value = True
    mock.delete_fact.return_value = True

    return mock

# Use in tests
def test_list_facts_success(authenticated_client: TestClient, mock_world_model_service):
    with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
        response = authenticated_client.get("/api/admin/governance/facts")
        assert response.status_code == 200
```

### Pattern 3: Authentication and Authorization Fixtures

**What:** Create fixtures for authenticated clients with different user roles (super_admin, admin, regular user).

**When to use:** Routes that require authentication or role-based access control.

**Example:**
```python
# Source: backend/tests/api/test_admin_routes_part1.py

@pytest.fixture(scope="function")
def super_admin_user(test_db: Session) -> User:
    """Create super admin user for testing."""
    user = User(
        id="admin_test_user",
        email="admin@test.com",
        name="Test Admin",
        role="super_admin",
        tenant_id="test_tenant",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user

@pytest.fixture(scope="function")
def authenticated_admin_client(client: TestClient, super_admin_user: User):
    """Create authenticated TestClient with super admin user."""
    from core.auth import get_current_user

    def override_get_current_user():
        return super_admin_user

    client.app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    client.app.dependency_overrides.clear()

def test_create_admin_role_requires_super_admin(authenticated_admin_client):
    """Test that role creation requires super_admin role."""
    response = authenticated_admin_client.post(
        "/api/admin/roles",
        json={"name": "test_role", "permissions": {"users": True}}
    )
    assert response.status_code == 201
```

### Anti-Patterns to Avoid

- **Shared FastAPI app across test files:** Causes SQLAlchemy session conflicts and dependency injection pollution
- **Synchronous mocking of async services:** Use AsyncMock, not MagicMock with async wrappers
- **Hardcoded database IDs:** Use fixtures or uuid.uuid4() for deterministic test data
- **Missing cleanup in fixtures:** Always yield fixtures and clean up resources (db.close(), app.dependency_overrides.clear())

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async service mocking | Manual async wrapper classes | AsyncMock from unittest.mock | Handles async/await correctly, less code |
| Database isolation | Shared PostgreSQL database | In-memory SQLite with StaticPool | Faster test execution, no external dependencies |
| Auth token generation | Manual JWT creation | Mock get_current_user dependency | Simpler, no crypto overhead, deterministic |
| File upload testing | Real filesystem with temp files | io.BytesIO with UploadFile mock | Faster, no cleanup required, works in CI |
| Coverage measurement | Custom scripts | pytest --cov with coverage.json | Standard tool, better IDE integration |

**Key insight:** The per-file FastAPI app pattern from Phase 167/172/177 eliminates 90% of testing complexity. Don't invent new patterns; follow what works.

## Common Pitfalls

### Pitfall 1: SQLAlchemy Session Conflicts

**What goes wrong:** Tests fail with "Session is already bound to a connection" or "SQLite objects created in a thread can only be used in that same thread".

**Why it happens:** Multiple test files sharing the same FastAPI app with different Session overrides cause SQLAlchemy's scoped_session to leak connections between tests.

**How to avoid:** Use per-file FastAPI app pattern (Pattern 1). Each test file creates its own FastAPI app with its own get_db override. This ensures complete isolation.

**Warning signs:** Tests pass individually but fail in parallel; intermittent SQLite threading errors; database state leaking between tests.

### Pitfall 2: External Service Calls Not Mocked

**What goes wrong:** Tests make real HTTP requests to R2/S3, LanceDB, or Redis, causing slow tests or CI failures.

**Why it happens:** Routes import services directly at module level, making them difficult to mock.

**How to avoid:** Patch service at the point of use in the route module:
```python
# GOOD: Patch at import location
def test_upload_and_extract(authenticated_client, mock_storage_service):
    with patch('api.admin.business_facts_routes.get_storage_service', return_value=mock_storage_service):
        # Test file upload

# BAD: Patch at definition location
def test_upload_and_extract(authenticated_client, mock_storage_service):
    with patch('core.storage.get_storage_service', return_value=mock_storage_service):
        # This might not work if business_facts_routes imports it differently
```

**Warning signs:** Tests take >1 second each; CI fails with network errors; tests require AWS credentials.

### Pitfall 3: Governance Enforcement Not Tested

**What goes wrong:** Tests don't verify that AUTONOMOUS maturity is required for critical actions.

**Why it happens:** Tests always use super_admin user which bypasses governance checks, or mocks don't simulate lower maturity levels.

**How to avoid:** Create fixtures for different maturity levels and test governance rejection:
```python
@pytest.fixture
def intern_user(test_db: Session) -> User:
    """Create INTERN maturity user for testing governance."""
    return User(id="intern", role="user", tenant_id="test", is_active=True)

def test_create_admin_role_blocked_for_intern(intern_client):
    """Test that INTERN maturity cannot create admin roles."""
    response = intern_client.post("/api/admin/roles", json={...})
    assert response.status_code == 403  # Permission denied
```

**Warning signs:** All tests use super_admin; no 403 responses tested; governance decorators never exercised.

### Pitfall 4: File Upload Handling Overcomplicated

**What goes wrong:** Tests create real temp files, require filesystem cleanup, fail in CI environments.

**Why it happens:** Trying to test UploadFile with real filesystem instead of mocking.

**How to avoid:** Use FastAPI's UploadFile with BytesIO:
```python
from fastapi import UploadFile
import io

@pytest.fixture
def mock_upload_file():
    """Create mock UploadFile without filesystem."""
    return UploadFile(
        filename="test.pdf",
        file=io.BytesIO(b"test content"),
        content_type="application/pdf"
    )

def test_upload_and_extract(authenticated_client, mock_upload_file):
    """Test document upload without real files."""
    with patch('api.admin.business_facts_routes.get_storage_service'):
        response = authenticated_client.post(
            "/api/admin/governance/facts/upload",
            files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
            data={"domain": "accounting"}
        )
```

**Warning signs:** Tests use tempfile.mkdtemp(); tests fail with permission errors; tests require cleanup in finally blocks.

## Code Examples

Verified patterns from Phase 177 and existing admin routes tests:

### Example 1: Testing CRUD Operations with Governance

```python
# Source: backend/tests/api/test_admin_routes_part1.py (extended pattern)

class TestAdminRoleCRUD:
    """Tests for admin role CRUD operations."""

    def test_create_admin_role_success(self, authenticated_admin_client: TestClient, test_db: Session):
        """Test successful admin role creation."""
        response = authenticated_admin_client.post(
            "/api/admin/roles",
            json={
                "name": "test_role",
                "permissions": {"users": True, "workflows": False},
                "description": "Test role for coverage"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test_role"
        assert data["permissions"]["users"] is True

    def test_create_admin_role_duplicate_name(self, authenticated_admin_client: TestClient, test_db: Session):
        """Test that duplicate role names return 409 conflict."""
        # Create first role
        authenticated_admin_client.post(
            "/api/admin/roles",
            json={"name": "duplicate_role", "permissions": {}}
        )

        # Try to create duplicate
        response = authenticated_admin_client.post(
            "/api/admin/roles",
            json={"name": "duplicate_role", "permissions": {}}
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_delete_admin_role_with_users_fails(self, authenticated_admin_client: TestClient, test_db: Session):
        """Test that deleting role with assigned users returns 409."""
        # Create role and assign to user
        # ... setup code ...

        response = authenticated_admin_client.delete(f"/api/admin/roles/{role_id}")
        assert response.status_code == 409
        assert "still assigned" in response.json()["detail"]
```

### Example 2: Testing File Upload with Mocked Storage

```python
# Pattern for testing business facts upload

class TestBusinessFactsUpload:
    """Tests for business facts document upload."""

    def test_upload_and_extract_success(self, authenticated_admin_client: TestClient):
        """Test successful document upload and fact extraction."""
        from unittest.mock import patch, MagicMock

        # Mock storage service
        mock_storage = MagicMock()
        mock_storage.upload_file.return_value = "s3://test-bucket/business_facts/test.pdf"
        mock_storage.check_exists.return_value = True

        # Mock policy fact extractor
        mock_extractor = AsyncMock()
        mock_extractor.extract_facts_from_document.return_value = ExtractionResult(
            facts=[
                ExtractedFact(
                    fact="Invoices over $500 require VP approval",
                    domain="accounting",
                    confidence=0.95
                )
            ],
            extraction_time=1.5
        )

        with patch('api.admin.business_facts_routes.get_storage_service', return_value=mock_storage):
            with patch('api.admin.business_facts_routes.get_policy_fact_extractor', return_value=mock_extractor):
                response = authenticated_admin_client.post(
                    "/api/admin/governance/facts/upload",
                    files={"file": ("policy.pdf", io.BytesIO(b"pdf content"), "application/pdf")},
                    data={"domain": "accounting"}
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["facts_extracted"] == 1
        assert len(data["facts"]) == 1

    def test_upload_invalid_file_type(self, authenticated_admin_client: TestClient):
        """Test that invalid file types return validation error."""
        response = authenticated_admin_client.post(
            "/api/admin/governance/facts/upload",
            files={"file": ("test.exe", io.BytesIO(b"exe content"), "application/exe")},
            data={"domain": "general"}
        )
        assert response.status_code == 422  # Validation error
        assert "Unsupported file type" in response.json()["detail"]
```

### Example 3: Testing System Health Endpoints

```python
# Pattern for testing health check endpoints

class TestSystemHealth:
    """Tests for system health check endpoints."""

    def test_system_health_all_operational(self, admin_client: TestClient):
        """Test health check when all services are operational."""
        from unittest.mock import patch, MagicMock

        # Mock database check
        mock_db = MagicMock()
        mock_db.execute.return_value = True

        # Mock Redis
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        # Mock LanceDB
        mock_lancedb = MagicMock()
        mock_lancedb.test_connection.return_value = {"connected": True}

        with patch('core.cache.cache.redis_client', mock_redis):
            with patch('core.lancedb_handler.LanceDBHandler', return_value=mock_lancedb):
                response = admin_client.get("/api/admin/health/api/admin/health")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "healthy"
        assert data["data"]["services"]["database"] == "operational"
        assert data["data"]["services"]["redis"] == "operational"
        assert data["data"]["services"]["vector_store"] == "operational"

    def test_system_health_degraded_when_db_slow(self, admin_client: TestClient):
        """Test health check returns degraded when database is slow."""
        import time
        from unittest.mock import patch

        # Mock slow database (2.5 second response)
        def slow_db_execute(*args, **kwargs):
            time.sleep(0.1)  # Simulate slow query
            return True

        mock_db = MagicMock()
        mock_db.execute.side_effect = slow_db_execute

        with patch('core.cache.cache.redis_client', None):  # Redis disabled
            with patch.object(db, 'execute', side_effect=slow_db_execute):
                response = admin_client.get("/api/admin/health/api/admin/health")

        # Should still return 200 but with degraded status
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] in ["healthy", "degraded"]
```

### Example 4: Testing WebSocket Management

```python
# Source: backend/tests/api/test_admin_routes_part2.py (existing pattern)

class TestWebSocketManagement:
    """Tests for WebSocket management endpoints."""

    def test_get_websocket_status_connected(self, authenticated_admin_client: TestClient, test_db: Session):
        """Test WebSocket status when connected."""
        from datetime import datetime, timezone

        # Create WebSocket state
        ws_state = WebSocketState(
            id=1,
            connected=True,
            ws_url="wss://api.example.com/ws",
            last_connected_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
            reconnect_attempts=3,
            consecutive_failures=0,
            disconnect_reason=None,
            fallback_to_polling=False
        )
        test_db.add(ws_state)
        test_db.commit()

        response = authenticated_admin_client.get("/api/admin/websocket/status")
        assert response.status_code == 200

        data = response.json()
        assert data["connected"] is True
        assert data["reconnect_attempts"] == 3
        assert data["fallback_to_polling"] is False

    def test_trigger_websocket_reconnect(self, authenticated_admin_client: TestClient, test_db: Session):
        """Test WebSocket reconnect trigger."""
        response = authenticated_admin_client.post("/api/admin/websocket/reconnect")
        assert response.status_code == 200

        data = response.json()
        assert data["reconnect_triggered"] is True
        assert "reconnection triggered" in data["message"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Shared app with global overrides | Per-file FastAPI apps | Phase 167 (Dec 2025) | Eliminated SQLAlchemy session conflicts, enabled parallel testing |
| MagicMock for async services | AsyncMock with async/await | Phase 172 (Jan 2026) | Correct async handling, cleaner test code |
| Real PostgreSQL for tests | In-memory SQLite with StaticPool | Phase 156 (Mar 2026) | 10x faster test execution, no external dependencies |
| Manual coverage measurement | pytest --cov with coverage.json | Phase 153 (Mar 2026) | Automated coverage tracking, IDE integration |

**Deprecated/outdated:**
- **Shared fixture modules:** Previous pattern of conftest.py with global fixtures caused conflicts. Now use per-file fixtures.
- **Real service integration testing:** Tests that make real HTTP calls to external services are too slow and flaky. Use AsyncMock instead.
- **Synchronous wrappers for async:** Creating wrapper classes to make async services synchronous is unnecessary. AsyncMock handles this correctly.

## Open Questions

1. **Business facts LanceDB import failure**
   - What we know: system_health_routes.py has safe import try/except for LanceDBHandler that sets HAS_LANCEDB flag
   - What's unclear: Should tests mock LanceDBHandler or should we create a minimal LanceDB test instance?
   - Recommendation: Mock LanceDBHandler with AsyncMock to avoid external dependencies. Set HAS_LANCEDB=True in test module to enable the code path. Follow pattern from system_health_routes.py line 73-87.

2. **Storage service R2/S3 mocking**
   - What we know: business_facts_routes.py uses storage service for file uploads and citation verification
   - What's unclear: Should we verify the entire upload/verify flow or mock at service boundary?
   - Recommendation: Mock at service boundary (get_storage_service()). Don't test actual R2/S3 uploads. Test citation verification with mock storage.check_exists() returning True/False to cover both paths.

3. **Governance maturity testing**
   - What we know: Admin routes have @require_governance decorators with AUTONOMOUS maturity requirements
   - What's unclear: Should we create tests for each maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)?
   - Recommendation: Test only AUTONOMOUS (success) and non-AUTONOMOUS (rejection). Don't test all intermediate levels. Follow pattern from Phase 172 governance tests: create one "restricted_user" fixture with lower maturity and verify 403 response.

## Sources

### Primary (HIGH confidence)

- **Phase 177-01-SUMMARY.md** - Analytics dashboard routes coverage plan execution summary
  - Verified patterns: Per-file FastAPI app, AsyncMock for analytics engine, TestClient structure
  - Test fixture patterns from conftest.py: mock_analytics_engine, mock_performance_metrics
  - Coverage measurement approach: pytest --cov with coverage.json output

- **Phase 172-01-SUMMARY.md** - Agent control routes coverage with governance enforcement
  - Verified patterns: Governance testing with maturity mocks, error path testing
  - Mock patterns: AsyncMock for GovernanceCache, AgentContextResolver
  - Test structure: Separate test classes per endpoint group

- **backend/tests/api/test_admin_routes_part1.py** - Existing admin routes tests (lines 1-545)
  - Verified patterns: Admin user/role CRUD, super_admin fixture, authentication
  - Test database setup: In-memory SQLite with StaticPool
  - Coverage: User CRUD (6 tests), Role CRUD (5 tests), auth (2 tests)

- **backend/tests/api/test_admin_routes_part2.py** - Existing admin routes tests (lines 546-1355)
  - Verified patterns: WebSocket management, rating sync, conflict resolution
  - Mock patterns: AsyncMock for RatingSyncService, ConflictResolutionService
  - Coverage: WebSocket (13 tests), Rating sync (8 tests), Conflicts (6 tests)

- **backend/tests/api/test_health_routes.py** - Existing health routes tests
  - Verified patterns: Liveness probe, readiness probe, database check, metrics endpoint
  - Mock patterns: AsyncMock for database checks, psutil disk space mocking
  - Coverage: Liveness (4 tests), Readiness (8 tests), Database (5 tests)

### Secondary (MEDIUM confidence)

- **FastAPI Testing Documentation** - https://fastapi.tiangolo.com/tutorial/testing/
  - Verified TestClient usage, dependency overrides, async test support
  - Official patterns for testing FastAPI applications

- **pytest Documentation** - https://docs.pytest.org/en/stable/
  - Verified fixture patterns, scope management, parametrization
  - Coverage measurement with pytest-cov

- **Python unittest.mock Documentation** - https://docs.python.org/3/library/unittest.mock.html
  - Verified AsyncMock usage, patch() strategies, MagicMock vs AsyncMock
  - Mocking async services and context managers

### Tertiary (LOW confidence)

- None. All patterns verified from primary sources (existing test files and Phase 177/172 summaries).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified from existing test files and Phase 177 patterns
- Architecture: HIGH - Per-file FastAPI app pattern proven in Phases 167, 172, 177
- Pitfalls: HIGH - All pitfalls identified from existing test failures and Phase 177 learnings
- Code examples: HIGH - All examples verified from existing test files (test_admin_routes_part1.py, test_admin_routes_part2.py, test_health_routes.py)

**Research date:** March 12, 2026
**Valid until:** April 11, 2026 (30 days - stable testing patterns, unlikely to change)

**Estimated effort:**
- Plan 01 (Admin skill routes): 600-800 lines of tests, 8-10 hours
- Plan 02 (Admin business facts routes): 700-900 lines of tests, 10-12 hours
- Plan 03 (System health routes): 500-700 lines of tests, 6-8 hours
- Plan 04 (Admin endpoints - Part 3): 400-600 lines of tests, 6-8 hours
- **Total:** 2200-3000 lines of tests, 30-38 hours (4 plans)

**Key success metrics:**
- 75%+ line coverage on all 4 route groups (measured via pytest --cov)
- All endpoints tested with happy paths and error paths (401, 403, 404, 409, 422, 500)
- External services mocked correctly (AsyncMock for WorldModelService, StorageService, etc.)
- Governance enforcement tested (AUTONOMOUS required for critical actions)
- File upload tested without real filesystem (BytesIO mock)

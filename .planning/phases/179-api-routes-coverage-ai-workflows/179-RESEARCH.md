# Phase 179: API Routes Coverage (AI Workflows & Automation) - Research

**Researched:** March 12, 2026
**Domain:** FastAPI Route Testing with TestClient
**Confidence:** HIGH

## Summary

Phase 179 requires comprehensive test coverage for AI workflow and automation route files, building on established patterns from Phase 177 (API Routes Coverage) and Phase 178 (Admin System Coverage). The phase targets five route files totaling 1,024 lines of code:

1. **ai_workflows_routes.py** (182 lines) - NLU parsing, text completion, AI providers
2. **ai_accounting_routes.py** (352 lines) - Transaction ingestion, categorization, posting, forecasting
3. **auto_install_routes.py** (100 lines) - Package installation with dependency resolution
4. **workflow_analytics_routes.py** (30 lines) - Execution metrics and analytics
5. **workflow_template_routes.py** (360 lines) - Template CRUD, instantiation, execution

All routes follow the standard FastAPI pattern with Pydantic models, BaseAPIRouter extensions, and dependency injection. The testing approach uses per-file FastAPI apps with isolated TestClient instances to avoid SQLAlchemy metadata conflicts (confirmed pattern from Phase 177).

**Primary recommendation:** Use the Phase 177/178 pattern with 3-4 test files (600-800 lines each) covering happy paths, error paths, authentication (where applicable), and edge cases. Target 75%+ line coverage with TestClient-based integration tests using MagicMock for external services.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 7.4+ | Test framework | Industry standard for Python testing, fixtures, parametrization |
| FastAPI | 0.100+ | Web framework | Existing codebase uses FastAPI with BaseAPIRouter |
| TestClient | fastapi.testclient | HTTP testing | Official FastAPI testing utility, no real server needed |
| Pydantic | 2.0+ | Request/response validation | All routes use Pydantic models (BaseModel subclasses) |
| SQLAlchemy | 2.0+ | ORM (mocked) | Existing codebase uses SQLAlchemy, mocked in tests |

### Testing Utilities

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | builtin | Mock/AsyncMock/MagicMock | All external service dependencies (LLM, database, Docker) |
| pytest fixtures | builtin | Test setup/teardown | Database fixtures, TestClient, mock services |
| sqlalchemy.pool.StaticPool | builtin | In-memory SQLite | Prevents database locking during tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TestClient | httpx.AsyncClient | TestClient is synchronous, easier to write, officially supported by FastAPI |
| MagicMock | monkeypatch | MagicMock is more versatile for complex objects, monkeypatch simpler for globals |
| Per-file FastAPI apps | Single shared app | Shared app causes SQLAlchemy metadata conflicts (Phase 177 finding) |

**Installation:**
```bash
# All packages already installed in Atom backend
pip install pytest pytest-asyncio fastapi sqlalchemy
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/api/
├── test_ai_workflows_routes_coverage.py    # NEW - AI workflows routes
├── test_ai_accounting_routes_coverage.py   # NEW - AI accounting routes
├── test_auto_install_routes_coverage.py    # NEW - Auto install routes
└── test_workflow_template_routes_coverage.py  # NEW - Workflow template routes (updates existing)
```

### Pattern 1: Per-File FastAPI Apps with TestClient

**What:** Each test file creates isolated FastAPI app including the target router, avoiding SQLAlchemy metadata conflicts.

**When to use:** ALL API route testing (established pattern from Phase 177-178).

**Example:**
```python
# Source: Phase 177/178 pattern (test_admin_system_health_routes.py)
@pytest.fixture(scope="function")
def client():
    """TestClient with isolated FastAPI app."""
    from fastapi import FastAPI
    from api.ai_workflows_routes import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)
```

### Pattern 2: Mock External Services with MagicMock

**What:** All external dependencies (database, LLM services, Docker) mocked using unittest.mock.

**When to use:** ALL external service calls in route handlers.

**Example:**
```python
# Source: Phase 177 pattern
@pytest.fixture
def mock_ai_service():
    """Mock AI service for NLU/completion endpoints."""
    mock = MagicMock()
    mock.process_with_nlu = AsyncMock(return_value={
        'intent': 'scheduling',
        'entities': [],
        'confidence': 0.85
    })
    return mock

def test_parse_nlu_success(client, mock_ai_service):
    with patch('api.ai_workflows_routes.ai_service', mock_ai_service):
        response = client.post("/api/ai-workflows/nlu/parse", json={
            "text": "Schedule a meeting",
            "provider": "deepseek"
        })
        assert response.status_code == 200
```

### Pattern 3: Test Database with StaticPool

**What:** In-memory SQLite with StaticPool prevents database locking issues during tests.

**When to use:** Routes that use get_db dependency (AI accounting, workflow templates).

**Example:**
```python
# Source: Phase 178 pattern (test_admin_system_health_routes.py)
@pytest.fixture(scope="function")
def test_db():
    """In-memory SQLite with StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(test_db):
    """TestClient with database override."""
    from fastapi import FastAPI
    from api.ai_accounting_routes import router

    app = FastAPI()
    app.include_router(router)

    # Override get_db dependency
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

### Pattern 4: Error Path Testing with HTTP Status Codes

**What:** Test all error paths (400, 401, 403, 404, 422, 500) with invalid inputs, unauthorized access, and service failures.

**When to use:** ALL route files (API-03 requirement).

**Example:**
```python
# Source: Phase 177 pattern
class TestAIWorkflowsErrorPaths:
    def test_parse_nlu_empty_text(self, client):
        """Test NLU parse with empty text."""
        response = client.post("/api/ai-workflows/nlu/parse", json={
            "text": "",
            "provider": "deepseek"
        })
        # May return 422 validation error or process with fallback
        assert response.status_code in [200, 422]

    def test_parse_nlu_invalid_provider(self, client):
        """Test NLU parse with invalid provider."""
        with patch('api.ai_workflows_routes.ai_service') as mock_service:
            mock_service.process_with_nlu.side_effect = Exception("Invalid provider")
            response = client.post("/api/ai-workflows/nlu/parse", json={
                "text": "Test",
                "provider": "invalid"
            })
            # Should use fallback or return error
            assert response.status_code in [200, 500]

    def test_complete_text_empty_prompt(self, client):
        """Test completion with empty prompt."""
        response = client.post("/api/ai-workflows/complete", json={
            "prompt": "",
            "provider": "deepseek"
        })
        assert response.status_code == 422
```

### Anti-Patterns to Avoid

- **Single shared FastAPI app**: Causes SQLAlchemy metadata conflicts (Phase 177 blocker)
- **Real database connections**: Slow, fragile, requires external dependencies
- **Real LLM API calls**: Expensive, slow, non-deterministic
- **Testing without error paths**: Fails API-03 requirement (401, 500, constraint violations)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP test client | Custom requests using httpx directly | TestClient from fastapi.testclient | Official FastAPI support, handles async/sync conversion |
| Mock framework | Custom mock classes | unittest.mock.MagicMock, AsyncMock | Handles complex objects, method call verification, context managers |
| Database fixtures | Custom SQLite setup | SQLAlchemy StaticPool pattern | Prevents locking issues, established pattern |
| Route authentication | Custom auth header injection | FastAPI dependency overrides | Clean separation, testable dependencies |

**Key insight:** TestClient, MagicMock, and dependency overrides are production-tested solutions. Custom implementations add complexity and maintenance burden.

## Common Pitfalls

### Pitfall 1: SQLAlchemy Metadata Conflicts

**What goes wrong:** Multiple tests using different Base metadata cause "Table already exists" errors.

**Why it happens:** SQLAlchemy's metadata is global. Using shared app mixes metadata from different route files.

**How to avoid:** Create per-file FastAPI apps (Pattern 1). Each test file has isolated app and router.

**Warning signs:** "Table already exists", "metadata bound to multiple engines", "Table X is already defined for this MetaData instance"

### Pitfall 2: Async Mocking Without AsyncMock

**What goes wrong:** Tests hang or fail when mocking async functions with regular MagicMock.

**Why it happens:** Async functions return coroutines, not values. MagicMock doesn't await them.

**How to avoid:** Always use AsyncMock for async service methods.

**Example:**
```python
# WRONG - causes test to hang
mock.service.process_with_nlu = MagicMock(return_value={'intent': 'test'})

# CORRECT - works with async
from unittest.mock import AsyncMock
mock.service.process_with_nlu = AsyncMock(return_value={'intent': 'test'})
```

**Warning signs:** Test timeout, "coroutine was never awaited", RuntimeWarning about coroutine

### Pitfall 3: Forgetting to Clear Dependency Overrides

**What goes wrong:** Subsequent tests use wrong database or authentication context.

**Why it happens:** FastAPI dependency_overrides persist across tests.

**How to avoid:** Always clear overrides in fixture teardown.

**Example:**
```python
@pytest.fixture
def client(test_db):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()  # CRITICAL: cleanup
```

**Warning signs:** Tests pass individually but fail in suite, wrong user context, database state bleeding

### Pitfall 4: Missing Error Path Coverage

**What goes wrong:** Coverage target achieved but API-03 requirement not met.

**Why it happens:** Focusing only on happy paths. API-03 requires testing 401, 500, constraint violations.

**How to avoid:** Create dedicated test classes for error paths (Pattern 4).

**Warning signs:** High line coverage but no 401/500 tests, all tests use valid inputs

### Pitfall 5: Real External Service Calls

**What goes wrong:** Tests fail when external services unavailable, slow execution, non-deterministic results.

**Why it happens:** Forgetting to mock external dependencies (LLM APIs, Docker, Redis).

**How to avoid:** Mock ALL external services. Use deterministic return values.

**Warning signs:** Tests require API keys, intermittent failures, slow execution (>1s per test)

## Code Examples

Verified patterns from existing Atom test files:

### Test Class Structure (Phase 178 Pattern)

```python
# Source: backend/tests/api/test_admin_system_health_routes.py
class TestAdminHealthSuccess:
    """Happy path tests for admin health endpoint."""

    def test_get_system_health_all_operational(self, client, mock_services):
        """Test system health with all services operational."""
        response = client.get("/api/admin/health")
        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "operational"

class TestAdminHealthErrorPaths:
    """Error path tests for admin health endpoint."""

    def test_get_system_health_database_timeout(self, client, mock_db):
        """Test system health when database times out."""
        mock_db.execute.side_effect = TimeoutError("Database timeout")
        response = client.get("/api/admin/health")
        assert response.status_code == 200  # Health checks still return 200
        data = response.json()
        assert data["services"]["database"]["status"] == "timeout"
```

### Mocking Service Dependencies (Phase 177 Pattern)

```python
# Source: backend/tests/api/test_agent_control_routes_fixed.py
@pytest.fixture
def mock_daemon_manager():
    """Mock DaemonManager for agent control routes."""
    mock = MagicMock()
    mock.is_running.return_value = False
    mock.start_daemon.return_value = 12345
    mock.stop_daemon.return_value = None
    return mock

def test_start_success(client, mock_daemon_manager):
    """Test successful daemon start."""
    with patch('api.agent_control_routes.DaemonManager', return_value=mock_daemon_manager):
        response = client.post("/api/agent/start")
        assert response.status_code == 200
        assert response.json()["pid"] == 12345
```

### Database Override Pattern (Phase 178 Pattern)

```python
# Source: backend/tests/api/test_admin_system_health_routes.py
@pytest.fixture(scope="function")
def test_db():
    """In-memory SQLite database with StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(test_db):
    """TestClient with database dependency override."""
    from fastapi import FastAPI
    from api.ai_accounting_routes import router
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

### Authentication Testing Pattern (Phase 178 Pattern)

```python
# Source: backend/tests/api/test_admin_skill_routes.py
@pytest.fixture
def super_admin_user(test_db):
    """Create super admin user in test database."""
    user = User(
        id="admin_123",
        email="admin@test.com",
        role="super_admin",
        status="active"
    )
    test_db.add(user)
    test_db.commit()
    return user

@pytest.fixture
def authenticated_admin_client(super_admin_user):
    """TestClient with super admin authentication."""
    from fastapi import FastAPI
    from api.workflow_template_routes import router
    from core.api_governance import get_current_user

    app = FastAPI()
    app.include_router(router)

    async def override_get_current_user():
        return super_admin_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_create_template_requires_auth(client):
    """Test template creation requires authentication."""
    response = client.post("/api/workflow-templates/", json={
        "name": "Test Template",
        "description": "Test"
    })
    assert response.status_code == 401
```

### Parametrized Testing (Phase 177 Pattern)

```python
# Source: backend/tests/api/test_agent_control_routes_fixed.py
@pytest.mark.parametrize("port,expected_status", [
    (1, 200),        # Minimum valid port
    (65535, 200),    # Maximum valid port
    (0, 422),        # Invalid port (zero)
    (70000, 422),    # Invalid port (too high)
    (-1, 422),       # Invalid port (negative)
])
def test_start_port_validation(client, port, expected_status):
    """Test port validation with boundary values."""
    response = client.post("/api/agent/start", json={"port": port})
    assert response.status_code == expected_status
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Shared FastAPI app for all tests | Per-file FastAPI apps | Phase 177 (Feb 2026) | Eliminated SQLAlchemy metadata conflicts |
| Real database fixtures | In-memory SQLite with StaticPool | Phase 177 (Feb 2026) | Faster tests, no external dependencies |
| Manual request construction | TestClient from fastapi.testclient | Phase 167 (Jan 2026) | Official FastAPI support, cleaner tests |
| Basic success/error tests | Comprehensive error path classes | Phase 178 (Mar 2026) | API-03 compliance (401, 500, constraints) |

**Deprecated/outdated:**
- **Shared app pattern**: Replaced by per-file apps due to SQLAlchemy conflicts
- **Real service calls**: Replaced by mocking for speed and reliability
- **Basic error testing**: Replaced by comprehensive error path classes for API-03

## Open Questions

1. **AI Accounting Routes Database Dependencies**
   - What we know: Routes use get_db dependency and access IntegrationMetric model
   - What's unclear: Whether other models (User, Workspace) are needed
   - Recommendation: Create only required models in test_db fixture (IntegrationMetric, User if needed for auth)

2. **Workflow Template Routes Authentication**
   - What we know: Routes use @require_governance decorator with ActionComplexity
   - What's unclear: Whether authentication is enforced in testing environment
   - Recommendation: Set EMERGENCY_GOVERNANCE_BYPASS=true or mock get_current_user dependency

3. **Auto Install Routes Docker Dependencies**
   - What we know: Routes depend on AutoInstallerService which uses Docker
   - What's unclear: Full scope of Docker operations (_image_exists, image build)
   - Recommendation: Mock AutoInstallerService completely, don't require real Docker

## Sources

### Primary (HIGH confidence)

- **backend/tests/api/test_admin_system_health_routes.py** - Test class structure, database fixtures, authentication patterns (41 tests, Phase 178)
- **backend/tests/api/test_agent_control_routes_fixed.py** - TestClient usage, MagicMock patterns, error path testing (30+ tests, Phase 177)
- **backend/tests/api/test_workflow_template_routes.py** - Existing workflow template tests (baseline coverage)
- **backend/tests/api/test_multi_integration_workflow_routes.py** - Workflow automation test patterns (25-30 tests)
- **backend/tests/api/conftest.py** - API test fixtures (150 lines, TestClient and mock service patterns)

### Secondary (MEDIUM confidence)

- **backend/api/ai_workflows_routes.py** - Target route file (182 lines, 3 endpoints)
- **backend/api/ai_accounting_routes.py** - Target route file (352 lines, 13 endpoints)
- **backend/api/auto_install_routes.py** - Target route file (100 lines, 3 endpoints)
- **backend/api/workflow_analytics_routes.py** - Target route file (30 lines, 3 endpoints)
- **backend/api/workflow_template_routes.py** - Target route file (360 lines, 8 endpoints)
- **backend/core/ai_accounting_engine.py** - AI accounting service (mock target)
- **backend/core/auto_installer_service.py** - Auto installer service (mock target)
- **backend/core/workflow_metrics.py** - Workflow metrics service (mock target)

### Tertiary (LOW confidence)

- **backend/enhanced_ai_workflow_endpoints.py** - AI workflow service (referenced by ai_workflows_routes, 800+ lines)
- **backend/core/workflow_template_system.py** - Template manager (complex service, may need focused mocking)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All packages verified in existing test files
- Architecture: HIGH - Phase 177/178 patterns proven to work, documented in SUMMARY files
- Pitfalls: HIGH - All pitfalls documented in Phase 177/176 SUMMARY files with solutions

**Research date:** March 12, 2026
**Valid until:** April 11, 2026 (30 days - stable testing patterns)

---

**Next Steps:** Planner should create 3-4 plan files (179-01-PLAN.md through 179-04-PLAN.md) following Phase 178 structure, with each plan targeting one route file or logical grouping (e.g., 179-01 for AI workflows, 179-02 for AI accounting, 179-03 for auto install + analytics, 179-04 for workflow templates).

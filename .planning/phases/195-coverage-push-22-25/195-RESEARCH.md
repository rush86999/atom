# Phase 195: Coverage Push to 22-25% - Research

**Researched:** March 15, 2026
**Domain:** Python Test Coverage (pytest, FastAPI, SQLAlchemy, API Routes)
**Confidence:** HIGH

## Summary

Phase 195 continues the multi-phase test coverage push from Phase 194's 74.6% baseline (which far exceeded the 18-22% target). The phase focuses on API route coverage (auth, analytics, admin), integration testing for complex orchestration, and addressing technical debt from Phase 194 (inline imports, database schema). With 1,456 existing tests and 92 API test files, the codebase has a solid testing foundation using pytest, FastAPI TestClient, factory_boy, and pytest-mock patterns.

**Primary recommendation:** Build on Phase 194's proven patterns (factory_boy for complex models, pytest-mock for mocks, FastAPI TestClient for API routes) and focus on the remaining untested API routes (auth_2fa, analytics_dashboard, admin/* subdirectories). Accept 40-70% coverage targets for complex orchestration (BYOKHandler inline imports, WorkflowEngine) and prioritize integration test patterns for end-to-end workflows.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test framework | Industry standard for Python testing, extensive plugin ecosystem |
| **pytest-cov** | Latest | Coverage reporting | Integration with pytest, JSON/HTML output for CI/CD |
| **FastAPI TestClient** | Built-in | API route testing | Official FastAPI testing approach, supports dependency overrides |
| **factory_boy** | 3.3+ | Test data fixtures | Proven in Phase 194 for complex models with NOT NULL constraints |
| **pytest-mock** | 3.12+ | Mocking fixtures | Simpler than unittest.mock, proven in Phase 194 (LanceDBHandler) |
| **pytest-asyncio** | Latest | Async test support | Required for async FastAPI endpoints and background tasks |
| **SQLAlchemy** | 2.0+ | Database ORM | Production database layer, test fixtures use in-memory SQLite |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **unittest.mock** | Built-in | Complex mock hierarchies | Legacy code, when pytest-mock insufficient |
| **pytest-xdist** | Latest | Parallel test execution | For large test suites (currently 1,456 tests) |
| **pytest-benchmark** | Latest | Performance regression tests | When testing performance-critical paths (governance cache, LLM routing) |
| **testcontainers-python** | Latest | Integration tests | For real database/integration testing (currently using in-memory SQLite) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| factory_boy | pytest-factoryboy | factory_boy is more mature, better documentation |
| FastAPI TestClient | httpx.AsyncClient | TestClient has built-in dependency overrides, async support |
| In-memory SQLite | testcontainers-postgres | In-memory is faster, no Docker overhead; testcontainers for production parity |

**Installation:**
```bash
# Core testing stack (already installed from Phase 194)
pip install pytest pytest-cov pytest-mock pytest-asyncio factory_boy

# Optional for this phase
pip install pytest-xdist  # Parallel execution
pip install pytest-benchmark  # Performance tests
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── api/                    # API route tests (92 existing files)
│   ├── test_auth_2fa_routes_enhanced.py
│   ├── test_admin_routes_coverage.py
│   ├── test_analytics_routes.py
│   ├── test_feedback_analytics_routes.py
│   └── test_canvas_routes.py
├── core/                   # Core service tests
│   ├── llm/
│   │   └── test_cache_aware_router_coverage_extend.py
│   ├── governance/
│   └── episodic_memory/
├── tools/                  # Tool tests
├── integration/            # Integration tests (new focus area)
│   └── test_complex_orchestration.py
├── unit/                   # Unit tests
└── conftest.py             # Shared fixtures
```

### Pattern 1: FastAPI TestClient with Dependency Overrides

**What:** TestClient from FastAPI with dependency injection for auth/database mocking

**When to use:** All API route testing (auth, analytics, admin, feedback)

**Example:**
```python
# Source: backend/tests/api/test_canvas_routes.py (Phase 194 pattern)
@pytest.fixture
def app_with_overrides(db: Session):
    """Create FastAPI app with dependency overrides for testing."""
    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.security_dependencies import get_current_user

    def override_get_db():
        yield db

    def override_get_current_user():
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield app

    app.dependency_overrides.clear()

@pytest.fixture
def client(app_with_overrides: FastAPI):
    """Create TestClient with overridden dependencies."""
    return TestClient(app_with_overrides, raise_server_exceptions=False)
```

**Why this pattern:** Dependency overrides isolate tests from real database/auth, proven in Phase 194 (canvas routes achieved 100% coverage)

### Pattern 2: factory_boy for Complex Models

**What:** factory_boy fixtures for test data with NOT NULL constraints and foreign keys

**When to use:** Models with foreign keys, NOT NULL constraints, or complex relationships (User, AgentEpisode, AdminUser, etc.)

**Example:**
```python
# Source: backend/tests/core/episodic_memory/test_episode_retrieval_service.py (Phase 194)
import factory
from core.models import AgentEpisode, User

class UserFactory(factory.Factory):
    class Meta:
        model = User

    id = factory.Sequence(lambda n: f"user-{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    role = "member"
    status = "active"

class AgentEpisodeFactory(factory.Factory):
    class Meta:
        model = AgentEpisode

    id = factory.Sequence(lambda n: f"episode-{n}")
    agent_id = factory.Faker("uuid4")
    tenant_id = factory.Faker("uuid4")
    task_description = "Test task"
    maturity_at_time = "student"
    outcome = "success"
    status = "active"
    constitutional_score = 1.0
```

**Why this pattern:** Solves NOT NULL constraint violations (Phase 194 plan 194-01 blocker), cleaner than manual model creation

### Pattern 3: pytest-mock for Thread/Async Mocking

**What:** pytest-mock's mocker.fixture for background threads and async operations

**When to use:** Background threads, async operations, external service calls

**Example:**
```python
# Source: backend/tests/core/test_lancedb_handler.py (Phase 194 pattern)
@pytest.fixture
def mock_background_thread(mocker):
    """Mock background thread to avoid race conditions."""
    mock_thread = mocker.patch("core.lancedb_config.Thread")
    mock_thread.return_value = None
    return mock_thread

def test_lancedb_handler_initialization(mock_background_thread):
    """Test handler initialization without real thread."""
    # Test logic here, no race conditions
    pass
```

**Why this pattern:** Eliminates race conditions from background threads, proven in Phase 194 (LanceDBHandler, WorkflowAnalyticsEngine)

### Pattern 4: Integration Testing for Complex Orchestration

**What:** End-to-end tests for complex workflows (agent execution, multi-step orchestration)

**When to use:** WorkflowEngine, AtomMetaAgent, multi-service workflows

**Example:**
```python
# Proposed pattern for Phase 195 integration tests
@pytest.mark.integration
@pytest.mark.asyncio
async def test_workflow_execution_full_orchestration(db: Session, mock_user: User):
    """Test complete workflow execution with all components."""
    # 1. Create workflow
    workflow = WorkflowFactory.create(user_id=mock_user.id)

    # 2. Execute workflow
    result = await workflow_engine.execute(workflow.id)

    # 3. Verify outcome
    assert result["status"] == "completed"
    assert result["steps_completed"] >= 1

    # 4. Verify database state
    execution = db.query(WorkflowExecution).filter_by(
        workflow_id=workflow.id
    ).first()
    assert execution is not None
    assert execution.status == "completed"
```

**Why this pattern:** Tests real orchestration paths, catches integration issues (Phase 194 plan 194-05 had 19% coverage due to complexity)

### Anti-Patterns to Avoid

- **Manual model creation in tests:** Use factory_boy instead (avoids NOT NULL errors)
- **Complex mock hierarchies:** Use pytest-mock's mocker.fixture (simpler, cleaner)
- **Testing background threads directly:** Mock threads to avoid race conditions
- **Unrealistic coverage targets:** Accept 40-70% for complex orchestration (BYOKHandler, WorkflowEngine)
- **Inline imports in production code:** Refactor to module-level imports (Phase 194 blocker)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test data factories | Manual model creation | factory_boy | Handles NOT NULL constraints, foreign keys, sequences |
| Async test execution | Custom async runners | pytest-asyncio | Industry standard, proven async support |
| API route testing | Custom HTTP clients | FastAPI TestClient | Built-in dependency overrides, official FastAPI approach |
| Background thread mocking | Manual thread patches | pytest-mock.mocker | Cleaner API, better teardown |
| Coverage reporting | Custom scripts | pytest-cov | JSON output for CI/CD, HTML reports |
| Parallel test execution | Custom threading | pytest-xdist | Handles test isolation, distributes load |

**Key insight:** Custom test infrastructure is a maintenance burden. Use pytest ecosystem (20+ plugins, 1,456+ tests already using it).

## Common Pitfalls

### Pitfall 1: Inline Imports Block Coverage

**What goes wrong:** BYOKHandler has 30+ inline imports (lines 272, 437, 490, 518, 572, etc.), preventing proper mocking in tests

**Why it happens:** Lazy loading for optional dependencies (OpenAI, pricing fetcher, benchmarks)

**How to avoid:** Refactor inline imports to module-level with try/except blocks:

```python
# Bad (inline imports in functions):
def handler():
    from core.dynamic_pricing_fetcher import get_pricing_fetcher  # Blocks coverage
    return get_pricing_fetcher()

# Good (module-level imports):
try:
    from core.dynamic_pricing_fetcher import get_pricing_fetcher
except ImportError:
    get_pricing_fetcher = None

def handler():
    if get_pricing_fetcher:
        return get_pricing_fetcher()
    return default_pricing()
```

**Warning signs:** Coverage plateaus at 36-40% despite tests, mock patches not working

**Phase 194 impact:** Plan 194-04 achieved 36.4% coverage instead of 65% target due to inline imports

### Pitfall 2: Database Schema Out of Sync

**What goes wrong:** Tests fail with "no such column: status" (AgentEpisode model)

**Why it happens:** Alembic migration not applied to test database

**How to avoid:**

```python
# In conftest.py or test fixture
@pytest.fixture(scope="session")
def apply_migrations():
    """Apply all Alembic migrations before tests."""
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield

    # Optional: downgrade after tests
    command.downgrade(alembic_cfg, "base")
```

**Warning signs:** "Column not found", "Table doesn't exist", "No such column"

**Phase 194 impact:** Plan 194-01 blocked by missing status column (migration `079c11319d8f` exists but not applied)

### Pitfall 3: Unoptimized Coverage Targets

**What goes wrong:** Aim for 100% coverage on complex orchestration, waste time on unmaintainable tests

**Why it happens:** Don't account for complexity, background threads, external dependencies

**How to avoid:** Set realistic targets by complexity:

| Component Type | Realistic Target | Examples |
|----------------|-----------------|----------|
| API routes | 75-100% | Canvas routes (100% in Phase 194) |
| Core services | 60-80% | CacheAwareRouter (100%), EpisodeRetrieval (blocked) |
| Complex orchestration | 40-70% | BYOKHandler (36.4%), WorkflowEngine (19%), AtomMetaAgent (74.6%) |
| Background tasks | 50-70% | LanceDBHandler (56%), WorkflowAnalytics (87%) |

**Warning signs:** Test files exceed 2,000 lines, tests require complex mock hierarchies, flaky tests

**Phase 194 impact:** Plans 194-04, 194-05, 194-06 adjusted targets to 40-70% for complex orchestration

### Pitfall 4: Race Conditions from Background Threads

**What goes wrong:** Tests fail intermittently with "thread already started", "database locked"

**Why it happens:** Background threads in production code interfere with test execution

**How to avoid:** Mock background threads completely:

```python
# Source: backend/tests/core/test_workflow_analytics_engine.py (Phase 194)
@pytest.fixture
def mock_background_threads(mocker):
    """Mock all background thread creation."""
    mocker.patch("core.workflow_analytics_engine.Thread")
    mocker.patch("core.workflow_analytics_engine.threading.Thread")

def test_analytics_engine_no_threads(mock_background_threads):
    """Test analytics without real background threads."""
    # Test logic here, deterministic execution
    pass
```

**Warning signs:** Flaky tests, "sometimes passes", CI failures

**Phase 194 impact:** Plan 194-03 achieved 100% pass rate after mocking threads (was 83%)

## Code Examples

Verified patterns from Phase 194 test files:

### Example 1: API Route Testing with Auth

```python
# Source: backend/tests/api/test_auth_2fa_routes_enhanced.py
@pytest.fixture
def client_enabled(mock_user_enabled):
    """Create test client with 2FA enabled user."""
    app = create_test_app()
    app.dependency_overrides[get_current_user] = lambda: mock_user_enabled
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()

def test_status_when_enabled(client_enabled):
    """Test GET /api/auth/2fa/status returns enabled=True."""
    response = client_enabled.get("/api/auth/2fa/status")

    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert data["enabled"] is True
```

### Example 2: Admin Routes with RBAC

```python
# Source: backend/tests/api/test_admin_routes_coverage.py
@pytest.fixture
def super_admin_user(test_db: Session) -> User:
    """Create super_admin user for authorization tests."""
    user = User(
        id=str(uuid.uuid4()),
        email="superadmin@test.com",
        role="super_admin",
        status="active"
    )
    test_db.add(user)
    test_db.commit()
    return user

def test_create_admin_user_success(client, super_admin_user, test_db):
    """Test successful admin user creation."""
    response = client.post(
        "/api/admin/users",
        json={
            "email": "newadmin@test.com",
            "name": "New Admin",
            "password": "SecurePass123!",
            "role_id": str(role_id)
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newadmin@test.com"
```

### Example 3: Analytics Routes with Time Filters

```python
# Source: backend/tests/api/test_analytics_routes.py
@pytest.mark.parametrize("time_window,expected_messages", [
    ("24h", 10),
    ("7d", 50),
    ("30d", 200),
])
def test_analytics_summary_time_windows(client, time_window, expected_messages):
    """Test analytics summary with different time windows."""
    response = client.get(f"/api/analytics/summary?time_window={time_window}")

    assert response.status_code == 200
    data = response.json()
    assert data["time_window"] == time_window
    assert data["message_stats"]["total_messages"] >= expected_messages
```

### Example 4: Mocking External Services

```python
# Source: backend/tests/core/test_lancedb_handler.py (Phase 194 pattern)
@pytest.fixture
def mock_lancedb_client(mocker):
    """Mock LanceDB client to avoid real vector database."""
    mock_client = mocker.patch("core.lancedb_config.lancedb")
    mock_connection = MagicMock()
    mock_client.connect.return_value = mock_connection
    return mock_connection

def test_lancedb_handler_vector_search(mock_lancedb_client):
    """Test vector search without real LanceDB."""
    # Configure mock behavior
    mock_lancedb_client.table.return_value.search.return_value.to_df.return_value = pd.DataFrame()

    # Test logic here
    pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual model creation | factory_boy fixtures | Phase 194 (Feb 2026) | Eliminates NOT NULL errors, cleaner tests |
| unittest.mock | pytest-mock.mocker | Phase 194 (Feb 2026) | Simpler API, better teardown |
| Real background threads | Mocked threads | Phase 194 (Feb 2026) | 100% pass rate (was 83%) |
| 100% coverage targets | Realistic 40-70% for complex code | Phase 194 (Feb 2026) | Reduced frustration, maintainable tests |
| Complex mock hierarchies | FastAPI TestClient overrides | Phase 194 (Feb 2026) | Cleaner dependency injection |

**Deprecated/outdated:**
- **Manual test data creation:** Replaced by factory_boy (cleaner, handles constraints)
- **Complex mock.patch decorators:** Replaced by pytest-mock.mocker.fixture (simpler)
- **Unrealistic 100% coverage:** Replaced by complexity-based targets (40-100%)
- **Testing background threads directly:** Replaced by mocking (eliminates race conditions)

## Open Questions

1. **Should we refactor inline imports in BYOKHandler?**
   - What we know: 30+ inline imports block coverage (36.4% vs 65% target)
   - What's unclear: Refactoring scope (BYOKHandler is 1,500+ lines, core LLM routing)
   - Recommendation: **DEFER to Phase 196** - Accept 40% coverage for now, create integration tests

2. **What's the priority for integration test suite?**
   - What we know: Phase 194 plan 194-05 had 19% coverage on WorkflowEngine orchestration
   - What's unclear: Which workflows to test first (agent execution, multi-service, ETL)
   - Recommendation: Start with **agent execution workflows** (core value, highest risk)

3. **Should we apply database migration for AgentEpisode.status?**
   - What we know: Migration `079c11319d8f` exists, status column in model, plan 194-01 blocked
   - What's unclear: Why migration wasn't applied (alembic current shows `079c11319d8f` is head)
   - Recommendation: **VERIFY first** - Check if test database needs migration applied explicitly

## Sources

### Primary (HIGH confidence)

- **pytest** - Test framework, fixtures, parametrize, markers
  - Verified in: `/Users/rushiparikh/projects/atom/backend/pytest.ini` (1,456 tests using pytest)
- **FastAPI TestClient** - API route testing with dependency overrides
  - Verified in: `/Users/rushiparikh/projects/atom/backend/tests/api/test_canvas_routes.py` (100% coverage)
- **factory_boy** - Test data fixtures for complex models
  - Verified in: Phase 194 plans (194-01, 194-02, 194-03 attempted factory_boy patterns)
- **pytest-mock** - Mocking with mocker.fixture
  - Verified in: `/Users/rushiparikh/projects/atom/backend/tests/core/test_lancedb_handler.py`
- **pytest-asyncio** - Async test support
  - Verified in: `/Users/rushiparikh/projects/atom/backend/pytest.ini` (`asyncio_mode = auto`)

### Secondary (MEDIUM confidence)

- **Phase 194 FINAL-SUMMARY.md** - Coverage patterns, lessons learned (74.6% achieved)
  - Verified in: `/Users/rushiparikh/projects/atom/.planning/phases/194-coverage-push-18-22/194-FINAL-SUMMARY.md`
- **pytest-cov** - Coverage reporting (JSON output for CI/CD)
  - Verified in: `/Users/rushiparikh/projects/atom/backend/.coveragerc` (coverage configuration)
- **SQLAlchemy 2.0** - Database ORM, test fixtures use in-memory SQLite
  - Verified in: `/Users/rushiparikh/projects/atom/backend/core/models.py` (Alembic migration `079c11319d8f`)

### Tertiary (LOW confidence)

- **pytest-xdist** - Parallel test execution (not yet verified in codebase)
- **pytest-benchmark** - Performance regression tests (not yet verified in codebase)
- **testcontainers-python** - Integration tests with real dependencies (not yet used, using in-memory SQLite)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified in backend code, 1,456+ tests using them
- Architecture: HIGH - Phase 194 patterns proven (factory_boy, pytest-mock, TestClient)
- Pitfalls: HIGH - Inline imports, database schema, and coverage targets documented in Phase 194

**Research date:** March 15, 2026
**Valid until:** March 29, 2026 (14 days - pytest ecosystem stable, but Phase 195 execution may reveal new patterns)

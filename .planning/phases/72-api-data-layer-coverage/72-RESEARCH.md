# Phase 72: API & Data Layer Coverage - Research

**Researched:** 2026-02-22
**Domain:** FastAPI REST/WebSocket Testing + SQLAlchemy ORM + Alembic Migrations
**Confidence:** HIGH

## Summary

Phase 72 requires achieving 80%+ test coverage for Atom's API layer (REST endpoints, WebSocket, authentication) and data layer (SQLAlchemy models, operations, migrations, transactions). The codebase has **136 API route files** (~47,500 lines), **77 Alembic migrations**, and comprehensive existing test infrastructure to build upon.

**Current State Analysis:**
- **API Routes:** 136 route files covering agents, canvas, workflows, authentication, WebSocket, device capabilities, etc.
- **Existing Tests:** Strong foundation with pytest, pytest-asyncio, factory pattern, transaction rollback, WebSocket mocks, and migration E2E tests
- **Database Models:** Large models.py file (2351+ lines) with complex relationships (User, Agent, Episode, Workspace, etc.)
- **Coverage Config:** pytest-cov configured with 80% threshold, branch coverage enabled, HTML/JSON reports

**Primary Recommendation:** Leverage existing test patterns (factory fixtures, transaction rollback, TestClient, AsyncMock) to systematically cover all API routes and database operations. Prioritize critical paths (authentication, agent endpoints, data integrity) over edge cases.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | >=7.0.0 | Test runner | Industry standard for Python testing, rich plugin ecosystem |
| **pytest-asyncio** | >=0.21.0 | Async test support | Required for FastAPI async endpoints and WebSocket |
| **pytest-cov** | latest | Coverage reporting | Integrates with pytest, generates HTML/JSON reports |
| **FastAPI TestClient** | built-in | API endpoint testing | Official FastAPI testing mechanism, async support |
| **SQLAlchemy** | 2.0+ | ORM testing | Core database layer, requires transaction testing |
| **Alembic** | 1.8+ | Migration testing | Database migration management |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **factory_boy** | existing | Test data creation | Already used in codebase (AgentFactory, UserFactory, etc.) |
| **freezegun** | existing | Time mocking | Already used for testing token expiration, timestamps |
| **unittest.mock** | stdlib | Mocking dependencies | AsyncMock for WebSocket, MagicMock for services |
| **Hypothesis** | existing | Property-based tests | Already configured (max_examples 50-200) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | Less powerful, fewer plugins, no async support out-of-box |
| TestClient | requests | Manual async handling, no dependency injection simulation |
| factory_boy | manual fixtures | More boilerplate, harder to maintain |
| pytest-cov | coverage.py | Manual configuration, no pytest integration |

**Installation:**
```bash
# Already installed in dev dependencies
pip install pytest pytest-asyncio pytest-cov hypothesis freezegun
```

## Architecture Patterns

### Recommended Project Structure
```
backend/tests/
├── api/                          # API endpoint tests (72-01, 72-02)
│   ├── test_rest_routes_coverage.py
│   ├── test_auth_routes.py
│   ├── test_websocket_routes.py
│   └── test_api_error_handling.py
├── database/                     # Database tests (72-03, 72-04, 72-05)
│   ├── test_models_coverage.py
│   ├── test_sqlalchemy_operations.py
│   ├── test_migrations.py
│   └── test_transactions.py
├── fixtures/                     # Shared fixtures
│   ├── api_fixtures.py          # API request/response factories
│   ├── database_fixtures.py     # DB session, migrations
│   └── auth_fixtures.py         # Token generation, users
├── factories/                    # Factory Boy factories
│   ├── agent_factory.py
│   ├── user_factory.py
│   └── episode_factory.py
└── conftest.py                   # Root fixtures, pytest config
```

### Pattern 1: FastAPI Endpoint Testing with TestClient
**What:** Test FastAPI routes using TestClient with dependency injection overrides
**When to use:** All REST API endpoints (GET, POST, PUT, DELETE)
**Example:**
```python
# Source: backend/tests/integration/test_api_integration.py
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

class TestAgentEndpoints:
    def test_list_agents_returns_empty_list(self, client: TestClient):
        """Test listing agents when none exist."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        # Response might be wrapped in success response or be direct list
        if isinstance(data, dict):
            assert "agents" in data or "data" in data or data.get("success") is True
        else:
            assert isinstance(data, list)

    def test_create_agent_requires_authentication(self, client_no_auth: TestClient):
        """Test creating agent requires valid JWT token."""
        response = client_no_auth.post("/api/agents", json={
            "name": "Test Agent",
            "category": "testing"
        })
        # Should return 401 Unauthorized or be redirected
        assert response.status_code in [401, 403, 405, 422]
```

### Pattern 2: WebSocket Testing with AsyncMock
**What:** Mock WebSocket connections for testing real-time features
**When to use:** WebSocket endpoints, real-time updates, agent guidance streaming
**Example:**
```python
# Source: backend/tests/integration/test_websocket_integration.py
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    return ws

@pytest.mark.asyncio(mode="auto")
async def test_websocket_manager_auth_flow(self, db_session):
    """Test WebSocket connection manager authentication flow."""
    from core.websockets import manager

    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.close = AsyncMock()
    mock_ws.send_json = AsyncMock()

    connected_user = await manager.connect(mock_ws, "dev-token")

    assert connected_user is not None
    assert connected_user.id == "dev-user"
    mock_ws.accept.assert_called_once()
```

### Pattern 3: Database Session with Transaction Rollback
**What:** Use transaction rollback for test isolation
**When to use:** All database tests requiring data persistence
**Example:**
```python
# Source: backend/tests/conftest.py
@pytest.fixture(scope="function")
def db_session():
    """Create a database session with transaction rollback."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    # Begin transaction for rollback
    transaction = session.begin()

    yield session

    # Rollback transaction to clean up
    session.close()
    transaction.rollback()

# Usage in tests
def test_agent_creation_defaults(self, db: Session):
    """Test agent creation with default values."""
    agent = AgentFactory(
        _session=db,
        name="test_agent",
        status=AgentStatus.STUDENT.value
    )
    db.flush()

    assert agent.id is not None
    assert agent.name == "test_agent"
```

### Pattern 4: Alembic Migration Testing
**What:** Test forward and rollback migrations with real database
**When to use:** Migration validation, schema changes, data migrations
**Example:**
```python
# Source: backend/tests/e2e/migrations/test_migration_e2e.py
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

@pytest.mark.e2e
@pytest.mark.requires_docker
def test_all_models_have_tables(fresh_database):
    """Verify all SQLAlchemy models have corresponding database tables."""
    # Get all tables from database
    db_inspector = inspect(fresh_database)
    db_tables = set(db_inspector.get_table_names())

    # Get all tables from SQLAlchemy models
    model_tables = set(Base.metadata.tables.keys())

    # Verify all model tables exist in database
    missing_tables = model_tables - db_tables
    assert not missing_tables, f"Missing tables: {missing_tables}"

    # Check core tables
    core_tables = ["agent_registry", "agent_execution", "agent_feedback"]
    for table in core_tables:
        assert table in db_tables, f"Core table '{table}' not found"
```

### Pattern 5: Factory Pattern for Test Data
**What:** Use Factory Boy to create test data with minimal boilerplate
**When to use:** Creating model instances, relationships, test data
**Example:**
```python
# Source: backend/tests/unit/test_models_orm.py
from tests.factories import AgentFactory, UserFactory

def test_agent_execution_relationship(self, db: Session):
    """Test AgentRegistry -> AgentExecution one-to-many relationship."""
    agent = AgentFactory(_session=db)
    execution = AgentExecutionFactory(
        _session=db,
        agent_id=agent.id,
        status="running"
    )

    # Test forward relationship
    loaded_execution = db.query(AgentExecution).filter_by(id=execution.id).first()
    assert loaded_execution.agent.id == agent.id

    # Test backward relationship (backref)
    loaded_agent = db.query(AgentRegistry).filter_by(id=agent.id).first()
    assert len(loaded_agent.executions) == 1
```

### Anti-Patterns to Avoid
- **Hardcoded database URLs:** Use environment variables or test-specific databases
- **Shared state between tests:** Always use transaction rollback, clean up in fixtures
- **Testing without authentication:** Many endpoints require valid JWT tokens
- **Mocking database:** Use real SQLite/PostgreSQL for accurate ORM behavior
- **Ignoring async:** FastAPI endpoints are async, use pytest-asyncio

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| API client | Manual requests with aiohttp | FastAPI TestClient | Async support, dependency injection, official |
| Test data factories | Manual model constructors | Factory Boy | Relationships, clean data, less boilerplate |
| WebSocket mocking | Manual WebSocket protocol | AsyncMock + MagicMock | Simple, reliable, no async complexity |
| Database isolation | Manual cleanup | Transaction rollback | Fast, atomic, no leftover data |
| Coverage reporting | Custom scripts | pytest-cov | HTML reports, branch coverage, CI integration |
| Authentication setup | Manual token generation | Existing auth fixtures | JWT creation, user factories, dev-token bypass |

**Key insight:** The codebase already has excellent test infrastructure. Leverage existing fixtures, factories, and patterns rather than building custom solutions.

## Common Pitfalls

### Pitfall 1: Insufficient Authentication Coverage
**What goes wrong:** Tests skip authentication, resulting in uncovered code paths
**Why it happens:** Setting up JWT tokens is tedious, tests use `client_no_auth` for speed
**How to avoid:**
- Create auth fixtures with valid tokens (user, admin, dev-token)
- Test both authenticated and unauthenticated paths
- Cover all auth decorators: `@require_auth`, `@require_admin`
**Warning signs:** <50% coverage on route handlers, all tests use `client_no_auth`

### Pitfall 2: Missing WebSocket Error Handling
**What goes wrong:** WebSocket tests only cover happy path, errors unhandled
**Why it happens:** WebSocket testing is complex, async errors hard to catch
**How to avoid:**
- Test connection failures, invalid tokens, expired tokens
- Test broadcast errors, empty channels, disconnect handling
- Use `caplog` to verify error logging
**Warning signs:** No tests for `WebSocketDisconnect`, no async error tests

### Pitfall 3: Untested Database Constraints
**What goes wrong:** Foreign keys, unique constraints, NOT NULL constraints violated
**Why it happens:** Tests use valid data, never hit constraint violations
**How to avoid:**
- Test duplicate inserts (unique constraints)
- Test orphaned records (foreign key violations)
- Test NULL violations (NOT NULL constraints)
- Use pytest.raises(IntegrityError)
**Warning signs:** No `IntegrityError` tests, no constraint validation tests

### Pitfall 4: Migration Rollback Untested
**What goes wrong:** Migrations only tested forward, rollback breaks data
**Why it happens:** Rollback testing is manual, requires real database
**How to avoid:**
- Test `alembic downgrade -1` after each migration
- Verify data integrity after downgrade
- Test upgrade again after downgrade (idempotency)
- Use fresh database fixture for migration tests
**Warning signs:** Migration tests only test `upgrade()`, never `downgrade()`

### Pitfall 5: Transaction Rollback Leaks
**What goes wrong:** Tests share data, fail when run in parallel
**Why it happens:** Incorrect session management, missing rollback
**How to avoid:**
- Always use `_session=db` parameter in factories
- Never mix factory objects with manual constructors
- Use `db.flush()` not `db.commit()` in tests
- Verify isolation with pytest-xdist
**Warning signs:** Tests pass individually but fail in suite, random failures

### Pitfall 6: Missing Edge Case Validation
**What goes wrong:** API validation untested, malformed requests accepted
**Why it happens:** Tests use valid data, never test Pydantic validation
**How to avoid:**
- Test missing required fields (422 validation errors)
- Test invalid types (string instead of int)
- Test out-of-range values (negative IDs, empty strings)
- Test SQL injection attempts, XSS payloads
**Warning signs:** All tests use valid data, no 422 error tests

## Code Examples

Verified patterns from codebase:

### API Route Testing with Authentication
```python
# Source: backend/tests/api/test_auth_routes.py
def test_mobile_login_with_valid_credentials(self, client: TestClient, db: Session):
    """Test mobile login with valid email and password."""
    # Create test user
    user = UserFactory(
        _session=db,
        email="mobile@example.com",
        password_hash=get_password_hash("password123")
    )
    db.commit()

    # Login request
    response = client.post("/api/auth/mobile/login", json={
        "email": "mobile@example.com",
        "password": "password123",
        "device_token": "test_device_token",
        "platform": "ios"
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
```

### WebSocket Manager Testing
```python
# Source: backend/tests/integration/test_websocket_integration.py
@pytest.mark.asyncio(mode="auto")
async def test_broadcast_to_channel(self, mock_websocket):
    """Test broadcasting message to a channel."""
    from core.websockets import manager

    # Given: Active channel with connections
    manager.subscribe(mock_websocket, "test_channel")

    # When: Broadcast message
    test_message = {"type": "test", "content": "Hello, WebSocket!"}
    await asyncio.wait_for(
        manager.broadcast("test_channel", test_message),
        timeout=5.0
    )

    # Then: Message should be sent
    mock_websocket.send_json.assert_called_once()
    call_args = mock_websocket.send_json.call_args[0][0]
    assert call_args["type"] == "test"
```

### Database Model Testing
```python
# Source: backend/tests/unit/test_models_orm.py
def test_agent_execution_relationship(self, db: Session):
    """Test AgentRegistry -> AgentExecution one-to-many relationship."""
    agent = AgentFactory(_session=db)
    execution = AgentExecutionFactory(
        _session=db,
        agent_id=agent.id,
        status="running"
    )

    # Test forward relationship
    loaded_execution = db.query(AgentExecution).filter_by(id=execution.id).first()
    assert loaded_execution.agent.id == agent.id

    # Test backward relationship (backref)
    loaded_agent = db.query(AgentRegistry).filter_by(id=agent.id).first()
    assert len(loaded_agent.executions) == 1
```

### Migration Testing
```python
# Source: backend/tests/e2e/migrations/test_migration_e2e.py
@pytest.mark.e2e
def test_all_columns_exist(fresh_database):
    """Verify column definitions match model expectations."""
    inspector = inspect(fresh_database)

    # Test agent_registry table
    agent_columns = {col["name"]: col for col in inspector.get_columns("agent_registry")}

    required_columns = {
        "id": str,
        "name": str,
        "status": str,
        "confidence_score": float,
    }

    for col_name, col_type in required_columns.items():
        assert col_name in agent_columns, f"Column '{col_name}' missing"
        assert agent_columns[col_name]["type"] == col_type
```

### Factory Pattern Usage
```python
# Source: backend/tests/factories/agent_factory.py (inferred)
class AgentFactory(BaseFactory):
    class Meta:
        model = AgentRegistry
        sqlalchemy_session_persistence = "commit"

    id = Sequence(lambda n: f"agent_{n}")
    name = Faker("name")
    status = AgentStatus.STUDENT.value
    confidence_score = 0.5
    user_id = None  # Set via SubFactory or parameter

# Usage
agent = AgentFactory(_session=db, name="Test Agent")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual test data | Factory Boy factories | Phase 1 | Reduced boilerplate, cleaner tests |
| Shared database | Transaction rollback | Phase 1 | Test isolation, faster tests |
| Sync testing only | pytest-asyncio for async | Phase 15 | FastAPI endpoint coverage |
| Coverage optional | 80% threshold enforced | Phase 15 | Quality gate, CI/CD block |
| Manual WebSocket mocks | AsyncMock patterns | Phase 15 | Real-time feature coverage |

**Deprecated/outdated:**
- Manual model constructors: Use factories instead
- Database commit in tests: Use flush + rollback
- Testing without auth: Use auth fixtures
- Skipping WebSocket tests: Use AsyncMock pattern

## Open Questions

1. **API Route File Count (136) vs. Test Capacity**
   - What we know: 136 API route files, ~47,500 lines of code
   - What's unclear: Whether all 136 files need 80% coverage or only critical paths
   - Recommendation: Prioritize critical routes (auth, agents, canvas, WebSocket) over administrative routes (billing, legacy integrations)

2. **Migration Testing Strategy**
   - What we know: 77 Alembic migrations exist, E2E migration tests exist
   - What's unclear: Whether to test all 77 migrations or only recent ones
   - Recommendation: Test all migrations for forward/rollback, use pytest marks to skip slow ones

3. **WebSocket Coverage Requirements**
   - What we know: WebSocket routes minimal (26 lines), real-time features critical
   - What's unclear: Whether 80% coverage applies to WebSocket manager (core/websockets.py)
   - Recommendation: Test WebSocket manager comprehensively (it's core infrastructure), even if route file is small

4. **Property-Based Testing for API Contracts**
   - What we know: Hypothesis configured, property tests exist for governance
   - What's unclear: Whether to add property tests for API validation (DATACOV-04)
   - Recommendation: Add property tests for critical invariants (foreign keys, unique constraints), not all API endpoints

## Sources

### Primary (HIGH confidence)
- **backend/tests/conftest.py** - Pytest configuration, fixtures, patterns
- **backend/tests/integration/test_api_integration.py** - API endpoint testing patterns
- **backend/tests/integration/test_websocket_integration.py** - WebSocket testing patterns
- **backend/tests/unit/test_models_orm.py** - Database model testing patterns
- **backend/tests/e2e/migrations/test_migration_e2e.py** - Migration testing patterns
- **backend/pytest.ini** - Coverage configuration (80% threshold, branch coverage)
- **backend/pyproject.toml** - Dependencies (pytest>=7.0.0, pytest-asyncio>=0.21.0)

### Secondary (MEDIUM confidence)
- **backend/api/*.py** (136 files) - API route implementations to test
- **backend/core/models.py** (2351 lines) - Database models to test
- **backend/alembic/versions/*.py** (77 files) - Migrations to test
- **backend/core/atom_agent_endpoints.py** - Core agent endpoints
- **backend/api/auth_routes.py** - Authentication endpoints
- **backend/api/websocket_routes.py** - WebSocket endpoints

### Tertiary (LOW confidence)
- **.planning/REQUIREMENTS.md** - Phase 72 requirements (APICOV-01 through APICOV-05, DATACOV-01 through DATACOV-05)
- **.planning/ROADMAP.md** - Phase 72 plan breakdown (5 plans)
- **FastAPI documentation** (https://fastapi.tiangolo.com/tutorial/testing/) - TestClient usage
- **SQLAlchemy documentation** (https://docs.sqlalchemy.org/en/20/orm/testing.html) - ORM testing patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified in pyproject.toml and pytest.ini
- Architecture: HIGH - Existing test patterns reviewed (conftest.py, 10+ test files examined)
- Pitfalls: HIGH - Common issues identified in existing tests (session management, auth coverage)

**Research date:** 2026-02-22
**Valid until:** 2026-03-24 (30 days - standard for stable testing frameworks)

**Codebase stats:**
- API route files: 136
- API lines of code: ~47,500
- Alembic migrations: 77
- Database models: 50+ (2351 lines in models.py)
- Existing test files: 350+
- Existing fixtures: 1530+ fixture definitions

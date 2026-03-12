# Phase 180: API Routes Coverage (Advanced Features) - Research

**Researched:** March 12, 2026
**Domain:** FastAPI Route Testing with TestClient
**Confidence:** HIGH

## Summary

Phase 180 requires comprehensive test coverage for advanced feature route files that handle specialized business functions: AP/AR invoice automation, artifact versioning, deep linking, and integration catalog management. These four route files total 871 lines of code with complex business logic and external dependencies:

1. **apar_routes.py** (241 lines) - Accounts Payable/Receivable automation with invoice lifecycle management
2. **artifact_routes.py** (130 lines) - Artifact CRUD with version control and locking
3. **deeplinks.py** (401 lines) - Deep link execution, audit, generation, and statistics
4. **integrations_catalog_routes.py** (99 lines) - Integration catalog with search and filtering

All routes follow the standard FastAPI pattern with Pydantic models, BaseAPIRouter extensions, and dependency injection. The testing approach uses per-file FastAPI apps with isolated TestClient instances to avoid SQLAlchemy metadata conflicts (proven pattern from Phase 177-179).

**Key challenge:** Three of four route files have NO existing tests, requiring greenfield test development. The APAR routes depend on a complex 353-line apar_engine service with reportlab PDF generation. Deep link routes require mocking async deep link execution and audit trail creation.

**Primary recommendation:** Use the Phase 177-179 pattern with 4 test files (600-800 lines each) covering happy paths, error paths, authentication, and edge cases. Target 75%+ line coverage with TestClient-based integration tests using MagicMock/AsyncMock for external services (APAREngine, DeepLinkAudit, database).

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
| unittest.mock | builtin | Mock/AsyncMock/MagicMock | All external service dependencies (APAREngine, DeepLinkAudit, database) |
| pytest fixtures | builtin | Test setup/teardown | Database fixtures, TestClient, mock services |
| sqlalchemy.pool.StaticPool | builtin | In-memory SQLite | Prevents database locking during tests |
| io.BytesIO | builtin | StreamingResponse testing | Testing PDF download endpoints in APAR routes |

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
├── test_apar_routes_coverage.py            # NEW - AP/AR invoice automation
├── test_artifact_routes_coverage.py        # NEW - Artifact version control
├── test_deeplinks_coverage.py              # NEW - Deep link execution & audit
└── test_integrations_catalog_coverage.py   # NEW - Integration catalog
```

### Pattern 1: Per-File FastAPI Apps with TestClient

**What:** Each test file creates isolated FastAPI app including the target router, avoiding SQLAlchemy metadata conflicts.

**When to use:** ALL API route testing (established pattern from Phase 177-179).

**Example:**
```python
# Source: Phase 177/178 pattern
@pytest.fixture(scope="function")
def client():
    """TestClient with isolated FastAPI app."""
    from fastapi import FastAPI
    from api.apar_routes import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)
```

### Pattern 2: Mock External Services with MagicMock

**What:** All external dependencies (database, APAREngine, reportlab) mocked using unittest.mock.

**When to use:** ALL external service calls in route handlers.

**Example:**
```python
# Source: Phase 177 pattern
@pytest.fixture
def mock_apar_engine():
    """Mock APAREngine for invoice operations."""
    mock = MagicMock()
    mock.intake_invoice.return_value = APInvoice(
        id="ap_123",
        vendor="Test Vendor",
        amount=100.0,
        due_date=datetime.now(),
        line_items=[]
    )
    return mock

def test_intake_ap_invoice_success(client, mock_apar_engine):
    """Test AP invoice intake."""
    with patch('api.apar_routes.apar_engine', mock_apar_engine):
        response = client.post("/api/apar/ap/intake", json={
            "vendor": "Test Vendor",
            "amount": 100.0
        })
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == "ap_123"
```

### Pattern 3: Test Database with StaticPool

**What:** In-memory SQLite with StaticPool prevents database locking issues during tests.

**When to use:** Routes that use get_db dependency (artifact_routes, deeplinks audit/stats).

**Example:**
```python
# Source: Phase 178 pattern
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
    from api.artifact_routes import router
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

### Pattern 4: StreamingResponse Testing for PDF Downloads

**What:** Test PDF download endpoints by mocking reportlab and checking response headers.

**When to use:** APAR routes that generate and download invoice PDFs.

**Example:**
```python
def test_download_ar_invoice_success(client, mock_apar_engine):
    """Test AR invoice PDF download."""
    mock_apar_engine.generate_invoice_pdf.return_value = b"%PDF-1.4 fake pdf content"

    with patch('api.apar_routes.apar_engine', mock_apar_engine):
        response = client.get("/api/apar/ar/inv_123/download")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert b"fake pdf content" in response.content
```

### Pattern 5: Deep Link Execution Testing with Async Mocks

**What:** Mock async deep link execution and audit trail creation.

**When to use:** Deeplink routes that execute, audit, and generate deep links.

**Example:**
```python
@pytest.fixture
def mock_deep_link_functions():
    """Mock deep link core functions."""
    execute_mock = AsyncMock(return_value={
        "success": True,
        "agent_id": "agent_123",
        "agent_name": "Test Agent",
        "execution_id": "exec_456"
    })
    return execute_mock

def test_execute_deeplink_success(client, mock_deep_link_functions):
    """Test successful deep link execution."""
    with patch('api.deeplinks.execute_deep_link', mock_deep_link_functions):
        response = client.post("/api/deeplinks/execute", json={
            "deeplink_url": "atom://agent/agent_123?message=Hello",
            "user_id": "user_1"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_id"] == "agent_123"
```

### Anti-Patterns to Avoid

- **Single shared FastAPI app**: Causes SQLAlchemy metadata conflicts (Phase 177 blocker)
- **Real database connections**: Slow, fragile, requires external dependencies
- **Real PDF generation**: Requires reportlab installation, slow execution, non-deterministic output
- **Real deep link execution**: Side effects (agent execution, audit writes), difficult to test
- **Testing without error paths**: Fails API-03 requirement (401, 500, constraint violations)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP test client | Custom requests using httpx directly | TestClient from fastapi.testclient | Official FastAPI support, handles async/sync conversion |
| Mock framework | Custom mock classes | unittest.mock.MagicMock, AsyncMock | Handles complex objects, method call verification, context managers |
| Database fixtures | Custom SQLite setup | SQLAlchemy StaticPool pattern | Prevents locking issues, established pattern |
| PDF testing | Real reportlab PDF generation | Mock bytes return value | Faster, deterministic, no external dependency |
| Async mocking | Custom async wrapper | AsyncMock from unittest.mock | Official support, handles coroutines correctly |

**Key insight:** TestClient, MagicMock/AsyncMock, and dependency overrides are production-tested solutions. Custom implementations add complexity and maintenance burden.

## Common Pitfalls

### Pitfall 1: SQLAlchemy Metadata Conflicts

**What goes wrong:** Multiple tests using different Base metadata cause "Table already exists" errors.

**Why it happens:** SQLAlchemy's metadata is global. Using shared app mixes metadata from different route files.

**How to avoid:** Create per-file FastAPI apps (Pattern 1). Each test file has isolated app and router.

**Warning signs:** "Table already exists", "metadata bound to multiple engines", "Table X is already defined for this MetaData instance"

### Pitfall 2: Forgetting AsyncMock for Async Functions

**What goes wrong:** Tests hang or fail when mocking async functions with regular MagicMock.

**Why it happens:** Async functions return coroutines, not values. MagicMock doesn't await them.

**How to avoid:** Always use AsyncMock for async service methods (execute_deep_link, database operations).

**Example:**
```python
# WRONG - causes test to hang
mock.execute_deep_link = MagicMock(return_value={'success': True})

# CORRECT - works with async
from unittest.mock import AsyncMock
mock.execute_deep_link = AsyncMock(return_value={'success': True})
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

### Pitfall 4: Not Mocking reportlab for PDF Tests

**What goes wrong:** Tests fail if reportlab not installed, slow PDF generation, non-deterministic output.

**Why it happens:** APAR routes use reportlab for PDF generation, which is an external dependency.

**How to avoid:** Mock APAREngine.generate_invoice_pdf to return deterministic bytes.

**Example:**
```python
@pytest.fixture
def mock_apar_engine():
    mock = MagicMock()
    mock.generate_invoice_pdf.return_value = b"%PDF-1.4\n1 0 obj...\n%%EOF"
    return mock
```

**Warning signs:** Tests require reportlab installation, intermittent failures, slow execution (>100ms per PDF test)

### Pitfall 5: Missing Deep Link Feature Flag Tests

**What goes wrong:** Tests don't verify DEEPLINK_ENABLED=false behavior.

**Why it happens:** Deep link routes check feature flag before processing.

**How to avoid:** Test both enabled and disabled states.

**Example:**
```python
def test_execute_deeplink_disabled(client):
    """Test deep link execution when feature disabled."""
    with patch('api.deeplinks.DEEPLINK_ENABLED', False):
        response = client.post("/api/deeplinks/execute", json={
            "deeplink_url": "atom://agent/agent_123",
            "user_id": "user_1"
        })
        assert response.status_code == 503
        assert "disabled" in response.json()["message"].lower()
```

**Warning signs:** All tests pass with DEEPLINK_ENABLED=true, no 503 tests, feature flag logic untested

### Pitfall 6: Not Testing Invoice Status Transitions

**What goes wrong:** Coverage achieved but invoice lifecycle not validated.

**Why it happens:** APAR routes have complex state machines (draft → pending → approved → paid).

**How to avoid:** Test each state transition path.

**Example:**
```python
class TestAPInvoiceLifecycle:
    """Test AP invoice state transitions."""

    def test_intake_to_approved_auto(self, client, mock_engine):
        """Test auto-approval for invoices under threshold."""
        mock_engine.intake_invoice.return_value = APInvoice(
            status=InvoiceStatus.APPROVED,  # Auto-approved
            approved_by="auto"
        )
        response = client.post("/api/apar/ap/intake", json={...})
        assert response.json()["data"]["auto_approved"] is True

    def test_intake_to_pending_manual(self, client, mock_engine):
        """Test manual approval required for large invoices."""
        mock_engine.intake_invoice.return_value = APInvoice(
            status=InvoiceStatus.PENDING_APPROVAL
        )
        response = client.post("/api/apar/ap/intake", json={...})
        assert response.json()["data"]["auto_approved"] is False
```

**Warning signs:** High coverage but no state transition tests, only one status tested per endpoint

### Pitfall 7: Missing Artifact Versioning Tests

**What goes wrong:** Artifact version control logic not tested.

**Why it happens:** Artifact routes create version records on update, which is easy to miss.

**How to avoid:** Test version increment and version history retrieval.

**Example:**
```python
def test_update_artifact_creates_version(client, test_db):
    """Test artifact update creates version record."""
    # Create artifact
    artifact = Artifact(id="art_1", version=1, content="v1")
    test_db.add(artifact)
    test_db.commit()

    # Update artifact
    response = client.post("/api/artifacts/update", json={
        "id": "art_1",
        "content": "v2"
    })
    assert response.status_code == 200
    assert response.json()["version"] == 2

    # Verify version record created
    version = test_db.query(ArtifactVersion).filter(
        ArtifactVersion.artifact_id == "art_1"
    ).first()
    assert version is not None
    assert version.version == 1  # Old version stored
```

**Warning signs:** Artifact update tests don't check ArtifactVersion table, version count never tested

## Code Examples

Verified patterns from existing Atom test files:

### Test Class Structure (Phase 178 Pattern)

```python
# Source: backend/tests/api/test_admin_system_health_routes.py
class TestAPARSuccess:
    """Happy path tests for APAR endpoints."""

    def test_intake_ap_invoice_success(self, client, mock_engine):
        """Test AP invoice intake."""
        response = client.post("/api/apar/ap/intake", json={
            "vendor": "Test Vendor",
            "amount": 100.0,
            "payment_terms": "Net 30"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["vendor"] == "Test Vendor"

class TestAPARErrorPaths:
    """Error path tests for APAR endpoints."""

    def test_intake_invoice_invalid_amount(self, client):
        """Test invoice intake with negative amount."""
        response = client.post("/api/apar/ap/intake", json={
            "vendor": "Test",
            "amount": -100.0
        })
        # May return 422 validation error or process with validation
        assert response.status_code in [200, 422]
```

### Mocking Complex Service Dependencies (Phase 177 Pattern)

```python
# Source: backend/tests/api/test_agent_control_routes_fixed.py
@pytest.fixture
def mock_apar_engine():
    """Mock APAREngine with invoice lifecycle."""
    mock = MagicMock()

    # Configure invoice objects
    mock.intake_invoice.return_value = APInvoice(
        id="ap_123",
        vendor="Test Vendor",
        amount=100.0,
        due_date=datetime.now(),
        status=InvoiceStatus.APPROVED,
        approved_by="auto"
    )

    mock.approve_invoice.return_value = APInvoice(
        id="ap_123",
        vendor="Test Vendor",
        amount=100.0,
        status=InvoiceStatus.APPROVED,
        approved_by="user_1"
    )

    mock.get_pending_approvals.return_value = [
        APInvoice(id="ap_1", vendor="Vendor 1", amount=50.0),
        APInvoice(id="ap_2", vendor="Vendor 2", amount=75.0)
    ]

    return mock

def test_get_pending_approvals(client, mock_apar_engine):
    """Test retrieving pending approvals."""
    with patch('api.apar_routes.apar_engine', mock_apar_engine):
        response = client.get("/api/apar/ap/pending")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["count"] == 2
        assert len(data["data"]["invoices"]) == 2
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
    from api.artifact_routes import router
    from core.database import get_db
    from core.models import User

    app = FastAPI()
    app.include_router(router)

    async def override_get_current_user():
        return User(id="user_1", email="test@example.com")

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()
```

### Authentication Testing Pattern (Phase 178 Pattern)

```python
@pytest.fixture
def authenticated_client(test_db):
    """TestClient with authentication."""
    from fastapi import FastAPI
    from api.artifact_routes import router
    from core.security_dependencies import get_current_user

    # Create test user
    user = User(id="user_1", email="test@example.com")
    test_db.add(user)
    test_db.commit()

    app = FastAPI()
    app.include_router(router)

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_list_artifacts_requires_auth(client):
    """Test artifact list requires authentication."""
    response = client.get("/api/artifacts/")
    assert response.status_code == 401

def test_list_artifacts_with_auth(authenticated_client):
    """Test artifact list with authentication."""
    response = authenticated_client.get("/api/artifacts/")
    assert response.status_code == 200
```

### Deep Link Audit Testing Pattern

```python
@pytest.fixture
def test_db_with_audit_data(test_db):
    """Populate test database with audit entries."""
    audit_entries = [
        DeepLinkAudit(
            id="audit_1",
            user_id="user_1",
            agent_id="agent_1",
            resource_type="agent",
            resource_id="agent_1",
            action="execute",
            deeplink_url="atom://agent/agent_1",
            status="success",
            created_at=datetime.now()
        ),
        DeepLinkAudit(
            id="audit_2",
            user_id="user_1",
            resource_type="workflow",
            resource_id="workflow_1",
            action="trigger",
            deeplink_url="atom://workflow/workflow_1",
            status="failed",
            error_message="Workflow not found",
            created_at=datetime.now() - timedelta(hours=1)
        )
    ]
    for entry in audit_entries:
        test_db.add(entry)
    test_db.commit()
    return test_db

def test_get_deeplink_audit_filtered(client, test_db_with_audit_data):
    """Test audit log with filters."""
    response = client.get("/api/deeplinks/audit?resource_type=agent")
    assert response.status_code == 200
    audits = response.json()
    assert len(audits) == 1
    assert audits[0]["resource_type"] == "agent"

def test_get_deeplink_stats_aggregation(client, test_db_with_audit_data):
    """Test statistics aggregation."""
    response = client.get("/api/deeplinks/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_executions"] == 2
    assert stats["successful_executions"] == 1
    assert stats["failed_executions"] == 1
    assert stats["by_resource_type"]["agent"] == 1
    assert stats["by_resource_type"]["workflow"] == 1
```

### Integration Catalog Search Testing

```python
def test_get_integrations_catalog_with_search(client, test_db):
    """Test catalog search functionality."""
    # Add test integrations
    integrations = [
        IntegrationCatalog(
            id="slack_1",
            name="Slack",
            description="Team messaging",
            category="communication"
        ),
        IntegrationCatalog(
            id="gmail_1",
            name="Gmail",
            description="Email service",
            category="email"
        )
    ]
    for integration in integrations:
        test_db.add(integration)
    test_db.commit()

    # Search by name
    response = client.get("/api/v1/integrations/catalog?search=slack")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["name"] == "Slack"

    # Search by description
    response = client.get("/api/v1/integrations/catalog?search=email")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["name"] == "Gmail"
```

### Parametrized Testing (Phase 177 Pattern)

```python
@pytest.mark.parametrize("endpoint,method", [
    ("/api/apar/ap/intake", "post"),
    ("/api/apar/ar/generate", "post"),
    ("/api/apar/ap/pending", "get"),
])
def test_deeplink_disabled_blocks_endpoints(client, endpoint, method):
    """Test that deeplink-disabled state blocks relevant endpoints."""
    with patch('api.deeplinks.DEEPLINK_ENABLED', False):
        if method == "post":
            response = client.post(endpoint, json={})
        else:
            response = client.get(endpoint)
        # Most endpoints should work, deeplink-specific ones return 503
        assert response.status_code in [200, 503, 422]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Shared FastAPI app for all tests | Per-file FastAPI apps | Phase 177 (Feb 2026) | Eliminated SQLAlchemy metadata conflicts |
| Real database fixtures | In-memory SQLite with StaticPool | Phase 177 (Feb 2026) | Faster tests, no external dependencies |
| Manual request construction | TestClient from fastapi.testclient | Phase 167 (Jan 2026) | Official FastAPI support, cleaner tests |
| Basic success/error tests | Comprehensive error path classes | Phase 178 (Mar 2026) | API-03 compliance (401, 500, constraints) |
| Real PDF generation | Mocked PDF bytes | Phase 180 (Mar 2026) | Faster tests, no reportlab dependency |

**Deprecated/outdated:**
- **Shared app pattern**: Replaced by per-file apps due to SQLAlchemy conflicts
- **Real service calls**: Replaced by mocking for speed and reliability
- **Basic error testing**: Replaced by comprehensive error path classes for API-03
- **Real reportlab PDF generation**: Replaced by mocked bytes for determinism

## Open Questions

1. **APAR Engine Scope for Mocking**
   - What we know: APAREngine has 13 methods (intake_invoice, approve_invoice, get_pending_approvals, etc.)
   - What's unclear: Full scope of invoice status transitions and edge cases (overdue, reminders, PDF generation)
   - Recommendation: Mock APAREngine completely, create focused test data for each invoice state, don't require real reportlab

2. **Deep Link Audit Data Volume**
   - What we know: Deep link stats require aggregation queries (counts, grouping, time-based filtering)
   - What's unclear: Performance implications of large audit tables in tests
   - Recommendation: Use small test datasets (5-10 entries), focus on aggregation logic correctness, not performance

3. **Integration Catalog Search Performance**
   - What we know: Catalog routes use ilike for case-insensitive search on name and description
   - What's unclear: Whether full-text search is needed for large catalogs
   - Recommendation: Test basic ilike search only, full-text search is out of scope for route testing

4. **Artifact Versioning Rollback**
   - What we know: Artifact routes create version records on update, but don't expose rollback endpoint
   - What's unclear: Whether rollback should be tested as a potential future feature
   - Recommendation: Don't test rollback (endpoint doesn't exist), focus on version history retrieval

## Sources

### Primary (HIGH confidence)

- **backend/tests/api/test_admin_system_health_routes.py** - Test class structure, database fixtures, authentication patterns (41 tests, Phase 178)
- **backend/tests/api/test_agent_control_routes_fixed.py** - TestClient usage, MagicMock patterns, error path testing (30+ tests, Phase 177)
- **backend/tests/api/test_integration_dashboard_routes.py** - Integration dashboard test patterns (existing tests, 700+ lines)
- **backend/tests/api/conftest.py** - API test fixtures (150 lines, TestClient and mock service patterns)
- **backend/api/apar_routes.py** - Target route file (241 lines, 14 endpoints)
- **backend/api/artifact_routes.py** - Target route file (130 lines, 5 endpoints)
- **backend/api/deeplinks.py** - Target route file (401 lines, 4 endpoints)
- **backend/api/integrations_catalog_routes.py** - Target route file (99 lines, 2 endpoints)
- **backend/core/apar_engine.py** - AP/AR engine service (353 lines, mock target)
- **backend/core/deeplinks.py** - Deep link execution service (616 lines, mock target)

### Secondary (MEDIUM confidence)

- **backend/core/models.py** - Database models for Artifact, ArtifactVersion, DeepLinkAudit, IntegrationCatalog
- **backend/core/integration_dashboard.py** - Integration dashboard service (existing mock patterns)
- **backend/core/connection_service.py** - Connection management service (for integration catalog context)

### Tertiary (LOW confidence)

- **backend/api/connection_routes.py** - Connection management routes (96 lines, governance patterns)
- **backend/api/integration_dashboard_routes.py** - Integration dashboard routes (508 lines, tested separately)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All packages verified in existing test files
- Architecture: HIGH - Phase 177-179 patterns proven to work, documented in SUMMARY files
- Pitfalls: HIGH - All pitfalls documented in Phase 177-179 SUMMARY files with solutions
- APAR domain knowledge: MEDIUM - Invoice lifecycle understood, but reportlab edge cases unclear
- Deep link domain knowledge: MEDIUM - URL parsing understood, but async execution edge cases unclear

**Research date:** March 12, 2026
**Valid until:** April 11, 2026 (30 days - stable testing patterns)

---

**Next Steps:** Planner should create 4 plan files (180-01-PLAN.md through 180-04-PLAN.md) following Phase 178 structure:
- 180-01: APAR routes coverage (test_apar_routes_coverage.py, ~600 lines)
- 180-02: Artifact routes coverage (test_artifact_routes_coverage.py, ~500 lines)
- 180-03: Deep links coverage (test_deeplinks_coverage.py, ~700 lines)
- 180-04: Integration catalog coverage (test_integrations_catalog_coverage.py, ~400 lines)

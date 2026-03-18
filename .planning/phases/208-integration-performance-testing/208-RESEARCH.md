# Phase 208: Integration & Performance Testing - Research

**Researched:** March 18, 2026
**Domain:** Integration testing, API contract testing, performance benchmarking
**Confidence:** HIGH

## Summary

Phase 208 complements Phase 207's 87.4% unit coverage achievement by adding integration tests, performance benchmarks, and API contract testing for complex orchestration modules that are poorly suited to unit testing. The phase focuses on workflow_engine (10% unit coverage), episode_segmentation (15% unit coverage), and other large modules where unit tests have diminishing returns.

**Primary Recommendation:** Use pytest-based integration testing with realistic fixtures, pytest-benchmark for performance tracking, and Schemathesis for API contract validation. Build on existing patterns from Phase 184 (advanced integration tests) and established performance test infrastructure.

**Key Insight from Phase 207:** Small modules (<500 lines) achieve 75%+ coverage efficiently with unit tests, while large complex modules (>1000 lines) struggle to reach 30% unit coverage due to async orchestration, external dependencies, and complex state management. Integration testing is the appropriate tool for these large modules.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.0+ | Test runner and fixtures | Already in use, excellent async support, rich plugin ecosystem |
| **pytest-asyncio** | 0.21+ | Async test execution | Required for workflow/episode integration tests (async orchestration) |
| **pytest-benchmark** | 4.0+ | Performance benchmarking | Historical performance tracking, statistical analysis, already installed |
| **Schemathesis** | 3.0+ | API contract testing | Property-based testing for OpenAPI specs, integrates with pytest |
| **httpx** | 0.24+ | Async HTTP client | Already in use, supports both sync/async, better than requests for testing |
| **factory_boy** | 3.3+ | Test data factories | Realistic test data, already used in E2E tests |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **locust** | 2.0+ | Load testing | Load testing for high-traffic endpoints (optional, can defer) |
| **responses** | 0.23+ | HTTP mocking | Mock external API responses (already in use from Phase 170) |
| **pytest-json-report** | 1.5+ | JSON test reports | CI/CD integration (already in use) |
| **pytest-rerunfailures** | 14.0+ | Flaky test detection | Retry failed tests (already configured in pytest.ini) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|----------|----------|
| **Schemathesis** | schemathesis-old | Old API deprecated, use 3.0+ for Hypothesis integration |
| **pytest-benchmark** | custom timing | pytest-benchmark provides historical tracking, statistical analysis |
| **httpx** | requests | httpx supports async, matches production code |
| **factory_boy** | Faker | factory_boy creates valid model instances, Faker generates random data |

**Installation:**
```bash
# Already installed in requirements-testing.txt
pip install pytest>=7.0 pytest-asyncio>=0.21 pytest-benchmark>=4.0

# Add for Phase 208 (if not already present)
pip install schemathesis>=3.0 factory_boy>=3.3
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── integration/              # Integration tests (already exists, 80+ files)
│   ├── workflows/           # NEW: Workflow orchestration tests
│   │   ├── conftest.py      # Shared fixtures for workflow tests
│   │   ├── test_workflow_engine_e2e.py
│   │   ├── test_episode_segmentation_e2e.py
│   │   └── test_multi_agent_workflows.py
│   ├── contracts/           # NEW: API contract tests
│   │   ├── conftest.py      # Schemathesis configuration
│   │   ├── test_agent_api_contracts.py
│   │   ├── test_workflow_api_contracts.py
│   │   └── test_canvas_api_contracts.py
│   └── performance/         # NEW: Performance benchmark tests
│       ├── conftest.py      # Benchmark fixtures
│       ├── test_workflow_performance.py
│       ├── test_episode_performance.py
│       └── test_api_latency.py
│
├── fixtures/                # Shared test fixtures (already exists)
│   ├── workflow_fixtures.py # Already exists in e2e/fixtures/
│   └── database_fixtures.py # Already exists
│
└── scripts/                 # Test utilities
    ├── run_integration_tests.sh
    ├── generate_benchmark_report.py
    └── verify_contracts.py
```

### Pattern 1: Integration Testing with Realistic Fixtures

**What:** Test multi-service interactions with real database and mocked external services.

**When to use:** Testing complex orchestration (workflow_engine, episode_segmentation) where unit tests struggle.

**Example:**
```python
# Source: backend/tests/integration/test_workflow_engine_integration.py (existing pattern)
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session
from core.workflow_engine import WorkflowEngine

@pytest.mark.asyncio
async def test_execute_simple_workflow_with_mocks(self, db_session: Session):
    """Test actual workflow execution with mocked dependencies."""
    # Mock state manager
    mock_state_manager = AsyncMock()
    mock_state_manager.create_execution = AsyncMock(return_value="exec_123")

    # Mock WebSocket manager
    mock_ws_manager = MagicMock()
    mock_ws_manager.notify_workflow_status = AsyncMock()

    # Create engine with mocked dependencies
    engine = WorkflowEngine(max_concurrent_steps=2)
    engine.state_manager = mock_state_manager

    # Create actual workflow definition
    workflow_def = {
        "id": "test_workflow",
        "nodes": [{"id": "step1", "type": "action"}],
        "connections": []
    }

    # Execute workflow
    result = await engine._execute_workflow_graph(
        execution_id="exec_123",
        workflow=workflow_def,
        state={"steps": {}, "outputs": {}},
        ws_manager=mock_ws_manager,
        user_id="test_user"
    )

    # Verify state manager was called
    mock_state_manager.create_execution.assert_called_once()
```

**Key Benefits:**
- Tests actual orchestration logic (not just state transitions)
- Uses real database for persistence testing
- Mocks only external services (WebSocket, LLM providers)
- Validates integration points between services

### Pattern 2: API Contract Testing with Schemathesis

**What:** Property-based testing for OpenAPI specification validation.

**When to use:** Validating API contracts, detecting breaking changes, ensuring request/response schemas match.

**Example:**
```python
# Source: backend/docs/API_CONTRACT_TESTING.md (existing infrastructure)
import pytest
from hypothesis import settings

# Load schema from FastAPI app
schema = schemathesis.from_wsgi("/openapi.json", app)

class TestAgentAPIContracts:
    @schema.parametrize(endpoint="/api/v1/agents/{agent_id}")
    @settings(max_examples=20, deadline=None)
    def test_get_agent_contracts(self, case):
        response = case.call_and_validate()
        # Schemathesis validates:
        # - Response status code matches spec
        # - Response body matches schema
        # - Required headers present

    @schema.parametrize(endpoint="/api/v1/agents")
    def test_create_agent_contracts(self, case):
        response = case.call_and_validate()
        assert response.status_code in [200, 201, 400, 422]
```

**Key Benefits:**
- Automatic test case generation (Hypothesis)
- Validates OpenAPI spec matches implementation
- Detects breaking changes before deployment
- Tests edge cases humans wouldn't think of

### Pattern 3: Performance Benchmarking with pytest-benchmark

**What:** Micro-benchmarking for critical paths with historical tracking.

**When to use:** Validating performance targets (<100ms P50, <500ms P99), detecting performance regressions.

**Example:**
```python
# Source: backend/tests/test_performance_benchmarks.py (existing pattern)
import pytest
from core.workflow_engine import WorkflowEngine

class TestWorkflowPerformance:
    @pytest.mark.benchmark(group="workflow-execution")
    def test_simple_workflow_execution(self, benchmark):
        """Test workflow execution < 100ms P50 target."""
        engine = WorkflowEngine(max_concurrent_steps=2)

        def execute_workflow():
            workflow_def = {
                "id": "test_workflow",
                "nodes": [{"id": "step1", "type": "action"}],
                "connections": []
            }
            # Execute workflow (simplified for benchmark)
            return engine._validate_workflow_schema(workflow_def)

        result = benchmark(execute_workflow)

        # Verify target (pytest-benchmark tracks historical data)
        assert result is not None
        # Historical comparison available in benchmark output
```

**Key Benefits:**
- Historical performance tracking (auto-saves benchmarks)
- Statistical analysis (min, max, mean, median, P50, P99)
- Regression detection (compare to previous runs)
- No manual timing code required

### Pattern 4: Load Testing with Locust (Optional)

**What:** Simulate concurrent users for high-traffic endpoints.

**When to use:** Validating system capacity, identifying bottlenecks, testing scalability.

**Example:**
```python
# Source: Existing locust infrastructure (if any, otherwise NEW)
from locust import HttpUser, task, between

class AtomAPIUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Login before running tasks."""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password"
        })
        self.token = response.json()["token"]

    @task(3)
    def get_agents(self):
        """List agents (3x more frequent than other endpoints)."""
        self.client.get("/api/v1/agents", headers={
            "Authorization": f"Bearer {self.token}"
        })

    @task(1)
    def create_agent(self):
        """Create new agent (less frequent)."""
        self.client.post("/api/v1/agents", json={
            "name": f"Agent-{random.randint(1000, 9999)}",
            "maturity": "AUTONOMOUS"
        }, headers={"Authorization": f"Bearer {self.token}"})
```

**Key Benefits:**
- Simulates realistic user behavior
- Distributed load testing (multiple workers)
- Real-time performance metrics
- Identifies bottlenecks under load

**Note:** Locust is optional for Phase 208. Can defer to Phase 209 if needed.

### Anti-Patterns to Avoid

- **Anti-pattern: Using unit tests for integration testing**
  - **Why it's bad:** Unit tests mock too much, miss integration bugs
  - **What to do instead:** Create dedicated integration tests with realistic fixtures

- **Anti-pattern: Hard-coded performance assertions**
  - **Why it's bad:** Performance varies by hardware, flaky tests
  - **What to do instead:** Use pytest-benchmark for historical tracking, not hard-coded assertions

- **Anti-pattern: Testing external services in integration tests**
  - **Why it's bad:** Tests depend on external availability, slow and flaky
  - **What to do instead:** Mock external services (LLM providers, WebSocket), test internal integration

- **Anti-pattern: Load testing in CI/CD**
  - **Why it's bad:** Load tests are slow, expensive, block CI pipelines
  - **What to do instead:** Run load tests on-demand or in separate pipeline

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Performance timing** | Custom `time.time()` code | pytest-benchmark | Historical tracking, statistics, regression detection |
| **API contract validation** | Manual schema checks | Schemathesis | Property-based testing, automatic edge case generation |
| **Test data generation** | Random data creation | factory_boy | Valid model instances, relationships, realistic data |
| **Load testing framework** | Custom threading code | locust | Distributed execution, real-time metrics, proven scalability |
| **Flaky test detection** | Custom retry logic | pytest-rerunfailures | Already configured, automatic retry, CI integration |
| **HTTP mocking** | Custom mock responses | responses library | Clean API, already used in Phase 170, context manager support |

**Key insight:** pytest-benchmark alone saves 50-100 lines of timing/statistics code per benchmark. Schemathesis replaces 100+ lines of manual test case generation with property-based testing.

## Common Pitfalls

### Pitfall 1: Integration Tests That Are Too Slow
**What goes wrong:** Integration tests take 10+ minutes, developers stop running them locally.
**Why it happens:** Testing too many scenarios, not mocking external services, no parallelization.
**How to avoid:**
- Test only critical integration paths (3-5 workflows max)
- Mock external services (LLM providers, WebSocket connections)
- Use `pytest-xdist` for parallel test execution
- Target <30 seconds for full integration test suite
**Warning signs:** Tests take >2 minutes, developers skip running them before commits

### Pitfall 2: Performance Tests That Are Flaky
**What goes wrong:** Performance tests pass locally, fail in CI due to hardware differences.
**Why it happens:** Hard-coded performance assertions, testing in CI with shared resources, no warmup.
**How to avoid:**
- Use pytest-benchmark for historical tracking (not pass/fail)
- Run benchmarks on dedicated hardware (not in CI)
- Use statistical comparisons (P50, P99) instead of absolute values
- Add warmup iterations for JIT compilation
**Warning signs:** Tests fail intermittently, pass rate <95%

### Pitfall 3: Contract Tests That Don't Match OpenAPI Spec
**What goes wrong:** Schemathesis tests pass but OpenAPI spec is outdated or incorrect.
**Why it happens:** Manually editing OpenAPI spec, not auto-generating from FastAPI, schema drift.
**How to avoid:**
- Auto-generate OpenAPI spec from FastAPI: `app.openapi()`
- Commit `openapi.json` to repo for diff tracking
- Run Schemathesis in CI before merge
- Use `openapi-diff` for breaking change detection
**Warning signs:** Schemathesis passes but manual API tests fail, schema validation errors in production

### Pitfall 4: Integration Tests with Shared State
**What goes wrong:** Tests pass individually but fail when run together.
**Why it happens:** Shared database state, global caches, non-deterministic test data.
**How to avoid:**
- Use unique IDs for test data: `f"test-agent-{uuid.uuid4().hex[:8]}"`
- Wrap tests in database transactions (rollback after each test)
- Clear caches before each test: `get_governance_cache().clear()`
- Run tests in random order (pytest-random-order)
**Warning signs:** Tests fail in CI but pass locally, failures disappear on re-run

### Pitfall 5: Over-Mocking in Integration Tests
**What goes wrong:** Integration tests mock everything, becoming unit tests in disguise.
**Why it happens:** Fear of external dependencies, wanting deterministic tests, avoiding flakiness.
**How to avoid:**
- Mock only external services (LLM providers, WebSocket)
- Use real database (SQLite in-memory or PostgreSQL test container)
- Test actual integration points (workflow engine → state manager)
- Keep unit tests separate (test pure logic in isolation)
**Warning signs:** Tests never catch integration bugs, mocks outnumber real code 2:1

## Code Examples

### Integration Test: Workflow Execution with Database

```python
# tests/integration/workflows/test_workflow_engine_e2e.py
import pytest
from sqlalchemy.orm import Session
from core.workflow_engine import WorkflowEngine
from core.models import WorkflowExecution, WorkflowExecutionStatus
from tests.factories.workflow_factory import WorkflowExecutionFactory

@pytest.mark.integration
@pytest.mark.asyncio
async def test_workflow_execution_with_database(self, db_session: Session):
    """Test workflow execution persists to database correctly."""
    # Create workflow definition
    workflow_def = {
        "id": "test_workflow",
        "nodes": [
            {"id": "step1", "type": "action", "config": {"action": "test_action"}}
        ],
        "connections": []
    }

    # Create engine with real state manager (mock only external deps)
    engine = WorkflowEngine(max_concurrent_steps=2)

    # Mock external dependencies only
    with patch('core.workflow_engine.call_llm') as mock_llm:
        mock_llm.return_value = {"result": "success"}

        # Execute workflow
        execution = await engine.execute_workflow(
            workflow=workflow_def,
            user_id="test_user",
            db_session=db_session
        )

    # Verify database persistence
    assert execution.id is not None
    assert execution.status == WorkflowExecutionStatus.COMPLETED

    # Verify in database
    db_execution = db_session.query(WorkflowExecution).filter(
        WorkflowExecution.id == execution.id
    ).first()
    assert db_execution is not None
    assert db_execution.status == WorkflowExecutionStatus.COMPLETED
```

### API Contract Test: Agent Endpoints

```python
# tests/integration/contracts/test_agent_api_contracts.py
import pytest
import schemathesis
from hypothesis import settings
from main import app

# Load OpenAPI schema from FastAPI app
schema = schemathesis.from_wsgi("/openapi.json", app)

class TestAgentAPIContracts:
    @schema.parametrize(endpoint="/api/v1/agents/{agent_id}")
    @settings(max_examples=20, deadline=None)
    def test_get_agent_contracts(self, case):
        """Test GET /api/v1/agents/{agent_id} validates OpenAPI spec."""
        response = case.call_and_validate()
        # Schemathesis validates:
        # - Response status code matches spec
        # - Response body matches schema
        # - Required headers present
        assert response.status_code in [200, 404, 403]

    @schema.parametrize(endpoint="/api/v1/agents")
    @settings(max_examples=15)
    def test_create_agent_contracts(self, case):
        """Test POST /api/v1/agents validates OpenAPI spec."""
        response = case.call_and_validate()
        assert response.status_code in [200, 201, 400, 422]

    @schema.parametrize(endpoint="/api/v1/agents/{agent_id}/chat")
    @settings(max_examples=10)
    def test_agent_chat_contracts(self, case):
        """Test POST /api/v1/agents/{agent_id}/chat validates OpenAPI spec."""
        response = case.call_and_validate()
        assert response.status_code in [200, 404, 403, 500]
```

### Performance Benchmark: Workflow Engine

```python
# tests/integration/performance/test_workflow_performance.py
import pytest
from core.workflow_engine import WorkflowEngine

class TestWorkflowPerformance:
    @pytest.mark.benchmark(group="workflow-validation")
    def test_workflow_schema_validation(self, benchmark):
        """Benchmark workflow schema validation (<50ms target)."""
        engine = WorkflowEngine()
        workflow_def = {
            "id": "test_workflow",
            "nodes": [
                {"id": "step1", "type": "action"},
                {"id": "step2", "type": "action"}
            ],
            "connections": [{"from": "step1", "to": "step2"}]
        }

        def validate_schema():
            return engine._validate_workflow_schema(workflow_def)

        result = benchmark(validate_schema)
        assert result is True  # Valid schema
        # pytest-benchmark tracks historical performance

    @pytest.mark.benchmark(group="workflow-execution")
    def test_simple_workflow_execution(self, benchmark):
        """Benchmark simple workflow execution (<100ms target)."""
        engine = WorkflowEngine()

        def execute_workflow():
            workflow_def = {
                "id": "test_workflow",
                "nodes": [{"id": "step1", "type": "action"}],
                "connections": []
            }
            return engine._topological_sort(workflow_def["nodes"], workflow_def["connections"])

        result = benchmark(execute_workflow)
        assert len(result) == 1  # One step in execution order
        # Historical comparison: benchmark.stats.stats.mean vs previous runs
```

### Load Test: Agent API (Optional)

```python
# tests/load/test_agent_load.py
from locust import HttpUser, task, between
import random

class AgentAPIUser(HttpUser):
    """Simulate realistic agent API usage."""
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    def on_start(self):
        """Login before running tasks."""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "test_password"
        })
        if response.status_code == 200:
            self.token = response.json()["token"]
        else:
            self.token = None

    @task(3)
    def list_agents(self):
        """List agents (3x more frequent)."""
        if self.token:
            self.client.get("/api/v1/agents", headers={
                "Authorization": f"Bearer {self.token}"
            })

    @task(2)
    def get_agent(self):
        """Get specific agent."""
        if self.token:
            agent_id = f"agent-{random.randint(1000, 9999)}"
            self.client.get(f"/api/v1/agents/{agent_id}", headers={
                "Authorization": f"Bearer {self.token}"
            })

    @task(1)
    def create_agent(self):
        """Create new agent (less frequent)."""
        if self.token:
            self.client.post("/api/v1/agents", json={
                "name": f"TestAgent-{random.randint(1000, 9999)}",
                "maturity": "AUTONOMOUS"
            }, headers={"Authorization": f"Bearer {self.token}"})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Manual timing** | pytest-benchmark | 2020+ | Historical tracking, statistics, regression detection |
| **Manual schema validation** | Schemathesis | 2021+ | Property-based testing, automatic edge cases |
| **Sequential test execution** | pytest-xdist parallel | 2019+ | 3-4x faster test suites |
| **Hard-coded test data** | factory_boy | 2018+ | Valid model instances, relationships |
| **Custom load testing** | locust | 2019+ | Distributed execution, real-time metrics |

**Deprecated/outdated:**
- **Manual `time.time()` benchmarking**: Use pytest-benchmark for historical tracking
- **Manual API schema tests**: Use Schemathesis for property-based contract testing
- **`unittest.mock` for everything**: Use `responses` library for HTTP mocking (cleaner API)
- **Sequential test execution**: Use `pytest-xdist` for parallel execution (3-4x faster)

## Open Questions

1. **Should we use Locust for load testing in Phase 208?**
   - What we know: Locust is the standard for Python load testing, but adds complexity
   - What's unclear: Whether load testing is critical for Phase 208 or can be deferred
   - Recommendation: Defer Locust to Phase 209, focus on pytest-benchmark for micro-benchmarks in Phase 208

2. **Should integration tests use PostgreSQL or SQLite?**
   - What we know: SQLite is faster, PostgreSQL matches production, both supported
   - What's unclear: Performance impact, test reliability, CI infrastructure
   - Recommendation: Use SQLite in-memory for speed, PostgreSQL test container for pre-merge validation

3. **Should we run Schemathesis in CI for every PR?**
   - What we know: Schemathesis is slow (5-10 minutes for full test suite), catches breaking changes
   - What's unclear: Whether slow contract tests block merge or run in separate pipeline
   - Recommendation: Run Schemathesis on separate pipeline, don't block merge (use `continue-on-error`)

## Sources

### Primary (HIGH confidence)
- **backend/tests/integration/test_workflow_engine_integration.py** - Integration test pattern with mocks (lines 1-100)
- **backend/tests/test_performance_benchmarks.py** - pytest-benchmark usage (lines 1-100)
- **backend/tests/unit/governance/test_governance_cache_performance.py** - Performance test patterns (lines 1-100)
- **backend/docs/API_CONTRACT_TESTING.md** - Schemathesis integration guide (complete)
- **backend/docs/E2E_TESTING_GUIDE.md** - Integration testing patterns (lines 1-500)
- **.planning/phases/207-coverage-quality-push/207-PHASE-SUMMARY.md** - Phase 207 lessons learned (complete)
- **.planning/phases/207-coverage-quality-push/207-10-LESSONS-LEARNED.md** - Coverage efficiency analysis (lines 1-200)
- **backend/pytest.ini** - Test configuration with markers and async support (complete)
- **backend/pyproject.toml** - pytest-benchmark already installed (line 116)
- **backend/requirements-testing.txt** - pytest-benchmark 4.0+ already listed (line 116)

### Secondary (MEDIUM confidence)
- **pytest-benchmark documentation** (https://pytest-benchmark.readthedocs.io/) - Historical tracking, statistics
- **Schemathesis documentation** (https://schemathesis.readthedocs.io/) - API contract testing patterns
- **locust documentation** (https://locust.io/) - Load testing best practices

### Tertiary (LOW confidence)
- **Python integration testing best practices** - General pytest patterns (verified against existing codebase)
- **API contract testing strategies** - Schemathesis usage (verified against existing API_CONTRACT_TESTING.md)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already installed or documented in existing guides
- Architecture: HIGH - Patterns verified against existing integration tests (80+ files in tests/integration/)
- Pitfalls: HIGH - Issues observed in Phase 207 (complex modules have low unit coverage)

**Research date:** March 18, 2026
**Valid until:** April 17, 2026 (30 days - testing infrastructure evolves slowly)

**Key Assumptions:**
1. Phase 207's 87.4% unit coverage is accurate baseline
2. workflow_engine (10% coverage) and episode_segmentation (15% coverage) are priority targets
3. Integration test infrastructure (80+ files) provides proven patterns to build on
4. pytest-benchmark and Schemathesis are appropriate for Phase 208 scope

**Risks:**
1. Schemathesis hook compatibility (Phase 128 had `@schemathesis.hook` deprecation issues)
2. pytest-benchmark hardware sensitivity (performance varies by CI vs local)
3. Integration test execution time (may exceed 30 seconds target without parallelization)

**Mitigation:**
1. Use Schemathesis 3.0+ with updated Hypothesis integration
2. Run benchmarks on dedicated hardware, use historical tracking not absolute values
3. Use pytest-xdist for parallel execution, target 3-5 critical workflows only

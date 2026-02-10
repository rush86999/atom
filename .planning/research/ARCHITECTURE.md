# Architecture Research

**Domain:** Comprehensive Testing Systems for Python/FastAPI/React Native
**Researched:** February 10, 2026
**Confidence:** HIGH

## Standard Architecture

### System Overview

Comprehensive testing systems follow a layered architecture with clear separation between test types, fixtures, and infrastructure. The design prioritizes test isolation, fast feedback, and coverage quality.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Test Execution Layer                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │   Unit     │  │  Property  │  │ Integration│  │    E2E     │   │
│  │   Tests    │  │   Tests    │  │   Tests    │  │   Tests    │   │
│  │  (pytest)  │  │(Hypothesis)│  │  (pytest)  │  │  (pytest)  │   │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘   │
├────────┼───────────────┼───────────────┼───────────────┼───────────┤
│        │               │               │               │           │
├────────▼───────────────▼───────────────▼───────────────▼───────────┤
│                   Test Infrastructure Layer                       │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Fixtures & Mocks (conftest.py)                  │  │
│  │  - Database sessions  - API clients  - Test data factories  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   Test Helpers & Utils                       │  │
│  │  - Assertions  - Test generators  - Coverage reporters      │  │
│  └─────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                   Advanced Testing Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ Fuzzy Tests  │  │Mutation Tests│  │Chaos Tests   │            │
│  │  (Atheris)   │  │  (mutmut)    │  │(ChaosToolkit)│            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
├─────────────────────────────────────────────────────────────────────┤
│                   Coverage & Reporting Layer                       │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Coverage Reports (pytest-cov) → HTML/JSON/Terminal         │  │
│  └─────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  CI/CD Integration (GitHub Actions) → Test Results           │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Unit Tests** | Test individual functions/classes in isolation | pytest + pytest-mock |
| **Property Tests** | Verify invariants hold for all inputs | Hypothesis with custom strategies |
| **Integration Tests** | Test module interactions with real dependencies | pytest with database fixtures |
| **E2E Tests** | Test complete workflows through API/UI | pytest + TestClient/Playwright |
| **Fuzzy Tests** | Find crashes/vulnerabilities with random inputs | Atheris with libFuzzer |
| **Mutation Tests** | Measure test quality by introducing bugs | mutmut with pytest runner |
| **Chaos Tests** | Verify resilience under failure conditions | Chaos Toolkit with custom probes |
| **Coverage System** | Track code coverage across test runs | pytest-cov with JSON/HTML reports |
| **Test Fixtures** | Provide reusable test data and dependencies | pytest fixtures (conftest.py) |
| **Test Doubles** | Mock external dependencies | unittest.mock, pytest-mock |

## Recommended Project Structure

```
backend/tests/
├── conftest.py                 # Root fixtures (DB, API clients, env)
├── pytest.ini                  # Pytest configuration
├── .pytest_cache/              # Pytest cache
│
├── unit/                       # Unit tests (40% of pyramid)
│   ├── test_core_services.py
│   ├── test_models.py
│   └── test_utils.py
│
├── property_tests/             # Property-based tests (40% of pyramid)
│   ├── conftest.py            # Shared fixtures for property tests
│   ├── database/              # Database invariants
│   │   ├── test_database_invariants.py
│   │   └── test_transaction_invariants.py
│   ├── financial/             # Financial operations invariants
│   ├── security/              # Security invariants
│   ├── multi_agent/           # Multi-agent coordination invariants
│   ├── episodes/              # Episode management invariants
│   ├── api/                   # API contract invariants
│   └── tools/                 # Tool execution invariants
│
├── integration/               # Integration tests (15% of pyramid)
│   ├── test_database_integration.py
│   ├── test_api_integration.py
│   └── test_llm_integration.py
│
├── e2e/                       # End-to-end tests (5% of pyramid)
│   ├── conftest.py            # E2E-specific fixtures
│   ├── test_scenario_01_governance.py
│   ├── test_scenario_02_streaming.py
│   └── test_scenario_10_complete_workflow.py
│
├── fuzzy_tests/               # Fuzzy tests (security-focused)
│   ├── fuzz_helpers.py        # Fuzz test utilities
│   ├── security_validation/   # Input sanitization fuzzing
│   └── financial_parsing/     # Currency parsing fuzzing
│
├── chaos/                     # Chaos engineering tests
│   ├── chaos_helpers.py       # Chaos test utilities
│   ├── test_database_chaos.py
│   └── test_network_chaos.py
│
├── mutation_tests/            # Mutation testing configuration
│   ├── MUTATION_TESTING_GUIDE.md
│   ├── config/                # mutmut configuration
│   └── scripts/               # Mutation test runners
│
├── coverage_reports/          # Coverage artifacts
│   ├── html/                  # HTML coverage reports
│   └── metrics/               # JSON coverage metrics
│
├── grey_box/                  # Grey-box testing (partial knowledge)
│   └── conftest.py
│
└── artifacts/                 # Test artifacts (screenshots, logs)
```

### Structure Rationale

- **`unit/`**: Fast tests (<0.1s each) that test business logic in isolation
- **`property_tests/`**: Medium-speed tests (<1s each) using Hypothesis to find edge cases
- **`integration/`**: Slower tests (<5s each) testing module interactions with real DB
- **`e2e/`**: Slowest tests (<30s each) testing complete workflows through API
- **`fuzzy_tests/`**: Long-running security tests (minutes to hours) with Atheris
- **`chaos/`**: Resilience tests injecting failures into running system
- **`mutation_tests/`**: Quality assurance to detect weak tests
- **`coverage_reports/`**: Generated artifacts, not source code

## Architectural Patterns

### Pattern 1: Test Pyramid with Property-Based Layer

**What:** Prioritize fast tests at bottom, fewer slow tests at top. Add property-based testing as middle layer.

**When to use:** All Python projects requiring comprehensive coverage.

**Trade-offs:**
- **Pros:** Fast feedback, high bug detection, excellent coverage
- **Cons:** Requires learning Hypothesis strategies, initial setup time

**Example:**
```python
# Bottom layer: Unit test (fast, example-based)
def test_addition():
    assert add(2, 3) == 5

# Middle layer: Property test (medium speed, exhaustive)
@given(st.integers(), st.integers())
def test_addition_commutative(x, y):
    assert add(x, y) == add(y, x)  # Property: commutativity

# Top layer: Integration test (slow, realistic)
def test_addition_workflow():
    response = client.post("/add", json={"x": 2, "y": 3})
    assert response.status_code == 200
    assert response.json()["result"] == 5
```

### Pattern 2: Fixture Hierarchy with Scoping

**What:** Organize fixtures in hierarchy with appropriate scoping (session/module/function).

**When to use:** Projects with shared test data and dependencies.

**Trade-offs:**
- **Pros:** DRY, easy maintenance, clear dependency chains
- **Cons:** Fixture dependency complexity, implicit state

**Example:**
```python
# conftest.py
@pytest.fixture(scope="session")
def db_engine():
    """Create engine once for entire test session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create fresh session for each test."""
    session = Session(bind=db_engine)
    yield session
    session.rollback()
    session.close()

@pytest.fixture(scope="function")
def test_agent(db_session):
    """Create test agent using fresh session."""
    agent = AgentRegistry(name="TestAgent", status="STUDENT")
    db_session.add(agent)
    db_session.commit()
    return agent
```

### Pattern 3: Strategy-Based Property Testing

**What:** Define custom Hypothesis strategies for domain objects to generate valid test data.

**When to use:** Property tests for complex domain models.

**Trade-offs:**
- **Pros:** Realistic test data, catches edge cases, reproducible failures
- **Cons:** Requires strategy design, can be slow with complex data

**Example:**
```python
from hypothesis import strategies as st

# Custom strategy for agent maturity levels
@st.composite
def agent_maturity_strategy(draw):
    maturity = draw(st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))

    # Validate consistency
    if maturity == "STUDENT":
        assume(confidence < 0.5)
    elif maturity == "AUTONOMOUS":
        assume(confidence > 0.9)

    return {"maturity": maturity, "confidence": confidence}

# Use strategy in property test
@given(agent_maturity_strategy())
def test_agent_maturity_consistency(agent_data):
    agent = AgentRegistry(**agent_data)
    assert agent.is_valid_configuration()
```

### Pattern 4: Layered Mock Strategy

**What:** Use mocks only at integration boundaries, test real behavior in unit tests.

**When to use:** Projects with external dependencies (APIs, databases, file system).

**Trade-offs:**
- **Pros:** Fast tests, isolation from external failures
- **Cons:** Mocks can drift from real implementations, over-mocking risks

**Example:**
```python
# ✅ Good: Mock external API in integration test
def test_slack_api_integration():
    with patch("integrations.slack.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        result = slack_integration.send_message("#general", "test")
        assert result.success
        mock_post.assert_called_once()

# ✅ Good: Test real business logic in unit test
def test_budget_guardrails():
    engine = FinancialOpsEngine()
    result = engine.check_budget(budget=100, spend=150)
    assert not result.approved
    assert result.reason == "Budget exceeded"

# ❌ Bad: Over-mocking business logic
def test_budget_guardrails_over_mocked():
    with patch.object(FinancialOpsEngine, "check_budget") as mock_check:
        mock_check.return_value = Mock(approved=False)
        # This test doesn't verify anything real
```

### Pattern 5: Coverage-Driven Test Development

**What:** Use coverage reports to identify untested code, write tests to increase coverage.

**When to use:** Projects with strict coverage targets (80%+).

**Trade-offs:**
- **Pros:** Quantifiable progress, clear gaps identification
- **Cons:** Coverage ≠ quality, can lead to useless tests

**Example:**
```bash
# Generate baseline coverage
pytest tests/ --cov=core --cov-report=json

# Identify low-coverage files
python -c "
import json
with open('coverage.json') as f:
    data = json.load(f)
    for file, metrics in data['files'].items():
        if metrics['summary']['percent_covered'] < 80:
            print(f'{file}: {metrics[\"summary\"][\"percent_covered\"]:.1f}%')
"

# Target low-coverage files with new tests
pytest tests/unit/test_low_coverage_module.py --cov=core.low_coverage_module
```

## Data Flow

### Test Execution Flow

```
[Developer runs pytest]
    ↓
[pytest discovers tests]
    ↓
[Load conftest.py fixtures]
    ↓
[For each test file]:
    1. Set up fixtures (db_session, test_agent, client)
    2. Execute test
    3. Record result (PASS/FAIL/SKIP)
    4. Teardown fixtures
    ↓
[Generate coverage report]
    ↓
[Output results to terminal/JSON/HTML]
```

### Property Test Execution Flow

```
[@given decorator generates test data]
    ↓
[Hypothesis strategy creates input]
    ↓
[Run test with generated input]
    ↓
[Test passes?]
    ├─ YES → [Generate new input (max_examples times)]
    └─ NO  → [Shrink input to minimal failure case]
            ↓
        [Report failing example]
```

### Coverage Data Aggregation

```
[Multiple test runs]
    ↓
[.coverage files generated]
    ↓
[pytest-cov aggregates coverage]
    ↓
[Generate combined report]
    ├─→ coverage.json (machine-readable)
    ├─→ coverage.html (human-readable)
    └─→ terminal output (quick summary)
    ↓
[Upload to CI/CD for trend analysis]
```

### CI/CD Integration Flow

```
[Git push/PR]
    ↓
[GitHub Actions trigger]
    ↓
[Parallel test execution]:
    ├─ Smoke tests (<30s) → Block commit on failure
    ├─ Property tests (<2min) → Comment PR with results
    ├─ Fuzzy tests (daily) → Open issue on crash
    └─ Mutation tests (weekly) → Report quality score
    ↓
[Coverage upload to Codecov/Codecov]
    ↓
[Status checks updated]
    ↓
[Block merge if thresholds not met]
```

### Key Data Flows

1. **Test Discovery Flow:** pytest scans `tests/` directory → finds `test_*.py` files → collects test functions → builds test graph
2. **Fixture Resolution Flow:** pytest builds dependency graph → resolves fixtures in order → injects into test functions → cleans up after test
3. **Coverage Collection Flow:** pytest-cov instruments code → runs tests → records line execution → aggregates coverage → generates reports
4. **Property Test Shrink Flow:** Hypothesis detects failure → binary search on input space → finds minimal counterexample → reports with reproduction steps

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **0-1k tests** | Single conftest.py, all fixtures in one file, sequential execution |
| **1k-10k tests** | Split fixtures by module (unit/conftest.py, integration/conftest.py), use pytest-xdist for parallelization |
| **10k+ tests** | Hierarchical fixture organization, test splitting by suite, distributed CI/CD runners, coverage delta reporting |

### Scaling Priorities

1. **First bottleneck:** Test execution time (10s → 2min → 10min)
   - **Fix:** Use pytest-xdist for parallel execution, split slow tests into separate suite, use fixture caching

2. **Second bottleneck:** Fixture setup complexity (simple → nested → implicit dependencies)
   - **Fix:** Document fixture dependencies, use explicit fixture parameters, create fixture factory pattern

3. **Third bottleneck:** Coverage analysis (manual → automated → trend monitoring)
   - **Fix:** Integrate coverage reports in CI/CD, set coverage gates, track coverage trends over time

## Anti-Patterns

### Anti-Pattern 1: Test Implementation Details

**What people do:** Write tests that check internal implementation rather than external behavior.

```python
# ❌ Bad: Tests private method
def test_agent__calculate_confidence():
    agent = AgentRegistry()
    assert agent._calculate_confidence() == 0.5  # Brittle!

# ✅ Good: Tests public API
def test_agent_confidence_property():
    agent = AgentRegistry(confidence=0.5)
    assert agent.confidence == 0.5  # Stable
```

**Why it's wrong:** Tests break when implementation changes, even if behavior is correct. Creates maintenance burden.

**Do this instead:** Test public APIs and observable behavior. Use black-box testing approach.

### Anti-Pattern 2: Over-Mocking

**What people do:** Mock everything including the code under test.

```python
# ❌ Bad: Mocking the code under test
def test_budget_check():
    with patch.object(FinancialOpsEngine, "check_budget") as mock_check:
        mock_check.return_value = Mock(approved=False)
        engine = FinancialOpsEngine()
        result = engine.check_budget(100, 150)
        assert not result.approved  # Tests nothing!

# ✅ Good: Test real logic
def test_budget_check():
    engine = FinancialOpsEngine()
    result = engine.check_budget(budget=100, spend=150)
    assert not result.approved  # Verifies real behavior
```

**Why it's wrong:** Tests pass even if code is broken. Gives false confidence.

**Do this instead:** Only mock external dependencies (APIs, databases, file system). Test real business logic.

### Anti-Pattern 3: Brittle Property Tests

**What people do:** Write property tests with overly specific assertions.

```python
# ❌ Bad: Brittle property test
@given(st.lists(st.integers()))
def test_list_sorting_specific(xs):
    sorted_xs = sort(xs)
    assert sorted_xs == sorted(xs)  # Tautology, tests nothing

# ✅ Good: General property test
@given(st.lists(st.integers()))
def test_list_sorting_ordered(xs):
    sorted_xs = sort(xs)
    assert all(sorted_xs[i] <= sorted_xs[i+1] for i in range(len(sorted_xs)-1))
    assert sorted_xs == sorted(set(xs))  # Verify stability
```

**Why it's wrong:** Tests don't verify meaningful properties. Can pass with buggy implementation.

**Do this instead:** Identify general invariants (ordering, uniqueness, round-trip) and test those.

### Anti-Pattern 4: Shared Mutable State

**What people do:** Use module-level or class-level mutable state in tests.

```python
# ❌ Bad: Shared state causes flaky tests
test_data = {"count": 0}

def test_increment():
    test_data["count"] += 1
    assert test_data["count"] == 1

def test_increment_again():
    test_data["count"] += 1
    assert test_data["count"] == 1  # FAILS if tests run in wrong order!

# ✅ Good: Isolated test data
def test_increment():
    count = 0
    count += 1
    assert count == 1  # Always passes
```

**Why it's wrong:** Tests become order-dependent. Parallel execution causes random failures.

**Do this instead:** Use fixtures to create fresh test data for each test. Avoid module-level mutable state.

### Anti-Pattern 5: Ignoring Hypothesis Warnings

**What people do:** Suppress Hypothesis health checks without investigation.

```python
# ❌ Bad: Suppress health check
@given(st.lists(st.integers()))
@settings(suppress_health_check=list(HealthCheck))  # DANGER!
def test_unbounded_input(xs):
    result = process(xs)
    assert result is not None

# ✅ Good: Set reasonable limits
@given(st.lists(st.integers(), max_size=100))  # Bounded
def test_bounded_input(xs):
    result = process(xs)
    assert result is not None
```

**Why it's wrong:** Health checks detect real problems (slow tests, flaky tests, useless examples). Suppressing hides bugs.

**Do this instead:** Investigate health check failures. Use max_size, max_examples to control test behavior.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Database** | pytest fixtures with in-memory SQLite | Fast isolation, but different from production PostgreSQL |
| **LLM Providers** | Mock responses in unit tests, real calls in E2E | Unit tests fast, E2E tests catch integration issues |
| **External APIs** | unittest.mock with responses library | Record/replay patterns for complex interactions |
| **File System** | pytest tmpdir fixture | Automatic cleanup, isolated per test |
| **Redis/WebSocket** | fakeredis library for testing | Faster than real Redis, but not identical |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **core/ ↔ api/** | TestClient (FastAPI) | Test API routes without starting server |
| **core/ ↔ tools/** | Direct function calls | Tools are pure functions, easy to test |
| **backend ↔ mobile** | HTTP API tests | Mobile tests call backend API endpoints |
| **property_tests ↔ unit** | Shared fixtures | Both use conftest.py fixtures for consistency |

## Sources

- [Testing Strategies: pytest, fixtures, and mocking best practices](https://dasroot.net/posts/2026/01/testing-strategies-pytest-fixtures-mocking/) - January 22, 2026
- [How to Use pytest with Mocking - OneUptime](https://oneuptime.com/blog/post/2026-02-02-pytest-mocking/view) - February 2, 2026
- [Mastering Pytest: Advanced Fixtures, Parameterization, and Mocking](https://medium.com/@abhayda/mastering-pytest-advanced-fixtures-parameterization-and-mocking-explained-108a7a2ab82d) - February 8, 2025
- [Using Hypothesis and Schemathesis to Test FastAPI](https://testdriven.io/blog/fastapi-hypothesis/) - Property-based testing for FastAPI
- [FastAPI Best Practices](https://auth0.com/blog/fastapi-best-practices/) - Auth0's FastAPI testing guide
- [Protecting Architecture with Automated Tests in Python](https://handsonarchitects.com/blog/2026/protecting-architecture-with-automated-tests/) - PyTestArch for architecture testing
- [Building a Production-Ready FastAPI Boilerplate with Clean Architecture](https://dev.to/alwil17/building-a-production-ready-fastapi-boilerplate-with-clean-architecture-5757) - Clean architecture patterns
- [FastAPI in 2026: The Architecture Behind 3000+ Requests Per Second](https://kawaldeepsingh.medium.com/fastapi-in-2026-the-architecture-behind-3-000-requests-per-second-automatic-api-documentation-43f2cf573f57) - 2026 FastAPI architecture
- [How to Use Property-Based Testing as Fuzzy Unit Testing](https://www.infoq.com/news/2024/12/fuzzy-unit-testing/) - InfoQ article on property-based testing
- [A REST API Fuzz Testing Framework Based on GUI Interaction](https://www.sciencedirect.com/org/science/article/pii/S1546221826000895) - January 2026 research on API fuzzing

---
*Architecture research for: Comprehensive Testing Systems*
*Researched: February 10, 2026*

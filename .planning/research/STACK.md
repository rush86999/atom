# Technology Stack

**Project:** Atom Backend 80% Coverage Initiative
**Researched:** March 11, 2026

## Executive Summary

Atom's backend test infrastructure is **comprehensive and production-ready** for achieving 80% coverage. The current stack includes pytest 7.4+, pytest-cov 4.1+, Hypothesis 6.92, pytest-xdist 3.6, and extensive fixture infrastructure (50+ fixtures in conftest.py).

**Critical Finding:** A methodology gap exists between reported coverage (74.6% service-level estimates) and actual line coverage (8.50% measured). The stack is optimal - the focus must be on **test execution and gap closure**, not tool acquisition.

**Key Recommendation:** No new tools needed. Use existing pytest + pytest-cov + Hypothesis + pytest-xdist stack with focused test creation to close the 71.5 percentage point gap to 80% target.

---

## Recommended Stack

### Core Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest** | 7.4+ | Test runner | Industry standard, extensive plugin ecosystem, fixture-based design |
| **pytest-asyncio** | 0.21+ | Async test support | Native asyncio support for FastAPI, auto-mode for seamless async tests |
| **pytest-cov** | 4.1+ | Coverage measurement | pytest integration for coverage.py, produces JSON/HTML reports, CI-ready |
| **coverage.py** | 7.3+ (via pytest-cov) | Coverage engine | Gold standard for Python coverage, branch coverage support |

**Current Status:** ✅ INSTALLED - All core tools present in requirements.txt

### Database Testing
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest-xdist** | 3.6+ | Parallel test execution | Run tests in parallel for faster feedback, worker isolation |
| **factory-boy** | 3.3+ | Test data generation | SQLAlchemy integration, reduces fixture boilerplate |
| **freezegun** | 1.4+ | Time mocking | Deterministic timestamp testing, critical for episodes/time-based logic |
| **SQLAlchemy test DB** | 2.0+ (via core) | In-memory SQLite | Fast test isolation, no external dependencies, transaction rollback |

**Current Status:** ✅ INSTALLED - All database testing tools present

### Property-Based Testing
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Hypothesis** | 6.92+ | Property-based testing | Finds edge cases unit tests miss, stateful testing, strategy-based data generation |
| **hypothesis[strategies]** | bundled | Advanced strategies | Complex data generation (lists, dicts, custom types), fuzzing integration |

**Current Status:** ✅ INSTALLED - Hypothesis 6.92.0 in requirements.txt

### API & Integration Testing
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **FastAPI TestClient** | 0.104+ (via core) | HTTP endpoint testing | Synchronous client for FastAPI apps, request/response validation |
| **httpx** | 0.24+ (via core) | Async HTTP testing | Async client for real-world API testing, WebSocket support |
| **responses** | 0.23+ (via core) | HTTP mocking | Mock external HTTP requests, deterministic external service testing |
| **Schemathesis** | 3.6+ | API contract testing | OpenAPI schema validation, property-based API testing |
| **openapi-spec-validator** | 0.5+ | Schema validation | Verify OpenAPI spec correctness, contract-first testing |

**Current Status:** ✅ INSTALLED - Schemathesis and validator present in requirements.txt

### Quality & Reporting
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest-json-report** | 1.5+ | JSON test results | Machine-readable test reports, CI integration, trend analysis |
| **pytest-random-order** | 1.1+ | Flaky test detection | Randomize test execution order to expose hidden dependencies |
| **pytest-rerunfailures** | 14.0+ | Retry flaky tests | Automatic retry for intermittent failures, identifies flaky tests |
| **diff-cover** | 8.0+ | Coverage diff | PR coverage comments, incremental coverage enforcement |

**Current Status:** ✅ INSTALLED - All quality tools in pyproject.toml [test-quality] section

### Test Organization & Structure
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest.ini** | bundled | pytest configuration | Centralized config, markers, coverage settings, test discovery |
| **conftest.py** | bundled | Shared fixtures | Root fixtures, test isolation, database sessions, mock services |
| **Faker** | 19.0+ (via core) | Fake data generation | Realistic test data, localization support, reduces hardcoded values |

**Current Status:** ✅ IMPLEMENTED - 1,180+ test files, extensive conftest.py with 50+ fixtures

### Mocking & External Services
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **unittest.mock** | 3.11+ (stdlib) | Mocking framework | Built-in mocking, patch decorators, MagicMock for services |
| **responses** | 0.23+ (via core) | HTTP request mocking | External API mocking without network calls |
| **Mock Services** | custom (in conftest.py) | Domain-specific mocks | MockLLMProvider, MockEmbeddingService, MockWebSocket for testing |

**Current Status:** ✅ IMPLEMENTED - Comprehensive mock services in tests/fixtures/mock_services.py

---

## Current Coverage Analysis

### Actual Coverage (Methodology Gap Identified)
- **Reported:** 74.6% (service-level estimates, inaccurate)
- **Measured:** 8.50% actual line coverage (coverage.json)
- **Target:** 80% line coverage
- **Gap:** 71.5 percentage points
- **Total Backend Lines:** 72,727

### Critical Issue: Service-Level vs Line Coverage
The 74.6% figure is based on service-level estimates, not actual line coverage. Real line coverage measured at 8.50% indicates most code paths are untested.

### Test File Count
- **Total test files:** 1,180+ Python files
- **Test types:** Unit, integration, property-based, API contract, E2E
- **Structure:** `tests/unit/`, `tests/integration/`, domain-specific subdirectories

---

## Installation

### Core Dependencies (Already Installed)
```bash
# All core testing dependencies are in requirements.txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-xdist==3.6.1
hypothesis>=6.92.0
factory_boy>=3.3.0
pytest-freezegun>=0.4.0
faker==22.7.0
```

### Test Quality Dependencies (Already in pyproject.toml)
```bash
pip install -e .[test-quality]

# Installs:
# - pytest-json-report>=1.5.0
# - pytest-random-order>=1.1.0
# - pytest-rerunfailures>=14.0
```

### API Contract Testing (Already Installed)
```bash
# Already in requirements.txt
pip install schemathesis>=3.6.0
pip install openapi-spec-validator>=0.5.0
```

### Full Testing Stack Installation
```bash
cd backend
pip install -e .[all]  # Includes enterprise, dev, test
pip install -e .[test-quality]  # Quality tools
```

---

## What NOT to Add (Avoid Tool Bloat)

### ❌ Not Recommended
| Tool | Why Avoid |
|------|-----------|
| **mutmut** | Mutation testing overkill for 80% target, slows CI 10-100x |
| **locust** | Load testing not needed for coverage goal, separate concern |
| **py.test-benchmark** | Performance testing distinct from coverage, adds complexity |
| **vcrpy** | Unnecessary with responses library, adds cassette maintenance |
| **testmon** | pytest-xdist provides parallelization, testmon adds minimal value |
| **pytest-bdd** | BDD layer unnecessary for unit/integration coverage goal |
| **green** | Drop-in pytest replacement, no benefit over pytest 7.4+ |
| **nose2** | Deprecated, pytest is superior in every dimension |

### ✅ Alternatives to Use Instead
| Instead of | Use This |
|------------|----------|
| mutmut | Coverage.py + manual code review for critical paths |
| locust | Load testing tools (k6, locust) only when needed |
| testmon | pytest-xdist for parallel execution |
| vcrpy | responses library (already installed) |
| Custom fixtures | factory-boy (already installed) |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **Coverage** | pytest-cov | coverage.py standalone | pytest-cov integrates seamlessly, uses same engine |
| **Parallel** | pytest-xdist | pytest-parallel | xdist is mature, better worker isolation, loadscope distribution |
| **Data** | factory-boy | model_bakery | factory_boy has SQLAlchemy integration, already installed |
| **Time** | freezegun | time-machine | freezegun is stable, already installed, sufficient for tests |
| **HTTP Mock** | responses | aioresponses | responses covers sync httpx/requests, sufficient for backend |

---

## Coverage Configuration

### Current pytest.ini Coverage Settings
```ini
[coverage:run]
source = backend
omit =
    */tests/*
    */test_*.py
    */__pycache__/*
    */migrations/*
branch = true

[coverage:report]
precision = 2
show_missing = True
skip_covered = false
fail_under = 80
fail_under_branch = 70
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    class .*\\bProtocol\\):
    @(abc\\.)?abstractmethod
```

### Coverage Measurement Commands
```bash
# Measure coverage for specific module
pytest tests/unit/governance/ --cov=core/agent_governance_service --cov-report=term-missing

# Generate JSON report for metrics
pytest tests/ --cov=backend --cov-report=json:tests/coverage_reports/metrics/coverage.json

# HTML coverage report with missing lines
pytest tests/ --cov=backend --cov-report=html:tests/coverage_reports/html

# Combined line + branch coverage
pytest tests/ --cov=backend --cov-branch --cov-report=term-missing:skip-covered

# Parallel coverage measurement with xdist
pytest -n auto tests/ --cov=backend --cov-report=term-missing
```

---

## Test Organization Patterns

### Current Structure (1180+ test files)
```
backend/tests/
├── unit/                          # Fast, isolated tests
│   ├── governance/               # Domain-specific unit tests
│   ├── llm/                      # LLM service coverage tests
│   ├── episodes/                 # Episode segmentation tests
│   ├── agent/                    # Agent governance tests
│   └── test_*.py                 # Other unit tests
├── integration/                   # Slower, dependency tests
│   ├── services/                 # Service-level integration tests
│   ├── api/                      # API endpoint integration tests
│   ├── database/                 # Database integration tests
│   └── test_*.py                 # Other integration tests
├── conftest.py                   # Root fixtures (50+ fixtures)
├── fixtures/                     # Shared fixture modules
│   ├── mock_services.py          # Mock services (LLM, embeddings, storage)
│   └── ...
└── coverage_reports/             # Coverage metrics and reports
    └── metrics/
```

### Fixture Hierarchy (Current Implementation)
```python
# Root fixtures (autouse=True for isolation)
@pytest.fixture(autouse=True)
def isolate_environment()          # ENV var isolation
@pytest.fixture(autouse=True)
def reset_agent_task_registry()    # Singleton reset
@pytest.fixture(autouse=True)
def ensure_numpy_available()       # Module restoration

# Database fixtures
@pytest.fixture(scope="function")
def db_session()                   # In-memory SQLite per test

# Agent fixtures
@pytest.fixture(scope="function")
def test_agent_student()           # STUDENT maturity agent
@pytest.fixture(scope="function")
def test_agent_intern()            # INTERN maturity agent
@pytest.fixture(scope="function")
def test_agent_supervised()        # SUPERVISED maturity agent
@pytest.fixture(scope="function")
def test_agent_autonomous()        # AUTONOMOUS maturity agent

# Mock services
@pytest.fixture(scope="session")
def mock_llm_service()             # Session-scoped LLM mock
@pytest.fixture(scope="function")
def mock_llm_response()            # Deterministic LLM responses
@pytest.fixture(scope="function")
def mock_embedding_vectors()       # Deterministic embeddings
```

---

## Parallel Execution with pytest-xdist

### Current Configuration
```ini
# pytest.ini
addopts = -n auto --dist loadscope --maxfail=10
```

### Worker Isolation Strategy
```python
# Implemented in conftest.py
def pytest_configure(config):
    """Set unique worker ID for parallel execution"""
    if hasattr(config, 'workerinput'):
        worker_id = config.workerinput.get('workerid', 'master')
        os.environ['PYTEST_XDIST_WORKER_ID'] = worker_id

@pytest.fixture(scope="function")
def unique_resource_name():
    """Generate unique resource name for parallel tests"""
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    unique_id = str(uuid.uuid4())[:8]
    return f"test_{worker_id}_{unique_id}"
```

### Distribution Strategies
```bash
# Load balancing by test scope (default)
pytest -n auto --dist loadscope

# Load balancing by file
pytest -n auto --dist loadfile

# Explicit worker count
pytest -n 4 --dist loadscope
```

---

## Property-Based Testing with Hypothesis

### Current Implementation (6.92.0)
```python
from hypothesis import given, strategies as st

@given(st.integers(), st.integers())
def test_addition_commutative(x, y):
    """Property: Addition is commutative for all integers"""
    assert x + y == y + x

@given(st.text(min_size=0, max_size=1000))
def test_input_validation(text):
    """Property: Input sanitization handles all strings"""
    result = sanitize_input(text)
    assert '\x00' not in result  # No null bytes
    assert len(result) <= len(text)  # Sanitization doesn't add length
```

### Custom Strategies
```python
from hypothesis import strategies as st

# Agent registry strategy
agent_strategy = st.builds(
    AgentRegistry,
    name=st.text(min_size=1, max_size=50),
    category=st.sampled_from(['testing', 'automation', 'analysis']),
    confidence_score=st.floats(min_value=0.0, max_value=1.0),
    status=st.sampled_from([s.value for s in AgentStatus])
)

# Episode strategy
episode_strategy = st.builds(
    Episode,
    agent_id=st.uuids(),
    title=st.text(min_size=1, max_size=200),
    maturity_level=st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])
)
```

---

## Integration Testing Strategies

### Database Testing
```python
@pytest.fixture(scope="function")
def db_session():
    """In-memory SQLite for fast, isolated tests"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    Base.metadata.create_all(engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    os.unlink(db_path)
```

### API Testing with TestClient
```python
from fastapi.testclient import TestClient

@pytest.fixture
def test_client():
    """FastAPI TestClient for endpoint testing"""
    from main import app
    return TestClient(app)

def test_agent_registration(test_client):
    """Test agent registration endpoint"""
    response = test_client.post(
        "/api/v1/agents",
        json={
            "name": "TestAgent",
            "category": "testing",
            "module_path": "test.module",
            "class_name": "TestAgent"
        }
    )
    assert response.status_code == 200
    assert response.json()["name"] == "TestAgent"
```

### External Service Mocking with responses
```python
import responses

@responses.activate
def test_llm_provider_fallback():
    """Test LLM provider fallback on failure"""
    # Mock primary provider failure
    responses.add(
        responses.POST,
        "https://api.openai.com/v1/chat/completions",
        status=500,
        json={"error": "Internal server error"}
    )

    # Mock fallback provider success
    responses.add(
        responses.POST,
        "https://api.anthropic.com/v1/messages",
        status=200,
        json={"content": "Fallback response"}
    )

    # Test fallback logic
    handler = BYOKHandler()
    response = handler.generate_response("test prompt")
    assert "Fallback response" in response
```

---

## Coverage Target: 80% by Module

### High-Priority Modules (Low Coverage, High Impact)
| Module | Current Coverage | Lines | Priority | Strategy |
|--------|-----------------|-------|----------|----------|
| `core/episode_segmentation_service.py` | 27% | 591 | HIGH | 75 focused tests in Phase 159-01 |
| `core/llm/byok_handler.py` | 43% | 800+ | HIGH | HTTP-level mocking, provider paths |
| `core/agent_governance_service.py` | 60% | 616 | MEDIUM | Permission checks, HITL actions |
| `core/episode_retrieval_service.py` | Unknown | ~500 | MEDIUM | Retrieval modes, vector search |
| `api/atom_agent_endpoints.py` | Unknown | ~400 | MEDIUM | Endpoint coverage, error paths |

### Coverage Improvement Strategy
1. **Gap Analysis**: Use coverage.json to identify missing lines per module
2. **Focused Tests**: Create targeted tests for unexecuted code paths
3. **Property-Based Tests**: Add Hypothesis tests for complex logic
4. **Integration Tests**: Cover service-to-service interactions
5. **Edge Cases**: Error handling, boundary conditions, state transitions

---

## Migration Path from Current Setup

### Phase 1: No Changes Required ✅
- **Current setup is already optimal** for 80% coverage goal
- All required tools installed and configured
- Fixture system comprehensive (50+ fixtures in conftest.py)
- Parallel execution enabled (pytest-xdist)
- Coverage reporting configured (pytest-cov)

### Phase 2: Test Execution Optimization
```bash
# Run fast tests first (unit)
pytest tests/unit/ -n auto --maxfail=10

# Run slow tests after (integration)
pytest tests/integration/ -n auto --maxfail=5

# Run property-based tests separately (expensive)
pytest tests/ -m property --hypothesis-seed=0
```

### Phase 3: Coverage Measurement & Tracking
```bash
# Baseline measurement (current state)
pytest tests/ --cov=backend --cov-report=json:tests/coverage_reports/metrics/baseline.json

# Per-module coverage tracking
pytest tests/unit/llm/ --cov=core/llm --cov-report=term-missing

# Trend tracking (PR-to-PR)
diff-cover compare.json --compare-branch=origin/main
```

### Phase 4: Gap Closure (Phase 159-160)
- Identify modules with lowest coverage
- Create focused tests for missing code paths
- Use property-based tests for complex logic
- Add integration tests for service interactions

---

## Performance Benchmarks

### Test Execution Time (Current)
| Test Suite | Duration | Parallelization | Target |
|------------|----------|-----------------|--------|
| Unit tests | ~2-5 min | pytest-xdist (auto) | <5 min |
| Integration tests | ~10-20 min | pytest-xdist (auto) | <15 min |
| Property-based tests | ~5-10 min | Sequential (Hypothesis) | <10 min |
| **Total** | **~20-35 min** | **Mixed** | **<30 min** |

### Coverage Measurement Overhead
| Command | Overhead | Notes |
|---------|----------|-------|
| `pytest tests/` | 0s | No coverage |
| `pytest --cov=backend` | ~10-20% | Coverage measurement |
| `pytest --cov-report=html` | ~20-30% | HTML generation |
| `pytest -n auto --cov` | ~15-25% | Parallel + coverage |

---

## Sources

### Official Documentation (HIGH confidence)
- pytest documentation: https://docs.pytest.org/
- pytest-cov: https://pytest-cov.readthedocs.io/
- coverage.py: https://coverage.readthedocs.io/
- Hypothesis: https://hypothesis.readthedocs.io/
- pytest-xdist: https://pytest-xdist.readthedocs.io/
- factory-boy: https://factoryboy.readthedocs.io/

### Tool Comparison Guides (MEDIUM confidence)
- pytest-cov vs coverage.py: Community consensus (pytest-cov is wrapper)
- pytest-xdist vs pytest-parallel: xdist has better worker isolation
- freezegun vs time-machine: freezegun is more stable

### Best Practices (MEDIUM confidence)
- Property-based testing patterns: Hypothesis documentation
- Database testing patterns: SQLAlchemy test fixtures
- API testing patterns: FastAPI TestClient docs
- Parallel test execution: pytest-xdist documentation

### Current Codebase Analysis (HIGH confidence)
- /Users/rushiparikh/projects/atom/backend/pytest.ini
- /Users/rushiparikh/projects/atom/backend/pyproject.toml
- /Users/rushiparikh/projects/atom/backend/requirements.txt
- /Users/rushiparikh/projects/atom/backend/tests/conftest.py
- /Users/rushiparikh/projects/atom/backend/coverage.json

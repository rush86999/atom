# Testing Guide - Atom Backend

**Last Updated:** 2026-04-03
**Phase:** 248-02 - Test Discovery and Documentation

This guide covers how to run tests, interpret results, and troubleshoot common issues in the Atom backend test suite.

---

## Quick Start

### Prerequisites

```bash
# Navigate to backend directory
cd /Users/rushiparikh/projects/atom/backend

# Activate virtual environment
source venv/bin/activate

# Verify pytest is installed
pytest --version
```

### Run All Tests

```bash
# Run all tests (WARNING: may take hours)
pytest -v

# Run with short traceback
pytest -v --tb=short

# Run with coverage report
pytest --cov=core --cov-report=html -v
```

### Run Specific Tests

```bash
# Run specific test file
pytest tests/api/test_auth_routes.py -v

# Run specific test class
pytest tests/api/test_dto_validation.py::TestAgentDTOValidation -v

# Run specific test function
pytest tests/api/test_dto_validation.py::TestAgentDTOValidation::test_agent_request_dto_required_fields -v

# Run multiple test files
pytest tests/api/test_auth_routes.py tests/api/test_canvas_routes.py -v
```

---

## Test Categories

### By Markers

Atom uses pytest markers to categorize tests by type and priority:

```bash
# Unit tests (fast, isolated)
pytest -m "unit" -v

# Integration tests (slower, requires dependencies)
pytest -m "integration" -v

# Property-based tests using Hypothesis
pytest -m "property" -v

# Fuzzy tests (bug discovery)
pytest -m "fuzzing" -v

# E2E UI tests with Playwright
pytest -m "e2e" -v

# Fast tests (<0.1s)
pytest -m "fast" -v

# Slow tests (>1 second)
pytest -m "slow" -v
```

### By Priority

```bash
# Critical priority (security, financial)
pytest -m "P0" -v

# High priority (core business logic)
pytest -m "P1" -v

# Medium priority (API, tools)
pytest -m "P2" -v

# Low priority (nice-to-have)
pytest -m "P3" -v
```

### By Domain

```bash
# Financial operations tests
pytest -m "financial" -v

# Security validation tests
pytest -m "security" -v

# API contract tests
pytest -m "api" -v

# Database model tests
pytest -m "database" -v

# Workflow execution tests
pytest -m "workflow" -v

# Episode management tests
pytest -m "episode" -v

# Agent coordination tests
pytest -m "agent" -v

# Governance tests
pytest -m "governance" -v
```

---

## Interpreting Results

### Test Outcome Symbols

- `PASSED` - Test passed successfully ✓
- `FAILED` - Test failed with assertion or error ✗
- `SKIPPED` - Test skipped (conditional or decorator) ⊘
- `XFAILED` - Expected failure (xfail marker) ◯
- `XPASS` - Unexpected pass (xfail marker but passed) ◐

### Test Summary

```
=========================== short test summary info ============================
FAILED tests/api/test_dto_validation.py::TestAgentDTOValidation::test_agent_request_dto_required_fields
FAILED tests/api/test_dto_validation.py::TestAgentDTOValidation::test_agent_request_dto_optional_fields
================= 7 failed, 56 passed, 134 warnings in 59.06s ==================
```

**Interpretation:**
- 7 tests failed (need fixing)
- 56 tests passed (working correctly)
- 134 warnings (should review but not blocking)
- Execution time: 59.06 seconds

### Warning Types

#### DeprecationWarnings
- **PydanticDeprecatedSince20:** Pydantic v1 style validators deprecated
- **SAWarning:** SQLAlchemy relationship warnings
- **Distutils Version:** Deprecated version classes

**Action:** Update code to use new APIs (non-blocking but should fix)

#### Import Warnings
- **RequestsDependencyWarning:** urllib3/chardet version mismatch

**Action:** Update dependencies (non-blocking)

---

## Common Issues and Solutions

### Issue 1: ModuleNotFoundError

**Symptom:**
```
ModuleNotFoundError: No module named 'cv2'
ModuleNotFoundError: No module named 'frontmatter'
```

**Solution:**
```bash
# Install missing package
pip install opencv-python-headless
pip install python-frontmatter
pip install boto3
```

### Issue 2: Import Errors During Collection

**Symptom:**
```
ImportError: cannot import name 'AgentPost' from 'core.models'
```

**Solution:**
- Check if the import exists in the module
- Update test to use correct import
- Or remove test if feature is deprecated

### Issue 3: Syntax Errors in Test Files

**Symptom:**
```
SyntaxError: f-string expression part cannot include a backslash
SyntaxError: invalid regex literal /inactive/i
```

**Solution:**
- Fix Python syntax (regex literals use strings, not `/pattern/`)
- Remove backslashes from f-string expressions
- Use proper Python syntax

### Issue 4: Pydantic Validation Errors

**Symptom:**
```
Failed: DID NOT RAISE <class 'pydantic_core._pydantic_core.ValidationError'>
AttributeError: 'AgentRunRequest' object has no attribute 'agent_id'
```

**Solution:**
- Update DTOs to Pydantic v2 syntax
- Check field names match test expectations
- Update validation logic

### Issue 5: Database Connection Errors

**Symptom:**
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: workflow_metrics
```

**Solution:**
```bash
# Run database migrations
alembic upgrade head

# Or create test database
python -c "from core.database import init_db; init_db()"
```

### Issue 6: Test Collection Errors

**Symptom:**
```
INTERNALERROR> ImportError while importing test module
```

**Solution:**
- Fix syntax errors in test files
- Fix import errors in test files
- Install missing dependencies
- Exclude problematic files: `pytest --ignore=tests/problematic/`

---

## Property-Based Testing

Property-based tests use Hypothesis to generate random inputs and verify invariants that must always be true. Unlike example-based tests that check specific inputs, property tests explore thousands of auto-generated inputs to find edge cases.

### When to Use Property Tests

Use property tests for:
- **Invariants** that must always be true (e.g., maturity ordering, cost calculation)
- **State machines** with transition rules (e.g., workflow status)
- **Mathematical properties** (e.g., additivity, associativity, commutativity)
- **Idempotent operations** (same input → same output)
- **Boundary conditions** (e.g., confidence scores in [0.0, 1.0])

### Hypothesis Configuration

Standard settings for property tests:

```python
from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import sampled_from, integers, floats, lists, text, datetimes

# Critical invariants (maturity ordering, cache performance)
HYPOTHESIS_SETTINGS_CRITICAL = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 200
}

# Standard invariants (permission checks, determinism)
HYPOTHESIS_SETTINGS_STANDARD = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 100
}

# IO-bound operations (database queries)
HYPOTHESIS_SETTINGS_IO = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 50
}
```

### Common Hypothesis Strategies

```python
from hypothesis.strategies import (
    sampled_from,   # Choose from list
    integers,       # Integer range
    floats,         # Floating point range
    lists,          # List of elements
    text,           # String generation
    datetimes,      # DateTime generation
    tuples,         # Tuples
    dictionaries,   # Dict generation
    booleans,       # True/False
    just,           # Always return specific value
    builds          # Build complex objects
)
```

### Property Test Pattern

```python
class TestMaturityLevelInvariants:
    """Property-based tests for maturity level invariants."""

    @given(
        level_a=sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
        level_b=sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    def test_maturity_total_ordering(self, level_a, level_b):
        """
        PROPERTY: Maturity levels form total ordering.

        STRATEGY: st.sampled_from(maturity_levels)

        INVARIANT: For any two levels a, b: a < b OR b < a OR a == b

        RADII: 200 examples explores all 16 pairwise comparisons (4x4 matrix)
        """
        maturity_order = {"STUDENT": 0, "INTERN": 1, "SUPERVISED": 2, "AUTONOMOUS": 3}
        order_a = maturity_order[level_a]
        order_b = maturity_order[level_b]

        # Total ordering: one of these must be true
        is_total_order = (order_a < order_b) or (order_b < order_a) or (order_a == order_b)
        assert is_total_order, f"Maturity levels {level_a} and {level_b} violate total ordering"
```

### Running Property Tests

```bash
# Run all property tests
pytest tests/property_tests/ -v

# Run specific property test file
pytest tests/property_tests/governance/test_governance_invariants_property.py -v

# Run with verbose output to see generated examples
pytest tests/property_tests/ -v -s

# Run with hypothesis profile
pytest tests/property_tests/ --hypothesis-profile=dev -v
```

### Property Test Files

The following property test files cover critical invariants:

| File | Invariants Covered |
|------|-------------------|
| `tests/property_tests/governance/test_governance_invariants_property.py` | Maturity ordering, permission checks, cache consistency |
| `tests/property_tests/llm/test_llm_business_logic_invariants.py` | Token counting, cost calculation, provider fallback |
| `tests/property_tests/workflows/test_workflow_business_logic_invariants.py` | Status transitions, step ordering, timestamp ordering |
| `tests/property_tests/core/test_governance_business_logic_invariants.py` | Governance business logic invariants |

### Writing New Property Tests

When writing new property tests:

1. **Identify the invariant** - What must always be true?
2. **Choose appropriate strategy** - What inputs to generate?
3. **Set appropriate max_examples** - How many examples to test?
4. **Document the property** - Explain what invariant is being tested
5. **Include edge cases** - Use @example decorator for specific cases

Example:
```python
from hypothesis import given, settings, example

@given(confidence=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
@example(confidence=0.0)  # Boundary: minimum
@example(confidence=0.5)  # Boundary: STUDENT/INTERN threshold
@example(confidence=0.7)  # Boundary: INTERN/SUPERVISED threshold
@example(confidence=0.9)  # Boundary: SUPERVISED/AUTONOMOUS threshold
@example(confidence=1.0)  # Boundary: maximum
@settings(**HYPOTHESIS_SETTINGS_STANDARD)
def test_confidence_bounds(self, confidence):
    """PROPERTY: Confidence scores stay within [0.0, 1.0] bounds."""
    assert 0.0 <= confidence <= 1.0
```

### Debugging Property Tests

When a property test fails:

1. **Use verbose mode** to see the failing input: `pytest -v -s`
2. **Use @example** to reproduce the specific case
3. **Use assume()** to filter invalid inputs
4. **Reduce max_examples** temporarily for faster debugging

```python
from hypothesis import assume

@given(x=integers(), y=integers())
def test_division(self, x, y):
    assume(y != 0)  # Filter out division by zero
    assert x / y == x / y
```

### Phase 252 Property Tests

**Added 49 property tests** for business logic invariants:

- **Governance (10 tests):** Maturity ordering, action complexity, permission checks, confidence scores, cache consistency
- **LLM (18 tests):** Token counting, cost calculation, provider fallback, streaming responses, caching, budgets, requests, validation, rate limiting
- **Workflows (21 tests):** Status transitions, step execution, timestamps, versions, rollback, cancellation, dependencies, parallelism, retry, state consistency, resource management

**Test Files:**
- `tests/property_tests/core/test_governance_business_logic_invariants.py` (402 lines, 10 tests)
- `tests/property_tests/llm/test_llm_business_logic_invariants.py` (411 lines, 18 tests)
- `tests/property_tests/workflows/test_workflow_business_logic_invariants.py` (503 lines, 21 tests)

**Execution:** ~22 seconds for all 49 property tests (0.45s per test average)

---

## Coverage Measurement (Phase 251)

### Run Coverage Measurement

```bash
# Navigate to backend directory
cd /Users/rushiparikh/projects/atom/backend

# Run coverage measurement with pytest-cov
python3 -m pytest \
  --cov=backend \
  --cov-branch \
  --cov-report=json:tests/coverage_reports/metrics/coverage_latest.json \
  --cov-report=term-missing \
  --cov-report=html:tests/coverage_reports/html \
  --ignore=tests/e2e_ui \
  -o "addopts="

# Generate baseline report (if needed)
python3 tests/scripts/generate_baseline_coverage_report.py
```

### Current Baseline

- **Phase:** 251
- **Line Coverage:** 5.50% (4,734 / 68,341 lines)
- **Branch Coverage:** 0.25% (47 / 18,576 branches)
- **Files Measured:** 494
- **Target:** 70%
- **Gap:** 64.50 percentage points to 70% target
- **Methodology:** Actual line execution (coverage.py) - not service-level estimates

### Coverage Reports

- **JSON:** tests/coverage_reports/metrics/coverage_251.json
- **HTML:** tests/coverage_reports/html/index.html
- **Baseline:** tests/coverage_reports/backend_251_baseline.md

### Interpreting Coverage Reports

1. **Line Coverage:** Percentage of executable lines executed during tests
2. **Branch Coverage:** Percentage of if/else branches taken (requires --cov-branch)
3. **Missing Lines:** Line numbers not executed (shown in term-missing report)

**Critical:** Always use actual line execution data from coverage.py, not service-level estimates. Phase 161 showed 8.50% actual coverage vs 74.6% service-level estimates. Phase 251 baseline is 5.50% actual coverage across 494 files.

### Coverage by Module

```bash
# Generate terminal coverage report
pytest --cov=backend --cov-report=term-missing -v

# Generate XML report (for CI)
pytest --cov=backend --cov-report=xml -v

# View HTML coverage report
open tests/coverage_reports/html/index.html
```

---

## CI/CD Integration

### GitHub Actions

Tests run automatically on:
- Pull requests
- Pushes to main branch
- Manual workflow triggers

**Test Commands in CI:**
```yaml
- name: Run unit tests
  run: pytest -m "unit" -v

- name: Run integration tests
  run: pytest -m "integration" -v

- name: Generate coverage report
  run: pytest --cov=core --cov-report=xml -v
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run pre-commit manually
pre-commit run --all-files
```

---

## Test Markers Reference

### Test Type Markers

| Marker | Description | Usage |
|--------|-------------|-------|
| `unit` | Unit tests (fast, isolated) | `@pytest.mark.unit` |
| `integration` | Integration tests (slower) | `@pytest.mark.integration` |
| `property` | Property-based tests (Hypothesis) | `@pytest.mark.property` |
| `invariant` | Invariant tests | `@pytest.mark.invariant` |
| `contract` | API contract tests (Schemathesis) | `@pytest.mark.contract` |
| `fast` | Fast tests (<0.1s) | `@pytest.mark.fast` |
| `slow` | Slow tests (>1s) | `@pytest.mark.slow` |
| `fuzzy` | Fuzzy tests (Atheris) | `@pytest.mark.fuzzy` |
| `mutation` | Mutation testing | `@pytest.mark.mutation` |
| `chaos` | Chaos engineering tests | `@pytest.mark.chaos` |
| `stress` | Stress tests | `@pytest.mark.stress` |

### Priority Markers

| Marker | Description | When to Run |
|--------|-------------|-------------|
| `P0` | Critical (security, financial) | Every commit |
| `P1` | High (core logic) | Every PR |
| `P2` | Medium (API, tools) | Nightly |
| `P3` | Low (nice-to-have) | Weekly |

### Domain Markers

| Marker | Domain |
|--------|--------|
| `financial` | Financial operations |
| `security` | Security validation |
| `api` | API endpoints |
| `database` | Database models |
| `workflow` | Workflow execution |
| `episode` | Episode management |
| `agent` | Agent coordination |
| `governance` | Agent governance |

### Governance Markers

| Marker | Agent Maturity |
|--------|---------------|
| `student` | STUDENT maturity tests |
| `intern` | INTERN maturity tests |
| `supervised` | SUPERVISED maturity tests |
| `autonomous` | AUTONOMOUS maturity tests |

---

## Advanced Usage

### Parallel Test Execution

```bash
# Run tests with 4 workers
pytest -n 4 -v

# Run tests with auto-detected CPUs
pytest -n auto -v
```

### Test Filtering

```bash
# Run tests matching pattern
pytest -k "test_auth" -v

# Run tests NOT matching pattern
pytest -k "not slow" -v

# Run multiple patterns
pytest -k "auth or canvas" -v
```

### Stop on First Failure

```bash
# Stop after first failure
pytest -x -v

# Stop after N failures
pytest --maxfail=5 -v
```

### Verbose Output

```bash
# Show full test names
pytest -vv

# Show print statements
pytest -s -v

# Show local variables on failure
pytest -l -v
```

### Rerun Failed Tests

```bash
# Rerun only failed tests from last run
pytest --lf -v

# Rerun failed tests first, then others
pytest --ff -v
```

### Debugging Failed Tests

```bash
# Drop into PDB on failure
pytest --pdb -v

# Drop into PDB on error (not just failure)
pytest --pdb --trace -v

# Use ipdb instead of pdb
pytest --pdbcls=IPython.terminal.debugger:TerminalPdb --pdb -v
```

---

## Test Fixtures

### Common Fixtures

```python
import pytest
from sqlalchemy.orm import Session

# Database session fixture
@pytest.fixture
def db_session():
    """Get a test database session"""
    from core.database import SessionLocal
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()

# Test client fixture
@pytest.fixture
def client():
    """Get FastAPI test client"""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)

# Authenticated client fixture
@pytest.fixture
def auth_client(client):
    """Get authenticated test client"""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpass"
    })
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

### Using Fixtures in Tests

```python
def test_create_agent(db_session: Session, auth_client):
    """Test agent creation with authenticated client"""
    response = auth_client.post("/api/agents", json={
        "name": "test-agent",
        "maturity": "STUDENT"
    })
    assert response.status_code == 201
    assert response.json()["name"] == "test-agent"
```

---

## Writing Tests

### Test Structure

```python
"""
Tests for [Feature Name]

Tests cover:
- [Scenario 1]
- [Scenario 2]
- [Edge cases]
"""

import pytest
from sqlalchemy.orm import Session

class TestFeatureName:
    """Test suite for [Feature]"""

    def test_scenario_1(self, db_session: Session):
        """Test [scenario 1]"""
        # Arrange
        input_data = {...}

        # Act
        result = function_under_test(input_data)

        # Assert
        assert result.expected == expected_value

    def test_scenario_2(self, db_session: Session):
        """Test [scenario 2]"""
        # Test implementation
        pass
```

### Test Naming Conventions

- **Files:** `test_<feature>.py` (e.g., `test_auth_routes.py`)
- **Classes:** `Test<FeatureName>` (e.g., `TestAuthRoutes`)
- **Functions:** `test_<scenario>_<expected_outcome>` (e.g., `test_login_invalid_credentials_returns_401`)

### Best Practices

1. **Arrange-Act-Assert Pattern:**
   ```python
   def test_create_agent():
       # Arrange: Set up test data
       agent_data = {"name": "test", "maturity": "STUDENT"}

       # Act: Execute function
       result = create_agent(agent_data)

       # Assert: Verify results
       assert result.name == "test"
       assert result.maturity == "STUDENT"
   ```

2. **Use Descriptive Names:**
   ```python
   # Good
   def test_login_with_invalid_credentials_returns_401_unauthorized():

   # Bad
   def test_login():
   ```

3. **Test One Thing:**
   ```python
   # Good: Single assertion
   def test_agent_name_is_required():
       with pytest.raises(ValidationError):
           AgentCreateRequest(name=None)

   # Bad: Multiple assertions
   def test_agent_validation():
       agent = AgentCreateRequest(name="test")
       assert agent.name == "test"
       assert agent.maturity == "STUDENT"  # Different concern
   ```

4. **Use Fixtures for Setup:**
   ```python
   # Good: Reusable fixture
   @pytest.fixture
   def test_agent(db_session):
       return create_test_agent(db_session, name="test")

   def test_agent_update(test_agent):
       test_agent.name = "updated"
       assert test_agent.name == "updated"

   # Bad: Duplicated setup
   def test_agent_update_1():
       agent = create_test_agent(name="test")
       agent.name = "updated"

   def test_agent_update_2():
       agent = create_test_agent(name="test")
       agent.name = "updated"
   ```

---

## Troubleshooting

### Tests Failing Locally but Passing in CI

**Possible Causes:**
1. Database state differences
2. Environment variable differences
3. Dependency version differences

**Solutions:**
```bash
# Reset database
alembic downgrade base && alembic upgrade head

# Check environment variables
env | grep ATOM

# Sync dependencies
pip install -r requirements.txt
```

### Flaky Tests (Intermittent Failures)

**Possible Causes:**
1. Race conditions
2. Time-dependent logic
3. External service dependencies

**Solutions:**
```python
# Add retry decorator
@pytest.mark.flaky
@pytest.mark.retry(max_retries=3)
def test_something_flaky():
    pass

# Use freezegun for time-dependent tests
@pytest.mark.freeze_time("2026-04-03")
def test_time_dependent():
    pass

# Mock external services
@patch('core.service.external_api_call')
def test_with_mock(mock_api):
    mock_api.return_value = expected_data
```

### Slow Tests

**Solutions:**
1. Use fixtures for expensive setup
2. Mock external dependencies
3. Use `@pytest.mark.skipif` for slow tests
4. Run tests in parallel: `pytest -n auto`

---

## Performance Benchmarks

### Expected Test Duration

| Category | Count | Duration |
|----------|-------|----------|
| Unit tests | ~500 | <5 min |
| Integration tests | ~200 | <15 min |
| E2E tests | ~100 | <30 min |
| Full suite | ~8000 | ~2-4 hours |

### Performance Targets

- Unit test: <0.1s per test
- Integration test: <1s per test
- E2E test: <10s per test

---

## Resources

### Documentation

- [pytest Documentation](https://docs.pytest.org/)
- [Pydantic v2 Migration Guide](https://errors.pydantic.dev/2.12/migration/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)

### Internal Docs

- `TEST_FAILURE_REPORT.md` - Comprehensive test failure analysis
- `BUILD.md` - Build process documentation
- `CODE_QUALITY_STANDARDS.md` - Code quality guidelines

### Configuration Files

- `pytest.ini` - pytest configuration
- `conftest.py` - Shared fixtures
- `.coveragerc` - Coverage configuration

---

**Last Updated:** 2026-04-03
**Maintained By:** Phase 248 Test Discovery Team
**Questions?** See `TEST_FAILURE_REPORT.md` for detailed failure analysis

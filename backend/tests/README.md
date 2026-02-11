# Atom Test Suite

Comprehensive test suite for the Atom AI-powered business automation platform.

---

## Overview

**Purpose**: Ensure code quality, prevent regressions, and validate system behavior.

**Coverage Goals**: 80% across all domains (governance, security, episodes, backend)

**Execution Time Target**: <5 minutes (parallel execution with pytest-xdist)

**Test Categories**:
- **Unit tests**: Isolated component tests (fast, no external dependencies)
- **Integration tests**: Component interaction tests (database, API, services)
- **Property tests**: Invariant validation with Hypothesis (comprehensive input testing)
- **Security tests**: Input validation, authorization, authentication (OWASP Top 10)

---

## Running Tests

### Basic Commands

```bash
# Run all tests (sequential)
pytest tests/ -v

# Run all tests (parallel - recommended)
pytest tests/ -n auto -v

# Run with coverage report
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html

# Run specific test file
pytest tests/property_tests/database/test_database_invariants.py -v

# Run specific test function
pytest tests/test_agent.py::test_agent_creation -v

# Run tests by marker
pytest tests/ -m unit              # Unit tests only
pytest tests/ -m integration       # Integration tests only
pytest tests/ -m "not slow"        # Exclude slow tests
pytest tests/ -m P0               # Critical priority tests
```

### Parallel Execution

```bash
# Auto-detect CPU cores
pytest tests/ -n auto

# Specify number of workers
pytest tests/ -n 4

# Load scope scheduling (group tests by module)
pytest tests/ -n auto --dist loadscope
```

**Speedup**: ~2-4x faster than sequential execution (depends on CPU cores).

**See**: [TEST_ISOLATION_PATTERNS.md](./docs/TEST_ISOLATION_PATTERNS.md) for parallel execution patterns.

### Coverage Reports

```bash
# HTML report (detailed, interactive)
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html
open tests/coverage_reports/html/index.html

# JSON report (for CI/CD)
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json

# Terminal report (quick overview)
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=term-missing

# Branch coverage (more accurate)
pytest tests/ --cov=core --cov-branch

# Fail if coverage below threshold
pytest tests/ --cov=core --cov-fail-under=80
```

**See**: [COVERAGE_GUIDE.md](./docs/COVERAGE_GUIDE.md) for coverage interpretation.

### Flaky Test Detection

```bash
# Retry failed tests up to 3 times
pytest tests/ --reruns 3

# Retry with delay between retries
pytest tests/ --reruns 3 --reruns-delay 1

# Retry only flaky-marked tests
pytest tests/ -m flaky --reruns 3
```

**See**: [FLAKY_TEST_GUIDE.md](./docs/FLAKY_TEST_GUIDE.md) for flaky test prevention.

### Development Workflow

```bash
# Run only modified tests (fast feedback)
pytest tests/ -v --lf  # "last failed"

# Run with pdb on failure (debugging)
pytest tests/ -v --pdb

# Stop on first failure (fast iteration)
pytest tests/ -v -x

# Run with verbose output
pytest tests/ -vv -s  # Show print statements

# Dry run (show what would run)
pytest tests/ --collect-only
```

---

## Test Structure

```
tests/
├── conftest.py                    # Root fixtures (pytest_configure, unique_resource_name)
├── pytest.ini                     # Pytest configuration (addopts, markers, xdist)
├── factories/                     # Test data factories (dynamic, isolated)
│   ├── __init__.py               # BaseFactory and factory exports
│   ├── agent_factory.py          # AgentRegistry, maturity-specific factories
│   ├── user_factory.py           # User, AdminUserFactory
│   ├── episode_factory.py        # Episode, EpisodeSegment, EpisodeAccessLog
│   ├── execution_factory.py      # AgentExecution, timing metadata
│   └── canvas_factory.py         # CanvasAudit, interaction records
├── unit/                          # Isolated unit tests
│   ├── governance/               # Agent governance, context resolution, caching
│   ├── security/                 # Authentication, encryption, validation
│   └── episodes/                 # Segmentation, retrieval, lifecycle, graduation
├── integration/                   # Component interaction tests
│   ├── database/                 # Database operations, transactions
│   ├── api/                      # API endpoints, request/response handling
│   └── services/                 # Service layer integration
├── property_tests/               # Hypothesis property tests (invariant validation)
│   ├── invariants/               # INVARIANTS.md (66 invariants documented)
│   │   ├── governance_invariants.py
│   │   ├── security_invariants.py
│   │   ├── episode_invariants.py
│   │   ├── state_management_invariants.py
│   │   ├── event_handling_invariants.py
│   │   ├── file_operations_invariants.py
│   │   └── database_invariants.py
│   └── database/                 # Database transaction invariants
│       └── test_database_invariants.py
├── security/                     # Security validation tests
│   ├── test_input_validation.py  # OWASP Top 10 payloads
│   ├── test_authorization.py     # 4x4 maturity/complexity matrix
│   └── test_authentication.py    # JWT, OAuth, password hashing
├── coverage_reports/             # Coverage reports and trending
│   ├── html/                     # HTML coverage report (index.html)
│   ├── metrics/                  # Coverage JSON snapshots
│   │   └── coverage.json         # Current coverage data
│   └── trends/                   # Historical coverage trends
│       ├── coverage_trend.json   # Aggregated trend data
│       └── README.md             # Trend data documentation
├── docs/                         # Test documentation guides
│   ├── COVERAGE_GUIDE.md         # Coverage interpretation
│   ├── TEST_ISOLATION_PATTERNS.md # Isolation patterns
│   └── FLAKY_TEST_GUIDE.md       # Flaky test prevention
└── README.md                     # This file
```

---

## Fixtures and Utilities

### unique_resource_name

**Purpose**: Generate collision-free resource names for parallel execution.

**Usage**:
```python
def test_create_agent(unique_resource_name):
    agent = AgentRegistry(
        id=unique_resource_name,  # "test_gw0_a1b2c3d4"
        name="Test Agent"
    )
    db.add(agent)
    db.commit()
    # No collision with parallel tests
```

**Implementation**: Combines worker ID (`PYTEST_XDIST_WORKER_ID`) with UUID.

**See**: [TEST_ISOLATION_PATTERNS.md](./docs/TEST_ISOLATION_PATTERNS.md) for details.

---

### db_session

**Purpose**: Database session with automatic transaction rollback.

**Usage**:
```python
def test_agent_deletion(db_session, unique_resource_name):
    agent = AgentFactory.create(_session=db_session, id=unique_resource_name)
    db_session.delete(agent)
    db_session.commit()
    # Automatic rollback - no cleanup needed
```

**Benefits**:
- No manual cleanup
- No shared state between tests
- Fast (rollback is instant)
- Safe for parallel execution

**See**: [TEST_ISOLATION_PATTERNS.md](./docs/TEST_ISOLATION_PATTERNS.md) for details.

---

### Factories

**Purpose**: Dynamic test data generation with unique values.

**Usage**:
```python
from tests.factories import AgentFactory, UserFactory

# Create with defaults
agent = AgentFactory.create()

# Override specific fields
agent = AgentFactory.create(
    status="STUDENT",
    confidence=0.4
)

# Create multiple
agents = AgentFactory.create_batch(5)

# Build without persistence
agent = AgentFactory.build()  # Not in database
```

**Available Factories**:
- `AgentFactory` - AgentRegistry instances
- `UserFactory` - User instances
- `EpisodeFactory` / `EpisodeSegmentFactory` - Episodic memory data
- `AgentExecutionFactory` - Execution records with timing
- `CanvasAuditFactory` - Canvas interaction records

**See**: [factories/README.md](./factories/README.md) for complete guide.

---

## Coverage Reports

### HTML Report

**Location**: `tests/coverage_reports/html/index.html`

**Usage**:
```bash
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html
open tests/coverage_reports/html/index.html
```

**Features**:
- Click directory/file to drill down
- Red lines = not executed
- Yellow lines = partially executed (branch coverage)
- Green lines = fully executed

---

### JSON Report

**Location**: `tests/coverage_reports/metrics/coverage.json`

**Usage**:
```bash
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json

# Extract coverage percentage
jq '.totals.percent_covered' tests/coverage_reports/metrics/coverage.json
```

**Format**: Standard pytest-cov JSON output with file-by-file breakdown.

---

### Coverage Trending

**Location**: `tests/coverage_reports/trends/coverage_trend.json`

**Usage**:
```bash
# View trend
jq '.coverage_history[] | .date + ": " + (.overall_percent | tostring) + "%"' \
  tests/coverage_reports/trends/coverage_trend.json

# Detect regression
LATEST=$(jq '.coverage_history[0].overall_percent' coverage_trend.json)
PREVIOUS=$(jq '.coverage_history[1].overall_percent' coverage_trend.json)
if (( $(echo "$LATEST < $PREVIOUS" | bc -l) )); then
    echo "Coverage regression: $PREVIOUS% → $LATEST%"
fi
```

**See**: [trends/README.md](./coverage_reports/trends/README.md) for details.

---

### Terminal Report

**Usage**:
```bash
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=term-missing
```

**Output**:
```
Name                                         Stmts   Miss  Cover   Missing
------------------------------------------------------------------------
core/agent_governance_service.py               150     75    50%   23-45, 89-102
core/models.py                                 300    120    60%   156-189, 234-267
api/auth_routes.py                              50     40    20%   12-35, 67-89
------------------------------------------------------------------------
TOTAL                                          500    235    53%
```

---

## Common Tasks

### Run Tests for Specific Domain

```bash
# Governance domain
pytest tests/unit/governance/ -v

# Security domain
pytest tests/security/ -v

# Episodic memory
pytest tests/unit/episodes/ -v

# Property tests (invariant validation)
pytest tests/property_tests/ -v
```

---

### Run Tests in Parallel

```bash
# Auto-detect CPU cores
pytest tests/ -n auto -v

# Specify number of workers
pytest tests/ -n 4 -v

# Group by module (reduces database lock contention)
pytest tests/ -n auto --dist loadscope
```

**Speedup**: ~2-4x faster than sequential execution.

---

### Generate Coverage Report

```bash
# HTML report (detailed, interactive)
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html
open tests/coverage_reports/html/index.html

# JSON report (for CI/CD)
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json

# Terminal report (quick overview)
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=term-missing
```

---

### Run Flaky Test Detection

```bash
# Retry failed tests up to 3 times
pytest tests/ --reruns 3

# Run tests 10 times to detect flakiness
for i in {1..10}; do
    pytest tests/test_agent.py -v
done
```

**See**: [FLAKY_TEST_GUIDE.md](./docs/FLAKY_TEST_GUIDE.md) for flaky test debugging.

---

### Debug Test Failures

```bash
# Run with pdb on failure
pytest tests/test_agent.py::test_agent_creation -v --pdb

# Show print statements
pytest tests/test_agent.py::test_agent_creation -v -s

# Stop on first failure
pytest tests/ -v -x

# Run last failed tests
pytest tests/ -v --lf
```

---

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'core'`

**Solution**: Check PYTHONPATH or run tests from backend directory.
```bash
export PYTHONPATH=/Users/rushiparikh/projects/atom/backend:$PYTHONPATH
pytest tests/ -v
```

---

### Database Errors

**Problem**: Tests fail with database errors or lock contention.

**Solution**: Use `db_session` fixture for automatic rollback.
```python
def test_agent_creation(db_session, unique_resource_name):
    agent = AgentFactory.create(_session=db_session)
    # Automatic cleanup, no lock issues
```

**See**: [TEST_ISOLATION_PATTERNS.md](./docs/TEST_ISOLATION_PATTERNS.md) for database isolation patterns.

---

### Flaky Tests

**Problem**: Tests pass locally but fail in CI (or vice versa).

**Solution**: Check for:
- Race conditions (use explicit synchronization)
- Shared state (use db_session, unique_resource_name)
- Time dependencies (mock with freezegun)
- External dependencies (mock APIs)

**See**: [FLAKY_TEST_GUIDE.md](./docs/FLAKY_TEST_GUIDE.md) for debugging steps.

---

### Coverage Not Updating

**Problem**: Coverage report shows old data.

**Solution**: Delete `.coverage` file and regenerate.
```bash
rm backend/.coverage
pytest backend/tests/ --cov=core --cov=api --cov=tools --cov-report=html
```

---

### Tests Timeout in CI

**Problem**: Tests take too long in CI/CD.

**Solution**: Run tests in parallel and optimize slow tests.
```bash
pytest tests/ -n auto -v  # Parallel execution
pytest tests/ -m "not slow" -v  # Exclude slow tests
```

---

## Coverage Targets

| Domain | Target | Current | Priority |
|--------|--------|---------|----------|
| Governance | 80% | 13.37% | P0 |
| Security | 80% | 22.40% | P0 |
| Episodes | 80% | 15.52% | P1 |
| Core backend | 80% | 15.57% | P1 |

**Overall Target**: 80% coverage across all domains.

**See**: [COVERAGE_GUIDE.md](./docs/COVERAGE_GUIDE.md) for coverage interpretation and improvement strategies.

---

## Related Documentation

### Test Guides
- **[COVERAGE_GUIDE.md](./docs/COVERAGE_GUIDE.md)** - Coverage report interpretation and improvement
- **[TEST_ISOLATION_PATTERNS.md](./docs/TEST_ISOLATION_PATTERNS.md)** - Test isolation patterns and examples
- **[FLAKY_TEST_GUIDE.md](./docs/FLAKY_TEST_GUIDE.md)** - Flaky test prevention and fixing

### Property Tests
- **[property_tests/INVARIANTS.md](./property_tests/INVARIANTS.md)** - 66 documented invariants across 7 domains
- **[property_tests/README.md](./property_tests/README.md)** - Property testing guide

### Factories
- **[factories/README.md](./factories/README.md)** - Test data factory usage and patterns

### General Testing
- **[TESTING_GUIDE.md](./TESTING_GUIDE.md)** - Comprehensive testing infrastructure documentation

---

## CI/CD Integration

GitHub Actions runs tests automatically:

1. **Push to main**: Full test suite with coverage
2. **Pull Request**: Full test suite with coverage enforcement
3. **Coverage Report**: Automatic trending and regression detection
4. **Artifacts**: Coverage reports retained for 30 days

**Workflow**: `.github/workflows/coverage-report.yml`

**See**: [coverage-report.yml](../.github/workflows/coverage-report.yml) for CI/CD configuration.

---

## Summary

**Quick Start**:
```bash
# Run all tests with coverage
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html -n auto

# View coverage report
open tests/coverage_reports/html/index.html
```

**Key Concepts**:
- **Parallel execution**: Use `-n auto` for faster test runs
- **Coverage**: Track coverage over time to detect regressions
- **Isolation**: Use `unique_resource_name` and `db_session` for parallel-safe tests
- **Factories**: Use factories for dynamic, isolated test data
- **Property tests**: Use Hypothesis for invariant validation

**Next Steps**:
1. Run tests for your domain: `pytest tests/unit/[domain]/ -v`
2. Check coverage: `pytest tests/ --cov=core --cov-report=html`
3. Improve coverage gaps identified in HTML report
4. Add property tests for critical invariants
5. Monitor coverage trends in `coverage_trend.json`

---

*Last Updated: 2026-02-11*

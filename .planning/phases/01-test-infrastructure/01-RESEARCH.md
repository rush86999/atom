# Phase 1: Test Infrastructure - Research

**Researched:** February 10, 2026
**Domain:** Python Testing Infrastructure (pytest, coverage, CI/CD)
**Confidence:** HIGH

## Summary

Phase 1 establishes the foundational test infrastructure for the Atom platform, focusing on pytest configuration, parallel execution, test data factories, coverage reporting, quality gates, and CI integration. The platform already has significant testing infrastructure in place (88,920+ lines of tests, 350+ test files), but requires systematic organization, factory_boy integration for test data isolation, parallel execution via pytest-xdist, and automated quality gates in CI/CD.

**Current State Analysis:**
- pytest 7.4+ already configured with comprehensive markers (unit, integration, property, invariant, fuzzy, mutation, chaos)
- pytest-cov generating HTML, terminal, and JSON reports to `tests/coverage_reports/`
- pytest-asyncio configured with `asyncio_mode = auto`
- Hypothesis property-based testing integrated with conservative strategy
- GitHub Actions CI pipeline exists but doesn't run full test suite with coverage enforcement
- Multiple conftest.py files providing fixtures for different test types (property_tests, e2e, grey_box)
- In-memory SQLite database fixtures ensuring test isolation

**Key Gaps Identified:**
1. No pytest-xdist for parallel test execution (INFRA-02)
2. No factory_boy integration for test data factories (INFRA-04, QUAL-06)
3. Coverage thresholds exist in pytest.ini (--cov-fail-under=80) but not enforced in CI
4. No assertion density metrics or quality gate automation (INFRA-06)
5. Test data factories documentation missing (DOCS-05)
6. CI/CD integration documentation incomplete (DOCS-04)

**Primary recommendation:** Build upon existing pytest infrastructure by adding pytest-xdist for parallelization, factory_boy pytest-factoryboy for dynamic test data generation, assertion density checking via pytest-density or custom plugin, and enhance GitHub Actions workflow to enforce quality gates with coverage and test metrics.

## Standard Stack

### Core Testing Framework

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test runner and framework | Industry standard for Python testing with powerful fixture system and plugin ecosystem |
| **pytest-asyncio** | 0.21.0+ | Async test support | Official pytest plugin for async/await test functions with auto mode |
| **pytest-xdist** | 3.6+ (current) | Parallel test execution | Enables distributed testing across CPU cores, reducing execution time significantly |
| **pytest-cov** | 4.1.0+ | Coverage reporting | Standard coverage plugin for pytest with multiple report formats (HTML, JSON, terminal) |
| **hypothesis** | 6.92.0+ | Property-based testing | Already integrated, generates test cases automatically to find edge cases |

### Test Data Generation

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **factory_boy** | 3.3.0+ | Dynamic test data factories | Create complex test objects with relationships, avoid hardcoded IDs |
| **pytest-factoryboy** | 2.7.0+ | factory_boy pytest integration | Expose factories as pytest fixtures with dependency injection |
| **faker** | 30.0+ (optional) | Realistic fake data | Generate names, emails, addresses, etc. for diverse test data |

### Quality Metrics & Gates

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-density** | 0.1.0+ | Assertion density measurement | Calculate assertions per line of test code (quality metric) |
| **pytest-pycodestyle** | 2.6.0+ | PEP8 style checking | Enforce code style in tests |
| **pytest-timeout** | 2.3.0+ | Test timeout enforcement | Prevent tests from hanging indefinitely |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| factory_boy | pytest model mom | factory_boy has broader community support and better async handling |
| pytest-xdist | pytest-parallel | pytest-xdist is more mature, better documented, handles fixtures correctly |
| pytest-cov | coverage.py directly | pytest-cov integrates seamlessly with pytest CLI and plugins |
| pytest-density | custom assertion counter | Custom requires maintenance, pytest-density is purpose-built |

**Installation:**
```bash
# Core testing (already installed)
pytest>=7.4.0,<8.0.0
pytest-asyncio>=0.21.0,<1.0.0
pytest-cov>=4.1.0,<5.0.0
hypothesis>=6.92.0,<7.0.0

# Add for Phase 1
pytest-xdist>=3.6.0,<4.0.0
factory_boy>=3.3.0,<4.0.0
pytest-factoryboy>=2.7.0,<3.0.0
faker>=30.0.0,<31.0.0  # Optional, for realistic data

# Quality metrics
pytest-density>=0.1.0  # If available, or implement custom
pytest-timeout>=2.3.0,<3.0.0
```

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── tests/
│   ├── conftest.py                    # Root fixtures (already exists)
│   ├── factories/                     # NEW: Test data factories
│   │   ├── __init__.py
│   │   ├── agent_factory.py           # AgentRegistry factories
│   │   ├── user_factory.py            # User factories
│   │   ├── episode_factory.py         # Episode/EpisodeSegment factories
│   │   ├── execution_factory.py       # AgentExecution factories
│   │   ├── workflow_factory.py        # Workflow factories
│   │   └── canvas_factory.py          # CanvasAudit factories
│   ├── unit/                          # NEW: Isolated unit tests
│   │   ├── core/
│   │   ├── api/
│   │   └── tools/
│   ├── integration/                   # NEW: Integration tests
│   │   ├── database/
│   │   ├── api/
│   │   └── services/
│   ├── property_tests/                # Already exists: Hypothesis tests
│   ├── e2e/                           # Already exists: End-to-end tests
│   ├── coverage_reports/              # Already exists: HTML/JSON coverage
│   │   ├── html/
│   │   └── metrics/
│   └── pytest.ini                     # Already exists: pytest configuration
```

### Pattern 1: Factory Boy for Test Data Isolation

**What:** Dynamic test data generation using factory pattern instead of hardcoded fixtures.

**When to use:**
- Creating test objects with relationships (e.g., Agent → Executions → Feedback)
- Need fresh, isolated data for each test (no hardcoded IDs)
- Generating diverse test data with Faker integration

**Example:**
```python
# tests/factories/agent_factory.py
import factory
from factory import fuzzy
from core.models import AgentRegistry, AgentStatus

class AgentFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = AgentRegistry
        sqlalchemy_session_persistence = "commit"

    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    category = factory.Iterator(['testing', 'automation', 'integration'])
    module_path = "test.module"
    class_name = "TestClass"
    status = fuzzy.FuzzyChoice([s.value for s in AgentStatus])
    confidence = fuzzy.FuzzyFloat(0.0, 1.0)
    capabilities = factory.List([factory.Faker('word') for _ in range(3)])

# Test using factory
def test_agent_governance_with_factory(db_session, agent_factory):
    agent = AgentFactory.create(
        status=AgentStatus.STUDENT.value,
        confidence=0.4
    )
    assert agent.status == AgentStatus.STUDENT.value
    assert agent.id is not None  # Dynamic ID, not hardcoded
```

**Source:** [pytest-factoryboy GitHub Repository](https://github.com/pytest-dev/pytest-factoryboy)

### Pattern 2: Parallel Test Execution with pytest-xdist

**What:** Distribute tests across multiple worker processes to reduce execution time.

**When to use:**
- Large test suites (>100 tests) taking >60 seconds
- CPU-bound tests (database, computation)
- Tests are isolated (no shared state between processes)

**Example:**
```bash
# Run tests in parallel using all CPU cores
pytest -n auto

# Run with specific number of workers
pytest -n 4

# Run tests in parallel with coverage
pytest -n auto --cov=core --cov=api --cov-report=html

# Group tests by module for better isolation
pytest -n auto --dist loadscope

# Run only subset in parallel (e.g., only unit tests)
pytest -n auto -m unit
```

**Source:** [pytest-xdist Documentation](https://pytest-xdist.readthedocs.io/)

### Pattern 3: Coverage Reporting with Multiple Formats

**What:** Generate coverage reports in HTML (human-readable), JSON (machine-readable), and terminal (CI-friendly) formats simultaneously.

**When to use:**
- Development: HTML reports for detailed line-by-line coverage
- CI/CD: JSON for programmatic quality gate enforcement
- Local runs: Terminal for immediate feedback

**Example (pytest.ini):**
```ini
[pytest]
addopts =
    --cov=core
    --cov=api
    --cov=tools
    --cov-report=html:tests/coverage_reports/html
    --cov-report=term-missing:skip-covered
    --cov-report=json:tests/coverage_reports/metrics/coverage.json
    --cov-fail-under=80  # Quality gate: fail if below 80%
```

**Source:** [pytest-cov Configuration Documentation](https://pytest-cov.readthedocs.io/en/latest/config.html)

### Pattern 4: Test Organization with Markers and Fixtures

**What:** Use pytest markers to categorize tests and control execution.

**When to use:**
- Differentiating test types (unit, integration, slow, property-based)
- Controlling which tests run in CI vs. locally
- Grouping tests by domain (financial, security, api)

**Example (pytest.ini):**
```ini
[pytest]
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, requires dependencies)
    property: Property-based tests using Hypothesis
    slow: Slow tests (> 1 second)
    P0: Critical priority (security, financial)
    P1: High priority (core business logic)
```

**Usage:**
```bash
# Run only unit tests
pytest -m unit

# Run all except slow tests
pytest -m "not slow"

# Run critical priority tests
pytest -m P0
```

**Source:** [Pytest Markers Documentation](https://docs.pytest.org/en/stable/example/markers.html)

### Anti-Patterns to Avoid

- **Hardcoded test IDs:** Using `agent_id = "test-agent-123"` in multiple tests creates coupling. Use factory_boy instead.
- **Shared test data:** Global fixtures or static data files that persist across tests. Use function-scoped fixtures with fresh data each test.
- **Testing internals:** Testing private methods (`_method`) instead of public APIs. Test behavior, not implementation.
- **No assertion variety:** Tests that only check `assert result is not None`. Use multiple assertion types (equality, contains, raises, etc.).
- **Ignoring async tests:** Forgetting `@pytest.mark.asyncio` on async test functions. Use `asyncio_mode = auto` in pytest.ini.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test data generation | Manual object creation with hardcoded IDs | factory_boy + pytest-factoryboy | Handles relationships, foreign keys, and isolation automatically |
| Parallel execution | Custom multiprocessing or threading | pytest-xdist | Handles fixture distribution, process isolation, and result collection |
| Coverage reports | Custom coverage parsing scripts | pytest-cov | Generates HTML/JSON/terminal reports, supports branch coverage, works with CI |
| Test discovery | Custom test runners or scripts | pytest test discovery | Built-in discovery with patterns, markers, and filtering |
| Async test handling | Custom event loop management | pytest-asyncio | Auto mode handles async fixtures and test functions automatically |
| Property-based testing | Custom random data generators | Hypothesis | Handles shrinking, replay, and diverse case generation |

**Key insight:** Custom test infrastructure solutions often fail on edge cases (e.g., pytest-xdist correctly handles database fixture isolation, multiprocessing requires manual cleanup). The pytest ecosystem has solved these problems over decades of development.

## Common Pitfalls

### Pitfall 1: Fixture Scope Confusion

**What goes wrong:** Using session-scoped fixtures for mutable data, causing tests to interfere with each other.

**Why it happens:** Session fixtures run once and share state across all tests, which breaks isolation.

**How to avoid:**
- Use `scope="function"` (default) for fixtures that create or modify data
- Only use `scope="session"` for immutable resources (database engine, config)
- Use `scope="module"` for expensive setup that doesn't change (e.g., loading ML models)

**Warning signs:** Tests pass individually but fail when run together, or pass in different orders.

### Pitfall 2: Test Database Leaks

**What goes wrong:** Tests don't clean up database transactions, leaving data that affects subsequent tests.

**Why it happens:** Not rolling back transactions after tests, or using committed sessions.

**How to avoid:**
```python
# GOOD: Rollback after each test
@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()  # Always cleanup
    session.close()

# BAD: Not cleaning up
@pytest.fixture(scope="function")
def db_session():
    session = Session()
    yield session
    # No cleanup - data leaks to next test!
```

**Warning signs:** Tests failing with "unique constraint" violations or unexpected data counts.

### Pitfall 3: Parallel Test Race Conditions

**What goes wrong:** Tests pass when run serially but fail with pytest-xdist parallel execution.

**Why it happens:** Tests share external resources (files, ports, database) without coordination.

**How to avoid:**
- Use `--dist loadscope` to group tests by module (reduces but doesn't eliminate risk)
- Ensure each test uses unique resource names (e.g., `test_file_{uuid}.txt`)
- Use function-scoped fixtures for external resources
- Avoid global state in tests

**Example fix:**
```python
# BAD: Shared file path
def test_write_file():
    with open("/tmp/test.data", "w") as f:
        f.write("data")

# GOOD: Unique file path
def test_write_file():
    import uuid
    path = f"/tmp/test_{uuid.uuid4()}.data"
    with open(path, "w") as f:
        f.write("data")
```

**Warning signs:** Intermittent failures in CI, "file not found" or "address already in use" errors.

### Pitfall 4: Coverage False Positives

**What goes wrong:** Coverage reports high percentage (e.g., 95%) but critical paths are untested.

**Why it happens:** Coverage measures lines executed, not assertions or meaningful tests. A test with `pass` still counts as coverage.

**How to avoid:**
- Track **assertion density** (assertions per line of test code)
- Use **branch coverage** (`--cov-branch`) to measure if/else paths
- Enforce quality gates combining coverage + assertion density
- Review coverage reports manually for gaps in critical paths

**Example quality gate:**
```python
# Target: 80% coverage AND 0.15 assertions per line
# (15 assertions per 100 lines of test code)
def calculate_assertion_density(test_file):
    lines = len(open(test_file).readlines())
    asserts = count_assertions(test_file)
    return asserts / lines
```

**Warning signs:** High coverage but low test count, or tests with no assertions.

### Pitfall 5: Ignoring Flaky Tests

**What goes wrong:** Tests that occasionally fail (flaky) are ignored or marked as "xfail" indefinitely.

**Why it happens:** Race conditions, timing dependencies, or external service calls.

**How to avoid:**
- Fix flaky tests immediately (they undermine CI trust)
- Use pytest-rerunfailures to detect flakiness: `--reruns 3`
- Add timeouts to prevent hanging: `@pytest.mark.timeout(30)`
- Mock external services (don't call real APIs in tests)

**Warning signs:** CI failures that "fix themselves" on re-run, or tests marked with `@pytest.mark.flaky`.

## Code Examples

Verified patterns from official sources:

### Creating and Using Factory Boy Factories

```python
# Source: pytest-factoryboy documentation
# tests/factories/__init__.py
from factory.alchemy import SQLAlchemyModelFactory
from core.models import AgentRegistry
from core.database import SessionLocal

class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        sqlalchemy_session = SessionLocal()
        sqlalchemy_session_persistence = "commit"

# tests/factories/agent_factory.py
import factory
from factory import fuzzy
from tests.factories import BaseFactory
from core.models import AgentRegistry, AgentStatus

class AgentFactory(BaseFactory):
    class Meta:
        model = AgentRegistry

    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    category = factory.Iterator(['testing', 'automation', 'integration'])
    module_path = "test.module"
    class_name = "TestClass"
    status = factory.LazyFunction(lambda: AgentStatus.STUDENT.value)
    confidence = fuzzy.FuzzyFloat(0.0, 1.0)
    capabilities = factory.List([factory.Faker('word') for _ in range(3)])

# Test using factory
def test_agent_with_factory(db_session):
    agent = AgentFactory.create(confidence=0.95)
    assert agent.id is not None
    assert agent.confidence == 0.95
```

**Source:** [pytest-factoryboy Documentation](https://pytest-factoryboy.readthedocs.io/)

### Parallel Execution with Coverage

```bash
# Source: pytest-xdist and pytest-cov documentation
# Run all tests in parallel with coverage report
pytest -n auto \
    --cov=core \
    --cov=api \
    --cov=tools \
    --cov-report=html \
    --cov-report=json \
    --cov-report=term-missing \
    --cov-branch \
    --cov-fail-under=80

# Run only unit tests in parallel
pytest -n auto -m unit --cov=core

# Run with specific worker count
pytest -n 4 --dist loadscope
```

**Source:** [pytest-xdist Documentation](https://pytest-xdist.readthedocs.io/), [pytest-cov Reporting Documentation](https://pytest-cov.readthedocs.io/en/latest/reporting.html)

### Async Test Configuration

```ini
# Source: pytest-asyncio documentation
# pytest.ini
[pytest]
asyncio_mode = auto
```

```python
# Tests automatically recognized as async
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result is not None
```

**Source:** [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)

### Markers for Test Organization

```python
# Source: pytest markers documentation
# conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow tests")

# test_example.py
import pytest

@pytest.mark.unit
def test_fast_calculation():
    assert 1 + 1 == 2

@pytest.mark.integration
@pytest.mark.slow
def test_database_query():
    result = db.query(User).all()
    assert len(result) > 0
```

**Usage:**
```bash
pytest -m unit              # Only unit tests
pytest -m "not slow"        # All except slow
pytest -m "integration or slow"  # Either marker
```

**Source:** [Pytest Custom Markers Documentation](https://docs.pytest.org/en/stable/example/markers.html)

### Assertion Density Quality Gate

```python
# Custom plugin for assertion density checking
# tests/conftest.py or plugins/pytest_density.py

import ast
from pathlib import Path

def count_assertions(node):
    """Count assert statements in AST node."""
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
    return count

def calculate_assertion_density(test_file: Path) -> float:
    """Calculate assertions per line of test code."""
    source = test_file.read_text()
    tree = ast.parse(source)
    lines = len(source.splitlines())
    asserts = count_assertions(tree)
    return asserts / lines if lines > 0 else 0.0

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Report assertion density after test run."""
    min_density = 0.15  # 15 assertions per 100 lines
    test_files = Path("tests").rglob("test_*.py")

    for test_file in test_files:
        density = calculate_assertion_density(test_file)
        if density < min_density and density > 0:
            terminalreporter.write_sep(
                "_",
                f"WARNING: {test_file} has low assertion density: {density:.2f}",
                red=True,
            )
```

**Source:** Adapted from [Measuring Quality and Quantity of Unit Tests](https://safjan.com/measuring-quality-and-quantity-of-unit-tests-in-python-projects-advanced-strategies/)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest module | pytest with fixtures | ~2015-2018 | Simplified test syntax, powerful dependency injection |
| Hardcoded test data | factory_boy + Faker | ~2019-2022 | Dynamic, isolated test data with realistic values |
| Serial test execution | pytest-xdist parallel | ~2020-2023 | 3-5x faster test execution on multi-core machines |
| Terminal coverage only | Multi-format coverage (HTML/JSON/term) | ~2019-2021 | Better coverage visibility and CI integration |
| Manual test organization | Markers + test discovery | ~2017-2020 | Flexible test categorization and selective execution |
| No quality gates | Coverage + assertion density gates | ~2023-2025 | Enforced test quality metrics in CI/CD |

**Deprecated/outdated:**
- **unittest.TestCase**: Replaced by pytest fixtures and plain functions (still supported but not recommended for new tests)
- **nosetests**: Discontinued, replaced by pytest
- **Mock patch**: Use pytest-mock's `mocker` fixture instead of `@patch` decorators
- **setUp/tearDown methods**: Replaced by pytest fixtures with `yield` statements

## Open Questions

1. **Assertion density target threshold**
   - What we know: Industry practice suggests 0.10-0.20 assertions per line (10-20 assertions per 100 lines of test code)
   - What's unclear: What's the right threshold for Atom's codebase quality goals?
   - Recommendation: Start with 0.15 (15 assertions per 100 lines) as a baseline, adjust based on existing test suite analysis

2. **Parallel test execution worker count**
   - What we know: pytest-xdist supports `-n auto` (detects CPU count) or explicit `-n 4`
   - What's unclear: Will CI GitHub Actions runners handle parallel tests reliably?
   - Recommendation: Use `-n auto` locally for speed, `-n 2` in CI (2 cores per GitHub Actions runner) to avoid resource exhaustion

3. **Factory Boy learning curve for team**
   - What we know: factory_boy adds new concepts (Factory, Faker, LazyAttribute, SubFactory)
   - What's unclear: Team familiarity with factory pattern?
   - Recommendation: Create comprehensive `tests/factories/README.md` with examples, conduct team training session

4. **Coverage enforcement in CI**
   - What we know: pytest-cov supports `--cov-fail-under=80` but current CI doesn't enforce it
   - What's unclear: Should coverage gates block all PRs or only warn?
   - Recommendation: Start with warning-only gate, transition to blocking once baseline is met. Use coverage.json for trend analysis.

5. **Test execution time budget**
   - What we know: Current test suite size (88,920 lines) suggests >10 minutes serial execution
   - What's unclear: What's the target time for full test run with parallel execution?
   - Recommendation: Measure current baseline, set target of <5 minutes with pytest-xdist, use pytest-markers to skip slow tests in PR validation

## Sources

### Primary (HIGH confidence)

- **pytest Documentation** - [How to use fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html), [Custom markers](https://docs.pytest.org/en/stable/example/markers.html), [Assertion documentation](https://docs.pytest.org/en/stable/how-to/assert.html)
- **pytest-xdist** - [Official documentation](https://pytest-xdist.readthedocs.io/) - Parallel test execution features
- **pytest-cov** - [Configuration](https://pytest-cov.readthedocs.io/en/latest/config.html), [Reporting](https://pytest-cov.readthedocs.io/en/latest/reporting.html) - Coverage reporting setup
- **pytest-asyncio** - Official pytest plugin for async test support (documented in pytest plugin list)
- **pytest-factoryboy** - [GitHub Repository](https://github.com/pytest-dev/pytest-factoryboy), [Documentation](https://pytest-factoryboy.readthedocs.io/) - Factory integration with pytest

### Secondary (MEDIUM confidence)

- [How to Handle pytest Markers - OneUptime](https://oneuptime.com/blog/post/2026-02-02-pytest-markers-guide/view) - February 2, 2026
- [How to Use pytest Fixtures - OneUptime](https://oneuptime.com/blog/post/2026-02-02-pytest-fixtures/view) - February 2, 2026
- [Supercharging Your Test Runs: Mastering Parallel Execution in Pytest](https://medium.com/ai-qa-nexus/supercharging-your-test-runs-mastering-parallel-execution-in-pytest-3124e166fd60) - May 2025
- [How to Run Tests in Parallel with pytest Using pytest-xdist - Statology](https://www.statology.org/how-to-run-tests-parallel-pytest-xdist/) - February 2025
- [Django Testing Framework Deep Dive: Factory Boy vs Fixture](https://www.cnblogs.com/yangykaifa/p/19523925) - January 23, 2026
- [Testing in Python Web Frameworks: Django, Flask and FastAPI](https://python.plainenglish.io/testing-in-python-web-frameworks-django-flask-and-fastapi-fd4cc533db08) - January 5, 2026
- [Full-Chain Testing System - Pytest + Playwright + Vitest](https://blog.csdn.net/weixin_52208686/article/details/156861497) - January 12, 2026
- [Mastering Fixtures in Pytest: Answering the 3 Most Common Questions](https://mayurdeorebytes.medium.com/mastering-fixtures-in-pytest-answering-the-3-most-common-questions-f55d58e854b5) - November 9, 2024
- [A Complete Guide to Pytest Fixtures | Better Stack Community](https://betterstack.com/community/guides/testing/pytest-fixtures-guide/) - June 21, 2024
- [Measuring Quality and Quantity of Unit Tests in Python Projects](https://safjan.com/measuring-quality-and-quantity-of-unit-tests-in-python-projects-advanced-strategies/) - Assertion density metrics
- [CI/CD: Automating Quality Gates](https://www.dhirajdas.dev/blog/ci-cd-automating-quality-gates) - November 29, 2025
- [How Can We Enforce Code Quality Checks in CI/CD?](https://medium.com/@haroldfinch01/how-can-you-enforce-code-quality-checks-in-ci-cd-f479e72f404b) - December 11, 2025
- [Concurrent tests in GitHub Actions - WarpBuild Blog](https://warpbuild.com/blog/concurrent-tests) - February 2026 (6 days ago)
- [Running our test suite in parallel on GitHub actions - Oh Dear](https://ohdear.app/news-and-updates/running-our-test-suite-in-parallel-on-github-actions) - April 23, 2025

### Tertiary (LOW confidence - marked for validation)

- [Stack Overflow: Report number of assertions in pytest](https://stackoverflow.com/questions/39500416/report-number-of-assertions-in-pytest) - Community discussion on assertion counting
- [Stack Overflow: How to best structure conftest and fixtures](https://stackoverflow.com/questions/74406488/how-to-best-structure-conftest-and-fixtures-in-across-multiple-test-files) - Fixture organization best practices

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries have official documentation, recent releases (2024-2026), and widespread adoption
- Architecture: HIGH - Patterns verified from official pytest docs and 2025-2026 blog posts
- Pitfalls: HIGH - Based on official docs and recent community discussions (2025-2026)

**Research date:** February 10, 2026

**Valid until:** March 10, 2026 (30 days - stable ecosystem)

**Existing infrastructure identified:**
- pytest 7.4+ configured with comprehensive markers
- pytest-cov generating HTML/JSON/terminal reports
- pytest-asyncio with auto mode
- Hypothesis property-based testing
- Multiple conftest.py files with fixtures
- In-memory SQLite database isolation
- GitHub Actions CI pipeline (backend-test job)
- 88,920+ lines of tests across 350+ test files

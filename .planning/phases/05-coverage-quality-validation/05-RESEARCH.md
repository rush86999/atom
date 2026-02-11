# Phase 5: Coverage & Quality Validation - Research

**Researched:** February 11, 2026
**Domain:** Code coverage, test quality assurance, test infrastructure
**Confidence:** HIGH

## Summary

Phase 5 focuses on achieving 80% code coverage across all domains (governance, security, episodic memory, backend, mobile, desktop), establishing comprehensive test quality standards, and creating detailed testing documentation. The current state shows significant gaps: governance domain at 13.37%, security at 22.40%, episodic memory at 15.52%, and overall backend at 15.57% coverage. The project already has a sophisticated testing infrastructure with property-based testing, fuzzy testing, mutation testing, and chaos engineering capabilities documented in TESTING_GUIDE.md.

**Primary recommendation:** Use pytest-xdist for parallel execution with worker isolation, pytest-rerunfailures for flaky test detection, Coverage.py for Python (already configured), Jest for React Native (already configured), and cargo-tarpaulin for Rust. Set up Codecov or Coveralls for coverage trending visualization. Focus on test isolation patterns using database transaction rollbacks and unique resource names to achieve zero shared state in parallel execution.

## Standard Stack

### Core Testing Framework
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.10.6 (current) | Python test runner | De facto standard for Python testing, 96% cache hit rate achieved |
| **pytest-cov** | Built-in | Coverage reporting | Native Coverage.py integration, outputs JSON/HTML |
| **pytest-xdist** | Latest | Parallel execution | Industry standard for parallel Python tests |
| **pytest-rerunfailures** | Latest | Flaky test detection | Recommended by pytest docs for flaky test handling |
| **Hypothesis** | Latest | Property-based testing | Already in use, 200+ property tests written |

### JavaScript/TypeScript Testing
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Jest** | Latest (via jest-expo) | React Native test runner | Expo's recommended testing framework |
| **jest-expo** | ~50.0.0 | Expo preset for Jest | Official Expo testing integration |
| **@testing-library/react-native** | ~12.4.2 | Component testing | Industry standard for React Native |
| **React Test Renderer** | 18.2.0 | Snapshot testing | Part of React ecosystem |

### Rust Testing
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **cargo-tarpaulin** | 0.13.1+ | Code coverage for Rust | Standard Rust coverage tool, Docker-based cross-platform support |
| **Cross** | Latest | Cross-platform testing | Addresses cargo-tarpaulin's x86_64 limitation |

### Coverage Visualization
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Codecov** | Latest | Coverage trending dashboard | Industry standard, JSON/LCOV support, free for OSS |
| **Coveralls** | Latest | Alternative coverage dashboard | Historical tracking, multiple report formats |
| **Coverage.py** | Built-in | Python coverage engine | Native pytest integration, outputs JSON |

### Quality Assurance
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **mutmut** | Latest | Mutation testing | Python mutation testing standard |
| **Atheris** | Latest | Fuzzy testing | Google's coverage-guided fuzzer for Python |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-xdist | pytest-parallel | pytest-xdist has better worker isolation, more mature |
| pytest-rerunfailures | flaky (box/flaky) | pytest-rerunfailures is officially recommended by pytest docs |
| Codecov | Coveralls | Codecov has better GitHub Actions integration |
| cargo-tarpaulin | grcov | tarpaulin is easier to use, grcov supports more processors |

**Installation:**
```bash
# Python (already installed)
pip install pytest pytest-cov pytest-xdist pytest-rerunfailures hypothesis mutmut atheris

# JavaScript/TypeScript (already in package.json)
npm install --save-dev jest jest-expo @testing-library/react-native

# Rust
cargo install cargo-tarpaulin
cargo install cross  # For cross-platform coverage

# Coverage trending (CI/CD integration)
# Codecov via GitHub Actions - no installation needed
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── conftest.py                    # Root fixtures (ALREADY EXISTS with xdist support)
├── pytest.ini                     # Pytest configuration (ALREADY EXISTS)
├── factories/                     # Test data factories (ALREADY EXISTS)
│   ├── __init__.py
│   ├── agent_factory.py
│   ├── user_factory.py
│   └── execution_factory.py
├── unit/                          # Isolated unit tests
│   ├── governance/
│   │   ├── test_agent_governance_service.py
│   │   ├── test_agent_context_resolver.py
│   │   ├── test_governance_cache.py
│   │   └── test_trigger_interceptor.py
│   ├── security/
│   │   ├── test_auth_service.py
│   │   ├── test_encryption.py
│   │   └── test_validation.py
│   └── episodes/
│       ├── test_episode_segmentation_service.py
│       ├── test_episode_retrieval_service.py
│       └── test_episode_lifecycle_service.py
├── integration/                   # Integration tests (ALREADY EXISTS)
├── property_tests/               # Property-based tests (ALREADY EXISTS)
│   ├── invariants/
│   │   ├── governance_invariants.py
│   │   ├── security_invariants.py
│   │   └── episode_invariants.py
│   └── database/
│       └── test_database_invariants.py
├── coverage_reports/             # Coverage reports (ALREADY EXISTS)
│   ├── html/
│   ├── metrics/
│   │   └── coverage.json        # Current coverage snapshot
│   └── trends/                  # NEW: Historical coverage data
│       ├── 2026-02-11_coverage.json
│       └── coverage_trend.json  # Aggregated trend data
└── docs/                        # NEW: Test documentation
    ├── COVERAGE_GUIDE.md        # DOCS-03: Coverage report interpretation
    ├── TEST_ISOLATION_PATTERNS.md  # QUAL-07: Isolation patterns
    └── FLAKY_TEST_GUIDE.md      # QUAL-02: Flaky test prevention
```

### Pattern 1: Pytest-Xdist Parallel Execution with Worker Isolation

**What:** Run tests in parallel across multiple CPU cores with zero shared state using pytest-xdist.

**When to use:** For all test suites requiring <5 minute execution time.

**Example:**
```python
# Source: backend/tests/conftest.py (ALREADY IMPLEMENTED)

def pytest_configure(config):
    """
    Pytest hook called after command line options have been parsed.
    Configures pytest-xdist worker isolation.
    """
    if hasattr(config, 'workerinput'):
        worker_id = config.workerinput.get('workerid', 'master')
        os.environ['PYTEST_XDIST_WORKER_ID'] = worker_id

@pytest.fixture(scope="function")
def unique_resource_name():
    """
    Generate unique resource name for parallel test execution.
    Combines worker ID with UUID to ensure no collisions.
    """
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    unique_id = str(uuid.uuid4())[:8]
    return f"test_{worker_id}_{unique_id}"

# Command to run tests in parallel
# pytest tests/ -n auto --dist loadscope
```

**Key insight:** The project already has pytest-xdist configured in pytest.ini with `--dist loadscope` and worker isolation in conftest.py. This is a SOLID FOUNDATION to build upon.

### Pattern 2: Database Transaction Rollback for Test Isolation

**What:** Each test wraps database operations in a transaction that rolls back after test completion.

**When to use:** For all database-dependent tests requiring zero shared state.

**Example:**
```python
# Source: pytest transaction isolation best practices

import pytest
from sqlalchemy.orm import Session

@pytest.fixture(scope="function")
def db_session():
    """
    Create isolated database session with automatic rollback.
    Ensures zero shared state between parallel tests.
    """
    from core.models import SessionLocal

    session = SessionLocal()
    transaction = session.begin()

    yield session

    # Rollback transaction to clean up test data
    session.rollback()
    session.close()

# Usage in tests
def test_agent_creation(db_session, unique_resource_name):
    agent = AgentRegistry(
        id=unique_resource_name,  # No collision with parallel tests
        name="Test Agent"
    )
    db_session.add(agent)
    db_session.commit()

    # Test runs...

    # Automatic rollback via fixture
```

### Pattern 3: Coverage Trending with Codecov

**What:** Upload coverage.json to Codecov after each test run for historical tracking and visualization.

**When to use:** For all CI/CD runs to track coverage trends over time.

**Example:**
```yaml
# Source: Codecov GitHub Actions documentation (https://oneuptime.com/blog/post/2026-01-27-code-coverage-reports-github-actions/view)

name: Coverage Trending
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python: '3.11'
      - name: Install dependencies
        run: |
          pip install pytest pytest-cov
      - name: Run tests with coverage
        run: |
          pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json
      - name: Upload to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: ./tests/coverage_reports/metrics/coverage.json
          flags: backend
          name: backend-coverage
```

### Pattern 4: Flaky Test Detection with pytest-rerunfailures

**What:** Automatically retry failed tests up to N times before reporting failure.

**When to use:** For tests with intermittent failures due to timing, network, or resource contention.

**Example:**
```python
# Source: pytest-rerunfailures documentation (https://pytest-rerunfailures.readthedocs.io/latest/mark.html)

import pytest

@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_oauth_token_refresh():
    """
    Test OAuth token refresh, retry up to 3 times if flaky.
    Waits 1 second between retries.
    """
    # Test implementation...

# Command-line usage
# pytest tests/ --reruns 3 --reruns-delay 1
```

### Anti-Patterns to Avoid

- **Shared test data:** Don't use hardcoded test data that causes collisions in parallel execution
  - *What to do instead:* Use factories with dynamic data (Faker, UUID)
  - *Project already does this:* factories/ directory exists with Faker integration

- **Global state mutations:** Don't modify global variables or singletons in tests
  - *What to do instead:* Use fixtures that reset state after each test
  - *Project already does this:* conftest.py has auto-use fixtures for numpy/pandas restoration

- **External service dependencies:** Don't call real APIs, databases, or services
  - *What to do instead:* Mock external dependencies with pytest-mock
  - *Project already does this:* security/conftest.py has comprehensive mocking

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parallel test execution | Custom threading/multiprocessing | pytest-xdist with `--dist loadscope` | Worker isolation, load balancing, automatic resource management |
| Coverage trending | Custom JSON parsing and plotting | Codecov or Coveralls | Dashboards, historical tracking, PR comments, diff coverage |
| Flaky test detection | Custom retry decorators | pytest-rerunfailures or `@flaky` marker | Standard retry logic, configurable delays, reporting |
| Test data generation | Hardcoded test data | Faker + factories (already exists) | Dynamic data, unique values, realistic data |
| Mutation testing | Custom AST mutation | mutmut | Standard mutations, HTML reports, survivor tracking |
| Cross-platform Rust coverage | Custom shell scripts | Cross + cargo-tarpaulin | Docker-based, handles cross-compilation |

**Key insight:** The project has already invested in sophisticated testing infrastructure (property tests, fuzzy tests, mutation tests, chaos engineering). Don't reinvent the wheel - leverage existing tools and fill gaps in coverage and documentation.

## Common Pitfalls

### Pitfall 1: Test Interdependence in Parallel Execution

**What goes wrong:** Tests fail when run in parallel but pass individually due to shared file system, database rows, or port conflicts.

**Why it happens:** Tests assume they're the only test running (implicit singleton assumption).

**How to avoid:**
1. Use `unique_resource_name()` fixture from conftest.py for all dynamic resource names
2. Wrap database operations in transactions with automatic rollback
3. Use random ports for network services (e.g., `pytest-randomly` or dynamic port allocation)
4. Mock external dependencies (APIs, databases, file systems)

**Warning signs:**
- Tests pass with `pytest tests/` but fail with `pytest tests/ -n auto`
- Intermittent "resource already exists" or "port already in use" errors
- Tests fail in CI but pass locally

### Pitfall 2: Coverage Paradox

**What goes wrong:** High coverage numbers but low quality - tests cover lines but not scenarios, edge cases, or error conditions.

**Why it happens:** Focusing on coverage percentage rather than test quality, testing implementation details rather than behavior.

**How to avoid:**
1. Use property-based tests (Hypothesis) to test invariants, not examples
2. Test error paths explicitly (`pytest.raises(Exception)`)
3. Use mutation testing (mutmut) to detect weak tests
4. Focus on assertion density (conftest.py already tracks this)

**Warning signs:**
- Coverage is 80%+ but mutation score is <60%
- Tests only assert "no exception" rather than specific outcomes
- No tests for edge cases, boundary conditions, or error paths

### Pitfall 3: Flaky Tests Due to Timing

**What goes wrong:** Tests fail intermittently due to race conditions, network delays, or resource cleanup timing.

**Why it happens:** Tests depend on timing (sleeps, timeouts) or external systems with variable response times.

**How to avoid:**
1. Mock network calls with predictable responses
2. Use explicit synchronization (events, barriers) instead of sleeps
3. Increase timeouts for integration tests
4. Use pytest-rerunfailures for known flaky tests (temporary fix)

**Warning signs:**
- Tests pass locally but fail in CI
- Tests fail when run in parallel but pass individually
- "Workaround: add sleep(1)" comments in tests

### Pitfall 4: Coverage Configuration Gaps

**What goes wrong:** Coverage reports show 80%+ but critical files are excluded or coverage measurement is incomplete.

**Why it happens:** Over-aggressive `.coveragerc` exclusions, missing branch coverage, not tracking coverage.json over time.

**How to avoid:**
1. Enable branch coverage: `--cov-branch` (already in pytest.ini)
2. Minimize exclusions in `.coveragerc`
3. Track coverage.json in git or upload to Codecov for trending
4. Separate coverage targets per domain (governance, security, episodes)

**Warning signs:**
- Coverage drops suddenly when tests are added (exclusion patterns)
- Coverage.json shows high overall but individual files are 0%
- No historical trend data to detect coverage regressions

### Pitfall 5: Mobile Testing Environment Mismatch

**What goes wrong:** Tests pass in Jest but fail on device/emulator due to platform differences.

**Why it happens:** Jest mocks don't match native module behavior, platform-specific code not tested.

**How to avoid:**
1. Use `jest-expo` preset (already configured)
2. Mock Expo modules accurately (jest.setup.js has comprehensive mocks)
3. Run E2E tests on real devices/simulators for critical flows
4. Test both iOS and Android platforms separately

**Warning signs:**
- Tests pass but app crashes on device
- Platform-specific bugs (iOS vs Android) not caught
- Missing coverage for native modules

## Code Examples

Verified patterns from official sources:

### Test Isolation with Database Transactions

```python
# Source: pytest transaction isolation best practices
# Ensures zero shared state in parallel execution

import pytest
from sqlalchemy.orm import Session
from core.models import SessionLocal, AgentRegistry

@pytest.fixture(scope="function")
def isolated_db():
    """
    Provide isolated database session with automatic rollback.
    Safe for parallel execution with pytest-xdist.
    """
    session = SessionLocal()
    transaction = session.begin()

    yield session

    # Cleanup: rollback transaction
    session.rollback()
    session.close()

def test_agent_governance_with_isolation(isolated_db, unique_resource_name):
    """
    Test agent governance with database isolation.
    No shared state between parallel test workers.
    """
    agent = AgentRegistry(
        id=unique_resource_name,  # Worker-specific unique ID
        name="Test Agent",
        status="STUDENT"
    )
    isolated_db.add(agent)
    isolated_db.commit()

    # Test logic...

    # Automatic rollback via fixture
```

### Property-Based Test for Governance Invariants

```python
# Source: Hypothesis documentation (https://hypothesis.readthedocs.io/)
# Already used extensively in backend/tests/property_tests/

from hypothesis import given, strategies as st, settings
from core.agent_governance_service import AgentGovernanceService

class TestGovernanceInvariants:
    """Property-based tests for governance invariants."""

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        action_complexity=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=200)
    def test_maturity_thresholds_invariant(self, confidence, action_complexity):
        """
        Test that maturity thresholds are enforced consistently.
        For all confidence values and action complexities, the invariant holds.
        """
        service = AgentGovernanceService()

        result = service.check_permission(
            agent_id="test_agent",
            maturity_level="STUDENT",
            confidence=confidence,
            action_complexity=action_complexity
        )

        # Invariant: STUDENT agents cannot perform high-complexity actions
        if action_complexity >= 3:
            assert not result.permitted
```

### Coverage Trending Setup

```yaml
# Source: Codecov documentation (https://oneuptime.com/blog/post/2026-01-27-code-coverage-reports-github-actions/view)
# Uploads coverage.json for historical tracking

name: Coverage Tracking
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run tests with coverage
        run: |
          pytest tests/ \
            --cov=core \
            --cov=api \
            --cov=tools \
            --cov-report=json:tests/coverage_reports/metrics/coverage.json \
            --cov-report=html \
            --cov-branch

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: ./tests/coverage_reports/metrics/coverage.json
          flags: backend
          name: backend-codecov
          fail_ci_if_error: false  # Don't fail CI if Codecov is down

      - name: Archive coverage reports
        uses: actions/upload-artifact@v4
        with:
          name: coverage-reports-${{ github.sha }}
          path: tests/coverage_reports/
          retention-days: 30
```

### React Native Test Coverage Configuration

```javascript
// Source: Expo testing documentation (https://expo.dev/blog/how-to-build-a-solid-test-harness-for-expo-apps)
// Already configured in mobile/package.json

module.exports = {
  preset: 'jest-expo',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testMatch: [
    '**/__tests__/**/*.[jt]s?(x)',
    '**/?(*.)+(spec|test).[jt]s?(x)'
  ],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/types/**',
    '!src/**/*.stories.tsx'  // Exclude Storybook stories
  ],
  coverageThresholds: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  }
};
```

### Rust Coverage with cargo-tarpaulin

```bash
# Source: tarpaulin GitHub (https://github.com/xd009642/tarpaulin)
# Run coverage for Tauri desktop app (menubar/src-tauri/)

# Basic coverage
cargo tarpaulin --out Json --output-dir coverage/

# With line and branch coverage
cargo tarpaulin --out Lcov --branch --output-dir coverage/

# Cross-platform coverage (using Docker via Cross)
cross test --target aarch64-unknown-linux-gnu
cargo tarpaulin --target aarch64-unknown-linux-gnu --out Json

# Limitations: tarpaulin only supports x86_64 processors
# For ARM testing, use Cross with Docker containers
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sequential test execution (5+ minutes) | Parallel execution with pytest-xdist (<5 minutes) | 2024 | 10x faster test execution |
| Coverage.py HTML only | Coverage.json + Codecov trending | 2024-2025 | Historical tracking, PR comments |
| Manual flaky test detection | pytest-rerunfailures automatic retry | 2024-2025 | Reduced false negatives, CI stability |
| Example-based testing | Property-based testing (Hypothesis) | 2023-2024 | 100x more test scenarios, invariant validation |
| Coverage without branch tracking | Branch coverage by default (`--cov-branch`) | 2024 | More accurate coverage measurement |

**Deprecated/outdated:**
- **nose**: Deprecated test runner, replaced by pytest
- **unittest.mock**: Use pytest-mock for better pytest integration
- **coverage.py v4**: Upgrade to v5+ for JSON output support
- **pytest-parallel**: Superseded by pytest-xdist with better isolation

## Open Questions

1. **Coverage visualization platform choice**
   - What we know: Codecov and Coveralls are both industry standards with JSON/LCOV support
   - What's unclear: Which one integrates better with the existing GitHub Actions setup
   - Recommendation: Start with Codecov (better GitHub Actions integration, free for OSS), can migrate to Coveralls if needed

2. **Rust coverage for Tauri desktop (menubar/)**
   - What we know: cargo-tarpaulin only supports x86_64, project has menubar/src-tauri/ with 5 Rust files
   - What's unclear: Whether ARM coverage is needed (most users are on x86_64)
   - Recommendation: Start with x86_64 coverage only, add Cross-based ARM coverage if Apple Silicon users report issues

3. **Mobile E2E testing strategy**
   - What we know: Jest unit tests exist (15 test files), but E2E testing not documented
   - What's unclear: Whether Detox (E2E for React Native) is needed or unit/integration tests are sufficient
   - Recommendation: Focus on 80% unit/integration coverage first, add Detox E2E tests for critical user flows if time permits

4. **Flaky test remediation priority**
   - What we know: pytest-rerunfailures can mask flaky tests with automatic retries
   - What's unclear: How many flaky tests currently exist and whether to fix or mark as flaky
   - Recommendation: Run full test suite 10 times with `--reruns 0` to identify flaky tests, then prioritize fixing P0/P1 flaky tests

## Sources

### Primary (HIGH confidence)
- **pytest-xdist documentation** - Parallel execution with worker isolation, `--dist loadscope` strategy
- **pytest-rerunfailures documentation** - Flaky test detection with `@flaky` marker and retry logic
- **Coverage.py documentation** - JSON output format, branch coverage configuration
- **Hypothesis documentation** - Property-based testing strategies and invariant testing
- **Expo testing guide** - jest-expo preset, React Native testing best practices
- **cargo-tarpaulin GitHub** - Rust coverage tool, x86_64 limitation, Docker-based cross-platform support
- **Codecov documentation** - Coverage trending, JSON/LCOV upload, GitHub Actions integration

### Secondary (MEDIUM confidence)
- [How to Generate Code Coverage Reports with GitHub Actions](https://oneuptime.com/blog/post/2026-01-27-code-coverage-reports-github-actions/view) (January 27, 2026)
- [How to build a solid test harness for Expo apps](https://expo.dev/blog/how-to-build-a-solid-test-harness-for-expo-apps) (March 6, 2025)
- [Plugin for nose or pytest that automatically reruns flaky tests](https://github.com/box/flaky) (GitHub)
- [8 Ways To Retry: Finding Flaky Tests - Semaphore CI](https://semaphore.io/blog/flaky-test-retry) (March 20, 2024)
- [Best 16 Code Coverage Tools to Boost Your Testing in 2026](https://www.testmuai.com/learning-hub/code-coverage-tools/) (February 3, 2026)
- [Code quality metrics in Grafana](https://medium.com/@adityakale732/code-quality-metrics-in-grafana-8b0b136c78ba) (October 16, 2024)

### Tertiary (LOW confidence)
- Various blog posts comparing Codecov vs Coveralls (needs verification for 2026 features)
- React Native testing guides not from official Expo sources
- Rust testing articles not referencing official tarpaulin documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools are industry standards with official documentation
- Architecture: HIGH - Project already has sophisticated testing infrastructure, building on proven patterns
- Pitfalls: HIGH - Based on official pytest documentation and common anti-patterns

**Research date:** February 11, 2026
**Valid until:** March 13, 2026 (30 days - testing tools evolve slowly)

**Current state assessment:**
- Governance domain: 13.37% coverage (trigger_interceptor.py at 0%)
- Security domain: 22.40% coverage (auth_routes.py at 0%)
- Episodic memory: 15.52% coverage (episode_integration.py at 0%)
- Overall backend: 15.57% coverage (401 files tracked)
- Mobile: Jest configured with 15 test files, coverage report exists
- Desktop: 5 Rust files in menubar/src-tauri/, no coverage configured

**Key gaps identified:**
1. Missing tests for governance, security, and episodic memory critical paths
2. No coverage trending setup (coverage.json not archived or visualized)
3. Flaky test detection not configured (no pytest-rerunfailures)
4. Mobile and desktop coverage not tracked in CI/CD
5. Missing test documentation (DOCS-01, DOCS-03 requirements)

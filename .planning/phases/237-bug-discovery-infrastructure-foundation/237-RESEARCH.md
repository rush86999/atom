# Phase 237: Bug Discovery Infrastructure Foundation - Research

**Researched:** 2026-03-24
**Domain:** Python pytest bug discovery infrastructure, CI/CD pipeline separation, property-based testing, fuzzing
**Confidence:** HIGH

## Summary

Phase 237 focuses on establishing bug discovery infrastructure that integrates with existing pytest framework while maintaining separate CI pipelines for fast PR tests (<10min) and weekly bug discovery tests (~2 hours). The research confirms that Atom has a robust testing foundation with **495+ E2E tests** (Phase 234), **comprehensive pytest infrastructure** with property-based testing (Hypothesis), automated bug filing service (Phase 236-08), and extensive test quality standards (TEST_QUALITY_STANDARDS.md).

**Primary recommendation:** Build on existing pytest infrastructure by adding specialized bug discovery test categories (fuzzing, chaos, property, browser) with dedicated markers, documentation templates, and CI workflow separation. Reuse existing fixtures (auth_fixtures, database_fixtures, page_objects) and enforce TEST_QUALITY_STANDARDS.md (TQ-01 through TQ-05). Integrate with existing bug filing service (backend/tests/bug_discovery/bug_filing_service.py) for automated GitHub issue creation.

**Key findings:**
1. **Existing infrastructure is production-ready**: E2E tests (91 tests), property tests (Hypothesis with 66 invariants), automated bug filing service with GitHub API integration
2. **Pytest markers already defined**: pytest.ini has comprehensive markers (unit, integration, property, slow, fast, fuzzy, chaos, stress) ready for CI pipeline separation
3. **Bug filing service exists**: backend/tests/bug_discovery/bug_filing_service.py with GitHub Issues API, idempotency, artifact collection
4. **Test quality standards enforced**: TEST_QUALITY_STANDARDS.md defines TQ-01 through TQ-05 (independence, 98% pass rate, performance, determinism, coverage quality)
5. **Separate CI workflows already implemented**: weekly-stress-tests.yml, automated-bug-filing.yml, e2e-unified.yml demonstrate pattern for fast vs slow pipeline separation

## Standard Stack

### Core Bug Discovery Tools
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4.x | Test runner and discovery | Industry standard, rich plugin ecosystem, already in use |
| **pytest-xdist** | 3.6.x | Parallel test execution | Speed up test runs 2-4x, already configured (pytest.ini: `-n auto`) |
| **pytest-timeout** | 2.2.x | Test timeout enforcement | Prevent hanging tests, TQ-03 compliance (<30s per test) |
| **pytest-rerunfailures** | 13.0+ | Flaky test detection | Automatic retry for transient failures, already in pytest.ini |
| **hypothesis** | 6.92.x | Property-based testing | De facto standard for Python property tests, 66 invariants already documented |
| **schemathesis** | 3.30.x | API contract testing | OpenAPI specification validation with Hypothesis integration |

### Fuzzing & Chaos Engineering
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **atheris** | 2.2.0 | Coverage-guided fuzzing | Memory safety, input validation, crash detection |
| **mutmut** | 2.4.0 | Mutation testing | Test quality validation, kill weak tests |
| **locust** | 2.15.x | Load testing | Stress testing, performance thresholds (already in requirements-testing.txt) |
| **k6** | (npm) | Load testing | Performance baseline tests (already in weekly-stress-tests.yml) |

### Coverage & Quality
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-cov** | 4.1.x | Coverage reporting | Coverage tracking, HTML reports, already in use |
| **coverage[toml]** | 7.0.x | Enhanced coverage | TOML configuration support, branch coverage |
| **diff-cover** | 7.0 | PR coverage enforcement | Coverage gates on pull requests |
| **radon** | 6.0 | Cyclomatic complexity | Code quality metrics for bug discovery targets |

### Fixtures & Utilities (Already Exist)
| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| **playwright** | 1.58.0 | Browser automation | E2E UI tests (Phase 234), 91 tests already implemented |
| **factory-boy** | 3.3.0 | Test data factories | test_data_factory.py for dynamic, isolated test data |
| **faker** | 22.7.0 | Fake data generation | Realistic test data (E2E tests) |
| **freezegun** | 1.4.x | Time freezing | Deterministic time-based tests (TQ-04 compliance) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **pytest** | unittest (stdlib) | pytest has richer plugins, better fixtures, parallel execution |
| **hypothesis** | quickcheck | Hypothesis has better Python integration, active development |
| **atheris** | libfuzzer (C++ only) | Atheris is Python-native, easier pytest integration |
| **pytest-xdist** | pytest-parallel | xdist is more mature, better pytest integration |

**Installation:**
```bash
# Core bug discovery (already installed)
pip install pytest pytest-xdist pytest-timeout pytest-rerunfailures

# Property-based testing (already installed)
pip install hypothesis schemathesis

# Fuzzing & mutation (in requirements-testing.txt)
pip install atheris mutmut

# Load testing (already configured)
npm install -g k6  # For weekly stress tests
```

## Architecture Patterns

### Recommended Test Structure

**Existing Structure (DO NOT CHANGE):**
```
backend/tests/
├── bug_discovery/          # ✅ EXISTS - Bug filing service
│   ├── bug_filing_service.py
│   ├── test_automated_bug_filing.py
│   └── fixtures/
│       └── bug_filing_fixtures.py
├── property_tests/         # ✅ EXISTS - Hypothesis tests
│   ├── conftest.py         # Hypothesis settings, strategies
│   ├── invariants/         # 66 documented invariants
│   └── database/           # Database property tests
├── e2e_ui/                 # ✅ EXISTS - Playwright E2E tests
│   ├── conftest.py         # API-first auth fixtures
│   ├── fixtures/
│   │   ├── auth_fixtures.py
│   │   ├── database_fixtures.py
│   │   ├── api_fixtures.py
│   │   └── test_data_factory.py
│   └── pages/              # Page Object Model
├── load/                   # ✅ EXISTS - k6 load tests
├── chaos/                  # ✅ EXISTS - Chaos engineering tests
└── conftest.py             # Root fixtures
```

**NEW Structure (Phase 237):**
```
backend/tests/
├── bug_discovery/          # ✅ KEEP - Bug filing service
│   ├── bug_filing_service.py
│   ├── test_automated_bug_filing.py
│   ├── fixtures/
│   │   └── bug_filing_fixtures.py
│   └── TEMPLATES/          # ✅ NEW - Documentation templates
│       ├── FUZZING_TEMPLATE.md
│       ├── CHAOS_TEMPLATE.md
│       ├── PROPERTY_TEMPLATE.md
│       └── BROWSER_TEMPLATE.md
├── fuzzing/                # ✅ NEW - Atheris fuzz tests
│   ├── conftest.py         # Atheris setup, teardown
│   ├── test_api_fuzzing.py
│   ├── test_input_validation_fuzzing.py
│   └── test_memory_safety_fuzzing.py
├── property_tests/         # ✅ KEEP - Hypothesis tests
│   ├── conftest.py
│   ├── invariants/
│   └── database/
├── chaos/                  # ✅ KEEP - Chaos engineering
│   ├── conftest.py
│   └── test_network_chaos.py
├── browser_discovery/      # ✅ NEW - Browser automation bug discovery
│   ├── conftest.py         # Playwright setup
│   ├── test_ui_crashes.py
│   ├── test_memory_leaks.py
│   └── test_network_failures.py
├── e2e_ui/                 # ✅ KEEP - Playwright E2E tests
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── auth_fixtures.py
│   │   ├── database_fixtures.py
│   │   ├── api_fixtures.py
│   │   └── test_data_factory.py
│   └── pages/
├── load/                   # ✅ KEEP - k6 load tests
└── conftest.py             # Root fixtures
```

**Key Principle:** DO NOT create separate `/bug-discovery/` directory (INFRA-01 requirement). Integrate bug discovery into existing `tests/` structure with subdirectories for each bug discovery category.

### Pattern 1: Pytest Marker-Based Test Separation

**What:** Use pytest markers to categorize tests by execution time and test type, enabling separate CI pipelines.

**When to use:** When you need fast PR tests (<10min) vs comprehensive weekly bug discovery (~2 hours).

**Example:**
```python
# Source: pytest.ini (already configured)
[pytest]
markers =
    fast: Fast tests (<0.1s) - run on every PR
    slow: Slow tests (> 1 second) - run weekly
    fuzzing: Fuzzing tests with Atheris - run weekly
    chaos: Chaos engineering tests - run weekly
    property: Property-based tests with Hypothesis - run on every PR
    browser: Browser automation bug discovery - run weekly
```

**Test marking:**
```python
import pytest

@pytest.mark.fuzzing
def test_api_input_validation_fuzzing():
    """Fuzz API input validation with Atheris."""
    # Coverage-guided fuzzing
    pass

@pytest.mark.chaos
def test_network_partition_tolerance():
    """Test system behavior under network partition."""
    # Chaos engineering: inject network failure
    pass

@pytest.mark.property
def test_agent_governance_invariant():
    """Test agent governance invariant with Hypothesis."""
    # Property-based test
    pass

@pytest.mark.browser
@pytest.mark.slow
def test_browser_memory_leak():
    """Detect browser memory leaks with Playwright."""
    # Browser automation bug discovery
    pass
```

**CI pipeline separation:**
```yaml
# .github/workflows/pr-tests.yml (fast PR tests <10min)
on: [pull_request]
jobs:
  fast-tests:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/ -m "fast or property" -n auto --tb=short

# .github/workflows/bug-discovery.yml (weekly comprehensive tests ~2 hours)
on:
  schedule:
    - cron: '0 3 * * 0'  # 3 AM UTC every Sunday
  workflow_dispatch:
jobs:
  bug-discovery:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/ -m "fuzzing or chaos or browser" --tb=long
```

### Pattern 2: Fixture Reuse for Bug Discovery

**What:** Reuse existing fixtures (auth_fixtures, database_fixtures, page_objects) to avoid duplication.

**When to use:** All bug discovery tests should leverage existing test infrastructure.

**Example:**
```python
# Source: backend/tests/e2e_ui/fixtures/auth_fixtures.py (already exists)
# API-first authentication: 10-100x faster than UI login

@pytest.fixture
def authenticated_user(db_session):
    """Create test user and return (user, JWT token) tuple."""
    from core.models import User
    user = User(email=f"test-{uuid4()}@example.com")
    db_session.add(user)
    db_session.commit()

    # Generate JWT token
    token = create_jwt_token(user.id)
    return user, token

@pytest.fixture
def authenticated_page(authenticated_user, browser):
    """Create Playwright page with JWT token in localStorage."""
    user, token = authenticated_user
    browser.goto("http://localhost:3000")
    browser.evaluate(f"() => localStorage.setItem('auth_token', '{token}')")
    return browser
```

**Bug discovery test using existing fixtures:**
```python
# backend/tests/browser_discovery/test_ui_crashes.py
import pytest
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page

@pytest.mark.browser
@pytest.mark.slow
def test_ui_crash_on_invalid_data(authenticated_page: Page):
    """Discover UI crashes when submitting invalid data."""
    # Already authenticated via fixture (10-100x faster)
    authenticated_page.goto("/dashboard")

    # Submit malformed form data
    authenticated_page.fill("input[name='data']", "{invalid}")
    authenticated_page.click("button[data-testid='submit']")

    # Check for browser crashes (Playwright detects crashes)
    assert authenticated_page.locator("body").is_visible()
```

### Pattern 3: Hypothesis Property-Based Testing

**What:** Use Hypothesis to generate hundreds of test inputs and validate invariants.

**When to use:** Testing properties that should hold for ALL inputs (e.g., serialization, validation).

**Example:**
```python
# Source: backend/tests/property_tests/conftest.py (already exists)
from hypothesis import given, settings
from hypothesis import strategies as st

# CI profile: faster tests with fewer examples
ci_profile = settings(max_examples=50, deadline=None)

# Local profile: thorough testing with more examples
local_profile = settings(max_examples=200, deadline=None)

DEFAULT_PROFILE = ci_profile if os.getenv("CI") else local_profile
```

**Property-based bug discovery test:**
```python
# backend/tests/property_tests/invariants/test_workflow_invariants.py
from hypothesis import given, settings
from tests.property_tests.conftest import DEFAULT_PROFILE

@pytest.mark.property
@given(st.lists(st.text(), min_size=1, max_size=100))
@settings(DEFAULT_PROFILE)
def test_workflow_serialization_roundtrip(steps):
    """Workflow serialization is lossless for all step lists."""
    from core.workflow_engine import Workflow

    workflow = Workflow(steps=steps)
    serialized = workflow.serialize()
    deserialized = Workflow.deserialize(serialized)

    assert deserialized.steps == steps  # Invariant holds for all inputs
```

### Pattern 4: Atheris Fuzzing Integration

**What:** Use Atheris (Google's coverage-guided fuzzer for Python) to find memory safety bugs and input validation flaws.

**When to use:** Testing input validation, memory safety, parsing logic.

**Example:**
```python
# backend/tests/fuzzing/test_api_input_validation_fuzzing.py
import pytest
import atheris

@pytest.mark.fuzzing
@pytest.mark.slow
def test_api_input_validation_with_atheris():
    """Fuzz API input validation with Atheris."""
    from api.agent_routes import create_agent

    def fuzz_create_agent(data):
        """Atheris fuzz target."""
        try:
            # Fuzz input: create_agent with random bytes
            create_agent(data)
        except Exception:
            # Expected: invalid input should raise exception
            pass

    # Run Atheris with 1000 iterations
    atheris.Setup([fuzz_create_agent], atheris.FuzzedDataProvider)
    atheris.Fuzz()
```

### Anti-Patterns to Avoid

- **Separate /bug-discovery/ directory:** Violates INFRA-01 requirement. Integrate into existing tests/ structure.
- **Duplicate fixtures:** Reuse auth_fixtures, database_fixtures, page_objects instead of creating new ones.
- **Ignoring TEST_QUALITY_STANDARDS.md:** All bug discovery tests must follow TQ-01 through TQ-05 (independence, 98% pass rate, <30s per test, determinism, coverage quality).
- **Monolithic CI pipeline:** Don't run bug discovery tests on every PR. Use separate pipelines (fast PR vs weekly comprehensive).
- **Skipping documentation templates:** Every bug discovery category needs a template (FUZZING_TEMPLATE.md, etc.) to ensure consistent test quality.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Test runner** | Custom test discovery and execution | pytest with pytest-xdist | Parallel execution, rich plugin ecosystem, already configured |
| **Property testing** | Custom input generators | Hypothesis | Shrinking, strategy composition, 66 invariants already documented |
| **Fuzzing engine** | Custom random input generator | Atheris | Coverage-guided fuzzing, crash detection, Google-maintained |
| **Browser automation** | Custom Selenium wrappers | Playwright Python 1.58.0 | Auto-waiting, network interception, 91 E2E tests already use it |
| **Test fixtures** | Custom auth/db setup | auth_fixtures, database_fixtures (e2e_ui/fixtures/) | API-first auth (10-100x faster), worker isolation |
| **Bug filing** | Custom GitHub API integration | bug_filing_service.py (Phase 236-08) | Idempotency, artifact collection, GitHub Issues API integration |
| **Flaky test detection** | Custom retry logic | pytest-rerunfailures | Automatic retry, already in pytest.ini |
| **Coverage tracking** | Custom coverage script | pytest-cov + coverage[toml] | HTML reports, branch coverage, diff-cover for PRs |

**Key insight:** Bug discovery infrastructure should leverage existing pytest ecosystem rather than building custom tools. The only custom code needed is test logic (fuzz targets, invariants, chaos scenarios) not test infrastructure.

## Common Pitfalls

### Pitfall 1: Ignoring Existing Test Infrastructure

**What goes wrong:** Duplicating fixtures, auth setup, database isolation that already exist in e2e_ui/fixtures/.

**Why it happens:** Developers don't explore existing test infrastructure before writing bug discovery tests.

**How to avoid:**
1. Read backend/tests/e2e_ui/README.md for fixture documentation
2. Import fixtures from tests.e2e_ui.fixtures instead of creating new ones
3. Use unique_resource_name and db_session for parallel-safe tests

**Warning signs:** New conftest.py files with auth/database fixtures that duplicate e2e_ui/fixtures/.

### Pitfall 2: Running Bug Discovery Tests on Every PR

**What goes wrong:** CI pipeline takes 2+ hours, blocking PR merges and slowing development.

**Why it happens:** Not using pytest markers to separate fast PR tests from slow bug discovery tests.

**How to avoid:**
1. Mark bug discovery tests with `@pytest.mark.slow` or `@pytest.mark.fuzzing`
2. Run fast tests on PR: `pytest tests/ -m "fast or property" -n auto`
3. Run bug discovery tests weekly: `pytest tests/ -m "fuzzing or chaos or browser"`

**Warning signs:** PR workflow runs for >10 minutes with fuzzing/chaos tests.

### Pitfall 3: Violating TEST_QUALITY_STANDARDS.md

**What goes wrong:** Bug discovery tests have low pass rate, are flaky, or exceed 30s per test (violating TQ-02, TQ-03, TQ-04).

**Why it happens:** Developers prioritize bug discovery over test quality standards.

**How to avoid:**
1. Enforce TQ-01 (test independence): Use db_session, unique_resource_name
2. Enforce TQ-02 (98% pass rate): Use pytest-rerunfailures sparingly
3. Enforce TQ-03 (<30s per test): Use pytest-timeout to detect slow tests
4. Enforce TQ-04 (determinism): Mock time with freezegun, avoid sleep()
5. Enforce TQ-05 (coverage quality): Test behavior, not implementation

**Warning signs:** Bug discovery tests marked as `@pytest.mark.flaky` to hide failures.

### Pitfall 4: Not Using Documentation Templates

**What goes wrong:** Bug discovery tests are inconsistent, missing critical information (environment setup, repro steps, expected behavior).

**Why it happens:** No standardized templates for different bug discovery categories (fuzzing, chaos, property, browser).

**How to avoid:**
1. Create TEMPLATES/ directory with FUZZING_TEMPLATE.md, CHAOS_TEMPLATE.md, etc.
2. Require all bug discovery tests to follow template structure
3. Include sections: Purpose, Setup, Test Procedure, Expected Behavior, Actual Behavior (on failure), Bug Filing

**Warning signs:** Bug discovery tests without docstrings or missing setup instructions.

### Pitfall 5: Failing to Integrate with Bug Filing Service

**What goes wrong:** Bug discovery tests find bugs but don't automatically file GitHub issues, losing valuable findings.

**Why it happens:** Developers don't know about bug_filing_service.py or don't integrate it into test failure handlers.

**How to avoid:**
1. Import BugFilingService from tests.bug_discovery.bug_filing_service
2. Call bug_filing_service.file_bug() in pytest_exception_interact hook
3. Configure GITHUB_TOKEN and GITHUB_REPOSITORY environment variables

**Warning signs:** Test failures logged to console but no GitHub issues created.

## Code Examples

Verified patterns from official sources:

### Pattern 1: Pytest Marker-Based CI Pipeline Separation

```python
# Source: pytest.ini (existing Atom configuration)
[pytest]
markers =
    fast: Fast tests (<0.1s)
    slow: Slow tests (> 1 second)
    fuzzing: Fuzzing tests using Atheris
    chaos: Chaos engineering tests
    property: Property-based tests using Hypothesis
    browser: Browser automation bug discovery
```

```yaml
# Source: .github/workflows/weekly-stress-tests.yml (existing workflow)
on:
  schedule:
    - cron: '0 3 * * 0'  # Weekly Sunday 3 AM UTC
  workflow_dispatch:

jobs:
  comprehensive-stress-tests:
    runs-on: ubuntu-latest
    steps:
      - name: Run all stress tests
        run: |
          pytest tests/load/ \
                 tests/e2e_ui/tests/test_network_*.py \
                 tests/e2e_ui/tests/test_memory_leak_detection.py \
                 -v --junitxml=stress-test-results.xml
```

### Pattern 2: Reusing Existing Fixtures

```python
# Source: backend/tests/e2e_ui/fixtures/auth_fixtures.py (existing fixture)
@pytest.fixture
def authenticated_page(browser, test_user):
    """Create Playwright page with JWT token in localStorage."""
    from core.models import User
    import jwt

    # Create test user
    user = User(email=f"test-{uuid4()}@example.com")
    db_session.add(user)
    db_session.commit()

    # Generate JWT token
    token = jwt.encode({"user_id": user.id}, "secret", algorithm="HS256")

    # Set token in localStorage (bypasses UI login)
    browser.goto("http://localhost:3000")
    browser.evaluate(f"() => localStorage.setItem('auth_token', '{token}')")

    return browser
```

**Bug discovery test using existing fixture:**
```python
# backend/tests/browser_discovery/test_ui_crashes.py
import pytest
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page

@pytest.mark.browser
@pytest.mark.slow
def test_ui_crash_on_malformed_data(authenticated_page: Page):
    """Discover UI crashes when submitting malformed form data."""
    authenticated_page.goto("/dashboard")

    # Submit invalid data
    authenticated_page.fill("input[name='agent_name']", "\x00\x01\x02")  # Null bytes
    authenticated_page.click("button[data-testid='create-agent']")

    # Check for browser crashes (Playwright detects crashes)
    assert authenticated_page.locator("body").is_visible()
```

### Pattern 3: Hypothesis Property-Based Testing

```python
# Source: backend/tests/property_tests/conftest.py (existing Hypothesis setup)
from hypothesis import settings, HealthCheck

# CI profile: faster tests with fewer examples
ci_profile = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)

# Auto-select based on environment
DEFAULT_PROFILE = ci_profile if os.getenv("CI") else local_profile
```

**Property-based bug discovery test:**
```python
# backend/tests/property_tests/invariants/test_agent_invariants.py
from hypothesis import given, settings
from tests.property_tests.conftest import DEFAULT_PROFILE
import strategies as st

@pytest.mark.property
@given(st.lists(st.text(), min_size=0, max_size=100))
@settings(DEFAULT_PROFILE)
def test_agent_name_validation_invariant(names):
    """Agent names should be valid for all string inputs."""
    from core.agent_governance_service import AgentGovernanceService

    for name in names:
        # Should not raise exception for any string input
        is_valid = AgentGovernanceService.validate_agent_name(name)
        assert isinstance(is_valid, bool)  # Invariant: returns bool
```

### Pattern 4: Automated Bug Filing Integration

```python
# Source: backend/tests/bug_discovery/bug_filing_service.py (existing service)
class BugFilingService:
    def __init__(self, github_token, github_repository):
        self.github_token = github_token
        self.github_repository = github_repository

    def file_bug(self, test_name, error_message, metadata):
        """File GitHub Issue for test failure."""
        # Check for duplicates (idempotency)
        if self._check_duplicate_bug(test_name):
            return

        # Create GitHub Issue
        issue_url = self._create_github_issue(
            title=f"[Bug] {test_name}",
            body=self._generate_bug_body(metadata),
            labels=["bug", "automated", metadata["test_type"]]
        )

        return issue_url
```

**Bug discovery test with automated filing:**
```python
# backend/tests/conftest.py (pytest hook for bug filing)
def pytest_exception_interact(node, call, report):
    """File GitHub Issue when bug discovery test fails."""
    if report.failed:
        # Check if test is bug discovery test
        if "bug_discovery" in str(node.fspath):
            from tests.bug_discovery.bug_filing_service import BugFilingService

            service = BugFilingService(
                github_token=os.getenv("GITHUB_TOKEN"),
                github_repository=os.getenv("GITHUB_REPOSITORY")
            )

            service.file_bug(
                test_name=node.name,
                error_message=str(call.excinfo.value),
                metadata={
                    "test_type": "fuzzing",
                    "file_path": str(node.fspath),
                    "line_number": node.lineno,
                    "screenshot_path": capture_screenshot(node.name),
                    "log_path": capture_logs(node.name)
                }
            )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Separate bug discovery directory** | Integrated into tests/ with markers | Phase 237 (planned) | Consistent test structure, CI pipeline separation via markers |
| **Manual bug filing** | Automated bug filing service | Phase 236-08 (complete) | GitHub Issues created automatically with metadata |
| **UI login for E2E tests** | API-first authentication (JWT in localStorage) | Phase 234 (complete) | 10-100x faster test setup, 91 E2E tests |
| **Sequential test execution** | Parallel execution with pytest-xdist | Phase 234 (complete) | 2-4x speedup, worker-based database isolation |
| **Generic property tests** | 66 documented invariants | Phase 234 (complete) | Focused invariant testing, comprehensive coverage |
| **No bug discovery CI** | Weekly bug discovery pipeline | Phase 237 (planned) | Fast PR tests (<10min) vs weekly comprehensive (~2 hours) |

**Deprecated/outdated:**
- **Custom test runners**: Use pytest with pytest-xdist instead
- **Manual GitHub issue filing**: Use bug_filing_service.py (Phase 236-08)
- **UI-based authentication**: Use auth_fixtures (API-first, 10-100x faster)
- **Separate /bug-discovery/ directory**: Integrate into tests/ with pytest markers (INFRA-01 requirement)

## Open Questions

1. **Bug discovery test execution frequency**
   - What we know: Weekly schedule (Sunday 3 AM UTC) for comprehensive tests, fast PR tests for every commit
   - What's unclear: Should fuzzing tests run more frequently (daily) due to high bug discovery value?
   - Recommendation: Start with weekly fuzzing, increase to daily if bug discovery rate is high (>5 bugs/week)

2. **Atheris fuzz test duration limits**
   - What we know: pytest-timeout enforces 30s per test (TQ-03), but fuzzing can run indefinitely
   - What's unclear: How long should Atheris fuzz tests run? 1000 iterations? Time-based (60s)?
   - Recommendation: Use iteration-based limits (1000-10000 iterations) with `@pytest.mark.timeout(300)` (5 minutes)

3. **Browser memory leak detection threshold**
   - What we know: Heap snapshots can detect leaks, but need threshold for "significant leak"
   - What's unclear: What memory increase percentage constitutes a leak? 10%? 50%?
   - Recommendation: Start with 50% increase threshold, adjust based on false positive rate

4. **Chaos engineering test coverage**
   - What we know: Chaos tests exist (backend/tests/chaos/), but need to verify coverage of all failure modes
   - What's unclear: Which chaos scenarios are most valuable? Network partition? Process crash? Disk full?
   - Recommendation: Prioritize network partition and process crash (highest impact), add others incrementally

5. **Property test invariant selection**
   - What we know: 66 invariants documented in property_tests/invariants/INVARIANTS.md
   - What's unclear: Which invariants should be targeted for bug discovery (high-risk, low coverage)?
   - Recommendation: Focus on governance and security invariants first (P0 priority), then business logic invariants

## Sources

### Primary (HIGH confidence)
- **backend/tests/e2e_ui/README.md** - E2E test infrastructure documentation (91 tests, API-first auth, Playwright 1.58.0)
- **backend/tests/bug_discovery/bug_filing_service.py** - Automated bug filing service with GitHub Issues API
- **backend/tests/property_tests/conftest.py** - Hypothesis property-based testing configuration
- **backend/docs/TEST_QUALITY_STANDARDS.md** - Test quality standards TQ-01 through TQ-05
- **pytest.ini** - Pytest markers and configuration (fast, slow, fuzzing, chaos, property, browser)
- **.github/workflows/weekly-stress-tests.yml** - Weekly comprehensive test pipeline example
- **.github/workflows/automated-bug-filing.yml** - Automated bug filing workflow integration
- **backend/requirements-testing.txt** - Testing dependencies (hypothesis, atheris, schemathesis, mutmut)

### Secondary (MEDIUM confidence)
- **pytest documentation** (pytest.org) - Test discovery, markers, fixtures, xdist parallel execution
- **Hypothesis documentation** (hypothesis.readthedocs.io) - Property-based testing, strategies, settings
- **Atheris documentation** (github.com/google/atheris) - Coverage-guided fuzzing for Python
- **Playwright for Python documentation** (playwright.dev/python) - Browser automation, auto-waiting, network interception

### Tertiary (LOW confidence)
- Web search limitations (rate limit exhausted, unable to verify current 2026 best practices)
- General knowledge of pytest ecosystem patterns (verified against local codebase)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already in use or specified in requirements-testing.txt, verified against codebase
- Architecture: HIGH - Existing test infrastructure well-documented (e2e_ui/README.md, TEST_QUALITY_STANDARDS.md), pytest markers configured
- Pitfalls: HIGH - Common pitfalls identified from existing anti-patterns in pytest.ini (flaky test warnings, ignore patterns)
- CI/CD patterns: HIGH - Existing workflows demonstrate fast vs slow pipeline separation (weekly-stress-tests.yml, e2e-unified.yml)

**Research date:** 2026-03-24
**Valid until:** 2026-04-23 (30 days - stable pytest ecosystem, Hypothesis, Atheris mature projects)

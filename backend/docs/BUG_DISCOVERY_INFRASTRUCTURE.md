# Bug Discovery Infrastructure

**Phase:** 237 - Bug Discovery Infrastructure Foundation
**Last Updated:** 2026-03-24
**Status:** Production Ready

## Overview

Atom's bug discovery infrastructure enables automated finding of bugs through fuzzing, chaos engineering, property-based testing, and browser automation. The infrastructure integrates with existing pytest framework and enforces TEST_QUALITY_STANDARDS.md (TQ-01 through TQ-05).

**Key Features:**
- Integrated into existing pytest infrastructure (no separate /bug-discovery/ directory)
- Separate CI pipelines (fast PR tests <10min, weekly bug discovery ~2 hours)
- Documentation templates for all bug discovery categories
- Enforced test quality standards (TQ-01 through TQ-05)
- Fixture reuse (no duplication of existing auth_fixtures, database_fixtures)

## Architecture

### Directory Structure

```
backend/tests/
├── fuzzing/                    # Atheris fuzzing tests
│   ├── conftest.py             # Fuzzing setup (imports e2e_ui fixtures)
│   └── test_*.py               # Fuzzing test files
├── browser_discovery/          # Playwright bug discovery tests
│   ├── conftest.py             # Browser setup (imports e2e_ui fixtures)
│   └── test_*.py               # Browser discovery test files
├── bug_discovery/              # Bug discovery shared infrastructure
│   ├── bug_filing_service.py   # Automated GitHub Issues filing
│   ├── fixtures/               # Bug filing fixtures
│   ├── TEMPLATES/              # Documentation templates
│   ├── FIXTURE_REUSE_GUIDE.md  # Fixture reuse guide
│   ├── INFRASTRUCTURE_VERIFICATION.md
│   └── TEST_QUALITY_GATE.md
├── e2e_ui/                     # E2E tests with fixtures to reuse
│   ├── fixtures/               # Auth, database, API fixtures
│   ├── pages/                  # Page objects
│   └── README.md               # E2E test documentation
└── property_tests/             # Hypothesis property-based tests
```

### CI/CD Pipeline Separation

**Fast PR Tests (<10 minutes):**
- Trigger: pull_request, push to main
- Marker: `-m "fast or property"`
- Includes: Unit tests, property tests, fast integration tests
- Excludes: Fuzzing, chaos, browser discovery (weekly only)

**Weekly Bug Discovery Tests (~2 hours):**
- Trigger: Schedule (Sunday 3 AM UTC), workflow_dispatch
- Marker: `-m "fuzzing or chaos or browser"`
- Includes: Atheris fuzzing, chaos engineering, browser discovery
- Artifacts: Screenshots, logs, failure reports

## Bug Discovery Categories

### 1. Fuzzing Tests

**Purpose:** Discover memory safety bugs and input validation flaws using Atheris (coverage-guided fuzzing)

**Location:** `backend/tests/fuzzing/`

**Key Fixtures:**
- Import `authenticated_user` from e2e_ui/fixtures (API-first auth)
- Import `db_session` from e2e_ui/fixtures (isolated database)

**Template:** `backend/tests/bug_discovery/TEMPLATES/FUZZING_TEMPLATE.md`

**Example:**
```python
import pytest
import atheris
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_user

@pytest.mark.fuzzing
@pytest.mark.slow
def test_api_input_validation_fuzzing(authenticated_user):
    """Fuzz API input validation with Atheris."""
    user, token = authenticated_user

    def fuzz_one_input(data):
        """Atheris fuzz target."""
        try:
            # Fuzz input validation
            create_agent(data)
        except (ValueError, ValidationError):
            pass  # Expected exceptions

    atheris.Setup([fuzz_one_input], atheris.FuzzedDataProvider)
    atheris.Fuzz()
```

### 2. Chaos Engineering Tests

**Purpose:** Validate system resilience to failure injection (network latency, database drops, memory pressure)

**Location:** `backend/tests/chaos/`

**Key Fixtures:**
- Import `db_session` from e2e_ui/fixtures (isolated test database)
- Blast radius controls (test databases only, duration caps)

**Template:** `backend/tests/bug_discovery/TEMPLATES/CHAOS_TEMPLATE.md`

**Example:**
```python
@pytest.mark.chaos
@pytest.mark.slow
def test_network_partition_tolerance(db_session):
    """Test system behavior under network partition."""
    # Inject network failure
    with inject_network_failure(latency_ms=5000):
        response = api_call()
        # Verify graceful degradation
        assert response.status_code in [200, 503]  # OK or Service Unavailable
```

### 3. Property-Based Tests

**Purpose:** Validate invariants using Hypothesis (property-based testing with counterexample shrinking)

**Location:** `backend/tests/property_tests/`

**Key Fixtures:**
- Import `db_session` from e2e_ui/fixtures (isolated database)

**Template:** `backend/tests/bug_discovery/TEMPLATES/PROPERTY_TEMPLATE.md`

**Example:**
```python
from hypothesis import given, settings, strategies as st
from tests.property_tests.conftest import DEFAULT_PROFILE

@pytest.mark.property
@given(st.lists(st.text(), min_size=0, max_size=100))
@settings(DEFAULT_PROFILE)
def test_workflow_serialization_roundtrip(steps):
    """Workflow serialization is lossless for all step lists."""
    workflow = Workflow(steps=steps)
    serialized = workflow.serialize()
    deserialized = Workflow.deserialize(serialized)
    assert deserialized.steps == steps  # Invariant holds
```

### 4. Browser Discovery Tests

**Purpose:** Discover UI bugs through console errors, accessibility violations, broken links, visual regression

**Location:** `backend/tests/browser_discovery/`

**Key Fixtures:**
- Import `authenticated_page` from e2e_ui/fixtures (10-100x faster than UI login)

**Template:** `backend/tests/bug_discovery/TEMPLATES/BROWSER_TEMPLATE.md`

**Example:**
```python
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page
from playwright.sync_api import Page

@pytest.mark.browser
@pytest.mark.slow
def test_console_errors_on_dashboard(authenticated_page: Page):
    """Discover console errors on dashboard."""
    authenticated_page.goto("/dashboard")  # Already authenticated!

    # Check for console errors
    console_errors = authenticated_page.evaluate(
        "() => window.consoleErrors || []"
    )
    assert len(console_errors) == 0, f"Console errors: {console_errors}"
```

## Fixture Reuse

Bug discovery tests MUST reuse existing fixtures from `tests/e2e_ui/fixtures/`:

**Authentication Fixtures:**
- `test_user`: Create test user with UUID email
- `authenticated_user`: Get (user, JWT token) tuple
- `authenticated_page`: Playwright page with JWT token (API-first auth)
- `admin_user`: Admin user with elevated permissions

**Database Fixtures:**
- `db_session`: SQLAlchemy session with worker isolation
- `clean_database`: Fresh database per test

**API Fixtures:**
- `setup_test_user`: Create user via API
- `setup_test_project`: Create project via API
- `api_client_authenticated`: HTTP client with auth header

**See:** `backend/tests/bug_discovery/FIXTURE_REUSE_GUIDE.md` for complete documentation.

## Test Quality Standards

All bug discovery tests comply with TEST_QUALITY_STANDARDS.md:

- **TQ-01: Test Independence** - Isolated fixtures, no shared state
- **TQ-02: 98% Pass Rate** - Deterministic tests, no flaky markers
- **TQ-03: <30s per test** - Timeout fixtures, deadline settings
- **TQ-04: Determinism** - Same input = same output
- **TQ-05: Coverage Quality** - Test behavior, not implementation

**See:** `backend/tests/bug_discovery/TEST_QUALITY_GATE.md` for quality enforcement.

## Automated Bug Filing

Test failures automatically file GitHub Issues via BugFilingService:

**Features:**
- Idempotency: No duplicate issues for same failure
- Metadata: Test-specific context (network_condition, memory_increase_mb, etc.)
- Severity: Automatic classification (critical/high/medium/low)
- Labels: Automatic labeling (test-type, severity, platform)

**See:** `backend/tests/bug_discovery/bug_filing_service.py`

## Documentation Templates

Templates ensure consistent test quality and documentation:

- `FUZZING_TEMPLATE.md`: Atheris fuzzing test structure
- `CHAOS_TEMPLATE.md`: Chaos engineering test structure
- `PROPERTY_TEMPLATE.md`: Hypothesis property test structure
- `BROWSER_TEMPLATE.md`: Playwright browser discovery structure

**See:** `backend/tests/bug_discovery/TEMPLATES/`

## Quick Start

### 1. Create a Fuzzing Test

```bash
# Copy template
cp backend/tests/bug_discovery/TEMPLATES/FUZZING_TEMPLATE.md \
   backend/tests/fuzzing/test_api_fuzzing.py

# Edit test
# Replace [bracketed placeholders] with your test details
# Import fixtures from tests.e2e_ui.fixtures

# Run test
pytest backend/tests/fuzzing/test_api_fuzzing.py -v
```

### 2. Create a Browser Discovery Test

```bash
# Copy template
cp backend/tests/bug_discovery/TEMPLATES/BROWSER_TEMPLATE.md \
   backend/tests/browser_discovery/test_console_errors.py

# Edit test
# Use authenticated_page fixture (10-100x faster than UI login)
# Import from tests.e2e_ui.fixtures.auth_fixtures

# Run test
pytest backend/tests/browser_discovery/test_console_errors.py -v
```

### 3. Run Bug Discovery Tests

```bash
# Run all bug discovery tests
pytest backend/tests/ -m "fuzzing or chaos or browser" -v

# Run specific category
pytest backend/tests/fuzzing/ -v
pytest backend/tests/browser_discovery/ -v

# Run with coverage
pytest backend/tests/ --cov=backend --cov-branch
```

## CI/CD Integration

### Fast PR Tests

```yaml
# .github/workflows/pr-tests.yml
pytest tests/ -m "fast or property" -n auto --tb=short
```

### Weekly Bug Discovery Tests

```yaml
# .github/workflows/bug-discovery-weekly.yml
pytest tests/ -m "fuzzing or chaos or browser" --tb=long
```

## Verification

Verify infrastructure setup:

```bash
# Run verification checklist
cat backend/tests/bug_discovery/INFRASTRUCTURE_VERIFICATION.md

# Verify pytest discovery
pytest backend/tests/ --collect-only | grep -E "fuzzing|browser_discovery"

# Verify fixture imports
grep "from tests.e2e_ui.fixtures import" backend/tests/fuzzing/conftest.py
grep "from tests.e2e_ui.fixtures import" backend/tests/browser_discovery/conftest.py
```

## Troubleshooting

### Fixtures Not Found

**Issue:** `ImportError: cannot import name 'authenticated_page'`

**Solution:**
```python
# CORRECT import
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page

# WRONG import
from tests.fuzzing.conftest import authenticated_page  # Doesn't exist!
```

### Tests Not Discovered

**Issue:** Pytest doesn't discover bug discovery tests

**Solution:**
```bash
# Verify pytest.ini testpaths includes new directories
grep "testpaths" backend/pytest.ini

# Should include:
# testpaths = tests tests/fuzzing tests/browser_discovery tests/e2e_ui/tests
```

### Bug Filing Not Working

**Issue:** Tests fail but no GitHub Issues created

**Solution:**
```bash
# Verify GITHUB_TOKEN and GITHUB_REPOSITORY are set
echo $GITHUB_TOKEN
echo $GITHUB_REPOSITORY

# Check pytest_exception_interact hook
grep "pytest_exception_interact" backend/tests/conftest.py
```

## See Also

- `backend/docs/TEST_QUALITY_STANDARDS.md` - Test quality requirements (TQ-01 through TQ-05)
- `backend/tests/bug_discovery/BUG_DISCOVERY.md` - Automated bug filing documentation
- `backend/tests/e2e_ui/README.md` - E2E test documentation
- `backend/tests/bug_discovery/FIXTURE_REUSE_GUIDE.md` - Fixture reuse guide
- `.planning/phases/237-bug-discovery-infrastructure-foundation/` - Phase 237 planning

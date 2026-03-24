# Bug Discovery Test Templates

Templates for consistent, high-quality bug discovery tests that comply with `TEST_QUALITY_STANDARDS.md` (TQ-01 through TQ-05).

## Overview

**Purpose:** Ensure consistent test quality and documentation across all bug discovery tests by providing standardized templates that enforce test quality standards.

**What are bug discovery tests?**
Automated tests that discover bugs through:
- **Fuzzing:** Coverage-guided crash discovery with Atheris
- **Chaos Engineering:** Failure injection with blast radius controls
- **Property-Based Testing:** Invariant validation with Hypothesis
- **Browser Discovery:** Console errors, accessibility violations, broken links

**Why use templates?**
- **Consistency:** All tests follow same structure and quality standards
- **TQ Compliance:** Templates enforce TQ-01 through TQ-05 automatically
- **Speed:** Copy template, fill placeholders, write test faster
- **Documentation:** Built-in documentation for each test type

## Template Structure

All templates include these sections:

1. **Purpose** - What the test validates (bug type, target, expected findings)
2. **Dependencies** - Required libraries, fixtures, target modules
3. **Setup** - Environment setup instructions (install, configure, verify)
4. **Test Procedure** - Step-by-step implementation with code examples
5. **Expected Behavior** - What constitutes a bug/finding
6. **Bug Filing** - How to file bugs using `BugFilingService` with metadata
7. **TQ Compliance** - How the test meets TQ-01 through TQ-05 standards

**Additional sections (template-specific):**
- **Invariant** (PROPERTY) - Document invariant before writing test
- **Blast Radius Controls** (CHAOS) - Isolation mechanisms for safety
- **pytest.ini Marker** - Pytest markers for CI/CD integration

## Template Usage

### Step 1: Choose the Right Template

| Bug Type | Template | Key Features |
|----------|----------|--------------|
| Input validation bugs | `FUZZING_TEMPLATE.md` | Atheris, coverage-guided, crash detection |
| Resilience failures | `CHAOS_TEMPLATE.md` | Failure injection, blast radius controls |
| Invariant violations | `PROPERTY_TEMPLATE.md` | Hypothesis, counterexample shrinking |
| UI bugs | `BROWSER_TEMPLATE.md` | Playwright, console/a11y/link checks |

**How to choose:**
- **Fuzzing:** "I want to crash this function with random input"
- **Chaos:** "I want to test if system survives database drops"
- **Property:** "I want to verify this invariant holds for all inputs"
- **Browser:** "I want to find console errors on this page"

### Step 2: Copy Template to Test File

```bash
# Copy template
cd backend/tests/bug_discovery
cp TEMPLATES/FUZZING_TEMPLATE.md test_[target]_fuzzing.md

# Or create test file from template
cat TEMPLATES/FUZZING_TEMPLATE.md | sed 's/\[target\]/[actual_target]/g' > test_[actual_target]_fuzzing.py
```

### Step 3: Fill in Placeholders

Replace `[bracketed placeholders]` with your specific test details:

**Template:**
```markdown
# Fuzzing Test: [Target Module/Function]

## Purpose
Fuzz [target function] to discover [vulnerability type]

## Dependencies
- Target: `backend/api/[routes].py`
```

**Filled:**
```markdown
# Fuzzing Test: Agent Execution

## Purpose
Fuzz `execute_agent()` to discover input validation bugs in agent execution

## Dependencies
- Target: `backend/api/agent_routes.py`
```

### Step 4: Document Invariants (Property Tests Only)

**CRITICAL:** For property-based tests, document invariant BEFORE writing test.

```python
# BAD: Write test first, no invariant documented
def test_workflow_serialization():
    workflow = Workflow(steps=[...])
    # ... test code

# GOOD: Document invariant first
"""
Invariant: Workflow serialization is lossless for all step lists.

Property:
- For any list of workflow steps, serializing and deserializing
  produces an equivalent workflow with the same steps.
"""
def test_workflow_serialization_roundtrip(steps):
    # ... test code
```

### Step 5: Verify TQ Compliance Checklist

Before committing test, verify TQ compliance:

- [ ] **TQ-01 (Independence):** Uses isolated fixtures (db_session, authenticated_page)
- [ ] **TQ-02 (Pass Rate):** Deterministic inputs, no flaky tests
- [ ] **TQ-03 (Performance):** Timeout settings (<30s per test)
- [ ] **TQ-04 (Determinism):** Same input = same output
- [ ] **TQ-05 (Coverage Quality):** Tests behavior, not implementation

### Step 6: Run Test and Verify Bug Filing

```bash
# Run test
pytest backend/tests/bug_discovery/test_[target]_fuzzing.py -v

# Verify bug filing integration (if test discovers bug)
# Check GitHub issues for new bug filed by BugFilingService
gh issue list --label "automated,test-type:fuzzing"
```

## TQ Compliance Mapping

Templates enforce `TEST_QUALITY_STANDARDS.md` requirements:

| TQ Standard | Template Enforcement |
|-------------|---------------------|
| **TQ-01: Independence** | Isolated fixtures (db_session, authenticated_page) |
| **TQ-02: 98% Pass Rate** | Deterministic inputs, no flaky markers, reproducible examples |
| **TQ-03: <30s per test** | Timeout fixtures, Hypothesis deadline settings, Playwright default |
| **TQ-04: Determinism** | Same input = same output, frozen time, fixed seeds |
| **TQ-05: Coverage Quality** | Test behavior (crashes, resilience, invariants), not implementation |

**How templates enforce TQ standards:**

**TQ-01 (Test Independence):**
- All templates require isolated fixtures (db_session, authenticated_page)
- Each test creates/cleans up own data
- No shared state between tests

**TQ-02 (Pass Rate):**
- Fuzzing: Crashes are reproducible with same input
- Chaos: Same failure injection produces same behavior
- Property: Same input produces same output (deterministic function)
- Browser: Same page produces same console output

**TQ-03 (Performance):**
- Fuzzing: 300s timeout for fuzzing campaigns
- Chaos: 60s timeout for failure injection
- Property: Hypothesis deadline (30s default, 5s CI profile)
- Browser: 30s per-test timeout (Playwright default)

**TQ-04 (Determinism):**
- Fuzzing: Same crash input produces same crash
- Chaos: Toxiproxy provides deterministic network conditions
- Property: Hypothesis uses fixed seed (reproducible examples)
- Browser: API-first auth (deterministic JWT tokens)

**TQ-05 (Coverage Quality):**
- Fuzzing: Tests crashes (observable behavior), not parsing code
- Chaos: Tests resilience (observable degradation), not error handling
- Property: Tests invariant (observable property), not implementation
- Browser: Tests user-facing bugs (console, a11y, links)

## Template Selection Guide

### Fuzzing Template (`FUZZING_TEMPLATE.md`)

**When to use:**
- Testing input validation (parsers, deserializers, API endpoints)
- Looking for memory safety bugs (buffer overflows, null pointer dereferences)
- Testing with random byte arrays, strings, JSON

**Examples:**
- Fuzz agent execution endpoint with malformed JSON
- Fuzz workflow deserialization with invalid step data
- Fuzz canvas presentation with corrupted canvas state

**Key features:**
- Atheris coverage-guided fuzzing
- Crash detection (segfaults, assertions, timeouts)
- Corpus management for interesting inputs

### Chaos Template (`CHAOS_TEMPLATE.md`)

**When to use:**
- Testing resilience to failures (network latency, database drops)
- Validating graceful degradation (error handling, retry logic)
- Testing recovery behavior (automatic recovery, data integrity)

**Examples:**
- Inject 2000ms network latency to database
- Drop database connections for 10 seconds
- Allocate 500MB memory for 30 seconds

**Key features:**
- Toxiproxy for network chaos
- Blast radius controls (isolated test database)
- Safety checks (never production)

### Property Template (`PROPERTY_TEMPLATE.md`)

**When to use:**
- Testing invariants (properties that must hold for all inputs)
- Testing stateless logic (serializers, transformers, validators)
- Looking for edge cases with automatic test generation

**Examples:**
- Workflow serialization is lossless for all step lists
- Agent execution is idempotent for all agent IDs
- JSON round-trip preserves data for all valid objects

**Key features:**
- Hypothesis automatic test generation (100+ examples)
- Counterexample shrinking (minimal failing case)
- Invariant-first thinking (document before writing test)

### Browser Template (`BROWSER_TEMPLATE.md`)

**When to use:**
- Testing for console errors (JavaScript errors, unhandled rejections)
- Testing accessibility (WCAG 2.1 AA violations)
- Testing for broken links (404 responses, 5xx errors)

**Examples:**
- Discover console errors on agent dashboard
- Check WCAG violations on workflow editor
- Find broken links on canvas presentation page

**Key features:**
- Playwright browser automation
- API-first authentication (10-100x faster than UI login)
- Axe-core for accessibility checking

## Pytest Markers

Templates reference pytest.ini markers for CI/CD integration:

```ini
# backend/pytest.ini
[pytest]
markers =
    fuzzing: Fuzzing tests (Atheris, slow, may crash)
    chaos: Chaos engineering tests (failure injection, isolated environment, slow)
    property: Property-based tests (Hypothesis, slow, thorough)
    browser: Browser bug discovery tests (Playwright, slow, console/a11y/link checks)
    visual: Visual regression tests (Percy, screenshots, slow)
    slow: Slow tests (>10s, skip in fast CI)
```

**Run specific test types:**
```bash
# Only fuzzing tests
pytest backend/tests/bug_discovery/ -v -m fuzzing

# Only chaos tests
pytest backend/tests/bug_discovery/ -v -m chaos

# Only property tests
pytest backend/tests/property_tests/ -v -m property

# Only browser tests
pytest backend/tests/browser_discovery/ -v -m browser
```

**Skip slow tests in fast CI:**
```bash
# Fast PR tests (<10 minutes)
pytest backend/tests/ -v -m "not slow"

# Weekly bug discovery (~2 hours)
pytest backend/tests/bug_discovery/ -v -m "slow"
```

## Bug Filing Integration

All templates include `BugFilingService` integration for automated bug filing:

```python
from tests.bug_discovery.bug_filing_service import BugFilingService

BugFilingService.file_bug(
    test_name="test_[target]_fuzzing",
    error_message="Crash discovered by fuzzing",
    metadata={
        "test_type": "fuzzing",
        "target_function": "[function_name]",
        "crash_input": crash_data.hex()
    }
)
```

**Automatic bug filing:**
- Fuzzing: On crash (segfault, assertion failure, timeout)
- Chaos: On resilience failure (crash, data loss, no recovery)
- Property: On invariant violation (counterexample found)
- Browser: On discovery (console errors, a11y violations, broken links)

**Bug metadata:**
- Test type (fuzzing, chaos, property, browser)
- Target (function, service, page)
- Discovery details (crash input, failure scenario, counterexample)
- Screenshot (for browser tests)
- Logs/stack traces

## CI/CD Integration

### Fast Pipeline (Pull Requests)

Run fast tests only (<10 minutes):
```yaml
# .github/workflows/test-pr.yml
- name: Run fast tests
  run: |
    pytest backend/tests/ -v -m "not slow" --tb=short
```

**Excludes:**
- Fuzzing tests (slow, 300s timeout)
- Chaos tests (slow, failure injection)
- Property tests (slow, 200 examples)
- Browser tests (slow, 30s per page)

### Weekly Bug Discovery Pipeline

Run comprehensive bug discovery (~2 hours):
```yaml
# .github/workflows/bug-discovery.yml
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly: Sunday midnight

- name: Run fuzzing tests
  run: pytest backend/tests/bug_discovery/ -v -m fuzzing

- name: Run chaos tests
  run: pytest backend/tests/bug_discovery/ -v -m chaos

- name: Run property tests
  run: pytest backend/tests/property_tests/ -v -m property

- name: Run browser tests
  run: pytest backend/tests/browser_discovery/ -v -m browser
```

**Includes:**
- All bug discovery tests
- Automated bug filing to GitHub
- Result aggregation and triage

## Best Practices

### 1. Invariant-First Thinking (Property Tests)

**Document invariant BEFORE writing test:**
```python
# BAD: Write test first, no invariant
def test_workflow_serialization():
    # ... test code

# GOOD: Document invariant first
"""
Invariant: Workflow serialization is lossless.

Property: For any workflow, serialize(deserialize(w)) == w
"""
def test_workflow_serialization_roundtrip(workflow):
    # ... test code
```

### 2. Blast Radius Controls (Chaos Tests)

**Never run chaos tests against production:**
```python
def assert_blast_radius():
    """Ensure failure is scoped to test environment only."""
    db_url = os.getenv("DATABASE_URL")
    assert "test" in db_url, f"Unsafe: {db_url}"
```

### 3. API-First Authentication (Browser Tests)

**Use API-first auth (10-100x faster than UI login):**
```python
# GOOD: API-first auth (fast, 0.1-0.5s)
authenticated_page = create_authenticated_page()
authenticated_page.goto("/dashboard")

# BAD: UI login (slow, 10-30s)
page.goto("/login")
page.fill("input[name='email']", "test@example.com")
page.click("button[type='submit']")
```

### 4. Corpus Management (Fuzzing Tests)

**Save interesting inputs to corpus:**
```bash
# Create corpus directory
mkdir -p backend/tests/bug_discovery/corpus/[target_name]

# Run fuzzing with corpus
pytest backend/tests/bug_discovery/test_[target]_fuzzing.py -v \
  --fuzzing-corpus=backend/tests/bug_discovery/corpus/[target_name]
```

### 5. Timeout Settings

**Set appropriate timeouts per test type:**
- Fuzzing: 300s (5 minutes) for coverage-guided fuzzing
- Chaos: 60s (1 minute) for failure injection
- Property: 30s (default) or 5s (CI profile)
- Browser: 30s (Playwright default)

## See Also

### Documentation

- **`backend/docs/TEST_QUALITY_STANDARDS.md`** - Full TQ-01 through TQ-05 requirements
- **`backend/tests/e2e_ui/README.md`** - E2E test infrastructure guide
- **`backend/tests/bug_discovery/bug_filing_service.py`** - Automated bug filing

### Templates

- **`FUZZING_TEMPLATE.md`** - Atheris fuzzing test template
- **`CHAOS_TEMPLATE.md`** - Chaos engineering test template
- **`PROPERTY_TEMPLATE.md`** - Hypothesis property test template
- **`BROWSER_TEMPLATE.md`** - Playwright browser discovery template

### External Resources

- **[Atheris Documentation](https://github.com/google/atheris)** - Coverage-guided fuzzing for Python
- **[Hypothesis Documentation](https://hypothesis.readthedocs.io)** - Property-based testing
- **[Toxiproxy Python](https://github.com/ihucos/toxiproxy-python)** - Network chaos testing
- **[Playwright Documentation](https://playwright.dev/python/)** - Browser automation
- **[Axe-Core Documentation](https://www.deque.com/axe/)** - Accessibility testing

## Contributing

**Adding new templates:**

1. Create new template in `TEMPLATES/` directory
2. Follow standard structure (Purpose, Dependencies, Setup, Test Procedure, Expected Behavior, Bug Filing, TQ Compliance)
3. Enforce TQ-01 through TQ-05 standards
4. Add pytest.ini marker reference
5. Update this README with template description

**Template checklist:**
- [ ] All 7 required sections present
- [ ] TQ-01 through TQ-05 compliance documented
- [ ] Pytest marker referenced
- [ ] Code examples provided
- [ ] Bug filing integration included
- [ ] 80+ lines for test templates, 50+ lines for README

---

**Version:** 1.0
**Last Updated:** 2026-03-24
**Maintainer:** Atom QA Team

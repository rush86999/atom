# Domain Pitfalls

**Domain:** Backend Testing Coverage Expansion (Existing Python System)
**Researched:** March 11, 2026
**Overall confidence:** HIGH (based on pytest/coverage.py official docs, existing Atom coverage analysis)

## Executive Summary

Adding comprehensive backend testing coverage to existing systems has unique pitfalls distinct from greenfield testing. Atom's discovery of a 71.5 percentage point gap between service-level estimates (74.6%) and actual line coverage (8.50%) illustrates the **critical methodology pitfall**: coverage estimation without actual execution data.

The highest-impact pitfalls for Atom's 80% backend coverage target are:

1. **Methodology Pitfalls** - Coverage estimation vs actual measurement, sampling bias
2. **Fixture Leaks** - Database session isolation, shared state in pytest-xdist
3. **Testing Anti-Patterns** - Over-mocking, testing implementation not behavior
4. **Coverage Gaming** - Wrong exclusion patterns, targeting wrong metrics
5. **Process Failures** - Unmaintainable test suites, technical debt accumulation

## Critical Pitfalls

### Pitfall 1: Service-Level Coverage Estimation Masking True Gaps

**What goes wrong:** Calculating coverage by aggregating service-level estimates (e.g., "episode services have ~74% coverage") instead of measuring actual line execution creates false confidence. Atom's episode services appeared at 74.6% estimated but actual line coverage was only 8.50% - a 71.5 percentage point gap.

**Why it happens:**
- Manual estimation based on "services tested" vs "total services"
- Sampling bias: only checking test file count, not execution paths
- Confusing "tests exist for module X" with "module X is covered"
- Using file-level metrics (e.g., "15 test files cover 20 services") instead of line coverage

**Consequences:**
- False sense of coverage progress
- Wasted effort testing already-covered code
- Critical untested paths remain hidden until production
- Sudden discovery of massive coverage gaps late in milestones

**Prevention:**
- **ALWAYS use actual coverage.py execution data** - `pytest --cov=backend --cov-report=json`
- Require coverage JSON as source of truth for all metrics
- Calculate coverage at **function/line level**, not service level
- Use `coverage report -m` for per-module line coverage
- Set up CI coverage gates that fail on actual measurements, not estimates

**Detection:**
- Service coverage % ≠ actual line coverage % (gap > 10% is warning sign)
- Test files exist but coverage report shows low execution percentages
- Manual calculations or spreadsheets used for coverage metrics

**Phase to Address:** Phase 159 (Backend 80% Coverage) - Establish baseline with actual coverage.py measurement before any test writing.

---

### Pitfall 2: Fixture Scope Leaks and Database Session Pollution

**What goes wrong:** Tests share database sessions, fixtures, or state due to incorrect pytest fixture scoping, causing tests to pass in isolation but fail in parallel runs or produce different coverage results.

**Why it happens:**
- Using `scope="session"` or `scope="module"` for database fixtures when `scope="function"` is needed
- Fixture finalizers not executing due to early exceptions (yield fixtures before yield)
- Database transactions not rolled back between tests
- Autouse fixtures modifying global state

**From pytest docs:**
> "pytest does not do any special processing for SIGTERM and SIGQUIT signals, so fixtures that manage external resources which are important to be cleared when the Python process is terminated might leak resources."
>
> "If a yield fixture raises an exception before yielding, pytest won't try to run the teardown code after that yield fixture's yield statement."

**Consequences:**
- Tests pass locally but fail in CI (parallel execution)
- Coverage results vary between runs
- Test data from one test affects another (false positives/negatives)
- Database locks in parallel test execution

**Prevention:**
```python
# BAD: Session-scoped database fixture
@pytest.fixture(scope="session")
def db_session():
    session = create_session()
    yield session  # NEVER cleaned up properly

# GOOD: Function-scoped with explicit cleanup
@pytest.fixture(scope="function")
def db_session():
    session = create_session()
    yield session
    session.rollback()
    session.close()
```

- Use `scope="function"` for all database fixtures
- Use `yield` fixtures with cleanup code after yield
- Implement transaction rollback in teardown: `session.rollback()`
- Use autouse fixtures to reset global state
- Run tests with `pytest -x` to stop at first failure (catches cascading issues)

**Detection:**
- Tests pass when run singly but fail in suite: `pytest tests/test_specific.py` vs `pytest`
- Coverage differs between runs
- Tests fail with pytest-xdist but pass without: `pytest -n 4` failures
- Database constraint violations about duplicate records

**Phase to Address:** Phase 157 (Edge Cases & Integration Testing) - Fix fixture scope issues before writing parallel test infrastructure.

---

### Pitfall 3: Over-Mocking External Dependencies

**What goes wrong:** Tests mock everything (database, HTTP clients, LLM providers) and verify implementation details (method calls) rather than behavior, creating brittle tests that break on refactoring and don't catch real integration bugs.

**Why it happens:**
- Desire for "fast" tests that avoid external dependencies
- Mocking everything to make tests deterministic
- Verifying mock call counts: `mock_llm.generate.assert_called_once()`
- Testing implementation: "did function call X" vs "did function produce Y"

**Consequences:**
- Tests pass but production code fails (mocks don't match real behavior)
- Refactoring breaks tests even when behavior unchanged
- False sense of security from high test counts
- Integration bugs only caught in production

**Prevention:**
```python
# BAD: Testing implementation details
def test_episode_creation(mock_llm, mock_db):
    service.create_episode(data)
    mock_llm.generate.assert_called_once()  # Brittle!
    mock_db.add.assert_called_once()

# GOOD: Testing behavior
def test_episode_creation_creates_record(db_session):
    episode = service.create_episode(data)
    assert episode.title == "Expected Title"  # Behavior!
    assert episode.summary is not None
    # Verify actual DB state
    db_session.query(Episode).filter_by(id=episode.id).first()
```

- Only mock external services (LLM providers, S3, external APIs)
- Use real database (SQLite in-memory) for tests
- Test observable behavior (return values, database state), not call sequences
- Prefer state-based testing over interaction-based testing
- Use Testcontainers or similar for real dependencies when possible

**Detection:**
- Tests have > 50% mock assertions (assert_called, assert_called_once)
- Tests break when refactoring code without changing behavior
- High test count but low bug detection rate
- Tests use `@patch` decorators extensively

**Phase to Address:** All phases - Establish testing patterns early (Phase 155) that avoid over-mocking.

---

### Pitfall 4: Coverage Gaming - Excluding Untestable Code

**What goes wrong:** Adding `# pragma: no cover` or coverage exclusion patterns to avoid testing difficult code (error handlers, edge cases, async paths), inflating coverage percentages while leaving critical paths untested.

**Why it happens:**
- Pressure to meet 80% coverage targets
- Error handlers and exception paths are hard to trigger
- Async/await code requires complex test setup
- Fear of "breaking" fragile code with tests

**From Atom's pytest.ini:**
```ini
[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

**Consequences:**
- Coverage percentage meets target but actual protection is low
- Production failures in "excluded" error paths
- False confidence from high coverage numbers
- Difficult to justify which exclusions are legitimate

**Prevention:**
- **Audit coverage exclusions quarterly** - remove outdated pragmas
- Only exclude genuinely untestable code: generated protocols, abstract methods
- Require PR review for any new `# pragma: no cover`
- Use `@pytest.mark.skipif` for platform-specific code instead of pragmas
- Focus coverage targets on critical paths (security, financial) first

**Detection:**
- Coverage report shows `pragma: no cover` on > 5% of lines
- High coverage % but many excluded lines
- Error handlers, raise statements, or exception paths excluded
- Coverage config has broad `omit` patterns

**Phase to Address:** Phase 160 (Backend 80% Target) - Audit and remove coverage exclusions as part of final push.

---

### Pitfall 5: Flaky Tests Masking Real Issues

**What goes wrong:** Tests that fail intermittently due to timing issues, race conditions, or async coordination problems are marked as `@pytest.mark.flaky` and auto-retried, masking real bugs and creating unreliable test suites.

**Why it happens:**
- Async tests without proper event loop management
- Time-based assertions: `assert time.time() - start < 1.0`
- Shared state between tests (global variables, singleton instances)
- External service dependencies (network timeouts, rate limits)

**From Atom's pytest.ini:**
```ini
# Pytest-rerunfailures configuration
addopts = --reruns 2 --reruns-delay 1 --maxfail=10
```

**Common causes documented in Atom's config:**
- Race conditions in parallel execution
- Improper async/await handling
- External service dependencies
- Time-based assertions without mocking
- Shared state between tests

**Consequences:**
- Flaky tests create "cry wolf" effect - ignored when they fail
- Real bugs hidden behind "it's just a flaky test"
- CI runs take longer due to retries
- Unreliable coverage measurements

**Prevention:**
```python
# BAD: Time-based assertion
def test_episode_timeout():
    start = time.time()
    episode = service.create_long_episode()
    assert time.time() - start < 5.0  # Flaky!

# GOOD: Mock time or use explicit waits
def test_episode_timeout(mock_time):
    mock_time.advance(timedelta(seconds=10))
    with pytest.raises(TimeoutError):
        service.create_long_episode()
```

- Use `pytest-asyncio` with explicit event loop management
- Mock time-dependent code: `freezegun` library or `unittest.mock.patch`
- Use unique resource names for parallel tests: `f"test_{uuid.uuid4()}"`
- Avoid shared state; use fresh fixtures for each test
- Fix root cause of flakiness, don't just add retries

**Detection:**
- Test fails intermittently: `pytest` fails, `pytest` again passes
- Tests marked with `@pytest.mark.flaky`
- High rerun count in CI logs
- Tests fail in CI but pass locally (or vice versa)

**Phase to Address:** Phase 157 (Edge Cases) - Fix flaky tests before scaling test suite. Establish "no flaky tests" policy.

---

### Pitfall 6: Wrong Coverage Metrics - Line vs Branch Coverage

**What goes wrong:** Focusing only on line coverage (80% target) while ignoring branch coverage, creating false confidence. Line coverage measures "lines executed" but branch coverage measures "decision outcomes tested" - a critical distinction for complex conditional logic.

**Why it happens:**
- Line coverage is default metric in coverage.py
- Branch coverage requires explicit enabling: `--branch`
- Branch coverage percentages are always lower than line coverage
- Misunderstanding that 80% line = 80% branch

**From Atom's pytest.ini:**
```ini
[coverage:run]
branch = true  # Branch coverage enabled

[coverage:report]
fail_under = 80
fail_under_branch = 70  # Different target for branch
```

**Example of difference:**
```python
def get_episode_maturity(agent_id):
    if agent_id is None:  # Line 1
        return "STUDENT"   # Line 2
    if agent.governance_level > 0.9:  # Line 3
        return "AUTONOMOUS"  # Line 4
    return "INTERN"  # Line 5
```

- **Line coverage**: Test with `agent_id="abc"` → lines 1, 3, 5 = **60%** (3/5 lines)
- **Branch coverage**: Test covers 1/4 decision paths = **25%** (False, True/False outcome not tested)

**Consequences:**
- 80% line coverage might be only 50% branch coverage
- Error handling paths (exception branches) often uncovered
- Complex boolean logic: `if x and y or z` appears covered but misses combinations
- False confidence in conditional logic protection

**Prevention:**
- **ALWAYS enable branch coverage**: `pytest --cov=backend --cov-branch`
- Set separate targets: 80% line, 70% branch (as Atom does)
- Review coverage report's "missing branches" section specifically
- Use mutation testing (e.g., `mutmut`) to verify branch quality
- Focus coverage efforts on low-branch-coverage modules

**Detection:**
- Coverage report shows "Missed" column with branch counts: `23 missed, 15 partial`
- High line coverage % but significantly lower branch coverage %
- Complex conditional logic with minimal tests
- Coverage run without `--branch` flag

**Phase to Address:** Phase 159 (Backend 80% Coverage) - Enable branch coverage from start; track both metrics separately.

---

### Pitfall 7: Async Testing Without Proper Event Loop Management

**What goes wrong:** Async tests using `pytest-asyncio` without proper event loop configuration, causing tests to pass in isolation but hang or fail when run in parallel, and producing unreliable coverage results.

**Why it happens:**
- Using `asyncio.run()` in fixtures instead of `@pytest.fixture` with async generators
- Mixing sync and async test code without proper event loop isolation
- Not using `pytest-asyncio`'s `auto` mode or explicit `@pytest.mark.asyncio`
- Event loop not closed between tests, causing resource leaks

**From Atom's pytest.ini:**
```ini
[pytest]
asyncio_mode = auto
```

**Consequences:**
- Tests hang indefinitely in CI
- "Event loop is closed" errors
- Coverage results inconsistent (async functions sometimes execute, sometimes don't)
- Database connection pool exhaustion

**Prevention:**
```python
# BAD: Manual event loop management
@pytest.fixture
def async_client():
    loop = asyncio.new_event_loop()
    client = AsyncClient(loop=loop)
    yield client
    loop.close()  # Too late if test failed

# GOOD: Let pytest-asyncio manage event loop
@pytest.fixture
async def async_client():
    async with AsyncClient() as client:
        yield client
    # Automatic cleanup
```

- Use `pytest-asyncio` with `asyncio_mode = auto` (as Atom does)
- Use `async def` for fixtures and tests
- Never manually create/close event loops in tests
- Use `async with` for resource cleanup
- Ensure all async dependencies use same event loop

**Detection:**
- Tests hang or timeout
- "RuntimeError: Event loop is closed" errors
- "Task attached to different loop" warnings
- Coverage missing for async functions

**Phase to Address:** Phase 148 (Cross-Platform E2E Orchestration) - Establish async testing patterns before writing async integration tests.

---

### Pitfall 8: Test Data Factories Creating Duplicate Records

**What goes wrong:** Test data factories (e.g., `create_test_agent()`) using hardcoded names or sequential IDs cause unique constraint violations when tests run in parallel with pytest-xdist.

**Why it happens:**
- Factories use static names: `create_test_agent(name="test-agent")`
- Sequential IDs from shared sequence generators
- Tests run in parallel with same seed data
- No worker ID in generated test data

**Consequences:**
- Tests pass serially but fail with `pytest -n 4`
- "IntegrityError: duplicate key value violates unique constraint"
- False test failures due to data collisions
- Developers run tests serially to avoid failures, slowing CI

**Prevention:**
```python
# BAD: Hardcoded names
def create_test_agent():
    return Agent(name="test-agent", maturity="STUDENT")

# GOOD: Unique data generation
def create_test_agent():
    suffix = uuid.uuid4().hex[:8]
    return Agent(name=f"test-agent-{suffix}", maturity="STUDENT")

# BEST: Use pytest-xdist worker ID
def create_test_agent(request):
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    return Agent(name=f"test-agent-{worker_id}-{uuid.uuid4().hex[:8]}")
```

- Use UUIDs or random suffixes for all unique fields
- Include worker ID in parallel test execution
- Use database transactions with rollback (not commit) in tests
- Check Atom's conftest.py for `pytest_configure` hook example

**Detection:**
- Tests fail with `-n 4` but pass without
- Unique constraint violations in test logs
- Tests depend on execution order
- Factories use loops or counters for IDs

**Phase to Address:** Phase 157 (Edge Cases) - Fix test data factories before parallel test infrastructure (Phase 148).

---

### Pitfall 9: Coverage Measurement False Positives from Import-Only Execution

**What goes wrong:** Code appears "covered" because modules are imported during test collection, but actual code paths are never executed, inflating coverage percentages for unused functions.

**Why it happens:**
- Coverage counts line execution during import time
- `def` statements and class definitions execute on import
- Decorators and default arguments execute on import
- Test collection imports modules without testing them

**Example:**
```python
# episode_service.py
def create_episode(data):
    validate(data)  # Line 10
    episode = Episode(data)  # Line 11
    return save(episode)  # Line 12

# test_episode.py
import episode_service  # Coverage marks lines 10-12 as "executed"
# But never calls create_episode()!
```

**Consequences:**
- Coverage reports 50-70% but actual behavioral coverage is near 0%
- Functions with 100% coverage but never called with real data
- False progress toward 80% target
- Production failures in "covered" code

**Prevention:**
- Use `coverage report --include="*/tests/*"` to verify test code vs production code
- Review coverage report for "import-only" modules (high coverage, 0 function calls)
- Write tests that explicitly call functions, don't just import modules
- Use `--cov-context=test` in pytest-cov to see which tests cover which lines
- Audit modules with > 90% coverage but < 10 test cases

**Detection:**
- Coverage shows high % for module but no tests call its functions
- `coverage html` report shows green on function definitions but red on function bodies
- Module has 0 test files but > 50% coverage
- Removing tests doesn't reduce coverage percentage

**Phase to Address:** Phase 159 (Backend 80% Coverage) - Audit coverage for import-only false positives when establishing baseline.

---

### Pitfall 10: CI/CD Test Suite Bloat - Slow Tests Blocking Feedback

**What goes wrong:** Test suite becomes too slow (10+ minutes) due to integration tests, database operations, or lack of parallelization, causing developers to skip running tests locally and reducing feedback cycle quality.

**Why it happens:**
- Too many integration tests, not enough unit tests
- Tests not marked with speed markers (`@pytest.mark.slow`, `@pytest.mark.fast`)
- Database fixtures not optimized (recreating schema each test)
- No test parallelization (pytest-xdist not configured)

**From Atom's pytest.ini markers:**
```ini
markers =
    fast: Fast tests (<0.1s)
    slow: Slow tests (> 1 second)
    integration: Integration tests (slower, requires dependencies)
```

**Consequences:**
- Developers push code without running tests locally
- CI queues back up, slowing team velocity
- Tests run less frequently, allowing regressions to accumulate
- Coverage becomes stale due to long feedback cycles

**Prevention:**
- Mark slow tests: `@pytest.mark.slow`
- Run fast tests in pre-commit hooks: `pytest -m "not slow"`
- Use pytest-xdist for parallel execution: `pytest -n auto`
- Optimize database fixtures: use SQLite in-memory, schema rollback not recreation
- Measure and track test execution time: `pytest --durations=10`

**Detection:**
- Full test suite takes > 10 minutes
- Pre-commit hooks skip tests
- Developers commonly push without local test runs
- CI queue backup or frequent timeout failures

**Phase to Address:** Phase 149 (Quality Infrastructure) - Set up test timing benchmarks and fast/slow test separation early.

---

## Moderate Pitfalls

### Pitfall 11: Missing Test Documentation - Unknown Test Purpose

**What goes wrong:** Test files lack docstrings or comments explaining what's being tested and why, making it difficult to maintain tests or understand what edge cases they cover.

**Consequences:**
- Tests become black boxes - breakage requires detective work
- Duplicate tests for same scenarios
- Edge cases tested but not documented
- Onboarding time increases for new developers

**Prevention:**
```python
def test_episode_retrieval_with_canvas_context_filters_by_type():
    """
    Test that episode retrieval with canvas context correctly filters
    by canvas type when detail level is 'summary'.

    Regression test for bug where canvas_type filter was ignored
    in contextual retrieval mode, returning all canvas types.
    """
    episode = retrieval_service.retrieve_contextual(
        agent_id="test-agent",
        canvas_types=["chart"],
        detail_level="summary"
    )
    assert episode.canvas_context[0]["type"] == "chart"
```

- Require docstrings for all test functions
- Document regression tests with bug IDs/tickets
- Use test class docstrings to explain test scenario groups
- Comment complex test data setup

**Phase to Address:** Ongoing - Establish test documentation standards in Phase 155.

---

### Pitfall 12: Test Fragility - Brittle Assertions

**What goes wrong:** Tests have overly specific assertions that break on minor implementation changes (e.g., asserting exact error messages, specific dict key ordering, internal function call sequences).

**Consequences:**
- Tests fail due to refactoring, not bugs
- Developers ignore test failures ("it's just the test being brittle")
- Test maintenance becomes burden, not safety net
- Fear of refactoring reduces code quality

**Prevention:**
```python
# BAD: Brittle assertion
def test_error_message():
    with pytest.raises(ValueError, match="Agent ID must be non-empty"):
        service.create_agent("")

# GOOD: Behavior-focused assertion
def test_error_handling():
    with pytest.raises(ValueError):
        service.create_agent("")
    # Verify system state, not message text
```

- Assert on behavior (return values, state changes), not implementation
- Use partial matching for error messages if needed: `match="agent.*invalid"`
- Avoid asserting on dict/list ordering: use set comparisons
- Test outcomes, not intermediate steps

**Phase to Address:** Phase 155 (Quick Wins) - Establish test writing patterns early.

---

## Minor Pitfalls

### Pitfall 13: Missing Negative Test Cases

**What goes wrong:** Tests only cover happy paths and valid inputs, leaving error handling untested.

**Prevention:**
- Use `pytest.mark.parametrize` for input validation testing
- Test error cases for each public function
- Use Hypothesis for property-based testing of edge cases
- Review code for `raise` statements and ensure tests trigger them

**Phase to Address:** Phase 157 (Edge Cases) - Focus specifically on negative testing.

---

### Pitfall 14: Ignoring Coverage for Helper/Utility Functions

**What goes wrong:** Focusing coverage on "service" layer while ignoring utility modules, helpers, and private functions, leaving critical code untested.

**Prevention:**
- Set coverage targets per module, not just overall
- Review coverage report for modules with < 50% coverage
- Test utility functions directly, don't rely on service-level coverage
- Use `coverage report -m` to see per-module coverage

**Phase to Address:** Phase 159 (Backend 80% Coverage) - Audit utility modules as part of baseline.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| **Phase 155: Quick Wins** | Over-mocking implementation details, brittleness | Establish testing patterns early: real DB, state-based assertions |
| **Phase 157: Edge Cases** | Flaky tests from time/assertions, async race conditions | Use mocks for time, explicit event loop management, unique test data |
| **Phase 159: Backend 80%** | Coverage estimation false positives, import-only coverage | Require actual coverage.py JSON, audit for false positives, enable branch coverage |
| **Phase 148: E2E Orchestration** | Fixture scope leaks, test data collisions | Use function-scoped fixtures, UUID-based test data, pytest-xdist worker isolation |
| **Phase 160: 80% Target** | Coverage gaming with exclusions, wrong metrics focus | Audit `# pragma: no cover`, track branch coverage separately, review edge case coverage |

---

## Sources

**HIGH Confidence** (official documentation, verified):

- [pytest Fixtures Documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html) - Fixture scopes, teardown, finalizers, yield patterns (verified)
- [pytest Good Integration Practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html) - Test layouts, import modes, strict configuration (verified)
- [Coverage.py Documentation](https://coverage.readthedocs.io/) - Line vs branch coverage, exclude patterns, reporting (verified)
- Atom's existing coverage reports - `/Users/rushiparikh/projects/atom/backend/coverage.json` (verified: episode_segmentation_service.py at 27.41% line coverage)
- Atom's pytest.ini configuration - `/Users/rushiparikh/projects/atom/backend/pytest.ini` (verified: flaky test reruns, branch coverage enabled)
- Atom's conftest.py - `/Users/rushiparikh/projects/atom/backend/tests/conftest.py` (verified: environment isolation, numpy restoration, fixture patterns)

**MEDIUM Confidence** (industry best practices, multiple sources):

- Pytest-xdist documentation for parallel execution patterns
- Hypothesis documentation for property-based testing pitfalls
- Mutation testing literature for coverage false positives

**LOW Confidence** (needs validation):

- Specific industry statistics on coverage gaps (service-level vs line coverage estimates)
- Quantitative impact of over-mocking on defect detection rates

**Gaps to Address:**

- **Mutation testing tools validation**: Research `mutmut` or `pymut` for Python to verify branch coverage quality
- **pytest-benchmark integration**: Performance regression testing patterns for test suite optimization
- **Testcontainers Python**: Real dependency testing patterns for database/integration tests

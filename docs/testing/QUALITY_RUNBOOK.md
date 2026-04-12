# Quality Runbook

**Purpose**: Troubleshooting guide for common test failures, coverage issues, and CI problems.

**Last Updated**: 2026-02-25

---

## Table of Contents

1. [Common Issues and Solutions](#common-issues-and-solutions)
2. [Debugging Techniques](#debugging-techniques)
3. [CI Failures](#ci-failures)
4. [Coverage Issues](#coverage-issues)
5. [Performance Optimization](#performance-optimization)
6. [Getting Help](#getting-help)

---

## Common Issues and Solutions

### Issue: Coverage Below Threshold

**Symptoms**:
- Pre-commit hook fails with "Coverage below 80%"
- CI gate fails with coverage regression alert
- HTML report shows red/yellow files

**Solutions**:

1. **Identify Low-Coverage Modules**
   ```bash
   # View HTML report
   open htmlcov/index.html

   # Use gap analysis script
   python tests/scripts/analyze_coverage_gaps.py --below 80

   # Parse coverage JSON
   python tests/scripts/parse_coverage_json.py --below-threshold 80 --format text
   ```

2. **Drill Down into Missing Lines**
   - Click on file in HTML report
   - Look for red lines (not executed)
   - Focus on critical paths (user-facing, data modification)

3. **Prioritize Test Additions**
   - **High priority**: Security checks, database writes, external API calls
   - **Medium priority**: Error handling, edge cases, validation
   - **Low priority**: Getters/setters, simple utilities

4. **Add Tests Incrementally**
   ```python
   # Start with happy path
   def test_feature_works():
       result = feature.run(input_data)
       assert result.success is True

   # Add error cases
   def test_feature_handles_invalid_input():
       with pytest.raises(ValidationError):
           feature.run(invalid_data)

   # Add edge cases
   def test_feature_handles_boundary_conditions():
       result = feature.run(boundary_value)
       assert result.is_at_boundary is True
   ```

5. **Verify Improvement**
   ```bash
   # Before: Record baseline
   pytest tests/ --cov=core.feature_module --cov-report=term-missing

   # Add tests...

   # After: Check improvement
   pytest tests/ --cov=core.feature_module --cov-report=term-missing

   # Compare percentages
   ```

**Prevention**:
- Write tests alongside code (TDD when possible)
- Run coverage locally before pushing
- Use pre-commit hook: `python tests/scripts/enforce_coverage.py --files-only`

---

### Issue: Flaky Tests

**Symptoms**:
- Test passes locally but fails in CI
- Test fails intermittently with same code
- Random order execution causes failures

**Solutions**:

1. **Identify Timing Issues**
   ```python
   # Bad: Hardcoded sleep
   time.sleep(1)  # Brittle, may not be enough

   # Good: Wait for condition
   from waiting import wait

   def test_async_operation_completes():
       operation.start()
       wait(lambda: operation.is_complete(), timeout_seconds=5)
       assert operation.result is not None
   ```

2. **Add Proper Mocks**
   ```python
   # Bad: Real API call (slow, unreliable)
   def test_external_api():
       response = requests.get("https://api.example.com/data")
       assert response.status_code == 200

   # Good: Mocked API call (fast, reliable)
   @patch('requests.get')
   def test_external_api(mock_get):
       mock_get.return_value.status_code = 200
       mock_get.return_value.json.return_value = {"data": "test"}
       response = requests.get("https://api.example.com/data")
       assert response.status_code == 200
   ```

3. **Fix Shared State**
   ```python
   # Bad: Global state
   global_cache = {}

   def test_cache_set():
       global_cache["key"] = "value"

   def test_cache_get():
       assert global_cache["key"] == "value"  # Depends on execution order

   # Good: Isolated state with fixtures
   @pytest.fixture
   def cache():
       cache = Cache()
       yield cache
       cache.clear()  # Cleanup

   def test_cache_set(cache):
       cache.set("key", "value")

   def test_cache_get(cache):
       cache.set("key", "value")
       assert cache.get("key") == "value"  # Independent
   ```

4. **Use Proper Fixtures**
   ```python
   # Bad: Manual cleanup
   def test_database_operation():
       session = SessionLocal()
       agent = Agent(id="test_agent")
       session.add(agent)
       session.commit()
       # ... test code ...
       session.delete(agent)  # May not run if test fails
       session.commit()

   # Good: Fixture with automatic cleanup
   @pytest.fixture
   def db_session():
       session = SessionLocal()
       try:
           yield session
       finally:
           session.rollback()
           session.close()

   def test_database_operation(db_session):
       agent = Agent(id="test_agent")
       db_session.add(agent)
       db_session.commit()
       # ... test code ...
       # Automatic rollback in finally block
   ```

5. **Detect Flaky Tests**
   ```bash
   # Run tests multiple times with random seeds
   python tests/scripts/detect_flaky_tests.py --runs 3 --random-order

   # Fix tests that fail intermittently
   ```

**Prevention**:
- Run tests with `--random-order` flag before committing
- Use proper fixtures for shared resources
- Mock external dependencies (APIs, databases, time)
- Clean up test data in `finally` blocks

---

### Issue: Slow Tests

**Symptoms**:
- Full test suite takes >5 minutes
- Individual tests take >1 second
- CI pipeline times out

**Solutions**:

1. **Profile Test Execution**
   ```bash
   # Show slowest 10 tests
   pytest tests/ --durations=10

   # Output:
   # 10.23s call tests/test_integration.py::test_external_api_call
   # 5.12s call tests/test_database.py::test_large_dataset_import
   # 0.89s call tests/test_service.py::test_complex_calculation
   ```

2. **Optimize Setup**
   ```python
   # Bad: Expensive setup for every test
   @pytest.fixture
   def db_session():
       session = SessionLocal()
       # Import 1000 records for every test
       for i in range(1000):
           session.add(Agent(id=f"agent_{i}"))
       session.commit()
       yield session

   # Good: Session-scoped fixture (reused across tests)
   @pytest.fixture(scope="session")
   def db_data():
       session = SessionLocal()
       for i in range(1000):
           session.add(Agent(id=f"agent_{i}"))
       session.commit()
       yield session
       session.rollback()
   ```

3. **Mock Slow Operations**
   ```python
   # Bad: Real external API call
   def test_notification_service():
       service = NotificationService()
       result = service.send_email("user@example.com", "Test")
       # Takes 2-5 seconds for real email sending

   # Good: Mocked email service
   @patch('core.services.email.SendGridClient')
   def test_notification_service(mock_email):
       mock_email.return_value.send.return_value = {"status": "sent"}
       service = NotificationService()
       result = service.send_email("user@example.com", "Test")
       # Takes <10ms
   ```

4. **Parallel Execution**
   ```bash
   # Run tests in parallel (requires pytest-xdist)
   pytest -n auto

   # Run on 4 workers
   pytest -n 4

   # Combine with coverage (use --cov-append)
   pytest -n auto --cov=core --cov-append
   ```

5. **Mark Slow Tests**
   ```python
   # Mark slow tests
   @pytest.mark.slow
   def test_integration_with_external_api():
       # This test takes >1s
       pass

   # Skip slow tests during development
   pytest tests/ -m "not slow"

   # Run only slow tests in CI
   pytest tests/ -m "slow"
   ```

**Prevention**:
- Profile test execution regularly
- Mock external API calls and database queries
- Use session-scoped fixtures for expensive setup
- Run slow tests separately (CI only)

---

### Issue: Import Errors

**Symptoms**:
- `ModuleNotFoundError: No module named 'core'`
- `ImportError: cannot import name 'AgentService'`
- Tests fail to load

**Solutions**:

1. **Check PYTHONPATH**
   ```bash
   # Set PYTHONPATH to include project root
   export PYTHONPATH=/Users/rushiparikh/projects/atom/backend:$PYTHONPATH

   # Or use pytest.ini with testpaths
   # [pytest]
   # testpaths = tests
   # pythonpath = .
   ```

2. **Verify conftest.py**
   ```python
   # tests/conftest.py
   import sys
   from pathlib import Path

   # Add project root to Python path
   sys.path.insert(0, str(Path(__file__).parent.parent))
   ```

3. **Isolate Test Modules**
   ```bash
   # Test if specific module imports work
   python -c "from core.agent_governance_service import AgentGovernanceService"

   # If this fails, fix import paths or dependencies
   ```

4. **Check Dependencies**
   ```bash
   # Verify all dependencies are installed
   pip install -e ".[dev]"

   # Check for missing packages
   pip list | grep -i pytest
   pip list | grep -i hypothesis
   ```

---

### Issue: Database Errors

**Symptoms**:
- `IntegrityError: UNIQUE constraint failed`
- `OperationalError: no such table`
- Tests interfere with each other

**Solutions**:

1. **Use db_session Fixture**
   ```python
   @pytest.fixture
   def db_session():
       """Create a clean database session for each test."""
       session = SessionLocal()
       try:
           yield session
       finally:
           session.rollback()
           session.close()

   def test_database_operation(db_session):
       agent = Agent(id="test_agent")
       db_session.add(agent)
       db_session.commit()
       # Automatic rollback after test
   ```

2. **Clean Up Test Data**
   ```python
   # Bad: No cleanup
   def test_agent_creation():
       agent = Agent(id="test_agent")
       session.add(agent)
       session.commit()
       # Data remains in database

   # Good: Explicit cleanup
   def test_agent_creation(db_session):
       agent = Agent(id="test_agent")
       db_session.add(agent)
       db_session.commit()

       # Test code...

       # Cleanup
       db_session.delete(agent)
       db_session.commit()
   ```

3. **Use Transactions**
   ```python
   def test_transaction_rollback(db_session):
       # Start transaction
       agent = Agent(id="test_agent")
       db_session.add(agent)

       # Test code...

       # Rollback instead of commit (test isolation)
       db_session.rollback()
   ```

---

## Debugging Techniques

### Run Single Test

```bash
# Run specific test function
pytest tests/test_governance.py::test_agent_permission -v

# Run specific test class
pytest tests/test_governance.py::TestAgentPermissions -v

# Run with verbose output
pytest tests/test_governance.py -vv
```

### Run with Output

```bash
# Show print statements
pytest tests/test_governance.py -v -s

# Combine with coverage
pytest tests/test_governance.py -v -s --cov=core.agent_governance_service
```

### Run with Debugger

```bash
# Drop into debugger on failure
pytest tests/test_governance.py --pdb

# Drop into debugger on error (not just failure)
pytest tests/test_governance.py --pdb --trace
```

**Debugger commands**:
- `n` (next): Execute next line
- `s` (step): Step into function
- `c` (continue): Continue execution
- `p variable` (print): Print variable value
- `l` (list): Show current code
- `q` (quit): Quit debugger

### Run with Coverage

```bash
# Generate HTML coverage report
pytest tests/test_governance.py --cov=core.agent_governance_service --cov-report=html

# Open report in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Run with Markers

```bash
# Run only unit tests
pytest tests/ -m "unit" -v

# Run only integration tests
pytest tests/ -m "integration" -v

# Exclude slow tests
pytest tests/ -m "not slow" -v

# Custom marker
@pytest.mark.security
def test_sql_injection_prevented():
    pass

# Run security tests
pytest tests/ -m "security" -v
```

### Run Failed Tests Only

```bash
# Run only tests that failed last time
pytest tests/ --lf

# Run failed tests first, then others
pytest tests/ --ff

# Combine with coverage
pytest tests/ --lf --cov=core
```

---

## CI Failures

### Check Logs for Specific Failure

```bash
# GitHub Actions logs show:
# - Which test failed
# - Error message and traceback
# - Coverage percentage
# - Pass rate

# Example:
# FAILED tests/test_governance.py::test_agent_permission - AssertionError: assert result.granted is True
```

### Reproduce Locally

```bash
# Use same pytest command from CI logs
# Example CI command:
# pytest tests/ --cov=core --cov-report=xml --cov-report=html

# Run locally with same flags
pytest tests/ --cov=core --cov-report=xml --cov-report=html
```

### Check Environment

```bash
# Verify Python version matches CI
python --version  # Should match CI (e.g., Python 3.11)

# Verify test dependencies
pip list | grep -i pytest
pip list | grep -i hypothesis

# Install missing dependencies
pip install -e ".[dev]"
```

### Check for State Issues

```bash
# Run with random order to detect shared state
pytest tests/ --random-order --random-order-seed=12345

# Fix tests that fail with random order
```

### Common CI Failure Patterns

1. **Import Error on CI Only**
   - Check CI Python version matches local
   - Verify all dependencies in `setup.py` or `pyproject.toml`
   - Check for missing dev dependencies

2. **Test Passes Locally, Fails on CI**
   - Check for environment-specific code (hardcoded paths)
   - Check for time-dependent tests (timezones, clocks)
   - Verify test data is committed (not in .gitignore)

3. **Flaky Test on CI**
   - Add retries: `@pytest.mark.flaky(reruns=3)`
   - Fix root cause (timing issues, shared state)
   - Use proper mocks and fixtures

---

## Coverage Issues

### View HTML Report

```bash
# Generate HTML report
pytest tests/ --cov=core --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

**HTML Report Features**:
- **Green**: >90% coverage (excellent)
- **Yellow**: 80-90% coverage (good)
- **Red**: <80% coverage (needs improvement)
- **Click on file**: Drill down to see uncovered lines

### Find Uncovered Lines

```bash
# Use JSON parser script
python tests/scripts/parse_coverage_json.py --below-threshold 80 --format text

# Output:
# core.agent_governance_service: 74.55% (missing 42 lines)
#   Lines not covered: 23, 45, 67, 89, 123, 145, 167, 189
```

### Check Branch Coverage

```bash
# Generate branch coverage report
pytest tests/ --cov=core --cov-branch --cov-report=term-missing

# Look for missing else/finally clauses
# Example output:
# core.agent_governance_service.py:45 - branch not covered (else clause)
# core.agent_governance_service.py:67 - branch not covered (finally clause)
```

**Common missing branches**:
- `if` statements without testing both branches
- `try/except` without testing exception path
- `for/else` without testing else clause
- Ternary operators: `value if condition else default`

### Profile Coverage

```bash
# Show which tests contribute to coverage
pytest tests/ --cov=core --cov-context=test

# Output shows which tests cover which lines
# Useful for understanding test impact
```

---

## Performance Optimization

### Parallel Execution

```bash
# Run tests in parallel (requires pytest-xdist)
pip install pytest-xdist

# Auto-detect CPU count
pytest -n auto

# Specify worker count
pytest -n 4

# Combine with coverage (use --cov-append)
pytest -n auto --cov=core --cov-append
```

### Test Splitting

```bash
# Run tests by marker
pytest tests/ -m "unit"  # Fast tests only
pytest tests/ -m "integration"  # Slower tests

# Run specific module
pytest tests/test_governance.py

# Run tests matching pattern
pytest tests/ -k "agent"  # All tests with "agent" in name
```

### Fixture Caching

```python
# Function-scoped (default): Runs for every test
@pytest.fixture
def db_session():
    session = SessionLocal()
    yield session
    session.close()

# Session-scoped: Runs once per test session
@pytest.fixture(scope="session")
def db_session():
    session = SessionLocal()
    yield session
    session.close()

# Module-scoped: Runs once per module
@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()
```

**Guidelines**:
- **Function scope**: Tests that modify data
- **Module scope**: Tests that read shared data
- **Session scope**: Expensive setup (database migrations, large datasets)

### Mock Slow Operations

```python
# Bad: Real API call
def test_external_api():
   response = requests.get("https://api.example.com/data")
   assert response.status_code == 200

# Good: Mocked API
@patch('requests.get')
def test_external_api(mock_get):
   mock_get.return_value.status_code = 200
   response = requests.get("https://api.example.com/data")
   assert response.status_code == 200
```

**Mock candidates**:
- External API calls (REST, GraphQL)
- Database queries (use in-memory SQLite)
- File system operations (use temp directories)
- Time-dependent code (use `freezegun`)
- Email/SMS sending (use mocks)

---

## Getting Help

### Check Documentation

- [TEST_COVERAGE_GUIDE.md](TEST_COVERAGE_GUIDE.md) - Coverage strategy and targets
- [QUALITY_STANDARDS.md](QUALITY_STANDARDS.md) - Testing patterns and conventions
- [backend/README.md](../README.md) - Project overview and quick start

### Ask in Team Chat

**Include in your message**:
1. **Error message**: Full traceback
2. **Reproduction steps**: Command to reproduce
3. **Context**: What you were trying to do
4. **Environment**: Python version, OS, pytest version

**Example**:
```
Help with test failure:

Error: AssertionError: assert result.granted is True
File: tests/test_governance.py::test_agent_permission

Traceback:
tests/test_governance.py:45: in test_agent_permission
    assert result.granted is True
E   AssertionError: assert False

Reproduction:
pytest tests/test_governance.py::test_agent_permission -v

Context: Testing AUTONOMOUS agent permission check

Environment: Python 3.11, macOS, pytest 7.4.0
```

### Create Issue

**Bug Report Template**:

```markdown
## Test Failure

**Test Name**: test_agent_permission_denied_for_student

**Error Message**: AssertionError: Expected False but got True

**Steps to Reproduce**:
1. Run `pytest tests/test_governance.py::test_agent_permission_denied_for_student`
2. Observe failure

**Expected Behavior**: STUDENT agents should be denied high-complexity actions

**Actual Behavior**: Test passes incorrectly

**Environment**:
- Python version: 3.11
- OS: macOS 14.0
- pytest version: 7.4.0

**Additional Context**:
This test started failing after commit abc1234.
```

### Useful Commands for Debugging

```bash
# Show pytest version
pytest --version

# Show all installed packages
pip list

# Check pytest configuration
pytest --verbose --setup-show

# Show test collection
pytest --collect-only

# Dry run (show what would be tested)
pytest --collect-only --quiet
```

---

## Quick Reference

### Common Commands

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=core --cov-report=html

# Run single test
pytest tests/test_governance.py::test_agent_permission -v

# Run with output
pytest tests/test_governance.py -v -s

# Run with debugger
pytest tests/test_governance.py --pdb

# Run failed tests only
pytest tests/ --lf

# Run with random order
pytest tests/ --random-order

# Run in parallel
pytest -n auto

# Check coverage gaps
python tests/scripts/analyze_coverage_gaps.py --below 80

# Detect flaky tests
python tests/scripts/detect_flaky_tests.py --runs 3

# Check pass rate
python tests/scripts/check_pass_rate.py --threshold 98
```

### Script References

All scripts are in `backend/tests/scripts/`:

- `enforce_coverage.py` - Pre-commit coverage enforcement
- `check_pass_rate.py` - Test suite health monitoring
- `detect_flaky_tests.py` - Flaky test identification
- `generate_coverage_trend.py` - Trend analysis
- `coverage_report_generator.py` - Report generation
- `parse_coverage_json.py` - CI integration
- `analyze_coverage_gaps.py` - Gap identification
- `ci_quality_gate.py` - Unified CI gate enforcement

---

*Last Updated: 2026-02-25*
*Phase: 090 (Quality Gates & CI/CD)*
*Plan: 06 (Documentation & Maintenance)*

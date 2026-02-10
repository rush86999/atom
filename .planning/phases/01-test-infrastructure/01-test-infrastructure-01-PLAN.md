---
phase: 01-test-infrastructure
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/requirements-testing.txt
  - backend/pytest.ini
  - backend/tests/conftest.py
autonomous: true

must_haves:
  truths:
    - "Developer can run tests in parallel with `pytest -n auto` without state sharing issues"
    - "Developer can run full test suite with `pytest -v` and see all tests categorized by markers"
    - "pytest-xdist is installed and configured for parallel execution"
    - "Test fixtures are properly scoped for parallel execution (function-scoped for mutable data)"
  artifacts:
    - path: "backend/requirements-testing.txt"
      contains: "pytest-xdist"
    - path: "backend/pytest.ini"
      contains: "asyncio_mode = auto"
    - path: "backend/tests/conftest.py"
      provides: "Root fixtures for test suite"
  key_links:
    - from: "pytest -n auto"
      to: "backend/tests/conftest.py"
      via: "Function-scoped db_session fixture ensures isolation"
      pattern: "@pytest.fixture\\(scope=\"function\"\\)"
---

<objective>
Install and configure pytest-xdist for parallel test execution, enabling faster test runs while ensuring proper test isolation through function-scoped fixtures.

Purpose: Reduce test execution time from ~30s serial to ~10s parallel on multi-core machines while maintaining test reliability.
Output: Configured pytest-xdist with isolated test fixtures
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-test-infrastructure/01-RESEARCH.md
@backend/tests/property_tests/conftest.py
@backend/pytest.ini
@backend/requirements-testing.txt
@backend/tests/conftest.py
</context>

<tasks>

<task type="auto">
  <name>Install pytest-xdist for parallel test execution</name>
  <files>backend/requirements-testing.txt</files>
  <action>
    Update backend/requirements-testing.txt to ensure pytest-xdist is properly pinned:

    1. Verify the existing line: `pytest-xdist>=3.5.0,<4.0.0`
    2. If it exists, keep it (already correct)
    3. If missing or wrong version, add: `pytest-xdist>=3.6.0,<4.0.0`

    Do NOT modify other dependencies in requirements-testing.txt. Only update the pytest-xdist line if needed.
  </action>
  <verify>grep "pytest-xdist" backend/requirements-testing.txt</verify>
  <done>pytest-xdist>=3.6.0,<4.0.0 is present in requirements-testing.txt</done>
</task>

<task type="auto">
  <name>Configure pytest for parallel execution with isolated fixtures</name>
  <files>backend/pytest.ini backend/tests/conftest.py</files>
  <action>
    1. Verify backend/pytest.ini has `asyncio_mode = auto` (already present, line 63)
    2. Add pytest-xdist configuration to backend/pytest.ini after the asyncio_mode line:

    ```ini
    # Parallel execution support
    addopts = -v --strict-markers --tb=short
        # ... existing coverage options ...
        --dist loadscope  # Group tests by scope for better isolation
    ```

    3. Update backend/tests/conftest.py to add a pytest-xdist hook for worker isolation:

    ```python
    def pytest_configure(config):
        """
        Pytest hook called after command line options have been parsed.
        Configures pytest-xdist worker isolation.
        """
        # Set unique worker ID for parallel execution
        if hasattr(config, 'workerinput'):
            # Running in pytest-xdist worker
            worker_id = config.workerinput.get('workerid', 'master')
            os.environ['PYTEST_XDIST_WORKER_ID'] = worker_id
    ```

    This ensures each worker has a unique identifier for resource isolation.
  </action>
  <verify>
    pytest -n auto --collect-only -q 2>&1 | head -5
  </verify>
  <done>pytest can run in parallel with `pytest -n auto` and tests are distributed across workers</done>
</task>

<task type="auto">
  <name>Add unique resource fixture for parallel execution</name>
  <files>backend/tests/conftest.py</files>
  <action>
    Add a fixture that generates unique resource names for parallel test execution:

    ```python
    @pytest.fixture(scope="function")
    def unique_resource_name():
        """
        Generate a unique resource name for parallel test execution.
        Combines worker ID with UUID to ensure no collisions.
        """
        worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
        unique_id = str(uuid.uuid4())[:8]
        return f"test_{worker_id}_{unique_id}"
    ```

    This fixture should be added AFTER the existing `ensure_numpy_available` fixture.

    Usage example in docstring:
    ```python
    def test_file_operations(unique_resource_name):
        filename = f"{unique_resource_name}.txt"
        # No collision with parallel tests
    ```
  </action>
  <verify>grep -A5 "unique_resource_name" backend/tests/conftest.py</verify>
  <done>unique_resource_name fixture exists and generates worker-prefixed unique IDs</done>
</task>

</tasks>

<verification>
1. Run `pytest -n auto --collect-only` to verify test discovery works in parallel mode
2. Run `pytest -n 2 tests/property_tests/conftest.py -v` to verify parallel execution on a small subset
3. Verify no "file already exists" or "port already in use" errors when running tests in parallel
</verification>

<success_criteria>
- pytest-xdist is installed and available in the test environment
- Tests can run with `pytest -n auto` without state sharing issues
- Each parallel worker has a unique identifier for resource isolation
- Full test suite completes faster in parallel than serial execution
</success_criteria>

<output>
After completion, create `.planning/phases/01-test-infrastructure/01-test-infrastructure-01-SUMMARY.md`
</output>

"""
Root conftest.py for test suite configuration

This file is loaded before any test modules and sets up necessary fixtures
and configuration for the entire test suite.
"""

import sys
import os
import uuid
import pytest
import ast
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Critical environment variables to isolate between tests
_CRITICAL_ENV_VARS = ['SECRET_KEY', 'ENVIRONMENT', 'DATABASE_URL', 'ALLOW_DEV_TEMP_USERS']


# CRITICAL: This code runs when conftest.py is first imported by pytest.
# It restores numpy/pandas/lancedb/pyarrow modules that may have been
# set to None by previously imported test modules (like test_proactive_messaging_simple.py).
#
# This must happen at module level, not in a function, to ensure it runs
# before test collection begins.
for mod in ["numpy", "pandas", "lancedb", "pyarrow"]:
    if mod in sys.modules and sys.modules[mod] is None:
        sys.modules.pop(mod, None)


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


@pytest.fixture(autouse=True)
def ensure_numpy_available(request):
    """
    Auto-use fixture that ensures numpy/pandas/lancedb/pyarrow are available
    before each test runs.

    This is a safety net in case any test sets these to None.
    """
    # Restore modules before each test
    for mod in ["numpy", "pandas", "lancedb", "pyarrow"]:
        if mod in sys.modules and sys.modules[mod] is None:
            sys.modules.pop(mod, None)

    yield

    # No cleanup needed


@pytest.fixture(autouse=True)
def isolate_environment():
    """
    Isolate environment variables between tests.

    Prevents test pollution from environment modifications by saving and restoring
    critical environment variables (SECRET_KEY, ENVIRONMENT, DATABASE_URL, etc.)
    before and after each test.
    """
    # Save critical env vars
    saved = {}
    for var in _CRITICAL_ENV_VARS:
        if var in os.environ:
            saved[var] = os.environ[var]

    yield

    # Restore saved env vars, delete ones that weren't set before
    for var in _CRITICAL_ENV_VARS:
        if var in saved:
            os.environ[var] = saved[var]
        else:
            os.environ.pop(var, None)


@pytest.fixture(autouse=True)
def reset_agent_task_registry(request):
    """
    Reset agent task registry before each test for isolation.

    This prevents task ID collisions between tests by ensuring each test
    starts with a clean registry state. The AgentTaskRegistry is a singleton
    that persists across test runs, so we need to explicitly reset it.

    This is an autouse fixture, so it runs automatically before every test
    without requiring explicit reference in test signatures.
    """
    from core.agent_task_registry import agent_task_registry
    agent_task_registry._reset()
    yield
    # No cleanup needed - each test gets fresh state at start


@pytest.fixture(scope="function")
def unique_resource_name():
    """
    Generate a unique resource name for parallel test execution.
    Combines worker ID with UUID to ensure no collisions.

    Usage example:
        def test_file_operations(unique_resource_name):
            filename = f"{unique_resource_name}.txt"
            # No collision with parallel tests
    """
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    unique_id = str(uuid.uuid4())[:8]
    return f"test_{worker_id}_{unique_id}"


def _count_assertions(node: ast.AST) -> int:
    """Count assert statements and pytest assertions in AST node."""
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
        # Check for common assertion patterns
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Attribute):
                if child.func.attr in ('assertEqual', 'assertTrue', 'assertFalse',
                                       'assertIn', 'assertNotIn', 'assertRaises',
                                       'assertIs', 'assertIsNone', 'assertIsNotNone'):
                    count += 1
    return count


def _calculate_assertion_density(test_file: Path) -> float:
    """Calculate assertions per line of test code."""
    try:
        source = test_file.read_text()
        tree = ast.parse(source)
        lines = len(source.splitlines())
        if lines == 0:
            return 0.0
        asserts = _count_assertions(tree)
        return asserts / lines
    except Exception:
        return 0.0


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Display quality metrics after test run.

    Reports assertion density and coverage summary.
    """
    # Assertion density check
    min_density = 0.15  # 15 assertions per 100 lines
    test_files = list(Path("tests").rglob("test_*.py"))
    low_density_files = []

    for test_file in test_files:
        density = _calculate_assertion_density(test_file)
        if 0 < density < min_density:
            low_density_files.append((test_file, density))

    if low_density_files:
        terminalreporter.write_sep("=", "WARNING: Low Assertion Density", red=True)
        for test_file, density in low_density_files[:5]:  # Show first 5
            terminalreporter.write_line(
                f"  {test_file}: {density:.3f} (target: {min_density:.2f})",
                red=True
            )

    # Coverage summary
    try:
        import json
        coverage_path = Path("tests/coverage_reports/metrics/coverage.json")
        if coverage_path.exists():
            with open(coverage_path) as f:
                coverage_data = json.load(f)

            line_coverage = coverage_data.get('totals', {}).get('percent_covered', 0)
            terminalreporter.write_sep("=", f"Coverage: {line_coverage:.1f}%", red=True)
    except Exception:
        pass

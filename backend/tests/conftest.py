"""
Root conftest.py for test suite configuration

This file is loaded before any test modules and sets up necessary fixtures
and configuration for the entire test suite.
"""

import sys
import os
import uuid
import pytest

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Display coverage summary after test run.

    This hook runs after all tests complete to show coverage metrics.
    """
    try:
        import json
        from pathlib import Path

        coverage_path = Path("tests/coverage_reports/metrics/coverage.json")
        if coverage_path.exists():
            with open(coverage_path) as f:
                coverage_data = json.load(f)

            # Extract key metrics
            total_lines = coverage_data.get('totals', {}).get('num_statements', 0)
            covered_lines = coverage_data.get('totals', {}).get('covered_lines', 0)
            line_coverage = coverage_data.get('totals', {}).get('percent_covered', 0)
            branch_coverage = coverage_data.get('totals', {}).get('percent_covered', 0)  # Simplified

            terminalreporter.write_sep("=", f"Coverage: {line_coverage:.1f}% lines", red=True)
            terminalreporter.write_line(f"  Total lines: {total_lines}")
            terminalreporter.write_line(f"  Covered: {covered_lines}")
            terminalreporter.write_line(f"  Report: tests/coverage_reports/html/index.html")
    except Exception:
        # Silently fail if coverage file not available
        pass

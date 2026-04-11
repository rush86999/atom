"""
Root conftest for pytest plugin registration.

pytest 7.4+ requires pytest_plugins to be defined only in top-level conftest.
See: https://docs.pytest.org/en/stable/deprecations.html#pytest-plugins-in-non-top-level-conftest-files

E2E UI fixtures are loaded conditionally - they must be importable to be registered.
This prevents ImportError when fixtures are not available (e.g., when running from backend directory).
"""

import pytest


# Register E2E UI fixtures as plugins (conditional import)
# This must be at the root level to avoid pytest deprecation warning
# Fix for Phase 250-01: Handle missing e2e_ui fixtures gracefully
pytest_plugins = []

# Try to import each e2e_ui fixture module
# Only add to pytest_plugins if import succeeds
for plugin in [
    "tests.e2e_ui.fixtures.auth_fixtures",
    "tests.e2e_ui.fixtures.database_fixtures",
    "tests.e2e_ui.fixtures.api_fixtures",
    "tests.e2e_ui.fixtures.test_data_factory",
]:
    try:
        __import__(plugin)
        pytest_plugins.append(plugin)
    except (ImportError, ModuleNotFoundError):
        # Plugin not available, skip it
        # This allows tests to run when e2e_ui fixtures are not available
        pass


def pytest_configure(config):
    """
    Pytest configuration hook.

    Register custom markers for all tests.
    """
    # Register custom markers
    config.addinivalue_line(
        "markers", "last: marker for tests that should run last"
    )
    config.addinivalue_line(
        "markers", "benchmark: marker for benchmark tests"
    )
    config.addinivalue_line(
        "markers", "slow: marker for slow-running tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marker for end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "requires_docker: marker for tests that require Docker to be running"
    )
    config.addinivalue_line(
        "markers", "no_browser: marker for tests that should not run with browser automation"
    )

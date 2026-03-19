"""
Backend pytest configuration file.

This file contains pytest configuration for backend tests.
pytest_plugins moved to root conftest (pytest 7.4+ requirement).
"""

import pytest


# ❌ OLD - causes collection error in pytest 7.4+
# pytest_plugins = [
#     "tests.e2e_ui.fixtures.auth_fixtures",
#     "tests.e2e_ui.fixtures.database_fixtures",
#     "tests.e2e_ui.fixtures.api_fixtures",
#     "tests.e2e_ui.fixtures.test_data_factory",
# ]

# ✅ NEW - moved to root conftest at /Users/rushiparikh/projects/atom/conftest.py
# pytest_plugins must be in top-level conftest only (pytest 7.4+ requirement)
# See: https://docs.pytest.org/en/stable/deprecations.html#pytest-plugins-in-non-top-level-conftest-files


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

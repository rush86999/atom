"""
Root pytest configuration file.

This file contains pytest configuration that applies to all tests.
For per-directory configuration, use conftest.py files in subdirectories.
"""

import pytest

# Register E2E UI fixtures as plugins
# This must be at the root level to avoid pytest deprecation warning
pytest_plugins = [
    "tests.e2e_ui.fixtures.auth_fixtures",
    "tests.e2e_ui.fixtures.database_fixtures",
    "tests.e2e_ui.fixtures.api_fixtures",
    "tests.e2e_ui.fixtures.test_data_factory",
]


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

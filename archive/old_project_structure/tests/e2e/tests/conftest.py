"""
Pytest configuration for E2E tests
Provides common fixtures for all test modules
"""

import pytest
from config.test_config import TestConfig


@pytest.fixture(scope="session")
def config():
    """Provide TestConfig instance to all tests"""
    return TestConfig()

"""
Visual regression test configuration.

This module provides pytest configuration for visual regression tests
including base URL, Percy integration, and test markers.
"""

import os
import sys
from pathlib import Path

import pytest


def pytest_configure(config):
    """
    Configure pytest with visual regression test markers.

    Args:
        config: Pytest config object
    """
    config.addinivalue_line(
        "markers", "visual: mark test as visual regression test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )


# Add frontend directory to Python path for imports
frontend_root = Path(__file__).parent.parent.parent
if str(frontend_root) not in sys.path:
    sys.path.insert(0, str(frontend_root))


@pytest.fixture(scope="session")
def base_url() -> str:
    """
    Provide base URL for visual tests.

    Returns:
        str: Base URL (default: http://localhost:3000)

    Override with:
        pytest --base-url=http://custom-url
    """
    return os.getenv("BASE_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """
    Provide API base URL for visual tests.

    Returns:
        str: API base URL (default: http://localhost:8000)

    Override with:
        export API_BASE_URL=http://custom-api-url
    """
    return os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="function")
def test_user_data() -> dict:
    """
    Provide test user credentials for authentication.

    Returns:
        dict: Test user credentials (email, password)

    Override with:
        export TEST_USER_EMAIL=user@example.com
        export TEST_USER_PASSWORD=password123
    """
    return {
        "email": os.getenv("TEST_USER_EMAIL", "visual-test@example.com"),
        "password": os.getenv("TEST_USER_PASSWORD", "VisualTest123!")
    }


# Import Percy fixtures for availability in tests
from frontend_nextjs.tests.visual.fixtures.percy_fixtures import (
    percy_snapshot,
    percy_page,
    authenticated_percy_page,
    percy_test_data,
    verify_percy_setup
)

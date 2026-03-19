"""
Shared fixtures for load testing with Locust.

This module provides pytest fixtures and configuration for load testing.
Fixtures provide test data (user credentials, agent IDs, workflow IDs) and
configuration for Locust load test scenarios.

Reference: Phase 209 Plan 01 - Locust Load Testing Infrastructure
"""

import pytest
import random
import string
from typing import Dict, List, Any


@pytest.fixture(scope="session")
def load_test_config() -> Dict[str, Any]:
    """
    Load test configuration for Locust scenarios.

    Provides default configuration values for load tests including
    host URL, wait times, and authentication endpoints.

    Returns:
        Dict: Configuration dictionary with keys:
            - host: Base URL for the application
            - default_wait_min: Minimum wait time between tasks (seconds)
            - default_wait_max: Maximum wait time between tasks (seconds)
            - auth_endpoint: Authentication endpoint path
    """
    return {
        "host": "http://localhost:8000",
        "default_wait_min": 1,
        "default_wait_max": 3,
        "auth_endpoint": "/api/v1/auth/login"
    }


@pytest.fixture(scope="session")
def test_user_credentials() -> List[Dict[str, str]]:
    """
    Test user credentials for load testing authentication.

    Provides 10 test user accounts with consistent email format
    and passwords. These users are used to simulate concurrent
    authenticated load on the API.

    Returns:
        List[Dict]: List of user credential dictionaries with keys:
            - email: User email address
            - password: User password
    """
    return [
        {
            "email": f"load_test_{i}@example.com",
            "password": "test_password_123"
        }
        for i in range(10)
    ]


@pytest.fixture(scope="session")
def agent_ids() -> List[str]:
    """
    Test agent IDs for load testing.

    Provides 100 test agent IDs to simulate realistic agent
    operations during load tests. Agent IDs follow a consistent
    naming pattern for easy identification.

    Returns:
        List[str]: List of agent ID strings
    """
    return [f"test_agent_{i:03d}" for i in range(100)]


@pytest.fixture(scope="session")
def workflow_ids() -> List[str]:
    """
    Test workflow IDs for load testing.

    Provides 20 test workflow IDs to simulate workflow execution
    during load tests. Workflow IDs follow a consistent naming
    pattern for easy identification.

    Returns:
        List[str]: List of workflow ID strings
    """
    return [f"test_workflow_{i:03d}" for i in range(20)]


@pytest.fixture(scope="session")
def episode_ids() -> List[str]:
    """
    Test episode IDs for load testing.

    Provides 50 test episode IDs to simulate episode retrieval
    operations during load tests. Episode IDs follow a consistent
    naming pattern for easy identification.

    Returns:
        List[str]: List of episode ID strings
    """
    return [f"test_episode_{i:03d}" for i in range(50)]


def generate_random_string(length: int = 10) -> str:
    """
    Generate a random string for test data.

    Args:
        length: Length of the random string (default: 10)

    Returns:
        str: Random alphanumeric string
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

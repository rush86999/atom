"""
Mobile API authentication fixtures.

This module provides API-first authentication fixtures that bypass
the slow UI login flow for mobile API testing.

Fixtures:
- mobile_test_user: Creates a test user with UUID v4 email
- mobile_auth_token: Returns JWT access token for authenticated requests
- mobile_auth_headers: Returns Authorization headers dict
- mobile_api_client: FastAPI TestClient for in-memory API testing

Performance: 10-100x faster than UI login (saves 2-10 seconds per test).
Uses TestClient for in-memory API testing (no server startup needed).
"""

import os
import uuid
from typing import Dict, Tuple
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Add backend to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.models import User
from core.auth import get_password_hash, create_access_token


@pytest.fixture(scope="function")
def mobile_test_user(db_session: Session) -> User:
    """Create a test user with UUID v4 email for uniqueness.

    The email uses UUID v4 to prevent collisions in parallel test execution.
    User is created with active status and hashed password.

    Args:
        db_session: Database session fixture

    Returns:
        User: Created user instance

    Example:
        def test_with_user(mobile_test_user):
            assert mobile_test_user.email.endswith("@example.com")
            assert mobile_test_user.is_active is True
    """
    # Generate unique email using UUID v4
    unique_id = str(uuid.uuid4())[:8]
    email = f"mobile_{unique_id}@example.com"

    # Create user with hashed password
    user = User(
        email=email,
        password_hash=get_password_hash("MobileTest123!"),
        status="active",
        created_at=datetime.utcnow()
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture(scope="function")
def mobile_auth_token(mobile_test_user: User) -> str:
    """Create a JWT access token for mobile API testing.

    This fixture creates a JWT token for the test user.
    Token is used for authenticated API requests.

    Args:
        mobile_test_user: Test user fixture

    Returns:
        str: JWT access token

    Example:
        def test_authenticated_request(mobile_auth_token):
            headers = {"Authorization": f"Bearer {mobile_auth_token}"}
            # Make authenticated API request
    """
    # Create JWT token with user ID as subject
    token = create_access_token(
        data={"sub": str(mobile_test_user.id)},
        expires_delta=None  # Use default 15 minutes
    )

    return token


@pytest.fixture(scope="function")
def mobile_auth_headers(mobile_auth_token: str) -> Dict[str, str]:
    """Create Authorization headers dict for mobile API requests.

    This fixture returns a dict with Bearer token authentication.
    Use this fixture to make authenticated requests easily.

    Args:
        mobile_auth_token: JWT token fixture

    Returns:
        Dict[str, str]: Headers dict with Authorization key

    Example:
        def test_authenticated_request(mobile_api_client, mobile_auth_headers):
            response = mobile_api_client.get("/api/v1/agents", headers=mobile_auth_headers)
            assert response.status_code == 200
    """
    return {"Authorization": f"Bearer {mobile_auth_token}"}


@pytest.fixture(scope="function")
def mobile_api_client():
    """Create a FastAPI TestClient for in-memory API testing.

    This fixture provides a TestClient instance for making API calls
    without starting a server. Uses in-memory request/response handling.

    Performance: <10ms per request (no network overhead).

    Returns:
        TestClient: FastAPI test client instance

    Example:
        def test_api_endpoint(mobile_api_client):
            response = mobile_api_client.post("/api/auth/login", json={
                "username": "test@example.com",
                "password": "password"
            })
            assert response.status_code == 200
    """
    # Import FastAPI app
    from core.main import app

    # Create test client
    client = TestClient(app)

    return client


@pytest.fixture(scope="function")
def mobile_authenticated_client(mobile_api_client: TestClient, mobile_auth_headers: Dict[str, str]):
    """Create an authenticated API client with pre-set headers.

    This fixture provides a function that makes authenticated API requests
    without manually setting headers each time.

    Args:
        mobile_api_client: TestClient fixture
        mobile_auth_headers: Auth headers fixture

    Returns:
        Callable: Function that makes authenticated requests

    Example:
        def test_authenticated_call(mobile_authenticated_client):
            response = mobile_authenticated_client("GET", "/api/v1/agents")
            assert response.status_code == 200
    """
    def make_request(method: str, endpoint: str, **kwargs):
        """Make authenticated API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., "/api/v1/agents")
            **kwargs: Additional arguments passed to TestClient

        Returns:
            Response: API response object
        """
        # Merge headers
        headers = kwargs.pop("headers", {})
        headers.update(mobile_auth_headers)

        return mobile_api_client.request(method, endpoint, headers=headers, **kwargs)

    return make_request


@pytest.fixture(scope="function")
def mobile_admin_user(db_session: Session) -> Tuple[User, str]:
    """Create an admin user with elevated permissions.

    This fixture creates a user with superuser privileges for testing
    admin-only endpoints and features.

    Args:
        db_session: Database session fixture

    Returns:
        Tuple[User, str]: (admin user, JWT token)

    Example:
        def test_admin_endpoint(mobile_admin_user):
            admin, token = mobile_admin_user
            assert admin.role == "super_admin"
    """
    unique_id = str(uuid.uuid4())[:8]
    email = f"mobile_admin_{unique_id}@example.com"

    admin = User(
        email=email,
        password_hash=get_password_hash("MobileAdmin123!"),
        role="super_admin",
        status="active",
        created_at=datetime.utcnow()
    )

    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    # Create JWT token for admin
    token = create_access_token(
        data={"sub": str(admin.id), "is_superuser": True},
        expires_delta=None
    )

    return admin, token

"""
Authentication fixtures for E2E UI tests.

This module provides API-first authentication fixtures that bypass
the slow UI login flow (10-100x faster than typing credentials).

Fixtures:
- test_user: Creates a test user with UUID v4 email
- authenticated_user: Creates and returns a user with JWT token
- authenticated_page: Creates a Playwright page with JWT token in localStorage
"""

import os
import uuid
from typing import Tuple
from datetime import datetime
import pytest
from playwright.sync_api import Page, Browser
from sqlalchemy.orm import Session

# Add backend to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.models import User
from core.auth import get_password_hash, create_access_token


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """Create a test user with UUID v4 email for uniqueness.

    The email uses UUID v4 to prevent collisions in parallel test execution.
    User is created with active status and hashed password.

    Args:
        db_session: Database session fixture

    Returns:
        User: Created user instance

    Example:
        def test_with_user(test_user):
            assert test_user.email.endswith("@example.com")
            assert test_user.is_active is True
    """
    # Generate unique email using UUID v4
    unique_id = str(uuid.uuid4())[:8]
    email = f"test_{unique_id}@example.com"

    # Create user with hashed password
    user = User(
        email=email,
        password_hash=get_password_hash("TestPassword123!"),
        status="active",
        created_at=datetime.utcnow()
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture(scope="function")
def authenticated_user(test_user: User) -> Tuple[User, str]:
    """Create a test user and return with JWT access token.

    This fixture creates a user via API and returns both the user
    instance and a valid JWT token for authentication.

    Args:
        test_user: Test user fixture

    Returns:
        Tuple[User, str]: (user instance, JWT access token)

    Example:
        def test_authenticated_request(authenticated_user):
            user, token = authenticated_user
            headers = {"Authorization": f"Bearer {token}"}
            # Make authenticated API request
    """
    # Create JWT token with user ID as subject
    token = create_access_token(
        data={"sub": str(test_user.id)},
        expires_delta=None  # Use default 15 minutes
    )

    return test_user, token


@pytest.fixture(scope="function")
def authenticated_page(browser: Browser, authenticated_user: Tuple[User, str]) -> Page:
    """Create a Playwright page with JWT token pre-set in localStorage.

    This fixture bypasses the slow UI login flow by directly setting
    the JWT token in localStorage. The page is ready to make authenticated
    requests without going through login screens.

    Performance: 10-100x faster than UI login (saves 2-10 seconds per test).

    Args:
        browser: Playwright browser fixture
        authenticated_user: Authenticated user fixture (user, token)

    Returns:
        Page: Playwright page with JWT token in localStorage

    Example:
        def test_authenticated_page(authenticated_page):
            authenticated_page.goto("http://localhost:3000/dashboard")
            # No redirect to login - token already set
            assert authenticated_page.locator("h1").contains("Dashboard")
    """
    user, token = authenticated_user

    # Create new browser context and page
    context = browser.new_context()
    page = context.new_page()

    # Set JWT token in localStorage before navigating
    # This bypasses the UI login flow
    page.goto("http://localhost:3001")  # Load E2E frontend on port 3001

    # Execute JavaScript to set token in localStorage
    page.evaluate(f"""() => {{
        localStorage.setItem('auth_token', '{token}');
        localStorage.setItem('next-auth.session-token', '{token}');
    }}""")

    yield page

    # Cleanup: Close context after test
    context.close()


@pytest.fixture(scope="function")
def api_client_authenticated(authenticated_user: Tuple[User, str]):
    """Create an HTTP client with pre-set Authorization header.

    This fixture provides a function that makes authenticated API requests
    without manually setting headers each time.

    Args:
        authenticated_user: Authenticated user fixture (user, token)

    Returns:
        Callable: Function that makes authenticated requests

    Example:
        def test_api_call(api_client_authenticated):
            response = api_client_authenticated("GET", "/api/v1/users/me")
            assert response.status_code == 200
    """
    import requests

    user, token = authenticated_user
    base_url = "http://localhost:8000"  # Backend API URL

    def make_request(method: str, endpoint: str, **kwargs):
        """Make authenticated API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., "/api/v1/users/me")
            **kwargs: Additional arguments passed to requests

        Returns:
            requests.Response: API response
        """
        url = f"{base_url}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        return requests.request(method, url, headers=headers, **kwargs)

    return make_request


@pytest.fixture(scope="function")
def admin_user(db_session: Session) -> Tuple[User, str]:
    """Create an admin user with elevated permissions.

    This fixture creates a user with superuser privileges for testing
    admin-only endpoints and features.

    Args:
        db_session: Database session fixture

    Returns:
        Tuple[User, str]: (admin user, JWT token)

    Example:
        def test_admin_endpoint(admin_user):
            admin, token = admin_user
            assert admin.is_superuser is True
    """
    unique_id = str(uuid.uuid4())[:8]
    email = f"admin_{unique_id}@example.com"

    admin = User(
        email=email,
        password_hash=get_password_hash("AdminPassword123!"),
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

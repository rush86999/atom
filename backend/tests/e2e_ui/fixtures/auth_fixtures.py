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

# Mirror main_api_app.py's dotenv loading BEFORE importing core.auth: the
# backend signs/verifies JWTs with SECRET_KEY from backend/.env (+ .env.local
# override). Without this, core.auth falls back to a per-process random key and
# every token minted here (create_access_token in the authenticated_user
# fixture, create_expired_token in test_auth_protected_routes) is signed with a
# key the live backend does not know — 401/404 regardless of validity.
from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))
load_dotenv(os.path.join(_BACKEND_DIR, ".env.local"), override=True)

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

    # Create user with hashed password and required fields
    user = User(
        email=email,
        hashed_password=get_password_hash("TestPassword123!"),
        first_name="Test",
        last_name="User",
        role="workspace_admin",
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
def authenticated_page(browser: Browser, test_user: User) -> Page:
    """Create a Playwright page with JWT token pre-set in localStorage.

    This fixture bypasses the slow UI login flow by directly setting
    the JWT token in localStorage. The page is ready to make authenticated
    requests without going through login screens.

    Performance: 10-100x faster than UI login (saves 2-10 seconds per test).

    Args:
        browser: Playwright browser fixture
        test_user: Test user fixture (created in the shared DB)

    Returns:
        Page: Playwright page with JWT token in localStorage

    Example:
        def test_authenticated_page(authenticated_page):
            authenticated_page.goto("http://localhost:3001/dashboard")
            # No redirect to login - token already set
            assert authenticated_page.locator("h1").contains("Dashboard")
    """
    # The backend's JWT secret is auto-generated at boot (dev mode), so a
    # token minted in this process is REJECTED by the live backend (401 on
    # every API call). Login through the backend's own endpoint instead so
    # the token is signed with its real secret.
    from tests.e2e_ui.utils.api_setup import APIClient, authenticate_user
    api = APIClient(base_url=os.getenv("E2E_API_URL", "http://localhost:8001"))
    auth_resp = authenticate_user(
        api, email=test_user.email, password="TestPassword123!"
    )
    token = auth_resp["access_token"]

    # Create new browser context and page
    context = browser.new_context()
    page = context.new_page()

    # The frontend middleware (middleware.ts) gates every route on the
    # auth_token COOKIE (set by lib/auth.ts on login) — localStorage alone
    # is not enough, otherwise the middleware redirects to /login. Pre-seed
    # the cookie on the context so page-load requests carry it.
    context.add_cookies([
        {"name": "auth_token", "value": token, "url": "http://localhost:3001"},
    ])

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
        hashed_password=get_password_hash("AdminPassword123!"),
        first_name="Test",
        last_name="Admin",
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


@pytest.fixture(scope="function")
def authenticated_page_api(browser: Browser, base_url: str, setup_test_user: dict):
    """Create authenticated page using API-first authentication (bypasses UI login).

    This fixture is 10-100x faster than authenticated_page because it:
    - Creates user via API (no UI form fill)
    - Logs in via API endpoint
    - Injects JWT token directly to localStorage
    - Skips navigation to login page

    Args:
        browser: Playwright browser fixture (session-scoped)
        base_url: Base URL fixture
        setup_test_user: API fixture that creates test user and returns token

    Yields:
        Page: Authenticated Playwright page object

    Example:
        def test_authenticated_page(authenticated_page_api):
            authenticated_page_api.goto(f"{base_url}/agents")
            # User already authenticated, no login needed
    """
    # Get user data and token from API fixture
    user_data = setup_test_user
    access_token = user_data.get("access_token")
    user_email = user_data.get("email")

    # Create new browser context and page
    context = browser.new_context()
    page = context.new_page()

    # Frontend middleware (middleware.ts) gates routes on the auth_token
    # COOKIE — localStorage alone gets redirected to /login. Pre-seed the
    # cookie so page-load requests pass the middleware gate.
    context.add_cookies([
        {"name": "auth_token", "value": access_token, "url": base_url},
    ])

    # Inject JWT token to localStorage (bypass UI login)
    page.goto(base_url)
    page.evaluate(f"""() => {{
        localStorage.setItem('access_token', '{access_token}');
        localStorage.setItem('auth_token', '{access_token}');
        localStorage.setItem('user_email', '{user_email}');
    }}""")

    yield page

    # Cleanup: close page and context
    page.close()
    context.close()

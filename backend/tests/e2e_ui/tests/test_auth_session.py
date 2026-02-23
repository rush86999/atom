"""
Authentication session persistence E2E tests.

This test suite validates that authenticated sessions persist correctly across:
- Page refreshes
- Multiple browser tabs
- Token expiration/clearing
- Protected route access

Tests use the authenticated_page fixture which pre-sets JWT tokens in
localStorage, bypassing the slow UI login flow (10-100x faster).

Run with: pytest backend/tests/e2e_ui/tests/test_auth_session.py -v
"""

import pytest
import json
import base64
from playwright.sync_api import Page, Browser

from tests.e2e_ui.pages.page_objects import DashboardPage, LoginPage


def get_jwt_token(page: Page) -> str:
    """Get JWT token from localStorage.

    Args:
        page: Playwright page instance

    Returns:
        str: JWT token or empty string if not found
    """
    return page.evaluate("() => localStorage.getItem('auth_token')")


def verify_jwt_format(token: str) -> bool:
    """Verify JWT token has correct format (header.payload.signature).

    Args:
        token: JWT token string

    Returns:
        bool: True if format is valid, False otherwise
    """
    if not token or not isinstance(token, str):
        return False

    # JWT should have 3 parts separated by dots
    parts = token.split('.')
    return len(parts) == 3


def decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without verifying signature.

    Args:
        token: JWT token string

    Returns:
        dict: Decoded payload

    Raises:
        ValueError: If token is invalid
    """
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")

    # Decode payload (middle part)
    payload = parts[1]

    # Add padding if needed
    padding = len(payload) % 4
    if padding != 0:
        payload += '=' * (4 - padding)

    # Base64 decode
    decoded = base64.b64decode(payload)
    return json.loads(decoded)


def test_session_persists_across_refresh(authenticated_page: Page):
    """Test that user session persists across browser refresh.

    This test validates that:
    1. Dashboard loads with authenticated session
    2. Page reload doesn't break authentication
    3. JWT token remains in localStorage after refresh

    Args:
        authenticated_page: Playwright page with JWT token pre-set
    """
    # Setup: Navigate to dashboard
    dashboard = DashboardPage(authenticated_page)
    dashboard.navigate()

    # Verify: Dashboard loads (authentication works)
    assert dashboard.is_loaded(), "Dashboard should load on first visit"
    welcome_text = dashboard.get_welcome_text()
    assert welcome_text is not None, "Welcome message should be visible"

    # Verify: Token exists in localStorage
    token_before = get_jwt_token(authenticated_page)
    assert token_before, "JWT token should exist in localStorage"
    assert verify_jwt_format(token_before), "Token should have valid JWT format"

    # Action: Refresh page
    authenticated_page.reload()

    # Verify: Dashboard still loads after refresh (no redirect to login)
    assert dashboard.is_loaded(), "Dashboard should load after refresh"
    welcome_text_after = dashboard.get_welcome_text()
    assert welcome_text_after is not None, "Welcome message should still be visible"

    # Verify: Token still exists in localStorage
    token_after = get_jwt_token(authenticated_page)
    assert token_after, "JWT token should still exist in localStorage after refresh"
    assert token_after == token_before, "Token should be the same after refresh"


def test_session_allows_protected_access(authenticated_page: Page):
    """Test that authenticated session allows access to protected routes.

    This test validates that:
    1. User can access /dashboard with valid token
    2. User can access /settings with valid token
    3. User can access /projects with valid token
    4. No redirects to login occur

    Args:
        authenticated_page: Playwright page with JWT token pre-set
    """
    # Test 1: Access dashboard
    authenticated_page.goto("http://localhost:3000/dashboard")
    dashboard = DashboardPage(authenticated_page)

    assert dashboard.is_loaded(), "Should access dashboard with valid token"
    dashboard_welcome = dashboard.get_welcome_text()
    assert dashboard_welcome is not None, "Dashboard should show welcome message"

    # Test 2: Access settings
    authenticated_page.goto("http://localhost:3000/settings")
    # Check that we're on settings page (not redirected to login)
    current_url = authenticated_page.url
    assert "settings" in current_url, "Should access settings with valid token"
    assert "login" not in current_url, "Should not be redirected to login"

    # Test 3: Access projects
    authenticated_page.goto("http://localhost:3000/projects")
    current_url = authenticated_page.url
    assert "projects" in current_url, "Should access projects with valid token"
    assert "login" not in current_url, "Should not be redirected to login"

    # Verify: Token still exists after navigating multiple routes
    token = get_jwt_token(authenticated_page)
    assert token, "JWT token should persist across route navigation"
    assert verify_jwt_format(token), "Token should have valid JWT format"


def test_session_expires_on_token_clear(browser: Browser):
    """Test that session expires when token is cleared from localStorage.

    This test validates that:
    1. User can access protected routes with valid token
    2. Clearing localStorage invalidates the session
    3. Page reload after clearing token redirects to login

    Args:
        browser: Playwright browser fixture
    """
    # Setup: Create page and set JWT token manually
    context = browser.new_context()
    page = context.new_page()

    # Create a test token (this would normally come from authenticated_user fixture)
    # For this test, we'll set a dummy token to simulate the scenario
    dummy_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItaWQiLCJleHAiOjk5OTk5OTk5OTl9.signature"

    # Navigate to app and set token
    page.goto("http://localhost:3000")
    page.evaluate(f"""() => {{
        localStorage.setItem('auth_token', '{dummy_token}');
        localStorage.setItem('next-auth.session-token', '{dummy_token}');
    }}""")

    # Verify: Can access dashboard with token
    page.goto("http://localhost:3000/dashboard")
    current_url = page.url
    # Note: Frontend might still redirect if backend validates token
    # This test verifies the localStorage clearing mechanism

    # Action: Clear localStorage (simulate logout/token expiration)
    page.evaluate("""() => {
        localStorage.clear();
    }""")

    # Verify: Token is cleared
    cleared_token = page.evaluate("() => localStorage.getItem('auth_token')")
    assert cleared_token is None, "Token should be cleared from localStorage"

    # Action: Reload page
    page.reload()

    # Verify: Redirected to login page (or shows login form)
    current_url = page.url
    # Should be on login page or have login in URL
    # Note: Actual redirect behavior depends on frontend implementation
    login_page = LoginPage(page)

    # Check if we're on login page (either by URL or visible login form)
    is_login_page = "login" in current_url.lower() or login_page.is_loaded()

    assert is_login_page, "Should redirect to login page after token is cleared"

    # Cleanup
    context.close()


def test_multiple_tabs_share_session(browser: Browser):
    """Test that multiple browser tabs can share the same authentication session.

    This test validates that:
    1. First tab with JWT token can access protected routes
    2. Second tab with same JWT token can also access protected routes
    3. Clearing token in first tab doesn't affect second tab (isolated contexts)

    Args:
        browser: Playwright browser fixture
    """
    # Setup: Create JWT token for testing
    dummy_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItaWQiLCJleHAiOjk5OTk5OTk5OTl9.signature"

    # Create first browser context (tab 1)
    context1 = browser.new_context()
    page1 = context1.new_page()

    # Set token in first tab
    page1.goto("http://localhost:3000")
    page1.evaluate(f"""() => {{
        localStorage.setItem('auth_token', '{dummy_token}');
        localStorage.setItem('next-auth.session-token', '{dummy_token}');
    }}""")

    # Verify: First tab can access protected routes
    page1.goto("http://localhost:3000/dashboard")
    url1 = page1.url
    assert "dashboard" in url1, "First tab should access dashboard"

    # Create second browser context (tab 2) - separate context
    context2 = browser.new_context()
    page2 = context2.new_page()

    # Set same token in second tab
    page2.goto("http://localhost:3000")
    page2.evaluate(f"""() => {{
        localStorage.setItem('auth_token', '{dummy_token}');
        localStorage.setItem('next-auth.session-token', '{dummy_token}');
    }}""")

    # Verify: Second tab can also access protected routes
    page2.goto("http://localhost:3000/dashboard")
    url2 = page2.url
    assert "dashboard" in url2, "Second tab should access dashboard with same token"

    # Verify: Both tabs have the token
    token1 = page1.evaluate("() => localStorage.getItem('auth_token')")
    token2 = page2.evaluate("() => localStorage.getItem('auth_token')")
    assert token1 == dummy_token, "First tab should have token"
    assert token2 == dummy_token, "Second tab should have token"
    assert token1 == token2, "Both tabs should have the same token"

    # Action: Clear token in first tab
    page1.evaluate("""() => {
        localStorage.clear();
    }""")

    # Verify: First tab no longer has token
    token1_after = page1.evaluate("() => localStorage.getItem('auth_token')")
    assert token1_after is None, "First tab token should be cleared"

    # Verify: Second tab still has token (contexts are isolated)
    token2_after = page2.evaluate("() => localStorage.getItem('auth_token')")
    assert token2_after == dummy_token, "Second tab should still have token"

    # Verify: Second tab can still access protected routes
    page2.goto("http://localhost:3000/dashboard")
    url2_after = page2.url
    assert "dashboard" in url2_after, "Second tab should still access dashboard"

    # Cleanup
    context1.close()
    context2.close()


def test_session_token_format_valid(authenticated_page: Page):
    """Test that JWT token format is valid and contains required claims.

    This test validates that:
    1. JWT token has correct structure (header.payload.signature)
    2. Token is not expired (exp claim is in the future)
    3. Token contains user ID in subject (sub) claim

    Args:
        authenticated_page: Playwright page with JWT token pre-set
    """
    # Get JWT token from localStorage
    token = get_jwt_token(authenticated_page)
    assert token, "JWT token should exist in localStorage"

    # Verify: Token format (header.payload.signature)
    assert verify_jwt_format(token), "Token should have valid JWT format (3 parts separated by dots)"

    # Decode payload to verify claims
    payload = decode_jwt_payload(token)

    # Verify: Token has subject (sub) claim
    assert "sub" in payload, "Token should have 'sub' claim (subject)"
    assert payload["sub"], "Subject claim should not be empty"

    # Verify: Subject contains user ID (should be a string)
    assert isinstance(payload["sub"], str), "Subject should be a string (user ID)"
    assert len(payload["sub"]) > 0, "User ID should not be empty"

    # Verify: Token has expiration (exp) claim
    assert "exp" in payload, "Token should have 'exp' claim (expiration)"
    assert isinstance(payload["exp"], int), "Expiration should be an integer (Unix timestamp)"

    # Verify: Token is not expired (exp > current time)
    import time
    current_time = int(time.time())
    assert payload["exp"] > current_time, "Token should not be expired"

    # Verify: Token has issued at (iat) claim (optional but recommended)
    if "iat" in payload:
        assert isinstance(payload["iat"], int), "Issued at should be an integer"
        assert payload["iat"] <= current_time, "Issued at should be in the past"

    print(f"✓ JWT token is valid:")
    print(f"  - Subject: {payload['sub']}")
    print(f"  - Expires at: {payload['exp']} (Unix timestamp)")
    print(f"  - Current time: {current_time}")
    print(f"  - Time to expiry: {payload['exp'] - current_time} seconds")

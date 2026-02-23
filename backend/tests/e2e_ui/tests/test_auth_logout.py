"""
E2E UI tests for user logout flow.

This test suite validates the complete logout workflow including:
- Logout via dashboard user menu
- Session cleanup (JWT token removal from localStorage)
- Redirect to login page after logout
- Blocking of protected route access after logout
- Re-login after logout

Uses existing fixtures and Page Objects for fast, reliable tests.
"""

import pytest
from tests.e2e_ui.pages.page_objects import LoginPage, DashboardPage


def get_auth_token(page):
    """Get JWT auth token from localStorage.

    Args:
        page: Playwright page instance

    Returns:
        str or None: JWT token value or None if not set
    """
    return page.evaluate("() => localStorage.getItem('auth_token')")


def get_next_auth_token(page):
    """Get next-auth session token from localStorage.

    Args:
        page: Playwright page instance

    Returns:
        str or None: Session token value or None if not set
    """
    return page.evaluate("() => localStorage.getItem('next-auth.session-token')")


def assert_no_token(page):
    """Assert that no auth tokens exist in localStorage.

    Args:
        page: Playwright page instance

    Raises:
        AssertionError: If any auth token is found
    """
    token = get_auth_token(page)
    next_auth = get_next_auth_token(page)

    assert token is None or token == "", \
        f"auth_token should be cleared after logout, got: {token}"
    assert next_auth is None or next_auth == "", \
        f"next-auth.session-token should be cleared after logout, got: {next_auth}"


class TestLogoutFlow:
    """Tests for user logout functionality."""

    def test_logout_via_user_menu(self, authenticated_page):
        """Test logout via dashboard user menu.

        This test verifies:
        1. Dashboard is loaded (user is authenticated)
        2. User profile button is visible
        3. Logout button appears in menu
        4. Clicking logout redirects to login page
        5. Login form is displayed after logout

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Setup: Start on authenticated dashboard
        dashboard = DashboardPage(authenticated_page)
        dashboard.navigate()
        assert dashboard.is_loaded(), "Dashboard should be loaded for authenticated user"

        # Verify user profile button is visible
        assert dashboard.user_profile_button.is_visible(), \
            "User profile button should be visible on dashboard"

        # Action: Logout via user menu
        dashboard.click_user_profile()

        # Verify logout button is visible in menu
        assert dashboard.logout_button.is_visible(), \
            "Logout button should be visible in user menu"

        # Click logout button
        dashboard.click_logout()

        # Wait for redirect to login page
        authenticated_page.wait_for_timeout(1000)

        # Verify: Redirected to login page
        login = LoginPage(authenticated_page)
        assert login.is_loaded(), "User should be redirected to login page after logout"

        # Verify login form is displayed
        assert login.email_input.is_visible(), "Login email input should be visible"
        assert login.password_input.is_visible(), "Login password input should be visible"
        assert login.submit_button.is_visible(), "Login submit button should be visible"

    def test_logout_clears_session(self, authenticated_page):
        """Test that logout clears JWT token from localStorage.

        This test verifies:
        1. JWT token exists before logout
        2. next-auth.session-token exists before logout
        3. Both tokens are cleared after logout
        4. No auth tokens remain in localStorage

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to dashboard
        dashboard = DashboardPage(authenticated_page)
        dashboard.navigate()

        # Verify JWT token exists in localStorage before logout
        token_before = get_auth_token(authenticated_page)
        assert token_before is not None and len(token_before) > 50, \
            f"JWT token should exist before logout, got: {token_before[:20] if token_before else 'None'}..."

        # Verify next-auth token exists
        next_auth_before = get_next_auth_token(authenticated_page)
        assert next_auth_before is not None, \
            "next-auth.session-token should exist before logout"

        # Execute logout
        dashboard.logout()

        # Wait for logout to complete
        authenticated_page.wait_for_timeout(1000)

        # Check localStorage for auth_token - should be cleared
        token_after = get_auth_token(authenticated_page)
        assert token_after is None or token_after == "", \
            f"auth_token should be None or empty after logout, got: {token_after}"

        # Check next-auth.session-token - should also be cleared
        next_auth_after = get_next_auth_token(authenticated_page)
        assert next_auth_after is None or next_auth_after == "", \
            f"next-auth.session-token should be None or empty after logout, got: {next_auth_after}"

        # Verify using helper
        assert_no_token(authenticated_page)

    def test_logout_blocks_protected_access(self, authenticated_page):
        """Test that protected routes are inaccessible after logout.

        This test verifies:
        1. User can access dashboard before logout
        2. After logout, /settings redirects to login
        3. After logout, /projects redirects to login
        4. Auth tokens are cleared

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to dashboard (should work)
        dashboard = DashboardPage(authenticated_page)
        dashboard.navigate()
        assert dashboard.is_loaded(), "Dashboard should be accessible before logout"

        # Execute logout
        dashboard.logout()

        # Wait for logout to complete
        authenticated_page.wait_for_timeout(1000)

        # Attempt to navigate to /settings directly
        authenticated_page.goto("http://localhost:3000/settings", wait_until="domcontentloaded")

        # Verify redirect to login page
        current_url = authenticated_page.url
        assert "login" in current_url.lower(), \
            f"Accessing /settings after logout should redirect to login, got URL: {current_url}"

        # Attempt to navigate to /projects directly
        authenticated_page.goto("http://localhost:3000/projects", wait_until="domcontentloaded")

        # Verify redirect to login page again
        current_url = authenticated_page.url
        assert "login" in current_url.lower(), \
            f"Accessing /projects after logout should redirect to login, got URL: {current_url}"

        # Verify tokens are cleared
        assert_no_token(authenticated_page)

    def test_logout_and_relogin_works(self, authenticated_page, test_user):
        """Test that user can log out and log back in.

        This test verifies:
        1. User is logged in initially
        2. Logout works correctly
        3. User is on login page after logout
        4. User can log in again with same credentials
        5. User is redirected to dashboard after re-login
        6. JWT token is set again in localStorage

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
            test_user: Test user fixture (with email and password)
        """
        # Navigate to dashboard (authenticated)
        dashboard = DashboardPage(authenticated_page)
        dashboard.navigate()
        assert dashboard.is_loaded(), "User should be logged in initially"

        # Get initial token
        initial_token = get_auth_token(authenticated_page)
        assert initial_token is not None and len(initial_token) > 50, \
            "Initial token should exist"

        # Logout
        dashboard.logout()

        # Wait for redirect
        authenticated_page.wait_for_timeout(1000)

        # Verify on login page
        login = LoginPage(authenticated_page)
        assert login.is_loaded(), "User should be on login page after logout"

        # Verify tokens are cleared
        assert_no_token(authenticated_page)

        # Login again using LoginPage with same credentials
        # Note: test_user has password "TestPassword123!" from auth_fixtures.py
        login.login(
            email=test_user.email,
            password="TestPassword123!"
        )

        # Wait for navigation after login
        authenticated_page.wait_for_timeout(2000)

        # Verify redirect to dashboard
        dashboard_after_login = DashboardPage(authenticated_page)
        assert dashboard_after_login.is_loaded(), \
            "User should be redirected to dashboard after re-login"

        # Verify token is set again
        new_token = get_auth_token(authenticated_page)
        assert new_token is not None and len(new_token) > 50, \
            f"JWT token should be set after re-login, got: {new_token[:20] if new_token else 'None'}..."

        # Verify it's a different token (optional, but good for security)
        # Note: JWTs include timestamp, so tokens should be different
        # assert new_token != initial_token, "New login should generate a different token"

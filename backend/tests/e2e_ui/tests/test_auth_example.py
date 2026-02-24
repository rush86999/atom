"""
Example E2E UI tests demonstrating authentication fixtures.

This test file demonstrates how to use the authenticated_page fixture
to test authenticated workflows without going through the slow UI login flow.

Performance: API-first auth is 10-100x faster than UI login.
"""

import pytest
from typing import Dict, Any
from tests.e2e_ui.pages.page_objects import DashboardPage, SettingsPage


class TestAuthenticatedAccess:
    """Tests for authenticated page access using API-first auth."""

    def test_authenticated_user_can_access_dashboard(self, authenticated_page):
        """Test that authenticated_page fixture provides access to dashboard.

        This test verifies that:
        1. JWT token is set in localStorage by the fixture
        2. Dashboard is accessible without redirect to login
        3. User can see welcome message

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage

        Performance: ~2 seconds (vs 10+ seconds for UI login)
        """
        # Navigate to dashboard
        dashboard = DashboardPage(authenticated_page)
        dashboard.navigate()

        # Verify dashboard is loaded (no redirect to login)
        assert dashboard.is_loaded(), "Dashboard should be loaded with authenticated page"

        # Verify welcome message is visible
        welcome_text = dashboard.get_welcome_text()
        assert welcome_text is not None, "Welcome message should be visible"
        assert "Welcome" in welcome_text or "Dashboard" in welcome_text, \
            f"Welcome text should contain greeting, got: {welcome_text}"

    def test_authenticated_page_has_token_in_localstorage(self, authenticated_page):
        """Test that authenticated_page has JWT token in localStorage.

        Verifies the fixture successfully set the auth token before test.

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Check localStorage for auth token
        token = authenticated_page.evaluate("() => localStorage.getItem('auth_token')")

        assert token is not None, "JWT token should be set in localStorage"
        assert len(token) > 50, f"JWT token should be long enough, got length {len(token)}"

        # Also check next-auth token
        next_auth_token = authenticated_page.evaluate(
            "() => localStorage.getItem('next-auth.session-token')"
        )
        assert next_auth_token is not None, "NextAuth token should also be set"

    def test_authenticated_user_can_access_settings(self, authenticated_page):
        """Test that authenticated user can access settings page.

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to settings
        settings = SettingsPage(authenticated_page)
        settings.navigate()

        # Verify settings page is loaded
        assert settings.is_loaded(), "Settings should be loaded with authenticated page"

        # Verify theme toggle is visible
        assert settings.theme_toggle.is_visible(), "Theme toggle should be visible"

    def test_authenticated_user_can_change_theme(self, authenticated_page):
        """Test that authenticated user can change theme in settings.

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to settings
        settings = SettingsPage(authenticated_page)
        settings.navigate()

        # Get current theme
        current_theme = settings.get_current_theme()

        # Toggle theme
        settings.toggle_theme()

        # Verify theme changed
        new_theme = settings.get_current_theme()
        assert new_theme != current_theme, \
            f"Theme should have changed from {current_theme} to {new_theme}"

    def test_authenticated_user_can_logout(self, authenticated_page):
        """Test that authenticated user can logout.

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Start on dashboard
        dashboard = DashboardPage(authenticated_page)
        dashboard.navigate()

        # Verify logged in
        assert dashboard.is_loaded(), "Should be logged in initially"

        # Logout
        dashboard.logout()

        # Verify redirected to login or logged out state
        # After logout, we should NOT see dashboard content
        authenticated_page.wait_for_timeout(1000)  # Wait for redirect
        is_on_dashboard = dashboard.welcome_message.is_visible()
        assert not is_on_dashboard, "Should not see dashboard after logout"


class TestUnauthenticatedAccess:
    """Tests for unauthenticated access (without auth fixtures)."""

    def test_unauthenticated_user_cannot_access_dashboard(self, page):
        """Test that unauthenticated user cannot access dashboard.

        Verifies that without auth, dashboard redirects to login.

        Args:
            page: Regular page fixture (no authentication)
        """
        # Try to navigate to dashboard
        page.goto("http://localhost:3001/dashboard")

        # Should be redirected to login
        current_url = page.url
        assert "login" in current_url.lower(), \
            f"Unauthenticated access should redirect to login, got URL: {current_url}"

    def test_unauthenticated_user_no_token_in_localstorage(self, page):
        """Test that regular page fixture has no auth token.

        Verifies the default page fixture doesn't set authentication.

        Args:
            page: Regular page fixture (no authentication)
        """
        # Check localStorage for auth token
        token = page.evaluate("() => localStorage.getItem('auth_token')")

        assert token is None, "Regular page should not have auth token in localStorage"


class TestPageObjectIntegration:
    """Tests demonstrating Page Object integration with auth fixtures."""

    def test_login_page_object_with_unauthenticated_page(self, page):
        """Test LoginPage Page Object with unauthenticated page.

        Args:
            page: Regular page fixture (no authentication)
        """
        from tests.e2e_ui.pages.page_objects import LoginPage

        # Navigate to login
        login_page = LoginPage(page)
        login_page.navigate()

        # Verify login page is loaded
        assert login_page.is_loaded(), "Login page should be loaded"

        # Verify form elements are visible
        assert login_page.email_input.is_visible(), "Email input should be visible"
        assert login_page.password_input.is_visible(), "Password input should be visible"
        assert login_page.submit_button.is_visible(), "Submit button should be visible"

    def test_dashboard_page_object_with_authenticated_page(self, authenticated_page):
        """Test DashboardPage Page Object with authenticated page.

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Dashboard should be accessible
        dashboard = DashboardPage(authenticated_page)
        dashboard.navigate()

        # Verify all main elements are visible
        assert dashboard.welcome_message.is_visible(), "Welcome message should be visible"
        assert dashboard.navigation_menu.is_visible(), "Navigation menu should be visible"

        # Can interact with page
        dashboard.click_user_profile()
        assert dashboard.logout_button.is_visible(), "Logout button should appear in menu"

    def test_settings_page_object_with_authenticated_page(self, authenticated_page):
        """Test SettingsPage Page Object with authenticated page.

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Settings should be accessible
        settings = SettingsPage(authenticated_page)
        settings.navigate()

        # Verify all main sections are visible
        assert settings.theme_toggle.is_visible(), "Theme toggle should be visible"
        assert settings.notifications_section.is_visible(), "Notifications section should be visible"
        assert settings.save_button.is_visible(), "Save button should be visible"

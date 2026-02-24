"""
E2E UI tests for Settings page functionality.

This test suite validates settings page access and preference updates:
- Theme preference (light/dark mode toggle)
- Notification preferences (email and push notifications)
- Settings persistence across page refresh
- Unauthenticated access control

Tests use authenticated_page fixture for API-first authentication (10-100x faster than UI login).
"""

import pytest
from typing import Dict, Any
from playwright.sync_api import Page
from tests.e2e_ui.pages.page_objects import SettingsPage, LoginPage


class TestSettingsPageAccess:
    """Tests for settings page access and navigation."""

    def test_access_settings_page(self, authenticated_page):
        """Test that authenticated user can access settings page.

        Verifies:
        1. Settings page loads successfully
        2. Theme toggle is visible
        3. All sections are present (Theme, Notifications, Account)
        4. Save button is visible

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to settings
        settings = SettingsPage(authenticated_page)
        settings.navigate()

        # Verify settings page loads (theme_toggle is visible)
        assert settings.is_loaded(), "Settings page should be loaded"

        # Verify all sections are present
        assert settings.theme_toggle.is_visible(), "Theme toggle should be visible"
        assert settings.theme_label.is_visible(), "Theme label should be visible"

        assert settings.notifications_section.is_visible(), \
            "Notifications section should be visible"
        assert settings.email_notifications_checkbox.is_visible(), \
            "Email notifications checkbox should be visible"
        assert settings.push_notifications_checkbox.is_visible(), \
            "Push notifications checkbox should be visible"

        assert settings.account_section.is_visible(), \
            "Account section should be visible"
        assert settings.security_section.is_visible(), \
            "Security section should be visible"

        # Verify save button is visible
        assert settings.save_button.is_visible(), "Save button should be visible"


class TestThemePreference:
    """Tests for theme preference functionality."""

    def test_update_theme_preference(self, authenticated_page):
        """Test that user can update theme preference and it persists.

        Verifies:
        1. Initial theme can be retrieved
        2. Theme can be toggled
        3. Save button shows success message
        4. Theme changes after toggle
        5. Theme persists across page reload

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to settings
        settings = SettingsPage(authenticated_page)
        settings.navigate()

        # Get current theme
        initial_theme = settings.get_current_theme()
        assert initial_theme in ["Light", "Dark"], \
            f"Initial theme should be Light or Dark, got: {initial_theme}"

        # Toggle theme
        settings.toggle_theme()

        # Click save button
        settings.click_save()

        # Wait for success message
        authenticated_page.wait_for_timeout(500)  # Brief wait for save operation

        # Verify theme changed
        new_theme = settings.get_current_theme()
        assert new_theme != initial_theme, \
            f"Theme should have changed from {initial_theme} to {new_theme}"

        # Reload page
        authenticated_page.reload()

        # Wait for page to load after reload
        settings.wait_for_load(timeout=5000)

        # Verify theme persists (still the changed theme)
        persisted_theme = settings.get_current_theme()
        assert persisted_theme == new_theme, \
            f"Theme should persist as {new_theme} after reload, got: {persisted_theme}"


class TestNotificationPreferences:
    """Tests for notification preference functionality."""

    def test_toggle_notifications(self, authenticated_page):
        """Test that user can toggle notification preferences.

        Verifies:
        1. Initial notification state can be retrieved
        2. Email notifications can be toggled
        3. Push notifications can be toggled
        4. Save button shows success message
        5. Checkbox states reflect changes

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to settings
        settings = SettingsPage(authenticated_page)
        settings.navigate()

        # Get initial email notification state
        initial_email_checked = settings.email_notifications_checkbox.is_checked()

        # Toggle email notifications
        new_email_state = not initial_email_checked
        settings.set_email_notifications(new_email_state)

        # Get initial push notification state
        initial_push_checked = settings.push_notifications_checkbox.is_checked()

        # Toggle push notifications
        new_push_state = not initial_push_checked
        settings.set_push_notifications(new_push_state)

        # Click save button
        settings.click_save()

        # Verify success message displayed
        authenticated_page.wait_for_timeout(500)  # Brief wait for save operation
        success_msg = settings.get_success_message()
        assert success_msg is not None, "Success message should be displayed"
        assert "saved" in success_msg.lower(), \
            f"Success message should contain 'saved', got: {success_msg}"

        # Verify checkbox states reflect changes
        actual_email_state = settings.email_notifications_checkbox.is_checked()
        assert actual_email_state == new_email_state, \
            f"Email notifications should be {'checked' if new_email_state else 'unchecked'}"

        actual_push_state = settings.push_notifications_checkbox.is_checked()
        assert actual_push_state == new_push_state, \
            f"Push notifications should be {'checked' if new_push_state else 'unchecked'}"


class TestSettingsPersistence:
    """Tests for settings persistence across page refresh."""

    def test_settings_persist_across_refresh(self, authenticated_page):
        """Test that settings persist across page refresh.

        Verifies:
        1. Theme can be changed to dark mode
        2. Email notifications can be enabled
        3. Settings save successfully
        4. Settings persist after page reload
        5. Multiple settings persist together

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to settings
        settings = SettingsPage(authenticated_page)
        settings.navigate()

        # Change theme to dark
        settings.set_theme("dark")

        # Enable email notifications
        settings.set_email_notifications(True)

        # Save settings
        settings.click_save()

        # Wait for save confirmation
        authenticated_page.wait_for_timeout(500)

        # Verify theme is dark before reload
        theme_before = settings.get_current_theme()
        email_checked_before = settings.email_notifications_checkbox.is_checked()

        # Reload page
        authenticated_page.reload()

        # Wait for page to load after reload
        settings.wait_for_load(timeout=5000)

        # Verify theme is still dark
        theme_after = settings.get_current_theme()
        assert theme_after == "Dark", \
            f"Theme should persist as Dark after reload, got: {theme_after}"

        # Verify email notifications still enabled
        email_checked_after = settings.email_notifications_checkbox.is_checked()
        assert email_checked_after is True, \
            "Email notifications should still be enabled after reload"


class TestUnauthenticatedAccess:
    """Tests for unauthenticated access control."""

    def test_unauthenticated_cannot_access_settings(self, browser):
        """Test that unauthenticated user cannot access settings page.

        Verifies:
        1. Unauthenticated user is redirected to login
        2. Settings page is not accessible without auth

        Args:
            browser: Playwright browser fixture (creates new unauthenticated context)
        """
        # Create new page context (no auth token)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Navigate to settings
            page.goto("http://localhost:3000/settings")

            # Wait for redirect
            page.wait_for_timeout(1000)

            # Verify redirect to login page
            current_url = page.url
            assert "login" in current_url.lower(), \
                f"Unauthenticated user should be redirected to login, got URL: {current_url}"

            # Verify settings page not accessible
            # Try to find theme toggle - should not exist on login page
            theme_toggle_exists = page.locator('[data-testid="settings-theme-toggle"]').count() > 0
            assert not theme_toggle_exists, \
                "Settings page elements should not be accessible to unauthenticated users"

            # Verify we're actually on login page by checking for login elements
            login_page = LoginPage(page)
            assert login_page.is_loaded(), \
                "Should be on login page after redirect from settings"

        finally:
            # Cleanup: Close context
            context.close()

"""
E2E UI tests for Settings page functionality.

This test suite validates settings page access and preference updates:
- Theme preference (light/dark/system select)
- Notification preference (enable/disable switch)
- Email digest frequency (daily/weekly/never select)
- Settings persistence across page refresh
- Unauthenticated access control

NOTE (2026-08-12 repair): the real settings UI is
frontend-nextjs/components/Settings/PreferencesTab.tsx — an AUTO-SAVE form
(no Save button, no success toast; every change POSTs to /api/v1/preferences
immediately). The previous suite targeted a settings UI that does not exist
(email/push checkboxes, save button, success message, account/security
sections) and used testids that were never wired. Tests now target the real
component; the canonical testid contract lives in
frontend-nextjs/src/lib/testIds.ts (SETTINGS.THEME_TOGGLE /
NOTIFICATIONS_TOGGLE / PREFERENCES_SECTION).

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
        2. Theme select and current-theme label are visible
        3. Notifications section is present (switch + email frequency select)

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to settings
        settings = SettingsPage(authenticated_page)
        settings.navigate()

        # Verify settings page loads (theme_toggle is visible)
        assert settings.is_loaded(), "Settings page should be loaded"

        # Verify preferences section is present
        assert settings.preferences_section.is_visible(), \
            "Preferences section should be visible"

        # Verify theme controls are present
        assert settings.theme_toggle.is_visible(), "Theme select should be visible"
        assert settings.theme_label.is_visible(), "Theme label should be visible"

        # Verify notifications section is present
        assert settings.notifications_section.is_visible(), \
            "Notifications section should be visible"
        assert settings.notifications_toggle.is_visible(), \
            "Notifications switch should be visible"
        assert settings.email_frequency_select.is_visible(), \
            "Email frequency select should be visible"


class TestThemePreference:
    """Tests for theme preference functionality."""

    def test_update_theme_preference(self, authenticated_page):
        """Test that user can update theme preference and it persists.

        Verifies:
        1. Initial theme can be retrieved
        2. Theme can be toggled via the select dropdown
        3. Theme changes after toggle
        4. Theme persists across page reload (auto-save round-trip)

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to settings
        settings = SettingsPage(authenticated_page)
        settings.navigate()

        # Get current theme
        initial_theme = settings.get_current_theme()
        assert initial_theme in ["Light", "Dark", "System"], \
            f"Initial theme should be Light, Dark or System, got: {initial_theme}"

        # Toggle theme (auto-save UI — no Save button to click)
        settings.toggle_theme()
        settings.click_save()  # waits for the auto-save round-trip

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
        2. Notifications can be toggled via the switch
        3. Switch state reflects the change
        4. Preference persists across page reload (auto-save round-trip)

        Args:
            authenticated_page: Page with JWT token pre-set in localStorage
        """
        # Navigate to settings
        settings = SettingsPage(authenticated_page)
        settings.navigate()

        # Get initial notification state
        initial_enabled = settings.is_notifications_enabled()

        # Toggle notifications (auto-save UI — no Save button to click)
        new_state = not initial_enabled
        settings.set_notifications(new_state)
        settings.click_save()  # waits for the auto-save round-trip

        # Verify switch state reflects the change
        actual_state = settings.is_notifications_enabled()
        assert actual_state == new_state, \
            f"Notifications should be {'enabled' if new_state else 'disabled'}"

        # Reload page
        authenticated_page.reload()
        settings.wait_for_load(timeout=5000)

        # Verify preference persists
        persisted_state = settings.is_notifications_enabled()
        assert persisted_state == new_state, \
            f"Notifications should persist as {'enabled' if new_state else 'disabled'} after reload"


class TestSettingsPersistence:
    """Tests for settings persistence across page refresh."""

    def test_settings_persist_across_refresh(self, authenticated_page):
        """Test that settings persist across page refresh.

        Verifies:
        1. Theme can be changed to dark mode
        2. Notifications can be enabled
        3. Settings save automatically
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

        # Enable notifications
        settings.set_notifications(True)

        # Auto-save round-trip
        settings.click_save()

        # Verify theme is dark before reload
        theme_before = settings.get_current_theme()
        notifications_before = settings.is_notifications_enabled()
        assert theme_before == "Dark", f"Theme should be Dark, got: {theme_before}"
        assert notifications_before is True, "Notifications should be enabled"

        # Reload page
        authenticated_page.reload()

        # Wait for page to load after reload
        settings.wait_for_load(timeout=5000)

        # Verify theme is still dark
        theme_after = settings.get_current_theme()
        assert theme_after == "Dark", \
            f"Theme should persist as Dark after reload, got: {theme_after}"

        # Verify notifications still enabled
        notifications_after = settings.is_notifications_enabled()
        assert notifications_after is True, \
            "Notifications should still be enabled after reload"


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
            page.goto("http://localhost:3001/settings")

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

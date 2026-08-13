"""
Simplified E2E User Journey Test that focuses on core functionality without excessive complexity.
This test validates the essential user path covering key features.

Aligned to the REAL UI (2026-08):
- Dashboard: h1 "ATOM Dashboard" (data-testid dashboard-welcome-message)
- Settings: auto-save preferences tab (theme select)
- Canvas: real /canvas list page + /canvas/{id} rendering route
- Chat: /chat with agent-chat-input / send-message-button / message-list
- Logout: sidebar profile menu
"""

import pytest
import re
import uuid
from playwright.sync_api import Page, expect
from tests.e2e_ui.pages.page_objects import (
    DashboardPage, SettingsPage, ChatPage,
    CanvasHostPage,
)
from tests.e2e_ui.tests.canvas_helpers import create_markdown_canvas


def _expect_url(page: Page, suffix: str, timeout: int = 15000) -> None:
    """Assert the page URL ends with `suffix` (possibly followed by a query)."""
    expect(page).to_have_url(re.compile(re.escape(suffix) + r"($|\?)"), timeout=timeout)


@pytest.mark.e2e
class TestSimplifiedUserJourney:
    """Simplified E2E test class for core user journey."""

    def test_basic_user_journey(self, authenticated_page: Page, authenticated_user, db_session):
        """Test basic user journey: dashboard, settings, canvas, logout."""
        page = authenticated_page
        user, _ = authenticated_user

        # 1. Dashboard exploration
        page.goto("http://localhost:3001/dashboard")
        dashboard = DashboardPage(page)
        assert dashboard.is_loaded(), "Dashboard should be loaded"
        welcome_text = dashboard.get_welcome_text()
        assert "ATOM Dashboard" in welcome_text, \
            f"Expected 'ATOM Dashboard' heading, got: {welcome_text!r}"

        # Agent count query is supported (may be 0 on a fresh user)
        agent_count = dashboard.get_agent_count()
        assert agent_count >= 0

        # 2. Settings persistence (auto-save theme select)
        settings = SettingsPage(page)
        settings.navigate()
        settings.hide_dev_overlays()
        assert settings.is_loaded(), "Settings page should be loaded"

        # Get initial theme and toggle it
        initial_theme = settings.get_current_theme()
        settings.toggle_theme()
        settings.click_save()
        page.wait_for_timeout(500)

        # Verify theme changed
        new_theme = settings.get_current_theme()
        assert new_theme != initial_theme, \
            f"Theme should change after toggle: {initial_theme} -> {new_theme}"

        # Reload and verify persistence
        page.reload()
        settings = SettingsPage(page)
        page.wait_for_selector("[data-testid='settings-theme-toggle']", timeout=20000)
        settings.hide_dev_overlays()
        assert settings.is_loaded(), "Settings page should reload"
        assert settings.get_current_theme() == new_theme, \
            f"Theme should persist after reload: {new_theme}"

        # Restore original theme
        if settings.get_current_theme() != initial_theme:
            settings.toggle_theme()
            settings.click_save()

        # 3. Canvas access: real list page + rendering route
        page.goto("http://localhost:3001/canvas")
        page.wait_for_selector("h1:has-text('Canvases')", timeout=20000)
        assert page.get_by_role("heading", name="Canvases").is_visible(), \
            "Canvas list page should load with its heading"

        canvas_id = create_markdown_canvas(
            db_session, user, "Journey Canvas", "# Journey Canvas\n\nRendered."
        )
        page.goto(f"http://localhost:3001/canvas/{canvas_id}")
        canvas_host = CanvasHostPage(page)
        canvas_host.wait_for_canvas_visible(timeout=10000)
        assert canvas_host.is_loaded(), "Canvas should render on /canvas/{id}"

        # 4. Logout
        dashboard = DashboardPage(page)
        dashboard.navigate()
        assert dashboard.is_loaded(), "Dashboard should be loaded before logout"
        dashboard.logout()

        # NextAuth signOut redirects to the configured signin page; the
        # session cookie must be cleared (logout is real, not cosmetic).
        _expect_url(page, "/auth/signin")
        cookies = page.context.cookies()
        assert all(c["name"] != "auth_token" for c in cookies), \
            "auth_token cookie should be cleared on logout"

        # The middleware gate must reject the now-unauthenticated browser
        page.goto("http://localhost:3001/dashboard")
        _expect_url(page, "/login")

        print("Simplified user journey test passed!")


@pytest.mark.e2e
class TestChatFunctionality:
    """Test chat functionality."""

    def test_send_message(self, authenticated_page: Page):
        """Test sending a chat message.

        The user message is appended optimistically by the chat UI, so it
        must appear in the message list regardless of LLM availability.
        """
        page = authenticated_page
        chat_page = ChatPage(page)

        chat_page.navigate()
        assert chat_page.is_loaded(), "Chat page should be loaded"

        test_message = f"Hello from simplified test {uuid.uuid4().hex[:8]}"
        chat_page.send_message(test_message)
        page.wait_for_timeout(1000)

        # Verify message appears in history (optimistic append)
        last_message = chat_page.get_last_user_message()
        assert test_message in last_message, \
            f"Expected message '{test_message}' in chat history, got: {last_message!r}"

        print("Chat functionality test passed!")


@pytest.mark.e2e
class TestCanvasFeatures:
    """Test canvas features."""

    def test_canvas_creation(self, authenticated_page: Page, authenticated_user, db_session):
        """Test that a canvas created like the agent flow does renders via the UI."""
        page = authenticated_page
        user, _ = authenticated_user

        # Navigate to canvas list
        page.goto("http://localhost:3001/canvas")
        page.wait_for_selector("h1:has-text('Canvases')", timeout=20000)
        assert page.get_by_role("heading", name="Canvases").is_visible(), \
            "Canvas list page should load"

        # Create a canvas through the same DB rows the agent tool writes
        # (Canvas + CanvasAudit), then verify the real rendering route.
        canvas_id = create_markdown_canvas(
            db_session, user, "Test Canvas", "# Test Canvas\n\nCreated for E2E."
        )
        page.goto(f"http://localhost:3001/canvas/{canvas_id}")
        canvas_host = CanvasHostPage(page)
        canvas_host.wait_for_canvas_visible(timeout=10000)

        # Verify canvas created and rendered
        assert canvas_host.is_loaded(), "Canvas host should be visible"
        assert canvas_host.is_visible(), "Canvas should be displayed"

        print("Canvas creation test passed!")

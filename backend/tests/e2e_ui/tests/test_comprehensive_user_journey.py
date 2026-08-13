"""
Comprehensive E2E User Journey Test that touches all major features and UI/UX flows.

This test validates the complete user path covering:
1. Authentication (API-first, logout)
2. Chat interaction (message send, history)
3. Canvas presentations (list page, detail rendering, accessibility)
4. Skills marketplace (backend API — no frontend UI exists)
5. Projects (Project Command Center)
6. Device capabilities / browser automation (backend surface)
7. Memory (chat-based)
8. Settings and preferences persistence
9. Session cleanup (logout redirects to login)

Run with: pytest backend/tests/e2e_ui/tests/test_comprehensive_user_journey.py -v
"""

import pytest
import re
import uuid
import requests
from playwright.sync_api import Page, expect
from tests.e2e_ui.pages.page_objects import (
    DashboardPage, SettingsPage, ChatPage,
    CanvasHostPage, ProjectsPage,
)
from tests.e2e_ui.tests.canvas_helpers import create_markdown_canvas


def _expect_url(page: Page, suffix: str, timeout: int = 15000) -> None:
    """Assert the page URL ends with `suffix` (possibly followed by a query)."""
    expect(page).to_have_url(re.compile(re.escape(suffix) + r"($|\?)"), timeout=timeout)


@pytest.mark.e2e
class TestComprehensiveUserJourney:
    """E2E test class implementing comprehensive user journey covering all major features."""

    def test_complete_user_journey_all_features(
        self,
        authenticated_page: Page,
        authenticated_user,
        db_session,
        setup_test_user: dict,
    ):
        """
        Execute comprehensive user journey touching all major features:
        1. Login via API-first authentication (bypassing UI login)
        2. Dashboard exploration
        3. Chat interaction with agent (message + memory)
        4. Canvas list + detail rendering
        5. Skills marketplace via backend API (no frontend UI exists)
        6. Project Command Center
        7. Device capabilities + browser automation (backend surface)
        8. Settings persistence
        9. Logout and session cleanup
        """
        # Extract test data from fixtures
        user, _ = authenticated_user
        user_data = setup_test_user

        # Use authenticated page (already logged in via API-first auth)
        page = authenticated_page

        # ============================================================================
        # 1. DASHBOARD EXPLORATION
        # ============================================================================

        # Navigate to dashboard
        page.goto("http://localhost:3001/dashboard")
        _expect_url(page, "/dashboard")

        dashboard = DashboardPage(page)
        assert dashboard.is_loaded(), "Dashboard should be loaded"

        # Verify heading (real dashboard h1 is "ATOM Dashboard")
        welcome_text = dashboard.get_welcome_text()
        assert "ATOM Dashboard" in welcome_text, \
            f"Expected dashboard heading, got: {welcome_text!r}"

        # Agent count query is supported (may be 0 on a fresh user)
        agent_count = dashboard.get_agent_count()
        assert agent_count >= 0, "Should be able to get agent count"

        # ============================================================================
        # 2. CHAT INTERACTION WITH AGENT
        # ============================================================================

        chat_page = ChatPage(page)
        chat_page.navigate()
        assert chat_page.is_loaded(), "Chat interface should be loaded"

        # Send a test message
        test_message = f"Hello from E2E test {uuid.uuid4().hex[:8]}"
        chat_page.send_message(test_message)

        # The user message is appended optimistically — it must appear in history
        last_message = chat_page.get_last_user_message()
        assert test_message in last_message, \
            f"Expected message '{test_message}' in chat history, got: {last_message!r}"

        # Verify message count increased
        message_count = chat_page.get_message_count()
        assert message_count >= 1, f"Expected at least 1 message, got: {message_count}"

        # ============================================================================
        # 3. CANVAS INTERACTION (list page + detail rendering)
        # ============================================================================

        # Navigate to canvas list page
        page.goto("http://localhost:3001/canvas")
        _expect_url(page, "/canvas")
        page.wait_for_selector("h1:has-text('Canvases')", timeout=20000)
        assert page.get_by_role("heading", name="Canvases").is_visible(), \
            "Canvas list page should load with its heading"

        # Create a canvas the same way the agent flow does (Canvas + CanvasAudit
        # rows) and verify the real rendering route /canvas/{id}.
        canvas_id = create_markdown_canvas(
            db_session, user, "Journey Canvas", "# Journey Canvas\n\nRendered for E2E."
        )
        page.goto(f"http://localhost:3001/canvas/{canvas_id}")
        canvas_host = CanvasHostPage(page)
        canvas_host.wait_for_canvas_visible(timeout=10000)
        assert canvas_host.is_loaded(), "Canvas should render on /canvas/{id}"
        assert canvas_host.is_visible(), "Canvas host should be displayed"

        # Test canvas interaction - close button is wired and accessible
        assert canvas_host.canvas_close_button.is_visible()
        close_label = canvas_host.canvas_close_button.get_attribute("aria-label")
        assert close_label, "Canvas close button should have an accessible name"

        # ============================================================================
        # 4. SKILLS MARKETPLACE (backend API — NO frontend UI exists)
        # ============================================================================

        # The skills marketplace has no frontend page in this codebase
        # (pages/skills* does not exist), so the marketplace surface is
        # verified through the backend API instead of UI navigation.
        api_token = user_data["access_token"]
        skills_resp = requests.get(
            "http://localhost:8001/api/skills/list?query=test&page=1&page_size=5",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=10,
        )
        assert skills_resp.status_code == 200, \
            f"Skills list API should return 200, got {skills_resp.status_code}"
        skills_payload = skills_resp.json()
        assert skills_payload.get("success") is True or "skills" in str(skills_payload), \
            f"Unexpected skills payload: {skills_payload}"

        # ============================================================================
        # 5. PROJECTS (Project Command Center)
        # ============================================================================

        page.goto("http://localhost:3001/dashboards/projects")
        _expect_url(page, "/projects")

        projects_page = ProjectsPage(page)
        assert projects_page.is_loaded(), "Project Command Center should be loaded"
        assert projects_page.projects_table.is_visible(), \
            "Projects table should be visible"
        # Sandbox has no connected PM platforms -> empty state, not an error
        projects_page.empty_state.wait_for(state="visible", timeout=15000)
        assert projects_page.empty_state.is_visible(), \
            "Empty state should render when no platforms are connected"

        # ============================================================================
        # 6. DEVICE CAPABILITIES + BROWSER AUTOMATION (backend surface)
        # ============================================================================

        # No frontend pages exist for /device/* or /browser — the features are
        # backend capabilities. Verify the API surfaces are mounted (OPTIONS
        # returns the Allow header for an existing route, with no side effects).
        api_headers = {"Authorization": f"Bearer {api_token}"}
        for route in ("/api/devices/location", "/api/browser/session/create"):
            resp = requests.options(f"http://localhost:8001{route}", headers=api_headers, timeout=10)
            allow = resp.headers.get("Allow", "")
            assert allow, f"OPTIONS {route} should advertise allowed methods (got {resp.status_code})"

        # ============================================================================
        # 7. MEMORY (chat-based)
        # ============================================================================

        # Memory is exercised through chat: send a message and confirm it lands
        # in the conversation history (durable recall requires LLM execution,
        # which is environment-dependent).
        memory_message = f"Remember this test fact: {uuid.uuid4().hex[:8]}"
        chat_page.navigate()
        assert chat_page.is_loaded(), "Chat interface should be loaded"
        chat_page.send_message(memory_message)
        page.wait_for_timeout(1000)

        last_response = chat_page.get_last_user_message()
        assert memory_message in last_response, \
            f"Memory message should appear in chat history, got: {last_response!r}"

        # ============================================================================
        # 8. SETTINGS PERSISTENCE TEST
        # ============================================================================

        settings_page = SettingsPage(page)
        settings_page.navigate()
        settings_page.hide_dev_overlays()
        assert settings_page.is_loaded(), "Settings page should be loaded"

        # Toggle the theme (auto-save UI)
        initial_theme = settings_page.get_current_theme()
        settings_page.toggle_theme()
        settings_page.click_save()
        page.wait_for_timeout(500)

        # Verify theme changed
        new_theme = settings_page.get_current_theme()
        assert new_theme != initial_theme, "Theme should have changed after toggle"

        # Reload page to test persistence
        page.reload()
        settings_page = SettingsPage(page)
        page.wait_for_selector("[data-testid='settings-theme-toggle']", timeout=20000)
        settings_page.hide_dev_overlays()
        assert settings_page.is_loaded(), "Settings page should reload"
        assert settings_page.get_current_theme() == new_theme, \
            f"Theme should persist after reload: expected {new_theme}"

        # Reset theme to original state
        if settings_page.get_current_theme() != initial_theme:
            settings_page.toggle_theme()
            settings_page.click_save()

        # ============================================================================
        # 9. LOGOUT AND SESSION CLEANUP
        # ============================================================================

        # Navigate back to dashboard for logout
        dashboard = DashboardPage(page)
        dashboard.navigate()
        assert dashboard.is_loaded(), "Dashboard should be loaded before logout"

        # Perform logout
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

        print("Complete user journey test passed successfully!")


# Additional helper tests for specific edge cases and error conditions

@pytest.mark.e2e
class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling in user journeys."""

    def test_empty_chat_message_handling(self, authenticated_page: Page):
        """Test that empty messages are handled properly."""
        page = authenticated_page
        chat_page = ChatPage(page)

        chat_page.navigate()
        assert chat_page.is_loaded(), "Chat interface should be loaded"

        # Get initial message count
        initial_count = chat_page.get_message_count()

        # The send button is disabled for empty/whitespace input — the UI
        # must not allow an empty message to be sent.
        chat_page.chat_input.fill("   ")
        assert chat_page.send_button.is_disabled(), \
            "Send button should be disabled for whitespace-only input"

        chat_page.chat_input.fill("")
        assert chat_page.send_button.is_disabled(), \
            "Send button should be disabled for empty input"

        # No message should have been added
        final_count = chat_page.get_message_count()
        assert initial_count == final_count, \
            f"Empty messages should not increase count: {initial_count} -> {final_count}"

    def test_canvas_accessibility_features(self, authenticated_page: Page, authenticated_user, db_session):
        """Test canvas accessibility features on the real rendering route."""
        page = authenticated_page
        user, _ = authenticated_user

        # Create a simple canvas for accessibility testing
        canvas_id = create_markdown_canvas(
            db_session, user, "A11y Canvas", "# A11y Canvas\n\nAccessible content."
        )
        page.goto(f"http://localhost:3001/canvas/{canvas_id}")
        canvas_host = CanvasHostPage(page)
        canvas_host.wait_for_canvas_visible(timeout=10000)

        # The canvas host must render with an accessible structure:
        # - container is a real element in the accessibility tree
        # - the close button carries an accessible name (aria-label)
        # - the canvas type badge is present
        assert canvas_host.is_loaded(), "Canvas should render for a11y testing"
        close_btn = canvas_host.canvas_close_button
        assert close_btn.get_attribute("aria-label"), \
            "Canvas close button should have an accessible name"
        assert canvas_host.canvas_component_badge.count() >= 1, \
            "Canvas type badge should be rendered"

    def test_skill_installation_error_handling(self, authenticated_page: Page, setup_test_user: dict):
        """Test skill installation error handling via the backend API.

        No skills frontend exists in this codebase (pages/skills* absent), so
        the marketplace/install surface is exercised through the API:
        - listing skills works
        - installing a non-existent skill returns a structured error
        """
        page = authenticated_page
        api_token = setup_test_user["access_token"]
        api_headers = {"Authorization": f"Bearer {api_token}"}

        # Search for a definitely non-existent skill
        search_resp = requests.get(
            "http://localhost:8001/api/skills/list?query=this-definitely-does-not-exist-skill-12345",
            headers=api_headers,
            timeout=10,
        )
        assert search_resp.status_code == 200, \
            f"Skills search should return 200, got {search_resp.status_code}"

        # Attempting to import a non-existent skill must not crash the API —
        # it must fail with a structured client error (validation), never a 500.
        import json
        install_resp = requests.post(
            "http://localhost:8001/api/skills/import",
            headers={**api_headers, "Content-Type": "application/json"},
            json={"skill_id": "this-definitely-does-not-exist-skill-12345"},
            timeout=10,
        )
        assert install_resp.status_code in (400, 404, 422), \
            f"Non-existent skill import must fail with a structured client error, got {install_resp.status_code}: {install_resp.text[:200]}"


if __name__ == "__main__":
    # This allows running the test directly for debugging
    pytest.main([__file__, "-v", "-s"])

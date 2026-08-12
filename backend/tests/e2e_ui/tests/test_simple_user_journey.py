"""
Simplified E2E User Journey Test that focuses on core functionality without excessive complexity.
This test validates the essential user path covering key features.
"""

import pytest
import uuid
from playwright.sync_api import Page, expect
from tests.e2e_ui.pages.page_objects import (
    LoginPage, DashboardPage, SettingsPage, ChatPage, 
    CanvasHostPage, SkillsMarketplacePage
)


@pytest.mark.e2e
class TestSimplifiedUserJourney:
    """Simplified E2E test class for core user journey."""

    def test_basic_user_journey(self, authenticated_page: Page):
        """Test basic user journey: login, dashboard, settings, canvas, logout."""
        page = authenticated_page
        
        # 1. Dashboard exploration
        page.goto("http://localhost:3001/dashboard")
        dashboard = DashboardPage(page)
        expect(dashboard.is_loaded()).to_be_truthy()
        welcome_text = dashboard.get_welcome_text()
        assert "Welcome" in welcome_text
        
        # Check agent count
        agent_count = dashboard.get_agent_count()
        assert agent_count >= 0
        
        # 2. Settings persistence
        page.goto("http://localhost:3001/settings")
        settings = SettingsPage(page)
        expect(settings.is_loaded()).to_be_truthy()
        
        # Get initial theme and toggle it
        initial_theme = settings.get_current_theme()
        settings.toggle_theme()
        settings.click_save()
        page.wait_for_timeout(500)
        
        # Verify theme changed
        new_theme = settings.get_current_theme()
        assert new_theme != initial_theme
        
        # Reload and verify persistence
        page.reload()
        expect(settings.is_loaded()).to_be_truthy()
        assert settings.get_current_theme() == new_theme
        
        # 3. Canvas access
        page.goto("http://localhost:3001/canvas")
        canvas_host = CanvasHostPage(page)
        expect(canvas_host.is_loaded()).to_be_truthy()
        canvas_host.create_new_canvas("Test Canvas", "chart")
        page.wait_for_timeout(1000)
        
        # 4. Logout
        page.goto("http://localhost:3001/dashboard")
        dashboard.logout()
        expect(page).to_have_url("*/login", timeout=5000)
        
        print("✅ Simplified user journey test passed!")


# Additional simple tests for specific features

@pytest.mark.e2e
class TestChatFunctionality:
    """Test chat functionality."""

    def test_send_message(self, authenticated_page: Page):
        """Test sending a chat message."""
        page = authenticated_page
        chat_page = ChatPage(page)
        
        page.goto("http://localhost:3001/chat")
        expect(chat_page.is_loaded()).to_be_truthy()
        
        test_message = f"Hello from simplified test {uuid.uuid4().hex[:8]}"
        chat_page.send_message(test_message)
        page.wait_for_timeout(1000)
        
        # Verify message appears
        last_message = chat_page.get_last_message()
        assert test_message in last_message
        
        print("✅ Chat functionality test passed!")


@pytest.mark.e2e
class TestCanvasFeatures:
    """Test canvas features."""

    def test_canvas_creation(self, authenticated_page: Page):
        """Test creating a canvas via UI."""
        page = authenticated_page
        
        # Navigate to canvas
        page.goto("http://localhost:3001/canvas")
        canvas_host = CanvasHostPage(page)
        expect(canvas_host.is_loaded()).to_be_truthy()
        
        # Create a new canvas
        canvas_host.create_new_canvas("Test Canvas", "chart")
        page.wait_for_timeout(1000)
        
        # Verify canvas created
        canvas_title = canvas_host.get_title()
        assert "Test Canvas" in canvas_title
        
        print("✅ Canvas creation test passed!")


if __name__ == "__main__":
    # This allows running the test directly for debugging
    pytest.main([__file__, "-v", "-s"])
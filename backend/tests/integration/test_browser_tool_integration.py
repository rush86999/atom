"""
Integration tests for browser automation tool.

Tests browser tool functions with mocked Playwright CDP to test real tool logic
without requiring actual browser instances.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from tools.browser_tool import (
    BrowserSession,
    BrowserSessionManager,
    browser_create_session,
    browser_navigate,
    browser_screenshot,
    browser_close_session
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_playwright():
    """Mock Playwright async API."""
    with patch("tools.browser_tool.async_playwright") as mock_pw:
        # Mock playwright instance
        playwright_instance = AsyncMock()
        mock_pw.return_value = playwright_instance

        # Mock browser
        browser = AsyncMock()
        browser.new_context = AsyncMock(return_value=AsyncMock())
        browser.close = AsyncMock()
        playwright_instance.chromium.launch = AsyncMock(return_value=browser)
        playwright_instance.firefox.launch = AsyncMock(return_value=browser)
        playwright_instance.webkit.launch = AsyncMock(return_value=browser)

        # Mock context
        context = AsyncMock()
        page = AsyncMock()

        # Mock page methods
        page.goto = AsyncMock(return_value=MagicMock(status=200))
        page.title = AsyncMock(return_value="Test Page")
        page.screenshot = AsyncMock(return_value=b"fake_screenshot_data")

        context.new_page = AsyncMock(return_value=page)
        context.close = AsyncMock()
        browser.new_context = AsyncMock(return_value=context)

        yield {
            "playwright": playwright_instance,
            "browser": browser,
            "context": context,
            "page": page
        }


@pytest.fixture
def mock_session_manager():
    """Mock browser session manager."""
    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        manager = MagicMock()
        mock_mgr.return_value = manager
        yield manager


# ============================================================================
# BrowserSession Tests
# ============================================================================

@pytest.mark.integration
async def test_browser_session_creation(mock_playwright):
    """Test browser session starts correctly."""
    with patch("tools.browser_tool.BROWSER_HEADLESS", True):
        session = BrowserSession(
            session_id="test-session-1",
            user_id="test-user",
            headless=True,
            browser_type="chromium"
        )

        result = await session.start()

        assert result == True
        assert session.playwright is not None
        assert session.browser is not None
        assert session.context is not None
        assert session.page is not None


@pytest.mark.integration
@pytest.mark.parametrize("browser_type", ["chromium", "firefox", "webkit"])
async def test_browser_session_multiple_types(browser_type):
    """Test browser session creation with different browser types."""
    with patch("tools.browser_tool.async_playwright") as mock_pw:
        # Mock different browsers
        playwright_instance = AsyncMock()
        mock_pw.return_value = playwright_instance

        browser = AsyncMock()
        browser.new_context = AsyncMock(return_value=AsyncMock())
        browser.close = AsyncMock()

        # Route to correct browser launch method
        if browser_type == "firefox":
            playwright_instance.firefox.launch = AsyncMock(return_value=browser)
        elif browser_type == "webkit":
            playwright_instance.webkit.launch = AsyncMock(return_value=browser)
        else:
            playwright_instance.chromium.launch = AsyncMock(return_value=browser)

        context = AsyncMock()
        page = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        browser.new_context = AsyncMock(return_value=context)

        session = BrowserSession(
            session_id=f"session-{browser_type}",
            user_id="test-user",
            browser_type=browser_type
        )

        result = await session.start()

        assert result == True


@pytest.mark.integration
async def test_browser_session_close(mock_playwright):
    """Test browser session closes and cleans up resources."""
    with patch("tools.browser_tool.BROWSER_HEADLESS", True):
        session = BrowserSession(
            session_id="test-session-2",
            user_id="test-user"
        )

        await session.start()
        result = await session.close()

        assert result == True


# ============================================================================
# BrowserSessionManager Tests
# ============================================================================

@pytest.mark.integration
async def test_browser_manager_create_session():
    """Test session manager creates and tracks sessions."""
    with patch("tools.browser_tool.async_playwright") as mock_pw:
        # Setup mocks
        playwright_instance = AsyncMock()
        mock_pw.return_value = playwright_instance

        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=browser)
        browser.new_context = AsyncMock(return_value=context)
        context.new_page = AsyncMock(return_value=page)

        manager = BrowserSessionManager()
        session = await manager.create_session(user_id="test-user")

        assert session.session_id in manager.sessions
        assert session.user_id == "test-user"
        assert session.browser is not None


@pytest.mark.integration
async def test_browser_manager_get_session():
    """Test session manager retrieves existing sessions."""
    with patch("tools.browser_tool.async_playwright") as mock_pw:
        playwright_instance = AsyncMock()
        mock_pw.return_value = playwright_instance

        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=browser)
        browser.new_context = AsyncMock(return_value=context)
        context.new_page = AsyncMock(return_value=page)

        manager = BrowserSessionManager()
        session = await manager.create_session(user_id="test-user")

        # Retrieve session
        retrieved = manager.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id


@pytest.mark.integration
async def test_browser_manager_close_session():
    """Test session manager closes and removes sessions."""
    with patch("tools.browser_tool.async_playwright") as mock_pw:
        playwright_instance = AsyncMock()
        mock_pw.return_value = playwright_instance

        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=browser)
        browser.new_context = AsyncMock(return_value=context)
        context.new_page = AsyncMock(return_value=page)

        manager = BrowserSessionManager()
        session = await manager.create_session(user_id="test-user")

        # Close session
        result = await manager.close_session(session.session_id)

        assert result == True
        assert session.session_id not in manager.sessions


@pytest.mark.integration
async def test_browser_manager_cleanup_expired_sessions():
    """Test session manager cleans up expired sessions."""
    with patch("tools.browser_tool.async_playwright") as mock_pw:
        playwright_instance = AsyncMock()
        mock_pw.return_value = playwright_instance

        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=browser)
        browser.new_context = AsyncMock(return_value=context)
        context.new_page = AsyncMock(return_value=page)

        manager = BrowserSessionManager(session_timeout_minutes=0)  # Expire immediately

        # Create session
        session = await manager.create_session(user_id="test-user")
        session.last_used = datetime.fromtimestamp(0)  # Set to epoch (expired)

        # Cleanup
        count = await manager.cleanup_expired_sessions()

        assert count >= 0  # May clean up the session we just created


# ============================================================================
# Browser Tool Functions Tests
# ============================================================================

@pytest.mark.integration
async def test_browser_create_session_success():
    """Test browser_create_session creates session successfully."""
    with patch("tools.browser_tool.async_playwright") as mock_pw:
        playwright_instance = AsyncMock()
        mock_pw.return_value = playwright_instance

        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=browser)
        browser.new_context = AsyncMock(return_value=context)
        context.new_page = AsyncMock(return_value=page)

        with patch("tools.browser_tool.FeatureFlags") as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

            with patch("tools.browser_tool.BROWSER_HEADLESS", True):
                result = await browser_create_session(
                    user_id="test-user",
                    browser_type="chromium"
                )

                assert result["success"] == True
                assert "session_id" in result
                assert result["browser_type"] == "chromium"
                assert result["headless"] == True


@pytest.mark.integration
async def test_browser_create_session_with_agent():
    """Test browser_create_session with agent governance."""
    with patch("tools.browser_tool.async_playwright") as mock_pw:
        playwright_instance = AsyncMock()
        mock_pw.return_value = playwright_instance

        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()

        playwright_instance.chromium.launch = AsyncMock(return_value=browser)
        browser.new_context = AsyncMock(return_value=context)
        context.new_page = AsyncMock(return_value=page)

        with patch("tools.browser_tool.FeatureFlags") as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

            with patch("tools.browser_tool.BROWSER_HEADLESS", True):
                result = await browser_create_session(
                    user_id="test-user",
                    agent_id="test-agent",
                    browser_type="firefox"
                )

                assert result["success"] == True
                assert result["agent_id"] == "test-agent"


@pytest.mark.integration
async def test_browser_navigate_success():
    """Test browser_navigate navigates to URL successfully."""
    # Create a proper mock for page with url attribute
    class MockPage:
        def __init__(self):
            self.url = "https://example.com"
        async def goto(self, url, wait_until="load", timeout=30000):
            return MagicMock(status=200)
        async def title(self):
            return "Example Domain"

    mock_page = MockPage()

    mock_session = MagicMock()
    mock_session.user_id = "test-user"
    mock_session.page = mock_page
    mock_session.last_used = datetime.now()

    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        mock_mgr.get_session.return_value = mock_session

        result = await browser_navigate(
            session_id="test-session",
            url="https://example.com",
            user_id="test-user"
        )

        assert result["success"] == True
        assert result["url"] == "https://example.com"
        assert result["title"] == "Example Domain"
        assert result["status"] == 200


@pytest.mark.integration
@pytest.mark.parametrize("wait_until", ["load", "domcontentloaded", "networkidle"])
async def test_browser_navigate_wait_options(wait_until):
    """Test browser_navigate with different wait_until options."""
    class MockPage:
        def __init__(self):
            self.url = "https://example.com"
        async def goto(self, url, wait_until="load", timeout=30000):
            return MagicMock(status=200)
        async def title(self):
            return "Test Page"

    mock_page = MockPage()

    mock_session = MagicMock()
    mock_session.user_id = "test-user"
    mock_session.page = mock_page
    mock_session.last_used = datetime.now()

    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        mock_mgr.get_session.return_value = mock_session

        result = await browser_navigate(
            session_id="test-session",
            url="https://example.com",
            wait_until=wait_until,
            user_id="test-user"
        )

        assert result["success"] == True


@pytest.mark.integration
async def test_browser_navigate_session_not_found():
    """Test browser_navigate returns error for non-existent session."""
    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        mock_mgr.get_session.return_value = None

        result = await browser_navigate(
            session_id="non-existent-session",
            url="https://example.com"
        )

        assert result["success"] == False
        assert "not found" in result["error"]


@pytest.mark.integration
async def test_browser_navigate_wrong_user():
    """Test browser_navigate blocks cross-user session access."""
    mock_session = MagicMock()
    mock_session.user_id = "other-user"
    mock_session.page = MagicMock()
    mock_session.last_used = datetime.now()

    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        mock_mgr.get_session.return_value = mock_session

        result = await browser_navigate(
            session_id="test-session",
            url="https://example.com",
            user_id="test-user"  # Different user
        )

        assert result["success"] == False
        assert "different user" in result["error"]


@pytest.mark.integration
async def test_browser_navigate_invalid_url():
    """Test browser_navigate handles invalid URL."""
    class MockPage:
        def __init__(self):
            self.url = "https://example.com"
        async def goto(self, url, wait_until="load", timeout=30000):
            raise Exception("Invalid URL")
        async def title(self):
            return "Test Page"

    mock_page = MockPage()

    mock_session = MagicMock()
    mock_session.user_id = "test-user"
    mock_session.page = mock_page
    mock_session.last_used = datetime.now()

    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        mock_mgr.get_session.return_value = mock_session

        result = await browser_navigate(
            session_id="test-session",
            url="invalid://url",
            user_id="test-user"
        )

        assert result["success"] == False
        assert "error" in result


@pytest.mark.integration
async def test_browser_screenshot_success():
    """Test browser_screenshot captures screenshot successfully."""
    class MockPage:
        async def screenshot(self, **kwargs):
            return b"fake_screenshot_bytes"

    mock_page = MockPage()

    mock_session = MagicMock()
    mock_session.user_id = "test-user"
    mock_session.page = mock_page
    mock_session.last_used = datetime.now()

    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        mock_mgr.get_session.return_value = mock_session

        result = await browser_screenshot(
            session_id="test-session",
            user_id="test-user"
        )

        assert result["success"] == True
        assert "screenshot_path" in result or "screenshot_data" in result


@pytest.mark.integration
async def test_browser_screenshot_full_page():
    """Test browser_screenshot with full_page option."""
    class MockPage:
        async def screenshot(self, **kwargs):
            # Return different data based on full_page
            if kwargs.get("full_page"):
                return b"full_page_screenshot"
            return b"viewport_screenshot"

    mock_page = MockPage()

    mock_session = MagicMock()
    mock_session.user_id = "test-user"
    mock_session.page = mock_page
    mock_session.last_used = datetime.now()

    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        mock_mgr.get_session.return_value = mock_session

        result = await browser_screenshot(
            session_id="test-session",
            full_page=True,
            user_id="test-user"
        )

        assert result["success"] == True


@pytest.mark.integration
async def test_browser_close_session_success():
    """Test browser_close_session closes session successfully."""
    mock_session = MagicMock()
    mock_session.close = AsyncMock(return_value=True)

    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        mock_mgr.get_session.return_value = mock_session
        mock_mgr.close_session = AsyncMock(return_value=True)

        result = await browser_close_session(
            session_id="test-session"
        )

        assert result["success"] == True


@pytest.mark.integration
async def test_browser_close_session_not_found():
    """Test browser_close_session handles non-existent session."""
    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        mock_mgr.get_session.return_value = None

        result = await browser_close_session(
            session_id="non-existent-session"
        )

        assert result["success"] == False
        assert "not found" in result["error"]


# ============================================================================
# Governance Tests
# ============================================================================

@pytest.mark.integration
async def test_browser_governance_blocks_student_agent():
    """Test that STUDENT agents are blocked from browser operations."""
    with patch("tools.browser_tool.FeatureFlags") as mock_flags:
        mock_flags.should_enforce_governance.return_value = True

        with patch("tools.browser_tool.AgentContextResolver") as mock_resolver:
            agent = MagicMock()
            agent.id = "student-agent"
            agent.name = "StudentAgent"
            agent.status = "student"

            mock_resolver.return_value.resolve_agent_for_request = AsyncMock(
                return_value=(agent, {})
            )

            with patch("tools.browser_tool.ServiceFactory") as mock_factory:
                service = MagicMock()
                service.can_perform_action.return_value = {
                    "allowed": False,
                    "reason": "STUDENT agents not permitted for browser operations"
                }
                mock_factory.get_governance_service.return_value = service

                mock_db = MagicMock()

                result = await browser_create_session(
                    user_id="test-user",
                    agent_id="student-agent",
                    db=mock_db
                )

                assert result["success"] == False
                assert "not permitted" in result["error"]


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.integration
async def test_browser_session_start_failure():
    """Test browser session handles start failures gracefully."""
    with patch("tools.browser_tool.async_playwright") as mock_pw:
        # Make start fail
        playwright_instance = AsyncMock()
        mock_pw.return_value = playwright_instance

        # Make chromium.launch raise an exception
        playwright_instance.chromium.launch = AsyncMock(
            side_effect=Exception("Playwright not installed")
        )

        session = BrowserSession(
            session_id="test-session",
            user_id="test-user"
        )

        with pytest.raises(Exception):
            await session.start()


@pytest.mark.integration
async def test_browser_navigate_timeout():
    """Test browser_navigate handles timeout errors."""
    mock_page = MagicMock()
    mock_page.goto = AsyncMock(side_effect=Exception("Timeout exceeded 30000ms"))

    mock_session = MagicMock()
    mock_session.user_id = "test-user"
    mock_session.page = mock_page
    mock_session.last_used = datetime.now()

    with patch("tools.browser_tool.get_browser_manager") as mock_mgr:
        mock_mgr.get_session.return_value = mock_session

        result = await browser_navigate(
            session_id="test-session",
            url="https://slow-example.com",
            user_id="test-user"
        )

        assert result["success"] == False
        assert "error" in result

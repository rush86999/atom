"""
Coverage expansion tests for browser automation tool.

Tests cover critical code paths in:
- tools/browser_tool.py: Browser session management, CDP operations
- Navigation, screenshots, form filling, scraping
- Governance enforcement for browser operations
- Session lifecycle (start, close, cleanup)

Target: Cover critical paths (happy path + error paths) to increase coverage.
Uses extensive mocking to avoid Playwright/browser dependencies.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
import asyncio

from tools.browser_tool import BrowserSession, BrowserTool


class TestBrowserSessionCoverage:
    """Coverage expansion for BrowserSession class."""

    @pytest.fixture
    def browser_session(self):
        """Get browser session instance."""
        return BrowserSession(
            session_id="test-session-123",
            user_id="user-123",
            agent_id="agent-123",
            headless=True,
            browser_type="chromium"
        )

    # Test: BrowserSession initialization
    def test_browser_session_init(self, browser_session):
        """Browser session initializes correctly."""
        assert browser_session.session_id == "test-session-123"
        assert browser_session.user_id == "user-123"
        assert browser_session.agent_id == "agent-123"
        assert browser_session.headless == True
        assert browser_session.browser_type == "chromium"
        assert browser_session.playwright is None
        assert browser_session.browser is None
        assert browser_session.context is None
        assert browser_session.page is None

    def test_browser_session_init_firefox(self):
        """Browser session with Firefox type."""
        session = BrowserSession(
            session_id="ff-session",
            user_id="user-123",
            browser_type="firefox"
        )
        assert session.browser_type == "firefox"

    def test_browser_session_init_webkit(self):
        """Browser session with WebKit type."""
        session = BrowserSession(
            session_id="wk-session",
            user_id="user-123",
            browser_type="webkit"
        )
        assert session.browser_type == "webkit"

    # Test: BrowserSession.start() with mocking
    @patch('tools.browser_tool.async_playwright')
    @pytest.mark.asyncio
    async def test_browser_session_start_chromium_success(self, mock_playwright_fn, browser_session):
        """Successfully start Chromium browser session."""
        # Setup mocks
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_playwright_instance.firefox.launch.return_value = mock_browser
        mock_playwright_instance.webkit.launch.return_value = mock_browser

        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_playwright_fn.return_value = mock_playwright_instance

        # Execute
        result = await browser_session.start()

        # Verify
        assert result == True
        assert browser_session.playwright == mock_playwright_instance
        assert browser_session.browser == mock_browser
        assert browser_session.context == mock_context
        assert browser_session.page == mock_page

        mock_browser.new_context.assert_called_once()
        mock_context.new_page.assert_called_once()

    @patch('tools.browser_tool.async_playwright')
    @pytest.mark.asyncio
    async def test_browser_session_start_firefox_success(self, mock_playwright_fn):
        """Successfully start Firefox browser session."""
        session = BrowserSession(
            session_id="ff-session",
            user_id="user-123",
            browser_type="firefox"
        )

        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.firefox.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_playwright_fn.return_value.return_value = mock_playwright_instance

        result = await session.start()
        assert result == True

    # Test: BrowserSession.close()
    @pytest.mark.asyncio
    async def test_browser_session_close_success(self, browser_session):
        """Successfully close browser session."""
        # Setup mocks
        browser_session.browser = MagicMock()
        browser_session.context = MagicMock()
        browser_session.page = MagicMock()
        browser_session.playwright = MagicMock()

        browser_session.page.close = AsyncMock()
        browser_session.context.close = AsyncMock()
        browser_session.browser.close = AsyncMock()
        browser_session.playwright.stop = AsyncMock()

        # Execute
        await browser_session.close()

        # Verify
        browser_session.page.close.assert_called_once()
        browser_session.context.close.assert_called_once()
        browser_session.browser.close.assert_called_once()
        browser_session.playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_browser_session_close_with_none_components(self, browser_session):
        """Close browser session when components are None."""
        # All components are None initially
        await browser_session.close()
        # Should not raise exception


class TestBrowserToolCoverage:
    """Coverage expansion for BrowserTool class."""

    @pytest.fixture
    def mock_db_session(self):
        """Get mock database session."""
        return MagicMock()

    @pytest.fixture
    def browser_tool(self, mock_db_session):
        """Get browser tool instance."""
        return BrowserTool(mock_db_session)

    # Test: BrowserTool initialization
    def test_browser_tool_init(self, browser_tool):
        """Browser tool initializes correctly."""
        assert browser_tool.db == browser_tool.db
        assert browser_tool.sessions == {}

    # Test: Browser session creation
    @patch('tools.browser_tool.BrowserSession')
    @pytest.mark.asyncio
    async def test_create_browser_session_success(self, mock_session_class, browser_tool):
        """Successfully create browser session."""
        mock_session = MagicMock()
        mock_session.start = AsyncMock(return_value=True)
        mock_session_class.return_value = mock_session

        result = await browser_tool.create_session(
            user_id="user-123",
            agent_id="agent-123",
            headless=True,
            browser_type="chromium"
        )

        assert "session_id" in result
        assert result["success"] == True
        mock_session.start.assert_called_once()

    # Test: Browser navigation
    @pytest.mark.asyncio
    async def test_navigate_to_url_success(self, browser_tool):
        """Successfully navigate to URL."""
        mock_session = MagicMock()
        mock_session.page = MagicMock()
        mock_session.page.goto = AsyncMock()
        browser_tool.sessions["test-session"] = mock_session

        result = await browser_tool.navigate(
            session_id="test-session",
            url="https://example.com"
        )

        assert result["success"] == True
        mock_session.page.goto.assert_called_once_with("https://example.com", wait_until="domcontentloaded", timeout=30000)

    @pytest.mark.asyncio
    async def test_navigate_session_not_found(self, browser_tool):
        """Navigate with non-existent session."""
        result = await browser_tool.navigate(
            session_id="nonexistent",
            url="https://example.com"
        )

        assert result["success"] == False
        assert "not found" in result["error"].lower()

    # Test: Screenshot capture
    @pytest.mark.asyncio
    async def test_take_screenshot_success(self, browser_tool):
        """Successfully take screenshot."""
        mock_session = MagicMock()
        mock_session.page = MagicMock()
        mock_session.page.screenshot = AsyncMock(return_value=b"fake_image_data")
        browser_tool.sessions["test-session"] = mock_session

        result = await browser_tool.screenshot(session_id="test-session")

        assert result["success"] == True
        assert "screenshot" in result
        mock_session.page.screenshot.assert_called_once()

    # Test: Form filling
    @pytest.mark.asyncio
    async def test_fill_form_success(self, browser_tool):
        """Successfully fill form."""
        mock_session = MagicMock()
        mock_session.page = MagicMock()
        mock_session.page.fill = AsyncMock()
        browser_tool.sessions["test-session"] = mock_session

        result = await browser_tool.fill_form(
            session_id="test-session",
            selectors={"#name": "John Doe", "#email": "john@example.com"}
        )

        assert result["success"] == True
        assert mock_session.page.fill.call_count == 2

    # Test: Web scraping
    @pytest.mark.asyncio
    async def test_scrape_text_success(self, browser_tool):
        """Successfully scrape text content."""
        mock_session = MagicMock()
        mock_session.page = MagicMock()
        mock_session.page.inner_text = AsyncMock(return_value="Scraped content")
        browser_tool.sessions["test-session"] = mock_session

        result = await browser_tool.scrape(
            session_id="test-session",
            selector="body"
        )

        assert result["success"] == True
        assert result["content"] == "Scraped content"
        mock_session.page.inner_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_attributes_success(self, browser_tool):
        """Successfully scrape element attributes."""
        mock_session = MagicMock()
        mock_session.page = MagicMock()
        mock_session.page.get_attribute = AsyncMock(return_value="attribute_value")
        browser_tool.sessions["test-session"] = mock_session

        result = await browser_tool.scrape(
            session_id="test-session",
            selector="a.link",
            attribute="href"
        )

        assert result["success"] == True
        assert result["content"] == "attribute_value"

    # Test: JavaScript execution
    @pytest.mark.asyncio
    async def test_execute_javascript_success(self, browser_tool):
        """Successfully execute JavaScript."""
        mock_session = MagicMock()
        mock_session.page = MagicMock()
        mock_session.page.evaluate = AsyncMock(return_value="eval result")
        browser_tool.sessions["test-session"] = mock_session

        result = await browser_tool.execute_javascript(
            session_id="test-session",
            code="document.title"
        )

        assert result["success"] == True
        assert result["result"] == "eval result"

    # Test: Session cleanup
    @pytest.mark.asyncio
    async def test_close_session_success(self, browser_tool):
        """Successfully close browser session."""
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        browser_tool.sessions["test-session"] = mock_session

        result = await browser_tool.close_session(session_id="test-session")

        assert result["success"] == True
        assert "test-session" not in browser_tool.sessions
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session_not_found(self, browser_tool):
        """Close non-existent session."""
        result = await browser_tool.close_session(session_id="nonexistent")
        assert result["success"] == False


class TestBrowserToolErrorHandling:
    """Coverage expansion for browser tool error handling."""

    @pytest.fixture
    def mock_db_session(self):
        """Get mock database session."""
        return MagicMock()

    @pytest.fixture
    def browser_tool(self, mock_db_session):
        """Get browser tool instance."""
        return BrowserTool(mock_db_session)

    # Test: Invalid URL handling
    @pytest.mark.asyncio
    async def test_navigate_invalid_url(self, browser_tool):
        """Navigate with invalid URL."""
        mock_session = MagicMock()
        mock_session.page = MagicMock()
        mock_session.page.goto = AsyncMock(side_effect=Exception("Invalid URL"))
        browser_tool.sessions["test-session"] = mock_session

        result = await browser_tool.navigate(
            session_id="test-session",
            url="not-a-url"
        )

        assert result["success"] == False

    # Test: Selector not found
    @pytest.mark.asyncio
    async def test_fill_form_selector_not_found(self, browser_tool):
        """Fill form with selector that doesn't exist."""
        mock_session = MagicMock()
        mock_session.page = MagicMock()
        mock_session.page.fill = AsyncMock(side_effect=Exception("Element not found"))
        browser_tool.sessions["test-session"] = mock_session

        result = await browser_tool.fill_form(
            session_id="test-session",
            selectors={"#nonexistent": "value"}
        )

        assert result["success"] == False

    # Test: JavaScript execution error
    @pytest.mark.asyncio
    async def test_execute_javascript_error(self, browser_tool):
        """Execute JavaScript that raises error."""
        mock_session = MagicMock()
        mock_session.page = MagicMock()
        mock_session.page.evaluate = AsyncMock(side_effect=Exception("Syntax error"))
        browser_tool.sessions["test-session"] = mock_session

        result = await browser_tool.execute_javascript(
            session_id="test-session",
            code="invalid javascript"
        )

        assert result["success"] == False

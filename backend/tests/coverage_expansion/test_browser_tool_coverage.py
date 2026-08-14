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

from tools.browser_tool import BrowserSession, BrowserSessionManager


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
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright_instance = MagicMock()
        # async_playwright().start() and the launch/new_context/new_page calls
        # are all awaited — they must be AsyncMocks.
        mock_playwright_instance.start = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright_instance.firefox.launch = AsyncMock(return_value=mock_browser)
        mock_playwright_instance.webkit.launch = AsyncMock(return_value=mock_browser)

        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

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

        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.start = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright_instance.firefox.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_playwright_fn.return_value = mock_playwright_instance

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


class TestBrowserFunctionsCoverage:
    """Coverage for the module-level browser_* service functions.

    Ported from the removed BrowserTool class to the current function API
    (browser_navigate / browser_screenshot / browser_fill_form /
    browser_extract_text / browser_execute_script / browser_close_session).
    """

    @pytest.fixture
    def browser_fns(self):
        """Provide the module functions plus the shared session manager."""
        import tools.browser_tool as bt
        bt.get_browser_manager().sessions.clear()
        old_flag = bt.BROWSER_LOCATOR_API_ENABLED
        bt.BROWSER_LOCATOR_API_ENABLED = False
        yield bt
        bt.BROWSER_LOCATOR_API_ENABLED = old_flag
        bt.get_browser_manager().sessions.clear()

    def _add_session(self, bt, session_id="test-session"):
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        bt.get_browser_manager().sessions[session_id] = mock_session
        return mock_session

    @pytest.mark.asyncio
    async def test_navigate_to_url_success(self, browser_fns):
        bt = browser_fns
        mock_session = self._add_session(bt)
        mock_session.page.goto = AsyncMock()
        mock_session.page.title = AsyncMock(return_value="Example")
        mock_session.page.url = "https://example.com"

        result = await bt.browser_navigate(session_id="test-session", url="https://example.com")

        assert result["success"] is True
        mock_session.page.goto.assert_called_once_with(
            "https://example.com", wait_until="load", timeout=30000)

    @pytest.mark.asyncio
    async def test_navigate_session_not_found(self, browser_fns):
        result = await browser_fns.browser_navigate(session_id="nonexistent", url="https://example.com")
        assert result["success"] is False
        assert "not found" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_take_screenshot_success(self, browser_fns):
        bt = browser_fns
        mock_session = self._add_session(bt)
        mock_session.page.screenshot = AsyncMock(return_value=b"fake_image_data")

        result = await bt.browser_screenshot(session_id="test-session")

        assert result["success"] is True
        mock_session.page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_fill_form_success(self, browser_fns):
        bt = browser_fns
        mock_session = self._add_session(bt)
        mock_session.page.fill = AsyncMock()

        element = MagicMock()
        element.evaluate = AsyncMock(return_value="INPUT")
        mock_session.page.wait_for_selector = AsyncMock()
        mock_session.page.query_selector = AsyncMock(return_value=element)

        result = await bt.browser_fill_form(
            session_id="test-session",
            selectors={"#name": "John Doe", "#email": "john@example.com"})

        assert result["success"] is True
        assert mock_session.page.fill.call_count == 2

    @pytest.mark.asyncio
    async def test_scrape_text_success(self, browser_fns):
        bt = browser_fns
        mock_session = self._add_session(bt)
        element = MagicMock()
        element.inner_text = AsyncMock(return_value="Scraped content")
        mock_session.page.query_selector_all = AsyncMock(return_value=[element])

        result = await bt.browser_extract_text(session_id="test-session", selector="body")

        assert result["success"] is True
        assert result.get("content", result.get("text")) == "Scraped content"
        element.inner_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_javascript_success(self, browser_fns):
        bt = browser_fns
        mock_session = self._add_session(bt)
        mock_session.page.evaluate = AsyncMock(return_value="eval result")

        result = await bt.browser_execute_script(session_id="test-session", script="document.title")

        assert result["success"] is True
        assert result.get("result") == "eval result"

    @pytest.mark.asyncio
    async def test_close_session_success(self, browser_fns):
        bt = browser_fns
        mock_session = self._add_session(bt)

        result = await bt.browser_close_session(session_id="test-session")

        assert result["success"] is True
        assert "test-session" not in bt.get_browser_manager().sessions
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session_not_found(self, browser_fns):
        result = await browser_fns.browser_close_session(session_id="nonexistent")
        assert result["success"] is False


class TestBrowserFunctionsErrorHandling:
    """Error-path coverage for the module-level browser_* functions."""

    @pytest.fixture
    def browser_fns(self):
        import tools.browser_tool as bt
        bt.get_browser_manager().sessions.clear()
        old_flag = bt.BROWSER_LOCATOR_API_ENABLED
        bt.BROWSER_LOCATOR_API_ENABLED = False
        yield bt
        bt.BROWSER_LOCATOR_API_ENABLED = old_flag
        bt.get_browser_manager().sessions.clear()

    def _add_session(self, bt, session_id="test-session"):
        mock_session = MagicMock()
        bt.get_browser_manager().sessions[session_id] = mock_session
        return mock_session

    @pytest.mark.asyncio
    async def test_navigate_invalid_url(self, browser_fns):
        bt = browser_fns
        mock_session = self._add_session(bt)
        mock_session.page.goto = AsyncMock(side_effect=Exception("Invalid URL"))

        result = await bt.browser_navigate(session_id="test-session", url="not-a-url")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_fill_form_selector_not_found(self, browser_fns):
        bt = browser_fns
        mock_session = self._add_session(bt)
        mock_session.page.wait_for_selector = AsyncMock(side_effect=Exception("Element not found"))

        result = await bt.browser_fill_form(
            session_id="test-session", selectors={"#nonexistent": "value"})

        # Per-field failures are tolerated: the form result stays successful
        # but no fields are filled (documented fill_form behavior).
        assert result["success"] is True
        assert result["fields_filled"] == 0

    @pytest.mark.asyncio
    async def test_execute_javascript_error(self, browser_fns):
        bt = browser_fns
        mock_session = self._add_session(bt)
        mock_session.page.evaluate = AsyncMock(side_effect=Exception("Syntax error"))

        result = await bt.browser_execute_script(session_id="test-session", script="invalid javascript")

        assert result["success"] is False

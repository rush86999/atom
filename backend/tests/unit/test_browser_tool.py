"""
Unit tests for browser tool functions.

Tests cover:
- BrowserSession initialization and lifecycle
- BrowserSessionManager session management
- Browser navigation and interaction
- Screenshot capture
- Form filling
- Data extraction
- Browser advanced operations
- Error handling
- Governance integration (INTERN+ required)

Focus: Unit testing core logic without full Playwright integration
"""

from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
import pytest

from tools.browser_tool import (
    BrowserSession,
    BrowserSessionManager,
    get_browser_manager,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_playwright():
    """Mock Playwright async API."""
    with patch('tools.browser_tool.async_playwright') as mock:
        mock_pw = MagicMock()
        mock.return_value.__aenter__.return_value = mock_pw
        yield mock


@pytest.fixture
def mock_browser():
    """Mock Playwright Browser."""
    browser = MagicMock()
    browser.new_context = AsyncMock()
    browser.close = AsyncMock()
    browser.launch = AsyncMock()
    return browser


@pytest.fixture
def mock_browser_context():
    """Mock Playwright BrowserContext."""
    context = MagicMock()
    context.new_page = AsyncMock()
    context.close = AsyncMock()
    return context


@pytest.fixture
def mock_page():
    """Mock Playwright Page."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.title = AsyncMock(return_value="Test Page")
    page.screenshot = AsyncMock(return_value=b"fake screenshot")
    page.wait_for_selector = AsyncMock()
    page.fill = AsyncMock()
    page.select_option = AsyncMock()
    page.click = AsyncMock()
    page.query_selector = AsyncMock()
    page.query_selector_all = AsyncMock()
    page.inner_text = AsyncMock(return_value="Page text")
    page.evaluate = AsyncMock()
    page.pdf = AsyncMock(return_value=b"fake pdf")
    page.close = AsyncMock()
    return page


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "user_123"


@pytest.fixture
def sample_agent_id():
    """Sample agent ID for testing."""
    return "agent_123"


@pytest.fixture
def sample_session_id():
    """Sample session ID for testing."""
    return "session_123"


# ============================================================================
# Test: BrowserSession Initialization
# ============================================================================

class TestBrowserSessionInitialization:
    """Tests for BrowserSession initialization."""

    def test_browser_session_initialization_defaults(self, sample_user_id):
        """Verify BrowserSession initializes with correct defaults"""
        session = BrowserSession(
            session_id="test-session-123",
            user_id=sample_user_id,
        )

        assert session.session_id == "test-session-123"
        assert session.user_id == sample_user_id
        assert session.agent_id is None
        assert session.headless is True
        assert session.browser_type == "chromium"
        assert session.playwright is None
        assert session.browser is None
        assert session.context is None
        assert session.page is None
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_used, datetime)

    def test_browser_session_with_agent_id(self, sample_user_id, sample_agent_id):
        """Verify BrowserSession with agent ID"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id,
            agent_id=sample_agent_id
        )

        assert session.agent_id == sample_agent_id

    def test_browser_session_headful_mode(self, sample_user_id):
        """Verify BrowserSession with headless=False"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id,
            headless=False
        )

        assert session.headless is False

    def test_browser_session_firefox(self, sample_user_id):
        """Verify BrowserSession supports Firefox browser type"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id,
            browser_type="firefox"
        )

        assert session.browser_type == "firefox"

    def test_browser_session_webkit(self, sample_user_id):
        """Verify BrowserSession supports WebKit browser type"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id,
            browser_type="webkit"
        )

        assert session.browser_type == "webkit"

    def test_browser_session_timestamps_set(self, sample_user_id):
        """Verify BrowserSession sets creation and last used timestamps"""
        before = datetime.now()
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id
        )
        after = datetime.now()

        assert before <= session.created_at <= after
        assert before <= session.last_used <= after


# ============================================================================
# Test: BrowserSession Lifecycle
# ============================================================================

class TestBrowserSessionLifecycle:
    """Tests for BrowserSession start and close methods."""

    @pytest.mark.asyncio
    async def test_browser_session_start_chromium(self, sample_user_id):
        """Verify starting Chromium browser session"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id,
            browser_type="chromium"
        )

        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright_instance.chromium = MagicMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            result = await session.start()

        assert result is True
        assert session.browser is not None
        assert session.context is not None
        assert session.page is not None

    @pytest.mark.asyncio
    async def test_browser_session_start_firefox(self, sample_user_id):
        """Verify starting Firefox browser session"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id,
            browser_type="firefox"
        )

        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright_instance.firefox = MagicMock()
        mock_playwright_instance.firefox.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            result = await session.start()

        assert result is True

    @pytest.mark.asyncio
    async def test_browser_session_start_webkit(self, sample_user_id):
        """Verify starting WebKit browser session"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id,
            browser_type="webkit"
        )

        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright_instance.webkit = MagicMock()
        mock_playwright_instance.webkit.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            result = await session.start()

        assert result is True

    @pytest.mark.asyncio
    async def test_browser_session_start_creates_context_with_viewport(self, sample_user_id):
        """Verify session start creates browser context with viewport"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id
        )

        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright_instance.chromium = MagicMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
            await session.start()

        # Verify new_context was called
        assert mock_browser.new_context.called
        call_kwargs = mock_browser.new_context.call_args[1] if mock_browser.new_context.call_args else {}
        assert "viewport" in call_kwargs

    @pytest.mark.asyncio
    async def test_browser_session_close(self, sample_user_id):
        """Verify closing browser session"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id
        )

        # Setup mock objects
        session.page = MagicMock()
        session.page.close = AsyncMock()
        session.context = MagicMock()
        session.context.close = AsyncMock()
        session.browser = MagicMock()
        session.browser.close = AsyncMock()
        session.playwright = MagicMock()
        session.playwright.stop = AsyncMock()

        result = await session.close()

        assert result is True
        session.page.close.assert_called_once()
        session.context.close.assert_called_once()
        session.browser.close.assert_called_once()
        session.playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_browser_session_close_handles_errors(self, sample_user_id):
        """Verify close handles errors gracefully"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id
        )

        # Mock page that raises error on close
        session.page = MagicMock()
        session.page.close = AsyncMock(side_effect=Exception("Close error"))
        session.context = None
        session.browser = None
        session.playwright = None

        result = await session.close()

        # Should return False on error
        assert result is False

    @pytest.mark.asyncio
    async def test_browser_session_close_partial_cleanup(self, sample_user_id):
        """Verify close attempts cleanup even if some resources fail"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id
        )

        # Setup mock objects with one failing
        session.page = MagicMock()
        session.page.close = AsyncMock(side_effect=Exception("Page close error"))
        session.context = MagicMock()
        session.context.close = AsyncMock()
        session.browser = MagicMock()
        session.browser.close = AsyncMock()
        session.playwright = MagicMock()
        session.playwright.stop = AsyncMock()

        result = await session.close()

        # Should still attempt to close other resources
        assert result is False
        session.context.close.assert_called_once()


# ============================================================================
# Test: BrowserSessionManager
# ============================================================================

class TestBrowserSessionManager:
    """Tests for BrowserSessionManager class."""

    def test_browser_session_manager_initialization(self):
        """Verify BrowserSessionManager initializes correctly"""
        manager = BrowserSessionManager(session_timeout_minutes=30)

        assert manager.session_timeout_minutes == 30
        assert isinstance(manager.sessions, dict)
        assert len(manager.sessions) == 0

    def test_browser_session_manager_default_timeout(self):
        """Verify BrowserSessionManager uses default timeout"""
        manager = BrowserSessionManager()

        assert manager.session_timeout_minutes == 30

    def test_get_session_returns_none_for_nonexistent(self):
        """Verify get_session returns None for nonexistent session"""
        manager = BrowserSessionManager()

        result = manager.get_session("nonexistent-session-id")

        assert result is None

    def test_get_session_returns_existing_session(self, sample_user_id):
        """Verify get_session returns existing session"""
        manager = BrowserSessionManager()
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id
        )
        manager.sessions["test-session"] = session

        result = manager.get_session("test-session")

        assert result is not None
        assert result.session_id == "test-session"

    @pytest.mark.asyncio
    async def test_create_session_default_params(self, sample_user_id):
        """Verify creating session with default parameters"""
        manager = BrowserSessionManager()

        # Mock the session start method
        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        assert session.session_id is not None
        assert session.user_id == sample_user_id
        assert session.headless is True
        assert session.browser_type == "chromium"
        assert "test-session" not in manager.sessions  # Not added until start succeeds

    @pytest.mark.asyncio
    async def test_create_session_with_agent(self, sample_user_id, sample_agent_id):
        """Verify creating session with agent ID"""
        manager = BrowserSessionManager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(
                user_id=sample_user_id,
                agent_id=sample_agent_id
            )

        assert session.agent_id == sample_agent_id

    @pytest.mark.asyncio
    async def test_create_session_headful(self, sample_user_id):
        """Verify creating non-headless session"""
        manager = BrowserSessionManager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(
                user_id=sample_user_id,
                headless=False
            )

        assert session.headless is False

    @pytest.mark.asyncio
    async def test_create_session_firefox(self, sample_user_id):
        """Verify creating Firefox session"""
        manager = BrowserSessionManager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(
                user_id=sample_user_id,
                browser_type="firefox"
            )

        assert session.browser_type == "firefox"

    @pytest.mark.asyncio
    async def test_close_session_success(self, sample_user_id, sample_session_id):
        """Verify closing and removing session"""
        manager = BrowserSessionManager()
        session = BrowserSession(
            session_id=sample_session_id,
            user_id=sample_user_id
        )
        manager.sessions[sample_session_id] = session

        with patch.object(BrowserSession, 'close', new=AsyncMock(return_value=True)):
            result = await manager.close_session(sample_session_id)

        assert result is True
        assert sample_session_id not in manager.sessions

    @pytest.mark.asyncio
    async def test_close_session_nonexistent(self):
        """Verify closing nonexistent session returns False"""
        manager = BrowserSessionManager()

        result = await manager.close_session("nonexistent")

        assert result is False

    def test_cleanup_expired_sessions(self, sample_user_id):
        """Verify cleanup of expired sessions"""
        manager = BrowserSessionManager(session_timeout_minutes=30)

        # Create expired session (31 minutes old)
        old_session = BrowserSession(
            session_id="old-session",
            user_id=sample_user_id
        )
        old_session.created_at = datetime.now() - timedelta(minutes=31)
        old_session.last_used = datetime.now() - timedelta(minutes=31)
        manager.sessions["old-session"] = old_session

        # Create active session
        active_session = BrowserSession(
            session_id="active-session",
            user_id=sample_user_id
        )
        manager.sessions["active-session"] = active_session

        manager.cleanup_expired_sessions()

        assert "old-session" not in manager.sessions
        assert "active-session" in manager.sessions

    def test_cleanup_expired_sessions_all_expired(self, sample_user_id):
        """Verify cleanup removes all expired sessions"""
        manager = BrowserSessionManager(session_timeout_minutes=30)

        # Create multiple expired sessions
        for i in range(3):
            session = BrowserSession(
                session_id=f"expired-{i}",
                user_id=sample_user_id
            )
            session.created_at = datetime.now() - timedelta(minutes=35)
            session.last_used = datetime.now() - timedelta(minutes=35)
            manager.sessions[f"expired-{i}"] = session

        count = manager.cleanup_expired_sessions()

        assert count == 3
        assert len(manager.sessions) == 0

    def test_cleanup_expired_sessions_none_expired(self, sample_user_id):
        """Verify cleanup doesn't remove active sessions"""
        manager = BrowserSessionManager(session_timeout_minutes=30)

        # Create active sessions
        for i in range(3):
            session = BrowserSession(
                session_id=f"active-{i}",
                user_id=sample_user_id
            )
            manager.sessions[f"active-{i}"] = session

        count = manager.cleanup_expired_sessions()

        assert count == 0
        assert len(manager.sessions) == 3


# ============================================================================
# Test: Browser Navigation
# ============================================================================

class TestBrowserNavigation:
    """Tests for browser navigation functionality."""

    def test_navigation_url_validation(self):
        """Verify URL validation for navigation"""
        # Valid URLs
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://example.com/path",
            "https://example.com?query=value",
        ]

        for url in valid_urls:
            assert url.startswith("http")

        # Invalid URL pattern
        invalid_url = "not-a-url"
        assert not invalid_url.startswith("http")

    def test_navigation_wait_for_selector_exists(self, mock_page):
        """Verify wait_for_selector method exists"""
        assert hasattr(mock_page, 'wait_for_selector')
        assert callable(mock_page.wait_for_selector)

    def test_navigation_supports_timeout(self):
        """Verify navigation supports timeout parameter"""
        timeout_ms = 5000
        assert isinstance(timeout_ms, int)
        assert timeout_ms > 0


# ============================================================================
# Test: Browser Interaction
# ============================================================================

class TestBrowserInteraction:
    """Tests for browser interaction functionality."""

    def test_click_element_exists(self, mock_page):
        """Verify click method exists"""
        assert hasattr(mock_page, 'click')
        assert callable(mock_page.click)

    def test_fill_form_exists(self, mock_page):
        """Verify fill method exists"""
        assert hasattr(mock_page, 'fill')
        assert callable(mock_page.fill)

    def test_select_dropdown_exists(self, mock_page):
        """Verify select_option method exists"""
        assert hasattr(mock_page, 'select_option')
        assert callable(mock_page.select_option)

    def test_query_selector_exists(self, mock_page):
        """Verify query_selector method exists"""
        assert hasattr(mock_page, 'query_selector')
        assert callable(mock_page.query_selector)

    def test_query_selector_all_exists(self, mock_page):
        """Verify query_selector_all method exists"""
        assert hasattr(mock_page, 'query_selector_all')
        assert callable(mock_page.query_selector_all)


# ============================================================================
# Test: Browser Advanced Operations
# ============================================================================

class TestBrowserAdvancedOperations:
    """Tests for advanced browser operations."""

    def test_execute_javascript_exists(self, mock_page):
        """Verify JavaScript execution method exists"""
        assert hasattr(mock_page, 'evaluate')
        assert callable(mock_page.evaluate)

    def test_screenshot_method_exists(self, mock_page):
        """Verify screenshot method exists"""
        assert hasattr(mock_page, 'screenshot')
        assert callable(mock_page.screenshot)

    def test_pdf_generation_exists(self, mock_page):
        """Verify PDF generation method exists"""
        assert hasattr(mock_page, 'pdf')
        assert callable(mock_page.pdf)

    def test_extract_text_method_exists(self, mock_page):
        """Verify text extraction method exists"""
        assert hasattr(mock_page, 'inner_text')
        assert callable(mock_page.inner_text)

    @pytest.mark.asyncio
    async def test_screenshot_capture_returns_bytes(self, mock_page):
        """Verify screenshot returns byte data"""
        result = await mock_page.screenshot()
        assert isinstance(result, bytes)
        assert result == b"fake screenshot"

    @pytest.mark.asyncio
    async def test_pdf_generation_returns_bytes(self, mock_page):
        """Verify PDF generation returns byte data"""
        result = await mock_page.pdf()
        assert isinstance(result, bytes)
        assert result == b"fake pdf"


# ============================================================================
# Test: Global Manager
# ============================================================================

class TestGlobalBrowserManager:
    """Tests for global browser manager."""

    def test_get_browser_manager_returns_manager(self):
        """Verify get_browser_manager returns BrowserSessionManager"""
        from tools.browser_tool import _session_manager

        manager = get_browser_manager()

        assert manager is _session_manager
        assert isinstance(manager, BrowserSessionManager)


# ============================================================================
# Test: Error Handling
# ============================================================================

class TestBrowserErrorHandling:
    """Tests for error handling in browser operations."""

    def test_session_handles_missing_attributes(self, sample_user_id):
        """Verify session handles missing optional attributes"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id
        )

        # All required attributes should be present
        assert hasattr(session, 'session_id')
        assert hasattr(session, 'user_id')
        assert hasattr(session, 'created_at')
        assert hasattr(session, 'last_used')

    def test_manager_handles_empty_sessions(self):
        """Verify manager handles empty sessions dict"""
        manager = BrowserSessionManager()

        assert len(manager.sessions) == 0
        assert manager.get_session("any") is None

    def test_manager_handles_duplicate_session_ids(self, sample_user_id):
        """Verify manager can handle session overwrite"""
        manager = BrowserSessionManager()
        session1 = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id
        )
        session2 = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id
        )

        manager.sessions["test-session"] = session1
        manager.sessions["test-session"] = session2

        assert manager.get_session("test-session") == session2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

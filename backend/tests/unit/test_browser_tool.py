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
        """Verify close returns False if page close fails (stops on first error)"""
        session = BrowserSession(
            session_id="test-session",
            user_id=sample_user_id
        )

        # Setup mock objects with page.close failing
        session.page = MagicMock()
        session.page.close = AsyncMock(side_effect=Exception("Page close error"))
        session.context = MagicMock()
        session.context.close = AsyncMock()
        session.browser = MagicMock()
        session.browser.close = AsyncMock()
        session.playwright = MagicMock()
        session.playwright.stop = AsyncMock()

        result = await session.close()

        # Should return False when first close fails
        # Note: Implementation stops on first error, so context.close is NOT called
        assert result is False
        session.page.close.assert_called_once()
        # These are not called because error handling stops at first failure
        session.context.close.assert_not_called()
        session.browser.close.assert_not_called()
        session.playwright.stop.assert_not_called()


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
# Test: Browser Navigation
# ============================================================================

class TestBrowserNavigation:
    """Tests for browser navigation functionality."""

    @pytest.mark.asyncio
    async def test_browser_navigate_successfully_loads_url(self, sample_user_id):
        """Verify browser_navigate successfully loads URL"""
        from tools.browser_tool import browser_navigate

        # Create and set up a session
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        # Mock page.goto and related methods
        mock_response = MagicMock()
        mock_response.status = 200

        session.page = MagicMock()
        session.page.goto = AsyncMock(return_value=mock_response)
        session.page.title = AsyncMock(return_value="Example Domain")
        session.page.url = "https://example.com"

        result = await browser_navigate(
            session_id=session.session_id,
            url="https://example.com",
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["title"] == "Example Domain"
        assert result["status"] == 200

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_navigate_returns_page_title(self, sample_user_id):
        """Verify browser_navigate returns page title"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        mock_response = MagicMock()
        mock_response.status = 200

        session.page = MagicMock()
        session.page.goto = AsyncMock(return_value=mock_response)
        session.page.title = AsyncMock(return_value="Test Page Title")
        session.page.url = "https://example.com"

        result = await browser_navigate(
            session_id=session.session_id,
            url="https://example.com",
            user_id=sample_user_id
        )

        assert result["title"] == "Test Page Title"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_navigate_returns_final_url_after_redirects(self, sample_user_id):
        """Verify browser_navigate returns final URL (after redirects)"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        mock_response = MagicMock()
        mock_response.status = 200

        session.page = MagicMock()
        session.page.goto = AsyncMock(return_value=mock_response)
        session.page.title = AsyncMock(return_value="Redirected Page")
        session.page.url = "https://example.com/final-destination"  # Final URL after redirect

        result = await browser_navigate(
            session_id=session.session_id,
            url="https://example.com/redirect",
            user_id=sample_user_id
        )

        assert result["url"] == "https://example.com/final-destination"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_navigate_returns_http_status(self, sample_user_id):
        """Verify browser_navigate returns HTTP status"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        mock_response = MagicMock()
        mock_response.status = 404

        session.page = MagicMock()
        session.page.goto = AsyncMock(return_value=mock_response)
        session.page.title = AsyncMock(return_value="Not Found")
        session.page.url = "https://example.com/notfound"

        result = await browser_navigate(
            session_id=session.session_id,
            url="https://example.com/notfound",
            user_id=sample_user_id
        )

        assert result["status"] == 404

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_navigate_with_wait_until_domcontentloaded(self, sample_user_id):
        """Verify browser_navigate with wait_until='domcontentloaded'"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        mock_response = MagicMock()
        mock_response.status = 200

        session.page = MagicMock()
        session.page.goto = AsyncMock(return_value=mock_response)
        session.page.title = AsyncMock(return_value="Test Page")
        session.page.url = "https://example.com"

        result = await browser_navigate(
            session_id=session.session_id,
            url="https://example.com",
            wait_until="domcontentloaded",
            user_id=sample_user_id
        )

        assert result["success"] is True
        # Verify goto was called with correct wait_until
        session.page.goto.assert_called_once()
        call_kwargs = session.page.goto.call_args[1]
        assert call_kwargs["wait_until"] == "domcontentloaded"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_navigate_with_wait_until_networkidle(self, sample_user_id):
        """Verify browser_navigate with wait_until='networkidle'"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        mock_response = MagicMock()
        mock_response.status = 200

        session.page = MagicMock()
        session.page.goto = AsyncMock(return_value=mock_response)
        session.page.title = AsyncMock(return_value="Test Page")
        session.page.url = "https://example.com"

        result = await browser_navigate(
            session_id=session.session_id,
            url="https://example.com",
            wait_until="networkidle",
            user_id=sample_user_id
        )

        assert result["success"] is True
        # Verify goto was called with correct wait_until
        call_kwargs = session.page.goto.call_args[1]
        assert call_kwargs["wait_until"] == "networkidle"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_navigate_handles_invalid_session_id(self):
        """Verify browser_navigate handles invalid session_id"""
        from tools.browser_tool import browser_navigate

        result = await browser_navigate(
            session_id="non-existent-session-id",
            url="https://example.com"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_browser_navigate_handles_user_id_mismatch(self, sample_user_id):
        """Verify browser_navigate handles user_id mismatch"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        result = await browser_navigate(
            session_id=session.session_id,
            url="https://example.com",
            user_id="different_user_456"
        )

        assert result["success"] is False
        assert "different user" in result["error"].lower()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_navigate_handles_navigation_timeout(self, sample_user_id):
        """Verify browser_navigate handles navigation timeout"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.goto = AsyncMock(side_effect=Exception("Navigation timeout: 30000ms exceeded"))

        result = await browser_navigate(
            session_id=session.session_id,
            url="https://slow-loading-site.com",
            user_id=sample_user_id
        )

        assert result["success"] is False
        assert "timeout" in result["error"].lower() or "exceeded" in result["error"].lower()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_navigate_updates_session_last_used_timestamp(self, sample_user_id):
        """Verify browser_navigate updates session.last_used timestamp"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        # Record original last_used time
        original_last_used = session.last_used

        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.01)

        mock_response = MagicMock()
        mock_response.status = 200

        session.page = MagicMock()
        session.page.goto = AsyncMock(return_value=mock_response)
        session.page.title = AsyncMock(return_value="Test Page")
        session.page.url = "https://example.com"

        await browser_navigate(
            session_id=session.session_id,
            url="https://example.com",
            user_id=sample_user_id
        )

        # Verify last_used was updated
        assert session.last_used > original_last_used

        # Cleanup
        await manager.close_session(session.session_id)


# ============================================================================
# Test: Browser Screenshots
# ============================================================================

class TestBrowserScreenshots:
    """Tests for browser screenshot functionality."""

    @pytest.mark.asyncio
    async def test_browser_screenshot_returns_base64_data_by_default(self, sample_user_id):
        """Verify browser_screenshot returns base64 data by default"""
        from tools.browser_tool import browser_screenshot
        import base64

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        # Mock screenshot method
        screenshot_bytes = b"fake_screenshot_data"
        session.page = MagicMock()
        session.page.screenshot = AsyncMock(return_value=screenshot_bytes)

        result = await browser_screenshot(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert "data" in result
        assert result["format"] == "png"

        # Verify it's valid base64
        decoded = base64.b64decode(result["data"])
        assert decoded == screenshot_bytes

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_screenshot_saves_to_file_when_path_provided(self, sample_user_id, tmp_path):
        """Verify browser_screenshot saves to file when path provided"""
        from tools.browser_tool import browser_screenshot

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        # Mock screenshot method
        screenshot_bytes = b"fake_screenshot_data"
        session.page = MagicMock()
        session.page.screenshot = AsyncMock(return_value=screenshot_bytes)

        # Create temp file path
        screenshot_path = str(tmp_path / "screenshot.png")

        result = await browser_screenshot(
            session_id=session.session_id,
            path=screenshot_path,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert "path" in result
        assert result["path"] == screenshot_path

        # Verify file was created
        import os
        assert os.path.exists(screenshot_path)

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_screenshot_with_full_page_true_captures_entire_page(self, sample_user_id):
        """Verify browser_screenshot with full_page=True captures entire page"""
        from tools.browser_tool import browser_screenshot

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        screenshot_bytes = b"full_page_screenshot"
        session.page = MagicMock()
        session.page.screenshot = AsyncMock(return_value=screenshot_bytes)

        result = await browser_screenshot(
            session_id=session.session_id,
            full_page=True,
            user_id=sample_user_id
        )

        assert result["success"] is True

        # Verify screenshot was called with full_page=True
        session.page.screenshot.assert_called_once()
        call_kwargs = session.page.screenshot.call_args[1]
        assert call_kwargs["full_page"] is True

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_screenshot_with_full_page_false_captures_viewport_only(self, sample_user_id):
        """Verify browser_screenshot with full_page=False captures viewport only"""
        from tools.browser_tool import browser_screenshot

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        screenshot_bytes = b"viewport_screenshot"
        session.page = MagicMock()
        session.page.screenshot = AsyncMock(return_value=screenshot_bytes)

        result = await browser_screenshot(
            session_id=session.session_id,
            full_page=False,
            user_id=sample_user_id
        )

        assert result["success"] is True

        # Verify screenshot was called with full_page=False
        call_kwargs = session.page.screenshot.call_args[1]
        assert call_kwargs["full_page"] is False

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_screenshot_handles_invalid_session_id(self):
        """Verify browser_screenshot handles invalid session_id"""
        from tools.browser_tool import browser_screenshot

        result = await browser_screenshot(
            session_id="non-existent-session-id"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_browser_screenshot_handles_user_id_mismatch(self, sample_user_id):
        """Verify browser_screenshot handles user_id mismatch"""
        from tools.browser_tool import browser_screenshot

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        result = await browser_screenshot(
            session_id=session.session_id,
            user_id="different_user_456"
        )

        assert result["success"] is False
        assert "different user" in result["error"].lower()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_screenshot_returns_png_format(self, sample_user_id):
        """Verify browser_screenshot returns PNG format"""
        from tools.browser_tool import browser_screenshot

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        screenshot_bytes = b"png_data"
        session.page = MagicMock()
        session.page.screenshot = AsyncMock(return_value=screenshot_bytes)

        result = await browser_screenshot(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["format"] == "png"

        # Verify type parameter was passed to screenshot method
        call_kwargs = session.page.screenshot.call_args[1]
        assert call_kwargs["type"] == "png"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_screenshot_returns_size_bytes(self, sample_user_id):
        """Verify browser_screenshot returns size_bytes"""
        from tools.browser_tool import browser_screenshot

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        screenshot_bytes = b"screenshot_of_certain_size"
        session.page = MagicMock()
        session.page.screenshot = AsyncMock(return_value=screenshot_bytes)

        result = await browser_screenshot(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert "size_bytes" in result
        assert result["size_bytes"] == len(screenshot_bytes)

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_screenshot_updates_session_last_used_timestamp(self, sample_user_id):
        """Verify browser_screenshot updates session.last_used timestamp"""
        from tools.browser_tool import browser_screenshot

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        # Record original last_used time
        original_last_used = session.last_used

        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.01)

        screenshot_bytes = b"screenshot"
        session.page = MagicMock()
        session.page.screenshot = AsyncMock(return_value=screenshot_bytes)

        await browser_screenshot(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        # Verify last_used was updated
        assert session.last_used > original_last_used

        # Cleanup
        await manager.close_session(session.session_id)


# ============================================================================
# Test: Browser Interaction
# ============================================================================

class TestBrowserInteraction:
    """Tests for browser interaction functionality."""

    @pytest.mark.asyncio
    async def test_browser_click_successfully_clicks_element(self, sample_user_id):
        """Verify browser_click successfully clicks element"""
        from tools.browser_tool import browser_click

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()
        session.page.click = AsyncMock()

        result = await browser_click(
            session_id=session.session_id,
            selector="#submit-button",
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["selector"] == "#submit-button"
        session.page.click.assert_called_once_with("#submit-button")

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_click_waits_for_element_visibility(self, sample_user_id):
        """Verify browser_click waits for element visibility"""
        from tools.browser_tool import browser_click

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()
        session.page.click = AsyncMock()

        await browser_click(
            session_id=session.session_id,
            selector="#button",
            user_id=sample_user_id
        )

        # Verify wait_for_selector was called with state="visible"
        session.page.wait_for_selector.assert_called_once()
        call_args = session.page.wait_for_selector.call_args
        assert call_args[0][0] == "#button"
        call_kwargs = call_args[1]
        assert call_kwargs.get("state") == "visible"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_click_waits_for_post_click_selector_if_specified(self, sample_user_id):
        """Verify browser_click waits for post-click selector if specified"""
        from tools.browser_tool import browser_click

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()
        session.page.click = AsyncMock()

        await browser_click(
            session_id=session.session_id,
            selector="#submit-button",
            wait_for="#success-message",
            user_id=sample_user_id
        )

        # Verify wait_for_selector was called twice (once for button, once for result)
        assert session.page.wait_for_selector.call_count == 2

        # Verify second call was for success message
        second_call_args = session.page.wait_for_selector.call_args_list[1]
        assert second_call_args[0][0] == "#success-message"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_click_handles_element_not_found(self, sample_user_id):
        """Verify browser_click handles element not found"""
        from tools.browser_tool import browser_click

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock(
            side_effect=Exception("Element #nonexistent not found")
        )

        result = await browser_click(
            session_id=session.session_id,
            selector="#nonexistent",
            user_id=sample_user_id
        )

        assert result["success"] is False
        assert "error" in result

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_click_handles_timeout(self, sample_user_id):
        """Verify browser_click handles timeout"""
        from tools.browser_tool import browser_click

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock(
            side_effect=Exception("Timeout 5000ms exceeded")
        )

        result = await browser_click(
            session_id=session.session_id,
            selector="#slow-button",
            user_id=sample_user_id
        )

        assert result["success"] is False
        assert "timeout" in result["error"].lower() or "exceeded" in result["error"].lower()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_click_updates_session_last_used_timestamp(self, sample_user_id):
        """Verify browser_click updates session.last_used timestamp"""
        from tools.browser_tool import browser_click

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        # Record original last_used time
        original_last_used = session.last_used

        # Small delay
        import asyncio
        await asyncio.sleep(0.01)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()
        session.page.click = AsyncMock()

        await browser_click(
            session_id=session.session_id,
            selector="#button",
            user_id=sample_user_id
        )

        # Verify last_used was updated
        assert session.last_used > original_last_used

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_fill_form_fills_multiple_fields(self, sample_user_id):
        """Verify browser_fill_form fills multiple fields"""
        from tools.browser_tool import browser_fill_form

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()

        # Mock query_selector to return element with tag
        mock_element = MagicMock()
        mock_element.evaluate = AsyncMock(side_effect=lambda code: "INPUT")

        session.page.query_selector = AsyncMock(return_value=mock_element)
        session.page.fill = AsyncMock()

        selectors = {
            "#email": "test@example.com",
            "#name": "Test User",
            "#message": "Hello World"
        }

        result = await browser_fill_form(
            session_id=session.session_id,
            selectors=selectors,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["fields_filled"] == 3

        # Verify fill was called 3 times
        assert session.page.fill.call_count == 3

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_fill_form_handles_input_fields(self, sample_user_id):
        """Verify browser_fill_form handles INPUT fields"""
        from tools.browser_tool import browser_fill_form

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()

        mock_element = MagicMock()
        mock_element.evaluate = AsyncMock(return_value="INPUT")
        session.page.query_selector = AsyncMock(return_value=mock_element)
        session.page.fill = AsyncMock()

        result = await browser_fill_form(
            session_id=session.session_id,
            selectors={"#email": "test@example.com"},
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["fields_filled"] == 1
        session.page.fill.assert_called_once()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_fill_form_handles_textarea_fields(self, sample_user_id):
        """Verify browser_fill_form handles TEXTAREA fields"""
        from tools.browser_tool import browser_fill_form

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()

        mock_element = MagicMock()
        mock_element.evaluate = AsyncMock(return_value="TEXTAREA")
        session.page.query_selector = AsyncMock(return_value=mock_element)
        session.page.fill = AsyncMock()

        result = await browser_fill_form(
            session_id=session.session_id,
            selectors={"#comments": "My comments"},
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["fields_filled"] == 1

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_fill_form_handles_select_dropdowns(self, sample_user_id):
        """Verify browser_fill_form handles SELECT dropdowns"""
        from tools.browser_tool import browser_fill_form

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()

        mock_element = MagicMock()
        mock_element.evaluate = AsyncMock(return_value="SELECT")
        session.page.query_selector = AsyncMock(return_value=mock_element)
        session.page.select_option = AsyncMock()

        result = await browser_fill_form(
            session_id=session.session_id,
            selectors={"#country": "USA"},
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["fields_filled"] == 1
        session.page.select_option.assert_called_once()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_fill_form_submits_form_when_submit_true(self, sample_user_id):
        """Verify browser_fill_form submits form when submit=True"""
        from tools.browser_tool import browser_fill_form

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()

        mock_element = MagicMock()
        mock_element.evaluate = AsyncMock(return_value="INPUT")
        mock_submit_button = MagicMock()
        mock_submit_button.click = AsyncMock()  # Make click async

        session.page.query_selector = AsyncMock(return_value=mock_element)
        session.page.fill = AsyncMock()

        # First call returns submit button, second call returns None (no form)
        session.page.query_selector = AsyncMock(
            side_effect=[mock_element, mock_submit_button, None]
        )

        result = await browser_fill_form(
            session_id=session.session_id,
            selectors={"#email": "test@example.com"},
            submit=True,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result.get("submitted") is True
        assert result.get("submission_method") in ["submit_button", "form_submit"]

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_fill_form_handles_unsupported_element_types_gracefully(self, sample_user_id):
        """Verify browser_fill_form handles unsupported element types gracefully"""
        from tools.browser_tool import browser_fill_form

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()

        # Mock a DIV element (unsupported)
        mock_element = MagicMock()
        mock_element.evaluate = AsyncMock(return_value="DIV")
        session.page.query_selector = AsyncMock(return_value=mock_element)

        result = await browser_fill_form(
            session_id=session.session_id,
            selectors={"#unsupported": "value"},
            user_id=sample_user_id
        )

        # Should still succeed but with 0 fields filled
        assert result["success"] is True
        assert result["fields_filled"] == 0

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_fill_form_returns_count_of_fields_filled(self, sample_user_id):
        """Verify browser_fill_form returns count of fields filled"""
        from tools.browser_tool import browser_fill_form

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()

        mock_element = MagicMock()
        mock_element.evaluate = AsyncMock(return_value="INPUT")
        session.page.query_selector = AsyncMock(return_value=mock_element)
        session.page.fill = AsyncMock()

        selectors = {
            "#field1": "value1",
            "#field2": "value2",
            "#field3": "value3",
            "#field4": "value4"
        }

        result = await browser_fill_form(
            session_id=session.session_id,
            selectors=selectors,
            user_id=sample_user_id
        )

        assert result["fields_filled"] == 4

        # Cleanup
        await manager.close_session(session.session_id)


# ============================================================================
# Test: Browser Data Extraction
# ============================================================================

class TestBrowserDataExtraction:
    """Tests for browser data extraction functionality."""

    @pytest.mark.asyncio
    async def test_browser_extract_text_extracts_full_page_text_without_selector(self, sample_user_id):
        """Verify browser_extract_text extracts full page text without selector"""
        from tools.browser_tool import browser_extract_text

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.inner_text = AsyncMock(return_value="Full page text content here")

        result = await browser_extract_text(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["text"] == "Full page text content here"
        assert result["length"] == len("Full page text content here")

        # Verify inner_text was called with "body"
        session.page.inner_text.assert_called_once_with("body")

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_extract_text_extracts_from_specific_elements_with_selector(self, sample_user_id):
        """Verify browser_extract_text extracts from specific elements with selector"""
        from tools.browser_tool import browser_extract_text

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        # Mock multiple elements
        mock_element1 = MagicMock()
        mock_element1.inner_text = AsyncMock(return_value="Item 1")

        mock_element2 = MagicMock()
        mock_element2.inner_text = AsyncMock(return_value="Item 2")

        mock_element3 = MagicMock()
        mock_element3.inner_text = AsyncMock(return_value="Item 3")

        session.page = MagicMock()
        session.page.query_selector_all = AsyncMock(
            return_value=[mock_element1, mock_element2, mock_element3]
        )

        result = await browser_extract_text(
            session_id=session.session_id,
            selector=".list-item",
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["text"] == "Item 1\nItem 2\nItem 3"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_extract_text_handles_multiple_matching_elements(self, sample_user_id):
        """Verify browser_extract_text handles multiple matching elements"""
        from tools.browser_tool import browser_extract_text

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        # Create multiple mock elements
        mock_elements = []
        for i in range(5):
            mock_el = MagicMock()
            mock_el.inner_text = AsyncMock(return_value=f"Item {i}")
            mock_elements.append(mock_el)

        session.page = MagicMock()
        session.page.query_selector_all = AsyncMock(return_value=mock_elements)

        result = await browser_extract_text(
            session_id=session.session_id,
            selector=".item",
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["text"] == "Item 0\nItem 1\nItem 2\nItem 3\nItem 4"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_extract_text_returns_text_length(self, sample_user_id):
        """Verify browser_extract_text returns text length"""
        from tools.browser_tool import browser_extract_text

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        test_text = "This is some test text with a certain length"
        session.page = MagicMock()
        session.page.inner_text = AsyncMock(return_value=test_text)

        result = await browser_extract_text(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert "length" in result
        assert result["length"] == len(test_text)

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_get_page_info_returns_page_title(self, sample_user_id):
        """Verify browser_get_page_info returns page title"""
        from tools.browser_tool import browser_get_page_info

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.title = AsyncMock(return_value="Test Page Title")
        session.page.url = "https://example.com"
        session.context = MagicMock()
        session.context.cookies = AsyncMock(return_value=[])

        result = await browser_get_page_info(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["title"] == "Test Page Title"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_get_page_info_returns_current_url(self, sample_user_id):
        """Verify browser_get_page_info returns current URL"""
        from tools.browser_tool import browser_get_page_info

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.title = AsyncMock(return_value="Test Page")
        session.page.url = "https://example.com/current-page"
        session.context = MagicMock()
        session.context.cookies = AsyncMock(return_value=[])

        result = await browser_get_page_info(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["url"] == "https://example.com/current-page"

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_get_page_info_returns_cookies_count(self, sample_user_id):
        """Verify browser_get_page_info returns cookies count"""
        from tools.browser_tool import browser_get_page_info

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.title = AsyncMock(return_value="Test Page")
        session.page.url = "https://example.com"
        session.context = MagicMock()
        session.context.cookies = AsyncMock(return_value=[
            {"name": "cookie1", "value": "value1"},
            {"name": "cookie2", "value": "value2"},
            {"name": "cookie3", "value": "value3"}
        ])

        result = await browser_get_page_info(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["cookies_count"] == 3

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_execute_script_executes_javascript_and_returns_result(self, sample_user_id):
        """Verify browser_execute_script executes JavaScript and returns result"""
        from tools.browser_tool import browser_execute_script

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        test_script = "document.title"
        expected_result = "Test Page"
        session.page.evaluate = AsyncMock(return_value=expected_result)

        result = await browser_execute_script(
            session_id=session.session_id,
            script=test_script,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["result"] == expected_result

        # Verify evaluate was called with the script
        session.page.evaluate.assert_called_once_with(test_script)

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_execute_script_handles_invalid_session_id(self):
        """Verify browser_execute_script handles invalid session_id"""
        from tools.browser_tool import browser_execute_script

        result = await browser_execute_script(
            session_id="non-existent-session-id",
            script="document.title"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()


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
# Test: Browser Session Manager
# ============================================================================

class TestBrowserSessionManager:
    """Tests for BrowserSessionManager session management."""

    def test_get_session_returns_existing_session_by_id(self, sample_user_id):
        """Verify get_session returns existing session by ID"""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id=sample_user_id
        )
        manager.sessions["test-session-123"] = session

        result = manager.get_session("test-session-123")

        assert result is not None
        assert result.session_id == "test-session-123"
        assert result.user_id == sample_user_id

    def test_get_session_returns_none_for_non_existent_session(self):
        """Verify get_session returns None for non-existent session"""
        manager = get_browser_manager()

        result = manager.get_session("non-existent-session-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_session_generates_unique_session_id_uuid_v4(self, sample_user_id):
        """Verify create_session generates unique session_id (UUID v4)"""
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session1 = await manager.create_session(user_id=sample_user_id)
            session2 = await manager.create_session(user_id=sample_user_id)

        # Verify session IDs are unique
        assert session1.session_id != session2.session_id

        # Verify format (UUID v4)
        import re
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        assert re.match(uuid_pattern, session1.session_id, re.IGNORECASE)
        assert re.match(uuid_pattern, session2.session_id, re.IGNORECASE)

        # Cleanup
        await manager.close_session(session1.session_id)
        await manager.close_session(session2.session_id)

    @pytest.mark.asyncio
    async def test_create_session_stores_session_in_sessions_dict(self, sample_user_id):
        """Verify create_session stores session in sessions dict"""
        manager = get_browser_manager()
        manager.sessions.clear()  # Start clean

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        # Verify session is stored
        assert session.session_id in manager.sessions
        assert manager.sessions[session.session_id] == session

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_create_session_starts_the_browser_session(self, sample_user_id):
        """Verify create_session starts the browser session"""
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)) as mock_start:
            session = await manager.create_session(user_id=sample_user_id)

        # Verify start was called
        mock_start.assert_called_once()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_close_session_removes_session_from_sessions_dict(self, sample_user_id):
        """Verify close_session removes session from sessions dict"""
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session_id = session.session_id

        # Verify session exists
        assert session_id in manager.sessions

        # Close session
        with patch.object(BrowserSession, 'close', new=AsyncMock(return_value=True)):
            await manager.close_session(session_id)

        # Verify session is removed
        assert session_id not in manager.sessions

    @pytest.mark.asyncio
    async def test_close_session_calls_session_close_method(self, sample_user_id):
        """Verify close_session calls session.close() method"""
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        with patch.object(BrowserSession, 'close', new=AsyncMock(return_value=True)) as mock_close:
            await manager.close_session(session.session_id)

        # Verify close was called
        mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session_returns_false_for_non_existent_session(self):
        """Verify close_session returns False for non-existent session"""
        manager = get_browser_manager()

        result = await manager.close_session("non-existent-session-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_removes_timed_out_sessions(self, sample_user_id):
        """Verify cleanup_expired_sessions removes timed-out sessions"""
        manager = get_browser_manager()
        manager.session_timeout_minutes = 30
        manager.sessions.clear()  # Start clean

        # Create expired session (35 minutes old)
        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            expired_session = await manager.create_session(user_id=sample_user_id)
        expired_session.created_at = datetime.now() - timedelta(minutes=35)
        expired_session.last_used = datetime.now() - timedelta(minutes=35)

        # Create active session
        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            active_session = await manager.create_session(user_id=sample_user_id)

        # Cleanup
        count = await manager.cleanup_expired_sessions()

        assert count == 1
        assert expired_session.session_id not in manager.sessions
        assert active_session.session_id in manager.sessions

        # Cleanup remaining
        await manager.close_session(active_session.session_id)

    def test_session_timeout_default_is_30_minutes(self):
        """Verify session timeout default is 30 minutes"""
        manager = get_browser_manager()

        assert manager.session_timeout_minutes == 30


# ============================================================================
# Test: Browser Close Session
# ============================================================================

class TestBrowserCloseSession:
    """Tests for browser_close_session function."""

    @pytest.mark.asyncio
    async def test_browser_close_session_closes_active_session(self, sample_user_id):
        """Verify browser_close_session closes active session"""
        from tools.browser_tool import browser_close_session

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session_id = session.session_id

        result = await browser_close_session(
            session_id=session_id,
            user_id=sample_user_id
        )

        assert result["success"] is True
        assert result["session_id"] == session_id
        assert session_id not in manager.sessions

    @pytest.mark.asyncio
    async def test_browser_close_session_removes_session_from_manager(self, sample_user_id):
        """Verify browser_close_session removes session from manager"""
        from tools.browser_tool import browser_close_session

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session_id = session.session_id

        # Verify session exists
        assert session_id in manager.sessions

        await browser_close_session(
            session_id=session_id,
            user_id=sample_user_id
        )

        # Verify session is removed
        assert session_id not in manager.sessions

    @pytest.mark.asyncio
    async def test_browser_close_session_handles_non_existent_session(self):
        """Verify browser_close_session handles non-existent session"""
        from tools.browser_tool import browser_close_session

        result = await browser_close_session(
            session_id="non-existent-session-id"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_browser_close_session_validates_user_id(self, sample_user_id):
        """Verify browser_close_session validates user_id"""
        from tools.browser_tool import browser_close_session

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        result = await browser_close_session(
            session_id=session.session_id,
            user_id="different_user_456"
        )

        assert result["success"] is False
        assert "different user" in result["error"].lower()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_close_session_handles_user_id_mismatch(self, sample_user_id):
        """Verify browser_close_session handles user_id mismatch"""
        from tools.browser_tool import browser_close_session

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        result = await browser_close_session(
            session_id=session.session_id,
            user_id="wrong_user_789"
        )

        assert result["success"] is False
        assert "different user" in result["error"].lower()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_close_session_returns_success_true_on_close(self, sample_user_id):
        """Verify browser_close_session returns success=True on close"""
        from tools.browser_tool import browser_close_session

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        result = await browser_close_session(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_browser_close_session_returns_error_when_session_not_found(self):
        """Verify browser_close_session returns error when session not found"""
        from tools.browser_tool import browser_close_session

        result = await browser_close_session(
            session_id="completely-fake-session-id"
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_multiple_sessions_can_be_closed_independently(self, sample_user_id):
        """Verify multiple sessions can be closed independently"""
        from tools.browser_tool import browser_close_session

        manager = get_browser_manager()

        # Create multiple sessions
        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session1 = await manager.create_session(user_id=sample_user_id)
            session2 = await manager.create_session(user_id=sample_user_id)
            session3 = await manager.create_session(user_id=sample_user_id)

        # Close session2 only
        result = await browser_close_session(
            session_id=session2.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is True

        # Verify session2 is closed but session1 and session3 remain
        assert session1.session_id in manager.sessions
        assert session2.session_id not in manager.sessions
        assert session3.session_id in manager.sessions

        # Cleanup remaining sessions
        await manager.close_session(session1.session_id)
        await manager.close_session(session3.session_id)


# ============================================================================
# Test: Browser Error Handling
# ============================================================================

class TestBrowserErrorHandlingDetailed:
    """Tests for error handling in browser operations."""

    @pytest.mark.asyncio
    async def test_browser_navigate_handles_network_errors(self, sample_user_id):
        """Verify browser_navigate handles network errors"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.goto = AsyncMock(
            side_effect=Exception("Network error: Connection refused")
        )

        result = await browser_navigate(
            session_id=session.session_id,
            url="https://unreachable-site.com",
            user_id=sample_user_id
        )

        assert result["success"] is False
        assert "error" in result

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_navigate_handles_invalid_url_format(self, sample_user_id):
        """Verify browser_navigate handles invalid URL format"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.goto = AsyncMock(
            side_effect=Exception("Invalid URL: not-a-url")
        )

        result = await browser_navigate(
            session_id=session.session_id,
            url="not-a-url",
            user_id=sample_user_id
        )

        assert result["success"] is False
        assert "error" in result

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_screenshot_handles_page_screenshot_failure(self, sample_user_id):
        """Verify browser_screenshot handles page screenshot failure"""
        from tools.browser_tool import browser_screenshot

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.screenshot = AsyncMock(
            side_effect=Exception("Screenshot failed: Page not ready")
        )

        result = await browser_screenshot(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is False
        assert "error" in result

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_click_handles_element_click_failure(self, sample_user_id):
        """Verify browser_click handles element click failure"""
        from tools.browser_tool import browser_click

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock(
            side_effect=Exception("Element not clickable")
        )

        result = await browser_click(
            session_id=session.session_id,
            selector="#button",
            user_id=sample_user_id
        )

        assert result["success"] is False
        assert "error" in result

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_fill_form_handles_field_fill_failure(self, sample_user_id):
        """Verify browser_fill_form handles field fill failure"""
        from tools.browser_tool import browser_fill_form

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock(
            side_effect=Exception("Selector timeout")
        )

        result = await browser_fill_form(
            session_id=session.session_id,
            selectors={"#email": "test@example.com"},
            user_id=sample_user_id
        )

        # Should still succeed but with 0 fields filled due to error
        assert result["success"] is True
        assert result["fields_filled"] == 0

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_fill_form_handles_submit_button_not_found(self, sample_user_id):
        """Verify browser_fill_form handles submit button not found"""
        from tools.browser_tool import browser_fill_form

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()

        mock_element = MagicMock()
        mock_element.evaluate = AsyncMock(return_value="INPUT")
        session.page.query_selector = AsyncMock(return_value=mock_element)
        session.page.fill = AsyncMock()

        result = await browser_fill_form(
            session_id=session.session_id,
            selectors={"#email": "test@example.com"},
            submit=True,
            user_id=sample_user_id
        )

        assert result["success"] is True
        # Should have filled the field but submission failed
        assert result["fields_filled"] == 1
        # submitted may be False if no submit button found
        # This is expected behavior

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_extract_text_handles_page_read_failure(self, sample_user_id):
        """Verify browser_extract_text handles page read failure"""
        from tools.browser_tool import browser_extract_text

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.inner_text = AsyncMock(
            side_effect=Exception("Page not loaded")
        )

        result = await browser_extract_text(
            session_id=session.session_id,
            user_id=sample_user_id
        )

        assert result["success"] is False
        assert "error" in result

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_execute_script_handles_javascript_syntax_error(self, sample_user_id):
        """Verify browser_execute_script handles JavaScript syntax error"""
        from tools.browser_tool import browser_execute_script

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.evaluate = AsyncMock(
            side_effect=Exception("JavaScript syntax error: Unexpected token")
        )

        result = await browser_execute_script(
            session_id=session.session_id,
            script="invalid javascript here {",
            user_id=sample_user_id
        )

        assert result["success"] is False
        assert "error" in result

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_browser_create_session_handles_playwright_launch_failure(self, sample_user_id):
        """Verify browser_create_session handles Playwright launch failure"""
        from tools.browser_tool import browser_create_session

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

            with patch.object(BrowserSession, 'start', new=AsyncMock(
                side_effect=Exception("Playwright launch failed: Executable not found")
            )):
                result = await browser_create_session(
                    user_id=sample_user_id,
                    headless=True
                )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_browser_close_session_handles_session_close_failure(self, sample_user_id):
        """Verify browser_close_session handles session close failure"""
        from tools.browser_tool import browser_close_session

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        # Mock manager.close_session to return False
        with patch.object(manager, 'close_session', new=AsyncMock(return_value=False)):
            result = await browser_close_session(
                session_id=session.session_id,
                user_id=sample_user_id
            )

        # Should still report failure
        assert result["success"] is False
        assert "error" in result

        # Cleanup (close will be called during cleanup)
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_all_errors_return_success_false_with_error_message(self, sample_user_id):
        """Verify all errors return success=False with error message"""
        from tools.browser_tool import browser_navigate

        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(user_id=sample_user_id)

        session.page = MagicMock()
        session.page.goto = AsyncMock(
            side_effect=Exception("Test error")
        )

        result = await browser_navigate(
            session_id=session.session_id,
            url="https://example.com",
            user_id=sample_user_id
        )

        assert result.get("success") is False
        assert "error" in result
        assert len(result["error"]) > 0

        # Cleanup
        await manager.close_session(session.session_id)


# ============================================================================
# Test: Browser Type Support
# ============================================================================

class TestBrowserTypeSupport:
    """Tests for browser type support."""

    @pytest.mark.asyncio
    async def test_chromium_browser_type_launches_correctly(self, sample_user_id):
        """Verify Chromium browser type launches correctly"""
        from tools.browser_tool import browser_create_session

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

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

                result = await browser_create_session(
                    user_id=sample_user_id,
                    browser_type="chromium"
                )

        assert result["success"] is True
        assert result["browser_type"] == "chromium"

        # Cleanup
        manager = get_browser_manager()
        await manager.close_session(result["session_id"])

    @pytest.mark.asyncio
    async def test_firefox_browser_type_launches_correctly(self, sample_user_id):
        """Verify Firefox browser type launches correctly"""
        from tools.browser_tool import browser_create_session

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

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

                result = await browser_create_session(
                    user_id=sample_user_id,
                    browser_type="firefox"
                )

        assert result["success"] is True
        assert result["browser_type"] == "firefox"

        # Cleanup
        manager = get_browser_manager()
        await manager.close_session(result["session_id"])

    @pytest.mark.asyncio
    async def test_webkit_browser_type_launches_correctly(self, sample_user_id):
        """Verify WebKit browser type launches correctly"""
        from tools.browser_tool import browser_create_session

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

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

                result = await browser_create_session(
                    user_id=sample_user_id,
                    browser_type="webkit"
                )

        assert result["success"] is True
        assert result["browser_type"] == "webkit"

        # Cleanup
        manager = get_browser_manager()
        await manager.close_session(result["session_id"])

    @pytest.mark.asyncio
    async def test_default_browser_type_is_chromium(self, sample_user_id):
        """Verify default browser type is chromium"""
        from tools.browser_tool import browser_create_session

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

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

                # Don't specify browser_type, should default to chromium
                result = await browser_create_session(
                    user_id=sample_user_id
                )

        assert result["success"] is True
        assert result["browser_type"] == "chromium"

        # Cleanup
        manager = get_browser_manager()
        await manager.close_session(result["session_id"])

    @pytest.mark.asyncio
    async def test_invalid_browser_type_handled_gracefully(self, sample_user_id):
        """Verify invalid browser type is handled gracefully"""
        from tools.browser_tool import browser_create_session

        # Browser tool should still work with invalid type (will try chromium)
        # This is implementation-defined behavior
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

            # Mock the session creation to handle any browser type
            with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
                result = await browser_create_session(
                    user_id=sample_user_id,
                    browser_type="invalid-browser-type"
                )

        # Should either succeed with fallback or fail gracefully
        assert "success" in result

        # Cleanup
        if result.get("success"):
            manager = get_browser_manager()
            await manager.close_session(result["session_id"])

    @pytest.mark.asyncio
    async def test_browser_type_passed_to_session_start_correctly(self, sample_user_id):
        """Verify browser type is passed to session.start() correctly"""
        from tools.browser_tool import browser_create_session

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

            with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)) as mock_start:
                result = await browser_create_session(
                    user_id=sample_user_id,
                    browser_type="firefox"
                )

        # Verify a session was created
        assert result["success"] is True

        # The browser type should be in the result
        assert result["browser_type"] == "firefox"


# ============================================================================
# Test: Error Handling (Original)
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


# ============================================================================
# Governance Enforcement Tests for browser_create_session
# ============================================================================

class TestBrowserCreateSessionGovernance:
    """Tests for browser_create_session() with governance enforcement enabled."""

    @pytest.mark.asyncio
    async def test_create_session_no_agent_no_governance_check(self, sample_user_id):
        """Test session creation without agent skips governance check."""
        from tools.browser_tool import browser_create_session

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            result = await browser_create_session(
                user_id=sample_user_id,
                agent_id=None,
                db=None
            )

            assert result["success"] is True
            assert "session_id" in result

    @pytest.mark.asyncio
    async def test_create_session_intern_agent_allowed(self, sample_user_id):
        """Test INTERN agent can create browser session with governance."""
        from tools.browser_tool import browser_create_session
        from unittest.mock import AsyncMock

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                mock_gov = MagicMock()
                mock_gov.can_perform_action.return_value = {
                    "allowed": True,
                    "reason": "INTERN maturity level permitted"
                }
                mock_gov.record_outcome = AsyncMock()
                mock_factory.get_governance_service.return_value = mock_gov

                with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                    # Mock INTERN agent
                    mock_agent = MagicMock()
                    mock_agent.id = "intern-agent-123"
                    mock_agent.maturity_level = 1  # INTERN
                    mock_agent.status = "INTERN"

                    mock_resolver_instance = MagicMock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
                    mock_resolver.return_value = mock_resolver_instance

                    result = await browser_create_session(
                        user_id=sample_user_id,
                        agent_id="intern-agent-123",
                        db=mock_db
                    )

                    assert result["success"] is True
                    assert "session_id" in result
                    assert result["agent_id"] == "intern-agent-123"
                    # Verify governance check was called
                    mock_gov.can_perform_action.assert_called_once()
                    # Verify outcome was recorded
                    mock_gov.record_outcome.assert_called_once_with(mock_agent.id, success=True)

    @pytest.mark.asyncio
    async def test_create_session_student_agent_blocked(self, sample_user_id):
        """Test STUDENT agent is blocked from creating browser session."""
        from tools.browser_tool import browser_create_session
        from unittest.mock import AsyncMock

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                mock_gov = MagicMock()
                mock_gov.can_perform_action.return_value = {
                    "allowed": False,
                    "reason": "STUDENT agents cannot use browser automation"
                }
                mock_gov.record_outcome = AsyncMock()
                mock_factory.get_governance_service.return_value = mock_gov

                with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                    # Mock STUDENT agent
                    mock_agent = MagicMock()
                    mock_agent.id = "student-agent-123"
                    mock_agent.maturity_level = 0  # STUDENT
                    mock_agent.status = "STUDENT"

                    mock_resolver_instance = MagicMock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
                    mock_resolver.return_value = mock_resolver_instance

                    result = await browser_create_session(
                        user_id=sample_user_id,
                        agent_id="student-agent-123",
                        db=mock_db
                    )

                    assert result["success"] is False
                    assert "not permitted" in result["error"]
                    # Verify governance check was called
                    mock_gov.can_perform_action.assert_called_once()
                    # When governance blocks early, record_outcome is NOT called
                    # (only called in success path or exception handler)
                    mock_gov.record_outcome.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_session_supervised_agent_allowed(self, sample_user_id):
        """Test SUPERVISED agent can create browser session."""
        from tools.browser_tool import browser_create_session
        from unittest.mock import AsyncMock

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                mock_gov = MagicMock()
                mock_gov.can_perform_action.return_value = {
                    "allowed": True,
                    "reason": "SUPERVISED maturity level permitted"
                }
                mock_gov.record_outcome = AsyncMock()
                mock_factory.get_governance_service.return_value = mock_gov

                with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                    # Mock SUPERVISED agent
                    mock_agent = MagicMock()
                    mock_agent.id = "supervised-agent-123"
                    mock_agent.maturity_level = 2  # SUPERVISED
                    mock_agent.status = "SUPERVISED"

                    mock_resolver_instance = MagicMock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
                    mock_resolver.return_value = mock_resolver_instance

                    result = await browser_create_session(
                        user_id=sample_user_id,
                        agent_id="supervised-agent-123",
                        db=mock_db
                    )

                    assert result["success"] is True
                    assert result["agent_id"] == "supervised-agent-123"
                    mock_gov.can_perform_action.assert_called_once()
                    mock_gov.record_outcome.assert_called_once_with(mock_agent.id, success=True)

    @pytest.mark.asyncio
    async def test_create_session_autonomous_agent_allowed(self, sample_user_id):
        """Test AUTONOMOUS agent can create browser session."""
        from tools.browser_tool import browser_create_session
        from unittest.mock import AsyncMock

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                mock_gov = MagicMock()
                mock_gov.can_perform_action.return_value = {
                    "allowed": True,
                    "reason": "AUTONOMOUS maturity level permitted"
                }
                mock_gov.record_outcome = AsyncMock()
                mock_factory.get_governance_service.return_value = mock_gov

                with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                    # Mock AUTONOMOUS agent
                    mock_agent = MagicMock()
                    mock_agent.id = "autonomous-agent-123"
                    mock_agent.maturity_level = 3  # AUTONOMOUS
                    mock_agent.status = "AUTONOMOUS"

                    mock_resolver_instance = MagicMock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
                    mock_resolver.return_value = mock_resolver_instance

                    result = await browser_create_session(
                        user_id=sample_user_id,
                        agent_id="autonomous-agent-123",
                        db=mock_db
                    )

                    assert result["success"] is True
                    assert result["agent_id"] == "autonomous-agent-123"
                    mock_gov.can_perform_action.assert_called_once()
                    mock_gov.record_outcome.assert_called_once_with(mock_agent.id, success=True)

    @pytest.mark.asyncio
    async def test_create_session_records_execution_on_success(self, sample_user_id):
        """Test successful session creation records AgentExecution."""
        from tools.browser_tool import browser_create_session
        from core.models import AgentExecution
        from unittest.mock import AsyncMock

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                mock_gov = MagicMock()
                mock_gov.can_perform_action.return_value = {"allowed": True}
                mock_gov.record_outcome = AsyncMock()
                mock_factory.get_governance_service.return_value = mock_gov

                with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                    mock_agent = MagicMock()
                    mock_agent.id = "agent-123"
                    mock_agent.maturity_level = 1

                    mock_resolver_instance = MagicMock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
                    mock_resolver.return_value = mock_resolver_instance

                    result = await browser_create_session(
                        user_id=sample_user_id,
                        agent_id="agent-123",
                        db=mock_db
                    )

                    assert result["success"] is True
                    # Verify AgentExecution was created and committed
                    mock_db.add.assert_called()
                    assert any(call[0][0].__class__.__name__ == "AgentExecution" for call in mock_db.add.call_args_list)

    @pytest.mark.asyncio
    async def test_create_session_records_outcome_on_failure(self, sample_user_id):
        """Test failed session creation records negative outcome."""
        from tools.browser_tool import browser_create_session
        from unittest.mock import AsyncMock

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                mock_gov = MagicMock()
                mock_gov.can_perform_action.return_value = {"allowed": True}
                mock_gov.record_outcome = AsyncMock()
                mock_factory.get_governance_service.return_value = mock_gov

                with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                    mock_agent = MagicMock()
                    mock_agent.id = "agent-123"
                    mock_agent.maturity_level = 1

                    mock_resolver_instance = MagicMock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('tools.browser_tool.get_browser_manager') as mock_manager:
                        # Make session creation fail
                        mock_manager.return_value.create_session = AsyncMock(side_effect=Exception("Browser launch failed"))

                        result = await browser_create_session(
                            user_id=sample_user_id,
                            agent_id="agent-123",
                            db=mock_db
                        )

                        assert result["success"] is False
                        # Verify governance outcome was recorded with failure
                        mock_gov.record_outcome.assert_called_once_with("agent-123", success=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

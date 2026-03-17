"""Test coverage for browser_tool.py - Target 50%+ coverage."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from tools.browser_tool import (
    BrowserSession,
    BrowserSessionManager,
    get_browser_manager,
    browser_create_session,
    browser_navigate,
    browser_screenshot,
    browser_fill_form,
    browser_click,
    browser_extract_text,
    browser_execute_script,
    browser_close_session,
    browser_get_page_info
)
from core.models import AgentRegistry, AgentStatus


@pytest.fixture
def db_session():
    """Mock database session for testing."""
    return Mock(spec=Session)


@pytest.fixture
def intern_agent(db_session):
    """Create an INTERN level agent (minimum for browser operations)."""
    agent = AgentRegistry(
        id="test-intern-agent",
        tenant_id="test-tenant",
        name="Test Intern Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6
    )
    return agent


@pytest.fixture
def autonomous_agent(db_session):
    """Create an AUTONOMOUS level agent for testing."""
    agent = AgentRegistry(
        id="test-autonomous-agent",
        tenant_id="test-tenant",
        name="Test Autonomous Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95
    )
    return agent


@pytest.fixture
def student_agent(db_session):
    """Create a STUDENT level agent (should be blocked)."""
    agent = AgentRegistry(
        id="test-student-agent",
        tenant_id="test-tenant",
        name="Test Student Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3
    )
    return agent


@pytest.fixture
def mock_playwright_page():
    """Mock Playwright Page object."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"fake_screenshot_bytes")
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.select_option = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock()
    page.query_selector_all = AsyncMock()
    page.evaluate = AsyncMock()
    page.title = AsyncMock(return_value="Test Page")
    page.inner_text = AsyncMock(return_value="Page content")
    page.url = "https://example.com"
    return page


@pytest.fixture
def mock_playwright_browser(mock_playwright_page):
    """Mock Playwright Browser object."""
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=mock_playwright_page)
    browser.close = AsyncMock()
    return browser


@pytest.fixture
def mock_playwright_context(mock_playwright_browser, mock_playwright_page):
    """Mock Playwright BrowserContext object."""
    context = MagicMock()
    context.new_page = AsyncMock(return_value=mock_playwright_page)
    context.close = AsyncMock()
    context.cookies = AsyncMock(return_value=[])
    return context


@pytest.fixture
def mock_playwright(mock_playwright_browser, mock_playwright_context):
    """Mock Playwright object."""
    pw = MagicMock()
    pw.chromium = MagicMock()
    pw.chromium.launch = AsyncMock(return_value=mock_playwright_browser)
    pw.firefox = MagicMock()
    pw.firefox.launch = AsyncMock(return_value=mock_playwright_browser)
    pw.webkit = MagicMock()
    pw.webkit.launch = AsyncMock(return_value=mock_playwright_browser)
    return pw


@pytest.fixture
def mock_async_playwright(mock_playwright):
    """Mock async_playwright context manager."""
    pw_context = MagicMock()
    pw_context.start = AsyncMock(return_value=mock_playwright)
    pw_context.__aenter__ = AsyncMock(return_value=mock_playwright)
    pw_context.__aexit__ = AsyncMock()
    return pw_context


@pytest.fixture
def browser_session():
    """Create a BrowserSession instance for testing."""
    return BrowserSession(
        session_id="test-session-123",
        user_id="test-user",
        agent_id="test-agent",
        headless=True,
        browser_type="chromium"
    )


@pytest.fixture
def reset_session_manager():
    """Reset global session manager before each test."""
    # Import the global manager
    from tools import browser_tool
    old_manager = browser_tool._session_manager
    browser_tool._session_manager = BrowserSessionManager()
    yield
    browser_tool._session_manager = old_manager


class TestBrowserSession:
    """Test BrowserSession class functionality."""

    @pytest.mark.asyncio
    async def test_browser_session_creation(self):
        """Test BrowserSession object creation."""
        session = BrowserSession(
            session_id="test-123",
            user_id="user-123",
            agent_id="agent-123",
            headless=True,
            browser_type="chromium"
        )
        assert session.session_id == "test-123"
        assert session.user_id == "user-123"
        assert session.agent_id == "agent-123"
        assert session.headless is True
        assert session.browser_type == "chromium"
        assert session.playwright is None
        assert session.browser is None
        assert session.context is None
        assert session.page is None

    @pytest.mark.asyncio
    async def test_browser_session_start_chromium(self, mock_async_playwright, mock_playwright):
        """Test starting a chromium browser session."""
        session = BrowserSession(
            session_id="test-123",
            user_id="user-123",
            headless=True,
            browser_type="chromium"
        )

        with patch('tools.browser_tool.async_playwright', return_value=mock_async_playwright):
            result = await session.start()
            assert result is True
            mock_playwright.chromium.launch.assert_called_once_with(headless=True)

    @pytest.mark.asyncio
    async def test_browser_session_start_firefox(self, mock_async_playwright, mock_playwright):
        """Test starting a firefox browser session."""
        session = BrowserSession(
            session_id="test-123",
            user_id="user-123",
            headless=False,
            browser_type="firefox"
        )

        with patch('tools.browser_tool.async_playwright', return_value=mock_async_playwright):
            result = await session.start()
            assert result is True
            mock_playwright.firefox.launch.assert_called_once_with(headless=False)

    @pytest.mark.asyncio
    async def test_browser_session_close(self, browser_session):
        """Test closing a browser session."""
        browser_session.playwright = MagicMock()
        browser_session.playwright.stop = AsyncMock()
        browser_session.browser = MagicMock()
        browser_session.browser.close = AsyncMock()
        browser_session.context = MagicMock()
        browser_session.context.close = AsyncMock()
        browser_session.page = MagicMock()
        browser_session.page.close = AsyncMock()

        result = await browser_session.close()
        assert result is True


class TestBrowserSessionManager:
    """Test BrowserSessionManager class functionality."""

    def test_session_manager_creation(self):
        """Test creating a session manager."""
        manager = BrowserSessionManager(session_timeout_minutes=30)
        assert manager.sessions == {}
        assert manager.session_timeout_minutes == 30

    def test_get_session_not_found(self):
        """Test getting a non-existent session."""
        manager = BrowserSessionManager()
        result = manager.get_session("non-existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_session(self, reset_session_manager):
        """Test creating a new browser session."""
        manager = get_browser_manager()
        session = await manager.create_session(
            user_id="test-user",
            agent_id="test-agent",
            headless=True,
            browser_type="chromium"
        )
        assert session is not None
        assert session.session_id in manager.sessions

    @pytest.mark.asyncio
    async def test_close_session(self, reset_session_manager):
        """Test closing a session."""
        manager = get_browser_manager()
        session = await manager.create_session(user_id="test-user")

        # Mock session close
        session.close = AsyncMock()

        result = await manager.close_session(session.session_id)
        assert result is True
        assert session.session_id not in manager.sessions

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, reset_session_manager):
        """Test cleanup of expired sessions."""
        manager = get_browser_manager()

        # Create a session and manually set last_used to old time
        session = await manager.create_session(user_id="test-user")
        from datetime import timedelta
        session.last_used = datetime.now() - timedelta(minutes=31)

        # Mock session close
        session.close = AsyncMock()

        expired_count = await manager.cleanup_expired_sessions()
        assert expired_count == 1
        assert session.session_id not in manager.sessions


class TestBrowserNavigation:
    """Test browser navigation functionality."""

    @pytest.mark.asyncio
    async def test_navigate_to_url_success(self, reset_session_manager, mock_playwright_page, mock_playwright_browser, mock_playwright_context, mock_async_playwright):
        """Test successful navigation to URL."""
        # Create a session and add it to manager
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user",
            headless=True
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_playwright_page.goto = AsyncMock(return_value=mock_response)
        mock_playwright_page.title = AsyncMock(return_value="Test Page")

        result = await browser_navigate(
            session_id="test-session-123",
            url="https://example.com",
            user_id="test-user"
        )

        assert result["success"] is True
        assert result["session_id"] == "test-session-123"
        assert result["url"] == "https://example.com"
        assert result["title"] == "Test Page"
        mock_playwright_page.goto.assert_called_once()

    @pytest.mark.asyncio
    async def test_navigate_session_not_found(self):
        """Test navigation with non-existent session."""
        result = await browser_navigate(
            session_id="non-existent-session",
            url="https://example.com"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_navigate_wrong_user(self, reset_session_manager):
        """Test navigation with wrong user ID."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="original-user"
        )
        session.page = MagicMock()
        manager.sessions[session.session_id] = session

        result = await browser_navigate(
            session_id="test-session-123",
            url="https://example.com",
            user_id="different-user"
        )

        assert result["success"] is False
        assert "different user" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_navigate_timeout_error(self, reset_session_manager, mock_playwright_page):
        """Test navigation timeout error handling."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        mock_playwright_page.goto = AsyncMock(side_effect=Exception("Timeout"))

        result = await browser_navigate(
            session_id="test-session-123",
            url="https://slow-example.com"
        )

        assert result["success"] is False
        assert "timeout" in str(result.get("error", "")).lower()


class TestPageOperations:
    """Test page interaction operations."""

    @pytest.mark.asyncio
    async def test_take_screenshot(self, reset_session_manager, mock_playwright_page):
        """Test taking a screenshot of current page."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        result = await browser_screenshot(
            session_id="test-session-123",
            full_page=True
        )

        assert result["success"] is True
        assert "data" in result
        assert result["format"] == "png"
        mock_playwright_page.screenshot.assert_called_once_with(full_page=True, type="png")

    @pytest.mark.asyncio
    async def test_screenshot_session_not_found(self):
        """Test screenshot with non-existent session."""
        result = await browser_screenshot(
            session_id="non-existent-session"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_screenshot_save_to_file(self, reset_session_manager, mock_playwright_page, tmp_path):
        """Test saving screenshot to file."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        screenshot_path = str(tmp_path / "screenshot.png")

        with patch('builtins.open', MagicMock()) as mock_open:
            result = await browser_screenshot(
                session_id="test-session-123",
                path=screenshot_path
            )

            assert result["success"] is True
            assert result["path"] == screenshot_path

    @pytest.mark.asyncio
    async def test_screenshot_failure(self, reset_session_manager, mock_playwright_page):
        """Test screenshot failure when page not ready."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        mock_playwright_page.screenshot = AsyncMock(side_effect=Exception("Page not loaded"))

        result = await browser_screenshot(
            session_id="test-session-123"
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_fill_form_fields(self, reset_session_manager, mock_playwright_page):
        """Test filling form fields on a page."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        # Mock element evaluation
        mock_element = MagicMock()
        mock_element.evaluate = AsyncMock(side_effect=lambda x: "INPUT" if "tagName" in x else "text")
        mock_playwright_page.query_selector = AsyncMock(return_value=mock_element)

        form_data = {
            "#email": "user@example.com",
            "#name": "Test User",
            "#country": "US"
        }

        result = await browser_fill_form(
            session_id="test-session-123",
            selectors=form_data
        )

        assert result["success"] is True
        assert result["fields_filled"] == 3

    @pytest.mark.asyncio
    async def test_fill_form_with_submit(self, reset_session_manager, mock_playwright_page):
        """Test filling form with submission."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        # Mock element evaluation
        mock_element = MagicMock()
        mock_element.evaluate = AsyncMock(side_effect=lambda x: "INPUT" if "tagName" in x else "text")
        mock_playwright_page.query_selector = AsyncMock(return_value=mock_element)

        result = await browser_fill_form(
            session_id="test-session-123",
            selectors={"#email": "test@example.com"},
            submit=True
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fill_form_element_not_found(self, reset_session_manager, mock_playwright_page):
        """Test filling form when element not found."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        mock_playwright_page.wait_for_selector = AsyncMock(side_effect=Exception("Element not found"))

        result = await browser_fill_form(
            session_id="test-session-123",
            selectors={"#email": "test@example.com"}
        )

        # Should still succeed but with 0 fields filled
        assert result["success"] is True
        assert result["fields_filled"] == 0

    @pytest.mark.asyncio
    async def test_click_element(self, reset_session_manager, mock_playwright_page):
        """Test clicking an element on the page."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        result = await browser_click(
            session_id="test-session-123",
            selector="#submit-button"
        )

        assert result["success"] is True
        mock_playwright_page.click.assert_called_once_with("#submit-button")

    @pytest.mark.asyncio
    async def test_click_element_not_found(self, reset_session_manager, mock_playwright_page):
        """Test clicking non-existent element."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        mock_playwright_page.wait_for_selector = AsyncMock(side_effect=Exception("Element not found"))

        result = await browser_click(
            session_id="test-session-123",
            selector="#non-existent"
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_extract_text_full_page(self, reset_session_manager, mock_playwright_page):
        """Test extracting full page text."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        result = await browser_extract_text(
            session_id="test-session-123"
        )

        assert result["success"] is True
        assert result["text"] == "Page content"

    @pytest.mark.asyncio
    async def test_extract_text_from_selector(self, reset_session_manager, mock_playwright_page):
        """Test extracting text from specific elements."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        # Mock elements
        mock_elements = [
            MagicMock(inner_text=AsyncMock(return_value="Text 1")),
            MagicMock(inner_text=AsyncMock(return_value="Text 2"))
        ]
        mock_playwright_page.query_selector_all = AsyncMock(return_value=mock_elements)

        result = await browser_extract_text(
            session_id="test-session-123",
            selector=".item"
        )

        assert result["success"] is True
        assert "Text 1" in result["text"]
        assert "Text 2" in result["text"]

    @pytest.mark.asyncio
    async def test_execute_script(self, reset_session_manager, mock_playwright_page):
        """Test executing JavaScript in browser."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        manager.sessions[session.session_id] = session

        mock_playwright_page.evaluate = AsyncMock(return_value=42)

        result = await browser_execute_script(
            session_id="test-session-123",
            script="return 2 * 21"
        )

        assert result["success"] is True
        assert result["result"] == 42
        mock_playwright_page.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_page_info(self, reset_session_manager, mock_playwright_page):
        """Test getting page information."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="test-user"
        )
        session.page = mock_playwright_page
        session.context = MagicMock()
        session.context.cookies = AsyncMock(return_value=[{"name": "test"}])
        manager.sessions[session.session_id] = session

        result = await browser_get_page_info(
            session_id="test-session-123"
        )

        assert result["success"] is True
        assert result["title"] == "Test Page"
        assert result["url"] == "https://example.com"


class TestBrowserSessionLifecycle:
    """Test browser session lifecycle: create, close, state queries."""

    @pytest.mark.asyncio
    async def test_close_browser_session(self, reset_session_manager):
        """Test closing a browser session."""
        manager = get_browser_manager()
        session = await manager.create_session(user_id="test-user")
        
        # Mock session close
        session.close = AsyncMock()

        result = await browser_close_session(
            session_id=session.session_id
        )

        assert result["success"] is True
        assert session.session_id not in manager.sessions

    @pytest.mark.asyncio
    async def test_close_session_not_found(self):
        """Test closing non-existent session."""
        result = await browser_close_session(
            session_id="non-existent-session"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_close_session_wrong_user(self, reset_session_manager):
        """Test closing session with wrong user ID."""
        manager = get_browser_manager()
        session = BrowserSession(
            session_id="test-session-123",
            user_id="original-user"
        )
        session.page = MagicMock()
        manager.sessions[session.session_id] = session

        result = await browser_close_session(
            session_id="test-session-123",
            user_id="different-user"
        )

        assert result["success"] is False
        assert "different user" in result["error"].lower()


class TestBrowserCreateSessionGovernance:
    """Test browser_create_session with governance integration."""

    @pytest.mark.asyncio
    async def test_create_session_no_governance(self, reset_session_manager, mock_async_playwright):
        """Test creating session without governance (no agent_id)."""
        with patch('tools.browser_tool.async_playwright', return_value=mock_async_playwright):
            result = await browser_create_session(
                user_id="test-user",
                db=None
            )

            assert result["success"] is True
            assert "session_id" in result

    @pytest.mark.asyncio
    async def test_create_session_with_governance_allowed(self, reset_session_manager, mock_async_playwright, db_session, intern_agent):
        """Test creating session with governance when allowed."""
        # Mock the governance service
        mock_governance = MagicMock()
        mock_governance.can_perform_action = MagicMock(return_value={"allowed": True})
        mock_governance.record_outcome = AsyncMock()

        with patch('tools.browser_tool.ServiceFactory.get_governance_service', return_value=mock_governance):
            with patch('tools.browser_tool.AgentContextResolver') as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(intern_agent, None))
                MockResolver.return_value = mock_resolver

                with patch('tools.browser_tool.async_playwright', return_value=mock_async_playwright):
                    result = await browser_create_session(
                        user_id="test-user",
                        agent_id="test-intern-agent",
                        db=db_session
                    )

                    assert result["success"] is True
                    assert result["agent_id"] == "test-intern-agent"

    @pytest.mark.asyncio
    async def test_create_session_governance_blocked(self, reset_session_manager, db_session, student_agent):
        """Test creating session when governance blocks (STUDENT agent)."""
        # Mock the governance service to block
        mock_governance = MagicMock()
        mock_governance.can_perform_action = MagicMock(return_value={
            "allowed": False,
            "reason": "LOW_MATURITY"
        })

        with patch('tools.browser_tool.FeatureFlags.should_enforce_governance', return_value=True):
            with patch('tools.browser_tool.ServiceFactory.get_governance_service', return_value=mock_governance):
                with patch('tools.browser_tool.AgentContextResolver') as MockResolver:
                    mock_resolver = MagicMock()
                    mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(student_agent, None))
                    MockResolver.return_value = mock_resolver

                    result = await browser_create_session(
                        user_id="test-user",
                        agent_id="test-student-agent",
                        db=db_session
                    )

                    assert result["success"] is False
                    assert "not permitted" in result["error"].lower()

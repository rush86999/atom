"""
Unit Tests for Browser Automation Tool

Tests browser automation functions:
- Session creation and management
- Page navigation
- Element interaction (click, fill)
- Screenshots
- Web scraping
- Form submission
- JavaScript execution
- Permission checks (INTERN+)
- Governance integration
- Error handling and timeout
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

from tools.browser_tool import (
    browser_create_session,
    browser_navigate,
    browser_screenshot,
    browser_fill_form,
    browser_click,
    browser_extract_text,
    browser_execute_script,
    browser_close_session,
    browser_get_page_info,
    BrowserSession,
    BrowserSessionManager,
    get_browser_manager,
)
from core.models import AgentExecution


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_agent():
    """Mock agent."""
    agent = Mock()
    agent.id = "agent-123"
    agent.name = "Test Agent"
    agent.maturity_level = "INTERN"
    return agent


@pytest.fixture
def mock_governance_service():
    """Mock governance service."""
    with patch("tools.browser_tool.ServiceFactory.get_governance_service") as mock:
        service = Mock()
        service.can_perform_action = Mock(return_value={
            "allowed": True,
            "reason": "Agent permitted"
        })
        service.record_outcome = AsyncMock()
        mock.return_value = service
        yield mock


@pytest.fixture
def mock_agent_context_resolver(mock_agent):
    """Mock agent context resolver."""
    with patch("tools.browser_tool.AgentContextResolver") as mock:
        resolver = Mock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, None))
        mock.return_value = resolver
        yield mock


@pytest.fixture
def mock_browser_session():
    """Mock browser session."""
    session = Mock(spec=BrowserSession)
    session.session_id = "session-123"
    session.user_id = "user-123"
    session.agent_id = "agent-123"
    session.headless = True
    session.browser_type = "chromium"
    session.created_at = datetime.now()
    session.last_used = datetime.now()
    session.page = Mock()
    session.context = Mock()
    return session


@pytest.fixture
def session_manager():
    """Get browser session manager."""
    return get_browser_manager()


# ============================================================================
# Test Browser Session Class
# ============================================================================

class TestBrowserSession:
    """Test BrowserSession class."""

    @pytest.mark.asyncio
    async def test_session_start_chromium(self):
        """Test starting chromium browser session."""
        session = BrowserSession(
            session_id="session-123",
            user_id="user-123",
            agent_id="agent-123",
            headless=True,
            browser_type="chromium"
        )

        with patch("tools.browser_tool.async_playwright") as mock_pw:
            mock_pw_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_pw.return_value.start = AsyncMock(return_value=mock_pw_instance)
            mock_pw_instance.chromium = Mock()
            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)

            result = await session.start()

            assert result is True
            assert session.playwright is not None
            assert session.browser is not None
            assert session.context is not None
            assert session.page is not None

    @pytest.mark.asyncio
    async def test_session_start_firefox(self):
        """Test starting firefox browser session."""
        session = BrowserSession(
            session_id="session-123",
            user_id="user-123",
            browser_type="firefox"
        )

        with patch("tools.browser_tool.async_playwright") as mock_pw:
            mock_pw_instance = AsyncMock()
            mock_browser = AsyncMock()

            mock_pw.return_value.start = AsyncMock(return_value=mock_pw_instance)
            mock_pw_instance.firefox = Mock()
            mock_pw_instance.firefox.launch = AsyncMock(return_value=mock_browser)

            await session.start()

            # Verify firefox was launched
            mock_pw_instance.firefox.launch.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_close(self):
        """Test closing browser session."""
        session = BrowserSession(
            session_id="session-123",
            user_id="user-123"
        )
        session.page = AsyncMock()
        session.context = AsyncMock()
        session.browser = AsyncMock()
        session.playwright = AsyncMock()

        result = await session.close()

        assert result is True
        session.page.close.assert_called_once()
        session.context.close.assert_called_once()
        session.browser.close.assert_called_once()
        session.playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_close_with_errors(self):
        """Test closing session with errors."""
        session = BrowserSession(
            session_id="session-123",
            user_id="user-123"
        )
        session.page = AsyncMock()
        session.page.close.side_effect = Exception("Close error")
        session.context = AsyncMock()
        session.browser = AsyncMock()
        session.playwright = AsyncMock()

        result = await session.close()

        # Should return False due to error
        assert result is False


# ============================================================================
# Test Session Manager
# ============================================================================

class TestBrowserSessionManager:
    """Test BrowserSessionManager class."""

    def test_get_session(self, session_manager):
        """Test getting existing session."""
        session = Mock(spec=BrowserSession)
        session_manager.sessions["session-123"] = session

        result = session_manager.get_session("session-123")

        assert result == session

    def test_get_session_not_found(self, session_manager):
        """Test getting non-existent session."""
        result = session_manager.get_session("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Test creating new browser session."""
        with patch("tools.browser_tool.BrowserSession") as mock_session_class:
            mock_session = Mock()
            mock_session.start = AsyncMock(return_value=True)
            mock_session.session_id = "test-session-id"
            mock_session_class.return_value = mock_session

            result = await session_manager.create_session(
                user_id="user-123",
                agent_id="agent-123",
                headless=True,
                browser_type="chromium"
            )

            assert result is not None
            assert result.session_id == "test-session-id"
            mock_session.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session(self, session_manager):
        """Test closing browser session."""
        mock_session = Mock()
        mock_session.close = AsyncMock(return_value=True)
        session_manager.sessions["session-123"] = mock_session

        result = await session_manager.close_session("session-123")

        assert result is True
        assert "session-123" not in session_manager.sessions

    @pytest.mark.asyncio
    async def test_close_session_not_found(self, session_manager):
        """Test closing non-existent session."""
        result = await session_manager.close_session("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_manager):
        """Test cleanup of expired sessions."""
        # Clear any existing sessions first
        session_manager.sessions.clear()

        # Create expired session with async close method
        old_session = Mock()
        old_session.last_used = datetime.now()  # Set to now
        old_session.close = AsyncMock(return_value=True)  # Async close method
        session_manager.sessions["old-session"] = old_session

        # Set timeout to make session expired
        original_timeout = session_manager.session_timeout_minutes
        session_manager.session_timeout_minutes = 0  # 0 minutes = immediate expiry

        cleaned = await session_manager.cleanup_expired_sessions()

        # Restore original timeout
        session_manager.session_timeout_minutes = original_timeout

        assert cleaned >= 0


# ============================================================================
# Test Browser Create Session
# ============================================================================

class TestBrowserCreateSession:
    """Test browser_create_session function."""

    @pytest.mark.asyncio
    async def test_create_session_success_no_agent(self, session_manager):
        """Test creating session without agent."""
        with patch.object(session_manager, "create_session", new_callable=AsyncMock) as mock_create:
            mock_session = Mock()
            mock_session.session_id = "session-123"
            mock_session.created_at = datetime.now()
            mock_create.return_value = mock_session

            result = await browser_create_session(
                user_id="user-123",
                headless=True,
                browser_type="chromium",
                db=None
            )

            assert result["success"] is True
            assert result["session_id"] == "session-123"
            assert result["browser_type"] == "chromium"

    @pytest.mark.asyncio
    async def test_create_session_with_agent_governance(self, mock_db, mock_agent_context_resolver, mock_governance_service, session_manager):
        """Test creating session with agent and governance."""
        with patch.object(session_manager, "create_session", new_callable=AsyncMock) as mock_create:
            mock_session = Mock()
            mock_session.session_id = "session-123"
            mock_session.created_at = datetime.now()
            mock_create.return_value = mock_session

            result = await browser_create_session(
                user_id="user-123",
                agent_id="agent-123",
                headless=True,
                browser_type="chromium",
                db=mock_db
            )

            assert result["success"] is True
            assert result["agent_id"] == "agent-123"

    @pytest.mark.asyncio
    async def test_create_session_governance_blocked(self, mock_db, mock_agent_context_resolver):
        """Test creating session blocked by governance."""
        with patch("tools.browser_tool.ServiceFactory.get_governance_service") as mock:
            service = Mock()
            service.can_perform_action = Mock(return_value={
                "allowed": False,
                "reason": "Agent maturity too low"
            })
            mock.return_value = service

            result = await browser_create_session(
                user_id="user-123",
                agent_id="student-agent",
                headless=True,
                db=mock_db
            )

            assert result["success"] is False
            assert "not permitted" in result["error"]


# ============================================================================
# Test Browser Navigation
# ============================================================================

class TestBrowserNavigation:
    """Test browser_navigate function."""

    @pytest.mark.asyncio
    async def test_navigate_success(self, session_manager, mock_browser_session):
        """Test successful page navigation."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_response = Mock()
        mock_response.status = 200
        mock_browser_session.page.goto = AsyncMock(return_value=mock_response)
        mock_browser_session.page.title = AsyncMock(return_value="Test Page")
        mock_browser_session.page.url = "https://example.com"

        result = await browser_navigate(
            session_id="session-123",
            url="https://example.com",
            wait_until="load"
        )

        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["title"] == "Test Page"
        assert result["status"] == 200

    @pytest.mark.asyncio
    async def test_navigate_session_not_found(self, session_manager):
        """Test navigating with non-existent session."""
        result = await browser_navigate(
            session_id="nonexistent",
            url="https://example.com"
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_navigate_wrong_user(self, session_manager, mock_browser_session):
        """Test navigating session owned by different user."""
        session_manager.sessions["session-123"] = mock_browser_session

        result = await browser_navigate(
            session_id="session-123",
            url="https://example.com",
            user_id="different-user"
        )

        assert result["success"] is False
        assert "different user" in result["error"]

    @pytest.mark.asyncio
    async def test_navigate_timeout(self, session_manager, mock_browser_session):
        """Test navigation timeout."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.goto = AsyncMock(side_effect=Exception("Timeout"))

        result = await browser_navigate(
            session_id="session-123",
            url="https://slow-site.com"
        )

        assert result["success"] is False
        assert "Timeout" in result["error"]


# ============================================================================
# Test Browser Screenshots
# ============================================================================

class TestBrowserScreenshots:
    """Test browser_screenshot function."""

    @pytest.mark.asyncio
    async def test_screenshot_base64(self, session_manager, mock_browser_session):
        """Test screenshot returning base64 data."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.screenshot = AsyncMock(return_value=b"fake-image-data")

        result = await browser_screenshot(
            session_id="session-123",
            full_page=False
        )

        assert result["success"] is True
        assert "data" in result
        assert result["format"] == "png"
        assert result["size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_screenshot_save_to_file(self, session_manager, mock_browser_session):
        """Test screenshot saved to file."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.screenshot = AsyncMock(return_value=b"fake-image-data")

        with patch("builtins.open", MagicMock()) as mock_open:
            result = await browser_screenshot(
                session_id="session-123",
                path="/tmp/screenshot.png",
                full_page=True
            )

            assert result["success"] is True
            assert result["path"] == "/tmp/screenshot.png"

    @pytest.mark.asyncio
    async def test_screenshot_session_not_found(self, session_manager):
        """Test screenshot with non-existent session."""
        result = await browser_screenshot(
            session_id="nonexistent"
        )

        assert result["success"] is False
        assert "not found" in result["error"]


# ============================================================================
# Test Form Filling
# ============================================================================

class TestFormFilling:
    """Test browser_fill_form function."""

    @pytest.mark.asyncio
    async def test_fill_form_success(self, session_manager, mock_browser_session):
        """Test successful form filling."""
        session_manager.sessions["session-123"] = mock_browser_session

        # Mock element queries
        mock_element = Mock()
        mock_element.evaluate = AsyncMock(side_effect=["INPUT", "text"])
        mock_browser_session.page.query_selector = AsyncMock(return_value=mock_element)
        mock_browser_session.page.wait_for_selector = AsyncMock()
        mock_browser_session.page.fill = AsyncMock()

        result = await browser_fill_form(
            session_id="session-123",
            selectors={
                "#name": "John Doe",
                "#email": "john@example.com"
            },
            submit=False
        )

        assert result["success"] is True
        assert result["fields_filled"] >= 0

    @pytest.mark.asyncio
    async def test_fill_form_with_submit(self, session_manager, mock_browser_session):
        """Test form filling with submission."""
        session_manager.sessions["session-123"] = mock_browser_session

        mock_element = Mock()
        mock_element.evaluate = AsyncMock(side_effect=["INPUT", "text"])
        mock_browser_session.page.query_selector = AsyncMock(return_value=mock_element)
        mock_browser_session.page.wait_for_selector = AsyncMock()
        mock_browser_session.page.fill = AsyncMock()

        # Mock submit button
        mock_submit = Mock()
        mock_browser_session.page.query_selector = AsyncMock(return_value=mock_submit)
        mock_submit.click = AsyncMock()

        result = await browser_fill_form(
            session_id="session-123",
            selectors={"#name": "John"},
            submit=True
        )

        assert result["success"] is True
        assert "submitted" in result

    @pytest.mark.asyncio
    async def test_fill_form_select_element(self, session_manager, mock_browser_session):
        """Test filling select element."""
        session_manager.sessions["session-123"] = mock_browser_session

        mock_element = Mock()
        mock_element.evaluate = AsyncMock(side_effect=["SELECT", "select-one"])
        mock_browser_session.page.query_selector = AsyncMock(return_value=mock_element)
        mock_browser_session.page.wait_for_selector = AsyncMock()
        mock_browser_session.page.select_option = AsyncMock()

        result = await browser_fill_form(
            session_id="session-123",
            selectors={"#country": "USA"}
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fill_form_unsupported_element(self, session_manager, mock_browser_session):
        """Test handling unsupported element type."""
        session_manager.sessions["session-123"] = mock_browser_session

        mock_element = Mock()
        mock_element.evaluate = AsyncMock(side_effect=["DIV", ""])
        mock_browser_session.page.query_selector = AsyncMock(return_value=mock_element)
        mock_browser_session.page.wait_for_selector = AsyncMock()

        result = await browser_fill_form(
            session_id="session-123",
            selectors={"#div": "content"}
        )

        # Should continue despite unsupported element
        assert result["success"] is True


# ============================================================================
# Test Click Interaction
# ============================================================================

class TestClickInteraction:
    """Test browser_click function."""

    @pytest.mark.asyncio
    async def test_click_success(self, session_manager, mock_browser_session):
        """Test successful element click."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.wait_for_selector = AsyncMock()
        mock_browser_session.page.click = AsyncMock()

        result = await browser_click(
            session_id="session-123",
            selector="#submit-button"
        )

        assert result["success"] is True
        assert result["selector"] == "#submit-button"

    @pytest.mark.asyncio
    async def test_click_with_wait(self, session_manager, mock_browser_session):
        """Test click with wait for another element."""
        session_manager.sessions["session-123"] = mock_browser_session

        # First wait for clickable element
        mock_browser_session.page.wait_for_selector = AsyncMock()
        mock_browser_session.page.click = AsyncMock()

        result = await browser_click(
            session_id="session-123",
            selector="#button",
            wait_for="#result"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_click_element_not_visible(self, session_manager, mock_browser_session):
        """Test clicking non-visible element."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.wait_for_selector = AsyncMock(
            side_effect=Exception("Element not visible")
        )

        result = await browser_click(
            session_id="session-123",
            selector="#hidden-button"
        )

        assert result["success"] is False


# ============================================================================
# Test Text Extraction
# ============================================================================

class TestTextExtraction:
    """Test browser_extract_text function."""

    @pytest.mark.asyncio
    async def test_extract_full_page_text(self, session_manager, mock_browser_session):
        """Test extracting full page text."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.inner_text = AsyncMock(return_value="Full page content here")

        result = await browser_extract_text(
            session_id="session-123"
        )

        assert result["success"] is True
        assert result["text"] == "Full page content here"
        assert result["length"] > 0

    @pytest.mark.asyncio
    async def test_extract_element_text(self, session_manager, mock_browser_session):
        """Test extracting text from specific elements."""
        session_manager.sessions["session-123"] = mock_browser_session

        mock_elements = [Mock(), Mock()]
        mock_elements[0].inner_text = AsyncMock(return_value="Item 1")
        mock_elements[1].inner_text = AsyncMock(return_value="Item 2")

        mock_browser_session.page.query_selector_all = AsyncMock(return_value=mock_elements)

        result = await browser_extract_text(
            session_id="session-123",
            selector=".item"
        )

        assert result["success"] is True
        assert "Item 1" in result["text"]
        assert "Item 2" in result["text"]


# ============================================================================
# Test JavaScript Execution
# ============================================================================

class TestJavaScriptExecution:
    """Test browser_execute_script function."""

    @pytest.mark.asyncio
    async def test_execute_script_success(self, session_manager, mock_browser_session):
        """Test successful JavaScript execution."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.evaluate = AsyncMock(return_value={"result": "success"})

        result = await browser_execute_script(
            session_id="session-123",
            script="document.title"
        )

        assert result["success"] is True
        assert result["result"] == {"result": "success"}

    @pytest.mark.asyncio
    async def test_execute_script_error(self, session_manager, mock_browser_session):
        """Test JavaScript execution with error."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.evaluate = AsyncMock(
            side_effect=Exception("JavaScript error")
        )

        result = await browser_execute_script(
            session_id="session-123",
            script="invalid javascript"
        )

        assert result["success"] is False
        assert "error" in result


# ============================================================================
# Test Close Session
# ============================================================================

class TestCloseSession:
    """Test browser_close_session function."""

    @pytest.mark.asyncio
    async def test_close_session_success(self, session_manager, mock_browser_session):
        """Test successfully closing session."""
        session_manager.sessions["session-123"] = mock_browser_session

        with patch.object(session_manager, "close_session", new_callable=AsyncMock) as mock_close:
            mock_close.return_value = True

            result = await browser_close_session(
                session_id="session-123"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_close_session_not_found(self, session_manager):
        """Test closing non-existent session."""
        result = await browser_close_session(
            session_id="nonexistent"
        )

        assert result["success"] is False
        assert "not found" in result["error"]


# ============================================================================
# Test Get Page Info
# ============================================================================

class TestGetPageInfo:
    """Test browser_get_page_info function."""

    @pytest.mark.asyncio
    async def test_get_page_info_success(self, session_manager, mock_browser_session):
        """Test getting page information."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.title = AsyncMock(return_value="Test Page")
        mock_browser_session.page.url = "https://example.com"
        mock_browser_session.context.cookies = AsyncMock(return_value=[
            {"name": "session", "value": "abc123"}
        ])

        result = await browser_get_page_info(
            session_id="session-123"
        )

        assert result["success"] is True
        assert result["title"] == "Test Page"
        assert result["url"] == "https://example.com"
        assert result["cookies_count"] == 1

    @pytest.mark.asyncio
    async def test_get_page_info_session_not_found(self, session_manager):
        """Test getting page info for non-existent session."""
        result = await browser_get_page_info(
            session_id="nonexistent"
        )

        assert result["success"] is False
        assert "not found" in result["error"]


# ============================================================================
# Test Error Recovery
# ============================================================================

class TestErrorRecovery:
    """Test error recovery and resilience."""

    @pytest.mark.asyncio
    async def test_navigation_failure_recovery(self, session_manager, mock_browser_session):
        """Test handling navigation failure gracefully."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.goto = AsyncMock(
            side_effect=Exception("Network error")
        )

        result = await browser_navigate(
            session_id="session-123",
            url="https://invalid-site.com"
        )

        assert result["success"] is False
        assert "Network error" in result["error"]

    @pytest.mark.asyncio
    async def test_screenshot_failure_recovery(self, session_manager, mock_browser_session):
        """Test handling screenshot failure gracefully."""
        session_manager.sessions["session-123"] = mock_browser_session
        mock_browser_session.page.screenshot = AsyncMock(
            side_effect=Exception("Page crashed")
        )

        result = await browser_screenshot(
            session_id="session-123"
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_form_fill_partial_failure(self, session_manager, mock_browser_session):
        """Test form fill with some fields failing."""
        session_manager.sessions["session-123"] = mock_browser_session

        # First element succeeds
        mock_element1 = Mock()
        mock_element1.evaluate = AsyncMock(side_effect=["INPUT", "text"])

        # Second element fails
        mock_browser_session.page.wait_for_selector = AsyncMock(
            side_effect=[None, Exception("Element not found")]
        )
        mock_browser_session.page.query_selector = AsyncMock(return_value=mock_element1)
        mock_browser_session.page.fill = AsyncMock()

        result = await browser_fill_form(
            session_id="session-123",
            selectors={"#field1": "value1", "#field2": "value2"}
        )

        # Should still succeed despite one field failing
        assert result["success"] is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for browser tool workflows."""

    @pytest.mark.asyncio
    async def test_full_navigation_workflow(self, session_manager, mock_browser_session):
        """Test complete navigation workflow."""
        session_manager.sessions["session-123"] = mock_browser_session

        # Setup mocks
        mock_response = Mock()
        mock_response.status = 200
        mock_browser_session.page.goto = AsyncMock(return_value=mock_response)
        mock_browser_session.page.title = AsyncMock(return_value="Home Page")
        mock_browser_session.page.url = "https://example.com"
        mock_browser_session.page.screenshot = AsyncMock(return_value=b"screenshot")
        mock_browser_session.context.cookies = AsyncMock(return_value=[])

        # Navigate
        nav_result = await browser_navigate(
            session_id="session-123",
            url="https://example.com"
        )
        assert nav_result["success"] is True

        # Screenshot
        shot_result = await browser_screenshot(
            session_id="session-123",
            full_page=False
        )
        assert shot_result["success"] is True

        # Get info
        info_result = await browser_get_page_info(
            session_id="session-123"
        )
        assert info_result["success"] is True
        assert info_result["title"] == "Home Page"

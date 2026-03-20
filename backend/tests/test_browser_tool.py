"""
Tests for Browser Tool

Comprehensive tests covering browser automation, navigation, interaction,
and governance. Tests Playwright CDP integration.

Coverage target: 80%+ line coverage for tools/browser_tool.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4
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
    get_browser_manager,
    BrowserSessionManager
)
from core.models import AgentExecution, AgentStatus


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.fixture
def mock_agent():
    """Mock agent with AUTONOMOUS maturity."""
    agent = MagicMock()
    agent.id = "test-agent-1"
    agent.name = "Test Agent"
    agent.status = AgentStatus.AUTONOMOUS.value
    return agent


@pytest.fixture
def mock_browser_session():
    """Mock browser session."""
    session = MagicMock()
    session.session_id = str(uuid4())
    session.user_id = "test-user-1"
    session.agent_id = "test-agent-1"
    session.headless = True
    session.browser_type = "chromium"
    session.created_at = datetime.now()
    session.last_used = datetime.now()
    session.page = MagicMock()
    session.context = MagicMock()
    session.browser = MagicMock()
    session.close = AsyncMock(return_value=True)
    return session


# ============================================================================
# Test Browser Session Management
# ============================================================================

class TestBrowserSessionManager:
    """Tests for BrowserSessionManager class."""

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test getting an existing session."""
        manager = BrowserSessionManager()
        session_id = "test-session-123"

        # Add a session
        manager.sessions[session_id] = {"session_id": session_id, "user_id": "user-1"}

        session = manager.get_session(session_id)
        assert session is not None
        assert session["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_get_session_not_found(self):
        """Test getting a non-existent session."""
        manager = BrowserSessionManager()
        session = manager.get_session("non-existent")
        assert session is None

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test closing a session."""
        manager = BrowserSessionManager()
        session_id = "test-session-123"

        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        manager.sessions[session_id] = mock_session

        result = await manager.close_session(session_id)

        assert result is True
        mock_session.close.assert_called_once()
        assert session_id not in manager.sessions

    @pytest.mark.asyncio
    async def test_close_session_not_found(self):
        """Test closing a non-existent session."""
        manager = BrowserSessionManager()
        result = await manager.close_session("non-existent")
        assert result is False


# ============================================================================
# Test Browser Session Creation
# ============================================================================

class TestBrowserSessionCreation:
    """Tests for browser_create_session function."""

    @pytest.mark.asyncio
    async def test_create_session_without_governance(self):
        """Test creating browser session without governance."""
        user_id = "test-user-1"

        with patch('tools.browser_tool.FeatureFlags.should_enforce_governance', return_value=False), \
             patch('tools.browser_tool.get_browser_manager') as mock_get_manager:

            mock_manager = MagicMock()
            mock_session = MagicMock()
            mock_session.session_id = "session-123"
            mock_session.created_at = datetime.now()
            mock_manager.create_session = AsyncMock(return_value=mock_session)
            mock_get_manager.return_value = mock_manager

            result = await browser_create_session(
                user_id=user_id,
                headless=True,
                browser_type="chromium"
            )

            assert result["success"] is True
            assert result["session_id"] == "session-123"
            assert result["agent_id"] is None

    @pytest.mark.asyncio
    async def test_create_session_with_agent(self):
        """Test creating browser session with agent."""
        user_id = "test-user-1"
        agent = MagicMock()
        agent.id = "agent-1"

        with patch('tools.browser_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.browser_tool.ServiceFactory') as mock_factory, \
             patch('tools.browser_tool.get_browser_manager') as mock_get_manager:

            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, {}))

            mock_governance = MagicMock()
            mock_factory.get_governance_service.return_value = mock_governance
            mock_governance.can_perform_action.return_value = {"allowed": True}
            mock_governance.record_outcome = AsyncMock()

            mock_manager = MagicMock()
            mock_session = MagicMock()
            mock_session.session_id = "session-123"
            mock_session.created_at = datetime.now()
            mock_manager.create_session = AsyncMock(return_value=mock_session)
            mock_get_manager.return_value = mock_manager

            result = await browser_create_session(
                user_id=user_id,
                agent_id=agent.id,
                db=MagicMock(),
                headless=True
            )

            assert result["success"] is True
            assert result["agent_id"] == agent.id

    @pytest.mark.asyncio
    async def test_create_session_governance_blocked(self):
        """Test session creation blocked by governance."""
        user_id = "test-user-1"
        agent = MagicMock()
        agent.id = "agent-1"

        with patch('tools.browser_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.browser_tool.ServiceFactory') as mock_factory:

            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, {}))

            mock_governance = MagicMock()
            mock_factory.get_governance_service.return_value = mock_governance
            mock_governance.can_perform_action.return_value = {
                "allowed": False,
                "reason": "STUDENT agents cannot use browser"
            }

            result = await browser_create_session(
                user_id=user_id,
                agent_id=agent.id,
                db=MagicMock()
            )

            assert result["success"] is False
            assert "not permitted" in result["error"]


# ============================================================================
# Test Browser Navigation
# ============================================================================

class TestBrowserNavigation:
    """Tests for browser navigation functionality."""

    @pytest.mark.asyncio
    async def test_navigate_to_url(self, mock_browser_session):
        """Test navigating to a URL."""
        session_id = mock_browser_session.session_id
        url = "https://example.com"

        # Mock the page.goto to return a response object
        mock_response = MagicMock()
        mock_response.url = url
        mock_response.status = 200
        mock_browser_session.page.goto = AsyncMock(return_value=mock_response)
        mock_browser_session.page.title = AsyncMock(return_value="Test Page")
        mock_browser_session.page.url = url

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_navigate(
                session_id=session_id,
                url=url,
                wait_until="load"
            )

            assert result["success"] is True
            assert result["url"] == url
            mock_browser_session.page.goto.assert_called_once()

    @pytest.mark.asyncio
    async def test_navigate_session_not_found(self):
        """Test navigating with non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = None
            mock_get_manager.return_value = mock_manager

            result = await browser_navigate(
                session_id="non-existent",
                url="https://example.com"
            )

            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_navigate_wrong_user(self, mock_browser_session):
        """Test navigating with wrong user ID."""
        mock_browser_session.user_id = "user-1"

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_navigate(
                session_id=mock_browser_session.session_id,
                url="https://example.com",
                user_id="user-2"  # Different user
            )

            assert result["success"] is False
            assert "different user" in result["error"]

    @pytest.mark.asyncio
    async def test_navigate_error_handling(self, mock_browser_session):
        """Test error handling in navigation."""
        session_id = mock_browser_session.session_id

        mock_browser_session.page.goto = AsyncMock(
            side_effect=Exception("Navigation failed")
        )

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_navigate(
                session_id=session_id,
                url="https://example.com"
            )

            assert result["success"] is False
            assert "error" in result


# ============================================================================
# Test Browser Screenshots
# ============================================================================

class TestBrowserScreenshots:
    """Tests for browser screenshot functionality."""

    @pytest.mark.asyncio
    async def test_take_screenshot(self, mock_browser_session):
        """Test taking a screenshot."""
        session_id = mock_browser_session.session_id

        mock_browser_session.page.screenshot = AsyncMock(return_value=b"screenshot_data")
        # Add base64 encoding mock
        import base64
        mock_browser_session.page.screenshot = AsyncMock(return_value=b"screenshot_data")

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager, \
             patch('base64.b64encode', return_value=b'c2NyZWVuc2hvdF9kYXRh'):

            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_screenshot(
                session_id=session_id,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is True
            assert "screenshot" in result
            mock_browser_session.page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_screenshot_session_not_found(self):
        """Test screenshot with non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = None
            mock_get_manager.return_value = mock_manager

            result = await browser_screenshot(
                session_id="non-existent",
                user_id="user-1"
            )

            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_screenshot_error_handling(self, mock_browser_session):
        """Test error handling in screenshot."""
        session_id = mock_browser_session.session_id

        mock_browser_session.page.screenshot = AsyncMock(
            side_effect=Exception("Screenshot failed")
        )

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_screenshot(
                session_id=session_id,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is False


# ============================================================================
# Test Browser Interaction
# ============================================================================

class TestBrowserInteraction:
    """Tests for browser interaction functionality."""

    @pytest.mark.asyncio
    async def test_click_element(self, mock_browser_session):
        """Test clicking an element."""
        session_id = mock_browser_session.session_id
        selector = "#submit-button"

        mock_browser_session.page.click = AsyncMock(return_value=None)
        # The code gets the title after clicking
        mock_browser_session.page.title = AsyncMock(return_value="Page After Click")

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_click(
                session_id=session_id,
                selector=selector,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is True
            mock_browser_session.page.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_element_not_found(self, mock_browser_session):
        """Test clicking non-existent element."""
        session_id = mock_browser_session.session_id
        selector = "#non-existent"

        mock_browser_session.page.click = AsyncMock(
            side_effect=Exception("Element not found")
        )

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_click(
                session_id=session_id,
                selector=selector,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_fill_form(self, mock_browser_session):
        """Test filling form fields."""
        session_id = mock_browser_session.session_id

        form_data = {
            "#email": "test@example.com",
            "#name": "Test User"
        }

        mock_browser_session.page.fill = AsyncMock(return_value=None)
        # The code gets the title after filling
        mock_browser_session.page.title = AsyncMock(return_value="Form Filled")

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_fill_form(
                session_id=session_id,
                form_data=form_data,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is True
            assert mock_browser_session.page.fill.call_count == len(form_data)

    @pytest.mark.asyncio
    async def test_fill_form_error_handling(self, mock_browser_session):
        """Test error handling in form filling."""
        session_id = mock_browser_session.session_id

        mock_browser_session.page.fill = AsyncMock(
            side_effect=Exception("Fill failed")
        )
        mock_browser_session.page.title = AsyncMock(return_value="Error Page")

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_fill_form(
                session_id=session_id,
                form_data={"#field": "value"},
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is False


# ============================================================================
# Test Browser Content Extraction
# ============================================================================

class TestBrowserContentExtraction:
    """Tests for browser content extraction functionality."""

    @pytest.mark.asyncio
    async def test_extract_all_text(self, mock_browser_session):
        """Test extracting all page text."""
        session_id = mock_browser_session.session_id

        mock_browser_session.page.inner_text = AsyncMock(return_value="Page full text content")

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_extract_text(
                session_id=session_id,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is True
            assert "text" in result
            assert result["text"] == "Page full text content"

    @pytest.mark.asyncio
    async def test_extract_text_session_not_found(self):
        """Test text extraction with non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = None
            mock_get_manager.return_value = mock_manager

            result = await browser_extract_text(
                session_id="non-existent",
                user_id="user-1"
            )

            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_text_error_handling(self, mock_browser_session):
        """Test error handling in text extraction."""
        session_id = mock_browser_session.session_id

        mock_browser_session.page.inner_text = AsyncMock(
            side_effect=Exception("Extraction failed")
        )

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_extract_text(
                session_id=session_id,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is False


# ============================================================================
# Test Browser Script Execution
# ============================================================================

class TestBrowserScriptExecution:
    """Tests for browser JavaScript execution."""

    @pytest.mark.asyncio
    async def test_execute_script(self, mock_browser_session):
        """Test executing JavaScript in browser."""
        session_id = mock_browser_session.session_id
        script = "document.title = 'New Title';"

        mock_browser_session.page.evaluate = AsyncMock(return_value=None)

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_execute_script(
                session_id=session_id,
                script=script,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is True
            mock_browser_session.page.evaluate.assert_called_once_with(script)

    @pytest.mark.asyncio
    async def test_execute_script_with_result(self, mock_browser_session):
        """Test executing script that returns a value."""
        session_id = mock_browser_session.session_id
        script = "return document.title;"

        expected_result = "Page Title"
        mock_browser_session.page.evaluate = AsyncMock(return_value=expected_result)

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_execute_script(
                session_id=session_id,
                script=script,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is True
            assert result["result"] == expected_result

    @pytest.mark.asyncio
    async def test_execute_script_error(self, mock_browser_session):
        """Test executing script that throws error."""
        session_id = mock_browser_session.session_id
        script = "throw new Error('Script error');"

        mock_browser_session.page.evaluate = AsyncMock(
            side_effect=Exception("Script error")
        )

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_execute_script(
                session_id=session_id,
                script=script,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is False
            assert "error" in result


# ============================================================================
# Test Browser Session Closure
# ============================================================================

class TestBrowserSessionClosure:
    """Tests for browser session closure functionality."""

    @pytest.mark.asyncio
    async def test_close_browser_session(self, mock_browser_session):
        """Test closing a browser session."""
        session_id = mock_browser_session.session_id

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_manager.close_session = AsyncMock(return_value=True)
            mock_get_manager.return_value = mock_manager

            result = await browser_close_session(
                session_id=session_id,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is True
            mock_manager.close_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session_not_found(self):
        """Test closing non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = None
            mock_get_manager.return_value = mock_manager

            result = await browser_close_session(
                session_id="non-existent",
                user_id="user-1"
            )

            assert result["success"] is False
            assert "not found" in result["error"]


# ============================================================================
# Test Browser Page Info
# ============================================================================

class TestBrowserPageInfo:
    """Tests for getting browser page information."""

    @pytest.mark.asyncio
    async def test_get_page_info(self, mock_browser_session):
        """Test getting page information."""
        session_id = mock_browser_session.session_id

        # page.title is a callable (async method)
        async def mock_title_func():
            return "Test Page"

        mock_browser_session.page.title = mock_title_func
        mock_browser_session.page.url = "https://example.com/page"
        mock_browser_session.page.evaluate = AsyncMock(return_value="https://example.com/page")

        with patch('tools.browser_tool.get_browser_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session.return_value = mock_browser_session
            mock_get_manager.return_value = mock_manager

            result = await browser_get_page_info(
                session_id=session_id,
                user_id=mock_browser_session.user_id
            )

            assert result["success"] is True
            assert "title" in result
            assert "url" in result


# ============================================================================
# Test Browser Permissions
# ============================================================================

class TestBrowserPermissions:
    """Tests for browser access permissions by maturity level."""

    @pytest.mark.asyncio
    async def test_intern_can_navigate(self):
        """Test INTERN agents can use browser navigation."""
        intern_agent = MagicMock()
        intern_agent.id = "intern-agent"
        intern_agent.status = AgentStatus.INTERN.value

        with patch('tools.browser_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.browser_tool.ServiceFactory') as mock_factory, \
             patch('tools.browser_tool.get_browser_manager') as mock_get_manager:

            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(intern_agent, {}))

            mock_governance = MagicMock()
            mock_factory.get_governance_service.return_value = mock_governance
            mock_governance.can_perform_action.return_value = {"allowed": True}
            mock_governance.record_outcome = AsyncMock()

            mock_manager = MagicMock()
            mock_session = MagicMock()
            mock_session.session_id = "session-123"
            mock_session.created_at = datetime.now()
            mock_manager.create_session = AsyncMock(return_value=mock_session)
            mock_get_manager.return_value = mock_manager

            result = await browser_create_session(
                user_id="user-1",
                agent_id=intern_agent.id,
                db=MagicMock()
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_student_blocked(self):
        """Test STUDENT agents are blocked from browser."""
        student_agent = MagicMock()
        student_agent.id = "student-agent"
        student_agent.status = AgentStatus.STUDENT.value

        with patch('tools.browser_tool.FeatureFlags.should_enforce_governance', return_value=True), \
             patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class, \
             patch('tools.browser_tool.ServiceFactory') as mock_factory:

            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(student_agent, {}))

            mock_governance = MagicMock()
            mock_factory.get_governance_service.return_value = mock_governance
            mock_governance.can_perform_action.return_value = {
                "allowed": False,
                "reason": "STUDENT agents cannot use browser"
            }

            result = await browser_create_session(
                user_id="user-1",
                agent_id=student_agent.id,
                db=MagicMock()
            )

            assert result["success"] is False
            assert "not permitted" in result["error"]

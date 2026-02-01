"""
Unit tests for browser automation with governance integration.

Tests cover:
- Browser session creation and management
- Navigation, screenshot, form filling
- Governance checks for browser actions (INTERN+ required)
- Browser audit trail creation
- Agent execution tracking
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime
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
    browser_get_page_info,
)
from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, User, Workspace


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_user():
    """Mock user."""
    user = Mock(spec=User)
    user.id = "user-1"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_agent_intern():
    """Mock intern-level agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "intern-agent-1"
    agent.name = "Intern Agent"
    agent.category = "automation"
    agent.status = AgentStatus.INTERN.value
    agent.confidence_score = 0.6
    return agent


@pytest.fixture
def mock_agent_student():
    """Mock student-level agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "student-agent-1"
    agent.name = "Student Agent"
    agent.category = "automation"
    agent.status = AgentStatus.STUDENT.value
    agent.confidence_score = 0.4
    return agent


# ============================================================================
# BrowserSession Tests
# ============================================================================

class TestBrowserSession:
    """Tests for BrowserSession class."""

    @pytest.mark.asyncio
    async def test_browser_session_init(self):
        """Test browser session initialization."""
        session = BrowserSession(
            session_id="test-session",
            user_id="user-1",
            agent_id="agent-1",
            headless=True,
            browser_type="chromium"
        )

        assert session.session_id == "test-session"
        assert session.user_id == "user-1"
        assert session.agent_id == "agent-1"
        assert session.headless is True
        assert session.browser_type == "chromium"
        assert session.playwright is None
        assert session.browser is None
        assert session.context is None
        assert session.page is None


# ============================================================================
# BrowserSessionManager Tests
# ============================================================================

class TestBrowserSessionManager:
    """Tests for BrowserSessionManager class."""

    def test_session_manager_init(self):
        """Test session manager initialization."""
        manager = BrowserSessionManager(session_timeout_minutes=30)
        assert manager.sessions == {}
        assert manager.session_timeout_minutes == 30

    def test_get_session_not_found(self):
        """Test getting non-existent session returns None."""
        manager = BrowserSessionManager()
        session = manager.get_session("non-existent")
        assert session is None

    @pytest.mark.asyncio
    async def test_create_and_close_session(self):
        """Test creating and closing a session."""
        manager = BrowserSessionManager()

        # Mock the browser session start method
        with patch.object(BrowserSession, 'start', new_callable=AsyncMock) as mock_start:
            with patch.object(BrowserSession, 'close', new_callable=AsyncMock) as mock_close:
                session = await manager.create_session(
                    user_id="user-1",
                    agent_id="agent-1",
                    headless=True
                )

                assert session is not None
                assert session.session_id in manager.sessions
                mock_start.assert_called_once()

                # Close session
                result = await manager.close_session(session.session_id)
                assert result is True
                assert session.session_id not in manager.sessions
                mock_close.assert_called_once()


# ============================================================================
# Browser Tool Functions Tests
# ============================================================================

class TestBrowserCreateSession:
    """Tests for browser_create_session function."""

    @pytest.mark.asyncio
    async def test_create_session_basic(self, mock_user):
        """Test basic session creation without governance."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = Mock()
            mock_session.session_id = "test-session-1"
            mock_session.created_at = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.create_session = AsyncMock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            result = await browser_create_session(
                user_id=mock_user.id,
                agent_id=None,
                headless=True,
                browser_type="chromium",
                db=None
            )

            assert result["success"] is True
            assert result["session_id"] == "test-session-1"
            assert result["browser_type"] == "chromium"

    @pytest.mark.asyncio
    async def test_create_session_with_governance_blocked(
        self, mock_db, mock_user, mock_agent_student
    ):
        """Test session creation blocked by governance (student agent)."""
        with patch.object(BrowserSessionManager, 'create_session', new_callable=AsyncMock) as mock_create:
            # Mock agent resolution and governance check
            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                with patch('tools.browser_tool.AgentGovernanceService') as mock_gov_class:
                    # Setup mocks
                    mock_resolver = Mock()
                    mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent_student, {}))
                    mock_resolver_class.return_value = mock_resolver

                    mock_gov = Mock()
                    mock_gov.can_perform_action.return_value = {
                        "allowed": False,
                        "reason": "Student agent not permitted for browser actions"
                    }
                    mock_gov.record_outcome = AsyncMock()
                    mock_gov_class.return_value = mock_gov

                    result = await browser_create_session(
                        user_id=mock_user.id,
                        agent_id=mock_agent_student.id,
                        headless=True,
                        db=mock_db
                    )

                    assert result["success"] is False
                    assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_create_session_with_governance_allowed(
        self, mock_db, mock_user, mock_agent_intern
    ):
        """Test session creation allowed by governance (intern agent)."""
        # Mock database operations
        mock_execution = Mock()
        mock_execution.id = "exec-1"

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda obj: setattr(obj, 'id', 'exec-1') if obj.__class__.__name__ == 'AgentExecution' else None)

        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = Mock()
            mock_session.session_id = "test-session-2"
            mock_session.created_at = datetime.now()

            mock_mgr_instance = Mock()
            mock_mgr_instance.create_session = AsyncMock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            # Mock agent resolution and governance check
            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                with patch('tools.browser_tool.AgentGovernanceService') as mock_gov_class:
                    # Setup mocks
                    mock_resolver = Mock()
                    mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent_intern, {}))
                    mock_resolver_class.return_value = mock_resolver

                    mock_gov = Mock()
                    mock_gov.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Intern agent permitted"
                    }
                    mock_gov.record_outcome = AsyncMock()
                    mock_gov_class.return_value = mock_gov

                    result = await browser_create_session(
                        user_id=mock_user.id,
                        agent_id=mock_agent_intern.id,
                        headless=True,
                        db=mock_db
                    )

                    assert result["success"] is True
                    assert result["session_id"] == "test-session-2"
                    assert result["agent_id"] == mock_agent_intern.id


class TestBrowserNavigate:
    """Tests for browser_navigate function."""

    @pytest.mark.asyncio
    async def test_navigate_session_not_found(self):
        """Test navigation with non-existent session."""
        result = await browser_navigate(
            session_id="non-existent",
            url="https://example.com",
            user_id="user-1"
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_navigate_wrong_user(self):
        """Test navigation with wrong user ownership."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = Mock()
            mock_session.user_id = "other-user"
            mock_session.page = Mock()

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            result = await browser_navigate(
                session_id="test-session",
                url="https://example.com",
                user_id="user-1"
            )

            assert result["success"] is False
            assert "different user" in result["error"]


class TestBrowserScreenshot:
    """Tests for browser_screenshot function."""

    @pytest.mark.asyncio
    async def test_screenshot_base64(self):
        """Test screenshot returns base64 data."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = Mock()
            mock_session.user_id = "user-1"
            mock_session.page = Mock()
            mock_session.page.screenshot = AsyncMock(return_value=b"fake-image-data")
            mock_session.last_used = None

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            result = await browser_screenshot(
                session_id="test-session",
                user_id="user-1"
            )

            assert result["success"] is True
            assert "data" in result
            assert result["format"] == "png"


class TestBrowserFillForm:
    """Tests for browser_fill_form function."""

    @pytest.mark.asyncio
    async def test_fill_form_success(self):
        """Test successful form filling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_element = Mock()
            mock_element.evaluate = AsyncMock(side_effect=lambda x: "INPUT" if "tagName" in x else "text")

            mock_session = Mock()
            mock_session.user_id = "user-1"
            mock_session.page = Mock()
            mock_session.page.wait_for_selector = AsyncMock(return_value=mock_element)
            mock_session.page.query_selector = AsyncMock(return_value=mock_element)
            mock_session.page.fill = AsyncMock()
            mock_session.last_used = None

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            result = await browser_fill_form(
                session_id="test-session",
                selectors={"#name": "John Doe", "#email": "john@example.com"},
                submit=False,
                user_id="user-1"
            )

            assert result["success"] is True
            assert result["fields_filled"] == 2


class TestBrowserClick:
    """Tests for browser_click function."""

    @pytest.mark.asyncio
    async def test_click_success(self):
        """Test successful element click."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = Mock()
            mock_session.user_id = "user-1"
            mock_session.page = Mock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.click = AsyncMock()
            mock_session.last_used = None

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            result = await browser_click(
                session_id="test-session",
                selector="#submit-button",
                user_id="user-1"
            )

            assert result["success"] is True
            assert result["selector"] == "#submit-button"


class TestBrowserExtractText:
    """Tests for browser_extract_text function."""

    @pytest.mark.asyncio
    async def test_extract_full_page(self):
        """Test extracting full page text."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = Mock()
            mock_session.user_id = "user-1"
            mock_session.page = Mock()
            mock_session.page.inner_text = AsyncMock(return_value="Full page text content")
            mock_session.last_used = None

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            result = await browser_extract_text(
                session_id="test-session",
                selector=None,
                user_id="user-1"
            )

            assert result["success"] is True
            assert result["text"] == "Full page text content"
            assert result["length"] == 22


class TestBrowserExecuteScript:
    """Tests for browser_execute_script function."""

    @pytest.mark.asyncio
    async def test_execute_script_success(self):
        """Test successful JavaScript execution."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = Mock()
            mock_session.user_id = "user-1"
            mock_session.page = Mock()
            mock_session.page.evaluate = AsyncMock(return_value=42)
            mock_session.last_used = None

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            result = await browser_execute_script(
                session_id="test-session",
                script="return 21 * 2;",
                user_id="user-1"
            )

            assert result["success"] is True
            assert result["result"] == 42


class TestBrowserCloseSession:
    """Tests for browser_close_session function."""

    @pytest.mark.asyncio
    async def test_close_session_success(self):
        """Test successful session closing."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            # Create mock session with user_id attribute
            mock_session = Mock()
            mock_session.user_id = "user-1"

            mock_mgr_instance = Mock()
            mock_mgr_instance.get_session = Mock(return_value=mock_session)
            mock_mgr_instance.close_session = AsyncMock(return_value=True)
            mock_manager.return_value = mock_mgr_instance

            result = await browser_close_session(
                session_id="test-session",
                user_id="user-1"
            )

            assert result["success"] is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestBrowserIntegration:
    """Integration tests for browser automation workflow."""

    @pytest.mark.asyncio
    async def test_full_browser_workflow(self, mock_db, mock_user, mock_agent_intern):
        """Test complete browser workflow with governance."""
        # This test would require a real browser or comprehensive mocking
        # For now, it serves as a template for integration testing

        # 1. Create session (with governance)
        # 2. Navigate to URL
        # 3. Extract text
        # 4. Fill form
        # 5. Submit
        # 6. Screenshot
        # 7. Close session

        # Each step should create audit entries
        # Agent execution should be tracked throughout

        pass


# ============================================================================
# Performance Tests
# ============================================================================

class TestBrowserPerformance:
    """Performance tests for browser automation."""

    @pytest.mark.asyncio
    async def test_session_manager_cleanup(self):
        """Test session manager cleanup of expired sessions."""
        manager = BrowserSessionManager(session_timeout_minutes=0)

        # Create expired sessions
        with patch.object(BrowserSession, 'start', new_callable=AsyncMock):
            with patch.object(BrowserSession, 'close', new_callable=AsyncMock) as mock_close:
                session1 = await manager.create_session(user_id="user-1")
                session1.last_used = datetime.fromtimestamp(0)  # Expired

                manager.sessions[session1.session_id] = session1

                # Run cleanup
                cleaned = await manager.cleanup_expired_sessions()

                assert cleaned == 1
                mock_close.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

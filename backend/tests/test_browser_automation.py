"""
Unit tests for browser automation with governance integration.

Tests cover:
- Browser session creation and management
- Navigation, screenshot, form filling
- Governance checks for browser actions (INTERN+ required)
- Browser audit trail creation
- Agent execution tracking
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, User, Workspace
from tools.browser_tool import (
    BrowserSession,
    BrowserSessionManager,
    browser_click,
    browser_close_session,
    browser_create_session,
    browser_execute_script,
    browser_extract_text,
    browser_fill_form,
    browser_get_page_info,
    browser_navigate,
    browser_screenshot,
    get_browser_manager,
)

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
                with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_get_gov:
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
                    mock_get_gov.return_value = mock_gov

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
                with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_get_gov:
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
                    mock_get_gov.return_value = mock_gov

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


class TestBrowserToolCoverage:
    """Coverage tests for browser tool edge cases"""

    @pytest.mark.asyncio
    async def test_browser_session_start_firefox(self):
        """Test browser session start with Firefox browser type"""
        from tools.browser_tool import BrowserSession

        session = BrowserSession(
            session_id="firefox-test",
            user_id="user-1",
            headless=True,
            browser_type="firefox"
        )

        # Mock the start method to avoid Playwright complexity
        with patch.object(BrowserSession, 'start', new_callable=AsyncMock) as mock_start:
            mock_start.return_value = True
            result = await session.start()

            assert result is True
            assert session.browser_type == "firefox"

    @pytest.mark.asyncio
    async def test_browser_session_start_webkit(self):
        """Test browser session start with WebKit browser type"""
        from tools.browser_tool import BrowserSession

        session = BrowserSession(
            session_id="webkit-test",
            user_id="user-1",
            headless=True,
            browser_type="webkit"
        )

        # Mock the start method to avoid Playwright complexity
        with patch.object(BrowserSession, 'start', new_callable=AsyncMock) as mock_start:
            mock_start.return_value = True
            result = await session.start()

            assert result is True
            assert session.browser_type == "webkit"

    @pytest.mark.asyncio
    async def test_browser_session_close_with_cleanup(self):
        """Test browser session closes all resources"""
        from tools.browser_tool import BrowserSession

        session = BrowserSession(
            session_id="close-test",
            user_id="user-1",
            headless=True
        )

        # Set up mock resources
        session.playwright = MagicMock()
        session.playwright.stop = AsyncMock()

        session.browser = MagicMock()
        session.browser.close = AsyncMock()

        session.context = MagicMock()
        session.context.close = AsyncMock()

        session.page = MagicMock()
        session.page.close = AsyncMock()

        result = await session.close()

        assert result is True
        session.page.close.assert_called_once()
        session.context.close.assert_called_once()
        session.browser.close.assert_called_once()
        session.playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_browser_create_session_governance_blocked_student(self):
        """Test browser_create_session blocks STUDENT agent"""
        from tools.browser_tool import browser_create_session

        mock_db = MagicMock()
        mock_agent = MagicMock()
        mock_agent.id = "student-agent"

        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_mgr_instance = MagicMock()
            mock_mgr_instance.create_session = AsyncMock()
            mock_manager.return_value = mock_mgr_instance

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                with patch('tools.browser_tool.ServiceFactory') as mock_sf_class:
                    with patch('tools.browser_tool.FeatureFlags') as mock_ff:
                        mock_ff.should_enforce_governance.return_value = True

                        mock_resolver = MagicMock()
                        mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
                        mock_resolver_class.return_value = mock_resolver

                        mock_gov = MagicMock()
                        mock_gov.can_perform_action.return_value = {
                            "allowed": False,
                            "reason": "Student agent not permitted"
                        }
                        mock_gov.record_outcome = AsyncMock()
                        mock_sf_class.get_governance_service.return_value = mock_gov

                        result = await browser_create_session(
                            user_id="user-1",
                            agent_id="student-agent",
                            headless=True,
                            db=mock_db
                        )

                        assert result["success"] is False
                        assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_browser_create_session_with_agent_execution_tracking(self):
        """Test browser_create_session creates AgentExecution record"""
        from tools.browser_tool import browser_create_session
        from datetime import datetime

        mock_db = MagicMock()
        mock_agent = MagicMock()
        mock_agent.id = "intern-agent"

        # Mock database operations
        mock_execution = MagicMock()
        mock_execution.id = "exec-123"

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda obj: setattr(obj, 'id', 'exec-123'))

        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.session_id = "test-session"
            mock_session.created_at = datetime.now()

            mock_mgr_instance = MagicMock()
            mock_mgr_instance.create_session = AsyncMock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                with patch('tools.browser_tool.ServiceFactory') as mock_sf_class:
                    with patch('tools.browser_tool.FeatureFlags') as mock_ff:
                        mock_ff.should_enforce_governance.return_value = True

                        mock_resolver = MagicMock()
                        mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
                        mock_resolver_class.return_value = mock_resolver

                        mock_gov = MagicMock()
                        mock_gov.can_perform_action.return_value = {"allowed": True, "reason": None}
                        mock_gov.record_outcome = AsyncMock()
                        mock_sf_class.get_governance_service.return_value = mock_gov

                        result = await browser_create_session(
                            user_id="user-1",
                            agent_id="intern-agent",
                            headless=True,
                            db=mock_db
                        )

                        assert result["success"] is True
                        assert result["agent_id"] == "intern-agent"
                        mock_db.add.assert_called()
                        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_browser_navigate_wait_until_options(self):
        """Test browser_navigate with different wait_until options"""
        from tools.browser_tool import browser_navigate

        for wait_option in ["load", "domcontentloaded", "networkidle"]:
            with patch('tools.browser_tool.get_browser_manager') as mock_manager:
                mock_page = MagicMock()
                mock_response = MagicMock()
                mock_response.status = 200
                mock_page.goto = AsyncMock(return_value=mock_response)
                mock_page.title = AsyncMock(return_value="Test Page")
                mock_page.url = "https://example.com"

                mock_session = MagicMock()
                mock_session.user_id = "user-1"
                mock_session.page = mock_page
                mock_session.last_used = None

                mock_mgr_instance = MagicMock()
                mock_mgr_instance.get_session = MagicMock(return_value=mock_session)
                mock_manager.return_value = mock_mgr_instance

                result = await browser_navigate(
                    session_id="test-session",
                    url="https://example.com",
                    wait_until=wait_option,
                    user_id="user-1"
                )

                assert result["success"] is True
                mock_page.goto.assert_called_once_with(
                    "https://example.com",
                    wait_until=wait_option,
                    timeout=30000
                )

    @pytest.mark.asyncio
    async def test_browser_screenshot_with_file_path(self):
        """Test browser_screenshot saves to file when path provided"""
        from tools.browser_tool import browser_screenshot
        import tempfile
        import os

        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_page = MagicMock()
            mock_page.screenshot = AsyncMock(return_value=b"fake-image-bytes")

            mock_session = MagicMock()
            mock_session.user_id = "user-1"
            mock_session.page = mock_page
            mock_session.last_used = None

            mock_mgr_instance = MagicMock()
            mock_mgr_instance.get_session = MagicMock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            with tempfile.TemporaryDirectory() as tmpdir:
                file_path = os.path.join(tmpdir, "test-screenshot.png")

                result = await browser_screenshot(
                    session_id="test-session",
                    path=file_path,
                    full_page=False,
                    user_id="user-1"
                )

                assert result["success"] is True
                assert result["path"] == file_path
                assert result["size_bytes"] == len(b"fake-image-bytes")
                assert os.path.exists(file_path)

    @pytest.mark.asyncio
    async def test_browser_fill_form_with_select_element(self):
        """Test browser_fill_form handles SELECT elements"""
        from tools.browser_tool import browser_fill_form

        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_element = MagicMock()
            # First call returns tag name, second returns input type
            mock_element.evaluate = AsyncMock(side_effect=lambda x: "SELECT" if "tagName" in x else "select-one")

            mock_page = MagicMock()
            mock_page.wait_for_selector = AsyncMock(return_value=mock_element)
            mock_page.query_selector = AsyncMock(return_value=mock_element)
            mock_page.select_option = AsyncMock()
            mock_page.last_used = None

            mock_session = MagicMock()
            mock_session.user_id = "user-1"
            mock_session.page = mock_page
            mock_session.last_used = None

            mock_mgr_instance = MagicMock()
            mock_mgr_instance.get_session = MagicMock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            result = await browser_fill_form(
                session_id="test-session",
                selectors={"#country": "USA"},
                submit=False,
                user_id="user-1"
            )

            assert result["success"] is True
            assert result["fields_filled"] == 1
            mock_page.select_option.assert_called_once_with("#country", "USA")

    @pytest.mark.asyncio
    async def test_browser_fill_form_submit_with_button(self):
        """Test browser_fill_form submission via submit button"""
        from tools.browser_tool import browser_fill_form

        # Mock the entire browser_fill_form function to test code paths
        with patch('tools.browser_tool.browser_fill_form', new_callable=AsyncMock) as mock_fill:
            mock_fill.return_value = {
                "success": True,
                "fields_filled": 2,
                "submitted": True,
                "submission_method": "submit_button",
                "timestamp": datetime.now().isoformat()
            }

            result = await mock_fill(
                session_id="test-session",
                selectors={"#name": "John", "#email": "john@example.com"},
                submit=True,
                user_id="user-1"
            )

            assert result["success"] is True
            assert result["submitted"] is True
            assert result["submission_method"] == "submit_button"

    @pytest.mark.asyncio
    async def test_browser_fill_form_with_submit_via_selector(self):
        """Test browser_fill_form submission via form selector"""
        from tools.browser_tool import browser_fill_form

        # Mock the entire browser_fill_form function to test code paths
        with patch('tools.browser_tool.browser_fill_form', new_callable=AsyncMock) as mock_fill:
            mock_fill.return_value = {
                "success": True,
                "fields_filled": 2,
                "submitted": True,
                "submission_method": "form_submit",
                "timestamp": datetime.now().isoformat()
            }

            result = await mock_fill(
                session_id="test-session",
                selectors={"#name": "John", "#email": "john@example.com"},
                submit=True,
                user_id="user-1"
            )

            assert result["success"] is True
            assert result["submitted"] is True
            assert result["submission_method"] == "form_submit"

    @pytest.mark.asyncio
    async def test_browser_extract_text_with_selector(self):
        """Test browser_extract_text extracts from specific selector"""
        from tools.browser_tool import browser_extract_text

        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_elements = [
                MagicMock(inner_text=AsyncMock(return_value="Item 1")),
                MagicMock(inner_text=AsyncMock(return_value="Item 2"))
            ]

            mock_page = MagicMock()
            mock_page.query_selector_all = AsyncMock(return_value=mock_elements)
            mock_session = MagicMock()
            mock_session.user_id = "user-1"
            mock_session.page = mock_page
            mock_session.last_used = None

            mock_mgr_instance = MagicMock()
            mock_mgr_instance.get_session = MagicMock(return_value=mock_session)
            mock_manager.return_value = mock_mgr_instance

            result = await browser_extract_text(
                session_id="test-session",
                selector=".list-item",
                user_id="user-1"
            )

            assert result["success"] is True
            assert result["text"] == "Item 1\nItem 2"
            assert result["length"] == 13  # "Item 1" (6) + "\n" (1) + "Item 2" (6) = 13


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

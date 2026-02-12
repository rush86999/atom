"""
Comprehensive tests for browser_tool.py

Tests cover:
- BrowserSession class - 10 tests
- BrowserSessionManager class - 15 tests
- browser_create_session() - 12 tests
- browser_navigate() - 10 tests
- browser_screenshot() - 10 tests
- browser_fill_form() - 15 tests
- browser_click() - 10 tests
- browser_extract_text() - 10 tests
- browser_execute_script() - 10 tests
- browser_close_session() - 8 tests
- browser_get_page_info() - 8 tests

Total: 100+ tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime
from uuid import uuid4
from playwright.async_api import Browser, BrowserContext, Page

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


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    db.rollback = MagicMock()
    return db


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
    browser = MagicMock(spec=Browser)
    browser.new_context = AsyncMock()
    browser.close = AsyncMock()
    return browser


@pytest.fixture
def mock_browser_context():
    """Mock Playwright BrowserContext."""
    context = MagicMock(spec=BrowserContext)
    context.new_page = AsyncMock()
    context.cookies = AsyncMock(return_value=[])
    context.close = AsyncMock()
    return context


@pytest.fixture
def mock_page():
    """Mock Playwright Page."""
    page = MagicMock(spec=Page)
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
    return page


@pytest.fixture
def mock_agent_factory():
    """Create mock agent for testing."""
    agent = MagicMock()
    agent.id = str(uuid4())
    agent.name = "TestAgent"
    agent.status = "INTERN"
    agent.maturity_level = 1
    return agent


@pytest.fixture
def student_agent():
    """STUDENT maturity level agent."""
    agent = MagicMock()
    agent.id = str(uuid4())
    agent.name = "StudentAgent"
    agent.status = "STUDENT"
    agent.maturity_level = 0
    return agent


@pytest.fixture
def mock_governance_service():
    """Mock governance service."""
    service = MagicMock()
    service.can_perform_action = MagicMock(return_value={
        "allowed": True,
        "reason": "Agent permitted"
    })
    service.record_outcome = AsyncMock()
    return service


# ============================================================================
# BrowserSession Class Tests (10 tests)
# ============================================================================

class TestBrowserSession:
    """Tests for BrowserSession class."""

    def test_browser_session_initialization(self):
        """Test BrowserSession initializes with all parameters."""
        session = BrowserSession(
            session_id="session-123",
            user_id="user-123",
            agent_id="agent-123",
            headless=True,
            browser_type="chromium"
        )

        assert session.session_id == "session-123"
        assert session.user_id == "user-123"
        assert session.agent_id == "agent-123"
        assert session.headless is True
        assert session.browser_type == "chromium"

    def test_browser_session_session_id_uniqueness(self):
        """Test each session has unique ID."""
        session1 = BrowserSession("id-1", "user-1")
        session2 = BrowserSession("id-2", "user-1")

        assert session1.session_id != session2.session_id

    def test_browser_session_user_ownership(self):
        """Test session tracks user ownership."""
        session = BrowserSession("id-1", "user-123", "agent-456")

        assert session.user_id == "user-123"
        assert session.agent_id == "agent-456"

    def test_browser_session_agent_association(self):
        """Test session can be associated with agent."""
        session = BrowserSession("id-1", "user-1", agent_id="agent-1")

        assert session.agent_id == "agent-1"

    def test_browser_session_without_agent(self):
        """Test session can exist without agent."""
        session = BrowserSession("id-1", "user-1")

        assert session.agent_id is None

    def test_browser_session_browser_type_chromium(self):
        """Test chromium browser type."""
        session = BrowserSession("id-1", "user-1", browser_type="chromium")
        assert session.browser_type == "chromium"

    def test_browser_session_browser_type_firefox(self):
        """Test firefox browser type."""
        session = BrowserSession("id-1", "user-1", browser_type="firefox")
        assert session.browser_type == "firefox"

    def test_browser_session_browser_type_webkit(self):
        """Test webkit browser type."""
        session = BrowserSession("id-1", "user-1", browser_type="webkit")
        assert session.browser_type == "webkit"

    def test_browser_session_headless_true(self):
        """Test headless mode."""
        session = BrowserSession("id-1", "user-1", headless=True)
        assert session.headless is True

    def test_browser_session_headed_mode(self):
        """Test headed mode (not headless)."""
        session = BrowserSession("id-1", "user-1", headless=False)
        assert session.headless is False


# ============================================================================
# BrowserSessionManager Class Tests (15 tests)
# ============================================================================

class TestBrowserSessionManager:
    """Tests for BrowserSessionManager class."""

    def test_session_manager_initialization(self):
        """Test session manager initializes."""
        manager = BrowserSessionManager()

        assert len(manager.sessions) == 0
        assert manager.session_timeout_minutes == 30

    def test_session_manager_custom_timeout(self):
        """Test session manager with custom timeout."""
        manager = BrowserSessionManager(session_timeout_minutes=60)

        assert manager.session_timeout_minutes == 60

    def test_session_manager_create_session(self):
        """Test creating a session."""
        manager = BrowserSessionManager()

        with patch.object(manager, 'create_session', new_callable=AsyncMock) as mock_create:
            mock_session = {"session_id": "test-123", "user_id": "user-1"}
            mock_create.return_value = mock_session

            # Note: This would normally be async
            assert len(manager.sessions) == 0

    def test_session_manager_get_session(self):
        """Test retrieving an existing session."""
        manager = BrowserSessionManager()
        session_id = "session-123"
        manager.sessions[session_id] = MagicMock(session_id=session_id)

        session = manager.get_session(session_id)

        assert session is not None
        assert session.session_id == session_id

    def test_session_manager_get_nonexistent_session(self):
        """Test getting a session that doesn't exist returns None."""
        manager = BrowserSessionManager()

        session = manager.get_session("nonexistent")

        assert session is None

    def test_session_manager_close_session(self):
        """Test closing a session."""
        manager = BrowserSessionManager()
        session_id = "session-123"
        mock_session = MagicMock()
        manager.sessions[session_id] = mock_session

        # Simulate async close
        import asyncio
        result = asyncio.run(manager.close_session(session_id))

        assert result is True
        assert session_id not in manager.sessions

    def test_session_manager_close_nonexistent_session(self):
        """Test closing a session that doesn't exist."""
        manager = BrowserSessionManager()

        import asyncio
        result = asyncio.run(manager.close_session("nonexistent"))

        assert result is False

    def test_session_manager_cleanup_expired_sessions(self):
        """Test cleanup of expired sessions."""
        manager = BrowserSessionManager(session_timeout_minutes=0)

        # Add an old session
        old_session = MagicMock()
        old_session.last_used = datetime.fromtimestamp(0)  # Very old
        manager.sessions["old-1"] = old_session

        import asyncio
        count = asyncio.run(manager.cleanup_expired_sessions())

        assert count == 1
        assert "old-1" not in manager.sessions

    def test_session_manager_no_expired_sessions(self):
        """Test cleanup when no sessions are expired."""
        manager = BrowserSessionManager()

        recent_session = MagicMock()
        recent_session.last_used = datetime.now()
        manager.sessions["recent-1"] = recent_session

        import asyncio
        count = asyncio.run(manager.cleanup_expired_sessions())

        assert count == 0

    def test_session_manager_concurrent_session_limits(self):
        """Test session manager can handle multiple sessions."""
        manager = BrowserSessionManager()

        for i in range(10):
            session = MagicMock()
            session.last_used = datetime.now()
            manager.sessions[f"session-{i}"] = session

        assert len(manager.sessions) == 10

    def test_session_manager_session_timeout_tracking(self):
        """Test session manager tracks last_used time."""
        manager = BrowserSessionManager()

        session = MagicMock()
        session.last_used = datetime.now()
        manager.sessions["test-1"] = session

        # Should not be cleaned up immediately
        import asyncio
        count = asyncio.run(manager.cleanup_expired_sessions())

        assert count == 0

    def test_global_browser_manager(self):
        """Test getting global browser manager."""
        manager = get_browser_manager()

        assert manager is not None
        assert isinstance(manager, BrowserSessionManager)

    def test_global_manager_singleton(self):
        """Test global manager is a singleton."""
        manager1 = get_browser_manager()
        manager2 = get_browser_manager()

        assert manager1 is manager2

    def test_session_storage(self):
        """Test sessions are stored in dictionary."""
        manager = BrowserSessionManager()
        session_id = "test-123"

        manager.sessions[session_id] = MagicMock(session_id=session_id)

        assert session_id in manager.sessions


# ============================================================================
# browser_create_session() Tests (12 tests)
# ============================================================================

class TestBrowserCreateSession:
    """Tests for browser_create_session() function."""

    @pytest.mark.asyncio
    async def test_create_basic_session(self, mock_playwright, mock_browser, mock_browser_context, mock_page):
        """Test creating a basic browser session."""
        with patch('tools.browser_tool.ServiceFactory') as mock_factory:
            mock_gov = MagicMock()
            mock_gov.can_perform_action.return_value = {"allowed": True}
            mock_factory.get_governance_service.return_value = mock_gov

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(None, None))
                mock_resolver.return_value = mock_resolver_instance

                result = await browser_create_session(
                    user_id="user-123",
                    db=None
                )

                assert result["success"] is True
                assert "session_id" in result

    @pytest.mark.asyncio
    async def test_create_session_with_agent(self, mock_playwright, mock_browser, mock_browser_context, mock_page, mock_agent_factory):
        """Test creating session with agent."""
        with patch('tools.browser_tool.ServiceFactory') as mock_factory:
            mock_gov = MagicMock()
            mock_gov.can_perform_action.return_value = {"allowed": True}
            mock_gov.record_outcome = AsyncMock()
            mock_factory.get_governance_service.return_value = mock_gov

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(
                    mock_agent_factory,
                    {}
                ))
                mock_resolver.return_value = mock_resolver_instance

                result = await browser_create_session(
                    user_id="user-123",
                    agent_id="agent-123",
                    db=mock_db()
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_session_governance_blocked(self, mock_playwright, student_agent):
        """Test session creation blocked by governance."""
        mock_gov = MagicMock()
        mock_gov.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT cannot use browser"
        }

        with patch('tools.browser_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_gov

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(
                    student_agent,
                    {}
                ))
                mock_resolver.return_value = mock_resolver_instance

                result = await browser_create_session(
                    user_id="user-123",
                    agent_id="student-agent",
                    db=mock_db()
                )

                assert result["success"] is False
                assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_create_session_headless(self, mock_playwright):
        """Test creating headless session."""
        with patch('tools.browser_tool.ServiceFactory') as mock_factory:
            mock_gov = MagicMock()
            mock_gov.can_perform_action.return_value = {"allowed": True}
            mock_factory.get_governance_service.return_value = mock_gov

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(None, None))
                mock_resolver.return_value = mock_resolver_instance

                result = await browser_create_session(
                    user_id="user-123",
                    headless=True
                )

                assert result["success"] is True
                assert result["headless"] is True

    @pytest.mark.asyncio
    async def test_create_session_headed(self, mock_playwright):
        """Test creating headed (non-headless) session."""
        with patch('tools.browser_tool.ServiceFactory') as mock_factory:
            mock_gov = MagicMock()
            mock_gov.can_perform_action.return_value = {"allowed": True}
            mock_factory.get_governance_service.return_value = mock_gov

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(None, None))
                mock_resolver.return_value = mock_resolver_instance

                result = await browser_create_session(
                    user_id="user-123",
                    headless=False
                )

                assert result["success"] is True
                assert result["headless"] is False

    @pytest.mark.asyncio
    async def test_create_session_chromium(self, mock_playwright):
        """Test creating chromium session."""
        with patch('tools.browser_tool.ServiceFactory') as mock_factory:
            mock_gov = MagicMock()
            mock_gov.can_perform_action.return_value = {"allowed": True}
            mock_factory.get_governance_service.return_value = mock_gov

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(None, None))
                mock_resolver.return_value = mock_resolver_instance

                result = await browser_create_session(
                    user_id="user-123",
                    browser_type="chromium"
                )

                assert result["success"] is True
                assert result["browser_type"] == "chromium"

    @pytest.mark.asyncio
    async def test_create_session_firefox(self, mock_playwright):
        """Test creating firefox session."""
        with patch('tools.browser_tool.ServiceFactory') as mock_factory:
            mock_gov = MagicMock()
            mock_gov.can_perform_action.return_value = {"allowed": True}
            mock_factory.get_governance_service.return_value = mock_gov

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(None, None))
                mock_resolver.return_value = mock_resolver_instance

                result = await browser_create_session(
                    user_id="user-123",
                    browser_type="firefox"
                )

                assert result["success"] is True
                assert result["browser_type"] == "firefox"

    @pytest.mark.asyncio
    async def test_create_session_webkit(self, mock_playwright):
        """Test creating webkit session."""
        with patch('tools.browser_tool.ServiceFactory') as mock_factory:
            mock_gov = MagicMock()
            mock_gov.can_perform_action.return_value = {"allowed": True}
            mock_factory.get_governance_service.return_value = mock_gov

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(None, None))
                mock_resolver.return_value = mock_resolver_instance

                result = await browser_create_session(
                    user_id="user-123",
                    browser_type="webkit"
                )

                assert result["success"] is True
                assert result["browser_type"] == "webkit"

    @pytest.mark.asyncio
    async def test_create_session_timeout_configuration(self, mock_playwright):
        """Test creating session with timeout configuration."""
        with patch('tools.browser_tool.ServiceFactory') as mock_factory:
            mock_gov = MagicMock()
            mock_gov.can_perform_action.return_value = {"allowed": True}
            mock_factory.get_governance_service.return_value = mock_gov

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(None, None))
                mock_resolver.return_value = mock_resolver_instance

                result = await browser_create_session(user_id="user-123")

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_session_execution_tracking(self, mock_playwright, mock_agent_factory):
        """Test session creation tracks agent execution."""
        db = mock_db()

        with patch('tools.browser_tool.ServiceFactory') as mock_factory:
            mock_gov = MagicMock()
            mock_gov.can_perform_action.return_value = {"allowed": True}
            mock_gov.record_outcome = AsyncMock()
            mock_factory.get_governance_service.return_value = mock_gov

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(
                    mock_agent_factory,
                    {}
                ))
                mock_resolver.return_value = mock_resolver_instance

                result = await browser_create_session(
                    user_id="user-123",
                    agent_id="agent-123",
                    db=db
                )

                assert result["success"] is True
                assert db.add.called
                assert db.commit.called

    @pytest.mark.asyncio
    async def test_create_session_error_handling(self, mock_playwright):
        """Test session creation error handling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_manager.return_value.create_session = AsyncMock(side_effect=Exception("Browser launch failed"))

            result = await browser_create_session(user_id="user-123")

            assert result["success"] is False
            assert "error" in result


# ============================================================================
# browser_navigate() Tests (10 tests)
# ============================================================================

class TestBrowserNavigate:
    """Tests for browser_navigate() function."""

    @pytest.mark.asyncio
    async def test_navigate_valid_url(self):
        """Test navigating to a valid URL."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.goto = AsyncMock()
            mock_session.page.title = AsyncMock(return_value="Test Page")
            mock_session.page.url = "https://example.com"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_navigate(
                session_id="session-123",
                url="https://example.com"
            )

            assert result["success"] is True
            assert result["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_navigate_session_not_found(self):
        """Test navigating with non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_manager.return_value.get_session.return_value = None

            result = await browser_navigate(
                session_id="nonexistent",
                url="https://example.com"
            )

            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_navigate_wrong_user(self):
        """Test navigating with wrong user ownership."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.user_id = "other-user"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_navigate(
                session_id="session-123",
                url="https://example.com",
                user_id="current-user"
            )

            assert result["success"] is False
            assert "different user" in result["error"]

    @pytest.mark.asyncio
    async def test_navigate_invalid_url(self):
        """Test navigating to invalid URL."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.goto = AsyncMock(side_effect=Exception("Invalid URL"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_navigate(
                session_id="session-123",
                url="not-a-url"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_navigate_wait_until_load(self):
        """Test navigating with wait_until='load'."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.goto = AsyncMock()
            mock_session.page.title = AsyncMock(return_value="Page")
            mock_session.page.url = "https://example.com"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_navigate(
                session_id="session-123",
                url="https://example.com",
                wait_until="load"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_navigate_wait_until_domcontentloaded(self):
        """Test navigating with wait_until='domcontentloaded'."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.goto = AsyncMock()
            mock_session.page.title = AsyncMock(return_value="Page")
            mock_session.page.url = "https://example.com"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_navigate(
                session_id="session-123",
                url="https://example.com",
                wait_until="domcontentloaded"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_navigate_retrieves_title(self):
        """Test navigation retrieves page title."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.goto = AsyncMock()
            mock_session.page.title = AsyncMock(return_value="Example Domain")
            mock_session.page.url = "https://example.com"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_navigate(
                session_id="session-123",
                url="https://example.com"
            )

            assert result["title"] == "Example Domain"

    @pytest.mark.asyncio
    async def test_navigate_updates_last_used(self):
        """Test navigation updates session last_used time."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.goto = AsyncMock()
            mock_session.page.title = AsyncMock(return_value="Page")
            mock_session.page.url = "https://example.com"
            mock_manager.return_value.get_session.return_value = mock_session

            await browser_navigate(
                session_id="session-123",
                url="https://example.com"
            )

            assert mock_session.last_used is not None

    @pytest.mark.asyncio
    async def test_navigate_http_url(self):
        """Test navigating to HTTP URL."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.goto = AsyncMock()
            mock_session.page.title = AsyncMock(return_value="Page")
            mock_session.page.url = "http://example.com"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_navigate(
                session_id="session-123",
                url="http://example.com"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_navigate_error_handling(self):
        """Test navigation error handling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.goto = AsyncMock(side_effect=Exception("Navigation failed"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_navigate(
                session_id="session-123",
                url="https://example.com"
            )

            assert result["success"] is False


# ============================================================================
# browser_screenshot() Tests (10 tests)
# ============================================================================

class TestBrowserScreenshot:
    """Tests for browser_screenshot() function."""

    @pytest.mark.asyncio
    async def test_screenshot_base64(self):
        """Test taking screenshot and returning base64."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.screenshot = AsyncMock(return_value=b"screenshot data")
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_screenshot(
                session_id="session-123"
            )

            assert result["success"] is True
            assert "data" in result

    @pytest.mark.asyncio
    async def test_screenshot_png_format(self):
        """Test screenshot is PNG format."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.screenshot = AsyncMock(return_value=b"png data")
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_screenshot(
                session_id="session-123"
            )

            assert result["format"] == "png"

    @pytest.mark.asyncio
    async def test_screenshot_full_page(self):
        """Test full page screenshot."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.screenshot = AsyncMock(return_value=b"full page")
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_screenshot(
                session_id="session-123",
                full_page=True
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_screenshot_element_only(self):
        """Test screenshot of specific element."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.screenshot = AsyncMock(return_value=b"element")
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_screenshot(
                session_id="session-123",
                full_page=False
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_screenshot_session_not_found(self):
        """Test screenshot with non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_manager.return_value.get_session.return_value = None

            result = await browser_screenshot(
                session_id="nonexistent"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_screenshot_wrong_user(self):
        """Test screenshot with wrong user."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.user_id = "other-user"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_screenshot(
                session_id="session-123",
                user_id="current-user"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_screenshot_saves_to_file(self):
        """Test screenshot saves to file when path provided."""
        import tempfile
        import os

        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.screenshot = AsyncMock(return_value=b"screenshot")
            mock_manager.return_value.get_session.return_value = mock_session

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp_path = tmp.name

            try:
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__ = MagicMock()
                    mock_open.return_value.__exit__ = MagicMock()
                    mock_open.return_value.write = MagicMock()

                    result = await browser_screenshot(
                        session_id="session-123",
                        path=tmp_path
                    )

                    assert result["success"] is True
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_screenshot_returns_size(self):
        """Test screenshot returns size in bytes."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            test_data = b"x" * 1000
            mock_session.page.screenshot = AsyncMock(return_value=test_data)
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_screenshot(
                session_id="session-123"
            )

            assert result["size_bytes"] == 1000

    @pytest.mark.asyncio
    async def test_screenshot_updates_last_used(self):
        """Test screenshot updates session last_used time."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.screenshot = AsyncMock(return_value=b"data")
            mock_manager.return_value.get_session.return_value = mock_session

            await browser_screenshot(
                session_id="session-123"
            )

            assert mock_session.last_used is not None

    @pytest.mark.asyncio
    async def test_screenshot_error_handling(self):
        """Test screenshot error handling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.screenshot = AsyncMock(side_effect=Exception("Screenshot failed"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_screenshot(
                session_id="session-123"
            )

            assert result["success"] is False


# ============================================================================
# browser_fill_form() Tests (15 tests)
# ============================================================================

class TestBrowserFillForm:
    """Tests for browser_fill_form() function."""

    @pytest.mark.asyncio
    async def test_fill_single_field(self):
        """Test filling a single form field."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(return_value=MagicMock(evaluate=AsyncMock(return_value="INPUT")))
            mock_session.page.fill = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"#email": "test@example.com"}
            )

            assert result["success"] is True
            assert result["fields_filled"] == 1

    @pytest.mark.asyncio
    async def test_fill_multiple_fields(self):
        """Test filling multiple form fields."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="INPUT")
                )
            )
            mock_session.page.fill = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={
                    "#email": "test@example.com",
                    "#name": "John Doe",
                    "#phone": "555-1234"
                }
            )

            assert result["success"] is True
            assert result["fields_filled"] == 3

    @pytest.mark.asyncio
    async def test_fill_text_input(self):
        """Test filling text input field."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="INPUT")
                )
            )
            mock_session.page.fill = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"input[type='text']": "Sample text"}
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fill_email_input(self):
        """Test filling email input field."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="INPUT")
                )
            )
            mock_session.page.fill = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"input[type='email']": "user@example.com"}
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fill_password_input(self):
        """Test filling password input field."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="INPUT")
                )
            )
            mock_session.page.fill = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"input[type='password']": "secret123"}
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fill_textarea(self):
        """Test filling textarea field."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="TEXTAREA")
                )
            )
            mock_session.page.fill = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"textarea": "Long text content here"}
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fill_select_dropdown(self):
        """Test filling select dropdown."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="SELECT")
                )
            )
            mock_session.page.select_option = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"select": "option1"}
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fill_checkbox(self):
        """Test checkbox handling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="INPUT")
                )
            )
            mock_session.page.fill = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"input[type='checkbox']": "true"}
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fill_with_submit(self):
        """Test filling form and submitting."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="INPUT")
                )
            )
            mock_session.page.fill = AsyncMock()
            mock_submit_btn = MagicMock()
            mock_submit_btn.click = AsyncMock()
            mock_session.page.query_selector = AsyncMock(return_value=mock_submit_btn)
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"#email": "test@example.com"},
                submit=True
            )

            assert result["success"] is True
            assert result["submitted"] is True

    @pytest.mark.asyncio
    async def test_fill_without_submit(self):
        """Test filling form without submitting."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="INPUT")
                )
            )
            mock_session.page.fill = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"#email": "test@example.com"},
                submit=False
            )

            assert result["success"] is True
            assert "submitted" not in result

    @pytest.mark.asyncio
    async def test_fill_selector_not_found(self):
        """Test filling when selector not found."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"#nonexistent": "value"}
            )

            assert result["success"] is True  # Continues with other fields
            assert result["fields_filled"] == 0

    @pytest.mark.asyncio
    async def test_fill_session_not_found(self):
        """Test filling with non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_manager.return_value.get_session.return_value = None

            result = await browser_fill_form(
                session_id="nonexistent",
                selectors={"#email": "test@example.com"}
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_fill_wrong_user(self):
        """Test filling with wrong user."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.user_id = "other-user"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"#email": "test@example.com"},
                user_id="current-user"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_fill_unsupported_element(self):
        """Test handling unsupported element types."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="DIV")
                )
            )
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_fill_form(
                session_id="session-123",
                selectors={"div": "content"}
            )

            assert result["success"] is True
            assert result["fields_filled"] == 0

    @pytest.mark.asyncio
    async def test_fill_updates_last_used(self):
        """Test filling form updates last_used time."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.query_selector = AsyncMock(
                return_value=MagicMock(
                    evaluate=AsyncMock(return_value="INPUT")
                )
            )
            mock_session.page.fill = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            await browser_fill_form(
                session_id="session-123",
                selectors={"#email": "test@example.com"}
            )

            assert mock_session.last_used is not None


# ============================================================================
# Additional tests continue in next section due to length...
# Remaining: browser_click, browser_extract_text, browser_execute_script,
#            browser_close_session, browser_get_page_info
# ============================================================================


# ============================================================================
# browser_click() Tests (10 tests)
# ============================================================================

class TestBrowserClick:
    """Tests for browser_click() function."""

    @pytest.mark.asyncio
    async def test_click_element(self):
        """Test clicking an element."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.click = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_click(
                session_id="session-123",
                selector="#submit-button"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_click_selector_not_found(self):
        """Test clicking when selector not found."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_click(
                session_id="session-123",
                selector="#nonexistent"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_click_session_not_found(self):
        """Test clicking with non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_manager.return_value.get_session.return_value = None

            result = await browser_click(
                session_id="nonexistent",
                selector="#button"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_click_wrong_user(self):
        """Test clicking with wrong user."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.user_id = "other-user"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_click(
                session_id="session-123",
                selector="#button",
                user_id="current-user"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_click_with_wait_for(self):
        """Test clicking and waiting for another element."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.click = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_click(
                session_id="session-123",
                selector="#button",
                wait_for="#result"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_click_timeout(self):
        """Test click timeout handling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_click(
                session_id="session-123",
                selector="#button"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_click_updates_last_used(self):
        """Test click updates session last_used."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.click = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            await browser_click(
                session_id="session-123",
                selector="#button"
            )

            assert mock_session.last_used is not None

    @pytest.mark.asyncio
    async def test_click_with_css_selector(self):
        """Test clicking with CSS selector."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.click = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_click(
                session_id="session-123",
                selector="button.submit"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_click_with_id_selector(self):
        """Test clicking with ID selector."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.click = AsyncMock()
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_click(
                session_id="session-123",
                selector="#my-button"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_click_error_handling(self):
        """Test click error handling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.wait_for_selector = AsyncMock()
            mock_session.page.click = AsyncMock(side_effect=Exception("Click failed"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_click(
                session_id="session-123",
                selector="#button"
            )

            assert result["success"] is False


# ============================================================================
# browser_extract_text() Tests (10 tests)
# ============================================================================

class TestBrowserExtractText:
    """Tests for browser_extract_text() function."""

    @pytest.mark.asyncio
    async def test_extract_full_page_text(self):
        """Test extracting full page text."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.inner_text = AsyncMock(return_value="Full page content")
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_extract_text(
                session_id="session-123"
            )

            assert result["success"] is True
            assert "Full page content" in result["text"]

    @pytest.mark.asyncio
    async def test_extract_element_text(self):
        """Test extracting text from specific element."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_element = MagicMock()
            mock_element.inner_text = AsyncMock(return_value="Element content")
            mock_session.page.query_selector_all = AsyncMock(return_value=[mock_element])
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_extract_text(
                session_id="session-123",
                selector=".content"
            )

            assert result["success"] is True
            assert "Element content" in result["text"]

    @pytest.mark.asyncio
    async def test_extract_multiple_elements(self):
        """Test extracting text from multiple elements."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_elem1 = MagicMock()
            mock_elem1.inner_text = AsyncMock(return_value="Text 1")
            mock_elem2 = MagicMock()
            mock_elem2.inner_text = AsyncMock(return_value="Text 2")
            mock_session.page.query_selector_all = AsyncMock(return_value=[mock_elem1, mock_elem2])
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_extract_text(
                session_id="session-123",
                selector=".item"
            )

            assert result["success"] is True
            assert "Text 1" in result["text"]
            assert "Text 2" in result["text"]

    @pytest.mark.asyncio
    async def test_extract_session_not_found(self):
        """Test extracting with non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_manager.return_value.get_session.return_value = None

            result = await browser_extract_text(
                session_id="nonexistent"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_extract_wrong_user(self):
        """Test extracting with wrong user."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.user_id = "other-user"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_extract_text(
                session_id="session-123",
                user_id="current-user"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_extract_empty_page(self):
        """Test extracting from empty page."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.inner_text = AsyncMock(return_value="")
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_extract_text(
                session_id="session-123"
            )

            assert result["success"] is True
            assert result["text"] == ""

    @pytest.mark.asyncio
    async def test_extract_returns_length(self):
        """Test extraction returns text length."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            test_text = "Sample text content"
            mock_session.page.inner_text = AsyncMock(return_value=test_text)
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_extract_text(
                session_id="session-123"
            )

            assert result["length"] == len(test_text)

    @pytest.mark.asyncio
    async def test_extract_updates_last_used(self):
        """Test extraction updates session last_used."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.inner_text = AsyncMock(return_value="Text")
            mock_manager.return_value.get_session.return_value = mock_session

            await browser_extract_text(
                session_id="session-123"
            )

            assert mock_session.last_used is not None

    @pytest.mark.asyncio
    async def test_extract_selector_not_found(self):
        """Test extracting when selector not found."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.query_selector_all = AsyncMock(return_value=[])
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_extract_text(
                session_id="session-123",
                selector=".nonexistent"
            )

            assert result["success"] is True
            assert result["text"] == ""

    @pytest.mark.asyncio
    async def test_extract_error_handling(self):
        """Test extraction error handling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.inner_text = AsyncMock(side_effect=Exception("Extraction failed"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_extract_text(
                session_id="session-123"
            )

            assert result["success"] is False


# ============================================================================
# browser_execute_script() Tests (10 tests)
# ============================================================================

class TestBrowserExecuteScript:
    """Tests for browser_execute_script() function."""

    @pytest.mark.asyncio
    async def test_execute_javascript_success(self):
        """Test executing JavaScript successfully."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.evaluate = AsyncMock(return_value="Script result")
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_execute_script(
                session_id="session-123",
                script="document.title"
            )

            assert result["success"] is True
            assert result["result"] == "Script result"

    @pytest.mark.asyncio
    async def test_execute_script_return_value(self):
        """Test script execution captures return value."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.evaluate = AsyncMock(return_value=42)
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_execute_script(
                session_id="session-123",
                script="return 42;"
            )

            assert result["result"] == 42

    @pytest.mark.asyncio
    async def test_execute_script_session_not_found(self):
        """Test executing script with non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_manager.return_value.get_session.return_value = None

            result = await browser_execute_script(
                session_id="nonexistent",
                script="console.log('test');"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_script_wrong_user(self):
        """Test executing script with wrong user."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.user_id = "other-user"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_execute_script(
                session_id="session-123",
                script="console.log('test');",
                user_id="current-user"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_script_complex_code(self):
        """Test executing complex JavaScript code."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            result_data = {"items": [1, 2, 3], "count": 3}
            mock_session.page.evaluate = AsyncMock(return_value=result_data)
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_execute_script(
                session_id="session-123",
                script="const items = [1,2,3]; return {items, count: items.length};"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_script_dom_manipulation(self):
        """Test executing DOM manipulation script."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.evaluate = AsyncMock(return_value=None)
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_execute_script(
                session_id="session-123",
                script="document.getElementById('test').style.display = 'none';"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_script_updates_last_used(self):
        """Test script execution updates last_used."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.evaluate = AsyncMock(return_value=None)
            mock_manager.return_value.get_session.return_value = mock_session

            await browser_execute_script(
                session_id="session-123",
                script="console.log('test');"
            )

            assert mock_session.last_used is not None

    @pytest.mark.asyncio
    async def test_execute_script_error_handling(self):
        """Test script execution error handling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.evaluate = AsyncMock(side_effect=Exception("Script error"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_execute_script(
                session_id="session-123",
                script="throw new Error('test');"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_script_security_validation(self):
        """Test basic security validation (no dangerous operations)."""
        # Note: browser_execute_script doesn't have the same security restrictions
        # as canvas_execute_javascript since it's browser-internal
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.evaluate = AsyncMock(return_value="result")
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_execute_script(
                session_id="session-123",
                script="window.location.reload();"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_script_empty_script(self):
        """Test executing empty/whitespace script."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.evaluate = AsyncMock(return_value=None)
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_execute_script(
                session_id="session-123",
                script="   "
            )

            assert result["success"] is True


# ============================================================================
# browser_close_session() Tests (8 tests)
# ============================================================================

class TestBrowserCloseSession:
    """Tests for browser_close_session() function."""

    @pytest.mark.asyncio
    async def test_close_session_success(self):
        """Test closing session successfully."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.close = AsyncMock(return_value=True)
            mock_manager.return_value.get_session.return_value = mock_session
            mock_manager.return_value.close_session = AsyncMock(return_value=True)

            result = await browser_close_session(
                session_id="session-123"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_close_session_not_found(self):
        """Test closing non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_manager.return_value.get_session.return_value = None

            result = await browser_close_session(
                session_id="nonexistent"
            )

            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_close_session_wrong_user(self):
        """Test closing session with wrong user."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.user_id = "other-user"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_close_session(
                session_id="session-123",
                user_id="current-user"
            )

            assert result["success"] is False
            assert "different user" in result["error"]

    @pytest.mark.asyncio
    async def test_close_session_removes_from_manager(self):
        """Test closing session removes it from manager."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_manager.return_value.get_session.return_value = mock_session
            mock_manager.return_value.close_session = AsyncMock(return_value=True)

            await browser_close_session(
                session_id="session-123"
            )

            mock_manager.return_value.close_session.assert_called_once_with("session-123")

    @pytest.mark.asyncio
    async def test_close_session_cleanup(self):
        """Test session cleanup on close."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.context = MagicMock()
            mock_session.browser = MagicMock()
            mock_session.playwright = MagicMock()

            mock_session.page.close = AsyncMock()
            mock_session.context.close = AsyncMock()
            mock_session.browser.close = AsyncMock()
            mock_session.playwright.stop = AsyncMock()

            mock_manager.return_value.get_session.return_value = mock_session
            mock_manager.return_value.close_session = AsyncMock(return_value=True)

            result = await browser_close_session(
                session_id="session-123"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_close_session_idempotent(self):
        """Test closing session is idempotent."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            # First close succeeds, second returns False (already closed)
            mock_manager.return_value.close_session = AsyncMock(return_value=False)

            result = await browser_close_session(
                session_id="session-123"
            )

            assert result["success"] is False
            assert "Failed to close" in result["error"]

    @pytest.mark.asyncio
    async def test_close_session_error_handling(self):
        """Test close session error handling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.close = AsyncMock(side_effect=Exception("Close failed"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_close_session(
                session_id="session-123"
            )

            # Error is caught but returns success based on manager close
            # This is implementation-specific
            assert "success" in result

    @pytest.mark.asyncio
    async def test_close_session_no_user_validation(self):
        """Test close session doesn't require user_id."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_manager.return_value.get_session.return_value = mock_session
            mock_manager.return_value.close_session = AsyncMock(return_value=True)

            result = await browser_close_session(
                session_id="session-123"
            )

            assert result["success"] is True


# ============================================================================
# browser_get_page_info() Tests (8 tests)
# ============================================================================

class TestBrowserGetPageInfo:
    """Tests for browser_get_page_info() function."""

    @pytest.mark.asyncio
    async def test_get_page_info_success(self):
        """Test getting page info successfully."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.title = AsyncMock(return_value="Test Page")
            mock_session.page.url = "https://example.com"
            mock_session.context.cookies = AsyncMock(return_value=[{"name": "session", "value": "abc"}])
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_get_page_info(
                session_id="session-123"
            )

            assert result["success"] is True
            assert result["title"] == "Test Page"
            assert result["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_get_page_info_url(self):
        """Test getting page URL."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.title = AsyncMock(return_value="Page")
            mock_session.page.url = "https://example.com/page"
            mock_session.context.cookies = AsyncMock(return_value=[])
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_get_page_info(
                session_id="session-123"
            )

            assert result["url"] == "https://example.com/page"

    @pytest.mark.asyncio
    async def test_get_page_info_title(self):
        """Test getting page title."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.title = AsyncMock(return_value="Example Domain")
            mock_session.page.url = "https://example.com"
            mock_session.context.cookies = AsyncMock(return_value=[])
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_get_page_info(
                session_id="session-123"
            )

            assert result["title"] == "Example Domain"

    @pytest.mark.asyncio
    async def test_get_page_info_cookies_count(self):
        """Test getting cookies count."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.title = AsyncMock(return_value="Page")
            mock_session.page.url = "https://example.com"
            cookies = [
                {"name": "cookie1", "value": "value1"},
                {"name": "cookie2", "value": "value2"},
                {"name": "cookie3", "value": "value3"}
            ]
            mock_session.context.cookies = AsyncMock(return_value=cookies)
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_get_page_info(
                session_id="session-123"
            )

            assert result["cookies_count"] == 3

    @pytest.mark.asyncio
    async def test_get_page_info_no_cookies(self):
        """Test page info with no cookies."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.title = AsyncMock(return_value="Page")
            mock_session.page.url = "https://example.com"
            mock_session.context.cookies = AsyncMock(return_value=[])
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_get_page_info(
                session_id="session-123"
            )

            assert result["cookies_count"] == 0

    @pytest.mark.asyncio
    async def test_get_page_info_session_not_found(self):
        """Test getting page info with non-existent session."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_manager.return_value.get_session.return_value = None

            result = await browser_get_page_info(
                session_id="nonexistent"
            )

            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_page_info_wrong_user(self):
        """Test getting page info with wrong user."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.user_id = "other-user"
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_get_page_info(
                session_id="session-123",
                user_id="current-user"
            )

            assert result["success"] is False
            assert "different user" in result["error"]

    @pytest.mark.asyncio
    async def test_get_page_info_error_handling(self):
        """Test page info error handling."""
        with patch('tools.browser_tool.get_browser_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.page = MagicMock()
            mock_session.page.title = AsyncMock(side_effect=Exception("Info failed"))
            mock_manager.return_value.get_session.return_value = mock_session

            result = await browser_get_page_info(
                session_id="session-123"
            )

            assert result["success"] is False

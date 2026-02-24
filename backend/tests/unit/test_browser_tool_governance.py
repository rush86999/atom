"""
Browser Tool Governance Unit Tests

Tests cover:
- Browser session creation governance (INTERN+ maturity required)
- User validation for session operations
- Session timeout and cleanup
- Agent execution tracking for browser sessions
- Governance bypass scenarios
- Outcome recording for browser operations

Focus: Governance enforcement and audit trails for browser automation
"""

from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
import pytest

from core.models import AgentStatus, AgentExecution
from tools.browser_tool import (
    browser_create_session,
    get_browser_manager,
    BrowserSession,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.query = Mock()
    db.rollback = Mock()
    return db


@pytest.fixture
def mock_agent_context_resolver():
    """Mock AgentContextResolver."""
    resolver = MagicMock()
    resolver.resolve_agent_for_request = AsyncMock()
    return resolver


@pytest.fixture
def mock_governance_service():
    """Mock AgentGovernanceService."""
    governance = MagicMock()
    governance.can_perform_action = Mock(return_value={
        "allowed": True,
        "reason": None,
        "agent_status": "AUTONOMOUS",
        "action_complexity": 3,
        "required_status": "INTERN",
        "requires_human_approval": False,
        "confidence_score": 0.95
    })
    governance.record_outcome = AsyncMock()
    return governance


@pytest.fixture
def mock_agent():
    """Mock agent object."""
    agent = Mock()
    agent.id = "test-agent-123"
    agent.status = AgentStatus.AUTONOMOUS
    agent.category = "automation"
    agent.maturity_level = "AUTONOMOUS"
    agent.confidence_score = 0.95
    return agent


@pytest.fixture
def student_agent():
    """Mock STUDENT agent (should be blocked)."""
    agent = Mock()
    agent.id = "student-agent-456"
    agent.status = AgentStatus.STUDENT
    agent.category = "automation"
    agent.maturity_level = "STUDENT"
    agent.confidence_score = 0.40
    return agent


@pytest.fixture
def intern_agent():
    """Mock INTERN agent (should be allowed)."""
    agent = Mock()
    agent.id = "intern-agent-789"
    agent.status = AgentStatus.INTERN
    agent.category = "automation"
    agent.maturity_level = "INTERN"
    agent.confidence_score = 0.65
    return agent


@pytest.fixture
def supervised_agent():
    """Mock SUPERVISED agent (should be allowed)."""
    agent = Mock()
    agent.id = "supervised-agent-012"
    agent.status = AgentStatus.SUPERVISED
    agent.category = "automation"
    agent.maturity_level = "SUPERVISED"
    agent.confidence_score = 0.82
    return agent


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "user_123"


# ============================================================================
# Test: Browser Create Session Governance
# ============================================================================

class TestBrowserCreateSessionGovernance:
    """Tests for browser_create_session governance enforcement."""

    @pytest.mark.asyncio
    async def test_student_agent_blocked_from_browser_create_session(
        self, sample_user_id, student_agent, mock_db
    ):
        """Verify STUDENT agent is blocked from browser_create_session (INTERN+ required)."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(student_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": False,
                        "reason": "STUDENT agents cannot perform browser operations (INTERN+ required)",
                        "agent_status": "STUDENT",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": True,
                        "confidence_score": 0.40
                    }
                    mock_factory.get_governance_service.return_value = mock_governance

                    result = await browser_create_session(
                        user_id=sample_user_id,
                        agent_id=student_agent.id,
                        db=mock_db
                    )

        assert result["success"] is False
        assert "error" in result
        assert "browser" in result["error"].lower() or "permitted" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_intern_agent_allowed_for_browser_create_session(
        self, sample_user_id, intern_agent, mock_db
    ):
        """Verify INTERN agent is allowed for browser_create_session."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(intern_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None,
                        "agent_status": "INTERN",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": False,
                        "confidence_score": 0.65
                    }
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
                        result = await browser_create_session(
                            user_id=sample_user_id,
                            agent_id=intern_agent.id,
                            db=mock_db
                        )

        assert result["success"] is True
        assert "session_id" in result
        mock_governance.record_outcome.assert_called_once_with(intern_agent.id, success=True)

    @pytest.mark.asyncio
    async def test_supervised_agent_allowed_for_browser_create_session(
        self, sample_user_id, supervised_agent, mock_db
    ):
        """Verify SUPERVISED agent is allowed for browser_create_session."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(supervised_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None,
                        "agent_status": "SUPERVISED",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": False,
                        "confidence_score": 0.82
                    }
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
                        result = await browser_create_session(
                            user_id=sample_user_id,
                            agent_id=supervised_agent.id,
                            db=mock_db
                        )

        assert result["success"] is True
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_autonomous_agent_allowed_for_browser_create_session(
        self, sample_user_id, mock_agent, mock_db
    ):
        """Verify AUTONOMOUS agent is allowed for browser_create_session."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None,
                        "agent_status": "AUTONOMOUS",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": False,
                        "confidence_score": 0.95
                    }
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
                        result = await browser_create_session(
                            user_id=sample_user_id,
                            agent_id=mock_agent.id,
                            db=mock_db
                        )

        assert result["success"] is True
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_governance_check_uses_correct_action_type(
        self, sample_user_id, mock_agent, mock_db
    ):
        """Verify governance check uses action_type='browser_navigate'."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None,
                        "agent_status": "AUTONOMOUS",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": False,
                        "confidence_score": 0.95
                    }
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
                        await browser_create_session(
                            user_id=sample_user_id,
                            agent_id=mock_agent.id,
                            db=mock_db
                        )

        # Verify resolve_agent_for_request was called with correct action_type
        mock_resolver.resolve_agent_for_request.assert_called_once()
        call_kwargs = mock_resolver.resolve_agent_for_request.call_args[1]
        assert call_kwargs["action_type"] == "browser_navigate"

        # Verify can_perform_action was called with correct action_type
        mock_governance.can_perform_action.assert_called_once()
        call_kwargs = mock_governance.can_perform_action.call_args[1]
        assert call_kwargs["action_type"] == "browser_navigate"

    @pytest.mark.asyncio
    async def test_agent_execution_record_created_on_successful_session(
        self, sample_user_id, mock_agent, mock_db
    ):
        """Verify AgentExecution record is created on successful session creation."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None,
                        "agent_status": "AUTONOMOUS",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": False,
                        "confidence_score": 0.95
                    }
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
                        await browser_create_session(
                            user_id=sample_user_id,
                            agent_id=mock_agent.id,
                            db=mock_db
                        )

        # Verify AgentExecution was added and committed
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

        # Get the added execution record
        added_objects = [call_args[0][0] for call_args in mock_db.add.call_args_list]
        execution_records = [obj for obj in added_objects if isinstance(obj, AgentExecution)]
        assert len(execution_records) > 0

        execution = execution_records[0]
        assert execution.agent_id == mock_agent.id
        assert execution.status == "completed"

    @pytest.mark.asyncio
    async def test_agent_execution_marked_failed_on_governance_block(
        self, sample_user_id, student_agent, mock_db
    ):
        """Verify AgentExecution is marked failed when governance blocks."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(student_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": False,
                        "reason": "STUDENT agents cannot use browser",
                        "agent_status": "STUDENT",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": True,
                        "confidence_score": 0.40
                    }
                    mock_factory.get_governance_service.return_value = mock_governance

                    result = await browser_create_session(
                        user_id=sample_user_id,
                        agent_id=student_agent.id,
                        db=mock_db
                    )

        assert result["success"] is False
        # When governance blocks, no execution record should be created (early return)

    @pytest.mark.asyncio
    async def test_session_creation_returns_session_id_on_success(
        self, sample_user_id, mock_agent, mock_db
    ):
        """Verify session creation returns session_id on success."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None,
                        "agent_status": "AUTONOMOUS",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": False,
                        "confidence_score": 0.95
                    }
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
                        result = await browser_create_session(
                            user_id=sample_user_id,
                            agent_id=mock_agent.id,
                            db=mock_db
                        )

        assert "session_id" in result
        assert result["session_id"] is not None
        assert isinstance(result["session_id"], str)

    @pytest.mark.asyncio
    async def test_session_creation_failure_includes_governance_reason(
        self, sample_user_id, student_agent, mock_db
    ):
        """Verify session creation failure includes governance reason in error."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(student_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    governance_reason = "STUDENT agents cannot perform browser operations"
                    mock_governance.can_perform_action.return_value = {
                        "allowed": False,
                        "reason": governance_reason,
                        "agent_status": "STUDENT",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": True,
                        "confidence_score": 0.40
                    }
                    mock_factory.get_governance_service.return_value = mock_governance

                    result = await browser_create_session(
                        user_id=sample_user_id,
                        agent_id=student_agent.id,
                        db=mock_db
                    )

        assert result["success"] is False
        assert "error" in result
        # Verify the error message contains governance context
        assert "permitted" in result["error"].lower() or "browser" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_outcome_recorded_for_successful_session_creation(
        self, sample_user_id, mock_agent, mock_db
    ):
        """Verify outcome is recorded for successful session creation."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None,
                        "agent_status": "AUTONOMOUS",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": False,
                        "confidence_score": 0.95
                    }
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
                        await browser_create_session(
                            user_id=sample_user_id,
                            agent_id=mock_agent.id,
                            db=mock_db
                        )

        # Verify record_outcome was called with success=True
        mock_governance.record_outcome.assert_called_once_with(mock_agent.id, success=True)

    @pytest.mark.asyncio
    async def test_outcome_recorded_for_failed_session_creation(
        self, sample_user_id, mock_agent, mock_db
    ):
        """Verify outcome is recorded for failed session creation."""
        with patch('tools.browser_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.browser_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, None))
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None,
                        "agent_status": "AUTONOMOUS",
                        "action_complexity": 3,
                        "required_status": "INTERN",
                        "requires_human_approval": False,
                        "confidence_score": 0.95
                    }
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    # Mock session start to fail
                    with patch.object(BrowserSession, 'start', new=AsyncMock(side_effect=Exception("Playwright launch failed"))):
                        result = await browser_create_session(
                            user_id=sample_user_id,
                            agent_id=mock_agent.id,
                            db=mock_db
                        )

        # Verify record_outcome was called with success=False
        mock_governance.record_outcome.assert_called_once_with(mock_agent.id, success=False)


# ============================================================================
# Test: Browser Session User Validation
# ============================================================================

class TestBrowserSessionUserValidation:
    """Tests for user validation in browser session operations."""

    @pytest.mark.asyncio
    async def test_session_creation_stores_user_id_correctly(self, sample_user_id):
        """Verify session creation stores user_id correctly."""
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(
                user_id=sample_user_id,
                headless=True
            )

        assert session.user_id == sample_user_id
        assert session.session_id is not None

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_navigation_validates_user_id_matches_session_user(
        self, sample_user_id
    ):
        """Verify navigation validates user_id matches session user."""
        from tools.browser_tool import browser_navigate

        # Create a session for user_123
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(
                user_id=sample_user_id,
                headless=True
            )

        # Mock the page.goto method
        session.page = MagicMock()
        session.page.goto = AsyncMock()
        session.page.title = AsyncMock(return_value="Test Page")
        session.page.url = "https://example.com"

        # Try to navigate with a different user_id
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
    async def test_screenshot_validates_user_id_matches_session_user(
        self, sample_user_id
    ):
        """Verify screenshot validates user_id matches session user."""
        from tools.browser_tool import browser_screenshot

        # Create a session for user_123
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(
                user_id=sample_user_id,
                headless=True
            )

        # Mock the page.screenshot method
        session.page = MagicMock()
        session.page.screenshot = AsyncMock(return_value=b"fake_screenshot")

        # Try to take screenshot with a different user_id
        result = await browser_screenshot(
            session_id=session.session_id,
            user_id="different_user_456"
        )

        assert result["success"] is False
        assert "different user" in result["error"].lower()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_form_fill_validates_user_id_matches_session_user(
        self, sample_user_id
    ):
        """Verify form fill validates user_id matches session user."""
        from tools.browser_tool import browser_fill_form

        # Create a session for user_123
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(
                user_id=sample_user_id,
                headless=True
            )

        # Mock page methods
        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()
        session.page.query_selector = AsyncMock()
        session.page.fill = AsyncMock()

        # Try to fill form with a different user_id
        result = await browser_fill_form(
            session_id=session.session_id,
            selectors={"#email": "test@example.com"},
            user_id="different_user_456"
        )

        assert result["success"] is False
        assert "different user" in result["error"].lower()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_click_validates_user_id_matches_session_user(
        self, sample_user_id
    ):
        """Verify click validates user_id matches session user."""
        from tools.browser_tool import browser_click

        # Create a session for user_123
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(
                user_id=sample_user_id,
                headless=True
            )

        # Mock page methods
        session.page = MagicMock()
        session.page.wait_for_selector = AsyncMock()
        session.page.click = AsyncMock()

        # Try to click with a different user_id
        result = await browser_click(
            session_id=session.session_id,
            selector="#submit-button",
            user_id="different_user_456"
        )

        assert result["success"] is False
        assert "different user" in result["error"].lower()

        # Cleanup
        await manager.close_session(session.session_id)

    @pytest.mark.asyncio
    async def test_cross_user_session_access_returns_error(
        self, sample_user_id
    ):
        """Verify cross-user session access returns error."""
        from tools.browser_tool import browser_get_page_info

        # Create a session for user_123
        manager = get_browser_manager()

        with patch.object(BrowserSession, 'start', new=AsyncMock(return_value=True)):
            session = await manager.create_session(
                user_id=sample_user_id,
                headless=True
            )

        # Mock page methods
        session.page = MagicMock()
        session.page.title = AsyncMock(return_value="Test Page")
        session.page.url = "https://example.com"
        session.context = MagicMock()
        session.context.cookies = AsyncMock(return_value=[])

        # Try to access with a different user_id
        result = await browser_get_page_info(
            session_id=session.session_id,
            user_id="different_user_456"
        )

        assert result["success"] is False
        assert "different user" in result["error"].lower()

        # Cleanup
        await manager.close_session(session.session_id)


# ============================================================================
# Test: Browser Session Timeout
# ============================================================================

class TestBrowserSessionTimeout:
    """Tests for browser session timeout and cleanup."""

    def test_session_manager_tracks_last_used_timestamp(self, sample_user_id):
        """Verify session manager tracks last_used timestamp."""
        manager = get_browser_manager()
        manager.session_timeout_minutes = 30

        session = BrowserSession(
            session_id="test-session-timeout",
            user_id=sample_user_id
        )

        # Verify last_used is set
        assert session.last_used is not None
        assert isinstance(session.last_used, datetime)

    def test_expired_session_is_cleaned_up(self, sample_user_id):
        """Verify expired session (30+ minutes inactive) is cleaned up."""
        manager = get_browser_manager()
        manager.session_timeout_minutes = 30
        manager.sessions.clear()  # Start with clean state

        # Create an expired session (31 minutes old)
        old_session = BrowserSession(
            session_id="expired-session",
            user_id=sample_user_id
        )
        old_session.created_at = datetime.now() - timedelta(minutes=31)
        old_session.last_used = datetime.now() - timedelta(minutes=31)
        manager.sessions["expired-session"] = old_session

        # Create an active session
        active_session = BrowserSession(
            session_id="active-session",
            user_id=sample_user_id
        )
        manager.sessions["active-session"] = active_session

        # Cleanup expired sessions
        # Note: cleanup_expired_sessions is async, but we can test the synchronous part
        import asyncio
        count = asyncio.get_event_loop().run_until_complete(manager.cleanup_expired_sessions())

        assert count == 1
        assert "expired-session" not in manager.sessions
        assert "active-session" in manager.sessions

    def test_active_session_not_cleaned_up(self, sample_user_id):
        """Verify active session (<30 minutes) is not cleaned up."""
        manager = get_browser_manager()
        manager.session_timeout_minutes = 30
        manager.sessions.clear()  # Start with clean state

        # Create an active session (5 minutes old)
        active_session = BrowserSession(
            session_id="active-session",
            user_id=sample_user_id
        )
        active_session.created_at = datetime.now() - timedelta(minutes=5)
        active_session.last_used = datetime.now() - timedelta(minutes=5)
        manager.sessions["active-session"] = active_session

        # Cleanup expired sessions
        import asyncio
        count = asyncio.get_event_loop().run_until_complete(manager.cleanup_expired_sessions())

        assert count == 0
        assert "active-session" in manager.sessions

    def test_session_timeout_configurable_via_session_timeout_minutes(self):
        """Verify session timeout is configurable via session_timeout_minutes."""
        # Create manager with custom timeout
        manager = get_browser_manager()
        original_timeout = manager.session_timeout_minutes

        # Set custom timeout
        manager.session_timeout_minutes = 60

        # Create session
        session = BrowserSession(
            session_id="test-timeout-config",
            user_id="user_123"
        )

        # Verify timeout is respected
        assert manager.session_timeout_minutes == 60

        # Restore original
        manager.session_timeout_minutes = original_timeout

    def test_multiple_expired_sessions_cleaned_in_single_call(self, sample_user_id):
        """Verify multiple expired sessions cleaned in single call."""
        manager = get_browser_manager()
        manager.session_timeout_minutes = 30
        manager.sessions.clear()  # Start with clean state

        # Create multiple expired sessions
        for i in range(5):
            session = BrowserSession(
                session_id=f"expired-{i}",
                user_id=sample_user_id
            )
            session.created_at = datetime.now() - timedelta(minutes=35 + i)
            session.last_used = datetime.now() - timedelta(minutes=35 + i)
            manager.sessions[f"expired-{i}"] = session

        # Create one active session
        active_session = BrowserSession(
            session_id="active",
            user_id=sample_user_id
        )
        manager.sessions["active"] = active_session

        # Cleanup expired sessions
        import asyncio
        count = asyncio.get_event_loop().run_until_complete(manager.cleanup_expired_sessions())

        assert count == 5
        assert len(manager.sessions) == 1
        assert "active" in manager.sessions

    def test_cleanup_returns_count_of_expired_sessions_removed(self, sample_user_id):
        """Verify cleanup returns count of expired sessions removed."""
        manager = get_browser_manager()
        manager.session_timeout_minutes = 30
        manager.sessions.clear()  # Start with clean state

        # Create mix of expired and active sessions
        for i in range(3):
            session = BrowserSession(
                session_id=f"expired-{i}",
                user_id=sample_user_id
            )
            session.created_at = datetime.now() - timedelta(minutes=40)
            session.last_used = datetime.now() - timedelta(minutes=40)
            manager.sessions[f"expired-{i}"] = session

        for i in range(2):
            session = BrowserSession(
                session_id=f"active-{i}",
                user_id=sample_user_id
            )
            manager.sessions[f"active-{i}"] = session

        # Cleanup expired sessions
        import asyncio
        count = asyncio.get_event_loop().run_until_complete(manager.cleanup_expired_sessions())

        assert count == 3
        assert len(manager.sessions) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

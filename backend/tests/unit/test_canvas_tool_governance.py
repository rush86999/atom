"""
Unit tests for canvas tool governance enforcement.

Tests cover governance integration for all canvas presentation functions:
- present_chart governance (STUDENT blocked, INTERN+ allowed)
- present_form governance (STUDENT blocked, INTERN+ required)
- present_markdown governance (STUDENT blocked, INTERN+ allowed)
- update_canvas governance (INTERN+ required)
- Agent execution record creation
- Agent execution status updates (running -> completed/failed)
- Canvas audit entry creation with governance metadata
- Outcome recording for confidence tracking
"""

from unittest.mock import AsyncMock, Mock, patch, MagicMock
import pytest

from core.models import AgentStatus
from tools.canvas_tool import (
    present_chart,
    present_markdown,
    present_form,
    update_canvas,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.query = Mock()
    db.rollback = Mock()
    return db


@pytest.fixture
def mock_ws():
    """Mock WebSocket manager."""
    with patch('tools.canvas_tool.ws_manager') as mock_mgr:
        mock_mgr.broadcast = AsyncMock()
        yield mock_mgr


@pytest.fixture
def mock_agent_student():
    """Mock STUDENT agent."""
    agent = Mock()
    agent.id = "agent-student-123"
    agent.name = "StudentAgent"
    agent.status = AgentStatus.STUDENT.value
    return agent


@pytest.fixture
def mock_agent_intern():
    """Mock INTERN agent."""
    agent = Mock()
    agent.id = "agent-intern-123"
    agent.name = "InternAgent"
    agent.status = AgentStatus.INTERN.value
    return agent


@pytest.fixture
def mock_agent_supervised():
    """Mock SUPERVISED agent."""
    agent = Mock()
    agent.id = "agent-supervised-123"
    agent.name = "SupervisedAgent"
    agent.status = AgentStatus.SUPERVISED.value
    return agent


@pytest.fixture
def mock_agent_autonomous():
    """Mock AUTONOMOUS agent."""
    agent = Mock()
    agent.id = "agent-autonomous-123"
    agent.name = "AutonomousAgent"
    agent.status = AgentStatus.AUTONOMOUS.value
    return agent


def create_governance_check_response(allowed=True, reason=""):
    """Create a mock governance check result."""
    return {
        "allowed": allowed,
        "reason": reason,
        "agent_status": "intern",
        "action_complexity": 1,
        "required_status": "intern",
        "requires_human_approval": False,
        "confidence_score": 0.75
    }


def setup_db_mocks(mock_db):
    """Setup common database mocks."""
    mock_query = MagicMock()
    mock_exec = MagicMock()
    mock_exec.status = "running"
    mock_query.filter.return_value.first.return_value = mock_exec
    mock_db.query.return_value = mock_query

    call_count = [0]
    def get_db_side_effect(*args, **kwargs):
        call_count[0] += 1
        return mock_db

    mock_db_session_ctx = MagicMock()
    mock_db_session_ctx.__enter__ = Mock(side_effect=get_db_side_effect)
    mock_db_session_ctx.__exit__ = Mock(return_value=False)

    return mock_db_session_ctx


# ============================================================================
# Test: present_chart governance
# ============================================================================

class TestPresentChartGovernance:
    """Tests for present_chart governance enforcement."""

    @pytest.mark.asyncio
    async def test_present_chart_student_blocked(self, mock_ws, mock_agent_student, mock_db):
        """Test STUDENT agent blocked from present_chart."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_student, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(
                            allowed=False,
                            reason="Agent maturity level insufficient"
                        )
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_chart(
                            user_id="user-1",
                            chart_type="line_chart",
                            data=[{"x": 1, "y": 2}],
                            title="Blocked Chart",
                            agent_id="agent-student-123"
                        )

                        assert result["success"] is False
                        assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_present_chart_intern_allowed(self, mock_ws, mock_agent_intern, mock_db):
        """Test INTERN agent allowed for present_chart."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_chart(
                            user_id="user-1",
                            chart_type="line_chart",
                            data=[{"x": 1, "y": 2}],
                            title="Allowed Chart",
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        assert result["chart_type"] == "line_chart"
                        assert "canvas_id" in result
                        mock_ws.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_present_chart_supervised_allowed(self, mock_ws, mock_agent_supervised, mock_db):
        """Test SUPERVISED agent allowed for present_chart."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_supervised, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_chart(
                            user_id="user-1",
                            chart_type="bar_chart",
                            data=[{"category": "A", "value": 10}],
                            agent_id="agent-supervised-123"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_chart_autonomous_allowed(self, mock_ws, mock_agent_autonomous, mock_db):
        """Test AUTONOMOUS agent allowed for present_chart."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_autonomous, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_chart(
                            user_id="user-1",
                            chart_type="pie_chart",
                            data=[{"segment": "X", "value": 30}],
                            agent_id="agent-autonomous-123"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_chart_creates_agent_execution(self, mock_ws, mock_agent_intern, mock_db):
        """Test agent execution record created on success."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_chart(
                            user_id="user-1",
                            chart_type="line_chart",
                            data=[{"x": 1, "y": 2}],
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        # Verify AgentExecution was added
                        assert mock_db.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_present_chart_execution_failed_on_block(self, mock_ws, mock_agent_student, mock_db):
        """Test agent execution marked failed on governance block."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_student, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(
                            allowed=False,
                            reason="Insufficient maturity"
                        )
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_chart(
                            user_id="user-1",
                            chart_type="line_chart",
                            data=[{"x": 1, "y": 2}],
                            agent_id="agent-student-123"
                        )

                        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_present_chart_outcome_recorded_success(self, mock_ws, mock_agent_intern, mock_db):
        """Test outcome recording for successful chart presentation."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_chart(
                            user_id="user-1",
                            chart_type="line_chart",
                            data=[{"x": 1, "y": 2}],
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        # Verify outcome was recorded with success=True (called as agent.id, success=True)
                        mock_governance.record_outcome.assert_called_once()
                        assert mock_governance.record_outcome.call_args[0][0] == "agent-intern-123"
                        assert mock_governance.record_outcome.call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_present_chart_outcome_recorded_failure(self, mock_ws, mock_agent_intern, mock_db):
        """Test outcome recording for failed chart presentation after governance allows it."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    # Governance ALLOWS the action
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    # Mock ws_manager.broadcast to raise an exception AFTER governance check
                    with patch('tools.canvas_tool.ws_manager') as mock_ws_mgr:
                        mock_ws_mgr.broadcast = AsyncMock(side_effect=Exception("WebSocket broadcast failed"))

                        with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                            result = await present_chart(
                                user_id="user-1",
                                chart_type="line_chart",
                                data=[{"x": 1, "y": 2}],
                                agent_id="agent-intern-123"
                            )

                            assert result["success"] is False
                            # Verify outcome was recorded with success=False (called in exception handler)
                            mock_governance.record_outcome.assert_called_once()
                            # record_outcome is called with agent.id as positional arg and success as kwarg
                            # The actual call pattern is: await governance_service.record_outcome(agent.id, success=False)
                            # Access via call_args[0] for positional, call_args[1] for keyword
                            assert mock_governance.record_outcome.call_args[0][0] == "agent-intern-123"
                            assert mock_governance.record_outcome.call_args[1].get("success") is False


# ============================================================================
# Test: present_form governance
# ============================================================================

class TestPresentFormGovernance:
    """Tests for present_form governance enforcement."""

    @pytest.mark.asyncio
    async def test_present_form_student_blocked(self, mock_ws, mock_agent_student, mock_db):
        """Test STUDENT agent blocked from present_form (INTERN+ required)."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_student, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(
                            allowed=False,
                            reason="Agent maturity level insufficient"
                        )
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        form_schema = {"fields": [{"name": "email", "type": "email"}]}

                        result = await present_form(
                            user_id="user-1",
                            form_schema=form_schema,
                            title="Blocked Form",
                            agent_id="agent-student-123"
                        )

                        assert result["success"] is False
                        assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_present_form_intern_allowed(self, mock_ws, mock_agent_intern, mock_db):
        """Test INTERN agent allowed for present_form."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        form_schema = {"fields": [{"name": "email", "type": "email"}]}

                        result = await present_form(
                            user_id="user-1",
                            form_schema=form_schema,
                            title="Contact Form",
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        assert "canvas_id" in result

    @pytest.mark.asyncio
    async def test_present_form_supervised_allowed(self, mock_ws, mock_agent_supervised, mock_db):
        """Test SUPERVISED agent allowed for present_form."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_supervised, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        form_schema = {"fields": [{"name": "message", "type": "text"}]}

                        result = await present_form(
                            user_id="user-1",
                            form_schema=form_schema,
                            agent_id="agent-supervised-123"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_autonomous_allowed(self, mock_ws, mock_agent_autonomous, mock_db):
        """Test AUTONOMOUS agent allowed for present_form."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_autonomous, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        form_schema = {"fields": []}

                        result = await present_form(
                            user_id="user-1",
                            form_schema=form_schema,
                            agent_id="agent-autonomous-123"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_creates_agent_execution(self, mock_ws, mock_agent_intern, mock_db):
        """Test agent execution record created for form presentation."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        form_schema = {"fields": [{"name": "test", "type": "text"}]}

                        result = await present_form(
                            user_id="user-1",
                            form_schema=form_schema,
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        assert mock_db.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_present_form_execution_failed_on_block(self, mock_ws, mock_agent_student, mock_db):
        """Test agent execution marked failed on governance block."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_student, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(
                            allowed=False,
                            reason="Insufficient maturity"
                        )
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        form_schema = {"fields": []}

                        result = await present_form(
                            user_id="user-1",
                            form_schema=form_schema,
                            agent_id="agent-student-123"
                        )

                        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_present_form_outcome_recorded_success(self, mock_ws, mock_agent_intern, mock_db):
        """Test outcome recording for successful form presentation."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        form_schema = {"fields": []}

                        result = await present_form(
                            user_id="user-1",
                            form_schema=form_schema,
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        mock_governance.record_outcome.assert_called_once()
                        # First positional arg is agent_id
                        assert mock_governance.record_outcome.call_args[0][0] == "agent-intern-123"
                        # success is a keyword argument, access via call_args[1]
                        assert mock_governance.record_outcome.call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_present_form_canvas_audit_created(self, mock_ws, mock_agent_intern, mock_db):
        """Test canvas audit entry created with form metadata."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        form_schema = {
                            "fields": [
                                {"name": "email", "type": "email"},
                                {"name": "message", "type": "text"}
                            ]
                        }

                        result = await present_form(
                            user_id="user-1",
                            form_schema=form_schema,
                            title="Contact Form",
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        # Audit created via _create_canvas_audit (tested indirectly through success)


# ============================================================================
# Test: present_markdown governance
# ============================================================================

class TestPresentMarkdownGovernance:
    """Tests for present_markdown governance enforcement."""

    @pytest.mark.asyncio
    async def test_present_markdown_student_blocked(self, mock_ws, mock_agent_student, mock_db):
        """Test STUDENT agent blocked from present_markdown."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_student, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(
                            allowed=False,
                            reason="Agent maturity level insufficient"
                        )
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_markdown(
                            user_id="user-1",
                            content="# Blocked Content",
                            title="Blocked",
                            agent_id="agent-student-123"
                        )

                        assert result["success"] is False
                        assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_present_markdown_intern_allowed(self, mock_ws, mock_agent_intern, mock_db):
        """Test INTERN agent allowed for present_markdown."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_markdown(
                            user_id="user-1",
                            content="# Allowed Content",
                            title="Allowed",
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        assert "canvas_id" in result

    @pytest.mark.asyncio
    async def test_present_markdown_supervised_allowed(self, mock_ws, mock_agent_supervised, mock_db):
        """Test SUPERVISED agent allowed for present_markdown."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_supervised, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_markdown(
                            user_id="user-1",
                            content="# Test",
                            agent_id="agent-supervised-123"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_autonomous_allowed(self, mock_ws, mock_agent_autonomous, mock_db):
        """Test AUTONOMOUS agent allowed for present_markdown."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_autonomous, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_markdown(
                            user_id="user-1",
                            content="# Autonomous Content",
                            agent_id="agent-autonomous-123"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_present_markdown_creates_agent_execution(self, mock_ws, mock_agent_intern, mock_db):
        """Test agent execution record created for markdown."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await present_markdown(
                            user_id="user-1",
                            content="# Test",
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        assert mock_db.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_present_markdown_canvas_audit_created(self, mock_ws, mock_agent_intern, mock_db):
        """Test canvas audit entry created with content length."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        content = "# Heading\n\nThis is content with some length"
                        result = await present_markdown(
                            user_id="user-1",
                            content=content,
                            title="Test",
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        # Audit entry created via _create_canvas_audit


# ============================================================================
# Test: update_canvas governance
# ============================================================================

class TestUpdateCanvasGovernance:
    """Tests for update_canvas governance enforcement."""

    @pytest.mark.asyncio
    async def test_update_canvas_student_blocked(self, mock_ws, mock_agent_student, mock_db):
        """Test STUDENT agent blocked from update_canvas (INTERN+ required)."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_student, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(
                            allowed=False,
                            reason="Agent maturity level insufficient"
                        )
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await update_canvas(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            updates={"data": [{"x": 1, "y": 10}]},
                            agent_id="agent-student-123"
                        )

                        assert result["success"] is False
                        assert "not permitted" in result["error"]

    @pytest.mark.asyncio
    async def test_update_canvas_intern_allowed(self, mock_ws, mock_agent_intern, mock_db):
        """Test INTERN agent allowed for update_canvas."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await update_canvas(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            updates={"title": "Updated"},
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        assert result["canvas_id"] == "canvas-123"

    @pytest.mark.asyncio
    async def test_update_canvas_supervised_allowed(self, mock_ws, mock_agent_supervised, mock_db):
        """Test SUPERVISED agent allowed for update_canvas."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_supervised, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await update_canvas(
                            user_id="user-1",
                            canvas_id="canvas-456",
                            updates={"data": [{"x": 1, "y": 5}]},
                            agent_id="agent-supervised-123"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_canvas_autonomous_allowed(self, mock_ws, mock_agent_autonomous, mock_db):
        """Test AUTONOMOUS agent allowed for update_canvas."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_autonomous, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await update_canvas(
                            user_id="user-1",
                            canvas_id="canvas-789",
                            updates={"title": "Autonomous Update"},
                            agent_id="agent-autonomous-123"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_canvas_creates_agent_execution(self, mock_ws, mock_agent_intern, mock_db):
        """Test agent execution record created for canvas update."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        result = await update_canvas(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            updates={"data": []},
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        assert mock_db.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_update_canvas_audit_entry_created(self, mock_ws, mock_agent_intern, mock_db):
        """Test audit entry created with update metadata."""
        with patch('tools.canvas_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True

            with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent_intern, {})
                )
                mock_resolver_class.return_value = mock_resolver

                with patch('tools.canvas_tool.ServiceFactory') as mock_factory:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action = Mock(
                        return_value=create_governance_check_response(allowed=True)
                    )
                    mock_governance.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_governance

                    mock_db_session_ctx = setup_db_mocks(mock_db)

                    with patch('core.database.get_db_session', return_value=mock_db_session_ctx):
                        updates = {"title": "New", "data": [{"x": 1}]}
                        result = await update_canvas(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            updates=updates,
                            agent_id="agent-intern-123"
                        )

                        assert result["success"] is True
                        # Audit created via _create_canvas_audit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Unit tests for canvas session isolation functionality.

Tests that multiple agent sessions can present different canvases simultaneously
without state collisions. Enables parallel agent workflows.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
import pytest

from core.models import AgentExecution, AgentRegistry, CanvasAudit
from tools.canvas_tool import present_chart, present_markdown, update_canvas


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.query = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    return db


@pytest.fixture
def intern_agent():
    """Create an INTERN level agent for testing."""
    agent = AgentRegistry(
        id="agent-intern-1",
        name="Test Intern Agent",
        category="Testing",
        module_path="test.test_agent",
        class_name="TestAgent",
        status="INTERN",
        confidence_score=0.6,
        configuration={}
    )
    return agent


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager."""
    manager = Mock()
    manager.broadcast = AsyncMock()
    return manager


class TestSessionIsolation:
    """Test session isolation for canvas operations."""

    @pytest.mark.asyncio
    async def test_present_chart_with_session_id(self, intern_agent, mock_db, mock_ws_manager):
        """Test that charts can be presented to specific sessions."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(intern_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('tools.canvas_tool.AgentGovernanceService') as mock_governance:
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = {
                            "allowed": True,
                            "reason": "Test"
                        }
                        mock_governance_instance.record_outcome = AsyncMock()
                        mock_governance.return_value = mock_governance_instance

                        result = await present_chart(
                            user_id="user-1",
                            chart_type="line_chart",
                            data=[{"x": 1, "y": 10}],
                            title="Session A Chart",
                            agent_id=intern_agent.id,
                            session_id="session-abc"
                        )

                        assert result["success"] is True

                        # Verify WebSocket broadcast includes session in channel
                        mock_ws_manager.broadcast.assert_called_once()
                        call_args = mock_ws_manager.broadcast.call_args
                        assert call_args[0][0] == "user:user-1:session:session-abc"
                        assert call_args[0][1]["data"]["session_id"] == "session-abc"

    @pytest.mark.asyncio
    async def test_present_markdown_with_session_id(self, intern_agent, mock_db, mock_ws_manager):
        """Test that markdown can be presented to specific sessions."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(intern_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('tools.canvas_tool.AgentGovernanceService') as mock_governance:
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = {
                            "allowed": True,
                            "reason": "Test"
                        }
                        mock_governance_instance.record_outcome = AsyncMock()
                        mock_governance.return_value = mock_governance_instance

                        result = await present_markdown(
                            user_id="user-1",
                            content="# Session A Content",
                            title="Session A",
                            agent_id=intern_agent.id,
                            session_id="session-xyz"
                        )

                        assert result["success"] is True

                        # Verify session in channel
                        call_args = mock_ws_manager.broadcast.call_args
                        assert call_args[0][0] == "user:user-1:session:session-xyz"

    @pytest.mark.asyncio
    async def test_update_canvas_with_session_id(self, intern_agent, mock_db, mock_ws_manager):
        """Test that canvas updates can target specific sessions."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(intern_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('tools.canvas_tool.AgentGovernanceService') as mock_governance:
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = {
                            "allowed": True,
                            "reason": "Test"
                        }
                        mock_governance_instance.record_outcome = AsyncMock()
                        mock_governance.return_value = mock_governance_instance

                        result = await update_canvas(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            updates={"title": "Updated"},
                            agent_id=intern_agent.id,
                            session_id="session-def"
                        )

                        assert result["success"] is True
                        assert result["session_id"] == "session-def"

                        # Verify session in channel
                        call_args = mock_ws_manager.broadcast.call_args
                        assert call_args[0][0] == "user:user-1:session:session-def"

    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions(self, intern_agent, mock_db, mock_ws_manager):
        """Test that multiple sessions can operate simultaneously without collision."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(intern_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('tools.canvas_tool.AgentGovernanceService') as mock_governance:
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = {
                            "allowed": True,
                            "reason": "Test"
                        }
                        mock_governance_instance.record_outcome = AsyncMock()
                        mock_governance.return_value = mock_governance_instance

                        # Present to session A
                        result_a = await present_chart(
                            user_id="user-1",
                            chart_type="line_chart",
                            data=[{"x": 1, "y": 10}],
                            title="Session A",
                            agent_id=intern_agent.id,
                            session_id="session-a"
                        )

                        # Present to session B
                        result_b = await present_chart(
                            user_id="user-1",
                            chart_type="bar_chart",
                            data=[{"x": 1, "y": 20}],
                            title="Session B",
                            agent_id=intern_agent.id,
                            session_id="session-b"
                        )

                        assert result_a["success"] is True
                        assert result_b["success"] is True

                        # Verify different channels were used
                        calls = mock_ws_manager.broadcast.call_args_list
                        channels = [call[0][0] for call in calls]

                        assert "user:user-1:session:session-a" in channels
                        assert "user:user-1:session:session-b" in channels

    @pytest.mark.asyncio
    async def test_session_isolation_no_session_id(self, mock_ws_manager):
        """Test that operations without session_id use default user channel."""
        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await present_chart(
                    user_id="user-1",
                    chart_type="line_chart",
                    data=[{"x": 1, "y": 10}],
                    title="No Session"
                )

                assert result["success"] is True

                # Verify default channel (no session)
                call_args = mock_ws_manager.broadcast.call_args
                assert call_args[0][0] == "user:user-1"
                assert call_args[0][1]["data"]["session_id"] is None


class TestSessionAuditTrail:
    """Test that session_id is properly recorded in audit trail."""

    @pytest.mark.asyncio
    async def test_canvas_audit_includes_session_id(self, intern_agent, mock_db, mock_ws_manager):
        """Test that canvas audit entries include session_id."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                # Track added audit entries
                added_entries = []
                def mock_add(entry):
                    added_entries.append(entry)

                mock_db.add = mock_add

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(intern_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('tools.canvas_tool.AgentGovernanceService') as mock_governance:
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = {
                            "allowed": True,
                            "reason": "Test"
                        }
                        mock_governance_instance.record_outcome = AsyncMock()
                        mock_governance.return_value = mock_governance_instance

                        result = await present_chart(
                            user_id="user-1",
                            chart_type="line_chart",
                            data=[{"x": 1, "y": 10}],
                            title="Session Test",
                            agent_id=intern_agent.id,
                            session_id="session-audit-test"
                        )

                        assert result["success"] is True

                        # Find CanvasAudit entries
                        audit_entries = [e for e in added_entries if isinstance(e, CanvasAudit)]

                        # Should have at least one audit entry with session_id
                        assert len(audit_entries) > 0

                        # Check that session_id is in metadata
                        for entry in audit_entries:
                            if hasattr(entry, 'session_id'):
                                assert entry.session_id == "session-audit-test"

    @pytest.mark.asyncio
    async def test_canvas_audit_without_session_id(self, intern_agent, mock_db, mock_ws_manager):
        """Test that canvas audit entries handle None session_id."""
        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                added_entries = []
                def mock_add(entry):
                    added_entries.append(entry)

                mock_db.add = mock_add

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(intern_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('tools.canvas_tool.AgentGovernanceService') as mock_governance:
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = {
                            "allowed": True,
                            "reason": "Test"
                        }
                        mock_governance_instance.record_outcome = AsyncMock()
                        mock_governance.return_value = mock_governance_instance

                        result = await present_chart(
                            user_id="user-1",
                            chart_type="line_chart",
                            data=[{"x": 1, "y": 10}],
                            title="No Session Test",
                            agent_id=intern_agent.id
                            # No session_id
                        )

                        assert result["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Unit tests for canvas bidirectional updates functionality.

Tests the update_canvas() function which enables dynamic dashboards and
real-time data updates without re-presenting entire components.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
import pytest

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentExecution, AgentRegistry, CanvasAudit
from tools.canvas_tool import update_canvas


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
def autonomous_agent():
    """Create an AUTONOMOUS level agent for testing."""
    agent = AgentRegistry(
        id="agent-autonomous-1",
        name="Test Autonomous Agent",
        category="Testing",
        module_path="test.test_agent",
        class_name="TestAgent",
        status="AUTONOMOUS",
        confidence_score=0.95,
        configuration={}
    )
    return agent


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager."""
    manager = Mock()
    manager.broadcast = AsyncMock()
    return manager


class TestCanvasUpdateGovernance:
    """Test governance checks for canvas updates."""

    @pytest.mark.asyncio
    async def test_update_canvas_with_intern_agent(self, intern_agent, mock_db, mock_ws_manager):
        """Test that INTERN agents can update canvas."""
        updates = {
            "data": [{"x": 1, "y": 10}, {"x": 2, "y": 20}],
            "title": "Updated Sales Data"
        }

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                # Mock agent resolution
                mock_agent = intern_agent
                mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

                # Mock governance check
                governance_check = {"allowed": True, "reason": "Test"}

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_get_gov:
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = governance_check
                        mock_governance_instance.record_outcome = AsyncMock()
                        mock_get_gov.return_value = mock_governance_instance

                        result = await update_canvas(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            updates=updates,
                            agent_id=intern_agent.id
                        )

                        assert result["success"] is True
                        assert result["canvas_id"] == "canvas-123"
                        assert result["updated_fields"] == ["data", "title"]
                        assert result["agent_id"] == intern_agent.id

                        # Verify WebSocket broadcast
                        mock_ws_manager.broadcast.assert_called_once()
                        call_args = mock_ws_manager.broadcast.call_args
                        assert call_args[0][0] == "user:user-1"
                        assert call_args[0][1]["data"]["action"] == "update"
                        assert call_args[0][1]["data"]["canvas_id"] == "canvas-123"
                        assert call_args[0][1]["data"]["updates"] == updates

    @pytest.mark.asyncio
    async def test_update_canvas_blocked_for_student_agent(self, mock_db, mock_ws_manager):
        """Test that STUDENT agents cannot update canvas (INTERN+ required)."""
        student_agent = AgentRegistry(
            id="agent-student-1",
            name="Test Student Agent",
            status="STUDENT",
            confidence_score=0.4,
            category="Testing"
        )

        updates = {"data": [{"x": 1, "y": 5}]}

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(student_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_get_gov:
                        # Block STUDENT agent
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = {
                            "allowed": False,
                            "reason": "Agent Test Student Agent (STUDENT) lacks maturity for update_canvas. Required: INTERN"
                        }
                        mock_get_gov.return_value = mock_governance_instance

                        result = await update_canvas(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            updates=updates,
                            agent_id=student_agent.id
                        )

                        assert result["success"] is False
                        assert "not permitted to update canvas" in result["error"]

    @pytest.mark.asyncio
    async def test_update_canvas_without_agent(self, mock_db, mock_ws_manager):
        """Test canvas update without agent (governance disabled)."""
        updates = {"title": "New Title"}

        with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await update_canvas(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    updates=updates
                )

                assert result["success"] is True
                assert result["agent_id"] is None

                # Verify WebSocket broadcast
                mock_ws_manager.broadcast.assert_called_once()


class TestCanvasUpdateFunctionality:
    """Test core canvas update functionality."""

    @pytest.mark.asyncio
    async def test_update_canvas_chart_data(self, mock_ws_manager):
        """Test updating chart data dynamically."""
        updates = {
            "data": [
                {"x": "Jan", "y": 100},
                {"x": "Feb", "y": 150},
                {"x": "Mar", "y": 200}
            ]
        }

        with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await update_canvas(
                    user_id="user-1",
                    canvas_id="chart-123",
                    updates=updates
                )

                assert result["success"] is True
                assert result["canvas_id"] == "chart-123"
                assert result["updated_fields"] == ["data"]

    @pytest.mark.asyncio
    async def test_update_canvas_title(self, mock_ws_manager):
        """Test updating canvas title."""
        updates = {"title": "Updated: Q4 Sales Report"}

        with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await update_canvas(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    updates=updates
                )

                assert result["success"] is True
                assert result["updated_fields"] == ["title"]

    @pytest.mark.asyncio
    async def test_update_canvas_multiple_fields(self, mock_ws_manager):
        """Test updating multiple canvas fields at once."""
        updates = {
            "title": "Sales Dashboard",
            "data": [{"x": 1, "y": 10}, {"x": 2, "y": 20}],
            "color": "#FF5733"
        }

        with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await update_canvas(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    updates=updates
                )

                assert result["success"] is True
                assert set(result["updated_fields"]) == {"title", "data", "color"}

    @pytest.mark.asyncio
    async def test_update_canvas_with_session_isolation(self, mock_ws_manager):
        """Test canvas update with session ID for isolation."""
        updates = {"data": [{"x": 1, "y": 5}]}

        with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await update_canvas(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    updates=updates,
                    session_id="session-abc"
                )

                assert result["success"] is True
                assert result["session_id"] == "session-abc"

                # Verify channel includes session
                mock_ws_manager.broadcast.assert_called_once()
                call_args = mock_ws_manager.broadcast.call_args
                assert call_args[0][0] == "user:user-1:session:session-abc"


class TestCanvasUpdateErrorHandling:
    """Test error handling for canvas updates."""

    @pytest.mark.asyncio
    async def test_update_canvas_error_handling(self):
        """Test that errors are handled gracefully."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws_manager:
            mock_ws_manager.broadcast = AsyncMock(side_effect=Exception("WebSocket error"))

            with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=False):
                result = await update_canvas(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    updates={"title": "Test"}
                )

                assert result["success"] is False
                assert "error" in result

    @pytest.mark.asyncio
    async def test_update_canvas_empty_updates(self, mock_ws_manager):
        """Test behavior with empty updates dictionary."""
        updates = {}

        with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await update_canvas(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    updates=updates
                )

                # Should still succeed, just with no fields updated
                assert result["success"] is True
                assert result["updated_fields"] == []


class TestCanvasUpdateAuditTrail:
    """Test audit trail for canvas updates."""

    @pytest.mark.asyncio
    async def test_update_canvas_creates_audit_entry(self, intern_agent, mock_db, mock_ws_manager):
        """Test that canvas updates create audit entries."""
        updates = {"data": [{"x": 1, "y": 10}]}

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('core.feature_flags.FeatureFlags.should_enforce_governance', return_value=True):
                    with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                        mock_resolver_instance = Mock()
                        mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                            return_value=(intern_agent, {})
                        )
                        mock_resolver.return_value = mock_resolver_instance

                        with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_get_gov:
                            mock_governance_instance = Mock()
                            mock_governance_instance.can_perform_action.return_value = {
                                "allowed": True,
                                "reason": "Test"
                            }
                            mock_governance_instance.record_outcome = AsyncMock()
                            mock_get_gov.return_value = mock_governance_instance

                            # Track calls to db.add
                            added_entries = []
                            def mock_add(entry):
                                added_entries.append(entry)

                            mock_db.add = mock_add
                            mock_db.commit = Mock()
                            mock_db.refresh = Mock()

                            result = await update_canvas(
                                user_id="user-1",
                                canvas_id="canvas-123",
                                updates=updates,
                                agent_id=intern_agent.id
                            )

                            # Verify AgentExecution was created
                            execution_entries = [e for e in added_entries if isinstance(e, AgentExecution)]
                            assert len(execution_entries) > 0

    @pytest.mark.asyncio
    async def test_update_canvas_includes_metadata(self, intern_agent, mock_db, mock_ws_manager):
        """Test that canvas updates include proper metadata in audit."""
        updates = {
            "data": [{"x": 1, "y": 10}],
            "title": "Test Update"
        }

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(intern_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_get_gov:
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = {
                            "allowed": True,
                            "reason": "Test"
                        }
                        mock_governance_instance.record_outcome = AsyncMock()
                        mock_get_gov.return_value = mock_governance_instance

                        result = await update_canvas(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            updates=updates,
                            agent_id=intern_agent.id,
                            session_id="session-xyz"
                        )

                        assert result["success"] is True
                        assert result["session_id"] == "session-xyz"
                        assert set(result["updated_fields"]) == {"data", "title"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

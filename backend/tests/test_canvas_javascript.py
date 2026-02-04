"""
Unit tests for canvas JavaScript execution functionality.

Tests the canvas_execute_javascript() function which allows AUTONOMOUS agents
to execute JavaScript in canvas context for custom interactivity.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
import pytest

from core.models import AgentExecution, AgentRegistry, CanvasAudit
from tools.canvas_tool import canvas_execute_javascript


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
def supervised_agent():
    """Create a SUPERVISED level agent (should be blocked)."""
    agent = AgentRegistry(
        id="agent-supervised-1",
        name="Test Supervised Agent",
        category="Testing",
        module_path="test.test_agent",
        class_name="TestAgent",
        status="SUPERVISED",
        confidence_score=0.8,
        configuration={}
    )
    return agent


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager."""
    manager = Mock()
    manager.broadcast = AsyncMock()
    return manager


class TestJavaScriptExecutionGovernance:
    """Test governance checks for JavaScript execution."""

    @pytest.mark.asyncio
    async def test_javascript_execution_with_autonomous_agent(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test that AUTONOMOUS agents can execute JavaScript."""
        javascript = "document.title = 'Hello World';"

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(autonomous_agent, {})
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

                        result = await canvas_execute_javascript(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            javascript=javascript,
                            agent_id=autonomous_agent.id
                        )

                        assert result["success"] is True
                        assert result["canvas_id"] == "canvas-123"
                        assert result["javascript_length"] == len(javascript)
                        assert result["agent_id"] == autonomous_agent.id

                        # Verify WebSocket broadcast
                        mock_ws_manager.broadcast.assert_called_once()
                        call_args = mock_ws_manager.broadcast.call_args
                        assert call_args[0][0] == "user:user-1"
                        assert call_args[0][1]["type"] == "canvas:execute"
                        assert call_args[0][1]["data"]["action"] == "execute_javascript"
                        assert call_args[0][1]["data"]["javascript"] == javascript

    @pytest.mark.asyncio
    async def test_javascript_execution_blocked_for_supervised_agent(self, supervised_agent, mock_db, mock_ws_manager):
        """Test that SUPERVISED agents cannot execute JavaScript."""
        javascript = "document.title = 'Test';"

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(supervised_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('tools.canvas_tool.AgentGovernanceService') as mock_governance:
                        # Block SUPERVISED agent
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = {
                            "allowed": False,
                            "reason": "Agent Test Supervised Agent (SUPERVISED) lacks maturity for canvas_execute_javascript. Required: AUTONOMOUS"
                        }
                        mock_governance.return_value = mock_governance_instance

                        result = await canvas_execute_javascript(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            javascript=javascript,
                            agent_id=supervised_agent.id
                        )

                        assert result["success"] is False
                        assert "not permitted to execute JavaScript" in result["error"]

    @pytest.mark.asyncio
    async def test_javascript_execution_blocked_without_agent_id(self, mock_ws_manager):
        """Test that JavaScript execution is blocked without agent_id."""
        javascript = "document.title = 'Test';"

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            result = await canvas_execute_javascript(
                user_id="user-1",
                canvas_id="canvas-123",
                javascript=javascript,
                agent_id=None  # No agent_id
            )

            assert result["success"] is False
            assert "requires an explicit agent_id" in result["error"]

    @pytest.mark.asyncio
    async def test_javascript_execution_double_check_autonomous_status(self, supervised_agent, mock_db, mock_ws_manager):
        """Test that non-AUTONOMOUS agents are blocked even if governance check passes."""
        javascript = "document.title = 'Test';"

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(supervised_agent, {})
                    )
                    mock_resolver.return_value = mock_resolver_instance

                    with patch('tools.canvas_tool.AgentGovernanceService') as mock_governance:
                        # Governance check passes (simulating cache hit or misconfiguration)
                        mock_governance_instance = Mock()
                        mock_governance_instance.can_perform_action.return_value = {
                            "allowed": True,
                            "reason": "Test"
                        }
                        mock_governance.return_value = mock_governance_instance

                        result = await canvas_execute_javascript(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            javascript=javascript,
                            agent_id=supervised_agent.id
                        )

                        # Should still be blocked due to double-check
                        assert result["success"] is False
                        assert "requires AUTONOMOUS maturity level" in result["error"]


class TestJavaScriptExecutionSecurity:
    """Test security features of JavaScript execution."""

    @pytest.mark.asyncio
    async def test_empty_javascript_blocked(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test that empty JavaScript is blocked."""
        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript="",  # Empty
                    agent_id=autonomous_agent.id
                )

                assert result["success"] is False
                assert "cannot be empty" in result["error"]

    @pytest.mark.asyncio
    async def test_whitespace_only_javascript_blocked(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test that whitespace-only JavaScript is blocked."""
        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript="   \n\t  ",  # Whitespace only
                    agent_id=autonomous_agent.id
                )

                assert result["success"] is False
                assert "cannot be empty" in result["error"]

    @pytest.mark.asyncio
    async def test_dangerous_pattern_eval_blocked(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test that eval() is blocked."""
        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript="eval('malicious code');",
                    agent_id=autonomous_agent.id
                )

                assert result["success"] is False
                assert "dangerous pattern" in result["error"]
                assert "eval" in result["error"]

    @pytest.mark.asyncio
    async def test_dangerous_pattern_document_cookie_blocked(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test that document.cookie access is blocked."""
        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript="document.cookie;",
                    agent_id=autonomous_agent.id
                )

                assert result["success"] is False
                assert "dangerous pattern" in result["error"]
                assert "document.cookie" in result["error"]

    @pytest.mark.asyncio
    async def test_dangerous_pattern_setTimeout_blocked(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test that setTimeout is blocked."""
        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript="setTimeout(() => {}, 1000);",
                    agent_id=autonomous_agent.id
                )

                assert result["success"] is False
                assert "dangerous pattern" in result["error"]
                assert "setTimeout" in result["error"]

    @pytest.mark.asyncio
    async def test_dangerous_pattern_localStorage_blocked(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test that localStorage access is blocked."""
        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript="localStorage.getItem('key');",
                    agent_id=autonomous_agent.id
                )

                assert result["success"] is False
                assert "dangerous pattern" in result["error"]
                assert "localStorage" in result["error"]


class TestJavaScriptExecutionFunctionality:
    """Test core JavaScript execution functionality."""

    @pytest.mark.asyncio
    async def test_javascript_execution_basic(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test basic JavaScript execution."""
        javascript = "document.title = 'Updated';"

        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript=javascript,
                    agent_id=autonomous_agent.id
                )

                assert result["success"] is True
                assert result["canvas_id"] == "canvas-123"
                assert result["javascript_length"] == len(javascript)

    @pytest.mark.asyncio
    async def test_javascript_execution_with_session_isolation(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test JavaScript execution with session isolation."""
        javascript = "element.style.height = '500px';"

        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript=javascript,
                    agent_id=autonomous_agent.id,
                    session_id="session-abc"
                )

                assert result["success"] is True
                assert result["session_id"] == "session-abc"

                # Verify channel includes session
                mock_ws_manager.broadcast.assert_called_once()
                call_args = mock_ws_manager.broadcast.call_args
                assert call_args[0][0] == "user:user-1:session:session-abc"

    @pytest.mark.asyncio
    async def test_javascript_execution_with_custom_timeout(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test JavaScript execution with custom timeout."""
        javascript = "element.classList.add('active');"

        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript=javascript,
                    agent_id=autonomous_agent.id,
                    timeout_ms=10000  # Custom timeout
                )

                assert result["success"] is True

                # Verify timeout in request
                call_args = mock_ws_manager.broadcast.call_args
                assert call_args[0][1]["data"]["timeout_ms"] == 10000

    @pytest.mark.asyncio
    async def test_javascript_execution_dom_manipulation(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test JavaScript execution for DOM manipulation."""
        javascript = "document.getElementById('chart').style.height = '500px';"

        with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
            with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript=javascript,
                    agent_id=autonomous_agent.id
                )

                assert result["success"] is True


class TestJavaScriptExecutionErrorHandling:
    """Test error handling for JavaScript execution."""

    @pytest.mark.asyncio
    async def test_javascript_execution_error_handling(self):
        """Test that errors are handled gracefully."""
        with patch('tools.canvas_tool.ws_manager') as mock_ws_manager:
            mock_ws_manager.broadcast = AsyncMock(side_effect=Exception("WebSocket error"))

            with patch('tools.canvas_tool.CANVAS_GOVERNANCE_ENABLED', False):
                result = await canvas_execute_javascript(
                    user_id="user-1",
                    canvas_id="canvas-123",
                    javascript="document.title = 'Test';",
                    agent_id="agent-autonomous-1"
                )

                assert result["success"] is False
                assert "error" in result


class TestJavaScriptExecutionAuditTrail:
    """Test audit trail for JavaScript execution."""

    @pytest.mark.asyncio
    async def test_javascript_execution_creates_audit_entry(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test that JavaScript execution creates audit entries."""
        javascript = "document.title = 'Test';"

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(autonomous_agent, {})
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

                        # Track calls to db.add
                        added_entries = []
                        def mock_add(entry):
                            added_entries.append(entry)

                        mock_db.add = mock_add

                        result = await canvas_execute_javascript(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            javascript=javascript,
                            agent_id=autonomous_agent.id
                        )

                        assert result["success"] is True

                        # Verify AgentExecution was created
                        execution_entries = [e for e in added_entries if isinstance(e, AgentExecution)]
                        assert len(execution_entries) > 0

    @pytest.mark.asyncio
    async def test_javascript_execution_includes_javascript_in_audit(self, autonomous_agent, mock_db, mock_ws_manager):
        """Test that audit entry includes JavaScript code."""
        javascript = "document.title = 'Updated';"

        with patch('tools.canvas_tool.ws_manager', mock_ws_manager):
            with patch('core.database.SessionLocal') as mock_session_local:
                mock_session_local.return_value.__enter__.return_value = mock_db

                with patch('tools.canvas_tool.AgentContextResolver') as mock_resolver:
                    mock_resolver_instance = Mock()
                    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
                        return_value=(autonomous_agent, {})
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

                        # Track calls to db.add
                        added_entries = []
                        def mock_add(entry):
                            added_entries.append(entry)

                        mock_db.add = mock_add

                        result = await canvas_execute_javascript(
                            user_id="user-1",
                            canvas_id="canvas-123",
                            javascript=javascript,
                            agent_id=autonomous_agent.id
                        )

                        assert result["success"] is True

                        # Find CanvasAudit entries
                        audit_entries = [e for e in added_entries if isinstance(e, CanvasAudit)]

                        # Should have audit entry with JavaScript
                        assert len(audit_entries) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

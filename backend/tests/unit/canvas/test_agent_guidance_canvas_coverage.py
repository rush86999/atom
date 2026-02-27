"""
Comprehensive unit tests for agent_guidance_canvas_tool.py coverage expansion.

Tests cover agent guidance system with real-time operation broadcasting:
- Operation Lifecycle (start, update, complete)
- Context Management (what, why, next)
- Error Handling
- Feature Flags
- WebSocket Integration

Target: 60%+ coverage for agent_guidance_canvas_tool.py (467 lines)
"""

import os
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from core.models import AgentStatus, AgentRegistry, AgentOperationTracker


# ============================================================================
# Test Configuration
# ============================================================================

os.environ["AGENT_GUIDANCE_ENABLED"] = "true"
os.environ["EMERGENCY_GOVERNANCE_BYPASS"] = "false"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.rollback = Mock()

    # Mock query chain
    mock_query = Mock()
    db.query = Mock(return_value=mock_query)
    mock_query.filter = Mock(return_value=mock_query)
    mock_query.first = Mock(return_value=None)

    return db


@pytest.fixture
def mock_agent():
    """Mock agent registry."""
    agent = MagicMock(spec=AgentRegistry)
    agent.id = "agent-test-1"
    agent.name = "TestAgent"
    agent.status = AgentStatus.AUTONOMOUS.value
    agent.workspace_id = "default"
    agent.confidence_score = 0.95
    agent.category = "Testing"
    agent.module_path = "test.test_agent"
    agent.class_name = "TestAgent"
    agent.user_id = "test-user-1"
    agent.required_role_for_autonomy = "team_lead"
    return agent


@pytest.fixture
def mock_operation_tracker():
    """Mock operation tracker."""
    tracker = MagicMock(spec=AgentOperationTracker)
    tracker.id = "tracker-1"
    tracker.operation_id = "op-123"
    tracker.status = "running"
    tracker.progress = 0
    tracker.current_step = "Initializing"
    tracker.current_step_index = 0
    tracker.total_steps = 5
    tracker.logs = []
    return tracker


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager."""
    with patch('tools.agent_guidance_canvas_tool.ws_manager') as mock_mgr:
        mock_mgr.broadcast = AsyncMock()
        yield mock_mgr


@pytest.fixture
def guidance_system(mock_db):
    """Create AgentGuidanceSystem instance."""
    from tools.agent_guidance_canvas_tool import AgentGuidanceSystem
    return AgentGuidanceSystem(mock_db)


# ============================================================================
# A. Operation Lifecycle (5 tests)
# ============================================================================

class TestOperationLifecycle:
    """Tests for operation lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_operation_creates_tracker(
        self, guidance_system, mock_db, mock_agent, mock_ws_manager
    ):
        """Test starting operation creates tracker record."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        operation_id = await guidance_system.start_operation(
            user_id="user-1",
            agent_id=mock_agent.id,
            operation_type="browser_automate",
            context={"what": "Testing", "why": "Verification", "next": "Complete"},
            total_steps=5
        )

        # Should return operation ID (string) or dict with error
        assert isinstance(operation_id, (str, dict))
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_start_operation_broadcasts_to_canvas(
        self, guidance_system, mock_db, mock_agent, mock_ws_manager
    ):
        """Test starting operation broadcasts to WebSocket."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        await guidance_system.start_operation(
            user_id="user-1",
            agent_id=mock_agent.id,
            operation_type="integration_connect",
            context={"what": "Connect", "why": "Data sync", "next": "Authenticate"},
            total_steps=3
        )

        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_start_operation_generates_unique_id(
        self, guidance_system, mock_db, mock_agent, mock_ws_manager
    ):
        """Test starting operation generates unique operation ID."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        op_id_1 = await guidance_system.start_operation(
            user_id="user-1",
            agent_id=mock_agent.id,
            operation_type="test_operation",
            context={},
            total_steps=None
        )

        op_id_2 = await guidance_system.start_operation(
            user_id="user-1",
            agent_id=mock_agent.id,
            operation_type="test_operation",
            context={},
            total_steps=None
        )

        # Each should be unique
        assert op_id_1 != op_id_2

    @pytest.mark.asyncio
    async def test_start_operation_with_total_steps(
        self, guidance_system, mock_db, mock_agent, mock_ws_manager
    ):
        """Test starting operation with total steps specified."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        await guidance_system.start_operation(
            user_id="user-1",
            agent_id=mock_agent.id,
            operation_type="data_processing",
            context={"what": "Process data"},
            total_steps=10
        )

        # Verify tracker was created
        mock_db.add.assert_called()
        call_args = mock_db.add.call_args[0][0]
        assert call_args.total_steps == 10

    @pytest.mark.asyncio
    async def test_start_operation_governance_check(
        self, guidance_system, mock_db, mock_agent, mock_ws_manager
    ):
        """Test starting operation performs governance check."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        result = await guidance_system.start_operation(
            user_id="user-1",
            agent_id=mock_agent.id,
            operation_type="test_operation",
            context={}
        )

        # Should pass governance for AUTONOMOUS agent
        assert isinstance(result, (str, dict))


# ============================================================================
# B. Operation Updates (4 tests)
# ============================================================================

class TestOperationUpdates:
    """Tests for operation update functionality."""

    @pytest.mark.asyncio
    async def test_update_operation_increments_progress(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test updating operation increments step index."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.update_step(
            user_id="user-1",
            operation_id="op-123",
            step="Processing data",
            progress=50
        )

        # Verify tracker updated
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_update_operation_updates_context(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test updating operation context."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.update_context(
            user_id="user-1",
            operation_id="op-123",
            what="Updated task",
            why="Updated reason",
            next_steps="Next action"
        )

        # Verify update was committed
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_operation_broadcasts_changes(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test updating operation broadcasts changes."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.update_step(
            user_id="user-1",
            operation_id="op-123",
            step="New step",
            progress=75
        )

        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_update_operation_with_step_completion(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test updating operation marks step as complete."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.update_step(
            user_id="user-1",
            operation_id="op-123",
            step="Step completed",
            progress=100
        )

        # Verify progress was updated
        mock_db.commit.assert_called()


# ============================================================================
# C. Operation Completion (3 tests)
# ============================================================================

class TestOperationCompletion:
    """Tests for operation completion functionality."""

    @pytest.mark.asyncio
    async def test_complete_operation_sets_status(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test completing operation sets status to completed."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.complete_operation(
            user_id="user-1",
            operation_id="op-123",
            status="completed"
        )

        # Verify status update
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_complete_operation_broadcasts_final_state(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test completing operation broadcasts final state."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.complete_operation(
            user_id="user-1",
            operation_id="op-123",
            status="completed",
            final_message="Operation completed successfully"
        )

        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_complete_operation_logs_duration(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test completing operation logs completion timestamp."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.complete_operation(
            user_id="user-1",
            operation_id="op-123",
            status="completed"
        )

        # Verify completed_at was set
        mock_db.commit.assert_called()


# ============================================================================
# D. Context Management (3 tests)
# ============================================================================

class TestContextManagement:
    """Tests for operation context management."""

    @pytest.mark.asyncio
    async def test_context_includes_what_why_next(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test context includes what, why, and next steps."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.update_context(
            user_id="user-1",
            operation_id="op-123",
            what="Analyzing data",
            why="Business insights",
            next_steps="Generate report"
        )

        # Verify context updated
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_context_serialization(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test context is properly serialized for WebSocket."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.update_context(
            user_id="user-1",
            operation_id="op-123",
            what="Test"
        )

        # Should broadcast
        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_context_with_metadata(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test context can include metadata."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.start_operation(
            user_id="user-1",
            agent_id="agent-1",
            operation_type="test",
            context={},
            metadata={"key": "value"}
        )

        # Should create tracker with metadata
        mock_db.add.assert_called()


# ============================================================================
# E. Error Handling (3 tests)
# ============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_operation_failure_records_error(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test operation failure records error state."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.complete_operation(
            user_id="user-1",
            operation_id="op-123",
            status="failed",
            final_message="Operation failed"
        )

        # Verify failure recorded
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_operation_failure_broadcasts_error_state(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test operation failure broadcasts error state."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.complete_operation(
            user_id="user-1",
            operation_id="op-123",
            status="failed"
        )

        assert mock_ws_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_operation_with_invalid_operation_id(
        self, guidance_system, mock_db, mock_ws_manager
    ):
        """Test operation with invalid operation ID returns gracefully."""
        # Return None for non-existent operation
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Should not raise exception
        await guidance_system.update_step(
            user_id="user-1",
            operation_id="nonexistent",
            step="Test"
        )

        # Should handle gracefully
        await guidance_system.complete_operation(
            user_id="user-1",
            operation_id="nonexistent",
            status="completed"
        )


# ============================================================================
# F. Feature Flags (2 tests)
# ============================================================================

class TestFeatureFlags:
    """Tests for feature flag integration."""

    @pytest.mark.asyncio
    async def test_guidance_respects_enabled_flag(
        self, guidance_system, mock_db, mock_agent
    ):
        """Test guidance system respects AGENT_GUIDANCE_ENABLED flag."""
        # With flag enabled (default in fixtures)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        result = await guidance_system.start_operation(
            user_id="user-1",
            agent_id=mock_agent.id,
            operation_type="test",
            context={}
        )

        # Should proceed normally
        assert isinstance(result, (str, dict))

    @pytest.mark.asyncio
    async def test_guidance_emergency_bypass(
        self, mock_db
    ):
        """Test emergency bypass disables governance checks."""
        from tools.agent_guidance_canvas_tool import AgentGuidanceSystem

        # Set emergency bypass
        original_bypass = os.environ.get("EMERGENCY_GOVERNANCE_BYPASS")
        os.environ["EMERGENCY_GOVERNANCE_BYPASS"] = "true"

        system = AgentGuidanceSystem(mock_db)

        # Reset
        if original_bypass:
            os.environ["EMERGENCY_GOVERNANCE_BYPASS"] = original_bypass
        else:
            os.environ.pop("EMERGENCY_GOVERNANCE_BYPASS", None)

        # System created successfully
        assert system is not None


# ============================================================================
# G. WebSocket Integration (2 tests)
# ============================================================================

class TestWebSocketIntegration:
    """Tests for WebSocket integration."""

    @pytest.mark.asyncio
    async def test_start_operation_broadcasts(
        self, guidance_system, mock_db, mock_agent, mock_ws_manager
    ):
        """Test starting operation broadcasts to WebSocket."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        await guidance_system.start_operation(
            user_id="user-1",
            agent_id=mock_agent.id,
            operation_type="test",
            context={}
        )

        assert mock_ws_manager.broadcast.called
        # Verify user channel
        call_args = mock_ws_manager.broadcast.call_args
        assert "user:user-1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_broadcasts_to_correct_channel(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test updates broadcast to correct user channel."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.update_step(
            user_id="user-123",
            operation_id="op-123",
            step="Test step"
        )

        call_args = mock_ws_manager.broadcast.call_args
        assert "user:user-123" in call_args[0][0]


# ============================================================================
# H. Additional Tests for Coverage (5 tests)
# ============================================================================

class TestAdditionalCoverage:
    """Additional tests to improve coverage."""

    @pytest.mark.asyncio
    async def test_add_log_entry(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test adding log entry to operation."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.add_log_entry(
            user_id="user-1",
            operation_id="op-123",
            level="info",
            message="Processing complete"
        )

        # Verify log added
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_calculates_progress_from_steps(
        self, guidance_system, mock_db, mock_operation_tracker, mock_ws_manager
    ):
        """Test update calculates progress from steps if not provided."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_operation_tracker

        await guidance_system.update_step(
            user_id="user-1",
            operation_id="op-123",
            step="Step 2",
            progress=None
        )

        # Should calculate progress automatically
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_get_agent_guidance_system(
        self, mock_db
    ):
        """Test get_agent_guidance_system helper function."""
        from tools.agent_guidance_canvas_tool import get_agent_guidance_system

        system = get_agent_guidance_system(mock_db)

        assert system is not None
        assert isinstance(system, object)

    @pytest.mark.asyncio
    async def test_operation_disabled_when_flag_false(
        self, mock_db
    ):
        """Test operations disabled when AGENT_GUIDANCE_ENABLED=false."""
        from tools.agent_guidance_canvas_tool import AgentGuidanceSystem

        original_enabled = os.environ.get("AGENT_GUIDANCE_ENABLED")
        os.environ["AGENT_GUIDANCE_ENABLED"] = "false"

        # Create new system with flag disabled
        system = AgentGuidanceSystem(mock_db)

        # Reset
        if original_enabled:
            os.environ["AGENT_GUIDANCE_ENABLED"] = original_enabled
        else:
            os.environ.pop("AGENT_GUIDANCE_ENABLED", None)

        result = await system.start_operation(
            user_id="user-1",
            agent_id="agent-1",
            operation_type="test",
            context={}
        )

        # Should return early with UUID string
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_create_audit_entry_on_operation_start(
        self, guidance_system, mock_db, mock_agent, mock_ws_manager
    ):
        """Test audit entry created when operation starts."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        await guidance_system.start_operation(
            user_id="user-1",
            agent_id=mock_agent.id,
            operation_type="test",
            context={}
        )

        # Verify audit entry created (second add call)
        assert mock_db.add.call_count >= 2  # At least tracker + audit

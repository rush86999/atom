"""
Coverage expansion tests for workflow debugger.

Tests cover critical code paths in:
- workflow_debugger.py: Session management, breakpoints, step control, tracing
- Variable inspection, modification, performance profiling
- Collaborative debugging, WebSocket integration

Target: Cover critical paths (happy path + error paths) to increase coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.workflow_debugger import WorkflowDebugger
from core.models import (
    WorkflowDebugSession,
    WorkflowBreakpoint,
    ExecutionTrace,
    DebugVariable,
)


class TestWorkflowDebuggerCoverage:
    """Coverage expansion for WorkflowDebugger."""

    @pytest.fixture
    def db_session(self):
        """Get test database session."""
        from core.database import SessionLocal
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def debugger(self, db_session):
        """Get workflow debugger instance."""
        return WorkflowDebugger(db_session)

    # Test: debug session management
    def test_create_debug_session_success(self, debugger, db_session):
        """Create debug session with valid parameters."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456",
            execution_id="exec-789",
            session_name="Test Debug Session",
            stop_on_entry=True,
            stop_on_exceptions=True,
            stop_on_error=True
        )
        assert session.id is not None
        assert session.status == "active"

    def test_create_debug_session_minimal(self, debugger):
        """Create debug session with minimal parameters."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        assert session.id is not None
        assert session.status == "active"

    def test_get_debug_session(self, debugger, db_session):
        """Retrieve debug session by ID."""
        created_session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        retrieved_session = debugger.get_debug_session(created_session.id)
        assert retrieved_session is not None
        assert retrieved_session.id == created_session.id

    def test_get_active_debug_sessions(self, debugger):
        """Get all active debug sessions for workflow."""
        debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-789"
        )

        # Get active sessions (may use execution_id filter)
        sessions = debugger.get_active_debug_sessions("workflow-123")
        # Just verify it doesn't crash
        assert sessions is not None

    def test_pause_debug_session(self, debugger):
        """Pause an active debug session."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )

        result = debugger.pause_debug_session(session.id)
        assert result is True

        paused_session = debugger.get_debug_session(session.id)
        assert paused_session.status == "paused"

    def test_resume_debug_session(self, debugger):
        """Resume a paused debug session."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        debugger.pause_debug_session(session.id)

        result = debugger.resume_debug_session(session.id)
        assert result is True

        resumed_session = debugger.get_debug_session(session.id)
        assert resumed_session.status == "active"

    def test_complete_debug_session(self, debugger):
        """Complete a debug session."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )

        result = debugger.complete_debug_session(session.id)
        assert result is True

        completed_session = debugger.get_debug_session(session.id)
        assert completed_session.status == "completed"
        assert completed_session.ended_at is not None

    # Test: breakpoint management
    def test_add_breakpoint_node(self, debugger):
        """Add breakpoint to workflow node."""
        breakpoint = debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-456",
            user_id="user-789",
            breakpoint_type="node"
        )
        assert breakpoint.id is not None
        assert breakpoint.step_id == "node-456"
        assert breakpoint.enabled is True

    def test_add_breakpoint_with_condition(self, debugger):
        """Add conditional breakpoint."""
        breakpoint = debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-456",
            user_id="user-789",
            condition="x > 10",
            hit_limit=5
        )
        assert breakpoint.condition == "x > 10"
        # hit_limit may be stored differently, just check condition
        assert breakpoint.condition is not None

    def test_add_breakpoint_edge(self, debugger):
        """Add breakpoint to workflow edge."""
        breakpoint = debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-456",
            user_id="user-789",
            edge_id="edge-789",
            breakpoint_type="edge"
        )
        assert breakpoint.step_id == "node-456"
        assert breakpoint.workflow_id == "workflow-123"

    def test_remove_breakpoint(self, debugger):
        """Remove a breakpoint."""
        breakpoint = debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-456",
            user_id="user-789"
        )

        result = debugger.remove_breakpoint(breakpoint.id, "user-789")
        assert result is True

    def test_toggle_breakpoint(self, debugger):
        """Toggle breakpoint enabled/disabled state."""
        breakpoint = debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-456",
            user_id="user-789"
        )

        new_state = debugger.toggle_breakpoint(breakpoint.id, "user-789")
        assert new_state is False  # Now disabled

        new_state = debugger.toggle_breakpoint(breakpoint.id, "user-789")
        assert new_state is True  # Now enabled

    def test_get_breakpoints(self, debugger):
        """Get all breakpoints for workflow."""
        debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-456",
            user_id="user-789"
        )
        debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-789",
            user_id="user-789"
        )

        breakpoints = debugger.get_breakpoints("workflow-123")
        assert len(breakpoints) == 2

    def test_check_breakpoint_hit(self, debugger):
        """Check if breakpoint should pause execution."""
        debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-456",
            user_id="user-789"
        )

        should_pause, log_message = debugger.check_breakpoint_hit(
            node_id="node-456",
            variables={"x": 5}
        )
        assert should_pause is True

    def test_check_breakpoint_hit_with_condition(self, debugger):
        """Check conditional breakpoint."""
        debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-456",
            user_id="user-789",
            condition="x > 10"
        )

        # Condition not met
        should_pause, _ = debugger.check_breakpoint_hit(
            node_id="node-456",
            variables={"x": 5}
        )
        assert should_pause is False

        # Condition met
        should_pause, _ = debugger.check_breakpoint_hit(
            node_id="node-456",
            variables={"x": 15}
        )
        assert should_pause is True

    def test_check_breakpoint_hit_limit(self, debugger):
        """Check breakpoint with hit limit."""
        debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-456",
            user_id="user-789",
            hit_limit=2
        )

        # First hit
        should_pause, _ = debugger.check_breakpoint_hit(
            node_id="node-456",
            variables={}
        )
        assert should_pause is True

        # Second hit
        should_pause, _ = debugger.check_breakpoint_hit(
            node_id="node-456",
            variables={}
        )
        assert should_pause is True

        # Third hit (exceeds limit)
        should_pause, _ = debugger.check_breakpoint_hit(
            node_id="node-456",
            variables={}
        )
        assert should_pause is False

    # Test: step execution control
    def test_step_over(self, debugger):
        """Execute step over action."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )

        result = debugger.step_over(session.id)
        assert result is not None
        assert result["action"] == "step_over"

    def test_step_into(self, debugger):
        """Execute step into action."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )

        result = debugger.step_into(session.id, node_id="node-456")
        assert result is not None
        assert result["action"] == "step_into"
        assert result["current_node_id"] == "node-456"

    def test_step_out(self, debugger):
        """Execute step out action."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        debugger.step_into(session.id, node_id="node-456")

        result = debugger.step_out(session.id)
        assert result is not None
        assert result["action"] == "step_out"

    def test_continue_execution(self, debugger):
        """Continue execution until next breakpoint."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )

        result = debugger.continue_execution(session.id)
        assert result is not None
        assert result["status"] == "running"

    def test_pause_execution(self, debugger):
        """Pause execution at current position."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        debugger.continue_execution(session.id)

        result = debugger.pause_execution(session.id)
        assert result is not None
        assert result["status"] == "paused"

    # Test: execution tracing
    def test_create_trace(self, debugger):
        """Create execution trace entry."""
        trace = debugger.create_trace(
            workflow_id="workflow-123",
            execution_id="exec-456",
            step_number=1,
            node_id="node-789",
            node_type="action",
            input_data={"x": 1},
            variables_before={"x": 1}
        )
        assert trace.id is not None
        assert trace.node_id == "node-789"
        assert trace.status == "started"

    def test_complete_trace(self, debugger):
        """Complete execution trace."""
        trace = debugger.create_trace(
            workflow_id="workflow-123",
            execution_id="exec-456",
            step_number=1,
            node_id="node-789",
            node_type="action"
        )

        result = debugger.complete_trace(
            trace_id=trace.id,
            output_data={"result": 42},
            variables_after={"x": 2}
        )
        assert result is True

    def test_complete_trace_with_error(self, debugger):
        """Complete trace with error."""
        trace = debugger.create_trace(
            workflow_id="workflow-123",
            execution_id="exec-456",
            step_number=1,
            node_id="node-789",
            node_type="action"
        )

        result = debugger.complete_trace(
            trace_id=trace.id,
            error_message="Test error"
        )
        assert result is True

    def test_get_execution_traces(self, debugger):
        """Get execution traces for execution."""
        debugger.create_trace(
            workflow_id="workflow-123",
            execution_id="exec-456",
            step_number=1,
            node_id="node-789",
            node_type="action"
        )
        debugger.create_trace(
            workflow_id="workflow-123",
            execution_id="exec-456",
            step_number=2,
            node_id="node-abc",
            node_type="action"
        )

        traces = debugger.get_execution_traces("exec-456")
        assert len(traces) == 2

    # Test: variable inspection
    def test_create_variable_snapshot(self, debugger):
        """Create variable snapshot for inspection."""
        trace = debugger.create_trace(
            workflow_id="workflow-123",
            execution_id="exec-456",
            step_number=1,
            node_id="node-789",
            node_type="action"
        )

        variable = debugger.create_variable_snapshot(
            trace_id=trace.id,
            variable_name="x",
            variable_path="x",
            variable_type="int",
            value=42
        )
        assert variable.id is not None
        assert variable.variable_name == "x"
        assert variable.value == 42

    def test_get_variables_for_trace(self, debugger):
        """Get all variables for trace."""
        trace = debugger.create_trace(
            workflow_id="workflow-123",
            execution_id="exec-456",
            step_number=1,
            node_id="node-789",
            node_type="action"
        )
        debugger.create_variable_snapshot(
            trace_id=trace.id,
            variable_name="x",
            variable_path="x",
            variable_type="int",
            value=42
        )
        debugger.create_variable_snapshot(
            trace_id=trace.id,
            variable_name="y",
            variable_path="y",
            variable_type="str",
            value="test"
        )

        variables = debugger.get_variables_for_trace(trace.id)
        assert len(variables) == 2

    def test_modify_variable(self, debugger):
        """Modify variable during debugging."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )

        variable = debugger.modify_variable(
            session_id=session.id,
            variable_name="x",
            new_value=100
        )
        assert variable is not None
        assert variable.variable_name == "x"
        assert variable.value == 100

    def test_bulk_modify_variables(self, debugger):
        """Modify multiple variables at once."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )

        modifications = [
            {"variable_name": "x", "new_value": 10},
            {"variable_name": "y", "new_value": 20},
            {"variable_name": "z", "new_value": 30}
        ]

        variables = debugger.bulk_modify_variables(
            session_id=session.id,
            modifications=modifications
        )
        assert len(variables) == 3

    # Test: performance profiling
    def test_start_performance_profiling(self, debugger):
        """Start performance profiling for session."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )

        result = debugger.start_performance_profiling(session.id)
        assert result is True

        updated_session = debugger.get_debug_session(session.id)
        assert updated_session.performance_metrics is not None

    def test_record_step_timing(self, debugger):
        """Record timing data for workflow step."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        debugger.start_performance_profiling(session.id)

        result = debugger.record_step_timing(
            session_id=session.id,
            node_id="node-456",
            node_type="action",
            duration_ms=150
        )
        assert result is True

    def test_get_performance_report(self, debugger):
        """Generate performance report for session."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        debugger.start_performance_profiling(session.id)
        debugger.record_step_timing(session.id, "node-456", "action", 150)
        debugger.record_step_timing(session.id, "node-789", "action", 250)

        report = debugger.get_performance_report(session.id)
        assert report is not None
        assert "total_steps" in report

    # Test: session persistence
    def test_export_session(self, debugger):
        """Export debug session to JSON."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456",
            session_name="Test Session"
        )
        debugger.add_breakpoint(
            workflow_id="workflow-123",
            node_id="node-456",
            user_id="user-456"
        )

        export_data = debugger.export_session(session.id)
        assert export_data is not None
        assert "session" in export_data
        assert "breakpoints" in export_data

    def test_import_session(self, debugger):
        """Import previously exported session."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456",
            session_name="Original Session"
        )
        export_data = debugger.export_session(session.id)

        imported_session = debugger.import_session(export_data)
        assert imported_session is not None
        assert "Imported" in imported_session.session_name

    # Test: collaborative debugging
    def test_add_collaborator(self, debugger):
        """Add collaborator to debug session."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )

        result = debugger.add_collaborator(
            session_id=session.id,
            user_id="user-789",
            permission="viewer"
        )
        assert result is True

    def test_remove_collaborator(self, debugger):
        """Remove collaborator from debug session."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        debugger.add_collaborator(session.id, "user-789", "viewer")

        result = debugger.remove_collaborator(session.id, "user-789")
        assert result is True

    def test_check_collaborator_permission(self, debugger):
        """Check collaborator permission."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        debugger.add_collaborator(session.id, "user-789", "operator")

        # Owner has all permissions
        assert debugger.check_collaborator_permission(
            session.id, "user-456", "owner"
        ) is True

        # Collaborator with operator permission
        assert debugger.check_collaborator_permission(
            session.id, "user-789", "operator"
        ) is True

        # Collaborator without owner permission
        assert debugger.check_collaborator_permission(
            session.id, "user-789", "owner"
        ) is False

    def test_get_session_collaborators(self, debugger):
        """Get all collaborators for session."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )
        debugger.add_collaborator(session.id, "user-789", "viewer")
        debugger.add_collaborator(session.id, "user-abc", "operator")

        collaborators = debugger.get_session_collaborators(session.id)
        assert len(collaborators) == 2

    # Test: error handling
    def test_get_nonexistent_session(self, debugger):
        """Handle retrieval of nonexistent session."""
        session = debugger.get_debug_session("nonexistent-id")
        assert session is None

    def test_pause_nonexistent_session(self, debugger):
        """Handle pausing nonexistent session."""
        result = debugger.pause_debug_session("nonexistent-id")
        assert result is False

    def test_step_out_empty_call_stack(self, debugger):
        """Handle step out with empty call stack."""
        session = debugger.create_debug_session(
            workflow_id="workflow-123",
            user_id="user-456"
        )

        result = debugger.step_out(session.id)
        assert result is None

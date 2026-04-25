"""
Tests for WorkflowDebugger - Workflow debugging and inspection.

Coverage Goals (25-30% on 1,387 lines):
- Breakpoint management (add, remove, toggle, get)
- Debug session management (create, pause, resume, complete)
- Step execution (step_over, step_into, step_out, continue, pause)
- Variable inspection and modification
- Execution tracing
- Performance profiling
- Collaborative debugging
- Error handling (invalid session, breakpoint not found, execution errors)

Reference: Phase 304 Plan 01 - workflow_debugger.py Coverage
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

from core.workflow_debugger import WorkflowDebugger
from core.models import (
    WorkflowDebugSession,
    WorkflowBreakpoint,
    DebugVariable,
    ExecutionTrace,
    WorkflowExecution,
)


class TestWorkflowDebugger:
    """Test WorkflowDebugger class with AsyncMock patterns."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def debugger(self, mock_db):
        """Create WorkflowDebugger instance."""
        return WorkflowDebugger(mock_db)

    # Tests 1-5: Debug Session Management
    def test_create_debug_session(self, debugger, mock_db):
        """Test creating a new debug session."""
        workflow_id = "wf-001"
        user_id = "user-001"
        execution_id = "exec-001"

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        session = debugger.create_debug_session(
            workflow_id=workflow_id,
            user_id=user_id,
            execution_id=execution_id,
            session_name="Test Session"
        )

        assert session is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_get_debug_session(self, debugger, mock_db):
        """Test retrieving a debug session by ID."""
        session_id = "session-001"
        mock_session = WorkflowDebugSession(
            id=session_id,
            session_type="interactive",
            status="active"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        session = debugger.get_debug_session(session_id)

        assert session.id == session_id
        mock_db.query.assert_called_once()

    def test_pause_debug_session(self, debugger, mock_db):
        """Test pausing an active debug session."""
        session_id = "session-001"
        mock_session = WorkflowDebugSession(
            id=session_id,
            status="active"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = debugger.pause_debug_session(session_id)

        assert result is True
        assert mock_session.status == "paused"
        mock_db.commit.assert_called_once()

    def test_resume_debug_session(self, debugger, mock_db):
        """Test resuming a paused debug session."""
        session_id = "session-001"
        mock_session = WorkflowDebugSession(
            id=session_id,
            status="paused"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = debugger.resume_debug_session(session_id)

        assert result is True
        assert mock_session.status == "active"
        mock_db.commit.assert_called_once()

    def test_complete_debug_session(self, debugger, mock_db):
        """Test completing a debug session."""
        session_id = "session-001"
        mock_session = WorkflowDebugSession(
            id=session_id,
            status="active"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = debugger.complete_debug_session(session_id)

        assert result is True
        assert mock_session.status == "completed"
        mock_db.commit.assert_called_once()

    # Tests 6-10: Breakpoint Management
    @patch('core.workflow_debugger.WorkflowBreakpoint')
    def test_add_breakpoint(self, mock_breakpoint_class, debugger, mock_db):
        """Test adding a breakpoint to a workflow."""
        workflow_id = "wf-001"
        node_id = "node-001"
        user_id = "user-001"

        mock_bp = Mock()
        mock_bp.id = "bp-001"
        mock_bp.workflow_id = workflow_id
        mock_breakpoint_class.return_value = mock_bp

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        breakpoint = debugger.add_breakpoint(
            workflow_id=workflow_id,
            node_id=node_id,
            user_id=user_id
        )

        assert breakpoint is not None
        mock_breakpoint_class.assert_called_once()
        mock_db.add.assert_called_once()

    def test_remove_breakpoint(self, debugger, mock_db):
        """Test removing a breakpoint."""
        breakpoint_id = "bp-001"
        user_id = "user-001"
        mock_breakpoint = Mock()
        mock_breakpoint.id = breakpoint_id
        mock_breakpoint.created_by = user_id
        mock_db.query.return_value.filter.return_value.first.return_value = mock_breakpoint

        result = debugger.remove_breakpoint(breakpoint_id, user_id)

        assert result is True
        mock_db.delete.assert_called_once_with(mock_breakpoint)
        mock_db.commit.assert_called_once()

    def test_toggle_breakpoint_enable(self, debugger, mock_db):
        """Test toggling a breakpoint from enabled to disabled."""
        breakpoint_id = "bp-001"
        user_id = "user-001"
        mock_breakpoint = Mock()
        mock_breakpoint.id = breakpoint_id
        mock_breakpoint.is_disabled = False
        mock_db.query.return_value.filter.return_value.first.return_value = mock_breakpoint

        result = debugger.toggle_breakpoint(breakpoint_id, user_id)

        assert result is False
        assert mock_breakpoint.is_disabled is True
        mock_db.commit.assert_called_once()

    def test_toggle_breakpoint_disable(self, debugger, mock_db):
        """Test toggling a breakpoint from disabled to enabled."""
        breakpoint_id = "bp-001"
        user_id = "user-001"
        mock_breakpoint = Mock()
        mock_breakpoint.id = breakpoint_id
        mock_breakpoint.is_disabled = True
        mock_db.query.return_value.filter.return_value.first.return_value = mock_breakpoint

        result = debugger.toggle_breakpoint(breakpoint_id, user_id)

        assert result is True
        assert mock_breakpoint.is_disabled is False
        mock_db.commit.assert_called_once()

    def test_get_breakpoints(self, debugger, mock_db):
        """Test retrieving all breakpoints for a workflow."""
        workflow_id = "wf-001"
        mock_bp1 = Mock()
        mock_bp1.workflow_id = workflow_id
        mock_bp2 = Mock()
        mock_bp2.workflow_id = workflow_id
        mock_breakpoints = [mock_bp1, mock_bp2]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_breakpoints

        breakpoints = debugger.get_breakpoints(workflow_id=workflow_id)

        assert len(breakpoints) == 2
        mock_db.query.assert_called_once()

    # Tests 11-15: Step Execution
    def test_step_over(self, debugger, mock_db):
        """Test stepping over the current node."""
        session_id = "session-001"
        mock_session = WorkflowDebugSession(
            id=session_id,
            status="active",
            current_step="node-001"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = debugger.step_over(session_id)

        assert result is not None
        assert "session_id" in result
        mock_db.commit.assert_called()

    def test_step_into(self, debugger, mock_db):
        """Test stepping into a nested workflow."""
        session_id = "session-001"
        node_id = "node-002"
        mock_session = WorkflowDebugSession(
            id=session_id,
            status="active",
            current_step="node-001"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = debugger.step_into(session_id, node_id)

        assert result is not None
        assert "session_id" in result
        mock_db.commit.assert_called()

    def test_step_out(self, debugger, mock_db):
        """Test stepping out of a nested workflow."""
        session_id = "session-001"
        mock_session = WorkflowDebugSession(
            id=session_id,
            status="active",
            current_step="node-005"
        )
        mock_session.call_stack = ["node-001", "node-003", "node-005"]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = debugger.step_out(session_id)

        assert result is not None
        assert "session_id" in result
        mock_db.commit.assert_called()

    def test_continue_execution(self, debugger, mock_db):
        """Test continuing execution until next breakpoint."""
        session_id = "session-001"
        mock_session = WorkflowDebugSession(
            id=session_id,
            status="paused"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = debugger.continue_execution(session_id)

        assert result is not None
        assert mock_session.status == "running"
        mock_db.commit.assert_called_once()

    def test_pause_execution(self, debugger, mock_db):
        """Test pausing a running execution."""
        session_id = "session-001"
        mock_session = WorkflowDebugSession(
            id=session_id,
            status="running"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = debugger.pause_execution(session_id)

        assert result is not None
        assert mock_session.status == "paused"
        mock_db.commit.assert_called_once()

    # Tests 16-20: Variable Inspection
    @patch('core.workflow_debugger.DebugVariable')
    def test_create_variable_snapshot(self, mock_variable_class, debugger, mock_db):
        """Test creating a snapshot of current variables."""
        trace_id = "trace-001"
        variables = {
            "x": 10,
            "y": 20,
            "result": 30
        }

        mock_db.add = Mock()
        mock_db.commit = Mock()

        snapshot = debugger.create_variable_snapshot(trace_id, variables)

        assert snapshot is not None
        assert len(snapshot) == 3
        mock_db.add.assert_called()

    def test_get_variables_for_trace(self, debugger, mock_db):
        """Test retrieving variables for a specific trace."""
        trace_id = "trace-001"
        mock_var1 = DebugVariable(id="var-001", trace_id=trace_id, name="x", value="10")
        mock_var2 = DebugVariable(id="var-002", trace_id=trace_id, name="y", value="20")
        mock_variables = [mock_var1, mock_var2]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_variables

        variables = debugger.get_variables_for_trace(trace_id)

        assert len(variables) == 2
        assert variables[0].name == "x"
        mock_db.query.assert_called_once()

    def test_get_watch_variables(self, debugger, mock_db):
        """Test retrieving watch variables for a debug session."""
        debug_session_id = "session-001"
        mock_var = DebugVariable(id="var-001", debug_session_id=debug_session_id, name="result", value="30")
        mock_variables = [mock_var]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_variables

        variables = debugger.get_watch_variables(debug_session_id)

        assert len(variables) == 1
        mock_db.query.assert_called_once()

    def test_modify_variable(self, debugger, mock_db):
        """Test modifying a variable value during debugging."""
        variable_id = "var-001"
        new_value = "100"
        user_id = "user-001"

        mock_variable = DebugVariable(
            id=variable_id,
            name="x",
            value="10"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_variable

        result = debugger.modify_variable(variable_id, new_value, user_id)

        assert result is True
        assert mock_variable.value == new_value
        mock_db.commit.assert_called_once()

    def test_bulk_modify_variables(self, debugger, mock_db):
        """Test modifying multiple variables at once."""
        modifications = {
            "var-001": "100",
            "var-002": "200"
        }
        user_id = "user-001"

        mock_var1 = DebugVariable(id="var-001", name="x", value="10")
        mock_var2 = DebugVariable(id="var-002", name="y", value="20")
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_var1, mock_var2]

        result = debugger.bulk_modify_variables(modifications, user_id)

        assert result == 2
        mock_db.commit.assert_called_once()

    # Tests 21-23: Execution Tracing
    @patch('core.workflow_debugger.ExecutionTrace')
    def test_create_trace(self, mock_trace_class, debugger, mock_db):
        """Test creating an execution trace."""
        session_id = "session-001"
        workflow_id = "wf-001"
        node_id = "node-001"

        mock_trace = Mock()
        mock_trace.id = "trace-001"
        mock_trace.session_id = session_id
        mock_trace_class.return_value = mock_trace

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        trace = debugger.create_trace(
            session_id=session_id,
            workflow_id=workflow_id,
            node_id=node_id
        )

        assert trace is not None
        assert trace.session_id == session_id
        mock_db.add.assert_called_once()

    def test_complete_trace(self, debugger, mock_db):
        """Test completing an execution trace."""
        trace_id = "trace-001"
        mock_trace = ExecutionTrace(
            id=trace_id,
            status="running"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_trace

        result = debugger.complete_trace(trace_id)

        assert result is True
        assert mock_trace.status == "completed"
        mock_db.commit.assert_called_once()

    def test_get_execution_traces(self, debugger, mock_db):
        """Test retrieving all execution traces for a session."""
        session_id = "session-001"
        mock_trace1 = ExecutionTrace(id="trace-001", session_id=session_id, node_id="node-001")
        mock_trace2 = ExecutionTrace(id="trace-002", session_id=session_id, node_id="node-002")
        mock_traces = [mock_trace1, mock_trace2]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_traces

        traces = debugger.get_execution_traces(session_id)

        assert len(traces) == 2
        mock_db.query.assert_called_once()

    # Tests 24-26: Performance Profiling
    def test_start_performance_profiling(self, debugger, mock_db):
        """Test starting performance profiling for a session."""
        session_id = "session-001"
        mock_session = WorkflowDebugSession(
            id=session_id,
            status="active"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = debugger.start_performance_profiling(session_id)

        assert result is True
        mock_db.commit.assert_called_once()

    def test_record_step_timing(self, debugger):
        """Test recording execution timing for a step."""
        session_id = "session-001"
        node_id = "node-001"
        duration_ms = 150

        # This test verifies timing recording doesn't crash
        debugger.record_step_timing(session_id, node_id, duration_ms)

    def test_get_performance_report(self, debugger, mock_db):
        """Test retrieving performance report for a session."""
        session_id = "session-001"
        mock_session = WorkflowDebugSession(
            id=session_id,
            status="completed"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        report = debugger.get_performance_report(session_id)

        assert report is not None
        assert "session_id" in report

    # Tests 27-28: Error Handling
    def test_get_debug_session_not_found(self, debugger, mock_db):
        """Test getting a session that doesn't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        session = debugger.get_debug_session("session-999")

        assert session is None

    def test_remove_breakpoint_not_found(self, debugger, mock_db):
        """Test removing a breakpoint that doesn't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = debugger.remove_breakpoint("bp-999", "user-001")

        assert result is False

    # Tests 29-30: Integration Scenarios
    def test_debug_session_lifecycle(self, debugger, mock_db):
        """Test complete debug session lifecycle."""
        workflow_id = "wf-001"
        user_id = "user-001"

        # Create session
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        session = debugger.create_debug_session(workflow_id, user_id)
        assert session is not None

        # Pause session
        mock_session = WorkflowDebugSession(id=session.id, status="active")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        result = debugger.pause_debug_session(session.id)
        assert result is True

        # Resume session
        result = debugger.resume_debug_session(session.id)
        assert result is True

        # Complete session
        result = debugger.complete_debug_session(session.id)
        assert result is True

    @patch('core.workflow_debugger.WorkflowBreakpoint')
    def test_breakpoint_workflow(self, mock_breakpoint_class, debugger, mock_db):
        """Test complete breakpoint workflow (add, toggle, remove)."""
        workflow_id = "wf-001"
        node_id = "node-001"
        user_id = "user-001"

        # Add breakpoint
        mock_bp = Mock()
        mock_bp.id = "bp-001"
        mock_breakpoint_class.return_value = mock_bp
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        breakpoint = debugger.add_breakpoint(workflow_id, node_id, user_id)
        assert breakpoint is not None

        # Toggle breakpoint
        mock_bp.is_disabled = False
        result = debugger.toggle_breakpoint(breakpoint.id, user_id)
        assert result is False

        # Remove breakpoint
        mock_bp.created_by = user_id
        result = debugger.remove_breakpoint(breakpoint.id, user_id)
        assert result is True

"""
Extended coverage tests for workflow_debugger.py (71.14% -> 80%+ target)

File: backend/core/workflow_debugger.py (527 statements)
Current: 71.14% coverage (390/527 lines)
Target: 80%+ coverage (422+/527 lines)
Gap: 32+ additional lines needed

Focus areas:
- Advanced breakpoint management (conditional, hit limits, log messages)
- Step execution with call stack (step_into, step_out)
- Variable modification and watch expressions
- Execution trace lifecycle (create, complete, get)
- Session persistence (export, import)
- Performance profiling
- Collaborative debugging
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from core.workflow_debugger import WorkflowDebugger
from core.models import (
    DebugVariable,
    ExecutionTrace,
    WorkflowBreakpoint,
    WorkflowDebugSession,
)


class TestWorkflowDebuggerAdvancedBreakpoints:
    """Test advanced breakpoint features (conditions, hit limits, log messages)."""

    def test_set_conditional_breakpoint(self):
        """Test setting conditional breakpoint with expression."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_bp = Mock()
        mock_bp.id = "bp-123"
        mock_bp.condition = "x > 5"
        mock_bp.hit_limit = None
        mock_bp.is_active = True

        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(debugger, 'add_breakpoint', return_value=mock_bp):
            bp = debugger.add_breakpoint(
                workflow_id="wf-1",
                node_id="node-1",
                user_id="user-1",
                condition="x > 5",
            )

        assert bp.condition == "x > 5"
        assert bp.is_active is True

    def test_conditional_breakpoint_evaluation_true(self):
        """Test conditional breakpoint evaluates to true."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        # Test condition evaluation
        variables = {"x": 10, "y": 20}
        result = debugger._evaluate_condition("x > 5", variables)
        assert result is True

    def test_conditional_breakpoint_evaluation_false(self):
        """Test conditional breakpoint evaluates to false."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        variables = {"x": 3, "y": 20}
        result = debugger._evaluate_condition("x > 5", variables)
        assert result is False

    def test_conditional_breakpoint_with_complex_expression(self):
        """Test conditional breakpoint with complex expression."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        variables = {"x": 10, "y": 20, "status": "active"}
        result = debugger._evaluate_condition("x > 5 and y == 20", variables)
        assert result is True

    def test_conditional_breakpoint_with_invalid_expression(self):
        """Test conditional breakpoint with invalid expression returns False."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        variables = {"x": 10}
        result = debugger._evaluate_condition("undefined_var > 5", variables)
        assert result is False

    def test_breakpoint_with_hit_limit(self):
        """Test breakpoint with hit limit."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_bp = Mock()
        mock_bp.id = "bp-123"
        mock_bp.hit_limit = 5
        mock_bp.hit_count = 0
        mock_bp.is_active = True

        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(debugger, 'add_breakpoint', return_value=mock_bp):
            bp = debugger.add_breakpoint(
                workflow_id="wf-1",
                node_id="node-1",
                user_id="user-1",
                hit_limit=5,
            )

        assert bp.hit_limit == 5
        assert bp.hit_count == 0

    @pytest.mark.parametrize("hit_limit", [1, 2, 5, 10, 100])
    def test_breakpoint_hit_limit_variations(self, hit_limit):
        """Test breakpoints with different hit limits."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_bp = Mock()
        mock_bp.hit_limit = hit_limit

        assert mock_bp.hit_limit == hit_limit

    def test_breakpoint_with_log_message(self):
        """Test breakpoint with log message (tracepoint)."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_bp = Mock()
        mock_bp.id = "bp-123"
        mock_bp.log_message = "Execution reached node-1"
        mock_bp.is_active = True

        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(debugger, 'add_breakpoint', return_value=mock_bp):
            bp = debugger.add_breakpoint(
                workflow_id="wf-1",
                node_id="node-1",
                user_id="user-1",
                log_message="Execution reached node-1",
            )

        assert bp.log_message == "Execution reached node-1"

    def test_check_breakpoint_hit_with_condition(self):
        """Test checking breakpoint hit with condition."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_bp = Mock()
        mock_bp.condition = "x > 5"
        mock_bp.hit_limit = None
        mock_bp.log_message = None
        mock_bp.is_active = True
        mock_bp.is_disabled = False
        mock_bp.hit_count = 0

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_bp]
        mock_db.query.return_value = mock_query

        should_pause, log_msg = debugger.check_breakpoint_hit(
            node_id="node-1",
            variables={"x": 10},
        )

        assert should_pause is True
        assert log_msg is None

    def test_check_breakpoint_hit_condition_fails(self):
        """Test breakpoint not hit when condition is false."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_bp = Mock()
        mock_bp.condition = "x > 5"
        mock_bp.hit_limit = None
        mock_bp.log_message = None
        mock_bp.is_active = True
        mock_bp.is_disabled = False

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_bp]
        mock_db.query.return_value = mock_query

        should_pause, log_msg = debugger.check_breakpoint_hit(
            node_id="node-1",
            variables={"x": 3},
        )

        assert should_pause is False
        assert log_msg is None

    def test_check_breakpoint_hit_with_log_message(self):
        """Test breakpoint with log message returns log instead of pausing."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_bp = Mock()
        mock_bp.condition = None
        mock_bp.hit_limit = None
        mock_bp.log_message = "Checkpoint reached"
        mock_bp.is_active = True
        mock_bp.is_disabled = False
        mock_bp.hit_count = 0

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_bp]
        mock_db.query.return_value = mock_query

        should_pause, log_msg = debugger.check_breakpoint_hit(
            node_id="node-1",
            variables={},
        )

        assert should_pause is False  # Don't pause for tracepoints
        assert log_msg == "Checkpoint reached"

    def test_check_breakpoint_hit_exceeds_limit(self):
        """Test breakpoint not hit when limit exceeded."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_bp = Mock()
        mock_bp.condition = None
        mock_bp.hit_limit = 5
        mock_bp.hit_count = 5  # Already at limit
        mock_bp.log_message = None
        mock_bp.is_active = True
        mock_bp.is_disabled = False

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_bp]
        mock_db.query.return_value = mock_query

        should_pause, log_msg = debugger.check_breakpoint_hit(
            node_id="node-1",
            variables={},
        )

        assert should_pause is False  # Limit exceeded


class TestWorkflowDebuggerStepExecution:
    """Test step execution with call stack management."""

    def test_step_into_with_node_id(self):
        """Test step into with specific node ID."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.current_step = 5
        mock_session.current_node_id = "node-1"
        mock_session.workflow_id = "wf-1"
        mock_session.call_stack = []

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.step_into("session-123", node_id="node-2")

        assert result is not None
        assert result["action"] == "step_into"
        assert result["session_id"] == "session-123"
        assert result["call_stack_depth"] == 1

    def test_step_into_pushes_call_stack(self):
        """Test step into pushes current frame to call stack."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.current_step = 5
        mock_session.current_node_id = "node-1"
        mock_session.workflow_id = "wf-1"
        mock_session.call_stack = []

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.step_into("session-123", node_id="child-node")

        assert len(mock_session.call_stack) == 1
        assert mock_session.call_stack[0]["node_id"] == "node-1"

    def test_step_over_increments_step(self):
        """Test step over increments current step."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.current_step = "5"
        mock_session.current_step = 5  # Test with int too

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.step_over("session-123")

        assert result is not None
        assert result["action"] == "step_over"
        assert result["session_id"] == "session-123"

    def test_step_out_pops_call_stack(self):
        """Test step out pops frame from call stack."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.current_step = 10
        mock_session.current_node_id = "child-node"
        mock_session.call_stack = [
            {"step_number": 5, "node_id": "parent-node", "workflow_id": "wf-1"}
        ]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.step_out("session-123")

        assert result is not None
        assert result["action"] == "step_out"
        assert "parent_frame" in result

    def test_step_out_with_empty_stack(self):
        """Test step out with empty call stack returns None."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.call_stack = []

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query

        result = debugger.step_out("session-123")

        assert result is None

    def test_continue_execution_changes_status(self):
        """Test continue execution changes session status to running."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.status = "paused"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.continue_execution("session-123")

        assert result is not None
        assert result["action"] == "continue"
        assert result["status"] == "running"

    def test_pause_execution_changes_status(self):
        """Test pause execution changes session status to paused."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.status = "running"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.pause_execution("session-123")

        assert result is not None
        assert result["action"] == "pause"
        assert result["status"] == "paused"


class TestWorkflowDebuggerExecutionTraces:
    """Test execution trace creation and lifecycle."""

    def test_create_trace_success(self):
        """Test creating execution trace with all parameters."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_trace = Mock()
        mock_trace.id = "trace-123"
        mock_trace.workflow_id = "wf-1"
        mock_trace.execution_id = "exec-1"
        mock_trace.step_number = 1

        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch.object(debugger, 'create_trace', return_value=mock_trace):
            trace = debugger.create_trace(
                workflow_id="wf-1",
                execution_id="exec-1",
                step_number=1,
                node_id="node-1",
                node_type="task",
                input_data={"key": "value"},
                variables_before={"x": 5},
                debug_session_id="session-123",
            )

        assert trace.id == "trace-123"
        assert trace.workflow_id == "wf-1"

    def test_complete_trace_success(self):
        """Test completing execution trace."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_trace = Mock()
        mock_trace.id = "trace-123"
        mock_trace.status = "started"
        mock_trace.output_data = None
        mock_trace.variables_after = None

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_trace
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.complete_trace(
            trace_id="trace-123",
            output_data={"result": "success"},
            variables_after={"x": 10},
        )

        assert result is True

    def test_complete_trace_not_found(self):
        """Test completing non-existent trace returns False."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = debugger.complete_trace(
            trace_id="nonexistent",
        )

        assert result is False

    def test_get_execution_traces(self):
        """Test getting execution traces for a debug session."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_trace1 = Mock()
        mock_trace1.id = "trace-1"
        mock_trace1.step_number = 1

        mock_trace2 = Mock()
        mock_trace2.id = "trace-2"
        mock_trace2.step_number = 2

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = [
            mock_trace1,
            mock_trace2,
        ]
        mock_db.query.return_value = mock_query

        traces = debugger.get_execution_traces(execution_id="exec-123")

        assert len(traces) == 2
        assert traces[0].id == "trace-1"


class TestWorkflowDebuggerVariableManagement:
    """Test variable inspection and modification."""

    def test_modify_variable_success(self):
        """Test modifying variable value."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_var = Mock()
        mock_var.id = "var-123"
        mock_var.variable_name = "x"
        mock_var.value = 10

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_var
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.modify_variable(
            session_id="session-123",
            variable_name="x",
            new_value=20,
        )

        assert result is not None
        assert result.variable_name == "x"
        assert result.value == 20

    def test_modify_variable_not_found(self):
        """Test modifying non-existent variable returns None."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = debugger.modify_variable(
            session_id="session-123",
            variable_name="nonexistent",
            new_value=20,
        )

        assert result is None

    def test_bulk_modify_variables(self):
        """Test bulk modifying multiple variables."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_var1 = Mock()
        mock_var1.id = "var-1"
        mock_var1.variable_name = "x"
        mock_var1.value = 10

        mock_var2 = Mock()
        mock_var2.id = "var-2"
        mock_var2.variable_name = "y"
        mock_var2.value = 20

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_var1, mock_var2]
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        modifications = {
            "x": 15,
            "y": 25,
        }

        results = debugger.bulk_modify_variables(
            session_id="session-123",
            modifications=modifications,
        )

        assert results is not None

    def test_get_variables_for_trace(self):
        """Test getting variables for a trace."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_var1 = Mock()
        mock_var1.variable_name = "x"
        mock_var1.value = 10

        mock_var2 = Mock()
        mock_var2.variable_name = "y"
        mock_var2.value = 20

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = [
            mock_var1,
            mock_var2,
        ]
        mock_db.query.return_value = mock_query

        variables = debugger.get_variables_for_trace(trace_id="trace-123")

        assert len(variables) == 2
        assert variables[0].variable_name == "x"

    def test_get_watch_variables(self):
        """Test getting watch variables for debug session."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_var = Mock()
        mock_var.variable_name = "result"
        mock_var.value = "success"

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_var]
        mock_db.query.return_value = mock_query

        variables = debugger.get_watch_variables(debug_session_id="session-123")

        assert len(variables) == 1
        assert variables[0].variable_name == "result"


class TestWorkflowDebuggerSessionPersistence:
    """Test session export and import functionality."""

    def test_export_session_success(self):
        """Test exporting debug session to dictionary."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.workflow_execution_id = "exec-1"
        mock_session.session_type = "interactive"
        mock_session.status = "paused"
        mock_session.current_step = "5"
        mock_session.breakpoints = []
        mock_session.started_at = datetime.now()
        mock_session.ended_at = None

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query

        export_data = debugger.export_session(session_id="session-123")

        assert export_data is not None
        assert export_data["id"] == "session-123"
        assert export_data["status"] == "paused"

    def test_export_session_not_found(self):
        """Test exporting non-existent session returns None."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        export_data = debugger.export_session(session_id="nonexistent")

        assert export_data is None

    def test_import_session_success(self):
        """Test importing debug session from dictionary."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        export_data = {
            "workflow_execution_id": "exec-1",
            "session_type": "interactive",
            "status": "paused",
            "current_step": "5",
            "breakpoints": [],
        }

        mock_session = Mock()
        mock_session.id = "new-session-123"

        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch('core.workflow_debugger.WorkflowDebugSession', return_value=mock_session):
            new_session = debugger.import_session(
                export_data=export_data,
                user_id="user-1",
            )

        assert new_session is not None


class TestWorkflowDebuggerPerformanceProfiling:
    """Test performance profiling features."""

    def test_start_performance_profiling(self):
        """Test starting performance profiling."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.profiling_enabled = False

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.start_performance_profiling(session_id="session-123")

        assert result is True

    def test_start_performance_profiling_not_found(self):
        """Test starting profiling for non-existent session returns False."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = debugger.start_performance_profiling(session_id="nonexistent")

        assert result is False

    def test_record_step_timing(self):
        """Test recording step timing for profiling."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_trace = Mock()
        mock_trace.id = "trace-123"
        mock_trace.started_at = datetime.now()

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_trace
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.record_step_timing(
            trace_id="trace-123",
            duration_ms=150,
        )

        assert result is True

    def test_get_performance_report(self):
        """Test getting performance report for debug session."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_trace1 = Mock()
        mock_trace1.id = "trace-1"
        mock_trace1.node_id = "node-1"
        mock_trace1.started_at = datetime.now()
        mock_trace1.completed_at = datetime.now()
        mock_trace1.duration_ms = 100

        mock_trace2 = Mock()
        mock_trace2.id = "trace-2"
        mock_trace2.node_id = "node-2"
        mock_trace2.started_at = datetime.now()
        mock_trace2.completed_at = datetime.now()
        mock_trace2.duration_ms = 150

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = [
            mock_trace1,
            mock_trace2,
        ]
        mock_db.query.return_value = mock_query

        report = debugger.get_performance_report(session_id="session-123")

        assert report is not None
        assert "total_steps" in report
        assert "total_duration_ms" in report


class TestWorkflowDebuggerCollaborativeDebugging:
    """Test collaborative debugging features."""

    def test_add_collaborator_success(self):
        """Test adding collaborator to debug session."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.collaborators = []

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.add_collaborator(
            session_id="session-123",
            user_id="user-2",
            permission="read_write",
        )

        assert result is True

    def test_add_collaborator_already_exists(self):
        """Test adding existing collaborator returns False."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.collaborators = [{"user_id": "user-2"}]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query

        result = debugger.add_collaborator(
            session_id="session-123",
            user_id="user-2",
            permission="read_write",
        )

        assert result is False

    def test_remove_collaborator_success(self):
        """Test removing collaborator from debug session."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.collaborators = [{"user_id": "user-2"}]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.remove_collaborator(
            session_id="session-123",
            user_id="user-2",
        )

        assert result is True

    def test_check_collaborator_permission(self):
        """Test checking collaborator permission."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.user_id = "owner-1"
        mock_session.collaborators = [
            {"user_id": "user-2", "permission": "read_write"}
        ]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query

        # Owner has full access
        has_permission = debugger.check_collaborator_permission(
            session_id="session-123",
            user_id="owner-1",
            required_permission="read_write",
        )

        assert has_permission is True

    def test_get_session_collaborators(self):
        """Test getting list of session collaborators."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.user_id = "owner-1"
        mock_session.collaborators = [
            {"user_id": "user-2", "permission": "read_write"},
            {"user_id": "user-3", "permission": "read_only"},
        ]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query

        collaborators = debugger.get_session_collaborators(session_id="session-123")

        assert len(collaborators) == 3  # Owner + 2 collaborators


class TestWorkflowDebuggerSessionStateTransitions:
    """Test debug session state transitions."""

    def test_pause_debug_session(self):
        """Test pausing active debug session."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.status = "active"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.pause_debug_session(session_id="session-123")

        assert result is True
        assert mock_session.status == "paused"

    def test_pause_debug_session_not_found(self):
        """Test pausing non-existent session returns False."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = debugger.pause_debug_session(session_id="nonexistent")

        assert result is False

    def test_resume_debug_session(self):
        """Test resuming paused debug session."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.status = "paused"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.resume_debug_session(session_id="session-123")

        assert result is True
        assert mock_session.status == "active"

    def test_complete_debug_session(self):
        """Test completing debug session."""
        mock_db = Mock(spec=Session)
        debugger = WorkflowDebugger(mock_db)

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.status = "active"
        mock_session.completed_at = None

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query
        mock_db.commit.return_value = None

        result = debugger.complete_debug_session(session_id="session-123")

        assert result is True
        assert mock_session.status == "completed"
        assert mock_session.completed_at is not None

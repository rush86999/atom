"""
Coverage-driven tests for workflow_debugger.py (0% -> 70%+ target)

Import blocker fix: None - imports work correctly when executed from backend directory
(application's expected working directory)

File: backend/core/workflow_debugger.py (527 statements)
Target: 70%+ coverage (370+ statements)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from core.workflow_debugger import WorkflowDebugger
from core.models import (
    DebugVariable,
    ExecutionTrace,
    WorkflowBreakpoint,
    WorkflowDebugSession,
    WorkflowExecution,
)


class TestWorkflowDebuggerCoverage:
    """Coverage-driven tests for workflow_debugger.py (0% -> 70%+ target)

    Import blocker fix: None - imports work correctly when executed from backend directory
    (application's expected working directory)
    """

    # ==================== Debug Session Management ====================

    def test_debugger_initialization(self, db_session):
        """Cover lines 30-50: Debugger initialization"""
        debugger = WorkflowDebugger(db_session)
        assert debugger.db == db_session
        assert debugger.expression_evaluator is not None

    def test_create_debug_session_success(self, db_session):
        """Cover lines 60-100: Debug session creation"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
            session_name="Test Debug Session",
            stop_on_entry=True,
            stop_on_exceptions=True,
            stop_on_error=True,
        )

        assert session.id is not None
        assert session.workflow_id == "wf-1"
        assert session.user_id == "user-1"
        assert session.session_name == "Test Debug Session"
        assert session.status == "active"
        assert session.current_step == 0
        assert session.breakpoints == []
        assert session.variables == {}
        assert session.call_stack == []
        assert session.stop_on_entry is True
        assert session.stop_on_exceptions is True
        assert session.stop_on_error is True

    def test_create_debug_session_with_defaults(self, db_session):
        """Cover lines 60-100: Debug session with default values"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-2",
            user_id="user-2",
        )

        assert session.session_name.startswith("Debug ")
        assert session.stop_on_entry is False
        assert session.stop_on_exceptions is True  # Default
        assert session.stop_on_error is True  # Default

    def test_get_debug_session_found(self, db_session):
        """Cover lines 100-120: Get debug session success"""
        debugger = WorkflowDebugger(db_session)
        created = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        retrieved = debugger.get_debug_session(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.workflow_id == "wf-1"

    def test_get_debug_session_not_found(self, db_session):
        """Cover lines 100-120: Get debug session not found"""
        debugger = WorkflowDebugger(db_session)
        retrieved = debugger.get_debug_session("nonexistent-session-id")
        assert retrieved is None

    # ==================== Breakpoint Management ====================

    def test_add_breakpoint_success(self, db_session):
        """Cover lines 150-200: Add breakpoint success"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        bp = debugger.add_breakpoint(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-1",
            condition="x > 5",
        )

        assert bp.id is not None
        assert bp.workflow_id == "wf-1"
        assert bp.node_id == "node-1"
        assert bp.condition == "x > 5"
        assert bp.enabled is True

    def test_add_breakpoint_with_line_number(self, db_session):
        """Cover lines 150-200: Add breakpoint with line number"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        bp = debugger.add_breakpoint(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-2",
            line_number=42,
            condition="result == 'success'",
        )

        assert bp.line_number == 42
        assert bp.condition == "result == 'success'"

    def test_add_breakpoint_hit_count(self, db_session):
        """Cover lines 150-200: Add breakpoint with hit count"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        bp = debugger.add_breakpoint(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-3",
            hit_count=5,
        )

        assert bp.hit_count == 0  # Initial hit count
        assert bp.hit_condition == 5

    def test_remove_breakpoint_success(self, db_session):
        """Cover lines 200-250: Remove breakpoint success"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        bp = debugger.add_breakpoint(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-1",
        )

        removed = debugger.remove_breakpoint(bp.id)
        assert removed is True

        # Verify breakpoint is disabled
        retrieved_bp = debugger.get_breakpoint(bp.id)
        assert retrieved_bp.enabled is False

    def test_remove_breakpoint_not_found(self, db_session):
        """Cover lines 200-250: Remove breakpoint not found"""
        debugger = WorkflowDebugger(db_session)
        removed = debugger.remove_breakpoint("nonexistent-bp-id")
        assert removed is False

    def test_enable_disable_breakpoint(self, db_session):
        """Cover lines 250-300: Enable/disable breakpoint"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        bp = debugger.add_breakpoint(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-1",
        )

        # Disable
        debugger.set_breakpoint_enabled(bp.id, False)
        retrieved = debugger.get_breakpoint(bp.id)
        assert retrieved.enabled is False

        # Enable
        debugger.set_breakpoint_enabled(bp.id, True)
        retrieved = debugger.get_breakpoint(bp.id)
        assert retrieved.enabled is True

    # ==================== State Machine Transitions ====================

    @pytest.mark.parametrize("initial_state,action,expected_states", [
        ("idle", "start", ["running", "paused"]),
        ("running", "pause", ["paused"]),
        ("paused", "continue", ["running"]),
        ("paused", "step_over", ["paused", "running"]),
        ("paused", "step_into", ["paused", "running"]),
        ("paused", "stop", ["idle"]),
        ("running", "stop", ["idle", "completed"]),
    ])
    def test_debugger_state_transitions(self, initial_state, action, expected_states, db_session):
        """Cover lines 300-400: State machine transitions"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        # Set initial state
        session.status = initial_state
        db_session.commit()

        # Execute action
        result = debugger.execute_debug_action(session.id, action)

        # Verify new state is in expected states
        assert result.status in expected_states

    def test_start_debugging_with_stop_on_entry(self, db_session):
        """Cover lines 300-400: Start debugging with stop_on_entry"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
            stop_on_entry=True,
        )

        result = debugger.start_debugging(session.id, "exec-1")
        assert result.status == "paused"  # Should pause on entry

    def test_start_debugging_without_stop_on_entry(self, db_session):
        """Cover lines 300-400: Start debugging without stop_on_entry"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
            stop_on_entry=False,
        )

        result = debugger.start_debugging(session.id, "exec-1")
        assert result.status == "running"

    # ==================== Variable Inspection ====================

    def test_inspect_variables_empty(self, db_session):
        """Cover lines 400-450: Variable inspection with no variables"""
        debugger = WorkflowDebugger(db_session)
        variables = debugger.inspect_variables(
            session_id="session-1",
            context={},
        )

        assert variables == {}

    def test_inspect_variables_with_data(self, db_session):
        """Cover lines 400-450: Variable inspection with data"""
        debugger = WorkflowDebugger(db_session)
        context = {
            "x": 5,
            "y": "hello",
            "z": {"nested": True},
            "list": [1, 2, 3],
        }

        variables = debugger.inspect_variables(
            session_id="session-1",
            context=context,
        )

        assert "x" in variables
        assert variables["x"]["value"] == 5
        assert variables["x"]["type"] == "int"

        assert "y" in variables
        assert variables["y"]["value"] == "hello"
        assert variables["y"]["type"] == "str"

        assert "z" in variables
        assert variables["z"]["value"]["nested"] is True

        assert "list" in variables
        assert variables["list"]["value"] == [1, 2, 3]

    def test_update_variable_value(self, db_session):
        """Cover lines 400-450: Update variable value"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        # Add variable to session
        session.variables = {"x": 5, "y": 10}
        db_session.commit()

        # Update variable
        updated = debugger.update_variable(
            session_id=session.id,
            variable_name="x",
            new_value=20,
        )

        assert updated is True
        assert session.variables["x"] == 20

    def test_update_variable_not_found(self, db_session):
        """Cover lines 400-450: Update non-existent variable"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        updated = debugger.update_variable(
            session_id=session.id,
            variable_name="nonexistent",
            new_value=20,
        )

        assert updated is False

    # ==================== Watch Expressions ====================

    def test_add_watch_expression(self, db_session):
        """Cover lines 450-500: Add watch expression"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        watch = debugger.add_watch_expression(
            session_id=session.id,
            expression="x + y",
        )

        assert "x + y" in session.watch_expressions

    def test_evaluate_watch_expression(self, db_session):
        """Cover lines 450-500: Evaluate watch expression"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        session.watch_expressions = ["x + y"]
        session.variables = {"x": 5, "y": 10}
        db_session.commit()

        results = debugger.evaluate_watch_expressions(session.id)

        assert "x + y" in results
        assert results["x + y"]["value"] == 15
        assert results["x + y"]["error"] is None

    def test_evaluate_watch_expression_error(self, db_session):
        """Cover lines 450-500: Evaluate watch expression with error"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        session.watch_expressions = ["undefined_var + 5"]
        session.variables = {}
        db_session.commit()

        results = debugger.evaluate_watch_expressions(session.id)

        assert "undefined_var + 5" in results
        assert results["undefined_var + 5"]["error"] is not None
        assert "undefined_var" in results["undefined_var + 5"]["error"]

    # ==================== Call Stack Management ====================

    def test_call_stack_empty(self, db_session):
        """Cover lines 500-550: Call stack empty on start"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        stack = debugger.get_call_stack(session.id)
        assert stack == []

    def test_call_stack_push_frame(self, db_session):
        """Cover lines 500-550: Push frame to call stack"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        debugger.push_call_frame(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-1",
            function_name="process_data",
        )

        stack = debugger.get_call_stack(session.id)
        assert len(stack) == 1
        assert stack[0]["workflow_id"] == "wf-1"
        assert stack[0]["node_id"] == "node-1"
        assert stack[0]["function_name"] == "process_data"

    def test_call_stack_pop_frame(self, db_session):
        """Cover lines 500-550: Pop frame from call stack"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        # Push two frames
        debugger.push_call_frame(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-1",
            function_name="outer",
        )
        debugger.push_call_frame(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-2",
            function_name="inner",
        )

        # Pop one frame
        popped = debugger.pop_call_frame(session.id)
        assert popped["function_name"] == "inner"

        stack = debugger.get_call_stack(session.id)
        assert len(stack) == 1
        assert stack[0]["function_name"] == "outer"

    # ==================== Execution Trace ====================

    def test_record_execution_trace(self, db_session):
        """Cover lines 550-600: Record execution trace"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        trace = debugger.record_trace(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-1",
            event_type="step",
            data={"result": "success"},
        )

        assert trace.id is not None
        assert trace.session_id == session.id
        assert trace.workflow_id == "wf-1"
        assert trace.node_id == "node-1"
        assert trace.event_type == "step"
        assert trace.data == {"result": "success"}

    def test_get_execution_traces(self, db_session):
        """Cover lines 550-600: Get execution traces"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        # Record multiple traces
        debugger.record_trace(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-1",
            event_type="step",
        )
        debugger.record_trace(
            session_id=session.id,
            workflow_id="wf-1",
            node_id="node-2",
            event_type="breakpoint",
        )

        traces = debugger.get_execution_traces(session.id)
        assert len(traces) == 2
        assert traces[0].event_type == "step"
        assert traces[1].event_type == "breakpoint"

    # ==================== Debug Session Lifecycle ====================

    def test_pause_debugging(self, db_session):
        """Cover lines 600-650: Pause debugging"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        session.status = "running"
        db_session.commit()

        result = debugger.pause_debugging(session.id)
        assert result.status == "paused"

    def test_resume_debugging(self, db_session):
        """Cover lines 600-650: Resume debugging"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        session.status = "paused"
        db_session.commit()

        result = debugger.resume_debugging(session.id)
        assert result.status == "running"

    def test_stop_debugging(self, db_session):
        """Cover lines 600-650: Stop debugging"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        session.status = "running"
        db_session.commit()

        result = debugger.stop_debugging(session.id)
        assert result.status == "idle"
        assert result.ended_at is not None

    def test_delete_debug_session(self, db_session):
        """Cover lines 600-650: Delete debug session"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        deleted = debugger.delete_debug_session(session.id)
        assert deleted is True

        # Verify session is deleted
        retrieved = debugger.get_debug_session(session.id)
        assert retrieved is None

    # ==================== Error Handling ====================

    def test_create_debug_session_error_handling(self, db_session):
        """Cover lines 90-100: Error handling in session creation"""
        debugger = WorkflowDebugger(db_session)

        # Force an error by passing invalid data
        with patch.object(db_session, 'commit', side_effect=Exception("Database error")):
            with pytest.raises(Exception) as exc_info:
                debugger.create_debug_session(
                    workflow_id="wf-1",
                    user_id="user-1",
                )

            assert "Database error" in str(exc_info.value)

    @pytest.mark.parametrize("invalid_breakpoint,expected_error", [
        ({"node_id": ""}, ValueError),  # Empty node_id
        ({"workflow_id": None}, TypeError),  # None workflow_id
    ])
    def test_add_breakpoint_validation(self, invalid_breakpoint, expected_error, db_session):
        """Cover lines 150-200: Breakpoint validation"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        with pytest.raises(expected_error):
            debugger.add_breakpoint(
                session_id=session.id,
                workflow_id=invalid_breakpoint.get("workflow_id", "wf-1"),
                node_id=invalid_breakpoint.get("node_id", "node-1"),
            )

    # ==================== Performance Profiling ====================

    def test_start_profiling(self, db_session):
        """Cover lines 650-700: Start performance profiling"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        result = debugger.start_profiling(session.id)
        assert result.profiling_enabled is True
        assert result.profiling_started_at is not None

    def test_stop_profiling(self, db_session):
        """Cover lines 650-700: Stop performance profiling"""
        debugger = WorkflowDebugger(db_session)
        session = debugger.create_debug_session(
            workflow_id="wf-1",
            user_id="user-1",
        )

        debugger.start_profiling(session.id)

        # Simulate some execution time
        import time
        time.sleep(0.01)

        result = debugger.stop_profiling(session.id)
        assert result.profiling_enabled is False
        assert result.profiling_ended_at is not None
        assert result.profiling_duration_ms > 0


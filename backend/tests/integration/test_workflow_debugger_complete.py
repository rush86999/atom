"""
Integration tests for WorkflowDebugger

Comprehensive integration tests covering complete debugging workflow lifecycle:
- Debug session management (create, pause, resume, close)
- Breakpoint management (add, remove, enable, disable, conditional)
- Step execution control (step over, into, out, continue)
- Variable inspection and modification
- Execution trace recording
- Error diagnostics at breakpoints

Target: 50%+ coverage of workflow_debugger.py (264+ of 527 lines)
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import uuid

from core.workflow_debugger import WorkflowDebugger
from core.models import (
    WorkflowDebugSession,
    WorkflowBreakpoint,
    ExecutionTrace,
    DebugVariable,
    WorkflowExecution,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Create a real database session for integration testing."""
    from core.database import get_db_session
    with get_db_session() as db:
        yield db
        # Cleanup is automatic via context manager


@pytest.fixture
def workflow_debugger(db_session):
    """Create a workflow debugger with real database session."""
    return WorkflowDebugger(db=db_session)


@pytest.fixture
def sample_workflow_id():
    """Sample workflow ID for testing."""
    return f"wf-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return f"user-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sample_execution_id():
    """Sample execution ID for testing."""
    return f"exec-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sample_node_id():
    """Sample node ID for testing."""
    return f"node-test-{uuid.uuid4().hex[:8]}"


# ============================================================================
# Debug Session Management Tests
# ============================================================================

class TestDebugSessionManagement:
    """Integration tests for debug session lifecycle management."""

    def test_create_debug_session_with_all_parameters(self, workflow_debugger,
                                                       sample_workflow_id, sample_user_id):
        """Test creating a debug session with all parameters."""
        execution_id = f"exec-{uuid.uuid4().hex[:8]}"
        session_name = "Test Debug Session"

        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id,
            execution_id=execution_id,
            session_name=session_name,
            stop_on_entry=True,
            stop_on_exceptions=False,
            stop_on_error=False,
        )

        assert session is not None
        assert session.id is not None
        assert session.workflow_id == sample_workflow_id
        assert session.user_id == sample_user_id
        assert session.execution_id == execution_id
        assert session.session_name == session_name
        assert session.status == "active"
        assert session.current_step == 0
        assert session.stop_on_entry is True
        assert session.stop_on_exceptions is False
        assert session.stop_on_error is False

    def test_create_debug_session_default_parameters(self, workflow_debugger,
                                                      sample_workflow_id, sample_user_id):
        """Test creating debug session with default parameters."""
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id,
        )

        assert session is not None
        assert session.status == "active"
        assert session.current_step == 0
        assert session.stop_on_entry is False
        assert session.stop_on_exceptions is True
        assert session.stop_on_error is True
        assert session.session_name is not None  # Auto-generated

    def test_get_active_sessions(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test retrieving all active sessions for a workflow."""
        # Create multiple sessions
        session1 = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id,
            session_name="Session 1"
        )
        session2 = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id,
            session_name="Session 2"
        )

        # Get active sessions
        active_sessions = workflow_debugger.get_active_debug_sessions(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        assert len(active_sessions) >= 2
        session_ids = [s.id for s in active_sessions]
        assert session1.id in session_ids
        assert session2.id in session_ids

        # All should be active
        for session in active_sessions:
            assert session.status == "active"

    def test_pause_and_resume_session(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test pausing and resuming a debug session."""
        # Create session
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )
        assert session.status == "active"

        # Pause session
        pause_result = workflow_debugger.pause_debug_session(session.id)
        assert pause_result is True

        # Verify paused
        paused_session = workflow_debugger.get_debug_session(session.id)
        assert paused_session.status == "paused"

        # Resume session
        resume_result = workflow_debugger.resume_debug_session(session.id)
        assert resume_result is True

        # Verify resumed
        resumed_session = workflow_debugger.get_debug_session(session.id)
        assert resumed_session.status == "active"

    def test_close_session(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test closing a debug session."""
        # Create session
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )
        assert session.status == "active"

        # Close session
        close_result = workflow_debugger.complete_debug_session(session.id)
        assert close_result is True

        # Verify closed
        closed_session = workflow_debugger.get_debug_session(session.id)
        assert closed_session.status == "completed"
        assert closed_session.completed_at is not None

    def test_close_nonexistent_session(self, workflow_debugger):
        """Test closing a session that doesn't exist."""
        result = workflow_debugger.complete_debug_session("nonexistent-session-id")
        assert result is False


# ============================================================================
# Breakpoint Management Tests
# ============================================================================

class TestBreakpointManagement:
    """Integration tests for breakpoint management."""

    def test_add_breakpoint(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test adding a breakpoint to a workflow node."""
        node_id = f"node-{uuid.uuid4().hex[:8]}"

        breakpoint = workflow_debugger.add_breakpoint(
            workflow_id=sample_workflow_id,
            node_id=node_id,
            user_id=sample_user_id
        )

        assert breakpoint is not None
        assert breakpoint.id is not None
        assert breakpoint.workflow_id == sample_workflow_id
        assert breakpoint.node_id == node_id
        assert breakpoint.is_active is True
        assert breakpoint.is_disabled is False
        assert breakpoint.breakpoint_type == "node"
        assert breakpoint.hit_count == 0

    def test_remove_breakpoint(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test removing a breakpoint."""
        # Add breakpoint
        node_id = f"node-{uuid.uuid4().hex[:8]}"
        breakpoint = workflow_debugger.add_breakpoint(
            workflow_id=sample_workflow_id,
            node_id=node_id,
            user_id=sample_user_id
        )

        # Remove breakpoint
        remove_result = workflow_debugger.remove_breakpoint(
            breakpoint_id=breakpoint.id,
            user_id=sample_user_id
        )
        assert remove_result is True

    def test_remove_nonexistent_breakpoint(self, workflow_debugger, sample_user_id):
        """Test removing a breakpoint that doesn't exist."""
        result = workflow_debugger.remove_breakpoint(
            breakpoint_id="nonexistent-bp-id",
            user_id=sample_user_id
        )
        assert result is False

    def test_enable_disable_breakpoint(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test enabling and disabling a breakpoint."""
        # Add breakpoint
        node_id = f"node-{uuid.uuid4().hex[:8]}"
        breakpoint = workflow_debugger.add_breakpoint(
            workflow_id=sample_workflow_id,
            node_id=node_id,
            user_id=sample_user_id
        )
        assert breakpoint.is_disabled is False

        # Disable breakpoint
        disabled_state = workflow_debugger.toggle_breakpoint(
            breakpoint_id=breakpoint.id,
            user_id=sample_user_id
        )
        assert disabled_state is False  # Now disabled

        # Verify
        disabled_bp = workflow_debugger.db.query(WorkflowBreakpoint).filter(
            WorkflowBreakpoint.id == breakpoint.id
        ).first()
        assert disabled_bp.is_disabled is True

        # Enable breakpoint
        enabled_state = workflow_debugger.toggle_breakpoint(
            breakpoint_id=breakpoint.id,
            user_id=sample_user_id
        )
        assert enabled_state is True  # Now enabled

    def test_conditional_breakpoint(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test adding a conditional breakpoint."""
        node_id = f"node-{uuid.uuid4().hex[:8]}"
        condition = "x > 10"
        hit_limit = 5

        breakpoint = workflow_debugger.add_breakpoint(
            workflow_id=sample_workflow_id,
            node_id=node_id,
            user_id=sample_user_id,
            condition=condition,
            hit_limit=hit_limit
        )

        assert breakpoint.condition == condition
        assert breakpoint.hit_limit == hit_limit
        assert breakpoint.hit_count == 0

    def test_breakpoint_hit_detection(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test that execution pauses at breakpoint."""
        node_id = f"node-{uuid.uuid4().hex[:8]}"

        # Add breakpoint
        breakpoint = workflow_debugger.add_breakpoint(
            workflow_id=sample_workflow_id,
            node_id=node_id,
            user_id=sample_user_id
        )

        # Check if breakpoint should trigger
        variables = {"x": 10, "y": 20}
        should_pause, log_message = workflow_debugger.check_breakpoint_hit(
            node_id=node_id,
            variables=variables
        )

        assert should_pause is True
        assert log_message is None

        # Verify hit count incremented
        updated_bp = workflow_debugger.db.query(WorkflowBreakpoint).filter(
            WorkflowBreakpoint.id == breakpoint.id
        ).first()
        assert updated_bp.hit_count == 1

    def test_breakpoint_hit_limit(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test that breakpoint respects hit limit."""
        node_id = f"node-{uuid.uuid4().hex[:8]}"
        hit_limit = 3

        # Add breakpoint with hit limit
        breakpoint = workflow_debugger.add_breakpoint(
            workflow_id=sample_workflow_id,
            node_id=node_id,
            user_id=sample_user_id,
            hit_limit=hit_limit
        )

        # Hit breakpoint up to limit
        for i in range(hit_limit):
            should_pause, _ = workflow_debugger.check_breakpoint_hit(
                node_id=node_id,
                variables={}
            )
            assert should_pause is True, f"Should pause on hit {i+1}"

        # One more time should not pause
        should_pause, _ = workflow_debugger.check_breakpoint_hit(
            node_id=node_id,
            variables={}
        )
        assert should_pause is False, "Should not pause after hit limit"

    def test_get_breakpoints(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test retrieving all breakpoints for a workflow."""
        # Add multiple breakpoints
        node1 = f"node-{uuid.uuid4().hex[:8]}"
        node2 = f"node-{uuid.uuid4().hex[:8]}"

        bp1 = workflow_debugger.add_breakpoint(
            workflow_id=sample_workflow_id,
            node_id=node1,
            user_id=sample_user_id
        )
        bp2 = workflow_debugger.add_breakpoint(
            workflow_id=sample_workflow_id,
            node_id=node2,
            user_id=sample_user_id
        )

        # Get all breakpoints
        breakpoints = workflow_debugger.get_breakpoints(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id,
            active_only=True
        )

        breakpoint_ids = [bp.id for bp in breakpoints]
        assert bp1.id in breakpoint_ids
        assert bp2.id in breakpoint_ids


# ============================================================================
# Step Execution Control Tests
# ============================================================================

class TestStepExecutionControl:
    """Integration tests for step execution control."""

    def test_step_over(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test stepping over to next sibling."""
        # Create session
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )
        initial_step = session.current_step

        # Step over
        result = workflow_debugger.step_over(session.id)

        assert result is not None
        assert result["action"] == "step_over"
        assert result["current_step"] == initial_step + 1

        # Verify session updated
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert updated_session.current_step == initial_step + 1

    def test_step_into_nested_workflow(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test stepping into a nested workflow."""
        # Create session
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )
        parent_node_id = f"node-{uuid.uuid4().hex[:8]}"
        child_node_id = f"node-{uuid.uuid4().hex[:8]}"

        # Set current node
        session.current_node_id = parent_node_id
        workflow_debugger.db.commit()

        # Step into child workflow
        result = workflow_debugger.step_into(
            session_id=session.id,
            node_id=child_node_id
        )

        assert result is not None
        assert result["action"] == "step_into"
        assert result["call_stack_depth"] == 1
        assert result["current_node_id"] == child_node_id

        # Verify call stack
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert len(updated_session.call_stack) == 1
        assert updated_session.call_stack[0]["node_id"] == parent_node_id

    def test_step_out_to_parent_workflow(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test stepping out to parent workflow."""
        # Create session with call stack
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        # Manually build a call stack
        parent_frame = {
            "step_number": 5,
            "node_id": f"node-{uuid.uuid4().hex[:8]}",
            "workflow_id": sample_workflow_id
        }
        session.call_stack = [parent_frame]
        session.current_step = 10
        workflow_debugger.db.commit()

        # Step out
        result = workflow_debugger.step_out(session.id)

        assert result is not None
        assert result["action"] == "step_out"
        assert result["call_stack_depth"] == 0
        assert result["current_step"] == parent_frame["step_number"] + 1

        # Verify call stack is empty
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert len(updated_session.call_stack) == 0

    def test_step_out_empty_stack(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test stepping out with empty call stack."""
        # Create session without call stack
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        # Try to step out with empty stack
        result = workflow_debugger.step_out(session.id)
        assert result is None

    def test_continue_execution(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test continuing execution until next breakpoint."""
        # Create paused session
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )
        workflow_debugger.pause_debug_session(session.id)

        # Continue execution
        result = workflow_debugger.continue_execution(session.id)

        assert result is not None
        assert result["action"] == "continue"
        assert result["status"] == "running"

        # Verify status
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert updated_session.status == "running"

    def test_pause_execution(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test pausing running execution."""
        # Create session
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )
        workflow_debugger.continue_execution(session.id)

        # Pause execution
        result = workflow_debugger.pause_execution(session.id)

        assert result is not None
        assert result["action"] == "pause"
        assert result["status"] == "paused"

        # Verify status
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert updated_session.status == "paused"


# ============================================================================
# Variable Inspection Tests
# ============================================================================

class TestVariableInspection:
    """Integration tests for variable inspection and modification."""

    def test_inspect_variables(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test inspecting variable state at breakpoint."""
        # Create trace
        trace = workflow_debugger.create_trace(
            workflow_id=sample_workflow_id,
            execution_id=f"exec-{uuid.uuid4().hex[:8]}",
            step_number=1,
            node_id=f"node-{uuid.uuid4().hex[:8]}",
            node_type="action",
            input_data={"input": "value"}
        )

        # Create variable snapshots
        var1 = workflow_debugger.create_variable_snapshot(
            trace_id=trace.id,
            variable_name="x",
            variable_path="x",
            variable_type="int",
            value=42
        )

        var2 = workflow_debugger.create_variable_snapshot(
            trace_id=trace.id,
            variable_name="message",
            variable_path="message",
            variable_type="str",
            value="hello"
        )

        # Get variables for trace
        variables = workflow_debugger.get_variables_for_trace(trace.id)

        assert len(variables) == 2
        var_names = {v.variable_name for v in variables}
        assert "x" in var_names
        assert "message" in var_names

    def test_modify_variable(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test modifying a variable at runtime."""
        # Create session with variables
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )
        session.variables = {"x": 10, "y": 20}
        workflow_debugger.db.commit()

        # Modify variable
        modified_var = workflow_debugger.modify_variable(
            session_id=session.id,
            variable_name="x",
            new_value=100
        )

        assert modified_var is not None
        assert modified_var.variable_name == "x"
        assert modified_var.value == 100
        assert modified_var.previous_value == 10
        assert modified_var.is_changed is True

        # Verify session updated
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert updated_session.variables["x"] == 100

    def test_variable_watch(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test watching variables during execution."""
        # Create session
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        # Create trace
        trace = workflow_debugger.create_trace(
            workflow_id=sample_workflow_id,
            execution_id=f"exec-{uuid.uuid4().hex[:8]}",
            step_number=1,
            node_id=f"node-{uuid.uuid4().hex[:8]}",
            node_type="action",
            debug_session_id=session.id
        )

        # Add watch variable
        watch_var = workflow_debugger.create_variable_snapshot(
            trace_id=trace.id,
            debug_session_id=session.id,
            variable_name="counter",
            variable_path="counter",
            variable_type="int",
            value=0,
            is_watch=True
        )

        assert watch_var.is_watch is True

        # Get watch variables
        watch_vars = workflow_debugger.get_watch_variables(session.id)
        assert len(watch_vars) >= 1
        assert any(v.variable_name == "counter" for v in watch_vars)


# ============================================================================
# Execution Tracing Tests
# ============================================================================

class TestExecutionTracing:
    """Integration tests for execution trace recording."""

    def test_record_execution_trace(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test recording execution trace."""
        execution_id = f"exec-{uuid.uuid4().hex[:8]}"

        trace = workflow_debugger.create_trace(
            workflow_id=sample_workflow_id,
            execution_id=execution_id,
            step_number=1,
            node_id=f"node-{uuid.uuid4().hex[:8]}",
            node_type="action",
            input_data={"input": "value"},
            variables_before={"x": 10}
        )

        assert trace is not None
        assert trace.workflow_id == sample_workflow_id
        assert trace.execution_id == execution_id
        assert trace.step_number == 1
        assert trace.status == "started"
        assert trace.input_data == {"input": "value"}
        assert trace.variables_before == {"x": 10}

    def test_complete_trace(self, workflow_debugger, sample_workflow_id):
        """Test completing an execution trace."""
        # Create trace
        trace = workflow_debugger.create_trace(
            workflow_id=sample_workflow_id,
            execution_id=f"exec-{uuid.uuid4().hex[:8]}",
            step_number=1,
            node_id=f"node-{uuid.uuid4().hex[:8]}",
            node_type="action",
            input_data={"input": "value"},
            variables_before={"x": 10}
        )

        # Complete trace
        result = workflow_debugger.complete_trace(
            trace_id=trace.id,
            output_data={"result": "success"},
            variables_after={"x": 20}
        )

        assert result is True

        # Verify trace updated
        completed_trace = workflow_debugger.db.query(ExecutionTrace).filter(
            ExecutionTrace.id == trace.id
        ).first()
        assert completed_trace.status == "completed"
        assert completed_trace.output_data == {"result": "success"}
        assert completed_trace.variables_after == {"x": 20}
        assert completed_trace.duration_ms is not None

    def test_complete_trace_with_error(self, workflow_debugger, sample_workflow_id):
        """Test completing a trace with error."""
        # Create trace
        trace = workflow_debugger.create_trace(
            workflow_id=sample_workflow_id,
            execution_id=f"exec-{uuid.uuid4().hex[:8]}",
            step_number=1,
            node_id=f"node-{uuid.uuid4().hex[:8]}",
            node_type="action"
        )

        # Complete with error
        result = workflow_debugger.complete_trace(
            trace_id=trace.id,
            error_message="Step failed: timeout"
        )

        assert result is True

        # Verify error recorded
        error_trace = workflow_debugger.db.query(ExecutionTrace).filter(
            ExecutionTrace.id == trace.id
        ).first()
        assert error_trace.status == "failed"
        assert error_trace.error_message == "Step failed: timeout"

    def test_get_trace_history(self, workflow_debugger, sample_workflow_id):
        """Test retrieving execution trace history."""
        execution_id = f"exec-{uuid.uuid4().hex[:8]}"

        # Create multiple traces
        trace1 = workflow_debugger.create_trace(
            workflow_id=sample_workflow_id,
            execution_id=execution_id,
            step_number=1,
            node_id=f"node-{uuid.uuid4().hex[:8]}",
            node_type="action"
        )

        trace2 = workflow_debugger.create_trace(
            workflow_id=sample_workflow_id,
            execution_id=execution_id,
            step_number=2,
            node_id=f"node-{uuid.uuid4().hex[:8]}",
            node_type="condition"
        )

        # Get trace history
        traces = workflow_debugger.get_execution_traces(
            execution_id=execution_id,
            limit=10
        )

        assert len(traces) >= 2
        trace_ids = [t.id for t in traces]
        assert trace1.id in trace_ids
        assert trace2.id in trace_ids

    def test_call_stack_tracking(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test nested workflow call stack tracking."""
        # Create session
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        # Simulate nested calls
        parent_node = f"node-{uuid.uuid4().hex[:8]}"
        child_node = f"node-{uuid.uuid4().hex[:8]}"

        # Step into first level
        workflow_debugger.step_into(session.id, parent_node)

        # Step into second level
        workflow_debugger.step_into(session.id, child_node)

        # Verify call stack depth
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert len(updated_session.call_stack) == 2


# ============================================================================
# Error Diagnostics Tests
# ============================================================================

class TestErrorDiagnostics:
    """Integration tests for error diagnostics at breakpoints."""

    def test_error_breakpoint(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test stop_on_error functionality."""
        # Create session with stop_on_error
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id,
            stop_on_error=True
        )

        assert session.stop_on_error is True

    def test_exception_breakpoint(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test stop_on_exceptions functionality."""
        # Create session with stop_on_exceptions disabled
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id,
            stop_on_exceptions=False
        )

        assert session.stop_on_exceptions is False

    def test_error_context_capture(self, workflow_debugger, sample_workflow_id):
        """Test capturing error context at breakpoint."""
        # Create trace with variables
        execution_id = f"exec-{uuid.uuid4().hex[:8]}"
        trace = workflow_debugger.create_trace(
            workflow_id=sample_workflow_id,
            execution_id=execution_id,
            step_number=1,
            node_id=f"node-{uuid.uuid4().hex[:8]}",
            node_type="action",
            variables_before={
                "timeout": 30,
                "retry_count": 3,
                "url": "https://api.example.com"
            }
        )

        # Complete with error
        workflow_debugger.complete_trace(
            trace_id=trace.id,
            error_message="Connection timeout after 30s"
        )

        # Get trace to verify error context captured
        error_trace = workflow_debugger.db.query(ExecutionTrace).filter(
            ExecutionTrace.id == trace.id
        ).first()

        assert error_trace.error_message == "Connection timeout after 30s"
        assert error_trace.status == "failed"
        assert error_trace.variables_before == {
            "timeout": 30,
            "retry_count": 3,
            "url": "https://api.example.com"
        }

    def test_variable_changes_on_error(self, workflow_debugger, sample_workflow_id):
        """Test that variable changes are tracked even on error."""
        # Create trace
        trace = workflow_debugger.create_trace(
            workflow_id=sample_workflow_id,
            execution_id=f"exec-{uuid.uuid4().hex[:8]}",
            step_number=1,
            node_id=f"node-{uuid.uuid4().hex[:8]}",
            node_type="action",
            variables_before={"x": 10, "y": 20, "z": 30}
        )

        # Complete with error and changed variables
        workflow_debugger.complete_trace(
            trace_id=trace.id,
            error_message="Processing failed",
            variables_after={"x": 15, "y": 25}  # z removed
        )

        # Get trace and verify changes tracked
        error_trace = workflow_debugger.db.query(ExecutionTrace).filter(
            ExecutionTrace.id == trace.id
        ).first()

        assert len(error_trace.variable_changes) == 3
        change_types = {c["type"] for c in error_trace.variable_changes}
        assert "changed" in change_types  # x and y
        assert "removed" in change_types  # z


# ============================================================================
# Session Persistence Tests
# ============================================================================

class TestSessionPersistence:
    """Integration tests for session export/import functionality."""

    def test_export_session(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test exporting debug session to JSON."""
        # Create session
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id,
            session_name="Export Test Session"
        )

        # Add breakpoints
        node1 = f"node-{uuid.uuid4().hex[:8]}"
        bp1 = workflow_debugger.add_breakpoint(
            workflow_id=sample_workflow_id,
            node_id=node1,
            user_id=sample_user_id,
            condition="x > 10"
        )

        # Create traces
        execution_id = f"exec-{uuid.uuid4().hex[:8]}"
        trace = workflow_debugger.create_trace(
            workflow_id=sample_workflow_id,
            execution_id=execution_id,
            step_number=1,
            node_id=f"node-{uuid.uuid4().hex[:8]}",
            node_type="action",
            debug_session_id=session.id
        )

        # Export session
        export_data = workflow_debugger.export_session(session.id)

        assert export_data is not None
        assert "session" in export_data
        assert "breakpoints" in export_data
        assert "traces" in export_data
        assert "exported_at" in export_data
        assert export_data["session"]["id"] == session.id
        assert export_data["session"]["workflow_id"] == sample_workflow_id

    def test_import_session(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test importing a previously exported session."""
        # Create export data
        export_data = {
            "session": {
                "workflow_id": sample_workflow_id,
                "user_id": sample_user_id,
                "session_name": "Imported Session",
                "stop_on_entry": True,
                "stop_on_exceptions": False,
                "stop_on_error": False,
                "variables": {"x": 100, "y": 200},
                "call_stack": [{"step": 1, "node": "node_1"}]
            },
            "breakpoints": [],
            "traces": []
        }

        # Import session
        imported_session = workflow_debugger.import_session(
            export_data,
            restore_breakpoints=True,
            restore_variables=True
        )

        assert imported_session is not None
        assert imported_session.id is not None
        assert imported_session.workflow_id == sample_workflow_id
        assert "Imported" in imported_session.session_name

    def test_import_session_with_breakpoints(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test importing session with breakpoint restoration."""
        node_id = f"node-{uuid.uuid4().hex[:8]}"

        export_data = {
            "session": {
                "workflow_id": sample_workflow_id,
                "user_id": sample_user_id,
                "session_name": "Session with BP",
                "stop_on_entry": False,
                "stop_on_exceptions": True,
                "stop_on_error": True,
            },
            "breakpoints": [
                {
                    "node_id": node_id,
                    "condition": "x > 5",
                    "hit_limit": 10,
                    "log_message": None
                }
            ],
            "traces": []
        }

        # Import with breakpoints
        imported_session = workflow_debugger.import_session(
            export_data,
            restore_breakpoints=True
        )

        assert imported_session is not None
        # Verify breakpoint was created
        breakpoints = workflow_debugger.get_breakpoints(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )
        assert len(breakpoints) > 0


# ============================================================================
# Performance Profiling Tests
# ============================================================================

class TestPerformanceProfiling:
    """Integration tests for performance profiling."""

    def test_start_performance_profiling(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test starting performance profiling for a session."""
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        result = workflow_debugger.start_performance_profiling(session.id)

        assert result is True

        # Verify metrics initialized
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert updated_session.performance_metrics is not None
        assert updated_session.performance_metrics["enabled"] is True
        assert "started_at" in updated_session.performance_metrics

    def test_record_step_timing(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test recording step timing data."""
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        # Start profiling
        workflow_debugger.start_performance_profiling(session.id)

        # Record step timing
        node_id = f"node-{uuid.uuid4().hex[:8]}"
        result = workflow_debugger.record_step_timing(
            session_id=session.id,
            node_id=node_id,
            node_type="action",
            duration_ms=150
        )

        assert result is True

        # Verify timing recorded
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert len(updated_session.performance_metrics["step_times"]) == 1
        assert updated_session.performance_metrics["total_duration_ms"] == 150

    def test_get_performance_report(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test generating performance report."""
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        # Start profiling and record some steps
        workflow_debugger.start_performance_profiling(session.id)

        workflow_debugger.record_step_timing(session.id, "node_1", "action", 100)
        workflow_debugger.record_step_timing(session.id, "node_2", "condition", 200)
        workflow_debugger.record_step_timing(session.id, "node_1", "action", 150)

        # Get report
        report = workflow_debugger.get_performance_report(session.id)

        assert report is not None
        assert report["total_duration_ms"] == 450
        assert report["total_steps"] == 3
        assert len(report["slowest_steps"]) <= 10
        assert len(report["slowest_nodes"]) <= 10


# ============================================================================
# Collaborative Debugging Tests
# ============================================================================

class TestCollaborativeDebugging:
    """Integration tests for collaborative debugging features."""

    def test_add_collaborator(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test adding a collaborator to debug session."""
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        collaborator_id = f"user-{uuid.uuid4().hex[:8]}"

        result = workflow_debugger.add_collaborator(
            session_id=session.id,
            user_id=collaborator_id,
            permission="viewer"
        )

        assert result is True

        # Verify collaborator added
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert collaborator_id in updated_session.collaborators
        assert updated_session.collaborators[collaborator_id]["permission"] == "viewer"

    def test_remove_collaborator(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test removing a collaborator."""
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        collaborator_id = f"user-{uuid.uuid4().hex[:8]}"

        # Add collaborator
        workflow_debugger.add_collaborator(
            session_id=session.id,
            user_id=collaborator_id,
            permission="operator"
        )

        # Remove collaborator
        result = workflow_debugger.remove_collaborator(session.id, collaborator_id)

        assert result is True

        # Verify removed
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert collaborator_id not in updated_session.collaborators

    def test_check_collaborator_permission(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test checking collaborator permissions."""
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        collaborator_id = f"user-{uuid.uuid4().hex[:8]}"

        # Add collaborator with operator permission
        workflow_debugger.add_collaborator(
            session_id=session.id,
            user_id=collaborator_id,
            permission="operator"
        )

        # Check permissions
        # Owner should have all permissions
        assert workflow_debugger.check_collaborator_permission(
            session.id, sample_user_id, "owner"
        ) is True

        # Operator should have viewer and operator but not owner
        assert workflow_debugger.check_collaborator_permission(
            session.id, collaborator_id, "viewer"
        ) is True

        assert workflow_debugger.check_collaborator_permission(
            session.id, collaborator_id, "operator"
        ) is True

        assert workflow_debugger.check_collaborator_permission(
            session.id, collaborator_id, "owner"
        ) is False

    def test_get_session_collaborators(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test getting all collaborators for a session."""
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        # Add multiple collaborators
        collab1 = f"user-{uuid.uuid4().hex[:8]}"
        collab2 = f"user-{uuid.uuid4().hex[:8]}"

        workflow_debugger.add_collaborator(session.id, collab1, "viewer")
        workflow_debugger.add_collaborator(session.id, collab2, "operator")

        # Get collaborators
        collaborators = workflow_debugger.get_session_collaborators(session.id)

        assert len(collaborators) >= 2
        collaborator_ids = {c["user_id"] for c in collaborators}
        assert collab1 in collaborator_ids
        assert collab2 in collaborator_ids


# ============================================================================
# Value Preview Tests
# ============================================================================

class TestValuePreviewGeneration:
    """Integration tests for value preview generation."""

    def test_generate_preview_for_none(self, workflow_debugger):
        """Test preview for None value."""
        preview = workflow_debugger._generate_value_preview(None)
        assert preview == "null"

    def test_generate_preview_for_string(self, workflow_debugger):
        """Test preview for string value."""
        preview = workflow_debugger._generate_value_preview("hello world")
        assert preview == "hello world"

    def test_generate_preview_for_number(self, workflow_debugger):
        """Test preview for numeric value."""
        preview = workflow_debugger._generate_value_preview(42)
        assert preview == "42"

    def test_generate_preview_for_boolean(self, workflow_debugger):
        """Test preview for boolean value."""
        preview = workflow_debugger._generate_value_preview(True)
        assert preview == "True"

    def test_generate_preview_for_dict(self, workflow_debugger):
        """Test preview for dict value."""
        preview = workflow_debugger._generate_value_preview({"key": "value"})
        assert "dict" in preview
        assert "keys" in preview

    def test_generate_preview_for_list(self, workflow_debugger):
        """Test preview for list value."""
        preview = workflow_debugger._generate_value_preview([1, 2, 3])
        assert "list" in preview
        assert "items" in preview

    def test_generate_preview_for_set(self, workflow_debugger):
        """Test preview for set value."""
        preview = workflow_debugger._generate_value_preview({1, 2, 3})
        assert "set" in preview
        assert "items" in preview


# ============================================================================
# Bulk Variable Modification Tests
# ============================================================================

class TestBulkVariableModification:
    """Integration tests for bulk variable modification."""

    def test_bulk_modify_variables(self, workflow_debugger, sample_workflow_id, sample_user_id):
        """Test modifying multiple variables at once."""
        session = workflow_debugger.create_debug_session(
            workflow_id=sample_workflow_id,
            user_id=sample_user_id
        )

        # Bulk modify
        modifications = [
            {"variable_name": "x", "new_value": 10},
            {"variable_name": "y", "new_value": 20},
            {"variable_name": "z", "new_value": 30},
        ]

        results = workflow_debugger.bulk_modify_variables(
            session_id=session.id,
            modifications=modifications
        )

        assert len(results) == 3

        # Verify all modified
        updated_session = workflow_debugger.get_debug_session(session.id)
        assert updated_session.variables["x"] == 10
        assert updated_session.variables["y"] == 20
        assert updated_session.variables["z"] == 30


# ============================================================================
# WebSocket Integration Tests
# ============================================================================

class TestWebSocketIntegration:
    """Integration tests for WebSocket integration features."""

    def test_create_trace_stream(self, workflow_debugger):
        """Test creating a trace stream."""
        execution_id = f"exec-{uuid.uuid4().hex[:8]}"
        session_id = f"session-{uuid.uuid4().hex[:8]}"

        stream_id = workflow_debugger.create_trace_stream(
            session_id=session_id,
            execution_id=execution_id
        )

        assert stream_id is not None
        assert "trace_" in stream_id
        assert execution_id in stream_id
        assert session_id in stream_id

    def test_stream_trace_update_no_manager(self, workflow_debugger):
        """Test streaming trace update without WebSocket manager."""
        stream_id = f"trace_exec-123_session-456_abc123"

        result = workflow_debugger.stream_trace_update(
            stream_id=stream_id,
            trace_data={"step": 1, "node_id": "node_001"},
            websocket_manager=None
        )

        # Should return False without manager
        assert result is False

    def test_close_trace_stream(self, workflow_debugger):
        """Test closing a trace stream."""
        stream_id = f"trace_exec-123_session-456_abc123"

        result = workflow_debugger.close_trace_stream(
            stream_id=stream_id,
            websocket_manager=None
        )

        # Should succeed even without manager
        assert result is True

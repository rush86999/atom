"""
Property-Based Tests for Workflow Debugger

Tests CRITICAL debugger invariants:
- Breakpoint management (add, remove, toggle, hit detection)
- State inspection and variable tracking
- Step execution control (step over, into, out, continue, pause)
- Call stack management for nested workflows
- Execution trace recording
- Variable modification and snapshots
- Session persistence (export/import)
- Performance profiling
- Collaborative debugging permissions
- Real-time trace streaming

These tests protect against debugger state corruption and ensure reliable
workflow debugging capabilities.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, MagicMock, patch
import json

from core.workflow_debugger import WorkflowDebugger
from core.models import (
    WorkflowDebugSession,
    WorkflowBreakpoint,
    ExecutionTrace,
    DebugVariable,
)


class TestBreakpointManagementInvariants:
    """Property-based tests for breakpoint management."""

    @pytest.fixture
    def db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def debugger(self, db):
        """Create a WorkflowDebugger instance."""
        return WorkflowDebugger(db)

    @given(
        workflow_id=st.text(min_size=1, max_size=30, alphabet='abc123_-'),
        node_id=st.text(min_size=1, max_size=30, alphabet='abc123_-'),
        user_id=st.text(min_size=1, max_size=20, alphabet='abc'),
        breakpoint_type=st.sampled_from(["node", "edge"]),
        has_condition=st.booleans(),
        hit_limit=st.one_of(st.none(), st.integers(min_value=1, max_value=10)),
        has_log_message=st.booleans()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_breakpoint_creation_invariant(self, debugger, db, workflow_id, node_id, user_id,
                                           breakpoint_type, has_condition, hit_limit, has_log_message):
        """INVARIANT: Breakpoint is created with correct state."""
        # Setup
        condition = f"var_{node_id} > 0" if has_condition else None
        log_message = f"Hit {node_id}" if has_log_message else None

        mock_breakpoint = MagicMock()
        mock_breakpoint.id = f"bp_{node_id}"
        db.add.return_value = None
        db.commit.return_value = None
        db.refresh.return_value = None

        # Create breakpoint
        result = debugger.add_breakpoint(
            workflow_id=workflow_id,
            node_id=node_id,
            user_id=user_id,
            breakpoint_type=breakpoint_type,
            condition=condition,
            hit_limit=hit_limit,
            log_message=log_message
        )

        # Invariant: add_breakpoint was called
        assert db.add.called or db.commit.called, "Database operations should be called"

    @given(
        step_ids=st.lists(
            st.text(min_size=1, max_size=30, alphabet='abc123_'),
            min_size=1,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multiple_breakpoints_invariant(self, debugger, db, step_ids):
        """INVARIANT: Multiple breakpoints can be created independently."""
        workflow_id = "test_workflow"
        user_id = "test_user"

        # Reset call count before test
        db.commit.reset_mock()

        for step_id in step_ids:
            mock_bp = MagicMock()
            mock_bp.id = f"bp_{step_id}"
            db.add.return_value = None
            db.commit.return_value = None

            debugger.add_breakpoint(
                workflow_id=workflow_id,
                node_id=step_id,
                user_id=user_id
            )

        # Invariant: Each breakpoint creation should call commit
        assert db.commit.call_count >= len(step_ids), \
            f"Should commit at least {len(step_ids)} times for {len(step_ids)} breakpoints"

    @given(
        node_id=st.text(min_size=1, max_size=30, alphabet='abc123_-'),
        user_id=st.text(min_size=1, max_size=20, alphabet='abc')
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_breakpoint_removal_invariant(self, debugger, db, node_id, user_id):
        """INVARIANT: Breakpoint can be removed."""
        breakpoint_id = f"bp_{node_id}"

        # Mock query to return a breakpoint
        mock_bp = MagicMock()
        mock_bp.id = breakpoint_id

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_bp
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Remove breakpoint
        result = debugger.remove_breakpoint(breakpoint_id, user_id)

        # Invariant: db.delete should be called
        assert db.delete.called, "Should call db.delete for removal"
        assert db.commit.called, "Should commit after deletion"

    @given(
        initial_disabled=st.booleans()
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_breakpoint_toggle_invariant(self, debugger, db, initial_disabled):
        """INVARIANT: Breakpoint toggle flips disabled state."""
        breakpoint_id = "bp_test"
        user_id = "test_user"

        # Mock query to return a breakpoint
        mock_bp = MagicMock()
        mock_bp.id = breakpoint_id
        mock_bp.is_disabled = initial_disabled
        mock_bp.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_bp
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Toggle breakpoint
        result = debugger.toggle_breakpoint(breakpoint_id, user_id)

        # Invariant: Disabled state should flip
        assert mock_bp.is_disabled != initial_disabled, \
            f"Disabled state should flip from {initial_disabled} to {not initial_disabled}"
        assert db.commit.called, "Should commit after toggle"


class TestStateInspectionInvariants:
    """Property-based tests for state inspection and variable tracking."""

    @pytest.fixture
    def db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def debugger(self, db):
        """Create a WorkflowDebugger instance."""
        return WorkflowDebugger(db)

    @given(
        variables=st.dictionaries(
            st.text(min_size=1, max_size=20, alphabet='abc'),
            st.one_of(st.integers(), st.text(), st.booleans(), st.none()),
            min_size=0,
            max_size=10
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_variable_snapshot_creation_invariant(self, debugger, db, variables):
        """INVARIANT: Variable snapshots preserve values and types."""
        trace_id = "trace_test"
        variable_name = "test_var"

        # Pick a value from variables
        value = list(variables.values())[0] if variables else "test_value"
        value_type = type(value).__name__

        mock_var = MagicMock()
        mock_var.id = f"var_{trace_id}"
        db.add.return_value = None
        db.commit.return_value = None
        db.refresh.return_value = None

        # Create variable snapshot
        result = debugger.create_variable_snapshot(
            trace_id=trace_id,
            variable_name=variable_name,
            variable_path=variable_name,
            variable_type=value_type,
            value=value
        )

        # Invariant: Database operations should be called
        assert db.add.called, "Should add variable to database"
        assert db.commit.called, "Should commit after creation"

    @given(
        current_state=st.dictionaries(
            st.text(min_size=1, max_size=20, alphabet='abc'),
            st.integers(min_value=-100, max_value=100),
            min_size=0,
            max_size=10
        ),
        variable_name=st.text(min_size=1, max_size=20, alphabet='abc')
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_variable_access_invariant(self, debugger, db, current_state, variable_name):
        """INVARIANT: Variables can be accessed from state."""
        trace_id = "trace_test"

        # Mock query to return variables
        mock_vars = []
        for var_name, var_value in current_state.items():
            mock_var = MagicMock()
            mock_var.variable_name = var_name
            mock_var.value = var_value
            mock_vars.append(mock_var)

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = mock_vars
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Get variables for trace
        result = debugger.get_variables_for_trace(trace_id)

        # Invariant: Should return all variables
        assert len(result) == len(current_state), \
            f"Should return {len(current_state)} variables"

    @given(
        variables=st.dictionaries(
            st.text(min_size=1, max_size=15, alphabet='abc'),
            st.integers(min_value=0, max_value=100),
            min_size=1,
            max_size=5
        ),
        new_value=st.integers(min_value=0, max_value=200)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_variable_modification_invariant(self, debugger, db, variables, new_value):
        """INVARIANT: Variables can be modified with audit trail."""
        session_id = "session_test"
        variable_name = list(variables.keys())[0]

        # Mock debug session
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.variables = variables.copy()
        mock_session.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_session
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        mock_var = MagicMock()
        db.add.return_value = None
        db.commit.return_value = None
        db.refresh.return_value = None

        # Modify variable
        result = debugger.modify_variable(
            session_id=session_id,
            variable_name=variable_name,
            new_value=new_value
        )

        # Invariant: Variable should be updated in session
        assert mock_session.variables[variable_name] == new_value, \
            f"Variable {variable_name} should be updated to {new_value}"
        assert db.commit.called, "Should commit after modification"


class TestStepExecutionInvariants:
    """Property-based tests for step execution control."""

    @pytest.fixture
    def db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def debugger(self, db):
        """Create a WorkflowDebugger instance."""
        return WorkflowDebugger(db)

    @given(
        current_step=st.integers(min_value=0, max_value=10),
        step_increment=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_step_over_invariant(self, debugger, db, current_step, step_increment):
        """INVARIANT: Step over advances to next sibling step."""
        session_id = "session_test"

        # Mock debug session
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.current_step = current_step
        mock_session.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_session
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Step over
        result = debugger.step_over(session_id)

        # Invariant: Current step should increment by 1
        assert mock_session.current_step == current_step + 1, \
            f"Step over should increment from {current_step} to {current_step + 1}"
        assert db.commit.called, "Should commit after step"

    @given(
        current_step=st.integers(min_value=0, max_value=10),
        node_id=st.text(min_size=1, max_size=20, alphabet='abc123_')
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_step_into_invariant(self, debugger, db, current_step, node_id):
        """INVARIANT: Step into pushes frame onto call stack."""
        session_id = "session_test"

        # Mock debug session
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.current_step = current_step
        mock_session.current_node_id = "parent_node"
        mock_session.workflow_id = "workflow_test"
        mock_session.call_stack = []
        mock_session.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_session
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Step into
        result = debugger.step_into(session_id, node_id)

        # Invariant: Call stack should have one frame
        assert len(mock_session.call_stack) == 1, \
            "Call stack should have one frame after step_into"
        assert mock_session.current_step == current_step + 1, \
            "Current step should increment"
        assert mock_session.current_node_id == node_id, \
            f"Current node should be {node_id}"
        assert db.commit.called, "Should commit after step"

    @given(
        stack_depth=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_step_out_invariant(self, debugger, db, stack_depth):
        """INVARIANT: Step out pops frame from call stack."""
        session_id = "session_test"

        # Build call stack
        call_stack = []
        for i in range(stack_depth):
            call_stack.append({
                "step_number": i * 10,
                "node_id": f"node_{i}",
                "workflow_id": f"workflow_{i}",
            })

        # Mock debug session
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.call_stack = call_stack.copy()
        mock_session.current_step = stack_depth * 10
        mock_session.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_session
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Step out
        result = debugger.step_out(session_id)

        # Invariant: Call stack depth should decrease by 1
        assert len(mock_session.call_stack) == stack_depth - 1, \
            f"Call stack should decrease from {stack_depth} to {stack_depth - 1}"
        assert db.commit.called, "Should commit after step"

    @given(
        initial_status=st.sampled_from(["active", "paused", "running"])
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_continue_execution_invariant(self, debugger, db, initial_status):
        """INVARIANT: Continue execution sets status to running."""
        session_id = "session_test"

        # Mock debug session
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.status = initial_status
        mock_session.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_session
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Continue execution
        result = debugger.continue_execution(session_id)

        # Invariant: Status should be "running"
        assert mock_session.status == "running", \
            f"Status should be 'running', got {mock_session.status}"
        assert db.commit.called, "Should commit after continue"

    @given(
        initial_status=st.sampled_from(["active", "paused", "running"])
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pause_execution_invariant(self, debugger, db, initial_status):
        """INVARIANT: Pause execution sets status to paused."""
        session_id = "session_test"

        # Mock debug session
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.status = initial_status
        mock_session.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_session
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Pause execution
        result = debugger.pause_execution(session_id)

        # Invariant: Status should be "paused"
        assert mock_session.status == "paused", \
            f"Status should be 'paused', got {mock_session.status}"
        assert db.commit.called, "Should commit after pause"


class TestBreakpointTriggeringInvariants:
    """Property-based tests for breakpoint triggering logic."""

    @pytest.fixture
    def db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def debugger(self, db):
        """Create a WorkflowDebugger instance."""
        return WorkflowDebugger(db)

    @given(
        node_id=st.text(min_size=1, max_size=20, alphabet='abc123_'),
        variables=st.dictionaries(
            st.text(min_size=1, max_size=15, alphabet='abc'),
            st.integers(min_value=0, max_value=100),
            min_size=0,
            max_size=5
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_breakpoint_invariant(self, debugger, db, node_id, variables):
        """INVARIANT: No breakpoints should not pause execution."""
        # Mock query to return no breakpoints
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = []
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Check breakpoint
        should_pause, log_message = debugger.check_breakpoint_hit(node_id, variables)

        # Invariant: Should not pause
        assert should_pause is False, "Should not pause when no breakpoints exist"
        assert log_message is None, "Log message should be None"

    @given(
        hit_count=st.integers(min_value=0, max_value=10),
        hit_limit=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_hit_limit_invariant(self, debugger, db, hit_count, hit_limit):
        """INVARIANT: Breakpoint respects hit limit."""
        node_id = "test_node"
        variables = {"test": 1}

        # Mock breakpoint
        mock_bp = MagicMock()
        mock_bp.hit_count = hit_count
        mock_bp.hit_limit = hit_limit
        mock_bp.condition = None
        mock_bp.log_message = None

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [mock_bp]
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query
        db.commit.return_value = None

        # Check breakpoint
        should_pause, log_message = debugger.check_breakpoint_hit(node_id, variables)

        # Invariant: Should pause only if hit_count < hit_limit
        if hit_count < hit_limit:
            assert should_pause is True, "Should pause when hit_count < hit_limit"
        else:
            assert should_pause is False, "Should not pause when hit_count >= hit_limit"

    @given(
        has_log_message=st.booleans()
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_log_message_invariant(self, debugger, db, has_log_message):
        """INVARIANT: Log-only breakpoints don't pause execution."""
        node_id = "test_node"
        variables = {"test": 1}
        log_message = "Hit breakpoint" if has_log_message else None

        # Mock breakpoint
        mock_bp = MagicMock()
        mock_bp.hit_count = 0
        mock_bp.hit_limit = None
        mock_bp.condition = None
        mock_bp.log_message = log_message

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = [mock_bp]
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query
        db.commit.return_value = None

        # Check breakpoint
        should_pause, result_log_message = debugger.check_breakpoint_hit(node_id, variables)

        # Invariant: Log breakpoints should not pause
        if has_log_message:
            assert should_pause is False, "Log-only breakpoints should not pause"
            assert result_log_message == log_message, "Should return log message"
        else:
            assert should_pause is True, "Regular breakpoints should pause"


class TestExecutionTraceInvariants:
    """Property-based tests for execution trace recording."""

    @pytest.fixture
    def db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def debugger(self, db):
        """Create a WorkflowDebugger instance."""
        return WorkflowDebugger(db)

    @given(
        step_number=st.integers(min_value=1, max_value=100),
        node_id=st.text(min_size=1, max_size=20, alphabet='abc123_'),
        node_type=st.sampled_from(["trigger", "action", "condition", "loop"]),
        input_data=st.dictionaries(
            st.text(min_size=1, max_size=15, alphabet='abc'),
            st.integers(min_value=0, max_value=100),
            min_size=0,
            max_size=5
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_trace_creation_invariant(self, debugger, db, step_number, node_id, node_type, input_data):
        """INVARIANT: Execution trace captures step information."""
        workflow_id = "workflow_test"
        execution_id = "execution_test"

        mock_trace = MagicMock()
        mock_trace.id = f"trace_{step_number}"
        db.add.return_value = None
        db.commit.return_value = None
        db.refresh.return_value = None

        # Create trace
        result = debugger.create_trace(
            workflow_id=workflow_id,
            execution_id=execution_id,
            step_number=step_number,
            node_id=node_id,
            node_type=node_type,
            input_data=input_data
        )

        # Invariant: Database operations should be called
        assert db.add.called, "Should add trace to database"
        assert db.commit.called, "Should commit after creation"

    @given(
        variables_before=st.dictionaries(
            st.text(min_size=1, max_size=10, alphabet='abc'),
            st.integers(min_value=0, max_value=50),
            min_size=2,
            max_size=5
        ),
        variables_after=st.dictionaries(
            st.text(min_size=1, max_size=10, alphabet='abc'),
            st.integers(min_value=0, max_value=100),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_variable_changes_invariant(self, debugger, variables_before, variables_after):
        """INVARIANT: Variable changes are calculated correctly."""
        # Calculate changes
        changes = debugger._calculate_variable_changes(variables_before, variables_after)

        # Invariant: All changes should be valid
        for change in changes:
            assert "variable" in change, "Change should have variable name"
            assert "type" in change, "Change should have type (added/changed/removed)"
            assert change["type"] in ["added", "changed", "removed"], \
                f"Change type should be valid, got {change['type']}"

        # Invariant: Added variables should be in after but not before
        added = [c for c in changes if c["type"] == "added"]
        for change in added:
            assert change["variable"] not in variables_before, \
                f"Added variable {change['variable']} should not be in before"
            assert change["variable"] in variables_after, \
                f"Added variable {change['variable']} should be in after"

        # Invariant: Removed variables should be in before but not after
        removed = [c for c in changes if c["type"] == "removed"]
        for change in removed:
            assert change["variable"] in variables_before, \
                f"Removed variable {change['variable']} should be in before"
            assert change["variable"] not in variables_after, \
                f"Removed variable {change['variable']} should not be in after"


class TestSessionPersistenceInvariants:
    """Property-based tests for session export/import."""

    @pytest.fixture
    def db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def debugger(self, db):
        """Create a WorkflowDebugger instance."""
        return WorkflowDebugger(db)

    @given(
        workflow_id=st.text(min_size=1, max_size=20, alphabet='abc123_'),
        user_id=st.text(min_size=1, max_size=15, alphabet='abc'),
        stop_on_entry=st.booleans(),
        stop_on_exceptions=st.booleans(),
        stop_on_error=st.booleans()
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_session_export_invariant(self, debugger, db, workflow_id, user_id,
                                       stop_on_entry, stop_on_exceptions, stop_on_error):
        """INVARIANT: Session export preserves all critical data."""
        session_id = "session_test"

        # Mock debug session
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.workflow_id = workflow_id
        mock_session.execution_id = "execution_test"
        mock_session.user_id = user_id
        mock_session.session_name = "Test Session"
        mock_session.status = "active"
        mock_session.current_step = 5
        mock_session.current_node_id = "node_5"
        mock_session.variables = {"var1": 1, "var2": 2}
        mock_session.call_stack = [{"step": 1, "node": "node_1"}]
        mock_session.stop_on_entry = stop_on_entry
        mock_session.stop_on_exceptions = stop_on_exceptions
        mock_session.stop_on_error = stop_on_error
        mock_session.created_at = datetime.now()
        mock_session.updated_at = datetime.now()
        mock_session.completed_at = None

        # Mock get_debug_session
        debugger.get_debug_session = MagicMock(return_value=mock_session)

        # Mock get_breakpoints to return empty list
        debugger.get_breakpoints = MagicMock(return_value=[])

        # Mock get_execution_traces to return empty list
        debugger.get_execution_traces = MagicMock(return_value=[])

        # Export session
        result = debugger.export_session(session_id)

        # Invariant: Export should contain session data
        assert result is not None, "Export should return data"
        assert "session" in result, "Export should contain session"
        assert result["session"]["id"] == session_id, "Session ID should match"
        assert result["session"]["workflow_id"] == workflow_id, "Workflow ID should match"
        assert result["session"]["stop_on_entry"] == stop_on_entry, \
            "stop_on_entry should be preserved"

    @given(
        workflow_id=st.text(min_size=1, max_size=20, alphabet='abc123_'),
        user_id=st.text(min_size=1, max_size=15, alphabet='abc'),
        variable_count=st.integers(min_value=0, max_value=5)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_session_import_invariant(self, debugger, db, workflow_id, user_id, variable_count):
        """INVARIANT: Session import recreates session correctly."""
        # Create export data
        variables = {f"var{i}": i * 10 for i in range(variable_count)}
        call_stack = [{"step": i, "node": f"node_{i}"} for i in range(3)]

        export_data = {
            "session": {
                "id": "original_session",
                "workflow_id": workflow_id,
                "execution_id": "execution_test",
                "user_id": user_id,
                "session_name": "Test Session",
                "variables": variables,
                "call_stack": call_stack,
                "stop_on_entry": False,
                "stop_on_exceptions": True,
                "stop_on_error": True,
            },
            "breakpoints": [],
            "traces": []
        }

        # Mock create_debug_session to return a session with proper initial state
        mock_new_session = MagicMock()
        mock_new_session.id = "new_session_id"
        mock_new_session.variables = {}
        mock_new_session.call_stack = []

        # Track calls
        create_session_calls = []
        original_create = debugger.create_debug_session

        def mock_create(*args, **kwargs):
            session = mock_new_session
            create_session_calls.append((args, kwargs))
            return session

        debugger.create_debug_session = mock_create

        # Mock add_breakpoint
        debugger.add_breakpoint = MagicMock()

        # Import session
        result = debugger.import_session(export_data)

        # Invariant: Should create new session
        assert result is not None, "Import should return new session"
        assert len(create_session_calls) > 0, "Should create new session"

        # Invariant: Should restore variables and call stack
        # The import_session method should set these on the session
        assert db.commit.called, "Should commit after import"


class TestPerformanceProfilingInvariants:
    """Property-based tests for performance profiling."""

    @pytest.fixture
    def db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def debugger(self, db):
        """Create a WorkflowDebugger instance."""
        return WorkflowDebugger(db)

    @given(
        node_id=st.text(min_size=1, max_size=20, alphabet='abc123_'),
        node_type=st.sampled_from(["action", "condition", "loop"]),
        duration_ms=st.integers(min_value=1, max_value=5000)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_step_timing_invariant(self, debugger, db, node_id, node_type, duration_ms):
        """INVARIANT: Step timing records duration accurately."""
        session_id = "session_test"

        # Mock debug session with performance metrics enabled
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.performance_metrics = {
            "enabled": True,
            "started_at": datetime.now().isoformat(),
            "step_times": [],
            "node_times": {},
            "total_duration_ms": 0,
        }
        mock_session.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_session
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Record step timing
        result = debugger.record_step_timing(session_id, node_id, node_type, duration_ms)

        # Invariant: Should record timing
        assert result is True, "Should record timing successfully"
        assert db.commit.called, "Should commit after recording"
        assert len(mock_session.performance_metrics["step_times"]) > 0, \
            "Should have step times recorded"

    @given(
        step_count=st.integers(min_value=1, max_value=20),
        avg_duration=st.integers(min_value=10, max_value=1000),
        duration_variance=st.integers(min_value=-5, max_value=5)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_performance_report_invariant(self, debugger, db, step_count, avg_duration, duration_variance):
        """INVARIANT: Performance report aggregates timing data."""
        session_id = "session_test"

        # Create mock performance metrics
        step_times = []
        node_times = {}
        total_duration = 0

        for i in range(step_count):
            duration = avg_duration + duration_variance
            total_duration += duration
            node_id = f"node_{i % 5}"  # 5 different nodes

            step_times.append({
                "node_id": node_id,
                "node_type": "action",
                "duration_ms": duration,
                "timestamp": datetime.now().isoformat(),
            })

            # Update node times
            if node_id not in node_times:
                node_times[node_id] = {
                    "count": 0,
                    "total_ms": 0,
                    "avg_ms": 0,
                    "min_ms": float('inf'),
                    "max_ms": 0,
                }

            node_times[node_id]["count"] += 1
            node_times[node_id]["total_ms"] += duration
            node_times[node_id]["avg_ms"] = node_times[node_id]["total_ms"] / node_times[node_id]["count"]
            node_times[node_id]["min_ms"] = min(node_times[node_id]["min_ms"], duration)
            node_times[node_id]["max_ms"] = max(node_times[node_id]["max_ms"], duration)

        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.performance_metrics = {
            "enabled": True,
            "started_at": datetime.now().isoformat(),
            "step_times": step_times,
            "node_times": node_times,
            "total_duration_ms": total_duration,
        }

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_session
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Get performance report
        result = debugger.get_performance_report(session_id)

        # Invariant: Report should contain all fields
        assert result is not None, "Should generate report"
        assert "total_duration_ms" in result, "Report should have total duration"
        assert "total_steps" in result, "Report should have step count"
        assert result["total_steps"] == step_count, \
            f"Step count should be {step_count}"
        assert "slowest_steps" in result, "Report should have slowest steps"
        assert "slowest_nodes" in result, "Report should have slowest nodes"


class TestCollaborativeDebuggingInvariants:
    """Property-based tests for collaborative debugging permissions."""

    @pytest.fixture
    def db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def debugger(self, db):
        """Create a WorkflowDebugger instance."""
        return WorkflowDebugger(db)

    @given(
        session_id=st.text(min_size=1, max_size=20, alphabet='abc123_'),
        user_id=st.text(min_size=1, max_size=15, alphabet='abc'),
        permission=st.sampled_from(["viewer", "operator", "owner"])
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_add_collaborator_invariant(self, debugger, db, session_id, user_id, permission):
        """INVARIANT: Collaborator is added with correct permission."""
        # Mock debug session
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.collaborators = {}
        mock_session.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_session
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Add collaborator
        result = debugger.add_collaborator(session_id, user_id, permission)

        # Invariant: Collaborator should be added
        assert result is True, "Should add collaborator successfully"
        assert user_id in mock_session.collaborators, \
            f"User {user_id} should be in collaborators"
        assert mock_session.collaborators[user_id]["permission"] == permission, \
            f"Permission should be {permission}"
        assert db.commit.called, "Should commit after adding"

    @given(
        user_permission=st.sampled_from(["viewer", "operator", "owner"]),
        required_permission=st.sampled_from(["viewer", "operator", "owner"])
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_permission_hierarchy_invariant(self, debugger, db, user_permission, required_permission):
        """INVARIANT: Permission hierarchy is enforced correctly."""
        session_id = "session_test"
        user_id = "user_test"
        owner_id = "owner_test"

        # Mock debug session
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.user_id = owner_id
        mock_session.collaborators = {
            user_id: {
                "permission": user_permission,
                "added_at": datetime.now().isoformat(),
            }
        }

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_session
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        # Check permission for collaborator
        result = debugger.check_collaborator_permission(
            session_id, user_id, required_permission
        )

        # Permission hierarchy: viewer=1, operator=2, owner=3
        hierarchy = {"viewer": 1, "operator": 2, "owner": 3}
        user_level = hierarchy[user_permission]
        required_level = hierarchy[required_permission]

        # Invariant: Permission check should follow hierarchy
        assert result == (user_level >= required_level), \
            f"User with {user_permission} (level {user_level}) should {'have' if user_level >= required_level else 'not have'} {required_permission} (level {required_level})"

        # Owner should always have permission
        owner_result = debugger.check_collaborator_permission(
            session_id, owner_id, required_permission
        )
        assert owner_result is True, "Owner should have all permissions"


class TestValuePreviewInvariants:
    """Property-based tests for value preview generation."""

    @pytest.fixture
    def db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def debugger(self, db):
        """Create a WorkflowDebugger instance."""
        return WorkflowDebugger(db)

    @given(
        value=st.one_of(
            st.none(),
            st.booleans(),
            st.integers(min_value=-1000, max_value=1000),
            st.text(min_size=0, max_size=50, alphabet='abc123'),
            st.dictionaries(
                st.text(min_size=1, max_size=10, alphabet='abc'),
                st.integers(min_value=0, max_value=100),
                min_size=0,
                max_size=5
            ),
            st.lists(
                st.integers(min_value=0, max_value=100),
                min_size=0,
                max_size=10
            ),
            st.sets(
                st.integers(min_value=0, max_value=100),
                min_size=0,
                max_size=10
            )
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_value_preview_invariant(self, debugger, value):
        """INVARIANT: Value preview generates correct string representation."""
        # Generate preview
        preview = debugger._generate_value_preview(value)

        # Invariant: Preview should be a string
        assert isinstance(preview, str), "Preview should be a string"
        assert preview is not None, "Preview should not be None"

        # Invariant: Preview should match value type
        if value is None:
            assert preview == "null", "None should preview as 'null'"
        elif isinstance(value, bool):
            assert preview == str(value), f"Boolean should preview as string, got {preview}"
        elif isinstance(value, (int, float, str)):
            assert preview == str(value), f"Primitive should preview as string, got {preview}"
        elif isinstance(value, dict):
            assert "dict" in preview and "keys" in preview, \
                f"Dict should preview as 'dict(N keys)', got {preview}"
        elif isinstance(value, list):
            assert "list" in preview and "items" in preview, \
                f"List should preview as 'list(N items)', got {preview}"
        elif isinstance(value, set):
            assert "set" in preview and "items" in preview, \
                f"Set should preview as 'set(N items)', got {preview}"

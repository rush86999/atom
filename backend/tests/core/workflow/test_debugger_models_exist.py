"""
Verification test for workflow debugger models.

Tests that the 4 missing models (DebugVariable, ExecutionTrace,
WorkflowBreakpoint, WorkflowDebugSession) exist in models.py
and can be imported successfully.

Created as part of Plan 190-01 to fix import blockers in workflow_debugger.py.
"""

import pytest
from core.models import (
    DebugVariable,
    ExecutionTrace,
    WorkflowBreakpoint,
    WorkflowDebugSession,
)
from core.workflow_debugger import WorkflowDebugger


class TestDebuggerModelsExist:
    """Verify all 4 workflow debugger models exist and are importable."""

    def test_debug_variable_model_exists(self):
        """Test that DebugVariable model exists with expected attributes."""
        # Verify model has expected attributes
        assert hasattr(DebugVariable, 'id')
        assert hasattr(DebugVariable, 'workflow_execution_id')
        assert hasattr(DebugVariable, 'variable_name')
        assert hasattr(DebugVariable, 'variable_value')
        assert hasattr(DebugVariable, 'timestamp')
        assert hasattr(DebugVariable, 'captured_at')
        assert hasattr(DebugVariable, '__tablename__')

        # Verify table name
        assert DebugVariable.__tablename__ == 'workflow_debug_variables'

    def test_execution_trace_model_exists(self):
        """Test that ExecutionTrace model exists with expected attributes."""
        assert hasattr(ExecutionTrace, 'id')
        assert hasattr(ExecutionTrace, 'workflow_execution_id')
        assert hasattr(ExecutionTrace, 'step_id')
        assert hasattr(ExecutionTrace, 'trace_type')
        assert hasattr(ExecutionTrace, 'message')
        assert hasattr(ExecutionTrace, 'trace_metadata')  # Renamed from 'metadata'
        assert hasattr(ExecutionTrace, 'timestamp')
        assert hasattr(ExecutionTrace, '__tablename__')

        # Verify table name
        assert ExecutionTrace.__tablename__ == 'workflow_execution_traces'

    def test_workflow_breakpoint_model_exists(self):
        """Test that WorkflowBreakpoint model exists with expected attributes."""
        assert hasattr(WorkflowBreakpoint, 'id')
        assert hasattr(WorkflowBreakpoint, 'workflow_id')
        assert hasattr(WorkflowBreakpoint, 'step_id')
        assert hasattr(WorkflowBreakpoint, 'condition')
        assert hasattr(WorkflowBreakpoint, 'enabled')
        assert hasattr(WorkflowBreakpoint, 'hit_count')
        assert hasattr(WorkflowBreakpoint, 'created_by')
        assert hasattr(WorkflowBreakpoint, 'created_at')
        assert hasattr(WorkflowBreakpoint, '__tablename__')

        # Verify table name
        assert WorkflowBreakpoint.__tablename__ == 'workflow_breakpoints'

    def test_workflow_debug_session_model_exists(self):
        """Test that WorkflowDebugSession model exists with expected attributes."""
        assert hasattr(WorkflowDebugSession, 'id')
        assert hasattr(WorkflowDebugSession, 'workflow_execution_id')
        assert hasattr(WorkflowDebugSession, 'session_type')
        assert hasattr(WorkflowDebugSession, 'status')
        assert hasattr(WorkflowDebugSession, 'breakpoints')
        assert hasattr(WorkflowDebugSession, 'current_step')
        assert hasattr(WorkflowDebugSession, 'started_at')
        assert hasattr(WorkflowDebugSession, 'ended_at')
        assert hasattr(WorkflowDebugSession, '__tablename__')

        # Verify table name
        assert WorkflowDebugSession.__tablename__ == 'workflow_debug_sessions'

    def test_workflow_debugger_importable(self):
        """Test that WorkflowDebugger class can be imported without ImportError."""
        # Verify WorkflowDebugger is importable
        assert WorkflowDebugger is not None

        # Verify WorkflowDebugger has expected methods
        assert hasattr(WorkflowDebugger, '__init__')
        assert hasattr(WorkflowDebugger, 'create_debug_session')
        assert hasattr(WorkflowDebugger, 'get_debug_session')
        assert hasattr(WorkflowDebugger, 'add_breakpoint')
        assert hasattr(WorkflowDebugger, 'remove_breakpoint')

    def test_all_models_importable(self):
        """Test that all 4 models can be imported in one statement."""
        from core.models import (
            DebugVariable,
            ExecutionTrace,
            WorkflowBreakpoint,
            WorkflowDebugSession,
        )

        # If we got here without ImportError, all models exist
        assert DebugVariable is not None
        assert ExecutionTrace is not None
        assert WorkflowBreakpoint is not None
        assert WorkflowDebugSession is not None

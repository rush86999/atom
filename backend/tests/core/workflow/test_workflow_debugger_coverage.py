"""
Coverage-driven tests for WorkflowDebugger (currently 0% -> target 80%+)

VALIDATED_BUG: workflow_debugger.py imports non-existent models from core.models:
- DebugVariable (does not exist)
- ExecutionTrace (does not exist)
- WorkflowBreakpoint (does not exist)
- WorkflowDebugSession (does not exist)
- Only WorkflowExecution exists in models.py

This prevents the module from being imported at all, so coverage cannot be measured.

This test file documents the issue and provides minimal tests for what CAN be tested.
"""

import pytest


class TestWorkflowDebuggerImportIssue:
    """Test that documents the import error in workflow_debugger.py."""

    def test_workflow_debugger_import_fails(self):
        """
        VALIDATED_BUG: workflow_debugger.py cannot be imported.

        Imports from core.models (lines 29-35):
        - DebugVariable: DOES NOT EXIST
        - ExecutionTrace: DOES NOT EXIST
        - WorkflowBreakpoint: DOES NOT EXIST
        - WorkflowDebugSession: DOES NOT EXIST
        - WorkflowExecution: EXISTS (line 661 in models.py)

        Fix required: Either create these models in core/models.py or update imports
        to use existing models.

        Severity: HIGH - Blocker for all debugger functionality
        Impact: No tests can run, no coverage can be measured
        """
        with pytest.raises(ImportError) as exc_info:
            from core.workflow_debugger import WorkflowDebugger

        assert "cannot import name 'DebugVariable' from 'core.models'" in str(exc_info.value)

    def test_check_existing_debug_models(self):
        """Check what debug-related models actually exist in core.models."""
        from core.models import DebugLog  # Only exists at line 5583
        from core.models import WorkflowExecution  # Exists at line 661

        # These models DON'T exist but are imported by workflow_debugger.py:
        # - DebugVariable
        # - ExecutionTrace (different from ExecutionTrace)
        # - WorkflowBreakpoint
        # - WorkflowDebugSession

        assert DebugLog is not None
        assert WorkflowExecution is not None

    def test_workflow_debugger_file_exists(self):
        """Verify the file exists but has import errors."""
        from pathlib import Path

        debugger_file = Path(__file__).parent.parent.parent.parent / "core" / "workflow_debugger.py"
        assert debugger_file.exists()

        # Read the file to verify the problematic imports
        content = debugger_file.read_text()
        assert "from core.models import" in content
        assert "DebugVariable" in content
        assert "WorkflowBreakpoint" in content
        assert "WorkflowDebugSession" in content


class TestWorkflowDebuggerCodeStructure:
    """Test the structure of workflow_debugger.py without importing it."""

    def test_class_exists_in_source(self):
        """Verify WorkflowDebugger class exists in source code."""
        from pathlib import Path

        debugger_file = Path(__file__).parent.parent.parent.parent / "core" / "workflow_debugger.py"
        content = debugger_file.read_text()

        assert "class WorkflowDebugger:" in content
        assert "def __init__(self, db: Session):" in content
        assert "def create_debug_session(" in content
        assert "def add_breakpoint(" in content

    def test_method_signatures(self):
        """Verify expected methods exist in source code."""
        from pathlib import Path

        debugger_file = Path(__file__).parent.parent.parent.parent / "core" / "workflow_debugger.py"
        content = debugger_file.read_text()

        # Debug session management methods
        assert "def create_debug_session(" in content
        assert "def get_debug_session(" in content
        assert "def pause_debug_session(" in content
        assert "def resume_debug_session(" in content
        assert "def complete_debug_session(" in content

        # Breakpoint management methods
        assert "def add_breakpoint(" in content
        # Other methods may exist but we can't import to verify

    @pytest.mark.parametrize("expected_line,content_snippet", [
        (29, "from core.models import"),
        (41, "class WorkflowDebugger:"),
        (54, "def __init__(self, db: Session):"),
        (60, "def create_debug_session("),
        (100, "def get_debug_session("),
        (122, "def pause_debug_session("),
        (141, "def resume_debug_session("),
        (160, "def complete_debug_session("),
        (182, "def add_breakpoint("),
    ])
    def test_code_structure_by_line(self, expected_line, content_snippet):
        """Verify code structure at specific lines."""
        from pathlib import Path

        debugger_file = Path(__file__).parent.parent.parent.parent / "core" / "workflow_debugger.py"
        content = debugger_file.read_text()

        lines = content.split("\n")

        # Check if content snippet exists around expected line
        found = False
        for i, line in enumerate(lines[expected_line-5:expected_line+5], start=expected_line-5):
            if content_snippet in line:
                found = True
                break

        assert found, f"Content '{content_snippet}' not found near line {expected_line}"

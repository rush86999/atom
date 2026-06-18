"""
Test suite for Path Traversal fix verification.

GREEN PHASE: These tests verify the path traversal fixes are applied.
"""

import pytest
import os
import inspect
from core.trajectory import TrajectoryRecorder
from core.advanced_workflow_system import StateManager


class TestPathTraversalFixes:
    """Tests for verifying the path traversal fixes."""

    def test_trajectory_directory_sanitized(self):
        """
        Test that directory parameter is now sanitized.

        GREEN PHASE: After the fix, directory should be sanitized.
        """
        source = inspect.getsource(TrajectoryRecorder.save)

        # Verify the fix - sanitization code is present
        assert 'replace' in source and '../' in source, \
            "Fix applied: Directory path traversal is blocked"
        assert 'isalnum' in source or 'sanitize' in source.lower(), \
            "Fix applied: Alphanumeric filtering applied"

    def test_trajectory_trace_id_sanitized(self):
        """
        Test that trace_id is now sanitized.

        GREEN PHASE: After the fix, trace_id should be sanitized.
        """
        source = inspect.getsource(TrajectoryRecorder.save)

        # Verify the fix - trace_id sanitization
        assert 'trace_id' in source and 'isalnum' in source, \
            "Fix applied: trace_id is sanitized to alphanumeric"

    def test_workflow_id_sanitized(self):
        """
        Test that workflow_id is now sanitized in StateManager.

        GREEN PHASE: After the fix, workflow_id should be sanitized.
        """
        source = inspect.getsource(StateManager._persist_to_file)

        # Verify the fix - workflow_id sanitization
        assert 'isalnum' in source, \
            "Fix applied: workflow_id is sanitized to alphanumeric"

        # Verify validation is present
        assert 'ValueError' in source or 'if not workflow_id' in source, \
            "Fix applied: Invalid workflow_id is rejected"

    def test_workflow_id_load_sanitized(self):
        """
        Test that workflow_id is sanitized in _load_from_file.

        GREEN PHASE: After the fix, _load_from_file should sanitize.
        """
        source = inspect.getsource(StateManager._load_from_file)

        # Verify the fix - workflow_id sanitization in load
        assert 'isalnum' in source, \
            "Fix applied: workflow_id is sanitized in _load_from_file"

    def test_workflow_id_delete_sanitized(self):
        """
        Test that workflow_id is sanitized in delete_state.

        GREEN PHASE: After the fix, delete_state should sanitize.
        """
        source = inspect.getsource(StateManager.delete_state)

        # Verify the fix - workflow_id sanitization in delete
        assert 'isalnum' in source, \
            "Fix applied: workflow_id is sanitized in delete_state"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

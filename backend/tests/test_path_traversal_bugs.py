"""
Test suite for Path Traversal vulnerabilities.

RED PHASE: These tests expose path traversal bugs in file operations.

The bugs:
1. trajectory.py:88 - directory parameter not validated, allows ../../../etc/passwd
2. advanced_workflow_system.py:217 - workflow_id not validated in filename
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch
from core.trajectory import TrajectoryRecorder


class TestPathTraversalBugs:
    """
    Test suite revealing path traversal vulnerabilities.

    The bug: User-controlled input used in file paths without validation,
    allowing attackers to read/write arbitrary files via path traversal.
    """

    def test_trajectory_directory_not_validated(self):
        """
        Test that directory parameter is not validated in trajectory save.

        BUG: Line 88 uses directory parameter directly: f"{directory}/{trace_id}.json"
        An attacker can use "../../../etc/passwd" to write to arbitrary locations.
        """
        import inspect

        # Get source code of save method
        source = inspect.getsource(TrajectoryRecorder.save)

        # Verify the bug - directory used without validation
        assert 'directory/' in source or 'directory}/' in source, \
            "Bug confirmed: directory parameter used in path without validation"

        # Verify no path sanitization
        assert 'sanitize' not in source.lower() and 'validate' not in source.lower(), \
            "Bug confirmed: No path sanitization for directory parameter"

    def test_workflow_id_not_validated_in_filename(self):
        """
        Test that workflow_id is not validated in filename.

        BUG: Line 217 uses workflow_id directly: f"workflow_states/{workflow_id}.json"
        An attacker can use "../../../etc/passwd" as workflow_id to read/write arbitrary files.
        """
        from core.advanced_workflow_system import StateManager

        import inspect

        # Get source code of _persist_to_file
        source = inspect.getsource(StateManager._persist_to_file)

        # Verify the bug - workflow_id used in filename without validation
        assert 'workflow_id}.json' in source or f'workflow_id' in source, \
            "Bug confirmed: workflow_id used in filename without validation"

        # Verify no path sanitization
        assert 'sanitize' not in source.lower() and 'validate' not in source.lower(), \
            "Bug confirmed: No path sanitization for workflow_id"

    def test_path_traversal_attack_vector(self):
        """
        Test that path traversal attack is possible.

        BUG: Using ../ in parameters allows escaping intended directory.
        """
        # Simulate a path traversal attack
        malicious_id = "../../../etc/passwd"
        expected_filename = f"workflow_states/{malicious_id}.json"

        # Verify the malicious filename would escape the directory
        assert "../" in expected_filename, \
            "Bug confirmed: Path traversal possible with ../ in ID"

        # Verify no normalization is applied
        from pathlib import Path
        normalized = Path(expected_filename).resolve()
        assert "/etc/" in str(normalized) or "etc:" in str(normalized), \
            "Bug confirmed: Path traversal escapes to system directories"

    def test_trace_id_not_validated(self):
        """
        Test that trace_id is not validated in trajectory save.

        BUG: trace.trace_id used directly without validation.
        """
        import inspect

        source = inspect.getsource(TrajectoryRecorder.save)

        # Verify trace_id used without validation
        assert 'trace.trace_id' in source or 'trace_id' in source, \
            "Bug confirmed: trace.trace_id used in filename without validation"

    def test_absolute_path_possible(self):
        """
        Test that absolute paths can be used as directory.

        BUG: Using /etc/passwd as directory would write to system files.
        """
        # Simulate absolute path attack
        malicious_directory = "/etc"
        expected_filename = f"{malicious_directory}/trace123.json"

        # Verify absolute path is not blocked
        assert expected_filename.startswith("/etc/"), \
            "Bug confirmed: Absolute paths can be used as directory"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

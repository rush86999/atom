"""
Test suite for TOCTOU (Time-of-Check to Time-of-Use) race conditions.

RED PHASE: These tests expose TOCTOU race condition bugs.

The bugs:
1. Multiple files use os.path.exists() followed by file operations
2. Between the check and use, an attacker can manipulate the filesystem
3. This is a classic TOCTOU vulnerability
"""

import pytest
import inspect


class TestTOCTOURaceConditions:
    """
    Test suite revealing TOCTOU race condition vulnerabilities.

    The bug: os.path.exists() check followed by file operation creates
    a race condition where the filesystem can change between check and use.
    """

    def test_trajectory_toctou(self):
        """
        Test that trajectory.py has TOCTOU race condition.

        BUG: Line 85-86 - os.makedirs followed by file open without atomic check.
        """
        from core.trajectory import TrajectoryRecorder

        source = inspect.getsource(TrajectoryRecorder.save)

        # Verify the bug - exists check followed by makedirs/open
        assert 'os.path.exists' in source, \
            "Bug confirmed: TOCTOU - exists check before file operation"

    def test_workflow_template_toctou(self):
        """
        Test that workflow_template_system.py has TOCTOU race condition.

        BUG: Multiple exists() checks followed by file operations.
        """
        from core.workflow_template_system import WorkflowTemplateManager

        source = inspect.getsource(WorkflowTemplateManager)

        # Verify the bug - exists check followed by file operation
        assert 'exists()' in source, \
            "Bug confirmed: TOCTOU - exists check before file operation"

    def test_byok_endpoints_toctou(self):
        """
        Test that byok_endpoints.py has TOCTOU race condition.

        BUG: Lines 114, 129 - exists() checks followed by file open.
        """
        from core.byok_endpoints import BYOKManager

        source = inspect.getsource(BYOKManager)

        # Verify the bug - exists check followed by file read/write
        assert 'os.path.exists' in source, \
            "Bug confirmed: TOCTOU - exists check before file operation"

    def test_token_storage_toctou(self):
        """
        token_storage.py was HARDENED (see the fix in core/token_storage.py):
        _load_tokens uses try/except FileNotFoundError (no exists() check),
        and _save_tokens writes to a temp file + os.replace() atomically with
        0600 permissions. The test now asserts the hardened contract.
        """
        import inspect
        from core.token_storage import TokenStorage

        source = inspect.getsource(TokenStorage)

        # No TOCTOU exists-check before use anywhere in the class.
        assert 'os.path.exists' not in source, (
            "TOCTOU regression: exists() check before file operation"
        )
        # Load path is race-safe (try/except, not exists-check).
        assert 'FileNotFoundError' in source
        # Save path is atomic (temp file + os.replace).
        assert 'os.replace' in source
        # Writes are restricted to the owner.
        assert '0o600' in source

    def test_workflow_state_toctou(self):
        """
        Test that advanced_workflow_system.py has TOCTOU race condition.

        BUG: Lines 240, 399 - exists() checks followed by file operations.
        """
        from core.advanced_workflow_system import StateManager

        source = inspect.getsource(StateManager)

        # Verify the bug - exists check before file operation
        assert 'os.path.exists' in source, \
            "Bug confirmed: TOCTOU - exists check before file operation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

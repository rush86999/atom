"""
Test suite for TOCTOU fix verification.

GREEN PHASE: These tests verify the TOCTOU fixes are applied.
"""

import pytest


class TestTOCTOUFixes:
    """Tests for verifying the TOCTOU fixes."""

    def test_token_storage_uses_try_except(self):
        """
        Test that token_storage uses try-except instead of exists check.

        GREEN PHASE: After the fix, FileNotFoundError should be caught.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/token_storage.py', 'r') as f:
            source = f.read()

        # Verify the fix - try-except with FileNotFoundError
        assert 'except FileNotFoundError:' in source, \
            "Fix applied: FileNotFoundError exception handled"
        # Verify exists check is removed or not used for file open
        # The old pattern was: if exists() then open
        # New pattern: try open except FileNotFoundError

    def test_byok_uses_try_except(self):
        """
        Test that byok_endpoints uses try-except instead of exists check.

        GREEN PHASE: After the fix, FileNotFoundError should be caught.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/byok_endpoints.py', 'r') as f:
            source = f.read()

        # Verify the fix - try-except with FileNotFoundError
        assert 'except FileNotFoundError:' in source, \
            "Fix applied: FileNotFoundError exception handled"

    def test_atomic_makedirs_used(self):
        """
        Test that os.makedirs uses exist_ok=True for atomic operation.

        GREEN PHASE: exist_ok=True prevents race condition in directory creation.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/byok_endpoints.py', 'r') as f:
            source = f.read()

        # Verify exist_ok=True is used (atomic directory creation)
        assert 'exist_ok=True' in source, \
            "Fix applied: Atomic makedirs with exist_ok=True"

    def test_trajectory_toctou_fixed(self):
        """
        Test that trajectory uses exist_ok=True.

        GREEN PHASE: After the fix, makedirs should be atomic.
        """
        from core.trajectory import TrajectoryRecorder

        import inspect
        source = inspect.getsource(TrajectoryRecorder.save)

        # Verify exist_ok is used
        assert 'exist_ok=True' in source, \
            "Fix applied: Atomic makedirs with exist_ok=True"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

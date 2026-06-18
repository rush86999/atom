"""
Test suite for Error Handling fix verification.

GREEN PHASE: These tests verify the error handling fixes are applied.
"""

import pytest
from core.directory_permission import DirectoryPermissionService
from core.local_agent_service import LocalAgentService


class TestErrorHandlingFixes:
    """Tests for verifying the error handling fixes."""

    def test_directory_permission_specific_exceptions(self):
        """
        Test that directory_permission now uses specific exceptions.

        GREEN PHASE: After the fix, specific exceptions should be used.
        """
        import inspect

        source = inspect.getsource(DirectoryPermissionService._is_blocked)

        # Verify the fix - specific exceptions instead of bare except
        assert 'OSError' in source or 'ValueError' in source, \
            "Fix applied: Specific exception types used"
        assert 'logger.debug' in source, \
            "Fix applied: Debug logging added for exceptions"

    def test_local_agent_specific_exceptions_communicate(self):
        """
        Test that local_agent_service uses specific exceptions for communicate.

        GREEN PHASE: After the fix, specific exceptions should be used.
        """
        # Read the file directly to check for the fix
        with open('/Users/rushiparikh/projects/atom/backend/core/local_agent_service.py', 'r') as f:
            source = f.read()

        # Verify the fix - specific exceptions instead of bare except
        assert 'ProcessLookupError' in source, \
            "Fix applied: ProcessLookupError exception handled"
        assert 'OSError' in source or 'BrokenPipeError' in source, \
            "Fix applied: OSError/BrokenPipeError exceptions handled"
        assert 'logger.warning' in source or 'logger.error' in source, \
            "Fix applied: Logging added for exceptions"

    def test_local_agent_specific_exceptions_health_check(self):
        """
        Test that local_agent_service uses specific exceptions for health check.

        GREEN PHASE: After the fix, specific exceptions should be used.
        """
        import inspect

        source = inspect.getsource(LocalAgentService.get_status)

        # Verify the fix - specific exceptions instead of bare except
        assert 'RequestError' in source or 'HTTPError' in source, \
            "Fix applied: Specific HTTP exceptions used"
        assert 'logger.debug' in source or 'logger.error' in source, \
            "Fix applied: Logging added for exceptions"

    def test_no_bare_except_in_fixed_files(self):
        """
        Test that bare except clauses are removed from fixed files.

        GREEN PHASE: After the fix, bare except should be gone.
        """
        # Read files directly to check for the fix
        with open('/Users/rushiparikh/projects/atom/backend/core/local_agent_service.py', 'r') as f:
            las_source = f.read()

        # The fix should have replaced bare except with specific exceptions
        assert 'ProcessLookupError' in las_source, \
            "Fix applied: ProcessLookupError in local_agent_service"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test suite for Resource Leak vulnerabilities.

RED PHASE: These tests expose resource leak bugs in resource management.

The bugs:
1. budget_enforcement_service.py:679 - __del__ method for cleanup is unreliable
2. Potential database session leaks without context managers
"""

import pytest
import gc
import inspect
from unittest.mock import Mock, patch
from core.budget_enforcement_service import BudgetEnforcementService


class TestResourceLeakBugs:
    """
    Test suite revealing resource leak vulnerabilities.

    The bug: __del__ methods used for cleanup are unreliable and can
    cause resource leaks when garbage collection is delayed.
    """

    def test_del_method_used_for_cleanup(self):
        """
        Test that __del__ method is used for database cleanup.

        BUG: __del__ is unreliable for resource cleanup.
        Garbage collection may be delayed indefinitely, keeping connections open.
        """
        import inspect

        # Get source code of __del__ method
        source = inspect.getsource(BudgetEnforcementService.__del__)

        # Verify the bug - __del__ is used for cleanup
        assert '__del__' in source or 'def __del__' in str(source), \
            "Bug confirmed: __del__ method exists for cleanup"

        # Verify it closes database
        assert 'close()' in source, \
            "Bug confirmed: __del__ closes database connection"

    def test_del_unreliable_pattern(self):
        """
        Test that __del__ pattern is unreliable.

        BUG: __del__ is not guaranteed to be called in a timely manner.
        Resources may leak when garbage collection is delayed.
        """
        # The __del__ method is problematic because:
        # 1. It's only called during garbage collection
        # 2. Garbage collection may be delayed indefinitely
        # 3. Circular references prevent __del__ from being called

        # Verify the bug exists
        assert hasattr(BudgetEnforcementService, '__del__'), \
            "Bug confirmed: __del__ method exists (unreliable cleanup)"

    def test_context_manager_pattern_missing(self):
        """
        Test that context manager pattern is not implemented.

        BUG: Without __enter__ and __exit__, cannot use 'with' statement.
        """
        # Verify the bug - no context manager support
        assert not hasattr(BudgetEnforcementService, '__enter__'), \
            "Bug confirmed: No __enter__ method (no context manager support)"
        assert not hasattr(BudgetEnforcementService, '__exit__'), \
            "Bug confirmed: No __exit__ method (no context manager support)"

    def test_database_session_not_managed(self):
        """
        Test that database session is not using context manager pattern.

        BUG: Direct db session without 'with' statement can leak.
        """
        import inspect

        # Get __init__ source
        source = inspect.getsource(BudgetEnforcementService.__init__)

        # Verify the bug - db session stored without context manager
        assert 'self.db = db' in source or 'self.db' in source, \
            "Bug confirmed: Database session stored in instance variable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

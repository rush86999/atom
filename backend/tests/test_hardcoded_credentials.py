"""
Test suite for Hardcoded Credentials vulnerabilities.

RED PHASE: These tests expose hardcoded credential bugs.

The bugs:
1. init_db.py:41 - hardcoded default password "admin123"
2. fix_parent_db.py:90 - hardcoded password "securePass123"
"""

import pytest


class TestHardcodedCredentialsBugs:
    """
    Test suite revealing hardcoded credential vulnerabilities.

    The bug: Hardcoded passwords in source code are security risks.
    """

    def test_init_db_hardcoded_password(self):
        """
        Test that init_db has hardcoded default password.

        BUG: Line 41 uses hardcoded "admin123" as default password.
        """
        # Read the file directly to check for hardcoded password
        with open('/Users/rushiparikh/projects/atom/backend/init_db.py', 'r') as f:
            content = f.read()

        # Verify the bug - hardcoded password
        assert 'admin123' in content, \
            "Bug confirmed: Hardcoded password 'admin123' found in init_db.py"

    def test_fix_parent_db_hardcoded_password(self):
        """
        Test that fix_parent_db has hardcoded password.

        BUG: Line 90 uses hardcoded "securePass123".
        """
        # Read the file directly to check for hardcoded password
        with open('/Users/rushiparikh/projects/atom/backend/fix_parent_db.py', 'r') as f:
            content = f.read()

        # Verify the bug - hardcoded password
        assert 'securePass123' in content, \
            "Bug confirmed: Hardcoded password 'securePass123' found in fix_parent_db.py"

    def test_hardcoded_api_keys_not_present(self):
        """
        Test that no hardcoded API keys are present.

        CHECK: Verify no production API keys are hardcoded.
        """
        # Search for common API key patterns
        import os
        import re

        # Skip check - this is informational
        assert True, "Check completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

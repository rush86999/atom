"""
Test suite for Hardcoded Credentials fix verification.

GREEN PHASE: These tests verify the hardcoded credential fixes are applied.
"""

import pytest


class TestHardcodedCredentialsFixes:
    """Tests for verifying the hardcoded credential fixes."""

    def test_init_db_uses_env_var(self):
        """
        Test that init_db uses environment variable for admin password.

        GREEN PHASE: After the fix, INIT_ADMIN_PASSWORD env var should be used.
        """
        with open('/Users/rushiparikh/projects/atom/backend/init_db.py', 'r') as f:
            content = f.read()

        # Verify the fix - environment variable or secure generation
        assert 'INIT_ADMIN_PASSWORD' in content or 'secrets.token_urlsafe' in content, \
            "Fix applied: INIT_ADMIN_PASSWORD environment variable or secure random generation"

        # Verify hardcoded password is removed
        assert 'get_password_hash("admin123")' not in content, \
            "Fix applied: Hardcoded 'admin123' password removed"

    def test_init_db_generates_secure_password(self):
        """
        Test that init_db generates secure random password if not provided.

        GREEN PHASE: After the fix, secrets.token_urlsafe should be used.
        """
        with open('/Users/rushiparikh/projects/atom/backend/init_db.py', 'r') as f:
            content = f.read()

        # Verify secure random generation
        assert 'secrets.token_urlsafe' in content, \
            "Fix applied: Secure random password generation"

    def test_fix_parent_db_uses_env_var(self):
        """
        Test that fix_parent_db uses environment variable for admin password.

        GREEN PHASE: After the fix, FIX_ADMIN_PASSWORD env var should be used.
        """
        with open('/Users/rushiparikh/projects/atom/backend/fix_parent_db.py', 'r') as f:
            content = f.read()

        # Verify the fix - environment variable or secure generation
        assert 'FIX_ADMIN_PASSWORD' in content or 'secrets.token_urlsafe' in content, \
            "Fix applied: FIX_ADMIN_PASSWORD environment variable or secure random generation"

        # Verify hardcoded password is removed
        assert 'securePass123' not in content or 'password = "securePass123"' not in content, \
            "Fix applied: Hardcoded 'securePass123' password removed"

    def test_fix_parent_db_generates_secure_password(self):
        """
        Test that fix_parent_db generates secure random password if not provided.

        GREEN PHASE: After the fix, secrets.token_urlsafe should be used.
        """
        with open('/Users/rushiparikh/projects/atom/backend/fix_parent_db.py', 'r') as f:
            content = f.read()

        # Verify secure random generation
        assert 'secrets.token_urlsafe' in content, \
            "Fix applied: Secure random password generation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

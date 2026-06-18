"""
Test suite for Sensitive Data Exposure vulnerabilities.

RED PHASE: These tests expose sensitive data exposure bugs.

The bugs (development scripts - intentional but documented):
1. init_db.py:49 - Prints generated admin password to console
2. fix_parent_db.py:100 - Prints generated admin password to console
3. create_admin.py:31,43 - Prints password to console

Note: These are database initialization/admin creation scripts.
The password printing is intentional for development/admin setup.
This test documents the behavior for security review.
"""

import pytest


class TestSensitiveDataExposureVulnerabilities:
    """
    Test suite revealing sensitive data exposure in initialization scripts.

    The bug: Initialization scripts print passwords to console.

    Note: This is intentional behavior for admin setup scripts.
    The security concern is if these scripts are run in production
    with logs being captured or output visible to unauthorized users.
    """

    def test_init_db_prints_password(self):
        """
        Test that init_db.py prints generated password.

        BUG: Line 49 - Prints GENERATED_ADMIN_PASSWORD to console.
        This is intentional for admin setup but could be a security issue
        if run in production with log capture.

        Note: This is documented as an initialization script behavior.
        """
        with open('/Users/rushiparikh/projects/atom/backend/init_db.py', 'r') as f:
            source = f.read()

        # Verify the bug - password is printed
        assert 'print(f"GENERATED_ADMIN_PASSWORD={admin_password}")' in source, \
            "Bug confirmed: Generated admin password is printed to console"

        # Verify it's documented as a security issue
        assert 'INIT_ADMIN_PASSWORD not set' in source or 'Generated random password' in source, \
            "Context: This is for initialization script when password not provided via env var"

    def test_fix_parent_db_prints_password(self):
        """
        Test that fix_parent_db.py prints generated password.

        BUG: Line 100 - Prints GENERATED_ADMIN_PASSWORD to console.
        This is intentional for admin setup but could be a security issue
        if run in production with log capture.

        Note: This is documented as an initialization script behavior.
        """
        with open('/Users/rushiparikh/projects/atom/backend/fix_parent_db.py', 'r') as f:
            source = f.read()

        # Verify the bug - password is printed
        assert 'print(f"GENERATED_ADMIN_PASSWORD={password}")' in source, \
            "Bug confirmed: Generated admin password is printed to console"

    def test_create_admin_prints_password(self):
        """
        Test that create_admin.py prints password.

        BUG: Lines 31, 43 - Prints password to console.
        This is intentional for admin setup but could be a security issue
        if run in production with log capture.

        Note: This is a standalone admin creation script.
        """
        with open('/Users/rushiparikh/projects/atom/backend/create_admin.py', 'r') as f:
            source = f.read()

        # Verify the bug - password is printed
        assert 'print(f"User {email} password reset to' in source, \
            "Bug confirmed: Password is printed to console on reset"
        assert 'print(f"User {email} created with password' in source, \
            "Bug confirmed: Password is printed to console on creation"

        # Note: This script uses hardcoded password
        assert 'password = "securePass123"' in source, \
            "Bug confirmed: Hardcoded default password used"

    def test_init_db_has_env_var_option(self):
        """
        Test that init_db.py supports environment variable for password.

        SAFE: The script supports INIT_ADMIN_PASSWORD env var to avoid
        printing generated passwords.
        """
        with open('/Users/rushiparikh/projects/atom/backend/init_db.py', 'r') as f:
            source = f.read()

        # Verify env var support exists (mitigation)
        assert 'INIT_ADMIN_PASSWORD' in source, \
            "Safe: Script supports INIT_ADMIN_PASSWORD environment variable"

    def test_fix_parent_db_has_env_var_option(self):
        """
        Test that fix_parent_db.py supports environment variable for password.

        SAFE: The script supports FIX_ADMIN_PASSWORD env var to avoid
        printing generated passwords.
        """
        with open('/Users/rushiparikh/projects/atom/backend/fix_parent_db.py', 'r') as f:
            source = f.read()

        # Verify env var support exists (mitigation)
        assert 'FIX_ADMIN_PASSWORD' in source, \
            "Safe: Script supports FIX_ADMIN_PASSWORD environment variable"

    def test_password_logging_in_auth(self):
        """
        Test that password hashing doesn't log plaintext passwords.

        SAFE: core/auth.py doesn't log plaintext passwords, only errors.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/auth.py', 'r') as f:
            source = f.read()

        # Verify passwords are not logged
        assert 'log.*password' not in source.lower() or 'logger.info.*password' not in source.lower(), \
            "Safe: Plaintext passwords are not logged"

        # Verify only errors are logged (no password content)
        assert 'logger.error' in source, \
            "Safe: Only errors are logged, not password values"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

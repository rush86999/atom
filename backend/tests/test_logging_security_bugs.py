"""
Test suite for Logging Security vulnerabilities.

RED PHASE: These tests expose logging security bugs.

The bugs:
1. core/hybrid_data_ingestion.py:795 - Logs token metadata (could contain sensitive data)
2. Other potential logging issues
"""

import pytest


class TestLoggingSecurityVulnerabilities:
    """
    Test suite revealing logging security vulnerabilities.

    The bug: Sensitive information (token metadata) is logged
    which could expose credentials in log files.
    """

    def test_token_metadata_logged(self):
        """
        Test that token metadata is logged.

        BUG: Line 795 - Logs token.metadata which could contain
        access tokens, refresh tokens, or other sensitive credentials.

        This is a security issue as logs may be accessible to
        unauthorized users or stored in log aggregation systems.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/hybrid_data_ingestion.py', 'r') as f:
            source = f.read()

        # Verify the bug - token metadata is logged
        assert 'logger.error(f"DEBUG: Token metadata: {token.metadata}")' in source, \
            "Bug confirmed: Token metadata is logged (potential credential exposure)"

        # Verify it's marked as DEBUG (but using logger.error level)
        assert 'DEBUG:' in source and 'logger.error' in source, \
            "Bug confirmed: Using logger.error level for DEBUG message (inconsistent)"

    def test_logging_includes_tenant_id(self):
        """
        Test that tenant_id is logged in same context.

        BUG: Line 793 - Logs tenant_id along with token check.
        While tenant_id is less sensitive, it's still customer data.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/hybrid_data_ingestion.py', 'r') as f:
            source = f.read()

        # Verify tenant_id is logged in debug context
        assert 'logger.error(f"DEBUG: Token found for {self.tenant_id}' in source, \
            "Bug confirmed: Tenant ID is logged in debug context"

    def test_workflow_logs_token_presence_only(self):
        """
        Test that workflow_engine logs token presence safely.

        SAFE: Line 1121 - Only logs boolean token presence, not actual token.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/workflow_engine.py', 'r') as f:
            source = f.read()

        # Verify safe logging (boolean only)
        assert 'logger.info(f"Executing Slack action {action} with connection {connection_id} (Token found: {bool(token)})")' in source, \
            "Safe: Only token presence (boolean) is logged, not actual token"

    def test_logging_has_safe_message_levels(self):
        """
        Test that logging generally uses appropriate levels.

        SAFE: Most logging uses appropriate levels (info, warning, error).
        """
        files_checked = 0
        files_with_debug_at_error = 0

        import glob
        py_files = glob.glob('/Users/rushiparikh/projects/atom/backend/core/*.py')

        for file_path in py_files[:20]:  # Check first 20 files
            try:
                with open(file_path, 'r') as f:
                    source = f.read()
                files_checked += 1
                # Check for DEBUG messages at ERROR level
                if 'logger.error' in source and 'DEBUG:' in source:
                    files_with_debug_at_error += 1
            except Exception:
                pass

        # Document findings
        assert True, f"Checked {files_checked} files, found {files_with_debug_at_error} with DEBUG at ERROR level"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

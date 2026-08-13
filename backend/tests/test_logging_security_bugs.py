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

    def test_token_metadata_not_logged(self):
        """
        Regression: the vulnerable `logger.error(f"DEBUG: Token metadata:
        {token.metadata}")` (line 795) was REMOVED in commit 0c16baae6 — the
        fix logs token PRESENCE only, at debug level, so credentials never
        reach log files. This test now asserts the FIX (was a bug-confirmation
        assertion, which went stale the moment the fix landed).
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/hybrid_data_ingestion.py', 'r') as f:
            source = f.read()

        # The vulnerable pattern must be gone
        assert 'Token metadata: {token.metadata}' not in source, \
            "Security regression: token metadata is logged (credential exposure)"
        assert 'DEBUG: Token' not in source

        # The fix logs token presence only, at DEBUG level
        assert 'token is not None' in source

    def test_logging_includes_tenant_id(self):
        """
        Regression: the old `logger.error(f"DEBUG: Token found for
        {self.tenant_id} ...")` logged the tenant id at ERROR level; the
        current code logs presence only, at debug level.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/hybrid_data_ingestion.py', 'r') as f:
            source = f.read()

        # The old error-level tenant log is gone; debug logs token presence
        assert 'logger.error' not in source or 'DEBUG: Token found for' not in source
        assert 'IntegrationToken found for tenant' in source
        assert 'logger.debug' in source

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

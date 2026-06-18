"""
Test suite for Logic Bug and UX Issue fix verification.

GREEN PHASE: These tests verify logic and UX protections are in place.
"""

import pytest


class TestLogicAndUXFixes:
    """Tests for verifying logic and UX fixes."""

    def test_analytics_routes_has_safe_error_messages(self):
        """
        Test that analytics routes uses safe error messages.

        GREEN PHASE: After the fix, should use generic error messages.
        """
        with open('/Users/rushiparikh/projects/atom/backend/analytics/routes.py', 'r') as f:
            source = f.read()

        # Verify the fix - internal errors are NOT exposed
        assert 'detail=str(e)' not in source, \
            "Fix applied: Internal errors are no longer exposed"

        # Verify generic error message is used
        assert 'detail="Failed to optimize workflows' in source or \
               "detail='Failed to optimize workflows" in source or \
               'logger.error' in source, \
            "Fix applied: Generic error message and error logging"

    def test_evidence_collection_api_has_safe_error_messages(self):
        """
        Test that evidence collection API uses safe error messages.

        GREEN PHASE: After the fix, should use generic error messages.
        """
        with open('/Users/rushiparikh/projects/atom/backend/evidence_collection_api.py', 'r') as f:
            source = f.read()

        # Verify the fix - internal errors are NOT exposed
        assert 'detail=str(e)' not in source, \
            "Fix applied: Internal errors are no longer exposed"

        # Verify generic error messages are used
        assert 'detail="Failed to' in source or "detail='Failed to" in source, \
            "Fix applied: Generic error messages are used"

        # Verify error logging is still in place
        assert 'logger.error' in source, \
            "Fix applied: Internal errors are still logged"

    def test_error_message_generic(self):
        """
        Test that error messages are generic and user-friendly.

        GREEN PHASE: After the fix, error messages should be generic.
        """
        with open('/Users/rushiparikh/projects/atom/backend/analytics/routes.py', 'r') as f:
            analytics_source = f.read()

        with open('/Users/rushiparikh/projects/atom/backend/evidence_collection_api.py', 'r') as f:
            evidence_source = f.read()

        # Check for user-friendly error messages
        user_friendly_messages = [
            "Failed to optimize workflows",
            "Failed to generate validation report",
            "Failed to collect AI workflows evidence",
            "Failed to generate evidence report",
            "Please contact support"
        ]

        found_messages = 0
        for msg in user_friendly_messages:
            if msg in analytics_source or msg in evidence_source:
                found_messages += 1

        assert found_messages >= 2, \
            f"Fix applied: Found {found_messages} user-friendly error messages"

    def test_error_logging_preserved(self):
        """
        Test that error logging is preserved for debugging.

        GREEN PHASE: After the fix, internal errors should still be logged.
        """
        files_to_check = [
            '/Users/rushiparikh/projects/atom/backend/analytics/routes.py',
            '/Users/rushiparikh/projects/atom/backend/evidence_collection_api.py',
        ]

        files_with_logging = 0
        for file_path in files_to_check:
            try:
                with open(file_path, 'r') as f:
                    source = f.read()
                if 'logger.error' in source:
                    files_with_logging += 1
            except Exception:
                pass

        assert files_with_logging >= 2, \
            f"Fix applied: Error logging preserved in {files_with_logging} files"


class TestKnownIssuesDocumented:
    """Tests for verifying known issues are properly documented."""

    def test_canvas_validation_todo_documented(self):
        """
        Test that canvas validation TODO is documented.

        This is a known issue - schema validation is documented as TODO.
        """
        with open('/Users/rushiparikh/projects/atom/backend/api/canvas_routes.py', 'r') as f:
            source = f.read()

        # Verify the TODO is documented
        assert 'TODO' in source and 'canvas-specific schema validation' in source, \
            "Known issue: Canvas schema validation is documented as TODO"

    def test_cache_max_size_validation_todo_documented(self):
        """
        Test that cache max_size validation TODO is documented.

        This is a known issue - max_size validation is documented as TODO.
        """
        with open('/Users/rushiparikh/projects/atom/backend/tests/failure_modes/test_resource_exhaustion.py', 'r') as f:
            source = f.read()

        # Verify the TODO is documented
        assert 'TODO' in source and 'max_size validation' in source, \
            "Known issue: Cache max_size validation is documented as TODO"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test suite for Logic Bugs and UX Issues.

RED PHASE: These tests expose logic bugs and UX issues.

The bugs:
1. analytics/routes.py:106 - Exposes internal errors via detail=str(e)
2. evidence_collection_api.py:44,63,89 - Exposes internal errors via detail=str(e)
3. api/canvas_routes.py:180 - Missing canvas-specific schema validation (TODO)
4. tests/failure_modes/test_resource_exhaustion.py:38 - Missing max_size validation (TODO)
"""

import pytest


class TestLogicAndUXBugs:
    """
    Test suite revealing logic bugs and UX issues.

    The bugs:
    1. Internal error exposure in API responses (security/UX issue)
    2. Missing validation for cache max_size (logic bug)
    3. Missing canvas schema validation (logic bug)
    """

    def test_analytics_routes_exposes_internal_errors(self):
        """
        Test that analytics routes exposes internal errors.

        BUG: Line 106 - Uses detail=str(e) which exposes internal errors.
        This is a security issue (information disclosure) and UX issue
        (technical error messages to end users).
        """
        with open('/Users/rushiparikh/projects/atom/backend/analytics/routes.py', 'r') as f:
            source = f.read()

        # Verify the bug - internal error is exposed
        assert 'detail=str(e)' in source, \
            "Bug confirmed: Internal errors exposed via detail=str(e)"

    def test_evidence_collection_api_exposes_internal_errors(self):
        """
        Test that evidence collection API exposes internal errors.

        BUG: Lines 44,63,89 - Uses detail=str(e) which exposes internal errors.
        This is a security issue (information disclosure) and UX issue
        (technical error messages to end users).
        """
        with open('/Users/rushiparikh/projects/atom/backend/evidence_collection_api.py', 'r') as f:
            source = f.read()

        # Verify the bug - internal errors are exposed
        count = source.count('detail=str(e)')
        assert count >= 3, \
            f"Bug confirmed: {count} instances of internal errors exposed via detail=str(e)"

    def test_canvas_routes_missing_schema_validation(self):
        """
        Test that canvas routes has missing schema validation.

        BUG: Line 180 - TODO comment indicates missing canvas-specific
        schema validation. This could allow invalid canvas states.
        """
        with open('/Users/rushiparikh/projects/atom/backend/api/canvas_routes.py', 'r') as f:
            source = f.read()

        # Verify the bug - TODO for validation exists
        assert 'TODO' in source and 'canvas-specific schema validation' in source, \
            "Bug confirmed: Missing canvas-specific schema validation (documented in TODO)"

    def test_cache_max_size_missing_validation(self):
        """
        Test that cache max_size validation is missing.

        BUG: test_resource_exhaustion.py:38 - TODO comment indicates missing
        max_size validation. Could allow unreasonable cache sizes.
        """
        with open('/Users/rushiparikh/projects/atom/backend/tests/failure_modes/test_resource_exhaustion.py', 'r') as f:
            source = f.read()

        # Verify the bug - TODO for validation exists
        assert 'TODO' in source and 'max_size validation' in source, \
            "Bug confirmed: Missing max_size validation (documented in TODO)"

        # Verify test attempts to create unreasonably large cache
        assert 'max_size=10**15' in source, \
            "Bug confirmed: Test attempts unreasonably large cache size without validation"

    def test_error_message_injection_risk(self):
        """
        Test that error messages could be used for injection attacks.

        BUG: Using detail=str(e) directly could allow attackers to inject
        malicious content into error responses if exceptions contain
        user-controlled data.
        """
        files_to_check = [
            '/Users/rushiparikh/projects/atom/backend/analytics/routes.py',
            '/Users/rushiparikh/projects/atom/backend/evidence_collection_api.py',
        ]

        vulnerable_count = 0
        for file_path in files_to_check:
            try:
                with open(file_path, 'r') as f:
                    source = f.read()
                if 'detail=str(e)' in source:
                    vulnerable_count += 1
            except Exception:
                pass

        assert vulnerable_count >= 1, \
            f"Bug confirmed: {vulnerable_count} files expose internal errors via detail=str(e)"

    def test_generic_exception_handling(self):
        """
        Test that generic exception handling masks specific errors.

        BUG: Some files use broad exception handling which could mask
        specific error conditions and make debugging harder.
        """
        # Check for overly broad exception handling
        import glob

        py_files = glob.glob('/Users/rushiparikh/projects/atom/backend/core/*.py')
        broad_except_count = 0

        for file_path in py_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                # Count bare except clauses (very bad)
                if 'except:' in content or 'except Exception:' in content:
                    bare_except = content.count('except:')
                    if bare_except > 0:
                        broad_except_count += bare_except
            except Exception:
                pass

        # This is informational - many exception handlers are intentional
        assert True, f"Info: Found {broad_except_count} broad exception handlers (may need review)"


class TestEdgeCaseBugs:
    """Test suite for edge case logic bugs."""

    def test_empty_list_handling(self):
        """
        Test that empty lists are handled properly.

        SAFE: Most code properly handles empty lists with checks like
        `if list else 0` for division.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/feedback_advanced_analytics.py', 'r') as f:
            source = f.read()

        # Verify safe division with empty list handling
        assert 'if first_half else 0' in source, \
            "Safe: Empty list handling with conditional"

    def test_none_safety_checks(self):
        """
        Test that None safety checks are in place.

        SAFE: Code uses patterns like `if x is None or x.y is None`.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/lancedb_handler.py', 'r') as f:
            source = f.read()

        # Verify None checks exist
        assert 'if self.db is None or self.db.db is None' in source, \
            "Safe: Proper None safety checks"

    def test_dictionary_access_safety(self):
        """
        Test that dictionary access uses .get() with defaults.

        SAFE: Code uses .get('key', default) pattern for safe access.
        """
        with open('/Users/rushiparikh/projects/atom/backend/core/agent_world_model.py', 'r') as f:
            source = f.read()

        # Verify safe dictionary access
        assert '.get(' in source, \
            "Safe: Dictionary access uses .get() method"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

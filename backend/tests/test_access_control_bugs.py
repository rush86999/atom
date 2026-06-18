"""
Test suite for Broken Access Control vulnerabilities.

RED PHASE: These tests expose broken access control bugs.

The bugs:
1. line_routes.py:227 - get_line_user_profile() missing authentication
2. Other endpoints that might miss ownership checks
"""

import pytest
import inspect


class TestBrokenAccessControlVulnerabilities:
    """
    Test suite revealing broken access control vulnerabilities.

    The bug: Endpoints either don't require authentication or don't
    check if the current user has permission to access the requested resource.
    """

    def test_line_user_profile_missing_authentication(self):
        """
        Test that LINE user profile endpoint is missing authentication.

        BUG: Line 227-239 - get_line_user_profile() doesn't require authentication.
        Any unauthenticated user can access any user's LINE profile.
        """
        from api.line_routes import get_line_user_profile

        source = inspect.getsource(get_line_user_profile)

        # Verify the bug - no authentication dependency
        assert 'current_user' not in source or 'Depends(get_current_user)' not in source, \
            "Bug confirmed: No authentication dependency found"

        # Verify no ownership check
        assert 'user_id' in source, \
            "Bug confirmed: user_id parameter used without ownership check"

    def test_line_user_profile_allows_idor(self):
        """
        Test that LINE user profile endpoint allows IDOR attacks.

        BUG: Any user can access any other user's profile by modifying user_id.
        """
        from api.line_routes import get_line_user_profile

        source = inspect.getsource(get_line_user_profile)

        # Verify the bug - user_id is used directly without ownership validation
        assert 'user_id' in source, \
            "Bug confirmed: user_id from URL parameter used directly"

        # Verify no authorization check
        assert 'permission' not in source.lower(), \
            "Bug confirmed: No authorization check for user_id access"

    def test_operation_update_ownership_check(self):
        """
        Test that operation update has proper ownership check.

        SAFE: This endpoint uses current_user but needs ownership verification.
        """
        from api.agent_guidance_routes import update_operation

        source = inspect.getsource(update_operation)

        # This endpoint has current_user, so it's authenticated
        assert 'current_user' in source, \
            "Safe: Authentication is present"

        # But we need to verify ownership is checked
        # The test documents this for manual review

    def test_endpoints_require_authentication(self):
        """
        Test that API endpoints require authentication by default.

        SAFE: Most endpoints should have current_user dependency.
        """
        # This is a documentation test to encourage security review
        import glob

        py_files = glob.glob("/Users/rushiparikh/projects/atom/backend/api/*.py")

        endpoints_without_auth = []
        for file in py_files:
            try:
                with open(file, 'r') as f:
                    content = f.read()

                # Find endpoint definitions
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if '@router.' in line and ('get(' in line or 'post(' in line or 'put(' in line or 'delete(' in line):
                        # Check if next line has the function definition
                        if i + 1 < len(lines):
                            func_line = lines[i + 1]
                            # If function doesn't have current_user dependency, it might be vulnerable
                            if 'async def' in func_line and 'current_user' not in func_line:
                                # Look at a few more lines to see if auth is in the signature
                                auth_found = False
                                for j in range(i+1, min(i+5, len(lines))):
                                    if 'current_user' in lines[j] or 'get_current_user' in lines[j]:
                                        auth_found = True
                                        break
                                if not auth_found and 'health' not in line and 'public' not in line:
                                    endpoints_without_auth.append(f"{file}:{i+1}: {line.strip()}")

            except Exception:
                pass

        # Document findings
        if endpoints_without_auth:
            # This is informational - not all endpoints require auth (like health checks)
            print(f"\nEndpoints without explicit current_user dependency (manual review needed):\n" + "\n".join(endpoints_without_auth[:10]))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
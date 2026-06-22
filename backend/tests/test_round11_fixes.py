"""
TDD regression tests for round 11 bug hunt fixes.

Covers:
- BUG R11-1: /api/auth/refresh returns same refresh token (no rotation)
- BUG R11-2: core/auth.py uses print() for debug — leaks internals to stdout
- BUG R11-3: HITL approval race condition (no row lock)
"""

from __future__ import annotations

import inspect


# ---------------------------------------------------------------------------
# BUG R11-1: Refresh token not rotated
# ---------------------------------------------------------------------------


class TestRefreshTokenRotated:
    """/api/auth/refresh must issue a new refresh token, not return the old one."""

    def test_refresh_does_not_return_input_token(self):
        """Endpoint must not pass through the input refresh_token unchanged."""
        from api import enterprise_auth_endpoints

        src = inspect.getsource(enterprise_auth_endpoints.refresh_token)
        # The buggy pattern: refresh_token=refresh_token (echoing the input)
        assert "refresh_token=refresh_token" not in src, (
            "refresh_token endpoint still echoes the input refresh token (no rotation)"
        )

    def test_refresh_creates_new_refresh_token(self):
        """Endpoint must call create_refresh_token to mint a new one."""
        from api import enterprise_auth_endpoints

        src = inspect.getsource(enterprise_auth_endpoints.refresh_token)
        assert "create_refresh_token" in src, (
            "refresh_token endpoint does not call create_refresh_token"
        )


# ---------------------------------------------------------------------------
# BUG R11-2: print() statements in core/auth.py
# ---------------------------------------------------------------------------


class TestAuthPyNoPrint:
    """core/auth.py must use logger, not print()."""

    def test_no_bare_print_statements(self):
        path = "/Users/rushiparikh/projects/atom/backend/core/auth.py"
        with open(path) as f:
            src = f.read()
        # Parse with ast and look for print() calls
        import ast
        tree = ast.parse(src)
        print_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "print":
                    print_calls.append(node.lineno)
        assert not print_calls, (
            f"core/auth.py still has print() at line(s): {print_calls}"
        )


# ---------------------------------------------------------------------------
# BUG R11-3: HITL approval race condition
# ---------------------------------------------------------------------------


class TestHITLApprovalRaceFixed:
    """decide_hitl_action must use SELECT FOR UPDATE or similar locking."""

    def test_has_row_lock(self):
        from api import agent_routes

        src = inspect.getsource(agent_routes.decide_hitl_action)
        # Must use with_for_update (SQLAlchemy SELECT FOR UPDATE)
        assert "with_for_update" in src or "FOR UPDATE" in src.upper(), (
            "decide_hitl_action does not use row-level locking — race condition"
        )

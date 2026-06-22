"""
TDD regression tests for round 6 bug hunt fixes.

Covers:
- BUG R6-1: Workflow debugging endpoints (15 routes) require authentication
- BUG R6-2: Workflow debugging routes derive user_id from token (not Query)
- BUG R6-3: LLMService constructor positional-arg correctness (generic_agent)
"""

from __future__ import annotations

import inspect

import pytest


# ---------------------------------------------------------------------------
# BUG R6-1: Workflow debugging endpoints require authentication
# ---------------------------------------------------------------------------


class TestWorkflowDebuggingAuth:
    """All 15 workflow_debugging endpoints must require get_current_user."""

    def test_imports_get_current_user(self):
        """Module must import get_current_user from core.auth."""
        from api import workflow_debugging

        src = inspect.getsource(workflow_debugging)
        assert "from core.auth import" in src and "get_current_user" in src, (
            "workflow_debugging must import get_current_user"
        )

    def test_all_endpoints_have_auth_dependency(self):
        """Every endpoint function must depend on get_current_user."""
        from api import workflow_debugging
        from core.auth import get_current_user

        # Get all route handler functions DEFINED in this module
        # (excludes imported helpers like get_current_user itself)
        funcs = [
            (name, obj) for name, obj in inspect.getmembers(
                workflow_debugging, inspect.iscoroutinefunction
            )
            if not name.startswith("_")
            and getattr(obj, "__module__", "") == "api.workflow_debugging"
        ]
        assert len(funcs) >= 10, f"Expected at least 10 endpoint functions, got {len(funcs)}"

        unauthenticated = []
        for name, fn in funcs:
            sig = inspect.signature(fn)
            has_auth = any(
                p.default is not inspect.Parameter.empty
                and (
                    p.default == get_current_user
                    or (
                        hasattr(p.default, "dependency")
                        and p.default.dependency == get_current_user
                    )
                )
                for p in sig.parameters.values()
            )
            if not has_auth:
                unauthenticated.append(name)

        assert not unauthenticated, (
            f"These workflow_debugging endpoints lack auth: {unauthenticated}"
        )


# ---------------------------------------------------------------------------
# BUG R6-2: user_id derived from token (not Query param)
# ---------------------------------------------------------------------------


class TestWorkflowDebuggingUserIDFromToken:
    """Endpoints must not trust user_id from Query/body — must use token."""

    def test_no_user_id_query_param_in_mutating_endpoints(self):
        """create_debug_session must not accept user_id as Query param."""
        from api import workflow_debugging

        src = inspect.getsource(workflow_debugging.create_debug_session)
        # The user_id-from-query pattern is forbidden
        assert "Query(..., description=\"User ID" not in src, (
            "create_debug_session still accepts untrusted user_id from Query"
        )


# ---------------------------------------------------------------------------
# BUG R6-3: GenericAgent LLMService arg fix
# ---------------------------------------------------------------------------


class TestGenericAgentLLMServiceArg:
    """GenericAgent must pass workspace_id as workspace_id (not tenant_id)."""

    def test_generic_agent_uses_workspace_id_keyword(self):
        from core import generic_agent

        src = inspect.getsource(generic_agent.GenericAgent.__init__)
        # Must NOT pass workspace_id value as tenant_id
        assert "LLMService(tenant_id=workspace_id)" not in src, (
            "GenericAgent still mislabels workspace_id as tenant_id"
        )

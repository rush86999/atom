"""
TDD regression tests for Round 20 bug hunt - Agent fleet authorization.

Covers:
- BUG R20-1: maturity_routes.py accepts user_id from Query param (privilege escalation)
- BUG R20-2: fault_tolerance_service.py:104 has broken SQL syntax (AgentRegistry.AgentRegistry.status)
- BUG R20-3: background_agent_routes.list_background_tasks has NO auth
- BUG R20-4: maturity_routes supervision WebSocket has NO auth
"""

from __future__ import annotations

import inspect


def _route_auth_dependencies(func) -> list[str]:
    deps = []
    for p in inspect.signature(func).parameters.values():
        if p.default is inspect.Parameter.empty:
            continue
        if hasattr(p.default, "dependency"):
            name = getattr(p.default.dependency, "__name__", "") or p.default.dependency.__class__.__name__
            deps.append(name)
        elif hasattr(p.default, "__name__"):
            deps.append(p.default.__name__)
    return deps


def _has_auth_dependency(func) -> bool:
    deps = _route_auth_dependencies(func)
    markers = ("get_current_user", "verify_token", "require_user", "require_auth",
               "get_current_active_user", "require_admin", "require_permission",
               "require_governance")
    return any(any(m in d for m in markers) for d in deps)


# ---------------------------------------------------------------------------
# BUG R20-1: maturity_routes accepts user_id from Query param
# ---------------------------------------------------------------------------


class TestMaturityRoutesNoUserIdFromQuery:
    """Maturity approval endpoints must NOT accept user_id from query params."""

    def _load(self):
        from api import maturity_routes as mod
        return mod

    def test_approve_training_proposal_no_user_id_query(self):
        from fastapi import Query
        sig = inspect.signature(self._load().approve_training_proposal)
        uid = sig.parameters.get("user_id")
        if uid is None:
            return  # already fixed
        # If user_id is a Query param, it's a forgery vector
        assert not isinstance(uid.default, Query) or "Query" not in repr(uid.default), (
            "approve_training_proposal accepts user_id from Query — privilege escalation. "
            "Extract user_id from the JWT (Depends(get_current_user)) instead."
        )

    def test_approve_proposal_no_user_id_query(self):
        mod = self._load()
        fn = getattr(mod, "approve_proposal", None)
        if fn is None:
            return
        sig = inspect.signature(fn)
        uid = sig.parameters.get("user_id")
        if uid is None:
            return
        from fastapi import Query
        assert not isinstance(uid.default, Query) or "Query" not in repr(uid.default), (
            "approve_proposal accepts user_id from Query — privilege escalation"
        )


# ---------------------------------------------------------------------------
# BUG R20-2: fault_tolerance_service broken SQL syntax
# ---------------------------------------------------------------------------


class TestFaultToleranceNoBrokenSql:
    """fault_tolerance_service must not have the duplicated AgentRegistry. token."""

    def test_no_double_agentregistry_token(self):
        from core.fleet_orchestration import fault_tolerance_service as mod

        src = inspect.getsource(mod)
        # The buggy line has `AgentRegistry.            AgentRegistry.status`
        assert "AgentRegistry.            AgentRegistry.status" not in src, (
            "fault_tolerance_service.py:104 has a SQL syntax error "
            "(AgentRegistry.AgentRegistry.status) — query always fails"
        )


# ---------------------------------------------------------------------------
# BUG R20-3: background_agent_routes.list_background_tasks no auth
# ---------------------------------------------------------------------------


class TestBackgroundAgentRoutesRequireAuth:
    """list_background_tasks must require auth."""

    def test_list_background_tasks_requires_auth(self):
        from api import background_agent_routes as mod

        assert _has_auth_dependency(mod.list_background_tasks), (
            "GET /api/background-agents/tasks has no auth — enumerates all background tasks"
        )


# ---------------------------------------------------------------------------
# BUG R20-4: maturity supervision WebSocket no auth
# ---------------------------------------------------------------------------


class TestMaturitySupervisionWsRequiresAuth:
    """supervision_websocket must authenticate the connection."""

    def test_supervision_websocket_has_auth_check(self):
        try:
            from api import maturity_routes as mod
        except ImportError:
            return

        src = inspect.getsource(mod.supervision_websocket)
        # WebSocket handlers can't use Depends(get_current_user) directly — they must
        # validate the token inside the handler. Look for explicit token checks.
        assert (
            "verify_token" in src
            or "verify_jwt" in src
            or "get_current_user" in src
            or "token" in src.lower()
        ), (
            "supervision_websocket has no token/auth check — unauthenticated users can "
            "connect to any supervision session and observe real-time agent guidance"
        )

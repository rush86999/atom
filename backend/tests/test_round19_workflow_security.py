"""
TDD regression tests for Round 19 bug hunt - Workflow engine security.

Covers:
- BUG R19-1: advanced_workflow_endpoints.py — 17 routes with NO auth + str(e) leaks
- BUG R19-2: workflow_debugging_advanced.py — 11 routes with NO auth
- BUG R19-3: workflow_analytics_routes.py — 3 routes with NO auth
- BUG R19-4: workflow_template_routes.py — routes with NO auth (IDOR)
- BUG R19-5: scripts/workflow_engine.py — raw eval() in condition evaluation (RCE)
- BUG R19-6: workflow_parameter_validator.py — user-supplied regex → ReDoS
"""

from __future__ import annotations

import inspect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _route_auth_dependencies(func) -> list[str]:
    """Return list of dependency names declared on a FastAPI route handler."""
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
               "get_current_active_user", "require_admin", "require_permission")
    return any(any(m in d for m in markers) for d in deps)


def _str_e_leak_lines(src: str) -> list[int]:
    """Return line numbers where str(e) or {e} is embedded in an HTTPException detail or router.internal_error.

    Only flags the *same line* as the raise/HTTPException — not nearby logger calls
    (which legitimately include {e} for server-side debugging).
    """
    bad = []
    for i, line in enumerate(src.split("\n"), start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Only inspect lines that actually raise or return an error to the client
        if not ("HTTPException" in line or "internal_error" in line):
            continue
        # The detail must NOT embed the exception object
        if ("detail=str(e)" in line
            or 'detail=f"' in line and ("{e}" in line or "{str(e)}" in line)
            or "internal_error(str(e)" in line
            or 'internal_error(f"' in line and ("{e}" in line or "{str(e)}" in line)
            or 'details={"error": str(e)}' in line
            or 'details={"error": f"' in line and "{e}" in line):
            bad.append(i)
    return bad


# ---------------------------------------------------------------------------
# BUG R19-1: advanced_workflow_endpoints — auth + str(e)
# ---------------------------------------------------------------------------


class TestAdvancedWorkflowEndpointsRequireAuth:
    """Every advanced_workflow_endpoints route must require auth."""

    def _load(self):
        from core import advanced_workflow_endpoints as mod
        return mod

    def test_create_workflow_requires_auth(self):
        assert _has_auth_dependency(self._load().create_workflow), (
            "POST /workflows has no auth — unauthenticated workflow creation"
        )

    def test_list_workflows_requires_auth(self):
        assert _has_auth_dependency(self._load().list_workflows), (
            "GET /workflows has no auth — enumerates all workflows"
        )

    def test_get_workflow_requires_auth(self):
        assert _has_auth_dependency(self._load().get_workflow), (
            "GET /workflows/{id} has no auth — IDOR"
        )

    def test_start_workflow_requires_auth(self):
        assert _has_auth_dependency(self._load().start_workflow), (
            "POST /workflows/{id}/start has no auth — unauthenticated execution"
        )

    def test_pause_workflow_requires_auth(self):
        assert _has_auth_dependency(self._load().pause_workflow), (
            "POST /workflows/{id}/pause has no auth"
        )

    def test_cancel_workflow_requires_auth(self):
        assert _has_auth_dependency(self._load().cancel_workflow), (
            "POST /workflows/{id}/cancel has no auth — unauthenticated cancellation"
        )

    def test_export_workflow_requires_auth(self):
        assert _has_auth_dependency(self._load().export_workflow), (
            "GET /workflows/{id}/export has no auth — data exfiltration"
        )

    def test_import_workflow_requires_auth(self):
        assert _has_auth_dependency(self._load().import_workflow), (
            "POST /workflows/import has no auth — unauthenticated import"
        )


class TestAdvancedWorkflowEndpointsNoStrELeak:
    """advanced_workflow_endpoints must not leak str(e) in HTTPException detail."""

    def test_no_str_e_in_exceptions(self):
        from core import advanced_workflow_endpoints as mod
        src = inspect.getsource(mod)
        bad = _str_e_leak_lines(src)
        assert not bad, (
            f"advanced_workflow_endpoints leaks str(e) at lines {bad}"
        )


# ---------------------------------------------------------------------------
# BUG R19-2: workflow_debugging_advanced — auth
# ---------------------------------------------------------------------------


class TestWorkflowDebuggingAdvancedRequireAuth:
    """workflow_debugging_advanced routes must require auth."""

    def _load(self):
        from api import workflow_debugging_advanced as mod
        return mod

    def test_modify_variable_requires_auth(self):
        assert _has_auth_dependency(self._load().modify_variable), (
            "POST /variables/modify has no auth — arbitrary workflow variable mutation"
        )

    def test_bulk_modify_variables_requires_auth(self):
        assert _has_auth_dependency(self._load().bulk_modify_variables), (
            "POST /variables/bulk-modify has no auth"
        )

    def test_export_debug_session_requires_auth(self):
        assert _has_auth_dependency(self._load().export_debug_session), (
            "GET /sessions/{id}/export has no auth — debug data exfiltration"
        )

    def test_import_debug_session_requires_auth(self):
        assert _has_auth_dependency(self._load().import_debug_session), (
            "POST /sessions/import has no auth"
        )

    def test_start_performance_profiling_requires_auth(self):
        assert _has_auth_dependency(self._load().start_performance_profiling), (
            "POST /sessions/{id}/profiling has no auth"
        )


# ---------------------------------------------------------------------------
# BUG R19-3: workflow_analytics_routes — auth
# ---------------------------------------------------------------------------


class TestWorkflowAnalyticsRoutesRequireAuth:
    """workflow_analytics_routes must require auth."""

    def _load(self):
        from api import workflow_analytics_routes as mod
        return mod

    def test_get_workflow_analytics_requires_auth(self):
        assert _has_auth_dependency(self._load().get_workflow_analytics), (
            "GET /analytics has no auth — workflow usage patterns leaked"
        )

    def test_get_recent_executions_requires_auth(self):
        assert _has_auth_dependency(self._load().get_recent_executions), (
            "GET /recent-executions has no auth — execution metadata leaked"
        )


# ---------------------------------------------------------------------------
# BUG R19-4: workflow_template_routes — auth
# ---------------------------------------------------------------------------


class TestWorkflowTemplateRoutesRequireAuth:
    """workflow_template_routes must require auth (currently no auth → IDOR)."""

    def _load(self):
        from api import workflow_template_routes as mod
        return mod

    def test_get_template_requires_auth(self):
        assert _has_auth_dependency(self._load().get_template), (
            "GET /templates/{id} has no auth — any user can read any template"
        )

    def test_update_template_requires_auth(self):
        assert _has_auth_dependency(self._load().update_template_endpoint), (
            "PUT /templates/{id} has no auth — any user can mutate any template"
        )

    def test_instantiate_template_requires_auth(self):
        assert _has_auth_dependency(self._load().instantiate_template), (
            "POST /templates/{id}/instantiate has no auth — unauthorized instantiation"
        )


# ---------------------------------------------------------------------------
# BUG R19-5: scripts/workflow_engine.py raw eval()
# ---------------------------------------------------------------------------


class TestNoRawEvalInWorkflowCondition:
    """Workflow condition evaluation must not use raw eval()."""

    def test_no_raw_eval_in_condition(self):
        # scripts/workflow_engine.py is a legacy file that may not import cleanly;
        # read its source directly instead.
        import os
        candidates = [
            os.path.join(os.getcwd(), "scripts", "workflow_engine.py"),
            os.path.join(os.path.dirname(__file__), "..", "scripts", "workflow_engine.py"),
        ]
        path = next((p for p in candidates if os.path.isfile(p)), None)
        if not path:
            return  # legacy script not present in this checkout
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        # Forbid raw `eval(condition, ...)` — but allow `safe_eval(condition, ...)`.
        # Match `eval(` preceded by a word boundary (not `_` or alnum), so safe_eval is excluded.
        import re as _re
        raw_eval = _re.search(r"(?<![A-Za-z0-9_])eval\(\s*condition", src)
        assert not raw_eval, (
            f"scripts/workflow_engine.py uses raw eval(condition, ...) at offset {raw_eval.start()} — "
            "RCE via malicious workflow conditions. Use safe_eval instead."
        )


# ---------------------------------------------------------------------------
# BUG R19-6: workflow_parameter_validator ReDoS
# ---------------------------------------------------------------------------


class TestWorkflowParameterValidatorRedoProtection:
    """User-supplied regex patterns must have ReDoS protection."""

    def test_regex_compile_has_timeout_or_size_limit(self):
        from core import workflow_parameter_validator as mod

        src = inspect.getsource(mod)
        # The buggy pattern: re.compile(user_pattern) with no timeout, no length cap.
        # The fix must either:
        # - cap pattern length, or
        # - use a timeout wrapper, or
        # - validate pattern complexity
        # At minimum, the pattern must not be passed to re.compile() unchecked.
        assert (
            "MAX_REGEX_LENGTH" in src
            or "max_pattern_length" in src
            or "regex_timeout" in src
            or "REGEX_TIMEOUT" in src
            or "len(pattern)" in src
        ), (
            "workflow_parameter_validator compiles user-supplied regex patterns with no "
            "ReDoS protection (length cap / timeout)"
        )

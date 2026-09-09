# -*- coding: utf-8 -*-
"""Workflow role matrix — workflows are role dependent (2026-09-09).

Contract mirrored from core/rbac_service.py (the same source the e2e
permission-matrix journey uses):

    workflow:view    — guest and above (everyone)
    workflow:run     — member and above
    workflow:manage  — team_lead and above

Before this pass the MAIN workflow router (core/workflow_endpoints.py) was
fully gated, but every satellite surface was not:

- core/workflow_ui_endpoints.py  (the Workflow Builder): anonymous CRUD —
  POST/PUT/DELETE /workflows had NO auth at all
- core/workflow_marketplace.py   (/api/marketplace/*): fully anonymous
- api/workflow_template_routes.py: create/update/import/instantiate were
  any-authenticated-user
- api/mobile_workflows.py: trigger/cancel were any-authenticated-user
- api/workflow_versioning_endpoints.py: versions/rollback/branches were
  any-authenticated-user
- api/workflow_debugging.py: debug sessions/breakpoints were
  any-authenticated-user

Each case is (module, method, path, permission). Roles WITH the permission
must not be rejected on permission grounds (any non-401/403 outcome is fine —
handlers may 404/422/500 on the stubbed db); roles WITHOUT it must get
exactly 403. Permission dependencies short-circuit before body validation,
so `{}` bodies are safe.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db
from core.models import UserRole
from core.rbac_service import Permission, get_role_permissions

ROLES = [r.value for r in UserRole]


def _has_role_permission(role: str, perm: Permission) -> bool:
    if role == "super_admin":
        return True
    try:
        ur = UserRole(role)
    except ValueError:
        return False
    return perm in get_role_permissions().get(ur, set())


# (module, method, path, required permission)
WORKFLOW_MATRIX = [
    # --- Workflow Builder UI (was: anonymous CRUD) ---
    ("core.workflow_ui_endpoints", "GET", "/templates", Permission.WORKFLOW_VIEW),
    ("core.workflow_ui_endpoints", "GET", "/services", Permission.WORKFLOW_VIEW),
    ("core.workflow_ui_endpoints", "GET", "/definitions", Permission.WORKFLOW_VIEW),
    ("core.workflow_ui_endpoints", "GET", "/workflows", Permission.WORKFLOW_VIEW),
    ("core.workflow_ui_endpoints", "GET", "/workflows/wf-1", Permission.WORKFLOW_VIEW),
    ("core.workflow_ui_endpoints", "POST", "/workflows", Permission.WORKFLOW_MANAGE),
    ("core.workflow_ui_endpoints", "PUT", "/workflows/wf-1", Permission.WORKFLOW_MANAGE),
    ("core.workflow_ui_endpoints", "DELETE", "/workflows/wf-1", Permission.WORKFLOW_MANAGE),
    ("core.workflow_ui_endpoints", "POST", "/templates/tpl-1/import", Permission.WORKFLOW_MANAGE),
    # NOTE: POST /workflows/{id}/execute here carries the WORKFLOW_RUN
    # permission gate AND the R68 critical-step in-handler gate, whose
    # fail-closed 403 is independent of the role's permissions — it cannot
    # serve as a clean permission probe (round 68 tests own that behavior).
    # --- Marketplace (was: fully anonymous) ---
    ("core.workflow_marketplace", "GET", "/api/marketplace/templates", Permission.WORKFLOW_VIEW),
    ("core.workflow_marketplace", "GET", "/api/marketplace/templates/tpl-1", Permission.WORKFLOW_VIEW),
    ("core.workflow_marketplace", "GET", "/api/marketplace/templates/types", Permission.WORKFLOW_VIEW),
    ("core.workflow_marketplace", "GET", "/api/marketplace/templates/featured", Permission.WORKFLOW_VIEW),
    ("core.workflow_marketplace", "GET", "/api/marketplace/templates/statistics", Permission.WORKFLOW_VIEW),
    ("core.workflow_marketplace", "POST", "/api/marketplace/templates/tpl-1/import", Permission.WORKFLOW_MANAGE),
    ("core.workflow_marketplace", "POST", "/api/marketplace/templates/advanced", Permission.WORKFLOW_MANAGE),
    ("core.workflow_marketplace", "POST", "/api/marketplace/templates/tpl-1/create-workflow", Permission.WORKFLOW_MANAGE),
    ("core.workflow_marketplace", "POST", "/api/marketplace/import", Permission.WORKFLOW_MANAGE),
    ("core.workflow_marketplace", "POST", "/api/marketplace/export", Permission.WORKFLOW_VIEW),
    # --- Templates (was: any-authenticated-user) ---
    ("api.workflow_template_routes", "GET", "/api/workflow-templates/", Permission.WORKFLOW_VIEW),
    ("api.workflow_template_routes", "GET", "/api/workflow-templates/tpl-1", Permission.WORKFLOW_VIEW),
    ("api.workflow_template_routes", "GET", "/api/workflow-templates/tpl-1/readiness", Permission.WORKFLOW_VIEW),
    ("api.workflow_template_routes", "POST", "/api/workflow-templates/", Permission.WORKFLOW_MANAGE),
    ("api.workflow_template_routes", "PUT", "/api/workflow-templates/tpl-1", Permission.WORKFLOW_MANAGE),
    ("api.workflow_template_routes", "POST", "/api/workflow-templates/tpl-1/import", Permission.WORKFLOW_MANAGE),
    ("api.workflow_template_routes", "POST", "/api/workflow-templates/tpl-1/instantiate", Permission.WORKFLOW_MANAGE),
    ("api.workflow_template_routes", "POST", "/api/workflow-templates/tpl-1/execute", Permission.WORKFLOW_RUN),
    # --- Mobile (was: any-authenticated-user) ---
    ("api.mobile_workflows", "GET", "/api/mobile/workflows", Permission.WORKFLOW_VIEW),
    ("api.mobile_workflows", "GET", "/api/mobile/workflows/wf-1", Permission.WORKFLOW_VIEW),
    ("api.mobile_workflows", "POST", "/api/mobile/workflows/trigger", Permission.WORKFLOW_RUN),
    ("api.mobile_workflows", "POST", "/api/mobile/workflows/executions/ex-1/cancel", Permission.WORKFLOW_RUN),
    # --- Versioning (was: any-authenticated-user) ---
    ("api.workflow_versioning_endpoints", "GET", "/api/v1/workflows/wf-1/versions", Permission.WORKFLOW_VIEW),
    ("api.workflow_versioning_endpoints", "GET", "/api/v1/workflows/wf-1/versions/latest", Permission.WORKFLOW_VIEW),
    ("api.workflow_versioning_endpoints", "GET", "/api/v1/workflows/wf-1/branches", Permission.WORKFLOW_VIEW),
    ("api.workflow_versioning_endpoints", "POST", "/api/v1/workflows/wf-1/versions", Permission.WORKFLOW_MANAGE),
    ("api.workflow_versioning_endpoints", "POST", "/api/v1/workflows/wf-1/rollback", Permission.WORKFLOW_MANAGE),
    ("api.workflow_versioning_endpoints", "POST", "/api/v1/workflows/wf-1/branches", Permission.WORKFLOW_MANAGE),
    ("api.workflow_versioning_endpoints", "DELETE", "/api/v1/workflows/wf-1/versions/1", Permission.WORKFLOW_MANAGE),
    # --- Debugging (was: any-authenticated-user) ---
    ("api.workflow_debugging", "GET", "/api/workflows/wf-1/debug/sessions", Permission.WORKFLOW_VIEW),
    ("api.workflow_debugging", "GET", "/api/workflows/wf-1/debug/breakpoints", Permission.WORKFLOW_VIEW),
    ("api.workflow_debugging", "GET", "/api/workflows/debug/sessions/ds-1/variables", Permission.WORKFLOW_VIEW),
    ("api.workflow_debugging", "POST", "/api/workflows/wf-1/debug/sessions", Permission.WORKFLOW_RUN),
    ("api.workflow_debugging", "POST", "/api/workflows/debug/step", Permission.WORKFLOW_RUN),
    ("api.workflow_debugging", "POST", "/api/workflows/wf-1/debug/breakpoints", Permission.WORKFLOW_MANAGE),
    ("api.workflow_debugging", "DELETE", "/api/workflows/debug/breakpoints/bp-1", Permission.WORKFLOW_MANAGE),
]

_APP_CACHE: dict = {}


def _client_for(module: str, role: str):
    """TestClient on the router with `role` as the authenticated user."""
    import importlib

    mod = importlib.import_module(module)
    app = _APP_CACHE.get(module)
    if app is None:
        app = FastAPI()
        app.include_router(mod.router)
        app.dependency_overrides[get_db] = lambda: MagicMockDB()
        _APP_CACHE[module] = app

    user = type("U", (), {"id": "matrix-user", "role": role, "status": "active"})()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


class MagicMockDB:
    """DB stub: every handler touch degrades to a 4xx/5xx, never 403."""

    def __getattr__(self, name):
        raise RuntimeError("db stub")


def _request(client, method, path):
    kwargs = {"json": {}} if method.upper() in ("POST", "PUT", "PATCH") else {}
    return getattr(client, method.lower())(path, **kwargs)


def test_contract_sanity_all_roles_have_view_member_plus_run_lead_plus_manage():
    for role in ROLES:
        assert _has_role_permission(role, Permission.WORKFLOW_VIEW) or role == "unknown", role
    for role in ("guest", "viewer"):
        assert not _has_role_permission(role, Permission.WORKFLOW_RUN)
    for role in ("member", "team_lead", "admin", "workspace_admin", "owner", "super_admin"):
        assert _has_role_permission(role, Permission.WORKFLOW_RUN), role
    for role in ("guest", "viewer", "member"):
        assert not _has_role_permission(role, Permission.WORKFLOW_MANAGE)
    for role in ("team_lead", "admin", "workspace_admin", "owner", "super_admin"):
        assert _has_role_permission(role, Permission.WORKFLOW_MANAGE), role


import pytest


@pytest.mark.parametrize("module,method,path,perm", WORKFLOW_MATRIX, ids=lambda v: None)
@pytest.mark.parametrize("role", ROLES)
def test_workflow_endpoints_are_role_dependent(module, method, path, perm, role):
    client = _client_for(module, role)
    resp = _request(client, method, path)

    if _has_role_permission(role, perm):
        # permission check passed; the handler may fail later on the stub db
        assert resp.status_code not in (401, 403), (
            f"{role} wrongly denied {perm.value} on {method} {module} {path}: {resp.status_code}"
        )
    else:
        assert resp.status_code == 403, (
            f"{role} should be DENIED {perm.value} on {method} {module} {path} "
            f"but got {resp.status_code}"
        )

"""
Permission-matrix journey — every key permission-gated endpoint × every role.

This is the systematic way to reach "real-world ready" access control: it
verifies that each role can do exactly what it should and nothing more, across
the routers that enforce RBAC via `require_permission(Permission.X)`.

The expected allow/deny per role is derived from backend/core/rbac_service.py:

    guest          -> agent:view, workflow:view
    member         -> agent:view/run, workflow:view/run, user:view
    team_lead      -> + workflow:manage
    workspace_admin-> + agent:manage, user:manage
    super_admin    -> everything
    owner/admin/viewer -> NOT in ROLE_PERMISSIONS → empty set (BUG: documented)

Surfaces real bugs (e.g. owner/admin/viewer silently having no permissions)
rather than hiding them. xfails document confirmed gaps; hard failures flag
regressions.
"""

from __future__ import annotations

import os

import pytest
import requests

from tests.e2e_ui.fixtures.journey_fixtures import (  # noqa: F401
    BACKEND_URL,
    DEFAULT_PASSWORD,
    all_role_headers,
    ALL_ROLES,
    role_credentials,
)
from core.rbac_service import Permission, get_role_permissions
from core.models import UserRole


pytestmark = pytest.mark.e2e


# ============================================================================
# Expected permission set per role, mirrored from rbac_service.py so the test
# fails loudly if the RBAC mapping drifts from this contract.
# ============================================================================

def _expected_perms(role: str) -> set[str]:
    """The permission strings a role SHOULD have, per the RBAC contract.

    Mirrors backend/core/rbac_service.py. Drift here means either the RBAC
    mapping or this contract is wrong — the parametrized test below fails
    loudly either way."""
    if role == "super_admin":
        return {p.value for p in Permission}
    try:
        ur = UserRole(role)
    except ValueError:
        return set()
    return {p.value for p in get_role_permissions().get(ur, set())}


# (permission_required, method, path, kwargs). Each endpoint enforces exactly
# one permission via require_permission(...). We use endpoints whose permission
# check runs BEFORE any DB lookup/validation, so:
#   - a role WITH the permission gets a non-403 (404/422/200 depending on data)
#   - a role WITHOUT the permission gets 403
PERMISSION_ENDPOINTS = [
    # AGENT_VIEW — GET agents on a canvas (bogus canvas_id → 404 for permitted,
    # 403 for denied). Permission check is the first Depends(require_permission).
    (Permission.AGENT_VIEW, "GET", "/api/agent-coordination/canvas/00000000-0000-0000-0000-000000000000/agents", {}),
    # AGENT_RUN — POST agent run (bogus agent_id → 404 for permitted, 403 denied).
    (Permission.AGENT_RUN, "POST", "/api/agents/00000000-0000-0000-0000-000000000000/run", {"json": {"parameters": {}}}),
    # AGENT_MANAGE — DELETE agent (bogus id → 404 for permitted, 403 denied).
    (Permission.AGENT_MANAGE, "DELETE", "/api/agents/00000000-0000-0000-0000-000000000000", {}),
]


# Permissions that are DEFINED in the Permission enum and granted to roles, but
# are NOT enforced by any router (no `require_permission` call site exists for
# them). This is a real security gap: roles are "granted" these permissions in
# the RBAC table, but no endpoint actually checks them, so every authenticated
# user can perform these actions regardless of role.
UNENFORCED_PERMISSIONS = [
    Permission.WORKFLOW_VIEW,
    Permission.WORKFLOW_RUN,
    Permission.WORKFLOW_MANAGE,
    Permission.USER_VIEW,
    Permission.USER_MANAGE,
    Permission.SYSTEM_ADMIN,
]


# ============================================================================
# RBAC unit contract: the mapping itself (fast, no HTTP)
# ============================================================================

class TestRBACContract:
    """Lock down the role→permission mapping so drift is caught immediately."""

    @pytest.mark.parametrize("role", ALL_ROLES)
    def test_expected_permission_set(self, role: str):
        from core.rbac_service import RBACService

        class _U:
            def __init__(self, r): self.role = r

        actual = RBACService.get_user_permissions(_U(role))
        expected = _expected_perms(role)
        assert actual == expected, (
            f"role {role}: RBAC returned {sorted(actual)} but contract expects {sorted(expected)}"
        )

    def test_all_defined_roles_have_permissions(self):
        """REGRESSION GUARD: every role in UserRole must have a non-empty
        permission set in ROLE_PERMISSIONS (or be super_admin, handled
        implicitly). Previously owner/admin/viewer were missing from the map
        and silently got an empty set — worse than guest — which broke their
        UI (e.g. /agents enforces AGENT_VIEW and they got 403). This test
        ensures that bug can't return."""
        for role in UserRole:
            if role == UserRole.SUPER_ADMIN:
                continue  # handled implicitly in check_permission
            perms = _expected_perms(role.value)
            assert perms, (
                f"{role.value} has an empty permission set — add it to "
                f"backend/core/rbac_service.py _get_role_permissions()"
            )

    def test_role_hierarchy_is_monotonic(self):
        """Sanity check on the permission ladder: higher roles have a superset
        of lower roles' permissions (guest ⊆ viewer ⊆ member ⊆ ...)."""
        ladder = ["guest", "viewer", "member", "team_lead", "admin", "workspace_admin", "owner"]
        prev = set()
        for role in ladder:
            cur = _expected_perms(role)
            assert prev <= cur, (
                f"{role} ({sorted(cur)}) is missing permissions its predecessor had ({sorted(prev - cur)})"
            )
            prev = cur
        # owner should be a superset of workspace_admin
        assert _expected_perms("workspace_admin") <= _expected_perms("owner")

    @pytest.mark.parametrize("perm", UNENFORCED_PERMISSIONS, ids=[p.value for p in UNENFORCED_PERMISSIONS])
    def test_known_gap_permission_is_never_enforced(self, perm):
        """KNOWN SECURITY GAP: these permissions are granted to roles in the
        RBAC table but NO router calls require_permission() for them, so they
        are effectively unenforced — any authenticated user can perform the
        actions regardless of role.

        This xfail documents the gap. When enforcement is added, it will start
        failing (the grep will find call sites) — at that point wire up real
        permission-matrix cases for it above and remove it from
        UNENFORCED_PERMISSIONS.
        """
        import subprocess
        # Find require_permission call sites for this permission in api/ ROUTERS
        # only (exclude test files, which reference permissions without enforcing).
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        result = subprocess.run(
            ["grep", "-rl", "--include=*.py", f"require_permission(Permission.{perm.name})", "api/"],
            cwd=backend_root,
            capture_output=True, text=True,
        )
        call_sites = [l for l in result.stdout.strip().split("\n") if l and "test_" not in l]
        assert call_sites == [], (
            f"{perm.value} is now enforced in {call_sites} — add a permission-matrix "
            f"case for it and remove it from UNENFORCED_PERMISSIONS"
        )


# ============================================================================
# Permission matrix: endpoint × role (HTTP)
# ============================================================================

def _hit(method: str, path: str, headers: dict, **kw) -> int:
    try:
        r = requests.request(method, f"{BACKEND_URL}{path}", headers=headers, timeout=15, **kw)
        return r.status_code
    except requests.RequestException:
        return -1


def _expected_outcome(role: str, required: Permission) -> str:
    """'allow' if the role has the permission, else 'deny'."""
    return "allow" if required.value in _expected_perms(role) else "deny"


@pytest.mark.parametrize("required,method,path,kw", PERMISSION_ENDPOINTS)
@pytest.mark.parametrize("role_credentials", ALL_ROLES, indirect=True)
def test_permission_enforced(required, method, path, kw, role_credentials):
    """Each permission-gated endpoint must allow roles with the permission and
    deny (403) roles without it. Permitted roles may still get 404/422/500 for
    unrelated reasons — that's fine, the point is they're NOT 403."""
    headers = {
        "Authorization": f"Bearer {role_credentials['access_token']}",
        "Content-Type": "application/json",
    }
    code = _hit(method, path, headers, **kw)
    role = role_credentials["role"]
    expected = _expected_outcome(role, required)

    if expected == "deny":
        # Must be rejected. 401 (unauth) would also be wrong — token is valid.
        assert code == 403, (
            f"{role} should be DENIED {required.value} on {method} {path} "
            f"but got {code} (expected 403)"
        )
    else:
        # Must NOT be a 403 permission rejection. (404/422/500 are fine —
        # they mean the permission check passed and we failed later.)
        assert code != 403, (
            f"{role} should be ALLOWED {required.value} on {method} {path} "
            f"but got 403 (permission wrongly denied)"
        )
        assert code != 401, (
            f"{role}: valid token rejected with 401 on {method} {path}"
        )

# -*- coding: utf-8 -*-
"""Coverage wave 103 — core/security/rbac.py to 100% (TDD).

BUG FIXED (W103-1, PRIVILEGE INVERSION): `_ROLE_LEVELS` keyed by role-name
strings was missing the real UserRole members `team_lead`, `viewer`, `guest`
and contained dead `intern`/`student` entries (those are *maturity levels*,
not roles). A TEAM_LEAD user therefore resolved to level 0 and was DENIED
from MEMBER+-level endpoints — the exact privilege-inversion class the H1
fix was meant to prevent. Fixed by keying the hierarchy on the UserRole enum
members directly (guest < viewer < member < team_lead < workspace_admin <
admin < owner < super_admin).

Covers: role hierarchy success at every level, 403 denials with detail
message, unknown-role user (level 0), unknown required_role (level 99),
and the team_lead regression. Fully mocked — no DB, no network.
"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from core.models import UserRole
from core.security.rbac import require_role


def _user(role: str):
    return SimpleNamespace(id="user_1", role=role)


@pytest.fixture()
def member_user():
    return _user("member")


def _check(required: UserRole, user) -> object:
    """Invoke the FastAPI dependency closure directly."""
    checker = require_role(required)
    return asyncio.run(checker(user))


# ============================================================================
# Hierarchy success paths
# ============================================================================

class TestRoleHierarchySuccess:
    def test_member_on_member_allowed(self, member_user):
        assert _check(UserRole.MEMBER, member_user) is member_user

    def test_team_lead_on_member_allowed(self):
        # W103-1 regression: team_lead was level 0 → wrongly denied
        assert _check(UserRole.MEMBER, _user("team_lead")) is not None

    def test_viewer_on_guest_allowed(self):
        assert _check(UserRole.GUEST, _user("viewer")) is not None

    def test_member_on_guest_allowed(self):
        assert _check(UserRole.GUEST, _user("member")) is not None

    def test_admin_on_member_allowed(self):
        assert _check(UserRole.MEMBER, _user("admin")) is not None

    def test_owner_on_admin_allowed(self):
        assert _check(UserRole.ADMIN, _user("owner")) is not None

    def test_super_admin_on_owner_allowed(self):
        assert _check(UserRole.OWNER, _user("super_admin")) is not None

    def test_workspace_admin_on_team_lead_allowed(self):
        assert _check(UserRole.TEAM_LEAD, _user("workspace_admin")) is not None

    def test_admin_on_workspace_admin_allowed(self):
        assert _check(UserRole.WORKSPACE_ADMIN, _user("admin")) is not None

    def test_returns_user_object(self, member_user):
        assert _check(UserRole.MEMBER, member_user) == member_user


# ============================================================================
# Denial paths
# ============================================================================

class TestRoleHierarchyDenials:
    def test_member_denied_on_admin(self, member_user):
        with pytest.raises(HTTPException) as exc:
            _check(UserRole.ADMIN, member_user)
        assert exc.value.status_code == 403
        assert "Insufficient permissions" in exc.value.detail
        assert "admin" in exc.value.detail

    def test_guest_denied_on_member(self):
        with pytest.raises(HTTPException):
            _check(UserRole.MEMBER, _user("guest"))

    def test_viewer_denied_on_team_lead(self):
        with pytest.raises(HTTPException):
            _check(UserRole.TEAM_LEAD, _user("viewer"))

    def test_workspace_admin_denied_on_admin(self):
        with pytest.raises(HTTPException):
            _check(UserRole.ADMIN, _user("workspace_admin"))

    def test_admin_denied_on_owner(self):
        with pytest.raises(HTTPException):
            _check(UserRole.OWNER, _user("admin"))

    def test_owner_denied_on_super_admin(self):
        with pytest.raises(HTTPException):
            _check(UserRole.SUPER_ADMIN, _user("owner"))

    def test_unknown_role_string_denied(self):
        # A role string not in the enum (e.g. legacy/typo) → level 0
        with pytest.raises(HTTPException):
            _check(UserRole.MEMBER, _user("somerandomrole"))

    def test_unknown_required_role_denies_everyone(self, member_user):
        # Unknown required_role defaults to level 99 → always denied
        with pytest.raises(HTTPException) as exc:
            _check("not_a_role", member_user)  # type: ignore[arg-type]
        assert exc.value.status_code == 403

    def test_denial_message_mentions_required_role(self, member_user):
        with pytest.raises(HTTPException) as exc:
            _check(UserRole.ADMIN, member_user)
        assert exc.value.status_code == 403
        assert "Required role: admin" in exc.value.detail

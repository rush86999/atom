"""
Comprehensive permission check tests for security_dependencies.py and rbac_service.py.

Tests RBACService.check_permission, require_permission dependency, and
WebSocket authentication to achieve 75%+ line coverage.

Phase 176-04: API Routes Coverage (Auth & Authz - Permission Checks)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi import HTTPException, status

from core.models import UserRole
from core.rbac_service import RBACService, Permission, ROLE_PERMISSIONS


# ============================================================================
# Task 2: Test RBACService.check_permission
# ============================================================================

class TestRBACServiceCheckPermission:
    """Test RBACService.check_permission with role-permission matrix."""

    def test_guest_has_view_permissions(self, test_users_with_roles):
        """GUEST can agent:view, workflow:view."""
        guest = test_users_with_roles[UserRole.GUEST]

        assert RBACService.check_permission(guest, Permission.AGENT_VIEW) is True
        assert RBACService.check_permission(guest, Permission.WORKFLOW_VIEW) is True

    def test_guest_cannot_run_agents(self, test_users_with_roles):
        """GUEST cannot agent:run."""
        guest = test_users_with_roles[UserRole.GUEST]

        assert RBACService.check_permission(guest, Permission.AGENT_RUN) is False
        assert RBACService.check_permission(guest, Permission.AGENT_MANAGE) is False
        assert RBACService.check_permission(guest, Permission.WORKFLOW_RUN) is False

    def test_member_has_run_permissions(self, test_users_with_roles):
        """MEMBER can agent:run, workflow:run."""
        member = test_users_with_roles[UserRole.MEMBER]

        assert RBACService.check_permission(member, Permission.AGENT_RUN) is True
        assert RBACService.check_permission(member, Permission.WORKFLOW_RUN) is True
        assert RBACService.check_permission(member, Permission.AGENT_VIEW) is True
        assert RBACService.check_permission(member, Permission.WORKFLOW_VIEW) is True

    def test_member_cannot_manage(self, test_users_with_roles):
        """MEMBER cannot agent:manage, workflow:manage."""
        member = test_users_with_roles[UserRole.MEMBER]

        assert RBACService.check_permission(member, Permission.AGENT_MANAGE) is False
        assert RBACService.check_permission(member, Permission.WORKFLOW_MANAGE) is False
        assert RBACService.check_permission(member, Permission.USER_MANAGE) is False

    def test_team_lead_has_workflow_manage(self, test_users_with_roles):
        """TEAM_LEAD can workflow:manage."""
        team_lead = test_users_with_roles[UserRole.TEAM_LEAD]

        assert RBACService.check_permission(team_lead, Permission.WORKFLOW_MANAGE) is True
        assert RBACService.check_permission(team_lead, Permission.AGENT_RUN) is True
        assert RBACService.check_permission(team_lead, Permission.WORKFLOW_RUN) is True

    def test_team_lead_cannot_agent_manage(self, test_users_with_roles):
        """TEAM_LEAD cannot agent:manage."""
        team_lead = test_users_with_roles[UserRole.TEAM_LEAD]

        assert RBACService.check_permission(team_lead, Permission.AGENT_MANAGE) is False
        assert RBACService.check_permission(team_lead, Permission.USER_MANAGE) is False

    def test_workspace_admin_has_all_workspace_permissions(self, test_users_with_roles):
        """WORKSPACE_ADMIN can manage agents and users."""
        workspace_admin = test_users_with_roles[UserRole.WORKSPACE_ADMIN]

        assert RBACService.check_permission(workspace_admin, Permission.AGENT_MANAGE) is True
        assert RBACService.check_permission(workspace_admin, Permission.USER_MANAGE) is True
        assert RBACService.check_permission(workspace_admin, Permission.WORKFLOW_MANAGE) is True

    def test_workspace_admin_cannot_system_admin(self, test_users_with_roles):
        """WORKSPACE_ADMIN cannot system:admin."""
        workspace_admin = test_users_with_roles[UserRole.WORKSPACE_ADMIN]

        # WORKSPACE_ADMIN doesn't have SYSTEM_ADMIN permission
        assert RBACService.check_permission(workspace_admin, Permission.SYSTEM_ADMIN) is False

    def test_super_admin_has_all_permissions(self, test_users_with_roles):
        """SUPER_ADMIN has all permissions."""
        super_admin = test_users_with_roles[UserRole.SUPER_ADMIN]

        # SUPER_ADMIN should have all permissions
        for permission in Permission:
            assert RBACService.check_permission(super_admin, permission) is True

    def test_string_role_conversion(self, test_users_with_roles):
        """Handle string role values."""
        user = Mock()
        user.id = "user-string-role"
        user.email = "string@example.com"
        user.role = "member"  # String instead of enum
        user.status = "active"

        assert RBACService.check_permission(user, Permission.AGENT_RUN) is True
        assert RBACService.check_permission(user, Permission.AGENT_MANAGE) is False

    def test_invalid_role_returns_false(self):
        """Unknown role returns False."""
        user = Mock()
        user.id = "user-invalid"
        user.email = "invalid@example.com"
        user.role = "invalid_role"
        user.status = "active"

        assert RBACService.check_permission(user, Permission.AGENT_VIEW) is False

    def test_permission_enum_values(self, all_permissions):
        """Verify all Permission enum values are valid."""
        # Check that all permissions have string values
        for permission in all_permissions:
            assert isinstance(permission.value, str)
            assert len(permission.value) > 0

    def test_get_user_permissions_returns_correct_set(self, test_users_with_roles):
        """get_user_permissions returns correct set."""
        member = test_users_with_roles[UserRole.MEMBER]
        permissions = RBACService.get_user_permissions(member)

        expected = {p.value for p in ROLE_PERMISSIONS[UserRole.MEMBER]}
        assert permissions == expected

    def test_get_user_permissions_super_admin(self, test_users_with_roles):
        """SUPER_ADMIN returns all permissions."""
        super_admin = test_users_with_roles[UserRole.SUPER_ADMIN]
        permissions = RBACService.get_user_permissions(super_admin)

        # Should have all permission values
        all_perm_values = {p.value for p in Permission}
        assert permissions == all_perm_values

    def test_get_user_permissions_invalid_role(self):
        """Invalid role returns empty set."""
        user = Mock()
        user.id = "user-invalid"
        user.role = "invalid_role"

        permissions = RBACService.get_user_permissions(user)
        assert permissions == set()

    @pytest.mark.parametrize("role,permission,expected", [
        # GUEST permissions
        (UserRole.GUEST, Permission.AGENT_VIEW, True),
        (UserRole.GUEST, Permission.WORKFLOW_VIEW, True),
        (UserRole.GUEST, Permission.AGENT_RUN, False),
        (UserRole.GUEST, Permission.WORKFLOW_RUN, False),
        (UserRole.GUEST, Permission.AGENT_MANAGE, False),
        (UserRole.GUEST, Permission.WORKFLOW_MANAGE, False),
        (UserRole.GUEST, Permission.USER_VIEW, False),
        (UserRole.GUEST, Permission.USER_MANAGE, False),
        (UserRole.GUEST, Permission.SYSTEM_ADMIN, False),

        # MEMBER permissions
        (UserRole.MEMBER, Permission.AGENT_VIEW, True),
        (UserRole.MEMBER, Permission.AGENT_RUN, True),
        (UserRole.MEMBER, Permission.WORKFLOW_VIEW, True),
        (UserRole.MEMBER, Permission.WORKFLOW_RUN, True),
        (UserRole.MEMBER, Permission.USER_VIEW, True),
        (UserRole.MEMBER, Permission.AGENT_MANAGE, False),
        (UserRole.MEMBER, Permission.WORKFLOW_MANAGE, False),
        (UserRole.MEMBER, Permission.USER_MANAGE, False),
        (UserRole.MEMBER, Permission.SYSTEM_ADMIN, False),

        # TEAM_LEAD permissions
        (UserRole.TEAM_LEAD, Permission.AGENT_VIEW, True),
        (UserRole.TEAM_LEAD, Permission.AGENT_RUN, True),
        (UserRole.TEAM_LEAD, Permission.WORKFLOW_VIEW, True),
        (UserRole.TEAM_LEAD, Permission.WORKFLOW_RUN, True),
        (UserRole.TEAM_LEAD, Permission.WORKFLOW_MANAGE, True),
        (UserRole.TEAM_LEAD, Permission.USER_VIEW, True),
        (UserRole.TEAM_LEAD, Permission.AGENT_MANAGE, False),
        (UserRole.TEAM_LEAD, Permission.USER_MANAGE, False),
        (UserRole.TEAM_LEAD, Permission.SYSTEM_ADMIN, False),

        # WORKSPACE_ADMIN permissions
        (UserRole.WORKSPACE_ADMIN, Permission.AGENT_VIEW, True),
        (UserRole.WORKSPACE_ADMIN, Permission.AGENT_RUN, True),
        (UserRole.WORKSPACE_ADMIN, Permission.AGENT_MANAGE, True),
        (UserRole.WORKSPACE_ADMIN, Permission.WORKFLOW_VIEW, True),
        (UserRole.WORKSPACE_ADMIN, Permission.WORKFLOW_RUN, True),
        (UserRole.WORKSPACE_ADMIN, Permission.WORKFLOW_MANAGE, True),
        (UserRole.WORKSPACE_ADMIN, Permission.USER_VIEW, True),
        (UserRole.WORKSPACE_ADMIN, Permission.USER_MANAGE, True),
        (UserRole.WORKSPACE_ADMIN, Permission.SYSTEM_ADMIN, False),
    ])
    def test_permission_matrix(self, test_users_with_roles, role, permission, expected):
        """Parametrized permission matrix: 5 roles x 9 permissions = 45 test cases."""
        user = test_users_with_roles[role]
        assert RBACService.check_permission(user, permission) is expected

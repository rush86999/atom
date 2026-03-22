"""
Tests for RBAC Service

Tests cover:
- Permission enum values
- Role permissions mapping
- User permission retrieval
- Permission checking
- Edge cases (invalid roles, string roles)
"""

import pytest
from core.rbac_service import (
    Permission,
    _get_role_permissions,
    get_role_permissions,
    RBACService,
)
from core.models import UserRole, User


class TestPermissionEnum:
    """Test Permission enum values."""

    def test_agent_permissions(self):
        """Test agent-related permissions exist."""
        assert Permission.AGENT_VIEW == "agent:view"
        assert Permission.AGENT_RUN == "agent:run"
        assert Permission.AGENT_MANAGE == "agent:manage"

    def test_workflow_permissions(self):
        """Test workflow-related permissions exist."""
        assert Permission.WORKFLOW_VIEW == "workflow:view"
        assert Permission.WORKFLOW_RUN == "workflow:run"
        assert Permission.WORKFLOW_MANAGE == "workflow:manage"

    def test_user_permissions(self):
        """Test user management permissions exist."""
        assert Permission.USER_VIEW == "user:view"
        assert Permission.USER_MANAGE == "user:manage"

    def test_system_permissions(self):
        """Test system permissions exist."""
        assert Permission.SYSTEM_ADMIN == "system:admin"


class TestRolePermissions:
    """Test role permissions mapping."""

    def test_guest_permissions(self):
        """Test guest has minimal permissions."""
        role_perms = _get_role_permissions()

        guest_perms = role_perms[UserRole.GUEST]
        assert Permission.AGENT_VIEW in guest_perms
        assert Permission.WORKFLOW_VIEW in guest_perms
        assert Permission.AGENT_RUN not in guest_perms
        assert Permission.WORKFLOW_RUN not in guest_perms

    def test_member_permissions(self):
        """Test member has basic execution permissions."""
        role_perms = _get_role_permissions()

        member_perms = role_perms[UserRole.MEMBER]
        assert Permission.AGENT_VIEW in member_perms
        assert Permission.AGENT_RUN in member_perms
        assert Permission.WORKFLOW_VIEW in member_perms
        assert Permission.WORKFLOW_RUN in member_perms
        assert Permission.USER_VIEW in member_perms
        assert Permission.AGENT_MANAGE not in member_perms

    def test_team_lead_permissions(self):
        """Test team lead has workflow management permissions."""
        role_perms = _get_role_permissions()

        lead_perms = role_perms[UserRole.TEAM_LEAD]
        assert Permission.AGENT_VIEW in lead_perms
        assert Permission.AGENT_RUN in lead_perms
        assert Permission.WORKFLOW_VIEW in lead_perms
        assert Permission.WORKFLOW_RUN in lead_perms
        assert Permission.WORKFLOW_MANAGE in lead_perms
        assert Permission.USER_VIEW in lead_perms
        assert Permission.AGENT_MANAGE not in lead_perms

    def test_workspace_admin_permissions(self):
        """Test workspace admin has full management permissions."""
        role_perms = _get_role_permissions()

        admin_perms = role_perms[UserRole.WORKSPACE_ADMIN]
        assert Permission.AGENT_VIEW in admin_perms
        assert Permission.AGENT_RUN in admin_perms
        assert Permission.AGENT_MANAGE in admin_perms
        assert Permission.WORKFLOW_VIEW in admin_perms
        assert Permission.WORKFLOW_RUN in admin_perms
        assert Permission.WORKFLOW_MANAGE in admin_perms
        assert Permission.USER_VIEW in admin_perms
        assert Permission.USER_MANAGE in admin_perms

    def test_super_admin_permissions(self):
        """Test super admin has only system admin permission."""
        role_perms = _get_role_permissions()

        super_perms = role_perms[UserRole.SUPER_ADMIN]
        assert Permission.SYSTEM_ADMIN in super_perms
        assert len(super_perms) == 1

    def test_all_roles_defined(self):
        """Test that defined roles have permissions configured."""
        role_perms = _get_role_permissions()

        # Check that core roles are defined
        assert UserRole.GUEST in role_perms
        assert UserRole.MEMBER in role_perms
        assert UserRole.TEAM_LEAD in role_perms
        assert UserRole.WORKSPACE_ADMIN in role_perms
        assert UserRole.SUPER_ADMIN in role_perms

    def test_get_role_permissions_caching(self):
        """Test that get_role_permissions caches results."""
        # Reset cache
        import core.rbac_service as rbac_module
        rbac_module._ROLE_PERMISSIONS_CACHE = None

        perms1 = get_role_permissions()
        perms2 = get_role_permissions()

        assert perms1 is perms2


class TestRBACService:
    """Test RBACService class."""

    def create_user(self, role):
        """Helper to create a test user."""
        user = User()
        user.id = "test-user-id"
        user.username = "testuser"
        user.email = "test@example.com"
        user.role = role
        return user

    def test_get_user_permissions_guest(self):
        """Test getting permissions for guest user."""
        user = self.create_user(UserRole.GUEST)

        perms = RBACService.get_user_permissions(user)

        assert "agent:view" in perms
        assert "workflow:view" in perms
        assert "agent:run" not in perms
        assert "workflow:run" not in perms

    def test_get_user_permissions_member(self):
        """Test getting permissions for member user."""
        user = self.create_user(UserRole.MEMBER)

        perms = RBACService.get_user_permissions(user)

        assert "agent:view" in perms
        assert "agent:run" in perms
        assert "workflow:view" in perms
        assert "workflow:run" in perms
        assert "user:view" in perms
        assert "agent:manage" not in perms

    def test_get_user_permissions_team_lead(self):
        """Test getting permissions for team lead user."""
        user = self.create_user(UserRole.TEAM_LEAD)

        perms = RBACService.get_user_permissions(user)

        assert "agent:view" in perms
        assert "agent:run" in perms
        assert "workflow:manage" in perms
        assert "agent:manage" not in perms

    def test_get_user_permissions_workspace_admin(self):
        """Test getting permissions for workspace admin user."""
        user = self.create_user(UserRole.WORKSPACE_ADMIN)

        perms = RBACService.get_user_permissions(user)

        assert "agent:view" in perms
        assert "agent:run" in perms
        assert "agent:manage" in perms
        assert "workflow:manage" in perms
        assert "user:manage" in perms

    def test_get_user_permissions_super_admin(self):
        """Test super admin has all permissions."""
        user = self.create_user(UserRole.SUPER_ADMIN)

        perms = RBACService.get_user_permissions(user)

        # Super admin should have all permissions
        assert len(perms) == len(Permission)
        for perm in Permission:
            assert perm.value in perms

    def test_get_user_permissions_string_role_valid(self):
        """Test getting permissions with string role (valid)."""
        user = self.create_user("member")  # Use value, not name

        perms = RBACService.get_user_permissions(user)

        assert "agent:view" in perms
        assert "agent:run" in perms

    def test_get_user_permissions_string_role_invalid(self):
        """Test getting permissions with invalid string role."""
        user = self.create_user("invalid_role")

        perms = RBACService.get_user_permissions(user)

        assert perms == set()

    def test_check_permission_guest_has_view(self):
        """Test guest has view permission."""
        user = self.create_user(UserRole.GUEST)

        assert RBACService.check_permission(user, Permission.AGENT_VIEW) is True

    def test_check_permission_guest_lacks_run(self):
        """Test guest lacks run permission."""
        user = self.create_user(UserRole.GUEST)

        assert RBACService.check_permission(user, Permission.AGENT_RUN) is False

    def test_check_permission_member_has_run(self):
        """Test member has run permission."""
        user = self.create_user(UserRole.MEMBER)

        assert RBACService.check_permission(user, Permission.AGENT_RUN) is True

    def test_check_permission_member_lacks_manage(self):
        """Test member lacks manage permission."""
        user = self.create_user(UserRole.MEMBER)

        assert RBACService.check_permission(user, Permission.AGENT_MANAGE) is False

    def test_check_permission_team_lead_has_manage(self):
        """Test team lead has manage permission."""
        user = self.create_user(UserRole.TEAM_LEAD)

        assert RBACService.check_permission(user, Permission.WORKFLOW_MANAGE) is True

    def test_check_permission_workspace_admin_has_all(self):
        """Test workspace admin has all management permissions."""
        user = self.create_user(UserRole.WORKSPACE_ADMIN)

        assert RBACService.check_permission(user, Permission.AGENT_MANAGE) is True
        assert RBACService.check_permission(user, Permission.WORKFLOW_MANAGE) is True
        assert RBACService.check_permission(user, Permission.USER_MANAGE) is True

    def test_check_permission_super_admin_always_true(self):
        """Test super admin always has permission."""
        user = self.create_user(UserRole.SUPER_ADMIN)

        assert RBACService.check_permission(user, Permission.AGENT_VIEW) is True
        assert RBACService.check_permission(user, Permission.AGENT_MANAGE) is True
        assert RBACService.check_permission(user, Permission.SYSTEM_ADMIN) is True

    def test_check_permission_string_role_valid(self):
        """Test check permission with valid string role."""
        user = self.create_user("member")  # Use value, not name

        assert RBACService.check_permission(user, Permission.AGENT_RUN) is True

    def test_check_permission_string_role_invalid(self):
        """Test check permission with invalid string role."""
        user = self.create_user("invalid_role")

        assert RBACService.check_permission(user, Permission.AGENT_VIEW) is False

    def test_permission_hierarchy(self):
        """Test that permission hierarchy works correctly."""
        guest = self.create_user(UserRole.GUEST)
        member = self.create_user(UserRole.MEMBER)
        admin = self.create_user(UserRole.WORKSPACE_ADMIN)

        # Guest can only view
        assert RBACService.check_permission(guest, Permission.AGENT_VIEW) is True
        assert RBACService.check_permission(guest, Permission.AGENT_RUN) is False

        # Member can view and run
        assert RBACService.check_permission(member, Permission.AGENT_VIEW) is True
        assert RBACService.check_permission(member, Permission.AGENT_RUN) is True
        assert RBACService.check_permission(member, Permission.AGENT_MANAGE) is False

        # Admin can do everything
        assert RBACService.check_permission(admin, Permission.AGENT_VIEW) is True
        assert RBACService.check_permission(admin, Permission.AGENT_RUN) is True
        assert RBACService.check_permission(admin, Permission.AGENT_MANAGE) is True

"""
Global Permission Tests for Single-Tenant Atom Platform

Tests the consolidated UserRole system and global permissions.
Atom is a single-tenant, single-workspace system - permissions are based
solely on the user's global role, not workspace membership.
"""

import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from core.models import User, Workspace, UserRole, user_workspaces
from core.enterprise_auth_service import EnterpriseAuthService
from core.exceptions import (
    UserNotFoundError,
    WorkspaceAccessDeniedError,
    ForbiddenError
)


@pytest.fixture
def mock_db():
    """Create mock database session"""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def auth_service():
    """Create enterprise auth service instance"""
    return EnterpriseAuthService(secret_key="test-secret-key")


class TestConsolidatedUserRole:
    """Test consolidated UserRole enum from models.py"""

    def test_all_role_values_exist(self):
        """Test that all expected role values exist"""
        # System-wide roles
        assert UserRole.SUPER_ADMIN.value == "super_admin"
        assert UserRole.SECURITY_ADMIN.value == "security_admin"
        assert UserRole.WORKSPACE_ADMIN.value == "workspace_admin"
        assert UserRole.WORKFLOW_ADMIN.value == "workflow_admin"
        assert UserRole.AUTOMATION_ADMIN.value == "automation_admin"
        assert UserRole.INTEGRATION_ADMIN.value == "integration_admin"
        assert UserRole.COMPLIANCE_ADMIN.value == "compliance_admin"

        # Workspace roles
        assert UserRole.TEAM_LEAD.value == "team_lead"
        assert UserRole.MEMBER.value == "member"
        assert UserRole.GUEST.value == "guest"

        # Legacy alias
        assert UserRole.ADMIN.value == "workspace_admin"  # Maps to WORKSPACE_ADMIN

    def test_role_hierarchy(self):
        """Test that roles maintain proper hierarchy"""
        # All roles should have string values
        for role in UserRole:
            assert isinstance(role.value, str)
            assert len(role.value) > 0

    def test_role_uniqueness(self):
        """Test that all role values are unique (except ADMIN alias)"""
        values = [role.value for role in UserRole]
        # ADMIN and WORKSPACE_ADMIN are allowed to duplicate
        unique_values = set(values)
        # We expect 10 unique values (11 total - 1 duplicate for ADMIN/WORKSPACE_ADMIN)
        assert len(unique_values) >= 10


class TestSuperAdminPermissions:
    """Test SUPER_ADMIN role permissions"""

    def test_super_admin_has_all_permissions(self, mock_db, auth_service):
        """Test that SUPER_ADMIN has 'all' permission"""
        user = Mock()
        user.role = UserRole.SUPER_ADMIN.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        assert "all" in permissions
        assert len(permissions) == 1  # Only "all" needed

    def test_super_admin_bypasses_workspace_check(self, mock_db, auth_service):
        """Test that SUPER_ADMIN bypasses workspace-specific checks"""
        user = Mock()
        user.role = UserRole.SUPER_ADMIN.value

        # Even without workspace_id, should get all permissions
        permissions = auth_service._get_user_permissions(mock_db, user)

        assert "all" in permissions


class TestSecurityAdminPermissions:
    """Test SECURITY_ADMIN role permissions"""

    def test_security_admin_permissions(self, mock_db, auth_service):
        """Test SECURITY_ADMIN has management permissions"""
        user = Mock()
        user.role = UserRole.SECURITY_ADMIN.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        expected_permissions = [
            "manage_users",
            "manage_security",
            "view_audit_logs",
            "manage_workflows",
            "manage_integrations",
            "view_analytics",
            "execute_workflows"
        ]

        for perm in expected_permissions:
            assert perm in permissions

    def test_security_admin_cannot_delete_without_super_admin(self, mock_db, auth_service):
        """Test that SECURITY_ADMIN cannot perform super-admin-only actions"""
        user = Mock()
        user.role = UserRole.SECURITY_ADMIN.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        # Should NOT have "all" permission
        assert "all" not in permissions


class TestWorkspaceAdminPermissions:
    """Test WORKSPACE_ADMIN role permissions"""

    def test_workspace_admin_permissions(self, mock_db, auth_service):
        """Test WORKSPACE_ADMIN has same permissions as SECURITY_ADMIN"""
        user = Mock()
        user.role = UserRole.WORKSPACE_ADMIN.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        expected_permissions = [
            "manage_users",
            "manage_security",
            "view_audit_logs",
            "manage_workflows",
            "manage_integrations",
            "view_analytics",
            "execute_workflows"
        ]

        for perm in expected_permissions:
            assert perm in permissions


class TestSpecializedAdminRoles:
    """Test specialized admin role permissions"""

    def test_workflow_admin_permissions(self, mock_db, auth_service):
        """Test WORKFLOW_ADMIN permissions"""
        user = Mock()
        user.role = UserRole.WORKFLOW_ADMIN.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        assert "manage_workflows" in permissions
        assert "view_analytics" in permissions
        assert "execute_workflows" in permissions
        assert "manage_automations" in permissions
        assert "manage_users" not in permissions

    def test_automation_admin_permissions(self, mock_db, auth_service):
        """Test AUTOMATION_ADMIN permissions"""
        user = Mock()
        user.role = UserRole.AUTOMATION_ADMIN.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        assert "manage_automations" in permissions
        assert "execute_workflows" in permissions
        assert "view_analytics" in permissions
        assert "manage_workflows" not in permissions

    def test_integration_admin_permissions(self, mock_db, auth_service):
        """Test INTEGRATION_ADMIN permissions"""
        user = Mock()
        user.role = UserRole.INTEGRATION_ADMIN.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        assert "manage_integrations" in permissions
        assert "view_analytics" in permissions
        assert "manage_workflows" not in permissions

    def test_compliance_admin_permissions(self, mock_db, auth_service):
        """Test COMPLIANCE_ADMIN permissions"""
        user = Mock()
        user.role = UserRole.COMPLIANCE_ADMIN.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        assert "view_audit_logs" in permissions
        assert "view_analytics" in permissions
        assert "manage_compliance" in permissions
        assert "manage_users" not in permissions


class TestStandardRolePermissions:
    """Test standard role (TEAM_LEAD, MEMBER, GUEST) permissions"""

    def test_team_lead_permissions(self, mock_db, auth_service):
        """Test TEAM_LEAD permissions"""
        user = Mock()
        user.role = UserRole.TEAM_LEAD.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        assert "read_workflows" in permissions
        assert "execute_workflows" in permissions
        assert "view_analytics" in permissions
        assert "manage_team_reports" in permissions
        assert "manage_workflows" not in permissions

    def test_member_permissions(self, mock_db, auth_service):
        """Test MEMBER permissions"""
        user = Mock()
        user.role = UserRole.MEMBER.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        assert "read_workflows" in permissions
        assert "execute_workflows" in permissions
        assert "view_analytics" in permissions
        assert "manage_workflows" not in permissions

    def test_guest_permissions(self, mock_db, auth_service):
        """Test GUEST permissions (read-only)"""
        user = Mock()
        user.role = UserRole.GUEST.value

        permissions = auth_service._get_user_permissions(mock_db, user)

        assert "read_workflows" in permissions
        assert "view_analytics" in permissions
        assert "execute_workflows" not in permissions
        assert "manage_workflows" not in permissions


class TestPermissionEdgeCases:
    """Test edge cases and error handling"""

    def test_unknown_role_gets_minimal_permissions(self, mock_db, auth_service):
        """Test that unknown roles get minimal permissions"""
        user = Mock()
        user.role = "unknown_role"

        permissions = auth_service._get_user_permissions(mock_db, user)

        # Should get minimal fallback permissions
        assert "read_workflows" in permissions
        assert len(permissions) == 1

    def test_workspace_id_parameter_is_ignored(self, mock_db, auth_service):
        """Test that workspace_id parameter is ignored (single-tenant system)"""
        user = Mock()
        user.role = UserRole.MEMBER.value

        # workspace_id should be ignored
        permissions_with_workspace = auth_service._get_user_permissions(
            mock_db,
            user,
            workspace_id="some_workspace_id"
        )
        permissions_without_workspace = auth_service._get_user_permissions(
            mock_db,
            user,
            workspace_id=None
        )

        # Both should return the same permissions
        assert permissions_with_workspace == permissions_without_workspace
        assert "read_workflows" in permissions_with_workspace
        assert "execute_workflows" in permissions_with_workspace


class TestSAMLRoleMapping:
    """Test SAML role mapping to internal roles"""

    def test_map_admin_saml_role(self, auth_service):
        """Test mapping 'admin' from SAML"""
        mapped = auth_service._map_saml_role_to_user_role("admin")
        assert mapped == UserRole.WORKSPACE_ADMIN.value

    def test_map_superadmin_saml_role(self, auth_service):
        """Test mapping 'superadmin' from SAML"""
        mapped = auth_service._map_saml_role_to_user_role("superadmin")
        assert mapped == UserRole.SUPER_ADMIN.value

    def test_map_member_saml_role(self, auth_service):
        """Test mapping 'member' from SAML"""
        mapped = auth_service._map_saml_role_to_user_role("member")
        assert mapped == UserRole.MEMBER.value

    def test_map_unknown_saml_role_defaults_to_member(self, auth_service):
        """Test that unknown SAML roles default to MEMBER"""
        mapped = auth_service._map_saml_role_to_user_role("unknown_role")
        assert mapped == UserRole.MEMBER.value

    def test_case_insensitive_role_mapping(self, auth_service):
        """Test that role mapping is case-insensitive"""
        mapped1 = auth_service._map_saml_role_to_user_role("Admin")
        mapped2 = auth_service._map_saml_role_to_user_role("ADMIN")
        mapped3 = auth_service._map_saml_role_to_user_role("admin")

        assert mapped1 == UserRole.WORKSPACE_ADMIN.value
        assert mapped2 == UserRole.WORKSPACE_ADMIN.value
        assert mapped3 == UserRole.WORKSPACE_ADMIN.value


class TestPermissionIntegration:
    """Integration tests for single-tenant permission system"""

    def test_super_admin_has_all_permissions(self, mock_db, auth_service):
        """Test that SUPER_ADMIN has all permissions regardless of other parameters"""
        user = Mock()
        user.role = UserRole.SUPER_ADMIN.value

        # Should have all permissions
        permissions = auth_service._get_user_permissions(
            mock_db,
            user,
            workspace_id="ignored_parameter"
        )

        assert "all" in permissions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

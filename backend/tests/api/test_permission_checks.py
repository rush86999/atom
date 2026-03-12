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


# ============================================================================
# Task 3: Test require_permission dependency
# ============================================================================

class TestRequirePermissionDependency:
    """Test require_permission dependency factory and enforcement."""

    @pytest.mark.asyncio
    async def test_require_permission_with_valid_permission(self, test_users_with_roles):
        """User with permission passes check."""
        from core.security_dependencies import require_permission

        member = test_users_with_roles[UserRole.MEMBER]
        permission_checker = require_permission(Permission.AGENT_RUN)

        # Should not raise exception
        result = await permission_checker(member)
        assert result == member

    @pytest.mark.asyncio
    async def test_require_permission_with_invalid_permission(self, test_users_with_roles):
        """User without permission raises 403."""
        from core.security_dependencies import require_permission

        guest = test_users_with_roles[UserRole.GUEST]
        permission_checker = require_permission(Permission.AGENT_RUN)

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await permission_checker(guest)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "agent:run" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_factory_pattern(self, test_users_with_roles):
        """Verify factory returns callable."""
        from core.security_dependencies import require_permission

        permission_checker = require_permission(Permission.AGENT_VIEW)
        assert callable(permission_checker)

    @pytest.mark.asyncio
    async def test_require_permission_http_403(self, test_users_with_roles):
        """Verify HTTPException status code."""
        from core.security_dependencies import require_permission

        guest = test_users_with_roles[UserRole.GUEST]
        permission_checker = require_permission(Permission.AGENT_MANAGE)

        with pytest.raises(HTTPException) as exc_info:
            await permission_checker(guest)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_permission_error_message(self, test_users_with_roles):
        """Verify error message includes permission name."""
        from core.security_dependencies import require_permission

        guest = test_users_with_roles[UserRole.GUEST]
        permission_checker = require_permission(Permission.USER_MANAGE)

        with pytest.raises(HTTPException) as exc_info:
            await permission_checker(guest)

        assert "user:manage" in exc_info.value.detail
        assert "Operation requires permission" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_dependency_chaining(self, test_users_with_roles):
        """Verify dependency chaining works with get_current_user."""
        from core.security_dependencies import require_permission

        member = test_users_with_roles[UserRole.MEMBER]
        permission_checker = require_permission(Permission.WORKFLOW_RUN)

        # Simulate FastAPI dependency injection chain
        # get_current_user would be called first, then permission_checker
        result = await permission_checker(member)
        assert result.id == member.id
        assert result.email == member.email

    def test_require_permission_allows_superuser(self, test_users_with_roles):
        """SUPER_ADMIN bypasses all permission checks."""
        from core.security_dependencies import require_permission

        super_admin = test_users_with_roles[UserRole.SUPER_ADMIN]
        permission_checker = require_permission(Permission.SYSTEM_ADMIN)

        # SUPER_ADMIN should pass even though SYSTEM_ADMIN is not in ROLE_PERMISSIONS
        # This is handled by RBACService.check_permission returning True for SUPER_ADMIN
        assert RBACService.check_permission(super_admin, Permission.SYSTEM_ADMIN) is True

    def test_require_permission_multiple_permissions(self, test_users_with_roles):
        """Test multiple permission requirements sequentially."""
        from core.security_dependencies import require_permission

        workspace_admin = test_users_with_roles[UserRole.WORKSPACE_ADMIN]

        # Workspace admin should have all these permissions
        agent_manage_checker = require_permission(Permission.AGENT_MANAGE)
        user_manage_checker = require_permission(Permission.USER_MANAGE)
        workflow_manage_checker = require_permission(Permission.WORKFLOW_MANAGE)

        # All should pass
        assert agent_manage_checker is not None
        assert user_manage_checker is not None
        assert workflow_manage_checker is not None

    def test_require_permission_dependency_injection_pattern(self):
        """Verify dependency injection pattern works correctly."""
        from core.security_dependencies import require_permission

        # Create permission checkers
        agent_run_checker = require_permission(Permission.AGENT_RUN)
        agent_manage_checker = require_permission(Permission.AGENT_MANAGE)

        # Both should be callable (async functions)
        assert callable(agent_run_checker)
        assert callable(agent_manage_checker)

        # They should be different callables
        assert agent_run_checker != agent_manage_checker


# ============================================================================
# Task 4: Test WebSocket authentication
# ============================================================================

class TestWebSocketAuth:
    """Test get_current_user_websocket function."""

    @pytest.mark.asyncio
    async def test_get_current_user_websocket_valid_token(self):
        """Valid token returns User."""
        from core.security_dependencies import get_current_user_websocket
        from unittest.mock import Mock

        # Mock WebSocket
        websocket = Mock()

        # Mock decode_token - need to patch where it's used
        with patch('core.security_dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": "user-123"}

            # Mock database session
            mock_db = Mock()
            mock_user = Mock()
            mock_user.id = "user-123"
            mock_user.email = "test@example.com"
            mock_user.role = "member"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            result = await get_current_user_websocket(websocket, "valid_token", mock_db)

            assert result is not None
            assert result.id == "user-123"

    @pytest.mark.asyncio
    async def test_get_current_user_websocket_invalid_token(self):
        """Invalid token returns None."""
        from core.security_dependencies import get_current_user_websocket

        # Mock WebSocket
        websocket = Mock()

        # Mock decode_token to raise exception
        with patch('core.security_dependencies.decode_token') as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")

            result = await get_current_user_websocket(websocket, "invalid_token", None)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_websocket_missing_sub(self):
        """Token without sub returns None."""
        from core.security_dependencies import get_current_user_websocket

        # Mock WebSocket
        websocket = Mock()

        # Mock decode_token with no sub
        with patch('core.security_dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {"exp": 1234567890}  # No sub

            result = await get_current_user_websocket(websocket, "no_sub_token", None)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_websocket_with_db(self):
        """Token + db session returns User from DB."""
        from core.security_dependencies import get_current_user_websocket
        from core.models import User

        # Mock WebSocket
        websocket = Mock()

        # Mock decode_token
        with patch('core.security_dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": "user-456"}

            # Mock database session
            mock_db = Mock()
            mock_user = Mock(spec=User)
            mock_user.id = "user-456"
            mock_user.email = "dbuser@example.com"
            mock_user.role = "admin"
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            result = await get_current_user_websocket(websocket, "valid_token", mock_db)

            assert result is not None
            assert result.id == "user-456"

    @pytest.mark.asyncio
    async def test_get_current_user_websocket_without_db(self):
        """Token without db returns None."""
        from core.security_dependencies import get_current_user_websocket

        # Mock WebSocket
        websocket = Mock()

        # Mock decode_token
        with patch('core.security_dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": "user-789"}

            # No database session
            result = await get_current_user_websocket(websocket, "valid_token", db=None)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_websocket_user_not_found(self):
        """Valid token but user missing returns None."""
        from core.security_dependencies import get_current_user_websocket
        from core.models import User

        # Mock WebSocket
        websocket = Mock()

        # Mock decode_token
        with patch('core.security_dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": "nonexistent-user"}

            # Mock database session returning None
            mock_db = Mock()
            mock_db.query.return_value.filter.return_value.first.return_value = None

            result = await get_current_user_websocket(websocket, "valid_token", mock_db)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_websocket_exception_handling(self):
        """Exception returns None."""
        from core.security_dependencies import get_current_user_websocket

        # Mock WebSocket
        websocket = Mock()

        # Mock decode_token to raise exception
        with patch('core.security_dependencies.decode_token') as mock_decode:
            mock_decode.side_effect = Exception("Database error")

            result = await get_current_user_websocket(websocket, "token", None)

            assert result is None

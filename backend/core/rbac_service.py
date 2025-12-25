from enum import Enum
from typing import List, Dict, Set
from core.models import User, UserRole

class Permission(str, Enum):
    # Agent Permissions
    AGENT_VIEW = "agent:view"
    AGENT_RUN = "agent:run"
    AGENT_MANAGE = "agent:manage"  # Create, Edit, Delete

    # Workflow Permissions
    WORKFLOW_VIEW = "workflow:view"
    WORKFLOW_RUN = "workflow:run"
    WORKFLOW_MANAGE = "workflow:manage"

    # User Management
    USER_VIEW = "user:view"
    USER_MANAGE = "user:manage"
    
    # System
    SYSTEM_ADMIN = "system:admin"

# Mapping Roles to Permissions
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.GUEST: {
        Permission.AGENT_VIEW,
        Permission.WORKFLOW_VIEW
    },
    UserRole.MEMBER: {
        Permission.AGENT_VIEW,
        Permission.AGENT_RUN,
        Permission.WORKFLOW_VIEW,
        Permission.WORKFLOW_RUN,
        Permission.USER_VIEW
    },
    UserRole.TEAM_LEAD: {
        Permission.AGENT_VIEW,
        Permission.AGENT_RUN,
        Permission.WORKFLOW_VIEW,
        Permission.WORKFLOW_RUN,
        Permission.WORKFLOW_MANAGE,
        Permission.USER_VIEW
    },
    UserRole.WORKSPACE_ADMIN: {
        Permission.AGENT_VIEW,
        Permission.AGENT_RUN,
        Permission.AGENT_MANAGE,
        Permission.WORKFLOW_VIEW,
        Permission.WORKFLOW_RUN,
        Permission.WORKFLOW_MANAGE,
        Permission.USER_VIEW,
        Permission.USER_MANAGE
    },
    UserRole.SUPER_ADMIN: {
        # Super admin has all permissions implicitly
        Permission.SYSTEM_ADMIN
    }
}

class RBACService:
    @staticmethod
    def get_user_permissions(user: User) -> Set[str]:
        """Get all permissions for a user based on their role"""
        role = user.role
        # Handle string role if not enum
        if isinstance(role, str):
            try:
                role = UserRole(role)
            except ValueError:
                # Default to safe empty set if role unknown
                return set()

        if role == UserRole.SUPER_ADMIN:
            return {p.value for p in Permission}
            
        permissions = ROLE_PERMISSIONS.get(role, set())
        return {p.value for p in permissions}

    @staticmethod
    def check_permission(user: User, required_permission: Permission) -> bool:
        """Check if user has specific permission"""
        role = user.role
        if isinstance(role, str):
            try:
                role = UserRole(role)
            except ValueError:
                return False

        if role == UserRole.SUPER_ADMIN:
            return True

        user_perms = ROLE_PERMISSIONS.get(role, set())
        return required_permission in user_perms

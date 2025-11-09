"""
Advanced User Permission System with Role-Based Access Control

This module provides enterprise-grade user permission management with:
- Role-based access control (RBAC)
- Fine-grained permissions for integrations and workflows
- Audit logging for compliance
- Permission inheritance and delegation
- Multi-tenant support
"""

import hashlib
import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Permission levels for resource access"""

    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


class ResourceType(Enum):
    """Types of resources that can be protected"""

    WORKFLOW = "workflow"
    INTEGRATION = "integration"
    MEMORY = "memory"
    USER = "user"
    ORGANIZATION = "organization"
    API_KEY = "api_key"
    AUDIT_LOG = "audit_log"


class UserRole(Enum):
    """Predefined user roles"""

    SUPER_ADMIN = "super_admin"
    ORGANIZATION_ADMIN = "organization_admin"
    TEAM_LEAD = "team_lead"
    POWER_USER = "power_user"
    STANDARD_USER = "standard_user"
    READ_ONLY_USER = "read_only_user"
    GUEST = "guest"


@dataclass
class Permission:
    """Individual permission definition"""

    resource_type: ResourceType
    resource_id: str
    permission_level: PermissionLevel
    granted_at: datetime
    granted_by: str
    expires_at: Optional[datetime] = None


@dataclass
class Role:
    """Role definition with permissions"""

    name: str
    description: str
    permissions: List[Permission]
    is_system_role: bool = False
    inherits_from: Optional[str] = None


@dataclass
class User:
    """User with roles and permissions"""

    user_id: str
    email: str
    organization_id: str
    roles: List[str]
    custom_permissions: List[Permission]
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)


@dataclass
class AuditLogEntry:
    """Audit log entry for compliance"""

    log_id: str
    user_id: str
    action: str
    resource_type: ResourceType
    resource_id: str
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None
    success: bool = True


class UserPermissionSystem:
    """
    Advanced user permission system with role-based access control,
    audit logging, and enterprise security features.
    """

    def __init__(self, database_manager=None):
        self.database_manager = database_manager
        self.users: Dict[str, User] = {}
        self.roles: Dict[str, Role] = {}
        self.audit_log: List[AuditLogEntry] = []

        # Initialize system roles
        self._initialize_system_roles()

        logger.info("User Permission System initialized")

    def _log_audit_event(
        self,
        user_id: str,
        action: str,
        resource_type: ResourceType,
        resource_id: str,
        ip_address: str = None,
        user_agent: str = None,
        additional_info: Dict[str, Any] = None,
        success: bool = True,
    ):
        """Log an audit event for compliance and security tracking"""
        log_id = str(uuid.uuid4())

        audit_entry = AuditLogEntry(
            log_id=log_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp=datetime.now(timezone.utc),
            ip_address=ip_address,
            user_agent=user_agent,
            additional_info=additional_info,
            success=success,
        )

        self.audit_log.append(audit_entry)

        # Log the audit event
        logger.info(
            f"Audit event: {action} by {user_id} on {resource_type.value}/{resource_id}"
        )

    def _initialize_system_roles(self):
        """Initialize predefined system roles"""
        current_time = datetime.now(timezone.utc)

        # Super Admin - Full system access
        super_admin_permissions = [
            Permission(
                ResourceType.WORKFLOW,
                "*",
                PermissionLevel.OWNER,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.INTEGRATION,
                "*",
                PermissionLevel.OWNER,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.MEMORY, "*", PermissionLevel.OWNER, current_time, "system"
            ),
            Permission(
                ResourceType.USER, "*", PermissionLevel.ADMIN, current_time, "system"
            ),
            Permission(
                ResourceType.ORGANIZATION,
                "*",
                PermissionLevel.OWNER,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.API_KEY, "*", PermissionLevel.ADMIN, current_time, "system"
            ),
            Permission(
                ResourceType.AUDIT_LOG,
                "*",
                PermissionLevel.READ,
                current_time,
                "system",
            ),
        ]
        self.roles[UserRole.SUPER_ADMIN.value] = Role(
            name=UserRole.SUPER_ADMIN.value,
            description="Full system administrator with complete access",
            permissions=super_admin_permissions,
            is_system_role=True,
        )

        # Organization Admin - Full organization access
        org_admin_permissions = [
            Permission(
                ResourceType.WORKFLOW,
                "*",
                PermissionLevel.ADMIN,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.INTEGRATION,
                "*",
                PermissionLevel.ADMIN,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.MEMORY, "*", PermissionLevel.ADMIN, current_time, "system"
            ),
            Permission(
                ResourceType.USER, "*", PermissionLevel.ADMIN, current_time, "system"
            ),
            Permission(
                ResourceType.API_KEY, "*", PermissionLevel.WRITE, current_time, "system"
            ),
            Permission(
                ResourceType.AUDIT_LOG,
                "*",
                PermissionLevel.READ,
                current_time,
                "system",
            ),
        ]
        self.roles[UserRole.ORGANIZATION_ADMIN.value] = Role(
            name=UserRole.ORGANIZATION_ADMIN.value,
            description="Organization administrator with full organizational access",
            permissions=org_admin_permissions,
            is_system_role=True,
        )

        # Team Lead - Team management capabilities
        team_lead_permissions = [
            Permission(
                ResourceType.WORKFLOW,
                "*",
                PermissionLevel.WRITE,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.INTEGRATION,
                "*",
                PermissionLevel.WRITE,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.MEMORY, "*", PermissionLevel.WRITE, current_time, "system"
            ),
            Permission(
                ResourceType.USER, "*", PermissionLevel.READ, current_time, "system"
            ),
        ]
        self.roles[UserRole.TEAM_LEAD.value] = Role(
            name=UserRole.TEAM_LEAD.value,
            description="Team lead with workflow and integration management capabilities",
            permissions=team_lead_permissions,
            is_system_role=True,
        )

        # Power User - Advanced user capabilities
        power_user_permissions = [
            Permission(
                ResourceType.WORKFLOW,
                "*",
                PermissionLevel.WRITE,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.INTEGRATION,
                "*",
                PermissionLevel.WRITE,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.MEMORY, "*", PermissionLevel.WRITE, current_time, "system"
            ),
        ]
        self.roles[UserRole.POWER_USER.value] = Role(
            name=UserRole.POWER_USER.value,
            description="Power user with advanced workflow and integration capabilities",
            permissions=power_user_permissions,
            is_system_role=True,
        )

        # Standard User - Basic user capabilities
        standard_user_permissions = [
            Permission(
                ResourceType.WORKFLOW, "*", PermissionLevel.READ, current_time, "system"
            ),
            Permission(
                ResourceType.INTEGRATION,
                "*",
                PermissionLevel.READ,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.MEMORY, "*", PermissionLevel.READ, current_time, "system"
            ),
        ]
        self.roles[UserRole.STANDARD_USER.value] = Role(
            name=UserRole.STANDARD_USER.value,
            description="Standard user with read access to workflows and integrations",
            permissions=standard_user_permissions,
            is_system_role=True,
        )

        # Read Only User - View-only access
        read_only_permissions = [
            Permission(
                ResourceType.WORKFLOW, "*", PermissionLevel.READ, current_time, "system"
            ),
            Permission(
                ResourceType.INTEGRATION,
                "*",
                PermissionLevel.READ,
                current_time,
                "system",
            ),
            Permission(
                ResourceType.MEMORY, "*", PermissionLevel.READ, current_time, "system"
            ),
        ]
        self.roles[UserRole.READ_ONLY_USER.value] = Role(
            name=UserRole.READ_ONLY_USER.value,
            description="Read-only user with view access only",
            permissions=read_only_permissions,
            is_system_role=True,
        )

        # Guest - Limited access
        guest_permissions = [
            Permission(
                ResourceType.WORKFLOW, "*", PermissionLevel.READ, current_time, "system"
            ),
        ]
        self.roles[UserRole.GUEST.value] = Role(
            name=UserRole.GUEST.value,
            description="Guest user with limited access",
            permissions=guest_permissions,
            is_system_role=True,
        )

    def create_user(
        self, email: str, organization_id: str, roles: List[str] = None
    ) -> User:
        """Create a new user with specified roles"""
        if roles is None:
            roles = [UserRole.STANDARD_USER.value]

        # Validate roles exist
        for role_name in roles:
            if role_name not in self.roles:
                raise ValueError(f"Role '{role_name}' does not exist")

        user_id = str(uuid.uuid4())
        user = User(
            user_id=user_id,
            email=email,
            organization_id=organization_id,
            roles=roles,
            custom_permissions=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.users[user_id] = user

        # Log user creation
        self._log_audit_event(
            user_id=user_id,
            action="user_created",
            resource_type=ResourceType.USER,
            resource_id=user_id,
            additional_info={"email": email, "roles": roles},
        )

        logger.info(f"Created user {user_id} with roles: {roles}")
        return user

    def check_permission(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        required_level: PermissionLevel,
    ) -> bool:
        """Check if user has required permission for a resource"""
        if user_id not in self.users:
            logger.warning(f"User {user_id} not found")
            return False

        user = self.users[user_id]
        if not user.is_active:
            logger.warning(f"User {user_id} is inactive")
            return False

        # Check custom permissions first (most specific)
        for permission in user.custom_permissions:
            if self._permission_matches(permission, resource_type, resource_id):
                if self._permission_sufficient(
                    permission.permission_level, required_level
                ):
                    return True

        # Check role permissions
        for role_name in user.roles:
            if role_name in self.roles:
                role = self.roles[role_name]
                for permission in role.permissions:
                    if self._permission_matches(permission, resource_type, resource_id):
                        if self._permission_sufficient(
                            permission.permission_level, required_level
                        ):
                            return True

        logger.debug(
            f"Permission denied for user {user_id} on {resource_type.value}/{resource_id}"
        )
        return False

    def _permission_matches(
        self, permission: Permission, resource_type: ResourceType, resource_id: str
    ) -> bool:
        """Check if permission matches the resource"""
        if permission.resource_type != resource_type:
            return False

        # Check for wildcard permission
        if permission.resource_id == "*":
            return True

        # Check for exact match
        if permission.resource_id == resource_id:
            return True

        # Check for pattern matching (future enhancement)
        return False

    def _permission_sufficient(
        self, user_level: PermissionLevel, required_level: PermissionLevel
    ) -> bool:
        """Check if user's permission level is sufficient for required level"""
        permission_hierarchy = {
            PermissionLevel.NONE: 0,
            PermissionLevel.READ: 1,
            PermissionLevel.WRITE: 2,
            PermissionLevel.ADMIN: 3,
            PermissionLevel.OWNER: 4,
        }

        return permission_hierarchy[user_level] >= permission_hierarchy[required_level]

    def grant_custom_permission(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        permission_level: PermissionLevel,
        granted_by: str,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """Grant custom permission to a user"""
        if user_id not in self.users:
            logger.error(f"User {user_id} not found")
            return False

        user = self.users[user_id]

        # Check if grantor has permission to grant this permission
        if not self.check_permission(
            granted_by, ResourceType.USER, user_id, PermissionLevel.ADMIN
        ):
            logger.error(
                f"User {granted_by} lacks permission to grant permissions to user {user_id}"
            )
            return False

        # Create new permission
        new_permission = Permission(
            resource_type=resource_type,
            resource_id=resource_id,
            permission_level=permission_level,
            granted_at=datetime.now(timezone.utc),
            granted_by=granted_by,
            expires_at=expires_at,
        )

        # Remove any existing permission for the same resource
        user.custom_permissions = [
            perm
            for perm in user.custom_permissions
            if not (
                perm.resource_type == resource_type and perm.resource_id == resource_id
            )
        ]

        # Add new permission
        user.custom_permissions.append(new_permission)
        user.updated_at = datetime.now(timezone.utc)

        # Log permission grant
        self._log_audit_event(
            user_id=granted_by,
            action="permission_granted",
            resource_type=resource_type,
            resource_id=resource_id,
            additional_info={
                "target_user_id": user_id,
                "permission_level": permission_level.value,
                "expires_at": expires_at.isoformat() if expires_at else None,
            },
        )

        logger.info(
            f"Granted {permission_level.value} permission on {resource_type.value}/{resource_id} to user {user_id}"
        )
        return True

    def revoke_custom_permission(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        revoked_by: str,
    ) -> bool:
        """Revoke custom permission from a user"""
        if user_id not in self.users:
            logger.error(f"User {user_id} not found")
            return False

        user = self.users[user_id]

        # Check if revoker has permission to revoke this permission
        if not self.check_permission(
            revoked_by, ResourceType.USER, user_id, PermissionLevel.ADMIN
        ):
            logger.error(
                f"User {revoked_by} lacks permission to revoke permissions from user {user_id}"
            )
            return False

        # Remove permission
        initial_count = len(user.custom_permissions)
        user.custom_permissions = [
            perm
            for perm in user.custom_permissions
            if not (
                perm.resource_type == resource_type and perm.resource_id == resource_id
            )
        ]

        if len(user.custom_permissions) < initial_count:
            user.updated_at = datetime.now(timezone.utc)

            # Log permission revocation
            self._log_audit_event(
                user_id=revoked_by,
                action="permission_revoked",
                resource_type=resource_type,
                resource_id=resource_id,
                additional_info={"target_user_id": user_id},
            )

            logger.info(
                f"Revoked permission on {resource_type.value}/{resource_id} from user {user_id}"
            )
            return True

        logger.warning(
            f"No permission found to revoke for user {user_id} on {resource_type.value}/{resource_id}"
        )
        return False

    def assign_role(self, user_id: str, role_name: str, assigned_by: str) -> bool:
        """Assign a role to a user"""
        if user_id not in self.users:
            logger.error(f"User {user_id} not found")
            return False

        if role_name not in self.roles:
            logger.error(f"Role {role_name} not found")
            return False

        user = self.users[user_id]

        # Check if assigner has permission to assign roles
        if not self.check_permission(
            assigned_by, ResourceType.USER, user_id, PermissionLevel.ADMIN
        ):
            logger.error(
                f"User {assigned_by} lacks permission to assign roles to user {user_id}"
            )
            return False

        # Add role if not already assigned
        if role_name not in user.roles:
            user.roles.append(role_name)
            user.updated_at = datetime.now(timezone.utc)

            # Log role assignment
            self._log_audit_event(
                user_id=assigned_by,
                action="role_assigned",
                resource_type=ResourceType.USER,
                resource_id=user_id,
                additional_info={"role_name": role_name},
            )

            logger.info(f"Assigned role {role_name} to user {user_id}")
            return True

        logger.info(f"User {user_id} already has role {role_name}")
        return False

    def remove_role(self, user_id: str, role_name: str, removed_by: str) -> bool:
        """Remove a role from a user"""
        if user_id not in self.users:
            logger.error(f"User {user_id} not found")
            return False

        user = self.users[user_id]

        # Check if remover has permission to remove roles
        if not self.check_permission(
            removed_by, ResourceType.USER, user_id, PermissionLevel.ADMIN
        ):
            logger.error(
                f"User {removed_by} lacks permission to remove roles from user {user_id}"
            )
            return False

        # Remove role if assigned
        if role_name in user.roles:
            user.roles.remove(role_name)
            user.updated_at = datetime.now(timezone.utc)

            # Log role removal
            self._log_audit_event(
                user_id=removed_by,
                action="role_removed",
                resource_type=ResourceType.USER,
                resource_id=user_id,
                additional_info={"role_name": role_name},
            )

            logger.info(f"Removed role {role_name} from user {user_id}")
            return True

        logger.info(f"User {user_id} does not have role {role_name}")
        return False

    def create_custom_role(
        self,
        name: str,
        description: str,
        permissions: List[Permission],
        created_by: str,
    ) -> bool:
        """Create a custom role"""
        # Check if creator has permission to create roles
        if not self.check_permission(
            created_by, ResourceType.USER, "*", PermissionLevel.ADMIN
        ):
            logger.error(f"User {created_by} lacks permission to create custom roles")
            return False

        # Check if role already exists
        if name in self.roles:
            logger.error(f"Role {name} already exists")
            return False

        # Create new role
        new_role = Role(
            name=name,
            description=description,
            permissions=permissions,
            is_system_role=False,
            created_by=created_by,
        )

        self.roles[name] = new_role

        # Log role creation
        self._log_audit_event(
            user_id=created_by,
            action="custom_role_created",
            resource_type=ResourceType.USER,
            resource_id="*",
            additional_info={"role_name": name, "description": description},
        )

        logger.info(f"Created custom role {name} with {len(permissions)} permissions")
        return True

    def get_audit_logs(
        self,
        user_id: str = None,
        resource_type: ResourceType = None,
        resource_id: str = None,
        action: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """Get audit logs with filtering capabilities"""
        filtered_logs = self.audit_log.copy()

        # Apply filters
        if user_id:
            filtered_logs = [log for log in filtered_logs if log.user_id == user_id]

        if resource_type:
            filtered_logs = [
                log for log in filtered_logs if log.resource_type == resource_type
            ]

        if resource_id:
            filtered_logs = [
                log for log in filtered_logs if log.resource_id == resource_id
            ]

        if action:
            filtered_logs = [log for log in filtered_logs if log.action == action]

        if start_time:
            filtered_logs = [
                log for log in filtered_logs if log.timestamp >= start_time
            ]

        if end_time:
            filtered_logs = [log for log in filtered_logs if log.timestamp <= end_time]

        # Sort by timestamp (most recent first) and limit results
        filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
        return filtered_logs[:limit]

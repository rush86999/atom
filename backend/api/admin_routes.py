"""
Admin User Management API Routes
Handles administrative users and role-based access control
"""
from datetime import datetime
import logging
from typing import Dict, List, Optional
from fastapi import Depends, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.exceptions import (
    MissingFieldError,
    UserAlreadyExistsError,
    UserNotFoundError,
    ValidationError,
    WorkspaceNotFoundError,
)
from core.models import AdminRole, AdminUser, User

router = BaseAPIRouter(prefix="/api/admin", tags=["Admin"])
logger = logging.getLogger(__name__)


async def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires super_admin role

    Raises 403 if current user is not a super_admin
    """
    if current_user.role != "super_admin":
        raise router.permission_denied_error(
            action="access_admin_endpoints",
            resource="Admin",
            details={"required_role": "super_admin", "actual_role": current_user.role}
        )
    return current_user


# Request/Response Models
class AdminUserWithRole(BaseModel):
    """Admin user with role information"""
    id: str
    email: str
    name: str
    role_id: str
    role_name: str
    permissions: dict
    status: str
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class UpdateLastLoginResponse(BaseModel):
    """Response after updating last login"""
    message: str


class CreateAdminUserRequest(BaseModel):
    """Request to create a new admin user"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8)
    role_id: str = Field(..., description="ID of the admin role to assign")


class UpdateAdminUserRequest(BaseModel):
    """Request to update an admin user"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    role_id: Optional[str] = Field(None, description="ID of the admin role to assign")
    status: Optional[str] = Field(None, description="Admin status (active, inactive)")


class AdminUserResponse(BaseModel):
    """Detailed admin user response"""
    id: str
    email: str
    name: str
    role_id: str
    status: str
    last_login: Optional[datetime]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class DeleteAdminUserResponse(BaseModel):
    """Response after deleting admin user"""
    message: str


class CreateAdminRoleRequest(BaseModel):
    """Request to create a new admin role"""
    name: str = Field(..., min_length=1, max_length=100, unique=True, description="Role name (must be unique)")
    permissions: Dict[str, bool] = Field(..., description="Permissions dict (e.g., {'users': true, 'workflows': false})")
    description: Optional[str] = Field(None, max_length=500, description="Role description")


class UpdateAdminRoleRequest(BaseModel):
    """Request to update an admin role"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    permissions: Optional[Dict[str, bool]] = Field(None, description="Permissions dict")
    description: Optional[str] = Field(None, max_length=500, description="Role description")


class AdminRoleResponse(BaseModel):
    """Admin role response"""
    id: str
    name: str
    permissions: Dict[str, bool]
    description: Optional[str]

    class Config:
        from_attributes = True


class DeleteAdminRoleResponse(BaseModel):
    """Response after deleting admin role"""
    message: str


# Endpoints
@router.get("/users", response_model=List[AdminUserWithRole])
async def list_admin_users(
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    List all admin users with their roles

    Requires super_admin role.
    Returns comprehensive list of admin users including permissions.
    """
    # Query admin users with roles
    admin_users = db.query(AdminUser).join(AdminRole).all()

    return [
        AdminUserWithRole(
            id=admin.id,
            email=admin.email,
            name=admin.name,
            role_id=admin.role_id,
            role_name=admin.role.name,
            permissions=admin.role.permissions or {},
            status=admin.status,
            last_login=admin.last_login
        )
        for admin in admin_users
    ]


@router.get("/users/{admin_id}", response_model=AdminUserResponse)
async def get_admin_user(
    admin_id: str,
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get specific admin user by ID

    Returns detailed admin user information.
    """
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()

    if not admin:
        raise router.not_found_error("AdminUser", admin_id)

    return AdminUserResponse(
        id=admin.id,
        email=admin.email,
        name=admin.name,
        role_id=admin.role_id,
        status=admin.status,
        last_login=admin.last_login,
        created_at=admin.created_at
    )


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
@require_governance(
    action_complexity=ActionComplexity.CRITICAL,
    action_name="create_admin_user",
    feature="admin"
)
async def create_admin_user(
    request: CreateAdminUserRequest,
    http_request: Request,
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Create a new admin user

    Creates a new admin user with the specified role.
    Requires super_admin role.

    **Governance**: Agent-based creation requires AUTONOMOUS maturity (CRITICAL).
    - Admin user creation is a critical action
    - Requires AUTONOMOUS maturity for agents
    """
    # Check if role exists
    role = db.query(AdminRole).filter(AdminRole.id == request.role_id).first()
    if not role:
        raise router.not_found_error(
            "AdminRole",
            request.role_id,
            details={"field": "role_id"}
        )

    # Check if email already exists
    existing = db.query(AdminUser).filter(AdminUser.email == request.email).first()
    if existing:
        raise router.conflict_error(
            message="Admin user with this email already exists",
            conflicting_resource=request.email,
            details={"field": "email", "email": request.email}
        )

    # Hash password (import from auth)
    from core.auth import get_password_hash
    password_hash = get_password_hash(request.password)

    admin = AdminUser(
        email=request.email,
        name=request.name,
        password_hash=password_hash,
        role_id=request.role_id,
        status="active"
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)

    logger.info(f"Admin user created: {admin.id} by {current_admin.id}")
    return AdminUserResponse(
        id=admin.id,
        email=admin.email,
        name=admin.name,
        role_id=admin.role_id,
        status=admin.status,
        last_login=admin.last_login,
        created_at=admin.created_at
    )


@router.patch("/users/{admin_id}", response_model=AdminUserResponse)
async def update_admin_user(
    admin_id: str,
    request: UpdateAdminUserRequest,
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Update admin user

    Updates admin user information. Only provided fields are updated.
    Requires super_admin role.
    """
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()

    if not admin:
        raise router.not_found_error("AdminUser", admin_id)

    # Update only provided fields
    if request.name is not None:
        admin.name = request.name
    if request.role_id is not None:
        # Verify role exists
        role = db.query(AdminRole).filter(AdminRole.id == request.role_id).first()
        if not role:
            raise router.not_found_error(
                "AdminRole",
                request.role_id,
                details={"field": "role_id"}
            )
        admin.role_id = request.role_id
    if request.status is not None:
        admin.status = request.status

    db.commit()
    db.refresh(admin)

    return AdminUserResponse(
        id=admin.id,
        email=admin.email,
        name=admin.name,
        role_id=admin.role_id,
        status=admin.status,
        last_login=admin.last_login,
        created_at=admin.created_at
    )


@router.delete("/users/{admin_id}", response_model=DeleteAdminUserResponse)
@require_governance(
    action_complexity=ActionComplexity.CRITICAL,
    action_name="delete_admin_user",
    feature="admin"
)
async def delete_admin_user(
    admin_id: str,
    http_request: Request,
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Delete admin user

    Permanently deletes an admin user.
    Requires super_admin role.

    **Governance**: Agent-based deletion requires AUTONOMOUS maturity (CRITICAL).
    - Admin user deletion is a critical action
    - Requires AUTONOMOUS maturity for agents
    """
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()

    if not admin:
        raise router.not_found_error("AdminUser", admin_id)

    deleted_email = admin.email
    db.delete(admin)
    db.commit()

    logger.info(f"Admin user deleted: {admin_id} ({deleted_email}) by {current_admin.id}")
    return DeleteAdminUserResponse(message="Admin user deleted successfully")


@router.patch("/users/{admin_id}/last-login", response_model=UpdateLastLoginResponse)
async def update_admin_last_login(
    admin_id: str,
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Update admin user's last login timestamp

    Called after successful admin authentication.
    """
    # Find admin user
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not admin:
        raise router.not_found_error("AdminUser", admin_id)

    # Update last login
    admin.last_login = datetime.utcnow()
    db.commit()

    return UpdateLastLoginResponse(message="Last login updated")


# Role Management Endpoints
@router.get("/roles", response_model=List[AdminRoleResponse])
async def list_admin_roles(
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    List all admin roles

    Returns all available admin roles with their permissions.
    """
    roles = db.query(AdminRole).all()

    return [
        AdminRoleResponse(
            id=role.id,
            name=role.name,
            permissions=role.permissions or {},
            description=role.description
        )
        for role in roles
    ]


@router.get("/roles/{role_id}", response_model=AdminRoleResponse)
async def get_admin_role(
    role_id: str,
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Get specific admin role by ID

    Returns detailed role information including permissions.
    """
    role = db.query(AdminRole).filter(AdminRole.id == role_id).first()

    if not role:
        raise router.not_found_error("AdminRole", role_id)

    return AdminRoleResponse(
        id=role.id,
        name=role.name,
        permissions=role.permissions or {},
        description=role.description
    )


@router.post("/roles", response_model=AdminRoleResponse, status_code=status.HTTP_201_CREATED)
@require_governance(
    action_complexity=ActionComplexity.CRITICAL,
    action_name="create_admin_role",
    feature="admin"
)
async def create_admin_role(
    request: CreateAdminRoleRequest,
    http_request: Request,
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Create a new admin role

    Creates a new admin role with specified permissions.
    Role names must be unique.

    **Governance**: Agent-based creation requires AUTONOMOUS maturity (CRITICAL).
    - Admin role creation is a critical action
    - Requires AUTONOMOUS maturity for agents
    """
    # Check if role name already exists
    existing = db.query(AdminRole).filter(AdminRole.name == request.name).first()
    if existing:
        raise router.conflict_error(
            message="Role with this name already exists",
            conflicting_resource=request.name,
            details={"field": "name", "name": request.name}
        )

    role = AdminRole(
        name=request.name,
        permissions=request.permissions,
        description=request.description
    )

    db.add(role)
    db.commit()
    db.refresh(role)

    return AdminRoleResponse(
        id=role.id,
        name=role.name,
        permissions=role.permissions,
        description=role.description
    )


@router.patch("/roles/{role_id}", response_model=AdminRoleResponse)
async def update_admin_role(
    role_id: str,
    request: UpdateAdminRoleRequest,
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Update admin role

    Updates role information. Only provided fields are updated.
    """
    role = db.query(AdminRole).filter(AdminRole.id == role_id).first()

    if not role:
        raise router.not_found_error("AdminRole", role_id)

    # Check if new name conflicts with existing role
    if request.name is not None and request.name != role.name:
        existing = db.query(AdminRole).filter(
            AdminRole.name == request.name,
            AdminRole.id != role_id
        ).first()
        if existing:
            raise router.conflict_error(
                message="Role with this name already exists",
                conflicting_resource=request.name,
                details={"field": "name", "name": request.name}
            )
        role.name = request.name

    # Update other fields
    if request.permissions is not None:
        role.permissions = request.permissions
    if request.description is not None:
        role.description = request.description

    db.commit()
    db.refresh(role)

    return AdminRoleResponse(
        id=role.id,
        name=role.name,
        permissions=role.permissions,
        description=role.description
    )


@router.delete("/roles/{role_id}", response_model=DeleteAdminRoleResponse)
@require_governance(
    action_complexity=ActionComplexity.CRITICAL,
    action_name="delete_admin_role",
    feature="admin"
)
async def delete_admin_role(
    role_id: str,
    http_request: Request,
    current_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Delete admin role

    Permanently deletes an admin role.
    Fails if the role is currently assigned to any admin users.

    **Governance**: Agent-based deletion requires AUTONOMOUS maturity (CRITICAL).
    - Admin role deletion is a critical action
    - Requires AUTONOMOUS maturity for agents
    """
    role = db.query(AdminRole).filter(AdminRole.id == role_id).first()

    if not role:
        raise router.not_found_error("AdminRole", role_id)

    # Check if role is in use
    users_with_role = db.query(AdminUser).filter(AdminUser.role_id == role_id).count()
    if users_with_role > 0:
        raise router.conflict_error(
            message=f"Cannot delete role: {users_with_role} admin user(s) still assigned to this role",
            details={"users_count": users_with_role, "role_id": role_id}
        )

    db.delete(role)
    db.commit()

    return DeleteAdminRoleResponse(message="Admin role deleted successfully")

"""
Admin User Management API Routes
Handles administrative users and role-based access control
"""
from datetime import datetime
import logging
from typing import Dict, List, Optional
from fastapi import Depends, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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


# ============================================================================
# WebSocket Management Endpoints
# ============================================================================

class WebSocketStatusResponse(BaseModel):
    """WebSocket status response"""
    connected: bool
    ws_url: Optional[str] = None
    last_connected_at: Optional[str] = None
    last_message_at: Optional[str] = None
    reconnect_attempts: int = 0
    consecutive_failures: int = 0
    last_disconnect_reason: Optional[str] = None
    fallback_to_polling: bool = False
    rate_limit_messages_per_sec: int = 100


class WebSocketReconnectResponse(BaseModel):
    """WebSocket reconnect response"""
    reconnect_triggered: bool
    message: str


class WebSocketToggleResponse(BaseModel):
    """WebSocket toggle response"""
    success: bool
    websocket_enabled: Optional[bool] = None
    message: str


@router.get("/websocket/status", response_model=WebSocketStatusResponse)
async def get_websocket_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get WebSocket connection status

    Returns current WebSocket connection details including:
    - Connection status (connected/disconnected)
    - Last connection and message timestamps
    - Reconnect attempts and failure reasons
    - Fallback mode status

    Requires AUTONOMOUS maturity.
    """
    # Check governance (AUTONOMOUS required)
    from core.agent_governance_service import GovernanceCache
    governance_cache = GovernanceCache()

    # Get user's maturity level
    user_maturity = "AUTONOMOUS"  # Default to AUTONOMOUS for human users

    if user_maturity != "AUTONOMOUS":
        raise router.permission_denied_error(
            action="get_websocket_status",
            resource="WebSocket",
            details={"required_maturity": "AUTONOMOUS", "actual_maturity": user_maturity}
        )

    # Get WebSocket state from database
    from core.models import WebSocketState
    ws_state = db.query(WebSocketState).first()

    if not ws_state:
        return WebSocketStatusResponse(
            connected=False,
            reconnect_attempts=0,
            consecutive_failures=0,
            rate_limit_messages_per_sec=100
        )

    return WebSocketStatusResponse(
        connected=ws_state.connected,
        last_connected_at=ws_state.last_connected_at.isoformat() if ws_state.last_connected_at else None,
        last_message_at=ws_state.last_message_at.isoformat() if ws_state.last_message_at else None,
        reconnect_attempts=ws_state.reconnect_attempts,
        consecutive_failures=ws_state.consecutive_failures,
        last_disconnect_reason=ws_state.disconnect_reason,
        fallback_to_polling=ws_state.fallback_to_polling,
        rate_limit_messages_per_sec=100
    )


@router.post("/websocket/reconnect", response_model=WebSocketReconnectResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="websocket_reconnect",
    feature="admin"
)
async def trigger_websocket_reconnect(
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Force WebSocket reconnection

    Triggers immediate WebSocket reconnection attempt.
    If currently connected, disconnects and reconnects.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    # Log audit trail
    logger.info(f"WebSocket reconnect triggered by {current_user.id} (agent: {agent_id})")

    # Get WebSocket client instance (would need to be stored globally)
    # For now, just update database state to trigger reconnect
    from core.models import WebSocketState
    ws_state = db.query(WebSocketState).first()

    if not ws_state:
        ws_state = WebSocketState(id=1)
        db.add(ws_state)

    # Reset reconnect attempts to allow immediate reconnect
    ws_state.reconnect_attempts = 0
    ws_state.consecutive_failures = 0
    ws_state.fallback_to_polling = False
    db.commit()

    return WebSocketReconnectResponse(
        reconnect_triggered=True,
        message="WebSocket reconnection triggered. Reconnect will attempt on next cycle."
    )


@router.post("/websocket/disable", response_model=WebSocketToggleResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="websocket_disable",
    feature="admin"
)
async def disable_websocket(
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Disable WebSocket (use polling only)

    Disables WebSocket connection and switches to polling-only mode.
    Useful for troubleshooting or if WebSocket is causing issues.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    # Log audit trail
    logger.info(f"WebSocket disabled by {current_user.id} (agent: {agent_id})")

    from core.models import WebSocketState
    ws_state = db.query(WebSocketState).first()

    if not ws_state:
        ws_state = WebSocketState(id=1)
        db.add(ws_state)

    ws_state.fallback_to_polling = True
    ws_state.fallback_started_at = datetime.now()
    ws_state.connected = False
    ws_state.disconnect_reason = "disabled_by_admin"
    db.commit()

    return WebSocketToggleResponse(
        success=True,
        websocket_enabled=False,
        message="WebSocket disabled. System will use polling for sync."
    )


@router.post("/websocket/enable", response_model=WebSocketToggleResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="websocket_enable",
    feature="admin"
)
async def enable_websocket(
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Re-enable WebSocket

    Re-enables WebSocket connection after it was disabled.
    System will attempt to reconnect to WebSocket server.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    # Log audit trail
    logger.info(f"WebSocket enabled by {current_user.id} (agent: {agent_id})")

    from core.models import WebSocketState
    ws_state = db.query(WebSocketState).first()

    if not ws_state:
        ws_state = WebSocketState(id=1)
        db.add(ws_state)

    ws_state.fallback_to_polling = False
    ws_state.next_ws_attempt_at = None
    ws_state.reconnect_attempts = 0
    db.commit()

    return WebSocketToggleResponse(
        success=True,
        websocket_enabled=True,
        message="WebSocket enabled. Reconnection will be attempted."
    )


# ============================================================================
# Rating Sync Admin Endpoints (Phase 61 Plan 02)
# ============================================================================

class RatingSyncRequest(BaseModel):
    """Request to trigger rating sync"""
    upload_all: bool = Field(default=False, description="Upload all ratings (default: only pending)")


class RatingSyncResponse(BaseModel):
    """Response from rating sync"""
    success: bool
    uploaded: int
    failed: int
    skipped: int
    pending_count: int
    message: Optional[str] = None
    error: Optional[str] = None


class FailedRatingUploadResponse(BaseModel):
    """Failed rating upload details"""
    id: str
    rating_id: str
    error_message: str
    failed_at: datetime
    retry_count: int
    last_retry_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class RetryRatingUploadResponse(BaseModel):
    """Response from retrying failed upload"""
    success: bool
    message: str
    retry_triggered: bool


@router.post("/sync/ratings", response_model=RatingSyncResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="rating_sync",
    feature="admin"
)
async def trigger_rating_sync(
    request: RatingSyncRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Trigger manual rating sync with Atom SaaS

    Manually trigger rating sync to upload pending ratings to Atom SaaS.
    Returns 503 if sync is already in progress.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    - Manual sync is a high-complexity administrative action
    - AUTONOMOUS maturity required for agents

    Args:
        request: Sync request with upload_all flag
        current_user: Authenticated user
        db: Database session
        agent_id: Agent ID if triggered by agent

    Returns:
        RatingSyncResponse with upload counts
    """
    from core.rating_sync_service import RatingSyncService
    from core.atom_saas_client import AtomSaaSClient

    # Log audit trail
    logger.info(
        f"Rating sync triggered by {current_user.id} "
        f"(agent: {agent_id}, upload_all: {request.upload_all})"
    )

    # Create sync service
    client = AtomSaaSClient()
    sync_service = RatingSyncService(db, client)

    # Check if sync is already in progress
    if sync_service._sync_in_progress:
        from fastapi import status
        raise router.api_error(
            error_code="RATING_SYNC_IN_PROGRESS",
            message="Rating sync is already in progress",
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    # Get pending count before sync
    pending_count = len(sync_service.get_pending_ratings())

    # Trigger sync
    import asyncio
    result = await sync_service.sync_ratings(upload_all=request.upload_all)

    logger.info(
        f"Rating sync completed for {current_user.id}: "
        f"{result.get('uploaded')} uploaded, {result.get('failed')} failed"
    )

    return RatingSyncResponse(
        success=result.get("success", False),
        uploaded=result.get("uploaded", 0),
        failed=result.get("failed", 0),
        skipped=result.get("skipped", 0),
        pending_count=pending_count,
        message=result.get("message"),
        error=result.get("error")
    )


@router.get("/ratings/failed-uploads", response_model=List[FailedRatingUploadResponse])
async def get_failed_rating_uploads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get failed rating uploads (dead letter queue)

    Returns list of failed rating uploads for inspection and manual retry.
    Failed uploads are stored when rating sync encounters errors.

    Requires AUTONOMOUS maturity.
    """
    from core.agent_governance_service import GovernanceCache
    governance_cache = GovernanceCache()

    # Get user's maturity level
    user_maturity = "AUTONOMOUS"  # Default to AUTONOMOUS for human users

    if user_maturity != "AUTONOMOUS":
        raise router.permission_denied_error(
            action="get_failed_rating_uploads",
            resource="RatingUpload",
            details={"required_maturity": "AUTONOMOUS", "actual_maturity": user_maturity}
        )

    from core.models import FailedRatingUpload

    # Query failed uploads, ordered by failed_at desc
    failed_uploads = (
        db.query(FailedRatingUpload)
        .order_by(FailedRatingUpload.failed_at.desc())
        .limit(100)  # Pagination limit
        .all()
    )

    return [
        FailedRatingUploadResponse(
            id=failed.id,
            rating_id=failed.rating_id,
            error_message=failed.error_message,
            failed_at=failed.failed_at,
            retry_count=failed.retry_count,
            last_retry_at=failed.last_retry_at
        )
        for failed in failed_uploads
    ]


@router.post("/ratings/failed-uploads/{failed_id}/retry", response_model=RetryRatingUploadResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="retry_rating_upload",
    feature="admin"
)
async def retry_failed_rating_upload(
    failed_id: str,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Retry failed rating upload

    Manually retry a failed rating upload from the dead letter queue.
    Deletes the failed upload record on success.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    from core.models import FailedRatingUpload, SkillRating
    from core.rating_sync_service import RatingSyncService
    from core.atom_saas_client import AtomSaaSClient

    # Log audit trail
    logger.info(
        f"Retry failed rating upload {failed_id} by {current_user.id} "
        f"(agent: {agent_id})"
    )

    # Fetch failed upload record
    failed = (
        db.query(FailedRatingUpload)
        .filter(FailedRatingUpload.id == failed_id)
        .first()
    )

    if not failed:
        raise router.not_found_error("FailedRatingUpload", failed_id)

    # Fetch the rating
    rating = (
        db.query(SkillRating)
        .filter(SkillRating.id == failed.rating_id)
        .first()
    )

    if not rating:
        # Rating was deleted, remove failed record
        db.delete(failed)
        db.commit()
        return RetryRatingUploadResponse(
            success=False,
            message="Rating no longer exists, failed record removed",
            retry_triggered=False
        )

    # Create sync service and retry upload
    client = AtomSaaSClient()
    sync_service = RatingSyncService(db, client)

    # Upload single rating
    import asyncio
    result = await sync_service.upload_rating(rating)

    if result.get("success"):
        # Success - mark as synced and remove failed record
        remote_id = result.get("rating_id")
        if remote_id:
            sync_service.mark_as_synced(rating.id, remote_id)

        db.delete(failed)
        db.commit()

        logger.info(f"Retry successful for failed upload {failed_id}")
        return RetryRatingUploadResponse(
            success=True,
            message=f"Rating uploaded successfully (remote_id: {remote_id})",
            retry_triggered=True
        )
    else:
        # Failed again - increment retry count
        failed.retry_count += 1
        failed.last_retry_at = datetime.now()
        failed.error_message = result.get("error", "Unknown error")
        db.commit()

        logger.error(f"Retry failed for {failed_id}: {result.get('error')}")
        return RetryRatingUploadResponse(
            success=False,
            message=f"Retry failed: {result.get('error')}",
            retry_triggered=True
        )


# ============================================================================
# Conflict Management Endpoints
# ============================================================================

class ConflictLogResponse(BaseModel):
    """Conflict log entry response"""
    id: int
    skill_id: str
    conflict_type: str
    severity: str
    local_data: dict
    remote_data: dict
    resolution_strategy: Optional[str]
    resolved_data: Optional[dict]
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConflictListResponse(BaseModel):
    """Paginated list of conflicts"""
    conflicts: List[ConflictLogResponse]
    total_count: int
    page: int
    page_size: int


class ResolveConflictRequest(BaseModel):
    """Request to resolve a conflict"""
    strategy: str = Field(..., description="Resolution strategy: remote_wins, local_wins, merge")
    resolved_by: str = Field(..., description="User or system resolving the conflict")


class ResolveConflictResponse(BaseModel):
    """Response after resolving conflict"""
    success: bool
    message: str
    resolved_data: Optional[dict] = None


class BulkResolveConflictsRequest(BaseModel):
    """Request to bulk resolve conflicts"""
    conflict_ids: List[int] = Field(..., min_items=1, max_items=100, description="List of conflict IDs to resolve (max 100)")
    strategy: str = Field(..., description="Resolution strategy: remote_wins, local_wins, merge")
    resolved_by: str = Field(..., description="User or system resolving the conflicts")


class BulkResolveConflictsResponse(BaseModel):
    """Response after bulk resolving conflicts"""
    success: bool
    message: str
    resolved_count: int
    failed_count: int
    errors: List[str] = []


@router.get("/conflicts", response_model=ConflictListResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="list_conflicts",
    feature="admin"
)
async def list_conflicts(
    severity: Optional[str] = None,
    conflict_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    List unresolved conflicts

    Returns paginated list of unresolved skill sync conflicts.
    Can filter by severity and conflict type.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    from core.models import ConflictLog
    from core.conflict_resolution_service import ConflictResolutionService

    # Log audit trail
    logger.info(
        f"List conflicts by {current_user.id} (agent: {agent_id}) "
        f"filters: severity={severity}, type={conflict_type}"
    )

    resolver = ConflictResolutionService(db)

    # Get unresolved conflicts
    conflicts = resolver.get_unresolved_conflicts(
        severity=severity,
        conflict_type=conflict_type,
        limit=page_size
    )

    # Calculate pagination
    total_count = len(conflicts)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_conflicts = conflicts[start_idx:end_idx]

    return ConflictListResponse(
        conflicts=[
            ConflictLogResponse(
                id=c.id,
                skill_id=c.skill_id,
                conflict_type=c.conflict_type,
                severity=c.severity,
                local_data=c.local_data,
                remote_data=c.remote_data,
                resolution_strategy=c.resolution_strategy,
                resolved_data=c.resolved_data,
                resolved_at=c.resolved_at,
                resolved_by=c.resolved_by,
                created_at=c.created_at
            )
            for c in paginated_conflicts
        ],
        total_count=total_count,
        page=page,
        page_size=page_size
    )


@router.get("/conflicts/{conflict_id}", response_model=ConflictLogResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="get_conflict",
    feature="admin"
)
async def get_conflict(
    conflict_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Get conflict details by ID

    Returns full conflict data including local/remote skill data
    and a diff summary of what changed.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    from core.conflict_resolution_service import ConflictResolutionService

    # Log audit trail
    logger.info(
        f"Get conflict {conflict_id} by {current_user.id} (agent: {agent_id})"
    )

    resolver = ConflictResolutionService(db)
    conflict = resolver.get_conflict_by_id(conflict_id)

    if not conflict:
        raise router.not_found_error("ConflictLog", conflict_id)

    return ConflictLogResponse(
        id=conflict.id,
        skill_id=conflict.skill_id,
        conflict_type=conflict.conflict_type,
        severity=conflict.severity,
        local_data=conflict.local_data,
        remote_data=conflict.remote_data,
        resolution_strategy=conflict.resolution_strategy,
        resolved_data=conflict.resolved_data,
        resolved_at=conflict.resolved_at,
        resolved_by=conflict.resolved_by,
        created_at=conflict.created_at
    )


@router.post("/conflicts/{conflict_id}/resolve", response_model=ResolveConflictResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="resolve_conflict",
    feature="admin"
)
async def resolve_conflict(
    conflict_id: int,
    request: ResolveConflictRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Resolve a conflict

    Applies the specified resolution strategy to a conflict.
    Updates the ConflictLog and triggers cache update with resolved data.

    Strategies:
    - remote_wins: Use Atom SaaS skill data
    - local_wins: Use local skill data
    - merge: Intelligently merge fields

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    from core.conflict_resolution_service import ConflictResolutionService

    # Validate strategy
    valid_strategies = ["remote_wins", "local_wins", "merge"]
    if request.strategy not in valid_strategies:
        raise router.validation_error(
            "Invalid strategy",
            details={"valid_strategies": valid_strategies, "provided": request.strategy}
        )

    # Log audit trail
    logger.info(
        f"Resolve conflict {conflict_id} by {current_user.id} "
        f"(agent: {agent_id}) using {request.strategy}"
    )

    resolver = ConflictResolutionService(db)

    # Resolve conflict
    resolved_data = resolver.resolve_conflict(
        conflict_id=conflict_id,
        strategy=request.strategy,
        resolved_by=request.resolved_by
    )

    if resolved_data is None and request.strategy != "manual":
        return ResolveConflictResponse(
            success=False,
            message="Failed to resolve conflict"
        )

    # Update cache with resolved data
    if resolved_data:
        from core.models import SkillCache
        from datetime import timezone, timedelta

        skill_id = resolved_data.get("skill_id") or resolved_data.get("id")
        if skill_id:
            # Calculate expiry
            expires_at = datetime.now(timezone.utc).replace(
                hour=23, minute=59, second=59, microsecond=0
            )

            # Update cache
            existing = db.query(SkillCache).filter(
                SkillCache.skill_id == skill_id
            ).first()

            if existing:
                existing.skill_data = resolved_data
                existing.expires_at = expires_at
                db.commit()

    return ResolveConflictResponse(
        success=True,
        message=f"Conflict resolved using {request.strategy}",
        resolved_data=resolved_data
    )


@router.post("/conflicts/bulk-resolve", response_model=BulkResolveConflictsResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="bulk_resolve_conflicts",
    feature="admin"
)
async def bulk_resolve_conflicts(
    request: BulkResolveConflictsRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Bulk resolve multiple conflicts

    Applies the same resolution strategy to multiple conflicts.
    Uses transaction for atomicity (all or nothing).

    Max 100 conflicts per request.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    from core.conflict_resolution_service import ConflictResolutionService

    # Validate strategy
    valid_strategies = ["remote_wins", "local_wins", "merge"]
    if request.strategy not in valid_strategies:
        raise router.validation_error(
            "Invalid strategy",
            details={"valid_strategies": valid_strategies, "provided": request.strategy}
        )

    # Log audit trail
    logger.info(
        f"Bulk resolve {len(request.conflict_ids)} conflicts by {current_user.id} "
        f"(agent: {agent_id}) using {request.strategy}"
    )

    resolver = ConflictResolutionService(db)
    resolved_count = 0
    failed_count = 0
    errors = []

    # Resolve each conflict
    for conflict_id in request.conflict_ids:
        try:
            resolved_data = resolver.resolve_conflict(
                conflict_id=conflict_id,
                strategy=request.strategy,
                resolved_by=request.resolved_by
            )

            if resolved_data or request.strategy == "manual":
                resolved_count += 1
            else:
                failed_count += 1
                errors.append(f"Conflict {conflict_id}: Failed to resolve")

        except Exception as e:
            failed_count += 1
            errors.append(f"Conflict {conflict_id}: {str(e)}")

    return BulkResolveConflictsResponse(
        success=(failed_count == 0),
        message=f"Resolved {resolved_count} conflicts, {failed_count} failed",
        resolved_count=resolved_count,
        failed_count=failed_count,
        errors=errors
    )


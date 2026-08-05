"""
Workspace Synchronization API Routes

Provides REST endpoints for unified workspace management:
- Create unified workspaces
- Add/remove platforms
- Propagate changes
- Get sync status
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.auth import get_current_user, User
from core.database import get_db
from integrations.workspace_sync_service import (
    ChangeType,
    SyncConflictResolution,
    WorkspaceSyncService,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Request/Response Models
# ============================================================================

class CreateWorkspaceRequest(BaseModel):
    """Request to create a unified workspace"""
    user_id: str
    # BUG-121: Add max_length to prevent unbounded DB writes (DoS vector).
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    slack_workspace_id: Optional[str] = Field(None, max_length=255)
    discord_guild_id: Optional[str] = Field(None, max_length=255)
    google_chat_space_id: Optional[str] = Field(None, max_length=255)
    teams_team_id: Optional[str] = Field(None, max_length=255)
    sync_config: Optional[Dict[str, Any]] = None


class AddPlatformRequest(BaseModel):
    """Request to add a platform to a workspace"""
    workspace_id: str
    platform: str  # slack, discord, google_chat, teams
    platform_id: str


class PropagateChangeRequest(BaseModel):
    """Request to propagate a change to other platforms"""
    workspace_id: str
    source_platform: str
    change_type: str
    change_data: Dict[str, Any]
    conflict_resolution: Optional[str] = SyncConflictResolution.LATEST_WINS


class WorkspaceResponse(BaseModel):
    """Response with workspace details"""
    id: str
    user_id: str
    name: str
    description: Optional[str]
    slack_workspace_id: Optional[str]
    discord_guild_id: Optional[str]
    google_chat_space_id: Optional[str]
    teams_team_id: Optional[str]
    sync_status: str
    last_sync_at: Optional[str]
    platform_count: int
    member_count: int
    created_at: str
    updated_at: str


# ============================================================================
# Router
# ============================================================================

router = BaseAPIRouter(
    prefix="/api/v1/workspaces",
    tags=["Workspace Synchronization"]
)


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/unified", summary="Create unified workspace")
async def create_unified_workspace(
    request: CreateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a new unified workspace spanning multiple platforms.

    Validates that at least one platform is provided and creates
    a unified workspace that can sync across platforms.
    """
    try:
        # Validate at least one platform
        has_platform = any([
            request.slack_workspace_id,
            request.discord_guild_id,
            request.google_chat_space_id,
            request.teams_team_id
        ])

        if not has_platform:
            raise router.validation_error(
                field="platforms",
                message="At least one platform ID must be provided"
            )

        service = WorkspaceSyncService(db)
        workspace = service.create_unified_workspace(
            # R54: ownership comes from the token, never from the body — a
            # client-supplied user_id would create workspaces AS other users.
            user_id=current_user.id,
            name=request.name,
            description=request.description,
            slack_workspace_id=request.slack_workspace_id,
            discord_guild_id=request.discord_guild_id,
            google_chat_space_id=request.google_chat_space_id,
            teams_team_id=request.teams_team_id,
            sync_config=request.sync_config
        )

        return router.success_response(
            data=_workspace_to_dict(workspace),
            message=f"Unified workspace '{workspace.name}' created successfully"
        )

    except ValueError as e:
        raise router.validation_error(
            field="workspace",
            message=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create unified workspace: {e}")
        raise router.internal_error(
            message="Failed to create unified workspace",
            details={"error": "Internal error"}
        )


@router.post("/unified/{workspace_id}/platforms", summary="Add platform to workspace")
async def add_platform_to_workspace(
    workspace_id: str,
    request: AddPlatformRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Add a new platform connection to an existing unified workspace.

    Supports adding slack, discord, google_chat, or teams to a workspace.
    """
    try:
        service = WorkspaceSyncService(db)
        _get_owned_workspace_or_error(db, workspace_id, current_user, "add_platform")
        workspace = service.add_platform_to_workspace(
            workspace_id=workspace_id,
            platform=request.platform,
            platform_id=request.platform_id
        )

        return router.success_response(
            data=_workspace_to_dict(workspace),
            message=f"Platform '{request.platform}' added successfully"
        )

    except ValueError as e:
        raise router.not_found_error(
            resource="UnifiedWorkspace",
            resource_id=workspace_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add platform to workspace: {e}")
        raise router.internal_error(
            message="Failed to add platform",
            details={"error": "Internal error"}
        )


@router.post("/unified/{workspace_id}/sync", summary="Propagate changes to other platforms")
async def propagate_changes(
    workspace_id: str,
    request: PropagateChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Propagate a change from one platform to all other connected platforms.

    Used when a workspace change occurs on one platform and needs to be
    synchronized to all other connected platforms.
    """
    try:
        service = WorkspaceSyncService(db)
        _get_owned_workspace_or_error(db, workspace_id, current_user, "propagate_change")
        result = service.propagate_change(
            workspace_id=workspace_id,
            source_platform=request.source_platform,
            change_type=request.change_type,
            change_data=request.change_data,
            conflict_resolution=request.conflict_resolution
        )

        return router.success_response(
            data=result,
            message=f"Change propagated to {result['status']} status"
        )

    except ValueError as e:
        raise router.not_found_error(
            resource="UnifiedWorkspace",
            resource_id=workspace_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to propagate changes: {e}")
        raise router.internal_error(
            message="Failed to propagate changes",
            details={"error": "Internal error"}
        )


@router.get("/unified/{workspace_id}", summary="Get workspace sync status")
async def get_workspace_status(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed sync status for a unified workspace.

    Returns information about connected platforms, recent sync operations,
    and any errors that occurred during synchronization.
    """
    try:
        service = WorkspaceSyncService(db)
        _get_owned_workspace_or_error(db, workspace_id, current_user, "get_workspace_status")
        status = service.get_workspace_sync_status(workspace_id)

        return router.success_response(
            data=status,
            message="Workspace status retrieved successfully"
        )

    except ValueError as e:
        raise router.not_found_error(
            resource="UnifiedWorkspace",
            resource_id=workspace_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workspace status: {e}")
        raise router.internal_error(
            message="Failed to get workspace status",
            details={"error": "Internal error"}
        )


@router.get("/unified", summary="List all unified workspaces")
async def list_unified_workspaces(
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List all unified workspaces, optionally filtered by user.

    Returns a paginated list of unified workspaces with their sync status.
    """
    try:
        from core.models import UnifiedWorkspace

        query = db.query(UnifiedWorkspace)

        # R54: always scope the list to the authenticated user — a client-
        # supplied user_id filtered OTHER users' workspaces into the response.
        query = query.filter(UnifiedWorkspace.user_id == current_user.id)

        workspaces = query.order_by(UnifiedWorkspace.updated_at.desc()).all()

        return router.success_list_response(
            items=[_workspace_to_dict(w) for w in workspaces],
            total=len(workspaces),
            message=f"Retrieved {len(workspaces)} workspaces"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list workspaces: {e}")
        raise router.internal_error(
            message="Failed to list workspaces",
            details={"error": "Internal error"}
        )


@router.delete("/unified/{workspace_id}", summary="Delete unified workspace")
async def delete_unified_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete a unified workspace.

    This only removes the unified workspace mapping - it does NOT
    delete the actual workspaces on the connected platforms.
    """
    try:
        from core.models import UnifiedWorkspace

        workspace = _get_owned_workspace_or_error(
            db, workspace_id, current_user, "delete_unified_workspace"
        )

        workspace_name = workspace.name
        db.delete(workspace)
        db.commit()

        return router.success_response(
            data={"deleted_workspace_id": workspace_id},
            message=f"Unified workspace '{workspace_name}' deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workspace: {e}")
        raise router.internal_error(
            message="Failed to delete workspace",
            details={"error": "Internal error"}
        )


# ============================================================================
# Helper Functions
# ============================================================================

def _get_owned_workspace_or_error(db, workspace_id: str, current_user, action: str):
    """Fetch a workspace and enforce ownership (R54).

    Returns the workspace when the authenticated user owns it; otherwise
    raises 404 (not found) or 403 (permission denied). Every workspace-id
    endpoint must gate through this so cross-user reads/writes — including
    propagate_change's external-platform side effects — are impossible.
    """
    from core.models import UnifiedWorkspace

    workspace = db.query(UnifiedWorkspace).filter(
        UnifiedWorkspace.id == workspace_id
    ).first()
    if not workspace:
        raise router.not_found_error(
            resource="UnifiedWorkspace",
            resource_id=workspace_id
        )
    if workspace.user_id != current_user.id:
        raise router.permission_denied_error(
            action=action,
            resource="UnifiedWorkspace",
        )
    return workspace


def _workspace_to_dict(workspace) -> Dict[str, Any]:
    """Convert UnifiedWorkspace model to dictionary"""
    return {
        "id": workspace.id,
        "user_id": workspace.user_id,
        "name": workspace.name,
        "description": workspace.description,
        "slack_workspace_id": workspace.slack_workspace_id,
        "discord_guild_id": workspace.discord_guild_id,
        "google_chat_space_id": workspace.google_chat_space_id,
        "teams_team_id": workspace.teams_team_id,
        "sync_status": workspace.sync_status,
        "last_sync_at": workspace.last_sync_at.isoformat() if workspace.last_sync_at else None,
        "platform_count": workspace.platform_count,
        "member_count": workspace.member_count,
        "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
        "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None
    }

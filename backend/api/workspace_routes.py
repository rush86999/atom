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
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
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
    name: str
    description: Optional[str] = None
    slack_workspace_id: Optional[str] = None
    discord_guild_id: Optional[str] = None
    google_chat_space_id: Optional[str] = None
    teams_team_id: Optional[str] = None
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
            user_id=request.user_id,
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
    except Exception as e:
        logger.error(f"Failed to create unified workspace: {e}")
        raise router.internal_error(
            message="Failed to create unified workspace",
            details={"error": str(e)}
        )


@router.post("/unified/{workspace_id}/platforms", summary="Add platform to workspace")
async def add_platform_to_workspace(
    workspace_id: str,
    request: AddPlatformRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Add a new platform connection to an existing unified workspace.

    Supports adding slack, discord, google_chat, or teams to a workspace.
    """
    try:
        service = WorkspaceSyncService(db)
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
    except Exception as e:
        logger.error(f"Failed to add platform to workspace: {e}")
        raise router.internal_error(
            message="Failed to add platform",
            details={"error": str(e)}
        )


@router.post("/unified/{workspace_id}/sync", summary="Propagate changes to other platforms")
async def propagate_changes(
    workspace_id: str,
    request: PropagateChangeRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Propagate a change from one platform to all other connected platforms.

    Used when a workspace change occurs on one platform and needs to be
    synchronized to all other connected platforms.
    """
    try:
        service = WorkspaceSyncService(db)
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
    except Exception as e:
        logger.error(f"Failed to propagate changes: {e}")
        raise router.internal_error(
            message="Failed to propagate changes",
            details={"error": str(e)}
        )


@router.get("/unified/{workspace_id}", summary="Get workspace sync status")
async def get_workspace_status(
    workspace_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed sync status for a unified workspace.

    Returns information about connected platforms, recent sync operations,
    and any errors that occurred during synchronization.
    """
    try:
        service = WorkspaceSyncService(db)
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
    except Exception as e:
        logger.error(f"Failed to get workspace status: {e}")
        raise router.internal_error(
            message="Failed to get workspace status",
            details={"error": str(e)}
        )


@router.get("/unified", summary="List all unified workspaces")
async def list_unified_workspaces(
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List all unified workspaces, optionally filtered by user.

    Returns a paginated list of unified workspaces with their sync status.
    """
    try:
        from core.models import UnifiedWorkspace

        query = db.query(UnifiedWorkspace)

        if user_id:
            query = query.filter(UnifiedWorkspace.user_id == user_id)

        workspaces = query.order_by(UnifiedWorkspace.updated_at.desc()).all()

        return router.success_list_response(
            items=[_workspace_to_dict(w) for w in workspaces],
            total=len(workspaces),
            message=f"Retrieved {len(workspaces)} workspaces"
        )

    except Exception as e:
        logger.error(f"Failed to list workspaces: {e}")
        raise router.internal_error(
            message="Failed to list workspaces",
            details={"error": str(e)}
        )


@router.delete("/unified/{workspace_id}", summary="Delete unified workspace")
async def delete_unified_workspace(
    workspace_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete a unified workspace.

    This only removes the unified workspace mapping - it does NOT
    delete the actual workspaces on the connected platforms.
    """
    try:
        from core.models import UnifiedWorkspace

        workspace = db.query(UnifiedWorkspace).filter(
            UnifiedWorkspace.id == workspace_id
        ).first()

        if not workspace:
            raise router.not_found_error(
                resource="UnifiedWorkspace",
                resource_id=workspace_id
            )

        workspace_name = workspace.name
        db.delete(workspace)
        db.commit()

        return router.success_response(
            data={"deleted_workspace_id": workspace_id},
            message=f"Unified workspace '{workspace_name}' deleted successfully"
        )

    except Exception as e:
        logger.error(f"Failed to delete workspace: {e}")
        raise router.internal_error(
            message="Failed to delete workspace",
            details={"error": str(e)}
        )


# ============================================================================
# Helper Functions
# ============================================================================

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

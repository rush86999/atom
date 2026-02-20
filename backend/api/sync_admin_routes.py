"""
Atom SaaS Sync Admin API Routes
Consolidated admin endpoints for sync operations
Requires AUTONOMOUS maturity for all operations
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User, SyncState

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/admin/sync", tags=["Sync Admin"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SyncStatusResponse(BaseModel):
    """Current sync status"""
    status: str = Field(..., description="Sync status: idle, syncing, error")
    last_sync: Optional[datetime] = Field(None, description="Last successful sync time")
    sync_age_minutes: Optional[float] = Field(None, description="Minutes since last sync")
    skills_cached: int = Field(..., description="Number of skills in cache")
    categories_cached: int = Field(..., description="Number of categories in cache")
    last_error: Optional[str] = Field(None, description="Last error message")

    model_config = ConfigDict(from_attributes=True)


class SyncConfigResponse(BaseModel):
    """Sync configuration"""
    enabled: bool = Field(..., description="Whether sync is enabled")
    interval_minutes: int = Field(..., description="Sync interval in minutes")
    batch_size: int = Field(..., description="Batch size for sync operations")
    websocket_enabled: bool = Field(..., description="Whether WebSocket updates are enabled")
    atom_saas_api_url: str = Field(..., description="Atom SaaS API URL")


class TriggerSyncResponse(BaseModel):
    """Response after triggering manual sync"""
    message: str = Field(..., description="Success message")
    sync_id: str = Field(..., description="Sync operation ID")
    status: str = Field(..., description="Sync status")


class RatingSyncStatusResponse(BaseModel):
    """Rating sync status"""
    status: str = Field(..., description="Rating sync status")
    last_sync: Optional[datetime] = Field(None, description="Last rating sync time")
    pending_ratings: int = Field(..., description="Number of ratings pending sync")
    failed_uploads: int = Field(..., description="Number of failed uploads")


class FailedRatingUpload(BaseModel):
    """Failed rating upload details"""
    id: str = Field(..., description="Failed upload ID")
    skill_id: str = Field(..., description="Skill ID")
    error_message: str = Field(..., description="Error message")
    created_at: datetime = Field(..., description="Failure timestamp")
    retry_count: int = Field(..., description="Number of retry attempts")

    model_config = ConfigDict(from_attributes=True)


class RetryFailedUploadResponse(BaseModel):
    """Response after retrying failed upload"""
    message: str = Field(..., description="Success message")
    success: bool = Field(..., description="Whether retry succeeded")


class WebSocketStatusResponse(BaseModel):
    """WebSocket connection status"""
    connected: bool = Field(..., description="Whether WebSocket is connected")
    last_message: Optional[datetime] = Field(None, description="Last message received")
    reconnect_count: int = Field(..., description="Number of reconnections")
    enabled: bool = Field(..., description="Whether WebSocket is enabled")


class WebSocketReconnectResponse(BaseModel):
    """Response after forcing WebSocket reconnection"""
    message: str = Field(..., description="Success message")
    connected: bool = Field(..., description="New connection status")


class WebSocketToggleResponse(BaseModel):
    """Response after enabling/disabling WebSocket"""
    message: str = Field(..., description="Success message")
    enabled: bool = Field(..., description="New enabled status")


class ConflictListItem(BaseModel):
    """Conflict list item"""
    id: str = Field(..., description="Conflict ID")
    conflict_type: str = Field(..., description="Type of conflict")
    skill_id: str = Field(..., description="Skill ID")
    created_at: datetime = Field(..., description="Conflict timestamp")
    resolved: bool = Field(..., description="Whether conflict is resolved")

    model_config = ConfigDict(from_attributes=True)


class ConflictDetail(BaseModel):
    """Detailed conflict information"""
    id: str = Field(..., description="Conflict ID")
    conflict_type: str = Field(..., description="Type of conflict")
    skill_id: str = Field(..., description="Skill ID")
    local_value: Dict[str, Any] = Field(..., description="Local value")
    remote_value: Dict[str, Any] = Field(..., description="Remote value")
    created_at: datetime = Field(..., description="Conflict timestamp")
    resolved: bool = Field(..., description="Whether conflict is resolved")
    resolution_strategy: Optional[str] = Field(None, description="Resolution strategy used")

    model_config = ConfigDict(from_attributes=True)


class ResolveConflictResponse(BaseModel):
    """Response after resolving conflict"""
    message: str = Field(..., description="Success message")
    conflict_id: str = Field(..., description="Conflict ID")


class BulkResolveResponse(BaseModel):
    """Response after bulk resolving conflicts"""
    message: str = Field(..., description="Success message")
    resolved_count: int = Field(..., description="Number of conflicts resolved")
    failed_count: int = Field(..., description="Number of conflicts that failed")
    failed_ids: List[str] = Field(..., description="IDs of failed conflicts")


class PaginatedResponse(BaseModel):
    """Generic paginated response"""
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")


# ============================================================================
# Background Sync Endpoints
# ============================================================================

@router.post("/trigger", response_model=TriggerSyncResponse, status_code=status.HTTP_202_ACCEPTED)
@require_governance(
    action_complexity=ActionComplexity.CRITICAL,
    action_name="trigger_manual_sync",
    feature="sync"
)
async def trigger_manual_sync(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Trigger manual skill sync

    Manually triggers a sync operation with Atom SaaS marketplace.
    Returns immediately with sync operation ID.

    **Governance**: Requires AUTONOMOUS maturity (CRITICAL).
    """
    # Placeholder: Will call SyncService.trigger_sync() from 61-01-background-sync
    sync_id = f"manual_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"Manual sync triggered by {current_user.id}, sync_id={sync_id}")

    return TriggerSyncResponse(
        message="Manual sync triggered successfully",
        sync_id=sync_id,
        status="queued"
    )


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current sync status

    Returns current sync state including last sync time, cache size, and status.
    """
    # Placeholder: Will query SyncState from 61-01-background-sync
    sync_state = db.query(SyncState).first()

    if not sync_state:
        return SyncStatusResponse(
            status="idle",
            last_sync=None,
            sync_age_minutes=None,
            skills_cached=0,
            categories_cached=0,
            last_error=None
        )

    age_minutes = None
    if sync_state.last_sync:
        age_minutes = (datetime.utcnow() - sync_state.last_sync).total_seconds() / 60

    return SyncStatusResponse(
        status=sync_state.status or "idle",
        last_sync=sync_state.last_sync,
        sync_age_minutes=age_minutes,
        skills_cached=sync_state.skills_cached or 0,
        categories_cached=sync_state.categories_cached or 0,
        last_error=sync_state.last_error
    )


@router.get("/config", response_model=SyncConfigResponse)
async def get_sync_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get sync configuration

    Returns current sync configuration settings.
    """
    # Placeholder: Will return config from 61-01-background-sync
    return SyncConfigResponse(
        enabled=True,
        interval_minutes=30,
        batch_size=100,
        websocket_enabled=True,
        atom_saas_api_url="https://api.atomsaas.com"
    )


# ============================================================================
# Rating Sync Endpoints
# ============================================================================

@router.post("/ratings", response_model=TriggerSyncResponse, status_code=status.HTTP_202_ACCEPTED)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="trigger_rating_sync",
    feature="sync"
)
async def trigger_rating_sync(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Trigger manual rating sync

    Manually triggers rating sync to Atom SaaS.
    Returns immediately with sync operation ID.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    # Placeholder: Will call RatingSyncService.trigger_sync() from 61-02-bidirectional-sync
    sync_id = f"rating_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"Rating sync triggered by {current_user.id}, sync_id={sync_id}")

    return TriggerSyncResponse(
        message="Rating sync triggered successfully",
        sync_id=sync_id,
        status="queued"
    )


@router.get("/ratings/status", response_model=RatingSyncStatusResponse)
async def get_rating_sync_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get rating sync status

    Returns current rating sync state including pending ratings and failed uploads.
    """
    # Placeholder: Will query rating sync state from 61-02-bidirectional-sync
    return RatingSyncStatusResponse(
        status="idle",
        last_sync=None,
        pending_ratings=0,
        failed_uploads=0
    )


@router.get("/ratings/failed-uploads", response_model=List[FailedRatingUpload])
async def list_failed_rating_uploads(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List failed rating uploads

    Returns paginated list of failed rating uploads with error details.
    """
    # Placeholder: Will query failed uploads from 61-02-bidirectional-sync
    return []


@router.post("/ratings/failed-uploads/{upload_id}/retry", response_model=RetryFailedUploadResponse)
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="retry_failed_upload",
    feature="sync"
)
async def retry_failed_upload(
    upload_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Retry failed rating upload

    Retries a specific failed rating upload.

    **Governance**: Requires AUTONOMOUS maturity (MODERATE).
    """
    # Placeholder: Will call RatingSyncService.retry_upload() from 61-02-bidirectional-sync
    logger.info(f"Retry failed upload {upload_id} by {current_user.id}")

    return RetryFailedUploadResponse(
        message="Upload retry triggered",
        success=True
    )


# ============================================================================
# WebSocket Endpoints
# ============================================================================

@router.get("/websocket/status", response_model=WebSocketStatusResponse)
async def get_websocket_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get WebSocket connection status

    Returns current WebSocket connection state.
    """
    # Placeholder: Will query WebSocket status from 61-03-websocket-updates
    return WebSocketStatusResponse(
        connected=False,
        last_message=None,
        reconnect_count=0,
        enabled=True
    )


@router.post("/websocket/reconnect", response_model=WebSocketReconnectResponse)
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="websocket_reconnect",
    feature="sync"
)
async def force_websocket_reconnect(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Force WebSocket reconnection

    Forces WebSocket client to disconnect and reconnect.

    **Governance**: Requires AUTONOMOUS maturity (MODERATE).
    """
    # Placeholder: Will call AtomSaaSWebSocketClient.reconnect() from 61-03-websocket-updates
    logger.info(f"WebSocket reconnect triggered by {current_user.id}")

    return WebSocketReconnectResponse(
        message="WebSocket reconnection triggered",
        connected=False
    )


@router.post("/websocket/disable", response_model=WebSocketToggleResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="disable_websocket",
    feature="sync"
)
async def disable_websocket(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Disable WebSocket updates

    Disables real-time WebSocket updates from Atom SaaS.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    # Placeholder: Will call AtomSaaSWebSocketClient.disable() from 61-03-websocket-updates
    logger.info(f"WebSocket disabled by {current_user.id}")

    return WebSocketToggleResponse(
        message="WebSocket updates disabled",
        enabled=False
    )


@router.post("/websocket/enable", response_model=WebSocketToggleResponse)
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="enable_websocket",
    feature="sync"
)
async def enable_websocket(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Enable WebSocket updates

    Enables real-time WebSocket updates from Atom SaaS.

    **Governance**: Requires AUTONOMOUS maturity (MODERATE).
    """
    # Placeholder: Will call AtomSaaSWebSocketClient.enable() from 61-03-websocket-updates
    logger.info(f"WebSocket enabled by {current_user.id}")

    return WebSocketToggleResponse(
        message="WebSocket updates enabled",
        enabled=True
    )


# ============================================================================
# Conflict Resolution Endpoints
# ============================================================================

@router.get("/conflicts", response_model=List[ConflictListItem])
async def list_conflicts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status: resolved, unresolved"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List conflicts

    Returns paginated list of sync conflicts.
    """
    # Placeholder: Will query conflicts from 61-04-conflict-resolution
    return []


@router.get("/conflicts/{conflict_id}", response_model=ConflictDetail)
async def get_conflict_detail(
    conflict_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get conflict details

    Returns detailed conflict information with local and remote values.
    """
    # Placeholder: Will query conflict detail from 61-04-conflict-resolution
    raise router.not_found_error("Conflict", conflict_id)


@router.post("/conflicts/{conflict_id}/resolve", response_model=ResolveConflictResponse)
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="resolve_conflict",
    feature="sync"
)
async def resolve_conflict(
    conflict_id: str,
    strategy: str = Query(..., description="Resolution strategy: local_wins, remote_wins, merge"),
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Resolve conflict

    Resolves a specific conflict using the specified strategy.

    **Governance**: Requires AUTONOMOUS maturity (HIGH).
    """
    # Placeholder: Will call ConflictResolutionService.resolve() from 61-04-conflict-resolution
    logger.info(f"Conflict {conflict_id} resolved by {current_user.id} using strategy: {strategy}")

    return ResolveConflictResponse(
        message="Conflict resolved successfully",
        conflict_id=conflict_id
    )


@router.post("/conflicts/bulk-resolve", response_model=BulkResolveResponse)
@require_governance(
    action_complexity=ActionComplexity.CRITICAL,
    action_name="bulk_resolve_conflicts",
    feature="sync"
)
async def bulk_resolve_conflicts(
    conflict_ids: List[str],
    strategy: str = Query(..., description="Resolution strategy: local_wins, remote_wins, merge"),
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Bulk resolve conflicts

    Resolves multiple conflicts using the specified strategy.

    **Governance**: Requires AUTONOMOUS maturity (CRITICAL).
    """
    # Placeholder: Will call ConflictResolutionService.bulk_resolve() from 61-04-conflict-resolution
    logger.info(f"Bulk resolve {len(conflict_ids)} conflicts by {current_user.id} using strategy: {strategy}")

    return BulkResolveResponse(
        message=f"Bulk resolve completed",
        resolved_count=len(conflict_ids),
        failed_count=0,
        failed_ids=[]
    )

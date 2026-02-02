"""
Mobile Canvas API Routes

Mobile-optimized endpoints for canvas operations on mobile devices.
Includes push notification registration, offline sync, and mobile-friendly responses.
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import MobileDevice, OfflineAction, SyncState, User
from core.push_notification_service import PushNotificationService, get_push_notification_service
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mobile", tags=["mobile"])


# Request/Response Models
class RegisterDeviceRequest(BaseModel):
    device_token: str
    platform: str  # ios, android, web
    device_info: Optional[Dict[str, Any]] = None
    notification_enabled: bool = True
    notification_preferences: Optional[Dict[str, Any]] = None


class RegisterDeviceResponse(BaseModel):
    device_id: str
    status: str
    platform: str
    message: str


class QueueOfflineActionRequest(BaseModel):
    action_type: str
    action_data: Dict[str, Any]
    priority: int = 0


class QueueOfflineActionResponse(BaseModel):
    action_id: str
    status: str
    queued_at: str


class SyncStatusResponse(BaseModel):
    device_id: str
    last_sync_at: Optional[str]
    last_successful_sync_at: Optional[str]
    pending_actions_count: int
    total_syncs: int
    successful_syncs: int
    failed_syncs: int


class MobileCanvasListItem(BaseModel):
    canvas_id: str
    title: str
    agent_name: str
    status: str
    created_at: str
    updated_at: str
    component_count: int


class MobileCanvasListResponse(BaseModel):
    canvases: List[MobileCanvasListItem]
    total: int
    has_more: bool


# Routes


@router.post("/notifications/register", response_model=RegisterDeviceResponse)
async def register_device(
    request: RegisterDeviceRequest,
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Register a mobile device for push notifications.

    Args:
        request: Device registration details
        user_id: User ID (from auth token)

    Returns:
        Device registration result
    """
    try:
        push_service = get_push_notification_service(db)

        # Check if device already exists
        existing_device = db.query(MobileDevice).filter(
            MobileDevice.device_token == request.device_token
        ).first()

        if existing_device:
            # Update existing device
            existing_device.platform = request.platform
            existing_device.device_info = request.device_info or {}
            existing_device.notification_enabled = request.notification_enabled
            existing_device.notification_preferences = request.notification_preferences or {}
            existing_device.last_active = datetime.utcnow()
            existing_device.status = "active"
            db.commit()

            logger.info(f"Updated device {existing_device.id} for user {user_id}")

            return RegisterDeviceResponse(
                device_id=existing_device.id,
                status="updated",
                platform=request.platform,
                message="Device updated successfully"
            )
        else:
            # Register new device via push service
            result = await push_service.register_device(
                user_id=user_id,
                device_token=request.device_token,
                platform=request.platform,
                device_info=request.device_info
            )

            if result.get("status") in ["registered", "updated"]:
                # Update notification preferences
                device = db.query(MobileDevice).filter(
                    MobileDevice.device_token == request.device_token
                ).first()

                if device:
                    device.notification_enabled = request.notification_enabled
                    device.notification_preferences = request.notification_preferences or {}
                    db.commit()

                return RegisterDeviceResponse(
                    device_id=result["device_id"],
                    status=result["status"],
                    platform=request.platform,
                    message="Device registered successfully"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result.get("error", "Failed to register device")
                )

    except Exception as e:
        logger.error(f"Failed to register device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Device registration failed: {str(e)}"
        )


@router.post("/offline/queue", response_model=QueueOfflineActionResponse)
async def queue_offline_action(
    request: QueueOfflineActionRequest,
    user_id: str,
    device_id: str,
    db: Session = Depends(get_db)
):
    """
    Queue an action for later sync when device is offline.

    Args:
        request: Action to queue
        user_id: User ID
        device_id: Device ID

    Returns:
        Queued action details
    """
    try:
        # Verify device belongs to user
        device = db.query(MobileDevice).filter(
            MobileDevice.id == device_id,
            MobileDevice.user_id == user_id
        ).first()

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )

        # Create offline action
        action = OfflineAction(
            device_id=device_id,
            user_id=user_id,
            action_type=request.action_type,
            action_data=request.action_data,
            priority=request.priority,
            status="pending"
        )

        db.add(action)
        db.commit()

        # Update sync state
        sync_state = db.query(SyncState).filter(
            SyncState.device_id == device_id
        ).first()

        if sync_state:
            sync_state.pending_actions_count += 1
            db.commit()

        logger.info(f"Queued offline action {action.id} for device {device_id}")

        return QueueOfflineActionResponse(
            action_id=action.id,
            status="queued",
            queued_at=action.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue offline action: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue action: {str(e)}"
        )


@router.post("/sync/trigger")
async def trigger_sync(
    user_id: str,
    device_id: str,
    db: Session = Depends(get_db)
):
    """
    Trigger background sync for pending offline actions.

    Args:
        user_id: User ID
        device_id: Device ID

    Returns:
        Sync status
    """
    try:
        # Verify device belongs to user
        device = db.query(MobileDevice).filter(
            MobileDevice.id == device_id,
            MobileDevice.user_id == user_id
        ).first()

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )

        # Get pending actions
        pending_actions = db.query(OfflineAction).filter(
            OfflineAction.device_id == device_id,
            OfflineAction.status == "pending"
        ).order_by(OfflineAction.priority.desc(), OfflineAction.created_at).all()

        if not pending_actions:
            return {
                "status": "no_actions",
                "message": "No pending actions to sync",
                "synced_count": 0
            }

        # Process actions (in production, this would be a background task)
        synced_count = 0
        failed_count = 0

        for action in pending_actions:
            try:
                # Process action based on type
                if action.action_type == "agent_message":
                    # Send agent message
                    await ws_manager.broadcast(
                        f"user:{user_id}",
                        {
                            "type": "agent:message",
                            "data": action.action_data
                        }
                    )
                elif action.action_type == "workflow_trigger":
                    # Trigger workflow
                    await ws_manager.broadcast(
                        f"user:{user_id}",
                        {
                            "type": "workflow:trigger",
                            "data": action.action_data
                        }
                    )
                # Add more action types as needed

                # Mark as completed
                action.status = "completed"
                action.synced_at = datetime.utcnow()
                synced_count += 1

            except Exception as e:
                logger.error(f"Failed to sync action {action.id}: {e}")
                action.status = "failed"
                action.last_sync_error = str(e)
                action.sync_attempts += 1
                failed_count += 1

        db.commit()

        # Update sync state
        sync_state = db.query(SyncState).filter(
            SyncState.device_id == device_id
        ).first()

        if sync_state:
            sync_state.last_sync_at = datetime.utcnow()
            if synced_count > 0:
                sync_state.last_successful_sync_at = datetime.utcnow()
            sync_state.total_syncs += 1
            sync_state.successful_syncs += synced_count
            sync_state.failed_syncs += failed_count
            sync_state.pending_actions_count -= (synced_count + failed_count)
            db.commit()

        # Send push notification
        push_service = get_push_notification_service(db)
        await push_service.send_notification(
            user_id=user_id,
            notification_type="sync_complete",
            title=f"Sync Complete",
            body=f"Synced {synced_count} actions{f', {failed_count} failed' if failed_count > 0 else ''}",
            data={
                "synced_count": synced_count,
                "failed_count": failed_count
            },
            priority="normal"
        )

        return {
            "status": "success",
            "message": f"Synced {synced_count} actions",
            "synced_count": synced_count,
            "failed_count": failed_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    user_id: str,
    device_id: str,
    db: Session = Depends(get_db)
):
    """
    Get sync status for device.

    Args:
        user_id: User ID
        device_id: Device ID

    Returns:
        Sync status details
    """
    try:
        # Verify device belongs to user
        device = db.query(MobileDevice).filter(
            MobileDevice.id == device_id,
            MobileDevice.user_id == user_id
        ).first()

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )

        # Get sync state
        sync_state = db.query(SyncState).filter(
            SyncState.device_id == device_id
        ).first()

        if not sync_state:
            # Create sync state if it doesn't exist
            sync_state = SyncState(
                device_id=device_id,
                user_id=user_id
            )
            db.add(sync_state)
            db.commit()

        return SyncStatusResponse(
            device_id=device_id,
            last_sync_at=sync_state.last_sync_at.isoformat() if sync_state.last_sync_at else None,
            last_successful_sync_at=sync_state.last_successful_sync_at.isoformat() if sync_state.last_successful_sync_at else None,
            pending_actions_count=sync_state.pending_actions_count,
            total_syncs=sync_state.total_syncs,
            successful_syncs=sync_state.successful_syncs,
            failed_syncs=sync_state.failed_syncs
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}"
        )


@router.get("/canvas/list", response_model=MobileCanvasListResponse)
async def list_mobile_canvases(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get mobile-optimized list of user's canvases.

    Args:
        user_id: User ID
        limit: Max items per page
        offset: Pagination offset

    Returns:
        Mobile-optimized canvas list
    """
    try:
        # TODO: Implement canvas listing when CanvasSession model is available
        # For now, return empty list
        logger.info(f"Canvas listing requested by user {user_id} - not yet implemented")

        return MobileCanvasListResponse(
            canvases=[],
            total=0,
            has_more=False
        )

    except Exception as e:
        logger.error(f"Failed to list canvases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list canvases: {str(e)}"
        )


@router.delete("/notifications/unregister")
async def unregister_device(
    user_id: str,
    device_id: str,
    db: Session = Depends(get_db)
):
    """
    Unregister a device (disable push notifications).

    Args:
        user_id: User ID
        device_id: Device ID

    Returns:
        Unregister status
    """
    try:
        # Verify device belongs to user
        device = db.query(MobileDevice).filter(
            MobileDevice.id == device_id,
            MobileDevice.user_id == user_id
        ).first()

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found"
            )

        # Mark as inactive
        device.status = "inactive"
        device.notification_enabled = False
        device.last_active = datetime.utcnow()
        db.commit()

        logger.info(f"Unregistered device {device_id} for user {user_id}")

        return {
            "status": "success",
            "message": "Device unregistered successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unregister device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unregister device: {str(e)}"
        )


@router.get("/notifications/devices")
async def list_user_devices(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    List all registered devices for user.

    Args:
        user_id: User ID

    Returns:
        List of user's devices
    """
    try:
        devices = db.query(MobileDevice).filter(
            MobileDevice.user_id == user_id
        ).all()

        return {
            "devices": [
                {
                    "device_id": device.id,
                    "platform": device.platform,
                    "status": device.status,
                    "notification_enabled": device.notification_enabled,
                    "last_active": device.last_active.isoformat(),
                    "created_at": device.created_at.isoformat(),
                    "device_info": device.device_info
                }
                for device in devices
            ],
            "total": len(devices)
        }

    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list devices: {str(e)}"
        )

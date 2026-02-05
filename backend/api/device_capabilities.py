"""
Device Capabilities Routes

API endpoints for device hardware access and automation.

Governance Integration:
- Camera/Location/Notifications: INTERN+ maturity level
- Screen Recording: SUPERVISED+ maturity level
- Command Execution: AUTONOMOUS only (security critical)
- Full audit trail via device_audit table
- Agent execution tracking for all device sessions
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import AgentExecution, DeviceAudit, DeviceNode, DeviceSession, User
from core.security_dependencies import get_current_user
from tools.device_tool import (
    device_camera_snap,
    device_execute_command,
    device_get_location,
    device_screen_record_start,
    device_screen_record_stop,
    device_send_notification,
    get_device_info,
    list_devices,
)

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/devices", tags=["devices"])

# Feature flags
DEVICE_GOVERNANCE_ENABLED = os.getenv("DEVICE_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"


# ============================================================================
# Request/Response Models
# ============================================================================

class CameraSnapRequest(BaseModel):
    device_node_id: str
    camera_id: Optional[str] = None
    resolution: Optional[str] = "1920x1080"
    save_path: Optional[str] = None
    agent_id: Optional[str] = None


class ScreenRecordStartRequest(BaseModel):
    device_node_id: str
    duration_seconds: Optional[int] = None
    audio_enabled: bool = False
    resolution: Optional[str] = "1920x1080"
    output_format: str = "mp4"
    agent_id: Optional[str] = None


class ScreenRecordStopRequest(BaseModel):
    session_id: str


class GetLocationRequest(BaseModel):
    device_node_id: str
    accuracy: str = "high"
    agent_id: Optional[str] = None


class SendNotificationRequest(BaseModel):
    device_node_id: str
    title: str
    body: str
    icon: Optional[str] = None
    sound: Optional[str] = None
    agent_id: Optional[str] = None


class ExecuteCommandRequest(BaseModel):
    device_node_id: str
    command: str
    working_dir: Optional[str] = None
    timeout_seconds: int = 30
    environment: Optional[Dict[str, str]] = None
    agent_id: Optional[str] = None


class DeviceInfoResponse(BaseModel):
    id: str
    device_id: str
    name: str
    node_type: str
    status: str
    platform: Optional[str]
    capabilities: List[str]
    last_seen: Optional[str]


# ============================================================================
# Helper Functions
# ============================================================================

async def resolve_agent_for_request(
    db: Session,
    user_id: str,
    agent_id: Optional[str]
) -> Optional[str]:
    """
    Resolve the agent ID for a request using context if not provided.

    Args:
        db: Database session
        user_id: User making the request
        agent_id: Explicit agent ID (optional)

    Returns:
        Resolved agent ID or None
    """
    if agent_id:
        return agent_id

    # Use agent context resolver if no explicit agent
    try:
        resolver = AgentContextResolver(db)
        agent, _ = await resolver.resolve_agent_for_request(
            user_id=user_id,
            action_type="device_operation"
        )
        return agent.id if agent else None
    except Exception as e:
        logger.warning(f"Failed to resolve agent: {e}")
        return None


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/camera/snap", response_model=Dict[str, Any])
async def camera_snap(
    request: CameraSnapRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Capture an image from the device camera.

    Action Complexity: 2 (INTERN+)

    Args:
        request: Camera snap request with device_node_id, camera_id, resolution
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with success status and file path
    """
    try:
        # Resolve agent
        agent_id = await resolve_agent_for_request(
            db, current_user.id, request.agent_id
        )

        # Execute device action
        result = await device_camera_snap(
            db=db,
            user_id=current_user.id,
            device_node_id=request.device_node_id,
            agent_id=agent_id,
            camera_id=request.camera_id,
            resolution=request.resolution,
            save_path=request.save_path
        )

        if not result.get("success"):
            if result.get("governance_blocked"):
                raise router.permission_denied_error("camera_snap", "Device", details={"error": result.get("error")})
            raise router.error_response("CAMERA_SNAP_FAILED", result.get("error", "Camera snap failed"), status_code=400)

        return router.success_response(data=result, message="Camera snapshot captured successfully")

    except Exception as e:
        logger.error(f"Camera snap error: {e}")
        if "permission" in str(e).lower() or "governance" in str(e).lower():
            raise router.permission_denied_error("camera_snap", "Device", details={"error": str(e)})
        raise router.internal_error(f"Camera snap error: {str(e)}")


@router.post("/screen/record/start", response_model=Dict[str, Any])
async def screen_record_start(
    request: ScreenRecordStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a screen recording session.

    Action Complexity: 3 (SUPERVISED+)

    Args:
        request: Screen record request with device_node_id, duration, audio
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with session_id and recording details
    """
    try:
        # Resolve agent
        agent_id = await resolve_agent_for_request(
            db, current_user.id, request.agent_id
        )

        # Execute device action
        result = await device_screen_record_start(
            db=db,
            user_id=current_user.id,
            device_node_id=request.device_node_id,
            agent_id=agent_id,
            duration_seconds=request.duration_seconds,
            audio_enabled=request.audio_enabled,
            resolution=request.resolution,
            output_format=request.output_format
        )

        if not result.get("success"):
            if result.get("governance_blocked"):
                raise router.permission_denied_error("screen_record_start", "Device", details={"error": result.get("error")})
            raise router.error_response("SCREEN_RECORD_START_FAILED", result.get("error", "Screen record start failed"), status_code=400)

        return router.success_response(data=result, message="Screen recording started successfully")

    except Exception as e:
        logger.error(f"Screen record start error: {e}")
        if "permission" in str(e).lower() or "governance" in str(e).lower():
            raise router.permission_denied_error("screen_record_start", "Device", details={"error": str(e)})
        raise router.internal_error(f"Screen record start error: {str(e)}")


@router.post("/screen/record/stop", response_model=Dict[str, Any])
async def screen_record_stop(
    request: ScreenRecordStopRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stop a screen recording session.

    Action Complexity: 3 (SUPERVISED+)

    Args:
        request: Screen record stop request with session_id
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with file path and recording details
    """
    try:
        # Execute device action
        result = await device_screen_record_stop(
            db=db,
            user_id=current_user.id,
            session_id=request.session_id
        )

        if not result.get("success"):
            raise router.error_response("SCREEN_RECORD_STOP_FAILED", result.get("error", "Screen record stop failed"), status_code=400)

        return router.success_response(data=result, message="Screen recording stopped successfully")

    except Exception as e:
        logger.error(f"Screen record stop error: {e}")
        raise router.internal_error(f"Screen record stop error: {str(e)}")


@router.post("/location", response_model=Dict[str, Any])
async def get_location(
    request: GetLocationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the device's current location.

    Action Complexity: 2 (INTERN+)

    Args:
        request: Location request with device_node_id, accuracy
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with latitude, longitude, accuracy
    """
    try:
        # Resolve agent
        agent_id = await resolve_agent_for_request(
            db, current_user.id, request.agent_id
        )

        # Execute device action
        result = await device_get_location(
            db=db,
            user_id=current_user.id,
            device_node_id=request.device_node_id,
            agent_id=agent_id,
            accuracy=request.accuracy
        )

        if not result.get("success"):
            if result.get("governance_blocked"):
                raise router.permission_denied_error("get_location", "Device", details={"error": result.get("error")})
            raise router.error_response("GET_LOCATION_FAILED", result.get("error", "Get location failed"), status_code=400)

        return router.success_response(data=result, message="Location retrieved successfully")

    except Exception as e:
        logger.error(f"Get location error: {e}")
        if "permission" in str(e).lower() or "governance" in str(e).lower():
            raise router.permission_denied_error("get_location", "Device", details={"error": str(e)})
        raise router.internal_error(f"Get location error: {str(e)}")


@router.post("/notification", response_model=Dict[str, Any])
async def send_notification(
    request: SendNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a system notification to the device.

    Action Complexity: 2 (INTERN+)

    Args:
        request: Notification request with device_node_id, title, body
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with success status
    """
    try:
        # Resolve agent
        agent_id = await resolve_agent_for_request(
            db, current_user.id, request.agent_id
        )

        # Execute device action
        result = await device_send_notification(
            db=db,
            user_id=current_user.id,
            device_node_id=request.device_node_id,
            title=request.title,
            body=request.body,
            agent_id=agent_id,
            icon=request.icon,
            sound=request.sound
        )

        if not result.get("success"):
            if result.get("governance_blocked"):
                raise router.permission_denied_error("send_notification", "Device", details={"error": result.get("error")})
            raise router.error_response("SEND_NOTIFICATION_FAILED", result.get("error", "Send notification failed"), status_code=400)

        return router.success_response(data=result, message="Notification sent successfully")

    except Exception as e:
        logger.error(f"Send notification error: {e}")
        if "permission" in str(e).lower() or "governance" in str(e).lower():
            raise router.permission_denied_error("send_notification", "Device", details={"error": str(e)})
        raise router.internal_error(f"Send notification error: {str(e)}")


@router.post("/execute", response_model=Dict[str, Any])
async def execute_command(
    request: ExecuteCommandRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute a shell command on the device.

    Action Complexity: 4 (AUTONOMOUS only)

    SECURITY CRITICAL:
    - AUTONOMOUS agents only
    - Command whitelist enforced
    - Timeout enforced (max 300s)
    - Working directory restricted
    - No interactive shells

    Args:
        request: Command execution request with device_node_id, command
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with exit code, stdout, stderr
    """
    try:
        # Resolve agent
        agent_id = await resolve_agent_for_request(
            db, current_user.id, request.agent_id
        )

        if not agent_id:
            raise router.permission_denied_error(
                action="execute_command",
                resource="Device",
                details={"reason": "Command execution requires an AUTONOMOUS agent"}
            )

        # Verify agent is AUTONOMOUS
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent or agent.status != "autonomous":
            current_status = agent.status if agent else 'None'
            raise router.governance_denied_error(
                agent_id=agent_id if agent else "unknown",
                action="execute_command",
                maturity_level=current_status,
                required_level="AUTONOMOUS",
                reason=f"Command execution requires AUTONOMOUS agent. Current: {current_status}"
            )

        # Execute device action
        result = await device_execute_command(
            db=db,
            user_id=current_user.id,
            device_node_id=request.device_node_id,
            command=request.command,
            agent_id=agent_id,
            working_dir=request.working_dir,
            timeout_seconds=request.timeout_seconds,
            environment=request.environment
        )

        if not result.get("success"):
            if result.get("governance_blocked"):
                raise router.permission_denied_error("execute_command", "Device", details={"error": result.get("error")})
            raise router.error_response("EXECUTE_COMMAND_FAILED", result.get("error", "Command execution failed"), status_code=400)

        return router.success_response(data=result, message="Command executed successfully")

    except Exception as e:
        logger.error(f"Execute command error: {e}")
        if "permission" in str(e).lower() or "governance" in str(e).lower():
            raise router.permission_denied_error("execute_command", "Device", details={"error": str(e)})
        raise router.internal_error(f"Execute command error: {str(e)}")


@router.get("/{device_node_id}", response_model=DeviceInfoResponse)
async def get_device_info_endpoint(
    device_node_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get information about a device.

    Args:
        device_node_id: Device ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Device information
    """
    try:
        result = await get_device_info(db, device_node_id)

        if not result:
            raise router.not_found_error("Device", device_node_id)

        # Verify user owns the device
        device = db.query(DeviceNode).filter(
            DeviceNode.device_id == device_node_id
        ).first()

        if device.user_id != current_user.id:
            raise router.permission_denied_error(
                action="get_device_info",
                resource="Device",
                details={"device_id": device_node_id, "reason": "User does not own this device"}
            )

        return router.success_response(data=result, message="Device information retrieved")

    except Exception as e:
        logger.error(f"Get device info error: {e}")
        if "not found" in str(e).lower():
            raise router.not_found_error("Device", device_node_id)
        raise router.internal_error(f"Get device info error: {str(e)}")


@router.get("", response_model=List[DeviceInfoResponse])
async def list_devices_endpoint(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List devices available to the current user.

    Args:
        status: Filter by status (online, offline, busy)
        current_user: Authenticated user
        db: Database session

    Returns:
        List of devices
    """
    try:
        result = await list_devices(db, current_user.id, status)
        return result

    except Exception as e:
        logger.error(f"List devices error: {e}")
        raise router.internal_error(f"List devices error: {str(e)}")


@router.get("/{device_node_id}/audit", response_model=List[Dict[str, Any]])
async def get_device_audit(
    device_node_id: str,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get audit trail for a device.

    Args:
        device_node_id: Device ID
        limit: Maximum number of audit entries
        current_user: Authenticated user
        db: Database session

    Returns:
        List of audit entries
    """
    try:
        # Verify device exists and user owns it
        device = db.query(DeviceNode).filter(
            DeviceNode.device_id == device_node_id
        ).first()

        if not device:
            raise router.not_found_error("Device", device_node_id)

        if device.user_id != current_user.id:
            raise router.permission_denied_error(
                action="get_device_audit",
                resource="Device",
                details={"device_id": device_node_id, "reason": "User does not own this device"}
            )

        # Get audit entries
        audits = db.query(DeviceAudit).filter(
            DeviceAudit.device_node_id == device_node_id
        ).order_by(
            DeviceAudit.created_at.desc()
        ).limit(limit).all()

        return [
            {
                "id": audit.id,
                "action_type": audit.action_type,
                "success": audit.success,
                "result_summary": audit.result_summary,
                "error_message": audit.error_message,
                "file_path": audit.file_path,
                "duration_ms": audit.duration_ms,
                "created_at": audit.created_at.isoformat() if audit.created_at else None,
                "agent_id": audit.agent_id,
                "user_id": audit.user_id
            }
            for audit in audits
        ]

    except Exception as e:
        logger.error(f"Get device audit error: {e}")
        if "not found" in str(e).lower():
            raise router.not_found_error("Device", device_node_id)
        raise router.internal_error(f"Get device audit error: {str(e)}")


@router.get("/sessions/active", response_model=List[Dict[str, Any]])
async def get_active_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get active device sessions for the current user.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of active sessions
    """
    try:
        sessions = db.query(DeviceSession).filter(
            DeviceSession.user_id == current_user.id,
            DeviceSession.status == "active"
        ).all()

        return [
            {
                "session_id": session.session_id,
                "session_type": session.session_type,
                "device_node_id": session.device_node_id,
                "status": session.status,
                "configuration": session.configuration,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "agent_id": session.agent_id
            }
            for session in sessions
        ]

    except Exception as e:
        logger.error(f"Get active sessions error: {e}")
        raise router.internal_error(f"Get active sessions error: {str(e)}")

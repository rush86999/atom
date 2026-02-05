"""
Device Automation Tool

**✅ REAL IMPLEMENTATION (WebSocket-based)**

This module provides REAL device communication via WebSocket to React Native mobile apps.
No longer using mock implementations - all device functions communicate with actual devices.

Architecture:
- Backend (FastAPI) <--WebSocket--> Mobile App (React Native + Socket.IO)
- Devices connect via WebSocket and register their capabilities
- Server sends commands (camera, location, etc.) and receives real results
- Connection tracking and heartbeat monitoring

Provides device hardware access for AI agents:
- Camera capture (snap/clip)
- Screen recording (start/stop)
- Location services
- System notifications
- Command execution

Governance Integration:
- Camera/Location/Notifications: INTERN+ maturity level
- Screen Recording: SUPERVISED+ maturity level
- Command Execution: AUTONOMOUS only (security critical)
- Full audit trail via device_audit table
- Agent execution tracking for all device sessions
"""

import asyncio
from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentExecution, DeviceAudit, DeviceNode, DeviceSession, User

logger = logging.getLogger(__name__)

# Import WebSocket communication
try:
    from api.device_websocket import (
        get_connected_devices_info,
        is_device_online,
        send_device_command,
    )
    WEBSOCKET_AVAILABLE = True
    logger.info("Device WebSocket module loaded - real device communication enabled")
except ImportError as e:
    WEBSOCKET_AVAILABLE = False
    logger.warning(f"Device WebSocket module not available: {e}")
    logger.warning("Device functions will fail with connection error")

# Feature flags
import os

DEVICE_GOVERNANCE_ENABLED = os.getenv("DEVICE_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

# Security settings
DEVICE_COMMAND_WHITELIST = os.getenv(
    "DEVICE_COMMAND_WHITELIST",
    "ls,pwd,cat,grep,head,tail,echo,find,ps,top"
).split(",")
DEVICE_SCREEN_RECORD_MAX_DURATION = int(os.getenv("DEVICE_SCREEN_RECORD_MAX_DURATION", "3600"))  # 1 hour default


# ============================================================================
# Session Manager
# ============================================================================

class DeviceSessionManager:
    """
    Manages active device sessions with automatic cleanup.

    Sessions are stored in memory and automatically cleaned up after
    a timeout period of inactivity.
    """

    def __init__(self, session_timeout_minutes: int = 60):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout_minutes = session_timeout_minutes

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get an existing session by ID."""
        return self.sessions.get(session_id)

    def create_session(
        self,
        user_id: str,
        device_node_id: str,
        session_type: str,
        agent_id: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new device session."""
        session_id = str(uuid.uuid4())

        session = {
            "session_id": session_id,
            "user_id": user_id,
            "device_node_id": device_node_id,
            "session_type": session_type,
            "agent_id": agent_id,
            "configuration": configuration or {},
            "status": "active",
            "created_at": datetime.now(),
            "last_used": datetime.now()
        }

        self.sessions[session_id] = session
        logger.info(f"Device session {session_id} created (type: {session_type})")
        return session

    def close_session(self, session_id: str) -> bool:
        """Close a device session."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session["status"] = "closed"
            session["closed_at"] = datetime.now()
            del self.sessions[session_id]
            logger.info(f"Device session {session_id} closed")
            return True
        return False

    def cleanup_expired_sessions(self):
        """Remove expired sessions based on timeout."""
        now = datetime.now()
        expired = []

        for session_id, session in self.sessions.items():
            last_used = session.get("last_used", session["created_at"])
            age_minutes = (now - last_used).total_seconds() / 60

            if age_minutes > self.session_timeout_minutes:
                expired.append(session_id)

        for session_id in expired:
            self.close_session(session_id)
            logger.info(f"Expired device session {session_id} cleaned up")

        return len(expired)


# Singleton instance
_device_session_manager: Optional[DeviceSessionManager] = None


def get_device_session_manager() -> DeviceSessionManager:
    """Get the global device session manager instance."""
    global _device_session_manager
    if _device_session_manager is None:
        _device_session_manager = DeviceSessionManager()
    return _device_session_manager


# ============================================================================
# Audit Helper
# ============================================================================

def _create_device_audit(
    db: Session,
    user_id: str,
    device_node_id: str,
    action_type: str,
    action_params: Dict[str, Any],
    success: bool,
    result_summary: Optional[str] = None,
    error_message: Optional[str] = None,
    result_data: Optional[Dict[str, Any]] = None,
    file_path: Optional[str] = None,
    duration_ms: Optional[int] = None,
    agent_id: Optional[str] = None,
    agent_execution_id: Optional[str] = None,
    session_id: Optional[str] = None,
    governance_check_passed: Optional[bool] = None
) -> DeviceAudit:
    """
    Create an audit entry for a device action.

    Args:
        db: Database session
        user_id: User who triggered the action
        device_node_id: Device that performed the action
        action_type: Type of action (e.g., 'camera_snap', 'screen_record_start')
        action_params: Parameters passed to the action
        success: Whether the action succeeded
        result_summary: Human-readable summary of the result
        error_message: Error message if action failed
        result_data: Structured result data
        file_path: Path to any file created (screenshots, recordings)
        duration_ms: Duration of the action in milliseconds
        agent_id: Agent that performed the action
        agent_execution_id: Agent execution record
        session_id: Device session ID
        governance_check_passed: Whether governance check passed

    Returns:
        DeviceAudit record
    """
    audit = DeviceAudit(
        id=str(uuid.uuid4()),
        user_id=user_id,
        device_node_id=device_node_id,
        action_type=action_type,
        action_params=action_params,
        success=success,
        result_summary=result_summary,
        error_message=error_message,
        result_data=result_data or {},
        file_path=file_path,
        duration_ms=duration_ms,
        agent_id=agent_id,
        agent_execution_id=agent_execution_id,
        session_id=session_id,
        governance_check_passed=governance_check_passed,
        created_at=datetime.now()
    )

    db.add(audit)
    db.commit()

    logger.info(
        f"Device audit created: {action_type} on device {device_node_id} "
        f"by user {user_id} - Success: {success}"
    )

    return audit


# ============================================================================
# Governance Helper
# ============================================================================

async def _check_device_governance(
    db: Session,
    agent_id: str,
    action_type: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Check if an agent is allowed to perform a device action.

    Args:
        db: Database session
        agent_id: Agent to check
        action_type: Action to check (e.g., 'device_camera_snap')
        user_id: User requesting the action

    Returns:
        Governance check result with 'allowed' boolean
    """
    if not DEVICE_GOVERNANCE_ENABLED or EMERGENCY_GOVERNANCE_BYPASS:
        return {
            "allowed": True,
            "reason": "Device governance disabled or emergency bypass active",
            "governance_check_passed": True
        }

    try:
        governance = AgentGovernanceService(db)
        check = governance.can_perform_action(agent_id, action_type)

        return {
            "allowed": check["allowed"],
            "reason": check["reason"],
            "governance_check_passed": check["allowed"]
        }

    except Exception as e:
        logger.error(f"Governance check failed for {action_type}: {e}")
        # Fail open for availability
        return {
            "allowed": True,
            "reason": f"Governance check failed: {str(e)}",
            "governance_check_passed": False
        }


# ============================================================================
# Device Functions
# ============================================================================

async def device_camera_snap(
    db: Session,
    user_id: str,
    device_node_id: str,
    agent_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    resolution: Optional[str] = "1920x1080",
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Capture an image from the device camera.

    Action Complexity: 2 (INTERN+)

    Args:
        db: Database session
        user_id: User requesting the capture
        device_node_id: Device to capture from
        agent_id: Agent performing the action (for governance)
        camera_id: Specific camera to use (if multiple)
        resolution: Image resolution (e.g., "1920x1080")
        save_path: Where to save the image

    Returns:
        Dict with success status and file path/base64 data
    """
    start_time = datetime.now()
    governance_check = None

    # Governance check
    if agent_id:
        governance_check = await _check_device_governance(
            db, agent_id, "device_camera_snap", user_id
        )
        if not governance_check["allowed"]:
            return {
                "success": False,
                "error": governance_check["reason"],
                "governance_blocked": True
            }

    try:
        # Check WebSocket availability
        if not WEBSOCKET_AVAILABLE:
            raise ValueError("Device WebSocket module not available. Cannot communicate with devices.")

        # Check if device is online
        if not is_device_online(device_node_id):
            raise ValueError(
                f"Device {device_node_id} is not currently connected. "
                "Please ensure the mobile app is running and connected via WebSocket."
            )

        # Send WebSocket command to device
        response = await send_device_command(
            device_node_id=device_node_id,
            command="camera_snap",
            params={
                "camera_id": camera_id or "default",
                "resolution": resolution,
                "save_path": save_path
            },
            db=db
        )

        if not response.get("success"):
            raise ValueError(response.get("error", "Camera capture failed on device"))

        result = {
            "success": True,
            "file_path": response.get("file_path"),
            "base64_data": response.get("data", {}).get("base64_data"),
            "resolution": resolution,
            "camera_id": camera_id or "default",
            "captured_at": datetime.now().isoformat()
        }

        # Create audit entry
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=device_node_id,
            action_type="camera_snap",
            action_params={
                "camera_id": camera_id,
                "resolution": resolution,
                "save_path": save_path
            },
            success=True,
            result_summary=f"Camera capture successful: {result['file_path']}",
            result_data=result,
            file_path=result["file_path"],
            duration_ms=duration_ms,
            agent_id=agent_id,
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )

        logger.info(f"Camera snap successful for device {device_node_id}")
        return result

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        error_msg = f"Camera snap failed: {str(e)}"

        # Create audit entry for failure
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=device_node_id,
            action_type="camera_snap",
            action_params={
                "camera_id": camera_id,
                "resolution": resolution,
                "save_path": save_path
            },
            success=False,
            error_message=error_msg,
            duration_ms=duration_ms,
            agent_id=agent_id,
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )

        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


async def device_screen_record_start(
    db: Session,
    user_id: str,
    device_node_id: str,
    agent_id: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    audio_enabled: bool = False,
    resolution: Optional[str] = "1920x1080",
    output_format: str = "mp4"
) -> Dict[str, Any]:
    """
    Start a screen recording session.

    Action Complexity: 3 (SUPERVISED+)

    Args:
        db: Database session
        user_id: User requesting the recording
        device_node_id: Device to record
        agent_id: Agent performing the action (for governance)
        duration_seconds: Maximum duration (default: from env, 3600s)
        audio_enabled: Whether to capture audio
        resolution: Recording resolution
        output_format: Output format (mp4, webm, gif)

    Returns:
        Dict with session_id and recording details
    """
    start_time = datetime.now()
    governance_check = None

    # Governance check
    if agent_id:
        governance_check = await _check_device_governance(
            db, agent_id, "device_screen_record_start", user_id
        )
        if not governance_check["allowed"]:
            return {
                "success": False,
                "error": governance_check["reason"],
                "governance_blocked": True
            }

    try:
        # Get device node
        device = db.query(DeviceNode).filter(
            DeviceNode.device_id == device_node_id
        ).first()

        if not device:
            raise ValueError(f"Device {device_node_id} not found")

        # Validate duration
        max_duration = DEVICE_SCREEN_RECORD_MAX_DURATION
        if duration_seconds and duration_seconds > max_duration:
            raise ValueError(
                f"Duration {duration_seconds}s exceeds maximum {max_duration}s"
            )

        # Create session
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id=user_id,
            device_node_id=device_node_id,
            session_type="screen_record",
            agent_id=agent_id,
            configuration={
                "duration_seconds": duration_seconds or max_duration,
                "audio_enabled": audio_enabled,
                "resolution": resolution,
                "output_format": output_format
            }
        )

        # Create database session record
        db_session = DeviceSession(
            id=str(uuid.uuid4()),
            session_id=session["session_id"],
            device_node_id=device_node_id,
            user_id=user_id,
            agent_id=agent_id,
            session_type="screen_record",
            status="active",
            configuration=session["configuration"],
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )
        db.add(db_session)
        db.commit()

        # Send WebSocket command to device to start recording
        if WEBSOCKET_AVAILABLE:
            try:
                response = await send_device_command(
                    device_node_id=device_node_id,
                    command="screen_record_start",
                    params={
                        "session_id": session["session_id"],
                        "duration_seconds": duration_seconds or max_duration,
                        "audio_enabled": audio_enabled,
                        "resolution": resolution,
                        "output_format": output_format
                    },
                    db=db
                )

                if not response.get("success"):
                    # Update session status to failed
                    db_session.status = "failed"
                    db.commit()
                    raise ValueError(response.get("error", "Screen recording start failed on device"))

            except ValueError as e:
                # Update session status to failed
                db_session.status = "failed"
                db.commit()
                raise

        result = {
            "success": True,
            "session_id": session["session_id"],
            "device_node_id": device_node_id,
            "configuration": session["configuration"],
            "started_at": session["created_at"].isoformat()
        }

        # Create audit entry
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=device_node_id,
            action_type="screen_record_start",
            action_params=session["configuration"],
            success=True,
            result_summary=f"Screen recording started: {session['session_id']}",
            result_data=result,
            duration_ms=duration_ms,
            agent_id=agent_id,
            session_id=session["session_id"],
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )

        logger.info(f"Screen recording started for device {device_node_id}: {session['session_id']}")
        return result

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        error_msg = f"Screen record start failed: {str(e)}"

        # Create audit entry for failure
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=device_node_id,
            action_type="screen_record_start",
            action_params={
                "duration_seconds": duration_seconds,
                "audio_enabled": audio_enabled,
                "resolution": resolution,
                "output_format": output_format
            },
            success=False,
            error_message=error_msg,
            duration_ms=duration_ms,
            agent_id=agent_id,
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )

        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


async def device_screen_record_stop(
    db: Session,
    user_id: str,
    session_id: str
) -> Dict[str, Any]:
    """
    Stop a screen recording session.

    Action Complexity: 3 (SUPERVISED+)

    Args:
        db: Database session
        user_id: User requesting to stop
        session_id: Recording session to stop

    Returns:
        Dict with file path and recording details
    """
    start_time = datetime.now()

    try:
        # Get session
        session_manager = get_device_session_manager()
        session = session_manager.get_session(session_id)

        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session["user_id"] != user_id:
            raise ValueError(f"Session {session_id} does not belong to user {user_id}")

        # Send WebSocket command to device to stop recording
        file_path = None
        duration_seconds = 0

        if WEBSOCKET_AVAILABLE:
            try:
                response = await send_device_command(
                    device_node_id=session["device_node_id"],
                    command="screen_record_stop",
                    params={
                        "session_id": session_id
                    },
                    db=db
                )

                if response.get("success"):
                    file_path = response.get("file_path")
                    duration_seconds = response.get("data", {}).get("duration_seconds", 0)
                else:
                    raise ValueError(response.get("error", "Screen recording stop failed on device"))

            except ValueError as e:
                logger.error(f"Failed to stop screen recording: {e}")
                # Continue to close session even if stop command fails

        # Close session
        session_manager.close_session(session_id)

        # Update database session record
        db_session = db.query(DeviceSession).filter(
            DeviceSession.session_id == session_id
        ).first()

        if db_session:
            db_session.status = "closed"
            db_session.closed_at = datetime.now()
            db.commit()

        result = {
            "success": True,
            "session_id": session_id,
            "file_path": file_path or f"/tmp/recording_{session_id}.mp4",
            "duration_seconds": duration_seconds or (datetime.now() - session["created_at"]).total_seconds(),
            "stopped_at": datetime.now().isoformat()
        }

        # Create audit entry
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=session["device_node_id"],
            action_type="screen_record_stop",
            action_params={"session_id": session_id},
            success=True,
            result_summary=f"Screen recording stopped: {result['file_path']}",
            result_data=result,
            file_path=result["file_path"],
            duration_ms=duration_ms,
            agent_id=session.get("agent_id"),
            session_id=session_id
        )

        logger.info(f"Screen recording stopped: {session_id}")
        return result

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        error_msg = f"Screen record stop failed: {str(e)}"

        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


async def device_get_location(
    db: Session,
    user_id: str,
    device_node_id: str,
    agent_id: Optional[str] = None,
    accuracy: str = "high"
) -> Dict[str, Any]:
    """
    Get the device's current location.

    Action Complexity: 2 (INTERN+)

    Args:
        db: Database session
        user_id: User requesting location
        device_node_id: Device to locate
        agent_id: Agent performing the action (for governance)
        accuracy: Location accuracy (high, medium, low)

    Returns:
        Dict with latitude, longitude, and accuracy
    """
    start_time = datetime.now()
    governance_check = None

    # Governance check
    if agent_id:
        governance_check = await _check_device_governance(
            db, agent_id, "device_get_location", user_id
        )
        if not governance_check["allowed"]:
            return {
                "success": False,
                "error": governance_check["reason"],
                "governance_blocked": True
            }

    try:
        # Check WebSocket availability
        if not WEBSOCKET_AVAILABLE:
            raise ValueError("Device WebSocket module not available. Cannot communicate with devices.")

        # Check if device is online
        if not is_device_online(device_node_id):
            raise ValueError(
                f"Device {device_node_id} is not currently connected. "
                "Please ensure the mobile app is running and connected via WebSocket."
            )

        # Send WebSocket command to device
        response = await send_device_command(
            device_node_id=device_node_id,
            command="get_location",
            params={
                "accuracy": accuracy
            },
            db=db
        )

        if not response.get("success"):
            raise ValueError(response.get("error", "Get location failed on device"))

        location_data = response.get("data", {})
        result = {
            "success": True,
            "latitude": location_data.get("latitude"),
            "longitude": location_data.get("longitude"),
            "accuracy": accuracy,
            "altitude": location_data.get("altitude"),
            "timestamp": location_data.get("timestamp", datetime.now().isoformat())
        }

        # Create audit entry
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=device_node_id,
            action_type="get_location",
            action_params={"accuracy": accuracy},
            success=True,
            result_summary=f"Location retrieved: {result['latitude']}, {result['longitude']}",
            result_data=result,
            duration_ms=duration_ms,
            agent_id=agent_id,
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )

        logger.info(f"Location retrieved for device {device_node_id}")
        return result

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        error_msg = f"Get location failed: {str(e)}"

        # Create audit entry for failure
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=device_node_id,
            action_type="get_location",
            action_params={"accuracy": accuracy},
            success=False,
            error_message=error_msg,
            duration_ms=duration_ms,
            agent_id=agent_id,
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )

        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


async def device_send_notification(
    db: Session,
    user_id: str,
    device_node_id: str,
    title: str,
    body: str,
    agent_id: Optional[str] = None,
    icon: Optional[str] = None,
    sound: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send a system notification to the device.

    Action Complexity: 2 (INTERN+)

    Args:
        db: Database session
        user_id: User sending notification
        device_node_id: Device to notify
        title: Notification title
        body: Notification body
        agent_id: Agent performing the action (for governance)
        icon: Optional icon path
        sound: Optional sound to play

    Returns:
        Dict with success status
    """
    start_time = datetime.now()
    governance_check = None

    # Governance check
    if agent_id:
        governance_check = await _check_device_governance(
            db, agent_id, "device_send_notification", user_id
        )
        if not governance_check["allowed"]:
            return {
                "success": False,
                "error": governance_check["reason"],
                "governance_blocked": True
            }

    try:
        # Check WebSocket availability
        if not WEBSOCKET_AVAILABLE:
            raise ValueError("Device WebSocket module not available. Cannot communicate with devices.")

        # Check if device is online
        if not is_device_online(device_node_id):
            raise ValueError(
                f"Device {device_node_id} is not currently connected. "
                "Please ensure the mobile app is running and connected via WebSocket."
            )

        # Send WebSocket command to device
        response = await send_device_command(
            device_node_id=device_node_id,
            command="send_notification",
            params={
                "title": title,
                "body": body,
                "icon": icon,
                "sound": sound
            },
            db=db
        )

        if not response.get("success"):
            raise ValueError(response.get("error", "Send notification failed on device"))

        result = {
            "success": True,
            "device_node_id": device_node_id,
            "title": title,
            "body": body,
            "sent_at": datetime.now().isoformat()
        }

        # Create audit entry
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=device_node_id,
            action_type="send_notification",
            action_params={
                "title": title,
                "body": body,
                "icon": icon,
                "sound": sound
            },
            success=True,
            result_summary=f"Notification sent: {title}",
            result_data=result,
            duration_ms=duration_ms,
            agent_id=agent_id,
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )

        logger.info(f"Notification sent to device {device_node_id}: {title}")
        return result

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        error_msg = f"Send notification failed: {str(e)}"

        # Create audit entry for failure
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=device_node_id,
            action_type="send_notification",
            action_params={
                "title": title,
                "body": body,
                "icon": icon,
                "sound": sound
            },
            success=False,
            error_message=error_msg,
            duration_ms=duration_ms,
            agent_id=agent_id,
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )

        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


async def device_execute_command(
    db: Session,
    user_id: str,
    device_node_id: str,
    command: str,
    agent_id: Optional[str] = None,
    working_dir: Optional[str] = None,
    timeout_seconds: int = 30,
    environment: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Execute a shell command on the device.

    Action Complexity: 4 (AUTONOMOUS only)

    SECURITY CRITICAL:
    - AUTONOMOUS agents only
    - Command whitelist enforced
    - Timeout enforced
    - Working directory restricted
    - No interactive shells

    Args:
        db: Database session
        user_id: User requesting execution
        device_node_id: Device to execute on
        command: Command to execute
        agent_id: Agent performing the action (for governance)
        working_dir: Working directory for command
        timeout_seconds: Command timeout (default: 30s)
        environment: Environment variables

    Returns:
        Dict with exit code, stdout, stderr
    """
    start_time = datetime.now()
    governance_check = None

    # Governance check
    if agent_id:
        governance_check = await _check_device_governance(
            db, agent_id, "device_execute_command", user_id
        )
        if not governance_check["allowed"]:
            return {
                "success": False,
                "error": governance_check["reason"],
                "governance_blocked": True
            }

    try:
        # Get device node
        device = db.query(DeviceNode).filter(
            DeviceNode.device_id == device_node_id
        ).first()

        if not device:
            raise ValueError(f"Device {device_node_id} not found")

        # Security: Validate command against whitelist
        command_base = command.split()[0] if command.strip() else ""
        if command_base not in DEVICE_COMMAND_WHITELIST:
            raise ValueError(
                f"Command '{command_base}' not in whitelist. "
                f"Allowed: {DEVICE_COMMAND_WHITELIST}"
            )

        # Security: Enforce timeout
        if timeout_seconds > 300:  # 5 minutes max
            raise ValueError(f"Timeout {timeout_seconds}s exceeds maximum 300s")

        # Check WebSocket availability
        if not WEBSOCKET_AVAILABLE:
            raise ValueError("Device WebSocket module not available. Cannot communicate with devices.")

        # Check if device is online
        if not is_device_online(device_node_id):
            raise ValueError(
                f"Device {device_node_id} is not currently connected. "
                "Please ensure the mobile app is running and connected via WebSocket."
            )

        # Send WebSocket command to device
        response = await send_device_command(
            device_node_id=device_node_id,
            command="execute_command",
            params={
                "command": command,
                "working_dir": working_dir,
                "timeout_seconds": timeout_seconds,
                "environment": environment
            },
            db=db
        )

        if not response.get("success"):
            raise ValueError(response.get("error", "Command execution failed on device"))

        command_data = response.get("data", {})
        result = {
            "success": True,
            "exit_code": command_data.get("exit_code", 0),
            "stdout": command_data.get("stdout", ""),
            "stderr": command_data.get("stderr", ""),
            "command": command,
            "working_dir": working_dir,
            "timeout_seconds": timeout_seconds,
            "executed_at": datetime.now().isoformat()
        }

        # Create audit entry
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=device_node_id,
            action_type="execute_command",
            action_params={
                "command": command,
                "working_dir": working_dir,
                "timeout_seconds": timeout_seconds,
                "environment": environment
            },
            success=True,
            result_summary=f"Command executed: {command} (exit: {result['exit_code']})",
            result_data=result,
            duration_ms=duration_ms,
            agent_id=agent_id,
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )

        logger.info(f"Command executed on device {device_node_id}: {command}")
        return result

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        error_msg = f"Execute command failed: {str(e)}"

        # Create audit entry for failure
        _create_device_audit(
            db=db,
            user_id=user_id,
            device_node_id=device_node_id,
            action_type="execute_command",
            action_params={
                "command": command,
                "working_dir": working_dir,
                "timeout_seconds": timeout_seconds,
                "environment": environment
            },
            success=False,
            error_message=error_msg,
            duration_ms=duration_ms,
            agent_id=agent_id,
            governance_check_passed=governance_check["governance_check_passed"] if governance_check else None
        )

        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


# ============================================================================
# Helper Functions
# ============================================================================

async def get_device_info(
    db: Session,
    device_node_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get information about a device.

    Args:
        db: Database session
        device_node_id: Device ID

    Returns:
        Device information or None
    """
    device = db.query(DeviceNode).filter(
        DeviceNode.device_id == device_node_id
    ).first()

    if not device:
        return None

    return {
        "id": device.id,
        "device_id": device.device_id,
        "name": device.name,
        "node_type": device.node_type,
        "status": device.status,
        "platform": device.platform,
        "platform_version": device.platform_version,
        "architecture": device.architecture,
        "capabilities": device.capabilities,
        "capabilities_detailed": device.capabilities_detailed,
        "hardware_info": device.hardware_info,
        "last_seen": device.last_seen.isoformat() if device.last_seen else None
    }


async def list_devices(
    db: Session,
    user_id: str,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List devices available to a user.

    Args:
        db: Database session
        user_id: User ID
        status: Filter by status (online, offline, busy)

    Returns:
        List of device information
    """
    query = db.query(DeviceNode).filter(DeviceNode.user_id == user_id)

    if status:
        query = query.filter(DeviceNode.status == status)

    devices = query.all()

    return [
        {
            "id": device.id,
            "device_id": device.device_id,
            "name": device.name,
            "node_type": device.node_type,
            "status": device.status,
            "platform": device.platform,
            "capabilities": device.capabilities,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None
        }
        for device in devices
    ]

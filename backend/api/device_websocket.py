"""
Device WebSocket Server

**Real-time bidirectional communication with mobile devices**

This module implements a WebSocket server for communicating with React Native mobile apps.
It replaces the mock implementation in device_tool.py with actual device communication.

Architecture:
- Backend (FastAPI) <--WebSocket--> Mobile App (React Native + Socket.IO)
- Devices connect and register their capabilities
- Server sends commands (camera, location, etc.)
- Devices return results with data

Security:
- Authentication required for device connections
- Device registration and verification
- Governance checks on all commands

Usage:
1. Mobile app connects with auth token
2. Device registers with capabilities
3. Server sends commands via WebSocket
4. Device executes and returns results
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from fastapi import Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from core.auth import decode_token
from core.database import SessionLocal, get_db
from core.models import DeviceNode, DeviceSession, User

logger = logging.getLogger(__name__)

# Feature flags
DEVICE_WEBSOCKET_ENABLED = True
DEVICE_HEARTBEAT_INTERVAL = 30  # seconds
DEVICE_CONNECTION_TIMEOUT = 300  # seconds (5 minutes)


# ============================================================================
# Connection Manager
# ============================================================================

class DeviceConnectionManager:
    """
    Manages active WebSocket connections to mobile devices.

    Provides:
    - Connection tracking by device_id
    - Broadcasting capabilities
    - Sending commands to devices
    - Handling disconnections and cleanup
    """

    def __init__(self):
        # Map: device_node_id -> WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

        # Map: device_node_id -> device info
        self.device_info: Dict[str, Dict[str, Any]] = {}

        # Map: user_id -> set of device_node_ids
        self.user_devices: Dict[str, Set[str]] = {}

        # Pending commands: device_node_id -> list of pending commands
        self.pending_commands: Dict[str, List[Dict[str, Any]]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        device_node_id: str,
        user_id: str,
        device_info: Dict[str, Any]
    ):
        """Register a new device connection."""
        await websocket.accept()

        self.active_connections[device_node_id] = websocket
        self.device_info[device_node_id] = device_info

        if user_id not in self.user_devices:
            self.user_devices[user_id] = set()
        self.user_devices[user_id].add(device_node_id)

        if device_node_id not in self.pending_commands:
            self.pending_commands[device_node_id] = []

        logger.info(
            f"Device {device_node_id} connected for user {user_id} "
            f"(capabilities: {device_info.get('capabilities', [])})"
        )

        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "device_node_id": device_node_id,
            "server_time": datetime.now().isoformat(),
            "heartbeat_interval": DEVICE_HEARTBEAT_INTERVAL
        })

    def disconnect(self, device_node_id: str, user_id: str):
        """Remove a device connection."""
        if device_node_id in self.active_connections:
            del self.active_connections[device_node_id]

        if device_node_id in self.device_info:
            del self.device_info[device_node_id]

        if device_node_id in self.pending_commands:
            del self.pending_commands[device_node_id]

        if user_id in self.user_devices and device_node_id in self.user_devices[user_id]:
            self.user_devices[user_id].discard(device_node_id)

        logger.info(f"Device {device_node_id} disconnected")

    async def send_command(
        self,
        device_node_id: str,
        command: str,
        params: Dict[str, Any],
        command_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a command to a device and wait for response.

        Args:
            device_node_id: Target device ID
            command: Command type (camera_snap, get_location, etc.)
            params: Command parameters
            command_id: Optional command ID (generated if not provided)

        Returns:
            Response from device

        Raises:
            ValueError: If device not connected
            TimeoutError: If device doesn't respond
        """
        if device_node_id not in self.active_connections:
            raise ValueError(f"Device {device_node_id} not connected")

        websocket = self.active_connections[device_node_id]

        # Generate command ID if not provided
        if not command_id:
            command_id = str(uuid.uuid4())

        # Create command message
        message = {
            "type": "command",
            "command_id": command_id,
            "command": command,
            "params": params,
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Send command
            await websocket.send_json(message)
            logger.info(f"Command {command} sent to device {device_node_id} (id: {command_id})")

            # Wait for response (with timeout)
            response = await websocket.receive_json(timeout=30)

            if response.get("command_id") != command_id:
                raise ValueError(f"Command ID mismatch: expected {command_id}, got {response.get('command_id')}")

            return response

        except WebSocketDisconnect:
            self.disconnect(device_node_id, self.device_info.get(device_node_id, {}).get("user_id", "unknown"))
            raise ValueError(f"Device {device_node_id} disconnected during command")

        except Exception as e:
            logger.error(f"Error sending command to device {device_node_id}: {e}")
            raise

    async def broadcast_to_user_devices(
        self,
        user_id: str,
        message: Dict[str, Any]
    ):
        """Send a message to all devices belonging to a user."""
        if user_id not in self.user_devices:
            return

        for device_node_id in self.user_devices[user_id]:
            if device_node_id in self.active_connections:
                try:
                    await self.active_connections[device_node_id].send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to device {device_node_id}: {e}")

    def is_device_connected(self, device_node_id: str) -> bool:
        """Check if a device is currently connected."""
        return device_node_id in self.active_connections

    def get_device_info(self, device_node_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a connected device."""
        return self.device_info.get(device_node_id)

    def get_user_devices(self, user_id: str) -> List[str]:
        """Get all device IDs for a user."""
        if user_id not in self.user_devices:
            return []
        return list(self.user_devices[user_id])

    def get_all_connected_devices(self) -> List[Dict[str, Any]]:
        """Get information about all connected devices."""
        return [
            {
                "device_node_id": device_id,
                **info
            }
            for device_id, info in self.device_info.items()
        ]


# Singleton instance
_device_connection_manager: Optional[DeviceConnectionManager] = None


def get_device_connection_manager() -> DeviceConnectionManager:
    """Get the global device connection manager instance."""
    global _device_connection_manager
    if _device_connection_manager is None:
        _device_connection_manager = DeviceConnectionManager()
    return _device_connection_manager


# ============================================================================
# WebSocket Endpoint
# ============================================================================

async def websocket_device_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket endpoint for device connections.

    Mobile devices connect to this endpoint to receive commands and send results.

    Connection Flow:
    1. Client connects with ?token=JWT_TOKEN
    2. Server validates token and gets user
    3. Client sends register message with device info
    4. Server registers device and sends confirmation
    5. Client listens for commands, executes, sends results
    6. Heartbeat messages every 30 seconds

    Message Types:
    - register: Client registers device
    - command: Server sends command to device
    - result: Device sends command result
    - heartbeat: Keep-alive messages
    - error: Error messages
    """
    if not DEVICE_WEBSOCKET_ENABLED:
        await websocket.close(code=1003, reason="Device WebSocket disabled")
        return

    manager = get_device_connection_manager()
    user: Optional[User] = None
    device_node_id: Optional[str] = None

    # Use context manager for WebSocket endpoint
    with SessionLocal() as db:
        try:
            # Authenticate user from token
            payload = decode_token(token)
            user_id = payload.get("sub")

            if not user_id:
                await websocket.close(code=1008, reason="Invalid token")
                return

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                await websocket.close(code=1008, reason="User not found")
                return

            # Accept connection
            await websocket.accept()

            # Wait for device registration
            try:
                register_msg = await websocket.receive_json(timeout=10)
            except Exception as e:
                await websocket.close(code=1008, reason="Registration timeout")
                return

            if register_msg.get("type") != "register":
                await websocket.close(code=1002, reason="Expected register message")
                return

            # Extract device info
            device_node_id = register_msg.get("device_node_id")
            if not device_node_id:
                await websocket.close(code=1002, reason="device_node_id required")
                return

            device_info = register_msg.get("device_info", {})
            device_info["user_id"] = user_id

            # Get or create device node in database
            device = db.query(DeviceNode).filter(
                DeviceNode.device_id == device_node_id
            ).first()

            if device:
                # Update existing device
                device.status = "online"
                device.last_seen = datetime.now()
                device.capabilities = device_info.get("capabilities", [])
                device.platform = device_info.get("platform")
                device.platform_version = device_info.get("platform_version")
                device.hardware_info = device_info.get("hardware_info", {})
            else:
                # Create new device
                device = DeviceNode(
                    id=str(uuid.uuid4()),
                    device_id=device_node_id,
                    user_id=user_id,
                    name=device_info.get("name", f"Device {device_node_id[:8]}"),
                    node_type=device_info.get("node_type", "mobile"),
                    status="online",
                    platform=device_info.get("platform"),
                    platform_version=device_info.get("platform_version"),
                    architecture=device_info.get("architecture"),
                    capabilities=device_info.get("capabilities", []),
                    capabilities_detailed=device_info.get("capabilities_detailed", {}),
                    hardware_info=device_info.get("hardware_info", {}),
                    last_seen=datetime.now()
                )
                db.add(device)

            db.commit()

            # Register connection
            await manager.connect(websocket, device_node_id, user_id, device_info)

            # Send registration confirmation
            await websocket.send_json({
                "type": "registered",
                "device_node_id": device_node_id,
                "registered_at": datetime.now().isoformat()
            })

            # Message loop
            last_heartbeat = datetime.now()

            while True:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=DEVICE_HEARTBEAT_INTERVAL
                    )

                    msg_type = message.get("type")

                    if msg_type == "result":
                        # Command result from device
                        logger.debug(f"Received result from device {device_node_id}: {message.get('command_id')}")
                        # Result is handled by the waiting command in send_command

                    elif msg_type == "heartbeat":
                        # Update heartbeat
                        last_heartbeat = datetime.now()
                        await websocket.send_json({
                            "type": "heartbeat_ack",
                            "timestamp": datetime.now().isoformat()
                        })

                        # Update device last_seen in database
                        device = db.query(DeviceNode).filter(
                            DeviceNode.device_id == device_node_id
                        ).first()
                        if device:
                            device.last_seen = datetime.now()
                            db.commit()

                    elif msg_type == "error":
                        # Error from device
                        logger.error(f"Device {device_node_id} error: {message.get('error')}")

                    else:
                        logger.warning(f"Unknown message type from device {device_node_id}: {msg_type}")

                except asyncio.TimeoutError:
                    # Heartbeat timeout - check if device should be disconnected
                    age = (datetime.now() - last_heartbeat).total_seconds()
                    if age > DEVICE_CONNECTION_TIMEOUT:
                        logger.warning(f"Device {device_node_id} heartbeat timeout after {age}s")
                        break

                    # Send heartbeat probe
                    try:
                        await websocket.send_json({
                            "type": "heartbeat_probe",
                            "timestamp": datetime.now().isoformat()
                        })
                    except Exception as e:
                        logger.debug(f"Heartbeat failed for device {device_node_id}: {e}")
                        break

        except WebSocketDisconnect:
            logger.info(f"Device {device_node_id} disconnected")

        except Exception as e:
            logger.error(f"WebSocket error for device {device_node_id}: {e}")

        finally:
            # Cleanup
            if device_node_id and user:
                manager.disconnect(device_node_id, user_id)

                # Update device status in database
                device = db.query(DeviceNode).filter(
                    DeviceNode.device_id == device_node_id
                ).first()
                if device:
                    device.status = "offline"
                    db.commit()


# ============================================================================
# Helper Functions for Device Tool
# ============================================================================

async def send_device_command(
    device_node_id: str,
    command: str,
    params: Dict[str, Any],
    db: Session
) -> Dict[str, Any]:
    """
    Send a command to a device via WebSocket.

    This is the main interface used by device_tool.py functions.

    Args:
        device_node_id: Target device ID
        command: Command type (camera_snap, get_location, etc.)
        params: Command parameters
        db: Database session

    Returns:
        Command result from device

    Raises:
        ValueError: If device not connected
        Exception: If command fails
    """
    manager = get_device_connection_manager()

    # Check if device is connected
    if not manager.is_device_connected(device_node_id):
        # Check if device exists in database
        device = db.query(DeviceNode).filter(
            DeviceNode.device_id == device_node_id
        ).first()

        if device:
            raise ValueError(
                f"Device {device_node_id} is not connected. "
                f"Current status: {device.status}. "
                f"Please ensure the mobile app is running and connected."
            )
        else:
            raise ValueError(f"Device {device_node_id} not found in database")

    # Send command and wait for response
    try:
        response = await manager.send_command(device_node_id, command, params)

        # Check if command was successful
        if response.get("type") == "result":
            if response.get("success"):
                return {
                    "success": True,
                    "data": response.get("data"),
                    "file_path": response.get("file_path"),
                    "result": response
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Command failed"),
                    "result": response
                }
        elif response.get("type") == "error":
            return {
                "success": False,
                "error": response.get("error", "Unknown error"),
                "result": response
            }
        else:
            return {
                "success": False,
                "error": f"Unexpected response type: {response.get('type')}",
                "result": response
            }

    except ValueError as e:
        raise
    except Exception as e:
        logger.error(f"Error sending command to device {device_node_id}: {e}")
        raise


def get_connected_devices_info() -> List[Dict[str, Any]]:
    """Get information about all currently connected devices."""
    manager = get_device_connection_manager()
    return manager.get_all_connected_devices()


def is_device_online(device_node_id: str) -> bool:
    """Check if a device is currently online and connected."""
    manager = get_device_connection_manager()
    return manager.is_device_connected(device_node_id)

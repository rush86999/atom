
from typing import Dict, List, Set, Any
from fastapi import WebSocket
import json
import logging
import asyncio
from datetime import datetime
from core.auth import get_current_user_ws
from core.database import SessionLocal

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Map channel_id -> List of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Map user_id -> List of WebSockets (for direct user targeting)
        self.user_connections: Dict[str, List[WebSocket]] = {}

        # Message types for streaming
        self.STREAMING_UPDATE = "streaming:update"
        self.STREAMING_ERROR = "streaming:error"
        self.STREAMING_COMPLETE = "streaming:complete"

        # Canvas event types
        self.CANVAS_PRESENT = "canvas:present"
        self.CANVAS_UPDATE = "canvas:update"
        self.CANVAS_CLOSE = "canvas:close"
        self.CANVAS_DELETE = "canvas:delete"
        self.CANVAS_EXECUTE = "canvas:execute"

        # Device event types
        self.DEVICE_REGISTERED = "device:registered"
        self.DEVICE_COMMAND = "device:command"
        self.DEVICE_CAMERA_READY = "device:camera:ready"
        self.DEVICE_RECORDING_COMPLETE = "device:recording:complete"
        self.DEVICE_LOCATION_UPDATE = "device:location:update"
        self.DEVICE_NOTIFICATION_SENT = "device:notification:sent"
        self.DEVICE_COMMAND_OUTPUT = "device:command:output"
        self.DEVICE_SESSION_CREATED = "device:session:created"
        self.DEVICE_SESSION_CLOSED = "device:session:closed"
        self.DEVICE_AUDIT_LOG = "device:audit:log"

    async def connect(self, websocket: WebSocket, token: str):
        await websocket.accept()
        
        # Authenticate
        db = SessionLocal()
        try:
            # Allow dev bypass
            if token == "dev-token":
                # Create a mock user for dev
                class MockUser:
                    id = "dev-user"
                    email = "dev@local.host"
                    teams = []
                    workspace_id = "default"
                user = MockUser()
            else:
                user = await get_current_user_ws(token, db)
            
            if not user:
                await websocket.close(code=4001) # Unauthorized
                return None
            
            user_id = user.id
            
            # Register user connection
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(websocket)
            
            # Auto-subscribe to User Channel
            self.subscribe(websocket, f"user:{user_id}")
            
            # Auto-subscribe to Team Channels
            for team in user.teams:
                self.subscribe(websocket, f"team:{team.id}")
                
            # Auto-subscribe to Workspace Channel
            if user.workspace_id:
                self.subscribe(websocket, f"workspace:{user.workspace_id}")
                
            logger.info(f"User {user.email} connected via WebSocket")
            return user
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            try:
                await websocket.close()
            except RuntimeError:
                # Connection might be already closed or in a state where close() is invalid
                pass
            return None
        finally:
            db.close()

    def disconnect(self, websocket: WebSocket, user_id: str):
        # Remove from user connections
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
                
        # Remove from all channels
        for channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)

    def subscribe(self, websocket: WebSocket, channel: str):
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        if websocket not in self.active_connections[channel]:
            self.active_connections[channel].append(websocket)

    def unsubscribe(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)

    async def broadcast(self, channel: str, message: dict):
        if channel in self.active_connections:
            # Create a copy to avoid modification during iteration
            connections = self.active_connections[channel][:]
            logger.info(f"[WS-DEBUG] Broadcasting to '{channel}' ({len(connections)} clients): {str(message)[:200]}...")
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {channel}: {e}")
        else:
             logger.warning(f"[WS-DEBUG] Attempted broadcast to EMPTY channel: '{channel}'. Msg: {str(message)[:50]}...")
                    # Cleanup dead connection?
                    
    async def broadcast_event(self, channel: str, event_type: str, data: Any):
        """Standardized event broadcasting"""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(channel, message)

    async def send_personal_message(self, user_id: str, message: dict):
        if user_id in self.user_connections:
            connections = self.user_connections[user_id][:]
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending personal message to {user_id}: {e}")

    def get_stats(self):
        return {
            "active_channels": len(self.active_connections),
            "connected_users": len(self.user_connections),
            "channels": {k: len(v) for k, v in self.active_connections.items()}
        }

    # ========================================================================
    # Device Event Broadcasting Methods
    # ========================================================================

    async def broadcast_device_registered(self, user_id: str, device_data: Dict[str, Any]):
        """Broadcast when a device is registered"""
        await self.broadcast_event(
            f"user:{user_id}",
            self.DEVICE_REGISTERED,
            device_data
        )

    async def broadcast_device_command(self, user_id: str, command_data: Dict[str, Any]):
        """Broadcast when a command is sent to a device"""
        await self.broadcast_event(
            f"user:{user_id}",
            self.DEVICE_COMMAND,
            command_data
        )

    async def broadcast_device_camera_ready(self, user_id: str, camera_data: Dict[str, Any]):
        """Broadcast when camera capture is ready"""
        await self.broadcast_event(
            f"user:{user_id}",
            self.DEVICE_CAMERA_READY,
            camera_data
        )

    async def broadcast_device_recording_complete(self, user_id: str, recording_data: Dict[str, Any]):
        """Broadcast when screen recording is complete"""
        await self.broadcast_event(
            f"user:{user_id}",
            self.DEVICE_RECORDING_COMPLETE,
            recording_data
        )

    async def broadcast_device_location_update(self, user_id: str, location_data: Dict[str, Any]):
        """Broadcast when location is retrieved"""
        await self.broadcast_event(
            f"user:{user_id}",
            self.DEVICE_LOCATION_UPDATE,
            location_data
        )

    async def broadcast_device_notification_sent(self, user_id: str, notification_data: Dict[str, Any]):
        """Broadcast when notification is sent"""
        await self.broadcast_event(
            f"user:{user_id}",
            self.DEVICE_NOTIFICATION_SENT,
            notification_data
        )

    async def broadcast_device_command_output(self, user_id: str, output_data: Dict[str, Any]):
        """Broadcast when command output is available"""
        await self.broadcast_event(
            f"user:{user_id}",
            self.DEVICE_COMMAND_OUTPUT,
            output_data
        )

    async def broadcast_device_session_created(self, user_id: str, session_data: Dict[str, Any]):
        """Broadcast when a device session is created"""
        await self.broadcast_event(
            f"user:{user_id}",
            self.DEVICE_SESSION_CREATED,
            session_data
        )

    async def broadcast_device_session_closed(self, user_id: str, session_data: Dict[str, Any]):
        """Broadcast when a device session is closed"""
        await self.broadcast_event(
            f"user:{user_id}",
            self.DEVICE_SESSION_CLOSED,
            session_data
        )

    async def broadcast_device_audit_log(self, user_id: str, audit_data: Dict[str, Any]):
        """Broadcast when a device audit log is created"""
        await self.broadcast_event(
            f"user:{user_id}",
            self.DEVICE_AUDIT_LOG,
            audit_data
        )

manager = ConnectionManager()

def get_connection_manager():
    """Get the global connection manager instance."""
    return manager

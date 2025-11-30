"""
WebSocket Connection Manager for Real-time Updates
Handles WebSocket connections and broadcasts workflow/system events
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections and message broadcasting"""
    
    def __init__(self):
        # All active connections
        self.active_connections: List[WebSocket] = []
        
        # Connections subscribed to specific channels
        self.channel_subscriptions: Dict[str, Set[WebSocket]] = {}
        
        # User sessions (websocket -> user_id mapping)
        self.user_sessions: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str = "anonymous"):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_sessions[websocket] = user_id
        logger.info(f"WebSocket connected: user={user_id}, total_connections={len(self.active_connections)}")
        
        # Send welcome message
        await self.send_personal_message({
            "type": "connection_established",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "message": "Connected to ATOM real-time updates"
        }, websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        user_id = self.user_sessions.get(websocket, "unknown")
        self.active_connections.remove(websocket)
        
        # Remove from all channel subscriptions
        for channel_subs in self.channel_subscriptions.values():
            channel_subs.discard(websocket)
        
        # Remove user session
        if websocket in self.user_sessions:
            del self.user_sessions[websocket]
        
        logger.info(f"WebSocket disconnected: user={user_id}, remaining={len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {str(e)}")
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {str(e)}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def subscribe_to_channel(self, websocket: WebSocket, channel: str):
        """Subscribe a client to a specific channel"""
        if channel not in self.channel_subscriptions:
            self.channel_subscriptions[channel] = set()
        
        self.channel_subscriptions[channel].add(websocket)
        
        await self.send_personal_message({
            "type": "subscribed",
            "channel": channel,
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        logger.info(f"User subscribed to channel: {channel}")
    
    async def unsubscribe_from_channel(self, websocket: WebSocket, channel: str):
        """Unsubscribe a client from a channel"""
        if channel in self.channel_subscriptions:
            self.channel_subscriptions[channel].discard(websocket)
        
        await self.send_personal_message({
            "type": "unsubscribed",
            "channel": channel,
            "timestamp": datetime.now().isoformat()
        }, websocket)
    
    async def broadcast_to_channel(self, channel: str, message: dict):
        """Broadcast a message to all subscribers of a channel"""
        if channel not in self.channel_subscriptions:
            return
        
        disconnected = []
        subscribers = self.channel_subscriptions[channel].copy()
        
        for connection in subscribers:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to channel {channel}: {str(e)}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    def get_stats(self) -> dict:
        """Get statistics about current connections"""
        return {
            "total_connections": len(self.active_connections),
            "channels": {
                channel: len(subs)
                for channel, subs in self.channel_subscriptions.items()
            },
            "active_users": len(set(self.user_sessions.values()))
        }


# Event types for workflow updates
class WorkflowEventType:
    STARTED = "workflow.started"
    STEP_COMPLETED = "workflow.step_completed"
    PAUSED = "workflow.paused"
    RESUMED = "workflow.resumed"
    COMPLETED = "workflow.completed"
    FAILED = "workflow.failed"
    PROGRESS_UPDATE = "workflow.progress"


# Global connection manager instance
manager = ConnectionManager()


# Helper functions to broadcast workflow events
async def broadcast_workflow_event(
    execution_id: str,
    event_type: str,
    data: dict
):
    """Broadcast a workflow execution event"""
    message = {
        "type": event_type,
        "execution_id": execution_id,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    # Broadcast to workflow-specific channel
    channel = f"workflow:{execution_id}"
    await manager.broadcast_to_channel(channel, message)
    
    # Also broadcast to general workflows channel
    await manager.broadcast_to_channel("workflows", message)


async def broadcast_system_event(event_type: str, data: dict):
    """Broadcast a system-level event (health, alerts, etc.)"""
    message = {
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    await manager.broadcast_to_channel("system", message)

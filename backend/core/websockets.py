"""
WebSocket Manager

Handles real-time communication with the frontend.
Manages active connections and broadcasts events.
"""

from fastapi import WebSocket
from typing import List, Dict, Any
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Map user_id to list of active websockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket")
        
    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected")
        
    async def send_personal_message(self, message: Dict[str, Any], user_id: str):
        """Send a message to a specific user"""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending WebSocket message to {user_id}: {e}")
                    # Cleanup dead connection
                    self.disconnect(connection, user_id)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected users"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)
            
    async def notify_workflow_status(self, user_id: str, execution_id: str, status: str, details: Dict[str, Any] = None):
        """Helper to send workflow status updates"""
        message = {
            "type": "workflow_status_update",
            "execution_id": execution_id,
            "status": status,
            "timestamp": details.get("timestamp") if details else None,
            "details": details or {}
        }
        await self.send_personal_message(message, user_id)

# Global instance
_manager = None

def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager

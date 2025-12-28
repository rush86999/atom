
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

    async def connect(self, websocket: WebSocket, token: str):
        await websocket.accept()
        
        # Authenticate
        db = SessionLocal()
        try:
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
            await websocket.close()
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
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {channel}: {e}")
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

manager = ConnectionManager()

def get_connection_manager():
    """Get the global connection manager instance."""
    return manager

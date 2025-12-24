import logging
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages active WebSocket connections per workspace.
    """
    def __init__(self):
        # Map workspace_id -> List[WebSocket]
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, workspace_id: str):
        await websocket.accept()
        if workspace_id not in self.active_connections:
            self.active_connections[workspace_id] = []
        self.active_connections[workspace_id].append(websocket)
        logger.info(f"WebSocket connected for workspace {workspace_id}. Total: {len(self.active_connections[workspace_id])}")

    def disconnect(self, websocket: WebSocket, workspace_id: str):
        if workspace_id in self.active_connections:
            if websocket in self.active_connections[workspace_id]:
                self.active_connections[workspace_id].remove(websocket)
                if not self.active_connections[workspace_id]:
                    del self.active_connections[workspace_id]
        logger.info(f"WebSocket disconnected for workspace {workspace_id}")

    async def broadcast(self, message: Dict[str, Any], workspace_id: str):
        """
        Sends a message to all connected clients in a workspace.
        """
        if workspace_id not in self.active_connections:
            return
            
        connections = self.active_connections[workspace_id]
        to_remove = []
        
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to socket: {e}")
                to_remove.append(connection)
        
        # Cleanup broken connections
        for dead_conn in to_remove:
            self.disconnect(dead_conn, workspace_id)

# Singleton
notification_manager = ConnectionManager()

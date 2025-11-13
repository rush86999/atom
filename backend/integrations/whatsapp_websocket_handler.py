
# WhatsApp WebSocket Handler
import asyncio
import json
import logging
from typing import Dict, Set, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class WhatsAppWebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        logger.info(f'WebSocket connected: {connection_id}')
        
    def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        logger.info(f'WebSocket disconnected: {connection_id}')

# Global instance
websocket_manager = WhatsAppWebSocketManager()


"""
WebSocket API Endpoints
Provides WebSocket connections for real-time updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, Body
from core.websockets import manager
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket endpoint for real-time updates
    
    Query params:
    - token: JWT access token for authentication
    """
    user = await manager.connect(websocket, token)
    
    if not user:
        # Connection rejected (closed in manager)
        return
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            # Handle client messages
            message_type = data.get("type")
            
            if message_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    manager.subscribe(websocket, channel)
            
            elif message_type == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    manager.unsubscribe(websocket, channel)
            
            elif message_type == "ping":
                # Respond to ping
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": data.get("timestamp")
                })
            
            elif message_type == "get_stats":
                # Send connection stats
                stats = manager.get_stats()
                await websocket.send_json({
                    "type": "stats",
                    "data": stats
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, user.id)


@router.get("/ws/stats")
async def get_websocket_stats():
    """Get current WebSocket connection statistics"""
    return manager.get_stats()


@router.post("/ws/test/broadcast")
async def test_broadcast(
    channel: str = "communication_stats", 
    event_type: str = "status_update",
    message: dict = Body(...)
):
    """Test endpoint to broadcast a message to a channel"""
    await manager.broadcast_event(channel, event_type, message)
    return {"status": "broadcasted", "channel": channel, "event": event_type}

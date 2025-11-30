"""
WebSocket API Endpoints
Provides WebSocket connections for real-time updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from core.websockets import manager, broadcast_workflow_event, broadcast_system_event, WorkflowEventType
import json

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str = Query(default="anonymous"),
    channels: str = Query(default="")
):
    """
    WebSocket endpoint for real-time updates
    
    Query params:
    - user_id: User identifier
    - channels: Comma-separated list of channels to subscribe to
      Available channels: workflows, system, health, workflow:{execution_id}
    """
    await manager.connect(websocket, user_id)
    
    # Subscribe to requested channels
    if channels:
        for channel in channels.split(","):
            channel = channel.strip()
            if channel:
                await manager.subscribe_to_channel(websocket, channel)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            # Handle client messages
            message_type = data.get("type")
            
            if message_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    await manager.subscribe_to_channel(websocket, channel)
            
            elif message_type == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    await manager.unsubscribe_from_channel(websocket, channel)
            
            elif message_type == "ping":
                # Respond to ping
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": data.get("timestamp")
                }, websocket)
            
            elif message_type == "get_stats":
                # Send connection stats
                stats = manager.get_stats()
                await manager.send_personal_message({
                    "type": "stats",
                    "data": stats
                }, websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)


@router.get("/ws/stats")
async def get_websocket_stats():
    """Get current WebSocket connection statistics"""
    return manager.get_stats()


# Example: Trigger a test broadcast (for development/testing)
@router.post("/ws/test/broadcast")
async def test_broadcast(channel: str = "workflows", message: str = "Test message"):
    """Test endpoint to broadcast a message to a channel"""
    await manager.broadcast_to_channel(channel, {
        "type": "test",
        "message": message
    })
    return {"status": "broadcasted", "channel": channel}

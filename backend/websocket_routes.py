
"""
WebSocket API Endpoints
Provides WebSocket connections for real-time updates
"""

import json
import logging
from fastapi import APIRouter, Body, Depends, Query, WebSocket, WebSocketDisconnect

from core.websockets import manager

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

            elif message_type == "agent_handoff":
                # Delegate to coordination logic
                from core.agent_coordination import handle_agent_handoff
                from core.database import get_db_session
                with get_db_session() as db:
                    await handle_agent_handoff(
                        room_id=f"workspace:{user.workspace_id}",
                        data=data,
                        user=user,
                        tenant_id=user.tenant_id if hasattr(user, "tenant_id") else "default",
                        db=db
                    )
            
            elif message_type == "canvas_join":
                # Simplified agent presence join
                canvas_id = data.get("canvas_id")
                if canvas_id:
                    manager.subscribe(websocket, f"canvas:{canvas_id}")
                    # In real app, we'd also update AgentCanvasPresence here
    
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


@router.websocket("/ws/boards/{board_id}")
async def board_websocket_endpoint(
    websocket: WebSocket,
    board_id: str,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time Kanban board updates (Phase 2).

    Subscribes the caller to the single-tenant board channel
    ``board:{board_id}``. Emits on task create / move /
    transition / comment.
    """
    user = await manager.connect(websocket, token)
    if not user:
        return

    # Verify board exists (lazy import)
    from core.database import get_db_session
    from core.models_board import Board

    with get_db_session() as db:
        board = db.query(Board).filter(Board.id == board_id).first()
        if not board:
            await websocket.close(code=4003, reason="Board not found")
            return

    room_id = f"board:{board_id}"
    manager.subscribe(websocket, room_id)

    logger.info(
        f"User {user.email} connected to board {board_id} (room: {room_id})"
    )

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                from datetime import datetime, timezone
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnect for board {board_id} (user {user.id})")
    except Exception as e:
        logger.error(f"WebSocket error for board {board_id}: {e}")
    finally:
        manager.unsubscribe(websocket, room_id)
        manager.disconnect(websocket, user.id)


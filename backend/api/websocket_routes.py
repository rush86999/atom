import logging
from fastapi import WebSocket, WebSocketDisconnect

from core.base_routes import BaseAPIRouter
from core.notification_manager import notification_manager

router = BaseAPIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/{workspace_id}")
async def websocket_endpoint(websocket: WebSocket, workspace_id: str):
    await notification_manager.connect(websocket, workspace_id)
    try:
        while True:
            # Keep connection alive + listen for client heartbeats/messages
            data = await websocket.receive_text()
            # Echo or process client messages here if needed
            # For now, we mainly use this for server->client broadcast
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        notification_manager.disconnect(websocket, workspace_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        notification_manager.disconnect(websocket, workspace_id)

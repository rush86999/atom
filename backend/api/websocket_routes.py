import logging
from fastapi import WebSocket, WebSocketDisconnect

from core.auth import get_current_user_ws
from core.base_routes import BaseAPIRouter
from core.database import SessionLocal
from core.notification_manager import notification_manager

router = BaseAPIRouter(tags=["WebSockets"])
logger = logging.getLogger(__name__)

@router.websocket("/ws/{workspace_id}")
async def websocket_endpoint(websocket: WebSocket, workspace_id: str):
    """Authenticated WebSocket endpoint with workspace routing.

    SECURITY: The client must pass a valid JWT via the ``token`` query
    parameter: ``ws://host/ws/{workspace_id}?token=<jwt>``.
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    db = SessionLocal()
    try:
        user = await get_current_user_ws(token, db)
    finally:
        db.close()

    if user is None:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    await notification_manager.connect(websocket, workspace_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        notification_manager.disconnect(websocket, workspace_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        notification_manager.disconnect(websocket, workspace_id)


@router.websocket("/ws")
async def websocket_endpoint_default(websocket: WebSocket):
    """Authenticated WebSocket endpoint (default workspace).

    Frontend connects to ``ws://host/ws?token=<jwt>`` — no workspace_id
    path segment. Defaults to "default" workspace.
    """
    await websocket_endpoint(websocket, "default")
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    db = SessionLocal()
    try:
        user = await get_current_user_ws(token, db)
    finally:
        db.close()

    if user is None:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    await notification_manager.connect(websocket, workspace_id)
    try:
        while True:
            # Keep connection alive + listen for client heartbeats/messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        notification_manager.disconnect(websocket, workspace_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        notification_manager.disconnect(websocket, workspace_id)

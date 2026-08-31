import json
import logging
from fastapi import WebSocket, WebSocketDisconnect

from core.auth import get_current_user_ws
from core.base_routes import BaseAPIRouter
from core.database import SessionLocal
from core.notification_manager import notification_manager
from core.websockets import manager as channel_manager

router = BaseAPIRouter(tags=["WebSockets"])
logger = logging.getLogger(__name__)

@router.websocket("/ws/{workspace_id}")
async def websocket_endpoint(websocket: WebSocket, workspace_id: str):
    """Authenticated WebSocket endpoint with workspace routing.

    SECURITY: The client must pass a valid JWT via the ``token`` query
    parameter: ``ws://host/ws/{workspace_id}?token=<jwt>``.

    The socket serves TWO buses:
    - notification_manager (workspace notifications), and
    - the channel manager (core.websockets): the frontend's subscribe/
      unsubscribe protocol. Agent Workspace step events, canvas updates and
      chat streams broadcast on channels like ``workspace:default`` — the
      client joins via ``{"type": "subscribe", "channel": ...}``. This
      endpoint previously ignored those messages, so no browser ever joined
      a channel and every live panel silently showed nothing.
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
    # Channel bus: join the workspace channel immediately (so clients that
    # never send an explicit subscribe still receive workspace broadcasts).
    try:
        channel_manager.subscribe(websocket, f"workspace:{workspace_id or 'default'}")
        channel_manager.subscribe(websocket, "workspace:default")
        # User channel too: canvas presents/updates broadcast to
        # user:{user_id} (canvas_crud_tool, canvas_tool.present_*), but this
        # endpoint never joined it — those broadcasts silently hit an EMPTY
        # channel ("Attempted broadcast to EMPTY channel: 'user:…'") and no
        # browser ever saw a live canvas update. The subscribe logic already
        # existed in channel_manager.connect(); this endpoint just bypassed
        # it. Scoping to the authenticated user's own channel only — no
        # content leaks to workspace peers.
        channel_manager.subscribe(websocket, f"user:{user.id}")
    except Exception as e:
        logger.warning(f"channel subscribe skipped: {e}")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                continue
            try:
                msg = json.loads(data)
            except Exception:
                continue
            mtype = msg.get("type")
            if mtype == "subscribe" and msg.get("channel"):
                channel_manager.subscribe(websocket, msg["channel"])
            elif mtype == "unsubscribe" and msg.get("channel"):
                channel_manager.unsubscribe(websocket, msg["channel"])
    except WebSocketDisconnect:
        notification_manager.disconnect(websocket, workspace_id)
        channel_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        notification_manager.disconnect(websocket, workspace_id)
        channel_manager.disconnect(websocket)


@router.websocket("/ws")
async def websocket_endpoint_default(websocket: WebSocket):
    """Authenticated WebSocket endpoint (default workspace).

    Frontend connects to ``ws://host/ws?token=<jwt>`` — no workspace_id
    path segment. Defaults to "default" workspace.
    """
    # Delegate to the parametrized endpoint. Auth/loop happen there.
    await websocket_endpoint(websocket, "default")

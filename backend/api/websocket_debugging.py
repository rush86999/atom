"""
WebSocket API Endpoints for Real-Time Debugging

Provides WebSocket endpoints for real-time updates during workflow debugging.
"""

import logging
from typing import Optional
from fastapi import Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.websocket_manager import get_debugging_websocket_manager, get_websocket_manager
from core.workflow_debugger import WorkflowDebugger

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/debug", tags=["websocket-debugging"])


@router.websocket("/streams/{stream_id}")
async def websocket_debug_stream(
    websocket: WebSocket,
    stream_id: str,
    session_id: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time debug stream updates.

    Connect to receive live updates for:
    - Trace updates during execution
    - Variable changes
    - Breakpoint hits
    - Session state changes

    Message types:
    - connected: Confirmation of successful connection
    - trace_update: New trace entry
    - variable_changed: Variable was modified
    - breakpoint_hit: Breakpoint was hit
    - session_paused: Session was paused
    - session_resumed: Session was resumed
    - step_completed: Step action completed
    - stream_closed: Stream is closing
    """
    manager = get_websocket_manager()

    try:
        # Connect to stream
        await manager.connect(websocket, stream_id)
        logger.info(f"WebSocket client connected to debug stream {stream_id}")

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                logger.debug(f"Received message on stream {stream_id}: {data}")

                # Echo back for ping/pong
                if data == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})

            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected from stream {stream_id}")
                break

    except Exception as e:
        logger.error(f"WebSocket error on stream {stream_id}: {e}")

    finally:
        # Cleanup
        manager.disconnect(websocket)


@router.websocket("/sessions/{session_id}/live")
async def websocket_debug_session(
    websocket: WebSocket,
    session_id: str,
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for live debug session updates.

    Connect to receive real-time updates for a specific debug session:
    - Variable changes
    - Breakpoint hits
    - Step execution updates
    - Session state changes

    Use this for interactive debugging UI components.
    """
    manager = get_websocket_manager()
    debug_manager = get_debugging_websocket_manager()

    # Create stream ID for this session
    stream_id = f"debug_session_{session_id}"

    try:
        # Verify session exists
        debugger = WorkflowDebugger(db)
        session = debugger.get_debug_session(session_id)

        if not session:
            await websocket.close(code=4001, reason="Debug session not found")
            return

        # Connect to stream
        await manager.connect(websocket, stream_id)
        logger.info(f"WebSocket client connected to debug session {session_id}")

        # Send initial session state
        await manager.send_personal(websocket, {
            "type": "session_state",
            "session": {
                "id": session.id,
                "workflow_id": session.workflow_id,
                "status": session.status,
                "current_step": session.current_step,
                "current_node_id": session.current_node_id,
                "variables": session.variables,
                "call_stack": session.call_stack,
            },
            "timestamp": session.updated_at.isoformat() if session.updated_at else None,
        })

        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received message on session {session_id}: {data}")

                # Handle client commands
                if data == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})

            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected from session {session_id}")
                break

    except Exception as e:
        logger.error(f"WebSocket error on session {session_id}: {e}")

    finally:
        # Cleanup
        manager.disconnect(websocket)


@router.websocket("/executions/{execution_id}/traces")
async def websocket_execution_traces(
    websocket: WebSocket,
    execution_id: str,
    session_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for live execution trace updates.

    Connect to receive real-time trace entries as workflow executes:
    - Step started events
    - Step completed events
    - Error events
    - Variable changes

    Use this for execution timeline visualization.
    """
    manager = get_websocket_manager()

    # Create stream ID for this execution
    stream_id = f"traces_{execution_id}"
    if session_id:
        stream_id += f"_{session_id}"

    try:
        # Connect to stream
        await manager.connect(websocket, stream_id)
        logger.info(f"WebSocket client connected to execution traces {execution_id}")

        # Send confirmation
        await manager.send_personal(websocket, {
            "type": "subscribed",
            "execution_id": execution_id,
            "session_id": session_id,
            "stream_id": stream_id,
        })

        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received message on execution {execution_id}: {data}")

                # Handle client commands
                if data == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})

            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected from execution {execution_id}")
                break

    except Exception as e:
        logger.error(f"WebSocket error on execution {execution_id}: {e}")

    finally:
        # Cleanup
        manager.disconnect(websocket)


@router.get("/streams/{stream_id}/info")
async def get_stream_info(stream_id: str):
    """
    Get information about a WebSocket stream.

    Returns connection count and metadata for a stream.
    """
    manager = get_websocket_manager()
    info = manager.get_stream_info(stream_id)

    if not info or info.get("connection_count", 0) == 0:
        return router.success_response(
            data={"stream_id": stream_id, "active": False, "connection_count": 0},
            message="Stream is inactive"
        )

    return router.success_response(
        data={
            "stream_id": stream_id,
            "active": True,
            **info,
        },
        message="Stream information retrieved"
    )


@router.get("/streams")
async def list_active_streams():
    """
    List all active WebSocket streams.

    Returns all streams with active connections.
    """
    manager = get_websocket_manager()
    streams = manager.get_all_streams()

    return router.success_response(
        data={
            "active_streams": list(streams),
            "total_count": len(streams),
            "streams_info": [
                manager.get_stream_info(stream_id)
                for stream_id in streams
            ],
        },
        message=f"Retrieved {len(streams)} active streams"
    )

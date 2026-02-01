"""
WebSocket Manager for Real-Time Debugging

Provides WebSocket connection management for broadcasting real-time updates
to connected clients during workflow debugging and execution.
"""

import logging
import json
import asyncio
from typing import Dict, Set, Any, Optional
from datetime import datetime
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """
    Manages WebSocket connections for real-time updates.

    Supports:
    - Multiple connections per stream
    - Broadcast to all subscribers
    - Direct message to specific connection
    - Connection lifecycle management
    """

    def __init__(self):
        """Initialize the WebSocket manager."""
        # Stream ID -> Set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # WebSocket -> Stream ID mapping
        self.connection_streams: Dict[WebSocket, str] = {}
        # Connection metadata
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, stream_id: str) -> None:
        """
        Connect a WebSocket to a stream.

        Args:
            websocket: WebSocket connection
            stream_id: Stream identifier to subscribe to
        """
        await websocket.accept()

        # Add to stream
        if stream_id not in self.active_connections:
            self.active_connections[stream_id] = set()
        self.active_connections[stream_id].add(websocket)

        # Track connection
        self.connection_streams[websocket] = stream_id
        self.connection_info[websocket] = {
            "stream_id": stream_id,
            "connected_at": datetime.now().isoformat(),
        }

        logger.info(f"WebSocket connected to stream {stream_id}")

        # Send welcome message
        await self.send_personal(websocket, {
            "type": "connected",
            "stream_id": stream_id,
            "timestamp": datetime.now().isoformat(),
        })

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Disconnect a WebSocket from its stream.

        Args:
            websocket: WebSocket connection to disconnect
        """
        stream_id = self.connection_streams.get(websocket)

        if stream_id and stream_id in self.active_connections:
            self.active_connections[stream_id].discard(websocket)

            # Clean up empty streams
            if not self.active_connections[stream_id]:
                del self.active_connections[stream_id]

        self.connection_streams.pop(websocket, None)
        self.connection_info.pop(websocket, None)

        logger.info(f"WebSocket disconnected from stream {stream_id}")

    async def send_personal(self, websocket: WebSocket, message: Dict[str, Any]) -> bool:
        """
        Send a message to a specific WebSocket connection.

        Args:
            websocket: Target WebSocket connection
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            await websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
            return False

    async def broadcast(self, stream_id: str, message: Dict[str, Any]) -> int:
        """
        Broadcast a message to all connections in a stream.

        Args:
            stream_id: Stream identifier
            message: Message to broadcast

        Returns:
            Number of connections message was sent to
        """
        if stream_id not in self.active_connections:
            return 0

        # Store connections to avoid modification during iteration
        connections = list(self.active_connections[stream_id])
        sent_count = 0

        for connection in connections:
            try:
                await connection.send_text(json.dumps(message))
                sent_count += 1
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                self.disconnect(connection)

        return sent_count

    async def broadcast_trace_update(
        self,
        stream_id: str,
        trace_data: Dict[str, Any],
    ) -> int:
        """
        Broadcast a trace update to all subscribers.

        Args:
            stream_id: Stream identifier
            trace_data: Trace data to broadcast

        Returns:
            Number of connections notified
        """
        message = {
            "type": "trace_update",
            "data": trace_data,
            "timestamp": datetime.now().isoformat(),
        }

        return await self.broadcast(stream_id, message)

    async def broadcast_session_update(
        self,
        session_id: str,
        update_type: str,
        data: Dict[str, Any],
    ) -> int:
        """
        Broadcast a debug session update.

        Args:
            session_id: Debug session ID
            update_type: Type of update (e.g., "session_paused", "variable_changed")
            data: Update data

        Returns:
            Number of connections notified
        """
        stream_id = f"debug_session_{session_id}"

        message = {
            "type": update_type,
            "session_id": session_id,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }

        return await self.broadcast(stream_id, message)

    def get_connection_count(self, stream_id: str) -> int:
        """
        Get the number of active connections for a stream.

        Args:
            stream_id: Stream identifier

        Returns:
            Number of active connections
        """
        return len(self.active_connections.get(stream_id, set()))

    def get_all_streams(self) -> Set[str]:
        """
        Get all active stream IDs.

        Returns:
            Set of active stream IDs
        """
        return set(self.active_connections.keys())

    def get_stream_info(self, stream_id: str) -> Dict[str, Any]:
        """
        Get information about a stream.

        Args:
            stream_id: Stream identifier

        Returns:
            Stream information including connection count and metadata
        """
        connections = self.active_connections.get(stream_id, set())

        return {
            "stream_id": stream_id,
            "connection_count": len(connections),
            "connections": [
                {
                    "connected_at": self.connection_info.get(conn, {}).get("connected_at"),
                }
                for conn in connections
            ],
        }


class DebuggingWebSocketManager:
    """
    Specialized WebSocket manager for debugging features.

    Provides high-level methods for common debugging operations:
    - Trace streaming
    - Variable updates
    - Breakpoint changes
    - Session state changes
    """

    def __init__(self, connection_manager: WebSocketConnectionManager):
        """
        Initialize the debugging WebSocket manager.

        Args:
            connection_manager: Underlying connection manager
        """
        self.manager = connection_manager

    async def stream_trace(
        self,
        execution_id: str,
        session_id: str,
        trace_data: Dict[str, Any],
    ) -> int:
        """
        Stream a trace update to all subscribers.

        Args:
            execution_id: Execution identifier
            session_id: Debug session identifier
            trace_data: Trace data to stream

        Returns:
            Number of subscribers notified
        """
        stream_id = f"trace_{execution_id}_{session_id}"

        message = {
            "type": "trace_update",
            "execution_id": execution_id,
            "session_id": session_id,
            "trace": trace_data,
            "timestamp": datetime.now().isoformat(),
        }

        return await self.manager.broadcast(stream_id, message)

    async def notify_variable_changed(
        self,
        session_id: str,
        variable_name: str,
        new_value: Any,
        previous_value: Any = None,
    ) -> int:
        """
        Notify subscribers that a variable was modified.

        Args:
            session_id: Debug session identifier
            variable_name: Name of the variable
            new_value: New value
            previous_value: Previous value (optional)

        Returns:
            Number of subscribers notified
        """
        stream_id = f"debug_session_{session_id}"

        message = {
            "type": "variable_changed",
            "session_id": session_id,
            "variable": {
                "name": variable_name,
                "new_value": new_value,
                "previous_value": previous_value,
            },
            "timestamp": datetime.now().isoformat(),
        }

        return await self.manager.broadcast(stream_id, message)

    async def notify_breakpoint_hit(
        self,
        session_id: str,
        breakpoint_id: str,
        node_id: str,
        hit_count: int,
    ) -> int:
        """
        Notify subscribers that a breakpoint was hit.

        Args:
            session_id: Debug session identifier
            breakpoint_id: Breakpoint identifier
            node_id: Node where breakpoint was hit
            hit_count: Current hit count

        Returns:
            Number of subscribers notified
        """
        stream_id = f"debug_session_{session_id}"

        message = {
            "type": "breakpoint_hit",
            "session_id": session_id,
            "breakpoint": {
                "id": breakpoint_id,
                "node_id": node_id,
                "hit_count": hit_count,
            },
            "timestamp": datetime.now().isoformat(),
        }

        return await self.manager.broadcast(stream_id, message)

    async def notify_session_paused(
        self,
        session_id: str,
        reason: str = "user_action",
        node_id: Optional[str] = None,
    ) -> int:
        """
        Notify subscribers that a session was paused.

        Args:
            session_id: Debug session identifier
            reason: Reason for pausing
            node_id: Current node ID (optional)

        Returns:
            Number of subscribers notified
        """
        stream_id = f"debug_session_{session_id}"

        message = {
            "type": "session_paused",
            "session_id": session_id,
            "reason": reason,
            "node_id": node_id,
            "timestamp": datetime.now().isoformat(),
        }

        return await self.manager.broadcast(stream_id, message)

    async def notify_session_resumed(
        self,
        session_id: str,
    ) -> int:
        """
        Notify subscribers that a session was resumed.

        Args:
            session_id: Debug session identifier

        Returns:
            Number of subscribers notified
        """
        stream_id = f"debug_session_{session_id}"

        message = {
            "type": "session_resumed",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        }

        return await self.manager.broadcast(stream_id, message)

    async def notify_step_completed(
        self,
        session_id: str,
        action: str,
        step_number: int,
        node_id: Optional[str] = None,
    ) -> int:
        """
        Notify subscribers that a step action completed.

        Args:
            session_id: Debug session identifier
            action: Action performed (step_over, step_into, step_out)
            step_number: New step number
            node_id: Current node ID (optional)

        Returns:
            Number of subscribers notified
        """
        stream_id = f"debug_session_{session_id}"

        message = {
            "type": "step_completed",
            "session_id": session_id,
            "action": action,
            "step_number": step_number,
            "node_id": node_id,
            "timestamp": datetime.now().isoformat(),
        }

        return await self.manager.broadcast(stream_id, message)


# Singleton instance
_manager: Optional[WebSocketConnectionManager] = None
_debug_manager: Optional[DebuggingWebSocketManager] = None


def get_websocket_manager() -> WebSocketConnectionManager:
    """Get the singleton WebSocket connection manager instance."""
    global _manager
    if _manager is None:
        _manager = WebSocketConnectionManager()
    return _manager


def get_debugging_websocket_manager() -> DebuggingWebSocketManager:
    """Get the singleton debugging WebSocket manager instance."""
    global _debug_manager
    if _debug_manager is None:
        _debug_manager = DebuggingWebSocketManager(get_websocket_manager())
    return _debug_manager

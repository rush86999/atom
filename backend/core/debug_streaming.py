"""
Debug Streaming Service

Real-time streaming of debug events via WebSocket.
Integrates with DebugCollector for live event broadcast.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket
from redis import Redis
from redis.exceptions import RedisError

from core.debug_collector import get_debug_collector
from core.structured_logger import StructuredLogger
from core.websocket_manager import WebSocketConnectionManager


# Configuration
DEBUG_STREAMING_ENABLED = os.getenv("DEBUG_STREAMING_ENABLED", "true").lower() == "true"
DEBUG_REDIS_KEY_PREFIX = os.getenv("DEBUG_REDIS_KEY_PREFIX", "debug")


class DebugStreamingService:
    """
    Real-time debug event streaming service.

    Broadcasts debug events, insights, and state changes to connected clients.

    Example:
        streaming = DebugStreamingService()

        # Client subscribes to debug stream
        await streaming.subscribe_client(websocket, "debug:agent-123")

        # Broadcast event to all subscribers
        await streaming.broadcast_event(event_data)

        # Publish insight
        await streaming.broadcast_insight(insight_data)
    """

    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        ws_manager: Optional[WebSocketConnectionManager] = None,
    ):
        """
        Initialize debug streaming service.

        Args:
            redis_client: Redis client for pub/sub
            ws_manager: WebSocket manager for broadcasting
        """
        self.logger = StructuredLogger(__name__)
        self.redis = redis_client
        self.ws_manager = ws_manager or WebSocketConnectionManager()

        # Redis pub/sub
        self._redis_channel = f"{DEBUG_REDIS_KEY_PREFIX}:events"
        self._pubsub_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start Redis pub/sub listener for real-time events."""
        if not DEBUG_STREAMING_ENABLED or not self.redis:
            return

        if self._running:
            return

        self._running = True
        self._pubsub_task = asyncio.create_task(self._redis_pubsub_listener())

        self.logger.info("Debug streaming service started")

    async def stop(self):
        """Stop Redis pub/sub listener."""
        if not self._running:
            return

        self._running = False

        if self._pubsub_task:
            self._pubsub_task.cancel()
            self._pubsub_task = None

        self.logger.info("Debug streaming service stopped")

    async def subscribe_client(
        self,
        websocket: WebSocket,
        stream_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ):
        """
        Subscribe a client to debug event stream.

        Args:
            websocket: WebSocket connection
            stream_id: Stream identifier (e.g., "debug:all", "debug:agent-123")
            filters: Optional filters for events
        """
        try:
            await self.ws_manager.connect(websocket, stream_id)

            # Store filters with connection
            if websocket not in self.ws_manager.connection_info:
                self.ws_manager.connection_info[websocket] = {}
            self.ws_manager.connection_info[websocket]["filters"] = filters

            self.logger.info(
                "Client subscribed to debug stream",
                stream_id=stream_id,
                filters=filters,
            )

        except Exception as e:
            self.logger.error(
                "Failed to subscribe client",
                stream_id=stream_id,
                error=str(e),
            )

    async def unsubscribe_client(self, websocket: WebSocket):
        """
        Unsubscribe a client from debug event stream.

        Args:
            websocket: WebSocket connection
        """
        try:
            self.ws_manager.disconnect(websocket)
            self.logger.info("Client unsubscribed from debug stream")
        except Exception as e:
            self.logger.error("Failed to unsubscribe client", error=str(e))

    async def broadcast_event(self, event_data: Dict[str, Any]):
        """
        Broadcast debug event to all subscribers.

        Args:
            event_data: Event data to broadcast
        """
        try:
            message = {
                "type": "debug:event",
                "data": event_data,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Broadcast to all debug stream subscribers
            await self._broadcast_to_all_streams(message)

        except Exception as e:
            self.logger.error("Failed to broadcast event", error=str(e))

    async def broadcast_insight(self, insight_data: Dict[str, Any]):
        """
        Broadcast debug insight to all subscribers.

        Args:
            insight_data: Insight data to broadcast
        """
        try:
            message = {
                "type": "debug:insight",
                "data": insight_data,
                "timestamp": datetime.utcnow().isoformat(),
            }

            await self._broadcast_to_all_streams(message)

        except Exception as e:
            self.logger.error("Failed to broadcast insight", error=str(e))

    async def broadcast_alert(self, alert_data: Dict[str, Any]):
        """
        Broadcast debug alert to all subscribers.

        Args:
            alert_data: Alert data to broadcast
        """
        try:
            message = {
                "type": "debug:alert",
                "data": alert_data,
                "timestamp": datetime.utcnow().isoformat(),
            }

            await self._broadcast_to_all_streams(message)

        except Exception as e:
            self.logger.error("Failed to broadcast alert", error=str(e))

    async def broadcast_state_change(self, state_data: Dict[str, Any]):
        """
        Broadcast state change to all subscribers.

        Args:
            state_data: State change data to broadcast
        """
        try:
            message = {
                "type": "debug:state_change",
                "data": state_data,
                "timestamp": datetime.utcnow().isoformat(),
            }

            await self._broadcast_to_all_streams(message)

        except Exception as e:
            self.logger.error("Failed to broadcast state change", error=str(e))

    async def broadcast_metric_update(self, metric_data: Dict[str, Any]):
        """
        Broadcast metric update to all subscribers.

        Args:
            metric_data: Metric data to broadcast
        """
        try:
            message = {
                "type": "debug:metric_update",
                "data": metric_data,
                "timestamp": datetime.utcnow().isoformat(),
            }

            await self._broadcast_to_all_streams(message)

        except Exception as e:
            self.logger.error("Failed to broadcast metric update", error=str(e))

    async def _broadcast_to_all_streams(self, message: Dict[str, Any]):
        """Broadcast message to all debug stream subscribers."""
        try:
            # Broadcast to streams starting with "debug:"
            for stream_id in list(self.ws_manager.active_connections.keys()):
                if stream_id.startswith("debug:"):
                    await self.ws_manager.broadcast(stream_id, message)
        except Exception as e:
            self.logger.error("Failed to broadcast to streams", error=str(e))

    async def _redis_pubsub_listener(self):
        """Listen for Redis pub/sub messages and broadcast to WebSocket clients."""
        if not self.redis:
            return

        try:
            pubsub = self.redis.pubsub()
            pubsub.subscribe(self._redis_channel)

            self.logger.info("Redis pub/sub listener started", channel=self._redis_channel)

            while self._running:
                try:
                    # Get message with timeout
                    message = pubsub.get_message(timeout=1.0)

                    if message and message["type"] == "message":
                        # Parse message data
                        data = json.loads(message["data"])

                        # Broadcast to WebSocket clients
                        await self._broadcast_to_all_streams(data)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error("Error in pub/sub listener", error=str(e))
                    await asyncio.sleep(1.0)

        except RedisError as e:
            self.logger.error("Redis pub/sub error", error=str(e))
        finally:
            try:
                pubsub.close()
            except:
                pass


# Global streaming service instance
_streaming_service: Optional[DebugStreamingService] = None


def get_debug_streaming() -> Optional[DebugStreamingService]:
    """
    Get the global DebugStreamingService instance.

    Returns:
        DebugStreamingService instance or None
    """
    global _streaming_service
    return _streaming_service


def init_debug_streaming(
    redis_client: Optional[Redis] = None,
    ws_manager: Optional[WebSocketConnectionManager] = None,
) -> Optional[DebugStreamingService]:
    """
    Initialize the global DebugStreamingService instance.

    Args:
        redis_client: Redis client for pub/sub
        ws_manager: WebSocket manager

    Returns:
        Initialized streaming service or None if disabled
    """
    global _streaming_service

    if not DEBUG_STREAMING_ENABLED:
        return None

    if _streaming_service is None:
        _streaming_service = DebugStreamingService(
            redis_client=redis_client,
            ws_manager=ws_manager,
        )

        # Start the service
        asyncio.create_task(_streaming_service.start())

    return _streaming_service

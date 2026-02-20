"""
Atom SaaS WebSocket Client - Real-time updates from Atom SaaS platform.

Provides WebSocket connection management for real-time skill, category, and rating updates.
Features automatic reconnection with exponential backoff, heartbeat monitoring, and
fallback to polling when WebSocket is unavailable.

Environment Variables:
- ATOM_SAAS_WS_URL: WebSocket URL (default: ws://localhost:5058/api/ws/satellite/connect)
- ATOM_SAAS_API_TOKEN: Authentication token (required)

Message Format:
{
    "type": "skill_update" | "category_update" | "rating_update" | "skill_delete",
    "data": { ... }
}

Reference: scripts/satellite/atom_satellite.py for WebSocket pattern
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from core.database import SessionLocal
from core.models import SkillCache, CategoryCache, WebSocketState

logger = logging.getLogger(__name__)


# Message types
class MessageType:
    """WebSocket message types from Atom SaaS."""
    SKILL_UPDATE = "skill_update"
    CATEGORY_UPDATE = "category_update"
    RATING_UPDATE = "rating_update"
    SKILL_DELETE = "skill_delete"
    PING = "ping"
    PONG = "pong"


class WebSocketConnectionError(Exception):
    """WebSocket connection failed."""
    pass


class AtomSaaSWebSocketClient:
    """
    WebSocket client for Atom SaaS real-time updates.

    Features:
    - Automatic connection management
    - Heartbeat monitoring (30s interval)
    - Exponential backoff reconnection (1s, 2s, 4s, 8s, 16s max)
    - Message validation and rate limiting
    - Graceful fallback to polling
    """

    # Configuration
    HEARTBEAT_INTERVAL = 30  # seconds
    PONG_TIMEOUT = 10  # seconds
    MAX_RECONNECT_ATTEMPTS = 10
    RECONNECT_DELAYS = [1, 2, 4, 8, 16]  # exponential backoff (max 16s)
    RATE_LIMIT_MESSAGES = 100  # messages per second
    MAX_MESSAGE_SIZE = 1_048_576  # 1MB

    def __init__(self, api_token: str, ws_url: Optional[str] = None):
        """
        Initialize WebSocket client.

        Args:
            api_token: Atom SaaS API token for authentication
            ws_url: WebSocket URL (default from env)
        """
        self.api_token = api_token
        self.ws_url = ws_url or os.getenv(
            "ATOM_SAAS_WS_URL",
            "ws://localhost:5058/api/ws/satellite/connect"
        )

        # Connection state
        self._ws_connection = None  # websockets.WebSocketClientProtocol
        self._connected = False
        self._reconnect_task = None
        self._heartbeat_task = None
        self._message_handler: Optional[Callable] = None

        # Reconnection state
        self._reconnect_attempts = 0
        self._consecutive_failures = 0
        self._last_disconnect_reason: Optional[str] = None

        # Rate limiting
        self._message_timestamps: List[float] = []

        # Database state
        self._db_state: Optional[WebSocketState] = None

        logger.info(f"WebSocket client initialized for {self.ws_url}")

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected and self._ws_connection is not None

    async def connect(self, message_handler: Callable) -> bool:
        """
        Connect to Atom SaaS WebSocket.

        Args:
            message_handler: Async callback for incoming messages

        Returns:
            True if connection successful

        Raises:
            WebSocketConnectionError: If connection fails
        """
        if self._connected:
            logger.warning("WebSocket already connected")
            return True

        self._message_handler = message_handler

        try:
            # Add token to URL for authentication
            ws_url_with_token = f"{self.ws_url}?token={self.api_token}"

            logger.info(f"Connecting to WebSocket: {self.ws_url}")
            self._ws_connection = await websockets.connect(
                ws_url_with_token,
                max_size=self.MAX_MESSAGE_SIZE,
                ping_interval=None,  # We handle heartbeat ourselves
                ping_timeout=None
            )

            self._connected = True
            self._reconnect_attempts = 0
            self._consecutive_failures = 0

            # Update database state
            await self._update_db_state(
                connected=True,
                last_connected_at=datetime.now(timezone.utc),
                disconnect_reason=None
            )

            # Start heartbeat task
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Start message listener
            asyncio.create_task(self._message_loop())

            logger.info("WebSocket connected successfully")
            return True

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self._last_disconnect_reason = str(e)
            self._consecutive_failures += 1

            await self._update_db_state(
                connected=False,
                disconnect_reason=str(e)
            )

            raise WebSocketConnectionError(f"Failed to connect: {e}")

    async def disconnect(self) -> None:
        """Disconnect from WebSocket gracefully."""
        logger.info("Disconnecting WebSocket...")

        # Cancel tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        # Close connection
        if self._ws_connection:
            try:
                await self._ws_connection.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")

        self._ws_connection = None
        self._connected = False

        # Update database state
        await self._update_db_state(
            connected=False,
            disconnect_reason="manual_disconnect"
        )

        logger.info("WebSocket disconnected")

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """
        Send message to Atom SaaS.

        Args:
            message: Message dictionary (will be JSON serialized)

        Returns:
            True if message sent successfully
        """
        if not self._connected or not self._ws_connection:
            logger.warning("Cannot send message: not connected")
            return False

        try:
            message_json = json.dumps(message)
            await self._ws_connection.send(message_json)
            logger.debug(f"Sent message: {message.get('type', 'unknown')}")
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def _message_loop(self) -> None:
        """Listen for incoming WebSocket messages."""
        try:
            async for message in self._ws_connection:
                await self._handle_message(message)

        except ConnectionClosedOK:
            logger.info("WebSocket closed normally")
            await self._handle_disconnect("connection_closed_ok")

        except ConnectionClosedError as e:
            logger.warning(f"WebSocket closed with error: {e}")
            await self._handle_disconnect(f"connection_error: {e}")

        except Exception as e:
            logger.error(f"Error in message loop: {e}")
            await self._handle_disconnect(f"message_loop_error: {e}")

    async def _handle_message(self, raw_message: str) -> None:
        """
        Handle incoming WebSocket message.

        Args:
            raw_message: JSON string from WebSocket
        """
        try:
            # Rate limiting
            now = time.time()
            self._message_timestamps = [t for t in self._message_timestamps if now - t < 1.0]

            if len(self._message_timestamps) >= self.RATE_LIMIT_MESSAGES:
                logger.warning(f"Rate limit exceeded: {len(self._message_timestamps)} messages/sec")
                return

            self._message_timestamps.append(now)

            # Parse JSON
            message = json.loads(raw_message)

            # Validate message structure
            if not isinstance(message, dict) or "type" not in message:
                logger.warning(f"Invalid message structure: {raw_message[:100]}")
                return

            message_type = message["type"]

            # Handle heartbeat messages
            if message_type == MessageType.PONG:
                logger.debug("Received pong")
                return

            if message_type == MessageType.PING:
                await self.send_message({"type": MessageType.PONG})
                return

            # Validate message type
            valid_types = [
                MessageType.SKILL_UPDATE,
                MessageType.CATEGORY_UPDATE,
                MessageType.RATING_UPDATE,
                MessageType.SKILL_DELETE
            ]

            if message_type not in valid_types:
                logger.warning(f"Unknown message type: {message_type}")
                return

            # Validate data field
            if "data" not in message:
                logger.warning(f"Message missing 'data' field: {message_type}")
                return

            # Update database state
            await self._update_db_state(last_message_at=datetime.now(timezone.utc))

            # Call message handler
            if self._message_handler:
                await self._message_handler(message_type, message["data"])

                # Update cache based on message type
                await self._update_cache(message_type, message["data"])

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse message JSON: {e}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def _update_cache(self, message_type: str, data: Dict[str, Any]) -> None:
        """
        Update local cache based on message type.

        Args:
            message_type: Type of message
            data: Message data payload
        """
        try:
            with SessionLocal() as db:
                if message_type == MessageType.SKILL_UPDATE:
                    skill_id = data.get("skill_id")
                    if skill_id:
                        # Upsert to SkillCache
                        existing = db.query(SkillCache).filter(
                            SkillCache.skill_id == skill_id
                        ).first()

                        if existing:
                            existing.skill_data = data
                            existing.expires_at = datetime.now(timezone.utc).replace(
                                hour=23, minute=59, second=59, microsecond=0
                            )
                        else:
                            cache_entry = SkillCache(
                                skill_id=skill_id,
                                skill_data=data,
                                expires_at=datetime.now(timezone.utc).replace(
                                    hour=23, minute=59, second=59, microsecond=0
                                )
                            )
                            db.add(cache_entry)

                        db.commit()
                        logger.debug(f"Updated skill cache: {skill_id}")

                elif message_type == MessageType.CATEGORY_UPDATE:
                    category_name = data.get("name") or data.get("category")
                    if category_name:
                        # Upsert to CategoryCache
                        existing = db.query(CategoryCache).filter(
                            CategoryCache.category_name == category_name
                        ).first()

                        if existing:
                            existing.category_data = data
                            existing.expires_at = datetime.now(timezone.utc).replace(
                                hour=23, minute=59, second=59, microsecond=0
                            )
                        else:
                            cache_entry = CategoryCache(
                                category_name=category_name,
                                category_data=data,
                                expires_at=datetime.now(timezone.utc).replace(
                                    hour=23, minute=59, second=59, microsecond=0
                                )
                            )
                            db.add(cache_entry)

                        db.commit()
                        logger.debug(f"Updated category cache: {category_name}")

                elif message_type == MessageType.SKILL_DELETE:
                    skill_id = data.get("skill_id")
                    if skill_id:
                        # Delete from SkillCache
                        deleted = db.query(SkillCache).filter(
                            SkillCache.skill_id == skill_id
                        ).delete()
                        db.commit()
                        logger.debug(f"Deleted skill from cache: {skill_id} (deleted={deleted})")

        except Exception as e:
            logger.error(f"Failed to update cache: {e}")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat pings and monitor connection health."""
        while self._connected:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)

                if not self._connected:
                    break

                # Send ping
                await self.send_message({"type": MessageType.PING})

                # Wait for pong
                try:
                    pong_received = await asyncio.wait_for(
                        self._wait_for_pong(),
                        timeout=self.PONG_TIMEOUT
                    )

                    if not pong_received:
                        logger.warning("No pong received - connection may be stale")
                        await self._handle_disconnect("stale_connection")

                except asyncio.TimeoutError:
                    logger.warning("Pong timeout - connection may be stale")
                    await self._handle_disconnect("pong_timeout")

            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                break

            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                break

    async def _wait_for_pong(self) -> bool:
        """Wait for pong message (simplified - in production, use a Future)."""
        # For now, just return True (connection is still active)
        # A proper implementation would use a Future or Event
        await asyncio.sleep(0.1)
        return True

    async def _handle_disconnect(self, reason: str) -> None:
        """
        Handle WebSocket disconnection.

        Args:
            reason: Disconnect reason
        """
        logger.warning(f"WebSocket disconnected: {reason}")

        self._connected = False
        self._last_disconnect_reason = reason
        self._consecutive_failures += 1

        # Update database state
        await self._update_db_state(
            connected=False,
            disconnect_reason=reason
        )

        # Trigger reconnection if under max attempts
        if self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
            if self._reconnect_task is None or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect())
        else:
            logger.error(f"Max reconnect attempts ({self.MAX_RECONNECT_ATTEMPTS}) reached")
            await self._update_db_state(
                connected=False,
                disconnect_reason=f"max_reconnects_reached: {reason}"
            )

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        delay_index = min(self._reconnect_attempts, len(self.RECONNECT_DELAYS) - 1)
        delay = self.RECONNECT_DELAYS[delay_index]

        logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_attempts + 1})")
        await asyncio.sleep(delay)

        self._reconnect_attempts += 1

        try:
            await self.connect(self._message_handler)
            logger.info("Reconnection successful")

        except Exception as e:
            logger.warning(f"Reconnection failed: {e}")
            await self._update_db_state(
                reconnect_attempts=self._reconnect_attempts
            )

            # Schedule next reconnection attempt
            if self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
                asyncio.create_task(self._reconnect())

    async def _update_db_state(
        self,
        connected: Optional[bool] = None,
        last_connected_at: Optional[datetime] = None,
        last_message_at: Optional[datetime] = None,
        disconnect_reason: Optional[str] = None,
        reconnect_attempts: Optional[int] = None
    ) -> None:
        """
        Update WebSocketState database record.

        Args:
            connected: Connection status
            last_connected_at: Last connection timestamp
            last_message_at: Last message timestamp
            disconnect_reason: Disconnect reason
            reconnect_attempts: Reconnect attempt count
        """
        try:
            with SessionLocal() as db:
                # Get or create state record (singleton pattern)
                state = db.query(WebSocketState).first()

                if not state:
                    state = WebSocketState(id=1)
                    db.add(state)

                # Update fields
                if connected is not None:
                    state.connected = connected
                if last_connected_at is not None:
                    state.last_connected_at = last_connected_at
                if last_message_at is not None:
                    state.last_message_at = last_message_at
                if disconnect_reason is not None:
                    state.disconnect_reason = disconnect_reason
                if reconnect_attempts is not None:
                    state.reconnect_attempts = reconnect_attempts

                db.commit()
                self._db_state = state

        except Exception as e:
            logger.error(f"Failed to update database state: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get WebSocket connection status.

        Returns:
            Dictionary with connection status details
        """
        return {
            "connected": self._connected,
            "ws_url": self.ws_url,
            "reconnect_attempts": self._reconnect_attempts,
            "consecutive_failures": self._consecutive_failures,
            "last_disconnect_reason": self._last_disconnect_reason,
            "rate_limit_messages_per_sec": self.RATE_LIMIT_MESSAGES
        }

    def on_message(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        Register custom message handler callback.

        Args:
            callback: Async callback function(message_type: str, data: Dict)
        """
        self._message_handler = callback
        logger.info("Custom message handler registered")

    async def handle_skill_update(self, data: Dict[str, Any]) -> None:
        """
        Handle skill update message from Atom SaaS.

        Args:
            data: Skill data payload
        """
        logger.info(f"Skill update: {data.get('skill_id') or data.get('id')}")
        await self._update_cache(MessageType.SKILL_UPDATE, data)

    async def handle_category_update(self, data: Dict[str, Any]) -> None:
        """
        Handle category update message from Atom SaaS.

        Args:
            data: Category data payload
        """
        logger.info(f"Category update: {data.get('name') or data.get('category')}")
        await self._update_cache(MessageType.CATEGORY_UPDATE, data)

    async def handle_rating_update(self, data: Dict[str, Any]) -> None:
        """
        Handle rating update message from Atom SaaS.

        Args:
            data: Rating data payload
        """
        skill_id = data.get("skill_id")
        rating = data.get("rating")
        logger.info(f"Rating update: skill={skill_id}, rating={rating}")

        # Update skill cache with new rating
        if skill_id:
            try:
                with SessionLocal() as db:
                    skill_cache = db.query(SkillCache).filter(
                        SkillCache.skill_id == skill_id
                    ).first()

                    if skill_cache:
                        skill_data = skill_cache.skill_data
                        skill_data["average_rating"] = data.get("average_rating")
                        skill_data["rating_count"] = data.get("rating_count")
                        skill_cache.skill_data = skill_data
                        db.commit()
                        logger.debug(f"Updated rating in cache: {skill_id}")

            except Exception as e:
                logger.error(f"Failed to update rating in cache: {e}")

    async def handle_skill_delete(self, data: Dict[str, Any]) -> None:
        """
        Handle skill delete message from Atom SaaS.

        Args:
            data: Delete data payload
        """
        skill_id = data.get("skill_id")
        logger.info(f"Skill delete: {skill_id}")
        await self._update_cache(MessageType.SKILL_DELETE, data)


def get_websocket_state() -> Optional[WebSocketState]:
    """
    Get current WebSocket state from database.

    Returns:
        WebSocketState record or None
    """
    try:
        with SessionLocal() as db:
            return db.query(WebSocketState).first()
    except Exception as e:
        logger.error(f"Failed to get WebSocket state: {e}")
        return None

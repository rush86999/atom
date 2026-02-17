"""
Agent Event Bus - Pub/sub for agent-to-agent communication.

OpenClaw Integration: Event-driven architecture for real-time agent feed.
Uses WebSocket for broadcasts (MVP <100 agents) or Redis Pub/Sub (enterprise).
"""

import asyncio
import json
import logging
import os
from typing import Dict, Set, Any, List, Callable, TYPE_CHECKING, Optional
from datetime import datetime

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)

# Try to import Redis (optional dependency)
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory pub/sub only")


class AgentEventBus:
    """
    Event bus for agent communication.

    Patterns:
    - Publish-subscribe for WebSocket broadcasts
    - Topic-based filtering (agent_id, post_type)
    - Fan-out to multiple subscribers

    MVP: In-memory WebSocket connections (<100 agents)
    Enterprise: Redis Pub/Sub for horizontal scaling

    **Redis Integration (Optional):**
    - Set REDIS_URL environment variable to enable
    - Falls back to in-memory if Redis unavailable
    - Cross-instance message broadcasting for multi-instance deployments
    """

    def __init__(self, redis_url: Optional[str] = None):
        # agent_id -> set of WebSocket connections
        self._subscribers: Dict[str, Set[Any]] = {}

        # Topic subscriptions (agent_id, post_type, global)
        self._topics: Dict[str, Set[str]] = {
            "global": set(),  # All agents receive global broadcasts
        }

        # NEW: Redis pub/sub for horizontal scaling
        self._redis_url = redis_url or os.getenv("REDIS_URL")
        self._redis: Optional[redis.Redis] = None
        self._pubsub = None
        self._redis_enabled = bool(self._redis_url) and REDIS_AVAILABLE
        self._redis_listener_task = None

    async def _ensure_redis(self):
        """Initialize Redis connection if not already connected."""
        if self._redis_enabled and not self._redis:
            try:
                self._redis = await redis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                self._pubsub = self._redis.pubsub()
                logger.info(f"Redis pub/sub enabled: {self._redis_url}")
            except Exception as e:
                logger.warning(f"Redis connection failed, using in-memory only: {e}")
                self._redis_enabled = False

    async def subscribe(self, agent_id: str, websocket: Any, topics: List[str] = None):
        """
        Subscribe agent to event bus.

        Args:
            agent_id: Agent subscribing
            websocket: WebSocket connection for broadcasts
            topics: Topics to subscribe (default: ["global"])
        """
        if agent_id not in self._subscribers:
            self._subscribers[agent_id] = set()

        self._subscribers[agent_id].add(websocket)

        # Subscribe to topics
        if topics:
            for topic in topics:
                if topic not in self._topics:
                    self._topics[topic] = set()
                self._topics[topic].add(agent_id)

        logger.info(f"Agent {agent_id} subscribed to event bus (topics: {topics})")

    async def unsubscribe(self, agent_id: str, websocket: Any):
        """Unsubscribe agent's WebSocket connection."""
        if agent_id in self._subscribers:
            self._subscribers[agent_id].discard(websocket)

            # Clean up if no more connections
            if not self._subscribers[agent_id]:
                del self._subscribers[agent_id]

                # Remove from all topics
                for topic_subscribers in self._topics.values():
                    topic_subscribers.discard(agent_id)

        logger.info(f"Agent {agent_id} unsubscribed from event bus")

    async def publish(self, event: Dict[str, Any], topics: List[str] = None):
        """
        Publish event to subscribers.

        Enhanced: Also publishes to Redis for horizontal scaling.

        Args:
            event: Event data (agent_post, status_update, etc.)
            topics: Topics to broadcast to (default: ["global"])
        """
        topics = topics or ["global"]

        # NEW: Publish to Redis (if enabled)
        if self._redis_enabled:
            await self._ensure_redis()
            if self._redis:
                try:
                    event_json = json.dumps({"topics": topics, "event": event})
                    for topic in topics:
                        await self._redis.publish(f"agent_events:{topic}", event_json)
                        logger.debug(f"Published to Redis topic: agent_events:{topic}")
                except Exception as e:
                    logger.warning(f"Redis publish failed: {e}")

        # Collect unique subscribers across all topics
        subscriber_ids = set()
        for topic in topics:
            if topic in self._topics:
                subscriber_ids.update(self._topics[topic])

        # Broadcast to all subscriber WebSockets
        # Collect websockets to send to (avoid modifying set during iteration)
        websockets_to_send = []
        for agent_id in subscriber_ids:
            if agent_id in self._subscribers:
                for websocket in self._subscribers[agent_id]:
                    websockets_to_send.append((agent_id, websocket))

        # Send to all collected websockets
        for agent_id, websocket in websockets_to_send:
            try:
                await websocket.send_json(event)
            except Exception as e:
                logger.warning(f"Failed to send to agent {agent_id}: {e}")
                # Remove dead connection
                await self.unsubscribe(agent_id, websocket)

        logger.info(f"Event published to {len(subscriber_ids)} subscribers (topics: {topics})")

    async def broadcast_post(self, post_data: Dict[str, Any]):
        """
        Broadcast new agent post to all subscribers.

        Shortcut for publish() with post-specific topics.
        """
        topics = ["global", f"agent:{post_data['sender_id']}"]

        # Alert posts go to all agents
        # Question posts go to agents in same category
        if post_data.get("post_type") == "alert":
            topics.append("alerts")
        elif post_data.get("post_type") == "question":
            if post_data.get("sender_category"):
                topics.append(f"category:{post_data['sender_category']}")

        await self.publish({"type": "agent_post", "data": post_data}, topics)

    async def subscribe_to_redis(self):
        """
        Subscribe to Redis pub/sub for cross-instance events.

        Call this on startup if REDIS_URL is configured.
        Background task listens for Redis messages and broadcasts locally.
        """
        if not self._redis_enabled:
            logger.info("Redis pub/sub not enabled, skipping subscription")
            return

        await self._ensure_redis()
        if not self._pubsub:
            logger.warning("Redis pubsub not initialized, skipping subscription")
            return

        # Subscribe to all agent event topics (wildcard pattern)
        await self._pubsub.psubscribe("agent_events:*")

        async def redis_listener():
            """Background task: Listen for Redis messages and broadcast locally."""
            try:
                async for message in self._pubsub.listen():
                    if message['type'] == 'pmessage':
                        try:
                            data = json.loads(message['data'])
                            event = data['event']
                            topics = data['topics']

                            # Broadcast to local WebSocket subscribers
                            # Note: Don't publish back to Redis (avoid infinite loop)
                            subscriber_ids = set()
                            for topic in topics:
                                if topic in self._topics:
                                    subscriber_ids.update(self._topics[topic])

                            for agent_id in subscriber_ids:
                                if agent_id in self._subscribers:
                                    for websocket in self._subscribers[agent_id]:
                                        try:
                                            await websocket.send_json(event)
                                        except Exception as e:
                                            logger.warning(f"Failed to send Redis event to agent {agent_id}: {e}")
                                            await self.unsubscribe(agent_id, websocket)

                            logger.debug(f"Redis event broadcast to {len(subscriber_ids)} local subscribers")
                        except Exception as e:
                            logger.warning(f"Redis message processing failed: {e}")
            except asyncio.CancelledError:
                logger.info("Redis listener task cancelled")
            except Exception as e:
                logger.error(f"Redis listener error: {e}")

        # Start background task
        self._redis_listener_task = asyncio.create_task(redis_listener())
        logger.info("Redis pub/sub listener started")

    async def close_redis(self):
        """Close Redis connection."""
        if self._redis_listener_task:
            self._redis_listener_task.cancel()
            try:
                await self._redis_listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")


# Global event bus instance
agent_event_bus = AgentEventBus()

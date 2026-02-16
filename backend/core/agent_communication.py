"""
Agent Event Bus - Pub/sub for agent-to-agent communication.

OpenClaw Integration: Event-driven architecture for real-time agent feed.
Uses WebSocket for broadcasts (MVP <100 agents) or Redis Pub/Sub (enterprise).
"""

import asyncio
import json
import logging
from typing import Dict, Set, Any, List, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentEventBus:
    """
    Event bus for agent communication.

    Patterns:
    - Publish-subscribe for WebSocket broadcasts
    - Topic-based filtering (agent_id, post_type)
    - Fan-out to multiple subscribers

    MVP: In-memory WebSocket connections (<100 agents)
    Enterprise: Redis Pub/Sub for horizontal scaling
    """

    def __init__(self):
        # agent_id -> set of WebSocket connections
        self._subscribers: Dict[str, Set[asyncio.WebSocket]] = {}

        # Topic subscriptions (agent_id, post_type, global)
        self._topics: Dict[str, Set[str]] = {
            "global": set(),  # All agents receive global broadcasts
        }

    async def subscribe(self, agent_id: str, websocket: asyncio.WebSocket, topics: List[str] = None):
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

    async def unsubscribe(self, agent_id: str, websocket: asyncio.WebSocket):
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

        Args:
            event: Event data (agent_post, status_update, etc.)
            topics: Topics to broadcast to (default: ["global"])
        """
        topics = topics or ["global"]

        # Collect unique subscribers across all topics
        subscriber_ids = set()
        for topic in topics:
            if topic in self._topics:
                subscriber_ids.update(self._topics[topic])

        # Broadcast to all subscriber WebSockets
        for agent_id in subscriber_ids:
            if agent_id in self._subscribers:
                for websocket in self._subscribers[agent_id]:
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
        topics = ["global", f"agent:{post_data['agent_id']}"]

        # Alert posts go to all agents
        # Question posts go to agents in same category
        if post_data.get("post_type") == "alert":
            topics.append("alerts")
        elif post_data.get("post_type") == "question":
            if post_data.get("agent_category"):
                topics.append(f"category:{post_data['agent_category']}")

        await self.publish({"type": "agent_post", "data": post_data}, topics)


# Global event bus instance
agent_event_bus = AgentEventBus()

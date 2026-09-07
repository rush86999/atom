from __future__ import annotations
import asyncio
import json
import logging
import os
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Union

from sqlalchemy import text

from core.database import DATABASE_URL

logger = logging.getLogger(__name__)


class EventBusInterface:
    """Interface for the Agent Event Bus"""

    async def start(self):
        pass

    async def stop(self):
        pass

    def publish_social_event(self, tenant_id: str, event_type: str, data: dict[str, Any]) -> bool:
        pass

    async def subscribe_tenant_events(
        self, tenant_id: str, callback: Callable[[dict[str, Any]], None]
    ):
        pass

    def get_connection_status(self) -> dict[str, Any]:
        pass


class PostgresEventBus(EventBusInterface):
    """
    Event bus for broadcasting events via Postgres NOTIFY/LISTEN.
    Best for serverless/DB-heavy workloads.
    """

    def __init__(self):
        self._listeners: dict[str, list[Callable]] = {}
        self._listener_task:Union[asyncio.Task, None] = None
        self._stop_event = asyncio.Event()

    async def _setup_listener(self):
        if "postgresql" not in DATABASE_URL:
            logger.warning("PostgresEventBus requires PostgreSQL. Events will be local-only.")
            return

        import asyncpg

        conn = None
        try:
            clean_url = (
                DATABASE_URL.replace("postgres://", "postgresql://", 1)
                if DATABASE_URL.startswith("postgres://")
                else DATABASE_URL
            )
            conn = await asyncpg.connect(clean_url)
            logger.info("✅ PostgresEventBus listener connected")

            async def notification_handler(connection, pid, channel, payload):
                try:
                    event = json.loads(payload)
                    tenant_id = event.get("tenant_id")
                    if tenant_id in self._listeners:
                        for cb in self._listeners[tenant_id]:
                            asyncio.create_task(cb(event))
                except Exception as e:
                    logger.error(f"Error handling notification: {e}")

            await conn.add_listener("atom_social_events", notification_handler)
            while not self._stop_event.is_set():
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Postgres listener error: {e}")
        finally:
            if conn:
                await conn.close()
                logger.info("PostgresEventBus listener disconnected")

    async def start(self):
        if not self._listener_task:
            self._stop_event.clear()
            self._listener_task = asyncio.create_task(self._setup_listener())

    async def stop(self):
        if self._listener_task:
            self._stop_event.set()
            await self._listener_task
            self._listener_task = None

    def publish_social_event(self, tenant_id: str, event_type: str, data: dict[str, Any]) -> bool:
        event = {
            "type": event_type,
            "tenant_id": tenant_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        from core.database import engine

        try:
            with engine.connect() as conn:
                conn.execute(
                    text("SELECT pg_notify('atom_social_events', :payload)"),
                    {"payload": json.dumps(event)},
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to publish via Postgres: {e}")
            if tenant_id in self._listeners:
                for cb in self._listeners[tenant_id]:
                    asyncio.create_task(cb(event))
            return False

    async def subscribe_tenant_events(
        self, tenant_id: str, callback: Callable[[dict[str, Any]], None]
    ):
        await self.start()
        if tenant_id not in self._listeners:
            self._listeners[tenant_id] = []
        self._listeners[tenant_id].append(callback)
        logger.info(f"Subscribed (Postgres) to tenant: {tenant_id}")
        try:
            while True:
                await asyncio.sleep(60)
        finally:
            if tenant_id in self._listeners and callback in self._listeners[tenant_id]:
                self._listeners[tenant_id].remove(callback)

    def get_connection_status(self) -> dict[str, Any]:
        return {
            "connected": self._listener_task is not None and not self._listener_task.done(),
            "mode": "postgres_notify",
        }


class RedisEventBus(EventBusInterface):
    """
    Event bus for broadcasting events via Redis Pub/Sub.
    High-performance, ideal for collab/chat features.
    """

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._listeners: dict[str, list[Callable]] = {}
        self._redis_client = None
        self._pubsub = None
        self._listener_task:Union[asyncio.Task, None] = None
        self._stop_event = asyncio.Event()

    async def _setup_listener(self):
        import redis.asyncio as redis

        try:
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self._pubsub = self._redis_client.pubsub()
            await self._pubsub.subscribe("atom_social_events")
            logger.info(f"✅ RedisEventBus listener connected to {self.redis_url.split('@')[-1]}")

            while not self._stop_event.is_set():
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message:
                    try:
                        event = json.loads(message["data"])
                        tenant_id = event.get("tenant_id")
                        if tenant_id in self._listeners:
                            for cb in self._listeners[tenant_id]:
                                asyncio.create_task(cb(event))
                    except Exception as e:
                        logger.error(f"Error handling Redis message: {e}")
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
        finally:
            if self._pubsub:
                await self._pubsub.unsubscribe()
            if self._redis_client:
                await self._redis_client.close()
            logger.info("RedisEventBus listener disconnected")

    async def start(self):
        if not self._listener_task:
            self._stop_event.clear()
            self._listener_task = asyncio.create_task(self._setup_listener())

    async def stop(self):
        if self._listener_task:
            self._stop_event.set()
            await self._listener_task
            self._listener_task = None

    def publish_social_event(self, tenant_id: str, event_type: str, data: dict[str, Any]) -> bool:
        event = {
            "type": event_type,
            "tenant_id": tenant_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        import redis

        r = None
        try:
            r = redis.from_url(self.redis_url)
            r.publish("atom_social_events", json.dumps(event))
            return True
        except Exception as e:
            logger.error(f"Failed to publish via Redis: {e}")
            return False
        finally:
            # Always close Redis connection to prevent leaks
            if r is not None:
                try:
                    r.close()
                except Exception:
                    pass

    async def subscribe_tenant_events(
        self, tenant_id: str, callback: Callable[[dict[str, Any]], None]
    ):
        await self.start()
        if tenant_id not in self._listeners:
            self._listeners[tenant_id] = []
        self._listeners[tenant_id].append(callback)
        logger.info(f"Subscribed (Redis) to tenant: {tenant_id}")
        try:
            while True:
                await asyncio.sleep(60)
        finally:
            if tenant_id in self._listeners and callback in self._listeners[tenant_id]:
                self._listeners[tenant_id].remove(callback)

    def get_connection_status(self) -> dict[str, Any]:
        return {
            "connected": self._listener_task is not None and not self._listener_task.done(),
            "mode": "redis_pubsub",
        }


# Helper methods (shortcuts)
def publish_social_post(
    tenant_id: str,
    post_id: str,
    author_type: str,
    author_id: str,
    post_type: str,
    content: str,
    metadata:Union[dict[str, Any], None] = None,
) -> bool:
    return get_agent_event_bus().publish_social_event(
        tenant_id,
        "social_post",
        {
            "post_id": post_id,
            "author_type": author_type,
            "author_id": author_id,
            "post_type": post_type,
            "content": content,
            "metadata": metadata or {},
        },
    )


def publish_social_reaction(
    tenant_id: str, post_id: str, user_id: str, emoji: str, action: str
) -> bool:
    return get_agent_event_bus().publish_social_event(
        tenant_id,
        "social_reaction",
        {"post_id": post_id, "user_id": user_id, "emoji": emoji, "action": action},
    )


def publish_social_alert(
    tenant_id: str,
    agent_id: str,
    alert_type: str,
    message: str,
    metadata:Union[dict[str, Any], None] = None,
) -> bool:
    return get_agent_event_bus().publish_social_event(
        tenant_id,
        "social_alert",
        {
            "agent_id": agent_id,
            "alert_type": alert_type,
            "message": message,
            "metadata": metadata or {},
        },
    )


# Existing single instance class (Legacy/Simple)
class AgentEventBus(PostgresEventBus):
    """Aliased for backward compatibility with existing code"""

    pass


# Global singleton
_event_bus_instance:Union[EventBusInterface, None] = None


def get_agent_event_bus() -> EventBusInterface:
    global _event_bus_instance
    if _event_bus_instance is None:
        # Priority: Dragonfly -> Social Event Bus -> Legacy Redis -> Upstash
        redis_url = (
            os.getenv("DRAGONFLY_URL")
            or os.getenv("SOCIAL_EVENT_BUS_URL")
            or os.getenv("REDIS_URL")
            or os.getenv("UPSTASH_REDIS_URL")
        )
        # Ensure we only use Redis if a real service is provided (exclude mock://)
        if redis_url and not redis_url.startswith("mock://"):
            _event_bus_instance = RedisEventBus(redis_url)
            mode_name = "Dragonfly" if os.getenv("DRAGONFLY_URL") else "Redis"
            logger.info(f"✅ Initializing AgentEventBus in {mode_name} mode (Higher Performance)")
        else:
            _event_bus_instance = PostgresEventBus()
            logger.info("ℹ️ Initializing AgentEventBus in Postgres mode (Fallback)")
    return _event_bus_instance

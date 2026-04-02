import logging
import json
from typing import Dict, Any, Callable, Optional
from datetime import datetime, timezone
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class FleetStateNotifier:
    """
    Redis pub/sub notifications for fleet state changes.
    Extends existing RedisEventBus pattern for fleet-specific channels.
    """

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis_client: Optional[redis.Redis] = None

    async def publish_blackboard_update(self, chain_id: str, updates: Dict[str, Any], agent_id: str, version: int):
        """Publish blackboard update to Redis pub/sub."""
        if not self._redis_client:
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)

        event = {
            "type": "blackboard_update",
            "chain_id": chain_id,
            "agent_id": agent_id,
            "version": version,
            "updates": updates,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        channel = f"fleet:blackboard:{chain_id}"
        try:
            await self._redis_client.publish(channel, json.dumps(event))
            logger.debug(f"Published blackboard update for chain {chain_id}, version {version}")
        except Exception as e:
            logger.error(f"Failed to publish blackboard update: {e}")

    async def subscribe_to_fleet(self, chain_id: str, callback: Callable):
        """Subscribe to blackboard updates for a specific fleet."""
        if not self._redis_client:
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)

        pubsub = self._redis_client.pubsub()
        channel = f"fleet:blackboard:{chain_id}"
        await pubsub.subscribe(channel)

        logger.info(f"Subscribed to fleet channel: {channel}")

        async def listener():
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        event = json.loads(message['data'])
                        await callback(event)
                    except Exception as e:
                        logger.error(f"Error processing fleet update: {e}")

        return listener

    async def close(self):
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.close()

# Singleton instance
_fleet_state_notifier_instance: Optional[FleetStateNotifier] = None

def get_fleet_state_notifier() -> Optional[FleetStateNotifier]:
    """Get singleton FleetStateNotifier instance."""
    global _fleet_state_notifier_instance
    if _fleet_state_notifier_instance is None:
        import os
        redis_url = os.getenv("DRAGONFLY_URL") or os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
        if redis_url:
            _fleet_state_notifier_instance = FleetStateNotifier(redis_url)
        else:
            logger.warning("No Redis URL configured, fleet state notifications disabled")
    return _fleet_state_notifier_instance

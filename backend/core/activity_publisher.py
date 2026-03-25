"""
Activity Publisher for Agent Status & Observability

Publishes real-time activity events for agents, enabling live monitoring
and status updates in the UI/Menu Bar.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ActivityPublisher:
    """
    Publishes agent activity events for real-time monitoring.
    
    Supports Redis pub/sub for streaming events to clients.
    Degrades gracefully if Redis is not available or enabled.
    """

    def __init__(self, redis_client: Optional[Any] = None, enabled: bool = True):
        """
        Initialize the publisher.
        
        Args:
            redis_client: Optional Redis client for pub/sub
            enabled: Whether activity publishing is globally enabled
        """
        self.redis = redis_client
        self.enabled = enabled and redis_client is not None
        
        if not self.enabled:
            logger.debug("ActivityPublisher initialized in NO-OP mode (Redis disabled or unavailable)")

    def publish_activity(
        self,
        tenant_id: str,
        agent_id: str,
        activity_type: str,
        state: str,
        session_key: str = 'main',
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish an activity event.
        
        Args:
            tenant_id: Tenant or Workspace ID
            agent_id: ID of the agent performing the activity
            activity_type: Type of activity (e.g., 'reasoning', 'skill-execution')
            state: Current state (e.g., 'thinking', 'working', 'idle')
            session_key: Logical session (default 'main')
            metadata: Additional activity context
            
        Returns:
            True if published successfully
        """
        if not self.enabled:
            return False

        try:
            event = {
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "session_key": session_key,
                "activity_type": activity_type,
                "state": state,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # Publish to Redis channel
            if self.redis:
                channel = f"activity:{tenant_id}:{agent_id}"
                self.redis.publish(channel, json.dumps(event))
                
                # Also publish to a general tenant channel for multi-agent views
                tenant_channel = f"activity:{tenant_id}:all"
                self.redis.publish(tenant_channel, json.dumps(event))

            return True
        except Exception as e:
            logger.error(f"Failed to publish activity: {e}")
            return False

    def publish_skill_execution(
        self,
        tenant_id: str,
        agent_id: str,
        skill_name: str,
        state: str,
        task_description: Optional[str] = None
    ) -> bool:
        """Helper for skill execution events."""
        return self.publish_activity(
            tenant_id=tenant_id,
            agent_id=agent_id,
            activity_type='skill-execution',
            state=state,
            metadata={
                'skill_name': skill_name,
                'task_description': task_description
            }
        )

    def publish_reasoning_activity(
        self,
        tenant_id: str,
        agent_id: str,
        phase: str,
        state: str = 'thinking'
    ) -> bool:
        """Helper for reasoning phase updates."""
        return self.publish_activity(
            tenant_id=tenant_id,
            agent_id=agent_id,
            activity_type='reasoning',
            state=state,
            metadata={'phase': phase}
        )

    def publish_episode_recording(
        self,
        tenant_id: str,
        agent_id: str,
        episode_id: str,
        status: str = 'completed'
    ) -> bool:
        """Helper for episode recording completion."""
        return self.publish_activity(
            tenant_id=tenant_id,
            agent_id=agent_id,
            activity_type='episode-recording',
            state=status,
            metadata={'episode_id': episode_id}
        )

def get_activity_publisher() -> ActivityPublisher:
    """
    Factory function for ActivityPublisher.
    Attempts to initialize Redis from global config.
    """
    try:
        from core.config import get_config
        config = get_config()
        
        if config.redis.enabled:
            import redis
            client = redis.from_url(config.redis.url)
            return ActivityPublisher(client, enabled=True)
    except Exception as e:
        logger.warning(f"Could not initialize ActivityPublisher with Redis: {e}")
    
    return ActivityPublisher(enabled=False)

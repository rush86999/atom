"""
Fleet progress service for real-time agent status tracking.

This service tracks individual agent status within fleets using Redis counters
with real-time progress queries and pub/sub updates for dashboard consumption.
Extends the PerformanceMetricsService pattern to track which agents are active,
completed, or failed within a fleet.
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field
import redis.asyncio as redis

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Models
# ============================================================================

class AgentStatus(str, Enum):
    """
    Agent execution status.

    Attributes:
        PENDING: Agent is queued but not yet started
        PROCESSING: Agent is actively executing a task
        COMPLETED: Agent completed task successfully
        FAILED: Agent task execution failed
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class FleetProgress(BaseModel):
    """
    Real-time fleet progress data for dashboard display.

    Attributes:
        chain_id: ID of the delegation chain (fleet)
        active_agents: List of agent IDs currently processing
        active_count: Number of active agents
        completed_count: Number of completed agents
        processing_count: Number of agents currently processing
        failed_count: Number of failed agents
        agent_details: Detailed status for up to 10 active agents
        timestamp: When progress data was captured
    """
    chain_id: str
    active_agents: List[str] = Field(default_factory=list)
    active_count: int = Field(ge=0, default=0)
    completed_count: int = Field(ge=0, default=0)
    processing_count: int = Field(ge=0, default=0)
    failed_count: int = Field(ge=0, default=0)
    agent_details: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============================================================================
# Service
# ============================================================================

class FleetProgressService:
    """
    Service for tracking real-time fleet progress with Redis counters.

    Tracks individual agent status within fleets for dashboard visualization.
    All operations are async and non-blocking to avoid impacting fleet execution.

    Redis key pattern:
    - fleet:{chain_id}:active_agents - Set of active agent IDs
    - fleet:{chain_id}:agent:{agent_id} - Hash with agent status details
    - fleet:{chain_id}:counters:processing - Counter for processing agents
    - fleet:{chain_id}:counters:completed - Counter for completed agents
    - fleet:{chain_id}:counters:failed - Counter for failed agents
    """

    # Key expiry (30 minutes)
    KEY_EXPIRY_SECONDS = 1800

    def __init__(self, db: Session, redis_url: Optional[str] = None):
        """
        Initialize fleet progress service.

        Args:
            db: Database session for persistence
            redis_url: Redis connection URL (optional, uses env if not provided)
        """
        self.db = db
        self.redis_url = redis_url
        self._redis_client: Optional[redis.Redis] = None

    async def _get_redis(self) -> Optional[redis.Redis]:
        """
        Get or create Redis connection.

        Returns:
            Redis client or None if connection fails
        """
        if self._redis_client is None:
            try:
                import os
                url = self.redis_url or os.getenv("DRAGONFLY_URL") or os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
                if url:
                    self._redis_client = redis.from_url(url, decode_responses=False)
                else:
                    logger.warning("No Redis URL configured, progress tracking disabled")
            except Exception as e:
                logger.error(f"Failed to create Redis client: {e}")
                return None
        return self._redis_client

    async def record_agent_start(
        self,
        chain_id: str,
        agent_id: str,
        task_description: str,
        trace_id: str
    ) -> None:
        """
        Record agent task start in Redis.

        Adds agent to active set, sets status hash, increments processing counter.

        Args:
            chain_id: Fleet delegation chain ID
            agent_id: Agent starting the task
            task_description: Task being executed
            trace_id: Distributed trace ID for correlation
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return

        try:
            pipe = redis_client.pipeline()

            # Add to active agents set
            pipe.sadd(f"fleet:{chain_id}:active_agents", agent_id)

            # Set agent status hash
            pipe.hset(
                f"fleet:{chain_id}:agent:{agent_id}",
                mapping={
                    "status": AgentStatus.PROCESSING.value,
                    "task": task_description[:200],  # Truncate for Redis
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "trace_id": trace_id
                }
            )

            # Increment processing counter
            pipe.incr(f"fleet:{chain_id}:counters:processing")

            # Set expiry (30 minutes)
            pipe.expire(f"fleet:{chain_id}:active_agents", self.KEY_EXPIRY_SECONDS)
            pipe.expire(f"fleet:{chain_id}:agent:{agent_id}", self.KEY_EXPIRY_SECONDS)
            pipe.expire(f"fleet:{chain_id}:counters:processing", self.KEY_EXPIRY_SECONDS)

            await pipe.execute()

            logger.debug(f"Recorded agent start: {agent_id} in fleet {chain_id}")

            # Publish progress update
            await self.publish_progress_update(
                chain_id=chain_id,
                agent_id=agent_id,
                status=AgentStatus.PROCESSING.value,
                progress_data={
                    "task": task_description[:200],
                    "trace_id": trace_id
                }
            )

        except Exception as e:
            logger.error(f"Failed to record agent start for {agent_id}: {e}")
            # Don't raise - progress tracking failure shouldn't break fleet execution

    async def record_agent_complete(
        self,
        chain_id: str,
        agent_id: str,
        result_summary: str,
        duration_ms: int
    ) -> None:
        """
        Record agent task completion in Redis.

        Removes from active set, updates status hash, decrements processing,
        increments completed counter.

        Args:
            chain_id: Fleet delegation chain ID
            agent_id: Agent completing the task
            result_summary: Brief result description
            duration_ms: Task execution duration in milliseconds
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return

        try:
            pipe = redis_client.pipeline()

            # Remove from active agents set
            pipe.srem(f"fleet:{chain_id}:active_agents", agent_id)

            # Update agent status hash
            pipe.hset(
                f"fleet:{chain_id}:agent:{agent_id}",
                mapping={
                    "status": AgentStatus.COMPLETED.value,
                    "result": result_summary[:200],
                    "duration_ms": str(duration_ms),
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }
            )

            # Decrement processing, increment completed
            pipe.incrby(f"fleet:{chain_id}:counters:processing", -1)
            pipe.incr(f"fleet:{chain_id}:counters:completed")

            # Set expiry
            pipe.expire(f"fleet:{chain_id}:agent:{agent_id}", self.KEY_EXPIRY_SECONDS)
            pipe.expire(f"fleet:{chain_id}:counters:processing", self.KEY_EXPIRY_SECONDS)
            pipe.expire(f"fleet:{chain_id}:counters:completed", self.KEY_EXPIRY_SECONDS)

            await pipe.execute()

            logger.debug(f"Recorded agent complete: {agent_id} in fleet {chain_id}")

            # Publish progress update
            await self.publish_progress_update(
                chain_id=chain_id,
                agent_id=agent_id,
                status=AgentStatus.COMPLETED.value,
                progress_data={
                    "result": result_summary[:200],
                    "duration_ms": duration_ms
                }
            )

        except Exception as e:
            logger.error(f"Failed to record agent complete for {agent_id}: {e}")

    async def record_agent_failed(
        self,
        chain_id: str,
        agent_id: str,
        error_message: str
    ) -> None:
        """
        Record agent task failure in Redis.

        Removes from active set, updates status hash with error,
        decrements processing, increments failed counter.

        Args:
            chain_id: Fleet delegation chain ID
            agent_id: Agent that failed
            error_message: Error description
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return

        try:
            pipe = redis_client.pipeline()

            # Remove from active agents set
            pipe.srem(f"fleet:{chain_id}:active_agents", agent_id)

            # Update agent status hash
            pipe.hset(
                f"fleet:{chain_id}:agent:{agent_id}",
                mapping={
                    "status": AgentStatus.FAILED.value,
                    "error": error_message[:500],
                    "failed_at": datetime.now(timezone.utc).isoformat()
                }
            )

            # Decrement processing, increment failed
            pipe.incrby(f"fleet:{chain_id}:counters:processing", -1)
            pipe.incr(f"fleet:{chain_id}:counters:failed")

            # Set expiry
            pipe.expire(f"fleet:{chain_id}:agent:{agent_id}", self.KEY_EXPIRY_SECONDS)
            pipe.expire(f"fleet:{chain_id}:counters:processing", self.KEY_EXPIRY_SECONDS)
            pipe.expire(f"fleet:{chain_id}:counters:failed", self.KEY_EXPIRY_SECONDS)

            await pipe.execute()

            logger.warning(f"Recorded agent failed: {agent_id} in fleet {chain_id}")

            # Publish progress update
            await self.publish_progress_update(
                chain_id=chain_id,
                agent_id=agent_id,
                status=AgentStatus.FAILED.value,
                progress_data={
                    "error": error_message[:500]
                }
            )

        except Exception as e:
            logger.error(f"Failed to record agent failed for {agent_id}: {e}")

    async def get_fleet_progress(self, chain_id: str) -> FleetProgress:
        """
        Get real-time fleet progress for dashboard.

        Queries active agents set, status counters, and agent details.

        Args:
            chain_id: Fleet delegation chain ID

        Returns:
            FleetProgress object with current progress data
        """
        redis_client = await self._get_redis()
        if not redis_client:
            # Return empty progress if Redis unavailable
            logger.warning(f"Redis unavailable for fleet {chain_id} progress")
            return FleetProgress(
                chain_id=chain_id,
                active_agents=[],
                active_count=0,
                completed_count=0,
                processing_count=0,
                failed_count=0,
                agent_details=[],
                timestamp=datetime.now(timezone.utc)
            )

        try:
            pipe = redis_client.pipeline()

            # Get active agents set
            pipe.smembers(f"fleet:{chain_id}:active_agents")

            # Get counters
            pipe.get(f"fleet:{chain_id}:counters:processing")
            pipe.get(f"fleet:{chain_id}:counters:completed")
            pipe.get(f"fleet:{chain_id}:counters:failed")

            results = await pipe.execute()

            # Decode active agent IDs
            active_agent_ids = []
            if results[0]:
                for aid in results[0]:
                    if isinstance(aid, bytes):
                        active_agent_ids.append(aid.decode('utf-8'))
                    else:
                        active_agent_ids.append(aid)

            # Decode counters
            def decode_counter(val):
                if val is None:
                    return 0
                if isinstance(val, bytes):
                    return int(val.decode('utf-8'))
                return int(val)

            processing_count = decode_counter(results[1])
            completed_count = decode_counter(results[2])
            failed_count = decode_counter(results[3])

            # Get details for each active agent (limit to 10 for performance)
            agent_details = []
            for agent_id in active_agent_ids[:10]:
                try:
                    detail = await redis_client.hgetall(f"fleet:{chain_id}:agent:{agent_id}")
                    if detail:
                        # Decode all values
                        decoded_detail = {}
                        for k, v in detail.items():
                            key = k.decode('utf-8') if isinstance(k, bytes) else k
                            value = v.decode('utf-8') if isinstance(v, bytes) else v
                            decoded_detail[key] = value

                        agent_details.append({
                            "agent_id": agent_id,
                            "status": decoded_detail.get("status", "unknown"),
                            "task": decoded_detail.get("task", ""),
                            "started_at": decoded_detail.get("started_at", ""),
                            "trace_id": decoded_detail.get("trace_id", ""),
                            "result": decoded_detail.get("result", ""),
                            "duration_ms": decoded_detail.get("duration_ms", ""),
                            "error": decoded_detail.get("error", "")
                        })
                except Exception as e:
                    logger.warning(f"Failed to get details for agent {agent_id}: {e}")
                    continue

            return FleetProgress(
                chain_id=chain_id,
                active_agents=active_agent_ids,
                active_count=len(active_agent_ids),
                completed_count=completed_count,
                processing_count=processing_count,
                failed_count=failed_count,
                agent_details=agent_details,
                timestamp=datetime.now(timezone.utc)
            )

        except Exception as e:
            logger.error(f"Failed to get fleet progress for chain {chain_id}: {e}")
            # Return empty progress on error
            return FleetProgress(
                chain_id=chain_id,
                active_agents=[],
                active_count=0,
                completed_count=0,
                processing_count=0,
                failed_count=0,
                agent_details=[],
                timestamp=datetime.now(timezone.utc)
            )

    async def publish_progress_update(
        self,
        chain_id: str,
        agent_id: str,
        status: str,
        progress_data: Dict[str, Any]
    ) -> None:
        """
        Publish progress update to Redis pub/sub.

        Enables real-time dashboard updates via WebSocket subscription.

        Args:
            chain_id: Fleet delegation chain ID
            agent_id: Agent with status change
            status: New agent status
            progress_data: Additional progress data (task, result, error, etc.)
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return

        try:
            update = {
                "chain_id": chain_id,
                "agent_id": agent_id,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **progress_data
            }

            await redis_client.publish(
                f"fleet:progress:{chain_id}",
                json.dumps(update)
            )

            logger.debug(f"Published progress update for {agent_id} in fleet {chain_id}")

        except Exception as e:
            logger.error(f"Failed to publish progress update: {e}")
            # Don't raise - pub/sub failure shouldn't break fleet execution

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None

# ============================================================================
# Singleton Pattern
# ============================================================================

_service_instance: Optional[FleetProgressService] = None

def get_fleet_progress_service(db: Session) -> FleetProgressService:
    """
    Get singleton FleetProgressService instance.

    Args:
        db: Database session

    Returns:
        FleetProgressService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = FleetProgressService(db)
    return _service_instance

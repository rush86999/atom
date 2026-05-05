"""
Sync Job Queue - Redis-based job queue for historical sync workers

Implements:
- Job enqueue/dequeue with priorities
- Job locking (prevent duplicate processing)
- Dead-letter queue for failed jobs
- Queue metrics for autoscaling

Architecture:
- Web machines enqueue jobs
- Worker machines poll and dequeue jobs
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from core.structured_logger import get_logger

logger = get_logger(__name__)


class JobPriority(Enum):
    """Job priority levels (higher number = higher priority)"""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 20


class SyncJobQueue:
    """
    Redis-based job queue for historical sync workers.
    """

    # Redis keys
    QUEUE_KEY = "sync:jobs:queue"
    PROCESSING_KEY = "sync:jobs:processing"
    DLQ_KEY = "sync:jobs:dlq"
    METRICS_KEY = "sync:jobs:metrics"

    # Lock timeout (seconds) - if worker crashes, lock expires
    LOCK_TIMEOUT = 300  # 5 minutes

    # Autoscaling thresholds (placeholders for Upstream)
    SCALE_UP_QUEUE_DEPTH = 5
    SCALE_DOWN_IDLE_MINUTES = 5

    def __init__(self):
        """Initialize job queue with direct Redis client."""
        self.redis_url = (
            os.getenv("DRAGONFLY_URL")
            or os.getenv("UPSTASH_REDIS_URL")
            or os.getenv("REDIS_URL")
            or ""
        )
        self.suspended = os.getenv("SUSPEND_REDIS", "false").lower() == "true"

        self._client = None
        self._async_client = None

        # Fly.io app name (for metrics/logging)
        self.fly_app_name = os.getenv("FLY_APP_NAME", "atom-upstream")

    @property
    def client(self):
        """Get synchronous Redis client"""
        if self._client is None and not self.suspended and self.redis_url:
            try:
                import urllib.parse as urlparse
                import redis

                parsed = urlparse.urlparse(self.redis_url)
                use_ssl = parsed.scheme == "rediss"

                self._client = redis.Redis(
                    host=parsed.hostname,
                    port=parsed.port or 6379,
                    password=parsed.password,
                    decode_responses=True,
                    ssl=use_ssl,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
            except Exception as e:
                logger.warning(f"Failed to create Redis client: {e}")

        return self._client

    @property
    async def async_client(self):
        """Get async Redis client"""
        if self._async_client is None and not self.suspended and self.redis_url:
            try:
                import redis.asyncio as aioredis

                self._async_client = await aioredis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
            except Exception as e:
                logger.warning(f"Failed to create async Redis client: {e}")

        return self._async_client

    async def enqueue(
        self, job_data: dict[str, Any], priority: JobPriority = JobPriority.NORMAL
    ) -> str:
        """Enqueue a job for processing."""
        if "job_id" not in job_data:
            raise ValueError("job_data must include 'job_id'")

        if "tenant_id" not in job_data:
            raise ValueError("job_data must include 'tenant_id'")

        # Add metadata
        job_data["enqueued_at"] = datetime.now(timezone.utc).isoformat()
        job_data["priority"] = priority.name

        # Calculate score: priority (higher first) + timestamp (earlier first)
        timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        score = (priority.value * 1000000) - timestamp_ms

        job_json = json.dumps(job_data)
        client = await self.async_client
        if client:
            await client.zadd(self.QUEUE_KEY, {job_json: score})
            logger.info(f"Enqueued job {job_data['job_id']} (priority: {priority.name})")
        else:
            logger.warning("Redis not available, job not enqueued")
            
        return job_data["job_id"]

    async def dequeue(self, timeout: int = 30) -> Optional[dict[str, Any]]:
        """Dequeue the next highest-priority job."""
        client = await self.async_client
        if not client:
            return None

        start_time = datetime.now(timezone.utc)
        while True:
            jobs = await client.zrange(self.QUEUE_KEY, 0, 0)
            if not jobs:
                if (datetime.now(timezone.utc) - start_time).total_seconds() >= timeout:
                    return None
                await asyncio.sleep(1)
                continue

            job_json = jobs[0]
            job_data = json.loads(job_json)
            await client.zrem(self.QUEUE_KEY, job_json)
            return job_data

    async def acquire_lock(self, job_id: str, worker_id: str, timeout: int = None) -> bool:
        """Acquire a lock on a job."""
        if timeout is None:
            timeout = self.LOCK_TIMEOUT

        lock_key = f"{self.PROCESSING_KEY}:{job_id}"
        client = await self.async_client
        if not client:
            return True

        lock_data = {
            "worker_id": worker_id,
            "locked_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=timeout)).isoformat(),
        }

        return await client.set(lock_key, json.dumps(lock_data), ex=timeout, nx=True)

    async def release_lock(self, job_id: str, worker_id: str) -> bool:
        """Release a lock on a job."""
        lock_key = f"{self.PROCESSING_KEY}:{job_id}"
        client = await self.async_client
        if not client:
            return True

        lock_data = await client.get(lock_key)
        if not lock_data:
            return False

        data = json.loads(lock_data)
        if data["worker_id"] != worker_id:
            return False

        await client.delete(lock_key)
        return True

    async def complete(self, job_id: str, worker_id: str) -> bool:
        """Mark job as completed."""
        return await self.release_lock(job_id, worker_id)

    async def get_queue_depth(self) -> int:
        """Get current queue depth."""
        client = await self.async_client
        if not client:
            return 0
        return await client.zcard(self.QUEUE_KEY)

    async def ensure_worker_running(self) -> bool:
        """
        Placeholder for Upstream. 
        In SaaS, this calls Fly Machines API to start a worker.
        """
        return True

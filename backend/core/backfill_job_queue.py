"""
Backfill Job Queue - Redis-based Background Processing

Non-blocking job queue for memory backfill operations.
Manages batch processing, retries, and TTL cleanup jobs.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

logger = logging.getLogger(__name__)


class BackfillJobType(str, Enum):
    """Types of backfill jobs."""
    ENTITY_TYPE_BACKFILL = "entity_type_backfill"
    NODE_MIGRATION = "node_migration"
    TTL_CLEANUP = "ttl_cleanup"
    BATCH_VALIDATION = "batch_validation"


class BackfillJobStatus(str, Enum):
    """Job execution status."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


class BackfillJobQueue:
    """
    Redis-based job queue for background backfill operations.

    Features:
    - Non-blocking job scheduling
    - Batch processing with configurable sizes
    - Exponential backoff retries
    - Dead letter queue for failed jobs
    - Job progress tracking
    - TTL-based job expiration

    Redis Keys:
    - job:queue:{tenant_id} - List of queued job IDs
    - job:data:{job_id} - Hash of job data
    - job:status:{job_id} - String status
    - job:progress:{job_id} - Hash of progress updates
    - job:retry:{job_id} - Retry count
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        max_retries: int = 4,
        retry_delays: List[int] = None  # Seconds: 60, 300, 900, 3600
    ):
        """
        Initialize backfill job queue.

        Args:
            redis_url: Redis connection URL
            max_retries: Maximum retry attempts before dead letter
            retry_delays: Exponential backoff delays in seconds
        """
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.retry_delays = retry_delays or [60, 300, 900, 3600]  # 1min, 5min, 15min, 1hr

        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    async def get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._pool = ConnectionPool.from_url(self.redis_url)
            self._client = redis.Redis(connection_pool=self._pool)
        return self._client

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()

    # ========================================================================
    # Job Scheduling
    # ========================================================================

    async def schedule_entity_type_backfill(
        self,
        tenant_id: str,
        slug: str,
        display_name: str,
        json_schema: Dict[str, Any],
        source: str,
        ttl_hours: int = 48
    ) -> str:
        """
        Schedule entity type backfill job.

        Args:
            tenant_id: Tenant UUID
            slug: Entity type slug
            display_name: Display name
            json_schema: JSON schema
            source: Ingestion source
            ttl_hours: Time to live before expiration

        Returns:
            Job ID
        """
        job_id = f"entity_type:{tenant_id}:{slug}:{datetime.utcnow().timestamp()}"

        job_data = {
            "job_type": BackfillJobType.ENTITY_TYPE_BACKFILL,
            "tenant_id": tenant_id,
            "slug": slug,
            "display_name": display_name,
            "json_schema": json.dumps(json_schema),
            "source": source,
            "ttl_hours": ttl_hours,
            "created_at": datetime.utcnow().isoformat()
        }

        await self._schedule_job(job_id, job_data, tenant_id)
        return job_id

    async def schedule_node_migration(
        self,
        tenant_id: str,
        workspace_id: str,
        entity_type_slug: str,
        batch_size: int = 1000
    ) -> str:
        """
        Schedule node migration job.

        Args:
            tenant_id: Tenant UUID
            workspace_id: Workspace UUID
            entity_type_slug: Entity type to migrate
            batch_size: Batch size for migration

        Returns:
            Job ID
        """
        job_id = f"node_migration:{tenant_id}:{workspace_id}:{entity_type_slug}:{datetime.utcnow().timestamp()}"

        job_data = {
            "job_type": BackfillJobType.NODE_MIGRATION,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "entity_type_slug": entity_type_slug,
            "batch_size": batch_size,
            "created_at": datetime.utcnow().isoformat()
        }

        await self._schedule_job(job_id, job_data, tenant_id)
        return job_id

    async def schedule_ttl_cleanup(
        self,
        tenant_id: str,
        interval_hours: int = 1
    ) -> str:
        """
        Schedule TTL cleanup job.

        Args:
            tenant_id: Tenant UUID
            interval_hours: Run interval in hours

        Returns:
            Job ID
        """
        job_id = f"ttl_cleanup:{tenant_id}:{datetime.utcnow().timestamp()}"

        job_data = {
            "job_type": BackfillJobType.TTL_CLEANUP,
            "tenant_id": tenant_id,
            "interval_hours": interval_hours,
            "created_at": datetime.utcnow().isoformat()
        }

        await self._schedule_job(job_id, job_data, tenant_id)
        return job_id

    async def _schedule_job(self, job_id: str, job_data: Dict[str, Any], tenant_id: str):
        """Schedule job in Redis queue."""
        client = await self.get_client()

        # Store job data
        await client.hset(f"job:data:{job_id}", mapping=job_data)

        # Set initial status
        await client.set(f"job:status:{job_id}", BackfillJobStatus.QUEUED.value)

        # Initialize retry count
        await client.set(f"job:retry:{job_id}", "0")

        # Add to tenant queue
        await client.rpush(f"job:queue:{tenant_id}", job_id)

        logger.info(f"Scheduled job {job_id} for tenant {tenant_id}")

    # ========================================================================
    # Job Status and Progress
    # ========================================================================

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get job status and metadata.

        Args:
            job_id: Job ID

        Returns:
            Job status dictionary
        """
        client = await self.get_client()

        status = await client.get(f"job:status:{job_id}")
        data = await client.hgetall(f"job:data:{job_id}")
        progress = await client.hgetall(f"job:progress:{job_id}")
        retry_count = await client.get(f"job:retry:{job_id}")

        return {
            "job_id": job_id,
            "status": status.decode() if status else "unknown",
            "data": {k.decode(): v.decode() for k, v in data.items()},
            "progress": {k.decode(): v.decode() for k, v in progress.items()},
            "retry_count": int(retry_count) if retry_count else 0
        }

    async def update_job_progress(
        self,
        job_id: str,
        progress: float,
        message: Optional[str] = None
    ):
        """
        Update job progress.

        Args:
            job_id: Job ID
            progress: Progress percentage (0-100)
            message: Optional progress message
        """
        client = await self.get_client()

        await client.hset(
            f"job:progress:{job_id}",
            mapping={
                "progress": str(progress),
                "message": message or "",
                "updated_at": datetime.utcnow().isoformat()
            }
        )

    async def set_job_status(self, job_id: str, status: BackfillJobStatus):
        """Set job status."""
        client = await self.get_client()
        await client.set(f"job:status:{job_id}", status.value)

    # ========================================================================
    # Job Processing and Retries
    # ========================================================================

    async def process_job_with_retry(self, job_id: str):
        """
        Process job with automatic retry logic.

        Args:
            job_id: Job ID
        """
        client = await self.get_client()

        retry_count = int(await client.get(f"job:retry:{job_id}") or 0)

        try:
            await self.set_job_status(job_id, BackfillJobStatus.PROCESSING)

            # Process job (implementation-specific)
            await self._execute_job(job_id)

            # Mark completed
            await self.set_job_status(job_id, BackfillJobStatus.COMPLETED)
            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")

            if retry_count < self.max_retries:
                # Schedule retry
                await self.set_job_status(job_id, BackfillJobStatus.RETRYING)
                await client.incr(f"job:retry:{job_id}")

                # Calculate delay
                delay = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]

                # Schedule retry
                await client.expire(f"job:data:{job_id}", delay)
                logger.info(f"Job {job_id} will retry in {delay}s (attempt {retry_count + 1}/{self.max_retries})")

            else:
                # Move to dead letter queue
                await self.set_job_status(job_id, BackfillJobStatus.DEAD_LETTER)
                logger.error(f"Job {job_id} moved to dead letter queue after {self.max_retries} retries")

    async def _execute_job(self, job_id: str):
        """
        Execute job (implementation-specific).

        This is a placeholder - actual implementation would call
        MemoryBackfillService methods to execute the job.
        """
        # TODO: Implement job execution logic
        # This would call MemoryBackfillService based on job type
        pass

    # ========================================================================
    # Queue Management
    # ========================================================================

    async def get_next_job(self, tenant_id: str) -> Optional[str]:
        """
        Get next job from tenant queue.

        Args:
            tenant_id: Tenant UUID

        Returns:
            Job ID or None
        """
        client = await self.get_client()

        # Blocking pop with timeout
        job_id = await client.blpop(f"job:queue:{tenant_id}", timeout=5)

        return job_id[1].decode() if job_id else None

    async def get_queue_size(self, tenant_id: str) -> int:
        """Get number of jobs in tenant queue."""
        client = await self.get_client()
        return await client.llen(f"job:queue:{tenant_id}")

    async def clear_queue(self, tenant_id: str):
        """Clear all jobs from tenant queue."""
        client = await self.get_client()
        await client.delete(f"job:queue:{tenant_id}")
        logger.info(f"Cleared queue for tenant {tenant_id}")


# ============================================================================
# Singleton Instance
# ============================================================================

_job_queue: Optional[BackfillJobQueue] = None


def get_backfill_job_queue() -> BackfillJobQueue:
    """Get singleton backfill job queue instance."""
    global _job_queue
    if _job_queue is None:
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _job_queue = BackfillJobQueue(redis_url=redis_url)
    return _job_queue

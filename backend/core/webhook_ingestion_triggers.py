from __future__ import annotations
"""
Webhook Ingestion Queue Service - Coordinates webhook-triggered ingestion jobs

Manages Redis-backed queue for asynchronous webhook processing with tenant isolation.
Webhook handlers enqueue jobs for background processing to avoid timeout issues.

Key features:
- Redis-backed job queue for webhook payload processing
- Tenant extraction from webhook payloads
- Background worker coordination
- Fallback to sync processing if Redis unavailable
- Queue monitoring and stuck job cleanup
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Union

import redis

from core.database import SessionLocal
from core.ingestion_pipeline import IngestionPipelineService
from core.models import Workspace
from core.structured_logger import get_logger
from core.usage_tracking_service import UsageTrackingService

logger = get_logger(__name__)


class WebhookIngestionQueue:
    """
    Queue and coordinate webhook-triggered ingestion jobs.

    Manages Redis-backed queue for asynchronous webhook processing.
    Extracts tenant_id from webhook payloads and enqueues background jobs.
    Falls back to sync processing if Redis unavailable.

    All operations enforce tenant_id isolation for security.
    """

    def __init__(self):
        """Initialize webhook ingestion queue with Redis client."""
        redis_url = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
        self.redis_client = redis.from_url(redis_url, decode_responses=True) if redis_url else None
        self.queue_key = "ingestion:webhook:jobs"

        if not self.redis_client:
            logger.warning("Redis unavailable - webhook ingestion will process synchronously")

    async def enqueue_ingestion_job(
        self,
        tenant_id: str,
        integration_id: str,
        trigger_type: str,
        payload: dict[str, Any],
        source_connection_id: Union[str, None] = None,
    ) -> str:
        """
        Enqueue ingestion job for background processing.

        Creates job dict with unique ID, timestamps, and payload data.
        Pushes to Redis list for background worker processing.

        Args:
            tenant_id: Tenant/workspace ID for multi-tenant isolation
            integration_id: Integration identifier (e.g., "slack", "salesforce")
            trigger_type: Trigger type ("webhook", "scheduled", "manual")
            payload: Webhook payload data
            source_connection_id: Optional UserConnection ID

        Returns:
            Job ID (UUID string) for tracking

        CRITICAL: Tenant_id is enforced for multi-tenant security.
        """
        job_id = str(uuid.uuid4())

        job_data = {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "trigger_type": trigger_type,
            "payload": payload,
            "source_connection_id": source_connection_id,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }

        # Serialize to JSON
        try:
            job_json = json.dumps(job_data)
        except (TypeError, ValueError) as e:
            logger.error(
                "Failed to serialize webhook job",
                job_id=job_id,
                integration_id=integration_id,
                tenant_id=tenant_id,
                error=str(e),
            )
            return job_id  # Return ID for error tracking

        # Push to Redis queue
        if self.redis_client:
            try:
                self.redis_client.lpush(self.queue_key, job_json)
                logger.info(
                    "Enqueued webhook ingestion job",
                    job_id=job_id,
                    integration_id=integration_id,
                    tenant_id=tenant_id,
                    queue_depth=await self.get_queue_depth(),
                )
            except redis.RedisError as e:
                logger.warning(
                    "Redis push failed - processing synchronously",
                    job_id=job_id,
                    integration_id=integration_id,
                    tenant_id=tenant_id,
                    error=str(e),
                )
                # Fallback to sync processing
                await self.process_webhook_job(job_data)
        else:
            # Fallback to sync processing
            logger.info(
                "Processing webhook job synchronously (Redis unavailable)",
                job_id=job_id,
                integration_id=integration_id,
                tenant_id=tenant_id,
            )
            await self.process_webhook_job(job_data)

        return job_id

    async def process_webhook_job(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """
        Process webhook payload through ingestion pipeline.

        Extracts tenant_id, creates IngestionPipelineService, and calls
        process_webhook_payload() for data extraction and GraphRAG ingestion.

        Args:
            job_data: Job dict with tenant_id, integration_id, payload, etc.

        Returns:
            Dict with processing results:
                - success: bool
                - job_id: str
                - tenant_id: str
                - integration_id: str
                - records_processed: int
                - entities_extracted: int
                - relationships_extracted: int
                - error: str (if failed)

        CRITICAL: Tenant_id is enforced for multi-tenant security.
        """
        import sys
        print(f"[FATAL_DEBUG] === process_webhook_job ENTERED === job_id={job_data.get('job_id', 'unknown')[:8]}", file=sys.stderr, flush=True)

        try:
            job_id = job_data.get("job_id", "unknown")
            tenant_id = job_data.get("tenant_id")
            integration_id = job_data.get("integration_id")
            payload = job_data.get("payload", {})

            print(f"[FATAL_DEBUG] Parsed job_data: job_id={job_id[:8]}, tenant={tenant_id[:8] if tenant_id else None}, integration={integration_id}", file=sys.stderr, flush=True)

            start_time = datetime.now(timezone.utc)

            logger.info(
                "Processing webhook job",
                job_id=job_id,
                integration_id=integration_id,
                tenant_id=tenant_id,
            )
        except Exception as e:
            print(f"[FATAL_DEBUG] CRASH IN VERY FIRST BLOCK: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()
            raise

        # Check quota before processing
        usage_tracker = UsageTrackingService(tenant_id=tenant_id)
        try:
            payload_size = len(str(payload))  # Estimate payload size
            estimated_acu = self._estimate_webhook_acu(integration_id, payload_size)

            quota_check = await usage_tracker.check_quota_before_job(
                integration_id=integration_id, estimated_acu=estimated_acu
            )

            if not quota_check["allowed"]:
                logger.warning(
                    "Quota exceeded - rejecting webhook job",
                    job_id=job_id,
                    integration_id=integration_id,
                    tenant_id=tenant_id,
                    estimated_acu=estimated_acu,
                    remaining_quota=quota_check["remaining_quota"],
                    reason=quota_check["reason"],
                )
                return {
                    "success": False,
                    "status": "rejected",
                    "job_id": job_id,
                    "tenant_id": tenant_id,
                    "integration_id": integration_id,
                    "error": f"Quota exceeded: {quota_check['reason']}",
                    "remaining_quota": quota_check["remaining_quota"],
                    "estimated_acu": estimated_acu,
                }
        except Exception as quota_err:
            # Log quota check error but continue processing (fail open)
            logger.warning(
                "Quota check failed - proceeding with job",
                job_id=job_id,
                integration_id=integration_id,
                tenant_id=tenant_id,
                error=str(quota_err),
            )
        finally:
            # Close UsageTrackingService to prevent DB leaks
            usage_tracker.close()

        try:
            # Resolve actual workspace UUID for this tenant
            # workspace_id != tenant_id - they are different tables/UUIDs
            # Use context manager to ensure proper cleanup and avoid DB leaks
            # CRITICAL: db_session must remain open for IngestionPipelineService to persist entities
            with SessionLocal() as db_session:
                workspace = db_session.query(Workspace).filter(
                    Workspace.tenant_id == tenant_id
                ).first()

                if not workspace:
                    logger.error(
                        "Workspace not found for tenant",
                        tenant_id=tenant_id,
                        job_id=job_id,
                    )
                    return {
                        "success": False,
                        "status": "failed",
                        "job_id": job_id,
                        "tenant_id": tenant_id,
                        "integration_id": integration_id,
                        "error": f"Workspace not found for tenant {tenant_id}",
                    }

                workspace_id = str(workspace.id)
                print(f"[FATAL_DEBUG] Resolved workspace_id={workspace_id[:8]} for tenant={tenant_id[:8]}", file=sys.stderr, flush=True)

                # Create ingestion pipeline service with correct workspace_id AND db session
                # CRITICAL: db parameter is required for persisting discovered_entities
                pipeline = IngestionPipelineService(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    db=db_session,  # Pass db session for entity persistence
                )

                # Process webhook payload through pipeline
                result = await pipeline.process_webhook_payload(
                    integration_id=integration_id,
                    webhook_data=payload,
                    source_connection_id=job_data.get("source_connection_id"),
                )

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            logger.info(
                "Webhook job completed",
                job_id=job_id,
                integration_id=integration_id,
                tenant_id=tenant_id,
                duration_seconds=duration,
                result=result,
            )

            return {
                "success": True,
                "job_id": job_id,
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "duration_seconds": duration,
                **result,
            }

        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_msg = f"Webhook job processing failed: {e}"

            logger.error(
                error_msg,
                job_id=job_id,
                integration_id=integration_id,
                tenant_id=tenant_id,
                duration_seconds=duration,
                error=str(e),
                exc_info=True,  # Include full traceback for debugging
            )

            return {
                "success": False,
                "job_id": job_id,
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "error": error_msg,
                "duration_seconds": duration,
            }

    async def get_queue_depth(self) -> int:
        """
        Get current queue depth for monitoring.

        Returns:
            Number of jobs currently in queue (0 if Redis unavailable)
        """
        if not self.redis_client:
            return 0

        try:
            return self.redis_client.llen(self.queue_key)
        except redis.RedisError as e:
            logger.warning(f"Failed to get queue depth: {e}")
            return 0

    async def get_pending_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get list of pending job IDs from queue.

        Args:
            limit: Maximum number of jobs to return (default 100)

        Returns:
            List of job dicts with job_id, tenant_id, integration_id, enqueued_at
        """
        if not self.redis_client:
            return []

        try:
            # Get job JSONs from queue (without removing)
            job_jsons = self.redis_client.lrange(self.queue_key, 0, limit - 1)

            jobs = []
            for job_json in job_jsons:
                try:
                    job_data = json.loads(job_json)
                    jobs.append(
                        {
                            "job_id": job_data.get("job_id"),
                            "tenant_id": job_data.get("tenant_id"),
                            "integration_id": job_data.get("integration_id"),
                            "enqueued_at": job_data.get("enqueued_at"),
                        }
                    )
                except (json.JSONDecodeError, KeyError):
                    continue

            return jobs

        except redis.RedisError as e:
            logger.warning(f"Failed to get pending jobs: {e}")
            return []

    async def clear_stuck_jobs(self, max_age_minutes: int = 60) -> int:
        """
        Remove stuck jobs older than specified age.

        Scans queue for jobs enqueued more than max_age_minutes ago
        and removes them to prevent queue backlog.

        Args:
            max_age_minutes: Maximum job age in minutes (default 60)

        Returns:
            Number of jobs cleared
        """
        if not self.redis_client:
            return 0

        try:
            # Get all jobs from queue
            job_jsons = self.redis_client.lrange(self.queue_key, 0, -1)

            cleared_count = 0
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)

            for job_json in job_jsons:
                try:
                    job_data = json.loads(job_json)
                    enqueued_at_str = job_data.get("enqueued_at")

                    if not enqueued_at_str:
                        continue

                    enqueued_at = datetime.fromisoformat(enqueued_at_str)

                    # Remove if older than cutoff
                    if enqueued_at < cutoff_time:
                        # Remove from queue (LREM removes 1 occurrence)
                        self.redis_client.lrem(self.queue_key, 1, job_json)
                        cleared_count += 1

                        logger.warning(
                            "Cleared stuck webhook job",
                            job_id=job_data.get("job_id"),
                            integration_id=job_data.get("integration_id"),
                            tenant_id=job_data.get("tenant_id"),
                            enqueued_at=enqueued_at_str,
                            age_minutes=max_age_minutes,
                        )

                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

            if cleared_count > 0:
                logger.info(
                    "Cleared stuck webhook jobs",
                    cleared_count=cleared_count,
                    max_age_minutes=max_age_minutes,
                )

            return cleared_count

        except redis.RedisError as e:
            logger.warning(f"Failed to clear stuck jobs: {e}")
            return 0

    async def dequeue_job(self) -> Union[dict[str, Any], None]:
        """
        Dequeue next job from queue for processing.

        Removes and returns the next job from the queue (RPOP).

        Returns:
            Job dict or None if queue empty

        Note: This is used by background worker processes.
        """
        import sys
        if not self.redis_client:
            print("[FATAL_DEBUG] dequeue_job: NO REDIS CLIENT", file=sys.stderr, flush=True)
            return None

        try:
            # Blocking pop from right side of queue (BRPOP with timeout=0)
            # For non-blocking, use RPOP
            job_json = self.redis_client.rpop(self.queue_key)

            if not job_json:
                return None

            print(f"[FATAL_DEBUG] dequeue_job: POPPED JOB, json_len={len(job_json)}", file=sys.stderr, flush=True)
            return json.loads(job_json)

        except (redis.RedisError, json.JSONDecodeError) as e:
            print(f"[FATAL_DEBUG] dequeue_job ERROR: {e}", file=sys.stderr, flush=True)
            logger.warning(f"Failed to dequeue job: {e}")
            return None

    def _estimate_webhook_acu(self, integration_id: str, payload_size: int) -> float:
        """
        Estimate ACU consumption for webhook job.

        Args:
            integration_id: Integration identifier
            payload_size: Payload size in bytes

        Returns:
            Estimated ACU consumption
        """
        # Base ACU: 5 ACU
        # Payload size factor: 0.001 ACU per byte
        # Integration complexity multiplier
        complexity_multipliers = {
            "slack": 1.0,
            "salesforce": 1.2,
            "hubspot": 1.1,
            "zoho_crm": 1.1,
            "zoho_desk": 1.1,
            "zoho_books": 1.0,
            "gmail": 0.8,
            "notion": 1.0,
            "asana": 1.1,
            "trello": 1.0,
            "jira": 1.2,
            "github": 0.9,
            "gitlab": 1.0,
            "pipedrive": 1.1,
            "mailchimp": 1.0,
            "stripe": 0.9,
            "shopify": 1.1,
        }
        multiplier = complexity_multipliers.get(integration_id, 1.0)
        return (5.0 + (payload_size * 0.001)) * multiplier

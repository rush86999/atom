"""
Task Queue Manager for Background Jobs

Provides RQ (Redis Queue) based background task processing for scheduled jobs.
Supports social media posting, workflow execution, and other async tasks.
"""

import logging
import os
import redis
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

try:
    from rq import Queue
    from rq.job import Job
    RQ_AVAILABLE = True
except ImportError:
    RQ_AVAILABLE = False
    Queue = None
    Job = None

logger = logging.getLogger(__name__)


class TaskQueueManager:
    """
    Manager for RQ-based background task queues.

    Provides methods for enqueueing, monitoring, and managing background jobs.
    """

    def __init__(self):
        """Initialize Redis connection and queues"""
        self._redis_conn = None
        self._queues = {}
        self._enabled = False

        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection and create queues"""
        if not RQ_AVAILABLE:
            logger.warning("RQ not available. Install with: pip install rq")
            return

        try:
            # Get Redis configuration from environment
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", 6379))
            redis_db = int(os.getenv("REDIS_DB", 0))
            redis_password = os.getenv("REDIS_PASSWORD", None)

            # Parse Redis URL if provided
            if redis_url and "://" in redis_url:
                # Use URL-based connection
                self._redis_conn = redis.from_url(
                    redis_url,
                    password=redis_password,
                    decode_responses=False
                )
            else:
                # Use host/port-based connection
                self._redis_conn = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password,
                    decode_responses=False
                )

            # Test connection
            self._redis_conn.ping()
            self._enabled = True

            # Create queues for different job types
            self._queues = {
                "social_media": Queue("social_media", connection=self._redis_conn),
                "workflows": Queue("workflows", connection=self._redis_conn),
                "default": Queue("default", connection=self._redis_conn),
            }

            logger.info("✓ Task queue initialized with Redis")

        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize task queue: {e}")
            self._enabled = False

    @property
    def enabled(self) -> bool:
        """Check if task queue is enabled"""
        return self._enabled

    def get_queue(self, queue_name: str = "default") -> Optional[Queue]:
        """Get a specific queue by name"""
        return self._queues.get(queue_name)

    def enqueue_job(
        self,
        func: Callable,
        queue_name: str = "default",
        *args,
        timeout: int = 300,
        **kwargs
    ) -> Optional[str]:
        """
        Enqueue a job for background processing.

        Args:
            func: The function to execute
            queue_name: Name of the queue (default, social_media, workflows)
            *args: Positional arguments for the function
            timeout: Job timeout in seconds (default: 300)
            **kwargs: Keyword arguments for the function

        Returns:
            Job ID if successful, None if queue is disabled
        """
        if not self._enabled:
            logger.warning("Task queue is disabled. Job not enqueued.")
            return None

        try:
            queue = self.get_queue(queue_name)
            if not queue:
                logger.error(f"Queue '{queue_name}' not found")
                return None

            job = queue.enqueue(
                func,
                *args,
                job_timeout=timeout,
                **kwargs
            )

            logger.info(f"Job {job.id} enqueued in {queue_name}")
            return job.id

        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            return None

    def enqueue_scheduled_job(
        self,
        func: Callable,
        scheduled_time: datetime,
        queue_name: str = "default",
        *args,
        timeout: int = 300,
        **kwargs
    ) -> Optional[str]:
        """
        Enqueue a job for scheduled execution at a specific time.

        Args:
            func: The function to execute
            scheduled_time: When to execute the job
            queue_name: Name of the queue
            *args: Positional arguments for the function
            timeout: Job timeout in seconds
            **kwargs: Keyword arguments for the function

        Returns:
            Job ID if successful, None if queue is disabled
        """
        if not self._enabled:
            logger.warning("Task queue is disabled. Scheduled job not enqueued.")
            return None

        try:
            queue = self.get_queue(queue_name)
            if not queue:
                logger.error(f"Queue '{queue_name}' not found")
                return None

            job = queue.enqueue_at(
                scheduled_time,
                func,
                *args,
                job_timeout=timeout,
                **kwargs
            )

            logger.info(f"Scheduled job {job.id} for {scheduled_time}")
            return job.id

        except Exception as e:
            logger.error(f"Failed to enqueue scheduled job: {e}")
            return None

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a job.

        Args:
            job_id: The job ID

        Returns:
            Dictionary with job status information
        """
        if not self._enabled or not Job:
            return {"error": "Task queue is disabled"}

        try:
            job = Job.fetch(job_id, connection=self._redis_conn)

            return {
                "id": job.id,
                "status": job.get_status(),
                "created_at": job.created_at,
                "enqueued_at": job.enqueued_at,
                "started_at": job.started_at,
                "ended_at": job.ended_at,
                "result": job.result,
                "exc_info": job.exc_info,
                "is_finished": job.is_finished,
                "is_queued": job.is_queued,
                "is_started": job.is_started,
                "is_failed": job.is_failed,
            }

        except Exception as e:
            logger.error(f"Failed to fetch job {job_id}: {e}")
            return {"error": str(e)}

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a queued job.

        Args:
            job_id: The job ID

        Returns:
            True if canceled, False otherwise
        """
        if not self._enabled or not Job:
            logger.warning("Task queue is disabled. Cannot cancel job.")
            return False

        try:
            job = Job.fetch(job_id, connection=self._redis_conn)

            if job.is_queued:
                job.cancel()
                logger.info(f"Job {job_id} canceled")
                return True
            else:
                logger.warning(f"Job {job_id} cannot be canceled (status: {job.get_status()})")
                return False

        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    def get_queue_info(self, queue_name: str = "default") -> Dict[str, Any]:
        """
        Get information about a queue.

        Args:
            queue_name: Name of the queue

        Returns:
            Dictionary with queue information
        """
        if not self._enabled:
            return {"error": "Task queue is disabled"}

        try:
            queue = self.get_queue(queue_name)
            if not queue:
                return {"error": f"Queue '{queue_name}' not found"}

            return {
                "name": queue.name,
                "count": len(queue),
                "failed_job_count": queue.failed_job_registry.count,
                "finished_job_count": queue.finished_job_registry.count,
                "started_job_count": queue.started_job_registry.count,
                "deferred_job_count": queue.deferred_job_registry.count,
            }

        except Exception as e:
            logger.error(f"Failed to get queue info: {e}")
            return {"error": str(e)}

    def get_all_queues_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all queues.

        Returns:
            Dictionary with queue names as keys and queue info as values
        """
        if not self._enabled:
            return {"error": "Task queue is disabled"}

        queues_info = {}
        for queue_name in self._queues.keys():
            queues_info[queue_name] = self.get_queue_info(queue_name)

        return queues_info


# Global instance
_task_queue_manager = None


def get_task_queue() -> TaskQueueManager:
    """Get the global task queue manager instance"""
    global _task_queue_manager

    if _task_queue_manager is None:
        _task_queue_manager = TaskQueueManager()

    return _task_queue_manager


# Convenience functions for social media scheduling
def enqueue_scheduled_post(
    post_id: str,
    platforms: List[str],
    text: str,
    scheduled_for: datetime,
    media_urls: Optional[List[str]] = None,
    link_url: Optional[str] = None,
    user_id: Optional[str] = None
) -> Optional[str]:
    """
    Enqueue a scheduled social media post.

    Convenience function for social media scheduling.

    Args:
        post_id: Unique identifier for the post
        platforms: List of platform names (twitter, linkedin, facebook)
        text: Post content
        scheduled_for: When to publish the post
        media_urls: Optional list of media URLs
        link_url: Optional link to include
        user_id: User ID for tracking

    Returns:
        Job ID if successful, None otherwise
    """
    from workers.social_media_worker import process_scheduled_post

    task_queue = get_task_queue()

    return task_queue.enqueue_scheduled_job(
        func=process_scheduled_post,
        scheduled_time=scheduled_for,
        queue_name="social_media",
        post_id=post_id,
        platforms=platforms,
        text=text,
        media_urls=media_urls,
        link_url=link_url,
        user_id=user_id,
        timeout=300
    )

"""
Supervised Queue Service

Manages queue for SUPERVISED agent executions when users are unavailable.
Executions are queued and auto-executed when users return online.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentRegistry,
    QueueStatus,
    SupervisedExecutionQueue,
    User,
    UserActivity,
    UserActivitySession,
    UserState,
)

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_QUEUE_EXPIRY_HOURS = 24
MAX_QUEUE_ATTEMPTS = 3
QUEUE_PROCESS_BATCH_SIZE = 10


class SupervisedQueueService:
    """
    Manage queue for SUPERVISED agent executions when users unavailable.

    When a SUPERVISED agent triggers but the user is offline, the execution
    is queued and automatically executed when the user returns online.

    Queue States:
    - pending: Waiting for user to become available
    - executing: Currently being executed
    - completed: Execution finished successfully
    - failed: Execution failed after max attempts
    - cancelled: Cancelled by user
    """

    def __init__(self, db: Session):
        self.db = db

    async def enqueue_execution(
        self,
        agent_id: str,
        user_id: str,
        trigger_type: str,
        execution_context: Dict[str, Any],
        priority: int = 0,
        expires_at: Optional[datetime] = None,
        supervisor_type: str = "user"
    ) -> SupervisedExecutionQueue:
        """
        Add supervised agent execution to queue.

        Args:
            agent_id: Agent to execute
            user_id: User who owns the agent
            trigger_type: "automated" or "manual"
            execution_context: Full execution context
            priority: Higher priority = executed first (default 0)
            expires_at: Optional expiry time (default 24 hours)
            supervisor_type: "user" or "autonomous_agent"

        Returns:
            Created SupervisedExecutionQueue record
        """
        # Set default expiry if not provided
        if not expires_at:
            expires_at = datetime.utcnow() + timedelta(hours=DEFAULT_QUEUE_EXPIRY_HOURS)

        # Create queue entry
        queue_entry = SupervisedExecutionQueue(
            id=f"queue_{uuid.uuid4()}",
            agent_id=agent_id,
            user_id=user_id,
            trigger_type=trigger_type,
            execution_context=execution_context,
            status=QueueStatus.pending,
            supervisor_type=supervisor_type,
            priority=priority,
            max_attempts=MAX_QUEUE_ATTEMPTS,
            attempt_count=0,
            expires_at=expires_at
        )

        self.db.add(queue_entry)
        self.db.commit()
        self.db.refresh(queue_entry)

        logger.info(
            f"Queued supervised execution: {queue_entry.id} "
            f"(agent={agent_id}, user={user_id}, priority={priority})"
        )

        return queue_entry

    async def process_pending_queues(
        self,
        limit: int = QUEUE_PROCESS_BATCH_SIZE
    ) -> List[SupervisedExecutionQueue]:
        """
        Process pending queue entries for available users.

        Called by background worker when users come online.

        Args:
            limit: Maximum number of queue entries to process

        Returns:
            List of processed queue entries
        """
        processed = []

        try:
            # Find users who are available (online or away)
            available_user_ids = self._get_available_user_ids()

            if not available_user_ids:
                logger.debug("No available users to process queues for")
                return processed

            # Find pending queues for available users
            # Order by priority (highest first) and created_at (oldest first)
            pending_queues = self.db.query(SupervisedExecutionQueue).filter(
                SupervisedExecutionQueue.user_id.in_(available_user_ids),
                SupervisedExecutionQueue.status == QueueStatus.pending,
                SupervisedExecutionQueue.expires_at > datetime.utcnow()
            ).order_by(
                SupervisedExecutionQueue.priority.desc(),
                SupervisedExecutionQueue.created_at.asc()
            ).limit(limit).all()

            for queue_entry in pending_queues:
                # Double-check user is still available
                if not await self._is_user_available(queue_entry.user_id):
                    continue

                # Process the queue entry
                result = await self._process_single_queue(queue_entry)
                if result:
                    processed.append(result)

            if processed:
                logger.info(
                    f"Processed {len(processed)} supervised queue entries"
                )

        except Exception as e:
            logger.error(f"Error processing pending queues: {e}", exc_info=True)

        return processed

    async def cancel_queue_entry(
        self,
        queue_id: str,
        user_id: str
    ) -> bool:
        """
        Cancel a queued execution.

        Args:
            queue_id: Queue entry to cancel
            user_id: User cancelling (must own the queue entry)

        Returns:
            True if cancelled, False if not found or unauthorized
        """
        queue_entry = self.db.query(SupervisedExecutionQueue).filter(
            SupervisedExecutionQueue.id == queue_id
        ).first()

        if not queue_entry:
            logger.warning(f"Queue entry not found: {queue_id}")
            return False

        # Check ownership
        if queue_entry.user_id != user_id:
            logger.warning(
                f"User {user_id} not authorized to cancel queue entry {queue_id}"
            )
            return False

        # Can only cancel pending entries
        if queue_entry.status != QueueStatus.pending:
            logger.warning(
                f"Cannot cancel queue entry {queue_id} with status {queue_entry.status}"
            )
            return False

        # Update status
        await self.update_queue_status(queue_id, QueueStatus.cancelled)

        logger.info(f"Cancelled queue entry: {queue_id}")

        return True

    async def get_user_queue(
        self,
        user_id: str,
        status: Optional[QueueStatus] = None
    ) -> List[SupervisedExecutionQueue]:
        """
        Get all queue entries for a user.

        Args:
            user_id: User to get queue for
            status: Optional status filter

        Returns:
            List of SupervisedExecutionQueue records
        """
        query = self.db.query(SupervisedExecutionQueue).filter(
            SupervisedExecutionQueue.user_id == user_id
        )

        if status:
            query = query.filter(SupervisedExecutionQueue.status == status)

        return query.order_by(
            SupervisedExecutionQueue.created_at.desc()
        ).all()

    async def update_queue_status(
        self,
        queue_id: str,
        status: QueueStatus,
        execution_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> SupervisedExecutionQueue:
        """
        Update queue entry status.

        Args:
            queue_id: Queue entry to update
            status: New status
            execution_id: Optional execution ID (for executing/completed)
            error_message: Optional error message (for failed)

        Returns:
            Updated SupervisedExecutionQueue record
        """
        queue_entry = self.db.query(SupervisedExecutionQueue).filter(
            SupervisedExecutionQueue.id == queue_id
        ).first()

        if not queue_entry:
            raise ValueError(f"Queue entry not found: {queue_id}")

        queue_entry.status = status

        if execution_id:
            queue_entry.execution_id = execution_id

        if error_message:
            queue_entry.error_message = error_message

        self.db.commit()
        self.db.refresh(queue_entry)

        logger.info(
            f"Updated queue entry {queue_id} status: {status.value}"
        )

        return queue_entry

    async def mark_expired_queues(self) -> int:
        """
        Mark expired queue entries as failed.

        Called by background worker to clean up expired entries.

        Returns:
            Number of entries marked as failed
        """
        expired_queues = self.db.query(SupervisedExecutionQueue).filter(
            SupervisedExecutionQueue.status == QueueStatus.pending,
            SupervisedExecutionQueue.expires_at < datetime.utcnow()
        ).all()

        count = 0
        for queue_entry in expired_queues:
            queue_entry.status = QueueStatus.failed
            queue_entry.error_message = "Queue entry expired"
            count += 1

        if count > 0:
            self.db.commit()
            logger.info(f"Marked {count} expired queue entries as failed")

        return count

    async def get_queue_stats(self, user_id: Optional[str] = None) -> Dict[str, int]:
        """
        Get queue statistics.

        Args:
            user_id: Optional user filter

        Returns:
            Dict with counts by status
        """
        query = self.db.query(SupervisedExecutionQueue)

        if user_id:
            query = query.filter(SupervisedExecutionQueue.user_id == user_id)

        stats = {
            "pending": 0,
            "executing": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "total": 0
        }

        for status in QueueStatus:
            count = query.filter(
                SupervisedExecutionQueue.status == status
            ).count()
            stats[status.value] = count
            stats["total"] += count

        return stats

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _get_available_user_ids(self) -> List[str]:
        """Get list of user IDs who are available (online or away)."""
        available_activities = self.db.query(UserActivity).filter(
            UserActivity.state.in_([UserState.online, UserState.away])
        ).all()

        return [a.user_id for a in available_activities]

    async def _is_user_available(self, user_id: str) -> bool:
        """Check if user is available to supervise."""
        activity = self.db.query(UserActivity).filter(
            UserActivity.user_id == user_id
        ).first()

        if not activity:
            return False

        return activity.state in [UserState.online, UserState.away]

    async def _process_single_queue(
        self,
        queue_entry: SupervisedExecutionQueue
    ) -> Optional[SupervisedExecutionQueue]:
        """
        Process a single queue entry.

        Creates execution and updates queue status.

        Args:
            queue_entry: Queue entry to process

        Returns:
            Updated queue entry or None if failed
        """
        try:
            # Update to executing status
            queue_entry.status = QueueStatus.executing
            queue_entry.attempt_count += 1
            self.db.commit()

            # Create execution record
            execution = await self._create_execution_from_queue(queue_entry)

            # Update queue with execution ID
            queue_entry.execution_id = execution.id
            queue_entry.status = QueueStatus.completed
            self.db.commit()

            logger.info(
                f"Successfully processed queue entry {queue_entry.id}, "
                f"execution: {execution.id}"
            )

            return queue_entry

        except Exception as e:
            logger.error(
                f"Failed to process queue entry {queue_entry.id}: {e}",
                exc_info=True
            )

            # Check if should retry
            if queue_entry.attempt_count < queue_entry.max_attempts:
                queue_entry.status = QueueStatus.pending
                queue_entry.error_message = f"Attempt {queue_entry.attempt_count} failed: {str(e)}"
            else:
                queue_entry.status = QueueStatus.failed
                queue_entry.error_message = f"Failed after {queue_entry.attempt_count} attempts: {str(e)}"

            self.db.commit()

            return queue_entry

    async def _create_execution_from_queue(
        self,
        queue_entry: SupervisedExecutionQueue
    ) -> AgentExecution:
        """
        Create AgentExecution from queued entry.

        Args:
            queue_entry: Queue entry with execution context

        Returns:
            Created AgentExecution record
        """
        # Get agent info
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == queue_entry.agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent not found: {queue_entry.agent_id}")

        # Create execution
        execution = AgentExecution(
            id=str(uuid.uuid4()),
            agent_id=queue_entry.agent_id,
            user_id=queue_entry.user_id,
            agent_name=agent.name,
            status="running",
            input_data=queue_entry.execution_context,
            started_at=datetime.utcnow()
        )

        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)

        # TODO: Actually execute the agent
        # For now, just mark as completed
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.output_summary = f"Executed from queue entry {queue_entry.id}"
        self.db.commit()

        return execution

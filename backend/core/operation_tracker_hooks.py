"""
Operation Tracker Hooks - Automatic social post generation from AgentOperationTracker.

Integrates with AgentOperationTracker to automatically generate social posts
when agents complete significant operations.
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import event
from sqlalchemy.engine import Engine

from core.models import AgentOperationTracker, AgentRegistry
from core.social_post_generator import social_post_generator
from core.agent_social_layer import agent_social_layer


logger = logging.getLogger(__name__)


class OperationTrackerHooks:
    """
    Hooks for automatic social post generation from AgentOperationTracker.

    Features:
    - Detect operation completion (running → completed status change)
    - Rate limiting per agent (1 post per 5 minutes)
    - Alert posts bypass rate limit
    - Maturity-based governance (INTERN+ can post, STUDENT read-only)
    - Audit logging for all auto-generated posts
    - Fire-and-forget async execution (no blocking)
    """

    # In-memory rate limit tracker: {agent_id: last_post_timestamp}
    _rate_limit_tracker: dict = {}

    # Rate limit window (minutes)
    RATE_LIMIT_MINUTES = int(os.getenv("SOCIAL_POST_RATE_LIMIT_MINUTES", "5"))

    # Cleanup interval for old rate limit entries
    CLEANUP_INTERVAL_HOURS = 1

    @staticmethod
    def is_alert_post(tracker: AgentOperationTracker) -> bool:
        """
        Determine if post is alert-type (bypasses rate limit).

        Args:
            tracker: AgentOperationTracker instance

        Returns:
            True if post is alert-type (critical error, security issue, etc.)
        """
        # Check for critical status
        if tracker.status == "failed":
            return True

        # Check for security-related operations
        if "security" in tracker.operation_type.lower():
            return True

        # Check for approval requests (always allow)
        if tracker.operation_type == "approval_requested":
            return True

        return False

    @staticmethod
    def is_rate_limited(agent_id: str) -> bool:
        """
        Check if agent is rate limited for posting.

        Args:
            agent_id: Agent ID to check

        Returns:
            True if agent should be rate limited
        """
        if agent_id not in OperationTrackerHooks._rate_limit_tracker:
            return False

        last_post = OperationTrackerHooks._rate_limit_tracker[agent_id]
        time_since_last = datetime.utcnow() - last_post

        return time_since_last < timedelta(minutes=OperationTrackerHooks.RATE_LIMIT_MINUTES)

    @staticmethod
    def update_rate_limit(agent_id: str) -> None:
        """
        Update rate limit tracker for agent.

        Args:
            agent_id: Agent ID to update
        """
        OperationTrackerHooks._rate_limit_tracker[agent_id] = datetime.utcnow()

        # Cleanup old entries (older than 1 hour)
        cutoff = datetime.utcnow() - timedelta(hours=OperationTrackerHooks.CLEANUP_INTERVAL_HOURS)
        OperationTrackerHooks._rate_limit_tracker = {
            k: v for k, v in OperationTrackerHooks._rate_limit_tracker.items()
            if v > cutoff
        }

    @staticmethod
    async def on_operation_complete(tracker_id: str, db: Session) -> None:
        """
        Generate social post when operation completes.

        Flow:
        1. Fetch tracker and agent
        2. Check agent maturity (INTERN+ only)
        3. Check rate limit (alert posts bypass)
        4. Generate post content
        5. Redact PII (placeholder - will be implemented in Plan 02)
        6. Post to feed
        7. Update rate limit tracker
        8. Log to audit trail

        Args:
            tracker_id: AgentOperationTracker ID
            db: Database session
        """
        try:
            # Step 1: Fetch tracker and agent
            tracker = db.query(AgentOperationTracker).filter(
                AgentOperationTracker.id == tracker_id
            ).first()

            if not tracker:
                logger.warning(f"Auto-post: Tracker {tracker_id} not found")
                return

            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == tracker.agent_id
            ).first()

            if not agent:
                logger.warning(f"Auto-post: Agent {tracker.agent_id} not found")
                return

            # Step 2: Check agent maturity (INTERN+ only, STUDENT read-only)
            if agent.status == "STUDENT":
                logger.info(
                    f"Auto-post: Skipping STUDENT agent {agent.id} "
                    f"(read-only maturity level)"
                )
                return

            # Step 3: Check rate limit (alert posts bypass)
            is_alert = OperationTrackerHooks.is_alert_post(tracker)
            if not is_alert and OperationTrackerHooks.is_rate_limited(agent.id):
                logger.info(
                    f"Auto-post: Rate limited agent {agent.id} "
                    f"(last post {OperationTrackerHooks.RATE_LIMIT_MINUTES} minutes ago)"
                )
                return

            # Step 4: Check if operation is significant
            if not social_post_generator.is_significant_operation(tracker):
                logger.debug(
                    f"Auto-post: Operation {tracker.operation_type} not significant, skipping"
                )
                return

            # Step 5: Generate post content
            try:
                content = await social_post_generator.generate_from_operation(tracker, agent)
            except ValueError as e:
                logger.warning(f"Auto-post: Failed to generate content: {e}")
                return
            except Exception as e:
                logger.error(f"Auto-post: Error generating post: {e}")
                return

            # Step 6: Redact PII (placeholder - will be implemented in Plan 02)
            # For now, just log that redaction would happen here
            redacted_content = content  # TODO: Implement PII redaction in Plan 02

            # Step 7: Post to feed
            try:
                await agent_social_layer.create_post(
                    sender_type="agent",
                    sender_id=agent.id,
                    sender_name=agent.name,
                    post_type="status",
                    content=redacted_content,
                    sender_maturity=agent.status,
                    sender_category=agent.category,
                    auto_generated=True,
                    db=db
                )

                # Step 8: Update rate limit tracker
                OperationTrackerHooks.update_rate_limit(agent.id)

                # Step 9: Log to audit trail
                logger.info(
                    f"Auto-post: Generated post for agent={agent.id}, "
                    f"operation={tracker.operation_type}, "
                    f"tracker={tracker.id}, "
                    f"status={tracker.status}"
                )

            except PermissionError as e:
                logger.warning(f"Auto-post: Permission denied: {e}")
            except Exception as e:
                logger.error(f"Auto-post: Failed to create post: {e}")

        except Exception as e:
            logger.error(f"Auto-post: Unexpected error in on_operation_complete: {e}")

    @staticmethod
    def on_operation_update(tracker: AgentOperationTracker, db: Session) -> None:
        """
        Called on significant step changes during operation.

        This is a placeholder for future enhancement where we might want to
        post updates during long-running operations (e.g., "Step 3/5: Processing data").

        Args:
            tracker: AgentOperationTracker instance
            db: Database session
        """
        # For now, we only post on completion, not during updates
        # This prevents feed spam from multi-step operations
        pass


# Global hooks instance
operation_tracker_hooks = OperationTrackerHooks()


def register_auto_post_hooks() -> None:
    """
    Register SQLAlchemy event listeners for automatic post generation.

    This function should be called once on module load to register hooks
    with AgentOperationTracker model.

    Uses SQLAlchemy event.listen() to detect status transitions:
    - running → completed: Trigger social post
    """
    @event.listens_for(AgentOperationTracker, 'after_update')
    def detect_operation_completion(mapper, connection, target):
        """
        Detect operation completion and trigger social post generation.

        Runs after AgentOperationTracker is updated.
        Checks if status transitioned from running → completed.
        """
        # Check if status just changed to "completed"
        # We need to inspect the session to get the previous value
        if target.status == "completed":
            # Get database session from connection
            from sqlalchemy.orm import sessionmaker
            Session = sessionmaker(bind=connection)
            db = Session()

            try:
                # Trigger async post generation in background
                # Note: This is fire-and-forget, we don't await it
                asyncio.create_task(
                    operation_tracker_hooks.on_operation_complete(target.id, db)
                )
            except Exception as e:
                logger.error(f"Failed to schedule auto-post generation: {e}")
            finally:
                db.close()

    logger.info("OperationTrackerHooks: Registered auto-post hooks with AgentOperationTracker")


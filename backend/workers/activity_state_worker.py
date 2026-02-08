"""
Activity State Worker

Background worker that processes user activity state transitions.
Runs every 60 seconds to check for inactive users and update their states.

State Transitions:
- online → away after 5 minutes of inactivity
- away → offline after 15 minutes of inactivity
- offline → online on activity resumption
"""

import asyncio
import logging
from datetime import datetime

from core.database import get_db
from core.user_activity_service import UserActivityService

logger = logging.getLogger(__name__)


class ActivityStateWorker:
    """
    Background worker for processing user activity state transitions.

    Runs every 60 seconds to:
    1. Check user state transitions based on inactivity
    2. Process manual override expiry
    3. Clean up stale sessions
    4. Emit state change events (optional, for WebSocket notifications)

    Performance target: <1s per batch of 100 users
    """

    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self.running = False

    async def run(self):
        """Main worker loop."""
        self.running = True
        logger.info("ActivityStateWorker started")

        while self.running:
            try:
                start_time = datetime.now()

                # Process state transitions
                await self.process_state_transitions()

                # Process manual override expiry
                await self.process_manual_override_expiry()

                # Cleanup stale sessions
                await self.cleanup_stale_sessions()

                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(
                    f"ActivityStateWorker cycle completed in {elapsed:.2f}s"
                )

            except Exception as e:
                logger.error(f"ActivityStateWorker error: {e}", exc_info=True)

            # Wait for next cycle
            await asyncio.sleep(self.interval_seconds)

    async def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("ActivityStateWorker stopped")

    async def process_state_transitions(self):
        """Process state transitions for inactive users."""
        db = next(get_db())

        try:
            service = UserActivityService(db)
            transitions = await service.transition_state_batch(limit=100)

            if transitions["total_processed"] > 0:
                transition_summary = ", ".join([
                    f"{k}: {v}"
                    for k, v in transitions.items()
                    if k != "total_processed" and v > 0
                ])
                logger.info(
                    f"State transitions: {transitions['total_processed']} processed"
                    + (f" ({transition_summary})" if transition_summary else "")
                )

        finally:
            db.close()

    async def process_manual_override_expiry(self):
        """Process manual overrides that have expired."""
        from core.models import UserActivity
        from sqlalchemy.orm import Session

        db: Session = next(get_db())

        try:
            # Find expired manual overrides
            now = datetime.utcnow()
            expired = db.query(UserActivity).filter(
                UserActivity.manual_override == True,
                UserActivity.manual_override_expires_at.isnot(None),
                UserActivity.manual_override_expires_at < now
            ).all()

            count = 0
            for activity in expired:
                # Clear manual override
                activity.manual_override = False
                activity.manual_override_expires_at = None

                # Recalculate state based on actual activity
                service = UserActivityService(db)
                await service._recalculate_activity_state(activity)

                count += 1
                logger.info(
                    f"Cleared expired manual override for user {activity.user_id}"
                )

            if count > 0:
                db.commit()
                logger.info(f"Cleared {count} expired manual overrides")

        finally:
            db.close()

    async def cleanup_stale_sessions(self):
        """Clean up stale sessions (no heartbeat for >1 hour)."""
        db = next(get_db())

        try:
            service = UserActivityService(db)
            count = await service.cleanup_stale_sessions(limit=50)

            if count > 0:
                logger.info(f"Cleaned up {count} stale sessions")

        finally:
            db.close()


# ============================================================================
# Worker Entry Point
# ============================================================================

async def main():
    """Entry point for running the worker."""
    worker = ActivityStateWorker(interval_seconds=60)

    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())

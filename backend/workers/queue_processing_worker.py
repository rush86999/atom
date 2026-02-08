"""
Queue Processing Worker

Background worker that processes supervised execution queue.
Runs every 60 seconds to check for available users and process their queues.
"""

import asyncio
import logging
from datetime import datetime

from core.database import get_db
from core.supervised_queue_service import SupervisedQueueService

logger = logging.getLogger(__name__)


class QueueProcessingWorker:
    """
    Background worker for processing supervised execution queue.

    Runs every 60 seconds to:
    1. Find users who recently became online/away
    2. Fetch their pending queues (batch of 10)
    3. Execute queued entries with supervision
    4. Handle expired queues (>24 hours)

    Performance target: <5s per batch of 10 entries
    """

    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self.running = False

    async def run(self):
        """Main worker loop."""
        self.running = True
        logger.info("QueueProcessingWorker started")

        while self.running:
            try:
                start_time = datetime.now()

                # Process pending queues
                await self.process_pending_queues()

                # Mark expired queues
                await self.mark_expired_queues()

                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(
                    f"QueueProcessingWorker cycle completed in {elapsed:.2f}s"
                )

            except Exception as e:
                logger.error(f"QueueProcessingWorker error: {e}", exc_info=True)

            # Wait for next cycle
            await asyncio.sleep(self.interval_seconds)

    async def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("QueueProcessingWorker stopped")

    async def process_pending_queues(self):
        """Process pending queue entries for available users."""
        db = next(get_db())

        try:
            service = SupervisedQueueService(db)
            processed = await service.process_pending_queues(limit=10)

            if processed:
                logger.info(
                    f"Processed {len(processed)} supervised queue entries"
                )

        finally:
            db.close()

    async def mark_expired_queues(self):
        """Mark expired queue entries as failed."""
        db = next(get_db())

        try:
            service = SupervisedQueueService(db)
            count = await service.mark_expired_queues()

            if count > 0:
                logger.info(f"Marked {count} expired queues as failed")

        finally:
            db.close()


# ============================================================================
# Worker Entry Point
# ============================================================================

async def main():
    """Entry point for running the worker."""
    worker = QueueProcessingWorker(interval_seconds=60)

    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())

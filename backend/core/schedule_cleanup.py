from __future__ import annotations
"""
Auto-cleanup task for old QStash schedules
Runs on API startup to remove orphaned schedules
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from qstash import AsyncQStash

logger = logging.getLogger(__name__)

QSTASH_URL = os.getenv("QSTASH_URL", "https://qstash-us-east-1.upstash.io")
QSTASH_TOKEN = os.getenv("QSTASH_TOKEN")

# Auto-cleanup schedules older than this (configurable via env)
MAX_SCHEDULE_AGE_DAYS = int(os.getenv("MAX_SCHEDULE_AGE_DAYS", "7"))


async def cleanup_old_schedules():
    """
    Automatically cleanup old schedules on startup.
    Removes schedules older than MAX_SCHEDULE_AGE_DAYS days.
    """
    if not QSTASH_TOKEN:
        logger.info("⏩ QSTASH_TOKEN not set, skipping schedule cleanup")
        return

    logger.info("🧹 Starting auto-cleanup of old QStash schedules...")

    try:
        client = AsyncQStash(token=QSTASH_TOKEN, base_url=QSTASH_URL)

        # Fetch all schedules
        schedules = await client.schedule.list()

        if not schedules:
            logger.info("✅ No schedules found, cleanup complete")
            return

        logger.info(f"📊 Found {len(schedules)} total schedules")

        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=MAX_SCHEDULE_AGE_DAYS)
        deleted_count = 0

        for schedule in schedules:
            schedule_id = schedule.schedule_id
            created_at = schedule.created_at  # Unix timestamp in milliseconds
            destination = schedule.destination
            cron = schedule.cron

            if not schedule_id or not created_at:
                continue

            # Convert milliseconds to datetime
            created_date = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)

            # Delete if older than cutoff
            if created_date < cutoff_time:
                age_days = (datetime.now(timezone.utc) - created_date).days
                logger.info(f"  🗑️  Deleting old schedule {schedule_id}")
                logger.info(f"      Age: {age_days} days")
                logger.info(f"      Destination: {destination}")
                logger.info(f"      Cron: {cron}")

                try:
                    await client.schedule.delete(schedule_id)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"    ❌ Failed to delete {schedule_id}: {e}")

        logger.info(f"✨ Auto-cleanup complete: {deleted_count} old schedules deleted")

    except Exception as e:
        logger.error(f"❌ Auto-cleanup failed: {e}")


async def get_schedule_stats():
    """Get statistics about current schedules"""
    if not QSTASH_TOKEN:
        return {"error": "QSTASH_TOKEN not set"}

    try:
        client = AsyncQStash(token=QSTASH_TOKEN, base_url=QSTASH_URL)
        schedules = await client.schedule.list()

        # Analyze schedules
        stats = {
            "total": len(schedules),
            "by_destination": {},
            "by_age": {"0-7days": 0, "8-30days": 0, "30+days": 0},
        }

        now = datetime.now(timezone.utc)
        for schedule in schedules:
            dest = schedule.destination or "unknown"
            stats["by_destination"][dest] = stats["by_destination"].get(dest, 0) + 1

            created_at = schedule.created_at
            if created_at:
                created_date = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
                age_days = (now - created_date).days

                if age_days <= 7:
                    stats["by_age"]["0-7days"] += 1
                elif age_days <= 30:
                    stats["by_age"]["8-30days"] += 1
                else:
                    stats["by_age"]["30+days"] += 1

        return stats

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import asyncio

    # Run cleanup
    asyncio.run(cleanup_old_schedules())

    # Show stats
    print("\n📊 Schedule Statistics:")
    stats = asyncio.run(get_schedule_stats())
    print(f"  Total: {stats.get('total', 0)}")
    print(f"  By Age: {stats.get('by_age', {})}")

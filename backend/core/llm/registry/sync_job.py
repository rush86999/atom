"""Scheduled Sync Job for LLM Model Registry

This module provides the ModelSyncJob class for automatically fetching
model metadata from LiteLLM and OpenRouter APIs on a scheduled basis.

The sync job runs every 1 month (720 hours) to:
- Fetch latest model pricing and metadata from external APIs
- Update the database with new/changed models
- Update last_sync_timestamp for monitoring
- Refresh the Redis cache

Manual trigger available via API for immediate sync when needed.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.llm.registry.models import LLMModel
from core.llm.registry.service import LLMRegistryService

logger = logging.getLogger(__name__)


class ModelSyncJob:
    """
    Scheduled job for automatic model metadata synchronization.

    Runs every 1 month (720 hours) to fetch model data from LiteLLM and OpenRouter APIs,
    update the database, and refresh the cache. Designed for cron or Celery
    scheduled execution. Manual trigger available via API for immediate sync.

    Usage:
        job = ModelSyncJob(db_session)
        result = await job.run(tenant_id='default')
        print(f"Synced {result['models_fetched']} models")

    Attributes:
        db: SQLAlchemy database session
        registry_service: LLMRegistryService instance for database operations
        logger: Logger instance for tracking sync progress
    """

    def __init__(self, db: Session):
        """
        Initialize the sync job.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.registry_service = LLMRegistryService(db, use_cache=True)
        self.logger = logging.getLogger(__name__)

    async def run(self, tenant_id: str = 'default') -> Dict[str, Any]:
        """
        Execute the sync job for a tenant.

        This method:
        1. Checks if sync is needed (based on last_sync_timestamp)
        2. Fetches models from LiteLLM and OpenRouter APIs
        3. Upserts models to database
        4. Updates last_sync_timestamp
        5. Refreshes cache

        Args:
            tenant_id: Tenant to sync models for

        Returns:
            Dict with sync results:
            {
                'success': bool,
                'models_fetched': int,
                'created': int,
                'updated': int,
                'failed': int,
                'sync_timestamp': datetime,
                'duration_seconds': float
            }

        Example:
            >>> job = ModelSyncJob(db)
            >>> result = await job.run('tenant-123')
            >>> print(f"Success: {result['success']}")
            >>> print(f"Created: {result['created']}, Updated: {result['updated']}")
        """
        start_time = datetime.utcnow()
        self.logger.info(f"Starting sync job for tenant {tenant_id}")

        result = {
            'success': False,
            'models_fetched': 0,
            'created': 0,
            'updated': 0,
            'failed': 0,
            'sync_timestamp': start_time,
            'duration_seconds': 0.0,
            'error': None
        }

        try:
            # Check if sync is needed (skip if recently synced)
            if not self.should_sync(tenant_id, self.db, interval_hours=720):
                self.logger.info(f"Sync not needed for tenant {tenant_id} (recently synced)")
                result['success'] = True
                result['sync_timestamp'] = datetime.utcnow()
                result['duration_seconds'] = (datetime.utcnow() - start_time).total_seconds()
                return result

            # Fetch and store models using existing service
            stats = await self.registry_service.fetch_and_store(tenant_id)

            # Update last_sync_timestamp for all models
            self._update_sync_timestamp(tenant_id)

            # Build result
            result['success'] = True
            result['models_fetched'] = stats.get('total', 0)
            result['created'] = stats.get('created', 0)
            result['updated'] = stats.get('updated', 0)
            result['failed'] = stats.get('failed', 0)
            result['sync_timestamp'] = datetime.utcnow()
            result['duration_seconds'] = (datetime.utcnow() - start_time).total_seconds()

            self.logger.info(
                f"Sync complete for tenant {tenant_id}: "
                f"{result['created']} created, {result['updated']} updated, "
                f"{result['failed']} failed in {result['duration_seconds']:.2f}s"
            )

        except Exception as e:
            self.logger.error(f"Sync failed for tenant {tenant_id}: {e}", exc_info=True)
            result['error'] = str(e)
            result['duration_seconds'] = (datetime.utcnow() - start_time).total_seconds()

        return result

    def _update_sync_timestamp(self, tenant_id: str) -> None:
        """
        Update last_sync_timestamp in database for all models.

        Sets the timestamp for all models in the tenant to indicate
        they were just synchronized from external APIs.

        Args:
            tenant_id: Tenant identifier

        Example:
            >>> job = ModelSyncJob(db)
            >>> job._update_sync_timestamp('tenant-123')
        """
        try:
            current_time = datetime.utcnow()

            # Update all models for tenant
            updated = self.db.query(LLMModel).filter(
                LLMModel.tenant_id == tenant_id
            ).update(
                {'last_sync_timestamp': current_time},
                synchronize_session=False
            )

            self.db.commit()
            self.logger.debug(f"Updated last_sync_timestamp for {updated} models in tenant {tenant_id}")

        except Exception as e:
            self.logger.error(f"Failed to update sync timestamp for tenant {tenant_id}: {e}")
            self.db.rollback()
            raise

    @staticmethod
    def should_sync(tenant_id: str, db: Session, interval_hours: int = 720) -> bool:
        """
        Check if sync is needed based on last sync timestamp.

        Args:
            tenant_id: Tenant to check
            db: Database session
            interval_hours: Minimum hours between syncs (default: 720 = 1 month)

        Returns:
            True if sync is needed, False otherwise

        Example:
            >>> # Check if sync needed (default 1 month interval)
            >>> if ModelSyncJob.should_sync('tenant-123', db):
            ...     print("Sync needed")
            >>>
            >>> # Check with 24-hour interval
            >>> if ModelSyncJob.should_sync('tenant-123', db, interval_hours=24):
            ...     print("Sync needed within last 24 hours")
        """
        try:
            # Get most recent sync timestamp for tenant
            latest_sync = db.query(LLMModel.last_sync_timestamp).filter(
                LLMModel.tenant_id == tenant_id
            ).order_by(
                LLMModel.last_sync_timestamp.desc()
            ).first()

            # No models exist - sync needed
            if not latest_sync or not latest_sync[0]:
                logger.debug(f"No sync timestamp found for tenant {tenant_id} - sync needed")
                return True

            # Check if enough time has passed
            last_sync = latest_sync[0]
            time_since_sync = datetime.utcnow() - last_sync
            hours_since_sync = time_since_sync.total_seconds() / 3600

            should_sync = hours_since_sync >= interval_hours

            if should_sync:
                logger.debug(
                    f"Sync needed for tenant {tenant_id}: "
                    f"{hours_since_sync:.1f} hours since last sync (threshold: {interval_hours})"
                )
            else:
                logger.debug(
                    f"Sync not needed for tenant {tenant_id}: "
                    f"{hours_since_sync:.1f} hours since last sync (threshold: {interval_hours})"
                )

            return should_sync

        except Exception as e:
            logger.error(f"Error checking sync status for tenant {tenant_id}: {e}")
            # Fail open - if we can't check, assume sync needed
            return True


async def run_sync_job(tenant_id: str = 'default') -> Dict[str, Any]:
    """
    Convenience function to run sync job with database session management.

    Useful for cron tasks or scheduled job runners. Creates a database session,
    runs the sync job, and ensures cleanup.

    Args:
        tenant_id: Tenant to sync models for

    Returns:
        Sync result dictionary with stats and status

    Example:
        >>> # In a cron job or scheduled task
        >>> result = await run_sync_job('tenant-123')
        >>> if result['success']:
        ...     print(f"Synced {result['models_fetched']} models")
        ... else:
        ...     print(f"Sync failed: {result.get('error')}")
    """
    from core.database import SessionLocal

    db = SessionLocal()
    try:
        job = ModelSyncJob(db)
        return await job.run(tenant_id)
    finally:
        db.close()

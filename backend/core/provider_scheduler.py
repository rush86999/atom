"""
Provider Scheduler - Automated provider registry sync using APScheduler
"""
import os
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Optional
from core.provider_auto_discovery import get_auto_discovery
from core.provider_health_monitor import get_provider_health_monitor

logger = logging.getLogger(__name__)


class ProviderScheduler:
    """
    Manages scheduled provider registry sync jobs using AsyncIOScheduler

    Features:
    - 24-hour polling interval for provider sync
    - max_instances=1 prevents overlapping sync jobs
    - coalesce=True combines missed executions if server was down
    - Environment variable toggle (PROVIDER_AUTO_SYNC_ENABLED)
    - Error handling with health monitoring integration
    - Singleton pattern for global access
    """

    _instance: Optional["ProviderScheduler"] = None

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.auto_discovery = get_auto_discovery()
        self.health_monitor = get_provider_health_monitor()

    @classmethod
    def get_instance(cls) -> "ProviderScheduler":
        """
        Get singleton ProviderScheduler instance

        Returns:
            ProviderScheduler instance
        """
        if cls._instance is None:
            cls._instance = ProviderScheduler()
        return cls._instance

    def start(self):
        """
        Schedule auto-sync every 24 hours if enabled

        Environment variable: PROVIDER_AUTO_SYNC_ENABLED (default: true)
        """
        if not os.getenv("PROVIDER_AUTO_SYNC_ENABLED", "true").lower() == "true":
            logger.info("Provider auto-sync disabled (PROVIDER_AUTO_SYNC_ENABLED=false)")
            return

        self.scheduler.add_job(
            self._sync_with_error_handling,
            'interval',
            hours=24,
            id='provider_auto_sync',
            max_instances=1,
            coalesce=True,
            replace_existing=True
        )
        self.scheduler.start()
        logger.info("ProviderScheduler started (24-hour polling)")

    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("ProviderScheduler stopped")

    async def _sync_with_error_handling(self):
        """
        Wrapper with error handling and health tracking

        Records sync success/failure to health_monitor for operational monitoring
        """
        try:
            result = await self.auto_discovery.sync_providers()
            logger.info(f"Auto-sync completed: {result}")
            # Record success for provider health (virtual "registry" provider)
            self.health_monitor.record_call("provider_registry", True, 0)
        except Exception as e:
            logger.error(f"Auto-sync failed: {e}")
            self.health_monitor.record_call("provider_registry", False, 0)


def get_provider_scheduler() -> Optional[ProviderScheduler]:
    """
    Get ProviderScheduler instance if enabled

    Environment variable: PROVIDER_AUTO_SYNC_ENABLED (default: true)

    Returns:
        ProviderScheduler instance if enabled, None otherwise
    """
    if os.getenv("PROVIDER_AUTO_SYNC_ENABLED", "true").lower() == "true":
        return ProviderScheduler.get_instance()
    return None

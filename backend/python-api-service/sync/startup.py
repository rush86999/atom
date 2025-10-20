"""
Startup Script for LanceDB Sync System

This script initializes and starts the LanceDB sync system with proper configuration
and error handling. It can be used as a standalone service or integrated into the
main application.
"""

import os
import sys
import logging
import asyncio
import signal
from typing import Optional, Dict, Any
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sync.orchestration_service import (
    OrchestrationService,
    create_orchestration_service,
    SourceConfig,
    SourceType,
)
from sync import get_config, update_config

logger = logging.getLogger(__name__)


class SyncSystemStartup:
    """
    Handles startup and initialization of the LanceDB sync system
    """

    def __init__(self, config_overrides: Optional[Dict[str, Any]] = None):
        self.config = get_config()
        self.orchestration_service: Optional[OrchestrationService] = None
        self.running = False

        # Apply configuration overrides if provided
        if config_overrides:
            self.config = update_config(**config_overrides)

    async def initialize(self) -> bool:
        """
        Initialize the sync system components

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing LanceDB sync system...")

            # Create orchestration service
            self.orchestration_service = create_orchestration_service(
                local_db_path=self.config.local_db_path,
                s3_bucket=self.config.s3_bucket,
                s3_prefix=self.config.s3_prefix,
                sync_state_dir=self.config.sync_state_dir,
                enable_source_monitoring=self.config.enable_source_monitoring,
            )

            logger.info("Sync system initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize sync system: {e}")
            return False

    async def start(self) -> bool:
        """
        Start the sync system

        Returns:
            bool: True if startup successful, False otherwise
        """
        if not self.orchestration_service:
            logger.error("Sync system not initialized. Call initialize() first.")
            return False

        try:
            logger.info("Starting LanceDB sync system...")

            # Start the orchestration service
            await self.orchestration_service.start()
            self.running = True

            # Set up signal handlers for graceful shutdown
            self._setup_signal_handlers()

            logger.info("Sync system started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start sync system: {e}")
            return False

    async def stop(self) -> bool:
        """
        Stop the sync system gracefully

        Returns:
            bool: True if shutdown successful, False otherwise
        """
        if not self.orchestration_service:
            return True

        try:
            logger.info("Stopping LanceDB sync system...")

            await self.orchestration_service.stop()
            self.running = False

            logger.info("Sync system stopped gracefully")
            return True

        except Exception as e:
            logger.error(f"Error during sync system shutdown: {e}")
            return False

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def add_default_sources(self) -> bool:
        """
        Add default document sources based on configuration

        Returns:
            bool: True if sources added successfully, False otherwise
        """
        if not self.orchestration_service:
            logger.error("Sync system not initialized")
            return False

        try:
            # Add local filesystem source if configured
            if self.config.enable_source_monitoring:
                local_source = SourceConfig(
                    source_type=SourceType.LOCAL_FILESYSTEM,
                    source_id="default_documents",
                    config={
                        "watch_paths": ["~/Documents", "~/Downloads"],
                        "file_patterns": self.config.file_watch_patterns,
                    },
                    poll_interval=self.config.default_poll_interval,
                    enabled=True,
                )

                result = await self.orchestration_service.add_source(local_source)
                if result["status"] == "success":
                    logger.info("Added default local filesystem source")
                else:
                    logger.warning(
                        f"Failed to add local source: {result.get('message')}"
                    )

            return True

        except Exception as e:
            logger.error(f"Failed to add default sources: {e}")
            return False

    async def get_status(self) -> Dict[str, Any]:
        """
        Get current system status

        Returns:
            Dict with system status information
        """
        if not self.orchestration_service:
            return {"status": "not_initialized"}

        try:
            return await self.orchestration_service.get_system_status()
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {"status": "error", "error": str(e)}

    async def wait_until_stopped(self):
        """Wait until the sync system is stopped"""
        while self.running:
            await asyncio.sleep(1)


async def main():
    """
    Main entry point for standalone sync system operation
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("sync_system.log")],
    )

    # Configuration overrides from environment
    config_overrides = {}
    if os.environ.get("SYNC_DISABLED"):
        config_overrides["enable_source_monitoring"] = False

    # Create and start the sync system
    startup = SyncSystemStartup(config_overrides)

    try:
        # Initialize the system
        if not await startup.initialize():
            logger.error("Failed to initialize sync system")
            return 1

        # Add default sources
        await startup.add_default_sources()

        # Start the system
        if not await startup.start():
            logger.error("Failed to start sync system")
            return 1

        logger.info("LanceDB sync system is running. Press Ctrl+C to stop.")

        # Wait until stopped
        await startup.wait_until_stopped()

        return 0

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await startup.stop()
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await startup.stop()
        return 1


def create_sync_system(
    config_overrides: Optional[Dict[str, Any]] = None,
) -> SyncSystemStartup:
    """
    Factory function to create a sync system instance

    Args:
        config_overrides: Optional configuration overrides

    Returns:
        SyncSystemStartup instance
    """
    return SyncSystemStartup(config_overrides)


async def start_sync_system_async(
    config_overrides: Optional[Dict[str, Any]] = None,
) -> SyncSystemStartup:
    """
    Convenience function to create and start sync system asynchronously

    Args:
        config_overrides: Optional configuration overrides

    Returns:
        Started SyncSystemStartup instance
    """
    startup = create_sync_system(config_overrides)

    if await startup.initialize():
        await startup.start()
        await startup.add_default_sources()

    return startup


if __name__ == "__main__":
    # Run the sync system as a standalone service
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

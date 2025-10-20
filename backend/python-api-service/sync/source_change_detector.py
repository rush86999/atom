"""
Source Change Detector for Document Ingestion Pipeline

This module detects changes in various document sources (Notion, Dropbox, local files, etc.)
and triggers incremental updates to the LanceDB vector store.
"""

import os
import logging
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass
from enum import Enum
import aiofiles
import aiofiles.os
import aiohttp
from pathlib import Path

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Supported document source types"""

    NOTION = "notion"
    DROPBOX = "dropbox"
    GOOGLE_DRIVE = "google_drive"
    LOCAL_FILESYSTEM = "local_filesystem"
    S3 = "s3"


class ChangeType(Enum):
    """Types of detected changes"""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass
class SourceChange:
    """Represents a detected change in a source"""

    source_type: SourceType
    source_id: str
    item_id: str
    item_path: str
    change_type: ChangeType
    timestamp: str
    metadata: Dict[str, Any]
    checksum: Optional[str] = None
    previous_path: Optional[str] = None


@dataclass
class SourceConfig:
    """Configuration for a document source"""

    source_type: SourceType
    source_id: str
    config: Dict[str, Any]
    poll_interval: int = 300  # seconds
    enabled: bool = True


class SourceChangeDetector:
    """
    Detects changes in document sources and triggers incremental updates
    """

    def __init__(self, state_dir: str = "data/sync_state"):
        self.state_dir = state_dir
        self.sources: Dict[str, SourceConfig] = {}
        self.change_handlers: List[Callable[[SourceChange], None]] = []
        self.running = False
        self.monitor_tasks: Dict[str, asyncio.Task] = {}

        # Create state directory
        os.makedirs(state_dir, exist_ok=True)

        logger.info("Initialized SourceChangeDetector")

    def add_source(self, config: SourceConfig) -> None:
        """Add a source to monitor for changes"""
        source_key = f"{config.source_type.value}_{config.source_id}"
        self.sources[source_key] = config
        logger.info(f"Added source: {source_key}")

    def remove_source(self, source_type: SourceType, source_id: str) -> None:
        """Remove a source from monitoring"""
        source_key = f"{source_type.value}_{source_id}"
        if source_key in self.sources:
            del self.sources[source_key]
            logger.info(f"Removed source: {source_key}")

    def add_change_handler(self, handler: Callable[[SourceChange], None]) -> None:
        """Add a handler for detected changes"""
        self.change_handlers.append(handler)
        logger.info("Added change handler")

    async def start_monitoring(self) -> None:
        """Start monitoring all enabled sources"""
        self.running = True

        for source_key, config in self.sources.items():
            if config.enabled:
                task = asyncio.create_task(self._monitor_source(source_key, config))
                self.monitor_tasks[source_key] = task
                logger.info(f"Started monitoring: {source_key}")

        logger.info("Started monitoring all enabled sources")

    async def stop_monitoring(self) -> None:
        """Stop monitoring all sources"""
        self.running = False

        # Cancel all monitoring tasks
        for task in self.monitor_tasks.values():
            task.cancel()

        # Wait for tasks to complete cancellation
        if self.monitor_tasks:
            await asyncio.gather(*self.monitor_tasks.values(), return_exceptions=True)

        self.monitor_tasks.clear()
        logger.info("Stopped monitoring all sources")

    async def _monitor_source(self, source_key: str, config: SourceConfig) -> None:
        """Monitor a specific source for changes"""
        while self.running:
            try:
                logger.debug(f"Checking for changes in {source_key}")

                changes = await self._detect_source_changes(config)

                for change in changes:
                    await self._handle_change(change)

                # Wait for next poll interval
                await asyncio.sleep(config.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring source {source_key}: {e}")
                await asyncio.sleep(config.poll_interval)  # Wait before retry

    async def _detect_source_changes(self, config: SourceConfig) -> List[SourceChange]:
        """Detect changes in a specific source"""
        try:
            if config.source_type == SourceType.LOCAL_FILESYSTEM:
                return await self._detect_local_filesystem_changes(config)
            elif config.source_type == SourceType.NOTION:
                return await self._detect_notion_changes(config)
            elif config.source_type == SourceType.DROPBOX:
                return await self._detect_dropbox_changes(config)
            elif config.source_type == SourceType.GOOGLE_DRIVE:
                return await self._detect_google_drive_changes(config)
            elif config.source_type == SourceType.S3:
                return await self._detect_s3_changes(config)
            else:
                logger.warning(f"Unsupported source type: {config.source_type}")
                return []

        except Exception as e:
            logger.error(f"Error detecting changes for {config.source_type}: {e}")
            return []

    async def _detect_local_filesystem_changes(
        self, config: SourceConfig
    ) -> List[SourceChange]:
        """Detect changes in local filesystem"""
        changes = []
        watch_paths = config.config.get("watch_paths", [])
        file_patterns = config.config.get("file_patterns", ["*"])

        # Load previous state
        state_file = os.path.join(self.state_dir, f"local_{config.source_id}.json")
        previous_state = await self._load_source_state(state_file)
        current_state = {}

        for watch_path in watch_paths:
            if not os.path.exists(watch_path):
                logger.warning(f"Watch path does not exist: {watch_path}")
                continue

            for pattern in file_patterns:
                for file_path in Path(watch_path).rglob(pattern):
                    if file_path.is_file():
                        try:
                            # Get file metadata
                            stat = await aiofiles.os.stat(file_path)
                            file_size = stat.st_size
                            mtime = stat.st_mtime

                            # Generate checksum for content changes
                            checksum = await self._generate_file_checksum(
                                str(file_path)
                            )

                            file_id = str(file_path)
                            current_state[file_id] = {
                                "path": str(file_path),
                                "size": file_size,
                                "mtime": mtime,
                                "checksum": checksum,
                            }

                            # Detect changes
                            if file_id not in previous_state:
                                # New file
                                changes.append(
                                    SourceChange(
                                        source_type=SourceType.LOCAL_FILESYSTEM,
                                        source_id=config.source_id,
                                        item_id=file_id,
                                        item_path=str(file_path),
                                        change_type=ChangeType.CREATED,
                                        timestamp=datetime.now(
                                            timezone.utc
                                        ).isoformat(),
                                        metadata=current_state[file_id],
                                        checksum=checksum,
                                    )
                                )
                            else:
                                prev = previous_state[file_id]
                                if (
                                    prev["mtime"] != mtime
                                    or prev["size"] != file_size
                                    or prev["checksum"] != checksum
                                ):
                                    # Updated file
                                    changes.append(
                                        SourceChange(
                                            source_type=SourceType.LOCAL_FILESYSTEM,
                                            source_id=config.source_id,
                                            item_id=file_id,
                                            item_path=str(file_path),
                                            change_type=ChangeType.UPDATED,
                                            timestamp=datetime.now(
                                                timezone.utc
                                            ).isoformat(),
                                            metadata=current_state[file_id],
                                            checksum=checksum,
                                        )
                                    )

                        except Exception as e:
                            logger.error(f"Error processing file {file_path}: {e}")

        # Detect deletions
        for file_id, file_info in previous_state.items():
            if file_id not in current_state:
                changes.append(
                    SourceChange(
                        source_type=SourceType.LOCAL_FILESYSTEM,
                        source_id=config.source_id,
                        item_id=file_id,
                        item_path=file_info["path"],
                        change_type=ChangeType.DELETED,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        metadata=file_info,
                    )
                )

        # Save current state
        await self._save_source_state(state_file, current_state)

        return changes

    async def _detect_notion_changes(self, config: SourceConfig) -> List[SourceChange]:
        """Detect changes in Notion databases/pages"""
        changes = []
        api_key = config.config.get("api_key")
        database_ids = config.config.get("database_ids", [])
        page_ids = config.config.get("page_ids", [])

        if not api_key:
            logger.warning("Notion API key not configured")
            return changes

        # Load previous state
        state_file = os.path.join(self.state_dir, f"notion_{config.source_id}.json")
        previous_state = await self._load_source_state(state_file)
        current_state = {}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            # Check databases
            for database_id in database_ids:
                try:
                    url = f"https://api.notion.com/v1/databases/{database_id}/query"
                    async with session.post(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()

                            for page in data.get("results", []):
                                page_id = page["id"]
                                last_edited = page.get("last_edited_time", "")
                                properties = page.get("properties", {})

                                # Generate checksum from page content
                                checksum_data = {
                                    "last_edited": last_edited,
                                    "properties": properties,
                                }
                                checksum = self._generate_data_checksum(checksum_data)

                                current_state[page_id] = {
                                    "last_edited": last_edited,
                                    "properties": properties,
                                    "checksum": checksum,
                                    "url": page.get("url", ""),
                                }

                                # Detect changes
                                if page_id not in previous_state:
                                    changes.append(
                                        SourceChange(
                                            source_type=SourceType.NOTION,
                                            source_id=config.source_id,
                                            item_id=page_id,
                                            item_path=page.get("url", ""),
                                            change_type=ChangeType.CREATED,
                                            timestamp=datetime.now(
                                                timezone.utc
                                            ).isoformat(),
                                            metadata=current_state[page_id],
                                            checksum=checksum,
                                        )
                                    )
                                else:
                                    prev = previous_state[page_id]
                                    if prev["checksum"] != checksum:
                                        changes.append(
                                            SourceChange(
                                                source_type=SourceType.NOTION,
                                                source_id=config.source_id,
                                                item_id=page_id,
                                                item_path=page.get("url", ""),
                                                change_type=ChangeType.UPDATED,
                                                timestamp=datetime.now(
                                                    timezone.utc
                                                ).isoformat(),
                                                metadata=current_state[page_id],
                                                checksum=checksum,
                                            )
                                        )

                        else:
                            logger.error(f"Notion API error: {response.status}")

                except Exception as e:
                    logger.error(f"Error checking Notion database {database_id}: {e}")

        # Detect deletions
        for page_id, page_info in previous_state.items():
            if page_id not in current_state:
                changes.append(
                    SourceChange(
                        source_type=SourceType.NOTION,
                        source_id=config.source_id,
                        item_id=page_id,
                        item_path=page_info.get("url", ""),
                        change_type=ChangeType.DELETED,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        metadata=page_info,
                    )
                )

        # Save current state
        await self._save_source_state(state_file, current_state)

        return changes

    async def _detect_dropbox_changes(self, config: SourceConfig) -> List[SourceChange]:
        """Detect changes in Dropbox (placeholder implementation)"""
        # TODO: Implement Dropbox change detection using Dropbox API
        logger.info("Dropbox change detection not yet implemented")
        return []

    async def _detect_google_drive_changes(
        self, config: SourceConfig
    ) -> List[SourceChange]:
        """Detect changes in Google Drive (placeholder implementation)"""
        # TODO: Implement Google Drive change detection using Google Drive API
        logger.info("Google Drive change detection not yet implemented")
        return []

    async def _detect_s3_changes(self, config: SourceConfig) -> List[SourceChange]:
        """Detect changes in S3 bucket (placeholder implementation)"""
        # TODO: Implement S3 change detection using S3 API
        logger.info("S3 change detection not yet implemented")
        return []

    async def _handle_change(self, change: SourceChange) -> None:
        """Handle a detected change by notifying all handlers"""
        logger.info(
            f"Detected change: {change.source_type} {change.change_type} - {change.item_path}"
        )

        for handler in self.change_handlers:
            try:
                handler(change)
            except Exception as e:
                logger.error(f"Error in change handler: {e}")

    async def _generate_file_checksum(self, file_path: str) -> str:
        """Generate checksum for file content"""
        try:
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.error(f"Error generating checksum for {file_path}: {e}")
            return ""

    def _generate_data_checksum(self, data: Any) -> str:
        """Generate checksum for data object"""
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

    async def _load_source_state(self, state_file: str) -> Dict[str, Any]:
        """Load source state from file"""
        try:
            if os.path.exists(state_file):
                async with aiofiles.open(state_file, "r") as f:
                    content = await f.read()
                    return json.loads(content)
        except Exception as e:
            logger.error(f"Error loading state file {state_file}: {e}")
        return {}

    async def _save_source_state(self, state_file: str, state: Dict[str, Any]) -> None:
        """Save source state to file"""
        try:
            async with aiofiles.open(state_file, "w") as f:
                await f.write(json.dumps(state, indent=2))
        except Exception as e:
            logger.error(f"Error saving state file {state_file}: {e}")

    async def force_scan(
        self, source_type: SourceType, source_id: str
    ) -> List[SourceChange]:
        """Force a scan of a specific source"""
        source_key = f"{source_type.value}_{source_id}"
        if source_key not in self.sources:
            logger.warning(f"Source not found: {source_key}")
            return []

        config = self.sources[source_key]
        changes = await self._detect_source_changes(config)

        for change in changes:
            await self._handle_change(change)

        return changes

    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            "running": self.running,
            "sources_monitored": len(self.sources),
            "active_tasks": len(self.monitor_tasks),
            "change_handlers": len(self.change_handlers),
            "source_details": {
                key: {
                    "type": config.source_type.value,
                    "enabled": config.enabled,
                    "poll_interval": config.poll_interval,
                }
                for key, config in self.sources.items()
            },
        }


# Factory function for easy detector creation
def create_source_change_detector(
    state_dir: str = "data/sync_state",
) -> SourceChangeDetector:
    """Create a source change detector with the specified state directory"""
    return SourceChangeDetector(state_dir)

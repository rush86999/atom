"""
Atom SaaS Sync Service - Background synchronization with Atom SaaS platform.

Provides periodic polling and WebSocket-based real-time sync for skills and categories.
Integrates with AtomSaaSClient and AtomSaaSWebSocketClient for data synchronization.

Features:
- Periodic polling every 15 minutes (configurable)
- WebSocket real-time updates
- Cache management (SkillCache, CategoryCache)
- Error handling with exponential backoff
- Fallback to polling when WebSocket unavailable
- Conflict resolution for skill synchronization

Phase 61-01/61-03/61-04 - Background Sync, WebSocket Updates, Conflict Resolution
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.atom_saas_client import AtomSaaSClient
from core.atom_saas_websocket import AtomSaaSWebSocketClient, MessageType
from core.database import SessionLocal
from core.models import SkillCache, CategoryCache, SyncState, WebSocketState

logger = logging.getLogger(__name__)


class SyncService:
    """
    Sync service for Atom SaaS marketplace data.

    Features:
    - Periodic polling via AtomSaaSClient
    - Real-time updates via WebSocket
    - Cache invalidation (TTL-based)
    - Error handling and retry logic
    - Conflict resolution for skill sync
    """

    # Configuration
    DEFAULT_SYNC_INTERVAL_MINUTES = 15
    CACHE_TTL_HOURS = 24  # Cache expires after 24 hours
    MAX_BATCH_SIZE = 100  # Fetch 100 skills at a time

    # Conflict resolution configuration
    DEFAULT_CONFLICT_STRATEGY = os.getenv(
        "ATOM_SAAS_CONFLICT_STRATEGY",
        "remote_wins"
    ).lower()  # remote_wins, local_wins, merge, manual

    def __init__(self, saas_client: AtomSaaSClient, ws_client: Optional[AtomSaaSWebSocketClient] = None):
        """
        Initialize sync service.

        Args:
            saas_client: Atom SaaS API client
            ws_client: Optional WebSocket client for real-time updates
        """
        self.saas_client = saas_client
        self.ws_client = ws_client
        self._syncing = False
        self._websocket_enabled = False

        # Conflict resolution metrics
        self._conflicts_detected = 0
        self._conflicts_resolved = 0
        self._conflicts_manual = 0

        logger.info(f"SyncService initialized (conflict strategy: {self.DEFAULT_CONFLICT_STRATEGY})")

    @property
    def is_syncing(self) -> bool:
        """Check if sync is in progress."""
        return self._syncing

    @property
    def websocket_enabled(self) -> bool:
        """Check if WebSocket is enabled."""
        return self._websocket_enabled and self.ws_client and self.ws_client.is_connected

    async def start_websocket(self, message_handler: Optional[callable] = None) -> bool:
        """
        Start WebSocket connection for real-time updates.

        Args:
            message_handler: Optional callback for WebSocket messages

        Returns:
            True if WebSocket started successfully
        """
        if not self.ws_client:
            logger.warning("WebSocket client not configured")
            return False

        if self.ws_client.is_connected:
            logger.info("WebSocket already connected")
            return True

        try:
            # Use default message handler if none provided
            if not message_handler:
                message_handler = self._handle_websocket_message

            await self.ws_client.connect(message_handler)
            self._websocket_enabled = True
            logger.info("WebSocket started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start WebSocket: {e}")
            self._websocket_enabled = False
            return False

    async def stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        if self.ws_client:
            await self.ws_client.disconnect()
        self._websocket_enabled = False
        logger.info("WebSocket stopped")

    async def sync_all(self, enable_websocket: bool = True) -> Dict[str, Any]:
        """
        Perform full sync (skills + categories).

        Args:
            enable_websocket: Start WebSocket after initial sync

        Returns:
            Sync result with counts and status
        """
        if self._syncing:
            logger.warning("Sync already in progress")
            return {
                "success": False,
                "error": "sync_already_in_progress",
                "message": "Sync already in progress"
            }

        self._syncing = True
        self.reset_conflict_metrics()  # Reset metrics for this sync
        start_time = datetime.now(timezone.utc)

        try:
            # Update sync state
            self._update_sync_state(status="syncing")

            # Sync categories
            categories_result = await self.sync_categories()
            category_count = categories_result.get("count", 0)

            # Sync skills
            skills_result = await self.sync_skills()
            skill_count = skills_result.get("count", 0)

            # Start WebSocket for real-time updates
            if enable_websocket and not self._websocket_enabled:
                await self.start_websocket()

            # Update sync state
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self._update_sync_state(
                status="success",
                skills_synced=skill_count,
                categories_synced=category_count
            )

            result = {
                "success": True,
                "skills_synced": skill_count,
                "categories_synced": category_count,
                "duration_seconds": duration,
                "websocket_enabled": self._websocket_enabled,
                "conflicts": self.get_conflict_metrics()
            }

            logger.info(
                f"Sync completed: {skill_count} skills, {category_count} categories "
                f"in {duration:.2f}s | Conflicts: {self._conflicts_detected} detected, "
                f"{self._conflicts_resolved} resolved, {self._conflicts_manual} manual"
            )
            return result

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            self._update_sync_state(status="error", error_message=str(e))
            return {
                "success": False,
                "error": "sync_failed",
                "message": str(e)
            }

        finally:
            self._syncing = False

    async def sync_skills(self) -> Dict[str, Any]:
        """
        Sync all skills from Atom SaaS.

        Returns:
            Sync result with count
        """
        try:
            page = 1
            total_count = 0

            while True:
                # Fetch batch
                response = await self.saas_client.fetch_skills(
                    page=page,
                    page_size=self.MAX_BATCH_SIZE
                )

                if not response.get("skills"):
                    break

                # Cache each skill
                for skill_data in response["skills"]:
                    await self.cache_skill(skill_data)
                    total_count += 1

                # Check if more pages
                if len(response["skills"]) < self.MAX_BATCH_SIZE:
                    break

                page += 1

            logger.info(f"Synced {total_count} skills")
            return {"success": True, "count": total_count}

        except Exception as e:
            logger.error(f"Failed to sync skills: {e}")
            return {"success": False, "error": str(e), "count": 0}

    async def sync_categories(self) -> Dict[str, Any]:
        """
        Sync all categories from Atom SaaS.

        Returns:
            Sync result with count
        """
        try:
            categories = await self.saas_client.get_categories()
            count = 0

            for category_data in categories:
                await self.cache_category(category_data)
                count += 1

            logger.info(f"Synced {count} categories")
            return {"success": True, "count": count}

        except Exception as e:
            logger.error(f"Failed to sync categories: {e}")
            return {"success": False, "error": str(e), "count": 0}

    async def cache_skill(self, skill_data: Dict[str, Any]) -> None:
        """
        Cache skill data in SkillCache with conflict resolution.

        Args:
            skill_data: Skill data from Atom SaaS
        """
        try:
            from core.conflict_resolution_service import ConflictResolutionService

            with SessionLocal() as db:
                skill_id = skill_data.get("skill_id") or skill_data.get("id")
                if not skill_id:
                    logger.warning("Skill data missing skill_id")
                    return

                # Calculate expiry (end of day)
                expires_at = datetime.now(timezone.utc).replace(
                    hour=23, minute=59, second=59, microsecond=0
                )

                # Check for existing skill (potential conflict)
                existing = db.query(SkillCache).filter(
                    SkillCache.skill_id == skill_id
                ).first()

                if existing:
                    # Conflict detected: skill exists locally
                    local_skill_data = existing.skill_data

                    # Initialize conflict resolution service
                    resolver = ConflictResolutionService(db)

                    # Detect conflict
                    conflict_type = resolver.detect_skill_conflict(local_skill_data, skill_data)

                    if conflict_type:
                        # Calculate severity
                        severity = resolver.calculate_severity(
                            local_skill_data,
                            skill_data,
                            conflict_type
                        )

                        self._conflicts_detected += 1
                        logger.info(f"Conflict detected for {skill_id}: {conflict_type} ({severity})")

                        # Apply configured strategy
                        strategy = self.DEFAULT_CONFLICT_STRATEGY

                        if strategy == "manual":
                            # Log conflict for manual resolution
                            resolver.log_conflict(
                                skill_id=skill_id,
                                conflict_type=conflict_type,
                                severity=severity,
                                local_data=local_skill_data,
                                remote_data=skill_data
                            )
                            self._conflicts_manual += 1
                            logger.warning(f"Manual conflict logged for {skill_id}")
                            return  # Don't cache manual conflicts

                        # Auto-resolve with strategy
                        resolved_data = resolver.auto_resolve_conflict(
                            local_skill_data,
                            skill_data,
                            strategy
                        )

                        if resolved_data:
                            # Cache resolved data
                            existing.skill_data = resolved_data
                            existing.expires_at = expires_at
                            self._conflicts_resolved += 1
                            logger.info(f"Resolved conflict for {skill_id} using {strategy}")
                        else:
                            # Manual strategy logged conflict, don't cache
                            return
                    else:
                        # No conflict, update normally
                        existing.skill_data = skill_data
                        existing.expires_at = expires_at
                else:
                    # No existing skill, cache normally
                    cache_entry = SkillCache(
                        skill_id=skill_id,
                        skill_data=skill_data,
                        expires_at=expires_at
                    )
                    db.add(cache_entry)

                db.commit()

        except Exception as e:
            logger.error(f"Failed to cache skill: {e}")

    async def cache_category(self, category_data: Dict[str, Any]) -> None:
        """
        Cache category data in CategoryCache.

        Args:
            category_data: Category data from Atom SaaS
        """
        try:
            with SessionLocal() as db:
                category_name = category_data.get("name") or category_data.get("category")
                if not category_name:
                    logger.warning("Category data missing name")
                    return

                # Calculate expiry (end of day)
                expires_at = datetime.now(timezone.utc).replace(
                    hour=23, minute=59, second=59, microsecond=0
                )

                # Upsert to cache
                existing = db.query(CategoryCache).filter(
                    CategoryCache.category_name == category_name
                ).first()

                if existing:
                    existing.category_data = category_data
                    existing.expires_at = expires_at
                else:
                    cache_entry = CategoryCache(
                        category_name=category_name,
                        category_data=category_data,
                        expires_at=expires_at
                    )
                    db.add(cache_entry)

                db.commit()

        except Exception as e:
            logger.error(f"Failed to cache category: {e}")

    async def invalidate_expired_cache(self) -> int:
        """
        Invalidate expired cache entries.

        Returns:
            Number of entries invalidated
        """
        try:
            with SessionLocal() as db:
                now = datetime.now(timezone.utc)

                # Invalidate skills
                expired_skills = db.query(SkillCache).filter(
                    SkillCache.expires_at < now
                ).count()
                db.query(SkillCache).filter(
                    SkillCache.expires_at < now
                ).delete()

                # Invalidate categories
                expired_categories = db.query(CategoryCache).filter(
                    CategoryCache.expires_at < now
                ).count()
                db.query(CategoryCache).filter(
                    CategoryCache.expires_at < now
                ).delete()

                db.commit()

                total = expired_skills + expired_categories
                if total > 0:
                    logger.info(f"Invalidated {total} expired cache entries")

                return total

        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return 0

    async def _handle_websocket_message(self, message_type: str, data: Dict[str, Any]) -> None:
        """
        Handle WebSocket message (called by AtomSaaSWebSocketClient).

        Args:
            message_type: Type of message
            data: Message data
        """
        # Cache updates are already handled by AtomSaaSWebSocketClient._update_cache()
        # This is for any additional processing
        logger.debug(f"WebSocket message: {message_type}")

    def _update_sync_state(
        self,
        status: str = "idle",
        skills_synced: int = 0,
        categories_synced: int = 0,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update SyncState in database.

        Args:
            status: Sync status (idle/syncing/error)
            skills_synced: Number of skills synced
            categories_synced: Number of categories synced
            error_message: Error message if status is error
        """
        try:
            with SessionLocal() as db:
                # Get or create sync state (singleton for marketplace sync)
                # Note: Using a different sync state than mobile devices
                state = db.query(SyncState).filter(
                    SyncState.device_id == "marketplace_sync"
                ).first()

                if not state:
                    # Create a placeholder state for marketplace sync
                    state = SyncState(
                        id="marketplace_sync",
                        device_id="marketplace_sync",
                        user_id="system"
                    )
                    db.add(state)

                # Update fields
                state.last_sync_at = datetime.now(timezone.utc)
                state.auto_sync_enabled = True

                if status == "syncing":
                    state.total_syncs += 1
                elif status == "success":
                    state.successful_syncs += 1
                    state.last_successful_sync_at = datetime.now(timezone.utc)
                    state.pending_actions_count = 0

                    # Log conflict metrics
                    if self._conflicts_detected > 0:
                        logger.info(
                            f"Sync conflict metrics: "
                            f"{self._conflicts_detected} detected, "
                            f"{self._conflicts_resolved} auto-resolved, "
                            f"{self._conflicts_manual} manual"
                        )
                elif status == "error":
                    state.failed_syncs += 1
                    state.pending_actions_count = 1  # Trigger retry
                    if error_message:
                        logger.error(f"Sync error: {error_message}")

                db.commit()

        except Exception as e:
            logger.error(f"Failed to update sync state: {e}")

    def get_conflict_metrics(self) -> Dict[str, int]:
        """
        Get conflict resolution metrics for current sync session.

        Returns:
            Dictionary with conflict counts
        """
        return {
            "conflicts_detected": self._conflicts_detected,
            "conflicts_resolved": self._conflicts_resolved,
            "conflicts_manual": self._conflicts_manual
        }

    def reset_conflict_metrics(self) -> None:
        """Reset conflict metrics (called after each sync)."""
        self._conflicts_detected = 0
        self._conflicts_resolved = 0
        self._conflicts_manual = 0


def get_sync_status() -> Dict[str, Any]:
    """
    Get current sync status from database.

    Returns:
        Sync status dictionary
    """
    try:
        with SessionLocal() as db:
            # Get sync state
            sync_state = db.query(SyncState).filter(
                SyncState.device_id == "marketplace_sync"
            ).first()

            # Get WebSocket state
            ws_state = db.query(WebSocketState).first()

            # Get cache stats
            skill_count = db.query(SkillCache).count()
            category_count = db.query(CategoryCache).count()

            result = {
                "sync": {
                    "status": "idle",
                    "last_sync_at": None,
                    "last_successful_sync_at": None,
                    "total_syncs": 0,
                    "successful_syncs": 0,
                    "failed_syncs": 0
                },
                "websocket": {
                    "connected": False,
                    "last_connected_at": None,
                    "last_message_at": None,
                    "fallback_to_polling": False
                },
                "cache": {
                    "skills_count": skill_count,
                    "categories_count": category_count
                }
            }

            if sync_state:
                result["sync"] = {
                    "status": "syncing" if sync_state.pending_actions_count > 0 else "idle",
                    "last_sync_at": sync_state.last_sync_at.isoformat() if sync_state.last_sync_at else None,
                    "last_successful_sync_at": sync_state.last_successful_sync_at.isoformat() if sync_state.last_successful_sync_at else None,
                    "total_syncs": sync_state.total_syncs,
                    "successful_syncs": sync_state.successful_syncs,
                    "failed_syncs": sync_state.failed_syncs
                }

            if ws_state:
                result["websocket"] = {
                    "connected": ws_state.connected,
                    "last_connected_at": ws_state.last_connected_at.isoformat() if ws_state.last_connected_at else None,
                    "last_message_at": ws_state.last_message_at.isoformat() if ws_state.last_message_at else None,
                    "fallback_to_polling": ws_state.fallback_to_polling,
                    "reconnect_attempts": ws_state.reconnect_attempts
                }

            return result

    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        return {"error": str(e)}

"""
Offline Sync Service

Manages offline actions queue, sync scheduling, and conflict resolution
for mobile devices. Handles background sync operations and retry logic.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.models import MobileDevice, OfflineAction, SyncState
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)


# Sync configuration
MAX_SYNC_ATTEMPTS = 5
SYNC_BATCH_SIZE = 50
SYNC_TIMEOUT_SECONDS = 30


class OfflineSyncService:
    """
    Offline sync service for mobile devices.

    Features:
    - Queue actions when offline
    - Background sync with retry logic
    - Conflict resolution
    - Sync state tracking
    - Push notifications on sync completion
    """

    def __init__(self, db: Session):
        self.db = db

    async def queue_action(
        self,
        device_id: str,
        user_id: str,
        action_type: str,
        action_data: Dict[str, Any],
        priority: int = 0
    ) -> Dict[str, Any]:
        """
        Queue an action for offline sync.

        Args:
            device_id: Device ID
            user_id: User ID
            action_type: Type of action (agent_message, workflow_trigger, etc.)
            action_data: Action payload
            priority: Priority (higher = more important)

        Returns:
            Queued action details
        """
        try:
            action = OfflineAction(
                id=str(uuid.uuid4()),
                device_id=device_id,
                user_id=user_id,
                action_type=action_type,
                action_data=action_data,
                priority=priority,
                status="pending"
            )

            self.db.add(action)
            self.db.commit()

            # Update sync state
            sync_state = self._get_or_create_sync_state(device_id, user_id)
            sync_state.pending_actions_count += 1
            self.db.commit()

            logger.info(f"Queued action {action.id} for device {device_id}")

            return {
                "action_id": action.id,
                "status": "queued",
                "priority": priority,
                "created_at": action.created_at.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to queue action: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def sync_device_actions(
        self,
        device_id: str,
        user_id: str,
        batch_size: int = SYNC_BATCH_SIZE
    ) -> Dict[str, Any]:
        """
        Sync all pending actions for a device.

        Args:
            device_id: Device ID
            user_id: User ID
            batch_size: Max actions to sync in one batch

        Returns:
            Sync results with counts
        """
        try:
            # Get pending actions (high priority first)
            pending_actions = self.db.query(OfflineAction).filter(
                and_(
                    OfflineAction.device_id == device_id,
                    OfflineAction.status == "pending"
                )
            ).order_by(OfflineAction.priority.desc(), OfflineAction.created_at).limit(batch_size).all()

            if not pending_actions:
                return {
                    "status": "no_actions",
                    "synced_count": 0,
                    "failed_count": 0,
                    "message": "No pending actions to sync"
                }

            synced_count = 0
            failed_count = 0

            for action in pending_actions:
                try:
                    # Process action based on type
                    success = await self._process_action(action)

                    if success:
                        action.status = "completed"
                        action.synced_at = datetime.utcnow()
                        synced_count += 1
                    else:
                        action.status = "failed"
                        action.sync_attempts += 1
                        action.last_sync_error = "Processing failed"
                        failed_count += 1

                except Exception as e:
                    logger.error(f"Failed to sync action {action.id}: {e}")
                    action.status = "failed"
                    action.last_sync_error = str(e)
                    action.sync_attempts += 1
                    failed_count += 1

            self.db.commit()

            # Update sync state
            sync_state = self._get_or_create_sync_state(device_id, user_id)
            sync_state.last_sync_at = datetime.utcnow()
            if synced_count > 0:
                sync_state.last_successful_sync_at = datetime.utcnow()
            sync_state.total_syncs += 1
            sync_state.successful_syncs += synced_count
            sync_state.failed_syncs += failed_count
            sync_state.pending_actions_count -= (synced_count + failed_count)
            self.db.commit()

            # Remove old completed actions (cleanup)
            self._cleanup_old_actions(device_id)

            logger.info(f"Synced {synced_count} actions, {failed_count} failed for device {device_id}")

            return {
                "status": "success",
                "synced_count": synced_count,
                "failed_count": failed_count,
                "remaining": sync_state.pending_actions_count
            }

        except Exception as e:
            logger.error(f"Failed to sync device actions: {e}")
            return {
                "status": "error",
                "error": str(e),
                "synced_count": 0,
                "failed_count": 0
            }

    async def _process_action(self, action: OfflineAction) -> bool:
        """
        Process a single offline action.

        Args:
            action: OfflineAction to process

        Returns:
            True if successful
        """
        try:
            # ========================================================================
            # NEW: Maturity-Based Trigger Interception for Agent Actions
            # ========================================================================
            agent_id = None

            # Extract agent_id from action_data for agent-related actions
            if action.action_type in ["agent_message", "workflow_trigger", "approval_request"]:
                agent_id = action.action_data.get("agent_id")

                if agent_id:
                    from core.trigger_interceptor import TriggerInterceptor, TriggerSource

                    interceptor = TriggerInterceptor(self.db, self.workspace_id)

                    trigger_context = {
                        "action_type": action.action_type,
                        "action_data": action.action_data,
                        "offline_action_id": action.id
                    }

                    try:
                        decision = await interceptor.intercept_trigger(
                            agent_id=agent_id,
                            trigger_source=TriggerSource.DATA_SYNC,
                            trigger_context=trigger_context,
                            user_id=action.user_id
                        )

                        # Log routing decision
                        logger.info(
                            f"Offline sync routing decision for agent {agent_id}: "
                            f"{decision.routing_decision.value} (maturity: {decision.agent_maturity}, "
                            f"confidence: {decision.confidence_score:.2f})"
                        )

                        # Handle blocked triggers
                        if not decision.execute:
                            # Agent was blocked - mark action as blocked
                            action.status = "failed"
                            action.last_sync_error = (
                                f"Agent blocked by maturity guard: {decision.reason}"
                            )
                            self.db.commit()

                            logger.warning(
                                f"Offline action {action.id} blocked: {decision.reason}"
                            )
                            return False

                    except ValueError as e:
                        # Agent not found or other error - log and continue
                        logger.warning(
                            f"Could not check maturity for agent {agent_id}: {e}"
                        )
                        # Continue with processing for backward compatibility
            # ========================================================================

            if action.action_type == "agent_message":
                # Send agent message via WebSocket
                await ws_manager.broadcast(
                    f"user:{action.user_id}",
                    {
                        "type": "agent:message",
                        "data": action.action_data
                    }
                )
                return True

            elif action.action_type == "workflow_trigger":
                # Trigger workflow
                await ws_manager.broadcast(
                    f"user:{action.user_id}",
                    {
                        "type": "workflow:trigger",
                        "data": action.action_data
                    }
                )
                return True

            elif action.action_type == "form_submit":
                # Submit form data
                await ws_manager.broadcast(
                    f"user:{action.user_id}",
                    {
                        "type": "form:submit",
                        "data": action.action_data
                    }
                )
                return True

            elif action.action_type == "canvas_update":
                # Update canvas component
                await ws_manager.broadcast(
                    f"user:{action.user_id}",
                    {
                        "type": "canvas:update",
                        "data": action.action_data
                    }
                )
                return True

            elif action.action_type == "approval_request":
                # Agent approval request
                await ws_manager.broadcast(
                    f"user:{action.user_id}",
                    {
                        "type": "agent:request",
                        "data": action.action_data
                    }
                )
                return True

            else:
                logger.warning(f"Unknown action type: {action.action_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to process action {action.id}: {e}")
            return False

    async def retry_failed_actions(
        self,
        device_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Retry failed actions that haven't exceeded max attempts.

        Args:
            device_id: Device ID
            user_id: User ID

        Returns:
            Retry results
        """
        try:
            # Get failed actions with remaining attempts
            failed_actions = self.db.query(OfflineAction).filter(
                and_(
                    OfflineAction.device_id == device_id,
                    OfflineAction.status == "failed",
                    OfflineAction.sync_attempts < MAX_SYNC_ATTEMPTS
                )
            ).all()

            retried_count = 0
            for action in failed_actions:
                # Reset to pending for retry
                action.status = "pending"
                retried_count += 1

            self.db.commit()

            # Trigger sync
            result = await self.sync_device_actions(device_id, user_id)

            logger.info(f"Retried {retried_count} failed actions for device {device_id}")

            return {
                "status": "success",
                "retried_count": retried_count,
                **result
            }

        except Exception as e:
            logger.error(f"Failed to retry actions: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def get_sync_status(
        self,
        device_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get sync status for device.

        Args:
            device_id: Device ID
            user_id: User ID

        Returns:
            Sync status details
        """
        try:
            sync_state = self._get_or_create_sync_state(device_id, user_id)

            return {
                "device_id": device_id,
                "last_sync_at": sync_state.last_sync_at.isoformat() if sync_state.last_sync_at else None,
                "last_successful_sync_at": sync_state.last_successful_sync_at.isoformat() if sync_state.last_successful_sync_at else None,
                "pending_actions_count": sync_state.pending_actions_count,
                "total_syncs": sync_state.total_syncs,
                "successful_syncs": sync_state.successful_syncs,
                "failed_syncs": sync_state.failed_syncs,
                "auto_sync_enabled": sync_state.auto_sync_enabled,
                "sync_interval_seconds": sync_state.sync_interval_seconds
            }

        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def clear_pending_actions(
        self,
        device_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Clear all pending actions for device (user-initiated).

        Args:
            device_id: Device ID
            user_id: User ID

        Returns:
            Clear results
        """
        try:
            # Get pending count
            pending_count = self.db.query(OfflineAction).filter(
                and_(
                    OfflineAction.device_id == device_id,
                    OfflineAction.status == "pending"
                )
            ).count()

            # Delete pending actions
            self.db.query(OfflineAction).filter(
                and_(
                    OfflineAction.device_id == device_id,
                    OfflineAction.status == "pending"
                )
            ).delete()

            # Update sync state
            sync_state = self._get_or_create_sync_state(device_id, user_id)
            sync_state.pending_actions_count = 0
            self.db.commit()

            logger.info(f"Cleared {pending_count} pending actions for device {device_id}")

            return {
                "status": "success",
                "cleared_count": pending_count
            }

        except Exception as e:
            logger.error(f"Failed to clear pending actions: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _get_or_create_sync_state(
        self,
        device_id: str,
        user_id: str
    ) -> SyncState:
        """Get existing sync state or create new one."""
        sync_state = self.db.query(SyncState).filter(
            SyncState.device_id == device_id
        ).first()

        if not sync_state:
            sync_state = SyncState(
                id=str(uuid.uuid4()),
                device_id=device_id,
                user_id=user_id
            )
            self.db.add(sync_state)
            self.db.commit()

        return sync_state

    def _cleanup_old_actions(
        self,
        device_id: str,
        days_to_keep: int = 7
    ):
        """
        Remove old completed/failed actions.

        Args:
            device_id: Device ID
            days_to_keep: Days to keep old actions
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            # Delete old completed actions
            self.db.query(OfflineAction).filter(
                and_(
                    OfflineAction.device_id == device_id,
                    OfflineAction.status.in_(["completed", "failed"]),
                    OfflineAction.created_at < cutoff_date
                )
            ).delete()

            self.db.commit()

            logger.debug(f"Cleaned up old actions for device {device_id}")

        except Exception as e:
            logger.error(f"Failed to cleanup old actions: {e}")

    async def get_pending_actions(
        self,
        device_id: str,
        user_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get list of pending actions for device.

        Args:
            device_id: Device ID
            user_id: User ID
            limit: Max actions to return

        Returns:
            List of pending actions
        """
        try:
            actions = self.db.query(OfflineAction).filter(
                and_(
                    OfflineAction.device_id == device_id,
                    OfflineAction.status == "pending"
                )
            ).order_by(OfflineAction.priority.desc(), OfflineAction.created_at).limit(limit).all()

            return [
                {
                    "action_id": action.id,
                    "action_type": action.action_type,
                    "priority": action.priority,
                    "created_at": action.created_at.isoformat(),
                    "data": action.action_data
                }
                for action in actions
            ]

        except Exception as e:
            logger.error(f"Failed to get pending actions: {e}")
            return []


# Singleton helper
def get_offline_sync_service(db: Session) -> OfflineSyncService:
    """Get or create offline sync service instance."""
    return OfflineSyncService(db)

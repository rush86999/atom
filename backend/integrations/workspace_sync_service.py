"""
Workspace Synchronization Service

Provides cross-platform workspace synchronization for:
- Slack
- Discord
- Google Chat
- Microsoft Teams

Features:
- Unified workspace management
- Change detection and propagation
- Conflict resolution
- Member synchronization
- Comprehensive audit logging
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.models import UnifiedWorkspace, WorkspaceSyncLog

logger = logging.getLogger(__name__)


class ChangeType:
    """Types of workspace changes that trigger synchronization"""
    WORKSPACE_NAME_CHANGE = "name_change"
    WORKSPACE_DESCRIPTION_CHANGE = "description_change"
    MEMBER_ADD = "member_add"
    MEMBER_REMOVE = "member_remove"
    MEMBER_ROLE_CHANGE = "member_role_change"
    CHANNEL_ADD = "channel_add"
    CHANNEL_REMOVE = "channel_remove"
    SETTINGS_CHANGE = "settings_change"


class SyncConflictResolution:
    """Strategies for resolving sync conflicts"""
    LATEST_WINS = "latest"  # Most recent change wins
    SOURCE_WINS = "source"  # Source platform wins
    MANUAL = "manual"  # Requires manual resolution


class WorkspaceSyncService:
    """
    Service for synchronizing workspaces across multiple communication platforms.

    Usage:
        service = WorkspaceSyncService(db)

        # Create unified workspace
        workspace = service.create_unified_workspace(
            user_id="user123",
            name="My Workspace",
            slack_workspace_id="T123456"
        )

        # Add another platform
        service.add_platform_to_workspace(
            workspace_id=workspace.id,
            platform="discord",
            platform_id="guild789"
        )

        # Propagate changes
        await service.propagate_change(
            workspace_id=workspace.id,
            source_platform="slack",
            change_type=ChangeType.WORKSPACE_NAME_CHANGE,
            change_data={"old_name": "Old Name", "new_name": "New Name"}
        )
    """

    def __init__(self, db: Session):
        self.db = db

    def create_unified_workspace(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        slack_workspace_id: Optional[str] = None,
        discord_guild_id: Optional[str] = None,
        google_chat_space_id: Optional[str] = None,
        teams_team_id: Optional[str] = None,
        sync_config: Optional[Dict[str, Any]] = None
    ) -> UnifiedWorkspace:
        """
        Create a new unified workspace.

        Args:
            user_id: User who owns the workspace
            name: Workspace name
            description: Optional description
            slack_workspace_id: Optional Slack workspace ID
            discord_guild_id: Optional Discord guild ID
            google_chat_space_id: Optional Google Chat space ID
            teams_team_id: Optional Microsoft Teams team ID
            sync_config: Optional sync configuration

        Returns:
            Created UnifiedWorkspace object
        """
        try:
            workspace = UnifiedWorkspace(
                user_id=user_id,
                name=name,
                description=description,
                slack_workspace_id=slack_workspace_id,
                discord_guild_id=discord_guild_id,
                google_chat_space_id=google_chat_space_id,
                teams_team_id=teams_team_id,
                sync_config=sync_config or self._get_default_sync_config()
            )

            # Calculate platform count
            workspace.platform_count = sum([
                bool(slack_workspace_id),
                bool(discord_guild_id),
                bool(google_chat_space_id),
                bool(teams_team_id)
            ])

            self.db.add(workspace)
            self.db.commit()
            self.db.refresh(workspace)

            logger.info(
                f"Created unified workspace {workspace.id} "
                f"for user {user_id} with {workspace.platform_count} platforms"
            )

            # Log creation
            self._log_sync_operation(
                workspace_id=workspace.id,
                operation="create",
                source_platform="system",
                target_platforms=[],
                change_type="workspace_creation",
                change_data={"name": name},
                status="success"
            )

            return workspace

        except Exception as e:
            logger.error(f"Failed to create unified workspace: {e}")
            self.db.rollback()
            raise

    def add_platform_to_workspace(
        self,
        workspace_id: str,
        platform: str,
        platform_id: str
    ) -> UnifiedWorkspace:
        """
        Add a platform to an existing unified workspace.

        Args:
            workspace_id: Unified workspace ID
            platform: Platform name (slack, discord, google_chat, teams)
            platform_id: Platform-specific workspace ID

        Returns:
            Updated UnifiedWorkspace object
        """
        try:
            workspace = self.db.query(UnifiedWorkspace).filter(
                UnifiedWorkspace.id == workspace_id
            ).first()

            if not workspace:
                raise ValueError(f"Unified workspace {workspace_id} not found")

            # Check if platform already exists
            existing_id = workspace.get_platform_id(platform)
            if existing_id:
                logger.warning(
                    f"Platform {platform} already exists for workspace {workspace_id} "
                    f"with ID {existing_id}"
                )

            # Add platform
            workspace.add_platform(platform, platform_id)
            workspace.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(workspace)

            logger.info(
                f"Added platform {platform} to workspace {workspace_id} "
                f"(now has {workspace.platform_count} platforms)"
            )

            # Log operation
            self._log_sync_operation(
                workspace_id=workspace_id,
                operation="update",
                source_platform="system",
                target_platforms=[platform],
                change_type="platform_add",
                change_data={"platform": platform, "platform_id": platform_id},
                status="success"
            )

            return workspace

        except Exception as e:
            logger.error(f"Failed to add platform to workspace: {e}")
            self.db.rollback()
            raise

    def propagate_change(
        self,
        workspace_id: str,
        source_platform: str,
        change_type: str,
        change_data: Dict[str, Any],
        conflict_resolution: str = SyncConflictResolution.LATEST_WINS
    ) -> Dict[str, Any]:
        """
        Propagate a change from one platform to all other connected platforms.

        Args:
            workspace_id: Unified workspace ID
            source_platform: Platform where the change originated
            change_type: Type of change (name_change, member_add, etc.)
            change_data: Details of the change
            conflict_resolution: Strategy for resolving conflicts

        Returns:
            Result dict with success/failure status for each target platform
        """
        try:
            workspace = self.db.query(UnifiedWorkspace).filter(
                UnifiedWorkspace.id == workspace_id
            ).first()

            if not workspace:
                raise ValueError(f"Unified workspace {workspace_id} not found")

            # Get all connected platforms except source
            target_platforms = self._get_connected_platforms(workspace, exclude=source_platform)

            if not target_platforms:
                logger.info(f"No other platforms to sync for workspace {workspace_id}")
                return {"status": "no_targets", "targets": []}

            logger.info(
                f"Propagating {change_type} from {source_platform} "
                f"to {len(target_platforms)} platforms for workspace {workspace_id}"
            )

            # Log start of sync operation
            sync_log_id = self._log_sync_operation(
                workspace_id=workspace_id,
                operation="propagate",
                source_platform=source_platform,
                target_platforms=target_platforms,
                change_type=change_type,
                change_data=change_data,
                status="in_progress"
            )

            # Propagate to each target platform
            results = {}
            successful_platforms = []
            failed_platforms = []

            for target_platform in target_platforms:
                try:
                    result = self._apply_change_to_platform(
                        workspace=workspace,
                        target_platform=target_platform,
                        change_type=change_type,
                        change_data=change_data,
                        conflict_resolution=conflict_resolution
                    )
                    results[target_platform] = result

                    if result.get("success"):
                        successful_platforms.append(target_platform)
                    else:
                        failed_platforms.append(target_platform)

                except Exception as e:
                    logger.error(
                        f"Failed to propagate change to {target_platform}: {e}"
                    )
                    results[target_platform] = {
                        "success": False,
                        "error": str(e)
                    }
                    failed_platforms.append(target_platform)

            # Update sync log with final status
            overall_status = "success" if not failed_platforms else (
                "partial_failure" if successful_platforms else "failure"
            )

            self._update_sync_log(
                log_id=sync_log_id,
                status=overall_status,
                completed_at=datetime.utcnow(),
                error_message=None if overall_status == "success" else f"{len(failed_platforms)} platforms failed"
            )

            # Update workspace last sync time
            workspace.last_sync_at = datetime.utcnow()
            if overall_status == "failure":
                workspace.sync_status = "error"
                workspace.last_sync_error = f"Failed to sync to {len(failed_platforms)} platforms"
            else:
                workspace.sync_status = "active"
                workspace.last_sync_error = None

            self.db.commit()

            logger.info(
                f"Sync completed for workspace {workspace_id}: "
                f"{len(successful_platforms)} successful, {len(failed_platforms)} failed"
            )

            return {
                "status": overall_status,
                "successful_platforms": successful_platforms,
                "failed_platforms": failed_platforms,
                "results": results
            }

        except Exception as e:
            logger.error(f"Failed to propagate change: {e}")
            self.db.rollback()
            raise

    def get_workspace_sync_status(self, workspace_id: str) -> Dict[str, Any]:
        """
        Get sync status for a unified workspace.

        Args:
            workspace_id: Unified workspace ID

        Returns:
            Status dict with sync information
        """
        workspace = self.db.query(UnifiedWorkspace).filter(
            UnifiedWorkspace.id == workspace_id
        ).first()

        if not workspace:
            raise ValueError(f"Unified workspace {workspace_id} not found")

        # Get recent sync logs
        recent_logs = self.db.query(WorkspaceSyncLog).filter(
            WorkspaceSyncLog.unified_workspace_id == workspace_id
        ).order_by(WorkspaceSyncLog.started_at.desc()).limit(10).all()

        return {
            "workspace_id": workspace.id,
            "name": workspace.name,
            "sync_status": workspace.sync_status,
            "last_sync_at": workspace.last_sync_at.isoformat() if workspace.last_sync_at else None,
            "last_sync_error": workspace.last_sync_error,
            "platforms": {
                "slack": workspace.slack_workspace_id,
                "discord": workspace.discord_guild_id,
                "google_chat": workspace.google_chat_space_id,
                "teams": workspace.teams_team_id
            },
            "platform_count": workspace.platform_count,
            "recent_syncs": [
                {
                    "operation": log.operation,
                    "source_platform": log.source_platform,
                    "target_platforms": log.target_platforms,
                    "change_type": log.change_type,
                    "status": log.status,
                    "started_at": log.started_at.isoformat(),
                    "duration_ms": log.duration_ms
                }
                for log in recent_logs
            ]
        }

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _get_default_sync_config(self) -> Dict[str, Any]:
        """Get default sync configuration"""
        return {
            "auto_sync": True,
            "conflict_resolution": SyncConflictResolution.LATEST_WINS,
            "sync_members": True,
            "sync_channels": False,
            "sync_settings": False
        }

    def _get_connected_platforms(
        self,
        workspace: UnifiedWorkspace,
        exclude: Optional[str] = None
    ) -> List[str]:
        """Get list of connected platforms (excluding one if specified)"""
        platforms = []

        if workspace.slack_workspace_id and exclude != "slack":
            platforms.append("slack")
        if workspace.discord_guild_id and exclude != "discord":
            platforms.append("discord")
        if workspace.google_chat_space_id and exclude != "google_chat":
            platforms.append("google_chat")
        if workspace.teams_team_id and exclude != "teams":
            platforms.append("teams")

        return platforms

    def _apply_change_to_platform(
        self,
        workspace: UnifiedWorkspace,
        target_platform: str,
        change_type: str,
        change_data: Dict[str, Any],
        conflict_resolution: str
    ) -> Dict[str, Any]:
        """
        Apply a change to a specific target platform.

        This is a placeholder that should be implemented with actual
        API calls to each platform's API.

        Args:
            workspace: Unified workspace
            target_platform: Platform to apply change to
            change_type: Type of change
            change_data: Change details
            conflict_resolution: Conflict resolution strategy

        Returns:
            Result dict with success status
        """
        # TODO: Implement actual platform API calls
        # For now, return success for all platforms

        platform_apis = {
            "slack": "integrations.atom_slack_integration.SlackIntegration",
            "discord": "integrations.atom_discord_integration.DiscordIntegration",
            "google_chat": "integrations.atom_google_chat_integration.GoogleChatIntegration",
            "teams": "integrations.atom_teams_integration.TeamsIntegration"
        }

        logger.info(
            f"Would apply {change_type} to {target_platform} "
            f"(platform_id={workspace.get_platform_id(target_platform)})"
        )

        return {
            "success": True,
            "message": f"Change applied to {target_platform} (placeholder implementation)"
        }

    def _log_sync_operation(
        self,
        workspace_id: str,
        operation: str,
        source_platform: str,
        target_platforms: List[str],
        change_type: str,
        change_data: Dict[str, Any],
        status: str
    ) -> str:
        """Log a sync operation to the database"""
        log = WorkspaceSyncLog(
            unified_workspace_id=workspace_id,
            operation=operation,
            source_platform=source_platform,
            target_platforms=target_platforms,
            change_type=change_type,
            change_data=change_data,
            status=status,
            started_at=datetime.utcnow()
        )

        self.db.add(log)
        self.db.flush()  # Get ID without committing

        return log.id

    def _update_sync_log(
        self,
        log_id: str,
        status: str,
        completed_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ):
        """Update an existing sync log"""
        log = self.db.query(WorkspaceSyncLog).filter(
            WorkspaceSyncLog.id == log_id
        ).first()

        if log:
            log.status = status
            log.completed_at = completed_at
            log.error_message = error_message

            if log.started_at and completed_at:
                duration_ms = int((completed_at - log.started_at).total_seconds() * 1000)
                log.duration_ms = duration_ms

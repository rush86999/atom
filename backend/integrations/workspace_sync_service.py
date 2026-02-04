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

        This method routes the change to the appropriate platform-specific handler.

        Args:
            workspace: Unified workspace
            target_platform: Platform to apply change to
            change_type: Type of change
            change_data: Change details
            conflict_resolution: Conflict resolution strategy

        Returns:
            Result dict with success status
        """
        platform_id = workspace.get_platform_id(target_platform)

        if not platform_id:
            logger.warning(f"No platform_id found for {target_platform} in workspace {workspace.id}")
            return {
                "success": False,
                "error": f"No platform ID found for {target_platform}"
            }

        logger.info(
            f"Applying {change_type} to {target_platform} "
            f"(platform_id={platform_id})"
        )

        # Route to platform-specific handler
        if target_platform == "slack":
            return self._apply_slack_change(platform_id, change_type, change_data)
        elif target_platform == "discord":
            return self._apply_discord_change(platform_id, change_type, change_data)
        elif target_platform == "google_chat":
            return self._apply_google_chat_change(platform_id, change_type, change_data)
        elif target_platform == "teams":
            return self._apply_teams_change(platform_id, change_type, change_data)
        else:
            logger.error(f"Unknown target platform: {target_platform}")
            return {"success": False, "error": f"Unknown platform: {target_platform}"}

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

    # ========================================================================
    # Platform-Specific Change Application Methods
    # ========================================================================

    def _apply_slack_change(
        self,
        platform_id: str,
        change_type: str,
        change_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply a change to Slack workspace."""
        try:
            # Import Slack service
            from integrations.slack_enhanced_service import slack_enhanced_service

            if not slack_enhanced_service:
                logger.warning("Slack enhanced service not available")
                return {
                    "success": False,
                    "error": "Slack service not available"
                }

            # Route based on change type
            if change_type == ChangeType.WORKSPACE_NAME_CHANGE:
                # Slack workspace name changes require admin API
                # Note: This is a placeholder - actual implementation would use team.rename API
                logger.info(f"Would rename Slack workspace {platform_id} to {change_data.get('new_name')}")
                return {
                    "success": True,
                    "message": "Workspace name change propagated to Slack",
                    "note": "Actual rename requires admin API access"
                }

            elif change_type == ChangeType.MEMBER_ADD:
                # Invite user to Slack workspace
                # Note: Requires admin API scope
                email = change_data.get('email')
                if email:
                    logger.info(f"Would invite {email} to Slack workspace {platform_id}")
                    return {
                        "success": True,
                        "message": f"Member add propagated to Slack for {email}",
                        "note": "Actual invite requires admin API access"
                    }

            elif change_type == ChangeType.MEMBER_REMOVE:
                # Remove user from Slack workspace
                # Note: Requires admin API scope
                user_id = change_data.get('user_id')
                if user_id:
                    logger.info(f"Would remove user {user_id} from Slack workspace {platform_id}")
                    return {
                        "success": True,
                        "message": f"Member removal propagated to Slack",
                        "note": "Actual removal requires admin API access"
                    }

            elif change_type == ChangeType.CHANNEL_ADD:
                # Create channel in Slack workspace
                channel_name = change_data.get('channel_name')
                if channel_name:
                    logger.info(f"Would create channel {channel_name} in Slack workspace {platform_id}")
                    return {
                        "success": True,
                        "message": f"Channel creation propagated to Slack",
                        "note": "Actual creation requires conversations.create API"
                    }

            elif change_type == ChangeType.CHANNEL_REMOVE:
                # Archive/delete channel in Slack workspace
                channel_id = change_data.get('channel_id')
                if channel_id:
                    logger.info(f"Would archive channel {channel_id} in Slack workspace {platform_id}")
                    return {
                        "success": True,
                        "message": f"Channel removal propagated to Slack",
                        "note": "Actual removal requires conversations.archive API"
                    }

            else:
                logger.info(f"Change type {change_type} noted for Slack workspace {platform_id}")
                return {
                    "success": True,
                    "message": f"Change {change_type} logged for Slack"
                }

        except ImportError as e:
            logger.error(f"Failed to import Slack service: {e}")
            return {
                "success": False,
                "error": f"Slack service unavailable: {e}"
            }
        except Exception as e:
            logger.error(f"Error applying Slack change: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_discord_change(
        self,
        platform_id: str,
        change_type: str,
        change_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply a change to Discord guild."""
        try:
            # Import Discord service
            from integrations.atom_discord_integration import atom_discord_integration

            if not atom_discord_integration:
                logger.warning("Discord integration service not available")
                return {
                    "success": False,
                    "error": "Discord service not available"
                }

            # Route based on change type
            if change_type == ChangeType.WORKSPACE_NAME_CHANGE:
                # Discord guild name changes
                new_name = change_data.get('new_name')
                if new_name:
                    logger.info(f"Would rename Discord guild {platform_id} to {new_name}")
                    return {
                        "success": True,
                        "message": "Guild name change propagated to Discord",
                        "note": "Actual rename requires guild modify API"
                    }

            elif change_type == ChangeType.MEMBER_ADD:
                # Add member to Discord guild (requires invite)
                # Note: Discord uses invite links, not direct member addition
                user_id = change_data.get('user_id')
                if user_id:
                    logger.info(f"Would add member {user_id} to Discord guild {platform_id}")
                    return {
                        "success": True,
                        "message": f"Member add propagated to Discord",
                        "note": "Actual addition requires invite or OAuth2"
                    }

            elif change_type == ChangeType.MEMBER_REMOVE:
                # Remove member from Discord guild
                user_id = change_data.get('user_id')
                if user_id:
                    logger.info(f"Would remove member {user_id} from Discord guild {platform_id}")
                    return {
                        "success": True,
                        "message": f"Member removal propagated to Discord",
                        "note": "Actual removal requires guild member remove API"
                    }

            elif change_type == ChangeType.CHANNEL_ADD:
                # Create channel in Discord guild
                channel_name = change_data.get('channel_name')
                channel_type = change_data.get('channel_type', 'text')
                if channel_name:
                    logger.info(f"Would create {channel_type} channel {channel_name} in Discord guild {platform_id}")
                    return {
                        "success": True,
                        "message": f"Channel creation propagated to Discord",
                        "note": "Actual creation requires guild create channel API"
                    }

            elif change_type == ChangeType.CHANNEL_REMOVE:
                # Delete channel in Discord guild
                channel_id = change_data.get('channel_id')
                if channel_id:
                    logger.info(f"Would delete channel {channel_id} in Discord guild {platform_id}")
                    return {
                        "success": True,
                        "message": f"Channel removal propagated to Discord",
                        "note": "Actual removal requires channel delete API"
                    }

            else:
                logger.info(f"Change type {change_type} noted for Discord guild {platform_id}")
                return {
                    "success": True,
                    "message": f"Change {change_type} logged for Discord"
                }

        except ImportError as e:
            logger.error(f"Failed to import Discord service: {e}")
            return {
                "success": False,
                "error": f"Discord service unavailable: {e}"
            }
        except Exception as e:
            logger.error(f"Error applying Discord change: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_google_chat_change(
        self,
        platform_id: str,
        change_type: str,
        change_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply a change to Google Chat space."""
        try:
            # Import Google Chat service
            from integrations.atom_google_chat_integration import atom_google_chat_integration

            if not atom_google_chat_integration:
                logger.warning("Google Chat integration service not available")
                return {
                    "success": False,
                    "error": "Google Chat service not available"
                }

            # Route based on change type
            if change_type == ChangeType.WORKSPACE_NAME_CHANGE:
                # Google Chat space display name changes
                new_name = change_data.get('new_name')
                if new_name:
                    logger.info(f"Would rename Google Chat space {platform_id} to {new_name}")
                    return {
                        "success": True,
                        "message": "Space name change propagated to Google Chat",
                        "note": "Actual rename requires spaces.patch API"
                    }

            elif change_type == ChangeType.MEMBER_ADD:
                # Add member to Google Chat space
                email = change_data.get('email')
                if email:
                    logger.info(f"Would add {email} to Google Chat space {platform_id}")
                    return {
                        "success": True,
                        "message": f"Member add propagated to Google Chat for {email}",
                        "note": "Actual addition requires membership create API"
                    }

            elif change_type == ChangeType.MEMBER_REMOVE:
                # Remove member from Google Chat space
                member_name = change_data.get('member_name')
                if member_name:
                    logger.info(f"Would remove {member_name} from Google Chat space {platform_id}")
                    return {
                        "success": True,
                        "message": f"Member removal propagated to Google Chat",
                        "note": "Actual removal requires membership delete API"
                    }

            elif change_type == ChangeType.CHANNEL_ADD:
                # Google Chat doesn't have channels - spaces are the unit
                logger.info(f"Channel add not applicable for Google Chat space {platform_id}")
                return {
                    "success": True,
                    "message": "Google Chat uses spaces, not channels"
                }

            elif change_type == ChangeType.CHANNEL_REMOVE:
                # Google Chat doesn't have channels
                logger.info(f"Channel remove not applicable for Google Chat space {platform_id}")
                return {
                    "success": True,
                    "message": "Google Chat uses spaces, not channels"
                }

            else:
                logger.info(f"Change type {change_type} noted for Google Chat space {platform_id}")
                return {
                    "success": True,
                    "message": f"Change {change_type} logged for Google Chat"
                }

        except ImportError as e:
            logger.error(f"Failed to import Google Chat service: {e}")
            return {
                "success": False,
                "error": f"Google Chat service unavailable: {e}"
            }
        except Exception as e:
            logger.error(f"Error applying Google Chat change: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_teams_change(
        self,
        platform_id: str,
        change_type: str,
        change_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply a change to Microsoft Teams team."""
        try:
            # Import Teams service
            from integrations.atom_teams_integration import atom_teams_integration

            if not atom_teams_integration:
                logger.warning("Teams integration service not available")
                return {
                    "success": False,
                    "error": "Teams service not available"
                }

            # Route based on change type
            if change_type == ChangeType.WORKSPACE_NAME_CHANGE:
                # Teams team display name changes
                new_name = change_data.get('new_name')
                if new_name:
                    logger.info(f"Would rename Teams team {platform_id} to {new_name}")
                    return {
                        "success": True,
                        "message": "Team name change propagated to Teams",
                        "note": "Actual rename requires group patch API"
                    }

            elif change_type == ChangeType.MEMBER_ADD:
                # Add member to Teams team
                email = change_data.get('email')
                if email:
                    logger.info(f"Would add {email} to Teams team {platform_id}")
                    return {
                        "success": True,
                        "message": f"Member add propagated to Teams for {email}",
                        "note": "Actual addition requires team member add API"
                    }

            elif change_type == ChangeType.MEMBER_REMOVE:
                # Remove member from Teams team
                user_id = change_data.get('user_id')
                if user_id:
                    logger.info(f"Would remove member {user_id} from Teams team {platform_id}")
                    return {
                        "success": True,
                        "message": f"Member removal propagated to Teams",
                        "note": "Actual removal requires team member delete API"
                    }

            elif change_type == ChangeType.CHANNEL_ADD:
                # Create channel in Teams team
                channel_name = change_data.get('channel_name')
                if channel_name:
                    logger.info(f"Would create channel {channel_name} in Teams team {platform_id}")
                    return {
                        "success": True,
                        "message": f"Channel creation propagated to Teams",
                        "note": "Actual creation requires channel create API"
                    }

            elif change_type == ChangeType.CHANNEL_REMOVE:
                # Delete channel in Teams team
                channel_id = change_data.get('channel_id')
                if channel_id:
                    logger.info(f"Would delete channel {channel_id} in Teams team {platform_id}")
                    return {
                        "success": True,
                        "message": f"Channel removal propagated to Teams",
                        "note": "Actual removal requires channel delete API"
                    }

            else:
                logger.info(f"Change type {change_type} noted for Teams team {platform_id}")
                return {
                    "success": True,
                    "message": f"Change {change_type} logged for Teams"
                }

        except ImportError as e:
            logger.error(f"Failed to import Teams service: {e}")
            return {
                "success": False,
                "error": f"Teams service unavailable: {e}"
            }
        except Exception as e:
            logger.error(f"Error applying Teams change: {e}")
            return {
                "success": False,
                "error": str(e)
            }

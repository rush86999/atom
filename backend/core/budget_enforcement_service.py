"""
Budget Enforcement Service for ATOM SaaS

Handles budget enforcement with four configurable modes:
- alert_only: Continue all operations, send notifications only
- soft_stop: Prevent new episodes, allow active to complete
- hard_stop: Halt all operations immediately
- approval: Require admin approval to continue
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.models import Tenant, AgentExecution, TenantSetting
from core.database import SessionLocal
from core.spend_aggregation_service import SpendAggregationService
from core.notification_service import NotificationService

logger = logging.getLogger(__name__)


# Budget enforcement exceptions
class BudgetError(Exception):
    """Base exception for budget enforcement errors"""
    pass


class InsufficientBudgetError(BudgetError):
    """Raised when budget is insufficient for an operation"""
    pass


class BudgetNotFoundError(BudgetError):
    """Raised when a budget is not found"""
    pass


class ConcurrentModificationError(BudgetError):
    """Raised when concurrent modification is detected"""
    pass


# Enforcement modes
class BudgetEnforcementMode:
    ALERT_ONLY = "alert_only"
    SOFT_STOP = "soft_stop"
    HARD_STOP = "hard_stop"
    APPROVAL = "approval"

    ALL = [ALERT_ONLY, SOFT_STOP, HARD_STOP, APPROVAL]


class BudgetEnforcementService:
    """
    Budget enforcement service with configurable modes.

    Checks budget before agent actions, enforces limits based on mode,
    stores enforcement state in tenant.settings JSONB.
    """

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
        self.spend_service = SpendAggregationService(self.db)
        self.notification_service = NotificationService(db_session=self.db)

    async def check_budget_before_action(
        self,
        tenant_id: str,
        agent_id: str,
        action: str,
        chain_id: Optional[str] = None # Phase 10
    ) -> Dict[str, Any]:
        """
        Check if action is allowed under current budget and enforcement mode.

        Returns:
            {
                "allowed": bool,
                "reason": str | None,
                "enforcement_mode": str,
                "current_spend_usd": float,
                "budget_limit_usd": float,
                "utilization_percent": float
            }
        """
        try:
            # Get current spend from SpendAggregationService
            spend_result = self.spend_service.update_tenant_spend(tenant_id)

            if "error" in spend_result:
                # Fail-open: allow action if spend check fails
                logger.warning(
                    f"[BudgetEnforcementService] Unable to verify spend for tenant {tenant_id}: "
                    f"{spend_result.get('error')}"
                )
                return {
                    "allowed": True,
                    "reason": "Unable to verify spend",
                    "enforcement_mode": "unknown",
                    "current_spend_usd": 0.0,
                    "budget_limit_usd": 0.0,
                    "utilization_percent": 0.0
                }

            current_spend = spend_result.get("current_spend_usd", 0.0)
            budget_limit = spend_result.get("budget_limit_usd", 0.0)
            utilization = spend_result.get("utilization_percent", 0.0)

            # Get enforcement mode from tenant.settings
            enforcement_mode = self._get_enforcement_mode(tenant_id)

            # Check if budget exceeded
            budget_exceeded = utilization >= 100.0 or current_spend >= budget_limit

            if not budget_exceeded:
                # Phase 10: Fleet Aggregate Check
                if chain_id:
                    from core.models import DelegationChain
                    chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
                    if chain:
                        fleet_spend = self.spend_service.get_fleet_spend(chain_id)
                        fleet_limit = chain.total_spend_usd or 0.0 # Aggregate cap for this recruitment chain

                        if fleet_limit > 0 and fleet_spend >= fleet_limit:
                            logger.warning(f"Fleet aggregate budget exceeded for chain {chain_id}: ${fleet_spend:.2f} >= ${fleet_limit:.2f}")
                            return {
                                "allowed": False,
                                "reason": f"Fleet aggregate budget limit (${fleet_limit:.2f}) reached.",
                                "enforcement_mode": enforcement_mode,
                                "current_spend_usd": fleet_spend,
                                "budget_limit_usd": fleet_limit,
                                "utilization_percent": (fleet_spend / fleet_limit * 100) if fleet_limit > 0 else 0
                            }

                return {
                    "allowed": True,
                    "reason": None,
                    "enforcement_mode": enforcement_mode,
                    "current_spend_usd": current_spend,
                    "budget_limit_usd": budget_limit,
                    "utilization_percent": utilization
                }

            # Budget exceeded - apply enforcement mode
            if enforcement_mode == BudgetEnforcementMode.ALERT_ONLY:
                # Phase 71 behavior - notifications only, allow all actions
                return {
                    "allowed": True,
                    "reason": None,
                    "enforcement_mode": enforcement_mode,
                    "current_spend_usd": current_spend,
                    "budget_limit_usd": budget_limit,
                    "utilization_percent": utilization
                }

            elif enforcement_mode == BudgetEnforcementMode.SOFT_STOP:
                # Prevent new episodes, allow active to complete
                if self._has_active_episodes(tenant_id, agent_id):
                    return {
                        "allowed": True,
                        "reason": "Active episode allowed to complete",
                        "enforcement_mode": enforcement_mode,
                        "current_spend_usd": current_spend,
                        "budget_limit_usd": budget_limit,
                        "utilization_percent": utilization
                    }
                else:
                    return {
                        "allowed": False,
                        "reason": "Budget exceeded. New episodes blocked. Active episodes will complete.",
                        "enforcement_mode": enforcement_mode,
                        "current_spend_usd": current_spend,
                        "budget_limit_usd": budget_limit,
                        "utilization_percent": utilization
                    }

            elif enforcement_mode == BudgetEnforcementMode.HARD_STOP:
                # Halt all operations immediately
                return {
                    "allowed": False,
                    "reason": "Budget exceeded. All operations halted immediately.",
                    "enforcement_mode": enforcement_mode,
                    "current_spend_usd": current_spend,
                    "budget_limit_usd": budget_limit,
                    "utilization_percent": utilization
                }

            elif enforcement_mode == BudgetEnforcementMode.APPROVAL:
                # Check if admin has approved override
                override = self._get_budget_override(tenant_id)
                if override and self._is_override_valid(override):
                    return {
                        "allowed": True,
                        "reason": "Admin override approved",
                        "enforcement_mode": enforcement_mode,
                        "current_spend_usd": current_spend,
                        "budget_limit_usd": budget_limit,
                        "utilization_percent": utilization
                    }
                else:
                    return {
                        "allowed": False,
                        "reason": "Budget exceeded. Admin approval required to continue.",
                        "enforcement_mode": enforcement_mode,
                        "current_spend_usd": current_spend,
                        "budget_limit_usd": budget_limit,
                        "utilization_percent": utilization
                    }

            # Default fail-open
            return {
                "allowed": True,
                "reason": None,
                "enforcement_mode": enforcement_mode,
                "current_spend_usd": current_spend,
                "budget_limit_usd": budget_limit,
                "utilization_percent": utilization
            }

        except Exception as e:
            logger.error(f"[BudgetEnforcementService] Error checking budget: {str(e)}")
            # Fail-open on errors
            return {
                "allowed": True,
                "reason": "Unable to verify spend",
                "enforcement_mode": "unknown",
                "current_spend_usd": 0.0,
                "budget_limit_usd": 0.0,
                "utilization_percent": 0.0
            }

    async def enforce_budget(
        self,
        tenant_id: str,
        current_spend: float,
        budget_limit: float,
        utilization_percent: float
    ) -> Dict[str, Any]:
        """
        Enforce budget when threshold exceeded.

        Called by SpendAggregationWorker when utilization >= 100%.
        Sends notifications, cancels active episodes (hard-stop), etc.
        """
        try:
            enforcement_mode = self._get_enforcement_mode(tenant_id)

            # Get tenant for notification
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return {
                    "success": False,
                    "error": f"Tenant {tenant_id} not found"
                }

            # Send notification based on mode
            if enforcement_mode == BudgetEnforcementMode.HARD_STOP:
                # Cancel all active episodes
                cancelled_count = self._cancel_active_episodes(tenant_id)

                # Send notification
                await self._send_enforcement_notification(
                    tenant_id=tenant_id,
                    mode=enforcement_mode,
                    current_spend=current_spend,
                    budget_limit=budget_limit,
                    utilization_percent=utilization_percent,
                    details=f"All operations halted. {cancelled_count} active episodes cancelled."
                )

                logger.info(
                    f"[BudgetEnforcementService] Hard-stop enforced for tenant {tenant_id}: "
                    f"{cancelled_count} episodes cancelled"
                )

                return {
                    "success": True,
                    "enforcement_mode": enforcement_mode,
                    "episodes_cancelled": cancelled_count,
                    "notification_sent": True
                }

            elif enforcement_mode == BudgetEnforcementMode.SOFT_STOP:
                # Send notification
                await self._send_enforcement_notification(
                    tenant_id=tenant_id,
                    mode=enforcement_mode,
                    current_spend=current_spend,
                    budget_limit=budget_limit,
                    utilization_percent=utilization_percent,
                    details="New episodes blocked. Active episodes will complete."
                )

                logger.info(
                    f"[BudgetEnforcementService] Soft-stop enforced for tenant {tenant_id}"
                )

                return {
                    "success": True,
                    "enforcement_mode": enforcement_mode,
                    "notification_sent": True
                }

            elif enforcement_mode == BudgetEnforcementMode.APPROVAL:
                # Check if override exists
                override = self._get_budget_override(tenant_id)
                if override and self._is_override_valid(override):
                    # Override active, no action needed
                    return {
                        "success": True,
                        "enforcement_mode": enforcement_mode,
                        "override_active": True
                    }

                # Send notification requesting approval
                await self._send_enforcement_notification(
                    tenant_id=tenant_id,
                    mode=enforcement_mode,
                    current_spend=current_spend,
                    budget_limit=budget_limit,
                    utilization_percent=utilization_percent,
                    details="Admin approval required to continue operations."
                )

                logger.info(
                    f"[BudgetEnforcementService] Approval mode enforced for tenant {tenant_id}"
                )

                return {
                    "success": True,
                    "enforcement_mode": enforcement_mode,
                    "notification_sent": True,
                    "approval_required": True
                }

            else:  # ALERT_ONLY
                # No enforcement, just logging
                logger.info(
                    f"[BudgetEnforcementService] Alert-only mode for tenant {tenant_id}, "
                    f"no enforcement action taken"
                )

                return {
                    "success": True,
                    "enforcement_mode": enforcement_mode,
                    "enforcement_action": "none"
                }

        except Exception as e:
            logger.error(f"[BudgetEnforcementService] Error enforcing budget: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _get_enforcement_mode(self, tenant_id: str) -> str:
        """
        Get enforcement mode from tenant.settings['billing']['enforcement']['mode'].
        Defaults to 'alert_only' if not set.
        """
        try:
            existing_setting = self.db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key == 'billing'
            ).first()

            if existing_setting and existing_setting.setting_value:
                settings_dict = json.loads(existing_setting.setting_value)
                enforcement = settings_dict.get('enforcement', {})
                mode = enforcement.get('mode', BudgetEnforcementMode.ALERT_ONLY)

                # Validate mode
                if mode not in BudgetEnforcementMode.ALL:
                    logger.warning(
                        f"[BudgetEnforcementService] Invalid enforcement mode '{mode}' "
                        f"for tenant {tenant_id}, defaulting to alert_only"
                    )
                    return BudgetEnforcementMode.ALERT_ONLY

                return mode

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"[BudgetEnforcementService] Error reading enforcement mode: {e}")

        return BudgetEnforcementMode.ALERT_ONLY

    def _get_budget_override(self, tenant_id: str) -> Optional[Dict]:
        """
        Get admin override from tenant.settings['billing']['enforcement']['override'].
        Returns None if no override exists.
        """
        try:
            existing_setting = self.db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key == 'billing'
            ).first()

            if existing_setting and existing_setting.setting_value:
                settings_dict = json.loads(existing_setting.setting_value)
                enforcement = settings_dict.get('enforcement', {})
                override = enforcement.get('override')

                return override

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"[BudgetEnforcementService] Error reading override: {e}")

        return None

    def _is_override_valid(self, override: Dict) -> bool:
        """
        Check if override is still valid (not expired).
        Override expires after 1 hour OR on billing cycle reset.
        """
        if not override:
            return False

        try:
            expires_at_str = override.get('expires_at')
            if not expires_at_str:
                return False

            expires_at = datetime.fromisoformat(expires_at_str)
            return datetime.now(timezone.utc) < expires_at

        except (ValueError, TypeError) as e:
            logger.warning(f"[BudgetEnforcementService] Error validating override: {e}")
            return False

    def _set_budget_override(self, tenant_id: str, user_id: str) -> Dict:
        """
        Set admin override with expiry (1 hour from now).
        """
        try:
            from core.models import Tenant

            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return {
                    "success": False,
                    "error": f"Tenant {tenant_id} not found"
                }

            # Get or initialize settings dict
            settings_dict = {}
            existing_setting = self.db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key == 'billing'
            ).first()

            if existing_setting and existing_setting.setting_value:
                try:
                    settings_dict = json.loads(existing_setting.setting_value)
                except (json.JSONDecodeError, TypeError):
                    settings_dict = {}

            # Initialize enforcement dict if needed
            if 'enforcement' not in settings_dict:
                settings_dict['enforcement'] = {}

            # Set override with 1-hour expiry
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            settings_dict['enforcement']['override'] = {
                'user_id': user_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'expires_at': expires_at.isoformat()
            }

            # Update settings
            settings_json = json.dumps(settings_dict)

            if existing_setting:
                existing_setting.setting_value = settings_json
            else:
                new_setting = TenantSetting(
                    tenant_id=tenant.id,
                    setting_key='billing',
                    setting_value=settings_json
                )
                self.db.add(new_setting)

            self.db.flush()

            logger.info(
                f"[BudgetEnforcementService] Budget override set for tenant {tenant_id} "
                f"by user {user_id}, expires at {expires_at.isoformat()}"
            )

            return {
                "success": True,
                "expires_at": expires_at.isoformat()
            }

        except Exception as e:
            logger.error(f"[BudgetEnforcementService] Error setting override: {str(e)}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }

    def _has_active_episodes(self, tenant_id: str, agent_id: str) -> bool:
        """
        Check if agent has active (running) episodes.
        """
        try:
            active_count = self.db.query(func.count(AgentExecution.id)).filter(
                AgentExecution.tenant_id == tenant_id,
                AgentExecution.agent_id == agent_id,
                AgentExecution.status == "running"
            ).scalar()

            return active_count > 0

        except Exception as e:
            logger.error(f"[BudgetEnforcementService] Error checking active episodes: {str(e)}")
            return False

    def _cancel_active_episodes(self, tenant_id: str) -> int:
        """
        Mark all running episodes as cancelled (hard-stop mode).
        Returns count of cancelled episodes.
        """
        try:
            # Query all running episodes for tenant
            running_episodes = self.db.query(AgentExecution).filter(
                AgentExecution.tenant_id == tenant_id,
                AgentExecution.status == "running"
            ).all()

            cancelled_count = 0
            for episode in running_episodes:
                episode.status = "cancelled"
                cancelled_count += 1

            self.db.flush()

            logger.info(
                f"[BudgetEnforcementService] Cancelled {cancelled_count} active episodes "
                f"for tenant {tenant_id}"
            )

            return cancelled_count

        except Exception as e:
            logger.error(f"[BudgetEnforcementService] Error cancelling episodes: {str(e)}")
            self.db.rollback()
            return 0

    async def _send_enforcement_notification(
        self,
        tenant_id: str,
        mode: str,
        current_spend: float,
        budget_limit: float,
        utilization_percent: float,
        details: str
    ) -> bool:
        """
        Send enforcement notification to admin users.
        """
        try:
            from core.models import User, Permission, CustomRole
            from core.models import Workspace

            # Get admin users
            admin_users = self.db.query(User).join(
                User.custom_role
            ).join(
                CustomRole.permissions
            ).filter(
                Permission.scope == 'billing',
                Permission.action == 'manage',
                User.tenant_id == tenant_id
            ).all()

            if not admin_users:
                # Fallback to tenant owner
                admin_users = self.db.query(User).filter(
                    User.tenant_id == tenant_id
                ).limit(1).all()

            if not admin_users:
                logger.warning(f"[BudgetEnforcementService] No admin users for tenant {tenant_id}")
                return False

            # Get workspace
            workspace = self.db.query(Workspace).filter(
                Workspace.tenant_id == tenant_id
            ).first()

            if not workspace:
                logger.warning(f"[BudgetEnforcementService] No workspace for tenant {tenant_id}")
                return False

            # Build notification
            mode_labels = {
                BudgetEnforcementMode.ALERT_ONLY: "Alert Only",
                BudgetEnforcementMode.SOFT_STOP: "Soft Stop",
                BudgetEnforcementMode.HARD_STOP: "Hard Stop",
                BudgetEnforcementMode.APPROVAL: "Approval Required"
            }

            title = f"Budget Enforcement: {mode_labels.get(mode, mode)} Active"
            message = f"""Budget limit exceeded.

Current Spend: ${current_spend:.2f}
Budget Limit: ${budget_limit:.2f}
Utilization: {utilization_percent:.1f}%

Enforcement Mode: {mode_labels.get(mode, mode)}
{details}
"""

            # Send to all admin users
            for user in admin_users:
                await self.notification_service.send_notification(
                    user_id=str(user.id),
                    workspace_id=str(workspace.id),
                    title=title,
                    message=message,
                    notification_type='error',
                    channels=['email', 'in_app'],
                    metadata={
                        'enforcement_mode': mode,
                        'current_spend': current_spend,
                        'budget_limit': budget_limit,
                        'utilization_percent': utilization_percent,
                        'alert_type': 'budget_enforcement'
                    }
                )

            logger.info(
                f"[BudgetEnforcementService] Enforcement notification sent to {len(admin_users)} "
                f"admin users for tenant {tenant_id}"
            )

            return True

        except Exception as e:
            logger.error(f"[BudgetEnforcementService] Error sending notification: {str(e)}")
            return False

    def clear_enforcement_state(self, tenant_id: str) -> None:
        """
        Clear override on billing cycle reset.
        Called by SpendAggregationService when new billing cycle starts.
        """
        try:
            existing_setting = self.db.query(TenantSetting).filter(
                TenantSetting.tenant_id == tenant_id,
                TenantSetting.setting_key == 'billing'
            ).first()

            if not existing_setting or not existing_setting.setting_value:
                return

            settings_dict = json.loads(existing_setting.setting_value)

            # Clear override
            if 'enforcement' in settings_dict and 'override' in settings_dict['enforcement']:
                del settings_dict['enforcement']['override']

                existing_setting.setting_value = json.dumps(settings_dict)
                self.db.flush()

                logger.info(
                    f"[BudgetEnforcementService] Cleared enforcement override for tenant {tenant_id} "
                    f"(billing cycle reset)"
                )

        except Exception as e:
            logger.error(f"[BudgetEnforcementService] Error clearing enforcement state: {str(e)}")
            self.db.rollback()

    def __del__(self):
        """Cleanup database session."""
        if hasattr(self, 'db'):
            self.db.close()

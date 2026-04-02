"""
Fleet Overage Service

Tracks temporary fleet size expansions beyond plan limits.
Implements SCALE-08: Overage handling with explicit user approval
and time-limited auto-contraction.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from core.models import FleetOverage, DelegationChain, Tenant
from core.notification_service import NotificationService

logger = logging.getLogger(__name__)

class OverageService:
    """
    Service for managing temporary fleet size overages.

    Handles:
    - Approving temporary expansions beyond plan limits
    - Tracking expiry timestamps for auto-contraction
    - Getting effective limits (base or overage)
    - Checking and expiring overages
    """

    # Maximum overage duration by plan (hours)
    MAX_OVERAGE_DURATION = {
        "free": 24,      # 1 day
        "solo": 48,      # 2 days
        "basic": 48,
        "team": 72,      # 3 days
        "premium": 72,
        "enterprise": 168  # 7 days
    }

    # Maximum overage multiplier by plan
    MAX_OVERAGE_MULTIPLIER = {
        "free": 1.5,     # Can go to 3 (2 * 1.5)
        "solo": 1.5,     # Can go to 7.5 (5 * 1.5)
        "basic": 1.5,
        "team": 1.5,     # Can go to 15 (10 * 1.5)
        "premium": 1.5,
        "enterprise": 2.0  # Can go to 50 (25 * 2)
    }

    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db_session=db)

    async def approve_overage(
        self,
        chain_id: str,
        
        proposed_size: int,
        user_id: str,
        duration_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Approve temporary fleet expansion beyond plan limits.

        Args:
            chain_id: Delegation chain to expand
            tenant_id: Any UUID
            proposed_size: Requested fleet size
            user_id: User approving the overage
            duration_hours: Duration (defaults by plan, max enforced)

        Returns:
            Dict with approval result and expiry timestamp

        Raises:
            ValueError: If proposed_size exceeds maximum allowed overage
        """
        # Get base limit
        base_limit = int(os.getenv("MAX_FLEET_SIZE", "100"))

        # Validate proposed size
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        plan_type = "enterprise" if tenant else 'free'

        max_multiplier = self.MAX_OVERAGE_MULTIPLIER.get(plan_type, 1.5)
        max_allowed = int(base_limit * max_multiplier)

        if proposed_size > max_allowed:
            raise ValueError(
                f"Proposed fleet size {proposed_size} exceeds maximum allowed overage "
                f"({max_allowed}, which is {base_limit} * {max_multiplier}). "
                f"Please upgrade your plan for higher limits."
            )

        # Determine duration (cap at plan maximum)
        max_duration = self.MAX_OVERAGE_DURATION.get(plan_type, 48)
        if duration_hours is None:
            duration_hours = max_duration // 2  # Default to half of max
        duration_hours = min(duration_hours, max_duration)

        expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

        # Cancel any existing active overages for this chain
        self.db.query(FleetOverage).filter(
            FleetOverage.chain_id == chain_id,
            FleetOverage.status == "active"
        ).update({"status": "cancelled"})

        # Create new overage record
        overage = FleetOverage(
            id=str(uuid.uuid4()),
            chain_id=chain_id,
                        approved_size=proposed_size,
            base_limit=base_limit,
            expires_at=expires_at,
            approved_by=user_id,
            status="active"
        )
        self.db.add(overage)
        self.db.flush()

        # Send notification
        await self._send_overage_notification(
            tenant_id, user_id, chain_id, base_limit, proposed_size, expires_at
        )

        logger.info(
            f"Fleet overage approved for chain {chain_id}: "
            f"{base_limit} -> {proposed_size} (expires {expires_at})"
        )

        return {
            "success": True,
            "overage_id": overage.id,
            "approved_size": proposed_size,
            "base_limit": base_limit,
            "expires_at": expires_at.isoformat(),
            "duration_hours": duration_hours
        }

    def get_effective_limit(self, chain_id: str) -> int:
        """
        Get current fleet size limit considering active overages.

        Args:
            chain_id: Delegation chain ID

        Returns:
            Effective limit (base plan limit or approved overage limit)

        This is the PRIMARY method to call when checking fleet size limits.
        It automatically checks for active overages before falling back to base limit.
        """
        # Check for active overage first
        active_overage = self.db.query(FleetOverage).filter(
            FleetOverage.chain_id == chain_id,
            FleetOverage.status == "active",
            FleetOverage.expires_at > datetime.now(timezone.utc)
        ).first()

        if active_overage:
            logger.info(
                f"Active overage for chain {chain_id}: "
                f"{active_overage.base_limit} -> {active_overage.approved_size} "
                f"until {active_overage.expires_at}"
            )
            return active_overage.approved_size

        # No active overage - return base plan limit
        chain = self.db.query(DelegationChain).filter(
            DelegationChain.id == chain_id
        ).first()

        if not chain:
            logger.warning(f"Chain {chain_id} not found, returning default limit 2")
            return 2

        base_limit = int(os.getenv("MAX_FLEET_SIZE", "100"))
        logger.info(f"Base plan limit for chain {chain_id}: {base_limit}")
        return base_limit

    def get_active_overage(self, chain_id: str) -> Optional[FleetOverage]:
        """Get active overage for chain, if any."""
        return self.db.query(FleetOverage).filter(
            FleetOverage.chain_id == chain_id,
            FleetOverage.status == "active",
            FleetOverage.expires_at > datetime.now(timezone.utc)
        ).first()

    async def check_overage_expiry(self, chain_id: str) -> bool:
        """
        Check if overage has expired and update status.

        Called by FleetScalerService monitoring loop (Phase 242-05).

        Args:
            chain_id: Delegation chain ID

        Returns:
            True if overage was expired (fleet should contract), False otherwise
        """
        now = datetime.now(timezone.utc)

        # Find expired active overages
        expired_overages = self.db.query(FleetOverage).filter(
            FleetOverage.chain_id == chain_id,
            FleetOverage.status == "active",
            FleetOverage.expires_at <= now
        ).all()

        if not expired_overages:
            return False

        # Mark as expired
        for overage in expired_overages:
            overage.status = "expired"
            logger.info(
                f"Fleet overage {overage.id} expired for chain {chain_id}. "
                f"Limit returns to {overage.base_limit} from {overage.approved_size}"
            )

        self.db.flush()

        # Send expiry notification
        if expired_overages:
            await self._send_expiry_notification(
                expired_overages[0].tenant_id,
                chain_id,
                expired_overages[0].base_limit,
                expired_overages[0].approved_size
            )

        return True

    def get_expiring_overages(self, hours_threshold: int = 2) -> List[FleetOverage]:
        """
        Get overages expiring soon (for warning notifications).

        Args:
            hours_threshold: How many hours until expiry is "soon"

        Returns:
            List of overages expiring within threshold
        """
        threshold_time = datetime.now(timezone.utc) + timedelta(hours=hours_threshold)

        return self.db.query(FleetOverage).filter(
            FleetOverage.status == "active",
            FleetOverage.expires_at <= threshold_time,
            FleetOverage.expires_at > datetime.now(timezone.utc)
        ).all()

    async def _send_overage_notification(
        self,
        
        user_id: str,
        chain_id: str,
        base_limit: int,
        approved_size: int,
        expires_at: datetime
    ) -> None:
        """Send notification when overage is approved."""
        try:
            await self.notification_service.send_notification(
                user_id=user_id,
                workspace_id=tenant_id,
                title="Fleet Expansion Approved",
                message=f"""Your fleet has been temporarily expanded.

Base limit: {base_limit} agents
Approved size: {approved_size} agents
Expires: {expires_at.strftime('%Y-%m-%d %H:%M')} UTC

Your fleet will automatically contract to {base_limit} agents when the overage expires.
To extend, please submit a new scaling proposal before expiration.""",
                notification_type="success",
                channels=["in_app", "email"]
            )
        except Exception as e:
            logger.error(f"Failed to send overage notification: {e}")

    async def _send_expiry_notification(
        self,
        
        chain_id: str,
        base_limit: int,
        previous_size: int
    ) -> None:
        """Send notification when overage expires."""
        try:
            # Get tenant owner for notification
            from core.models import User
            owner = self.db.query(User).filter(
                User.                User.role == "admin"
            ).first()

            if owner:
                await self.notification_service.send_notification(
                    user_id=owner.id,
                    workspace_id=tenant_id,
                    title="Fleet Expansion Expired",
                    message=f"""Your temporary fleet expansion has expired.

Your fleet size has returned to the base plan limit of {base_limit} agents
(from the temporary expansion of {previous_size} agents).

To expand again, please submit a new scaling proposal.""",
                    notification_type="warning",
                    channels=["in_app", "email"]
                )
        except Exception as e:
            logger.error(f"Failed to send expiry notification: {e}")

# Convenience function for DI
def get_overage_service(db: Session) -> OverageService:
    """Get OverageService instance."""
    return OverageService(db)

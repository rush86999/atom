"""
Scaling Proposal Service for adaptive fleet scaling.

This service analyzes performance metrics and generates expansion/contraction proposals
with cost estimates and hysteresis to prevent rapid proposal oscillation.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from enum import Enum

from pydantic import BaseModel, Field
import redis.asyncio as redis

from sqlalchemy.orm import Session

from core.fleet_orchestration.performance_metrics_service import PerformanceMetricsService
from core.fleet_orchestration.overage_service import OverageService
from core.models import ScalingProposal as ScalingProposalRecord
from sqlalchemy import func

logger = logging.getLogger(__name__)

# ============================================================================
# Enums
# ============================================================================

class ScalingProposalType(str, Enum):
    """Type of scaling proposal."""
    EXPANSION = "expansion"
    CONTRACTION = "contraction"

class ScalingProposalStatus(str, Enum):
    """Status of a scaling proposal."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"

# ============================================================================
# Pydantic Models
# ============================================================================

class ScalingProposal(BaseModel):
    """
    Scaling proposal for fleet size adjustment.

    Attributes:
        id: Unique proposal identifier
        chain_id: ID of the delegation chain (fleet)
        tenant_id: Any UUID
        proposal_type: Expansion or contraction
        current_fleet_size: Current number of agents in fleet
        proposed_fleet_size: Proposed number of agents
        reason: Why this proposal was created
        metrics: Current performance metrics that triggered proposal
        cost_estimate: Estimated additional cost (USD)
        duration_hours: Estimated duration of scaling
        status: Proposal status
        expires_at: When proposal expires
        created_at: When proposal was created
        metadata: Additional metadata
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str
    proposal_type: ScalingProposalType
    current_fleet_size: int = Field(ge=1)
    proposed_fleet_size: int = Field(ge=1)
    reason: str
    metrics: Dict[str, float] = Field(default_factory=dict)
    cost_estimate: float = Field(ge=0.0)
    duration_hours: float = Field(ge=0.0)
    status: ScalingProposalStatus = ScalingProposalStatus.PENDING
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True

# ============================================================================
# Service
# ============================================================================

class ScalingProposalService:
    """
    Service for creating and managing scaling proposals.

    Analyzes performance metrics to detect scaling needs and creates
    proposals with cost estimates and hysteresis to prevent flapping.
    """

    # Default thresholds for scaling triggers
    DEFAULT_THRESHOLDS = {
        "expansion": {
            "success_rate_critical": 70.0,  # Below = immediate expansion
            "success_rate_warning": 85.0,   # Below = consider expansion
            "latency_critical_ms": 45000,   # Above = immediate expansion
            "latency_warning_ms": 20000,    # Above = consider expansion
        },
        "contraction": {
            "utilization_low": 30.0,        # Below = consider contraction
            "success_rate_excellent": 95.0, # Above + low utilization = contraction
        }
    }

    # Hysteresis configuration
    HYSTERESIS_CONFIG = {
        "min_time_between_proposals_hours": 1,
        "rejection_suppression_hours": 4,
    }

    def __init__(self, db: Session, redis_url: Optional[str] = None):
        """
        Initialize scaling proposal service.

        Args:
            db: Database session for persistence
            redis_url: Redis connection URL (optional)
        """
        self.db = db
        self.redis_url = redis_url
        self._redis_client: Optional[redis.Redis] = None
        self.metrics_service = PerformanceMetricsService(db, redis_url)
        self.overage_service = OverageService(db)

    async def _get_redis(self) -> Optional[redis.Redis]:
        """Get or create Redis connection."""
        if self._redis_client is None:
            try:
                import os
                url = self.redis_url or os.getenv("DRAGONFLY_URL") or os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
                if url:
                    self._redis_client = redis.from_url(url, decode_responses=True)
                else:
                    logger.warning("No Redis URL configured, hysteresis tracking disabled")
            except Exception as e:
                logger.error(f"Failed to create Redis client: {e}")
                return None
        return self._redis_client

    async def validate_fleet_size_limit(
        self,
        chain_id: str,
        
        proposed_size: int
    ) -> Dict[str, Any]:
        """
        Validate if proposed fleet size is within limits.

        Checks effective limit (base or active overage) and returns
        validation result with warnings if approaching limits.

        Args:
            chain_id: Delegation chain ID
            tenant_id: Any UUID
            proposed_size: Proposed fleet size

        Returns:
            Dict with:
            - allowed (bool): True if within limits
            - reason (str): Block reason if not allowed
            - current_limit (int): Effective limit
            - current_size (int): Current fleet size
            - usage_percent (float): Current usage percentage
            - warnings (List[str]): Warnings if approaching limits
        """
        # Get effective limit (checks active overages)
        effective_limit = self.overage_service.get_effective_limit(chain_id)

        # Get current fleet size
        current_size = await self._get_current_fleet_size(chain_id)

        # Calculate usage percentage
        usage_percent = (current_size / effective_limit * 100) if effective_limit > 0 else 0

        # Check if proposed size exceeds limit
        if proposed_size > effective_limit:
            return {
                "allowed": False,
                "reason": f"Proposed fleet size {proposed_size} exceeds limit {effective_limit}. "
                         f"Request overage approval to expand temporarily.",
                "current_limit": effective_limit,
                "current_size": current_size,
                "usage_percent": usage_percent,
                "warnings": self._get_fleet_size_warnings(current_size, effective_limit)
            }

        # Within limits - check for warnings
        warnings = self._get_fleet_size_warnings(proposed_size, effective_limit)

        return {
            "allowed": True,
            "reason": "Within fleet size limits",
            "current_limit": effective_limit,
            "current_size": current_size,
            "usage_percent": usage_percent,
            "warnings": warnings
        }

    def _get_fleet_size_warnings(self, size: int, limit: int) -> List[Dict[str, str]]:
        """
        Get warnings if fleet is approaching size limit.

        Warning thresholds:
        - 90%: Critical warning
        - 80%: Warning

        Args:
            size: Current or proposed fleet size
            limit: Fleet size limit

        Returns:
            List of warning messages
        """
        warnings = []

        if limit == 0:
            return warnings

        usage_percent = (size / limit) * 100

        if usage_percent >= 90:
            warnings.append({
                "severity": "critical",
                "message": f"Fleet size at {usage_percent:.0f}% of limit ({size}/{limit}). "
                         f"Approaching hard limit - consider overage approval or plan upgrade."
            })
        elif usage_percent >= 80:
            warnings.append({
                "severity": "warning",
                "message": f"Fleet size at {usage_percent:.0f}% of limit ({size}/{limit}). "
                         f"Approaching limit - plan ahead for expansion."
            })

        return warnings

    async def _get_current_fleet_size(self, chain_id: str) -> int:
        """
        Get current fleet size for a delegation chain.

        Args:
            chain_id: Delegation chain ID

        Returns:
            Current number of active/in_progress agents in fleet
        """
        from core.models import ChainLink

        count = self.db.query(func.count(ChainLink.id)).filter(
            ChainLink.chain_id == chain_id,
            ChainLink.status.in_(['active', 'in_progress'])
        ).scalar()

        return count if count else 0

    async def analyze_scaling_need(
        self,
        chain_id: str) -> Optional[ScalingProposal]:
        """
        Analyze performance metrics and create scaling proposal if needed.

        Args:
            chain_id: ID of the delegation chain
            tenant_id: Any UUID

        Returns:
            ScalingProposal if scaling needed, None otherwise
        """
        try:
            # Get current metrics
            metrics = await self.metrics_service.get_metrics(chain_id, window="5m")

            # Check for expansion need
            expansion_proposal = await self._check_expansion_need(
                chain_id, metrics
            )
            if expansion_proposal:
                # Check hysteresis
                if await self._check_hysteresis(chain_id, "expansion"):
                    return expansion_proposal
                else:
                    logger.info(f"Expansion proposal suppressed by hysteresis for chain {chain_id}")
                    return None

            # Check for contraction need
            contraction_proposal = await self._check_contraction_need(
                chain_id, metrics
            )
            if contraction_proposal:
                # Check hysteresis
                if await self._check_hysteresis(chain_id, "contraction"):
                    return contraction_proposal
                else:
                    logger.info(f"Contraction proposal suppressed by hysteresis for chain {chain_id}")
                    return None

            return None

        except Exception as e:
            logger.error(f"Failed to analyze scaling need for chain {chain_id}: {e}")
            return None

    async def _check_expansion_need(
        self,
        chain_id: str,
        
        metrics: Any
    ) -> Optional[ScalingProposal]:
        """Check if expansion is needed based on metrics."""
        thresholds = self.DEFAULT_THRESHOLDS["expansion"]

        # Check success rate
        if metrics.success_rate < thresholds["success_rate_critical"]:
            reason = f"Critical success rate ({metrics.success_rate:.1f}% < {thresholds['success_rate_critical']:.1f}%)"
            return await self._create_expansion_proposal(
                chain_id, metrics, reason
            )
        elif metrics.success_rate < thresholds["success_rate_warning"]:
            reason = f"Low success rate ({metrics.success_rate:.1f}% < {thresholds['success_rate_warning']:.1f}%)"
            return await self._create_expansion_proposal(
                chain_id, metrics, reason, urgency="warning"
            )

        # Check latency
        if metrics.avg_latency_ms > thresholds["latency_critical_ms"]:
            reason = f"Critical latency ({metrics.avg_latency_ms:.0f}ms > {thresholds['latency_critical_ms']:.0f}ms)"
            return await self._create_expansion_proposal(
                chain_id, metrics, reason
            )
        elif metrics.avg_latency_ms > thresholds["latency_warning_ms"]:
            reason = f"High latency ({metrics.avg_latency_ms:.0f}ms > {thresholds['latency_warning_ms']:.0f}ms)"
            return await self._create_expansion_proposal(
                chain_id, metrics, reason, urgency="warning"
            )

        return None

    async def _check_contraction_need(
        self,
        chain_id: str,
        
        metrics: Any
    ) -> Optional[ScalingProposal]:
        """Check if contraction is needed based on metrics."""
        thresholds = self.DEFAULT_THRESHOLDS["contraction"]

        # Check for excellent performance with low utilization
        # (simplified - in production, track utilization separately)
        if metrics.success_rate > thresholds["success_rate_excellent"]:
            # Low throughput might indicate underutilization
            if metrics.throughput_per_minute < 2.0:  # Less than 2 tasks/min
                reason = f"Underutilized fleet (success rate {metrics.success_rate:.1f}%, throughput {metrics.throughput_per_minute:.1f} tasks/min)"
                return await self._create_contraction_proposal(
                    chain_id, metrics, reason
                )

        return None

    async def _create_expansion_proposal(
        self,
        chain_id: str,
        
        metrics: Any,
        reason: str,
        urgency: str = "critical"
    ) -> ScalingProposal:
        """Create an expansion proposal."""
        # Calculate proposed size (increase by 50% or add 5, whichever is smaller)
        current_size = metrics.execution_count or 3  # Default to 3 if no data
        proposed_size = min(int(current_size * 1.5), current_size + 5)
        proposed_size = max(proposed_size, current_size + 1)  # At least +1

        # Estimate cost (simplified - use $0.01 per agent-hour)
        duration_hours = 24.0 if urgency == "critical" else 12.0
        cost_estimate = (proposed_size - current_size) * 0.01 * duration_hours

        # Set expiration (24 hours for expansion)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        return ScalingProposal(
            chain_id=chain_id,
                        proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=current_size,
            proposed_fleet_size=proposed_size,
            reason=reason,
            metrics={
                "success_rate": metrics.success_rate,
                "avg_latency_ms": metrics.avg_latency_ms,
                "throughput_per_minute": metrics.throughput_per_minute,
                "execution_count": metrics.execution_count,
            },
            cost_estimate=cost_estimate,
            duration_hours=duration_hours,
            expires_at=expires_at,
            metadata={"urgency": urgency}
        )

    async def _create_contraction_proposal(
        self,
        chain_id: str,
        
        metrics: Any,
        reason: str
    ) -> ScalingProposal:
        """Create a contraction proposal."""
        # Calculate proposed size (decrease by 30% or remove 3, whichever is larger)
        current_size = metrics.execution_count or 5  # Default to 5 if no data
        proposed_size = max(int(current_size * 0.7), current_size - 3)
        proposed_size = max(proposed_size, 2)  # Minimum 2 agents

        # Estimate savings
        duration_hours = 168.0  # 1 week
        cost_savings = (current_size - proposed_size) * 0.01 * duration_hours

        # Set expiration (7 days for contraction - less urgent)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        return ScalingProposal(
            chain_id=chain_id,
                        proposal_type=ScalingProposalType.CONTRACTION,
            current_fleet_size=current_size,
            proposed_fleet_size=proposed_size,
            reason=reason,
            metrics={
                "success_rate": metrics.success_rate,
                "avg_latency_ms": metrics.avg_latency_ms,
                "throughput_per_minute": metrics.throughput_per_minute,
                "execution_count": metrics.execution_count,
            },
            cost_estimate=-cost_savings,  # Negative = savings
            duration_hours=duration_hours,
            expires_at=expires_at,
            metadata={"savings": cost_savings}
        )

    async def _check_hysteresis(
        self,
        chain_id: str,
        
        proposal_type: str
    ) -> bool:
        """
        Check if hysteresis allows a new proposal.

        Args:
            chain_id: ID of the delegation chain
            tenant_id: Any UUID
            proposal_type: 'expansion' or 'contraction'

        Returns:
            True if proposal is allowed, False if suppressed
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return True  # Allow if Redis unavailable

        try:
            key = f"fleet:{chain_id}:scaling:last_proposal:{proposal_type}"
            last_proposal_time = await redis_client.get(key)

            if last_proposal_time:
                last_time = datetime.fromisoformat(last_proposal_time)
                hours_since = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600

                if hours_since < self.HYSTERESIS_CONFIG["min_time_between_proposals_hours"]:
                    return False

            return True

        except Exception as e:
            logger.error(f"Hysteresis check failed for chain {chain_id}: {e}")
            return True  # Allow on error

    async def _set_hysteresis_timestamp(
        self,
        chain_id: str,
        proposal_type: str
    ) -> None:
        """Set hysteresis timestamp after creating proposal."""
        redis_client = await self._get_redis()
        if not redis_client:
            return

        try:
            key = f"fleet:{chain_id}:scaling:last_proposal:{proposal_type}"
            await redis_client.set(key, datetime.now(timezone.utc).isoformat())
            # Expire after suppression period
            await redis_client.expire(
                key,
                int(self.HYSTERESIS_CONFIG["rejection_suppression_hours"] * 3600)
            )
        except Exception as e:
            logger.error(f"Failed to set hysteresis timestamp: {e}")

    async def _set_rejection_suppression(
        self,
        chain_id: str,
        proposal_type: str,
        duration_hours: int = 4
    ) -> None:
        """Set rejection suppression after rejecting proposal."""
        redis_client = await self._get_redis()
        if not redis_client:
            return

        try:
            key = f"fleet:{chain_id}:scaling:rejection_suppression:{proposal_type}"
            await redis_client.set(key, datetime.now(timezone.utc).isoformat())
            await redis_client.expire(key, int(duration_hours * 3600))
        except Exception as e:
            logger.error(f"Failed to set rejection suppression: {e}")

    async def create_expansion_proposal(
        self,
        chain_id: str,
        
        current_size: int,
        proposed_size: int,
        reason: str
    ) -> ScalingProposal:
        """
        Manually create an expansion proposal.

        Args:
            chain_id: ID of the delegation chain
            tenant_id: Any UUID
            current_size: Current fleet size
            proposed_size: Proposed fleet size
            reason: Reason for expansion

        Returns:
            Created ScalingProposal

        Raises:
            ValueError: If proposed size exceeds limit without overage available
        """
        # Validate fleet size limit first
        validation = await self.validate_fleet_size_limit(
            chain_id, proposed_size
        )

        if not validation["allowed"]:
            # Check if user can request overage
            quota_check = {"allowed": True, "current_limit": int(os.getenv("MAX_FLEET_SIZE", "100")), "overage_available": True}
            if not quota_check.get("overage_available"):
                raise ValueError(
                    f"Cannot create expansion proposal: {validation['reason']}"
                )

        duration_hours = 24.0
        cost_estimate = (proposed_size - current_size) * 0.01 * duration_hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        # Include warnings in proposal metadata
        metadata = {
            "warnings": validation.get("warnings", []),
            "usage_percent": validation.get("usage_percent", 0),
            "current_limit": validation.get("current_limit", 0)
        }

        proposal = ScalingProposal(
            chain_id=chain_id,
                        proposal_type=ScalingProposalType.EXPANSION,
            current_fleet_size=current_size,
            proposed_fleet_size=proposed_size,
            reason=reason,
            cost_estimate=cost_estimate,
            duration_hours=duration_hours,
            expires_at=expires_at,
            metadata=metadata
        )

        # Persist to database
        await self._persist_proposal(proposal)

        # Set hysteresis
        await self._set_hysteresis_timestamp(chain_id, "expansion")

        return proposal

    async def create_contraction_proposal(
        self,
        chain_id: str,
        
        current_size: int,
        proposed_size: int,
        reason: str
    ) -> ScalingProposal:
        """
        Manually create a contraction proposal.

        Args:
            chain_id: ID of the delegation chain
            tenant_id: Any UUID
            current_size: Current fleet size
            proposed_size: Proposed fleet size
            reason: Reason for contraction

        Returns:
            Created ScalingProposal
        """
        duration_hours = 168.0  # 1 week
        cost_savings = (current_size - proposed_size) * 0.01 * duration_hours
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        proposal = ScalingProposal(
            chain_id=chain_id,
                        proposal_type=ScalingProposalType.CONTRACTION,
            current_fleet_size=current_size,
            proposed_fleet_size=proposed_size,
            reason=reason,
            cost_estimate=-cost_savings,  # Negative = savings
            duration_hours=duration_hours,
            expires_at=expires_at,
            metadata={"savings": cost_savings}
        )

        # Persist to database
        await self._persist_proposal(proposal)

        # Set hysteresis
        await self._set_hysteresis_timestamp(chain_id, "contraction")

        return proposal

    async def _persist_proposal(self, proposal: ScalingProposal) -> None:
        """Persist proposal to database."""
        try:
            model = ScalingProposalRecord(
                id=proposal.id,
                chain_id=proposal.chain_id,
                                proposal_type=proposal.proposal_type.value if hasattr(proposal.proposal_type, 'value') else proposal.proposal_type,
                current_fleet_size=proposal.current_fleet_size,
                proposed_fleet_size=proposal.proposed_fleet_size,
                reason=proposal.reason,
                metrics_json=proposal.metrics,
                cost_estimate=proposal.cost_estimate,
                duration_hours=proposal.duration_hours,
                status=proposal.status.value if hasattr(proposal.status, 'value') else proposal.status,
                expires_at=proposal.expires_at)

            self.db.add(model)
            self.db.commit()
            logger.info(f"Persisted scaling proposal {proposal.id} to database")

        except Exception as e:
            logger.error(f"Failed to persist scaling proposal: {e}")
            self.db.rollback()

    async def get_proposal(self, proposal_id: str) -> Optional[ScalingProposal]:
        """
        Get proposal by ID.

        Args:
            proposal_id: Proposal ID
            tenant_id: Any UUID for authorization

        Returns:
            ScalingProposal or None
        """
        model = self.db.query(ScalingProposalRecord).filter(
            ScalingProposalRecord.id == proposal_id
        ).first()

        if not model:
            return None

        return self._model_to_proposal(model)

    async def get_pending_proposals(self) -> List[ScalingProposal]:
        """
        Get all pending proposals for tenant.

        Args:
            tenant_id: Any UUID

        Returns:
            List of pending ScalingProposal objects
        """
        models = self.db.query(ScalingProposalRecord).filter(
            ScalingProposalRecord.            ScalingProposalRecord.status == 'pending'
        ).all()

        return [self._model_to_proposal(m) for m in models]

    def _model_to_proposal(self, model: ScalingProposalRecord) -> ScalingProposal:
        """Convert database model to Pydantic model."""
        return ScalingProposal(
            id=model.id,
            chain_id=model.chain_id,
                        proposal_type=model.proposal_type,
            current_fleet_size=model.current_fleet_size,
            proposed_fleet_size=model.proposed_fleet_size,
            reason=model.reason,
            metrics=model.metrics_json or {},
            cost_estimate=float(model.cost_estimate),
            duration_hours=float(model.duration_hours),
            status=model.status,
            expires_at=model.expires_at,
            created_at=model.created_at,
            metadata={}
        )

    async def approve_proposal(
        self,
        proposal_id: str,
        
        approved_by: str,
        note: Optional[str] = None
    ) -> ScalingProposal:
        """
        Approve a scaling proposal.

        Args:
            proposal_id: Proposal ID
            tenant_id: Any UUID
            approved_by: User ID who approved
            note: Optional approval note

        Returns:
            Updated ScalingProposal
        """
        model = self.db.query(ScalingProposalRecord).filter(
            ScalingProposalRecord.id == proposal_id
        ).first()

        if not model:
            raise ValueError(f"Proposal {proposal_id} not found")

        if model.status != 'pending':
            raise ValueError(f"Proposal {proposal_id} is not pending (status: {model.status})")

        if datetime.now(timezone.utc) > model.expires_at:
            model.status = 'expired'
            self.db.commit()
            raise ValueError(f"Proposal {proposal_id} has expired")

        # Update to approved
        model.status = 'approved'
        model.approved_by = approved_by
        model.approved_at = datetime.now(timezone.utc)

        self.db.commit()

        logger.info(f"Scaling proposal {proposal_id} approved by {approved_by}")

        return await self.get_proposal(proposal_id)

    async def reject_proposal(
        self,
        proposal_id: str,
        
        rejected_by: str,
        reason: str
    ) -> ScalingProposal:
        """
        Reject a scaling proposal.

        Args:
            proposal_id: Proposal ID
            tenant_id: Any UUID
            rejected_by: User ID who rejected
            reason: Rejection reason

        Returns:
            Updated ScalingProposal
        """
        model = self.db.query(ScalingProposalRecord).filter(
            ScalingProposalRecord.id == proposal_id
        ).first()

        if not model:
            raise ValueError(f"Proposal {proposal_id} not found")

        if model.status != 'pending':
            raise ValueError(f"Proposal {proposal_id} is not pending")

        # Update to rejected
        model.status = 'rejected'
        model.rejection_reason = reason

        self.db.commit()

        # Set hysteresis suppression (4 hours)
        await self._set_rejection_suppression(
            model.chain_id,
            model.proposal_type,
            duration_hours=4
        )

        logger.info(f"Scaling proposal {proposal_id} rejected by {rejected_by}: {reason}")

        return await self.get_proposal(proposal_id)

    async def estimate_scaling_cost(
        self,
        current_size: int,
        proposed_size: int,
        duration_hours: float) -> float:
        """
        Estimate cost of scaling.

        Args:
            current_size: Current fleet size
            proposed_size: Proposed fleet size
            duration_hours: Estimated duration
            tenant_id: Any UUID for historical data

        Returns:
            Estimated cost in USD
        """
        delta = abs(proposed_size - current_size)
        agent_hour_cost = 0.01  # $0.01 per agent-hour (simplified)

        return delta * agent_hour_cost * duration_hours

    async def validate_budget_for_proposal(
        self,
        chain_id: str,
        proposed_size: int,
        duration_hours: float
    ) -> Dict[str, Any]:
        """
        Validate that scaling proposal is within budget constraints.

        Note: In upstream, all proposals are allowed (no budget tracking).

        Args:
            chain_id: Delegation chain ID
            proposed_size: Proposed fleet size
            duration_hours: Estimated duration

        Returns:
            Dict with:
            - allowed (bool): Always True in upstream
            - reason (str): Always allowed
            - current_limit (int): MAX_FLEET_SIZE env var
            - budget_remaining (float): Infinite in upstream
            - estimated_cost (float): 0.0 in upstream
            - budget_exceeded (bool): Always False in upstream
        """
        current_size = await self._get_current_fleet_size(chain_id)

        return {
            "allowed": True,
            "reason": "Budget checks disabled in upstream",
            "current_limit": int(os.getenv("MAX_FLEET_SIZE", "100")),
            "budget_remaining": float("inf"),
            "estimated_cost": 0.0,
            "budget_exceeded": False
        }

    async def predict_scaling_cost(
        self,
        
        current_size: int,
        proposed_size: int,
        duration_hours: float = 24.0
    ) -> Dict[str, float]:
        """
        Predict cost of scaling with breakdown.

        Args:
            tenant_id: Any UUID
            current_size: Current fleet size
            proposed_size: Proposed fleet size
            duration_hours: Duration for cost calculation

        Returns:
            Dict with:
            - hourly_cost: Cost per hour
            - daily_cost: Cost per day (24h)
            - weekly_cost: Cost per week (7 days)
            - monthly_cost: Cost per month (30 days)
            - total: Total cost for specified duration
            - breakdown: {agent_cost, token_cost, total}
        """
        # Calculate base cost for the specified duration
        base_cost = await self.estimate_scaling_cost(
            current_size, proposed_size, duration_hours)

        # Extrapolate to different time horizons
        hourly_cost = base_cost / duration_hours if duration_hours > 0 else 0
        daily_cost = hourly_cost * 24
        weekly_cost = daily_cost * 7
        monthly_cost = daily_cost * 30

        # Simplified breakdown (80% agent cost, 20% token cost)
        agent_cost = base_cost * 0.8
        token_cost = base_cost * 0.2

        return {
            "hourly_cost": round(hourly_cost, 4),
            "daily_cost": round(daily_cost, 2),
            "weekly_cost": round(weekly_cost, 2),
            "monthly_cost": round(monthly_cost, 2),
            "total": round(base_cost, 2),
            "breakdown": {
                "agent_cost": round(agent_cost, 2),
                "token_cost": round(token_cost, 2),
                "total": round(base_cost, 2)
            }
        }

# ============================================================================
# Singleton Pattern
# ============================================================================

_service_instance: Optional[ScalingProposalService] = None

def get_scaling_proposal_service(db: Session) -> ScalingProposalService:
    """
    Get singleton ScalingProposalService instance.

    Args:
        db: Database session

    Returns:
        ScalingProposalService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = ScalingProposalService(db)
    return _service_instance

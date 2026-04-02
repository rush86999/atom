"""
Fleet Scaler Service

Orchestrates fleet scaling operations with overage integration.
Monitors delegation chains and executes scaling proposals with budget validation.
"""

import logging
import asyncio
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from enum import Enum

from core.fleet_orchestration.overage_service import OverageService
from core.fleet_orchestration.scaling_proposal_service import (
    ScalingProposalService,
    ScalingProposal,
    ScalingProposalType,
    ScalingProposalStatus
)
from core.fleet_orchestration.performance_metrics_service import PerformanceMetricsService
from core.models import DelegationChain, ChainLink, FleetOverage
from sqlalchemy import func

logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Models
# ============================================================================

class ScalingOperationStatus(str, Enum):
    """Status of scaling operation execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

class ScalingOperation(BaseModel):
    """Scaling operation execution tracking."""
    id: str = Field(..., description="Operation ID")
    chain_id: str = Field(..., description="Delegation chain ID")
    = Field(..., description="Tenant UUID")
    proposal_id: str = Field(..., description="Associated proposal ID")
    operation_type: str = Field(..., description="Operation type (expand/contract)")
    from_size: int = Field(..., ge=0, description="Starting fleet size")
    to_size: int = Field(..., ge=0, description="Target fleet size")
    agents_added: List[str] = Field(default_factory=list, description="Recruited agent IDs")
    agents_removed: List[str] = Field(default_factory=list, description="Removed agent IDs")
    status: ScalingOperationStatus = Field(..., description="Operation status")
    started_at: datetime = Field(..., description="Operation start time")
    completed_at: Optional[datetime] = Field(None, description="Operation completion time")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        from_attributes = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "chain_id": self.chain_id,
            "tenant_id": self.tenant_id,
            "proposal_id": self.proposal_id,
            "operation_type": self.operation_type,
            "from_size": self.from_size,
            "to_size": self.to_size,
            "agents_added": self.agents_added,
            "agents_removed": self.agents_removed,
            "status": self.status.value if hasattr(self.status, 'value') else self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata
        }

class FleetScalerService:
    """
    Main orchestration service for adaptive fleet scaling.

    Monitors fleet performance, creates scaling proposals,
    and executes approved scaling operations.

    Integrates with:
    - PerformanceMetricsService for real-time monitoring
    - ScalingProposalService for proposal management
    - OverageService for fleet size limit enforcement
    - FleetCoordinatorService for agent recruitment
    """

    def __init__(self, db: Session, redis_url: Optional[str] = None):
        """
        Initialize fleet scaler service.

        Args:
            db: Database session
            redis_url: Optional Redis URL for metrics service
        """
        self.db = db
        self.overage_service = OverageService(db)
        self.proposal_service = ScalingProposalService(db)
        self.metrics_service = PerformanceMetricsService(db, redis_url)
        self.running = False
        self._monitor_task: Optional[asyncio.Task] = None

    # ========================================================================
    # Main Monitoring and Execution Methods
    # ========================================================================

    async def monitor_and_scale(
        self,
        chain_id: str) -> Optional[ScalingProposal]:
        """
        Monitor fleet performance and create scaling proposal if needed.

        This is the main entry point for automatic scaling detection.
        Called by background worker or after fleet execution.

        Args:
            chain_id: Delegation chain ID
            tenant_id: Any UUID

        Returns:
            ScalingProposal if created, None if no scaling needed
        """
        # 1. Get current metrics
        metrics = await self.metrics_service.get_metrics(chain_id, window="5m")

        logger.debug(
            f"Monitoring chain {chain_id}: "
            f"success_rate={metrics.success_rate:.1f}%, "
            f"latency={metrics.avg_latency_ms:.0f}ms, "
            f"throughput={metrics.throughput_per_minute:.1f}/min"
        )

        # 2. Check for scaling need
        proposal = await self.proposal_service.analyze_scaling_need(
            chain_id, tenant_id
        )

        if proposal:
            # 3. Validate budget before creating
            budget_check = await self.proposal_service.validate_budget_for_proposal(
                chain_id, tenant_id,
                proposal.proposed_fleet_size,
                proposal.duration_hours
            )

            if not budget_check["allowed"]:
                logger.warning(
                    f"Scaling proposal blocked by budget check: {budget_check['reason']}"
                )
                return None

            # 4. Persist proposal
            await self.proposal_service._persist_proposal(proposal)

            logger.info(
                f"Scaling proposal {proposal.id} created for chain {chain_id}: "
                f"{proposal.current_fleet_size} -> {proposal.proposed_fleet_size}"
            )

        return proposal

    async def execute_scaling(
        self,
        proposal_id: str) -> ScalingOperation:
        """
        Execute an approved scaling proposal.

        Args:
            proposal_id: Approved proposal ID
            tenant_id: Any UUID

        Returns:
            ScalingOperation with execution results

        Raises:
            ValueError: If proposal not found, not approved, or expired
        """
        # 1. Get and validate proposal
        proposal = await self.proposal_service.get_proposal(proposal_id, tenant_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ScalingProposalStatus.APPROVED:
            raise ValueError(f"Proposal {proposal_id} is not approved (status: {proposal.status})")

        if datetime.now(timezone.utc) > proposal.expires_at:
            raise ValueError(f"Proposal {proposal_id} has expired")

        # 2. Create scaling operation
        operation = ScalingOperation(
            id=str(uuid.uuid4()),
            chain_id=proposal.chain_id,
            tenant_id=tenant_id,
            proposal_id=proposal_id,
            operation_type="expand" if proposal.proposal_type == ScalingProposalType.EXPANSION else "contract",
            from_size=proposal.current_fleet_size,
            to_size=proposal.proposed_fleet_size,
            status=ScalingOperationStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc)
        )

        # 3. Execute scaling
        try:
            if proposal.proposal_type == ScalingProposalType.EXPANSION:
                result = await self._execute_expansion(proposal, operation)
            else:
                result = await self._execute_contraction(proposal, operation)

            operation.status = ScalingOperationStatus.COMPLETED
            operation.completed_at = datetime.now(timezone.utc)

            # Update proposal status
            await self.proposal_service._update_proposal_status(
                proposal_id, ScalingProposalStatus.EXECUTED
            )

            logger.info(
                f"Scaling operation {operation.id} completed: "
                f"{operation.from_size} -> {operation.to_size}"
            )

        except Exception as e:
            operation.status = ScalingOperationStatus.FAILED
            operation.error_message = str(e)
            operation.completed_at = datetime.now(timezone.utc)

            logger.error(f"Scaling operation {operation.id} failed: {e}")

        # 4. Persist operation
        await self._persist_operation(operation)

        return operation

    async def _execute_expansion(
        self,
        proposal: ScalingProposal,
        operation: ScalingOperation
    ) -> Dict[str, Any]:
        """
        Execute fleet expansion by recruiting additional agents.

        Args:
            proposal: Approved expansion proposal
            operation: Scaling operation tracking

        Returns:
            Execution result with recruited agent IDs
        """
        # Calculate agents to recruit
        agents_needed = proposal.proposed_fleet_size - proposal.current_fleet_size

        # Get existing fleet to determine domains
        existing_agents = self.db.query(ChainLink.child_agent_id).filter(
            ChainLink.chain_id == proposal.chain_id,
            ChainLink.status.in_(['active', 'in_progress'])
        ).all()

        logger.info(f"Expanding fleet by {agents_needed} agents")

        # Recruit through coordinator (simplified - actual implementation
        # would use agent registry and domain matching)
        recruited_agents = []
        for i in range(agents_needed):
            # In production, use AgentRegistry to find available agents
            # by domain matching existing fleet composition
            agent_id = f"recruited-agent-{uuid.uuid4().hex[:8]}"
            recruited_agents.append(agent_id)
            operation.agents_added.append(agent_id)

            # Create chain link for new agent
            link = ChainLink(
                chain_id=proposal.chain_id,
                parent_agent_id=existing_agents[0][0] if existing_agents else "system",
                child_agent_id=agent_id,
                task_description="Fleet expansion recruitment",
                status='active',
                link_order=0
            )
            self.db.add(link)

        self.db.commit()

        # Update blackboard with new agents
        from core.fleet_orchestration import get_distributed_blackboard
        blackboard = get_distributed_blackboard(self.db)
        await blackboard.notify_state_update(
            chain_id=proposal.chain_id,
            update_type="agents_added",
            data={"agent_ids": recruited_agents}
        )

        logger.info(
            f"Expanded fleet {proposal.chain_id}: "
            f"{proposal.current_fleet_size} -> {proposal.proposed_fleet_size} "
            f"({len(recruited_agents)} agents recruited)"
        )

        return {"recruited_agents": recruited_agents}

    async def _execute_contraction(
        self,
        proposal: ScalingProposal,
        operation: ScalingOperation
    ) -> Dict[str, Any]:
        """
        Execute fleet contraction by removing idle agents.

        Args:
            proposal: Approved contraction proposal
            operation: Scaling operation tracking

        Returns:
            Execution result with removed agent IDs
        """
        # Calculate agents to remove
        agents_to_remove = proposal.current_fleet_size - proposal.proposed_fleet_size

        # Get fleet members to identify idle/low-utility agents
        fleet_members = self.db.query(ChainLink).filter(
            ChainLink.chain_id == proposal.chain_id,
            ChainLink.status.in_(['active', 'in_progress'])
        ).order_by(ChainLink.created_at.asc()).limit(agents_to_remove).all()

        removed_agents = []
        for link in fleet_members:
            # Mark as completed/removed
            link.status = 'completed'
            removed_agents.append(link.child_agent_id)
            operation.agents_removed.append(link.child_agent_id)

        self.db.commit()

        # Update blackboard with removed agents
        from core.fleet_orchestration import get_distributed_blackboard
        blackboard = get_distributed_blackboard(self.db)
        await blackboard.notify_state_update(
            chain_id=proposal.chain_id,
            update_type="agents_removed",
            data={"agent_ids": removed_agents}
        )

        logger.info(
            f"Contracted fleet {proposal.chain_id}: "
            f"{proposal.current_fleet_size} -> {proposal.proposed_fleet_size} "
            f"({len(removed_agents)} agents removed)"
        )

        return {"removed_agents": removed_agents}

    async def check_scaling_constraints(
        self,
        chain_id: str,
        
        proposed_size: int
    ) -> Dict[str, Any]:
        """
        Check all scaling constraints before execution.

        Combines:
        - Effective fleet size limit (base or overage)
        - Budget validation
        - Overage expiry check

        Args:
            chain_id: Delegation chain ID
            tenant_id: Any UUID
            proposed_size: Proposed fleet size

        Returns:
            Dict with constraint check results
        """
        from core.quota_manager import QuotaManager

        results = {
            "allowed": True,
            "constraints": {}
        }

        # 1. Check effective fleet size limit
        effective_limit = self.overage_service.get_effective_limit(chain_id)
        results["constraints"]["fleet_size_limit"] = {
            "current_limit": effective_limit,
            "proposed_size": proposed_size,
            "within_limit": proposed_size <= effective_limit
        }

        if proposed_size > effective_limit:
            results["allowed"] = False
            results["constraints"]["fleet_size_limit"]["reason"] = \
                f"Proposed size {proposed_size} exceeds effective limit {effective_limit}"

        # 2. Check plan-based quota (for new proposals without overage)
        current_size = await self._get_current_fleet_size(chain_id)
        quota_check = await QuotaManager.check_fleet_scaling_quota(
            tenant_id, current_size, proposed_size, self.db
        )
        results["constraints"]["plan_quota"] = quota_check

        if not quota_check.get("allowed") and not quota_check.get("overage_available"):
            results["allowed"] = False

        # 3. Check for expiring overages
        if await self.overage_service.check_overage_expiry(chain_id):
            results["constraints"]["overage_expiry"] = {
                "status": "expired",
                "message": "Active overage has expired, fleet should contract"
            }

        return results

    async def get_scaling_status(
        self,
        chain_id: str) -> Dict[str, Any]:
        """
        Get current scaling status for a fleet.

        Args:
            chain_id: Delegation chain ID
            tenant_id: Any UUID

        Returns:
            Dict with current fleet size, pending proposals, recent operations
        """
        # Get current fleet size
        current_size = self.db.query(func.count(ChainLink.id)).filter(
            ChainLink.chain_id == chain_id,
            ChainLink.status.in_(['active', 'in_progress'])
        ).scalar() or 0

        # Get pending proposals
        from core.models import ScalingProposal as ScalingProposalModel
        pending_proposals = self.db.query(ScalingProposalModel).filter(
            ScalingProposalModel.chain_id == chain_id,
            ScalingProposalModel.tenant_id == tenant_id,
            ScalingProposalModel.status == ScalingProposalStatus.PENDING.value
        ).all()

        pending_list = [
            self.proposal_service._model_to_proposal(p)
            for p in pending_proposals
        ]

        # Get recent operations
        recent_ops = await self._get_recent_operations(chain_id, limit=5)

        return {
            "chain_id": chain_id,
            "current_fleet_size": current_size,
            "pending_proposals": [p.to_dict() for p in pending_list],
            "recent_operations": [op.to_dict() for op in recent_ops],
            "last_monitored": datetime.now(timezone.utc).isoformat()
        }

    # ========================================================================
    # Existing Constraint Checking Methods
    # ========================================================================

    async def check_scaling_constraints(
        self,
        chain_id: str,
        
        proposed_size: int
    ) -> Dict[str, Any]:
        """
        Check all scaling constraints before execution.

        Combines:
        - Effective fleet size limit (base or overage)
        - Budget validation
        - Overage expiry check

        Args:
            chain_id: Delegation chain ID
            tenant_id: Any UUID
            proposed_size: Proposed fleet size

        Returns:
            Dict with constraint check results
        """
        from core.quota_manager import QuotaManager

        results = {
            "allowed": True,
            "constraints": {}
        }

        # 1. Check effective fleet size limit
        effective_limit = self.overage_service.get_effective_limit(chain_id)
        results["constraints"]["fleet_size_limit"] = {
            "current_limit": effective_limit,
            "proposed_size": proposed_size,
            "within_limit": proposed_size <= effective_limit
        }

        if proposed_size > effective_limit:
            results["allowed"] = False
            results["constraints"]["fleet_size_limit"]["reason"] = \
                f"Proposed size {proposed_size} exceeds effective limit {effective_limit}"

        # 2. Check plan-based quota (for new proposals without overage)
        current_size = await self._get_current_fleet_size(chain_id)
        quota_check = await QuotaManager.check_fleet_scaling_quota(
            tenant_id, current_size, proposed_size, self.db
        )
        results["constraints"]["plan_quota"] = quota_check

        if not quota_check.get("allowed") and not quota_check.get("overage_available"):
            results["allowed"] = False

        # 3. Check for expiring overages
        if await self.overage_service.check_overage_expiry(chain_id):
            results["constraints"]["overage_expiry"] = {
                "status": "expired",
                "message": "Active overage has expired, fleet should contract"
            }

        return results

    async def _get_current_fleet_size(self, chain_id: str) -> int:
        """
        Get current fleet size for a delegation chain.

        Args:
            chain_id: Delegation chain ID

        Returns:
            Current number of active/in_progress agents in fleet
        """
        count = self.db.query(func.count(ChainLink.id)).filter(
            ChainLink.chain_id == chain_id,
            ChainLink.status.in_(['active', 'in_progress'])
        ).scalar()

        return count if count else 0

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _persist_operation(self, operation: ScalingOperation) -> None:
        """
        Persist scaling operation to database.

        Args:
            operation: ScalingOperation to persist
        """
        try:
            # Try to use ScalingOperation model if it exists
            from core.models import ScalingOperation as ScalingOperationModel

            model = ScalingOperationModel(
                id=operation.id,
                chain_id=operation.chain_id,
                tenant_id=operation.tenant_id,
                proposal_id=operation.proposal_id,
                operation_type=operation.operation_type,
                from_size=operation.from_size,
                to_size=operation.to_size,
                agents_added=operation.agents_added,
                agents_removed=operation.agents_removed,
                status=operation.status.value if hasattr(operation.status, 'value') else operation.status,
                started_at=operation.started_at,
                completed_at=operation.completed_at,
                error_message=operation.error_message,
                metadata_json=operation.metadata
            )

            self.db.add(model)
            self.db.commit()

            logger.debug(f"Persisted scaling operation {operation.id}")

        except Exception as e:
            # Model doesn't exist yet or other error - log and continue
            logger.debug(f"Could not persist operation {operation.id}: {e}")

    async def _get_recent_operations(
        self,
        chain_id: str,
        limit: int = 5
    ) -> List[ScalingOperation]:
        """
        Get recent scaling operations for a chain.

        Args:
            chain_id: Delegation chain ID
            limit: Maximum number of operations to return

        Returns:
            List of recent ScalingOperation objects
        """
        try:
            from core.models import ScalingOperation as ScalingOperationModel

            models = self.db.query(ScalingOperationModel).filter(
                ScalingOperationModel.chain_id == chain_id
            ).order_by(ScalingOperationModel.started_at.desc()).limit(limit).all()

            return [
                ScalingOperation(
                    id=m.id,
                    chain_id=m.chain_id,
                    tenant_id=m.tenant_id,
                    proposal_id=m.proposal_id,
                    operation_type=m.operation_type,
                    from_size=m.from_size,
                    to_size=m.to_size,
                    agents_added=m.agents_added or [],
                    agents_removed=m.agents_removed or [],
                    status=ScalingOperationStatus(m.status),
                    started_at=m.started_at,
                    completed_at=m.completed_at,
                    error_message=m.error_message,
                    metadata=m.metadata_json or {}
                )
                for m in models
            ]

        except (ImportError, AttributeError):
            # Model doesn't exist yet
            return []

    # ========================================================================
    # Background Monitoring
    # ========================================================================

    async def continuous_monitoring_loop(
        self,
        
        interval_seconds: int = 300  # 5 minutes
    ):
        """
        Background loop for continuous fleet monitoring.

        Args:
            tenant_id: Any to monitor
            interval_seconds: Seconds between checks
        """
        while self.running:
            try:
                # Get all active chains for tenant
                active_chains = self.db.query(DelegationChain).filter(
                    DelegationChain.tenant_id == tenant_id,
                    DelegationChain.status == 'active'
                ).all()

                for chain in active_chains:
                    await self.monitor_and_scale(chain.id, tenant_id)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            await asyncio.sleep(interval_seconds)

    async def _get_active_chains(self) -> List[str]:
        """
        Get list of active delegation chains.

        Returns:
            List of chain IDs with active scaling proposals or overages
        """
        # Get chains with active overages
        overage_chains = self.db.query(FleetOverage.chain_id).filter(
            FleetOverage.status == "active",
            FleetOverage.expires_at > datetime.now(timezone.utc)
        ).all()

        chain_ids = [c[0] for c in overage_chains]

        # Get chains with recent scaling activity (last 7 days)
        from core.models import ScalingProposal as ScalingProposalModel
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        proposal_chains = self.db.query(ScalingProposalModel.chain_id).filter(
            ScalingProposalModel.created_at >= recent_cutoff
        ).distinct().all()

        for c in proposal_chains:
            if c[0] not in chain_ids:
                chain_ids.append(c[0])

        return chain_ids

    async def _monitoring_loop(self):
        """Background monitoring loop for scaling checks."""
        while self.running:
            try:
                # Check overage expiry for active chains
                active_chains = await self._get_active_chains()
                logger.info(f"Checking {len(active_chains)} active chains for overage expiry")

                for chain_id in active_chains:
                    try:
                        if await self.overage_service.check_overage_expiry(chain_id):
                            # Trigger contraction proposal
                            await self._handle_overage_expiry(chain_id)
                    except Exception as e:
                        logger.error(f"Error checking overage expiry for chain {chain_id}: {e}")

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            await asyncio.sleep(300)  # 5 minutes

    async def _handle_overage_expiry(self, chain_id: str):
        """Handle fleet contraction when overage expires."""
        from core.quota_manager import QuotaManager

        chain = self.db.query(DelegationChain).filter(
            DelegationChain.id == chain_id
        ).first()

        if not chain:
            logger.warning(f"Chain {chain_id} not found for overage expiry handling")
            return

        # Get new base limit
        base_limit = QuotaManager.get_fleet_size_limit(chain.tenant_id, self.db)
        current_size = await self._get_current_fleet_size(chain_id)

        if current_size > base_limit:
            # Create contraction proposal (auto-approved due to expiry)
            logger.info(
                f"Creating auto-contraction proposal for chain {chain_id}: "
                f"{current_size} -> {base_limit} (overage expired)"
            )

            proposal = await self.proposal_service.create_contraction_proposal(
                chain_id=chain_id,
                tenant_id=chain.tenant_id,
                current_size=current_size,
                proposed_size=base_limit,
                reason="Overage expired - returning to base plan limit"
            )

            # Auto-approve the proposal
            try:
                await self.proposal_service.approve_proposal(
                    proposal_id=proposal.id,
                    tenant_id=chain.tenant_id,
                    approved_by="system",
                    note="Auto-approved due to overage expiry"
                )
                logger.info(f"Auto-approved contraction proposal {proposal.id}")
            except Exception as e:
                logger.error(f"Failed to auto-approve contraction proposal: {e}")

    async def start_monitoring(self):
        """Start background monitoring for overage expiry."""
        if self.running:
            logger.warning("Monitoring already running")
            return

        self.running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started fleet scaler monitoring")

    async def stop_monitoring(self):
        """Stop background monitoring."""
        if not self.running:
            return

        self.running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped fleet scaler monitoring")

    async def execute_scaling_proposal(
        self,
        proposal_id: str) -> Dict[str, Any]:
        """
        Execute an approved scaling proposal.

        Args:
            proposal_id: Proposal ID to execute
            tenant_id: Any UUID

        Returns:
            Execution result
        """
        # Get proposal
        proposal = await self.proposal_service.get_proposal(proposal_id, tenant_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        # Check constraints before execution
        constraints = await self.check_scaling_constraints(
            proposal.chain_id,
            tenant_id,
            proposal.proposed_fleet_size
        )

        if not constraints["allowed"]:
            raise ValueError(
                f"Scaling constraints not met: {constraints}"
            )

        # Execute scaling (placeholder - actual fleet scaling logic would go here)
        logger.info(
            f"Executing scaling proposal {proposal_id}: "
            f"{proposal.current_fleet_size} -> {proposal.proposed_fleet_size}"
        )

        return {
            "success": True,
            "proposal_id": proposal_id,
            "previous_size": proposal.current_fleet_size,
            "new_size": proposal.proposed_fleet_size,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }

# Convenience function for DI
def get_fleet_scaler_service(db: Session) -> FleetScalerService:
    """Get FleetScalerService instance."""
    return FleetScalerService(db)

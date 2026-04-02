"""
Auto-Approval Service for Adaptive Fleet Scaling

Evaluates scaling proposals against auto-approval rules and automatically
approves proposals that meet configured criteria.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.models import ScalingAutoApproval, ScalingProposal
from core.database import SessionLocal
from core.fleet_orchestration.scaling_proposal_service import ScalingProposalService

logger = logging.getLogger(__name__)

class AutoApprovalService:
    """
    Service for evaluating and applying auto-approval rules to scaling proposals.

    Supports:
    - Rule-based auto-approval based on cost, size, and metrics thresholds
    - Priority-based rule evaluation (lower priority number = higher priority)
    - Chain-specific and tenant-wide rules
    - Rule statistics tracking
    """

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    def create_auto_approval_rule(
        self,
        
        rule_name: str,
        created_by: str,
        chain_id: Optional[str] = None,
        description: Optional[str] = None,
        max_cost_per_hour: Optional[float] = None,
        max_fleet_size: Optional[int] = None,
        max_size_increase: Optional[int] = None,
        min_success_rate_threshold: Optional[float] = None,
        max_latency_threshold: Optional[int] = None,
        priority: int = 100,
        is_active: bool = True
    ) -> ScalingAutoApproval:
        """
        Create a new auto-approval rule.

        Args:
            tenant_id: Any UUID
            rule_name: Human-readable rule name
            created_by: User ID creating the rule
            chain_id: Optional chain ID (NULL = applies to all chains)
            description: Optional rule description
            max_cost_per_hour: Maximum cost per hour in USD
            max_fleet_size: Maximum fleet size allowed
            max_size_increase: Maximum number of agents to add
            min_success_rate_threshold: Minimum success rate percentage
            max_latency_threshold: Maximum latency in milliseconds
            priority: Rule priority (lower = higher priority)
            is_active: Whether rule is active

        Returns:
            Created ScalingAutoApproval rule
        """
        rule = ScalingAutoApproval(
            id=str(__import__('uuid').uuid4()),
            tenant_id=tenant_id,
            chain_id=chain_id,
            rule_name=rule_name,
            description=description,
            max_cost_per_hour=Decimal(str(max_cost_per_hour)) if max_cost_per_hour is not None else None,
            max_fleet_size=max_fleet_size,
            max_size_increase=max_size_increase,
            min_success_rate_threshold=Decimal(str(min_success_rate_threshold)) if min_success_rate_threshold is not None else None,
            max_latency_threshold=max_latency_threshold,
            priority=priority,
            is_active=is_active,
            created_by=created_by
        )

        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)

        logger.info(f"[AutoApproval] Created rule '{rule_name}' for tenant {tenant_id}")
        return rule

    def get_active_rules(
        self,
        
        chain_id: Optional[str] = None
    ) -> List[ScalingAutoApproval]:
        """
        Get all active auto-approval rules for a tenant/chain.

        Rules are ordered by priority (lower number = higher priority).
        Chain-specific rules are evaluated before tenant-wide rules.

        Args:
            tenant_id: Any UUID
            chain_id: Optional chain ID

        Returns:
            List of active ScalingAutoApproval rules
        """
        query = self.db.query(ScalingAutoApproval).filter(
            ScalingAutoApproval.tenant_id == tenant_id,
            ScalingAutoApproval.is_active == True
        )

        # Get chain-specific rules first, then tenant-wide rules
        chain_rules = query.filter(
            ScalingAutoApproval.chain_id == chain_id
        ).order_by(ScalingAutoApproval.priority).all()

        tenant_wide_rules = query.filter(
            ScalingAutoApproval.chain_id.is_(None)
        ).order_by(ScalingAutoApproval.priority).all()

        return chain_rules + tenant_wide_rules

    def evaluate_proposal(
        self,
        proposal: ScalingProposal,
        metrics: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[ScalingAutoApproval], str]:
        """
        Evaluate a scaling proposal against auto-approval rules.

        Args:
            proposal: ScalingProposal to evaluate
            metrics: Optional current performance metrics

        Returns:
            Tuple of (is_approved, matching_rule, reason)
        """
        rules = self.get_active_rules(
            tenant_id=proposal.tenant_id,
            chain_id=proposal.chain_id
        )

        if not rules:
            return False, None, "No auto-approval rules found"

        # Calculate proposal metrics
        size_increase = max(0, proposal.proposed_fleet_size - proposal.current_fleet_size)
        cost_per_hour = float(proposal.cost_estimate) / max(1, float(proposal.duration_hours))

        # Get metrics from proposal or provided dict
        metrics_data = metrics or (proposal.metrics_json if proposal.metrics_json else {})
        success_rate = metrics_data.get('success_rate', 100.0)
        avg_latency = metrics_data.get('avg_latency_ms', 0)

        # Evaluate each rule in priority order
        last_reason = ""
        for rule in rules:
            matches, reason = self._evaluate_rule(
                rule=rule,
                proposal=proposal,
                size_increase=size_increase,
                cost_per_hour=cost_per_hour,
                success_rate=success_rate,
                avg_latency=avg_latency
            )

            if matches:
                logger.info(
                    f"[AutoApproval] Proposal {proposal.id} auto-approved by rule '{rule.rule_name}': {reason}"
                )
                return True, rule, reason

            # Track the last rejection reason for better error messages
            last_reason = reason

        return False, None, last_reason if last_reason else "No matching auto-approval rules"

    def _evaluate_rule(
        self,
        rule: ScalingAutoApproval,
        proposal: ScalingProposal,
        size_increase: int,
        cost_per_hour: float,
        success_rate: float,
        avg_latency: int
    ) -> Tuple[bool, str]:
        """
        Evaluate a single auto-approval rule against a proposal.

        Args:
            rule: ScalingAutoApproval rule to evaluate
            proposal: ScalingProposal to check
            size_increase: Number of agents to add
            cost_per_hour: Estimated cost per hour
            success_rate: Current success rate percentage
            avg_latency: Current average latency in ms

        Returns:
            Tuple of (matches_rule, reason)
        """
        reasons = []

        # Check cost constraint
        if rule.max_cost_per_hour is not None:
            if cost_per_hour > float(rule.max_cost_per_hour):
                return False, f"Cost per hour ${cost_per_hour:.2f} exceeds max ${float(rule.max_cost_per_hour):.2f}"
            reasons.append(f"cost ${cost_per_hour:.2f}/hr <= ${float(rule.max_cost_per_hour):.2f}")

        # Check fleet size constraint
        if rule.max_fleet_size is not None:
            if proposal.proposed_fleet_size > rule.max_fleet_size:
                return False, f"Proposed size {proposal.proposed_fleet_size} exceeds max {rule.max_fleet_size}"
            reasons.append(f"size {proposal.proposed_fleet_size} <= max {rule.max_fleet_size}")

        # Check size increase constraint (for expansion only)
        if rule.max_size_increase is not None and size_increase > 0:
            if size_increase > rule.max_size_increase:
                return False, f"Size increase {size_increase} exceeds max {rule.max_size_increase}"
            reasons.append(f"increase {size_increase} <= max {rule.max_size_increase}")

        # Check success rate constraint
        if rule.min_success_rate_threshold is not None:
            if success_rate < float(rule.min_success_rate_threshold):
                return False, f"Success rate {success_rate:.1f}% below min {float(rule.min_success_rate_threshold):.1f}%"
            reasons.append(f"success rate {success_rate:.1f}% >= min {float(rule.min_success_rate_threshold):.1f}%")

        # Check latency constraint
        if rule.max_latency_threshold is not None:
            if avg_latency > rule.max_latency_threshold:
                return False, f"Latency {avg_latency}ms exceeds max {rule.max_latency_threshold}ms"
            reasons.append(f"latency {avg_latency}ms <= max {rule.max_latency_threshold}ms")

        if reasons:
            return True, "All conditions met: " + ", ".join(reasons)
        return True, "No conditions specified (unconditional approval)"

    async def auto_approve_proposal(
        self,
        proposal_id: str,
        metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Automatically approve a proposal if it matches auto-approval rules.

        Args:
            proposal_id: ScalingProposal ID
            metrics: Optional current performance metrics

        Returns:
            Dict with:
                - approved (bool): Whether proposal was auto-approved
                - rule_name (str|None): Name of matching rule
                - reason (str): Approval/rejection reason
                - proposal (ScalingProposal): Updated proposal object
        """
        proposal = self.db.query(ScalingProposal).filter(
            ScalingProposal.id == proposal_id
        ).first()

        if not proposal:
            return {
                "approved": False,
                "rule_name": None,
                "reason": f"Proposal {proposal_id} not found",
                "proposal": None
            }

        # Only approve pending proposals
        if proposal.status != 'pending':
            return {
                "approved": False,
                "rule_name": None,
                "reason": f"Proposal status is '{proposal.status}', not 'pending'",
                "proposal": proposal
            }

        # Evaluate against rules
        is_approved, matching_rule, reason = self.evaluate_proposal(proposal, metrics)

        if is_approved and matching_rule:
            # Auto-approve the proposal
            proposal.status = 'approved'
            proposal.approved_by = f"auto-approval-rule:{matching_rule.id}"
            proposal.approved_at = datetime.now(timezone.utc)

            # Update rule statistics
            matching_rule.times_applied += 1
            matching_rule.last_applied_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(proposal)
            self.db.refresh(matching_rule)

            logger.info(
                f"[AutoApproval] Auto-approved proposal {proposal_id} via rule '{matching_rule.rule_name}'"
            )

            return {
                "approved": True,
                "rule_name": matching_rule.rule_name,
                "reason": reason,
                "proposal": proposal
            }

        return {
            "approved": False,
            "rule_name": matching_rule.rule_name if matching_rule else None,
            "reason": reason,
            "proposal": proposal
        }

    def update_rule(
        self,
        rule_id: str,
        
        updates: Dict[str, Any]
    ) -> Optional[ScalingAutoApproval]:
        """
        Update an auto-approval rule.

        Args:
            rule_id: Rule UUID
            tenant_id: Any UUID (for ownership verification)
            updates: Dict of fields to update

        Returns:
            Updated ScalingAutoApproval or None if not found
        """
        rule = self.db.query(ScalingAutoApproval).filter(
            ScalingAutoApproval.id == rule_id,
            ScalingAutoApproval.tenant_id == tenant_id
        ).first()

        if not rule:
            return None

        # Update allowed fields
        allowed_fields = [
            'rule_name', 'description', 'max_cost_per_hour', 'max_fleet_size',
            'max_size_increase', 'min_success_rate_threshold', 'max_latency_threshold',
            'priority', 'is_active'
        ]

        for field, value in updates.items():
            if field in allowed_fields:
                if field in ['max_cost_per_hour', 'min_success_rate_threshold']:
                    setattr(rule, field, Decimal(str(value)) if value is not None else None)
                else:
                    setattr(rule, field, value)

        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """
        Delete an auto-approval rule.

        Args:
            rule_id: Rule UUID
            tenant_id: Any UUID (for ownership verification)

        Returns:
            True if deleted, False if not found
        """
        rule = self.db.query(ScalingAutoApproval).filter(
            ScalingAutoApproval.id == rule_id,
            ScalingAutoApproval.tenant_id == tenant_id
        ).first()

        if not rule:
            return False

        self.db.delete(rule)
        self.db.commit()
        logger.info(f"[AutoApproval] Deleted rule {rule_id}")
        return True

    def get_rule_statistics(
        self) -> Dict[str, Any]:
        """
        Get auto-approval rule statistics for a tenant.

        Args:
            tenant_id: Any UUID

        Returns:
            Dict with rule statistics
        """
        rules = self.db.query(ScalingAutoApproval).filter(
            ScalingAutoApproval.tenant_id == tenant_id
        ).all()

        active_rules = [r for r in rules if r.is_active]
        total_applications = sum(r.times_applied for r in rules)

        return {
            "total_rules": len(rules),
            "active_rules": len(active_rules),
            "inactive_rules": len(rules) - len(active_rules),
            "total_applications": total_applications,
            "rules": [
                {
                    "id": r.id,
                    "rule_name": r.rule_name,
                    "is_active": r.is_active,
                    "priority": r.priority,
                    "times_applied": r.times_applied,
                    "last_applied_at": r.last_applied_at.isoformat() if r.last_applied_at else None
                }
                for r in rules
            ]
        }

def get_auto_approval_service(db: Session = None) -> AutoApprovalService:
    """
    Factory function to get AutoApprovalService instance.

    Args:
        db: Optional database session

    Returns:
        AutoApprovalService instance
    """
    return AutoApprovalService(db=db)

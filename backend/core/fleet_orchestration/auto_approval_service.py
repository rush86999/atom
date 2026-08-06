"""
Auto-Approval Service for Adaptive Fleet Scaling

Evaluates scaling proposals against auto-approval rules and automatically
approves proposals that meet configured criteria.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.models import ScalingAutoApproval, ScalingProposal
from core.database import SessionLocal

logger = logging.getLogger(__name__)

class AutoApprovalService:
    """
    Service for evaluating and applying auto-approval rules to scaling proposals.

    Rules are stored in the ScalingAutoApproval table with the following
    constraints:
    - max_agents: Maximum proposed fleet size eligible for auto-approval
    - max_cost_increase_percent: Maximum allowed cost increase percentage
    - risk_threshold: Maximum risk score (0-1) for auto-approval
    """

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    def create_auto_approval_rule(
        self,
        rule_name: str,
        created_by: str,
        description: Optional[str] = None,
        max_agents: int = 10,
        max_cost_increase_percent: float = 50.0,
        risk_threshold: float = 0.3,
        is_active: bool = True
    ) -> ScalingAutoApproval:
        """
        Create a new auto-approval rule.

        Args:
            rule_name: Human-readable rule name (stored in description)
            created_by: User ID creating the rule
            description: Optional rule description
            max_agents: Maximum proposed fleet size allowed
            max_cost_increase_percent: Maximum cost increase percentage
            risk_threshold: Maximum risk score (0-1)
            is_active: Whether rule is active

        Returns:
            Created ScalingAutoApproval rule
        """
        rule = ScalingAutoApproval(
            id=str(__import__('uuid').uuid4()),
            tenant_id="default",
            max_agents=max_agents,
            max_cost_increase_percent=max_cost_increase_percent,
            risk_threshold=risk_threshold,
            is_active=is_active,
            description=f"{rule_name}: {description}" if description else rule_name,
            created_by=created_by
        )

        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)

        logger.info(
            f"[AutoApproval] Created rule '{rule_name}' "
            f"(max_agents={max_agents}, max_cost_increase_pct={max_cost_increase_percent})"
        )
        return rule

    def get_active_rules(
        self,
        chain_id: Optional[str] = None
    ) -> List[ScalingAutoApproval]:
        """
        Get all active auto-approval rules.

        Args:
            chain_id: Unused (rules are tenant-wide in this schema)

        Returns:
            List of active ScalingAutoApproval rules
        """
        return self.db.query(ScalingAutoApproval).filter(
            ScalingAutoApproval.is_active == True
        ).order_by(ScalingAutoApproval.created_at).all()

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
        rules = self.get_active_rules()

        if not rules:
            return False, None, "No auto-approval rules found"

        # Support both pydantic ScalingProposal and the SQLAlchemy model
        current_size = getattr(proposal, "current_fleet_size", None)
        if current_size is None:
            current_size = proposal.current_agents
        proposed_size = getattr(proposal, "proposed_fleet_size", None)
        if proposed_size is None:
            proposed_size = proposal.proposed_agents

        size_increase = max(0, proposed_size - current_size)
        cost_increase_percent = (
            (size_increase / max(1, current_size)) * 100
        )
        risk = float(
            getattr(proposal, "risk_score", None)
            or proposal.metadata.get("risk_score", 0.5)
        )

        last_reason = ""
        for rule in rules:
            matches, reason = self._evaluate_rule(
                rule=rule,
                proposal=proposal,
                proposed_size=proposed_size,
                cost_increase_percent=cost_increase_percent,
                risk=risk
            )

            if matches:
                logger.info(
                    f"[AutoApproval] Proposal {proposal.id} auto-approved by rule "
                    f"'{rule.description}': {reason}"
                )
                return True, rule, reason

            last_reason = reason

        return False, None, last_reason if last_reason else "No matching auto-approval rules"

    def _evaluate_rule(
        self,
        rule: ScalingAutoApproval,
        proposal: ScalingProposal,
        proposed_size: int,
        cost_increase_percent: float,
        risk: float
    ) -> Tuple[bool, str]:
        """
        Evaluate a single auto-approval rule against a proposal.

        Args:
            rule: ScalingAutoApproval rule to evaluate
            proposal: ScalingProposal to check
            proposed_size: Proposed fleet size
            cost_increase_percent: Estimated cost increase percentage
            risk: Proposal risk score

        Returns:
            Tuple of (matches_rule, reason)
        """
        reasons = []

        if proposed_size > rule.max_agents:
            return False, (
                f"Proposed size {proposed_size} exceeds max "
                f"{rule.max_agents}"
            )
        reasons.append(f"size {proposed_size} <= max {rule.max_agents}")

        if cost_increase_percent > rule.max_cost_increase_percent:
            return False, (
                f"Cost increase {cost_increase_percent:.1f}% exceeds max "
                f"{rule.max_cost_increase_percent:.1f}%"
            )
        reasons.append(
            f"cost increase {cost_increase_percent:.1f}% <= "
            f"{rule.max_cost_increase_percent:.1f}%"
        )

        if risk > rule.risk_threshold:
            return False, (
                f"Risk {risk:.2f} exceeds threshold {rule.risk_threshold:.2f}"
            )
        reasons.append(f"risk {risk:.2f} <= {rule.risk_threshold:.2f}")

        return True, "All conditions met: " + ", ".join(reasons)

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

        if proposal.status != 'pending':
            return {
                "approved": False,
                "rule_name": None,
                "reason": f"Proposal status is '{proposal.status}', not 'pending'",
                "proposal": proposal
            }

        is_approved, matching_rule, reason = self.evaluate_proposal(proposal, metrics)

        if is_approved and matching_rule:
            proposal.status = 'approved'
            proposal.approved_by = f"auto-approval-rule:{matching_rule.id}"
            proposal.approved_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(proposal)

            logger.info(
                f"[AutoApproval] Auto-approved proposal {proposal_id} via rule "
                f"'{matching_rule.description}'"
            )

            return {
                "approved": True,
                "rule_name": matching_rule.description,
                "reason": reason,
                "proposal": proposal
            }

        return {
            "approved": False,
            "rule_name": matching_rule.description if matching_rule else None,
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
            updates: Dict of fields to update

        Returns:
            Updated ScalingAutoApproval or None if not found
        """
        rule = self.db.query(ScalingAutoApproval).filter(
            ScalingAutoApproval.id == rule_id
        ).first()

        if not rule:
            return None

        allowed_fields = [
            'description', 'max_agents', 'max_cost_increase_percent',
            'risk_threshold', 'is_active'
        ]

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(rule, field, value)

        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """
        Delete an auto-approval rule.

        Args:
            rule_id: Rule UUID

        Returns:
            True if deleted, False if not found
        """
        rule = self.db.query(ScalingAutoApproval).filter(
            ScalingAutoApproval.id == rule_id
        ).first()

        if not rule:
            return False

        self.db.delete(rule)
        self.db.commit()
        logger.info(f"[AutoApproval] Deleted rule {rule_id}")
        return True

    def get_rule_statistics(
        self
    ) -> Dict[str, Any]:
        """
        Get auto-approval rule statistics.

        Returns:
            Dict with rule statistics
        """
        rules = self.db.query(ScalingAutoApproval).all()

        active_rules = [r for r in rules if r.is_active]

        return {
            "total_rules": len(rules),
            "active_rules": len(active_rules),
            "inactive_rules": len(rules) - len(active_rules),
            "rules": [
                {
                    "id": r.id,
                    "rule_name": r.description,
                    "is_active": r.is_active,
                    "max_agents": r.max_agents,
                    "max_cost_increase_percent": r.max_cost_increase_percent,
                    "risk_threshold": r.risk_threshold
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

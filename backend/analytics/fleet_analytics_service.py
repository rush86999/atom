import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from core.models import DelegationChain, AgentExecution, TokenUsage, HITLAction, HITLActionStatus

logger = logging.getLogger(__name__)

class FleetAnalyticsService:
    """
    Upstream Analytics service for Fleet Admiralty operations.
    Aggregates costs, efficiency metrics, and HITL frequency across delegation chains.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_fleet_stats(self, chain_id: str) -> Dict[str, Any]:
        """
        Get comprehensive performance statistics for a specific delegation chain.
        """
        # 1. Fetch Chain Metadata
        chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
        if not chain:
            return {"error": "Delegation chain not found"}

        # 2. Aggregate Token Usage (Fleet-wide cost attribution)
        usage_stats = self.db.query(
            func.sum(TokenUsage.cost_usd).label("total_cost"),
            func.sum(TokenUsage.prompt_tokens).label("total_input_tokens"),
            func.sum(TokenUsage.completion_tokens).label("total_output_tokens"),
            func.count(TokenUsage.id).label("interaction_count")
        ).filter(TokenUsage.chain_id == chain_id).first()

        # 3. Member Statistics
        members_count = self.db.query(func.count(AgentExecution.id)).filter(
            AgentExecution.chain_id == chain_id
        ).scalar()

        # 4. HITL Frequency (Interventions per Chain)
        hitl_stats = self.db.query(
            func.count(HITLAction.id).label("total_interventions"),
            func.sum(case((HITLAction.status == HITLActionStatus.APPROVED.value, 1), else_=0)).label("approved_count"),
            func.sum(case((HITLAction.status == HITLActionStatus.REJECTED.value, 1), else_=0)).label("rejected_count")
        ).filter(HITLAction.chain_id == chain_id).first()

        # 5. Calculate Metrics
        total_cost = usage_stats.total_cost or 0.0
        total_tokens = (usage_stats.total_input_tokens or 0) + (usage_stats.total_output_tokens or 0)
        
        success_weight = 1.0 if chain.status == 'COMPLETED' else 0.0
        efficiency_score = (success_weight / total_cost) if total_cost > 0 else 0.0

        return {
            "chain_id": chain_id,
            "goal": chain.root_task_description,
            "status": chain.status,
            "metrics": {
                "total_cost_usd": float(total_cost),
                "total_tokens": int(total_tokens),
                "interaction_count": int(usage_stats.interaction_count or 0),
                "member_count": int(members_count or 0),
                "efficiency_score": round(float(efficiency_score), 4)
            },
            "hitl_summary": {
                "total_requests": int(hitl_stats.total_interventions or 0),
                "approved": int(hitl_stats.approved_count or 0),
                "rejected": int(hitl_stats.rejected_count or 0)
            },
            "created_at": chain.created_at.isoformat() if chain.created_at else None,
            "updated_at": chain.updated_at.isoformat() if chain.updated_at else None
        }

    def get_most_efficient_fleets(self, workspace_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most cost-effective delegation chains for a workspace (Upstream model).
        """
        chains = self.db.query(DelegationChain).filter(
            DelegationChain.workspace_id == workspace_id,
            DelegationChain.status == 'COMPLETED'
        ).order_by(DelegationChain.created_at.desc()).limit(limit).all()

        results = []
        for chain in chains:
            results.append(self.get_fleet_stats(chain.id))
        
        return results

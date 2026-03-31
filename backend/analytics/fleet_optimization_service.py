import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from analytics.fleet_analytics_service import FleetAnalyticsService
from core.llm.byok_handler import QueryComplexity

logger = logging.getLogger(__name__)

class FleetOptimizationService:
    """
    Upstream Optimization engine for Fleet Admiralty.
    Suggests agent configurations and model tiers based on historical telemetry.
    """

    def __init__(self, db: Session):
        self.db = db
        self.analytics = FleetAnalyticsService(db)

    def get_optimization_parameters(
        self, 
        tenant_id: str, 
        domain: str, 
        task_description: str,
        complexity_override: Optional[QueryComplexity] = None
    ) -> Dict[str, Any]:
        """
        Calculates optimized parameters for a fleet recruitment sub-task.
        
        Logic:
        - HIGH success rate (>95%) + LOW complexity: Downgrade to faster/cheaper model.
        - LOW success rate (<85%) or LOW HITL approval: Upgrade to higher reasoning model.
        - High latency: Suggest lower max_steps or parallelization.
        """
        logger.info(f"Optimizing recruitment for domain: {domain} (Tenant: {tenant_id})")
        
        # 1. Fetch domain history
        history = self.analytics.get_domain_performance_stats(tenant_id, domain)
        
        # Default parameters
        params = {
            "model": "auto",
            "max_steps": 8,
            "mentorship_mode": False,
            "optimized_context": {},
            "optimization_reason": "Default starting point (Standard Profiling)"
        }

        # 2. Heuristic-based Optimization
        success_rate = history.get("success_rate", 0.0)
        hitl_rate = history.get("hitl_approval_rate", 1.0)
        total_interactions = history.get("total_interactions", 0)

        # We need a minimum sample size to be confident (Combined Links + HITL)
        hitl_total = history.get("total_hitl_requests", 0)
        if (total_interactions + hitl_total) < 3:
            params["optimization_reason"] = "Insufficient data for domain optimization. Using defaults."
            return params

        # Optimization Rule 1: Reasoning Upgrade (Fail-Fast protection)
        if success_rate < 0.85 or hitl_rate < 0.8:
            params["model"] = "quality" # Force high-reasoning model
            params["max_steps"] = 10
            params["mentorship_mode"] = True
            params["optimization_reason"] = f"Low historical performance ({success_rate:.0%}) detected. Upgrading to high-reasoning tier."
            return params

        # Optimization Rule 2: Cost-Down (Efficiency gain)
        if success_rate >= 0.96 and hitl_rate >= 0.95:
            if len(task_description) < 150:
                params["model"] = "fast" # Downgrade to cheap model
                params["max_steps"] = 5
                params["optimization_reason"] = f"Efficiency gain: Excellent historical success ({success_rate:.0%}) with low task complexity. Downgrading for cost savings."
                return params

        params["optimization_reason"] = f"Standard parity maintained. Domain performance stable ({success_rate:.0%})."
        return params

    def analyze_bottlenecks(self, chain_id: str) -> List[Dict[str, Any]]:
        """
        Post-hoc analysis to identify which links in a chain were inefficient.
        """
        return []

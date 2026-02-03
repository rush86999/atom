import logging
from typing import Any, Dict, List
from intelligence.models import CapacityPlan, ResourceRole
from sales.models import Deal, DealStage
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class StaffingForecaster:
    def __init__(self, db: Session):
        self.db = db

    def predict_resource_demand(self, workspace_id: str) -> Dict[str, float]:
        """
        Calculates demand based on open pipeline probability.
        Heuristic: $100k Deal Value = 500 Engineering Hours (Rate $200/hr)
        """
        # Fetch Open Pipeline
        pipeline = self.db.query(Deal).filter(
            Deal.workspace_id == workspace_id,
            Deal.stage.notin_([DealStage.CLOSED_WON, DealStage.CLOSED_LOST])
        ).all()
        
        weighted_pipeline_value = 0.0
        for deal in pipeline:
            # Simple probability map
            prob = 0.1
            if deal.stage == DealStage.NEGOTIATION: prob = 0.8
            elif deal.stage == DealStage.PROPOSAL: prob = 0.5
            
            weighted_pipeline_value += (deal.value * prob)
            
        # Convert to Hours (Simplified Model)
        # Assume 50% of revenue goes to Engineering Labor at $100/hr cost
        labor_budget = weighted_pipeline_value * 0.5
        demand_hours = labor_budget / 100.0
        
        return {
            "weighted_pipeline_value": weighted_pipeline_value,
            "estimated_engineering_hours": demand_hours
        }

    def check_capacity_gap(self, workspace_id: str, demand_hours: float) -> Dict[str, Any]:
        """
        Compare Demand vs Supply (Capacity Plans)
        """
        # Sum active capacity
        plans = self.db.query(CapacityPlan).filter(
            CapacityPlan.workspace_id == workspace_id
        ).all()
        
        supply_hours = sum(p.available_hours for p in plans)
        
        if demand_hours > supply_hours:
            gap = demand_hours - supply_hours
            return {
                "status": "SHORTAGE",
                "gap_hours": gap,
                "message": f"Capacity Shortage: Need {int(gap)} more hours to support pipeline."
            }
            
        return {"status": "OK", "surplus_hours": supply_hours - demand_hours}

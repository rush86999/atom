import logging
import json
from sqlalchemy.orm import Session
from typing import Dict, Any

from intelligence.models import BusinessScenario, ResourceRole

logger = logging.getLogger(__name__)

class ScenarioEngine:
    def __init__(self, db: Session):
        self.db = db

    def simulate_hiring_scenario(self, workspace_id: str, hiring_plan: Dict[str, int]) -> BusinessScenario:
        """
        Simulate impact of hiring X people in Role Y.
        Input: {"Senior Engineer": 2}
        """
        # 1. Calculate Cost Impact
        monthly_cost_increase = 0.0
        capacity_increase_hours = 0.0
        
        for role_name, count in hiring_plan.items():
            role = self.db.query(ResourceRole).filter(
                ResourceRole.workspace_id == workspace_id,
                ResourceRole.name == role_name
            ).first()
            
            if role:
                # Assume 160 hrs/mo
                cost = role.hourly_cost * 160 * count
                monthly_cost_increase += cost
                capacity_increase_hours += (160 * count)
            else:
                 logger.warning(f"Role {role_name} not found, skipping cost calc.")

        impact = {
            "monthly_cash_burn_increase": monthly_cost_increase,
            "monthly_capacity_increase_hours": capacity_increase_hours,
            "can_support_additional_revenue": capacity_increase_hours * 200 # Assume $200 billable rate
        }
        
        # Save Scenario
        scenario = BusinessScenario(
            workspace_id=workspace_id,
            name=f"Hiring Simulation: {json.dumps(hiring_plan)}",
            parameters_json=hiring_plan,
            impact_json=impact
        )
        self.db.add(scenario)
        self.db.commit()
        
        return scenario

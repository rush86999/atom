import logging
from datetime import datetime
from typing import Any, Dict, List
from service_delivery.models import Project, ProjectTask

from core.database import get_db_session
from core.resource_reasoning import ResourceReasoningEngine

logger = logging.getLogger(__name__)

class ProjectRiskForecaster:
    """
    Evaluates project risks based on timeline slippage and resource health.
    """

    def __init__(self, db_session: Any = None, reasoning_engine: Any = None):
        self.db = db_session
        self.reasoning = reasoning_engine or ResourceReasoningEngine(db_session)

    def evaluate_risks(self, project_id: str) -> Dict[str, Any]:
        """
        Calculates risk score and rationale for a project.
        """
        db = self.db or get_db_session()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {"risk_score": 0.0, "rationale": "Project not found"}

            risk_score = 0.0
            reasons = []

            # 1. Timeline Slippage Risk
            if project.predicted_end_date and project.planned_end_date:
                if project.predicted_end_date > project.planned_end_date:
                    delay_days = (project.predicted_end_date - project.planned_end_date).days
                    if delay_days > 0:
                        severity = min(40.0, delay_days * 5.0) # Cap at 40
                        risk_score += severity
                        reasons.append(f"Predicted delay of {delay_days} days")

            # 2. Resource Burnout Risk
            # Check risk for all assigned users on this project
            assigned_user_ids = (
                db.query(ProjectTask.assigned_to)
                .filter(ProjectTask.project_id == project_id)
                .filter(ProjectTask.assigned_to.isnot(None))
                .distinct()
                .all()
            )
            
            for (user_id,) in assigned_user_ids:
                burnout_data = self.reasoning.assess_burnout_risk(user_id)
                if burnout_data.get("risk_level") == "high":
                    risk_score += 20.0
                    reasons.append(f"High burnout risk for team member {user_id}")
                elif burnout_data.get("risk_level") == "medium":
                    risk_score += 10.0
                    reasons.append(f"Medium burnout risk for team member {user_id}")

            # 3. Scope Smog (Pending vs Completed)
            pending_count = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).filter(ProjectTask.status != "completed").count()
            completed_count = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).filter(ProjectTask.status == "completed").count()
            
            if pending_count > completed_count * 2 and pending_count > 5:
                risk_score += 15.0
                reasons.append("High ratio of pending work to completed work (Scope Smog)")

            # Finalize
            risk_score = min(100.0, risk_score)
            project.risk_score = risk_score
            project.risk_rationale = "; ".join(reasons)
            
            # Simple mapping to level
            if risk_score > 60:
                project.risk_level = "high"
            elif risk_score > 30:
                project.risk_level = "medium"
            else:
                project.risk_level = "low"
                
            db.commit()
            
            return {
                "risk_score": risk_score,
                "risk_level": project.risk_level,
                "rationale": project.risk_rationale
            }
        finally:
            if not self.db:
                db.close()

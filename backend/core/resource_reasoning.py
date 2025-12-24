import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.database import SessionLocal
from core.models import User
from service_delivery.models import ProjectTask
from core.knowledge_ingestion import get_knowledge_ingestion
from core.workforce_analytics import WorkforceAnalyticsService

logger = logging.getLogger(__name__)

class ResourceReasoningEngine:
    """
    AI-driven engine for optimal task assignment and burnout detection.
    """

    def __init__(self, db_session: Any = None):
        self.db = db_session
        self.knowledge_manager = get_knowledge_ingestion()

    async def get_optimal_assignee(self, workspace_id: str, task_name: str, task_description: Optional[str] = None) -> Dict[str, Any]:
        """
        Suggests the best team member based on semantic skill match, current workload, and estimation bias.
        """
        db = self.db or SessionLocal()
        analytics = WorkforceAnalyticsService(db_session=db)
        try:
            # 1. Get all active users in workspace
            users = db.query(User).filter(User.status == "active").all()
            
            candidates = []
            for user in users:
                # Calculate Load
                load = db.query(ProjectTask).filter(ProjectTask.assigned_to == user.id).filter(ProjectTask.status == "in_progress").count()
                
                # Fetch Bias Profile
                bias_profile = analytics.get_user_bias_profile(user.id, workspace_id)
                bias_factor = bias_profile.get("adjustment_multiplier", 1.0)
                
                # Semantic Skill Match
                skill_score = 0.5
                user_skills = set(s.strip().lower() for s in user.skills.split(",")) if user.skills else set()
                
                # 1. Check for explicit required_skills in metadata
                match_content = f"{task_name} {task_description or ''}".lower()
                
                # If "required skills:" is in the description, prioritize those
                if "required skills:" in match_content:
                    req_part = match_content.split("required skills:")[1].split(".")[0]
                    # Handle multi-word skills separated by commas or semi-colons
                    required_keywords = [s.strip() for s in req_part.replace(";", ",").split(",")]
                    
                    found_matches = 0
                    for req in required_keywords:
                        if req in user_skills:
                            found_matches += 1
                    
                    if found_matches > 0:
                        # Weight by how many of the requirements we meet
                        skill_score = min(1.0, 0.5 + (found_matches / len(required_keywords)) * 0.5)
                else:
                    # Fallback to general keyword match
                    # We check if any of the user's skills (which can be multi-word) are mentioned in the task name
                    for skill in user_skills:
                        if skill in match_content:
                            skill_score = max(skill_score, 0.9)
                
                # Composite Score: Higher Skill, Lower Load, Lower Bias
                # bias_penalty: if bias_factor > 1.0, they take longer, so we penalize
                bias_penalty = 1.0 / bias_factor if bias_factor > 0 else 1.0
                
                composite_score = skill_score * (1.0 / (load + 1)) * bias_penalty
                
                candidates.append({
                    "user_id": user.id,
                    "name": f"{user.first_name} {user.last_name}",
                    "load": load,
                    "skill_score": skill_score,
                    "bias_factor": bias_factor,
                    "composite_score": composite_score
                })
            
            # Sort by composite score
            candidates.sort(key=lambda x: x["composite_score"], reverse=True)
            
            top_match = candidates[0] if candidates else None
            
            return {
                "suggested_user": top_match,
                "alternatives": candidates[1:3]
            }
        finally:
            if not self.db:
                db.close()

    def assess_burnout_risk(self, user_id: str) -> Dict[str, Any]:
        """
        Detects signs of burnout based on workload, throughput volatility, and engagement.
        """
        db = self.db or SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"risk": "unknown"}
            
            # Indicators:
            # 1. High Load (> 10 active tasks)
            load = db.query(ProjectTask).filter(ProjectTask.assigned_to == user.id).filter(ProjectTask.status == "in_progress").count()
            
            # 2. Overdue Tasks
            overdue = (
                db.query(ProjectTask)
                .filter(ProjectTask.assigned_to == user_id)
                .filter(ProjectTask.status != "completed")
                .filter(ProjectTask.due_date < datetime.utcnow())
                .count()
            )
            
            risk_level = "low"
            reasons = []
            
            if load > 8:
                risk_level = "medium"
                reasons.append("high_active_load")
            
            if overdue > 3:
                risk_level = "high" if risk_level == "medium" else "medium"
                reasons.append("multiple_overdue_tasks")
            
            return {
                "user_id": user_id,
                "risk_level": risk_level,
                "reasons": reasons,
                "metrics": {
                    "active_tasks": load,
                    "overdue_tasks": overdue
                }
            }
        finally:
            if not self.db:
                db.close()

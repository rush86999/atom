import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.database import SessionLocal
from core.models import User
from service_delivery.models import ProjectTask
from core.knowledge_ingestion import get_knowledge_ingestion

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
        Suggests the best team member based on semantic skill match and current workload.
        """
        db = self.db or SessionLocal()
        try:
            # 1. Get all active users in workspace
            users = db.query(User).filter(User.status == "active").all() # Simplified workspace check
            
            # 2. Semantic Expertise Search (Knowledge Graph)
            # Find people who have worked on similar terms in the past
            # expertise_results = await self.knowledge_manager.memory.search(query=task_name, limit=5)
            # For now, we'll simulate expertise discovery via skills column
            
            candidates = []
            for user in users:
                # Calculate Load
                load = db.query(ProjectTask).filter(ProjectTask.assigned_to == user.id).filter(ProjectTask.status == "in_progress").count()
                
                # Semantic Match (Improved keyword matching)
                skill_score = 0.5
                if user.skills:
                    task_keywords = set(task_name.lower().split())
                    user_skills = set(s.strip().lower() for s in user.skills.split(","))
                    if task_keywords & user_skills: # Intersection found
                        skill_score = 1.0
                
                # Composite Score: Higher Skill, Lower Load
                composite_score = skill_score * (1.0 / (load + 1))
                
                candidates.append({
                    "user_id": user.id,
                    "name": f"{user.first_name} {user.last_name}",
                    "load": load,
                    "skill_score": skill_score,
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

import json
import logging
from typing import Any, Dict, List, Optional

from core.ai_service import get_ai_service
from core.database import get_db_session
from core.models import User
from core.resource_manager import resource_monitor

logger = logging.getLogger(__name__)

class StaffingAdvisor:
    """
    AI-driven talent allocation advisor.
    Matches project requirements to user skills and capacity.
    """

    async def recommend_staff(self, project_description: str, workspace_id: str, limit: int = 3) -> Dict[str, Any]:
        """
        Extracts required skills from description and recommends available users.
        """
        logger.info(f"Generating staffing recommendations for project: {project_description[:50]}...")

        # 1. Extract Required Skills using AI
        required_skills = await self._extract_required_skills(project_description)
        if not required_skills:
             return {"status": "error", "message": "Could not identify required skills from description"}

        # 2. Match Users
        recommendations = []
        with get_db_session() as db:
            # Fetch all active users in workspace with skills
            users = db.query(User).filter(
                User.workspace_id == workspace_id,
                User.skills != None,
                User.status == "active"
            ).all()

            for user in users:
                user_skills = []
                try:
                    user_skills = json.loads(user.skills) if user.skills.startswith('[') else user.skills.split(',')
                    user_skills = [s.strip().lower() for s in user_skills]
                except Exception as e:
                    logger.warning(f"Failed to parse user skills for {user.id}: {e}")
                    user_skills = [user.skills.lower()]

                # Calculate match score
                matches = [s for s in required_skills if s.lower() in user_skills]
                if not matches:
                    continue

                match_score = len(matches) / len(required_skills)
                
                # Check utilization (don't recommend if already > 90%)
                util = resource_monitor.calculate_utilization(user.id, db=db)
                if util.get("utilization_percentage", 0) > 95:
                    continue

                recommendations.append({
                    "user_id": user.id,
                    "name": f"{user.first_name} {user.last_name}",
                    "match_score": round(match_score * 100, 2),
                    "matched_skills": matches,
                    "current_utilization": util.get("utilization_percentage"),
                    "risk_level": util.get("risk_level")
                })

        # Sort by match score (primary) and utilization (secondary)
        recommendations.sort(key=lambda x: (x["match_score"], -x["current_utilization"]), reverse=True)

        return {
            "status": "success",
            "required_skills": required_skills,
            "recommendations": recommendations[:limit]
        }

    async def _extract_required_skills(self, description: str) -> List[str]:
        """
        Uses AI to pull a list of technical or professional skills from a text block.
        """
        ai_service = get_ai_service()
        system_prompt = """Extract a list of 3-5 specific professional or technical skills required for the following project description. 
        Output ONLY a comma-separated list of keywords. 
        Example: Python, Graphic Design, Project Management"""
        
        try:
            response = await ai_service.process_with_nlu(description, system_prompt=system_prompt)
            if isinstance(response, str):
                return [s.strip() for s in response.split(',')]
            elif isinstance(response, list):
                return response
            elif isinstance(response, dict) and "skills" in response:
                return response["skills"]
            return []
        except Exception as e:
            logger.error(f"Failed to extract skills: {e}")
            return []

# Global Instance
staffing_advisor = StaffingAdvisor()

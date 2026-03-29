import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from core.models import AgentRegistry, AgentEpisode, AgentStatus
from core.reflection_service import ReflectionService

logger = logging.getLogger(__name__)

class GraduationService:
    def __init__(self, db: Session):
        self.db = db

    async def check_skill_promotion(
        self, 
        agent_id: str, 
        skill_id: str, 
        complexity: str = "moderate"
    ) -> Dict[str, Any]:
        """
        Check if a specific skill for an agent should be promoted to 'Autonomous'
        based on the Dynamic Threshold Rule.
        """
        # 1. Determine Threshold based on complexity
        thresholds = {
            "simple": 3,
            "moderate": 5,
            "complex": 8,
            "advanced": 8
        }
        required_successes = thresholds.get(complexity.lower(), 5)

        # 2. Query recent episodes for this agent and skill
        # We need to filter by episodes where this skill was used.
        # This assumes metadata_json contains the used skill_id.
        episodes = self.db.query(AgentEpisode).filter(
            and_(
                AgentEpisode.agent_id == agent_id,
                # Filtering by skill_id in JSONB/JSON column
                # This depends on how the skill_id is stored in metadata_json
                AgentEpisode.metadata_json.contains({"skill_id": skill_id})
            )
        ).order_by(desc(AgentEpisode.started_at)).limit(required_successes).all()

        if len(episodes) < required_successes:
            return {
                "promoted": False,
                "reason": f"Insufficient episodes ({len(episodes)}/{required_successes})",
                "current_streak": 0
            }

        # 3. Validate "Clean Run" for the streak
        streak = 0
        for ep in episodes:
            # Definition of a Clean Run:
            # - success = True
            # - human_intervention_count = 0
            # - constitutional_score >= 0.95
            is_clean = (
                ep.success and 
                (ep.human_intervention_count or 0) == 0 and 
                (ep.constitutional_score or 0.0) >= 0.95
            )
            
            if is_clean:
                streak += 1
            else:
                break # Streak broken

        if streak >= required_successes:
            # 4. Promote! Promote means "freezing" the successful path.
            # For now, we update the agent's configuration or a dedicated skill mapping.
            await self._promote_skill_path(agent_id, skill_id, episodes[0])
            return {
                "promoted": True,
                "reason": f"Completed {streak} consecutive clean runs.",
                "streak": streak
            }

        return {
            "promoted": False,
            "reason": f"Streak broken or incomplete ({streak}/{required_successes})",
            "current_streak": streak
        }

    async def _promote_skill_path(self, agent_id: str, skill_id: str, latest_episode: AgentEpisode):
        """
        Freeze the optimized execution path for the skill.
        """
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            return

        # Update Agent configuration to "lock" this skill path
        config = dict(agent.configuration or {})
        promoted_skills = config.get("promoted_skills", {})
        
        # Lock the successful prompt additives or tool sequence
        # In a real scenario, we'd extract the "learned prompt" from the trace
        promoted_skills[skill_id] = {
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "last_successful_episode": str(latest_episode.id),
            "status": "autonomous"
        }
        
        config["promoted_skills"] = promoted_skills
        agent.configuration = config
        
        self.db.commit()
        logger.info(f"Skill {skill_id} promoted to AUTONOMOUS for agent {agent_id}")

"""
Skill Executor Service - Bridge for Skill Composition execution.
Ported from atom-upstream patterns.
"""

import logging
from typing import Dict, Any, Optional
from core.database import get_db
from core.sandbox_execution_service import SandboxExecutionService

logger = logging.getLogger(__name__)

class SkillExecutorService:
    """
    Bridge service for executing skills within compositions.
    Handles mapping from SkillComposition requirements to internal execution backends.
    """

    def __init__(self, db=None):
        self.db = db or next(get_db())

    async def executeSkill(
        self,
        skill: Any,
        input_params: Dict[str, Any],
        agent_id: str,
        tenant_id: str,
        workspace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a skill and return results in the format expected by SkillCompositionService.
        """
        sandbox = SandboxExecutionService(self.db)
        
        try:
            result = await sandbox.execute_skill(
                skill_id=skill.id,
                agent_id=agent_id,
                tenant_id=tenant_id,
                input_params=input_params,
                workspace_id=workspace_id
            )
            
            # Map status "success" -> "completed" for compatibility with Composition service
            status = "completed" if result.get("status") == "success" else "failed"
            
            return {
                "status": status,
                "result": result.get("output"),
                "durationMs": int(result.get("execution_seconds", 0) * 1000),
                "formatted_output": result.get("formatted_output")
            }
        except Exception as e:
            logger.error(f"Skill execution failed in bridge: {e}")
            return {
                "status": "failed",
                "result": {"error": str(e)},
                "durationMs": 0
            }

import logging
import json
from typing import Dict, Any, List, Optional
from core.lifecycle_comm_generator import LifecycleCommGenerator
from core.database import get_db_session
from service_delivery.models import Project, Contract
from core.byok_endpoints import get_byok_manager

logger = logging.getLogger(__name__)

class ChangeOrderAgent:
    """
    Drafts and manages change orders for projects exceeding budget or scope.
    """

    def __init__(self, ai_service: Any = None):
        self.ai_service = ai_service
        self.comm_gen = LifecycleCommGenerator(ai_service=ai_service)

    async def draft_change_order(self, project_id: str, reason: str, workspace_id: str) -> Dict[str, Any]:
        """
        Creates a draft change order and notification email.
        """
        with get_db_session() as db:
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {"error": "Project not found"}
            
            # 1. Generate Change Order Content
            prompt = f"""
            Generate a formal Change Order for the project: {project.name}.
            Reason for Change: {reason}
            Current Actual Burn: ${project.actual_burn:,.2f}
            Original Budget: ${project.budget_amount:,.2f}
            
            Provide:
            1. A brief explanation of why this change is necessary (scope creep or budget overrun).
            2. Proposed budget adjustment (suggest a 15% buffer).
            3. Formal legalistic but friendly tone for a small business.
            """
            
            content = "Formal Change Order Draft Content" # Default
            if self.ai_service and hasattr(self.ai_service, 'analyze_text'):
                res = await self.ai_service.analyze_text(prompt)
                content = res.get("response", content)
            
            # 2. Draft Notification Email via CommGen
            email_context = {
                "project_name": project.name,
                "reason": reason,
                "burn": project.actual_burn,
                "change_order_preview": content[:200] + "..."
            }
            email_draft = await self.comm_gen.generate_draft("change_order_notification", email_context, workspace_id=workspace_id)
            
            return {
                "project_id": project_id,
                "change_order_content": content,
                "notification_email": email_draft,
                "suggested_status": "PAUSED_CLIENT" # Recommend pausing until signed
            }
        finally:
            db.close()
            
    async def analyze_and_trigger(self, project_id: str, workspace_id: str):
        """
        Analyzes project state and triggers change order if critical.
        """
        with get_db_session() as db:
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project and project.budget_status == "over_budget":
                logger.warning(f"Project {project_id} is over budget. Triggering change order draft.")
                return await self.draft_change_order(project_id, "Budget threshold exceeded (100% burn reached)", workspace_id)
        finally:
            db.close()
        return None

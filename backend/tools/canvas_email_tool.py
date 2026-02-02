"""Email Canvas Tool"""
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


async def present_email_canvas(
    user_id: str,
    subject: str,
    recipients: List[str],
    agent_id: Optional[str] = None,
    template: Optional[str] = None,
    layout: str = "conversation"
) -> Dict[str, Any]:
    """
    Present an email canvas.

    Creates a compose interface for email creation.
    """
    from core.database import SessionLocal
    from core.canvas_email_service import EmailCanvasService
    from tools.canvas_tool import present_specialized_canvas

    try:
        with SessionLocal() as db:
            service = EmailCanvasService(db)

            result = service.create_email_canvas(
                user_id=user_id,
                subject=subject,
                recipients=recipients,
                agent_id=agent_id,
                layout=layout,
                template=template
            )

            if not result.get("success"):
                return result

            canvas_id = result["canvas_id"]

            present_result = await present_specialized_canvas(
                user_id=user_id,
                canvas_type="email",
                component_type="compose_form",
                data={
                    "subject": subject,
                    "recipients": recipients,
                    "template": template
                },
                title=subject,
                agent_id=agent_id,
                layout=layout
            )

            if not present_result.get("success"):
                return present_result

            return {
                "success": True,
                "canvas_id": canvas_id,
                "subject": subject,
                "message": f"Presented email canvas: {subject}"
            }

    except Exception as e:
        logger.error(f"Failed to present email canvas: {e}")
        return {"success": False, "error": str(e)}

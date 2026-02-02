"""Orchestration Canvas Tool"""
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


async def present_orchestration_canvas(
    user_id: str,
    title: str,
    agent_id: Optional[str] = None,
    layout: str = "board",
    tasks: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Present an orchestration canvas.

    Creates a multi-app workflow orchestration deck.
    """
    from core.database import SessionLocal
    from core.canvas_orchestration_service import OrchestrationCanvasService
    from tools.canvas_tool import present_specialized_canvas

    try:
        with SessionLocal() as db:
            service = OrchestrationCanvasService(db)

            result = service.create_orchestration_canvas(
                user_id=user_id,
                title=title,
                agent_id=agent_id,
                layout=layout,
                tasks=tasks
            )

            if not result.get("success"):
                return result

            canvas_id = result["canvas_id"]

            present_result = await present_specialized_canvas(
                user_id=user_id,
                canvas_type="orchestration",
                component_type="kanban_board",
                data={
                    "title": title,
                    "tasks": result.get("tasks", []),
                    "nodes": [],
                    "connections": []
                },
                title=title,
                agent_id=agent_id,
                layout=layout
            )

            if not present_result.get("success"):
                return present_result

            return {
                "success": True,
                "canvas_id": canvas_id,
                "title": title,
                "message": f"Presented orchestration canvas: {title}"
            }

    except Exception as e:
        logger.error(f"Failed to present orchestration canvas: {e}")
        return {"success": False, "error": str(e)}

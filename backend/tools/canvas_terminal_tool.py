"""Terminal Canvas Tool"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def present_terminal_canvas(
    user_id: str,
    command: str,
    agent_id: Optional[str] = None,
    working_dir: str = "."
) -> Dict[str, Any]:
    """
    Present a terminal canvas.

    Creates a terminal interface for command execution.
    """
    from core.database import SessionLocal
    from core.canvas_terminal_service import TerminalCanvasService
    from tools.canvas_tool import present_specialized_canvas

    try:
        with SessionLocal() as db:
            service = TerminalCanvasService(db)

            result = service.create_terminal_canvas(
                user_id=user_id,
                command=command,
                agent_id=agent_id,
                working_dir=working_dir
            )

            if not result.get("success"):
                return result

            canvas_id = result["canvas_id"]

            present_result = await present_specialized_canvas(
                user_id=user_id,
                canvas_type="terminal",
                component_type="shell_output",
                data={
                    "command": command,
                    "working_dir": working_dir
                },
                title=f"Terminal: {working_dir}",
                agent_id=agent_id
            )

            if not present_result.get("success"):
                return present_result

            return {
                "success": True,
                "canvas_id": canvas_id,
                "command": command,
                "message": f"Presented terminal canvas"
            }

    except Exception as e:
        logger.error(f"Failed to present terminal canvas: {e}")
        return {"success": False, "error": str(e)}

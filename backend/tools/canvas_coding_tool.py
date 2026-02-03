"""Coding Canvas Tool"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def present_coding_canvas(
    user_id: str,
    repo: str,
    branch: str,
    agent_id: Optional[str] = None,
    layout: str = "repo_view"
) -> Dict[str, Any]:
    """
    Present a coding canvas.

    Creates a code development workspace.
    """
    from core.canvas_coding_service import CodingCanvasService
    from core.database import get_db_session
    from tools.canvas_tool import present_specialized_canvas

    try:
        with get_db_session() as db:
            service = CodingCanvasService(db)

            result = service.create_coding_canvas(
                user_id=user_id,
                repo=repo,
                branch=branch,
                agent_id=agent_id,
                layout=layout
            )

            if not result.get("success"):
                return result

            canvas_id = result["canvas_id"]

            present_result = await present_specialized_canvas(
                user_id=user_id,
                canvas_type="coding",
                component_type="repo_browser",
                data={
                    "repo": repo,
                    "branch": branch
                },
                title=f"{repo} ({branch})",
                agent_id=agent_id,
                layout=layout
            )

            if not present_result.get("success"):
                return present_result

            return {
                "success": True,
                "canvas_id": canvas_id,
                "repo": repo,
                "branch": branch,
                "message": f"Presented coding canvas: {repo}"
            }

    except Exception as e:
        logger.error(f"Failed to present coding canvas: {e}")
        return {"success": False, "error": str(e)}

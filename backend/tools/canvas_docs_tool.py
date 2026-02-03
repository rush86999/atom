"""
Documentation Canvas Tool

Agent tool for creating and managing documentation canvases.
"""
import logging
from typing import Dict, Any, Optional

from core.canvas_docs_service import DocumentationCanvasService
from tools.canvas_tool import present_specialized_canvas

logger = logging.getLogger(__name__)


async def present_docs_canvas(
    user_id: str,
    title: str,
    content: str,
    agent_id: Optional[str] = None,
    layout: str = "document",
    enable_comments: bool = True,
    enable_versioning: bool = True
) -> Dict[str, Any]:
    """
    Present a documentation canvas to the user.

    Creates a rich text document with optional versioning and commenting.

    Args:
        user_id: User ID to present to
        title: Document title
        content: Markdown content
        agent_id: Optional agent ID
        layout: Layout (document, split_view, focus)
        enable_comments: Enable commenting feature
        enable_versioning: Enable version history

    Returns:
        Dict with success status and canvas details

    Example:
        result = await present_docs_canvas(
            user_id="user-1",
            title="API Documentation",
            content="# API Reference\\n\\nEndpoints...",
            agent_id="agent-1",
            layout="document",
            enable_comments=True
        )
    """
    from core.database import get_db_session

    try:
        with get_db_session() as db:
            service = DocumentationCanvasService(db)

            # Create document canvas
            result = service.create_document_canvas(
                user_id=user_id,
                title=title,
                content=content,
                agent_id=agent_id,
                layout=layout,
                enable_comments=enable_comments,
                enable_versioning=enable_versioning
            )

            if not result.get("success"):
                logger.error(f"Failed to create document canvas: {result.get('error')}")
                return result

            canvas_id = result["canvas_id"]

            # Present the canvas
            present_result = await present_specialized_canvas(
                user_id=user_id,
                canvas_type="docs",
                component_type="rich_editor",
                data={
                    "title": title,
                    "content": content,
                    "enable_comments": enable_comments,
                    "enable_versioning": enable_versioning,
                    "versions": result.get("versions", []),
                    "comments": []
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
                "layout": layout,
                "message": f"Presented documentation canvas: {title}"
            }

    except Exception as e:
        logger.error(f"Failed to present docs canvas: {e}")
        return {"success": False, "error": str(e)}


async def update_docs_canvas(
    user_id: str,
    canvas_id: str,
    content: str,
    changes: str = "",
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update a documentation canvas.

    Args:
        user_id: User ID making the update
        canvas_id: Canvas ID
        content: New content
        changes: Description of changes
        agent_id: Optional agent ID

    Returns:
        Dict with success status
    """
    from core.database import get_db_session

    try:
        with get_db_session() as db:
            service = DocumentationCanvasService(db)

            result = service.update_document_content(
                canvas_id=canvas_id,
                user_id=user_id,
                content=content,
                changes=changes,
                create_version=True
            )

            if not result.get("success"):
                return result

            return {
                "success": True,
                "canvas_id": canvas_id,
                "message": "Document updated successfully"
            }

    except Exception as e:
        logger.error(f"Failed to update docs canvas: {e}")
        return {"success": False, "error": str(e)}

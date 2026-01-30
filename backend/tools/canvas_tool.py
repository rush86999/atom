"""
Canvas Tool Backend Helper

Provides helper functions for agents to present charts and visualizations
to users via the Canvas system.
"""

import logging
from typing import List, Dict, Any, Optional
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)


async def present_chart(
    user_id: str,
    chart_type: str,
    data: List[Dict[str, Any]],
    title: str = None,
    **kwargs
):
    """
    Send a chart to the frontend canvas.

    Args:
        user_id: User ID to send the chart to
        chart_type: 'line_chart', 'bar_chart', or 'pie_chart'
        data: List of dicts with chart data
        title: Chart title
        **kwargs: Additional chart options (color, etc.)
    """
    try:
        user_channel = f"user:{user_id}"

        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": f"{chart_type}",
                    "data": {"data": data, "title": title, **kwargs}
                }
            }
        )

        logger.info(f"Presented {chart_type} to user {user_id}")
        return {"success": True, "chart_type": chart_type}

    except Exception as e:
        logger.error(f"Failed to present chart: {e}")
        return {"success": False, "error": str(e)}


async def present_status_panel(
    user_id: str,
    items: List[Dict[str, Any]],
    title: str = None
):
    """
    Send a status panel to the frontend canvas.

    Args:
        user_id: User ID to send the panel to
        items: List of status items with 'label', 'value', and optional 'trend'
        title: Panel title
    """
    try:
        user_channel = f"user:{user_id}"

        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": "status_panel",
                    "data": {"items": items, "title": title}
                }
            }
        )

        logger.info(f"Presented status panel to user {user_id}")
        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to present status panel: {e}")
        return {"success": False, "error": str(e)}


async def present_markdown(
    user_id: str,
    content: str,
    title: str = None
):
    """
    Send markdown content to the frontend canvas.

    Args:
        user_id: User ID to send the content to
        content: Markdown formatted content
        title: Content title
    """
    try:
        user_channel = f"user:{user_id}"

        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": "markdown",
                    "data": {"content": content, "title": title}
                }
            }
        )

        logger.info(f"Presented markdown content to user {user_id}")
        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to present markdown: {e}")
        return {"success": False, "error": str(e)}


async def close_canvas(user_id: str):
    """
    Close the canvas for a user.

    Args:
        user_id: User ID to close the canvas for
    """
    try:
        user_channel = f"user:{user_id}"

        await ws_manager.broadcast(
            user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "close"
                }
            }
        )

        logger.info(f"Closed canvas for user {user_id}")
        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to close canvas: {e}")
        return {"success": False, "error": str(e)}

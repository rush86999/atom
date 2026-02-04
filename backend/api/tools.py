"""
Tool Discovery API

Provides REST endpoints for discovering and querying available tools.
Integrates with the ToolRegistry for comprehensive tool metadata.

Endpoints:
- GET /api/tools - List all tools
- GET /api/tools/{name} - Get tool details
- GET /api/tools/category/{category} - List tools by category
- GET /api/tools/search?query= - Search tools
- GET /api/tools/stats - Get registry statistics
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from tools.registry import ToolRegistry, get_tool_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools(
    category: Optional[str] = None,
    maturity: Optional[str] = None,
    registry: ToolRegistry = Depends(get_tool_registry)
):
    """
    List all registered tools.

    Query Parameters:
    - category: Filter by category (canvas, browser, device)
    - maturity: Filter by agent maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)

    Returns:
        List of tool metadata dictionaries
    """
    try:
        if category:
            tool_names = registry.list_by_category(category)
        elif maturity:
            tool_names = registry.list_by_maturity(maturity)
        else:
            tool_names = registry.list_all()

        tools = []
        for name in tool_names:
            metadata = registry.get(name)
            if metadata:
                tools.append(metadata.to_dict())

        return {
            "success": True,
            "count": len(tools),
            "tools": tools
        }

    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}")
async def get_tool(
    name: str,
    registry: ToolRegistry = Depends(get_tool_registry)
):
    """
    Get detailed metadata for a specific tool.

    Path Parameters:
    - name: Tool name (e.g., present_chart, browser_navigate)

    Returns:
        Tool metadata dictionary
    """
    try:
        metadata = registry.get(name)

        if not metadata:
            raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")

        return {
            "success": True,
            "tool": metadata.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category/{category}")
async def list_tools_by_category(
    category: str,
    registry: ToolRegistry = Depends(get_tool_registry)
):
    """
    List tools by category.

    Path Parameters:
    - category: Tool category (canvas, browser, device, general)

    Returns:
        List of tool metadata dictionaries in category
    """
    try:
        tool_names = registry.list_by_category(category)

        if not tool_names:
            return {
                "success": True,
                "count": 0,
                "category": category,
                "tools": []
            }

        tools = []
        for name in tool_names:
            metadata = registry.get(name)
            if metadata:
                tools.append(metadata.to_dict())

        return {
            "success": True,
            "count": len(tools),
            "category": category,
            "tools": tools
        }

    except Exception as e:
        logger.error(f"Error listing tools by category {category}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_tools(
    query: str = Query(..., description="Search query for tools"),
    registry: ToolRegistry = Depends(get_tool_registry)
):
    """
    Search tools by name, description, or tags.

    Query Parameters:
    - query: Search query string

    Returns:
        List of matching tool metadata dictionaries
    """
    try:
        if not query or len(query.strip()) < 2:
            raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

        results = registry.search(query)

        tools = [metadata.to_dict() for metadata in results]

        return {
            "success": True,
            "count": len(tools),
            "query": query,
            "tools": tools
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_tool_stats(
    registry: ToolRegistry = Depends(get_tool_registry)
):
    """
    Get tool registry statistics.

    Returns:
        Registry statistics including total tools, category distribution,
        complexity distribution, and maturity distribution
    """
    try:
        stats = registry.get_stats()

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Error getting tool stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def list_categories(
    registry: ToolRegistry = Depends(get_tool_registry)
):
    """
    List all tool categories.

    Returns:
        List of category names with tool counts
    """
    try:
        stats = registry.get_stats()

        categories = [
            {
                "name": category,
                "count": count
            }
            for category, count in stats["categories"].items()
        ]

        # Sort by count descending
        categories.sort(key=lambda x: x["count"], reverse=True)

        return {
            "success": True,
            "count": len(categories),
            "categories": categories
        }

    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

"""
Canvas State API Routes

Provides real-time access to canvas component state for AI agents.
Enables agents to read canvas content without OCR.
"""

import logging
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from core.database import get_db
from core.agent_governance_service import AgentGovernanceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/canvas", tags=["canvas-state"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CanvasStateRequest(BaseModel):
    canvas_id: str
    agent_id: str


class CanvasStateResponse(BaseModel):
    canvas_id: str
    canvas_type: str
    state: Dict[str, Any]
    timestamp: str


# ============================================================================
# HTTP Endpoints
# ============================================================================

@router.get("/state/{canvas_id}")
async def get_canvas_state(
    canvas_id: str,
    agent_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get current state of a canvas component.

    Args:
        canvas_id: Canvas component ID
        agent_id: Agent requesting state (for governance check)

    Returns:
        Canvas state dict with component-specific data
    """
    # Governance check (read_canvas = Level 1, STUDENT+)
    governance = AgentGovernanceService(db)
    check = governance.can_perform_action(
        agent_id=agent_id,
        action_type="read_canvas"
    )

    if not check.get("allowed", True):
        return {
            "success": False,
            "error": check.get("reason", "Governance check failed"),
            "governance_check": check
        }

    # In a real implementation, this would query the frontend's canvas state
    # For now, return a placeholder that documents the expected schema
    # The actual state comes from the frontend via WebSocket

    return {
        "success": True,
        "message": "Canvas state available via WebSocket connection",
        "canvas_id": canvas_id,
        "websocket_url": f"/api/canvas/ws/{canvas_id}",
        "governance_check": check
    }


@router.get("/types")
async def list_canvas_types(
    agent_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List all available canvas types and their state schemas.

    Returns:
        Dict mapping canvas types to their state schemas
    """
    # Governance check
    governance = AgentGovernanceService(db)
    check = governance.can_perform_action(
        agent_id=agent_id,
        action_type="read_canvas"
    )

    if not check.get("allowed", True):
        return {
            "success": False,
            "error": check.get("reason"),
            "governance_check": check
        }

    # Canvas type schemas
    canvas_types = {
        "generic": {
            "description": "Generic canvas with custom components",
            "components": ["line_chart", "bar_chart", "pie_chart", "markdown", "form", "status_panel"],
            "state_fields": ["component", "data", "title"],
            "examples": ["Data charts", "Status panels", "Markdown content"]
        },
        "docs": {
            "description": "Documentation canvas with markdown content",
            "components": ["document_viewer", "comment_panel", "version_history"],
            "state_fields": ["content", "comments", "versions"],
            "examples": ["Technical docs", "Policy documents", "Meeting notes"]
        },
        "email": {
            "description": "Email composer and viewer",
            "components": ["inbox", "conversation", "compose"],
            "state_fields": ["subject", "thread_id", "messages", "draft"],
            "examples": ["Email threads", "Draft compositions", "Attachments"]
        },
        "sheets": {
            "description": "Spreadsheet canvas with data grids",
            "components": ["sheet", "chart", "pivot_table"],
            "state_fields": ["cells", "formulas", "charts"],
            "examples": ["Data tables", "Pivot tables", "Charts"]
        },
        "orchestration": {
            "description": "Workflow orchestration canvas",
            "components": ["workflow_board", "timeline", "node_graph"],
            "state_fields": ["tasks", "nodes", "connections"],
            "examples": ["Workflow approvals", "Integration flows", "Task boards"]
        },
        "terminal": {
            "description": "Terminal/console output canvas",
            "components": ["terminal", "shell", "monitor"],
            "state_fields": ["lines", "cursor_pos", "working_dir", "command"],
            "examples": ["Command output", "Process logs", "File trees"]
        },
        "coding": {
            "description": "Code editor and diff viewer",
            "components": ["editor", "diff_view", "pr_review"],
            "state_fields": ["files", "diffs", "pull_requests"],
            "examples": ["Code editing", "PR reviews", "Diff viewing"]
        }
    }

    return {
        "success": True,
        "canvas_types": canvas_types,
        "governance_check": check
    }


# ============================================================================
# WebSocket Endpoint for Real-Time State
# ============================================================================

class CanvasStateConnectionManager:
    """Manages WebSocket connections for canvas state streaming"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, canvas_id: str, websocket: WebSocket):
        await websocket.accept()
        if canvas_id not in self.active_connections:
            self.active_connections[canvas_id] = []
        self.active_connections[canvas_id].append(websocket)

    def disconnect(self, canvas_id: str, websocket: WebSocket):
        if canvas_id in self.active_connections:
            self.active_connections[canvas_id].remove(websocket)
            if not self.active_connections[canvas_id]:
                del self.active_connections[canvas_id]

    async def broadcast_state(self, canvas_id: str, state: Dict[str, Any]):
        """Broadcast state update to all connections for a canvas"""
        if canvas_id in self.active_connections:
            for connection in self.active_connections[canvas_id]:
                try:
                    await connection.send_json({
                        "type": "canvas:state_change",
                        "canvas_id": canvas_id,
                        "state": state,
                        "timestamp": state.get("timestamp", "")
                    })
                except Exception as e:
                    logger.error(f"Error broadcasting state: {e}")


manager = CanvasStateConnectionManager()


@router.websocket("/ws/{canvas_id}")
async def canvas_state_websocket(
    canvas_id: str,
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time canvas state updates.

    Clients connect to receive state changes as they happen.
    The frontend broadcasts state updates via this connection.
    """
    await manager.connect(canvas_id, websocket)

    try:
        while True:
            # Receive state updates from frontend
            data = await websocket.receive_json()

            if data.get("type") == "canvas:state_update":
                # Broadcast to other connected clients
                await manager.broadcast_state(canvas_id, data.get("state", {}))

            elif data.get("type") == "canvas:subscribe":
                # Client wants to subscribe to state updates
                # Send current state if available
                await websocket.send_json({
                    "type": "canvas:subscribed",
                    "canvas_id": canvas_id,
                    "message": "Subscribed to canvas state updates"
                })

    except WebSocketDisconnect:
        manager.disconnect(canvas_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for canvas {canvas_id}: {e}")
        manager.disconnect(canvas_id, websocket)

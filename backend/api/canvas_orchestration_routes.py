"""Orchestration Canvas API Routes"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import logging

from core.database import get_db
from core.canvas_orchestration_service import OrchestrationCanvasService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/canvas/orchestration", tags=["canvas_orchestration"])


class CreateOrchestrationRequest(BaseModel):
    user_id: str
    title: str
    canvas_id: Optional[str] = None
    agent_id: Optional[str] = None
    layout: str = "board"
    tasks: Optional[List[Dict[str, Any]]] = None


class AddNodeRequest(BaseModel):
    user_id: str
    app_name: str
    node_type: str
    config: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, int]] = None


class ConnectNodesRequest(BaseModel):
    user_id: str
    from_node: str
    to_node: str
    condition: Optional[str] = None


class AddTaskRequest(BaseModel):
    user_id: str
    title: str
    status: str = "todo"
    assignee: Optional[str] = None
    integrations: Optional[List[str]] = None


@router.post("/create")
async def create_orchestration_canvas(request: CreateOrchestrationRequest, db: Session = Depends(get_db)):
    """Create a new orchestration canvas."""
    service = OrchestrationCanvasService(db)
    result = service.create_orchestration_canvas(
        user_id=request.user_id,
        title=request.title,
        canvas_id=request.canvas_id,
        agent_id=request.agent_id,
        layout=request.layout,
        tasks=request.tasks
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/{canvas_id}/node")
async def add_integration_node(canvas_id: str, request: AddNodeRequest, db: Session = Depends(get_db)):
    """Add an integration node to the workflow."""
    service = OrchestrationCanvasService(db)
    result = service.add_integration_node(
        canvas_id=canvas_id,
        user_id=request.user_id,
        app_name=request.app_name,
        node_type=request.node_type,
        config=request.config,
        position=request.position
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/{canvas_id}/connect")
async def connect_nodes(canvas_id: str, request: ConnectNodesRequest, db: Session = Depends(get_db)):
    """Connect two integration nodes."""
    service = OrchestrationCanvasService(db)
    result = service.connect_nodes(
        canvas_id=canvas_id,
        user_id=request.user_id,
        from_node=request.from_node,
        to_node=request.to_node,
        condition=request.condition
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/{canvas_id}/task")
async def add_task(canvas_id: str, request: AddTaskRequest, db: Session = Depends(get_db)):
    """Add a task to the workflow."""
    service = OrchestrationCanvasService(db)
    result = service.add_task(
        canvas_id=canvas_id,
        user_id=request.user_id,
        title=request.title,
        status=request.status,
        assignee=request.assignee,
        integrations=request.integrations
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/{canvas_id}")
async def get_orchestration_canvas(canvas_id: str, db: Session = Depends(get_db)):
    """Get an orchestration canvas."""
    from core.models import CanvasAudit
    from sqlalchemy import desc

    audit = db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.canvas_type == "orchestration"
    ).order_by(desc(CanvasAudit.created_at)).first()

    if not audit:
        raise HTTPException(status_code=404, detail="Orchestration canvas not found")

    return audit.audit_metadata

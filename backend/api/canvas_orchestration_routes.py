"""Orchestration Canvas API Routes"""
import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.canvas_orchestration_service import OrchestrationCanvasService
from core.database import get_db

logger = logging.getLogger(__name__)
router = BaseAPIRouter(prefix="/api/canvas/orchestration", tags=["canvas_orchestration"])


class TaskStatus(str, Enum):
    """Task status enum for orchestration workflows"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    TODO = "todo"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    status: TaskStatus = TaskStatus.TODO
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
        raise router.error_response(
            error_code="ORCHESTRATION_CANVAS_CREATE_FAILED",
            message=result.get("error", "Failed to create orchestration canvas"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message=f"Orchestration canvas '{request.title}' created successfully"
    )


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
        raise router.error_response(
            error_code="ADD_NODE_FAILED",
            message=result.get("error", "Failed to add integration node"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message=f"Integration node '{request.app_name}' added successfully"
    )


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
        raise router.error_response(
            error_code="CONNECT_NODES_FAILED",
            message=result.get("error", "Failed to connect nodes"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message=f"Nodes connected: {request.from_node} -> {request.to_node}"
    )


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
        raise router.error_response(
            error_code="ADD_TASK_FAILED",
            message=result.get("error", "Failed to add task"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message=f"Task '{request.title}' added successfully"
    )


@router.get("/{canvas_id}")
async def get_orchestration_canvas(canvas_id: str, db: Session = Depends(get_db)):
    """Get an orchestration canvas."""
    from sqlalchemy import desc

    from core.models import CanvasAudit

    audit = db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.canvas_type == "orchestration"
    ).order_by(desc(CanvasAudit.created_at)).first()

    if not audit:
        raise router.not_found_error(
            resource="OrchestrationCanvas",
            resource_id=canvas_id
        )

    return router.success_response(
        data=audit.audit_metadata,
        message="Orchestration canvas retrieved successfully"
    )

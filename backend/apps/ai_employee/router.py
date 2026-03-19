from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from .models import EmployeeWorkspace
from .executor import employee_executor
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/employee",
    tags=["AI Employee"],
    responses={404: {"description": "Not found"}},
)

@router.get("/status")
async def get_status():
    """
    Check if the AI Employee service is online.
    """
    return {"status": "online", "system": "AI Employee (Isolated)"}

from pydantic import BaseModel
from typing import Optional, Any, Dict

class TaskRequest(BaseModel):
    workspace_id: str
    command: str
    current_state: Dict[str, Any]

@router.post("/task")
async def execute_task(request: TaskRequest, db: Session = Depends(get_db)):
    """
    Execute a task for the AI Employee in a specific workspace.
    """
    workspace = db.query(EmployeeWorkspace).filter(EmployeeWorkspace.id == request.workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    # Run the task through the executor
    result = await employee_executor.run_task(request.command, request.current_state)
    
    # Update workspace state in DB
    workspace.workspace_state = result["new_state"]
    db.commit()
    
    return result

@router.post("/workspace/init")
async def init_workspace(user_id: str, db: Session = Depends(get_db)):
    """
    Initialize or retrieve a persistent workspace for the AI Employee.
    """
    # Check if workspace already exists
    workspace = db.query(EmployeeWorkspace).filter(EmployeeWorkspace.user_id == user_id).first()
    
    if not workspace:
        workspace = EmployeeWorkspace(
            id=str(uuid.uuid4()),
            user_id=user_id,
            workspace_state={
                "editorContent": "# Welcome to your AI Employee Workspace\n\nStart your task here.",
                "views": []
            }
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        logger.info(f"Initialized new workspace for user {user_id}")
    else:
        logger.info(f"Retrieved existing workspace for user {user_id}")
        
    return workspace

@router.post("/workspace/save")
async def save_workspace(workspace_id: str, state: dict, db: Session = Depends(get_db)):
    """
    Save the current workspace state.
    """
    workspace = db.query(EmployeeWorkspace).filter(EmployeeWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    workspace.workspace_state = state
    db.commit()
    return {"status": "saved"}

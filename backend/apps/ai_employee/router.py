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
    workspace = db.query(EmployeeWorkspace).filter(EmployeeWorkspace.id == request.workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Run the dynamic executor
    result = await employee_executor.run_task(request.command, request.current_state)
    
    # Persist the full state back to the DB
    workspace.workspace_state = result["new_state"]
    # Also update the explicitly tracked deliverables list
    workspace.deliverables = result["new_state"].get("deliverables", [])
    
    db.commit()
    return result

@router.post("/workspace/init")
async def init_workspace(user_id: str, db: Session = Depends(get_db)):
    workspace = db.query(EmployeeWorkspace).filter(EmployeeWorkspace.user_id == user_id).first()
    
    if not workspace:
        workspace = EmployeeWorkspace(
            id=str(uuid.uuid4()),
            user_id=user_id,
            workspace_state={
                "editorContent": "# Welcome to your AI Employee Workspace\n\nStart your task here.",
                "plan": [],
                "deliverables": [],
                "views": []
            },
            deliverables=[]
        )
        db.add(workspace)
        db.commit()
        
    return {
        "id": workspace.id,
        "workspace_state": workspace.workspace_state,
        "deliverables": workspace.deliverables
    }

@router.post("/workspace/reset")
async def reset_workspace(workspace_id: str, db: Session = Depends(get_db)):
    workspace = db.query(EmployeeWorkspace).filter(EmployeeWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    new_state = employee_executor.reset_state()
    workspace.workspace_state = new_state
    workspace.deliverables = []
    db.commit()
    return {"status": "success", "new_state": new_state}

@router.post("/workspace/save")
async def save_workspace(workspace_id: str, state: Dict[str, Any], db: Session = Depends(get_db)):
    workspace = db.query(EmployeeWorkspace).filter(EmployeeWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    workspace.workspace_state = state
    db.commit()
    return {"status": "success"}

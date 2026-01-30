from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from core.database import get_db
from service_delivery.models import Project, Milestone, ProjectTask
from core.pm_engine import pm_engine
from core.pm_orchestrator import pm_orchestrator
from pydantic import BaseModel

router = APIRouter(prefix="/pm", tags=["Project Management"])

class ProjectLaunchRequest(BaseModel):
    prompt: str
    contract_id: Optional[str] = None
    user_id: str

@router.post("/launch")
async def launch_project(request: ProjectLaunchRequest):
    """
    Launch a new project from a natural language requirement.
    """
    result = await pm_engine.generate_project_from_nl(
        prompt=request.prompt,
        user_id=request.user_id,
        workspace_id="default",
        contract_id=request.contract_id
    )
    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@router.post("/projects/{project_id}/sync")
async def sync_project_status(project_id: str, user_id: str, db: Session = Depends(get_db)):
    """
    Trigger an AI-driven status inference for a project.
    """
    result = await pm_engine.infer_project_status(project_id, user_id)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result

@router.get("/projects/{project_id}/risks")
async def get_project_risks(project_id: str, user_id: str, db: Session = Depends(get_db)):
    """
    Get AI-detected risks for a project.
    """
    result = await pm_engine.analyze_project_risks(project_id, user_id)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result

@router.get("/projects/{project_id}/details")
async def get_project_details(project_id: str, db: Session = Depends(get_db)):
    """
    Get full project details including milestones and tasks.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    milestones = db.query(Milestone).filter(Milestone.project_id == project_id).all()
    
    milestone_list = []
    for ms in milestones:
        tasks = db.query(ProjectTask).filter(ProjectTask.milestone_id == ms.id).all()
        milestone_list.append({
            "id": ms.id,
            "name": ms.name,
            "status": ms.status,
            "due_date": ms.due_date,
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "status": t.status,
                    "due_date": t.due_date
                } for t in tasks
            ]
        })
    
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "risk_level": project.risk_level,
        "budget_amount": project.budget_amount,
        "milestones": milestone_list
    }

@router.post("/provision/{deal_id}")
async def provision_project(deal_id: str, external_platform: Optional[str] = None, user_id: str = "default"):
    """
    Manually trigger project provisioning from a deal and optionally sync to external PM tool.
    """
    result = await pm_orchestrator.provision_from_deal(deal_id, user_id, "default", external_platform)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result

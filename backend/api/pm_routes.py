from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from service_delivery.models import Milestone, Project, ProjectTask
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.pm_engine import pm_engine
from core.pm_orchestrator import pm_orchestrator

router = BaseAPIRouter(prefix="/pm", tags=["Project Management"])

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
        raise router.internal_error(
            message="Failed to launch project",
            details={"error": result.get("error", "Unknown error")}
        )
    return router.success_response(
        data=result,
        message="Project launched successfully"
    )

@router.post("/projects/{project_id}/sync")
async def sync_project_status(project_id: str, user_id: str, db: Session = Depends(get_db)):
    """
    Trigger an AI-driven status inference for a project.
    """
    result = await pm_engine.infer_project_status(project_id, user_id)
    if result["status"] == "error":
        raise router.not_found_error(
            resource="Project",
            resource_id=project_id,
            details={"message": result.get("message", "Project not found")}
        )
    return router.success_response(
        data=result,
        message="Project status synced successfully"
    )

@router.get("/projects/{project_id}/risks")
async def get_project_risks(project_id: str, user_id: str, db: Session = Depends(get_db)):
    """
    Get AI-detected risks for a project.
    """
    result = await pm_engine.analyze_project_risks(project_id, user_id)
    if result["status"] == "error":
        raise router.not_found_error(
            resource="Project",
            resource_id=project_id,
            details={"message": result.get("message", "Project not found")}
        )
    return router.success_response(
        data=result,
        message="Project risks retrieved successfully"
    )

@router.get("/projects/{project_id}/details")
async def get_project_details(project_id: str, db: Session = Depends(get_db)):
    """
    Get full project details including milestones and tasks.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise router.not_found_error("Project", project_id)

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

    return router.success_response(
        data={
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "risk_level": project.risk_level,
            "budget_amount": project.budget_amount,
            "milestones": milestone_list
        },
        message="Project details retrieved successfully"
    )

@router.post("/provision/{deal_id}")
async def provision_project(deal_id: str, external_platform: Optional[str] = None, user_id: str = "default"):
    """
    Manually trigger project provisioning from a deal and optionally sync to external PM tool.
    """
    result = await pm_orchestrator.provision_from_deal(deal_id, user_id, "default", external_platform)
    if result["status"] == "error":
        raise router.error_response(
            error_code="PROVISION_FAILED",
            message=result.get("message", "Failed to provision project"),
            status_code=400
        )
    return router.success_response(
        data=result,
        message="Project provisioned successfully"
    )

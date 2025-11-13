
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

router = APIRouter()

# Sample workflow templates
WORKFLOW_TEMPLATES = [
    {
        "id": "daily_standup",
        "name": "Daily Standup Automation",
        "description": "Automate daily standup preparation and reporting",
        "services": ["slack", "google_calendar", "asana"],
        "trigger": "scheduled:09:00"
    },
    {
        "id": "meeting_followup",
        "name": "Meeting Follow-up",
        "description": "Automate meeting follow-up tasks",
        "services": ["google_calendar", "gmail", "asana"],
        "trigger": "calendar_event_ended"
    },
    {
        "id": "code_review",
        "name": "Code Review Automation",
        "description": "Automate code review process",
        "services": ["github", "slack"],
        "trigger": "github:pull_request_opened"
    }
]

@router.get("/api/workflows/templates")
async def get_workflow_templates():
    """Get available workflow templates"""
    return {
        "templates": WORKFLOW_TEMPLATES,
        "total_templates": len(WORKFLOW_TEMPLATES)
    }

@router.get("/api/workflows/templates/{template_id}")
async def get_workflow_template(template_id: str):
    """Get specific workflow template"""
    template = next((t for t in WORKFLOW_TEMPLATES if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.post("/api/workflows/execute")
async def execute_workflow(workflow_data: Dict[Any, Any]):
    """Execute a workflow"""
    return {
        "success": True,
        "execution_id": f"exec_{int(time.time())}",
        "status": "started",
        "message": "Workflow execution started"
    }

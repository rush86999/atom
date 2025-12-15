from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import random

# Import core workflow models if available, otherwise define local ones for UI
# For now, we'll define UI-specific models to match the frontend expectations

router = APIRouter(prefix="/api/workflows", tags=["workflow_ui"])

# --- Models matching Frontend Interfaces ---

class WorkflowStep(BaseModel):
    id: str
    type: str
    service: Optional[str] = None
    action: Optional[str] = None
    parameters: Dict[str, Any] = {}
    name: str

class WorkflowTemplate(BaseModel):
    id: str
    name: str
    description: str
    category: str
    icon: str
    steps: List[WorkflowStep]
    input_schema: Dict[str, Any]

class WorkflowDefinition(BaseModel):
    id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    input_schema: Dict[str, Any]
    created_at: str
    updated_at: str
    steps_count: int

class WorkflowExecution(BaseModel):
    execution_id: str
    workflow_id: str
    status: str  # "pending" | "running" | "completed" | "failed" | "cancelled"
    start_time: str
    end_time: Optional[str] = None
    current_step: int
    total_steps: int
    trigger_data: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    has_errors: bool = False

class ServiceInfo(BaseModel):
    name: str
    actions: List[str]
    description: str

# --- Mock Data for UI ---

MOCK_TEMPLATES = [
    WorkflowTemplate(
        id="tpl_marketing_campaign",
        name="Marketing Campaign",
        description="Generate and schedule a multi-channel marketing campaign",
        category="business",
        icon="campaign",
        steps=[
            WorkflowStep(id="s1", type="action", service="ai", action="generate_content", name="Generate Copy", parameters={"prompt": "Write a marketing post about {product}"}),
            WorkflowStep(id="s2", type="action", service="slack", action="send_message", name="Notify Team", parameters={"channel": "#marketing"}),
            WorkflowStep(id="s3", type="action", service="twitter", action="post_tweet", name="Post to Twitter", parameters={}),
        ],
        input_schema={
            "type": "object",
            "properties": {
                "product": {"type": "string", "title": "Product Name"},
                "target_audience": {"type": "string", "title": "Target Audience"}
            },
            "required": ["product"]
        }
    ),
    WorkflowTemplate(
        id="tpl_daily_standup",
        name="Daily Standup Summary",
        description="Collect updates and post summary to Slack",
        category="productivity",
        icon="group",
        steps=[
            WorkflowStep(id="s1", type="action", service="asana", action="get_tasks", name="Fetch Tasks", parameters={}),
            WorkflowStep(id="s2", type="action", service="ai", action="summarize", name="Summarize Updates", parameters={}),
            WorkflowStep(id="s3", type="action", service="slack", action="send_message", name="Post Summary", parameters={}),
        ],
        input_schema={
            "type": "object",
            "properties": {
                "team_channel": {"type": "string", "title": "Slack Channel"}
            },
            "required": ["team_channel"]
        }
    )
]

MOCK_WORKFLOWS = [
    WorkflowDefinition(
        id="wf_1",
        name="Weekly Report",
        description="Generate weekly progress report",
        steps=[],
        input_schema={},
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        steps_count=3
    )
]

MOCK_EXECUTIONS = [
    WorkflowExecution(
        execution_id="exec_1",
        workflow_id="wf_1",
        status="completed",
        start_time=datetime.now().isoformat(),
        end_time=datetime.now().isoformat(),
        current_step=3,
        total_steps=3,
        results={"summary": "All good"}
    )
]

MOCK_SERVICES = {
    "asana": ServiceInfo(name="Asana", actions=["get_tasks", "create_task"], description="Project management"),
    "slack": ServiceInfo(name="Slack", actions=["send_message", "create_channel"], description="Team communication"),
    "gmail": ServiceInfo(name="Gmail", actions=["send_email", "read_email"], description="Email service"),
    "ai": ServiceInfo(name="Atom AI", actions=["generate_content", "summarize", "analyze"], description="AI capabilities")
}

# --- Endpoints ---

@router.get("/templates")
async def get_templates():
    return {"success": True, "templates": [t.dict() for t in MOCK_TEMPLATES]}

@router.get("/definitions")
async def get_workflows():
    return {"success": True, "workflows": [w.dict() for w in MOCK_WORKFLOWS]}

@router.post("/definitions")
async def create_workflow_definition(payload: Dict[str, Any]):
    new_id = f"wf_{uuid.uuid4().hex[:8]}"
    # Simple conversion from builder data to backend model (mock)
    new_workflow = WorkflowDefinition(
        id=new_id,
        name=payload.get("name", "New Visual Workflow"),
        description=payload.get("description", "Created via Visual Builder"),
        steps=[], # In real app, we'd parse visual nodes to steps
        input_schema={},
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        steps_count=len(payload.get("definition", {}).get("nodes", []))
    )
    MOCK_WORKFLOWS.insert(0, new_workflow)
    return {"success": True, "workflow": new_workflow.dict()}

@router.get("/executions")
async def get_executions():
    return {"success": True, "executions": [e.dict() for e in MOCK_EXECUTIONS]}

@router.get("/services")
async def get_services():
    return {"success": True, "services": {k: v.dict() for k, v in MOCK_SERVICES.items()}}

@router.post("/execute")
async def execute_workflow(payload: Dict[str, Any]):
    # Mock execution start
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    new_execution = WorkflowExecution(
        execution_id=execution_id,
        workflow_id=payload.get("workflow_id", "unknown"),
        status="running",
        start_time=datetime.now().isoformat(),
        current_step=0,
        total_steps=3, # Mock
        trigger_data=payload.get("input")
    )
    MOCK_EXECUTIONS.insert(0, new_execution)
    return {"success": True, "execution_id": execution_id, "status": "running"}

@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    for exc in MOCK_EXECUTIONS:
        if exc.execution_id == execution_id:
            exc.status = "cancelled"
            return {"success": True}
    raise HTTPException(status_code=404, detail="Execution not found")

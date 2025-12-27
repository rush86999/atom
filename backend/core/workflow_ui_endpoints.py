from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import random

# Import core workflow models if available, otherwise define local ones for UI
# For now, we'll define UI-specific models to match the frontend expectations

router = APIRouter(tags=["workflow_ui"])

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
    ),
    WorkflowTemplate(
        id="tpl_o365_finance",
        name="O365 Financial Reporting",
        description=" OneDrive ingestion -> Excel processing -> Power BI refresh -> Teams notification",
        category="business",
        icon="finance",
        steps=[
            WorkflowStep(id="s1", type="action", service="onedrive", action="get_file", name="Get Statement", parameters={"file_path": "/Finances/Monthly.xlsx"}),
            WorkflowStep(id="s2", type="action", service="excel", action="update_range", name="Process Data", parameters={"range": "A1:G100"}),
            WorkflowStep(id="s3", type="action", service="powerbi", action="refresh_dataset", name="Refresh Dashboard", parameters={"dataset_id": "sales_dashboard"}),
            WorkflowStep(id="s4", type="action", service="msteams", action="send_message", name="Notify Finance Team", parameters={"channel_id": "finance_channel"}),
        ],
        input_schema={
            "type": "object",
            "properties": {
                "month": {"type": "string", "title": "Reporting Month"},
                "dataset": {"type": "string", "title": "Power BI Dataset ID"}
            },
            "required": ["month"]
        }
    ),
    WorkflowTemplate(
        id="tpl_o365_project",
        name="Project Inception",
        description="Setup Project Tracker (Excel) and Tasks (Planner)",
        category="productivity",
        icon="assignment",
        steps=[
            WorkflowStep(id="s1", type="action", service="excel", action="create_workbook", name="Create Tracker", parameters={"name": "{project_name}_Tracker"}),
            WorkflowStep(id="s2", type="action", service="planner", action="create_task", name="Create Launch Task", parameters={"title": "Launch {project_name}"}),
            WorkflowStep(id="s3", type="action", service="msteams", action="send_message", name="Notify PMO", parameters={"message": "Project {project_name} initialized."}),
        ],
        input_schema={
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "title": "Project Name"},
                "pmo_channel": {"type": "string", "title": "PMO Channel ID"}
            },
            "required": ["project_name"]
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
    "ai": ServiceInfo(name="Atom AI", actions=["generate_content", "summarize", "analyze"], description="AI capabilities"),
    "onedrive": ServiceInfo(name="OneDrive", actions=["list_files", "get_content"], description="File storage"),
    "excel": ServiceInfo(name="Excel", actions=["update_range", "append_row"], description="Spreadsheet automation"),
    "powerbi": ServiceInfo(name="Power BI", actions=["refresh_dataset"], description="Business intelligence"),
    "teams": ServiceInfo(name="Microsoft Teams", actions=["send_message", "create_channel"], description="Team collaboration"),
    "outlook": ServiceInfo(name="Outlook", actions=["send_email", "create_event"], description="Email and calendar"),
    "planner": ServiceInfo(name="Planner", actions=["create_task"], description="Task management")
}

# --- Endpoints ---

@router.get("/templates")
async def get_templates():
    return {"success": True, "templates": [t.dict() for t in MOCK_TEMPLATES]}

@router.get("/services")
async def get_services():
    return {"success": True, "services": [s.dict() for s in MOCK_SERVICES.values()]}

@router.get("/definitions")
async def get_workflows():
    return {"success": True, "workflows": [w.dict() for w in MOCK_WORKFLOWS]}

# Alias for /workflows to match common API patterns
@router.get("/workflows")
async def list_workflows():
    """List all workflows (alias for /definitions)"""
    return {"success": True, "workflows": [w.dict() for w in MOCK_WORKFLOWS]}

@router.get("/workflows/{workflow_id}")
async def get_workflow_by_id(workflow_id: str):
    """Get a specific workflow by ID"""
    for w in MOCK_WORKFLOWS:
        if w.id == workflow_id:
            return {"success": True, "workflow": w.dict()}
    raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

@router.post("/workflows")
async def create_workflow(payload: Dict[str, Any]):
    """Create a new workflow"""
    new_id = f"wf_{uuid.uuid4().hex[:8]}"
    new_workflow = WorkflowDefinition(
        id=new_id,
        name=payload.get("name", "New Workflow"),
        description=payload.get("description", ""),
        steps=[],
        input_schema={},
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        steps_count=len(payload.get("steps", []))
    )
    MOCK_WORKFLOWS.insert(0, new_workflow)
    return {"success": True, "workflow": new_workflow.dict()}

@router.put("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, payload: Dict[str, Any]):
    """Update an existing workflow"""
    for i, w in enumerate(MOCK_WORKFLOWS):
        if w.id == workflow_id:
            MOCK_WORKFLOWS[i] = WorkflowDefinition(
                id=workflow_id,
                name=payload.get("name", w.name),
                description=payload.get("description", w.description),
                steps=w.steps,
                input_schema=w.input_schema,
                created_at=w.created_at,
                updated_at=datetime.now().isoformat(),
                steps_count=w.steps_count
            )
            return {"success": True, "workflow": MOCK_WORKFLOWS[i].dict()}
    raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow"""
    for i, w in enumerate(MOCK_WORKFLOWS):
        if w.id == workflow_id:
            del MOCK_WORKFLOWS[i]
            return {"success": True, "message": f"Workflow '{workflow_id}' deleted"}
    raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow_by_id(workflow_id: str, background_tasks: BackgroundTasks, payload: Dict[str, Any] = None):
    """Execute a workflow by ID"""
    from advanced_workflow_orchestrator import orchestrator
    
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    input_data = payload or {}
    input_data["_ui_workflow_id"] = workflow_id
    
    async def _run_orchestration():
        await orchestrator.execute_workflow(workflow_id, input_data, execution_id=execution_id)
    
    try:
        background_tasks.add_task(_run_orchestration)
    except:
        pass  # Orchestrator may not be available
    
    return {"success": True, "execution_id": execution_id, "workflow_id": workflow_id}

@router.get("/workflows/{workflow_id}/history")
async def get_workflow_history(workflow_id: str):
    """Get execution history for a workflow"""
    history = [e.dict() for e in MOCK_EXECUTIONS if e.workflow_id == workflow_id]
    return {"success": True, "workflow_id": workflow_id, "history": history}

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
    # Fetch real executions from the orchestrator
    try:
        from advanced_workflow_orchestrator import orchestrator, WorkflowStatus
        
        executions = []
        # Convert Orchestrator contexts to UI Execution models
        for context in orchestrator.active_contexts.values():
            status_map = {
                WorkflowStatus.PENDING: "pending",
                WorkflowStatus.RUNNING: "running",
                WorkflowStatus.COMPLETED: "completed",
                WorkflowStatus.FAILED: "failed",
                WorkflowStatus.CANCELLED: "cancelled"
            }
            
            # Calculate metrics
            total_steps = 4 # Default estimate
            current_step = 0
            if context.results:
                current_step = len(context.results)
            
            executions.append(WorkflowExecution(
                execution_id=context.execution_id,
                workflow_id=context.input_data.get("_ui_workflow_id", context.workflow_id), # Prefer UI ID if stored
                status=status_map.get(context.status, "unknown"),
                start_time=context.started_at.isoformat() if context.started_at else datetime.now().isoformat(),
                end_time=context.completed_at.isoformat() if context.completed_at else None,
                current_step=current_step,
                total_steps=total_steps,
                trigger_data=context.input_data,
                results=context.results,
                errors=[context.error_message] if context.error_message else []
            ))
            
        # Sort by start time (newest first)
        executions.sort(key=lambda x: x.start_time, reverse=True)
        return {"success": True, "executions": [e.dict() for e in executions]}
            
    except ImportError:
        # Fallback if orchestrator not available/path issue
        return {"success": True, "executions": [e.dict() for e in MOCK_EXECUTIONS]}

@router.post("/execute")
async def execute_workflow(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    from advanced_workflow_orchestrator import orchestrator
    
    workflow_id = payload.get("workflow_id")
    input_data = payload.get("input", {})
    
    # Store UI workflow ID in input for correlation
    input_data["_ui_workflow_id"] = workflow_id
    
    # Map UI Template IDs to Orchestrator Workflow IDs
    # This ensures we run the REAL predefined workflows
    orchestrator_id = workflow_id
    if workflow_id == "tpl_o365_finance":
        orchestrator_id = "financial_reporting_automation"
    elif workflow_id == "tpl_o365_project":
        orchestrator_id = "project_inception_workflow"
    
    # Check if workflow exists in orchestrator
    if orchestrator_id not in orchestrator.workflows:
        # Fallback logic could go here
        pass

    # Generate Execution ID for immediate UI feedback
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    
    async def _run_orchestration():
        await orchestrator.execute_workflow(orchestrator_id, input_data, execution_id=execution_id)
        
    background_tasks.add_task(_run_orchestration)
    
    return {"success": True, "execution_id": execution_id, "message": "Workflow started via Real Orchestrator"}

@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    for exc in MOCK_EXECUTIONS:
        if exc.execution_id == execution_id:
            exc.status = "cancelled"
            return {"success": True}
    raise HTTPException(status_code=404, detail="Execution not found")

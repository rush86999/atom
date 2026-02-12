from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import WorkflowTemplate

logger = logging.getLogger(__name__)

# Feature flags
WORKFLOW_MOCK_ENABLED = os.getenv("WORKFLOW_MOCK_ENABLED", "false").lower() == "true"

router = APIRouter(tags=["workflow_ui"])

# --- Models matching Frontend Interfaces ---

class WorkflowStep(BaseModel):
    id: str
    type: str
    service: Optional[str] = None
    action: Optional[str] = None
    parameters: Dict[str, Any] = {}
    name: str

class WorkflowTemplateResponse(BaseModel):
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
    WorkflowTemplateResponse(
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
    WorkflowTemplateResponse(
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
    WorkflowTemplateResponse(
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
    WorkflowTemplateResponse(
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
async def get_templates(
    category: Optional[str] = None,
    complexity: Optional[str] = None,
    is_public: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get workflow templates from database.

    Args:
        category: Filter by category (automation, data_processing, ai_ml, etc.)
        complexity: Filter by complexity (beginner, intermediate, advanced, expert)
        is_public: Only show public templates
        db: Database session
    """
    # Use mock data if feature flag is enabled (for migration/testing)
    if WORKFLOW_MOCK_ENABLED:
        logger.warning("Using mock workflow templates (WORKFLOW_MOCK_ENABLED=true)")
        return {"success": True, "templates": [t.dict() for t in MOCK_TEMPLATES]}

    # Query database for templates
    query = db.query(WorkflowTemplate).filter(WorkflowTemplate.is_public == is_public)

    if category:
        query = query.filter(WorkflowTemplate.category == category)

    if complexity:
        query = query.filter(WorkflowTemplate.complexity == complexity)

    # Order by rating and usage count
    templates = query.order_by(
        WorkflowTemplate.is_featured.desc(),
        WorkflowTemplate.usage_count.desc()
    ).limit(50).all()

    # Transform to match expected format
    result = []
    for template in templates:
        result.append({
            "id": template.template_id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "complexity": template.complexity,
            "icon": template.tags[0] if template.tags and isinstance(template.tags, list) else "workflow",
            "steps": template.steps_schema or [],
            "input_schema": template.inputs_schema or {},
            "rating": template.rating,
            "usage_count": template.usage_count,
            "is_featured": template.is_featured,
            "author_id": template.author_id,
            "version": template.version,
            "tags": template.tags or []
        })

    return {
        "success": True,
        "templates": result,
        "count": len(result)
    }

@router.get("/services")
async def get_services():
    return {"success": True, "services": [s.dict() for s in MOCK_SERVICES.values()]}

@router.get("/definitions")
async def get_workflows(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get workflow definitions (legacy endpoint, uses templates)"""
    # Use mock data if feature flag is enabled
    if WORKFLOW_MOCK_ENABLED:
        logger.warning("Using mock workflow definitions (WORKFLOW_MOCK_ENABLED=true)")
        return {"success": True, "workflows": [w.dict() for w in MOCK_WORKFLOWS]}

    # Query database for templates (workflows are now templates)
    templates = db.query(WorkflowTemplate).filter(
        WorkflowTemplate.is_public == True
    ).order_by(
        WorkflowTemplate.created_at.desc()
    ).limit(limit).offset(offset).all()

    result = []
    for template in templates:
        result.append({
            "id": template.template_id,
            "name": template.name,
            "description": template.description,
            "steps": template.steps_schema or [],
            "input_schema": template.inputs_schema or {},
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
            "steps_count": len(template.steps_schema) if template.steps_schema else 0,
            "category": template.category,
            "complexity": template.complexity,
            "rating": template.rating,
            "usage_count": template.usage_count
        })

    return {
        "success": True,
        "workflows": result,
        "count": len(result)
    }

# Alias for /workflows to match common API patterns
@router.get("/workflows")
async def list_workflows(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List all workflows (alias for /definitions)"""
    return await get_workflows(limit=limit, offset=offset, db=db)

@router.get("/workflows/{workflow_id}")
async def get_workflow_by_id(workflow_id: str, db: Session = Depends(get_db)):
    """Get a specific workflow by ID"""
    # Use mock data if feature flag is enabled
    if WORKFLOW_MOCK_ENABLED:
        for w in MOCK_WORKFLOWS:
            if w.id == workflow_id:
                return {"success": True, "workflow": w.dict()}
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    # Query database
    template = db.query(WorkflowTemplate).filter(
        WorkflowTemplate.template_id == workflow_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    return {
        "success": True,
        "workflow": {
            "id": template.template_id,
            "name": template.name,
            "description": template.description,
            "steps": template.steps_schema or [],
            "input_schema": template.inputs_schema or {},
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
            "steps_count": len(template.steps_schema) if template.steps_schema else 0,
            "category": template.category,
            "complexity": template.complexity,
            "rating": template.rating,
            "usage_count": template.usage_count,
            "tags": template.tags or [],
            "version": template.version,
            "author_id": template.author_id
        }
    }

@router.post("/workflows")
async def create_workflow(
    payload: Dict[str, Any],
    author_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a new workflow template"""
    # Use mock if feature flag is enabled
    if WORKFLOW_MOCK_ENABLED:
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

    # Create database record
    template_id = f"tpl_{uuid.uuid4().hex[:8]}"
    template = WorkflowTemplate(
        template_id=template_id,
        name=payload.get("name", "New Workflow"),
        description=payload.get("description", ""),
        category=payload.get("category", "automation"),
        complexity=payload.get("complexity", "beginner"),
        tags=payload.get("tags", []),
        author_id=author_id,
        is_public=payload.get("is_public", False),
        template_json=payload,
        inputs_schema=payload.get("input_schema", {}),
        steps_schema=payload.get("steps", []),
        output_schema=payload.get("output_schema", {}),
        version="1.0.0"
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    return {
        "success": True,
        "workflow": {
            "id": template.template_id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "complexity": template.complexity,
            "tags": template.tags,
            "author_id": template.author_id,
            "is_public": template.is_public,
            "steps": template.steps_schema or [],
            "input_schema": template.inputs_schema or {},
            "output_schema": template.output_schema or {},
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
            "steps_count": len(template.steps_schema) if template.steps_schema else 0,
            "version": template.version
        }
    }

@router.put("/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Update an existing workflow"""
    # Use mock if feature flag is enabled
    if WORKFLOW_MOCK_ENABLED:
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

    # Update database record
    template = db.query(WorkflowTemplate).filter(
        WorkflowTemplate.template_id == workflow_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    # Update fields
    if "name" in payload:
        template.name = payload["name"]
    if "description" in payload:
        template.description = payload["description"]
    if "category" in payload:
        template.category = payload["category"]
    if "complexity" in payload:
        template.complexity = payload["complexity"]
    if "tags" in payload:
        template.tags = payload["tags"]
    if "input_schema" in payload:
        template.inputs_schema = payload["input_schema"]
    if "steps" in payload:
        template.steps_schema = payload["steps"]
    if "output_schema" in payload:
        template.output_schema = payload["output_schema"]
    if "is_public" in payload:
        template.is_public = payload["is_public"]

    db.commit()
    db.refresh(template)

    return {
        "success": True,
        "workflow": {
            "id": template.template_id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "complexity": template.complexity,
            "tags": template.tags,
            "is_public": template.is_public,
            "steps": template.steps_schema or [],
            "input_schema": template.inputs_schema or {},
            "output_schema": template.output_schema or {},
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
            "steps_count": len(template.steps_schema) if template.steps_schema else 0,
            "version": template.version
        }
    }

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """Delete a workflow"""
    # Use mock if feature flag is enabled
    if WORKFLOW_MOCK_ENABLED:
        for i, w in enumerate(MOCK_WORKFLOWS):
            if w.id == workflow_id:
                del MOCK_WORKFLOWS[i]
                return {"success": True, "message": f"Workflow '{workflow_id}' deleted"}
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    # Delete from database
    template = db.query(WorkflowTemplate).filter(
        WorkflowTemplate.template_id == workflow_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    db.delete(template)
    db.commit()

    return {
        "success": True,
        "message": f"Workflow '{workflow_id}' deleted"
    }

@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow_by_id(workflow_id: str, background_tasks: BackgroundTasks, payload: Dict[str, Any] = None):
    """Execute a workflow by ID"""
    from advanced_workflow_orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    input_data = payload or {}
    input_data["_ui_workflow_id"] = workflow_id
    
    async def _run_orchestration():
        await orchestrator.execute_workflow(workflow_id, input_data, execution_id=execution_id)
    
    try:
        background_tasks.add_task(_run_orchestration)
    except Exception as e:
        logger.error(f"Failed to schedule workflow execution: {e}", exc_info=True)
        # Orchestrator may not be available

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
        from advanced_workflow_orchestrator import WorkflowStatus, get_orchestrator
        orchestrator = get_orchestrator()
        
        executions = []
        # Convert Orchestrator contexts to UI Execution models

        # Use list() to avoid RuntimeError if dict changes size during iteration
        for context in list(orchestrator.active_contexts.values()):
            try:
                # Handle potential dict vs object (migration safety)
                c_id = getattr(context, 'workflow_id', None)
                if not c_id and isinstance(context, dict):
                     c_id = context.get('workflow_id')
                
                c_input = getattr(context, 'input_data', {})
                if not c_input and isinstance(context, dict):
                    c_input = context.get('input_data', {})
                
                c_status = getattr(context, 'status', 'pending')
                if isinstance(context, dict):
                    c_status = context.get('status', 'pending')
                
                status_str = "unknown"
                if hasattr(c_status, 'value'): 
                    status_str = c_status.value
                else:
                    status_str = str(c_status)
                
                # Safe Date Handling
                c_started = getattr(context, 'started_at', None)
                if isinstance(context, dict):
                     c_started = context.get('started_at')
                     
                start_time_str = datetime.now().isoformat()
                if isinstance(c_started, datetime):
                    start_time_str = c_started.isoformat()
                elif isinstance(c_started, str):
                    start_time_str = c_started
                
                c_ended = getattr(context, 'completed_at', None)
                if isinstance(context, dict):
                    c_ended = context.get('completed_at')
                    
                end_time_str = None
                if isinstance(c_ended, datetime):
                    end_time_str = c_ended.isoformat()
                elif isinstance(c_ended, str):
                    end_time_str = c_ended

                c_results = getattr(context, 'results', {})
                if isinstance(context, dict):
                    c_results = context.get('results', {})
                
                c_error = getattr(context, 'error_message', None)
                if isinstance(context, dict):
                    c_error = context.get('error_message')

                # Calculate metrics
                current_step = len(c_results) if c_results else 0
                
                executions.append(WorkflowExecution(
                    execution_id=str(c_id),
                    workflow_id=c_input.get("_ui_workflow_id", str(c_id)), # Prefer UI ID if stored
                    status=status_str,
                    start_time=start_time_str,
                    end_time=end_time_str,
                    current_step=current_step,
                    total_steps=4,
                    trigger_data=c_input,
                    results=c_results,
                    errors=[str(c_error)] if c_error else []
                ))
            except Exception as e:
                # Log but don't crash the whole list
                import traceback
                logger.error(f"Error parsing execution context: {e}")
                # traceback.print_exc()
                continue

            
        # Sort by start time (newest first)
        executions.sort(key=lambda x: x.start_time, reverse=True)
        return {"success": True, "executions": [e.dict() for e in executions]}
            
    except ImportError:
        # Fallback if orchestrator not available/path issue
        return {"success": True, "executions": [e.dict() for e in MOCK_EXECUTIONS]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e), "executions": []}

@router.post("/execute")
async def execute_workflow(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    from advanced_workflow_orchestrator import (
        WorkflowContext,
        WorkflowDefinition,
        WorkflowStatus,
        WorkflowStep,
        WorkflowStepType,
        get_orchestrator,
    )
    orchestrator = get_orchestrator()
    
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
        # [FIX] Bridge Mock/UI Workflows to Real Orchestrator
        # If not found, check MOCK_WORKFLOWS and register it on the fly
        found_mock = next((w for w in MOCK_WORKFLOWS if w.id == workflow_id), None)
        if not found_mock:
            # Check templates if not in active workflows
            found_mock = next((t for t in MOCK_TEMPLATES if t.id == workflow_id), None)
            
        if found_mock:
            orchestrator_steps = []
            
            # Simple conversion logic
            for step in found_mock.steps:
                # Default to universal integration
                step_type = WorkflowStepType.UNIVERSAL_INTEGRATION
                svc = step.service.lower() if step.service else "unknown"
                act = step.action.lower() if step.action else "execute"
                
                if svc in ["ai", "llm"]:
                    step_type = WorkflowStepType.NLU_ANALYSIS
                elif svc in ["slack", "discord"]:
                    step_type = WorkflowStepType.SLACK_NOTIFICATION
                elif svc in ["email", "gmail", "outlook"]:
                    step_type = WorkflowStepType.EMAIL_SEND
                elif svc == "delay":
                    step_type = WorkflowStepType.DELAY
                
                orchestrator_steps.append(WorkflowStep(
                    step_id=step.id,
                    step_type=step_type,
                    description=step.name,
                    parameters={**step.parameters, "service": svc, "action": act},
                    next_steps=[] # Sequential by default in this simple bridge
                ))
            
            # Link steps sequentially
            for i in range(len(orchestrator_steps) - 1):
                orchestrator_steps[i].next_steps = [orchestrator_steps[i+1].step_id]
                
            new_def = WorkflowDefinition(
                workflow_id=workflow_id,
                name=found_mock.name,
                description=found_mock.description,
                steps=orchestrator_steps,
                start_step=orchestrator_steps[0].step_id if orchestrator_steps else "end",
                version="1.0-ui-bridge"
            )
            
            orchestrator.workflows[workflow_id] = new_def
            orchestrator_id = workflow_id # Use the ID we just registered
        else:
             logger.warning(f"Warning: Workflow ID {workflow_id} not found in orchestrator or mocks.")

    # Generate Execution ID for immediate UI feedback
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    
    # [FIX] Pre-register the context so it appears in lists immediately
    # and provides valid data for the UI response
    context = WorkflowContext(
        workflow_id=execution_id, 
        user_id="ui_user",
        input_data=input_data
    )
    context.execution_id = execution_id # Ensure this field exists if defined by chance
    context.started_at = datetime.now()
    context.status = WorkflowStatus.PENDING
    
    # Register immediately
    orchestrator.active_contexts[execution_id] = context
    
    async def _run_orchestration():
        try:
            # Pass the ALREADY CREATED contex ID
            await orchestrator.execute_workflow(orchestrator_id, input_data, execution_id=execution_id)
        except Exception as e:
            logger.error(f"Background execution failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            context.status = WorkflowStatus.FAILED
            context.error_message = str(e)
            context.completed_at = datetime.now()
        
    background_tasks.add_task(_run_orchestration)

    # Calculate actual step count from workflow definition
    total_steps = 0
    if orchestrator_id and orchestrator_id in orchestrator.workflows:
        workflow_def = orchestrator.workflows[orchestrator_id]
        total_steps = len(workflow_def.steps) if workflow_def.steps else 0
    elif found_mock and hasattr(found_mock, 'steps'):
        total_steps = len(found_mock.steps)

    # Return FULL Execution Object compatible with Frontend
    return {
        "success": True,
        "execution_id": execution_id,
        "workflow_id": workflow_id,
        "status": "pending",
        "start_time": context.started_at.isoformat(),
        "current_step": 0,
        "total_steps": total_steps,  # Dynamic count from workflow definition
        "results": {},
        "message": "Workflow started via Real Orchestrator"
    }

@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    for exc in MOCK_EXECUTIONS:
        if exc.execution_id == execution_id:
            exc.status = "cancelled"
            return {"success": True}
    raise HTTPException(status_code=404, detail="Execution not found")
@router.get("/debug/state")
async def get_orchestrator_state():
    """Debug endpoint to inspect orchestrator memory"""
    from advanced_workflow_orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    return {
        "active_contexts": list(orchestrator.active_contexts.keys()),
        "memory_snapshots": list(orchestrator.memory_snapshots.keys()),
        "snapshot_details": {k: {"step": v.get("current_step"), "vars": list(v.get("variables", {}).keys())} for k, v in orchestrator.memory_snapshots.items()}
    }

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid
import json
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple file-based storage for MVP
WORKFLOWS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workflows.json")

class WorkflowNode(BaseModel):
    id: str
    type: str
    title: str
    description: str
    position: Dict[str, float]
    config: Dict[str, Any]
    connections: List[str]

class WorkflowConnection(BaseModel):
    id: str
    source: str
    target: str
    condition: Optional[str] = None

class WorkflowDefinition(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    version: str
    nodes: List[WorkflowNode]
    connections: List[WorkflowConnection]
    triggers: List[str]
    enabled: bool
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

def load_workflows() -> List[Dict]:
    if not os.path.exists(WORKFLOWS_FILE):
        return []
    try:
        with open(WORKFLOWS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_workflows(workflows: List[Dict]):
    with open(WORKFLOWS_FILE, 'w') as f:
        json.dump(workflows, f, indent=2)

@router.get("/workflows", response_model=List[WorkflowDefinition])
async def get_workflows():
    return load_workflows()

@router.get("/workflows/{workflow_id}", response_model=WorkflowDefinition)
async def get_workflow(workflow_id: str):
    workflows = load_workflows()
    workflow = next((w for w in workflows if w['id'] == workflow_id), None)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@router.post("/workflows", response_model=WorkflowDefinition)
async def create_workflow(workflow: WorkflowDefinition):
    workflows = load_workflows()
    
    # Generate ID if new
    if not workflow.id:
        workflow.id = str(uuid.uuid4())
        workflow.createdAt = datetime.now().isoformat()
    
    workflow.updatedAt = datetime.now().isoformat()
    
    # Check if exists (update)
    existing_index = next((i for i, w in enumerate(workflows) if w['id'] == workflow.id), -1)
    
    workflow_dict = workflow.dict()
    
    if existing_index >= 0:
        workflows[existing_index] = workflow_dict
    else:
        workflows.append(workflow_dict)
    
    save_workflows(workflows)
    return workflow_dict

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    workflows = load_workflows()
    workflows = [w for w in workflows if w['id'] != workflow_id]
    save_workflows(workflows)
    return {"status": "success"}

class ExecutionResult(BaseModel):
    execution_id: str
    workflow_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    results: List[Dict[str, Any]] = []
    errors: List[str] = []

@router.post("/workflows/{workflow_id}/execute", response_model=ExecutionResult)
async def execute_workflow(workflow_id: str, input_data: Optional[Dict[str, Any]] = None):
    """Execute a workflow by ID"""
    from ai.automation_engine import AutomationEngine
    
    # Load workflow
    workflows = load_workflows()
    workflow = next((w for w in workflows if w['id'] == workflow_id), None)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Create execution record
    execution_id = str(uuid.uuid4())
    started_at = datetime.now().isoformat()
    
    try:
        # Initialize engine
        engine = AutomationEngine()
        
        # Execute workflow
        results = await engine.execute_workflow_definition(workflow, input_data or {}, execution_id=execution_id)
        
        return ExecutionResult(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status="success", # This should ideally come from the engine result
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
            results=results,
            errors=[]
        )
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        return ExecutionResult(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status="failed",
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
            results=[],
            errors=[str(e)]
        )

@router.get("/workflows/{workflow_id}/executions", response_model=List[Dict[str, Any]])
async def get_workflow_executions(workflow_id: str):
    """Get execution history for a workflow"""
    from ai.automation_engine import AutomationEngine
    engine = AutomationEngine()
    executions = engine.get_execution_history(workflow_id)
    return [e.to_dict() for e in executions]

@router.get("/workflows/executions/{execution_id}", response_model=Dict[str, Any])
async def get_execution_details(execution_id: str):
    """Get details of a specific execution"""
    from ai.automation_engine import AutomationEngine
    engine = AutomationEngine()
    if execution_id not in engine.executions:
        raise HTTPException(status_code=404, detail="Execution not found")
    return engine.executions[execution_id].to_dict()

# Scheduling Endpoints

@router.post("/workflows/{workflow_id}/schedule")
async def schedule_workflow(workflow_id: str, schedule_config: Dict[str, Any] = Body(...)):
    """
    Schedule a workflow execution.
    
    schedule_config should contain:
    - trigger_type: 'cron', 'interval', or 'date'
    - trigger_config: Dict with trigger params (e.g. {'minutes': 30} for interval)
    - input_data: Optional input data
    """
    from ai.workflow_scheduler import workflow_scheduler
    
    try:
        trigger_type = schedule_config.get('trigger_type')
        trigger_config = schedule_config.get('trigger_config')
        input_data = schedule_config.get('input_data')
        
        if not trigger_type or not trigger_config:
            raise HTTPException(status_code=400, detail="Missing trigger_type or trigger_config")
            
        job_id = workflow_scheduler.schedule_workflow(workflow_id, trigger_type, trigger_config, input_data)
        
        return {"success": True, "job_id": job_id, "message": f"Workflow scheduled with ID {job_id}"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Scheduling failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/workflows/{workflow_id}/schedule/{job_id}")
async def unschedule_workflow(workflow_id: str, job_id: str):
    """Remove a scheduled workflow job"""
    from ai.workflow_scheduler import workflow_scheduler
    workflow_scheduler.remove_schedule(job_id)
    return {"success": True, "message": "Schedule removed"}

@router.get("/scheduler/jobs")
async def list_scheduled_jobs():
    """List all scheduled jobs"""
    from ai.workflow_scheduler import workflow_scheduler
    return workflow_scheduler.list_jobs()


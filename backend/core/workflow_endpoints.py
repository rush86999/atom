from fastapi import APIRouter, HTTPException, Depends
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
        results = await engine.execute_workflow_definition(workflow, input_data or {})
        
        return ExecutionResult(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status="success",
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


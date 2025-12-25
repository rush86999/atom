from fastapi import APIRouter, HTTPException, Depends, Body, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid
import json
import os
import logging
import re
from core.models import User
from core.security_dependencies import require_permission
from core.rbac_service import Permission

# Import AI workflow editor for natural language processing
logger = logging.getLogger(__name__)

try:
    from ai.workflow_nlu_editor import get_workflow_editor
    AI_EDITOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AI workflow editor not available: {e}")
    AI_EDITOR_AVAILABLE = False

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

class WorkflowEditRequest(BaseModel):
    command: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class WorkflowEditResponse(BaseModel):
    success: bool
    message: str
    modified_workflow: Optional[Dict[str, Any]] = None
    changes: List[Dict[str, Any]] = []


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
async def get_workflows(user: User = Depends(require_permission(Permission.WORKFLOW_VIEW))):
    return load_workflows()

@router.get("/workflows/{workflow_id}", response_model=WorkflowDefinition)
async def get_workflow(workflow_id: str, user: User = Depends(require_permission(Permission.WORKFLOW_VIEW))):
    workflows = load_workflows()
    workflow = next((w for w in workflows if w.get('id') == workflow_id or w.get('workflow_id') == workflow_id), None)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@router.post("/workflows", response_model=WorkflowDefinition)
async def create_workflow(workflow: WorkflowDefinition, user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE))):
    workflows = load_workflows()

    # Generate ID if new
    if not workflow.id:
        workflow.id = str(uuid.uuid4())
        workflow.createdAt = datetime.now().isoformat()

    workflow.updatedAt = datetime.now().isoformat()

    workflow_dict = workflow.dict()

    # Check if exists (update)
    existing_index = next((i for i, w in enumerate(workflows) if w.get('id') == workflow.id or w.get('workflow_id') == workflow.id), -1)

    if existing_index >= 0:
        workflows[existing_index] = workflow_dict
    else:
        workflows.append(workflow_dict)

    save_workflows(workflows)
    return workflow_dict

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE))):
    workflows = load_workflows()
    workflows = [w for w in workflows if w.get('id') != workflow_id and w.get('workflow_id') != workflow_id]
    save_workflows(workflows)
    return {"status": "success"}


async def _legacy_rule_based_edit(
    workflow_id: str,
    request: WorkflowEditRequest,
    workflows: List[Dict],
    workflow: Dict[str, Any]
) -> WorkflowEditResponse:
    """
    Original rule-based parsing for natural language workflow editing.
    Used as fallback when AI parsing is not available or fails.
    """
    command = request.command.lower()
    changes = []

    # Add step pattern
    add_step_match = re.search(r'add (?:a |an )?(\w+) step', command)
    if add_step_match:
        service = add_step_match.group(1)
        # Generate new node ID
        new_node_id = f"node_{str(uuid.uuid4())[:8]}"
        new_node = {
            "id": new_node_id,
            "type": "action",
            "title": f"{service.capitalize()} Action",
            "description": f"Added via natural language command: {request.command}",
            "position": {"x": 100, "y": 100},  # Default position
            "config": {
                "service": service,
                "action": "default",
                "parameters": {}
            },
            "connections": []
        }
        workflow['nodes'].append(new_node)
        changes.append({
            "type": "add_step",
            "step_id": new_node_id,
            "service": service
        })
        # Save modified workflow
        save_workflows(workflows)
        return WorkflowEditResponse(
            success=True,
            message=f"Added {service} step to workflow",
            modified_workflow=workflow,
            changes=changes
        )

    # Remove step pattern
    remove_step_match = re.search(r'remove step (\w+)', command)
    if remove_step_match:
        step_id = remove_step_match.group(1)
        # Find and remove node
        original_count = len(workflow['nodes'])
        workflow['nodes'] = [n for n in workflow['nodes'] if n['id'] != step_id]
        if len(workflow['nodes']) < original_count:
            # Also remove connections involving this node
            workflow['connections'] = [c for c in workflow['connections']
                                     if c['source'] != step_id and c['target'] != step_id]
            changes.append({
                "type": "remove_step",
                "step_id": step_id
            })
            save_workflows(workflows)
            return WorkflowEditResponse(
                success=True,
                message=f"Removed step {step_id} from workflow",
                modified_workflow=workflow,
                changes=changes
            )
        else:
            return WorkflowEditResponse(
                success=False,
                message=f"Step {step_id} not found in workflow",
                modified_workflow=None,
                changes=[]
            )

    # Update condition pattern
    update_condition_match = re.search(r'update condition (?:of )?connection (\w+) to (.+)', command)
    if update_condition_match:
        connection_id = update_condition_match.group(1)
        new_condition = update_condition_match.group(2)
        # Find connection
        for conn in workflow['connections']:
            if conn['id'] == connection_id:
                conn['condition'] = new_condition
                changes.append({
                    "type": "update_condition",
                    "connection_id": connection_id,
                    "new_condition": new_condition
                })
                save_workflows(workflows)
                return WorkflowEditResponse(
                    success=True,
                    message=f"Updated condition for connection {connection_id}",
                    modified_workflow=workflow,
                    changes=changes
                )
        return WorkflowEditResponse(
            success=False,
            message=f"Connection {connection_id} not found",
            modified_workflow=None,
            changes=[]
        )

    # If no pattern matched
    return WorkflowEditResponse(
        success=False,
        message="Could not understand the command. Supported commands: add step, remove step, update condition",
        modified_workflow=None,
        changes=[]
    )


@router.post("/workflows/{workflow_id}/edit", response_model=WorkflowEditResponse)
async def edit_workflow_natural_language(
    workflow_id: str,
    request: WorkflowEditRequest,
    user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE))
):
    """
    Edit a workflow using natural language commands with AI-powered parsing.
    Enhanced with BYOK AI model integration for better understanding.

    Examples:
    - "add a slack step that sends message to #general when a new issue is created in GitHub"
    - "remove the email notification step from the workflow"
    - "update the condition on connection X to check if amount > 1000"
    - "add a delay of 5 minutes before sending the slack message"
    """
    workflows = load_workflows()
    workflow = next((w for w in workflows if w.get('id') == workflow_id or w.get('workflow_id') == workflow_id), None)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    command = request.command
    changes = []

    try:
        # Use AI-powered editor if available, otherwise fallback to rule-based
        if AI_EDITOR_AVAILABLE:
            editor = await get_workflow_editor()

            # Parse command with AI
            edit_plan = await editor.parse_workflow_edit_command(command, workflow)

            if edit_plan.confidence < 0.3:
                logger.warning(f"AI parsing low confidence: {edit_plan.confidence}. Command: {command}")
                # Fallback to rule-based parsing
                edit_plan = editor._rule_based_parse(command.lower(), workflow)

            # Apply edit plan
            modified_workflow = await editor.apply_edit_plan(edit_plan, workflow)

            # Convert operations to change log format
            for operation in edit_plan.operations:
                if operation.operation_type == "add_node":
                    changes.append({
                        "type": "add_step",
                        "step_id": operation.target_id or "unknown",
                        "service": operation.data.get("config", {}).get("service", "unknown") if operation.data else "unknown"
                    })
                elif operation.operation_type == "remove_node":
                    changes.append({
                        "type": "remove_step",
                        "step_id": operation.target_id or "unknown"
                    })
                elif operation.operation_type == "update_condition":
                    changes.append({
                        "type": "update_condition",
                        "connection_id": operation.target_id or "unknown",
                        "new_condition": operation.data.get("condition") if operation.data else "unknown"
                    })
                elif operation.operation_type == "add_connection":
                    changes.append({
                        "type": "add_connection",
                        "connection_id": operation.target_id or "unknown",
                        "source": operation.data.get("source") if operation.data else "unknown",
                        "target": operation.data.get("target") if operation.data else "unknown"
                    })
                elif operation.operation_type == "remove_connection":
                    changes.append({
                        "type": "remove_connection",
                        "connection_id": operation.target_id or "unknown"
                    })
                elif operation.operation_type == "update_node":
                    changes.append({
                        "type": "update_node",
                        "node_id": operation.target_id or "unknown"
                    })

            # Update workflow in storage
            for i, w in enumerate(workflows):
                if w.get('id') == workflow_id or w.get('workflow_id') == workflow_id:
                    workflows[i] = modified_workflow
                    break

            save_workflows(workflows)

            # Build success message
            if edit_plan.reasoning:
                message = f"Workflow edited successfully. AI reasoning: {edit_plan.reasoning}"
            else:
                message = f"Workflow edited successfully. Confidence: {edit_plan.confidence:.2f}"

            return WorkflowEditResponse(
                success=True,
                message=message,
                modified_workflow=modified_workflow,
                changes=changes
            )
        else:
            # Fallback to original rule-based parsing if AI editor not available
            logger.warning("AI editor not available, using rule-based parsing")
            return await _legacy_rule_based_edit(workflow_id, request, workflows, workflow)

    except Exception as e:
        logger.error(f"Error editing workflow with AI: {e}")
        # Fallback to rule-based parsing on error
        try:
            return await _legacy_rule_based_edit(workflow_id, request, workflows, workflow)
        except Exception as fallback_error:
            logger.error(f"Fallback parsing also failed: {fallback_error}")
            return WorkflowEditResponse(
                success=False,
                message=f"Could not understand the command. Error: {str(e)[:100]}",
                modified_workflow=None,
                changes=[]
            )

class ExecutionResult(BaseModel):
    execution_id: str
    workflow_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    results: List[Dict[str, Any]] = []
    errors: List[str] = []

@router.post("/workflows/{workflow_id}/execute", response_model=ExecutionResult)
async def execute_workflow(
    workflow_id: str, 
    background_tasks: BackgroundTasks,
    input_data: Optional[Dict[str, Any]] = None,
    user: User = Depends(require_permission(Permission.WORKFLOW_RUN))
):
    """Execute a workflow by ID"""
    from core.workflow_engine import get_workflow_engine
    
    # Load workflow
    workflows = load_workflows()
    workflow = next((w for w in workflows if w.get('id') == workflow_id or w.get('workflow_id') == workflow_id), None)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Create execution record
    started_at = datetime.now().isoformat()
    
    try:
        # Initialize engine
        engine = get_workflow_engine()
        
        # Execute workflow (starts in background)
        execution_id = await engine.start_workflow(workflow, input_data or {}, background_tasks)
        
        return ExecutionResult(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status="running",
            started_at=started_at,
            completed_at=None,
            results=[],
            errors=[]
        )
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        # Generate a temporary ID for error reporting if start_workflow failed before returning ID
        temp_id = str(uuid.uuid4())
        return ExecutionResult(
            execution_id=temp_id,
            workflow_id=workflow_id,
            status="failed",
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
            results=[],
            errors=[str(e)]
        )

@router.post("/workflows/{execution_id}/resume")
async def resume_workflow(
    execution_id: str, 
    input_data: Dict[str, Any] = Body(...),
    user: User = Depends(require_permission(Permission.WORKFLOW_RUN))
):
    """Resume a paused workflow execution"""
    from core.workflow_engine import get_workflow_engine
    from core.execution_state_manager import get_state_manager
    
    engine = get_workflow_engine()
    state_manager = get_state_manager()
    
    # Get current state to find workflow definition
    state = await state_manager.get_execution_state(execution_id)
    if not state:
        raise HTTPException(status_code=404, detail="Execution not found")
        
    # Load workflow definition
    # In a real app, we might store the definition snapshot with the execution
    # For now, load current definition
    workflows = load_workflows()
    workflow = next((w for w in workflows if w.get('id') == state['workflow_id'] or w.get('workflow_id') == state['workflow_id']), None)
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
        
    success = await engine.resume_workflow(execution_id, workflow, input_data)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to resume workflow")
        
    return {"status": "resumed", "execution_id": execution_id}



@router.get("/workflows/{workflow_id}/executions", response_model=List[Dict[str, Any]])
async def get_workflow_executions(
    workflow_id: str,
    user: User = Depends(require_permission(Permission.WORKFLOW_VIEW))
):
    """Get execution history for a workflow"""
    from ai.automation_engine import AutomationEngine
    engine = AutomationEngine()
    executions = engine.get_execution_history(workflow_id)
    return [e.to_dict() for e in executions]

@router.get("/workflows/executions/{execution_id}", response_model=Dict[str, Any])
async def get_execution_details(
    execution_id: str,
    user: User = Depends(require_permission(Permission.WORKFLOW_VIEW))
):
    """Get details of a specific execution"""
    from ai.automation_engine import AutomationEngine
    engine = AutomationEngine()
    if execution_id not in engine.executions:
        raise HTTPException(status_code=404, detail="Execution not found")
    return engine.executions[execution_id].to_dict()

# Scheduling Endpoints

@router.post("/workflows/{workflow_id}/schedule")
async def schedule_workflow(
    workflow_id: str, 
    schedule_config: Dict[str, Any] = Body(...),
    user: User = Depends(require_permission(Permission.WORKFLOW_RUN))
):
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
async def unschedule_workflow(
    workflow_id: str, 
    job_id: str,
    user: User = Depends(require_permission(Permission.WORKFLOW_RUN))
):
    """Remove a scheduled workflow job"""
    from ai.workflow_scheduler import workflow_scheduler
    workflow_scheduler.remove_schedule(job_id)
    return {"success": True, "message": "Schedule removed"}

@router.get("/scheduler/jobs")
async def list_scheduled_jobs(user: User = Depends(require_permission(Permission.WORKFLOW_VIEW))):
    """List all scheduled jobs"""
    from ai.workflow_scheduler import workflow_scheduler
    return workflow_scheduler.list_jobs()


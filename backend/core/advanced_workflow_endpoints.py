"""
Advanced Workflow API Endpoints
Multi-input, multi-step, multi-output workflow support with state management
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio
import logging

from .advanced_workflow_system import (
    AdvancedWorkflowDefinition, WorkflowState, WorkflowStep,
    ParameterType, InputParameter, StateManager,
    ParameterValidator, ExecutionEngine
)
from .workflow_template_manager import WorkflowTemplateManager, get_workflow_template_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize global instances
state_manager = StateManager()
execution_engine = ExecutionEngine(state_manager)
template_manager = get_workflow_template_manager()

# Request/Response Models
class CreateWorkflowRequest(BaseModel):
    name: str
    description: str
    category: str = "general"
    tags: List[str] = []
    input_schema: List[Dict[str, Any]] = []
    steps: List[Dict[str, Any]] = []
    output_config: Optional[Dict[str, Any]] = None

class StartWorkflowRequest(BaseModel):
    workflow_id: str
    inputs: Dict[str, Any] = {}

class UpdateWorkflowRequest(BaseModel):
    inputs: Dict[str, Any] = {}

class WorkflowStepRequest(BaseModel):
    step_id: str
    inputs: Dict[str, Any] = {}

class WorkflowTemplate(BaseModel):
    template_id: str
    name: str
    description: str
    category: str
    input_schema: List[Dict[str, Any]]
    steps: List[Dict[str, Any]]
    tags: List[str] = []

# Helper Functions
def serialize_workflow(workflow: AdvancedWorkflowDefinition) -> Dict[str, Any]:
    """Convert workflow to serializable dict"""
    return {
        "workflow_id": workflow.workflow_id,
        "name": workflow.name,
        "description": workflow.description,
        "version": workflow.version,
        "category": workflow.category,
        "tags": workflow.tags,
        "input_schema": [param.dict() for param in workflow.input_schema],
        "steps": [step.dict() for step in workflow.steps],
        "output_config": workflow.output_config.dict() if workflow.output_config else None,
        "state": workflow.state.value,
        "current_step": workflow.current_step,
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat(),
        "created_by": workflow.created_by
    }

# Endpoints
@router.post("/workflows", response_model=Dict[str, Any])
async def create_workflow(request: CreateWorkflowRequest):
    """Create a new advanced workflow"""
    try:
        # Convert request to workflow definition
        workflow_data = {
            "workflow_id": f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(request.name) % 10000}",
            "name": request.name,
            "description": request.description,
            "category": request.category,
            "tags": request.tags,
            "input_schema": [InputParameter(**param) for param in request.input_schema],
            "steps": [WorkflowStep(**step) for step in request.steps],
            "output_config": request.output_config
        }

        # Create workflow
        workflow = await execution_engine.create_workflow(workflow_data)

        return {
            "status": "success",
            "workflow_id": workflow.workflow_id,
            "workflow": serialize_workflow(workflow)
        }

    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/workflows")
async def list_workflows(
    state: Optional[WorkflowState] = None,
    category: Optional[str] = None,
    tags: Optional[str] = None,  # Comma-separated tags
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    limit: Optional[int] = None,
    offset: int = 0
):
    """
    List workflows with comprehensive filtering and sorting.

    Query Parameters:
    - state: Filter by workflow state (draft, running, completed, etc.)
    - category: Filter by category
    - tags: Comma-separated list of tags (workflows must have ALL specified tags)
    - sort_by: Field to sort by (updated_at, created_at, name)
    - sort_order: Sort order (asc or desc)
    - limit: Maximum number of workflows to return
    - offset: Number of workflows to skip
    """
    try:
        # Convert state enum to status string if provided
        status_filter = None
        if state is not None:
            status_filter = state.value if isinstance(state, WorkflowState) else state

        # Parse tags from comma-separated string
        tags_list = None
        if tags:
            tags_list = [t.strip() for t in tags.split(",") if t.strip()]

        # Get workflows from state manager with all filters
        workflows = state_manager.list_workflows(
            status=status_filter,
            category=category,
            tags=tags_list,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset
        )

        # Get total count (without pagination for accurate total)
        total_workflows = len(state_manager.list_workflows(
            status=status_filter,
            category=category,
            tags=tags_list
        ))

        # Return workflows with pagination metadata
        return {
            "workflows": workflows,
            "total": total_workflows,
            "offset": offset,
            "limit": limit if limit is not None else len(workflows),
            "filters": {
                "state": status_filter,
                "category": category,
                "tags": tags_list
            }
        }

    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow(workflow_id: str):
    """Get workflow details"""
    try:
        state = state_manager.load_state(workflow_id)
        if not state:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = AdvancedWorkflowDefinition(**state)

        return {
            "status": "success",
            "workflow": serialize_workflow(workflow),
            "execution_status": execution_engine.get_workflow_status(workflow_id)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{workflow_id}/start", response_model=Dict[str, Any])
async def start_workflow(workflow_id: str, request: StartWorkflowRequest):
    """Start or resume workflow execution"""
    try:
        # Validate inputs
        state = state_manager.load_state(workflow_id)
        if not state:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = AdvancedWorkflowDefinition(**state)

        # Validate inputs
        validation_errors = []
        for param in workflow.input_schema:
            if param.name in request.inputs:
                is_valid, error_msg = ParameterValidator.validate_parameter(param, request.inputs[param.name])
                if not is_valid:
                    validation_errors.append(f"{param.name}: {error_msg}")

        if validation_errors:
            raise HTTPException(status_code=400, detail={
                "type": "validation_error",
                "errors": validation_errors
            })

        # Start execution
        result = await execution_engine.start_workflow(workflow_id, request.inputs)

        return {
            "status": "success",
            "result": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{workflow_id}/pause", response_model=Dict[str, Any])
async def pause_workflow(workflow_id: str):
    """Pause workflow execution"""
    try:
        success = execution_engine.pause_workflow(workflow_id)

        if not success:
            raise HTTPException(status_code=400, detail="Workflow cannot be paused")

        return {
            "status": "success",
            "message": "Workflow paused"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{workflow_id}/resume", response_model=Dict[str, Any])
async def resume_workflow(workflow_id: str, request: UpdateWorkflowRequest):
    """Resume paused workflow execution"""
    try:
        result = execution_engine.resume_workflow(workflow_id, request.inputs)

        return {
            "status": "success",
            "result": result
        }

    except Exception as e:
        logger.error(f"Failed to resume workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{workflow_id}/cancel", response_model=Dict[str, Any])
async def cancel_workflow(workflow_id: str):
    """Cancel workflow execution"""
    try:
        success = execution_engine.cancel_workflow(workflow_id)

        if not success:
            raise HTTPException(status_code=400, detail="Workflow cannot be cancelled")

        return {
            "status": "success",
            "message": "Workflow cancelled"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/{workflow_id}/status", response_model=Dict[str, Any])
async def get_workflow_status(workflow_id: str):
    """Get current workflow execution status"""
    try:
        status = execution_engine.get_workflow_status(workflow_id)

        if not status:
            raise HTTPException(status_code=404, detail="Workflow not found")

        return {
            "status": "success",
            "workflow_status": status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow status {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/{workflow_id}/step/{step_id}", response_model=Dict[str, Any])
async def get_workflow_step(workflow_id: str, step_id: str):
    """Get specific workflow step details"""
    try:
        state = state_manager.load_state(workflow_id)
        if not state:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = AdvancedWorkflowDefinition(**state)

        # Find the step
        step = next((s for s in workflow.steps if s.step_id == step_id), None)
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")

        # Get step result if available
        step_result = workflow.step_results.get(step_id, None)

        return {
            "status": "success",
            "step": step.dict(),
            "result": step_result,
            "is_current_step": workflow.current_step == step_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow step {workflow_id}/{step_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{workflow_id}/step/{step_id}/execute", response_model=Dict[str, Any])
async def execute_workflow_step(workflow_id: str, step_id: str, request: WorkflowStepRequest):
    """Execute a specific workflow step with provided inputs"""
    try:
        state = state_manager.load_state(workflow_id)
        if not state:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = AdvancedWorkflowDefinition(**state)

        # Find the step
        step = next((s for s in workflow.steps if s.step_id == step_id), None)
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")

        # Prepare step inputs
        step_inputs = request.inputs
        step_inputs.update(workflow.user_inputs)

        # Validate step inputs
        validation_errors = []
        for param in step.input_parameters:
            if param.name in step_inputs:
                is_valid, error_msg = ParameterValidator.validate_parameter(param, step_inputs[param.name])
                if not is_valid:
                    validation_errors.append(f"{param.name}: {error_msg}")

        if validation_errors:
            raise HTTPException(status_code=400, detail={
                "type": "validation_error",
                "errors": validation_errors
            })

        # Execute step
        result = await execution_engine._execute_step(workflow, step)

        # Update workflow state
        workflow.step_results[step_id] = result
        workflow.updated_at = datetime.now()
        state_manager.save_state(workflow_id, workflow.dict())

        return {
            "status": "success",
            "step_result": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute workflow step {workflow_id}/{step_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/{workflow_id}/inputs/required", response_model=Dict[str, Any])
async def get_required_inputs(workflow_id: str):
    """Get required inputs for the workflow"""
    try:
        state = state_manager.load_state(workflow_id)
        if not state:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = AdvancedWorkflowDefinition(**state)

        # Get missing inputs
        missing_inputs = execution_engine._get_missing_inputs(workflow, workflow.user_inputs)

        return {
            "status": "success",
            "required_inputs": [param.dict() for param in missing_inputs],
            "current_step": workflow.current_step,
            "workflow_state": workflow.state.value
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get required inputs {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Template Management
@router.get("/workflows/templates", response_model=List[Dict[str, Any]])
async def list_workflow_templates(
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    active_only: bool = True
):
    """List available workflow templates"""
    try:
        templates = template_manager.list_templates(
            category=category,
            tags=tags,
            active_only=active_only
        )

        return [template.dict() for template in templates]

    except Exception as e:
        logger.error(f"Failed to list workflow templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/templates", response_model=Dict[str, Any])
async def create_workflow_template(template: Dict[str, Any]):
    """Create a workflow template"""
    try:
        created_template = template_manager.create_template(template)

        return {
            "status": "success",
            "template_id": created_template.template_id,
            "template": created_template.dict()
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create workflow template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/from-template", response_model=Dict[str, Any])
async def create_workflow_from_template(
    template_id: str,
    workflow_data: Dict[str, Any]
):
    """Create a new workflow from a template"""
    try:
        # Get workflow definition from template
        workflow_definition = template_manager.create_workflow_from_template(
            template_id=template_id,
            workflow_data=workflow_data
        )

        # Create the workflow
        workflow = await execution_engine.create_workflow(workflow_definition)

        return {
            "status": "success",
            "workflow_id": workflow.workflow_id,
            "template_id": template_id,
            "workflow": serialize_workflow(workflow)
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create workflow from template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Parameter Types and Validation
@router.get("/workflows/parameter-types", response_model=List[str])
async def get_parameter_types():
    """Get available parameter types"""
    return [param_type.value for param_type in ParameterType]

@router.post("/workflows/validate-parameters", response_model=Dict[str, Any])
async def validate_parameters(
    parameters: List[Dict[str, Any]],
    inputs: Dict[str, Any]
):
    """Validate input parameters"""
    try:
        results = {}

        for param_data in parameters:
            param = InputParameter(**param_data)
            value = inputs.get(param.name)

            is_valid, error_msg = ParameterValidator.validate_parameter(param, value)

            results[param.name] = {
                "valid": is_valid,
                "error": error_msg,
                "type": param.type.value,
                "required": param.required
            }

        return {
            "status": "success",
            "validation_results": results,
            "all_valid": all(r["valid"] for r in results.values())
        }

    except Exception as e:
        logger.error(f"Failed to validate parameters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Export/Import
@router.get("/workflows/{workflow_id}/export", response_model=Dict[str, Any])
async def export_workflow(workflow_id: str):
    """Export workflow definition"""
    try:
        state = state_manager.load_state(workflow_id)
        if not state:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Remove execution-specific data for export
        export_data = state.copy()
        export_data.pop("step_results", None)
        export_data.pop("execution_context", None)
        export_data.pop("state", None)
        export_data.pop("current_step", None)

        return {
            "status": "success",
            "workflow_definition": export_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/import", response_model=Dict[str, Any])
async def import_workflow(workflow_definition: Dict[str, Any]):
    """Import workflow definition"""
    try:
        # Create new workflow from definition
        workflow_definition["workflow_id"] = f"imported_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        workflow_definition["state"] = WorkflowState.DRAFT

        workflow = await execution_engine.create_workflow(workflow_definition)

        return {
            "status": "success",
            "workflow_id": workflow.workflow_id,
            "workflow": serialize_workflow(workflow)
        }

    except Exception as e:
        logger.error(f"Failed to import workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))
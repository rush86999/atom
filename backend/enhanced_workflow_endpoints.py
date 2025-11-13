from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from data_persistence import data_persistence
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from workflow_engine import WorkflowStatus, workflow_engine

router = APIRouter()


# Pydantic models for request/response
class WorkflowTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    template_data: Dict[str, Any]
    category: Optional[str] = "general"
    version: Optional[str] = "1.0.0"


class WorkflowTemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    template_data: Dict[str, Any]
    category: str
    version: str
    is_active: bool
    created_at: str
    updated_at: str


class WorkflowExecutionRequest(BaseModel):
    workflow_id: str
    input_data: Optional[Dict[str, Any]] = None


class WorkflowExecutionResponse(BaseModel):
    execution_id: str
    workflow_id: str
    status: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    execution_time_ms: Optional[int] = None


class WorkflowStatusResponse(BaseModel):
    execution_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None


class WorkflowLogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    step_id: Optional[str] = None


# Workflow template endpoints
@router.post("/api/workflows/templates", response_model=WorkflowTemplateResponse)
async def create_workflow_template(template: WorkflowTemplateCreate):
    """Create a new workflow template"""
    try:
        template_id = str(uuid4())

        template_data = {
            "id": template_id,
            "name": template.name,
            "description": template.description,
            "template_data": template.template_data,
            "category": template.category,
            "version": template.version,
            "is_active": True,
        }

        success = data_persistence.save_workflow_template(template_data)
        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to save workflow template"
            )

        # Get the saved template to return
        saved_template = data_persistence.get_workflow_template(template_id)
        if not saved_template:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve saved template"
            )

        return WorkflowTemplateResponse(**saved_template)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create workflow template: {str(e)}"
        )


@router.get("/api/workflows/templates", response_model=Dict[str, Any])
async def get_workflow_templates():
    """Get all workflow templates"""
    try:
        templates = data_persistence.get_all_workflow_templates()

        formatted_templates = []
        for template in templates:
            formatted_templates.append(WorkflowTemplateResponse(**template))

        return {
            "templates": formatted_templates,
            "total_templates": len(formatted_templates),
            "active_templates": len([t for t in formatted_templates if t.is_active]),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get workflow templates: {str(e)}"
        )


@router.get(
    "/api/workflows/templates/{template_id}", response_model=WorkflowTemplateResponse
)
async def get_workflow_template(template_id: str):
    """Get a specific workflow template"""
    try:
        template = data_persistence.get_workflow_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Workflow template not found")

        return WorkflowTemplateResponse(**template)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get workflow template: {str(e)}"
        )


@router.put(
    "/api/workflows/templates/{template_id}", response_model=WorkflowTemplateResponse
)
async def update_workflow_template(template_id: str, template: WorkflowTemplateCreate):
    """Update a workflow template"""
    try:
        # Check if template exists
        existing_template = data_persistence.get_workflow_template(template_id)
        if not existing_template:
            raise HTTPException(status_code=404, detail="Workflow template not found")

        template_data = {
            "id": template_id,
            "name": template.name,
            "description": template.description,
            "template_data": template.template_data,
            "category": template.category,
            "version": template.version,
            "is_active": existing_template["is_active"],  # Preserve active status
        }

        success = data_persistence.save_workflow_template(template_data)
        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to update workflow template"
            )

        # Get the updated template to return
        updated_template = data_persistence.get_workflow_template(template_id)
        if not updated_template:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve updated template"
            )

        return WorkflowTemplateResponse(**updated_template)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update workflow template: {str(e)}"
        )


@router.delete("/api/workflows/templates/{template_id}")
async def delete_workflow_template(template_id: str):
    """Delete a workflow template (soft delete by setting inactive)"""
    try:
        template = data_persistence.get_workflow_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Workflow template not found")

        # Soft delete by setting inactive
        template["is_active"] = False
        success = data_persistence.save_workflow_template(template)

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to delete workflow template"
            )

        return {"message": "Workflow template deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete workflow template: {str(e)}"
        )


# Workflow execution endpoints
@router.post("/api/workflows/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    execution_request: WorkflowExecutionRequest, background_tasks: BackgroundTasks
):
    """Execute a workflow"""
    try:
        # Check if template exists and is active
        template = data_persistence.get_workflow_template(execution_request.workflow_id)
        if not template:
            raise HTTPException(status_code=404, detail="Workflow template not found")

        if not template.get("is_active", True):
            raise HTTPException(
                status_code=400, detail="Workflow template is not active"
            )

        # Execute workflow in background
        execution_id = str(uuid4())

        # Create initial execution record
        execution_data = {
            "id": execution_id,
            "template_id": execution_request.workflow_id,
            "input_data": execution_request.input_data,
            "status": WorkflowStatus.RUNNING.value,
            "started_at": datetime.now().isoformat(),
        }
        data_persistence.save_workflow_execution(execution_data)

        # Execute workflow in background
        background_tasks.add_task(
            _execute_workflow_background,
            execution_request.workflow_id,
            execution_id,
            execution_request.input_data or {},
        )

        return WorkflowExecutionResponse(
            execution_id=execution_id,
            workflow_id=execution_request.workflow_id,
            status=WorkflowStatus.RUNNING.value,
            input_data=execution_request.input_data,
            started_at=execution_data["started_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to execute workflow: {str(e)}"
        )


async def _execute_workflow_background(
    workflow_id: str, execution_id: str, input_data: Dict[str, Any]
):
    """Background task to execute workflow"""
    try:
        result = await workflow_engine.execute_workflow(workflow_id, input_data)

        # Update execution record with result
        execution_data = {
            "id": execution_id,
            "template_id": workflow_id,
            "input_data": input_data,
            "output_data": result.get("result"),
            "status": result["status"],
            "completed_at": datetime.now().isoformat(),
        }
        data_persistence.save_workflow_execution(execution_data)

    except Exception as e:
        # Update execution record with error
        execution_data = {
            "id": execution_id,
            "template_id": workflow_id,
            "input_data": input_data,
            "status": WorkflowStatus.FAILED.value,
            "error_message": str(e),
            "completed_at": datetime.now().isoformat(),
        }
        data_persistence.save_workflow_execution(execution_data)


@router.get(
    "/api/workflows/executions/{execution_id}", response_model=WorkflowExecutionResponse
)
async def get_workflow_execution(execution_id: str):
    """Get workflow execution details"""
    try:
        execution = data_persistence.get_workflow_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Workflow execution not found")

        return WorkflowExecutionResponse(
            execution_id=execution["id"],
            workflow_id=execution["template_id"],
            status=execution["status"],
            input_data=execution.get("input_data"),
            output_data=execution.get("output_data"),
            error_message=execution.get("error_message"),
            started_at=execution["started_at"],
            completed_at=execution.get("completed_at"),
            execution_time_ms=execution.get("execution_time_ms"),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get workflow execution: {str(e)}"
        )


@router.get(
    "/api/workflows/executions/{execution_id}/status",
    response_model=WorkflowStatusResponse,
)
async def get_workflow_status(execution_id: str):
    """Get workflow execution status"""
    try:
        execution = data_persistence.get_workflow_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Workflow execution not found")

        # Get additional status from workflow engine if running
        progress = None
        if execution["status"] == WorkflowStatus.RUNNING.value:
            engine_status = workflow_engine.get_workflow_status(execution_id)
            if engine_status:
                progress = {
                    "current_step": "unknown",  # Would be populated from engine in real implementation
                    "total_steps": "unknown",
                    "progress_percentage": 0,
                }

        return WorkflowStatusResponse(
            execution_id=execution_id,
            status=execution["status"],
            started_at=execution["started_at"],
            completed_at=execution.get("completed_at"),
            error_message=execution.get("error_message"),
            progress=progress,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get workflow status: {str(e)}"
        )


@router.post("/api/workflows/executions/{execution_id}/cancel")
async def cancel_workflow_execution(execution_id: str):
    """Cancel a running workflow execution"""
    try:
        execution = data_persistence.get_workflow_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Workflow execution not found")

        if execution["status"] != WorkflowStatus.RUNNING.value:
            raise HTTPException(status_code=400, detail="Workflow is not running")

        success = await workflow_engine.cancel_workflow(execution_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to cancel workflow")

        return {"message": "Workflow cancellation requested"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to cancel workflow: {str(e)}"
        )


@router.get(
    "/api/workflows/executions/{execution_id}/logs",
    response_model=List[WorkflowLogEntry],
)
async def get_workflow_logs(execution_id: str, limit: int = 100):
    """Get workflow execution logs"""
    try:
        execution = data_persistence.get_workflow_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Workflow execution not found")

        logs = workflow_engine.get_workflow_logs(execution_id, limit)

        formatted_logs = []
        for log in logs:
            formatted_logs.append(WorkflowLogEntry(**log))

        return formatted_logs

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get workflow logs: {str(e)}"
        )


@router.get("/api/workflows/executions", response_model=Dict[str, Any])
async def get_workflow_executions(limit: int = 50, offset: int = 0):
    """Get workflow execution history"""
    try:
        # In a real implementation, this would query the database with pagination
        # For now, return basic execution list
        executions = []  # This would be populated from database

        return {
            "executions": executions,
            "total_executions": len(executions),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get workflow executions: {str(e)}"
        )


# Workflow validation endpoint
@router.post("/api/workflows/validate")
async def validate_workflow(template: WorkflowTemplateCreate):
    """Validate a workflow template"""
    try:
        # Basic validation checks
        errors = []

        # Check required fields
        if not template.name or not template.name.strip():
            errors.append("Workflow name is required")

        if not template.template_data:
            errors.append("Template data is required")

        # Check steps structure
        steps = template.template_data.get("steps", [])
        if not steps:
            errors.append("Workflow must contain at least one step")

        # Validate individual steps
        step_ids = set()
        for i, step_data in enumerate(steps):
            step_errors = _validate_step(step_data, i)
            if step_errors:
                errors.extend(step_errors)

            # Check for duplicate step IDs
            step_id = step_data.get("id")
            if step_id:
                if step_id in step_ids:
                    errors.append(f"Duplicate step ID: {step_id}")
                step_ids.add(step_id)

        # Check for circular dependencies
        dependency_errors = _check_circular_dependencies(steps)
        if dependency_errors:
            errors.extend(dependency_errors)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": [],  # Could add warnings for non-critical issues
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to validate workflow: {str(e)}"
        )


def _validate_step(step_data: Dict[str, Any], step_index: int) -> List[str]:
    """Validate a single workflow step"""
    errors = []

    if not step_data.get("id"):
        errors.append(f"Step {step_index}: ID is required")

    if not step_data.get("name"):
        errors.append(f"Step {step_data.get('id', step_index)}: Name is required")

    if not step_data.get("action"):
        errors.append(f"Step {step_data.get('id', step_index)}: Action is required")

    # Check if action is registered
    action = step_data.get("action")
    if action and action not in workflow_engine.actions:
        errors.append(
            f"Step {step_data.get('id', step_index)}: Unknown action '{action}'"
        )

    return errors


def _check_circular_dependencies(steps: List[Dict[str, Any]]) -> List[str]:
    """Check for circular dependencies in workflow steps"""
    # Simple implementation - in production, use proper graph cycle detection
    errors = []

    # Build dependency graph
    graph = {}
    for step in steps:
        step_id = step.get("id")
        if step_id:
            graph[step_id] = step.get("depends_on", [])

    # Check for self-dependencies
    for step_id, dependencies in graph.items():
        if step_id in dependencies:
            errors.append(f"Step {step_id} depends on itself")

    return errors


# Initialize sample workflows
@router.post("/api/workflows/initialize-samples")
async def initialize_sample_workflows():
    """Initialize sample workflow templates"""
    try:
        sample_templates = [
            {
                "id": "data-processing",
                "name": "Data Processing Pipeline",
                "description": "Process and transform data from multiple sources",
                "template_data": {
                    "steps": [
                        {
                            "id": "fetch-data",
                            "name": "Fetch Data",
                            "action": "http_request",
                            "parameters": {
                                "url": "https://api.example.com/data",
                                "method": "GET",
                            },
                        },
                        {
                            "id": "transform-data",
                            "name": "Transform Data",
                            "action": "transform_data",
                            "parameters": {
                                "template": "Processed: {{input}}",
                                "data": {"input": "{{fetch-data.body}}"},
                            },
                            "depends_on": ["fetch-data"],
                        },
                        {
                            "id": "save-result",
                            "name": "Save Result",
                            "action": "log",
                            "parameters": {
                                "message": "Data processing completed: {{transform-data}}",
                                "level": "info",
                            },
                            "depends_on": ["transform-data"],
                        },
                    ]
                },
                "category": "data-processing",
                "version": "1.0.0",
                "is_active": True,
            },
            {
                "id": "notification-workflow",
                "name": "Notification Workflow",
                "description": "Send notifications across multiple channels",
                "template_data": {
                    "steps": [
                        {
                            "id": "prepare-message",
                            "name": "Prepare Message",
                            "action": "set_variable",
                            "parameters": {
                                "name": "notification_message",
                                "value": "Hello from ATOM workflow!",
                            },
                        },
                        {
                            "id": "log-notification",
                            "name": "Log Notification",
                            "action": "log",
                            "parameters": {
                                "message": "Sending notification: {{notification_message}}",
                                "level": "info",
                            },
                            "depends_on": ["prepare-message"],
                        },
                        {
                            "id": "wait-delivery",
                            "name": "Wait for Delivery",
                            "action": "wait",
                            "parameters": {"seconds": 2},
                            "depends_on": ["log-notification"],
                        },
                    ]
                },
                "category": "notifications",
                "version": "1.0.0",
                "is_active": True,
            },
            {
                "id": "conditional-workflow",
                "name": "Conditional Workflow",
                "description": "Execute steps based on conditions",
                "template_data": {
                    "steps": [
                        {
                            "id": "check-condition",
                            "name": "Check Condition",
                            "action": "condition",
                            "parameters": {
                                "condition": "variables.get('should_execute', True)"
                            },
                        },
                        {
                            "id": "execute-if-true",
                            "name": "Execute if True",
                            "action": "log",
                            "parameters": {
                                "message": "Condition was true - executing step",
                                "level": "info",
                            },
                            "depends_on": ["check-condition"],
                        },
                        {
                            "id": "final-step",
                            "name": "Final Step",
                            "action": "log",
                            "parameters": {
                                "message": "Workflow completed",
                                "level": "info",
                            },
                            "depends_on": ["execute-if-true"],
                        },
                    ]
                },
                "category": "conditional",
                "version": "1.0.0",
                "is_active": True,
            },
        ]

        # Save sample templates
        created_templates = []
        for template_data in sample_templates:
            success = data_persistence.save_workflow_template(template_data)
            if success:
                created_templates.append(template_data["id"])

        return {
            "message": f"Sample workflows initialized: {len(created_templates)} templates created",
            "created_templates": created_templates,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize sample workflows: {str(e)}"
        )


# Helper function to get workflow execution
def get_workflow_execution(execution_id: str) -> Optional[Dict[str, Any]]:
    """Get workflow execution from database"""
    # This would be implemented in data_persistence
    # For now, return None as placeholder
    return None

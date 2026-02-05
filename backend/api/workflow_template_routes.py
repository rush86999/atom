import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.api_governance import require_governance, ActionComplexity
from core.base_routes import BaseAPIRouter
from core.database import get_db

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/workflow-templates", tags=["Workflow Templates"])

# Lazy import to avoid circular dependencies
def get_template_manager():
    from core.workflow_template_system import WorkflowTemplateManager
    return WorkflowTemplateManager()

class InstantiateRequest(BaseModel):
    workflow_name: str
    parameters: Dict[str, Any] = {}
    customizations: Optional[Dict[str, Any]] = None

class CreateTemplateRequest(BaseModel):
    name: str
    description: str
    category: str = "automation"
    complexity: str = "intermediate"
    tags: List[str] = []
    steps: List[Dict[str, Any]] = []

class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    inputs: Optional[List[Dict[str, Any]]] = None
    tags: Optional[List[str]] = None

@router.post("/")
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="create_template",
    feature="workflow"
)
async def create_template(
    request: CreateTemplateRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Create a new workflow template from the visual builder.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    - Workflow template creation is a moderate action
    - Requires INTERN maturity or higher
    """
    try:
        manager = get_template_manager()

        template_data = {
            "name": request.name,
            "description": request.description,
            "category": request.category,
            "complexity": request.complexity,
            "tags": request.tags,
            "steps": [
                {
                    "step_id": step.get("step_id", f"step_{i}"),
                    "name": step.get("name", f"Step {i}"),
                    "description": step.get("description", ""),
                    "step_type": step.get("step_type", "agent_execution"),
                    "parameters": step.get("parameters", []),
                    "depends_on": step.get("depends_on", [])
                }
                for i, step in enumerate(request.steps)
            ]
        }

        template = manager.create_template(template_data)

        logger.info(f"Template created: {template.template_id}")
        return {
            "status": "success",
            "template_id": template.template_id,
            "message": f"Template '{template.name}' created successfully"
        }

    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise router.internal_error(
            message="Failed to create template",
            details={"error": str(e)}
        )

@router.get("/", response_model=List[Dict[str, Any]])
async def list_templates(category: Optional[str] = None, limit: int = 50):
    """List all available workflow templates"""
    try:
        manager = get_template_manager()
        
        # Filter by category if provided
        if category:
            from core.workflow_template_system import TemplateCategory
            try:
                cat_enum = TemplateCategory(category)
            except ValueError:
                raise router.validation_error(
                    field="category",
                    message=f"Invalid category: {category}",
                    details={"provided_category": category}
                )
            templates = manager.list_templates(category=cat_enum, limit=limit)
        else:
            templates = manager.list_templates(limit=limit)
        
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "category": t.category.value,
                "complexity": t.complexity.value,
                "tags": t.tags,
                "usage_count": t.usage_count,
                "rating": t.rating,
                "is_featured": t.is_featured,
                "steps": [s.model_dump() if hasattr(s, 'model_dump') else s.__dict__ for s in t.steps]
            }
            for t in templates
        ]
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise router.internal_error(
            message="Failed to list templates",
            details={"error": str(e)}
        )

@router.get("/{template_id}")
async def get_template(template_id: str):
    """Get a specific template by ID"""
    manager = get_template_manager()
    template = manager.get_template(template_id)
    
    if not template:
        raise router.not_found_error("Template", template_id)
    
    return template.dict()

@router.put("/{template_id}")
async def update_template_endpoint(template_id: str, request: UpdateTemplateRequest):
    """Update an existing workflow template"""
    try:
        manager = get_template_manager()
        
        # Convert request model to dict, excluding None values
        updates = {k: v for k, v in request.dict().items() if v is not None}
        
        if not updates:
             raise router.validation_error(
                 field="updates",
                 message="No updates provided"
             )

        # Special handling for steps if provided (need to map format)
        if "steps" in updates:
            # We assume steps come in the same format as CreateRequest, 
            # so we might need to process them if the internal model expects differently.
            # However, workflow_template_system.py expects Pydantic models or dicts matching schema.
            # Let's clean up the steps just in case
            processed_steps = []
            for i, step in enumerate(updates["steps"]):
                 processed_steps.append({
                    "id": step.get("step_id", step.get("id", f"step_{i}")), # Map step_id -> id
                    "name": step.get("name", f"Step {i}"),
                    "description": step.get("description", ""),
                    "step_type": step.get("step_type", "action"),
                    "parameters": step.get("parameters", []),
                    "depends_on": step.get("depends_on", []),
                    "condition": step.get("condition"),
                    # Add other fields as needed
                 })
            updates["steps"] = processed_steps

        updated_template = manager.update_template(template_id, updates)
        
        return {
            "status": "success",
            "message": f"Template {template_id} updated",
            "template": updated_template.dict()
        }
        
    except ValueError as e:
        raise router.not_found_error(
            "Template",
            template_id,
            details={"reason": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to update template: {e}")
        raise router.internal_error(
            message="Failed to update template",
            details={"error": str(e)}
        )

@router.post("/{template_id}/instantiate")
async def instantiate_template(template_id: str, request: InstantiateRequest):
    """Create a runnable workflow from a template"""
    try:
        manager = get_template_manager()
        
        result = manager.create_workflow_from_template(
            template_id=template_id,
            workflow_name=request.workflow_name,
            template_parameters=request.parameters,
            customizations=request.customizations
        )
        
        return result
        
    except ValueError as e:
        raise router.validation_error(
            field="template_id",
            message=str(e),
            details={"template_id": template_id}
        )
    except Exception as e:
        logger.error(f"Failed to instantiate template: {e}")
        raise router.internal_error(
            message="Failed to instantiate template",
            details={"error": str(e)}
        )

@router.get("/search")
async def search_templates(query: str, limit: int = 20):
    """Search templates by text query"""
    manager = get_template_manager()
    templates = manager.search_templates(query, limit=limit)
    
    return [
        {
            "template_id": t.template_id,
            "name": t.name,
            "description": t.description,
            "category": t.category.value,
            "tags": t.tags
        }
        for t in templates
    ]

@router.post("/{template_id}/execute")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="execute_template",
    feature="workflow"
)
async def execute_template(
    template_id: str,
    parameters: Dict[str, Any] = {},
    request: Request = None,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Execute a workflow template immediately.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    - Workflow execution is a high-complexity action
    - Requires SUPERVISED maturity or higher
    """
    try:
        manager = get_template_manager()

        # 1. Instantiate the template
        workflow_data = manager.create_workflow_from_template(
            template_id=template_id,
            workflow_name=f"Execution of {template_id}",
            template_parameters=parameters
        )

        workflow_id = workflow_data.get("workflow_id")

        # 2. Execute via orchestrator
        import asyncio
        from advanced_workflow_orchestrator import get_orchestrator

        # Create execution context
        context = await get_orchestrator().execute_workflow(
            workflow_id,  # Use the instantiated workflow_id
            input_data=parameters,
            execution_context={"source": "visual_builder", "agent_id": agent_id}
        )

        logger.info(f"Template executed: {template_id} by agent {agent_id or 'system'}, workflow_id: {workflow_id}")
        return {
            "status": "success",
            "execution_id": context.workflow_id,
            "workflow_status": context.status.value,
            "message": f"Workflow executed. Status: {context.status.value}"
        }

    except ValueError as e:
        if "not found" in str(e).lower() and "template" in str(e).lower():
            raise router.not_found_error(
                "Template",
                template_id,
                details={"reason": str(e)}
            )
        raise router.validation_error(
            field="template_id",
            message=str(e),
            details={"template_id": template_id}
        )
    except Exception as e:
        logger.error(f"Failed to execute template: {e}")
        raise router.internal_error(
            message="Failed to execute template",
            details={"error": str(e)}
        )

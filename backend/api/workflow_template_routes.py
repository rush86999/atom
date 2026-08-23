import logging
from typing import Any, Dict, List, Optional
from fastapi import Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.workflow_security import require_workflow_executor_definition

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
    name: str = Field(..., min_length=1, description="Template name (must not be empty)")
    description: str
    category: str = "automation"
    complexity: str = "intermediate"
    tags: List[str] = []
    steps: List[Dict[str, Any]] = []

class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="Template name (must not be empty)")
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
    current_user: User = Depends(get_current_user),
    http_request: Request = None,
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
        from core.workflow_template_system import TemplateCategory, TemplateComplexity

        # R71: reject invalid category/complexity at the API boundary (422),
        # mirroring the category validation already done by list_templates.
        # Previously arbitrary strings were accepted and only failed later
        # inside the manager (or never, when mocked).
        try:
            TemplateCategory(request.category)
        except ValueError:
            raise router.validation_error(
                field="category",
                message=f"Invalid category: {request.category}",
                details={"provided_category": request.category}
            )
        try:
            TemplateComplexity(request.complexity)
        except ValueError:
            raise router.validation_error(
                field="complexity",
                message=f"Invalid complexity: {request.complexity}",
                details={"provided_complexity": request.complexity}
            )

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

    except HTTPException:
        # R71: re-raise our own validation errors (invalid category/complexity
        # -> 422) instead of the bare `except Exception` masking them as 500.
        raise
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise router.internal_error(
            message="Failed to create template"
        )

@router.get("/", response_model=List[Dict[str, Any]])
async def list_templates(category: Optional[str] = None, limit: int = 50, current_user: User = Depends(get_current_user)):
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
    except HTTPException:
        # R71: re-raise our own validation errors (invalid category -> 422).
        # Previously the bare `except Exception` swallowed the 422 raised
        # above and converted it into a 500 internal error.
        raise
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise router.internal_error(
            message="Failed to list templates"
        )

@router.get("/search")
async def search_templates(
    query: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Search templates by text query"""
    try:
        manager = get_template_manager()
        templates = manager.search_templates(query, limit=limit)
    except Exception as e:
        logger.error(f"Failed to search templates: {e}")
        raise router.internal_error(
            message="Failed to search templates"
        )

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

@router.get("/{template_id}")
async def get_template(template_id: str, current_user: User = Depends(get_current_user)):
    """Get a specific template by ID"""
    manager = get_template_manager()
    template = manager.get_template(template_id)
    
    if not template:
        raise router.not_found_error("Template", template_id)
    
    return template.dict()

@router.get("/{template_id}/readiness")
async def get_template_readiness(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """First-run friction killer: can this starter run *right now*?

    Personal starters declare integrations (``template.dependencies``); this
    checks them against the user's actual OAuth tokens so the UI can render a
    single "Connect Gmail" CTA instead of failing mid-workflow.
    """
    from core.models import IntegrationToken
    from core.workflow_ui_endpoints import _compute_readiness

    template = get_template_manager().get_template(template_id)
    if not template:
        raise router.not_found_error("Template", template_id)

    dependencies = list(template.dependencies or [])
    if not dependencies:
        return {"success": True, **_compute_readiness([], set())}

    token_query = db.query(IntegrationToken.provider).filter(
        IntegrationToken.user_id == current_user.id
    )
    if getattr(current_user, "tenant_id", None):
        token_query = token_query.filter(
            IntegrationToken.tenant_id == str(current_user.tenant_id)
        )
    connected = {p.lower() for (p,) in token_query.distinct().all()}
    return {"success": True, **_compute_readiness(dependencies, connected)}


@router.put("/{template_id}")
async def update_template_endpoint(template_id: str, request: UpdateTemplateRequest, current_user: User = Depends(get_current_user)):
    """Update an existing workflow template"""
    try:
        manager = get_template_manager()

        # MASS ASSIGNMENT FIX: Block sensitive fields from mass assignment
        # These fields should never be modifiable via user input
        BLOCKED_FIELDS = {
            'id', 'template_id', 'owner_id', 'author_id', 'user_id', 'workspace_id',
            'created_at', 'updated_at', 'created_by', 'modified_by',
            'is_public', 'is_featured', 'is_official', 'is_active',
            'version', 'usage_count', 'rating', 'category'
        }

        # Convert request model to dict, excluding None and blocked fields
        updates = {k: v for k, v in request.dict().items()
                   if v is not None and k not in BLOCKED_FIELDS}

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
        
    except HTTPException:
        # R71: re-raise our own validation errors (e.g. "No updates provided"
        # -> 422) instead of letting the bare `except Exception` below mask
        # them as 500 internal errors.
        raise
    except HTTPException:
        # R71: re-raise our own validation errors (e.g. "No updates provided"
        # -> 422) instead of the bare `except Exception` masking them as 500.
        raise
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
async def instantiate_template(template_id: str, request: InstantiateRequest, current_user: User = Depends(get_current_user)):
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
            message="Failed to instantiate template"
        )

@router.post("/{template_id}/import")
@require_governance(ActionComplexity.LOW, "import_template", "workflow")
async def import_template(
    template_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    body: Optional[Dict[str, Any]] = None
):
    """Import a template as a new workflow (Simplified Instantiation)"""
    try:
        manager = get_template_manager()
        template = manager.get_template(template_id)
        if not template:
             raise router.not_found_error("Template", template_id)

        result = manager.create_workflow_from_template(
            template_id=template_id,
            workflow_name=f"Imported {template.name}",
            template_parameters={}
        )
        
        return {
            "status": "success",
            "message": f"Template imported as '{result.get('workflow_name')}'",
            "workflow_id": result.get("workflow_id")
        }
        
    except ValueError as e:
        raise router.validation_error(
            field="template_id",
            message=str(e),
            details={"template_id": template_id}
        )
    except HTTPException:
        # R71: re-raise our own errors (template not found -> 404) instead of
        # masking them as 500 internal errors.
        raise
    except Exception as e:
        logger.error(f"Failed to import template: {e}")
        raise router.internal_error(
            message="Failed to import template"
        )

@router.post("/{template_id}/execute")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="execute_template",
    feature="workflow"
)
async def execute_template(
    template_id: str,
    parameters: Optional[Dict[str, Any]] = None,
    request: Request = None,
    current_user: User = Depends(get_current_user),
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
            template_parameters=parameters or {}
        )

        workflow_id = workflow_data.get("workflow_id")

        # R68: governance maturity (SUPERVISED+) is not a role gate — critical
        # MCP steps still require WORKFLOW_MANAGE (TEAM_LEAD+).
        await require_workflow_executor_definition(
            current_user, workflow_data.get("workflow_definition") or {}
        )

        # 2. Execute via orchestrator
        import asyncio
        from advanced_workflow_orchestrator import get_orchestrator

        # Create execution context
        context = await get_orchestrator().execute_workflow(
            workflow_id,  # Use the instantiated workflow_id
            input_data=parameters if parameters is not None else {},
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
    except HTTPException:
        # R68: the critical-step gate must reach the client as 403, not be
        # masked as an internal error.
        raise
    except Exception as e:
        logger.error(f"Failed to execute template: {e}")
        raise router.internal_error(
            message="Failed to execute template",
            details={"error": str(e)}
        )

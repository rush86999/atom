import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Governance feature flags
WORKFLOW_GOVERNANCE_ENABLED = os.getenv("WORKFLOW_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

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
async def create_template(request: CreateTemplateRequest, agent_id: Optional[str] = None):
    """
    Create a new workflow template from the visual builder.

    **Governance**: Requires INTERN+ maturity for template creation.
    """
    # Governance check for workflow template creation
    if WORKFLOW_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="create_template",
                resource_type="workflow_template",
                complexity=2  # MODERATE - workflow creation
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for create_template by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

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

        logger.info(f"Template created: {template.template_id} by agent {agent_id or 'system'}")
        return {
            "status": "success",
            "template_id": template.template_id,
            "message": f"Template '{template.name}' created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{template_id}")
async def get_template(template_id: str):
    """Get a specific template by ID"""
    manager = get_template_manager()
    template = manager.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    
    return template.dict()

@router.put("/{template_id}")
async def update_template_endpoint(template_id: str, request: UpdateTemplateRequest):
    """Update an existing workflow template"""
    try:
        manager = get_template_manager()
        
        # Convert request model to dict, excluding None values
        updates = {k: v for k, v in request.dict().items() if v is not None}
        
        if not updates:
             raise HTTPException(status_code=400, detail="No updates provided")

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
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to instantiate template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
async def execute_template(template_id: str, parameters: Dict[str, Any] = {}, agent_id: Optional[str] = None):
    """
    Execute a workflow template immediately.

    **Governance**: Requires SUPERVISED+ maturity for workflow execution.
    """
    # Governance check for workflow execution
    if WORKFLOW_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="execute_template",
                resource_type="workflow_execution",
                complexity=3  # HIGH - workflow execution
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for execute_template by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

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

    except HTTPException:
        raise
    except ValueError as e:
        if "not found" in str(e).lower() and "template" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to execute template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

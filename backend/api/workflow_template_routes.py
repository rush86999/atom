import logging
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.workflow_security import require_workflow_executor_definition
from core.workflow_template_write_service import (
    create_template as _create_workflow_template_decision,
    update_template as _update_workflow_template_decision,
)
from core.security_dependencies import require_permission
from core.rbac_service import Permission

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


def _raise_workflow_template_decision(result: Dict[str, Any]) -> None:
    """Map the verified template-decision envelope to a safe HTTP error."""
    status_value = str(result.get("status") or "")
    if status_value == "refused":
        raise HTTPException(
            status_code=int(result.get("http_status") or 422),
            detail={
                "error": {
                    "code": result.get("error_code") or "VALIDATION_ERROR",
                    "message": result.get("error") or "Request refused",
                },
                "field": result.get("field"),
                "verification": result.get("verification"),
            },
        )
    if status_value == "conflict":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": result.get("error_code") or "STALE_TARGET",
                    "message": result.get("error") or "Conflict",
                },
                "verification": result.get("verification"),
            },
        )
    if status_value == "not_applied":
        raise HTTPException(
            status_code=int(result.get("http_status") or 409),
            detail={
                "error": {
                    "code": result.get("error_code")
                    or "WORKFLOW_TEMPLATE_TRANSACTION_ROLLED_BACK",
                    "message": result.get("error")
                    or "The workflow-template decision did not apply.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
            },
        )
    if status_value in ("committed_unverified", "effect_unknown"):
        code = (
            "WORKFLOW_TEMPLATE_EFFECT_UNKNOWN"
            if status_value == "effect_unknown"
            else "WORKFLOW_TEMPLATE_COMMITTED_UNVERIFIED")
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": code,
                    "message": result.get("message")
                    or "The workflow-template outcome is uncertain.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
                "target_id": result.get("target_id"),
            },
        )


@router.post(
    "/",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))],
)
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="create_template",
    feature="workflow"
)
async def create_template(
    request: CreateTemplateRequest,
    operation_id: Optional[str] = None,
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

        result = _create_workflow_template_decision(
            db,
            actor=current_user,
            payload=template_data,
            operation_id=operation_id,
            manager=manager,
        )
        _raise_workflow_template_decision(result)
        data = result.get("data") or {}
        template_id = data.get("template_id")

        logger.info(f"Template created: {template_id}")
        return {
            "status": "success",
            "template_id": template_id,
            "message": f"Template '{request.name}' created successfully",
            "verification": data.get("verification"),
            "operation_id": result.get("operation_id"),
            "audit_id": result.get("audit_id"),
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

@router.get(
    "/",
    response_model=List[Dict[str,
    Any]],
    dependencies=[Depends(require_permission(Permission.WORKFLOW_VIEW))],
)
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

@router.get(
    "/search",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_VIEW))],
)
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

@router.get(
    "/{template_id}",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_VIEW))],
)
async def get_template(template_id: str, current_user: User = Depends(get_current_user)):
    """Get a specific template by ID"""
    manager = get_template_manager()
    template = manager.get_template(template_id)
    
    if not template:
        raise router.not_found_error("Template", template_id)
    
    return template.dict()

@router.get(
    "/{template_id}/readiness",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_VIEW))],
)
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


@router.put(
    "/{template_id}",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))],
)
async def update_template_endpoint(
    template_id: str,
    request: UpdateTemplateRequest,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
        updates = {k: v for k, v in request.model_dump().items()
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

        result = _update_workflow_template_decision(
            db,
            actor=current_user,
            template_id=template_id,
            updates=updates,
            operation_id=operation_id,
            manager=manager,
        )
        _raise_workflow_template_decision(result)
        data = result.get("data") or {}

        return {
            "status": "success",
            "message": f"Template {template_id} updated",
            "template": data.get("template"),
            "verification": data.get("verification"),
            "operation_id": result.get("operation_id"),
            "audit_id": result.get("audit_id"),
        }

    except HTTPException:
        # R71: re-raise our own validation errors (e.g. "No updates provided"
        # -> 422) instead of letting the bare `except Exception` below mask
        # them as 500 internal errors.
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

@router.post(
    "/{template_id}/instantiate",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))],
)
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

def _persist_imported_workflow(
    manager,
    *,
    template,
    workflow_name: str,
    author_email: Optional[str],
    template_parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Instantiate a template AND persist it as a private editable template copy.

    Previously ``import_template`` generated a workflow definition and threw it
    away — ``workflow_id`` pointed at nothing queryable, so the editor's
    ``GET /{template_id}`` 404'd and the post-import deep link dead-ended.
    Persisting through ``create_template`` makes the imported id resolvable by
    the same surface the editor reads (file-backed, survives restarts).
    """
    result = manager.create_workflow_from_template(
        template_id=template.template_id,
        workflow_name=workflow_name,
        template_parameters=template_parameters or {},
        # Import creates a draft; the editor collects required run values
        # later. Only explicit values/defaults are applied here, while
        # instantiate/execute keep the strict default.
        require_all_inputs=False,
    )
    workflow_def = result.get("workflow_definition") or {}

    # Generated steps carry parameters under "input_parameters"; the
    # TemplateStep model expects "parameters". Remap so edits keep param data.
    steps = []
    for step in workflow_def.get("steps", []):
        step = dict(step)
        params = step.pop("input_parameters", None)
        if params is not None:
            step["parameters"] = params
        steps.append(step)

    def _enum_value(value):
        return value.value if hasattr(value, "value") else str(value)

    imported = manager.create_template({
        "template_id": result["workflow_id"],
        "name": workflow_name,
        "description": template.description,
        "category": _enum_value(template.category),
        "complexity": _enum_value(template.complexity),
        "tags": ["imported"] + list(template.tags or []),
        "author": author_email or "import",
        "is_public": False,
        "steps": steps,
        "inputs": [p.model_dump() for p in template.inputs],
    })
    return {
        "workflow_id": imported.template_id,
        "workflow_name": imported.name,
        "editor_url": f"/workflows/editor/{imported.template_id}",
    }


@router.post(
    "/{template_id}/import",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_MANAGE))],
)
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

        result = _persist_imported_workflow(
            manager,
            template=template,
            workflow_name=f"Imported {template.name}",
            author_email=getattr(current_user, "email", None),
            template_parameters=body if isinstance(body, dict) else {},
        )

        return {
            "status": "success",
            "message": f"Template imported as '{result.get('workflow_name')}'",
            "workflow_id": result.get("workflow_id"),
            "editor_url": result.get("editor_url")
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

@router.get(
    "/executions/{execution_id}/status",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_VIEW))],
)
async def get_execution_status(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Post-run loop closure: did the execution I just started work?

    Matches either the persisted ``execution_id`` or the ``workflow_id`` the
    execute endpoint hands back, so callers can poll with whatever they got.
    """
    from core.models import WorkflowExecution

    row = (
        db.query(WorkflowExecution)
        .filter(
            (WorkflowExecution.execution_id == execution_id)
            | (WorkflowExecution.workflow_id == execution_id)
        )
        .filter(_execution_access_filter(current_user))
        .order_by(WorkflowExecution.created_at.desc())
        .first()
    )
    if not row:
        raise router.not_found_error("Execution", execution_id)

    return {
        "success": True,
        "execution_id": row.execution_id,
        "workflow_id": row.workflow_id,
        "status": row.status,
        "error": row.error,
        "started_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def _safe_json_loads(raw):
    """Parse a JSON Text column defensively — legacy rows may hold anything."""
    import json as _json

    if not raw:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return _json.loads(raw)
    except Exception:  # noqa: BLE001
        return None


_RESULT_AI_KEYS = ("agent_response", "provider", "model")
_RESULT_AI_WRAPPER_SERVICE = "ai"
_RESULT_AI_WRAPPER_ACTIONS = ("summarize", "generate_content")
_RESULT_MAX_STEPS = 100
_RESULT_MAX_OUTPUTS = 50
_RESULT_MAX_TEXT = 8000
_RESULT_MAX_STEP_ID = 200
_RESULT_MAX_STATUS = 100
_RESULT_MAX_STEP_TYPE = 100
_RESULT_MAX_EFFECT_ID = 200
_RESULT_MAX_SUBTASKS = 100
_RESULT_EFFECT_GOAL_SERVICE = "goal_management"
_RESULT_EFFECT_GOAL_ACTION = "create_goal"
_RESULT_EFFECT_NOTIFICATION_SERVICE = "workflow_notification"
_RESULT_EFFECT_NOTIFICATION_ACTION = "notify_caller"
_RESULT_EFFECT_GOAL_VERIFICATION_STATUSES = ("verified", "already_applied")

# Leading punctuation commonly produced by quoting or light markdown around a
# path token in prose (e.g. ``read '/Users/alice/x'`` or ``(`/tmp/x`)``).
_LOCAL_PATH_TOKEN_LEADING = "\"'`([{<*_~>#-•"


def _execution_projection_failure() -> None:
    """Public, non-leaking failure for an unreadable/unprojectable result."""
    raise HTTPException(
        status_code=409,
        detail={
            "error": "execution_result_unavailable",
            "message": "the persisted execution result could not be projected "
                       "safely",
        },
    )


def _bounded_text(value: Any, limit: int) -> Optional[str]:
    """Keep only bounded string values; never stringify structured data."""
    if not isinstance(value, str):
        return None
    return value[:limit]


def _project_verified_ai_result(value: Any) -> Dict[str, str]:
    """Project only the verified AI result envelope.

    The normal WorkflowEngine persists
    ``{"result": {"result": {"agent_response": ..., "provider": ...,
    "model": ...}}}``. The generic AI engine persists
    ``{"service": "ai", "action": ..., "status": "success",
    "result": {"agent_response": ..., "provider": ..., "model": ..., ...}}``.
    Only the allowlisted string fields are carried through; the wrapper's
    metadata, arbitrary keys, and legacy string ``result`` are never exposed.
    Any other shape is refused rather than exposed as an empty success.
    """
    if not isinstance(value, dict):
        _execution_projection_failure()
    wrapper = value.get("result")
    if not isinstance(wrapper, dict):
        _execution_projection_failure()
    if value.get("service") == _RESULT_AI_WRAPPER_SERVICE:
        if (value.get("status") != "success"
                or value.get("action") not in _RESULT_AI_WRAPPER_ACTIONS
                or wrapper.get("status") != "success"):
            _execution_projection_failure()
        business = wrapper
    else:
        business = wrapper.get("result")
    if not isinstance(business, dict):
        _execution_projection_failure()

    projected: Dict[str, str] = {}
    for key in _RESULT_AI_KEYS:
        item = business.get(key)
        if item is None:
            continue
        if not isinstance(item, str) or len(item) > _RESULT_MAX_TEXT:
            _execution_projection_failure()
        projected[key] = item
    if not projected.get("agent_response"):
        _execution_projection_failure()
    return projected


def _project_exact_effect_id(value: Any) -> str:
    """Keep an effect id exactly as persisted, never truncating or coercing it."""
    if (not isinstance(value, str) or not value
            or len(value) > _RESULT_MAX_EFFECT_ID):
        _execution_projection_failure()
    return value


def _project_effect_success_result(value: Dict[str, Any]) -> Dict[str, Any]:
    """Return the result object of a successful effect wrapper only."""
    if value.get("status") != "success":
        _execution_projection_failure()
    result = value.get("result")
    if not isinstance(result, dict):
        _execution_projection_failure()
    return result


def _project_goal_management_result(value: Dict[str, Any]) -> Dict[str, Any]:
    """Project the audited create_goal receipt without its goal text or plan."""
    result = _project_effect_success_result(value)
    goal = result.get("goal")
    if not isinstance(goal, dict):
        _execution_projection_failure()
    goal_id = _project_exact_effect_id(goal.get("id"))
    audit_id = _project_exact_effect_id(goal.get("audit_id"))
    verification = goal.get("verification")
    if not isinstance(verification, dict):
        _execution_projection_failure()
    verification_status = verification.get("status")
    if (not isinstance(verification_status, str)
            or verification_status
            not in _RESULT_EFFECT_GOAL_VERIFICATION_STATUSES):
        _execution_projection_failure()
    if verification.get("effect") != "committed":
        _execution_projection_failure()
    if verification.get("audit_id") != audit_id:
        _execution_projection_failure()
    subtasks = result.get("subtasks")
    if (not isinstance(subtasks, list)
            or len(subtasks) > _RESULT_MAX_SUBTASKS):
        _execution_projection_failure()
    return {
        "goal_id": goal_id,
        "audit_id": audit_id,
        "verification_status": verification_status,
        "subtask_count": len(subtasks),
    }


def _project_workflow_notification_result(
        value: Dict[str, Any]) -> Dict[str, Any]:
    """Project only the committed in-app notification receipt."""
    result = _project_effect_success_result(value)
    notification_id = _project_exact_effect_id(
        result.get("notification_id"))
    created = result.get("created")
    if (not isinstance(created, bool)
            or result.get("emailed") is not False):
        _execution_projection_failure()
    return {
        "notification_id": notification_id,
        "committed": True,
    }


def _project_verified_output_result(value: Any) -> Dict[str, Any]:
    """Dispatch only the known durable success wrappers to safe projections."""
    if not isinstance(value, dict):
        _execution_projection_failure()
    service = value.get("service")
    action = value.get("action")
    if (service == _RESULT_EFFECT_GOAL_SERVICE
            or action == _RESULT_EFFECT_GOAL_ACTION):
        if (service != _RESULT_EFFECT_GOAL_SERVICE
                or action != _RESULT_EFFECT_GOAL_ACTION):
            _execution_projection_failure()
        return _project_goal_management_result(value)
    if (service == _RESULT_EFFECT_NOTIFICATION_SERVICE
            or action == _RESULT_EFFECT_NOTIFICATION_ACTION):
        if (service != _RESULT_EFFECT_NOTIFICATION_SERVICE
                or action != _RESULT_EFFECT_NOTIFICATION_ACTION):
            _execution_projection_failure()
        return _project_workflow_notification_result(value)
    return _project_verified_ai_result(value)


def _stored_result_present(raw: Any) -> bool:
    if raw is None:
        return False
    if isinstance(raw, str):
        return bool(raw.strip())
    if isinstance(raw, (dict, list)):
        return bool(raw)
    return True


def _text_has_embedded_local_path(value: str, pattern) -> bool:
    """Detect a local-path token embedded in bounded projected prose.

    ``_EXPORT_LOCAL_PATH`` is anchored for whole values, so a response such as
    ``read /Users/alice/private/report.txt`` slips past the shared scanner.
    Apply that same pattern to whitespace-delimited tokens after stripping
    leading quotes/markdown punctuation.
    """
    for token in value.split():
        candidate = token.lstrip(_LOCAL_PATH_TOKEN_LEADING)
        if candidate and pattern.match(candidate):
            return True
    return False


def _project_normal_execution_results(row: Any):
    """Project the normal WorkflowEngine ``row.outputs``/``row.steps`` shape.

    Returns ``(steps, outputs)`` or ``None`` when the row carries no stored
    result at all (e.g. still running). Malformed, unsupported, unsafe or
    oversized stored fields raise one fixed public error instead of falling
    back to raw input/context or pretending the missing result succeeded.
    """
    outputs_present = _stored_result_present(getattr(row, "outputs", None))
    steps_present = _stored_result_present(getattr(row, "steps", None))
    if not outputs_present and not steps_present:
        return None

    raw_outputs = _safe_json_loads(getattr(row, "outputs", None))
    raw_steps = _safe_json_loads(getattr(row, "steps", None))
    if outputs_present and not isinstance(raw_outputs, dict):
        _execution_projection_failure()
    if steps_present and not isinstance(raw_steps, dict):
        _execution_projection_failure()
    outputs_raw = raw_outputs if isinstance(raw_outputs, dict) else {}
    steps_raw = raw_steps if isinstance(raw_steps, dict) else {}

    if (len(outputs_raw) > _RESULT_MAX_OUTPUTS
            or len(steps_raw) > _RESULT_MAX_STEPS):
        _execution_projection_failure()

    # Persisted JSON object keys are strings. Validate every step id before
    # building any output, and never truncate one (that could merge receipts).
    for source in (steps_raw, outputs_raw):
        for step_id in source:
            if (not isinstance(step_id, str) or not step_id
                    or len(step_id) > _RESULT_MAX_STEP_ID):
                _execution_projection_failure()

    ordered_ids: List[str] = []
    seen = set()
    for source in (steps_raw, outputs_raw):
        for step_id in source:
            if step_id not in seen:
                seen.add(step_id)
                ordered_ids.append(step_id)
    if len(ordered_ids) > _RESULT_MAX_STEPS:
        _execution_projection_failure()

    steps = []
    status_by_id: Dict[str, Optional[str]] = {}
    for step_id in ordered_ids:
        raw_step = steps_raw.get(step_id)
        if step_id in steps_raw and not isinstance(raw_step, dict):
            _execution_projection_failure()
        raw_output = outputs_raw.get(step_id)
        status = raw_step.get("status") if isinstance(raw_step, dict) else None
        if not status and isinstance(raw_output, dict):
            status = raw_output.get("status")
        status = _bounded_text(status, _RESULT_MAX_STATUS)
        step_type = (raw_step.get("step_type")
                     if isinstance(raw_step, dict) else None)
        status_by_id[step_id] = status
        steps.append({
            "step_id": step_id,
            "step_type": _bounded_text(step_type, _RESULT_MAX_STEP_TYPE),
            "status": status,
            "notes": None,
        })

    outputs = {}
    for step_id in ordered_ids:
        if step_id not in outputs_raw:
            continue
        raw_output = outputs_raw[step_id]
        if not isinstance(raw_output, dict):
            _execution_projection_failure()
        status = raw_output.get("status")
        if status is None:
            status = status_by_id.get(step_id)
        outputs[step_id] = {
            "status": _bounded_text(status, _RESULT_MAX_STATUS),
            "result": _project_verified_output_result(raw_output),
        }

    # Scan only the small projected response — never the raw stored fields.
    try:
        from core.workflow_endpoints import (
            _EXPORT_LOCAL_PATH,
            _export_sensitive_fields,
        )
    except Exception:  # noqa: BLE001
        _execution_projection_failure()
    projected_response = {"steps": steps, "outputs": outputs or None}
    if _export_sensitive_fields(projected_response, path="results"):
        _execution_projection_failure()
    for output in outputs.values():
        answer = (output.get("result") or {}).get("agent_response")
        if (isinstance(answer, str)
                and _text_has_embedded_local_path(
                    answer, _EXPORT_LOCAL_PATH)):
            _execution_projection_failure()

    return steps, (outputs or None)


def _execution_access_filter(current_user: User):
    """R89: scope execution reads to their owner (or the caller's tenant for
    legacy unattributed rows).

    WorkflowExecution rows carry user_id/owner_id/tenant_id but the status and
    results endpoints matched on id alone — any authenticated user could read
    another user's run outputs (business data), step history, and errors.
    Rule: your own runs (user_id or owner_id), plus pre-R89 rows with no
    identity at all ONLY when they are also un-tenanted or tenanted to the
    caller — cross-tenant legacy rows stay hidden.
    """
    from sqlalchemy import or_

    from core.models import WorkflowExecution

    uid = str(current_user.id)
    caller_tenant = str(getattr(current_user, "tenant_id", None) or "")
    own = or_(
        WorkflowExecution.user_id == uid,
        WorkflowExecution.owner_id == uid,
    )
    # Unattributed rows (pre-R89, never stamped): tenant-stamped ones stay
    # within their tenant; fully anonymous rows are visible only to
    # tenant-less callers (pure local-dev legacy). Anonymous rows belong to
    # no one — not to everyone.
    if caller_tenant:
        legacy_unattributed = (
            WorkflowExecution.user_id.is_(None)
            & WorkflowExecution.owner_id.is_(None)
            & (WorkflowExecution.tenant_id == caller_tenant)
        )
    else:
        legacy_unattributed = (
            WorkflowExecution.user_id.is_(None)
            & WorkflowExecution.owner_id.is_(None)
            & WorkflowExecution.tenant_id.is_(None)
        )
    return or_(own, legacy_unattributed)


@router.get(
    "/executions/{execution_id}/results",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_VIEW))],
)
async def get_execution_results(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step-level results for a finished/running execution.

    Reads the orchestrator-persisted ``context`` blob (variables + results +
    execution_history). Capped so a runaway run can't blow up the response.
    """
    from core.models import WorkflowExecution

    row = (
        db.query(WorkflowExecution)
        .filter(
            (WorkflowExecution.execution_id == execution_id)
            | (WorkflowExecution.workflow_id == execution_id)
        )
        .filter(_execution_access_filter(current_user))
        .order_by(WorkflowExecution.created_at.desc())
        .first()
    )
    if not row:
        raise router.not_found_error("Execution", execution_id)

    context = _safe_json_loads(row.context)
    if not isinstance(context, dict):
        context = {}

    if "results" not in context and "execution_history" not in context:
        # A normal scoped WorkflowEngine execution stores its completed step
        # output/status in row.outputs/row.steps, not in the orchestrator
        # context. Project that shape only when the orchestrator result fields
        # are absent, so generated executions keep the exact legacy shape.
        projected = _project_normal_execution_results(row)
        if projected is not None:
            steps, outputs = projected
            return {
                "success": True,
                "execution_id": row.execution_id,
                "status": row.status,
                "error": row.error,
                "steps": steps,
                "outputs": outputs,
            }

    raw_history = context.get("execution_history") or []
    steps = []
    for entry in raw_history[:100]:
        if not isinstance(entry, dict):
            continue
        steps.append({
            "step_id": entry.get("step_id") or entry.get("step"),
            "step_type": entry.get("step_type"),
            "status": entry.get("status"),
            "notes": (str(entry.get("notes"))[:200] if entry.get("notes") else None),
        })

    raw_outputs = context.get("results")
    outputs = raw_outputs if isinstance(raw_outputs, dict) else None
    if outputs and len(outputs) > 50:
        outputs = dict(list(outputs.items())[:50])

    return {
        "success": True,
        "execution_id": row.execution_id,
        "status": row.status,
        "error": row.error,
        "steps": steps,
        "outputs": outputs,
    }


@router.post(
    "/{template_id}/execute",
    dependencies=[Depends(require_permission(Permission.WORKFLOW_RUN))],
)
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
    agent_id: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
):
    """
    Execute a workflow template immediately.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    - Workflow execution is a high-complexity action
    - Requires SUPERVISED maturity or higher
    """
    try:
        manager = get_template_manager()

        # Select the catalog row once. Both the native orchestrator path and
        # the canonical dispatch path below use this exact manager-selected
        # record; the canonical path must not re-resolve the id in another
        # store (workflows.json / DB templates).
        template = manager.get_template(template_id)

        # Stock invoice launch: the server-known catalog id takes the shared
        # admission path. Visibility was already decided by the catalog
        # lookup above and RBAC stays on the route dependency. Malformed stock
        # input is refused here before any generic instantiation.
        # (Matches core.workflow_endpoints.STOCK_INVOICE_LAUNCH_WORKFLOW_ID.)
        if template and template_id == "htn_invoice_followup":
            from core.workflow_endpoints import run_stock_invoice_launch

            return await run_stock_invoice_launch(
                current_user=current_user,
                request=request,
                body=parameters,
                validate_executor=require_workflow_executor_definition,
            )

        # 1. Instantiate the template (validates required inputs and keeps the
        # native editor contract). The generated id is only used by the
        # native orchestrator path.
        workflow_data = manager.create_workflow_from_template(
            template_id=template_id,
            workflow_name=f"Execution of {template_id}",
            template_parameters=parameters or {}
        )

        workflow_id = workflow_data.get("workflow_id")

        # R68: governance maturity (SUPERVISED+) is not a role gate — critical
        # MCP steps still require WORKFLOW_MANAGE (TEAM_LEAD+). This checks
        # the instantiated definition; the canonical branch below re-checks
        # the canonical step contract it will actually dispatch.
        await require_workflow_executor_definition(
            current_user, workflow_data.get("workflow_definition") or {}
        )

        # Truthful admission: inspect the catalog template's own bindings
        # before registering anything with an engine. Unsupported business
        # steps used to be mapped to API_CALL and reported as completed
        # simulations. Drafts/imports stay editable; only execution is
        # refused.
        from core.workflow_template_preflight import (
            TemplateExecutionBlocker,
            _clean_binding,
            _engine_services,
            blockers_detail,
            normalize_orchestrator_step_type,
            preflight_template_steps,
        )

        template_steps = getattr(template, "steps", []) or []
        orchestrator_blockers = preflight_template_steps(
            template_steps,
            target="orchestrator",
        )

        canonical_definition: Optional[Dict[str, Any]] = None
        if orchestrator_blockers:
            # Native orchestrator dispatch stays first for compatible shapes.
            # Only a template containing at least one orchestrator simulator
            # (API_CALL) can need canonical dispatch at all. If none of the
            # refusals is a simulator, these are missing/unknown/design-time
            # steps that canonical cannot invent either — refuse immediately.
            if not any(
                blocker.code == "simulated_api_call"
                for blocker in orchestrator_blockers
            ):
                raise HTTPException(
                    status_code=422,
                    detail=blockers_detail(orchestrator_blockers),
                )
            if template is None:
                raise HTTPException(
                    status_code=422,
                    detail=blockers_detail(orchestrator_blockers),
                )

            from core.workflow_template_system import (
                normalize_template_execution_definition,
            )

            canonical_definition = normalize_template_execution_definition(
                template)
            canonical_blockers = list(preflight_template_steps(
                canonical_definition.get("steps") or [],
                target="workflow_engine",
            ))

            # Only real built-in service bindings with proven registry
            # support may take the canonical path. A catalog-only external
            # service is the Workflows-list route's concern, not an implicit
            # editor fallback.
            builtin_services = set(_engine_services())
            for step in canonical_definition.get("steps") or []:
                if str(step.get("type") or "").strip().lower() == "trigger":
                    continue
                service = _clean_binding(step.get("service"))
                if service and service not in builtin_services:
                    canonical_blockers.append(TemplateExecutionBlocker(
                        step_id=str(step.get("id") or "template"),
                        step_name=str(step.get("name") or step.get("id")
                                       or "template"),
                        code="service_not_available",
                        reason=(
                            f"service '{service}' is not in the canonical "
                            "engine's built-in registry; the editor does not "
                            "auto-dispatch external/catalog-only fallbacks"
                        ),
                    ))

            if canonical_blockers:
                # The candidate path's full preflight is the truthful answer:
                # it reports every step the canonical engine cannot run and
                # nothing is registered or started.
                raise HTTPException(
                    status_code=422,
                    detail=blockers_detail(canonical_blockers),
                )

        if canonical_definition is not None:
            # Canonical dispatch uses the same real file-backed definition
            # and durable engine as the Workflows-list route. Validate the
            # graph and the canonical critical-step contract before starting
            # anything, then freeze the authenticated caller's scope into the
            # durable run.
            from core.workflow_endpoints import _validate_workflow_dag

            _validate_workflow_dag(canonical_definition)
            await require_workflow_executor_definition(
                current_user, canonical_definition)

            from core.workflow_engine import get_workflow_engine

            if background_tasks is None:
                background_tasks = BackgroundTasks()

            execution_id = await get_workflow_engine().start_workflow(
                canonical_definition,
                parameters or {},
                background_tasks,
                scope={
                    "workspace_id": getattr(
                        current_user, "workspace_id", None),
                    "tenant_id": getattr(current_user, "tenant_id", None),
                    "user_id": getattr(current_user, "id", None),
                },
            )

            logger.info(
                f"Template executed via canonical engine: {template_id} "
                f"by agent {agent_id or 'system'}, "
                f"execution_id: {execution_id}")
            return {
                "status": "success",
                "execution_id": execution_id,
                "workflow_status": "running",
                "message": "Workflow started. Status: running",
            }

        # 2. Register the instantiated definition with the orchestrator, then
        # execute it. create_workflow_from_template returns a definition, but
        # the orchestrator's registry is a separate in-memory store; without
        # this registration execute_workflow saw only the generated id and
        # raised "not found in registry or templates".
        from advanced_workflow_orchestrator import (
            WorkflowDefinition,
            WorkflowStep,
            WorkflowStepType,
            get_orchestrator,
        )

        orchestrator = get_orchestrator()
        definition = workflow_data.get("workflow_definition") or {}
        raw_steps = [dict(step) for step in (definition.get("steps") or [])]
        reg_steps = []
        for index, step in enumerate(raw_steps):
            # Share the preflight's normalization so admission and dispatch
            # agree on which steps lower to the API_CALL simulator.
            step_type = WorkflowStepType(
                normalize_orchestrator_step_type(step.get("step_type")))
            raw_params = step.get("parameters")
            if raw_params is None:
                raw_params = step.get("input_parameters")
            step_params = raw_params if isinstance(raw_params, dict) else {}
            if isinstance(raw_params, list):
                step_params = {
                    str(p.get("name")): p.get("default_value")
                    for p in raw_params if isinstance(p, dict) and p.get("name")
                }
            # Keep the template's declared binding visible to the
            # orchestrator's generic API dispatcher without overriding an
            # explicit parameter value.
            if step.get("service") and "service" not in step_params:
                step_params = {**step_params, "service": step["service"]}
            if step.get("action") and "action" not in step_params:
                step_params = {**step_params, "action": step["action"]}
            next_steps = list(step.get("next_steps") or [])
            if not next_steps and index + 1 < len(raw_steps):
                next_steps = [str(raw_steps[index + 1].get("step_id")
                                  or raw_steps[index + 1].get("id"))]
            reg_steps.append(WorkflowStep(
                step_id=str(step.get("step_id") or step.get("id")),
                step_type=step_type,
                description=str(step.get("description")
                                or step.get("name") or "template step"),
                parameters=step_params,
                next_steps=next_steps,
            ))
        if reg_steps:
            orchestrator.register_workflow(WorkflowDefinition(
                workflow_id=workflow_id,
                name=definition.get("name") or f"Execution of {template_id}",
                description=definition.get("description") or "",
                steps=reg_steps,
                start_step=reg_steps[0].step_id,
            ))

        # Create execution context — R89: stamp the caller's identity so the
        # run is attributable and the status/results reads can scope to it.
        context = await orchestrator.execute_workflow(
            workflow_id,  # Use the instantiated/registered workflow_id
            input_data=parameters if parameters is not None else {},
            execution_context={
                "source": "visual_builder",
                "agent_id": agent_id,
                "user_id": str(current_user.id),
                **(
                    {"tenant_id": str(current_user.tenant_id)}
                    if getattr(current_user, "tenant_id", None) else {}
                ),
            }
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

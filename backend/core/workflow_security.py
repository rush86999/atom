"""Shared workflow-trigger security gates (R67 + R68).

Workflows whose steps execute critical MCP tools (local machine exec, browser
automation, email/messaging) run the same tool set the agent governance layer
gates to AUTONOMOUS maturity (``core/mcp_service.py`` critical_tools). Every
workflow trigger path must therefore gate those steps to ``WORKFLOW_MANAGE``
(TEAM_LEAD+), mirroring the agent-path maturity gates — members get 403 before
any execution/scheduling starts.

The shared engine sink ``workflow_engine._execute_mcp_action`` stays ungated:
it has no User/RBAC in scope. Every reachable trigger gates at the route level
(consistent with the shipped R67 approach).

Import discipline: this module imports only ``fastapi``, ``core.models``
(``User``) and ``core.rbac_service`` (``Permission``, ``RBACService``). It must
NOT import the orchestrator at module level (duck-typed via attributes) and must
NOT import ``Permission`` from ``core.models`` (that module has its own
unrelated ``Permission(Base)`` model).
"""

from typing import Any, Dict, List, Optional, cast

from fastapi import HTTPException

from core.models import User
from core.rbac_service import Permission, RBACService

# R67: same critical-tool set as core/workflow_endpoints.py shipped with.
CRITICAL_MCP_TOOLS = {
    "read_codebase",
    "write_code_file",
    "list_directory_recursive",
    "terminal_command",
    "propose_command",
    "run_local_terminal",
    "browser_navigate",
    "browser_action",
    "email_send",
    "whatsapp_send_message",
}

# R68: orchestrator step types that execute the same critical local-machine /
# messaging actions as the MCP tool set (see WorkflowStepType enum in
# advanced_workflow_orchestrator.py). R67 deliberately did not include
# slack/discord — keep those benign.
CRITICAL_ORCHESTRATOR_STEP_TYPES = {"terminal", "browser", "email_send"}

# Universal-integration steps route on ``parameters["service"]`` as the
# connector id (_execute_universal_integration). Email-family connectors send
# mail — treat as critical like the ``email_send`` tool.
_CRITICAL_EMAIL_CONNECTORS = {"email", "gmail", "outlook"}

_UNKNOWN_DEFINITION_DETAIL = (
    "Workflow definition could not be resolved; execution refused."
)


def _normalize_step(step: Any) -> Dict[str, Any]:
    """Normalize a step into a plain dict for criticality checks.

    Accepts workflow-file dicts, ``advanced_workflow_orchestrator.WorkflowStep``
    dataclasses and ``core.workflow_template_system.TemplateStep`` pydantic
    models. ``step_type`` is resolved to its string value when it is an Enum.
    """
    if isinstance(step, dict):
        return step

    step_type = getattr(step, "step_type", None)
    if hasattr(step_type, "value"):
        # hasattr() doesn't narrow the type for mypy — step_type may be a
        # pydantic str field (no .value) or an Enum (has .value).
        step_type = cast(Any, step_type).value

    params = getattr(step, "parameters", None) or {}
    if not isinstance(params, dict):
        params = {}

    service = getattr(step, "service", None) or params.get("service")
    action = getattr(step, "action", None) or params.get("action")

    out: Dict[str, Any] = {
        "step_type": step_type,
        "service": service,
        "action": action,
        "parameters": params,
    }
    # Carry through identity keys that some normalizers key off.
    for key in ("step_id", "id", "name", "description"):
        if hasattr(step, key):
            out[key] = getattr(step, key)
    return out


def _has_critical_mcp_tool(step: Dict[str, Any]) -> bool:
    """R67 byte-for-byte dict semantics for an already-normalized dict step.

    True when a step executes a critical MCP tool. Checks both workflow-file
    steps (``service == "mcp"`` with ``action`` or ``parameters.tool_name``)
    and conductor steps (tool name in ``parameters`` without a ``service``
    key). A templated (``${...}``) or missing tool name on an mcp step is
    treated as critical: the effective tool cannot be proven benign statically
    (input templating via ``_resolve_parameters`` can inject the tool name at
    runtime).
    """
    params = step.get("parameters") or {}
    tool_name = params.get("tool_name") or step.get("action")
    service = (step.get("service") or str(step.get("step_type") or "")).lower()
    if service == "mcp":
        if not tool_name or "${" in str(tool_name) or tool_name in CRITICAL_MCP_TOOLS:
            return True
    elif tool_name and ("${" in str(tool_name) or tool_name in CRITICAL_MCP_TOOLS):
        return True
    return False


def has_critical_step(steps: Optional[List[Any]]) -> bool:
    """True when any step executes a critical MCP tool or orchestrator action.

    Combines the R67 dict semantics with the orchestrator step types that run
    the same critical actions (TERMINAL/BROWSER/EMAIL_SEND) and
    universal_integration steps routed to an email-family connector.
    """
    for raw in steps or []:
        step = _normalize_step(raw)
        if not isinstance(step, dict):
            continue
        if _has_critical_mcp_tool(step):
            return True
        step_type = str(step.get("step_type") or "").lower()
        if step_type in CRITICAL_ORCHESTRATOR_STEP_TYPES:
            return True
        if step_type == "universal_integration":
            service = str(
                step.get("service") or (step.get("parameters") or {}).get("service") or ""
            ).lower()
            if service in _CRITICAL_EMAIL_CONNECTORS:
                return True
    return False


def has_critical_definition(defn: Any) -> bool:
    """True when a workflow definition (list / dict-with-steps / object) has a
    critical step."""
    if defn is None:
        return False
    if isinstance(defn, list):
        return has_critical_step(defn)
    if isinstance(defn, dict):
        return has_critical_step(defn.get("steps"))
    return has_critical_step(getattr(defn, "steps", None))


async def require_workflow_executor(user: User, steps: Optional[List[Any]]) -> None:
    """R67/R68 gate: workflows with critical steps require WORKFLOW_MANAGE
    (TEAM_LEAD+). Members get 403 before any execution/scheduling starts."""
    if has_critical_step(steps) and not RBACService.check_permission(
        user, Permission.WORKFLOW_MANAGE
    ):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Workflows with critical MCP actions "
            "require WORKFLOW_MANAGE",
        )


async def require_workflow_executor_definition(user: User, defn: Any) -> None:
    """Same gate, taking a workflow definition instead of a raw step list."""
    if has_critical_definition(defn) and not RBACService.check_permission(
        user, Permission.WORKFLOW_MANAGE
    ):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Workflows with critical MCP actions "
            "require WORKFLOW_MANAGE",
        )


def resolve_orchestrator_steps(orchestrator: Any, workflow_id: str) -> Optional[List[Any]]:
    """Resolve a workflow's steps from an orchestrator.

    Prefers the live definition in ``orchestrator.workflows``; falls back to
    the template manager. Returns ``None`` when the definition is unknown so
    callers can fail closed.
    """
    workflow = None
    workflows = getattr(orchestrator, "workflows", None)
    if workflows is not None:
        workflow = workflows.get(workflow_id)
    if workflow is not None:
        return getattr(workflow, "steps", None)

    template_manager = getattr(orchestrator, "template_manager", None)
    if template_manager is not None:
        try:
            template = template_manager.get_template(workflow_id)
        except Exception:
            template = None
        if template is not None:
            return getattr(template, "steps", None)
    return None


async def require_workflow_executor_orchestrator(
    user: User, orchestrator: Any, workflow_id: str
) -> None:
    """Gate a workflow execution against an orchestrator definition.

    An unresolvable definition fails closed (403): ``execute_workflow`` would
    raise ValueError for an unknown id anyway, so refusing is safe.
    """
    steps = resolve_orchestrator_steps(orchestrator, workflow_id)
    if steps is None:
        raise HTTPException(status_code=403, detail=_UNKNOWN_DEFINITION_DETAIL)
    await require_workflow_executor(user, steps)


async def require_critical_tool(user: User, tool_name: Any) -> None:
    """Single-tool gate for direct ``mcp_service.execute_tool`` calls.

    Users with WORKFLOW_MANAGE are exempt (same role as the workflow gate).
    For everyone else a missing, templated or critical tool name is refused.
    """
    if RBACService.check_permission(user, Permission.WORKFLOW_MANAGE):
        return
    tool = str(tool_name or "")
    if not tool or "${" in tool or tool in CRITICAL_MCP_TOOLS:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Critical MCP tools require "
            "WORKFLOW_MANAGE",
        )


# R69: MCP tools that trigger whole workflows are a bare workflow-execution
# surface — the target definition can contain critical steps, so the trigger
# tool itself requires WORKFLOW_MANAGE regardless of the tool name's own
# criticality.
WORKFLOW_TRIGGER_TOOLS = {"trigger_workflow"}


async def require_workflow_trigger_tool(user: User, tool_name: Any) -> None:
    """Gate workflow-triggering MCP tools (e.g. ``trigger_workflow``).

    WORKFLOW_MANAGE holders are exempt. For everyone else a
    workflow-triggering tool name is refused with 403.
    """
    if RBACService.check_permission(user, Permission.WORKFLOW_MANAGE):
        return
    tool = str(tool_name or "")
    if tool in WORKFLOW_TRIGGER_TOOLS:
        raise HTTPException(
            status_code=403,
            detail="Workflow-triggering tools require WORKFLOW_MANAGE",
        )


# R69: AutomationEngine definitions execute ``nodes[].config.actionType``
# (send_email, run_agent_task, ...) — a surface invisible to
# ``has_critical_definition`` which only inspects ``steps``. These action
# types drive the same critical local-machine / messaging sinks.
CRITICAL_AUTOMATION_ACTION_TYPES = {
    "send_email",
    "run_agent_task",
    "terminal",
    "browser",
    "write",
    "send_message",
}


def has_critical_automation_nodes(defn: Any) -> bool:
    """True when an AutomationEngine definition has a critical action node.

    Inspects ``nodes[].config.actionType`` (dict or object defs). Used at the
    scheduler fire time to catch definitions whose critical actions are
    invisible to ``has_critical_definition``.
    """
    if defn is None:
        return False
    if isinstance(defn, dict):
        nodes = defn.get("nodes") or []
    else:
        nodes = getattr(defn, "nodes", None) or []
    for node in nodes:
        if isinstance(node, dict):
            config = node.get("config") or {}
        else:
            config = getattr(node, "config", None) or {}
        if not isinstance(config, dict):
            config = {}
        action_type = config.get("actionType")
        if action_type in CRITICAL_AUTOMATION_ACTION_TYPES:
            return True
    return False

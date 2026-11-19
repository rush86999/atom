"""Truthful admission checks for catalog-template execution.

A catalog template describes *intent*; it does not by itself prove that the
engine selected to run it can dispatch every step. Before this module existed,
the editor route mapped every unrecognised business step type to the
orchestrator's simulated ``API_CALL`` handler (reporting ``completed`` without
doing the work), while the Workflows-list route attempted the same template
through the canonical engine and persisted a durable ``FAILED`` run at the
first service that was not in the integration catalog.

The helpers here are deliberately read-only. They inspect the template's own
declared bindings, the canonical engine's real service registry, the
IntegrationCatalog action metadata, and the advanced orchestrator's native
step-type dispatch. They never mutate a template, start an engine, or create a
run receipt; callers use the returned blockers to refuse admission before a
run (real or simulated) begins.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


#: Step types whose ``service``/``action`` pair is the executable contract.
#: These are *not* native orchestrator handlers: they must resolve through the
#: canonical engine registry or the integration catalog.
_GENERIC_BINDING_STEP_TYPES = frozenset({
    "api_call",
    "universal_integration",
})


#: Fallback mirror of ``AdvancedWorkflowOrchestrator``'s explicit native
#: handlers. The live value is read from the orchestrator module when it is
#: importable; this fallback keeps the check deterministic in partial builds.
_NATIVE_ORCHESTRATOR_STEP_TYPES_FALLBACK = frozenset({
    "nlu_analysis",
    "email_send",
    "slack_notification",
    "asana_integration",
    "conditional_logic",
    "parallel_execution",
    "notion_integration",
    "gmail_fetch",
    "gmail_integration",
    "gmail_search",
    "notion_search",
    "notion_db_query",
    "hubspot_integration",
    "salesforce_integration",
    "knowledge_lookup",
    "knowledge_update",
    "system_reasoning",
    "invoice_processing",
    "ecommerce_sync",
    "agent_execution",
    "cost_leak_detection",
    "budget_check",
    "invoice_reconciliation",
    "background_agent_start",
    "background_agent_stop",
    "graphrag_query",
    "project_create",
    "project_status_sync",
    "contract_provision",
    "milestone_billing",
    "auto_staffing",
    "revenue_recognition",
    "retention_playbook",
    "business_agent_execution",
    "b2b_po_detection",
    "zoho_crm_integration",
    "zoom_integration",
    "browser",
    "terminal",
    "entity",
    "approval_required",
    "delay",
    "app_search",
})


@dataclass(frozen=True)
class TemplateExecutionBlocker:
    """One declared step that has no executable dispatch."""

    step_id: str
    step_name: str
    code: str
    reason: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "code": self.code,
            "reason": self.reason,
        }


def _field(step: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(step, dict):
            if name in step and step[name] is not None:
                return step[name]
        else:
            value = getattr(step, name, None)
            if value is not None:
                return value
    return default


def _clean_binding(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() in ("default", "unknown"):
        return None
    return text


def _parameter_binding(parameters: Any) -> Tuple[Optional[str], Optional[str]]:
    """Read service/action from a dict- or list-shaped parameter declaration."""
    if isinstance(parameters, dict):
        return (
            _clean_binding(parameters.get("service")),
            _clean_binding(parameters.get("action")),
        )
    if isinstance(parameters, (list, tuple)):
        found: Dict[str, Any] = {}
        for item in parameters:
            if isinstance(item, dict):
                name = item.get("name")
                value = item.get("default_value")
            else:
                name = getattr(item, "name", None)
                value = getattr(item, "default_value", None)
            if name in ("service", "action"):
                found[name] = value
        return (
            _clean_binding(found.get("service")),
            _clean_binding(found.get("action")),
        )
    return None, None


def _engine_services() -> frozenset:
    try:
        from core.workflow_engine import WorkflowEngine

        return frozenset(WorkflowEngine.supported_services())
    except Exception:  # noqa: BLE001 — partial build / import cycle
        return frozenset()


def _catalog_actions(service: str) -> Optional[List[Dict[str, Any]]]:
    """Read the catalog row's action metadata, or ``None`` when unavailable.

    Only the read-only catalog is consulted. A missing row, unreadable store,
    or unsupported schema is treated as "not available" so admission fails
    closed instead of guessing that an unknown service exists.
    """
    try:
        from core.cache import cache

        cached = cache.get(f"catalog:{service}")
        if cached:
            actions = cached.get("actions")
            return list(actions) if isinstance(actions, list) else None
    except Exception:  # noqa: BLE001 — cache is optional
        pass

    try:
        from core.database import get_db_session
        from core.models import IntegrationCatalog

        with get_db_session() as db:
            catalog_item = (
                db.query(IntegrationCatalog)
                .filter(IntegrationCatalog.id == service)
                .first()
            )
            if catalog_item is None:
                return None
            actions = catalog_item.actions
            return list(actions) if isinstance(actions, list) else []
    except Exception:  # noqa: BLE001 — fail closed without leaking internals
        return None


def _availability(service: str, action: str) -> Tuple[bool, str]:
    if service in _engine_services():
        return True, ""

    actions = _catalog_actions(service)
    if actions is None:
        return False, "service_not_available"
    if not any(
        isinstance(item, dict) and item.get("name") == action
        for item in actions
    ):
        return False, "action_not_available"
    return True, ""


def _native_orchestrator_step_types() -> frozenset:
    try:
        from advanced_workflow_orchestrator import (
            ORCHESTRATOR_NATIVE_STEP_TYPES,
        )

        return frozenset(
            member.value if hasattr(member, "value") else str(member)
            for member in ORCHESTRATOR_NATIVE_STEP_TYPES
        )
    except Exception:  # noqa: BLE001 — partial build / import cycle
        return _NATIVE_ORCHESTRATOR_STEP_TYPES_FALLBACK


def normalize_orchestrator_step_type(raw_type: Any) -> str:
    """Resolve a template step type exactly as the editor route registers it.

    ``api/workflow_template_routes.py`` builds ``WorkflowStepType(raw_type)``
    and falls back to ``API_CALL`` for business names (``action``,
    ``verification``, ...). ``API_CALL`` always dispatches to
    ``_execute_api_call``, a simulator that reports ``completed`` without doing
    the work, so admission must reason from this normalized value rather than
    from a declared service/action that happens to be registered elsewhere.
    """
    raw = str(raw_type or "api_call").strip().lower()
    try:
        from advanced_workflow_orchestrator import WorkflowStepType
    except Exception:  # noqa: BLE001 — partial build / import cycle
        if (raw in _native_orchestrator_step_types()
                or raw in ("trigger", "universal_integration")):
            return raw
        return "api_call"
    try:
        return WorkflowStepType(raw).value
    except ValueError:
        return WorkflowStepType.API_CALL.value


def _orchestrator_step_type(step: Any) -> str:
    # The editor route reads only ``step_type``; mirror that field exactly.
    return normalize_orchestrator_step_type(
        _field(step, "step_type", default=None))


def _normalize_step_type(step: Any) -> str:
    raw = _field(step, "step_type", "type", default="")
    value = str(raw or "").strip().lower()
    return value or "action"


def _step_identity(step: Any, index: int) -> Tuple[str, str]:
    step_id = str(_field(step, "step_id", "id", default="") or
                  f"step_{index}")
    step_name = str(_field(step, "name", default="") or step_id)
    return step_id, step_name


def preflight_template_steps(
    steps: Iterable[Any],
    *,
    target: str = "catalog",
) -> List[TemplateExecutionBlocker]:
    """Return every declared step that has no executable dispatch.

    ``target`` selects the engine that will run the template:

    * ``"orchestrator"`` — the editor/template execute route. Native
      orchestrator step types (delay, conditional logic, connector-mapped
      notifications, ...) are executable without a generic service/action.
      Explicit ``API_CALL`` and every business step name that the route lowers
      to it are refused even when a canonical binding exists, because that
      handler is only a simulator.
    * ``"workflow_engine"`` — the Workflows-list route. It dispatches strictly
      by ``service``/``action``, so every non-trigger step needs a resolvable
      binding.
    * ``"catalog"`` (default) — catalog-level truth: a step is admitted when it
      has a resolvable generic binding or is a native orchestrator step type.

    A trigger is admitted only as a design-time start marker (first step, no
    dependencies). A trigger placed mid-graph is a business wait expressed in
    the wrong primitive and is refused rather than silently treated as a
    completed no-op.
    """
    normalized_target = str(target or "catalog").strip().lower()
    step_list = list(steps or [])
    if not step_list and normalized_target in ("orchestrator", "workflow_engine"):
        # Draft creation/import/editing may legitimately begin with no steps.
        # Both execution targets, however, need at least one step to run;
        # otherwise the editor registers nothing (404) and the canonical engine
        # persists a durable COMPLETED run with zero steps.
        return [TemplateExecutionBlocker(
            step_id="template",
            step_name="template",
            code="no_steps",
            reason=(
                "the catalog template declares no steps; execution requires "
                "at least one executable step"
            ),
        )]

    native_types = _native_orchestrator_step_types()
    blockers: List[TemplateExecutionBlocker] = []

    for index, step in enumerate(step_list):
        step_id, step_name = _step_identity(step, index)
        step_type = _normalize_step_type(step)
        depends_on = _field(step, "depends_on", default=[]) or []
        if not isinstance(depends_on, (list, tuple, set)):
            depends_on = [depends_on]

        if step_type == "trigger":
            if depends_on or index > 0:
                blockers.append(TemplateExecutionBlocker(
                    step_id=step_id,
                    step_name=step_name,
                    code="design_time_trigger",
                    reason=(
                        "a design-time trigger is a start marker, not a "
                        "runtime wait; this step needs an executable wait "
                        "or event-trigger binding"
                    ),
                ))
            elif normalized_target == "workflow_engine":
                blockers.append(TemplateExecutionBlocker(
                    step_id=step_id,
                    step_name=step_name,
                    code="step_type_not_executable",
                    reason=(
                        "the canonical workflow engine has no design-time "
                        "trigger dispatcher; this step must declare an "
                        "executable service/action binding"
                    ),
                ))
            continue

        service = _clean_binding(_field(step, "service"))
        action = _clean_binding(_field(step, "action"))
        if not service or not action:
            param_service, param_action = _parameter_binding(
                _field(step, "parameters", default=None))
            service = service or param_service
            action = action or param_action

        if service and action:
            available, code = _availability(service, action)
            if available:
                # The editor route dispatches by step_type first. API_CALL
                # (including every business name the route lowers to it) has
                # no real handler there; a resolvable canonical binding does
                # not make the orchestrator's simulator a real execution.
                if (normalized_target == "orchestrator"
                        and _orchestrator_step_type(step) == "api_call"):
                    blockers.append(TemplateExecutionBlocker(
                        step_id=step_id,
                        step_name=step_name,
                        code="simulated_api_call",
                        reason=(
                            "the editor orchestrator has no real handler for "
                            "this step type; it would be executed as a "
                            "simulated API_CALL and report completed without "
                            "doing the work"
                        ),
                    ))
                    continue
                continue
            blockers.append(TemplateExecutionBlocker(
                step_id=step_id,
                step_name=step_name,
                code=code,
                reason=(
                    f"service '{service}' action '{action}' is not "
                    "available to the selected execution engine"
                ),
            ))
            continue

        if service or action:
            # A half-declared binding is never upgraded into a native step.
            missing = "action" if service else "service"
            blockers.append(TemplateExecutionBlocker(
                step_id=step_id,
                step_name=step_name,
                code="missing_action_binding",
                reason=(
                    f"step declares a service/action pair without the "
                    f"required {missing}"
                ),
            ))
            continue

        if (normalized_target != "workflow_engine"
                and step_type in native_types):
            continue

        if step_type in _GENERIC_BINDING_STEP_TYPES:
            reason = (
                "generic API steps require an explicit service and action "
                "binding; none was declared"
            )
        else:
            reason = (
                "step has no executable service/action binding and its "
                "step type is not a native orchestrator handler"
            )
        blockers.append(TemplateExecutionBlocker(
            step_id=step_id,
            step_name=step_name,
            code="missing_action_binding",
            reason=reason,
        ))

    return blockers


def blockers_detail(blockers: Iterable[TemplateExecutionBlocker]) -> Dict[str, Any]:
    """Build the shared public 422 detail for a refused execution."""
    return {
        "error": "execution_blocked",
        "message": "template contains steps that cannot be executed",
        "blockers": [blocker.as_dict() for blocker in blockers],
    }

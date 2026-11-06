"""Validated, server-compiled workflow blueprints (ORCH-01).

The model may propose a blueprint, but it does not author executable mechanics.
This module validates the proposal as a DAG, rejects unsupported/ambiguous
shapes, inserts the mandatory approval checkpoint before a governed mutation,
and compiles the existing workflow step representation. Persistence and route
scope live in ``core.workflow_blueprint_service``.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field


NodeType = Literal["trigger", "skill", "agent", "entity"]
ActionKind = Literal["read", "compute", "notify", "write", "approval"]
ExecutionMode = Literal["one_off", "recurring_automation"]

#: Server-owned design references. A model may name only these existing
#: connector/action families; an unknown reference is a typed refusal, never
#: a supported runnable registration.
KNOWN_ACTION_SERVICES = frozenset({
    "email", "gmail", "outlook", "slack", "teams", "notion", "asana",
    "hubspot", "salesforce", "zoho-crm", "zoom", "mcp", "http", "https",
    "api", "internal", "knowledge", "documents", "tasks", "browser",
    "terminal", "crm", "inventory", "finance", "procurement", "erp",
})
KNOWN_ACTION_NAMES = frozenset({
    "read", "compute", "notify", "write", "send", "create", "update",
    "delete", "lookup", "query", "search", "list", "get", "fetch", "draft",
    "approve", "sync", "post", "upload", "publish", "execute", "run",
})
MUTATING_ACTION_NAMES = frozenset({
    "notify", "write", "send", "create", "update", "delete", "post",
    "upload", "publish", "execute", "run",
})
#: Only these business-readable fields may reach execution parameters. Any
#: other model metadata is design prose, not executable authority.
ALLOWED_METADATA_KEYS = frozenset({
    "trigger_event", "schedule", "condition", "entity_name", "entity_type",
    "description", "properties", "role", "label", "notes", "reason",
})


def _entity_executable_actions():
    """Return the handler-owned entity operation contract, or None.

    The executor module owns the set; the compiler must not maintain a
    second, drifting copy. A missing contract fails closed.
    """
    try:
        from advanced_workflow_orchestrator import ENTITY_EXECUTABLE_ACTIONS
    except Exception:  # noqa: BLE001 — fail closed
        return None
    return frozenset(ENTITY_EXECUTABLE_ACTIONS)


def _registered_action_names():
    """Return the actual action-registry names, or None when unavailable."""
    try:
        from core.action_registry import action_registry
    except Exception:  # noqa: BLE001 — fail closed
        return None
    return frozenset(action_registry.list_actions())


def _is_registered_action(service: str, action_name: str) -> bool:
    """Resolve a declared service/action pair against the real registry."""
    names = _registered_action_names()
    if not names:
        return False
    return bool({
        f"{service}.{action_name}",
        f"connected.{service}.{action_name}",
        f"brennan.{service}.{action_name}",
    } & names)



class WorkflowNodeAction(BaseModel):
    """The design intent of one node, never executable plumbing."""

    model_config = ConfigDict(extra="forbid")

    kind: ActionKind
    service: Optional[str] = Field(default=None, max_length=80)
    action: Optional[str] = Field(default=None, max_length=80)


class WorkflowBlueprintNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        min_length=1, max_length=80,
        pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    type: NodeType
    name: str = Field(min_length=1, max_length=200)
    capability_required: Optional[str] = Field(
        default=None, max_length=120)
    dependencies: List[str] = Field(default_factory=list, max_length=40)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    action: Optional[WorkflowNodeAction] = None


class MissingCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class WorkflowBlueprintDraft(BaseModel):
    """The model-owned shape. Server fields are added by the compiler."""

    model_config = ConfigDict(extra="forbid")

    architecture_name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    execution_mode: ExecutionMode = "one_off"
    nodes: List[WorkflowBlueprintNode] = Field(
        min_length=1, max_length=60)
    required_integrations: List[str] = Field(
        default_factory=list, max_length=20)
    missing_capabilities: List[MissingCapability] = Field(
        default_factory=list, max_length=20)


class BlueprintValidationError(ValueError):
    """A safe, typed refusal before any durable/executable write."""

    def __init__(
        self, code: str, message: str,
        details: Optional[Sequence[Any]] = None,
    ):
        self.code = str(code)
        self.message = str(message)
        self.details = list(details or [])
        super().__init__(self.message)


class BlueprintGenerationError(RuntimeError):
    """A model/route failure that must not become a fallback workflow."""

    def __init__(
        self, code: str, message: str, status_code: int = 503,
        details: Optional[Sequence[Any]] = None,
    ):
        self.code = str(code)
        self.message = str(message)
        self.status_code = int(status_code)
        self.details = list(details or [])
        super().__init__(self.message)


def _cycle_or_missing(
    nodes: Sequence[Dict[str, Any]],
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Return topological order and adjacency, raising on a bad graph."""
    ids = [node["id"] for node in nodes]
    if len(ids) != len(set(ids)):
        raise BlueprintValidationError(
            "workflow_node_duplicate",
            "workflow node ids must be unique",
            details=sorted({node_id for node_id in ids
                           if ids.count(node_id) > 1}))
    by_id = {node["id"]: node for node in nodes}
    adjacency: Dict[str, List[str]] = {node["id"]: [] for node in nodes}
    indegree = {node["id"]: 0 for node in nodes}
    for node in nodes:
        for dependency in node.get("dependencies") or []:
            if dependency not in by_id:
                raise BlueprintValidationError(
                    "workflow_dependency_missing",
                    f"node {node['id']!r} depends on unknown node "
                    f"{dependency!r}",
                    details=[node["id"], dependency])
            if dependency == node["id"]:
                raise BlueprintValidationError(
                    "workflow_dependency_self",
                    f"node {node['id']!r} depends on itself")
            adjacency[dependency].append(node["id"])
            indegree[node["id"]] += 1
    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    ordered: List[str] = []
    while ready:
        node_id = ready.pop(0)
        ordered.append(node_id)
        for successor in adjacency[node_id]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
    if len(ordered) != len(nodes):
        raise BlueprintValidationError(
            "workflow_cycle",
            "the workflow dependency graph contains a cycle")
    return ordered, adjacency


def _is_mutating(node: Dict[str, Any]) -> bool:
    action = node.get("action") or {}
    kind = str(action.get("kind") or "").strip().lower()
    if node.get("type") == "entity":
        # An entity node represents persistent state. A lookup/query must say
        # so explicitly; the default is a mutation and therefore gated.
        return kind not in ("read", "compute")
    return kind in ("write", "notify")


def _step_type(node_type: str) -> str:
    if node_type == "trigger":
        return "trigger"
    if node_type == "entity":
        return "entity"
    if node_type == "approval":
        return "approval_required"
    # A skill or agent is a reasoning/execution request owned by the business
    # agent. It is never silently mapped to a universal external integration.
    return "business_agent_execution"


def _approval_node(
    node: Dict[str, Any], *, workflow_id: str = "",
) -> Dict[str, Any]:
    approval_id = f"approval_{node['id']}"
    return {
        "id": approval_id,
        "type": "approval",
        "name": f"Approve {node['name']}",
        "capability_required": None,
        "dependencies": list(node.get("dependencies") or []),
        "metadata": {
            "checkpoint": "approval_required",
            "guarded_step": node["id"],
            "reason": (
                f"Human approval is required before {node['name']} "
                "mutates governed state or sends an external effect."),
            "workflow_id": workflow_id,
        },
        "action": {"kind": "approval"},
    }


def compile_blueprint(
    draft: WorkflowBlueprintDraft | Dict[str, Any],
    *,
    execution_mode: Optional[ExecutionMode] = None,
    workspace_id: str = "",
    tenant_id: str = "",
) -> Dict[str, Any]:
    """Validate one model draft and compile the server-owned plan.

    Raises ``BlueprintValidationError`` for any refusal. No persistence or
    workflow registration occurs here.
    """
    if not isinstance(draft, WorkflowBlueprintDraft):
        try:
            draft = WorkflowBlueprintDraft.model_validate(draft)
        except Exception as exc:  # pydantic validation is a typed refusal
            raise BlueprintValidationError(
                "workflow_blueprint_invalid",
                "the workflow blueprint is malformed",
                details=[str(exc)]) from exc
    mode: str = str(execution_mode or draft.execution_mode)
    if mode not in ("one_off", "recurring_automation"):
        raise BlueprintValidationError(
            "workflow_execution_mode_invalid",
            "execution_mode must be one_off or recurring_automation")
    if execution_mode and draft.execution_mode != execution_mode:
        raise BlueprintValidationError(
            "workflow_execution_mode_mismatch",
            "the model execution_mode does not match the classified request",
            details=[draft.execution_mode, execution_mode])
    if draft.missing_capabilities:
        raise BlueprintValidationError(
            "workflow_capability_missing",
            "the workflow needs capabilities that are not available; no "
            "runnable workflow was created",
            details=[item.model_dump() for item in draft.missing_capabilities])

    nodes = [node.model_dump() for node in draft.nodes]
    # Reference and authority validation happens before any registration.
    for node in nodes:
        action = node.get("action") or {}
        kind = str(action.get("kind") or "").strip().lower()
        service = str(action.get("service") or "").strip().lower()
        action_name = str(action.get("action") or "").strip().lower()
        if service and service not in KNOWN_ACTION_SERVICES:
            raise BlueprintValidationError(
                "workflow_action_reference_unknown",
                f"node {node['id']!r} names an unknown action service "
                f"{service!r}")
        if action_name and action_name not in KNOWN_ACTION_NAMES:
            raise BlueprintValidationError(
                "workflow_action_reference_unknown",
                f"node {node['id']!r} names an unknown action "
                f"{action_name!r}")
        if bool(service) != bool(action_name):
            raise BlueprintValidationError(
                "workflow_action_reference_incomplete",
                f"node {node['id']!r} must name both service and action, or "
                "neither")
        if kind == "approval":
            raise BlueprintValidationError(
                "workflow_action_approval_model_authored",
                "approval checkpoints are server-owned; a model node cannot "
                "author one")
    ordered, adjacency = _cycle_or_missing(nodes)
    roots = [node["id"] for node in nodes if not node.get("dependencies")]
    if len(roots) != 1:
        raise BlueprintValidationError(
            "workflow_start_ambiguous",
            "the workflow must have exactly one start node",
            details=roots)
    triggers = [node for node in nodes if node.get("type") == "trigger"]
    if len(triggers) > 1:
        raise BlueprintValidationError(
            "workflow_trigger_duplicate",
            "a workflow may declare at most one trigger",
            details=[node["id"] for node in triggers])
    if mode == "recurring_automation":
        if len(triggers) != 1:
            raise BlueprintValidationError(
                "workflow_trigger_required",
                "recurring automation requires exactly one trigger node")
        if triggers[0]["id"] != roots[0]:
            raise BlueprintValidationError(
                "workflow_trigger_start",
                "the recurring trigger must be the workflow start node")
        metadata = triggers[0].get("metadata") or {}
        if not any(str(metadata.get(key) or "").strip() for key in (
                "trigger_event", "schedule", "condition")):
            raise BlueprintValidationError(
                "workflow_trigger_metadata_required",
                "the recurring trigger must declare an event, schedule or "
                "condition")
    elif triggers and triggers[0]["id"] != roots[0]:
        raise BlueprintValidationError(
            "workflow_trigger_start",
            "the trigger node must be the workflow start node")

    # A trigger is a design-time start marker. Any model-supplied action on it
    # is not an executable effect and must not create a spurious HITL gate.
    for node in nodes:
        if node.get("type") == "trigger":
            node["action"] = {"kind": "read"}

    workflow_id = f"ai_wf_{uuid.uuid4().hex[:12]}"

    # A generated workflow must never contain an ungated governed mutation.
    compiled_nodes: List[Dict[str, Any]] = []
    approval_ids: List[str] = []
    execution_blockers: List[str] = []
    for node in nodes:
        action = node.get("action") or {}
        kind = str(action.get("kind") or "").strip().lower()
        action_name = str(action.get("action") or "").strip().lower()
        mutating = _is_mutating(node) or action_name in MUTATING_ACTION_NAMES
        if node.get("type") == "trigger":
            mutating = False
        if mutating:
            approval = _approval_node(node, workflow_id=workflow_id)
            if any(existing.get("id") == approval["id"]
                   for existing in compiled_nodes):
                raise BlueprintValidationError(
                    "workflow_approval_id_conflict",
                    f"approval node id {approval['id']!r} is not unique")
            compiled_nodes.append(approval)
            approval_ids.append(approval["id"])
            node["dependencies"] = [approval["id"]]
        compiled_nodes.append(node)

    # Recompute adjacency after the HITL insertion.
    ordered, adjacency = _cycle_or_missing(compiled_nodes)
    roots = [
        node["id"] for node in compiled_nodes
        if not node.get("dependencies")
    ]
    if len(roots) != 1:
        raise BlueprintValidationError(
            "workflow_start_ambiguous",
            "the compiled workflow must have exactly one start node",
            details=roots)

    steps: List[Dict[str, Any]] = []
    for node in compiled_nodes:
        safe_metadata = {
            key: value for key, value in (node.get("metadata") or {}).items()
            if str(key) in ALLOWED_METADATA_KEYS
        }
        parameters: Dict[str, Any] = dict(safe_metadata)
        parameters.update({
            "capability_required": node.get("capability_required"),
            "design_action": node.get("action") or {},
            "hitl": node.get("type") == "approval",
        })
        action = node.get("action") or {}
        kind = str(action.get("kind") or "").strip().lower()
        service = str(action.get("service") or "").strip().lower()
        action_name = str(action.get("action") or "").strip().lower()
        mutating = _is_mutating(node) or action_name in MUTATING_ACTION_NAMES
        if node.get("type") == "trigger":
            mutating = False
            parameters.pop("action", None)
        elif node.get("type") == "entity":
            # The model's label is not the effect authority, but a DECLARED
            # specific operation must not be replaced by a different one.
            # Bind to the actual entity executor contract; an unsupported
            # operation stays non-executable with an honest blocker.
            if action_name:
                supported = _entity_executable_actions()
                parameters["action"] = action_name
                if supported is None:
                    execution_blockers.append(
                        f"{node['id']}: the entity executor contract is "
                        "unavailable; the declared operation cannot be "
                        "certified")
                elif action_name not in supported:
                    execution_blockers.append(
                        f"{node['id']}: entity action {action_name!r} is not "
                        "supported by the current entity executor; supported "
                        f"operations are {', '.join(sorted(supported))}")
            else:
                parameters["action"] = "create" if mutating else "lookup"
            parameters["entity_name"] = str(
                safe_metadata.get("entity_name") or node["name"])
            parameters["entity_type"] = str(
                safe_metadata.get("entity_type") or "business_record")
        elif node.get("type") == "approval":
            parameters = {
                "action": "workflow_step",
                "checkpoint": "approval_required",
                "guarded_step": (node.get("metadata") or {}).get(
                    "guarded_step"),
                "server_required": True,
                "workflow_id": workflow_id,
                "workspace_id": str(workspace_id or ""),
                "tenant_id": str(tenant_id or ""),
            }
        elif node.get("type") in ("skill", "agent"):
            capability = str(
                node.get("capability_required") or "").strip().lower()
            # A model-design step is executable only when its capability is
            # bound to an existing business-agent registry entry. Otherwise
            # the blueprint is reviewable but explicitly non-executable.
            try:
                from core.business_agents import AGENT_SUITE
            except Exception:  # noqa: BLE001 — fail closed
                AGENT_SUITE = {}
            if capability and capability in AGENT_SUITE:
                parameters["agent_type"] = capability
            else:
                execution_blockers.append(
                    f"{node['id']}: capability "
                    f"{capability or '<none>'} is not bound to a registered "
                    "business agent")
            # A declared connector action is executable only when the actual
            # action registry contains that pair (including its connector
            # namespaces). Design vocabulary alone is not a binding.
            if service and action_name and not _is_registered_action(
                    service, action_name):
                execution_blockers.append(
                    f"{node['id']}: action {service}.{action_name} is not a "
                    "registered executable action")
        steps.append({
            "step_id": node["id"],
            "step_type": _step_type(node["type"]),
            "description": node["name"],
            "parameters": parameters,
            "next_steps": list(adjacency.get(node["id"]) or []),
        })

    # Bind each server-required checkpoint to the immutable compiled material
    # of the step it guards. A changed reviewed effect cannot reuse an old
    # approval receipt even when the workflow/step ids are unchanged.
    steps_by_id = {step["step_id"]: step for step in steps}
    for step in steps:
        if step.get("step_type") != "approval_required":
            continue
        guarded_id = str(
            (step.get("parameters") or {}).get("guarded_step") or "")
        guarded = steps_by_id.get(guarded_id)
        if guarded is None:
            continue
        step["parameters"]["guarded_digest"] = hashlib.sha256(
            json.dumps(
                {
                    "parameters": guarded.get("parameters") or {},
                    "next_steps": list(guarded.get("next_steps") or []),
                },
                sort_keys=True, default=str,
            ).encode()).hexdigest()

    execution_ready = not execution_blockers
    trigger_descriptors = [
        {
            "node_id": node["id"],
            "trigger_event": (node.get("metadata") or {}).get(
                "trigger_event") or "",
            "schedule": (node.get("metadata") or {}).get("schedule") or "",
            "condition": (node.get("metadata") or {}).get("condition") or "",
        }
        for node in triggers
    ]
    definition_material = {
        "architecture_name": draft.architecture_name,
        "description": draft.description,
        "execution_mode": mode,
        "start_step": roots[0],
        "nodes": compiled_nodes,
        "steps": steps,
        "triggers": trigger_descriptors,
        "required_integrations": list(draft.required_integrations),
        "execution_ready": execution_ready,
        "execution_blockers": list(execution_blockers),
    }
    digest = hashlib.sha256(json.dumps(
        definition_material, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "workflow_id": workflow_id,
        "blueprint_id": str(uuid.uuid4()),
        "status": "designed",
        "source": "model",
        "schema": "orch-workflow-blueprint-1",
        "architecture_name": draft.architecture_name,
        "name": draft.architecture_name,
        "description": draft.description,
        "execution_mode": mode,
        "start_step": roots[0],
        "nodes": compiled_nodes,
        "steps": steps,
        "triggers": trigger_descriptors,
        "required_integrations": list(draft.required_integrations),
        "missing_capabilities": [],
        "hitl_gates": approval_ids,
        "step_count": len(steps),
        "definition_digest": digest,
        "execution_ready": execution_ready,
        "execution_blockers": list(execution_blockers),
        "definition": definition_material,
    }

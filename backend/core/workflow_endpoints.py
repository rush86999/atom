from contextlib import contextmanager
import copy
from datetime import datetime
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User
from core.rbac_service import Permission, RBACService
from core.security_dependencies import require_permission
from core.workflow_security import require_workflow_executor

# Import AI workflow editor for natural language processing
logger = logging.getLogger(__name__)

try:
    from ai.workflow_nlu_editor import get_workflow_editor
    AI_EDITOR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AI workflow editor not available: {e}")
    AI_EDITOR_AVAILABLE = False

router = APIRouter()

# R67/R68: Workflows whose steps contain critical MCP actions (local machine
# exec, browser automation, messaging) execute the same tools the agent
# governance layer gates to AUTONOMOUS maturity (core/mcp_service.py
# critical_tools). The workflow trigger routes are role-routed only
# (WORKFLOW_RUN is granted to every member), so these steps must require
# the same role as workflow creation (WORKFLOW_MANAGE, TEAM_LEAD+). The gate
# lives in core/workflow_security.py so every trigger path shares it.

# Simple file-based storage for MVP
WORKFLOWS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workflows.json")

# Shared writer guard for the catalog.
#
# Every JSON writer in this module goes through ``save_workflows`` (atomic
# replace) and the deployment/create/delete paths also hold the shared
# read-modify-write transaction below. The lock file is an advisory POSIX
# ``flock`` beside the single anchored catalog path; it is not a new data
# store. It serialises cooperating processes that use this module. It cannot
# make the SQL blueprint row and the JSON catalog one transaction, and it is
# not an exactly-once arbiter for non-cooperating writers — callers must
# reconcile the persisted row instead of claiming a rollback after a commit.
_STORE_THREAD_LOCK = threading.RLock()
_STORE_LOCAL = threading.local()


class WorkflowStoreError(RuntimeError):
    """Base class for shared catalog failures."""


class WorkflowStoreUnreadable(WorkflowStoreError):
    """An existing catalog file is corrupt/unreadable/wrong-shaped.

    Mutations must refuse without touching the existing bytes.
    """


class WorkflowStoreLockError(WorkflowStoreError):
    """A required filesystem lock exists but could not be acquired."""


@contextmanager
def _workflow_store_guard():
    depth = getattr(_STORE_LOCAL, "depth", 0)
    if depth:
        _STORE_LOCAL.depth = depth + 1
        try:
            yield
        finally:
            _STORE_LOCAL.depth -= 1
        return
    with _STORE_THREAD_LOCK:
        try:
            import fcntl
        except ImportError:
            # True platform limitation (no POSIX flock). The in-process RLock
            # still serialises this module's writers; cross-process
            # contention is truthful but not asserted as exactly-once.
            fcntl = None
        lock_handle = None
        acquired = False
        try:
            if fcntl is not None:
                lock_path = WORKFLOWS_FILE + ".lock"
                parent = os.path.dirname(os.path.abspath(lock_path))
                # A failure to create/open the lock must surface; never
                # continue writing unguarded after a failed lock attempt.
                try:
                    os.makedirs(parent, exist_ok=True)
                    lock_handle = open(lock_path, "a+")
                except OSError as exc:
                    raise WorkflowStoreLockError(
                        "catalog lock could not be opened; no write was "
                        "attempted") from exc
                try:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                    acquired = True
                except OSError as exc:
                    raise WorkflowStoreLockError(
                        "catalog lock could not be acquired; no write was "
                        "attempted") from exc
            _STORE_LOCAL.depth = 1
            yield
        finally:
            _STORE_LOCAL.depth = 0
            if lock_handle is not None:
                try:
                    if acquired:
                        import fcntl as acquired_fcntl
                        acquired_fcntl.flock(
                            lock_handle.fileno(), acquired_fcntl.LOCK_UN)
                finally:
                    lock_handle.close()


def _read_existing_store_payload() -> Optional[List[Dict]]:
    """Strict read of the existing catalog.

    Returns ``None`` when there is no existing regular file (absent or a
    special target such as a device). Raises ``WorkflowStoreUnreadable`` for
    an existing regular file that cannot be read, is not valid JSON, is not a
    list, or contains non-object rows. Read-only callers may opt into the
    tolerant compatibility wrapper instead.
    """
    import stat

    try:
        file_stat = os.stat(WORKFLOWS_FILE)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WorkflowStoreUnreadable(
            f"catalog {WORKFLOWS_FILE!r} cannot be inspected") from exc
    if not stat.S_ISREG(file_stat.st_mode):
        return None
    try:
        with open(WORKFLOWS_FILE, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise WorkflowStoreUnreadable(
            f"catalog {WORKFLOWS_FILE!r} cannot be read") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowStoreUnreadable(
            f"catalog {WORKFLOWS_FILE!r} is not valid JSON") from exc
    if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload):
        raise WorkflowStoreUnreadable(
            f"catalog {WORKFLOWS_FILE!r} is not a JSON list of objects")
    return payload


def _atomic_write_workflows(workflows: List[Dict]):
    """Write the whole catalog through one temp file + os.replace."""
    import stat

    try:
        target_stat = os.stat(WORKFLOWS_FILE)
    except FileNotFoundError:
        target_stat = None
    if target_stat is not None and not stat.S_ISREG(target_stat.st_mode):
        # Special files (device/FIFO) cannot be atomically replaced and hold
        # no authoritative catalog bytes; direct write is the general
        # contract for them.
        with open(WORKFLOWS_FILE, "w") as handle:
            json.dump(workflows, handle, indent=2)
        return
    directory = os.path.dirname(os.path.abspath(WORKFLOWS_FILE)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".workflows.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(workflows, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, WORKFLOWS_FILE)
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


def load_workflows() -> List[Dict]:
    """Tolerant read path for existing display/read consumers.

    Corruption is logged and treated as an empty read here for compatibility;
    mutations never use this path and refuse instead.
    """
    try:
        payload = _read_existing_store_payload()
    except WorkflowStoreUnreadable as exc:
        logger.error("Failed to load workflows: %s", exc, exc_info=True)
        return []
    return list(payload or [])


def load_workflows_strict() -> List[Dict]:
    """Strict read used by every shared mutation."""
    return list(_read_existing_store_payload() or [])


def save_workflows(workflows: List[Dict]):
    with _workflow_store_guard():
        # Legacy writers call load_workflows() (tolerant) before this. Refuse
        # here rather than replacing an existing unreadable authoritative
        # file with the empty list they may have observed.
        _read_existing_store_payload()
        _atomic_write_workflows(workflows)


def mutate_workflows(mutator):
    """Shared read-modify-write over the one catalog path.

    ``mutator(workflows)`` returns ``(changed, value)``. The write happens
    only when ``changed`` is true, inside the shared guard, so a refusal is a
    true no-write and a committed write can be reconciled by the caller.
    """
    with _workflow_store_guard():
        workflows = load_workflows_strict()
        changed, value = mutator(workflows)
        if changed:
            # Re-check under the same guard immediately before replace.
            _read_existing_store_payload()
            _atomic_write_workflows(workflows)
        return value


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
    # Derived step-based dialect (populated on read for node-based defs) so
    # the step-based UI/frontend can render and execute node-based workflows.
    steps: Optional[List[Dict[str, Any]]] = None
    steps_count: Optional[int] = None
    # Server-owned deployment metadata for generated blueprints. Public
    # create/update callers cannot set or clear it; only the deploy adapter
    # writes it. Absence means a legacy/unscoped row (preserved as-is).
    deployment: Optional[Dict[str, Any]] = None

class WorkflowEditRequest(BaseModel):
    command: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class WorkflowEditResponse(BaseModel):
    success: bool
    message: str
    modified_workflow: Optional[Dict[str, Any]] = None
    changes: List[Dict[str, Any]] = []


def _linearize_nodes(workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert a node-based (graph) workflow dict into linear steps.

    Mirrors the engine's graph→steps linearization (Kahn topological sort) so
    read paths and the security gate can reason about node-based definitions
    without instantiating the engine. Node ``config`` drives the step's
    ``service``/``action``/``parameters`` — the same fields
    ``core.workflow_security`` inspects for critical MCP actions.
    """
    nodes = {n["id"]: n for n in workflow.get("nodes", [])}
    connections = workflow.get("connections", [])

    adj = {nid: [] for nid in nodes}
    in_degree = {nid: 0 for nid in nodes}
    for conn in connections:
        source = conn.get("source")
        target = conn.get("target")
        if source in adj and target in in_degree:
            adj[source].append(target)
            in_degree[target] += 1

    queue = [nid for nid in nodes if in_degree[nid] == 0]
    sorted_ids: List[str] = []
    while queue:
        u = queue.pop(0)
        sorted_ids.append(u)
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    # Cycles: the engine raises; read paths must not crash on a bad graph,
    # so fall back to insertion order.
    if len(sorted_ids) != len(nodes):
        logger.error(
            f"Workflow contains cycle; falling back to insertion order. "
            f"Nodes in cycle: {[n for n in nodes if n not in sorted_ids]}"
        )
        sorted_ids = list(nodes.keys())

    steps = []
    for i, node_id in enumerate(sorted_ids):
        node = nodes[node_id]
        config = node.get("config", {}) or {}
        steps.append({
            "id": node_id,
            "type": "trigger" if node.get("type") == "trigger" else "action",
            "name": node.get("title", node_id),
            "sequence_order": i + 1,
            "service": config.get("service", "default"),
            "action": config.get("action", "default"),
            "parameters": config.get("parameters", {}),
        })
    return steps


def _resolve_workflow_steps(workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Resolve the effective step list for a workflow definition.

    Step-based definitions already carry ``steps``; node-based (graph)
    definitions are linearized on demand. The converted list is cached on the
    workflow dict so the security gate and the engine share one list.
    """
    if workflow.get("steps"):
        return workflow["steps"]
    if workflow.get("nodes"):
        steps = _linearize_nodes(workflow)
        workflow["steps"] = steps
        return steps
    return []


def _enrich_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Add the step-based dialect (``steps`` + ``steps_count``) to a workflow
    dict so step-based UI consumers can render/execute node-based definitions.

    Also normalizes step-based "Dynamic Workflow" rows (written by the
    agent-driven create flow with no node dialect) to the response contract:
    ``nodes``/``connections``/``triggers``/``enabled`` are required by
    ``WorkflowDefinition``, so a row without them 500s the whole list with
    ResponseValidationError (the primary workflow list was broken whenever a
    dynamic workflow existed).
    """
    workflow.setdefault("nodes", [])
    workflow.setdefault("connections", [])
    workflow.setdefault("triggers", [])
    workflow.setdefault("enabled", True)
    # R81: the response models require `description`/`version` — a stored row
    # missing either (e.g. an agent-driven "Dynamic Workflow" row written
    # without the node dialect, or a hand-edited file entry) 500s the whole
    # list with ResponseValidationError. Normalize defaults so one malformed
    # row can't break every consumer of the workflow list.
    workflow.setdefault("description", "")
    workflow.setdefault("version", "1")
    steps = _resolve_workflow_steps(workflow)
    workflow["steps"] = steps
    workflow["steps_count"] = len(steps)
    return workflow


def _load_template_definition(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Resolve a DB template (``WorkflowTemplate``) into an executable definition.

    The UI lists templates from template stores and executes them via
    ``/workflows/{id}/execute``; neither store's rows live in
    ``workflows.json``, so the durable-store lookup alone 404s. Two
    resolvers run in order:

    * the DB ``WorkflowTemplate`` table (editor/imported templates keyed
      on the UUID ``id`` column);
    * the file-backed template system — the rows ``GET
      /api/workflow-templates`` serves, with ids like
      ``template_personal_candidate_pipeline``. This is the store the
      Workflows page's "Use Template → Execute" flow posts, which 404'd
      here (issue #618).
    """
    try:
        from core.models import WorkflowTemplate

        db = next(get_db())
        try:
            # The ORM WorkflowTemplate keys on `id` (a UUID PK) —
            # `template_id` lives on the file-backed template system, not
            # this model.
            template = (
                db.query(WorkflowTemplate)
                .filter(WorkflowTemplate.id == workflow_id)
                .first()
            )
            if template is not None:
                return {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description or "",
                    "steps": template.steps or [],
                }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to resolve template definition '{workflow_id}': {e}")

    # File-backed template system. Steps carry the engine's execution
    # contract natively (service/action/parameters — see
    # WorkflowEngine._execute_step). Declared (list-shaped) parameters bind
    # to the execution's input_data through the engine's ${input.<name>}
    # convention, preferring the declared default when one exists.
    try:
        from core.workflow_template_system import WorkflowTemplateManager

        template = WorkflowTemplateManager().get_template(workflow_id)
        if template is None:
            return None
        steps = []
        for step in template.steps or []:
            params = step.parameters
            if isinstance(params, list):
                params = {
                    p.name: p.default_value
                    if p.default_value is not None
                    else f"${{input.{p.name}}}"
                    for p in params
                }
            steps.append({
                "id": step.step_id,
                "name": step.name,
                "service": step.service or "default",
                "action": step.action or "default",
                "type": step.step_type or "action",
                "parameters": params or {},
                "depends_on": step.depends_on or [],
                "condition": step.condition,
            })
        return {
            "id": template.template_id,
            "name": template.name,
            "description": template.description or "",
            "steps": steps,
        }
    except Exception as e:
        logger.error(f"Failed to resolve file-backed template '{workflow_id}': {e}")
        return None


def _validate_workflow_dag(workflow: Dict[str, Any]) -> None:
    """Reject cyclic node graphs using the engine's authoritative linearization.

    R81: the lenient read-path linearization (``_linearize_nodes``) falls back
    to insertion order when a graph contains a cycle, so cyclic workflows
    previously CREATED and EXECUTED in an arbitrary order instead of being
    rejected. Create + execute now validate the graph up front and return 400
    with the engine's circular-dependency message.
    """
    if not workflow.get("nodes"):
        return
    from core.workflow_engine import WorkflowEngine
    try:
        WorkflowEngine()._convert_nodes_to_steps(workflow)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Generated-blueprint handoff helpers
# ---------------------------------------------------------------------------

def _caller_scope(user: User) -> Dict[str, str]:
    """Authoritative scope from the token/User object only."""
    return {
        "tenant_id": str(getattr(user, "tenant_id", None) or "default"),
        "workspace_id": str(getattr(user, "workspace_id", None) or "default"),
        "user_id": str(getattr(user, "id", None) or ""),
    }


def _is_visible_to_user(workflow: Dict[str, Any], user: User) -> bool:
    """Strict for new generated rows; legacy rows keep their old behavior.

    A row with server-owned deployment metadata is only visible inside its
    recorded tenant/workspace. A row without that metadata is a legacy row:
    it stays visible (A7), and its global catalog limitation is not certified
    or silently rewritten.
    """
    deployment = workflow.get("deployment")
    if not isinstance(deployment, dict) or not deployment.get("tenant_id"):
        return True
    scope = _caller_scope(user)
    return (
        str(deployment.get("tenant_id")) == scope["tenant_id"]
        and str(deployment.get("workspace_id")) == scope["workspace_id"]
    )


def _visible_workflows(user: User) -> List[Dict]:
    return [w for w in load_workflows() if _is_visible_to_user(w, user)]


def _find_visible_workflow(workflow_id: str, user: User) -> Optional[Dict[str, Any]]:
    for workflow in load_workflows():
        if (workflow.get("id") == workflow_id
                or workflow.get("workflow_id") == workflow_id):
            if _is_visible_to_user(workflow, user):
                return workflow
            return None
    return None


def _generated_definition_scope(workflow_id: str) -> Dict[str, Any]:
    """Resolve the authoritative scope for a generated definition.

    ``generated`` carries exact tenant/workspace. ``legacy`` is returned only
    when an existing legacy row is positively identified. When neither the
    catalog deployment projection nor the SQL blueprint is readable, the
    result is ``unknown`` — never an implicit legacy/global grant.
    """
    catalog_row_found = False
    catalog_scope = None
    for row in load_workflows():
        if (row.get("id") == workflow_id
                or row.get("workflow_id") == workflow_id):
            catalog_row_found = True
            deployment = row.get("deployment")
            if isinstance(deployment, dict) and deployment.get(
                    "canonical_workflow_id"):
                catalog_scope = (
                    str(deployment.get("tenant_id") or ""),
                    str(deployment.get("workspace_id") or ""),
                )
            break

    sql_row_found = False
    sql_scope = None
    sql_generated = False
    sql_available = True
    try:
        from core.database import get_db_session
        from core.models import Workflow

        with get_db_session() as db:
            workflow = db.query(Workflow).filter(
                Workflow.id == workflow_id).first()
            if workflow is not None:
                sql_row_found = True
                configuration = workflow.configuration
                if isinstance(configuration, dict):
                    generation = configuration.get("generation") or {}
                    sql_generated = bool(
                        configuration.get("schema")
                        == "orch-workflow-blueprint-1"
                        or configuration.get("blueprint_id")
                        or (isinstance(generation, dict)
                            and generation.get("profile")
                            == "workflow_blueprint"))
                    if sql_generated:
                        sql_scope = (
                            str(workflow.tenant_id or ""),
                            str(configuration.get("workspace_id") or ""),
                        )
    except Exception as exc:  # noqa: BLE001 — missing authority is unknown
        logger.warning(
            "Could not resolve workflow scope %s: %s", workflow_id, exc)
        sql_available = False

    if catalog_scope is not None:
        if sql_row_found and not sql_generated:
            return {"kind": "generated", "tenant_id": "",
                    "workspace_id": "", "contradictory": True}
        if sql_scope is not None and catalog_scope != sql_scope:
            return {"kind": "generated", "tenant_id": "",
                    "workspace_id": "", "contradictory": True}
        return {"kind": "generated", "tenant_id": catalog_scope[0],
                "workspace_id": catalog_scope[1]}
    if sql_generated:
        if catalog_row_found:
            return {"kind": "generated", "tenant_id": "",
                    "workspace_id": "", "contradictory": True}
        if sql_scope is None:
            return {"kind": "generated", "tenant_id": "",
                    "workspace_id": "", "contradictory": True}
        return {"kind": "generated", "tenant_id": sql_scope[0],
                "workspace_id": sql_scope[1]}
    if catalog_row_found or sql_row_found:
        # Positively identified existing legacy row: preserve compatibility.
        return {"kind": "legacy"}
    if not sql_available:
        return {"kind": "unknown", "reason": "authority_lookup_unavailable"}
    return {"kind": "unknown", "reason": "no_authoritative_row"}


def _scope_matches_user(user: User, tenant_id: str, workspace_id: str) -> bool:
    if not tenant_id or not workspace_id:
        return False
    scope = _caller_scope(user)
    return (str(tenant_id) == scope["tenant_id"]
            and str(workspace_id) == scope["workspace_id"])


def _authorize_generated_read(user: User, workflow_id: str) -> bool:
    """Refuse foreign/unknown generated reads; legacy only when positive."""
    resolved = _generated_definition_scope(workflow_id)
    kind = resolved.get("kind")
    if kind == "generated":
        return _scope_matches_user(
            user, resolved.get("tenant_id"), resolved.get("workspace_id"))
    if kind == "legacy":
        return True
    # Unknown/missing authority is not a positive legacy grant.
    return False


def _row_server_scope(row: Any) -> tuple:
    """Server-bound execution scope from the durable row/context."""
    tenant_id = str(getattr(row, "tenant_id", None) or "")
    workspace_id = ""
    try:
        context = json.loads(getattr(row, "context", None) or "{}")
        variables = context.get("variables") if isinstance(
            context, dict) else None
        if isinstance(variables, dict):
            tenant_id = str(variables.get("tenant_id") or tenant_id or "")
            workspace_id = str(variables.get("workspace_id") or "")
    except (TypeError, ValueError):
        pass
    return tenant_id, workspace_id


def _authorize_execution_row(user: User, row: Any) -> bool:
    resolved = _generated_definition_scope(str(row.workflow_id))
    kind = resolved.get("kind")
    if kind == "generated":
        return _scope_matches_user(
            user, resolved.get("tenant_id"), resolved.get("workspace_id"))
    if kind == "legacy":
        return True
    tenant_id, workspace_id = _row_server_scope(row)
    return _scope_matches_user(user, tenant_id, workspace_id)


def _authorize_runtime_scope(user: User, definition_id: str, variables: Any) -> bool:
    resolved = _generated_definition_scope(definition_id)
    kind = resolved.get("kind")
    if kind == "generated":
        return _scope_matches_user(
            user, resolved.get("tenant_id"), resolved.get("workspace_id"))
    if kind == "legacy":
        return True
    if not isinstance(variables, dict):
        return False
    return _scope_matches_user(
        user, variables.get("tenant_id"), variables.get("workspace_id"))


def _authorize_workflow_history(user: User, workflow_id: str, rows: List[Any]) -> bool:
    resolved = _generated_definition_scope(workflow_id)
    kind = resolved.get("kind")
    if kind == "generated":
        return _scope_matches_user(
            user, resolved.get("tenant_id"), resolved.get("workspace_id"))
    if kind == "legacy":
        return True
    # Unknown authority: every durable row must carry a server-bound scope
    # that matches; a mixed or unscoped history is refused.
    if not rows:
        return False
    return all(_authorize_execution_row(user, row) for row in rows)


def _definition_material_from_view(view: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild the exact compiler material from a persisted blueprint view."""
    return {
        "architecture_name": view.get("architecture_name"),
        "description": view.get("description") or "",
        "execution_mode": view.get("execution_mode"),
        "start_step": view.get("start_step"),
        "nodes": list(view.get("nodes") or []),
        "steps": list(view.get("steps") or []),
        "triggers": list(view.get("triggers") or []),
        "required_integrations": list(
            view.get("required_integrations") or []),
        "execution_ready": bool(view.get("execution_ready", True)),
        "execution_blockers": list(view.get("execution_blockers") or []),
    }


def _recompute_definition_digest(view: Dict[str, Any]) -> str:
    material = _definition_material_from_view(view)
    return hashlib.sha256(json.dumps(
        material, sort_keys=True, default=str).encode()).hexdigest()


def _compiled_from_view(view: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal compiled shape accepted by register_compiled_workflow."""
    return {
        "workflow_id": str(view.get("workflow_id") or ""),
        "architecture_name": str(view.get("architecture_name") or ""),
        "description": str(view.get("description") or ""),
        "steps": list(view.get("steps") or []),
        "start_step": str(view.get("start_step") or ""),
        "definition_digest": str(view.get("definition_digest") or ""),
        "execution_ready": bool(view.get("execution_ready", True)),
        "execution_blockers": list(view.get("execution_blockers") or []),
    }


def _project_blueprint_to_catalog(
    view: Dict[str, Any], *, deployment: Dict[str, Any],
) -> Dict[str, Any]:
    """A display projection plus a reference to the canonical SQL blueprint.

    The projection is not execution authority. The execute/schedule paths
    detect ``deployment.canonical_workflow_id`` and reload the scoped SQL
    definition through the compiler/orchestrator.
    """
    steps = list(view.get("steps") or [])
    nodes = []
    connections = []
    for index, raw in enumerate(steps):
        nodes.append({
            "id": str(raw.get("step_id")),
            "type": str(raw.get("step_type") or "action"),
            "title": str(raw.get("description") or raw.get("step_id")),
            "description": str(raw.get("description") or ""),
            "position": {"x": 100.0, "y": 100.0 + (index * 120.0)},
            "config": {},
            "connections": list(raw.get("next_steps") or []),
        })
        for target in raw.get("next_steps") or []:
            connections.append({
                "id": f"{raw.get('step_id')}->{target}",
                "source": str(raw.get("step_id")),
                "target": str(target),
            })
    trigger_labels = []
    for trigger in view.get("triggers") or []:
        label = (trigger.get("schedule")
                 or trigger.get("trigger_event")
                 or trigger.get("condition")
                 or "manual")
        trigger_labels.append(str(label))
    return {
        "id": str(view.get("workflow_id") or ""),
        "name": str(view.get("architecture_name") or "Generated workflow"),
        "description": str(view.get("description") or ""),
        "version": "1.0",
        "nodes": nodes,
        "connections": connections,
        "triggers": trigger_labels or ["manual"],
        "enabled": True,
        "deployment": dict(deployment),
    }


def _deploy_operation_id(
    *, tenant_id: str, workspace_id: str, workflow_id: str,
    definition_digest: str, approval_id: Optional[str],
) -> str:
    material = "|".join([
        tenant_id, workspace_id, workflow_id, definition_digest,
        str(approval_id or ""),
    ])
    return "deploy_" + hashlib.sha256(material.encode()).hexdigest()[:24]


def _read_catalog_row(workflow_id: str) -> Optional[Dict[str, Any]]:
    # Strict: deployment replay/readback must never treat an unreadable
    # authoritative catalog as empty.
    for row in load_workflows_strict():
        if row.get("id") == workflow_id or row.get("workflow_id") == workflow_id:
            return row
    return None


def _row_matches_deployment(
    row: Optional[Dict[str, Any]], *, workflow_id: str,
    definition_digest: str, tenant_id: str, workspace_id: str,
    operation_id: str,
) -> bool:
    if not row:
        return False
    deployment = row.get("deployment")
    if not isinstance(deployment, dict):
        return False
    return (
        str(row.get("id") or row.get("workflow_id")) == workflow_id
        and str(deployment.get("definition_digest")) == definition_digest
        and str(deployment.get("tenant_id")) == tenant_id
        and str(deployment.get("workspace_id")) == workspace_id
        and str(deployment.get("operation_id")) == operation_id
    )


def _deploy_approval_material(
    view: Dict[str, Any], *, scope: Dict[str, str],
    agent_id: str, trigger_type: str,
) -> Dict[str, Any]:
    return {
        "workflow_id": str(view.get("workflow_id")),
        "blueprint_id": view.get("blueprint_id"),
        "definition_digest": str(view.get("definition_digest")),
        "tenant_id": scope["tenant_id"],
        "workspace_id": scope["workspace_id"],
        "requested_by": scope["user_id"],
        "executor_agent_id": agent_id,
        "execution_mode": str(view.get("execution_mode") or "one_off"),
        "trigger_type": trigger_type,
        "deployment_action": "deploy_generated_workflow",
    }


def _find_or_create_deploy_approval(
    db: Session, *, material: Dict[str, Any], reason: str,
) -> str:
    from core.agent_governance_service import AgentGovernanceService
    from core.models import HITLAction

    existing = db.query(HITLAction).filter(
        HITLAction.action_type == "deploy_workflow",
        HITLAction.status == "pending",
        HITLAction.tenant_id == material["tenant_id"],
        HITLAction.workspace_id == material["workspace_id"],
    ).all()
    for row in existing:
        params = row.params or {}
        if (str(params.get("workflow_id")) == material["workflow_id"]
                and str(params.get("definition_digest"))
                == material["definition_digest"]
                and str(params.get("executor_agent_id"))
                == material["executor_agent_id"]):
            return row.id
    governance = AgentGovernanceService(
        db,
        workspace_id=material["workspace_id"],
        tenant_id=material["tenant_id"],
    )
    return governance.request_approval(
        agent_id=material["executor_agent_id"],
        action_type="deploy_workflow",
        params=dict(material),
        reason=reason,
        user_id=material["requested_by"] or None,
    )


def _check_deploy_approval(
    db: Session, *, approval_id: str, material: Dict[str, Any],
) -> Dict[str, Any]:
    """Read-only decision check; no mutation."""
    from core.models import HITLAction

    row = db.query(HITLAction).filter(
        HITLAction.id == approval_id,
        HITLAction.action_type == "deploy_workflow",
        HITLAction.tenant_id == material["tenant_id"],
        HITLAction.workspace_id == material["workspace_id"],
    ).first()
    if row is None:
        return {"decision": "not_found"}
    params = row.params or {}
    for key in ("workflow_id", "definition_digest", "executor_agent_id"):
        if str(params.get(key)) != str(material.get(key)):
            return {"decision": "mismatch", "approval_id": row.id}
    if params.get("deployment_consumed"):
        return {"decision": "already_consumed", "approval_id": row.id}
    if row.status != "approved":
        return {"decision": str(row.status or "unknown"),
                "approval_id": row.id}
    return {"decision": "approved", "approval_id": row.id}


def _consume_deploy_approval(
    db: Session, *, approval_id: str, material: Dict[str, Any],
) -> Dict[str, Any]:
    """Mark an already-verified approved material as consumed (idempotent)."""
    from core.models import HITLAction

    row = db.query(HITLAction).filter(
        HITLAction.id == approval_id,
        HITLAction.action_type == "deploy_workflow",
        HITLAction.tenant_id == material["tenant_id"],
        HITLAction.workspace_id == material["workspace_id"],
    ).first()
    if row is None:
        return {"decision": "not_found"}
    params = row.params or {}
    for key in ("workflow_id", "definition_digest", "executor_agent_id"):
        if str(params.get(key)) != str(material.get(key)):
            return {"decision": "mismatch", "approval_id": row.id}
    if params.get("deployment_consumed"):
        return {"decision": "already_consumed", "approval_id": row.id,
                "consumed": True}
    if row.status != "approved":
        return {"decision": str(row.status or "unknown"),
                "approval_id": row.id}
    updated = dict(params)
    updated["deployment_consumed"] = dict(material)
    row.params = updated
    db.commit()
    return {"decision": "consumed", "approval_id": row.id,
            "consumed": True}


def _scoped_agent(db: Session, agent_id: str, scope: Dict[str, str]):
    from core.models import AgentRegistry

    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == agent_id).first()
    if agent is None:
        return None
    agent_tenant = str(agent.tenant_id or "default")
    agent_workspace = str(agent.workspace_id or "default")
    if agent_tenant != scope["tenant_id"]:
        return None
    if agent_workspace not in (scope["workspace_id"], "default"):
        return None
    if not bool(getattr(agent, "enabled", True)):
        return None
    if str(getattr(agent, "status", "") or "").lower() in (
            "inactive", "disabled", "archived"):
        return None
    return agent


def _verify_existing_deployment(
    db: Session, existing: Dict[str, Any], *,
    workflow_id: str, view: Dict[str, Any], scope: Dict[str, str],
    stored_digest: str, recorded_agent: str, requested_agent: str,
) -> Dict[str, Any]:
    """Verify every binding before replaying already_deployed.

    Same digest alone is not enough: the canonical id, exact operation id,
    executor agent, owner, approval material and current authority must all
    still match. Any mismatch refuses without a write.
    """
    deployment = existing.get("deployment")
    if not isinstance(deployment, dict):
        return {"ok": False, "status": "not_deployed"}
    if (str(deployment.get("tenant_id")) != scope["tenant_id"]
            or str(deployment.get("workspace_id")) != scope["workspace_id"]):
        return {"ok": False, "status": "not_found"}
    reasons = []
    if str(deployment.get("canonical_workflow_id")) != workflow_id:
        reasons.append("canonical_workflow_id")
    if str(deployment.get("definition_digest")) != stored_digest:
        reasons.append("definition_digest")
    approval_id = deployment.get("approval_id")
    expected_operation = _deploy_operation_id(
        tenant_id=scope["tenant_id"], workspace_id=scope["workspace_id"],
        workflow_id=workflow_id, definition_digest=stored_digest,
        approval_id=approval_id)
    if str(deployment.get("operation_id")) != expected_operation:
        reasons.append("operation_id")
    deployed_agent = str(deployment.get("executor_agent_id") or "")
    current_agent = recorded_agent or requested_agent
    if not deployed_agent or deployed_agent != current_agent:
        reasons.append("executor_agent_id")
    if str(deployment.get("owner_user_id") or "") != scope["user_id"]:
        reasons.append("owner_user_id")

    agent = _scoped_agent(db, deployed_agent, scope) if deployed_agent else None
    if agent is None:
        reasons.append("executor_agent_unavailable")
    elif approval_id is None and not _can_deploy_directly(agent):
        reasons.append("authority_changed")

    if approval_id:
        approval_material = {
            "workflow_id": workflow_id,
            "definition_digest": stored_digest,
            "tenant_id": scope["tenant_id"],
            "workspace_id": scope["workspace_id"],
            "executor_agent_id": deployed_agent,
            "requested_by": str(deployment.get("owner_user_id") or ""),
        }
        decision = _check_deploy_approval(
            db, approval_id=str(approval_id), material=approval_material)
        if decision.get("decision") != "already_consumed":
            reasons.append(f"approval_{decision.get('decision')}")

    try:
        current_authority = _observe_deployment_authority(
            db, scope, deployed_agent, require_direct=(approval_id is None))
    except HTTPException:
        reasons.append("current_authority_changed")
    else:
        recorded_authority = deployment.get("authority")
        if not isinstance(recorded_authority, dict):
            reasons.append("authority_claim_missing")
        else:
            for key in (
                    "actor_user_id", "actor_role", "executor_agent_id",
                    "executor_maturity"):
                if str(recorded_authority.get(key)) != str(
                        current_authority.get(key)):
                    reasons.append(f"authority_{key}")
    if reasons:
        return {"ok": False, "status": "binding_mismatch",
                "reasons": reasons}
    return {"ok": True, "status": "already_deployed"}


def _current_actor(db: Session, scope: Dict[str, str]):
    """Reload the acting user from the database, not the request snapshot."""
    actor = db.query(User).filter(User.id == scope["user_id"]).first()
    if actor is None:
        return None, "actor_not_found"
    if not bool(getattr(actor, "is_active", True)):
        return None, "actor_inactive"
    if str(getattr(actor, "status", "") or "").lower() not in ("", "active"):
        return None, "actor_inactive"
    if str(actor.tenant_id or "default") != scope["tenant_id"]:
        return None, "actor_tenant_changed"
    if str(actor.workspace_id or "default") != scope["workspace_id"]:
        return None, "actor_workspace_changed"
    if not RBACService.check_permission(actor, Permission.WORKFLOW_MANAGE):
        return None, "actor_permission_revoked"
    return actor, None


def _nullsafe_condition(column, value):
    return column.is_(None) if value is None else column == value


def _load_deployment_authority(
    db: Session, scope: Dict[str, str], agent_id: str,
    *, require_direct: bool,
) -> Dict[str, Any]:
    """Validate the current actor/executor in the session's transaction."""
    from api.agent_governance_routes import get_maturity_level_from_score

    actor, denial = _current_actor(db, scope)
    if actor is None:
        raise HTTPException(status_code=403, detail={
            "error": "current_authority_changed",
            "reason": denial,
            "message": "the current actor no longer holds deployment "
                       "authority; no catalog write was attempted",
            "possible_effect": False,
        })
    agent = _scoped_agent(db, agent_id, scope) if agent_id else None
    if agent is None:
        raise HTTPException(status_code=409, detail={
            "error": "executor_authority_changed",
            "reason": "executor_agent_unavailable",
            "message": "the executor agent is no longer available in this "
                       "scope; no catalog write was attempted",
            "possible_effect": False,
        })
    maturity = get_maturity_level_from_score(
        agent.confidence_score if agent.confidence_score is not None else 0.5)
    if require_direct and not _can_deploy_directly(agent):
        raise HTTPException(status_code=409, detail={
            "error": "executor_authority_changed",
            "reason": "maturity_no_longer_allows_direct_deploy",
            "message": "the executor's current maturity requires approval; "
                       "no catalog write was attempted",
            "possible_effect": False,
        })
    return {
        "actor_user_id": str(actor.id),
        "actor_role": str(getattr(actor, "role", "") or ""),
        "actor_status": str(getattr(actor, "status", "") or ""),
        "actor_is_active": bool(getattr(actor, "is_active", False)),
        "actor_tenant_id": str(actor.tenant_id or "default"),
        "actor_workspace_id": str(actor.workspace_id or "default"),
        "executor_agent_id": str(agent.id),
        "executor_agent_status": str(getattr(agent, "status", "") or ""),
        "executor_agent_enabled": bool(getattr(agent, "enabled", False)),
        "executor_confidence_score": float(
            agent.confidence_score if agent.confidence_score is not None
            else 0.5),
        "executor_maturity": maturity,
        "observed_at": datetime.utcnow().isoformat() + "Z",
        # Exact raw values used by the conditional DML claim. Scope aliases
        # are not normalized here: a NULL scope must pin IS NULL, not
        # "default".
        "actor_raw_is_active": actor.is_active,
        "actor_raw_status": actor.status,
        "actor_raw_role": actor.role,
        "actor_raw_tenant_id": actor.tenant_id,
        "actor_raw_workspace_id": actor.workspace_id,
        "executor_raw_enabled": agent.enabled,
        "executor_raw_status": agent.status,
        "executor_raw_tenant_id": agent.tenant_id,
        "executor_raw_workspace_id": agent.workspace_id,
        "executor_raw_confidence_score": agent.confidence_score,
    }


def _observe_deployment_authority(
    db: Session, scope: Dict[str, str], agent_id: str,
    *, require_direct: bool,
) -> Dict[str, Any]:
    """Fresh-read observation used by replay/verification.

    Read-only: it does not claim and is not the write linearization point.
    """
    # End any prior read transaction so this observation sees concurrent
    # commits, then re-read. The request may have loaded these rows for its
    # first eligibility check; a stale identity map or snapshot is not
    # authority.
    db.rollback()
    db.expire_all()
    return _load_deployment_authority(
        db, scope, agent_id, require_direct=require_direct)


def _current_read_actor(db: Session, scope: Dict[str, str]):
    """Re-check a read actor's current active state, scope and view permission."""
    db.expire_all()
    actor = db.query(User).filter(User.id == scope["user_id"]).first()
    if actor is None:
        return None
    if not bool(getattr(actor, "is_active", True)):
        return None
    if str(getattr(actor, "status", "") or "").lower() not in ("", "active"):
        return None
    if str(actor.tenant_id or "default") != scope["tenant_id"]:
        return None
    if str(actor.workspace_id or "default") != scope["workspace_id"]:
        return None
    if not RBACService.check_permission(actor, Permission.WORKFLOW_VIEW):
        return None
    return actor


def _reauthorize_deployment(
    db: Session, scope: Dict[str, str], agent_id: str,
    *, require_direct: bool, approval_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    definition_digest: Optional[str] = None,
) -> Dict[str, Any]:
    """Claim the exact observed authority with guarded conditional DML.

    The claim is a no-op UPDATE whose WHERE clause pins the observed actor
    id/status/is_active/role/raw scope and executor enabled/status/maturity
    inputs/raw scope. The resulting write transaction is held across the
    catalog file RMW, so a peer revocation that commits before this claim
    makes the claim match zero rows and refuses; a peer revocation that
    commits after this authorized transaction commits is not retroactive.

    This is the honest linearization boundary: the SQL claim commit, not the
    read and not the file write alone.
    """
    from sqlalchemy import update
    from core.models import AgentRegistry, HITLAction

    # Defined authority entry for a route-owned session: end any stale read
    # transaction, then make exactly one validated raw observation. The
    # conditional UPDATE pins that exact snapshot; there is no second
    # observation and no test-only read.
    db.rollback()
    db.expire_all()
    observed = _load_deployment_authority(
        db, scope, agent_id, require_direct=require_direct)

    actor_claim = db.execute(
        update(User).where(
            User.id == observed["actor_user_id"],
            _nullsafe_condition(
                User.is_active, observed["actor_raw_is_active"]),
            _nullsafe_condition(
                User.status, observed["actor_raw_status"]),
            _nullsafe_condition(User.role, observed["actor_raw_role"]),
            _nullsafe_condition(
                User.tenant_id, observed["actor_raw_tenant_id"]),
            _nullsafe_condition(
                User.workspace_id, observed["actor_raw_workspace_id"]),
        ).values(id=User.id).execution_options(synchronize_session=False)
    )
    if actor_claim.rowcount != 1:
        raise HTTPException(status_code=403, detail={
            "error": "current_authority_changed",
            "reason": "actor_claim_mismatch",
            "message": "the acting user changed before the catalog commit; "
                       "no catalog write was attempted",
            "possible_effect": False,
        })

    agent_claim = db.execute(
        update(AgentRegistry).where(
            AgentRegistry.id == observed["executor_agent_id"],
            _nullsafe_condition(
                AgentRegistry.enabled, observed["executor_raw_enabled"]),
            _nullsafe_condition(
                AgentRegistry.status, observed["executor_raw_status"]),
            _nullsafe_condition(
                AgentRegistry.tenant_id, observed["executor_raw_tenant_id"]),
            _nullsafe_condition(
                AgentRegistry.workspace_id,
                observed["executor_raw_workspace_id"]),
            _nullsafe_condition(
                AgentRegistry.confidence_score,
                observed["executor_raw_confidence_score"]),
        ).values(id=AgentRegistry.id).execution_options(
            synchronize_session=False)
    )
    if agent_claim.rowcount != 1:
        raise HTTPException(status_code=409, detail={
            "error": "executor_authority_changed",
            "reason": "executor_claim_mismatch",
            "message": "the executor agent changed before the catalog "
                       "commit; no catalog write was attempted",
            "possible_effect": False,
        })

    if approval_id:
        approval_claim = db.execute(
            update(HITLAction).where(
                HITLAction.id == approval_id,
                HITLAction.action_type == "deploy_workflow",
                HITLAction.status == "approved",
                _nullsafe_condition(
                    HITLAction.tenant_id, observed["actor_raw_tenant_id"]),
                _nullsafe_condition(
                    HITLAction.workspace_id,
                    observed["actor_raw_workspace_id"]),
            ).values(id=HITLAction.id).execution_options(
                synchronize_session=False)
        )
        if approval_claim.rowcount != 1:
            raise HTTPException(status_code=409, detail={
                "error": "approval_binding_changed",
                "reason": "approval_claim_mismatch",
                "message": "the approval changed before the catalog commit; "
                           "no catalog write was attempted",
                "possible_effect": False,
            })
        row = db.query(HITLAction).filter(
            HITLAction.id == approval_id).populate_existing().one()
        params = row.params or {}
        expected = {
            "workflow_id": workflow_id,
            "definition_digest": definition_digest,
            "executor_agent_id": observed["executor_agent_id"],
        }
        for key, value in expected.items():
            if value is not None and str(params.get(key)) != str(value):
                raise HTTPException(status_code=409, detail={
                    "error": "approval_binding_changed",
                    "reason": "approval_params_mismatch",
                    "message": "the approval material changed before the "
                               "catalog commit; no catalog write was attempted",
                    "possible_effect": False,
                })

    observed.update({
        "claim": "guarded-conditional-noop-dml",
        "claimed_at": datetime.utcnow().isoformat() + "Z",
        "linearization": (
            "conditional SQL claim held across the catalog replace; peer "
            "revocation committed before the claim refuses; revocation after "
            "the authorized claim commit is not retroactive"),
        "approval_claimed": bool(approval_id),
    })
    return observed


def _commit_authority_claim(db: Session) -> None:
    """Release the held claim. A failure here happens after a file commit."""
    db.commit()


def _can_deploy_directly(agent) -> bool:
    from api.agent_governance_routes import (
        can_deploy_directly, get_maturity_level_from_score,
    )
    score = (agent.confidence_score
             if agent.confidence_score is not None else 0.5)
    return can_deploy_directly(
        get_maturity_level_from_score(score), score)


@router.get("/workflows", response_model=List[WorkflowDefinition])
async def get_workflows(user: User = Depends(require_permission(Permission.WORKFLOW_VIEW))):
    workflows = _visible_workflows(user)
    for w in workflows:
        _enrich_workflow(w)
    return workflows

@router.get("/workflows/{workflow_id}", response_model=WorkflowDefinition)
async def get_workflow(workflow_id: str, user: User = Depends(require_permission(Permission.WORKFLOW_VIEW))):
    workflow = _find_visible_workflow(workflow_id, user)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _enrich_workflow(workflow)

@router.post("/workflows", response_model=WorkflowDefinition)
async def create_workflow(workflow: WorkflowDefinition, user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE))):
    # R81: reject cyclic graphs at composition time (the engine would otherwise
    # execute them in arbitrary insertion order).
    _validate_workflow_dag(workflow.dict())

    # Generate ID if new
    if not workflow.id:
        workflow.id = str(uuid.uuid4())
        workflow.createdAt = datetime.now().isoformat()

    workflow.updatedAt = datetime.now().isoformat()

    workflow_dict = workflow.dict()
    # Deployment metadata is server-owned. A public create/update must never
    # grant scope, digest, agent or approval binding.
    workflow_dict.pop("deployment", None)

    def mutator(workflows: List[Dict]):
        existing_index = next(
            (i for i, w in enumerate(workflows)
             if w.get('id') == workflow.id
             or w.get('workflow_id') == workflow.id), -1)
        if existing_index >= 0:
            prior = workflows[existing_index]
            if isinstance(prior.get("deployment"), dict):
                workflow_dict["deployment"] = prior["deployment"]
            workflows[existing_index] = workflow_dict
        else:
            workflows.append(workflow_dict)
        return True, workflow_dict

    try:
        return mutate_workflows(mutator)
    except WorkflowStoreUnreadable as exc:
        raise HTTPException(status_code=503, detail={
            "error": "workflow_store_unreadable",
            "message": "the workflow catalog is unreadable; no write was "
                       "attempted and existing bytes were preserved",
            "possible_effect": False,
        }) from exc
    except WorkflowStoreLockError as exc:
        raise HTTPException(status_code=503, detail={
            "error": "workflow_store_lock_unavailable",
            "message": "the workflow catalog lock is unavailable; no write "
                       "was attempted",
            "possible_effect": False,
        }) from exc

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE))):
    existing = next(
        (w for w in load_workflows()
         if w.get('id') == workflow_id or w.get('workflow_id') == workflow_id),
        None)
    if existing is not None and not _is_visible_to_user(existing, user):
        raise HTTPException(status_code=404, detail="Workflow not found")

    def mutator(workflows: List[Dict]):
        remaining = [
            w for w in workflows
            if w.get('id') != workflow_id and w.get('workflow_id') != workflow_id
        ]
        return len(remaining) != len(workflows), {"status": "success"}

    try:
        return mutate_workflows(mutator)
    except WorkflowStoreUnreadable as exc:
        raise HTTPException(status_code=503, detail={
            "error": "workflow_store_unreadable",
            "message": "the workflow catalog is unreadable; no write was "
                       "attempted and existing bytes were preserved",
            "possible_effect": False,
        }) from exc
    except WorkflowStoreLockError as exc:
        raise HTTPException(status_code=503, detail={
            "error": "workflow_store_lock_unavailable",
            "message": "the workflow catalog lock is unavailable; no write "
                       "was attempted",
            "possible_effect": False,
        }) from exc



class DeployWorkflowRequest(BaseModel):
    definition_digest: str
    agent_id: Optional[str] = None
    approval_id: Optional[str] = None


@router.post("/workflows/{workflow_id}/deploy")
async def deploy_generated_workflow(
    workflow_id: str,
    request: DeployWorkflowRequest,
    user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE)),
    db: Session = Depends(get_db),
):
    """Save one authorized generated design as a manually runnable workflow.

    This is the additive deployment command. It never executes and never
    schedules. The durable SQL blueprint remains the execution authority; the
    JSON catalog row is a scoped projection plus reference. Pending approval
    records exactly one durable HITL row and does not write the catalog.
    """
    from core.workflow_blueprint_service import (
        load_blueprint, register_compiled_workflow,
    )

    scope = _caller_scope(user)
    view = load_blueprint(
        db,
        workflow_id=workflow_id,
        tenant_id=scope["tenant_id"],
        workspace_id=scope["workspace_id"],
    )
    if view is None:
        raise HTTPException(status_code=404, detail={
            "error": "workflow_not_found",
            "message": "workflow not found",
        })

    stored_digest = str(view.get("definition_digest") or "")
    request_digest = str(request.definition_digest or "")
    recomputed_digest = _recompute_definition_digest(view)
    if (not request_digest or not stored_digest
            or request_digest != stored_digest
            or recomputed_digest != stored_digest):
        raise HTTPException(status_code=409, detail={
            "error": "definition_digest_mismatch",
            "message": "the requested material does not match the persisted "
                       "canonical blueprint",
            "stored_digest": stored_digest,
            "recomputed_digest": recomputed_digest,
        })

    blockers = list(view.get("execution_blockers") or [])
    if not view.get("execution_ready", True):
        raise HTTPException(status_code=422, detail={
            "error": "execution_blocked",
            "message": "the blueprint is reviewable but not executable",
            "blockers": blockers,
        })

    provenance = view.get("provenance") or {}
    recorded_agent = str(
        provenance.get("requested_executor_agent_id") or "").strip()
    requested_agent = str(request.agent_id or "").strip()
    if recorded_agent and requested_agent and requested_agent != recorded_agent:
        raise HTTPException(status_code=409, detail={
            "error": "agent_binding_mismatch",
            "message": "the requested agent does not match the recorded "
                       "executor provenance",
            "recorded_agent_id": recorded_agent,
        })
    agent_id = recorded_agent or requested_agent

    # Old requests without a recorded agent remain reviewable designs. They
    # can only deploy through a fresh explicit matching review; a UI-supplied
    # higher-maturity agent never grants direct authority.
    direct = False
    if recorded_agent:
        agent = _scoped_agent(db, recorded_agent, scope)
        if agent is None:
            raise HTTPException(status_code=404, detail={
                "error": "executor_agent_unavailable",
                "message": "the recorded executor agent is not available in "
                           "this scope",
            })
        direct = _can_deploy_directly(agent)

    trigger_type = "manual"
    for trigger in view.get("triggers") or []:
        trigger_type = str(
            trigger.get("schedule") or trigger.get("trigger_event")
            or trigger.get("condition") or "manual")
        break

    # Idempotency/conflict against the existing catalog row. Replay requires
    # every binding to still match; the digest alone is not authority.
    try:
        existing = _read_catalog_row(workflow_id)
    except WorkflowStoreUnreadable as exc:
        raise HTTPException(status_code=503, detail={
            "error": "workflow_store_unreadable",
            "message": "the workflow catalog is unreadable; no write was "
                       "attempted and existing bytes were preserved",
            "possible_effect": False,
        }) from exc
    if existing is not None:
        deployment = existing.get("deployment") or {}
        if str(deployment.get("definition_digest")) != stored_digest:
            raise HTTPException(status_code=409, detail={
                "error": "workflow_material_conflict",
                "message": "a different deployed material already owns this id",
            })
        verified = _verify_existing_deployment(
            db, existing, workflow_id=workflow_id, view=view, scope=scope,
            stored_digest=stored_digest, recorded_agent=recorded_agent,
            requested_agent=requested_agent)
        if verified.get("status") == "not_found":
            raise HTTPException(status_code=404, detail={
                "error": "workflow_not_found",
                "message": "workflow not found",
            })
        if not verified.get("ok"):
            raise HTTPException(status_code=409, detail={
                "error": "deployment_binding_mismatch",
                "message": "the existing deployment no longer matches the "
                           "current actor/agent/approval bindings",
                "reasons": verified.get("reasons") or [],
            })
        return {
            "status": "already_deployed",
            "workflow_id": workflow_id,
            "definition_digest": stored_digest,
            "execution_mode": view.get("execution_mode") or "one_off",
            "manual_run_endpoint":
                f"/api/v1/workflows/workflows/{workflow_id}/execute",
            "approval_id": deployment.get("approval_id"),
            "operation_id": deployment.get("operation_id"),
            "scheduler_job_id": None,
            "message": "This design is already saved and manually "
                       "runnable; no new run or schedule was started.",
        }

    material = _deploy_approval_material(
        view, scope=scope, agent_id=agent_id or "system_default_agent",
        trigger_type=trigger_type)

    approval_id = request.approval_id
    if approval_id:
        checked = _check_deploy_approval(
            db, approval_id=approval_id, material=material)
        decision = checked["decision"]
        if decision == "not_found":
            raise HTTPException(status_code=404, detail={
                "error": "approval_not_found",
                "message": "approval not found in this scope",
            })
        if decision == "mismatch":
            raise HTTPException(status_code=409, detail={
                "error": "approval_binding_mismatch",
                "message": "the approval is not bound to this exact material",
            })
        if decision == "already_consumed":
            # Catalog should already exist; reaching here means the stores
            # disagree. Report the uncertainty instead of claiming a rollback
            # or blindly re-deploying.
            return {
                "status": "committed_unverified",
                "workflow_id": workflow_id,
                "definition_digest": stored_digest,
                "approval_id": approval_id,
                "scheduler_job_id": None,
                "message": "The approval was already consumed but the catalog "
                           "row could not be verified. Reconcile before retry.",
            }
        if decision != "approved":
            raise HTTPException(status_code=409, detail={
                "error": "approval_not_approved",
                "message": f"approval is {decision}, not approved",
                "approval_id": approval_id,
            })
    elif direct:
        pass
    else:
        approval_id = _find_or_create_deploy_approval(
            db, material=material,
            reason=(
                "Generated workflow deployment requires exact human review: "
                f"{workflow_id} ({stored_digest})."),
        )
        return {
            "status": "pending_approval",
            "workflow_id": workflow_id,
            "definition_digest": stored_digest,
            "execution_mode": view.get("execution_mode") or "one_off",
            "manual_run_endpoint":
                f"/api/v1/workflows/workflows/{workflow_id}/execute",
            "approval_id": approval_id,
            "scheduler_job_id": None,
            "message": "Submitted for approval. No workflow was activated, "
                       "executed or scheduled.",
        }

    operation_id = _deploy_operation_id(
        tenant_id=scope["tenant_id"],
        workspace_id=scope["workspace_id"],
        workflow_id=workflow_id,
        definition_digest=stored_digest,
        approval_id=approval_id,
    )
    committed_at = datetime.utcnow().isoformat() + "Z"
    deployment = {
        "schema": "generated-workflow-deployment-1",
        "operation_id": operation_id,
        "canonical_workflow_id": workflow_id,
        "canonical_blueprint_id": view.get("blueprint_id"),
        "definition_digest": stored_digest,
        "executor_agent_id": agent_id or "system_default_agent",
        "tenant_id": scope["tenant_id"],
        "workspace_id": scope["workspace_id"],
        "owner_user_id": scope["user_id"],
        "approval_id": approval_id,
        "execution_mode": view.get("execution_mode") or "one_off",
        "triggers_activated": False,
        "committed_at": committed_at,
    }
    projection = _project_blueprint_to_catalog(view, deployment=deployment)

    def mutator(workflows: List[Dict]):
        # Closest point to the atomic replace: reload actor/executor and
        # record the visible conditional claim that authorized this commit.
        deployment["authority"] = _reauthorize_deployment(
            db, scope, agent_id or "system_default_agent",
            require_direct=direct, approval_id=approval_id,
            workflow_id=workflow_id, definition_digest=stored_digest)
        projection["deployment"] = deployment
        for index, row in enumerate(workflows):
            if (row.get("id") == workflow_id
                    or row.get("workflow_id") == workflow_id):
                prior = row.get("deployment") or {}
                if str(prior.get("definition_digest")) == stored_digest:
                    return False, {"status": "already_deployed"}
                return False, {"status": "conflict"}
        workflows.append(projection)
        return True, {"status": "deployed"}

    try:
        result = mutate_workflows(mutator)
    except HTTPException:
        raise
    except WorkflowStoreUnreadable as exc:
        logger.error("Generated workflow write refused unreadable catalog: %s", exc)
        raise HTTPException(status_code=503, detail={
            "error": "workflow_store_unreadable",
            "message": "the workflow catalog is unreadable; no write was "
                       "attempted and existing bytes were preserved",
            "possible_effect": False,
        }) from exc
    except WorkflowStoreLockError as exc:
        logger.error("Generated workflow write refused unavailable lock: %s", exc)
        raise HTTPException(status_code=503, detail={
            "error": "workflow_store_lock_unavailable",
            "message": "the workflow catalog lock is unavailable; no write "
                       "was attempted",
            "possible_effect": False,
        }) from exc
    except Exception as exc:  # noqa: BLE001 — reconcile, never assume rollback
        logger.error("Generated workflow catalog write failed: %s", exc)
        try:
            row = _read_catalog_row(workflow_id)
        except WorkflowStoreUnreadable:
            row = None
        if _row_matches_deployment(
                row, workflow_id=workflow_id,
                definition_digest=stored_digest,
                tenant_id=scope["tenant_id"],
                workspace_id=scope["workspace_id"],
                operation_id=operation_id):
            return {
                "status": "committed_unverified",
                "workflow_id": workflow_id,
                "definition_digest": stored_digest,
                "approval_id": approval_id,
                "operation_id": operation_id,
                "possible_effect": True,
                "scheduler_job_id": None,
                "message": "The catalog write committed but its exact readback "
                           "raised. Reconcile before retry; this is not a "
                           "rollback or an exactly-once claim.",
            }
        raise HTTPException(status_code=503, detail={
            "error": "deployment_write_unknown",
            "message": "the catalog write raised and its exact readback did "
                       "not verify. A write may have committed; reconcile "
                       "using the operation id instead of assuming rollback "
                       "or retrying blindly",
            "operation_id": operation_id,
            "possible_effect": True,
        }) from exc

    if result["status"] == "conflict":
        raise HTTPException(status_code=409, detail={
            "error": "workflow_material_conflict",
            "message": "a different deployed material already owns this id",
        })
    if result["status"] == "already_deployed":
        try:
            concurrent = _read_catalog_row(workflow_id)
        except WorkflowStoreUnreadable as exc:
            raise HTTPException(status_code=503, detail={
                "error": "workflow_store_unreadable",
                "message": "the workflow catalog became unreadable; no "
                           "success is claimed",
                "possible_effect": True,
            }) from exc
        replay = _verify_existing_deployment(
            db, concurrent or {}, workflow_id=workflow_id, view=view,
            scope=scope, stored_digest=stored_digest,
            recorded_agent=recorded_agent, requested_agent=requested_agent)
        if not replay.get("ok"):
            raise HTTPException(status_code=409, detail={
                "error": "deployment_binding_mismatch",
                "message": "a concurrent deployment exists but does not "
                           "match the current actor/agent/approval bindings",
                "reasons": replay.get("reasons") or [],
            })
        return {
            "status": "already_deployed",
            "workflow_id": workflow_id,
            "definition_digest": stored_digest,
            "execution_mode": view.get("execution_mode") or "one_off",
            "manual_run_endpoint":
                f"/api/v1/workflows/workflows/{workflow_id}/execute",
            "approval_id": approval_id,
            "scheduler_job_id": None,
            "message": "Already saved and manually runnable.",
        }

    try:
        persisted_row = _read_catalog_row(workflow_id)
    except WorkflowStoreUnreadable:
        persisted_row = None
    verified = _row_matches_deployment(
        persisted_row, workflow_id=workflow_id,
        definition_digest=stored_digest,
        tenant_id=scope["tenant_id"],
        workspace_id=scope["workspace_id"],
        operation_id=operation_id)
    if not verified:
        raise HTTPException(status_code=503, detail={
            "error": "deployment_write_unknown",
            "message": "the catalog write returned but its exact readback did "
                       "not verify. A write may have committed; reconcile "
                       "using the operation id instead of assuming rollback",
            "operation_id": operation_id,
            "possible_effect": True,
        })

    registered = False
    try:
        registered = register_compiled_workflow(_compiled_from_view(view))
    except Exception as exc:  # noqa: BLE001 — durable catalog is primary
        logger.warning("Generated workflow stored but not registered: %s", exc)

    if approval_id:
        try:
            consumed = _consume_deploy_approval(
                db, approval_id=approval_id, material=material)
        except Exception as exc:  # noqa: BLE001
            logger.error("Deployment stored but approval marker failed: %s", exc)
            return {
                "status": "committed_unverified",
                "workflow_id": workflow_id,
                "definition_digest": stored_digest,
                "approval_id": approval_id,
                "operation_id": operation_id,
                "possible_effect": True,
                "scheduler_job_id": None,
                "message": "The workflow was saved but the approval marker "
                           "did not verify. Reconcile before retry.",
            }
        if consumed.get("decision") not in ("consumed", "already_consumed"):
            return {
                "status": "committed_unverified",
                "workflow_id": workflow_id,
                "definition_digest": stored_digest,
                "approval_id": approval_id,
                "operation_id": operation_id,
                "possible_effect": True,
                "scheduler_job_id": None,
                "message": "The workflow was saved but the approval binding "
                           "could not be consumed exactly.",
            }
    else:
        try:
            _commit_authority_claim(db)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Deployment stored but authority claim commit failed: %s", exc)
            return {
                "status": "committed_unverified",
                "workflow_id": workflow_id,
                "definition_digest": stored_digest,
                "approval_id": None,
                "operation_id": operation_id,
                "possible_effect": True,
                "scheduler_job_id": None,
                "message": "The catalog file was written but the authority "
                           "claim did not commit. Reconcile before retry; this "
                           "is a file effect, not a rollback.",
            }

    return {
        "status": "deployed",
        "workflow_id": workflow_id,
        "definition_digest": stored_digest,
        "execution_mode": view.get("execution_mode") or "one_off",
        "manual_run_endpoint":
            f"/api/v1/workflows/workflows/{workflow_id}/execute",
        "approval_id": approval_id,
        "operation_id": operation_id,
        "registered": bool(registered),
        "scheduler_job_id": None,
        "message": "Saved and manually runnable. No run or schedule was "
                   "started.",
    }


def _commit_workflow_edit(
    workflow_id: str, baseline: Dict[str, Any], modified: Dict[str, Any],
) -> Dict[str, Any]:
    """Commit one edited row under the shared RMW, never a stale list.

    The row is re-read under the lock and compared to the exact snapshot the
    edit was based on. A concurrent writer therefore wins (the edit refuses)
    instead of the edit replacing the whole old catalog and dropping rows that
    were committed during an awaited model call.
    """
    def mutator(rows: List[Dict]):
        index = next(
            (i for i, row in enumerate(rows)
             if row.get('id') == workflow_id
             or row.get('workflow_id') == workflow_id), -1)
        if index < 0:
            return False, {"status": "missing"}
        current = rows[index]
        if current != baseline:
            return False, {"status": "stale"}
        if isinstance(current.get("deployment"), dict) and current[
                "deployment"].get("canonical_workflow_id"):
            return False, {"status": "canonical"}
        rows[index] = modified
        return True, {"status": "committed"}

    try:
        return mutate_workflows(mutator)
    except WorkflowStoreUnreadable as exc:
        logger.error("Workflow edit refused unreadable catalog: %s", exc)
        return {"status": "unreadable"}
    except WorkflowStoreLockError as exc:
        logger.error("Workflow edit refused unavailable lock: %s", exc)
        return {"status": "locked"}


def _edit_refusal(response: WorkflowEditResponse, status: str) -> WorkflowEditResponse:
    messages = {
        "missing": "Workflow no longer exists; nothing was overwritten.",
        "stale": (
            "Workflow changed while it was being edited; nothing was "
            "overwritten. Reload and retry."),
        "canonical": (
            "Generated workflows keep their canonical design; this editor "
            "does not change execution. Nothing was overwritten."),
        "unreadable": (
            "The workflow catalog is unreadable; nothing was overwritten."),
        "locked": (
            "The workflow catalog is locked; nothing was overwritten."),
    }
    return WorkflowEditResponse(
        success=False,
        message=messages.get(status, "Edit was not committed."),
        modified_workflow=None,
        changes=[],
    )


async def _legacy_rule_based_edit(
    workflow_id: str,
    request: WorkflowEditRequest,
    workflows: List[Dict],
    workflow: Dict[str, Any]
) -> WorkflowEditResponse:
    """
    Original rule-based parsing for natural language workflow editing.
    Used as fallback when AI parsing is not available or fails.

    Pure with respect to the shared catalog: it edits the supplied candidate
    only. The route commits exactly one row under the shared read-modify-write
    so a stale snapshot can never replace newer rows.
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
        # Caller commits exactly this row under the shared RMW.
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
    try:
        workflows = load_workflows_strict()
    except WorkflowStoreUnreadable as exc:
        logger.error("Workflow edit refused unreadable catalog: %s", exc)
        return _edit_refusal(WorkflowEditResponse(
            success=False, message="", modified_workflow=None, changes=[]),
            "unreadable")
    workflow = next((w for w in workflows if w.get('id') == workflow_id or w.get('workflow_id') == workflow_id), None)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if isinstance(workflow.get("deployment"), dict) and workflow[
            "deployment"].get("canonical_workflow_id"):
        return _edit_refusal(WorkflowEditResponse(
            success=False, message="", modified_workflow=None, changes=[]),
            "canonical")

    baseline = copy.deepcopy(workflow)
    candidate = copy.deepcopy(workflow)
    command = request.command
    changes = []

    def commit_or_refuse(modified_workflow, message, change_list=None):
        commit = _commit_workflow_edit(
            workflow_id, baseline, modified_workflow)
        if commit.get("status") != "committed":
            return _edit_refusal(WorkflowEditResponse(
                success=False, message="", modified_workflow=None,
                changes=[]), str(commit.get("status")))
        return WorkflowEditResponse(
            success=True,
            message=message,
            modified_workflow=modified_workflow,
            changes=change_list if change_list is not None else changes,
        )

    try:
        # Use AI-powered editor if available, otherwise fallback to rule-based
        if AI_EDITOR_AVAILABLE:
            editor = await get_workflow_editor()

            # Parse command with AI
            edit_plan = await editor.parse_workflow_edit_command(command, candidate)

            if edit_plan.confidence < 0.3:
                logger.warning(f"AI parsing low confidence: {edit_plan.confidence}. Command: {command}")
                # Fallback to rule-based parsing
                edit_plan = editor._rule_based_parse(command.lower(), candidate)

            # Apply edit plan
            modified_workflow = await editor.apply_edit_plan(edit_plan, candidate)

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

            # Build success message
            if edit_plan.reasoning:
                message = f"Workflow edited successfully. AI reasoning: {edit_plan.reasoning}"
            else:
                message = f"Workflow edited successfully. Confidence: {edit_plan.confidence:.2f}"

            return commit_or_refuse(modified_workflow, message)
        else:
            # Fallback to original rule-based parsing if AI editor not available
            logger.warning("AI editor not available, using rule-based parsing")
            result = await _legacy_rule_based_edit(
                workflow_id, request, workflows, candidate)
            if result.success and result.modified_workflow is not None:
                return commit_or_refuse(
                    result.modified_workflow, result.message,
                    change_list=result.changes)
            return result

    except Exception as e:
        logger.error(f"Error editing workflow with AI: {e}")
        # Fallback to rule-based parsing on error
        try:
            result = await _legacy_rule_based_edit(
                workflow_id, request, workflows, candidate)
            if result.success and result.modified_workflow is not None:
                return commit_or_refuse(
                    result.modified_workflow, result.message,
                    change_list=result.changes)
            return result
        except Exception as fallback_error:
            logger.error(f"Fallback parsing also failed: {fallback_error}")
            return WorkflowEditResponse(
                success=False,
                message="Could not understand the command.",
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

# R67 route-shadowing fix: this static path MUST be registered before
# /workflows/{workflow_id}/execute — otherwise "conductor" is captured as a
# workflow_id and the route is unreachable (404 "Workflow not found").
@router.post("/workflows/conductor/execute")
async def execute_with_conductor(
    steps: List[Dict[str, Any]] = Body(...),
    start_step: str = Body(""),
    strategy: str = Body("sequential"),
    context: Optional[Dict[str, Any]] = Body(None),
    user: User = Depends(require_permission(Permission.WORKFLOW_RUN))
):
    """Execute a workflow using the Phase 5 Conductor Agent.

    Supports 5 execution strategies: SEQUENTIAL, PARALLEL, HYBRID, ADAPTIVE,
    ROLLBACK_SAFE. The Conductor wraps the live WorkflowEngine step executor,
    adding strategy-aware dispatch (parallel, adaptive selection) and rollback
    on failure (ROLLBACK_SAFE).
    """
    from core.orchestration.conductor_agent import (
        get_conductor_agent, ExecutionStrategy, WorkflowStep,
    )

    try:
        # R67: enum values are lowercase — upper() could never match, so the
        # conductor route 422'd on every request even with a valid strategy.
        strategy_enum = ExecutionStrategy(strategy.lower())
    except ValueError:
        valid = [s.value for s in ExecutionStrategy]
        raise HTTPException(
            status_code=422,
            detail=f"Invalid strategy '{strategy}'. Must be one of: {valid}",
        )

    # R67: the conductor executes raw caller-supplied steps through the live
    # engine — gate critical MCP steps exactly like workflow execution.
    await require_workflow_executor(user, steps)

    conductor = get_conductor_agent()

    # Inject the real WorkflowEngine step executor so the Conductor runs
    # actual AI/webhook/tool steps instead of the mock stub.
    try:
        from core.workflow_engine import get_workflow_engine
        engine = get_workflow_engine()
        conductor.set_step_executor(engine._execute_step)
    except Exception:
        pass  # Falls back to mock executor if engine isn't available

    # Build WorkflowStep objects from the raw step dicts. Map common field
    # names (id → step_id) and default step_type to AGENT.
    from core.orchestration.conductor_agent import StepType
    wf_steps = []
    for s in steps:
        step_kwargs = {k: v for k, v in s.items() if k in {
            "step_id", "name", "description", "agent_id", "capability",
            "parameters", "depends_on", "next_steps", "condition",
            "parallel_group", "is_parallel_root",
        }}
        if "step_id" not in step_kwargs and "id" in s:
            step_kwargs["step_id"] = s["id"]
        step_kwargs.setdefault("step_type", StepType.AGENT)
        wf_steps.append(WorkflowStep(**step_kwargs))

    # The route accepts a plain JSON object, but the conductor works on a
    # WorkflowExecutionContext. Passing the dict through (the old behavior)
    # reached `context.started_at = ...` inside execute_workflow and 500'd every
    # conductor call that supplied context — the documented `context` field was
    # therefore unusable. Build the real execution context and keep the caller's
    # object as input/shared data.
    from core.orchestration.conductor_agent import WorkflowExecutionContext

    exec_context = WorkflowExecutionContext(
        tenant_id=getattr(user, "tenant_id", None) or "default",
        user_id=str(getattr(user, "id", "") or ""),
        workspace_id=getattr(user, "workspace_id", None) or "default",
        input_data=dict(context or {}),
        shared_context=dict(context or {}),
    )

    result = await conductor.execute_workflow(
        steps=wf_steps,
        start_step=start_step,
        context=exec_context,
        strategy=strategy_enum,
    )

    return {
        "execution_id": getattr(result, "execution_id", ""),
        "status": getattr(result, "status", "unknown"),
        "completed_steps": getattr(result, "completed_steps", 0),
        "failed_steps": getattr(result, "failed_steps", 0),
        "results": getattr(result, "step_results", []),
        "strategy_used": strategy_enum.value,
    }

async def _execute_generated_workflow(
    workflow: Dict[str, Any], *, workflow_id: str,
    input_data: Optional[Dict[str, Any]], user: User, db: Session,
) -> "ExecutionResult":
    """Run one generated design through the canonical compiled engine.

    The JSON row is only a reference. The scoped SQL blueprint is reloaded,
    its exact compiler digest is recomputed, it is re-registered through the
    existing blueprint consumer (so a fresh process can run it), and the real
    orchestrator dispatches the supported handler. HITL checkpoints inside the
    compiled definition remain mandatory.
    """
    from core.workflow_blueprint_service import (
        load_blueprint, register_compiled_workflow,
    )

    scope = _caller_scope(user)
    deployment = workflow.get("deployment") or {}
    view = load_blueprint(
        db,
        workflow_id=workflow_id,
        tenant_id=scope["tenant_id"],
        workspace_id=scope["workspace_id"],
    )
    if view is None:
        raise HTTPException(status_code=404, detail={
            "error": "workflow_not_found",
            "message": "workflow not found",
        })

    stored_digest = str(view.get("definition_digest") or "")
    recomputed_digest = _recompute_definition_digest(view)
    if (not stored_digest
            or recomputed_digest != stored_digest
            or str(deployment.get("definition_digest")) != stored_digest):
        raise HTTPException(status_code=409, detail={
            "error": "definition_changed",
            "message": "the deployed reference no longer matches the "
                       "canonical blueprint; re-deploy after review",
        })

    if not view.get("execution_ready", True):
        raise HTTPException(status_code=422, detail={
            "error": "execution_blocked",
            "message": "the blueprint is not executable",
            "blockers": list(view.get("execution_blockers") or []),
        })

    # Same critical-action gate, now over the canonical compiled steps.
    await require_workflow_executor(user, list(view.get("steps") or []))

    registered = register_compiled_workflow(_compiled_from_view(view))
    if not registered:
        raise HTTPException(status_code=503, detail={
            "error": "canonical_registration_unavailable",
            "message": "the canonical blueprint could not be registered for "
                       "manual execution; nothing was run",
        })

    from advanced_workflow_orchestrator import get_orchestrator

    context = await get_orchestrator().execute_workflow(
        workflow_id,
        input_data or {},
        execution_context={
            "tenant_id": scope["tenant_id"],
            "workspace_id": scope["workspace_id"],
            "user_id": scope["user_id"],
        },
    )
    status = getattr(context, "status", None)
    status_value = str(getattr(status, "value", status) or "unknown")
    raw_results = getattr(context, "results", {}) or {}
    results: List[Dict[str, Any]] = []
    for step_id, value in raw_results.items():
        if isinstance(value, dict):
            results.append({"step_id": step_id, **value})
        else:
            results.append({"step_id": step_id, "result": value})
    started = getattr(context, "started_at", None)
    completed = getattr(context, "completed_at", None)
    error_message = getattr(context, "error_message", None)
    return ExecutionResult(
        execution_id=str(getattr(context, "workflow_id", "") or ""),
        workflow_id=workflow_id,
        status=status_value,
        started_at=started.isoformat() if started else datetime.now().isoformat(),
        completed_at=completed.isoformat() if completed else None,
        results=results,
        errors=[str(error_message)] if error_message else [],
    )


@router.post("/workflows/{workflow_id}/execute", response_model=ExecutionResult)
async def execute_workflow(
    workflow_id: str, 
    background_tasks: BackgroundTasks,
    input_data: Optional[Dict[str, Any]] = None,
    user: User = Depends(require_permission(Permission.WORKFLOW_RUN)),
    db: Session = Depends(get_db),
):
    """Execute a workflow by ID"""
    from core.workflow_engine import get_workflow_engine

    # Load workflow; generated rows are scope-checked before use.
    workflow = _find_visible_workflow(workflow_id, user)
    if not workflow:
        # UI templates (DB WorkflowTemplate) execute through this endpoint;
        # resolve them on the fly so "Use Template → Execute" works end to end.
        workflow = _load_template_definition(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    deployment = workflow.get("deployment")
    if isinstance(deployment, dict) and deployment.get("canonical_workflow_id"):
        return await _execute_generated_workflow(
            workflow, workflow_id=workflow_id, input_data=input_data,
            user=user, db=db)

    # R81: reject cyclic graphs at execution time (read-path linearization
    # falls back to insertion order, so cycles used to execute anyway).
    _validate_workflow_dag(workflow)

    # R67: critical MCP steps (terminal, browser, messaging) execute local
    # machine actions — the same tool set agent governance gates. Members
    # may run ordinary workflows only. Node-based definitions have no
    # top-level `steps`, so resolve them (nodes → steps) before gating —
    # otherwise critical actions bypass the gate.
    await require_workflow_executor(user, _resolve_workflow_steps(workflow))

    # Create execution record
    started_at = datetime.now().isoformat()
    
    try:
        # Initialize engine
        engine = get_workflow_engine()
        
        # Execute workflow (starts in background). Freeze the authenticated
        # caller's scope into the durable execution so a governance-created
        # approval lands in the reviewer's real queue and survives a resume.
        execution_id = await engine.start_workflow(
            workflow,
            input_data or {},
            background_tasks,
            scope={
                "workspace_id": getattr(user, "workspace_id", None),
                "tenant_id": getattr(user, "tenant_id", None),
            },
        )
        
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
        # BUG-126: Previously returned HTTP 200 with a phantom execution_id
        # that was never persisted → frontend showed "Started" + spun forever.
        # Now returns a proper error response. (HTTPException is module-level;
        # a local `from fastapi import HTTPException` here would shadow it for
        # the whole function and make the 404 raises above UnboundLocalError.)
        raise HTTPException(status_code=500, detail="Workflow execution failed")

@router.post("/workflows/{execution_id}/resume")
async def resume_workflow(
    execution_id: str, 
    input_data: Dict[str, Any] = Body(...),
    user: User = Depends(require_permission(Permission.WORKFLOW_RUN))
):
    """Resume a paused workflow execution"""
    from core.execution_state_manager import get_state_manager
    from core.workflow_engine import get_workflow_engine
    from advanced_workflow_orchestrator import get_orchestrator

    engine = get_workflow_engine()
    state_manager = get_state_manager()

    # Get current state to find workflow definition
    state = await state_manager.get_execution_state(execution_id)
    if not state:
        # The durable engine has no record of this execution — fall back to the
        # advanced orchestrator (workflow UI path). It owns executions whose
        # steps are waiting for human approval.
        orchestrator = get_orchestrator()
        context = orchestrator.active_contexts.get(execution_id)
        if context is None:
            raise HTTPException(status_code=404, detail="Execution not found")

        results = getattr(context, "results", {}) or {}
        approvable = next(
            (step_id for step_id, st in results.items()
             if isinstance(st, dict) and st.get("status") == "waiting_approval"),
            None,
        )
        if approvable is None:
            raise HTTPException(
                status_code=400,
                detail="Execution has no step waiting for approval",
            )
        await orchestrator.resume_workflow(execution_id, approvable)
        return {"status": "resumed", "execution_id": execution_id}

    # Load workflow definition
    # In a real app, we might store the definition snapshot with the execution
    # For now, load current definition
    workflows = load_workflows()
    workflow = next((w for w in workflows if w.get('id') == state['workflow_id'] or w.get('workflow_id') == state['workflow_id']), None)
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow definition not found")

    # R67: resuming re-executes the remaining steps — same critical-tool gate.
    # Node-based definitions: resolve nodes → steps before gating.
    await require_workflow_executor(user, _resolve_workflow_steps(workflow))

    success = await engine.resume_workflow(execution_id, workflow, input_data)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to resume workflow")
        
    return {"status": "resumed", "execution_id": execution_id}



def _safe_json(text) -> Any:
    """Parse a Text-JSON column, tolerating null/invalid values."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _db_execution_row_to_dict(row) -> Dict[str, Any]:
    """Map a DB WorkflowExecution row to the legacy AutomationEngine shape."""
    return {
        "execution_id": row.execution_id,
        "workflow_id": row.workflow_id,
        "trigger_data": _safe_json(row.input_data),
        "start_time": row.created_at.isoformat() if row.created_at else None,
        "end_time": row.completed_at.isoformat() if row.completed_at else None,
        "status": (row.status or "unknown").lower(),
        "actions_executed": [],
        "errors": [row.error] if row.error else [],
        "results": _safe_json(row.outputs),
        "duration_ms": 0.0,
    }


def _orchestrator_execution_to_dict(execution_id: str, context) -> Dict[str, Any]:
    """Map an advanced-orchestrator context to the legacy shape."""
    results = getattr(context, "results", {}) or {}
    waiting = any(
        isinstance(st, dict) and st.get("status") == "waiting_approval"
        for st in results.values()
    )
    return {
        "execution_id": execution_id,
        "workflow_id": getattr(context, "workflow_id", ""),
        "trigger_data": getattr(context, "input_data", {}) or {},
        "start_time": None,
        "end_time": None,
        "status": "waiting" if waiting else "running",
        "actions_executed": [],
        "errors": [],
        "results": results,
        "duration_ms": 0.0,
    }


@router.get("/workflows/{workflow_id}/executions", response_model=List[Dict[str, Any]])
async def get_workflow_executions(
    workflow_id: str,
    user: User = Depends(require_permission(Permission.WORKFLOW_VIEW))
):
    """Get execution history for a workflow in the caller's scope."""
    from core.models import WorkflowExecution as WorkflowExecutionRow

    rows = []
    try:
        db = next(get_db())
        try:
            rows = db.query(WorkflowExecutionRow).filter(
                WorkflowExecutionRow.workflow_id == workflow_id
            ).all()
        finally:
            db.close()
    except Exception:
        logger.exception("Failed to read persisted execution history")

    if not _authorize_workflow_history(user, workflow_id, rows):
        raise HTTPException(status_code=404, detail="Workflow not found")

    from ai.automation_engine import AutomationEngine
    engine = AutomationEngine()
    executions = [e.to_dict() for e in engine.get_execution_history(workflow_id)]

    # Durable-engine fallback: merge DB rows already loaded for the scope
    # check, deduping against the legacy AutomationEngine executions.
    seen = {e["execution_id"] for e in executions}
    for row in rows:
        if row.execution_id in seen:
            continue
        executions.append(_db_execution_row_to_dict(row))
        seen.add(row.execution_id)

    return executions

@router.get("/workflows/executions/{execution_id}", response_model=Dict[str, Any])
async def get_execution_details(
    execution_id: str,
    user: User = Depends(require_permission(Permission.WORKFLOW_VIEW))
):
    """Get details of a specific execution in the caller's authorized scope."""
    from core.models import WorkflowExecution as WorkflowExecutionRow

    # Resolve the durable row first: cache/orchestrator fallbacks must not
    # bypass the generated workflow's authoritative scope.
    row = None
    try:
        db = next(get_db())
        try:
            row = db.query(WorkflowExecutionRow).filter(
                WorkflowExecutionRow.execution_id == execution_id
            ).first()
        finally:
            db.close()
    except Exception:
        logger.exception("Failed to read persisted execution details")
    if row is not None:
        if not _authorize_execution_row(user, row):
            raise HTTPException(status_code=404, detail="Execution not found")
        return _db_execution_row_to_dict(row)

    # Orchestrator fallback (workflow UI path).
    from advanced_workflow_orchestrator import get_orchestrator
    context = get_orchestrator().active_contexts.get(execution_id)
    if context is not None:
        variables = getattr(context, "variables", {}) or {}
        definition_id = str(
            variables.get("_workflow_definition_id")
            or getattr(context, "workflow_id", "") or "")
        if not definition_id or not _authorize_runtime_scope(
                user, definition_id, variables):
            raise HTTPException(status_code=404, detail="Execution not found")
        return _orchestrator_execution_to_dict(execution_id, context)

    # Legacy in-memory engine. An unknown/absent workflow identity fails
    # closed rather than exposing an unscoped cache entry.
    from ai.automation_engine import AutomationEngine
    engine = AutomationEngine()
    if execution_id in engine.executions:
        data = engine.executions[execution_id].to_dict()
        workflow_id = str(data.get("workflow_id") or "")
        if not workflow_id or not _authorize_generated_read(user, workflow_id):
            raise HTTPException(status_code=404, detail="Execution not found")
        return data

    raise HTTPException(status_code=404, detail="Execution not found")


def _export_token(value: Any, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-")
    return (token[:48] or fallback)


@router.get("/workflows/executions/{execution_id}/export")
async def export_execution_result(
    execution_id: str,
    user: User = Depends(require_permission(Permission.WORKFLOW_VIEW)),
    db: Session = Depends(get_db),
):
    """Download one completed execution's final results as a JSON document.

    This is a read-only projection of the fresh durable row. It never executes,
    forks, resumes, promotes or schedules anything, and it never exposes the
    stored context blob, filesystem paths or credentials.
    """
    from core.models import WorkflowExecution as WorkflowExecutionRow

    row = db.query(WorkflowExecutionRow).filter(
        WorkflowExecutionRow.execution_id == execution_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    if not _authorize_execution_row(user, row):
        raise HTTPException(status_code=404, detail="Execution not found")
    if _current_read_actor(db, _caller_scope(user)) is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    owner_id = str(row.owner_id or row.user_id or "")
    if owner_id:
        if owner_id != str(user.id):
            raise HTTPException(status_code=404, detail="Execution not found")
    else:
        resolved = _generated_definition_scope(str(row.workflow_id))
        if resolved.get("kind") != "legacy":
            # A generated execution without an owner binding is not export
            # authority; do not fall back to a workspace/global grant.
            raise HTTPException(status_code=404, detail="Execution not found")

    status = str(row.status or "").lower()
    if status != "completed":
        raise HTTPException(status_code=409, detail={
            "error": "execution_not_completed",
            "status": status or "unknown",
            "message": "only a completed execution has a downloadable result",
        })
    if row.error:
        raise HTTPException(status_code=409, detail={
            "error": "execution_has_error",
            "message": "the execution recorded an error; no success document "
                       "is available",
        })

    context = _safe_json(row.context)
    history = context.get("execution_history") if isinstance(
        context, dict) else None
    if not isinstance(history, list) or not history:
        raise HTTPException(status_code=409, detail={
            "error": "execution_history_missing",
            "message": "the execution has no complete step history; a partial "
                       "document is not offered",
        })
    failure_statuses = {
        "failed", "error", "cancelled", "canceled", "running",
        "waiting_approval", "pending", "partial",
    }
    steps = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        step_status = str(entry.get("status") or "").lower()
        if not step_status:
            raise HTTPException(status_code=409, detail={
                "error": "execution_partial",
                "message": "a step has no completed status; a partial document "
                           "is not offered",
            })
        if step_status in failure_statuses:
            raise HTTPException(status_code=409, detail={
                "error": "execution_not_completed",
                "step_id": entry.get("step_id"),
                "step_status": step_status,
                "message": "the execution contains a non-successful step; no "
                           "success document is available",
            })
        steps.append({
            "step_id": entry.get("step_id") or entry.get("step"),
            "step_type": entry.get("step_type"),
            "status": step_status,
            "error": (str(entry.get("error"))[:500]
                      if entry.get("error") else None),
        })

    try:
        outputs = json.loads(row.outputs or "{}")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail={
            "error": "execution_output_unreadable",
            "message": "the persisted output is unreadable; no document is "
                       "offered",
        }) from exc
    if not isinstance(outputs, dict) or not outputs:
        raise HTTPException(status_code=409, detail={
            "error": "execution_has_no_output",
            "message": "the completed execution has no final business output",
        })
    for value in outputs.values():
        if isinstance(value, dict) and str(
                value.get("status") or "").lower() in failure_statuses:
            raise HTTPException(status_code=409, detail={
                "error": "execution_not_completed",
                "message": "the final output contains a non-successful step",
            })

    def iso(value):
        return value.isoformat() if value is not None else None

    document = {
        "schema": "atom.workflow.execution-result.v1",
        "execution": {
            "execution_id": row.execution_id,
            "workflow_id": row.workflow_id,
            "status": status,
            "created_at": iso(row.created_at),
            "completed_at": iso(row.completed_at),
            "user_id": row.user_id,
            "owner_id": row.owner_id,
        },
        "workflow": {"workflow_id": row.workflow_id},
        "results": outputs,
        "steps": steps,
        "provenance": {
            "source": "durable_workflow_execution",
            "result_field": "outputs",
            "document_version": 1,
            "workflow_id": row.workflow_id,
            "execution_id": row.execution_id,
        },
    }
    body = (json.dumps(
        document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    filename = (
        "workflow-"
        + _export_token(row.workflow_id, "workflow")
        + "-execution-"
        + _export_token(row.execution_id, "execution")
        + ".json"
    )
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(body)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "ETag": f'"sha256:{digest}"',
        },
    )


# Scheduling Endpoints

@router.post("/workflows/{workflow_id}/schedule")
async def schedule_workflow(
    workflow_id: str, 
    schedule_config: Dict[str, Any] = Body(...),
    user: User = Depends(require_permission(Permission.WORKFLOW_RUN)),
    db: Session = Depends(get_db),
):
    """
    Schedule a workflow execution.
    
    schedule_config should contain:
    - trigger_type: 'cron', 'interval', or 'date'
    - trigger_config: Dict with trigger params (e.g. {'minutes': 30} for interval)
    - input_data: Optional input data
    """
    from ai.workflow_scheduler import workflow_scheduler

    # R67: scheduling defers execution with no per-run auth — gate critical
    # MCP steps up front so members cannot queue terminal workflows.
    workflow = _find_visible_workflow(workflow_id, user)
    if not workflow:
        # DB templates (WorkflowTemplate) live outside workflows.json — the
        # same fallback execute_workflow uses, so templates are schedulable.
        workflow = _load_template_definition(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    deployment = workflow.get("deployment")
    if isinstance(deployment, dict) and deployment.get("canonical_workflow_id"):
        from core.workflow_blueprint_service import load_blueprint
        scope = _caller_scope(user)
        view = load_blueprint(
            db, workflow_id=workflow_id,
            tenant_id=scope["tenant_id"],
            workspace_id=scope["workspace_id"],
        )
        if view is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        if _recompute_definition_digest(view) != str(
                view.get("definition_digest") or ""):
            raise HTTPException(status_code=409, detail={
                "error": "definition_changed",
                "message": "re-deploy the changed design before scheduling",
            })
        await require_workflow_executor(user, list(view.get("steps") or []))
    else:
        # Node-based definitions: resolve nodes → steps before gating.
        await require_workflow_executor(user, _resolve_workflow_steps(workflow))

    try:
        trigger_type = schedule_config.get('trigger_type')
        trigger_config = schedule_config.get('trigger_config')
        input_data = schedule_config.get('input_data')

        # Freeze the scheduling user's authoritative scope into the persisted
        # job args: the deferred fire has no request principal, and a later
        # approval must still land in that user's tenant/workspace queue.
        from core.workflow_engine import freeze_execution_scope
        input_data = freeze_execution_scope(
            input_data,
            workspace_id=getattr(user, "workspace_id", None),
            tenant_id=getattr(user, "tenant_id", None),
        )
        
        if not trigger_type or not trigger_config:
            raise HTTPException(status_code=400, detail="Missing trigger_type or trigger_config")    
        # R69: record whether the scheduling user may run critical definitions.
        # The scheduler fire skips critical defs unless authorized was captured
        # as True (WORKFLOW_MANAGE) at schedule time.
        authorized = RBACService.check_permission(user, Permission.WORKFLOW_MANAGE)
        job_id = workflow_scheduler.schedule_workflow(workflow_id, trigger_type, trigger_config, input_data, authorized=authorized)
        
        return {"success": True, "job_id": job_id, "message": f"Workflow scheduled with ID {job_id}"}
        
    except HTTPException:
        # R79: the missing-config 400 must not be masked as a 500 by the
        # broad handler below.
        raise
    except (ValueError, TypeError) as e:
        # R81: invalid trigger configs (e.g. CronTrigger kwargs with an
        # unknown key) raise TypeError from APScheduler — previously only
        # ValueError was mapped to 400, so bad user input surfaced as a 500.
        raise HTTPException(status_code=400, detail="Internal error")
    except Exception as e:
        logger.error(f"Scheduling failed: {e}")
        raise HTTPException(status_code=500, detail="Internal error")

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

@router.post("/scheduler/reload")
async def reload_scheduler_jobs(user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE))):
    """Reload system jobs from user preferences"""
    from ai.workflow_scheduler import workflow_scheduler
    try:
        workflow_scheduler.reload_system_jobs()
        return {"status": "success", "message": "System pipelines reloaded from preferences"}
    except Exception as e:
        logger.error(f"Failed to reload scheduler: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


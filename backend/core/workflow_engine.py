"""
Production Workflow Engine

Handles the execution of workflows with support for:
- State persistence via ExecutionStateManager
- Pause/Resume logic for missing inputs
- Many-to-many data mapping
- Automatic retries and error handling
"""

import asyncio
import copy
from core.asyncio_compat import get_event_loop, iscoroutinefunction
import json
from datetime import datetime, timezone
import logging
import os
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union
import uuid
import httpx
import jsonschema
from jsonschema import ValidationError, validate

from core.auto_healing import async_retry_with_backoff
from core.database import get_db_session
from core.exceptions import (
    AgentExecutionError,
    AuthenticationError,
    ExternalServiceError,
    ValidationError as AtomValidationError,
)
from core.llm.byok_handler import _CallerDeadlineExceeded
from core.execution_state_manager import (
    EXECUTION_SCOPE_KEY,
    ExecutionStateManager,
    frozen_execution_identity,
    get_state_manager,
    normalize_execution_identity,
    normalize_scope_token,
)
from core.models import IntegrationCatalog, WorkflowExecutionLog, WorkflowSnapshot, AgentRegistry
from core.token_storage import token_storage
from core.websockets import get_connection_manager
from core.service_factory import ServiceFactory
from core.workflow_notifier import notifier
from core.marketplace_usage_tracker import MarketplaceUsageTracker
import threading

# Stripe integration (SaaS-specific)
try:
    from integrations.stripe_service import StripeService
    HAS_STRIPE = True
except ImportError:
    # Stripe is SaaS-specific billing integration
    StripeService = None
    HAS_STRIPE = False

logger = logging.getLogger(__name__)

# Internal marker the dispatcher attaches to every step (regardless of the
# primary service, so an ``ai`` fallback is covered too). It carries ONLY the
# caller scope frozen into the persisted execution inputs; it is never read
# from the workflow definition or params.
AI_EXECUTION_SCOPE_KEY = "_atom_ai_execution_scope"

# The single authoritative step identity/context attached by every dispatcher
# path (linear and graph). It carries the real execution id, the real step id
# and the caller identity frozen into the persisted execution inputs
# (tenant/workspace/user). Definition-supplied copies and step parameters are
# never consulted; the runner overwrites this marker on a run-local step.
# Durable writers (e.g. the goal write and notification services) bind the
# exact principal, scope and operation to this context only.
EXECUTION_IDENTITY_KEY = "_atom_execution_identity"

def _normalize_step_identity_context(value: Any) -> Dict[str, str]:
    """Normalize the internal step context, including execution/step ids.

    Only the dedicated marker is ever passed here. The identity portion is
    limited to the same provable tenant/workspace/user tokens used by the
    durable writer, and the execution/step ids are normalized as opaque
    strings. Missing values are dropped rather than invented.
    """
    context = normalize_execution_identity(
        value if isinstance(value, dict) else None)
    if isinstance(value, dict):
        for key in ("execution_id", "step_id"):
            token = normalize_scope_token(value.get(key))
            if token:
                context[key] = token
    return context


def _step_identity_context(
    execution_id: Any,
    step_id: Any,
    identity: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Build the authoritative context from server-owned run material.

    ``identity`` is the trusted identity frozen into the persisted execution
    inputs. ``execution_id``/``step_id`` are the real ids supplied by the
    dispatcher, not values read from the definition or step parameters.
    """
    context = normalize_execution_identity(identity)
    execution_token = normalize_scope_token(execution_id)
    step_token = normalize_scope_token(step_id)
    if execution_token:
        context["execution_id"] = execution_token
    if step_token:
        context["step_id"] = step_token
    return context


def _attach_step_identity_context(
    step: Dict[str, Any],
    *,
    execution_id: Any,
    step_id: Any,
    identity: Optional[Dict[str, Any]],
    ai_scope: Optional[Dict[str, str]],
    workspace_id: Optional[str],
    tenant_id: Optional[str],
) -> None:
    """Install the one authoritative runtime context on a dispatched step.

    Every definition/input claim of execution id or scope is overwritten (or
    removed), so a workflow author cannot bind a durable write to another run
    or principal. Top-level execution/workspace/tenant keys are kept for the
    existing ``mcp`` contract; ``ai`` keeps its dedicated frozen-only marker.
    """
    context = _step_identity_context(execution_id, step_id, identity)
    step["execution_id"] = context.get("execution_id")
    step["workspace_id"] = workspace_id
    step["tenant_id"] = tenant_id
    step["user_id"] = context.get("user_id")
    step[EXECUTION_IDENTITY_KEY] = context
    step[AI_EXECUTION_SCOPE_KEY] = ai_scope
    # The legacy candidate used the persisted-input key as a step fallback.
    # It is removed so only the authoritative context can name the run.
    step.pop(EXECUTION_SCOPE_KEY, None)


def _stable_operation_id(prefix: str, execution_id: str, step_id: str) -> str:
    """Return a stable, persistence-safe operation id for one step effect."""
    operation_id = f"{prefix}:{execution_id}:{step_id}"
    if not re.fullmatch(r"[A-Za-z0-9:_-]{1,180}", operation_id):
        import hashlib

        operation_id = (
            f"{prefix}:"
            + hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
        )
    return operation_id


def _ai_failure(
    action: str,
    error: str,
    failure_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the fixed, public failure envelope for the legacy AI service."""
    result: Dict[str, Any] = {
        "action": action,
        "status": "error",
        "error": error,
    }
    if failure_reason:
        result["failure_reason"] = failure_reason
    return result


def freeze_execution_scope(
    input_data: Optional[Dict[str, Any]],
    *,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach the caller's authoritative scope to execution inputs.

    Call this only AFTER authentication. Any client-supplied value under the
    reserved key is discarded first; missing scope values are not invented —
    the engine falls back to the workflow definition's own scope. Values are
    normalized to plain JSON/pickle-safe tokens (never provider or ORM
    objects), so a persisted scheduled job can round-trip them.
    """
    frozen = dict(input_data) if isinstance(input_data, dict) else {}
    frozen.pop(EXECUTION_SCOPE_KEY, None)
    scope: Dict[str, str] = {}
    for key, value in (
        ("workspace_id", workspace_id),
        ("tenant_id", tenant_id),
        ("user_id", user_id),
    ):
        text = normalize_scope_token(value)
        if text:
            scope[key] = text
    if scope:
        frozen[EXECUTION_SCOPE_KEY] = scope
    return frozen


def strip_execution_scope(input_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Drop the reserved scope key from untrusted resume inputs."""
    cleaned = dict(input_data) if isinstance(input_data, dict) else {}
    cleaned.pop(EXECUTION_SCOPE_KEY, None)
    return cleaned


def frozen_execution_scope(
    input_data: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Trusted scope persisted in server-owned job args / execution inputs.

    The scheduler calls this to re-supply the scope frozen at schedule time to
    ``start_workflow``. Only the reserved marker is read; it is never derived
    from job input keys or workflow metadata.
    """
    return frozen_execution_identity(input_data)


def _as_aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Return ``value`` as an aware UTC datetime.

    SQLite round-trips ``DateTime`` columns without timezone information, so a
    value written as aware UTC is read back naive. Treat such a stored value as
    UTC instead of failing arithmetic against a fresh aware timestamp; values
    that already carry a timezone remain valid and are normalized to UTC.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# Text-only model dispatch services. A workflow-engine deadline on these has a
# narrower retry contract than an ordinary integration call: the provider
# worker can still be in flight after ``wait_for`` stops awaiting it.
_TEXT_MODEL_SERVICES = frozenset({"main_agent", "ai"})


def _retry_step_failure(exc: BaseException) -> bool:
    """Retry every step failure except the model timeout subtype."""
    return not isinstance(exc, ModelStepTimeoutError)


def _step_timeout_error(
    service: str,
    step_id: str,
    timeout: float,
    *,
    message: Optional[str] = None,
) -> "StepTimeoutError":
    """Build the typed timeout for one executor dispatch.

    ``main_agent`` and ``ai`` are text-model dispatches and use the
    non-retryable subtype; every other service retains the existing retryable
    timeout behavior.
    """
    error_type = (
        ModelStepTimeoutError
        if service in _TEXT_MODEL_SERVICES
        else StepTimeoutError
    )
    return error_type(
        message or f"Step {step_id} timed out after {timeout} seconds",
        step_id=step_id,
        timeout=timeout,
    )


class WorkflowEngine:
    #: Canonical service registry names. The bound executor methods are
    #: resolved lazily in ``_service_registry`` so tests can still replace a
    #: handler on an instance. Catalog-template admission reads
    #: ``supported_services`` instead of duplicating this list.
    _SERVICE_HANDLER_METHODS = {
        "slack": "_execute_slack_action",
        "asana": "_execute_asana_action",
        "github": "_execute_github_action",
        "email": "_execute_email_action",
        "gmail": "_execute_gmail_action",
        "outlook": "_execute_outlook_action",
        "jira": "_execute_jira_action",
        "trello": "_execute_trello_action",
        "stripe": "_execute_stripe_action",
        "shopify": "_execute_shopify_action",
        "zoho_crm": "_execute_zoho_crm_action",
        "zoho_books": "_execute_zoho_books_action",
        "zoho_inventory": "_execute_zoho_inventory_action",
        "hubspot": "_execute_hubspot_action",
        "salesforce": "_execute_salesforce_action",
        "discord": "_execute_discord_action",
        "zoom": "_execute_zoom_action",
        "notion": "_execute_notion_action",
        "calendar": "_execute_calendar_action",
        "database": "_execute_database_action",
        "ai": "_execute_ai_action",
        "webhook": "_execute_webhook_action",
        "mcp": "_execute_mcp_action",
        "main_agent": "_execute_main_agent_action",
        "workflow": "_execute_workflow_action",
        "email_automation": "_execute_email_automation_action",
        "goal_management": "_execute_goal_management_action",
        "workflow_notification": "_execute_workflow_notification_action",
    }

    @classmethod
    def supported_services(cls) -> frozenset:
        """Return the service names with a real dispatch handler."""
        return frozenset(cls._SERVICE_HANDLER_METHODS)

    def _service_registry(self) -> Dict[str, Any]:
        return {
            name: getattr(self, method_name)
            for name, method_name in self._SERVICE_HANDLER_METHODS.items()
        }

    def __init__(self, max_concurrent_steps: int = 5):
        self.state_manager = get_state_manager()
        # Regex for finding variable references like ${step_id.output_key}
        self.var_pattern = re.compile(r'\${([^}]+)}')
        self.max_concurrent_steps = max_concurrent_steps
        self.semaphore = asyncio.Semaphore(max_concurrent_steps)
        self.cancellation_requests = set()
        # Strong references to background execution tasks. Python's asyncio
        # only keeps a weak ref to create_task results; without a strong ref
        # the task can be GC'd and silently cancelled mid-execution.
        self._background_tasks: set = set()

    def _publish_orchestration_event(self, event_type_name: str, workflow_id: str,
                                     execution_id: str, step_id: str = "",
                                     data: Dict[str, Any] = None) -> None:
        """Publish a Phase-5 EventBus event for workflow lifecycle observability.

        Best-effort: a failure (e.g. EventBus unavailable) is logged and swallowed
        so it never affects the workflow execution itself. This makes every live
        workflow feed the Phase-5 EventBus, enabling event-driven triggers
        (``create_workflow_trigger``) — the marketed "event-driven workflow
        triggering with pub/sub."
        """
        try:
            from core.orchestration.event_bus import get_event_bus, EventType
            event_bus = get_event_bus()
            event_type = getattr(EventType, event_type_name, None)
            if event_type is None:
                return
            event_bus.publish(
                event_type=event_type,
                source=execution_id,
                data={"workflow_id": workflow_id, "execution_id": execution_id,
                      "step_id": step_id, **(data or {})},
                source_type="workflow",
            )
        except Exception as e:
            logger.debug(f"Orchestration event publish skipped (non-fatal): {e}")

    async def _durable_cancellation_observed(self, execution_id: str) -> bool:
        """Read the durable status shared by every engine instance.

        The in-process ``cancellation_requests`` set only covers the engine
        that accepted a request. A cancellation committed by another engine
        instance (or by the API/UI surface) is visible through the execution
        row's status, which every dispatch boundary re-reads.
        """
        try:
            state = await self.state_manager.get_execution_state(execution_id)
        except Exception as exc:  # noqa: BLE001 — status guard still applies
            logger.warning(
                "workflow %s: execution state lookup failed: %s",
                execution_id, exc)
            return False
        return bool(
            state
            and str(state.get("status") or "").strip().upper() == "CANCELLED")

    async def _stop_at_cancellation_boundary(
        self,
        execution_id: str,
        ws_manager: Any,
        user_id: str,
    ) -> bool:
        """Stop before more work when cancellation is observed.

        Called only at safe boundaries: before dispatching the next step, not
        while an effect is in flight. Already-dispatched work is left alone;
        neither this loop nor the durable writer pretends to undo it.
        """
        requested = execution_id in self.cancellation_requests
        durable = await self._durable_cancellation_observed(execution_id)
        if not requested and not durable:
            return False

        self.cancellation_requests.discard(execution_id)
        if durable:
            # The accepting surface already committed the authoritative row.
            # Do not rewrite it (or its reason) from this late worker.
            logger.info(
                "Workflow %s stopped at durable cancellation boundary",
                execution_id)
            return True

        logger.info("Workflow %s cancelled by user request", execution_id)
        await self.state_manager.update_execution_status(
            execution_id, "CANCELLED")
        await ws_manager.notify_workflow_status(
            user_id, execution_id, "CANCELLED", {"reason": "user_request"})
        return True

    def _notify_workflow_paused(self, workflow: Dict[str, Any], execution_id: str,
                                step_id: str, user_id: str, reason: str,
                                missing_var: Optional[str] = None,
                                hitl_action_id: Optional[str] = None) -> None:
        """Fan out a pause notification on every channel when a workflow pauses
        awaiting human input (HITL).

        Publishes the ``WORKFLOW_PAUSED`` EventBus event (event-driven triggers),
        fires the Slack/email workflow-notifier, and persists an in-app
        notification. All best-effort — a notification failure must never
        affect the (already paused) execution.
        """
        workflow_id = workflow.get("id", "unknown")
        self._publish_orchestration_event(
            "WORKFLOW_PAUSED", workflow_id, execution_id, step_id,
            data={"reason": reason, **({"missing_var": missing_var} if missing_var else {}),
                  **({"hitl_action_id": hitl_action_id} if hitl_action_id else {})},
        )

        workflow_name = workflow.get("name", "Untitled Workflow")
        try:
            asyncio.create_task(notifier.notify_paused(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                execution_id=execution_id,
                reason=reason,
                step_id=step_id,
                missing_var=missing_var,
                hitl_action_id=hitl_action_id,
            ))
        except Exception as e:
            logger.debug(f"Slack/email pause notification skipped (non-fatal): {e}")

        async def _in_app_notification() -> None:
            try:
                from core.notification_service import NotificationService
                await NotificationService().send_notification(
                    user_id,
                    "workflow_paused",
                    {
                        "title": f"Workflow paused: {workflow_name}",
                        "message": reason,
                        "workspace_id": workflow.get("workspace_id", "default"),
                        "tenant_id": workflow.get("tenant_id", "default"),
                        "action_url": f"/workflows/executions/{execution_id}",
                        "action_label": "Review paused workflow",
                    },
                )
            except Exception as e:
                logger.debug(f"In-app pause notification skipped (non-fatal): {e}")

        try:
            asyncio.create_task(_in_app_notification())
        except Exception as e:
            logger.debug(f"In-app pause notification dispatch skipped (non-fatal): {e}")

    async def _durable_step_approval(
        self,
        execution_id: str,
        step_id: str,
        action_type: str,
        input_data: Dict[str, Any],
        *,
        payload: Optional[Any] = None,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolve a DURABLE approval for exactly this workflow step.

        ``resume_workflow`` only passes the approval reference through the
        execution inputs; the authority itself is the persisted HITL row.
        This re-reads it (so a restarted worker sees the same decision) and
        refuses mismatched execution/step/action/scope references. A boolean
        in ``input_data`` alone can never authorize an effect.
        """
        hitl_id = str(
            input_data.get("hitl_action_id")
            or input_data.get("approval_hitl_id")
            or "").strip()
        if not input_data.get("approved") or not hitl_id:
            return None
        consumed = {
            str(item) for item in (
                input_data.get("consumed_hitl_action_ids") or [])
        }
        if hitl_id in consumed:
            return None
        try:
            from core.models import HITLAction

            with get_db_session() as db:
                action = db.query(HITLAction).filter(
                    HITLAction.id == hitl_id).first()
                if action is None:
                    return None
                if str(action.status or "").lower() not in (
                        "approved", "executed"):
                    return None
                params = action.params if isinstance(action.params, dict) else {}
                if str(params.get("execution_id") or "") != str(execution_id):
                    return None
                if str(params.get("step_id") or "") != str(step_id):
                    return None
                if str(action.action_type or "") != str(action_type or ""):
                    return None
                # The approval names the exact executable payload reviewed.
                # A changed parameter set is a different effect and must be
                # reviewed again instead of inheriting the old decision.
                if payload is not None and "parameters" in params:
                    def _canonical(value: Any) -> str:
                        if isinstance(value, str):
                            try:
                                value = json.loads(value)
                            except (TypeError, ValueError):
                                pass
                        return json.dumps(
                            value, sort_keys=True, separators=(",", ":"),
                            default=str)

                    if _canonical(params.get("parameters")) != _canonical(payload):
                        logger.warning(
                            "workflow %s: durable approval %s does not bind "
                            "the current step payload", execution_id, hitl_id)
                        return None
                if (tenant_id
                        and action.tenant_id
                        and str(action.tenant_id) != str(tenant_id)):
                    return None
                if (workspace_id
                        and getattr(action, "workspace_id", None)
                        and str(action.workspace_id) != str(workspace_id)):
                    return None
                return {
                    "hitl_action_id": hitl_id,
                    "approved_by": (
                        action.reviewed_by
                        or getattr(action, "resolver_id", None)),
                    "resolved_at": (
                        action.reviewed_at.isoformat()
                        if getattr(action, "reviewed_at", None) else None),
                }
        except Exception as exc:  # noqa: BLE001 — fail closed
            logger.warning(
                "workflow %s: durable approval lookup failed: %s",
                execution_id, exc)
            return None

    def _execution_scope(
        self,
        workflow: Dict[str, Any],
        state: Optional[Dict[str, Any]] = None,
    ) -> tuple:
        """Resolve the durable execution scope, then the definition's own.

        The public start path freezes the authenticated caller's scope into
        the persisted execution inputs; a resumed worker therefore resolves
        the same tenant/workspace as the original request. Seeded/scheduled
        definitions that carry their own scope remain supported, and a run
        with no scope at all keeps the legacy ``"default"`` behavior.
        """
        frozen: Dict[str, Any] = {}
        if isinstance(state, dict):
            frozen = frozen_execution_identity(state.get("input_data"))
        workspace_id = frozen.get("workspace_id") or ""
        tenant_id = frozen.get("tenant_id") or ""
        if not workspace_id:
            workspace_id = str(workflow.get("workspace_id") or "").strip()
        if not tenant_id:
            tenant_id = str(workflow.get("tenant_id") or "").strip()
        return workspace_id or "default", tenant_id or "default"

    def _ai_execution_scope(
        self,
        state: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, str]]:
        """Return the caller-frozen AI scope, with no definition/default fallback.

        The legacy ``ai`` service may call a provider, so it is authorized ONLY
        by the scope persisted in the execution's ``input_data`` at start. A
        workflow definition's own workspace/tenant or the literal ``"default"``
        is not proof of the caller's identity and must never reach the provider.
        """
        inputs = state.get("input_data") if isinstance(state, dict) else None
        frozen = frozen_execution_identity(inputs)
        workspace_id = str(frozen.get("workspace_id") or "").strip()
        tenant_id = str(frozen.get("tenant_id") or "").strip()
        if not workspace_id or not tenant_id:
            return None
        return {"workspace_id": workspace_id, "tenant_id": tenant_id}

    async def start_workflow(
        self,
        workflow: Dict[str, Any],
        input_data: Dict[str, Any],
        background_tasks: Any = None,
        *,
        scope: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a new workflow execution.

        ``scope`` is the authenticated caller's authoritative
        ``{"workspace_id", "tenant_id", "user_id"}``. It is normalized and
        passed explicitly to the durable writer, which freezes it into the
        persisted execution inputs so governance-created approvals, the
        durable owner/user/tenant stamp and every later resume resolve the
        same scope. Any marker already in ``input_data`` is stripped by the
        writer and never treated as identity.
        """
        # Convert graph to steps if needed
        if "steps" not in workflow and "nodes" in workflow:
            workflow["steps"] = self._convert_nodes_to_steps(workflow)

        # Some definitions carry only the alternate "workflow_id" key — normalize
        # it to "id" so every downstream consumer (create_execution, events,
        # _run_execution) works without a KeyError.
        if "id" not in workflow and workflow.get("workflow_id"):
            workflow["id"] = workflow["workflow_id"]

        scope_values = scope if isinstance(scope, dict) else {}
        trusted_scope = normalize_execution_identity({
            "workspace_id": scope_values.get("workspace_id"),
            "tenant_id": scope_values.get("tenant_id"),
            "user_id": scope_values.get("user_id"),
        })
        input_data = strip_execution_scope(input_data)

        # Only pass the identity keyword when a trusted scope was proven. An
        # unscoped run (no authenticated caller scope) keeps the historical
        # two-argument call, so positional-only/fake writers still work.
        if trusted_scope:
            execution_id = await self.state_manager.create_execution(
                workflow["id"], input_data, identity=trusted_scope,
            )
        else:
            execution_id = await self.state_manager.create_execution(
                workflow["id"], input_data,
            )

        # Phase 5: publish a WORKFLOW_STARTED event for the EventBus.
        self._publish_orchestration_event(
            "WORKFLOW_STARTED", workflow["id"], execution_id,
            data={"step_count": len(workflow.get("steps", []))},
        )

        # Run execution in background
        if background_tasks:
            background_tasks.add_task(self._run_execution, execution_id, workflow)
        else:
            task = asyncio.create_task(self._run_execution(execution_id, workflow))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        return execution_id

    def _convert_nodes_to_steps(self, workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert graph-based nodes/connections to linear steps"""
        nodes = {n["id"]: n for n in workflow.get("nodes", [])}
        connections = workflow.get("connections", [])
        
        # Build adjacency list and in-degree
        adj = {n: [] for n in nodes}
        in_degree = {n: 0 for n in nodes}
        
        for conn in connections:
            source = conn.get("source")
            target = conn.get("target")
            if source is None or target is None:
                # Malformed connection (missing source/target) must not crash
                # the whole conversion — skip it and continue.
                logger.warning("Ignoring malformed connection: %s", conn)
                continue
            if source in adj and target in in_degree:
                adj[source].append(target)
                in_degree[target] += 1
                
        # Topological sort (Kahn's algorithm)
        queue = [n for n in nodes if in_degree[n] == 0]
        sorted_ids = []

        while queue:
            u = queue.pop(0)
            sorted_ids.append(u)

            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        # BUG FIX: Check for cycles - if not all nodes were processed, there's a cycle
        if len(sorted_ids) != len(nodes):
            # Find nodes that weren't processed (part of cycles)
            cycle_nodes = [n for n in nodes if n not in sorted_ids]
            logger.error(f"Workflow contains cycle. Nodes in cycle: {cycle_nodes}")
            raise ValueError(
                f"Workflow contains circular dependencies. "
                f"Nodes involved in cycle: {cycle_nodes}. "
                f"Please fix the workflow to remove circular references."
            )

        # Convert to steps
        steps = []
        for i, node_id in enumerate(sorted_ids):
            node = nodes[node_id]
            config = node.get("config", {})
            
            step = {
                "id": node_id,
                "name": node.get("title", node_id),
                "sequence_order": i + 1,
                "service": config.get("service", "default"),
                "action": config.get("action", "default"),
                "parameters": config.get("parameters", {}),
                "continue_on_error": config.get("continue_on_error", False),
                "timeout": config.get("timeout", None),
                "input_schema": config.get("input_schema", {}),
                "output_schema": config.get("output_schema", {})
            }
            
            # Map specific node types/configs to step fields if needed
            if node.get("type") == "trigger":
                step["type"] = "trigger"
                step["action"] = config.get("action", "manual_trigger")
            else:
                step["type"] = "action"
                
            steps.append(step)
            
        return steps

    def _build_execution_graph(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build execution graph from workflow nodes and connections.
        Returns dict with:
        - nodes: dict node_id -> node
        - connections: list of connections with source, target, condition
        - adjacency: dict node_id -> list of outgoing connections
        - reverse_adjacency: dict node_id -> list of incoming connections
        """
        nodes = {n["id"]: n for n in workflow.get("nodes", [])}
        connections = workflow.get("connections", [])

        adjacency = {n: [] for n in nodes}
        reverse_adjacency = {n: [] for n in nodes}

        for conn in connections:
            source = conn.get("source")
            target = conn.get("target")
            if source in nodes and target in nodes:
                adjacency[source].append(conn)
                reverse_adjacency[target].append(conn)

        return {
            "nodes": nodes,
            "connections": connections,
            "adjacency": adjacency,
            "reverse_adjacency": reverse_adjacency
        }

    def _has_conditional_connections(self, workflow: Dict[str, Any]) -> bool:
        """Check if any connection has a condition."""
        connections = workflow.get("connections", [])
        for conn in connections:
            if conn.get("condition"):
                return True
        return False

    async def _execute_workflow_graph(self, execution_id: str, workflow: Dict[str, Any], state: Dict[str, Any], ws_manager, user_id: str, start_time: datetime) -> None:
        """
        Execute workflow using graph traversal with conditional branching and parallel execution.
        """
        # Import analytics engine
        from core.analytics_engine import get_analytics_engine
        analytics = get_analytics_engine()

        graph = self._build_execution_graph(workflow)
        workspace_id, tenant_id = self._execution_scope(workflow, state)
        # Provider-backed ``ai`` steps are authorized only by the scope frozen
        # into the persisted execution inputs. Attach it to every step (not
        # just service == "ai") so a fallback to ``ai`` cannot bypass it, and
        # overwrite any marker a workflow definition may have supplied.
        ai_scope = self._ai_execution_scope(state)
        execution_identity = frozen_execution_identity(
            state.get("input_data") if isinstance(state, dict) else None)
        nodes = graph["nodes"]
        adjacency = graph["adjacency"]
        reverse_adjacency = graph["reverse_adjacency"]

        # Track step status
        step_status = {step_id: state["steps"].get(step_id, {}).get("status", "PENDING")
                      for step_id in nodes}
        # Track activated connections (condition evaluated true)
        # Use tuple (source, target) as hashable identifier instead of dict
        activated_connections = set()
        # Lock for state updates to prevent race conditions
        state_lock = asyncio.Lock()

        # Helper to evaluate connection condition
        def evaluate_connection_condition(conn, current_state):
            condition = conn.get("condition")
            if condition is None or condition == "":
                return True  # No condition means always activate
            return self._evaluate_condition(condition, current_state)

        # Initialize: evaluate already completed steps (for resume scenarios)
        for step_id, status in step_status.items():
            if status == "COMPLETED":
                # Evaluate outgoing connections for completed steps
                async with state_lock:
                    current_state = await self.state_manager.get_execution_state(execution_id)
                for conn in adjacency[step_id]:
                    if evaluate_connection_condition(conn, current_state):
                        # Use tuple (source, target) as hashable identifier
                        activated_connections.add((conn.get("source"), conn.get("target")))

        # Helper to get ready steps
        def get_ready_steps():
            ready = set()
            for step_id in nodes:
                if step_status.get(step_id) in ["COMPLETED", "RUNNING", "FAILED", "PAUSED"]:
                    continue
                incoming_conns = reverse_adjacency[step_id]
                # If no incoming connections, or all incoming connections are activated
                if not incoming_conns or all(
                    (conn.get("source"), conn.get("target")) in activated_connections
                    for conn in incoming_conns
                ):
                    ready.add(step_id)
            return ready

        # Main execution loop
        try:
            while True:
                # Durable CANCELLED is authoritative across engine instances.
                # Check before selecting/dispatching any further ready steps;
                # work already in flight is allowed to settle.
                if await self._stop_at_cancellation_boundary(
                        execution_id, ws_manager, user_id):
                    return

                ready_steps = get_ready_steps()
                if not ready_steps:
                    # No more steps ready to execute
                    break

                # Execute ready steps in parallel
                async def execute_single_step(step_id):
                    node = nodes[step_id]
                    config = node.get("config", {})
                    step = {
                        "id": step_id,
                        "name": node.get("title", step_id),
                        "service": config.get("service", "default"),
                        "action": config.get("action", "default"),
                        "parameters": config.get("parameters", {}),
                        "type": node.get("type", "action"),
                        "continue_on_error": config.get("continue_on_error", False),
                        "timeout": config.get("timeout", None),
                        "input_schema": config.get("input_schema", {}),
                        "output_schema": config.get("output_schema", {}),
                        "workflow_id": workflow.get("id", "unknown"),
                        "connection_id": config.get("connectionId"),
                    }
                    _attach_step_identity_context(
                        step,
                        execution_id=execution_id,
                        step_id=step_id,
                        identity=execution_identity,
                        ai_scope=ai_scope,
                        workspace_id=workspace_id,
                        tenant_id=tenant_id,
                    )

                    async with self.semaphore:
                        # Update step status to RUNNING
                        async with state_lock:
                            await self.state_manager.update_step_status(execution_id, step_id, "RUNNING")
                            await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_RUNNING", {"step_id": step_id})
                            current_state = await self.state_manager.get_execution_state(execution_id)

                        # Resolve parameters (may raise MissingInputError)
                        try:
                            resolved_params = self._resolve_parameters(step.get("parameters", {}), current_state)
                        except MissingInputError as e:
                            async with state_lock:
                                logger.info(f"Pausing execution {execution_id} at step {step_id}: {e}")
                                await self.state_manager.update_step_status(execution_id, step_id, "PAUSED", error=str(e))
                                await self.state_manager.update_execution_status(execution_id, "PAUSED", error=f"Missing input: {e.missing_var}")
                                await ws_manager.notify_workflow_status(
                                    user_id, execution_id, "PAUSED",
                                    {"reason": "missing_input", "missing_var": e.missing_var, "step_id": step_id}
                                )
                                self._notify_workflow_paused(
                                    workflow, execution_id, step_id, user_id,
                                    reason=f"Missing input: {e.missing_var}",
                                    missing_var=e.missing_var,
                                )
                            raise  # Re-raise to stop parallel execution

                        # Validate input schema
                        self._validate_input_schema(step, resolved_params)

                        # Execute step
                        try:
                            start_step_time = datetime.now(timezone.utc)
                            output = await self._execute_step(step, resolved_params)
                            duration_ms = int((datetime.now(timezone.utc) - start_step_time).total_seconds() * 1000)
                            self._validate_output_schema(step, output)
                            
                            # Extract resource_id from output
                            resource_id = None
                            if isinstance(output, dict):
                                result_data = output.get("result", {})
                                if isinstance(result_data, dict):
                                    resource_id = str(result_data.get("id") or 
                                                     result_data.get("resource_id") or 
                                                     result_data.get("task_id") or 
                                                     result_data.get("email_id") or 
                                                     result_data.get("execution_id") or "")

                            async with state_lock:
                                await self.state_manager.update_step_status(execution_id, step_id, "COMPLETED", output=output)
                                await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_COMPLETED", {"step_id": step_id})
                                step_status[step_id] = "COMPLETED"
                                current_state = await self.state_manager.get_execution_state(execution_id)

                            # Evaluate outgoing connections
                            new_activated = []
                            for conn in adjacency[step_id]:
                                if evaluate_connection_condition(conn, current_state):
                                    # Use tuple (source, target) as hashable identifier
                                    new_activated.append((conn.get("source"), conn.get("target")))

                            # Update activated connections
                            async with state_lock:
                                activated_connections.update(new_activated)

                            return (step_id, True, output, None)

                        except Exception as e:
                            logger.error(f"Step {step_id} failed: {e}")

                            async with state_lock:
                                await self.state_manager.update_step_status(execution_id, step_id, "FAILED", error=str(e))
                            step_status[step_id] = "FAILED"
                            return (step_id, False, None, e)

                # Execute all ready steps concurrently
                tasks = [execute_single_step(step_id) for step_id in ready_steps]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                has_failure = False
                failure_error = None
                for result in results:
                    if isinstance(result, Exception):
                        # This should not happen as exceptions are caught in execute_single_step
                        logger.error(f"Unexpected exception in step execution: {result}")
                        has_failure = True
                        failure_error = result
                        continue

                    step_id, success, output, error = result
                    if not success:
                        # Check if step has continue_on_error flag
                        node = nodes[step_id]
                        config = node.get("config", {})
                        continue_on_error = config.get("continue_on_error", False)
                        if continue_on_error:
                            logger.warning(f"Step {step_id} failed but continue_on_error is True, marking as failed but continuing workflow")
                            # Bug #4: activate downstream connections so the
                            # workflow doesn't stall. Previously failed steps
                            # never activated their outgoing connections, so
                            # descendants were permanently blocked.
                            async with state_lock:
                                current_state = await self.state_manager.get_execution_state(execution_id)
                                new_activated = []
                                for conn in adjacency.get(step_id, []):
                                    if evaluate_connection_condition(conn, current_state):
                                        new_activated.append((conn.get("source"), conn.get("target")))
                                activated_connections.update(new_activated)
                        else:
                            has_failure = True
                            failure_error = error
                            # If a step failed, we may want to stop the whole workflow
                            # For now, we continue processing other steps but mark failure
                            # The step status is already updated to FAILED

                # If any step failed with MissingInputError, we've paused the workflow
                # Check if workflow is paused
                async with state_lock:
                    current_state = await self.state_manager.get_execution_state(execution_id)
                    if current_state["status"] == "PAUSED":
                        logger.info(f"Workflow {execution_id} paused due to missing input")
                        return

                # If any step failed (non-MissingInputError), fail the whole execution
                if has_failure and failure_error:
                    logger.error(f"Workflow execution {execution_id} failed due to step failure: {failure_error}")
                    async with state_lock:
                        await self.state_manager.update_execution_status(execution_id, "FAILED", error=str(failure_error))
                        await ws_manager.notify_workflow_status(user_id, execution_id, "FAILED", {"error": str(failure_error)})
                    
                    # Send failure notification
                    asyncio.create_task(notifier.notify_failure(
                        workflow_id=workflow.get("id", "unknown"),
                        workflow_name=workflow.get("name", "Untitled Workflow"),
                        execution_id=execution_id,
                        error=str(failure_error)
                    ))
                    return

                # Continue to next iteration (new steps may have become ready)

            # All steps processed. Re-check at this final safe boundary so a
            # cancellation committed while the last step was settling cannot
            # be replaced by a late COMPLETED/PARTIAL write or notification.
            if await self._stop_at_cancellation_boundary(
                    execution_id, ws_manager, user_id):
                return

            completed = all(status == "COMPLETED" for status in step_status.values())
            if completed:
                async with state_lock:
                    status_updated = await self.state_manager.update_execution_status(
                        execution_id, "COMPLETED")
                    if status_updated is False:
                        # A cancellation committed between the final boundary
                        # read and this UPDATE. The row stays CANCELLED; do not
                        # publish a misleading COMPLETED status or success.
                        logger.info(
                            "Workflow %s COMPLETED write rejected by durable "
                            "cancellation", execution_id)
                        return
                    await ws_manager.notify_workflow_status(user_id, execution_id, "COMPLETED")

                # Send completion notification
                asyncio.create_task(notifier.notify_completion(
                    workflow_id=workflow.get("id", "unknown"),
                    workflow_name=workflow.get("name", "Untitled Workflow"),
                    execution_id=execution_id,
                    results=state.get("outputs", {})
                ))

                # Students observe successful workflow outcomes (automated
                # observation trigger — fire-and-forget, best-effort).
                from core.student_learning_service import auto_observe
                asyncio.create_task(auto_observe(
                    workspace_id=workspace_id,
                    observation_type="workflow_execution",
                    summary=f"Workflow '{workflow.get('name', workflow.get('id', 'unknown'))}' completed successfully",
                    details={"workflow_id": workflow.get("id"), "execution_id": execution_id},
                ))

                # Track success
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                analytics.track_workflow_execution(
                    workflow_id=workflow.get("id", "unknown"),
                    success=True,
                    duration_seconds=duration,
                    time_saved_seconds=workflow.get("estimated_time_saved", 60),
                    business_value=workflow.get("business_value", 10)
                )
            else:
                # Some steps stuck (maybe due to unmet conditions)
                logger.warning(f"Workflow execution {execution_id} ended with pending steps")
                async with state_lock:
                    status_updated = await self.state_manager.update_execution_status(
                        execution_id, "PARTIAL")
                    if status_updated is False:
                        # Cancellation won the race with this terminal write.
                        # Keep the durable CANCELLED row and stay silent.
                        logger.info(
                            "Workflow %s PARTIAL write rejected by durable "
                            "cancellation", execution_id)
                        return
                    await ws_manager.notify_workflow_status(user_id, execution_id, "PARTIAL")

                # Track partial completion
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                analytics.track_workflow_execution(
                    workflow_id=workflow.get("id", "unknown"),
                    success=False,
                    duration_seconds=duration,
                    time_saved_seconds=0,
                    business_value=0
                )

        except Exception as e:
            logger.error(f"Workflow graph execution {execution_id} failed: {e}")
            async with state_lock:
                await self.state_manager.update_execution_status(execution_id, "FAILED", error=str(e))
                await ws_manager.notify_workflow_status(user_id, execution_id, "FAILED", {"error": str(e)})

            # Track failure
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            analytics.track_workflow_execution(
                workflow_id=workflow.get("id", "unknown"),
                success=False,
                duration_seconds=duration,
                time_saved_seconds=0,
                business_value=0
            )

    async def resume_workflow(self, execution_id: str, workflow: Dict[str, Any], new_inputs: Dict[str, Any]) -> bool:
        """Resume a paused workflow with new inputs"""
        state = await self.state_manager.get_execution_state(execution_id)
        if not state:
            raise ValueError(f"Execution {execution_id} not found")

        if state["status"] != "PAUSED":
            logger.warning(f"Cannot resume execution {execution_id} in state {state['status']}")
            return False

        # Resume inputs are untrusted: they may carry the approval reference,
        # never a replacement execution scope. The scope frozen at start (and
        # persisted in the execution row) stays authoritative.
        new_inputs = strip_execution_scope(new_inputs)

        # Update state with new inputs
        await self.state_manager.update_execution_inputs(execution_id, new_inputs)
        status_updated = await self.state_manager.update_execution_status(
            execution_id, "RUNNING")
        if status_updated is False:
            # Cancellation won the resume race. The durable row stays
            # CANCELLED, so do not announce a resume or dispatch the run.
            logger.info(
                "Workflow %s resume rejected by durable cancellation",
                execution_id)
            return False

        # Phase 5: publish WORKFLOW_RESUMED for EventBus observability
        # (e.g. clearing HITL alert state, downstream triggers).
        self._publish_orchestration_event(
            "WORKFLOW_RESUMED", workflow.get("id", "unknown"), execution_id,
            data={"resumed_with_inputs": sorted(new_inputs.keys())},
        )

        # Resume execution — strong ref to prevent GC cancellation
        task = asyncio.create_task(self._run_execution(execution_id, workflow))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return True

    async def launch_reserved_event_execution(
        self,
        execution_id: str,
        state: Dict[str, Any],
        dispatch_preflight: Callable[
            [str, Dict[str, Any], Dict[str, Any]], Awaitable[bool]
        ],
    ) -> bool:
        """Launch an already-reserved event execution exactly once.

        The execution row and its workflow snapshot are created by the event
        reservation path. This entry never creates another row, never accepts a
        caller-chosen workflow, and performs no engine effect (claim, event
        publish, or run dispatch) until the exact PENDING receipt has been
        validated and the trusted preflight has approved the dispatch.

        ``state`` is the already-loaded execution state. The receipt must live
        under ``context._atom_event_admission`` and name this exact ``evt_``
        execution id and the state's workflow id; its ``workflow_snapshot`` is
        the only workflow this entry will launch.
        """
        if not isinstance(state, dict):
            return False

        token = str(execution_id or "").strip()
        if not token.startswith("evt_"):
            logger.warning(
                "reserved event execution %s: not a reserved event id", token)
            return False

        if str(state.get("execution_id") or "").strip() != token:
            logger.warning(
                "reserved event execution %s: state execution id mismatch",
                token)
            return False

        if str(state.get("status") or "").strip() != "PENDING":
            logger.warning(
                "reserved event execution %s: execution is not pending", token)
            return False

        context = state.get("context")
        if isinstance(context, str):
            try:
                context = json.loads(context)
            except (TypeError, ValueError):
                context = None
        admission = (
            context.get("_atom_event_admission")
            if isinstance(context, dict) else None)
        if not isinstance(admission, dict):
            logger.warning(
                "reserved event execution %s: missing event admission", token)
            return False

        if str(admission.get("execution_id") or "").strip() != token:
            logger.warning(
                "reserved event execution %s: admission execution id mismatch",
                token)
            return False

        workflow_id = str(state.get("workflow_id") or "").strip()
        admission_workflow_id = str(
            admission.get("workflow_id") or "").strip()
        if (not workflow_id or not admission_workflow_id
                or workflow_id != admission_workflow_id):
            logger.warning(
                "reserved event execution %s: workflow id mismatch", token)
            return False

        snapshot = admission.get("workflow_snapshot")
        if not isinstance(snapshot, dict):
            logger.warning(
                "reserved event execution %s: missing workflow snapshot", token)
            return False

        # Copy before graph conversion so adding steps never mutates the frozen
        # reservation material.
        workflow = copy.deepcopy(snapshot)
        snapshot_workflow_id = str(
            workflow.get("id") or workflow.get("workflow_id") or "").strip()
        if snapshot_workflow_id and snapshot_workflow_id != workflow_id:
            logger.warning(
                "reserved event execution %s: workflow snapshot mismatch",
                token)
            return False
        workflow["id"] = workflow_id

        if "steps" not in workflow and "nodes" in workflow:
            try:
                workflow["steps"] = self._convert_nodes_to_steps(workflow)
            except Exception as exc:  # noqa: BLE001 — reject before any effect
                logger.warning(
                    "reserved event execution %s: invalid workflow graph: %s",
                    token, exc)
                return False

        # Preflight runs before the claim. A refused or failed preflight must
        # leave the reservation untouched.
        try:
            approved = await dispatch_preflight(token, state, workflow)
        except Exception as exc:  # noqa: BLE001 — fail closed before claim
            logger.warning(
                "reserved event execution %s: dispatch preflight failed: %s",
                token, exc)
            return False
        if not approved:
            logger.info(
                "reserved event execution %s: dispatch preflight rejected",
                token)
            return False

        try:
            claimed = await self.state_manager.claim_event_execution(token)
        except Exception as exc:  # noqa: BLE001 — claim failure is not a launch
            logger.warning(
                "reserved event execution %s: claim failed: %s", token, exc)
            return False
        if not claimed:
            # Another caller already owns the single dispatch; emit nothing.
            return False

        # Only the claim winner reaches this point. Reuse the existing runner
        # so task-profile binding and never-autonomous admission still run.
        self._publish_orchestration_event(
            "WORKFLOW_STARTED", workflow_id, token,
            data={"step_count": len(workflow.get("steps", []))},
        )
        task = asyncio.create_task(self._run_execution(token, workflow))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return True

    async def cancel_execution(self, execution_id: str) -> bool:
        """Request cancellation of a running workflow execution."""
        self.cancellation_requests.add(execution_id)
        logger.info(f"Cancellation requested for execution {execution_id}")

        # Notify via WebSocket
        ws_manager = get_connection_manager()
        await self.state_manager.update_execution_status(execution_id, "CANCELLED")
        await ws_manager.notify_workflow_status("default", execution_id, "CANCELLED")
        return True

    async def _admit_never_autonomous_task(
        self,
        execution_id: str,
        workflow: Dict[str, Any],
        state: Dict[str, Any],
        user_id: str,
        workspace_id: str,
        tenant_id: str,
    ) -> Optional[str]:
        """TASK-LEVEL admission before the workflow's first step/model call.

        Returns ``"paused"`` when the run must stop for human review. A
        previously approved durable task admission for THIS execution is
        re-read and reused on resume; a boolean in the resume payload is never
        authority. The granted clearance covers only this task and only the
        reviewed rule revisions.
        """
        from core.autonomy_policy import (
            NEVER_TASK_ADMISSION_ACTION,
            evaluate_task_admission,
            grant_never_autonomous_clearance,
            task_admission_params,
            warm_task_admission_receipt_denial,
        )
        from core.task_classification import (
            build_unknown_task_profile,
            current_task_profile,
        )

        profile = current_task_profile()
        task_material = " ".join(
            str(value) for value in (
                workflow.get("name"), workflow.get("description"),
                workflow.get("goal"), workflow.get("objective"),
            ) if value
        )
        agent_id = str(workflow.get("agent_id") or "system_agent")
        # The admitted workflow actor is the policy owner. Never let a stale
        # ancestor profile choose a different owner than the run's creator.
        owner_user_id = (
            workflow.get("created_by")
            or workflow.get("user_id")
            or user_id
            or (profile.owner_user_id if profile is not None else None))
        if profile is None:
            # Missing classification cannot prove a configured rule
            # inapplicable; review against the canonical unknown profile
            # before the workflow's first step/model call.
            try:
                profile = build_unknown_task_profile(
                    user_id=owner_user_id, reason="profile_unavailable")
                logger.warning(
                    "workflow %s: task profile unavailable at admission; "
                    "evaluating configured rules against an unknown profile",
                    execution_id)
            except Exception:  # noqa: BLE001 — policy below fails closed
                profile = None
        try:
            with get_db_session() as db:
                governance = ServiceFactory.get_governance_service(
                    db, workspace_id=workspace_id, tenant_id=tenant_id)
                decision = evaluate_task_admission(
                    db,
                    profile,
                    task_material=task_material,
                    agent_id=agent_id,
                    user_id=owner_user_id,
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                )
                if decision.get("outcome") != "review":
                    return None
                durable = decision.get("durable_admission") or {}
                if durable.get("hitl_action_id"):
                    if warm_task_admission_receipt_denial(
                            decision, decision,
                            hitl_action_id=durable.get("hitl_action_id")):
                        return "paused"
                    holder: Dict[str, Any] = {}
                    if not grant_never_autonomous_clearance(
                            holder, decision, task_profile=profile,
                            execution_id=execution_id,
                            tenant_id=tenant_id,
                            workspace_id=workspace_id):
                        return "paused"
                    logger.info(
                        "workflow %s: reused durable task admission %s",
                        execution_id, durable.get("hitl_action_id"))
                    return None

                # Reuse an existing PENDING admission instead of filing a new
                # decision every resume attempt for the same execution/task.
                from core.models import HITLAction

                pending = (
                    db.query(HITLAction)
                    .filter(
                        HITLAction.action_type == NEVER_TASK_ADMISSION_ACTION,
                        HITLAction.status == "pending",
                        HITLAction.agent_id == agent_id,
                    )
                    .order_by(HITLAction.created_at.desc())
                    .limit(20)
                    .all()
                )
                analytics_task = None
                for row in pending:
                    params = row.params if isinstance(row.params, dict) else {}
                    snapshot = (
                        row.context_snapshot
                        if isinstance(row.context_snapshot, dict) else {})
                    if (str(params.get("execution_id")
                            or snapshot.get("execution_id") or "")
                            == str(execution_id)
                            and str(params.get("task_fingerprint") or "")
                            == str(decision.get("task_fingerprint") or "")):
                        analytics_task = row
                        break
                if analytics_task is None:
                    decision_params = task_admission_params(
                        decision,
                        execution_id=execution_id,
                        profile=profile,
                        extra={"workflow_id": workflow.get("id")},
                    )
                    decision_params["task_input"] = str(task_material)[:2000]
                    action_id = governance.request_approval(
                        agent_id=agent_id,
                        action_type=NEVER_TASK_ADMISSION_ACTION,
                        params=decision_params,
                        reason=decision.get("reason") or (
                            "A never-autonomous task rule matched this "
                            "workflow; a human must approve this execution."),
                        execution_context={
                            "execution_id": execution_id,
                            "workspace_id": workspace_id,
                            "tenant_id": tenant_id,
                            "user_id": owner_user_id,
                        },
                        user_id=owner_user_id,
                    )
                else:
                    action_id = analytics_task.id
            reason = decision.get("reason") or (
                "A never-autonomous task rule matched this workflow.")
            await self.state_manager.update_execution_status(
                execution_id, "PAUSED", error=reason)
            await get_connection_manager().notify_workflow_status(
                user_id, execution_id, "PAUSED",
                {"reason": "never_autonomous", "hitl_action_id": action_id,
                 "task_level": True})
            self._notify_workflow_paused(
                workflow, execution_id, "never_autonomous", user_id,
                reason=reason,
            )
            return "paused"
        except Exception as exc:  # noqa: BLE001 — configured policy fails CLOSED
            logger.warning(
                "workflow %s: never-autonomous task admission unavailable: %s",
                execution_id, exc)
            reason = (
                "Never-autonomous task policy could not be evaluated; "
                "human review is required.")
            await self.state_manager.update_execution_status(
                execution_id, "PAUSED", error=reason)
            return "paused"

    async def _run_execution(self, execution_id: str, workflow: Dict[str, Any]) -> None:
        """Bind the workflow's canonical task profile for the whole run.

        The profile is an in-process object bound through the same context
        variable the topic gates and governance use; it is not written into
        the persisted workflow definition. The body keeps the existing
        execution loop unchanged.
        """
        token = None
        boundary = None
        try:
            from core.task_classification import (
                begin_task_profile_boundary,
                bind_task_profile,
                build_unknown_task_profile,
                build_workflow_task_profile,
                end_task_profile_boundary,
                reset_task_profile,
            )

            # Own this run's task boundary before building anything: a
            # nested workflow must never be admitted against an ancestor's
            # profile if both this build and the unknown fallback fail.
            boundary = begin_task_profile_boundary(None)
            try:
                profile = build_workflow_task_profile(workflow)
            except Exception as _classify_err:  # noqa: BLE001
                # Bind the canonical unknown profile rather than letting the
                # run skip task admission entirely. Configured rules become
                # potential matches (durable review before the first step).
                logger.warning(
                    "workflow %s: task classification unavailable (%s); "
                    "evaluating configured rules against an unknown profile",
                    execution_id, type(_classify_err).__name__)
                profile = build_unknown_task_profile(
                    user_id=(
                        workflow.get("created_by")
                        or workflow.get("user_id")),
                    reason=type(_classify_err).__name__,
                )
            token = bind_task_profile(None, profile)
        except Exception as _profile_err:  # noqa: BLE001
            logger.debug(
                "workflow %s: task profile bind skipped: %s",
                execution_id, _profile_err)
        try:
            await self._run_execution_body(execution_id, workflow)
        finally:
            try:
                if token is not None:
                    from core.task_classification import reset_task_profile

                    reset_task_profile(token)
            except Exception:  # noqa: BLE001
                pass
            try:
                from core.task_classification import end_task_profile_boundary

                # Restore the caller's profile/clearance on success, error
                # and cancellation alike.
                end_task_profile_boundary(boundary)
            except Exception:  # noqa: BLE001
                pass

    async def _run_execution_body(self, execution_id: str, workflow: Dict[str, Any]) -> None:
        """Main execution loop"""
        ws_manager = get_connection_manager()
        # Import here to avoid circular imports if any
        from core.analytics_engine import get_analytics_engine
        analytics = get_analytics_engine()
        
        user_id = workflow.get("created_by", "default")
        start_time = datetime.now(timezone.utc)
        
        try:
            status_updated = await self.state_manager.update_execution_status(
                execution_id, "RUNNING")
            if status_updated is False:
                # Cancellation was committed before this worker could claim
                # the run. Do not announce RUNNING or resume any work.
                logger.info(
                    "Workflow %s RUNNING write rejected by durable "
                    "cancellation", execution_id)
                return
            await ws_manager.notify_workflow_status(user_id, execution_id, "RUNNING")
            
            state = await self.state_manager.get_execution_state(execution_id)
            # Prefer the scope frozen at start (durable across restarts);
            # fall back to the definition's own scope for seeded/scheduled runs.
            workspace_id, tenant_id = self._execution_scope(workflow, state)
            # The legacy ``ai`` service is NOT authorized by that fallback.
            # It sees only the exact pair frozen into the persisted execution
            # inputs, attached to every step so fallback ai is covered too.
            ai_scope = self._ai_execution_scope(state)
            # Complete trusted identity for executors that perform durable
            # writes on the run's behalf (e.g. goal creation). Only the
            # server-frozen execution inputs are authoritative.
            execution_identity = frozen_execution_identity(
                state.get("input_data") if isinstance(state, dict) else None)

            # A cancellation may have been accepted between creation and this
            # worker starting, or while resuming. Stop before admission or the
            # first dispatch; the guarded status write above kept it CANCELLED.
            if await self._stop_at_cancellation_boundary(
                    execution_id, ws_manager, user_id):
                return

            # TASK-LEVEL never-autonomous admission BEFORE the first step,
            # model call or output. Reuses a durable approved task HITL on
            # resume; independent per-step guards still run afterwards.
            if await self._admit_never_autonomous_task(
                    execution_id, workflow, state, user_id,
                    workspace_id, tenant_id) == "paused":
                return

            # Decide execution mode based on conditional connections
            if self._has_conditional_connections(workflow):
                # Use graph execution with branching
                await self._execute_workflow_graph(execution_id, workflow, state, ws_manager, user_id, start_time)
                # The graph execution will update execution status internally
                # If it returns, we assume completion or failure handled
                return

            # Work on a run-local shallow copy of each step so attaching
            # runtime scope cannot mutate the shared workflow definition or
            # race with simultaneous runs of the same definition.
            steps = [dict(step) for step in workflow.get("steps", [])]
            # Sort the run-local copies by sequence_order
            steps.sort(key=lambda x: x.get("sequence_order", 0))

            # Tracks steps that failed but were allowed to continue via the
            # continue_on_error flag — the workflow ends PARTIAL so the failure
            # stays visible (mirrors the graph-execution path).
            had_step_failures = False

            for step in steps:
                step_id = step["id"]

                # Durable CANCELLED is authoritative across engine instances.
                # This is the linear dispatch boundary: stop before the next
                # step is marked RUNNING/logged/executed. A step already in
                # flight is allowed to settle and is never rolled back here.
                if await self._stop_at_cancellation_boundary(
                        execution_id, ws_manager, user_id):
                    return

                # Check if step already completed (for resume scenarios)
                step_state = state["steps"].get(step_id, {})
                if step_state.get("status") == "COMPLETED":
                    continue
                
                # Install the same authoritative context used by the graph
                # dispatcher. This overwrites definition/input claims and
                # always carries the real execution id (not one taken from the
                # workflow definition or step parameters).
                _attach_step_identity_context(
                    step,
                    execution_id=execution_id,
                    step_id=step_id,
                    identity=execution_identity,
                    ai_scope=ai_scope,
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                )
                
                # Check dependencies
                if not self._check_dependencies(step, state):
                    # This shouldn't happen in a linear sequence, but important for DAGs
                    # Previously, `continue` permanently dropped the step and the
                    # workflow reported COMPLETED. Now log as a warning so the
                    # partial completion is visible, and mark the step as SKIPPED.
                    logger.warning(f"Step {step_id} skipped — dependencies not met")
                    await self.state_manager.update_step_status(execution_id, step_id, "SKIPPED",
                                                                error="Dependencies not met")
                    continue

                # Check condition (if specified)
                condition = step.get("condition")
                if condition is not None:
                    condition_met = self._evaluate_condition(condition, state)
                    if not condition_met:
                        logger.info(f"Step {step_id} condition not met: {condition}")
                        await self.state_manager.update_step_status(
                            execution_id,
                            step_id,
                            "SKIPPED",
                            error=f"Condition not met: {condition}"
                        )
                        await ws_manager.notify_workflow_status(
                            user_id,
                            execution_id,
                            "STEP_SKIPPED",
                            {"step_id": step_id, "reason": f"Condition not met: {condition}"}
                        )
                        continue

                # Resolve inputs
                try:
                    resolved_params = self._resolve_parameters(step.get("parameters", {}), state)
                except MissingInputError as e:
                    logger.info(f"Pausing execution {execution_id} at step {step_id}: {e}")
                    await self.state_manager.update_step_status(execution_id, step_id, "PAUSED", error=str(e))
                    await self.state_manager.update_execution_status(execution_id, "PAUSED", error=f"Missing input: {e.missing_var}")
                    
                    await ws_manager.notify_workflow_status(
                        user_id,
                        execution_id,
                        "PAUSED",
                        {
                            "reason": "missing_input",
                            "missing_var": e.missing_var,
                            "step_id": step_id
                        }
                    )
                    self._notify_workflow_paused(
                        workflow, execution_id, step_id, user_id,
                        reason=f"Missing input: {e.missing_var}",
                        missing_var=e.missing_var,
                    )
                    return

                # Validate input schema
                self._validate_input_schema(step, resolved_params)

                # Execute step
                await self.state_manager.update_step_status(execution_id, step_id, "RUNNING")
                await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_RUNNING", {"step_id": step_id})

                # --- START SAAS GOVERNANCE INTERLOCK ---
                # Check for agent governance authorization
                # try wraps the whole `with get_db_session()` block: the
                # session context manager commits on exit, and a failure there
                # (e.g. an invalidated transaction after a swallowed inner
                # error) must not abort the run — fail open as intended.
                try:
                    with get_db_session() as db:
                        governance = ServiceFactory.get_governance_service(
                            db, workspace_id=workspace_id,
                            tenant_id=tenant_id)
                        agent_id = workflow.get("agent_id") or "system_agent"
                        
                        # Find registry agent if not system
                        agent_record = None
                        if agent_id != "system_agent":
                            agent_record = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                        
                        # Governance applies only to registry-backed agents;
                        # unbound system_agent workflows still honor the
                        # workflow owner's never-autonomous baskets even
                        # though they have no maturity row to govern.
                        from core.task_classification import (
                            current_task_profile,
                        )

                        if agent_record is not None:
                            can_perform_result = await governance.can_perform_action_async(
                                agent_id=agent_id,
                                action_type=step.get("action", "default"),
                                task_profile=current_task_profile(),
                            )
                        else:
                            from core.autonomy_policy import (
                                evaluate_never_autonomous,
                                has_never_autonomous_clearance,
                            )

                            _profile = current_task_profile()
                            _never = evaluate_never_autonomous(
                                db,
                                user_id,
                                _profile,
                                tenant_id=tenant_id,
                                workspace_id=workspace_id,
                                action_type=step.get("action", "default"),
                            )
                            if (_never.get("outcome") == "review"
                                    and has_never_autonomous_clearance(
                                        None,
                                        decision=_never,
                                        task_profile=_profile,
                                        tenant_id=tenant_id,
                                        workspace_id=workspace_id,
                                        execution_id=execution_id)):
                                _never = dict(_never)
                                _never["cleared"] = True
                            can_perform_result = {
                                "allowed": _never.get("outcome") != "review",
                                "requires_human_approval": (
                                    _never.get("outcome") == "review"),
                                "reason": _never.get("reason"),
                                "never_autonomous": _never,
                            }
                        if can_perform_result is not None:
                            can_perform = (
                                can_perform_result.get("allowed", False)
                                if isinstance(can_perform_result, dict)
                                else bool(can_perform_result)
                            )
                            message = (
                                can_perform_result.get("reason", "Governance denied")
                                if isinstance(can_perform_result, dict)
                                else ""
                            )
                            _never_review = bool(
                                isinstance(can_perform_result, dict)
                                and (can_perform_result.get("never_autonomous") or {}).get(
                                    "outcome") == "review")
                            if not can_perform or _never_review:
                                # Trust policy / maturity gate: the agent is
                                # not autonomous enough for this action. A
                                # resume carrying the approval for THIS exact
                                # step is the one authorized way through —
                                # the durable HITL row is re-read, never a
                                # boolean or stale in-process grant.
                                execution_inputs = (
                                    state.get("input_data")
                                    if isinstance(state, dict) else {}) or {}
                                previous_step_status = str(
                                    (step_state or {}).get("status") or "")
                                approved_binding = await self._durable_step_approval(
                                    execution_id, step_id,
                                    step.get("action", "default"),
                                    execution_inputs,
                                    payload=resolved_params,
                                    workspace_id=workspace_id,
                                    tenant_id=tenant_id,
                                )
                                if approved_binding is not None:
                                    if previous_step_status == "RUNNING":
                                        # The approved step was already
                                        # dispatched by an earlier worker and
                                        # never recorded a terminal state.
                                        # Re-running it could duplicate the
                                        # effect; stop for reconciliation.
                                        reason = (
                                            "Approved step was already "
                                            "dispatched before this resume; "
                                            "its outcome is uncertain. "
                                            "Reconcile it before retrying.")
                                        await self.state_manager.update_step_status(
                                            execution_id, step_id, "PAUSED",
                                            error=reason)
                                        await self.state_manager.update_execution_status(
                                            execution_id, "PAUSED", error=reason)
                                        await ws_manager.notify_workflow_status(
                                            user_id, execution_id, "PAUSED",
                                            {"reason": "approval_already_consumed",
                                             "step_id": step_id,
                                             "hitl_action_id": approved_binding[
                                                 "hitl_action_id"],
                                             "error": reason})
                                        return
                                    # Consume the approval durably BEFORE
                                    # dispatch: a crash can leave the step
                                    # ambiguous, never executable twice.
                                    consumed = list(
                                        execution_inputs.get(
                                            "consumed_hitl_action_ids") or [])
                                    consumed.append(
                                        approved_binding["hitl_action_id"])
                                    await self.state_manager.update_execution_inputs(
                                        execution_id,
                                        {"consumed_hitl_action_ids":
                                         consumed[-50:]})
                                    logger.info(
                                        "Workflow %s step %s authorized by "
                                        "durable HITL %s", execution_id,
                                        step_id,
                                        approved_binding["hitl_action_id"])
                                    if isinstance(can_perform_result, dict) and (
                                            can_perform_result.get(
                                                "never_autonomous")):
                                        from core.autonomy_policy import (
                                            grant_never_autonomous_clearance,
                                        )

                                        grant_never_autonomous_clearance(
                                            step,
                                            can_perform_result[
                                                "never_autonomous"],
                                            task_profile=current_task_profile(),
                                            execution_id=execution_id,
                                            tenant_id=tenant_id,
                                            workspace_id=workspace_id,
                                        )
                                else:
                                    # No matching durable approval yet: pause
                                    # durably and file the exact effect for a
                                    # human decision.
                                    logger.warning(f"🚫 Governance pause for execution {execution_id} at step {step_id}: {message}")
                                    hitl_action_id = None
                                    try:
                                        hitl_action_id = governance.request_approval(
                                            agent_id=agent_id,
                                            action_type=step.get("action", "default"),
                                            params={
                                                "execution_id": execution_id,
                                                "workflow_id": workflow.get("id", "unknown"),
                                                "step_id": step_id,
                                                "parameters": resolved_params,
                                                "tenant_id": tenant_id,
                                            },
                                            reason=message,
                                        )
                                    except Exception as hitl_error:
                                        logger.error(f"Failed to create HITL action for paused execution {execution_id}: {hitl_error}")
                                    await self.state_manager.update_step_status(execution_id, step_id, "PAUSED", error=f"Governance approval required: {message}")
                                    await self.state_manager.update_execution_status(execution_id, "PAUSED", error=f"Governance approval required: {message}")
                                    await ws_manager.notify_workflow_status(
                                        user_id, execution_id, "PAUSED",
                                        {"reason": "hitl_required", "hitl_action_id": hitl_action_id,
                                         "step_id": step_id, "error": message}
                                    )
                                    self._notify_workflow_paused(
                                        workflow, execution_id, step_id, user_id,
                                        reason=f"Governance approval required: {message}",
                                        hitl_action_id=hitl_action_id,
                                    )
                                    return
                except Exception as gov_error:
                    logger.error(f"Governance check failed, failing open for safety but logging error: {gov_error}")
                # --- END SAAS GOVERNANCE INTERLOCK ---

                # Phase 5: publish STEP_STARTED for EventBus observability.
                self._publish_orchestration_event(
                    "STEP_STARTED", workflow.get("id", "unknown"), execution_id, step_id,
                )

                # Create step execution record
                try:
                    with get_db_session() as db:
                        step_exec = WorkflowExecutionLog(
                            execution_id=execution_id,
                            workflow_id=workflow.get("id", "unknown"),
                            step_id=step["id"],
                            step_type=step.get("type", "action"),
                            start_time=datetime.now(timezone.utc),
                            end_time=datetime.now(timezone.utc),
                            duration_ms=0,
                            status="running",
                            trigger_data=resolved_params
                        )
                        db.add(step_exec)
                        db.commit()
                except Exception as e:
                    logger.error(f"Failed to create step execution record: {e}")
                
                try:
                    output = await self._execute_step(step, resolved_params)
                    # BUG-067: _execute_step can return {"status": "error", ...}
                    # instead of raising. Previously this was treated as success
                    # (step marked COMPLETED, workflow continued). Now check the
                    # returned status and fail the step if it errored.
                    if isinstance(output, dict) and output.get("status") == "error":
                        error_msg = output.get("error", "Step execution failed")
                        raise Exception(f"Step {step_id} failed: {error_msg}")
                    self._validate_output_schema(step, output)
                    await self.state_manager.update_step_status(execution_id, step_id, "COMPLETED", output=output)
                    await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_COMPLETED", {"step_id": step_id})

                    # --- START SAAS TIME TRAVEL SNAPSHOT ---
                    # Create snapshot for forking/replay capability
                    try:
                        with get_db_session() as db:
                            # Refresh state to capture current results
                            current_state = await self.state_manager.get_execution_state(execution_id)
                            snapshot_data = {
                                "input_data": current_state.get("input_data", {}),
                                "outputs": current_state.get("outputs", {}),
                                "step_results": current_state.get("step_results", {}),
                                "metadata": workflow.get("metadata", {})
                            }
                            
                            snapshot = WorkflowSnapshot(
                                tenant_id=tenant_id,
                                execution_id=execution_id,
                                step_id=step_id,
                                step_order=steps.index(step),
                                context_snapshot=json.dumps(snapshot_data),
                                status="COMPLETED"
                            )
                            db.add(snapshot)
                            db.commit()
                            logger.debug(f"📸 Snapshot created for {execution_id} at step {step_id}")
                    except Exception as snapshot_error:
                        logger.warning(f"Failed to create Time Travel snapshot: {snapshot_error}")
                    # --- END SAAS TIME TRAVEL SNAPSHOT ---

                    # Update step execution record
                    try:
                        with get_db_session() as db:
                            step_exec = db.query(WorkflowExecutionLog).filter(
                                WorkflowExecutionLog.execution_id == execution_id,
                                WorkflowExecutionLog.step_id == step_id
                            ).first()
                            if step_exec:
                                end_time = datetime.now(timezone.utc)
                                # SQLite returns the stored start as naive UTC;
                                # normalize it before subtracting the aware end.
                                start_time = _as_aware_utc(step_exec.start_time)
                                step_exec.status = "completed"
                                step_exec.end_time = end_time
                                if start_time is not None:
                                    step_exec.duration_ms = max(
                                        0,
                                        int((end_time - start_time).total_seconds() * 1000),
                                    )
                                step_exec.results = output
                                db.commit()
                    except Exception as e:
                        logger.error(f"Failed to update step execution record: {e}")
                    
                    # Update in-memory state for next steps
                    state = await self.state_manager.get_execution_state(execution_id)

                    # Phase 5: publish STEP_COMPLETED for EventBus observability.
                    self._publish_orchestration_event(
                        "STEP_COMPLETED", workflow.get("id", "unknown"), execution_id, step_id,
                    )

                except Exception as e:
                    logger.error(f"Step {step_id} failed: {e}")
                    await self.state_manager.update_step_status(execution_id, step_id, "FAILED", error=str(e))

                    # continue_on_error: mark the step FAILED but keep the
                    # workflow running (mirrors the graph-execution path that
                    # activates downstream connections after a tolerated
                    # failure). The workflow ends PARTIAL instead of COMPLETED
                    # so the failure remains visible.
                    if step.get("continue_on_error"):
                        logger.warning(f"Step {step_id} failed but continue_on_error is True, continuing workflow")
                        await ws_manager.notify_workflow_status(
                            user_id, execution_id, "STEP_FAILED",
                            {"step_id": step_id, "error": str(e), "continue_on_error": True}
                        )
                        had_step_failures = True
                        state = await self.state_manager.get_execution_state(execution_id)
                        continue

                    await self.state_manager.update_execution_status(execution_id, "FAILED", error=str(e))
                    await ws_manager.notify_workflow_status(user_id, execution_id, "FAILED", {"error": str(e), "step_id": step_id})

                    # Phase 5: publish STEP_FAILED + WORKFLOW_FAILED for EventBus.
                    self._publish_orchestration_event(
                        "STEP_FAILED", workflow.get("id", "unknown"), execution_id, step_id,
                        data={"error": str(e)},
                    )
                    self._publish_orchestration_event(
                        "WORKFLOW_FAILED", workflow.get("id", "unknown"), execution_id,
                        data={"error": str(e), "step_id": step_id},
                    )
                    
                    # Send failure notification
                    asyncio.create_task(notifier.notify_failure(
                        workflow_id=workflow.get("id", "unknown"),
                        workflow_name=workflow.get("name", "Untitled Workflow"),
                        execution_id=execution_id,
                        error=str(e)
                    ))

                    # Track failure
                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                    analytics.track_workflow_execution(
                        workflow_id=workflow.get("id", "unknown"),
                        success=False,
                        duration_seconds=duration,
                        time_saved_seconds=0, # Could calculate based on step metadata
                        business_value=0
                    )

                    # Marketplace Tracking
                    template_id = workflow.get("created_from_template")
                    if template_id:
                        MarketplaceUsageTracker.track_usage(
                            item_type="workflow",
                            item_id=template_id,
                            success=False,
                            duration_ms=int(duration * 1000)
                        )
                    return

            # A cancellation accepted while the last step was settling must
            # not turn into a late COMPLETED/PARTIAL write or notification.
            if await self._stop_at_cancellation_boundary(
                    execution_id, ws_manager, user_id):
                return

            if had_step_failures:
                status_updated = await self.state_manager.update_execution_status(
                    execution_id, "PARTIAL")
                if status_updated is False:
                    # A cancellation committed after the final boundary read.
                    # The guarded UPDATE kept CANCELLED; publish no terminal
                    # status or success event for this run.
                    logger.info(
                        "Workflow %s PARTIAL write rejected by durable "
                        "cancellation", execution_id)
                    return
                await ws_manager.notify_workflow_status(user_id, execution_id, "PARTIAL")
            else:
                status_updated = await self.state_manager.update_execution_status(
                    execution_id, "COMPLETED")
                if status_updated is False:
                    logger.info(
                        "Workflow %s COMPLETED write rejected by durable "
                        "cancellation", execution_id)
                    return
                await ws_manager.notify_workflow_status(user_id, execution_id, "COMPLETED")

            # Phase 5: publish WORKFLOW_COMPLETED for EventBus observability.
            self._publish_orchestration_event(
                "WORKFLOW_COMPLETED", workflow.get("id", "unknown"), execution_id,
            )

            # Send completion notification
            asyncio.create_task(notifier.notify_completion(
                workflow_id=workflow.get("id", "unknown"),
                workflow_name=workflow.get("name", "Untitled Workflow"),
                execution_id=execution_id,
                results=state.get("outputs", {})
            ))

            # Students observe successful workflow outcomes (automated
            # observation trigger — fire-and-forget, best-effort).
            from core.student_learning_service import auto_observe
            asyncio.create_task(auto_observe(
                workspace_id=workspace_id,
                observation_type="workflow_execution",
                summary=f"Workflow '{workflow.get('name', workflow.get('id', 'unknown'))}' completed successfully",
                details={"workflow_id": workflow.get("id"), "execution_id": execution_id},
            ))
            
            # Track success
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            analytics.track_workflow_execution(
                workflow_id=workflow.get("id", "unknown"),
                success=True,
                duration_seconds=duration,
                time_saved_seconds=workflow.get("estimated_time_saved", 60), # Default 1 min saved
                business_value=workflow.get("business_value", 10) # Default $10 value
            )

            # Marketplace Tracking
            template_id = workflow.get("created_from_template")
            if template_id:
                MarketplaceUsageTracker.track_usage(
                    item_type="workflow",
                    item_id=template_id,
                    success=True,
                    duration_ms=int(duration * 1000)
                )
            
        except Exception as e:
            logger.error(f"Execution {execution_id} failed: {e}")
            await self.state_manager.update_execution_status(execution_id, "FAILED", error=str(e))
            await ws_manager.notify_workflow_status(user_id, execution_id, "FAILED", {"error": str(e)})
            
            # Track failure
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            analytics.track_workflow_execution(
                workflow_id=workflow.get("id", "unknown"),
                success=False,
                duration_seconds=duration,
                time_saved_seconds=0,
                business_value=0
            )

    def _check_dependencies(self, step: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """Check if all dependencies are met"""
        depends_on = step.get("depends_on", [])
        for dep_id in depends_on:
            dep_state = state.get("steps", {}).get(dep_id, {})
            if dep_state.get("status") != "COMPLETED":
                return False
        return True

    def _evaluate_condition(self, condition: str, state: Dict[str, Any]) -> bool:
        """
        Evaluate a condition string against current state.
        Supports variable substitution like ${step_id.output_key} and simple boolean expressions.
        Example conditions:
        - "${step1.output.success} == true"
        - "${input.count} > 5"
        - "${step2.result.status} == 'completed'"
        """
        if not condition:
            return True  # No condition means always execute

        try:
            # First, replace all variable references with their values
            # We'll build a new expression with values substituted
            expr = condition
            matches = self.var_pattern.findall(condition)

            # Replace each variable with its actual value
            for var_path in matches:
                value = self._get_value_from_path(var_path, state)
                if value is None:
                    # Variable not found, condition evaluates to False
                    logger.warning(f"Variable {var_path} not found in condition: {condition}")
                    return False

                # Convert value to appropriate string representation for eval
                if isinstance(value, str):
                    # Quote strings for eval
                    replacement = repr(value)
                elif isinstance(value, (int, float, bool)):
                    replacement = str(value)
                elif value is None:
                    replacement = "None"
                else:
                    # For complex objects, use repr
                    replacement = repr(value)

                # Replace the variable reference in the expression
                expr = expr.replace(f"${{{var_path}}}", replacement)

            # CODE INJECTION FIX: Use safe_eval with AST validation
            # This prevents sandbox escape via __class__, __base__, __subclasses__, etc.
            from core.safe_evaluator import safe_eval, SafeEvalError

            try:
                # Evaluate the expression with AST validation
                result = safe_eval(expr, {})

                # Convert to boolean
                if isinstance(result, bool):
                    return result
                else:
                    # Non-boolean result, treat as truthy/falsy
                    return bool(result)

            except SafeEvalError as e:
                logger.error(f"Code injection blocked in condition '{condition}': {e}")
                # If expression is unsafe, default to False for safety
                return False

        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            # If we can't evaluate, default to False for safety
            return False

    def _resolve_parameters(self, parameters: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve parameter values from state (inputs and previous outputs).
        Raises MissingInputError if a required variable is missing.
        """
        return {
            key: self._resolve_parameter_value(value, state)
            for key, value in parameters.items()
        }

    def _resolve_parameter_value(self, value: Any, state: Dict[str, Any]) -> Any:
        """Resolve a single parameter value, recursing into nested dicts and
        lists so ${...} references inside structured parameters (HTTP configs,
        MCP arguments, arrays) are substituted too — previously they were
        passed to integrations as literal strings."""
        if isinstance(value, dict):
            return {
                k: self._resolve_parameter_value(v, state)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self._resolve_parameter_value(v, state) for v in value]
        if isinstance(value, str):
            # Check for variable substitution ${var}
            matches = self.var_pattern.findall(value)
            if not matches:
                return value
            # A pure single reference ("${path}" exactly) preserves the
            # resolved value's type (e.g. an int output stays an int).
            if len(matches) == 1 and value == f"${{{matches[0]}}}":
                resolved_val = self._get_value_from_path(matches[0], state)
                if resolved_val is None and not self._path_exists(matches[0], state):
                    raise MissingInputError(
                        f"Variable {matches[0]} not found", matches[0]
                    )
                return resolved_val
            # Interpolate EVERY variable occurrence into the string,
            # preserving surrounding text (e.g. "Hello ${name}!").
            # Replacing the whole value with only the first variable
            # silently dropped prefixes/suffixes and later variables.
            interpolated = value
            for var_path in matches:
                resolved_val = self._get_value_from_path(var_path, state)
                if resolved_val is None and not self._path_exists(var_path, state):
                    raise MissingInputError(
                        f"Variable {var_path} not found", var_path
                    )
                interpolated = interpolated.replace(
                    f"${{{var_path}}}", str(resolved_val)
                )
            return interpolated
        return value

    def _path_exists(self, path: str, state: Dict[str, Any]) -> bool:
        """Check whether a dot-path exists in state — distinguishes a
        legitimately-None output value from a genuinely missing variable, so a
        None value does not pause the workflow with MissingInputError."""
        parts = path.split(".")
        root = parts[0]
        if root == "input":
            current = state.get("input_data", {})
        else:
            current = state.get("outputs", {}).get(root)
        if current is None:
            return False
        for part in parts[1:]:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        return True

    def _get_value_from_path(self, path: str, state: Dict[str, Any]) -> Any:
        """
        Retrieve value from state using dot notation.
        e.g. "step_id.output_key" or "input.key"
        """
        parts = path.split('.')
        root = parts[0]
        
        if root == "input":
            # Access input data
            current = state.get("input_data", {})
            for part in parts[1:]:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
            return current
            
        else:
            # Access step output
            step_output = state.get("outputs", {}).get(root)
            if step_output is None:
                return None
                
            current = step_output
            for part in parts[1:]:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
            return current

    def _validate_input_schema(self, step: Dict[str, Any], params: Dict[str, Any]) -> None:
        """Validate input parameters against step's input schema."""
        input_schema = step.get("input_schema")
        if not input_schema:
            return
        try:
            validate(instance=params, schema=input_schema)
        except ValidationError as e:
            raise SchemaValidationError(
                f"Input validation failed for step {step.get('id', 'unknown')}: {e.message}",
                schema_type="input",
                errors=[e.message]
            )

    def _validate_output_schema(self, step: Dict[str, Any], output: Dict[str, Any]) -> None:
        """Validate output against step's output schema."""
        output_schema = step.get("output_schema")
        if not output_schema:
            return
        try:
            validate(instance=output, schema=output_schema)
        except ValidationError as e:
            raise SchemaValidationError(
                f"Output validation failed for step {step.get('id', 'unknown')}: {e.message}",
                schema_type="output",
                errors=[e.message]
            )

    @async_retry_with_backoff(max_retries=3, retry_if=_retry_step_failure)
    async def _execute_step(self, step: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single step.
        This is where we would dispatch to specific service integrations.
        For now, we'll simulate execution or use a basic dispatcher.
        """
        service = step["service"]
        action = step["action"]
        
        logger.info(f"Executing {service}.{action} with params: {params}")
        
        # Fixed: Implement actual service registry lookup and execution
        # Service registry mapping (source of truth for catalog admission).
        service_registry = self._service_registry()

        # Check for fallback service
        fallback_service = step.get("fallback_service")
        # Get timeout if specified
        timeout = step.get("timeout")

        # Try primary service first
        primary_error = None
        executor = service_registry.get(service)
        if executor is None:
            # Try generic executor for catalog integrations
            try:
                logger.info(f"Service {service} not in registry, attempting generic execution via catalog")
                result = await self._execute_generic_action(service, action, params, step.get("connection_id"))
                return {
                    "status": "success",
                    "service": service,
                    "action": action,
                    "result": result,
                    "timestamp": datetime.now().isoformat(),
                    "execution_method": "generic_catalog_executor"
                }
            except Exception as e:
                logger.warning(f"Generic execution failed or service not found in catalog: {e}")
                # Record the failure and continue to the fallback path instead
                # of raising — an unknown service with a fallback_service must
                # still attempt the fallback.
                primary_error = ValueError(
                    f"Unknown service: {service} (and generic execution failed: {e})"
                )
        else:
            try:
                # Pass automation context if executor supports it
                context = {
                    "workflow_id": step.get("workflow_id"),
                    "execution_id": step.get("execution_id")
                }

                # P9: the mcp executor consumes the step's run identity so its
                # tool dispatch goes through the shared sandbox gate.
                # main_agent needs the same trusted step so it can resolve its
                # requested agent inside the run's workspace/tenant scope.
                # The legacy ai text service likewise reads only the run's
                # trusted scope from the step, never from params.
                step_kwargs = (
                    {"step": step}
                    if service in (
                        "mcp", "main_agent", "ai", "goal_management",
                        "workflow_notification")
                    else {})

                if timeout is not None and timeout > 0:
                    # A text-model dispatch gets the same configured step
                    # deadline as an absolute monotonic instant, so the
                    # provider worker cannot start after the workflow's
                    # budget has already elapsed.
                    if service in _TEXT_MODEL_SERVICES:
                        step_kwargs["caller_deadline"] = (
                            time.monotonic() + timeout)
                    try:
                        result = await asyncio.wait_for(executor(action, params, connection_id=step.get("connection_id"), **step_kwargs), timeout=timeout)
                    except _CallerDeadlineExceeded:
                        # The provider never dispatched: this is the model's
                        # configured step timeout, not a provider failure.
                        raise _step_timeout_error(
                            service, step['id'], timeout)
                    except asyncio.TimeoutError:
                        raise _step_timeout_error(
                            service, step['id'], timeout)
                else:
                    result = await executor(action, params, connection_id=step.get("connection_id"), **step_kwargs)
                # Executors that return a non-success status envelope (e.g.
                # MCP {"status": "error"}, sub-workflow {"status": "timeout"})
                # must surface as failures, not be wrapped as a successful
                # result. Previously only status == "error" was caught, so a
                # timed-out sub-workflow (status == "timeout") was silently
                # marked COMPLETED and the parent workflow continued.
                if (
                    isinstance(result, dict)
                    and result.get("status")
                    and result.get("status") != "success"
                ):
                    raise Exception(
                        f"Step {step['id']} failed: {result.get('error', 'Step execution failed')}"
                    )
                return {
                    "status": "success",
                    "service": service,
                    "action": action,
                    "result": result,
                    "timestamp": datetime.now().isoformat(),
                    "execution_method": "service_registry"
                }
            except Exception as e:
                primary_error = e
                logger.warning(f"Primary service {service}.{action} failed: {e}")
                # Continue to fallback if available

        # If primary failed and fallback service is specified, try fallback
        if primary_error is not None and fallback_service and fallback_service in service_registry:
            logger.info(f"Attempting fallback service {fallback_service}.{action}")
            try:
                fallback_executor = service_registry[fallback_service]
                fallback_step_kwargs = (
                    {"step": step}
                    if fallback_service in (
                        "mcp", "main_agent", "ai", "goal_management",
                        "workflow_notification")
                    else {})
                if timeout is not None and timeout > 0:
                    if fallback_service in _TEXT_MODEL_SERVICES:
                        fallback_step_kwargs["caller_deadline"] = (
                            time.monotonic() + timeout)
                    try:
                        result = await asyncio.wait_for(fallback_executor(action, params, connection_id=step.get("connection_id"), **fallback_step_kwargs), timeout=timeout)
                    except _CallerDeadlineExceeded:
                        raise _step_timeout_error(
                            fallback_service,
                            step.get("id", "unknown"),
                            timeout,
                            message=(
                                f"Fallback service {fallback_service}.{action} "
                                f"timed out after {timeout}s"),
                        )
                    except asyncio.TimeoutError:
                        raise _step_timeout_error(
                            fallback_service,
                            step.get("id", "unknown"),
                            timeout,
                            message=(
                                f"Fallback service {fallback_service}.{action} "
                                f"timed out after {timeout}s"),
                        )
                else:
                    result = await fallback_executor(action, params, connection_id=step.get("connection_id"), **fallback_step_kwargs)
                if isinstance(result, dict) and result.get("status") and result.get("status") != "success":
                    raise ValueError(
                        f"Fallback service {fallback_service}.{action} returned error: "
                        f"{result.get('error', 'unknown error')}"
                    )
                return {
                    "status": "success",
                    "service": fallback_service,
                    "action": action,
                    "result": result,
                    "timestamp": datetime.now().isoformat(),
                    "execution_method": "fallback_service",
                    "original_service": service,
                    "fallback_used": True
                }
            except Exception as e:
                logger.error(f"Fallback service {fallback_service}.{action} also failed: {e}")
                # Both primary and fallback failed — raise so the run loop marks
                # the step FAILED. Returning an error dict would be treated as a
                # COMPLETED step (the run loop only fails steps on exceptions).
                #
                # A model dispatch that timed out may still be running in the
                # background. Keep its original typed timeout (and its
                # configured deadline) instead of masking it as a generic
                # fallback error; the shared retry predicate then declines to
                # repeat the same step automatically. A model timeout raised by
                # the fallback itself is preserved for the same reason.
                if isinstance(primary_error, ModelStepTimeoutError):
                    raise primary_error from e
                if isinstance(e, ModelStepTimeoutError):
                    raise
                raise ValueError(
                    f"Primary service failed: {primary_error}; "
                    f"fallback {fallback_service} also failed: {e}"
                ) from e

        # No fallback or fallback not in registry
        logger.error(f"Failed to execute {service}.{action}: {primary_error}")
        if isinstance(primary_error, Exception):
            raise primary_error
        raise ValueError(f"Unknown service: {service}")

    # Service executor methods
    async def _execute_slack_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Slack service actions"""
        from integrations.slack_service_unified import slack_unified_service

        # Try to get token if connection_id is present
        token_data = None
        if connection_id:
            token_data = token_storage.get_token(connection_id)
            if not token_data:
                # Fallback: try looking up by service name
                token_data = token_storage.get_token("slack")
        
        token = token_data.get("access_token") if token_data else None
        
        logger.info(f"Executing Slack action {action} with connection {connection_id} (Token found: {bool(token)})")

        try:
            result = None

            if not token:
                raise AuthenticationError("Slack authentication required (no token found)")

            # Map workflow actions to Slack service methods
            if action == "chat_postMessage":
                channel = params.get("channel")
                text = params.get("text")
                result = await slack_unified_service.post_message(token=token, channel_id=channel, text=text)

            elif action == "chat_getChannels" or action == "list_channels":
                # List channels (public and private by default)
                types = params.get("types", "public_channel,private_channel")
                result = await slack_unified_service.list_channels(token=token, types=types)

            elif action == "chat_getUsers" or action == "list_users":
                # Get user info - use team info endpoint for user list
                result = await slack_unified_service.get_team_info(token=token)

            elif action == "get_channel_info":
                channel_id = params.get("channel_id")
                if not channel_id:
                    raise ValueError("channel_id is required for get_channel_info")
                result = await slack_unified_service.get_channel_info(token=token, channel_id=channel_id)

            elif action == "get_channel_history":
                channel_id = params.get("channel_id")
                limit = params.get("limit", 100)
                if not channel_id:
                    raise ValueError("channel_id is required for get_channel_history")
                result = await slack_unified_service.get_channel_history(token=token, channel_id=channel_id, limit=limit)

            elif action == "update_message":
                channel_id = params.get("channel_id")
                message_ts = params.get("message_ts")
                text = params.get("text")
                if not all([channel_id, message_ts, text]):
                    raise ValueError("channel_id, message_ts, and text are required for update_message")
                result = await slack_unified_service.update_message(token=token, channel_id=channel_id, message_ts=message_ts, text=text)

            elif action == "delete_message":
                channel_id = params.get("channel_id")
                message_ts = params.get("message_ts")
                if not all([channel_id, message_ts]):
                    raise ValueError("channel_id and message_ts are required for delete_message")
                result = await slack_unified_service.delete_message(token=token, channel_id=channel_id, message_ts=message_ts)

            elif action == "search_messages":
                query = params.get("query")
                if not query:
                    raise ValueError("query is required for search_messages")
                count = params.get("count", 100)
                result = await slack_unified_service.search_messages(token=token, query=query, count=count)

            elif action == "files_list":
                channel_id = params.get("channel_id")
                user_id = params.get("user_id")
                count = params.get("count", 100)
                result = await slack_unified_service.list_files(token=token, channel_id=channel_id, user_id=user_id, count=count)

            elif action == "files_get_upload_url_external":
                # File upload requires special handling - get upload URL first
                # For now, provide a structured response indicating the flow
                result = {
                    "ok": False,
                    "error": "File upload requires getUploadURLExternal endpoint followed by file upload",
                    "flow": "1. Call files.getUploadURLExternal, 2. Upload file to returned URL, 3. Call files.completeUploadExternal"
                }

            elif action == "reactions_add":
                # Add reaction to message
                # This would need to be implemented in SlackUnifiedService
                result = {
                    "ok": False,
                    "error": "reactions_add not yet implemented in SlackUnifiedService - needs API endpoint addition",
                    "endpoint": "reactions.add"
                }

            else:
                # Unknown action - provide helpful error
                raise ValueError(
                    f"Unsupported Slack action: {action}. "
                    f"Supported actions: chat_postMessage, chat_getChannels, chat_getUsers, "
                    f"get_channel_info, get_channel_history, update_message, delete_message, "
                    f"search_messages, files_list, files_get_upload_url_external, reactions_add"
                )

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": bool(token)
            }
        except Exception as e:
             logger.error(f"Slack execution failed: {e}")
             raise e

    async def _execute_asana_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Asana service actions"""
        from integrations.asana_service import asana_service
        
        token = self._get_token(connection_id, "asana")
        if not token:
             # Try environment if no connection but that is fallback
             token = os.getenv("ASANA_ACCESS_TOKEN")

        logger.info(f"Executing Asana action {action} with connection {connection_id}")
        
        try:
            result = None

            if not token:
                raise AuthenticationError("Asana authentication required")

            # Map workflow actions to Asana service methods
            if action == "create_task":
                task_data = {
                    "name": params.get("name"),
                    "workspace": params.get("workspace"),
                    "projects": params.get("projects", [])
                }
                if params.get("notes"): task_data["notes"] = params.get("notes")
                if params.get("due_on"): task_data["due_on"] = params.get("due_on")
                if params.get("assignee"): task_data["assignee"] = params.get("assignee")

                result = await asana_service.create_task(token, task_data)

            elif action == "get_tasks":
                project_gid = params.get("project")
                workspace_gid = params.get("workspace")
                assignee = params.get("assignee")
                limit = params.get("limit", 50)

                result = await asana_service.get_tasks(
                    token,
                    project_gid=project_gid,
                    workspace_gid=workspace_gid,
                    assignee=assignee,
                    limit=limit
                )

            elif action == "get_projects":
                workspace = params.get("workspace")
                result = await asana_service.get_projects(token, workspace_gid=workspace)

            elif action == "update_task":
                task_gid = params.get("task_gid")
                if not task_gid:
                    raise ValueError("task_gid is required for update_task")

                updates = {}
                if params.get("name"): updates["name"] = params.get("name")
                if params.get("notes"): updates["notes"] = params.get("notes")
                if params.get("completed") is not None: updates["completed"] = params.get("completed")
                if params.get("due_on"): updates["due_on"] = params.get("due_on")
                if params.get("assignee"): updates["assignee"] = params.get("assignee")

                result = await asana_service.update_task(token, task_gid, updates)

            elif action == "add_comment":
                task_gid = params.get("task_gid")
                text = params.get("text")
                if not all([task_gid, text]):
                    raise ValueError("task_gid and text are required for add_comment")

                result = await asana_service.add_task_comment(token, task_gid, text)

            elif action == "get_workspaces":
                result = await asana_service.get_workspaces(token)

            elif action == "get_users":
                workspace_gid = params.get("workspace")
                if not workspace_gid:
                    raise ValueError("workspace is required for get_users")
                limit = params.get("limit", 50)
                result = await asana_service.get_users(token, workspace_gid, limit)

            elif action == "get_teams":
                workspace_gid = params.get("workspace")
                if not workspace_gid:
                    raise ValueError("workspace is required for get_teams")
                limit = params.get("limit", 50)
                result = await asana_service.get_teams(token, workspace_gid, limit)

            elif action == "search_tasks":
                workspace_gid = params.get("workspace")
                query = params.get("query")
                if not all([workspace_gid, query]):
                    raise ValueError("workspace and query are required for search_tasks")
                limit = params.get("limit", 20)
                result = await asana_service.search_tasks(token, workspace_gid, query, limit)

            elif action == "create_project":
                # Project creation needs to be added to AsanaService
                # For now, provide structured error
                result = {
                    "ok": False,
                    "error": "create_project not yet implemented in AsanaService - needs API endpoint addition",
                    "endpoint": "projects.create"
                }

            else:
                # Unknown action - provide helpful error
                raise ValueError(
                    f"Unsupported Asana action: {action}. "
                    f"Supported actions: create_task, get_tasks, get_projects, update_task, "
                    f"add_comment, get_workspaces, get_users, get_teams, search_tasks, create_project"
                )

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": bool(token)
            }
        except Exception as e:
            logger.error(f"Asana execution failed: {e}")
            raise e

    async def _execute_discord_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Discord service actions"""
        from integrations.discord_service import discord_service
        
        token = self._get_token(connection_id, "discord")
        logger.info(f"Executing Discord action {action} with connection {connection_id}")
        
        try:
            if not token and not discord_service.bot_token:
                 raise AuthenticationError("Discord authentication required")

            if action == "send_message":
                 channel_id = params.get("channel_id")
                 content = params.get("content")
                 result = await discord_service.send_message(channel_id, content, access_token=token, use_bot_token=not bool(token))
            else:
                 await asyncio.sleep(0.1)
                 result = f"Discord {action} simulated"

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": bool(token) or bool(discord_service.bot_token)
            }
        except Exception as e:
             logger.error(f"Discord execution failed: {e}")
             raise e

    async def _execute_hubspot_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute HubSpot service actions"""
        from integrations.hubspot_service import HubSpotService

        token = self._get_token(connection_id, "hubspot")
        logger.info(f"Executing HubSpot action {action} with connection {connection_id}")
        
        try:
            hubspot_service = HubSpotService()
            if not token and not hubspot_service.access_token:
                 raise AuthenticationError("HubSpot authentication required")

            if action == "create_contact":
                 email = params.get("email")
                 first_name = params.get("firstname")
                 last_name = params.get("lastname")
                 result = await hubspot_service.create_contact(email=email, first_name=first_name, last_name=last_name, token=token)
            elif action == "create_deal":
                 name = params.get("dealname")
                 amount = params.get("amount", 0)
                 result = await hubspot_service.create_deal(name=name, amount=float(amount), token=token)
            else:
                 await asyncio.sleep(0.1)
                 result = f"HubSpot {action} simulated"

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": bool(token)
            }
        except Exception as e:
             logger.error(f"HubSpot execution failed: {e}")
             raise e

    async def _execute_salesforce_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Salesforce service actions"""
        from integrations.salesforce_service import SalesforceService
        
        token_data = None
        if connection_id:
             token_data = token_storage.get_token(connection_id)
        
        access_token = token_data.get("access_token") if token_data else None
        instance_url = token_data.get("instance_url") if token_data else None

        logger.info(f"Executing Salesforce action {action} with connection {connection_id}")
        
        try:
            sf_service = SalesforceService()
            # If we have dynamic tokens, create client
            sf = None
            if access_token and instance_url:
                sf = sf_service.create_client(access_token, instance_url)
            
            # If no dynamic client, validation fails unless we have some other fallback (which SF service doesn't really have easily)
            if not sf:
                 raise AuthenticationError("Salesforce authentication required (token + instance_url)")

            if action == "create_lead":
                 last_name = params.get("lastname")
                 company = params.get("company")
                 email = params.get("email")
                 result = await sf_service.create_lead(sf, last_name=last_name, company=company, email=email)
            elif action == "create_contact":
                 last_name = params.get("lastname")
                 email = params.get("email")
                 result = await sf_service.create_contact(sf, last_name=last_name, email=email)
            elif action == "create_opportunity":
                 name = params.get("name")
                 stage = params.get("stagename")
                 close_date = params.get("closedate")
                 result = await sf_service.create_opportunity(sf, name=name, stage_name=stage, close_date=close_date)
            else:
                 await asyncio.sleep(0.1)
                 result = f"Salesforce {action} simulated"

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": True
            }
        except Exception as e:
             logger.error(f"Salesforce execution failed: {e}")
             raise e

    async def _execute_github_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute GitHub service actions"""
        from integrations.github_service import GitHubService
        
        token = self._get_token(connection_id, "github")
        logger.info(f"Executing GitHub action {action} with connection {connection_id}")
        
        try:
            # Instantiate service with token (config-based; the constructor
            # does not accept an access_token positional/keyword argument)
            github = GitHubService(config={"access_token": token} if token else {})
            
            if action == "create_issue":
                 owner = params.get("owner")
                 repo = params.get("repo")
                 title = params.get("title")
                 body = params.get("body")
                 result = github.create_issue(owner, repo, title, body)
            else:
                 await asyncio.sleep(0.1)
                 result = f"GitHub {action} simulated"

            return {
                "action": action,
                "result": result,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"GitHub execution failed: {e}")
            raise e
            
    async def _execute_zoom_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        from integrations.zoom_service import ZoomService
        token = self._get_token(connection_id, "zoom")
        try:
            zoom_service = ZoomService()
            if action == "create_meeting":
                topic = params.get("topic")
                result = await zoom_service.create_meeting(topic=topic, access_token=token)
            else:
                await asyncio.sleep(0.1)
                result = f"Zoom {action} simulated"
            return {"action": action, "result": result, "status": "success"}
        except Exception as e:
            logger.error(f"Zoom execution failed: {e}")
            raise e

    async def _execute_notion_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        from integrations.notion_service import NotionService
        token = self._get_token(connection_id, "notion")
        try:
            notion = NotionService(config={"access_token": token} if token else {})
            if action == "create_page":
                parent = params.get("parent") # e.g. {"database_id": "..."}
                properties = params.get("properties")
                result = notion.create_page(parent, properties)
            else:
                await asyncio.sleep(0.1)
                result = f"Notion {action} simulated"
            return {"action": action, "result": result, "status": "success"}
        except Exception as e:
            logger.error(f"Notion execution failed: {e}")
            raise e

    def _get_token(self, connection_id: Optional[str], service_name: str) -> Optional[str]:
        """Helper to retrieve token from connection or fallback"""
        token_data = None
        if connection_id:
            token_data = token_storage.get_token(connection_id)
            if not token_data and service_name:
                token_data = token_storage.get_token(service_name)
        
        if token_data:
            return token_data.get("access_token")
        return None

    async def _execute_email_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Email service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Email {action} executed",
            "status": "success"
        }

    async def _execute_gmail_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Gmail service actions"""
        from integrations.gmail_service import GmailService

        # Try to get token if connection_id is present
        token_data = None
        if connection_id:
            token_data = token_storage.get_token(connection_id)
            if not token_data:
                token_data = token_storage.get_token("google")
        
        token = token_data.get("access_token") if token_data else None
        logger.info(f"Executing Gmail action {action} with connection {connection_id} (Token found: {bool(token)})")
        
        try:
            gmail_service = GmailService()
            result = None
            if action == "send_email":
                to = params.get("to")
                subject = params.get("subject")
                body = params.get("body")
                
                if not token:
                     raise AuthenticationError("Gmail authentication required (no token found)")

                # Use refactored send_message with token
                result = gmail_service.send_message(to=to, subject=subject, body=body, token=token)

                if not result:
                    raise ExternalServiceError("Gmail", "Failed to send email")
            
            elif action == "create_draft":
                 to = params.get("to")
                 subject = params.get("subject")
                 body = params.get("body")
                 if not token:
                     raise AuthenticationError("Gmail authentication required")
                 result = gmail_service.draft_message(to=to, subject=subject, body=body, token=token)

            else:
                await asyncio.sleep(0.1)
                result = f"Gmail {action} simulated"

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": bool(token)
            }
        except Exception as e:
             logger.error(f"Gmail execution failed: {e}")
             raise e

    async def _execute_calendar_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Calendar service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Calendar {action} executed",
            "status": "success"
        }

    async def _execute_database_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Database service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Database {action} executed",
            "status": "success"
        }

    async def _execute_ai_action(
        self,
        action: str,
        params: dict,
        connection_id: Optional[str] = None,
        step: Optional[dict] = None,
        caller_deadline: Optional[float] = None,
    ) -> dict:
        """Execute the legacy AI service's text-only actions.

        Only ``generate_content`` and ``summarize`` are real. They use the
        existing scoped LLM facade with the dispatcher's frozen AI scope, never
        the definition fallback and never params. Unknown actions, missing
        input/scope, provider failures and blank output are truthful failures.
        """
        ai_scope = (step or {}).get(AI_EXECUTION_SCOPE_KEY)
        workspace_id = (
            str(ai_scope.get("workspace_id") or "").strip()
            if isinstance(ai_scope, dict) else "")
        tenant_id = (
            str(ai_scope.get("tenant_id") or "").strip()
            if isinstance(ai_scope, dict) else "")
        if not workspace_id or not tenant_id:
            return _ai_failure(
                action, "ai step is missing its execution scope")

        if action == "generate_content":
            prompt = params.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                return _ai_failure(
                    action,
                    "generate_content requires a nonblank 'prompt' parameter")
            messages = [{"role": "user", "content": prompt}]
        elif action == "summarize":
            text = params.get("text")
            if not isinstance(text, str) or not text.strip():
                return _ai_failure(
                    action,
                    "summarize requires a nonblank 'text' parameter")
            messages = [{
                "role": "user",
                "content": f"Summarize the following text:\n\n{text}",
            }]
        else:
            return _ai_failure(
                action,
                f"Unsupported AI action '{action}'; supported actions: "
                "generate_content, summarize")

        from core.database import get_db_session
        from core.llm_service import get_llm_service

        completion_kwargs: Dict[str, Any] = {
            "messages": messages,
            "temperature": 0.7,
            "workspace_id": workspace_id,
            "tenant_id": tenant_id,
        }
        # An unset deadline keeps the historical call exactly as it was; only
        # a timed workflow step opts the provider dispatch into the boundary.
        if caller_deadline is not None:
            completion_kwargs["caller_deadline"] = caller_deadline

        try:
            with get_db_session() as db:
                llm_service = get_llm_service(
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    db=db)
                completion = await llm_service.generate_completion(
                    **completion_kwargs)
        except _CallerDeadlineExceeded:
            # Let the engine boundary translate this pre-dispatch refusal into
            # the configured step's typed timeout. Returning the ordinary AI
            # failure envelope here would erase both the type and its message.
            raise
        except Exception as llm_error:
            logger.error(
                "AI action '%s' failed in scoped LLM execution: %s",
                action, llm_error)
            return _ai_failure(
                action, "AI text completion failed", "provider_error")

        if not isinstance(completion, dict) or completion.get("success") is not True:
            if (
                caller_deadline is not None
                and isinstance(completion, dict)
                and isinstance((failure := completion.get("failure")), dict)
                and failure.get("reason") == "deadline_exceeded"
            ):
                raise _CallerDeadlineExceeded("caller deadline expired before provider dispatch")
            failure = (
                completion.get("failure")
                if isinstance(completion, dict) else None)
            reason = (
                str(failure.get("reason") or "")
                if isinstance(failure, dict) else "")
            if not isinstance(completion, dict) or reason == "empty_generation":
                logger.error(
                    "AI action '%s' received empty LLM content", action)
                return _ai_failure(
                    action, "AI action returned no usable response",
                    "empty_response")
            logger.error(
                "AI action '%s' LLM completion failed (%s)",
                action, reason or "generation_failed")
            return _ai_failure(
                action, "AI text completion failed", "provider_error")

        content = completion.get("content")
        if not isinstance(content, str) or not content.strip():
            logger.error(
                "AI action '%s' received empty LLM content", action)
            return _ai_failure(
                action, "AI action returned no usable response",
                "empty_response")

        provider_value = completion.get("provider")
        provider = (
            provider_value.strip()
            if isinstance(provider_value, str) and provider_value.strip()
            else None)
        model_value = completion.get("model")
        model = (
            model_value.strip()
            if isinstance(model_value, str) and model_value.strip()
            else None)
        return {
            "action": action,
            "status": "success",
            # Preserve the legacy AI result location for existing callers.
            "result": content,
            "agent_response": content,
            "provider": provider,
            "model": model,
        }

    async def _execute_webhook_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Webhook service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Webhook {action} executed",
            "status": "success"
        }

    async def _execute_mcp_action(self, action: str, params: dict, connection_id: Optional[str] = None, step: Optional[dict] = None) -> dict:
        """Execute MCP server actions"""
        try:
            from integrations.mcp_service import mcp_service

            server_id = params.get("server_id")
            tool_name = params.get("tool_name", action)
            tool_args = params.get("arguments", {})

            if not server_id:
                raise ValueError("server_id is required for MCP actions")

            # P9: dispatch through call_tool — the shared sandbox-gated entry
            # point — NOT the raw execute_tool helper. execute_tool skips the
            # P9 sandbox gate + P2 capability gate that every other dispatch
            # path (agent loop, fleet, business agents) goes through, so a
            # workflow MCP node executed tools with no blast-radius bound.
            # The workflow's run identity is threaded through so the gate can
            # issue a policy (KillRun, caps, FS scope all key on run_id).
            context: Dict[str, Any] = {}
            if step:
                context["run_id"] = step.get("execution_id")
                context["execution_id"] = step.get("execution_id")
                context["workspace_id"] = step.get("workspace_id")
                context["tenant_id"] = step.get("tenant_id")
                context["agent_id"] = params.get("agent_id") or step.get("agent_id")
                tier = params.get("tier") or step.get("tier")
                if tier:
                    context["tier_at_issuance"] = tier
                # The run-level canonical profile + any per-step durable HITL
                # clearance are server-only objects. Copying the opaque
                # clearance is what lets an approved step reach the effect
                # without re-pausing, while a different step still re-gates.
                try:
                    from core.autonomy_policy import (
                        NEVER_CLEARANCE_CONTEXT_KEY,
                        current_never_autonomous_clearance,
                    )
                    from core.task_classification import (
                        TASK_PROFILE_CONTEXT_KEY,
                        current_task_profile,
                    )

                    profile = current_task_profile()
                    if profile is not None:
                        context[TASK_PROFILE_CONTEXT_KEY] = profile
                        context.setdefault(
                            "user_id", getattr(profile, "owner_user_id", None))
                    clearance = (
                        step.get(NEVER_CLEARANCE_CONTEXT_KEY)
                        or current_never_autonomous_clearance())
                    if clearance is not None:
                        context[NEVER_CLEARANCE_CONTEXT_KEY] = clearance
                except Exception as _profile_err:  # noqa: BLE001
                    logger.debug(
                        "workflow task profile attach skipped: %s",
                        _profile_err)

            # Execute MCP tool through the gated entry point
            result = await mcp_service.call_tool(tool_name, tool_args, context)

            return {
                "action": action,
                "server_id": server_id,
                "tool_name": tool_name,
                "result": result,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Workflow MCP action '{action}' failed: {e}")
            return {
                "action": action,
                "error": "MCP action failed",
                "status": "error"
            }

    async def _execute_main_agent_action(
        self,
        action: str,
        params: dict,
        connection_id: Optional[str] = None,
        step: Optional[dict] = None,
        caller_deadline: Optional[float] = None,
    ) -> dict:
        """Execute a main_agent text action inside the run's trusted scope.

        The workflow step carries the run's trusted scope. The requested
        agent is resolved only inside that workspace/tenant; an absent
        agent id, an unresolved caller scope, a requested MCP server, a
        provider failure, or an empty response is a failed action — never
        a successful one wrapped around an inner failure.
        """
        agent_action = params.get("agent_action", action)
        mcp_servers = params.get("mcp_servers")
        input_data = params.get("input_data", {})
        requested_agent_id = str(params.get("agent_id") or "").strip()
        workspace_id = str((step or {}).get("workspace_id") or "").strip()
        tenant_id = str((step or {}).get("tenant_id") or "").strip()

        # Direct callers must prove the run's scope. Do NOT invent a
        # permissive "default" scope for an unresolved workflow caller.
        if not workspace_id or not tenant_id:
            return {
                "action": action,
                "error": "main_agent step is missing its execution scope",
                "status": "error"
            }
        if not requested_agent_id:
            return {
                "action": action,
                "error": "agent_id is required for main_agent steps",
                "status": "error"
            }
        # The MCP catalog is global and carries no authenticated tenant
        # filtering, so this workflow action must not consult it. Refuse an
        # explicit request rather than silently ignoring it.
        if mcp_servers:
            return {
                "action": action,
                "error": "mcp_servers are not available to main_agent workflow steps",
                "status": "error"
            }

        try:
            # Prepare agent context with the trusted execution scope. No MCP
            # connections or tool definitions are admitted on this path.
            agent_context = {
                "action": agent_action,
                "agent_id": requested_agent_id,
                "workspace_id": workspace_id,
                "tenant_id": tenant_id,
                "input_data": input_data,
                "mcp_connections": {},
            }
            # Only a timed step adds the provider boundary, preserving the
            # existing agent context shape for every untimed call.
            if caller_deadline is not None:
                agent_context["caller_deadline"] = caller_deadline

            result = await self._execute_agent_with_mcp(agent_context)

            if not isinstance(result, dict) or result.get("success") is not True:
                # The existing workflow envelope: a status that is not
                # "success" makes _execute_step raise instead of marking the
                # step COMPLETED. Keep the inner diagnostics for callers.
                error_message = (
                    result.get("error")
                    if isinstance(result, dict) else None
                ) or "main_agent execution failed"
                return {
                    "action": action,
                    "agent_action": agent_action,
                    "mcp_servers_used": list(agent_context["mcp_connections"].keys()),
                    "result": result,
                    "status": "error",
                    "error": str(error_message)
                }

            return {
                "action": action,
                "agent_action": agent_action,
                "mcp_servers_used": list(agent_context["mcp_connections"].keys()),
                "result": result,
                "status": "success"
            }

        except _CallerDeadlineExceeded:
            # Pre-dispatch caller-deadline refusal: the engine boundary owns
            # translating it into the typed configured-step timeout.
            raise
        except Exception as e:
            # Log the detail; return only a concise, safe message.
            logger.error(f"main_agent action '{action}' failed: {e}")
            return {
                "action": action,
                "error": "main_agent execution failed",
                "status": "error"
            }

    async def _execute_agent_with_mcp(self, agent_context: dict) -> dict:
        """
        Execute a main_agent text action through the scoped LLM service.

        The requested agent must be an enabled AgentRegistry row for the
        workflow's exact (id, workspace, tenant); that single scoped query
        is the admission gate. The existing LLMService.generate_completion
        facade owns provider routing and reports explicit
        success/content/provider/model. A provider failure, an unresolved
        LLM scope or an empty/unusable response is a failure result, never a
        fabricated success. This text-only path advertises and executes no
        tools.
        """
        try:
            action = agent_context.get("action", "unknown")
            input_data = agent_context.get("input_data", {})
            mcp_connections = agent_context.get("mcp_connections", {})
            agent_id = str(agent_context.get("agent_id") or "").strip()
            workspace_id = str(
                agent_context.get("workspace_id") or "").strip()
            tenant_id = str(agent_context.get("tenant_id") or "").strip()
            caller_deadline = agent_context.get("caller_deadline")

            if not workspace_id or not tenant_id:
                return {
                    "success": False,
                    "failure_reason": "scope_unavailable",
                    "error": "main_agent execution scope is unavailable"
                }
            if not agent_id:
                return {
                    "success": False,
                    "failure_reason": "agent_required",
                    "error": "agent_id is required for main_agent execution"
                }

            from core.llm_service import get_llm_service
            from core.models import AgentRegistry
            from core.database import get_db_session

            # One exact, scoped admission query: the row must exist for the
            # requested id in this workspace AND tenant, and must be enabled.
            with get_db_session() as db:
                agent = (
                    db.query(AgentRegistry)
                    .filter(
                        AgentRegistry.id == agent_id,
                        AgentRegistry.workspace_id == workspace_id,
                        AgentRegistry.tenant_id == tenant_id,
                        AgentRegistry.enabled.is_(True),
                    )
                    .first()
                )
                if agent is None:
                    logger.error(
                        "Agent %s is not enabled in the workflow scope",
                        agent_id)
                    return {
                        "success": False,
                        "failure_reason": "agent_not_found",
                        "error": (
                            "requested agent is not available in this "
                            "workflow scope")
                    }

            # No tools are advertised: this workflow action is text-only.
            tool_definitions = []

            prompt = f"""You are executing action: {action}

Input data:
{input_data if isinstance(input_data, str) else str(input_data)}

Return your response in a clear, structured format."""

            # Dispatch through the existing LLM service facade with the SAME
            # trusted workspace and tenant that scoped the agent resolution.
            # generate_completion owns provider routing and reports an
            # explicit success/content/provider/model result; the BYOK
            # handler's raw chat_completion shape is not part of this
            # workflow contract.
            completion_kwargs: Dict[str, Any] = {
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "workspace_id": workspace_id,
                "tenant_id": tenant_id,
                "agent_id": agent_id,
            }
            # Only a timed workflow step opts in; an unset deadline preserves
            # the existing generate_completion call exactly.
            if caller_deadline is not None:
                completion_kwargs["caller_deadline"] = caller_deadline

            try:
                with get_db_session() as db:
                    llm_service = get_llm_service(
                        workspace_id=workspace_id,
                        tenant_id=tenant_id,
                        db=db)
                    completion = await llm_service.generate_completion(
                        **completion_kwargs)
            except _CallerDeadlineExceeded:
                # The provider was never dispatched. Surface the boundary
                # exception unchanged so the engine can translate it into the
                # configured step's typed timeout and message.
                raise
            except Exception as llm_error:
                # Never turn a provider failure into a made-up success.
                logger.error(
                    "LLM execution failed for agent %s: %s",
                    agent_id, llm_error)
                return {
                    "success": False,
                    "failure_reason": "provider_error",
                    "execution_method": "main_agent_with_mcp",
                    "agent_id": agent_id,
                    "provider": None,
                    "model": None,
                    "tool_definitions": tool_definitions,
                    "tools_available": 0,
                    "mcp_connections": len(mcp_connections),
                    "error": "main_agent LLM execution failed"
                }

            if not isinstance(completion, dict):
                logger.error(
                    "LLM returned an unusable response for agent %s",
                    agent_id)
                return {
                    "success": False,
                    "failure_reason": "empty_response",
                    "execution_method": "main_agent_with_mcp",
                    "agent_id": agent_id,
                    "provider": None,
                    "model": None,
                    "tool_definitions": tool_definitions,
                    "tools_available": 0,
                    "mcp_connections": len(mcp_connections),
                    "error": "main_agent returned no usable response"
                }

            content = completion.get("content")
            provider_value = completion.get("provider")
            provider = (
                provider_value.strip()
                if isinstance(provider_value, str) and provider_value.strip()
                else None)
            model_value = completion.get("model")
            model = (
                model_value.strip()
                if isinstance(model_value, str) and model_value.strip()
                else None)

            if completion.get("success") is not True:
                if (
                    caller_deadline is not None
                    and isinstance(completion, dict)
                    and isinstance((failure := completion.get("failure")), dict)
                    and failure.get("reason") == "deadline_exceeded"
                ):
                    raise _CallerDeadlineExceeded("caller deadline expired before provider dispatch")
                failure = completion.get("failure")
                failure = failure if isinstance(failure, dict) else {}
                failure_reason = str(failure.get("reason") or "")
                if completion.get("unresolved_scope"):
                    logger.error(
                        "LLM scope is unresolved for agent %s", agent_id)
                    return {
                        "success": False,
                        "failure_reason": "llm_scope_unresolved",
                        "execution_method": "main_agent_with_mcp",
                        "agent_id": agent_id,
                        "provider": provider,
                        "model": model,
                        "tool_definitions": tool_definitions,
                        "tools_available": 0,
                        "mcp_connections": len(mcp_connections),
                        "error": "main_agent LLM scope is unresolved"
                    }
                if failure_reason == "empty_generation":
                    logger.error(
                        "LLM returned empty content for agent %s", agent_id)
                    return {
                        "success": False,
                        "failure_reason": "empty_response",
                        "execution_method": "main_agent_with_mcp",
                        "agent_id": agent_id,
                        "provider": provider,
                        "model": model,
                        "tool_definitions": tool_definitions,
                        "tools_available": 0,
                        "mcp_connections": len(mcp_connections),
                        "error": "main_agent returned no usable response"
                    }
                logger.error(
                    "LLM completion failed for agent %s (%s)",
                    agent_id, failure_reason or "generation_failed")
                return {
                    "success": False,
                    "failure_reason": "provider_error",
                    "execution_method": "main_agent_with_mcp",
                    "agent_id": agent_id,
                    "provider": provider,
                    "model": model,
                    "tool_definitions": tool_definitions,
                    "tools_available": 0,
                    "mcp_connections": len(mcp_connections),
                    "error": "main_agent LLM execution failed"
                }

            if not isinstance(content, str) or not content.strip():
                logger.error(
                    "LLM returned empty content for agent %s", agent_id)
                return {
                    "success": False,
                    "failure_reason": "empty_response",
                    "execution_method": "main_agent_with_mcp",
                    "agent_id": agent_id,
                    "provider": provider,
                    "model": model,
                    "tool_definitions": tool_definitions,
                    "tools_available": 0,
                    "mcp_connections": len(mcp_connections),
                    "error": "main_agent returned no usable response"
                }

            return {
                "success": True,
                "agent_response": content,
                "content": content,
                # No MCP tool was executed by this text-only path; empty is
                # truthful, and the definitions stay as metadata.
                "tool_calls": [],
                "tool_definitions": tool_definitions,
                "tools_available": 0,
                "mcp_connections": len(mcp_connections),
                "mcp_connection_metadata": mcp_connections,
                "input_processed": input_data,
                "execution_method": "main_agent_with_mcp",
                "agent_id": agent_id,
                "provider": provider,
                "model": model,
                "usage": (
                    completion.get("usage")
                    if isinstance(completion.get("usage"), dict) else {}),
                "action": action
            }

        except _CallerDeadlineExceeded:
            # Never wrap the caller-deadline refusal as an agent failure: the
            # engine boundary must see it to preserve the typed step timeout.
            raise
        except Exception as e:
            logger.error(f"MCP agent execution failed: {e}")
            raise AgentExecutionError(
                agent_id=agent_context.get("agent_id", "unknown"),
                reason=str(e),
                cause=e
            )

    async def _execute_email_automation_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute email automation service actions (Follow-ups, etc.)"""
        try:
            from core.email_followup_engine import followup_engine
            
            if action == "detect_followups":
                # In a real app, we'd fetch actual emails here. 
                # For now, we'll use mock data like the analytics endpoint did.
                from datetime import datetime, timedelta
                now = datetime.now()
                mock_sent = [
                    {"id": "e1", "to": "investor@venture.com", "subject": "Quarterly Update", "sent_at": (now - timedelta(days=5)).isoformat(), "thread_id": "thread_1", "snippet": "Hey, checking in on the report..."},
                ]
                mock_received = []
                
                days_threshold = params.get("days_threshold", 3)
                followup_engine.days_threshold = days_threshold
                
                candidates = await followup_engine.detect_missing_replies(mock_sent, mock_received)
                return {
                    "status": "success",
                    "candidates": [c.dict() for c in candidates],
                    "count": len(candidates)
                }
            
            elif action == "draft_nudge":
                subject = params.get("subject", "Following up")
                # Simple AI-like drafting
                draft = f"Hi there,\n\nI'm just following up on my previous email regarding \"{subject}\". I assume you've been busy, but I wanted to make sure this stayed on your radar. Looking forward to hearing from you!\n\nBest, [Your Name]"
                return {
                    "status": "success",
                    "draft": draft
                }
            
            else:
                raise ValueError(f"Unknown email_automation action: {action}")
                
        except Exception as e:
            logger.error(f"Email automation failed: {e}")
            return {"status": "error", "error": str(e)}

    async def _execute_workflow_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute a sub-workflow as a step."""
        try:
            workflow_id = params.get("workflow_id")
            if not workflow_id:
                raise ValueError("workflow_id is required for workflow actions")

            input_data = params.get("input_data", {})
            max_depth = params.get("max_depth", 10)  # Prevent infinite recursion
            timeout = params.get("timeout", 300)  # Default 5 minute timeout

            # Check recursion depth (track via context or simple counter)
            # For now, implement simple depth check
            # In a full implementation, we would track via execution context

            # Load workflow definition
            workflow = self._load_workflow_by_id(workflow_id)
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")

            # Execute sub-workflow using the same engine
            # This creates a new execution ID and runs asynchronously
            execution_id = await self.start_workflow(workflow, input_data)

            # Monitor the execution status with timeout
            start_time = datetime.now()
            poll_interval = 0.5  # Poll every 500ms

            while True:
                # Check timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    logger.warning(f"Sub-workflow {workflow_id} execution {execution_id} timed out after {timeout}s")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "status": "timeout",
                        "error": f"Sub-workflow execution timed out after {timeout} seconds"
                    }

                # Get current execution state
                state = await self.state_manager.get_execution_state(execution_id)

                if not state:
                    logger.error(f"Sub-workflow execution {execution_id} not found in state manager")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "status": "error",
                        "error": "Execution state not found"
                    }

                status = state.get("status")

                # Check if execution is complete
                if status in ["COMPLETED", "SUCCESS"]:
                    logger.info(f"Sub-workflow {workflow_id} execution {execution_id} completed successfully")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "result": state.get("outputs", {}),
                        "status": "success"
                    }
                elif status in ["FAILED", "ERROR"]:
                    error_msg = state.get("error", "Unknown error")
                    logger.error(f"Sub-workflow {workflow_id} execution {execution_id} failed: {error_msg}")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "status": "error",
                        "error": error_msg
                    }
                elif status in ["CANCELLED"]:
                    logger.warning(f"Sub-workflow {workflow_id} execution {execution_id} was cancelled")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "status": "cancelled",
                        "error": "Sub-workflow was cancelled"
                    }
                elif status in ["PAUSED"]:
                    logger.warning(f"Sub-workflow {workflow_id} execution {execution_id} is paused, waiting for input")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "status": "paused",
                        "error": "Sub-workflow is paused waiting for input"
                    }
                elif status in ["RUNNING", "PENDING"]:
                    # Still running, wait and poll again
                    await asyncio.sleep(poll_interval)
                    continue
                else:
                    logger.warning(f"Sub-workflow {workflow_id} execution {execution_id} has unknown status: {status}")
                    await asyncio.sleep(poll_interval)
                    continue

        except Exception as e:
            logger.error(f"Error executing sub-workflow: {e}")
            return {
                "action": action,
                "error": str(e),
                "status": "error"
            }

    def _load_workflow_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load workflow definition by ID from workflows.json."""
        import json
        import os

        # Calculate path to workflows.json (same as in workflow_endpoints.py)
        workflows_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "workflows.json"
        )

        if not os.path.exists(workflows_file):
            return None

        try:
            with open(workflows_file, 'r') as f:
                workflows = json.load(f)

            # Find workflow by ID
            for workflow in workflows:
                if workflow.get('id') == workflow_id:
                    return workflow
            return None
        except Exception as e:
            logger.error(f"Error loading workflow {workflow_id}: {e}")
            return None

    async def _execute_outlook_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Outlook service actions"""
        try:
            from integrations.outlook_service import OutlookService
            service = OutlookService()
            
            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None
            user_id = params.get("user_id", "default") # Or derive from context
            
            # Helper to call service method
            async def call_service(method_name, **kwargs):
                method = getattr(service, method_name)
                # Filter kwargs to match method signature to be safe, or rely on **kwargs in service
                # Our service methods are explicit, so we should map params carefully or rely on compatible keys
                # Simplified invocation:
                if token:
                    kwargs["token"] = token
                result = await method(**kwargs)
                return result

            result = None
            if action == "send_email":
                result = await call_service("send_email", 
                    user_id=user_id,
                    to_recipients=params.get("to_recipients"),
                    subject=params.get("subject"),
                    body=params.get("body"),
                    cc_recipients=params.get("cc_recipients"),
                    bcc_recipients=params.get("bcc_recipients")
                )
            elif action == "create_event":
                 result = await call_service("create_calendar_event",
                    user_id=user_id,
                    subject=params.get("subject"),
                    body=params.get("body"),
                    start=params.get("start"),
                    end=params.get("end"),
                    location=params.get("location"),
                    attendees=params.get("attendees")
                 )
            elif action == "get_emails":
                result = await call_service("get_user_emails",
                    user_id=user_id,
                    folder=params.get("folder", "inbox"),
                    max_results=params.get("max_results", 10),
                    query=params.get("query")
                )
            else:
                # Generic fallback if action matches method name
                if hasattr(service, action):
                     # Add user_id if not in params
                     if "user_id" not in params:
                         params["user_id"] = user_id
                     result = await call_service(action, **params)
                else:
                    raise ValueError(f"Unknown Outlook action: {action}")
            
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Outlook execution failed: {e}")
            raise e

    async def _execute_jira_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Jira service actions"""
        try:
            from integrations.jira_service import JiraService
            service = JiraService()
            
            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None
            
            if hasattr(service, action):
                method = getattr(service, action)
                if token:
                    params["token"] = token
                result = method(**params)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Jira action: {action}")
        except Exception as e:
            logger.error(f"Jira execution failed: {e}")
            raise e

    async def _execute_trello_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Trello service actions"""
        try:
            from integrations.trello_service import TrelloService
            service = TrelloService()
            
            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None # In Trello, this might be 'token'
            
            # TrelloService methods explicitly take 'token'
            if hasattr(service, action):
                method = getattr(service, action)
                if token:
                    params["token"] = token
                result = method(**params)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Trello action: {action}")
        except Exception as e:
            logger.error(f"Trello execution failed: {e}")
            raise e

    async def _execute_stripe_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Stripe service actions"""
        if not HAS_STRIPE or StripeService is None:
            raise AtomValidationError("Stripe service not available")
        try:
            service = StripeService()
            
            token_data = token_storage.get_token(connection_id) if connection_id else None
            access_token = token_data.get("access_token") if token_data else None
            
            if not access_token:
                # StripeService methods require access_token
                # Log warning and skip execution if token not available
                logger.warning(
                    f"Stripe action '{action}' requires access_token but none found "
                    f"for connection_id: {connection_id}. Skipping execution."
                )
                return {
                    "status": "error",
                    "error": "Stripe access token not found",
                    "connection_id": connection_id,
                    "action": action
                }

            if hasattr(service, action):
                method = getattr(service, action)
                if access_token:
                    params["access_token"] = access_token
                
                # Strip connection_id from params if it leaked in? No, params is separate.
                result = method(**params)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Stripe action: {action}")
        except Exception as e:
            logger.error(f"Stripe execution failed: {e}")
            raise e

    async def _execute_shopify_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Shopify service actions"""
        try:
            from integrations.shopify_service import ShopifyService
            service = ShopifyService()
            
            token_data = token_storage.get_token(connection_id) if connection_id else None
            access_token = token_data.get("access_token") if token_data else None
            shop = token_data.get("shop_url") or token_data.get("shop") if token_data else None
            
            if access_token:
                params["access_token"] = access_token
            if shop:
                params["shop"] = shop

            if hasattr(service, action):
                method = getattr(service, action)
                # Allow async methods
                if iscoroutinefunction(method):
                    result = await method(**params)
                else:
                    result = method(**params)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Shopify action: {action}")
        except Exception as e:
            logger.error(f"Shopify execution failed: {e}")
            raise e

    async def _execute_zoho_crm_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Zoho CRM service actions"""
        try:
            from integrations.zoho_crm_service import ZohoCRMService
            service = ZohoCRMService()

            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None

            if hasattr(service, action):
                method = getattr(service, action)
                if token:
                    params["token"] = token
                if iscoroutinefunction(method):
                    result = await method(**params)
                else:
                    result = method(**params)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Zoho CRM action: {action}")
        except Exception as e:
            logger.error(f"Zoho CRM execution failed: {e}")
            raise e

    async def _execute_zoho_books_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Zoho Books service actions"""
        try:
            from integrations.zoho_books_service import ZohoBooksService
            service = ZohoBooksService()

            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None
            organization_id = token_data.get("organization_id") or token_data.get("org_id") if token_data else None

            if hasattr(service, action):
                method = getattr(service, action)
                # Check method signature or just pass likely kwargs
                kwargs = params.copy()
                if token:
                    kwargs["access_token"] = token # ZohoBooksService uses 'access_token' param name
                if organization_id and "organization_id" not in kwargs:
                    kwargs["organization_id"] = organization_id

                if iscoroutinefunction(method):
                    result = await method(**kwargs)
                else:
                    result = method(**kwargs)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Zoho Books action: {action}")
        except Exception as e:
            logger.error(f"Zoho Books execution failed: {e}")
            raise e

    async def _execute_zoho_inventory_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Zoho Inventory service actions"""
        try:
            from integrations.zoho_inventory_service import ZohoInventoryService
            service = ZohoInventoryService()

            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None
            organization_id = token_data.get("organization_id") or token_data.get("org_id") if token_data else None

            if hasattr(service, action):
                method = getattr(service, action)
                kwargs = params.copy()
                if token:
                    kwargs["token"] = token
                if organization_id and "organization_id" not in kwargs:
                    kwargs["organization_id"] = organization_id

                if iscoroutinefunction(method):
                    result = await method(**kwargs)
                else:
                    result = method(**kwargs)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Zoho Inventory action: {action}")
        except Exception as e:
            logger.error(f"Zoho Inventory execution failed: {e}")
            raise e

    async def _execute_generic_action(self, service_name: str, action_name: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """
        Universal Generic Executor for Catalog Integrations.
        Fetches metadata from IntegrationCatalog and executes HTTP request.
        """
        from core.cache import cache
        
        logger.info(f"Attempting generic execution for {service_name}.{action_name}")
        
        # 0. Try Cache
        cache_key = f"catalog:{service_name}"
        catalog_data = cache.get(cache_key)
        
        if not catalog_data:
            # 1. Fetch metadata from DB
            with get_db_session() as db:
                try:
                    catalog_item = db.query(IntegrationCatalog).filter(IntegrationCatalog.id == service_name).first()
                    if not catalog_item:
                        raise ValueError(f"Service '{service_name}' not found in Integration Catalog")

                    # Serialize for cache
                    catalog_data = {
                        "id": catalog_item.id,
                        "actions": catalog_item.actions
                    }
                    # Cache for 1 hour
                    cache.set(cache_key, catalog_data, ttl=3600)
                except Exception as e:
                    logger.error(f"Failed to fetch catalog item: {e}")
                    raise
            
        # 2. Find specific action definition
        actions = catalog_data.get("actions") or []
        action_def = next((a for a in actions if a.get("name") == action_name), None)
            
        if not action_def:
            raise ValueError(f"Action '{action_name}' not found in catalog for service '{service_name}'")
            
        # 3. Construct HTTP Request
        url = action_def.get("url") or action_def.get("path")
        method = action_def.get("method", "GET").upper()
            
        if not url:
            raise ValueError(f"No URL/path defined for action '{action_name}'")
            
        # Parameter Substitution (Path variables)
        # e.g. /users/{id}
        path_params = re.findall(r'\{([^}]+)\}', url)
        for param in path_params:
            if param in params:
                url = url.replace(f"{{{param}}}", str(params.pop(param)))
            else:
                raise ValueError(f"Missing path parameter: {param}")
            
        # Prepare Query & Body
        # Simple heuristic: GET/DELETE uses query, POST/PUT/PATCH uses body
        query_params = {}
        json_body = {}
            
        if method in ["GET", "DELETE"]:
            query_params = params
        else:
            json_body = params
            
        # 4. Authentication
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Atom-Workflow-Engine/1.0"
        }
            
        if connection_id:
            token_data = token_storage.get_token(connection_id)
            if token_data:
                # Generic Bearer Auth Support
                if "access_token" in token_data:
                    headers["Authorization"] = f"Bearer {token_data['access_token']}"
            
        # 5. Execute Request
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_body if method not in ["GET", "DELETE"] else None,
                headers=headers,
                timeout=30.0
            )
                
            response.raise_for_status()
            return response.json()

    async def _execute_goal_management_action(
        self,
        action: str,
        params: Dict[str, Any],
        connection_id: Optional[str] = None,
        step: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute goal management actions.

        Goal creation is a durable write: it goes through the verified goal
        write service under the exact actor/scope frozen into the execution
        inputs, with one stable operation id per execution step so a retry
        replays the receipt instead of creating another goal. The created
        goal's own domain status (e.g. ``ACTIVE``) is nested under ``goal``
        and must not be mistaken for the executor envelope status.
        """
        from core.goal_engine import goal_engine

        if action == "create_goal":
            title = params.get("title")
            target_date_str = params.get("target_date")

            if not title or not target_date_str:
                raise ValueError("Missing title or target_date for create_goal")

            from datetime import datetime
            target_date = datetime.fromisoformat(
                str(target_date_str).replace('Z', '+00:00'))

            # Only the single authoritative step context is trusted. Never use
            # params, template metadata, definition scope, or a legacy step
            # alias: the dispatcher overwrites this marker with the real
            # execution/step ids and the caller identity frozen at start.
            step_data = step if isinstance(step, dict) else {}
            identity = _normalize_step_identity_context(
                step_data.get(EXECUTION_IDENTITY_KEY))
            workspace_id = identity.get("workspace_id")
            tenant_id = identity.get("tenant_id")
            user_id = identity.get("user_id")
            execution_id = identity.get("execution_id")
            step_id = identity.get("step_id")
            if not all((workspace_id, tenant_id, user_id,
                        execution_id, step_id)):
                raise ValueError(
                    "Missing caller-frozen execution identity for "
                    "create_goal (tenant/workspace/user/execution/step)")

            # Generate and validate the subtask plan BEFORE any write. An
            # invalid plan is surfaced to the caller and no goal is created.
            description = str(params.get("description") or "")
            goal_text = " ".join(
                part for part in (str(title), description) if part)
            from core.goals.htn_planner import HTNPlanner
            plan = HTNPlanner().decompose(goal_text)
            if not isinstance(plan, dict) or not plan.get("subtasks"):
                raise ValueError("Goal subtask plan is empty")
            if plan.get("cycles"):
                raise ValueError(
                    "Goal subtask plan is invalid: dependency cycle "
                    f"{plan['cycles']}")

            # Stable per-execution-step operation id. The write service owns
            # the receipt/replay semantics; a retry of this exact step must
            # never create a second goal.
            operation_id = _stable_operation_id(
                "goal:create", execution_id, step_id)

            from core.goals import goal_write_service as writes
            from types import SimpleNamespace

            # The service re-reads and claims the authoritative User row from
            # this id, so the actor is exactly the run's frozen caller.
            actor = SimpleNamespace(id=user_id)
            with get_db_session() as db:
                result = writes.create_goal(
                    db,
                    actor=actor,
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    title=str(title),
                    description=description,
                    target_date=target_date,
                    source="workflow",
                    operation_id=operation_id,
                )

            writer_status = str(result.get("status") or "")
            if writer_status not in ("verified", "already_applied"):
                detail = (
                    result.get("error")
                    or result.get("message")
                    or "Goal creation failed")
                raise ValueError(
                    f"Goal creation {writer_status or 'failed'}: {detail}")

            goal = result.get("data") or {}
            subtasks = plan.get("subtasks") or []
            return {
                "status": "success",
                "goal": goal,
                "plan": plan,
                "subtasks": subtasks,
                "sub_tasks": subtasks,
                "execution_groups": plan.get("execution_groups") or [],
                "method": plan.get("method"),
                # Planned work only. Nothing in this step executed the
                # subtasks, so do not report them as executed tasks.
                "executed_tasks": [],
                "tasks_executed": False,
            }

        elif action == "check_escalations":
            escalations = await goal_engine.check_for_escalations()
            return {"escalations": escalations}
            
        elif action == "update_subtask":
            goal_id = params.get("goal_id")
            sub_task_id = params.get("sub_task_id")
            status = params.get("status")
            
            if goal_id not in goal_engine.goals:
                raise ValueError(f"Goal {goal_id} not found")
                
            goal = goal_engine.goals[goal_id]
            for st in goal.sub_tasks:
                if st.id == sub_task_id:
                    st.status = status
                    break
            
            await goal_engine.update_goal_progress(goal_id)
            return goal.dict()
            
        else:
            raise ValueError(f"Unknown goal_management action: {action}")

    async def _execute_workflow_notification_action(
        self,
        action: str,
        params: Dict[str, Any],
        connection_id: Optional[str] = None,
        step: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist the workflow's in-app notification for its frozen caller.

        ``notify_caller`` writes through the read-only
        ``NotificationService.send_workflow_notification`` boundary. The
        recipient and scope come only from the dispatcher-installed step
        context; ``params`` supplies only the definition's title/message and
        can never choose a recipient. No email or other outbound delivery is
        performed, and the persisted notification id is returned only after
        the service verifies the committed row.
        """
        if action != "notify_caller":
            raise ValueError(
                f"Unknown workflow_notification action: {action}")

        step_data = step if isinstance(step, dict) else {}
        identity = _normalize_step_identity_context(
            step_data.get(EXECUTION_IDENTITY_KEY))
        workspace_id = identity.get("workspace_id")
        tenant_id = identity.get("tenant_id")
        user_id = identity.get("user_id")
        execution_id = identity.get("execution_id")
        step_id = identity.get("step_id")
        missing = not all((workspace_id, tenant_id, user_id,
                           execution_id, step_id))
        if missing:
            return {
                "action": action,
                "status": "error",
                "notification_id": None,
                "error": (
                    "Missing caller-frozen execution identity for "
                    "notify_caller (tenant/workspace/user/execution/step)"),
            }

        definition = params if isinstance(params, dict) else {}
        title = definition.get("title")
        message = definition.get("message")
        if not isinstance(title, str) or not title.strip():
            return {
                "action": action,
                "status": "error",
                "notification_id": None,
                "error": "notify_caller requires a nonblank 'title' parameter",
            }
        if not isinstance(message, str) or not message.strip():
            return {
                "action": action,
                "status": "error",
                "notification_id": None,
                "error": "notify_caller requires a nonblank 'message' parameter",
            }

        # Stable per-execution-step operation id: a retry/lost ack replays the
        # same persisted row instead of delivering a second notification.
        operation_id = _stable_operation_id(
            "workflow_notification:notify_caller", execution_id, step_id)

        from core.notification_service import NotificationService

        try:
            result = await NotificationService().send_workflow_notification(
                user_id=user_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                operation_id=operation_id,
                title=title,
                message=message,
            )
        except Exception as exc:  # noqa: BLE001 — report, never fake success
            logger.error(
                "Workflow notification step failed (execution=%s step=%s): %s",
                execution_id, step_id, exc)
            return {
                "action": action,
                "status": "error",
                "notification_id": None,
                "error": "Workflow notification failed",
            }

        if (
            not isinstance(result, dict)
            or result.get("success") is not True
            or not result.get("notification_id")
        ):
            detail = (
                result.get("error")
                if isinstance(result, dict) else None) or "notification_failed"
            logger.error(
                "Workflow notification step was not persisted "
                "(execution=%s step=%s): %s",
                execution_id, step_id, detail)
            return {
                "action": action,
                "status": "error",
                "error": f"Workflow notification failed: {detail}",
            }

        return {
            "action": action,
            "status": "success",
            "notification_id": result["notification_id"],
            "created": bool(result.get("created", False)),
            # This boundary is in-app only; keep the service's explicit
            # "nothing was emailed" contract visible to the workflow.
            "emailed": False,
        }

    async def run_workflow_with_arbor_refinement(
        self,
        tenant_id: str,
        workflow: Dict[str, Any],
        input_data: Dict[str, Any],
        tier: str = "solo",
        previous_tree_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow under the Arbor Hypothesis Tree Refinement (HTR) framework.

        Tracks the workflow execution structure, creates a WorkflowHypothesisNode to measure
        parallelizability, throughput, cost-savings potential, and latency. Failed workflow
        runs are pruned from the optimization tree (TEST_FAILED/LATENCY_REGRESSION), while the
        optimal configurations are recorded on SUCCESS nodes and persisted to the database.
        """
        from core.hypothesis_tree import (
            OptimizationTree,
            WorkflowHypothesisNode,
            NodeMetrics,
            NodeStatus,
            PruningReason,
            TaskType
        )
        from core.database import get_db_session
        from core.hypothesis_tree_endpoints import _persist_tree

        tree_id = str(uuid.uuid4())
        tree = OptimizationTree(
            id=tree_id,
            task_description=f"Workflow refinement: {workflow.get('name', 'Untitled')}",
            tier=tier,
            task_type=TaskType.WORKFLOW
        )

        # Inherit negative constraints from previous runs if provided
        if previous_tree_id:
            with get_db_session() as db:
                from core.auto_dev.models import HypothesisTreeRecord
                prev_record = db.query(HypothesisTreeRecord).filter(HypothesisTreeRecord.id == previous_tree_id).first()
                if prev_record and prev_record.negative_constraints:
                    tree.negative_constraints = list(prev_record.negative_constraints)

        logger.info(f"[Arbor/Workflow] Initialized Workflow OptimizationTree={tree_id} tier={tier}")

        # Normalize graph-format workflows (nodes/connections) to steps BEFORE
        # measuring parallelizability — start_workflow does the same conversion
        # later, so measuring the raw nodes dict would always report ratio 0.
        if "steps" not in workflow and "nodes" in workflow:
            workflow["steps"] = self._convert_nodes_to_steps(workflow)

        # Measure parallelizable nodes vs sequential nodes
        steps = workflow.get("steps", [])
        total_steps = len(steps)
        parallelizable_count = 0
        
        # Simple heuristic to identify parallel steps based on lack of direct step requirements
        dependency_map = {}
        for s in steps:
            reqs = s.get("config", {}).get("requires", [])
            dependency_map[s["id"]] = reqs
            if not reqs:
                parallelizable_count += 1
                
        parallel_ratio = (parallelizable_count / max(1, total_steps))

        node = WorkflowHypothesisNode(
            depth=0,
            hypothesis=f"Execute {workflow.get('name', 'Workflow')} layout",
            description=f"Workflow Execution with parallelizable ratio: {parallel_ratio:.2f}",
            parallelizable_ratio=parallel_ratio,
            cost_optimization_potential=0.15 if parallel_ratio > 0.3 else 0.05,
            estimated_throughput_rps=10.0 * (1.0 + parallel_ratio),
            estimated_latency_ms=250.0 * total_steps,
            metrics=NodeMetrics(tokens_used=0),
            session_id=tenant_id
        )

        tree.add_node(node)

        # Execute the workflow
        try:
            start_time = datetime.now()
            execution_id = await self.start_workflow(workflow, input_data)
            
            # Simple polling wait for completeness
            success = False
            error_msg = None
            for _ in range(600):  # max 5 mins
                state = await self.state_manager.get_execution_state(execution_id)
                if not state:
                    break
                status = state.get("status")
                if status in ["COMPLETED", "SUCCESS"]:
                    success = True
                    break
                elif status in ["FAILED", "ERROR"]:
                    error_msg = state.get("error", "Failed")
                    break
                await asyncio.sleep(0.5)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000.0
            node.metrics.execution_time_ms = duration_ms

            if success:
                node.status = NodeStatus.SUCCESS
                node.promise_score = node.calculate_promise_score()
                tree.winning_path = tree.get_path_to_root(node.id)
                tree.completed_at = datetime.now(timezone.utc)
                logger.info(f"[Arbor/Workflow] Workflow execution SUCCESS. Node promise={node.promise_score:.2f}")
            else:
                tree.prune_branch(node.id, PruningReason.TEST_FAILED)
                tree.completed_at = datetime.now(timezone.utc)
                logger.warning(f"[Arbor/Workflow] Workflow execution FAILED: {error_msg}")

            # Persist the tree to DB
            with get_db_session() as db:
                _persist_tree(db, tree_id, tree, tenant_id, "workflow")

            return {
                "tree_id": tree_id,
                "node_id": node.id,
                "execution_id": execution_id,
                "success": success,
                "duration_ms": duration_ms,
                "parallel_ratio": parallel_ratio,
                "promise_score": node.promise_score if success else 0.0,
                "tree_stats": tree.get_domain_statistics()
            }
        except Exception as e:
            logger.error(f"[Arbor/Workflow] HTR execution wrapper failed: {e}")
            tree.prune_branch(node.id, PruningReason.MANUAL)
            tree.completed_at = datetime.now(timezone.utc)
            with get_db_session() as db:
                try:
                    _persist_tree(db, tree_id, tree, tenant_id, "workflow")
                except Exception:
                    pass
            raise e


class MissingInputError(Exception):
    def __init__(self, message: str, missing_var: str):
        super().__init__(message)
        self.missing_var = missing_var

class SchemaValidationError(Exception):
    def __init__(self, message: str, schema_type: str, errors: list = None):
        super().__init__(message)
        self.schema_type = schema_type  # "input" or "output"
        self.errors = errors or []

class StepTimeoutError(Exception):
    #: Ordinary integration timeouts keep the shared retry helper's default
    #: retry behavior.
    retryable = True

    def __init__(self, message: str, step_id: str, timeout: float):
        super().__init__(message)
        self.step_id = step_id
        self.timeout = timeout
        self.retryable = True


class ModelStepTimeoutError(StepTimeoutError):
    """A workflow deadline expired while awaiting a text-model dispatch.

    ``asyncio.wait_for`` stops awaiting the provider task at the step deadline,
    but the underlying provider worker may still be running. Automatically
    repeating the same step could overlap or duplicate that work, so this
    typed timeout opts out of the shared retry helper while retaining the
    original configured timeout.
    """

    retryable = False

    def __init__(self, message: str, step_id: str, timeout: float):
        super().__init__(message, step_id=step_id, timeout=timeout)
        self.retryable = False

# Global instance
_workflow_engine = None
_workflow_engine_lock = __import__('threading').Lock()
def get_workflow_engine() -> WorkflowEngine:
    global _workflow_engine
    if _workflow_engine is None:
        with _workflow_engine_lock:
            if _workflow_engine is None:
                _workflow_engine = WorkflowEngine()
    return _workflow_engine

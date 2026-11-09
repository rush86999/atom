"""
Canvas Tool Backend Helper

Provides helper functions for agents to present charts and visualizations
to users via the Canvas system.

Now includes governance integration with:
- Agent execution tracking for all presentations
- Governance checks before presenting
- Complete audit trail via canvas_audit table
- Performance-optimized caching

Refactored to use standardized decorators and service factory.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.canvas_type_registry import canvas_type_registry
from core.chat_session_context import audit_agent_id, audit_session_id
from core.feature_flags import FeatureFlags
from core.models import AgentExecution, CanvasAudit
from core.presentation_material import material_sha256, presentation_material

from core.structured_logger import get_logger
from core.websockets import manager as ws_manager

logger = get_logger(__name__)


def _user_broadcast_channels(user_id: Any, session_id: Any) -> List[str]:
    """Channels a canvas event must reach (2026-09-09 consolidation).

    EVERY canvas present/update fans out to BOTH the plain user channel
    and the session-scoped variant: the main chat pane's socket auto-joins
    ``user:{user_id}`` server-side (api/websocket_routes.py), while the
    ``/canvas/{id}`` page additionally subscribes the session channel (the
    session binding is that page's own state). Session-scoped-only
    delivery left the chat pane blind; user-only delivery left the canvas
    page blind (pre-fix). Mirrors the fan-out chat_orchestrator already
    does for document presents."""
    channels = [f"user:{user_id or 'default'}"]
    if session_id and user_id:
        channels.append(f"user:{user_id}:session:{session_id}")
    return channels



class CanvasPresentationReceiptError(RuntimeError):
    """Persistence may have happened; this identity must never be redispatched."""
    def __init__(self, audit_id: str, canvas_id: str, committed: bool):
        super().__init__("Canvas presentation persistence could not be confirmed")
        self.audit_id = audit_id
        self.canvas_id = canvas_id
        self.committed = committed

    def as_result(self):
        return {
            "success": False,
            "status": "committed_unverified" if self.committed else "effect_unknown",
            "canvas_id": self.canvas_id,
            "audit_id": self.audit_id,
            "replay": "do_not_repeat",
            "error": str(self),
            "verification": {"status": "unavailable", "effect": "committed" if self.committed else "unknown"},
        }


async def _presentation_failure_result(result, execution_id=None):
    # Storage uncertainty is not a semantic model failure or completed work.
    if execution_id:
        try:
            from core.database import get_db_session
            with get_db_session() as db:
                execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
                if execution and execution.status == "running":
                    execution.status = "failed" if result["verification"]["effect"] == "none" else "blocked"
                    execution.error_message = result["error"]
                    if execution.status == "failed":
                        execution.completed_at = datetime.now()
                    db.commit()
        except Exception as state_error:
            logger.warning("Presentation execution state unavailable", error_class=type(state_error).__name__)
    return result


async def _create_canvas_audit(
    db: Session,
    agent_id: Optional[str],
    agent_execution_id: Optional[str],
    user_id: str,
    canvas_id: Optional[str],
    session_id: Optional[str],  # Session isolation
    canvas_type: str = "generic",  # NEW: Canvas type (generic, docs, email, sheets, orchestration, terminal, coding)
    component_type: str = "component",  # NEW: Default component type
    component_name: Optional[str] = None,
    action: str = "present",
    governance_check_passed: Optional[bool] = None,
    metadata: Dict[str, Any] = None,
    tenant_id: str = "default",
    require_durable_receipt: bool = False,
    expected_tenant_id: Optional[str] = None,
    expected_workspace_id: Optional[str] = None,
) -> Optional[CanvasAudit]:
    """
    Create a canvas audit entry for tracking.

    Helper function to log all canvas actions for governance and audit trail.

    Args:
        db: Database session
        agent_id: Optional agent ID
        agent_execution_id: Optional agent execution ID
        user_id: User ID
        canvas_id: Canvas ID
        session_id: Optional session ID for isolation
        canvas_type: Canvas type (generic, docs, email, sheets, orchestration, terminal, coding)
        component_type: Component type (chart, markdown, form, rich_editor, thread_view, etc.)
        component_name: Optional component name
        action: Action (present, close, submit, update)
        governance_check_passed: Whether governance check passed
        metadata: Optional metadata dictionary

    Returns:
        CanvasAudit object or None on failure
    """
    audit = None
    audit_identity = str(uuid.uuid4())
    commit_attempted = False
    commit_confirmed = False
    try:
        metadata = dict(metadata or {})
        if require_durable_receipt:
            if not isinstance(canvas_id, str) or not canvas_id:
                return None
            from core.models import Canvas
            from tools.canvas_crud_tool import active_canvas_actor, _claim_canvas_actor
            actor = active_canvas_actor(db, user_id)
            if not actor.get("ok"):
                return None
            # Match the caller's known context to the authoritative principal;
            # only the established Personal Edition aliases are equivalent.
            for expected, actual in ((expected_tenant_id, actor.get("tenant_id")),
                                     (expected_workspace_id, actor.get("workspace_id"))):
                if expected is not None and not (isinstance(expected, str) and
                    (expected == actual or expected in ("", "default") and actual in (None, "", "default"))):
                    return None
            if not _claim_canvas_actor(db, actor):
                db.rollback()
                return None
            workspace_id = actor.get("workspace_id") or None
            if workspace_id is not None:
                from sqlalchemy import update
                from core.models import Workspace
                from tools.canvas_crud_tool import _raw_exact
                workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
                if workspace is None or workspace.status != "active":
                    db.rollback()
                    return None
                workspace_tenant = workspace.tenant_id
                actor_tenant = actor.get("tenant_id")
                if not (workspace_tenant == actor_tenant or workspace_tenant in (None, "", "default") and actor_tenant in (None, "", "default")):
                    db.rollback()
                    return None
                claim = db.execute(update(Workspace).where(
                    Workspace.id == workspace_id,
                    _raw_exact(Workspace.tenant_id, workspace_tenant),
                    Workspace.status == "active",
                ).values(updated_at=Workspace.updated_at))
                if claim.rowcount != 1:
                    db.rollback()
                    return None
            if db.query(Canvas).filter(Canvas.id == canvas_id).first() is not None:
                db.rollback()
                return None
            user_id = actor["id"]
            tenant_id = actor.get("tenant_id") or "default"
            metadata["tenant_id"] = tenant_id
            metadata["workspace_id"] = actor.get("workspace_id")
            db.add(Canvas(id=canvas_id, tenant_id=tenant_id,
                          workspace_id=actor.get("workspace_id") or None, created_by=user_id,
                          name=metadata.get("title") or component_name or canvas_type,
                          canvas_type=canvas_type, content=metadata.get("content"),
                          status="active", is_public=False))
        audit = CanvasAudit(
            id=audit_identity,
            tenant_id=tenant_id or "default",
            canvas_type=canvas_type,
            # Chat-context attribution (same as canvas_crud_tool): when the
            # action runs inside a chat turn, the audit row attributes to
            # that turn's session/agent so training episodes capture it.
            agent_id=audit_agent_id(agent_id),
            user_id=user_id,
            canvas_id=canvas_id,
            session_id=audit_session_id(session_id),
            action_type=action,
            details_json={
                **metadata,
                "canvas_type": canvas_type,
                "component_type": component_type,
                "component_name": component_name,
                "agent_execution_id": agent_execution_id,
                "governance_check_passed": governance_check_passed,
            }
        )
        db.add(audit)
        commit_attempted = True
        db.commit()
        commit_confirmed = True
        db.refresh(audit)
        return audit
    except Exception as e:
        if require_durable_receipt:
            from sqlalchemy.exc import IntegrityError
            logger.warning("Canvas presentation persistence unavailable",
                           stage="readback" if commit_confirmed else "commit" if commit_attempted else "prepare", error_class=type(e).__name__)
            if commit_attempted and audit is not None:
                # A refresh failure cannot undo a confirmed commit. Other
                # commit exceptions are unknown unless rollback is proven.
                if not commit_confirmed and isinstance(e, IntegrityError):
                    try:
                        db.rollback()
                    except Exception:
                        raise CanvasPresentationReceiptError(audit_identity, str(canvas_id), False) from None
                    return None
                try:
                    db.rollback()
                except Exception as cleanup_error:
                    logger.warning("Presentation transaction cleanup unavailable", error_class=type(cleanup_error).__name__)
                raise CanvasPresentationReceiptError(audit_identity, str(canvas_id), commit_confirmed) from None
            try:
                db.rollback()
            except Exception:
                raise CanvasPresentationReceiptError(audit_identity, str(canvas_id), False) from None
            return None
        logger.error(f"Failed to create canvas audit: {e}")
        return None


async def present_chart(
    user_id: str,
    chart_type: str,
    data: List[Dict[str, Any]],
    title: str = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    operation_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    **kwargs
):
    """
    Send a chart to the frontend canvas with governance integration.

    Args:
        user_id: User ID to send the chart to
        chart_type: 'line_chart', 'bar_chart', or 'pie_chart'
        data: List of dicts with chart data
        title: Chart title
        agent_id: Agent ID presenting the chart (for governance)
        session_id: Optional session ID for session isolation
        **kwargs: Additional chart options (color, etc.)
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None
    audit = None
    audit_id = None

    try:
        # Governance: Resolve agent and check permissions
        if FeatureFlags.should_enforce_governance('canvas'):
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                from core.service_factory import ServiceFactory
                governance = ServiceFactory.get_governance_service(db)

                # Resolve agent
                agent, resolution_context = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="present_chart"
                )

                # Check governance
                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="present_chart"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked chart presentation: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted to present chart: {governance_check['reason']}"
                        }

                    # Create agent execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Present {chart_type}: {title or 'Untitled'}",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

                    logger.info(f"Agent execution {agent_execution.id} for chart presentation")

        canvas_id = str(uuid.uuid4())
        # Build and commit the audit BEFORE broadcasting. Audit persistence is
        # independent of optional governance enforcement: a presentation with
        # no durable audit must never reach the user.
        material = presentation_material(
            "canvas.present_chart",
            {"chart_type": chart_type, "data": data})
        with get_db_session() as db:
            audit = await _create_canvas_audit(
                db=db,
                require_durable_receipt=True,
                expected_tenant_id=tenant_id,
                expected_workspace_id=workspace_id,
                agent_id=agent.id if agent else None,
                agent_execution_id=agent_execution.id if agent_execution else None,
                user_id=user_id,
                canvas_id=canvas_id,
                session_id=session_id,
                canvas_type=chart_type,  # Preserve the native renderer on readback
                component_type="chart",
                component_name=chart_type,
                action="present",
                governance_check_passed=governance_check["allowed"] if governance_check else None,
                tenant_id=tenant_id or "default",
                metadata={
                    "title": title,
                    "data_points": len(data),
                    "chart_type": chart_type,
                    "session_id": session_id,
                    "data": data,
                    "content": data,
                    "chart_config": {"type": chart_type, "title": title},
                    "material": material,
                    "material_sha256": material_sha256(material),
                    "operation_id": operation_id,
                    "workspace_id": workspace_id,
                    "tenant_id": tenant_id or "default",
                }
            )
            audit_id = str(audit.id) if audit is not None else None
            if audit is not None:
                user_id = str(audit.user_id)

        if audit is None:
            logger.error("Chart presentation refused: canvas audit was not persisted")
            return await _presentation_failure_result({
                "success": False,
                "status": "not_applied",
                "canvas_id": canvas_id,
                "verification": {"status": "refused", "effect": "none"},
                "error": "Canvas audit could not be persisted; chart was not presented"
            }, agent_execution.id if agent_execution else None)

        # Broadcast only after the audit row is durably committed.
        user_channels = _user_broadcast_channels(user_id, session_id)

        for _user_channel in user_channels:
            await ws_manager.broadcast(
                _user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": f"{chart_type}",
                    "canvas_id": canvas_id,
                    "session_id": session_id,
                    "revision_audit_id": audit_id,
                    "data": {"data": data, "title": title, **kwargs}
                }
            }
        )

        # Mark execution as completed only after the audited presentation.
        if agent_execution:
            with get_db_session() as db:
                execution = db.query(AgentExecution).filter(
                    AgentExecution.id == agent_execution.id
                ).first()
                if execution:
                    execution.status = "completed"
                    execution.output_summary = f"Presented {chart_type} with {len(data)} data points"
                    execution.completed_at = datetime.now()
                    db.commit()

                    # Record outcome for confidence
                    from core.service_factory import ServiceFactory
                    governance_service = ServiceFactory.get_governance_service(db)
                    await governance_service.record_outcome(agent.id, success=True)

        logger.info(f"Presented {chart_type} to user {user_id}" + (f" (agent: {agent.name})" if agent else ""))
        return {
            "success": True,
            "chart_type": chart_type,
            "canvas_id": canvas_id,
            "audit_id": audit_id,
            "agent_id": agent.id if agent else None
        }

    except CanvasPresentationReceiptError as error:
        return await _presentation_failure_result(error.as_result(), agent_execution.id if agent_execution else None)

    except Exception as e:
        if audit_id and audit is not None:
            logger.warning("Committed presentation follow-through unavailable", error_class=type(e).__name__)
            return await _presentation_failure_result(
                CanvasPresentationReceiptError(audit_id, canvas_id, True).as_result(),
                agent_execution.id if agent_execution else None)
        logger.error(f"Failed to present chart: {e}")

        # Mark execution as failed
        if agent_execution and FeatureFlags.should_enforce_governance('canvas'):
            try:
                with get_db_session() as db:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "failed"
                        execution.error_message = str(e)
                        execution.completed_at = datetime.now()
                        db.commit()

                        if agent:
                            from core.service_factory import ServiceFactory
                            governance_service = ServiceFactory.get_governance_service(db)
                            await governance_service.record_outcome(agent.id, success=False)
            except Exception as inner_e:
                logger.error(f"Failed to record execution failure: {inner_e}")

        return {"success": False, "error": str(e)}


async def present_status_panel(
    user_id: str,
    items: List[Dict[str, Any]],
    title: str = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Send a status panel to the frontend canvas with governance integration.

    Args:
        user_id: User ID to send the panel to
        items: List of status items with 'label', 'value', and optional 'trend'
        title: Panel title
        agent_id: Agent ID presenting the panel (for governance)
        session_id: Optional session ID for session isolation
    """
    from core.database import get_db_session

    agent = None
    governance_check = None

    try:
        # Governance: Check agent permissions
        if FeatureFlags.should_enforce_governance('canvas'):
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                from core.service_factory import ServiceFactory
                governance = ServiceFactory.get_governance_service(db)

                agent, _ = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="present_chart"
                )

                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="present_chart"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked status panel: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted: {governance_check['reason']}"
                        }

        # Present the panel
        user_channels = _user_broadcast_channels(user_id, session_id)

        for _user_channel in user_channels:
            await ws_manager.broadcast(
                _user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": "status_panel",
                    "session_id": session_id,
                    "data": {"items": items, "title": title}
                }
            }
        )

        logger.info(f"Presented status panel to user {user_id}" + (f" (agent: {agent.name})" if agent else ""))
        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to present status panel: {e}")
        return {"success": False, "error": str(e)}


async def present_markdown(
    user_id: str,
    content: str,
    title: str = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    operation_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
):
    """
    Send markdown content to the frontend canvas with governance integration.

    Args:
        user_id: User ID to send the content to
        content: Markdown formatted content
        title: Content title
        agent_id: Agent ID presenting the content (for governance)
        session_id: Optional session ID for session isolation
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None
    audit = None
    audit_id = None

    try:
        # Governance: Resolve agent and check permissions
        if FeatureFlags.should_enforce_governance('canvas'):
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                from core.service_factory import ServiceFactory
                governance = ServiceFactory.get_governance_service(db)

                agent, _ = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="present_markdown"
                )

                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="present_markdown"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked markdown: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted: {governance_check['reason']}"
                        }

                    # Create execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Present markdown: {title or 'Untitled'}",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

        canvas_id = str(uuid.uuid4())
        # Build and commit the audit BEFORE broadcasting. Audit persistence is
        # independent of optional governance enforcement: a presentation with
        # no durable audit must never reach the user.
        material = presentation_material(
            "canvas.present_markdown", {"content": content})
        with get_db_session() as db:
            audit = await _create_canvas_audit(
                db=db,
                require_durable_receipt=True,
                expected_tenant_id=tenant_id,
                expected_workspace_id=workspace_id,
                agent_id=agent.id if agent else None,
                agent_execution_id=agent_execution.id if agent_execution else None,
                user_id=user_id,
                canvas_id=canvas_id,
                session_id=session_id,  # NEW: Session isolation
                canvas_type="markdown",
                component_type="markdown",
                component_name=None,
                action="present",
                governance_check_passed=governance_check["allowed"] if governance_check else None,
                tenant_id=tenant_id or "default",
                metadata={
                    "title": title,
                    "content": str(content),
                    "content_length": len(content),
                    "content_sha256": hashlib.sha256(
                        str(content).encode("utf-8")).hexdigest(),
                    "material": material,
                    "material_sha256": material_sha256(material),
                    "operation_id": operation_id,
                    "workspace_id": workspace_id,
                    "tenant_id": tenant_id or "default",
                    "session_id": session_id,
                }
            )
            audit_id = str(audit.id) if audit is not None else None
            if audit is not None:
                user_id = str(audit.user_id)

        if audit is None:
            logger.error("Markdown presentation refused: canvas audit was not persisted")
            return await _presentation_failure_result({
                "success": False,
                "status": "not_applied",
                "canvas_id": canvas_id,
                "verification": {"status": "refused", "effect": "none"},
                "error": "Canvas audit could not be persisted; markdown was not presented"
            }, agent_execution.id if agent_execution else None)

        # Present the markdown only after the audit row is durably committed.
        user_channels = _user_broadcast_channels(user_id, session_id)

        for _user_channel in user_channels:
            await ws_manager.broadcast(
                _user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "component": "markdown",
                    "canvas_id": canvas_id,
                    "session_id": session_id,
                    "revision_audit_id": audit_id,
                    "data": {"content": content, "title": title}
                }
            }
        )

        # Mark execution as completed only after the audited presentation.
        if agent_execution:
            with get_db_session() as db:
                execution = db.query(AgentExecution).filter(
                    AgentExecution.id == agent_execution.id
                ).first()
                if execution:
                    execution.status = "completed"
                    execution.output_summary = f"Presented markdown ({len(content)} chars)"
                    execution.completed_at = datetime.now()
                    db.commit()

                    from core.service_factory import ServiceFactory
                    governance_service = ServiceFactory.get_governance_service(db)
                    await governance_service.record_outcome(agent.id, success=True)

        logger.info(f"Presented markdown content to user {user_id}" + (f" (agent: {agent.name})" if agent else ""))
        return {
            "success": True,
            "canvas_id": canvas_id,
            "audit_id": audit_id,
            "agent_id": agent.id if agent else None
        }

    except CanvasPresentationReceiptError as error:
        return await _presentation_failure_result(error.as_result(), agent_execution.id if agent_execution else None)

    except Exception as e:
        if audit_id and audit is not None:
            logger.warning("Committed presentation follow-through unavailable", error_class=type(e).__name__)
            return await _presentation_failure_result(
                CanvasPresentationReceiptError(audit_id, canvas_id, True).as_result(),
                agent_execution.id if agent_execution else None)
        logger.error(f"Failed to present markdown: {e}")
        return {"success": False, "error": str(e)}


def _form_operation_ids(actor_id: str, operation_id: str):
    """Deterministic, collision-safe Canvas/audit ids for one operation.

    The tuple is JSON-encoded so opaque identifiers cannot run together and
    collide. Actor scope is part of the key: the same actor + exact operation
    replays one surface, while a different actor is a different operation.
    """
    def _uuid(kind: str) -> str:
        name = json.dumps(
            [
                "atom:canvas:present_form",
                str(kind),
                str(actor_id),
                str(operation_id),
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return str(uuid.uuid5(uuid.NAMESPACE_URL, name))

    return _uuid("canvas"), _uuid("audit")


def _form_replay_conflict(
    canvas,
    audit,
    *,
    actor_id: str,
    tenant_id: Any,
    workspace_id: Any,
    title: Any,
    material,  # type: ignore[no-untyped-def]
    material_digest: str,
    agent_id: Optional[str],
    session_id: Optional[str],
    operation_id: str,
) -> Optional[str]:
    """Return why an existing actor/operation surface is not this replay."""
    if canvas is None or audit is None:
        return "form operation identity is incomplete"

    details = audit.details_json or {}
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except (TypeError, ValueError):
            details = {}
    if not isinstance(details, dict):
        details = {}

    stored_agent = str(audit.agent_id or "").strip()
    expected_agent = str(agent_id or "").strip()
    stored_session = "" if audit.session_id is None else str(audit.session_id)
    expected_session = "" if session_id is None else str(session_id)
    stored_material = details.get("material")
    stored_material_digest = (
        material_sha256(stored_material)
        if isinstance(stored_material, dict) else "")

    if (str(audit.action_type or "") != "present"
            or str(canvas.canvas_type or "").lower() != "form"
            or str(audit.canvas_type or "").lower() != "form"):
        return "operation already names a different canvas action"
    if str(audit.canvas_id or "") != str(canvas.id):
        return "audit is bound to a different canvas"
    if (str(audit.user_id or "") != actor_id
            or str(canvas.created_by or "") != actor_id):
        return "operation already belongs to a different actor"
    if (canvas.tenant_id != tenant_id or audit.tenant_id != tenant_id
            or details.get("tenant_id") != tenant_id
            or canvas.workspace_id != workspace_id
            or details.get("workspace_id") != workspace_id):
        return "operation already belongs to a different scope"
    if str(details.get("operation_id") or "") != operation_id:
        return "audit carries a different operation identity"
    if (str(canvas.name or "") != str(title or "")
            or details.get("title") != title):
        return "operation already names a different title"
    if (not stored_material_digest
            or stored_material_digest != str(material_digest)):
        return "operation already names different material"
    if stored_agent != expected_agent:
        return "operation already names a different agent"
    if stored_session != expected_session:
        return "operation already belongs to a different session"
    return None


async def present_form(
    user_id: str,
    form_schema: Dict[str, Any],
    title: str = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    operation_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None
):
    """
    Present a form to the user with governance integration.

    The form is a durable Canvas surface: the authoritative actor-scoped
    Canvas row and its present audit are committed BEFORE the event is
    broadcast, and success is returned only after an independent read-back
    confirms the exact schema/title/scope. Chart/markdown presentation is
    unchanged and remains audit-only.

    Args:
        user_id: User ID to present the form to
        form_schema: Form schema with fields, validation rules
        title: Form title
        agent_id: Agent ID presenting the form (for governance)
        session_id: Optional session ID for session isolation

    Returns:
        Dict with success status and canvas_id for tracking submissions
    """
    from core.database import get_db_session
    from core.models import Canvas
    from tools.canvas_crud_tool import _claim_canvas_actor, active_canvas_actor, resolve_submit_agent

    agent = None
    agent_execution = None
    governance_check = None
    commit_attempted = False
    committed = False
    already_applied = False
    replayed_execution_id = None

    schema = form_schema if form_schema is not None else {}
    display_title = title if title is not None else "Untitled form"
    material = presentation_material(
        "canvas.present_form",
        {"form_schema": schema, "title": display_title})
    if material is None:
        return {"success": False, "error": "form_schema is required"}

    canvas_id = str(uuid.uuid4())
    audit_id = str(uuid.uuid4())
    resolved_operation_id = (
        str(operation_id).strip() if operation_id is not None else ""
    ) or f"canvas-present-form:{uuid.uuid4().hex}"
    material_digest = material_sha256(material)

    try:
        # Persist the authoritative surface and its present audit in ONE
        # transaction, regardless of the governance flag. `tenant_id` and
        # `workspace_id` arguments are retained only for caller
        # compatibility: the CURRENT active User row is the scope authority.
        with get_db_session() as db:
            actor = active_canvas_actor(db, user_id)
            if not actor.get("ok"):
                return {
                    "success": False,
                    "error": (
                        actor.get("error")
                        or "Acting user is not active"),
                }
            actor_id = str(actor.get("id") or "")
            actor_tenant_id = actor.get("tenant_id")
            actor_workspace_id = actor.get("workspace_id")
            if not str(actor_tenant_id or "").strip():
                return {
                    "success": False,
                    "error": "Acting user has no tenant scope",
                }

            canvas_id, audit_id = _form_operation_ids(actor_id, resolved_operation_id)
            existing_canvas = db.get(Canvas, canvas_id)
            existing_audit = db.get(CanvasAudit, audit_id)
            if existing_canvas is not None or existing_audit is not None:
                conflict = _form_replay_conflict(
                    existing_canvas, existing_audit, actor_id=actor_id,
                    tenant_id=actor_tenant_id, workspace_id=actor_workspace_id,
                    title=display_title, material=material,
                    material_digest=material_digest, agent_id=agent_id,
                    session_id=session_id, operation_id=resolved_operation_id)
                if conflict:
                    return {"success": False, "status": "conflict", "error": conflict,
                            "canvas_id": canvas_id, "audit_id": audit_id,
                            "operation_id": resolved_operation_id,
                            "verification": {"status": "refused", "effect": "none"}}
                already_applied = True
                replayed_execution_id = (existing_audit.details_json or {}).get("agent_execution_id")
            if agent_id:
                bound = resolve_submit_agent(db, actor, agent_id, None, canvas_id=canvas_id)
                if not bound.get("ok"):
                    db.rollback()
                    return {"success": False, "error": "Form agent scope could not be authorized"}
                agent = bound["agent"]

            # Governance: resolve the agent and check permissions. A policy
            # that requires human approval is NOT waived by a presentation.
            if agent and FeatureFlags.should_enforce_governance('canvas'):
                from core.service_factory import ServiceFactory
                governance = ServiceFactory.get_governance_service(
                    db, workspace_id=actor_workspace_id, tenant_id=actor_tenant_id)


                if agent:
                    bound = resolve_submit_agent(db, actor, agent.id, None, canvas_id=canvas_id)
                    if not bound.get("ok"):
                        db.rollback()
                        return {"success": False, "error": "Form agent scope could not be authorized"}
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="present_form"
                    )
                    if not isinstance(governance_check, dict):
                        return {
                            "success": False,
                            "error": (
                                "Agent form presentation could not be "
                                "authorized"),
                        }
                    if (governance_check.get("allowed") is not True
                            or governance_check.get(
                                "requires_human_approval") is not False):
                        logger.warning("Governance blocked form presentation")
                        return {
                            "success": False,
                            "error": (
                                "Agent not permitted to present form: "
                                f"{governance_check.get('reason')}"),
                        }

                    if not already_applied:
                        agent_execution = AgentExecution(
                            agent_id=agent.id,
                            tenant_id=actor_tenant_id,
                            workspace_id=actor_workspace_id,
                            status="running",
                            input_summary=(
                                f"Present form: {display_title}"),
                            triggered_by="canvas"
                        )
                        db.add(agent_execution)
                        db.flush()

            if not already_applied:
                db.add(Canvas(
                    id=canvas_id,
                    tenant_id=actor_tenant_id,
                    workspace_id=actor_workspace_id,
                    created_by=actor_id,
                    name=str(display_title),
                    canvas_type="form",
                    content={"schema": schema, "title": display_title},
                    status="active",
                    last_edited_by=actor_id,
                ))
                db.add(CanvasAudit(
                    id=audit_id,
                    canvas_id=canvas_id,
                    tenant_id=actor_tenant_id,
                    session_id=session_id,
                    action_type="present",
                    canvas_type="form",
                    user_id=actor_id,
                    agent_id=agent.id if agent else None,
                    details_json={
                        "canvas_type": "form",
                        "component_type": "form",
                        "component_name": None,
                        "agent_execution_id": (
                            agent_execution.id if agent_execution else None),
                        "governance_check_passed": (
                            governance_check.get("allowed")
                            if isinstance(governance_check, dict) else None),
                        "title": display_title,
                        "field_count": (
                            len(schema.get("fields", []))
                            if isinstance(schema, dict) else 0),
                        "schema": schema,
                        "form_schema": schema,
                        "material": material,
                        "material_sha256": material_digest,
                        "operation_id": resolved_operation_id,
                        "workspace_id": actor_workspace_id,
                        "tenant_id": actor_tenant_id,
                        "session_id": session_id,
                        "actor_id": actor_id,
                    },
                ))

                if agent_execution:
                    agent_execution.status = "completed"
                    agent_execution.output_summary = (
                        f"Presented form with "
                        f"{len(schema.get('fields', []))} fields"
                        if isinstance(schema, dict) else "Presented form")
                    agent_execution.completed_at = datetime.now()

            # The actor claim is the transaction's linearization point: a
            # move/deactivation committed before this point refuses the form.
            if not _claim_canvas_actor(db, actor):
                db.rollback()
                return {
                    "success": False,
                    "error": (
                        "Acting user changed while presenting the form; "
                        "refused"),
                }

            # Re-read related authority under the actor write reservation.
            # Never let an old ORM snapshot certify an agent disabled/moved
            # after the initial resolution.
            if agent:
                with db.no_autoflush:
                    bound = resolve_submit_agent(
                        db, actor, agent.id, None, canvas_id=canvas_id, lock=True)
                    if not bound.get("ok"):
                        db.rollback()
                        return {"success": False, "error": "Form agent authority changed"}
                    if FeatureFlags.should_enforce_governance('canvas'):
                        check = governance.can_perform_action(agent_id=agent.id, action_type="present_form")
                        if (not isinstance(check, dict) or check.get("allowed") is not True
                                or check.get("requires_human_approval") is not False):
                            db.rollback()
                            return {"success": False, "error": "Form presentation requires an authorized review"}

            # Commit explicitly so a failed/unknown commit is observed here
            # (and never mistaken for a durable surface).
            commit_attempted = True
            db.commit()
            committed = True

        # The context manager has committed. Only an independent fresh-session
        # read-back of the exact Canvas + present audit can certify the form
        # surface, so an unknown/failed commit never becomes success or a
        # broadcast.
        from core.oracle import validate, oracle_verifier_enabled

        verification_ctx = {
            "canvas_id": canvas_id,
            "audit_id": audit_id,
            "_oracle_action": "canvas.present_form",
            "_oracle_expected_canvas_id": canvas_id,
            "_oracle_expected_operation_id": resolved_operation_id,
            "_oracle_expected_material": material,
            "_oracle_expected_material_sha256": material_digest,
            "_oracle_expected_actor_id": actor_id,
            "_oracle_expected_tenant_id": actor_tenant_id,
            "_oracle_expected_workspace_id": actor_workspace_id,
            "_oracle_expected_title": display_title,
        }
        oracle = (await validate("canvas.present_form", verification_ctx)
                  if oracle_verifier_enabled() else None)
        verified = bool(oracle is not None and oracle.verified)
        evidence = str(getattr(oracle, "evidence", "") or "")
        if not verified:
            logger.error("Form presentation committed but could not be verified")
            return {
                "success": False,
                "status": "committed_unverified",
                "canvas_id": canvas_id,
                "audit_id": audit_id,
                "operation_id": resolved_operation_id,
                "verification": {
                    "status": (
                        "unavailable" if oracle is None else "refuted"),
                    "effect": "committed",
                    "replay": "do_not_repeat",
                    "evidence": evidence,
                },
                "error": (
                    "Form presentation committed but its durable surface "
                    "could not be verified"),
            }

        if not already_applied:
            # Broadcast only AFTER the durable surface is verified.
            user_channels = _user_broadcast_channels(user_id, session_id)

            for _user_channel in user_channels:
                await ws_manager.broadcast(
                    _user_channel,
                {
                    "type": "canvas:update",
                    "data": {
                        "action": "present",
                        "component": "form",
                        "canvas_id": canvas_id,
                        "session_id": session_id,
                        "data": {"schema": form_schema, "title": title}
                    }
                }
            )

        logger.info(f"Presented form to user {user_id}" + (f" (agent: {agent.name})" if agent else ""))
        return {
            "success": True,
            "already_applied": already_applied,
            "canvas_id": canvas_id,
            "audit_id": audit_id,
            "operation_id": resolved_operation_id,
            "agent_execution_id": agent_execution.id if agent_execution else replayed_execution_id,
            "agent_id": agent.id if agent else None,
            "verification": {
                "status": "verified",
                "effect": "committed",
                "evidence": evidence,
            },
        }

    except Exception as e:
        # Raw DB errors may contain user data or bound parameters. Preserve
        # durable operation identities without inventing a zero-effect claim.
        logger.error(f"Form presentation failed at controlled boundary: {type(e).__name__}")
        status = "committed_unverified" if committed else "effect_unknown" if commit_attempted else "refused"
        return {
            "success": False, "status": status,
            "error": "Form presentation could not be confirmed",
            "canvas_id": canvas_id, "audit_id": audit_id,
            "operation_id": resolved_operation_id,
            "verification": {
                "status": "unavailable" if commit_attempted else "not_attempted",
                "effect": "committed" if committed else "unknown" if commit_attempted else "none",
                "replay": "do_not_repeat" if commit_attempted else "safe_to_retry",
            },
        }



async def update_canvas(
    user_id: str,
    canvas_id: str,
    updates: Dict[str, Any],
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Update existing canvas with new data without re-presenting entire component.

    Enables bidirectional canvas updates for dynamic dashboards and real-time data updates.
    Similar to OpenClaw's surfaceUpdate and dataModelUpdate commands.

    Args:
        user_id: User ID to send the update to
        canvas_id: Canvas ID to update (must exist from prior present_chart/form/markdown call)
        updates: Dictionary containing update data (e.g., {"data": [...], "title": "Updated"})
        agent_id: Agent ID performing the update (for governance)
        session_id: Optional session ID for session isolation

    Returns:
        Dict with success status and update details

    Example:
        # Update chart data
        await update_canvas(
            user_id="user-1",
            canvas_id="canvas-123",
            updates={"data": [{"x": 1, "y": 5}, {"x": 2, "y": 10}]},
            agent_id="agent-1"
        )

        # Update title
        await update_canvas(
            user_id="user-1",
            canvas_id="canvas-123",
            updates={"title": "Updated Sales Data"}
        )
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Governance: Resolve agent and check permissions
        if FeatureFlags.should_enforce_governance('canvas'):
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                from core.service_factory import ServiceFactory
                governance = ServiceFactory.get_governance_service(db)

                # Resolve agent
                agent, resolution_context = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="update_canvas"
                )

                # Check governance (INTERN+ required for updates)
                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="update_canvas"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked canvas update: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted to update canvas: {governance_check['reason']}"
                        }

                    # Create agent execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Update canvas {canvas_id}",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

                    logger.info(f"Agent execution {agent_execution.id} for canvas update")

        # Send update via WebSocket
        user_channels = _user_broadcast_channels(user_id, session_id)

        for _user_channel in user_channels:
            await ws_manager.broadcast(
                _user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "update",
                    "canvas_id": canvas_id,
                    "updates": updates
                }
            }
        )

        # Create audit entry
        if FeatureFlags.should_enforce_governance('canvas'):
            with get_db_session() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    session_id=session_id,  # NEW: Session isolation
                    component_type="canvas_update",
                    component_name=None,
                    action="update",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={
                        "update_keys": list(updates.keys()),
                        "session_id": session_id
                    }
                )

                # Mark execution as completed
                if agent_execution:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "completed"
                        execution.output_summary = f"Updated canvas {canvas_id} with {len(updates)} fields"
                        execution.completed_at = datetime.now()
                        db.commit()

                        # Record outcome for confidence
                        from core.service_factory import ServiceFactory
                        governance_service = ServiceFactory.get_governance_service(db)
                        await governance_service.record_outcome(agent.id, success=True)

        logger.info(f"Updated canvas {canvas_id} for user {user_id}" + (f" (agent: {agent.name})" if agent else ""))
        return {
            "success": True,
            "canvas_id": canvas_id,
            "updated_fields": list(updates.keys()),
            "agent_id": agent.id if agent else None,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Failed to update canvas: {e}")

        # Mark execution as failed
        if agent_execution and FeatureFlags.should_enforce_governance('canvas'):
            try:
                with get_db_session() as db:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "failed"
                        execution.error_message = str(e)
                        execution.completed_at = datetime.now()
                        db.commit()

                        if agent:
                            from core.service_factory import ServiceFactory
                            governance_service = ServiceFactory.get_governance_service(db)
                            await governance_service.record_outcome(agent.id, success=False)
            except Exception as inner_e:
                logger.error(f"Failed to record execution failure: {inner_e}")

        return {"success": False, "error": str(e)}


async def present_to_canvas(
    db: Session,
    user_id: str,
    canvas_type: str,
    content: Dict[str, Any],
    title: str = None,
    agent_id: Optional[str] = None,
    agent_execution_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Generic wrapper for presenting content to canvas.

    Routes to the appropriate specialized canvas presentation function based on canvas_type.
    This provides a unified interface for the proposal service and other components.

    Args:
        db: Database session (for audit purposes, may not be used by all canvas types)
        user_id: User ID to present content to
        canvas_type: Type of canvas (chart, form, markdown, status_panel, docs, email, sheets, etc.)
        content: Content dict (structure varies by canvas_type)
        title: Content title
        agent_id: Optional agent ID for governance
        agent_execution_id: Optional agent execution ID for tracking
        session_id: Optional session ID for session isolation

    Returns:
        Dict with success status and canvas_id

    Canvas Types and Content Structure:
        - chart: {"chart_type": "line_chart", "data": [...]}
        - form: {"fields": [...], "validation": {...}}
        - markdown: {"content": "markdown text"}
        - status_panel: {"items": [...]}
        - docs, email, sheets, orchestration, terminal, coding: Specialized canvas data
    """
    try:
        # Route to appropriate specialized function
        if canvas_type == "chart":
            # Extract chart-specific parameters
            chart_type = content.get("chart_type", "line_chart")
            data = content.get("data", [])
            return await present_chart(
                user_id=user_id,
                chart_type=chart_type,
                data=data,
                title=title,
                agent_id=agent_id,
                session_id=session_id
            )

        elif canvas_type == "form":
            # Extract form-specific parameters
            form_schema = content
            return await present_form(
                user_id=user_id,
                form_schema=form_schema,
                title=title,
                agent_id=agent_id,
                session_id=session_id
            )

        elif canvas_type == "markdown":
            # Extract markdown-specific parameters
            markdown_content = content.get("content", "")
            return await present_markdown(
                user_id=user_id,
                content=markdown_content,
                title=title,
                agent_id=agent_id,
                session_id=session_id
            )

        elif canvas_type == "status_panel":
            # Extract status panel-specific parameters
            items = content.get("items", [])
            return await present_status_panel(
                user_id=user_id,
                items=items,
                title=title,
                agent_id=agent_id,
                session_id=session_id
            )

        elif canvas_type in ["docs", "email", "sheets", "orchestration", "terminal", "coding"]:
            # Use specialized canvas for domain-specific types
            component_type = content.get("component_type", "generic")
            data = content
            return await present_specialized_canvas(
                user_id=user_id,
                canvas_type=canvas_type,
                component_type=component_type,
                data=data,
                title=title,
                agent_id=agent_id,
                session_id=session_id
            )

        else:
            logger.warning(f"Unknown canvas type: {canvas_type}")
            return {
                "success": False,
                "error": f"Unknown canvas type: {canvas_type}. Supported types: chart, form, markdown, status_panel, docs, email, sheets, orchestration, terminal, coding"
            }

    except Exception as e:
        logger.error(f"Failed to present to canvas: {e}")
        return {"success": False, "error": str(e)}


async def close_canvas(user_id: str, session_id: Optional[str] = None):
    """
    Close the canvas for a user.

    Args:
        user_id: User ID to close the canvas for
        session_id: Optional session ID for session isolation
    """
    try:
        user_channels = _user_broadcast_channels(user_id, session_id)

        for _user_channel in user_channels:
            await ws_manager.broadcast(
                _user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "close"
                }
            }
        )

        logger.info(f"Closed canvas for user {user_id}" + (f" (session: {session_id})" if session_id else ""))
        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to close canvas: {e}")
        return {"success": False, "error": str(e)}


async def canvas_execute_javascript(
    user_id: str,
    canvas_id: str,
    javascript: str,
    agent_id: str,  # Required - must be AUTONOMOUS
    session_id: Optional[str] = None,
    timeout_ms: int = 5000
):
    """
    Execute JavaScript in a canvas context (AUTONOMOUS agents only).

    WARNING: This function requires AUTONOMOUS maturity level due to security risks.
    JavaScript execution can manipulate the DOM, access browser APIs, and perform
    arbitrary client-side actions.

    Args:
        user_id: User ID to execute JavaScript for
        canvas_id: Canvas ID to execute JavaScript in
        javascript: JavaScript code to execute
        agent_id: Agent ID performing the execution (must be AUTONOMOUS)
        session_id: Optional session ID for session isolation
        timeout_ms: Execution timeout in milliseconds (default: 5000)

    Returns:
        Dict with success status and execution details

    Example:
        # Update document title
        await canvas_execute_javascript(
            user_id="user-1",
            canvas_id="canvas-123",
            javascript="document.title = 'Updated Title';",
            agent_id="agent-autonomous-1"
        )

        # Manipulate DOM
        await canvas_execute_javascript(
            user_id="user-1",
            canvas_id="canvas-123",
            javascript="document.getElementById('chart').style.height = '500px';",
            agent_id="agent-autonomous-1"
        )
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None

    try:
        # Security: Require agent_id (no anonymous execution)
        if not agent_id:
            logger.warning("JavaScript execution blocked: No agent_id provided")
            return {
                "success": False,
                "error": "JavaScript execution requires an explicit agent_id (AUTONOMOUS only)"
            }

        # Governance: Resolve agent and check permissions
        if FeatureFlags.should_enforce_governance('canvas'):
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                from core.service_factory import ServiceFactory
                governance = ServiceFactory.get_governance_service(db)

                # Resolve agent
                agent, resolution_context = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type="canvas_execute_javascript"
                )

                # Check governance (AUTONOMOUS required)
                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type="canvas_execute_javascript"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked JavaScript execution: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted to execute JavaScript: {governance_check['reason']}"
                        }

                    # Verify agent is AUTONOMOUS (double-check for security)
                    from core.models import AgentStatus
                    if (agent.status or "").upper() != AgentStatus.AUTONOMOUS.name:
                        logger.warning(f"JavaScript execution blocked: Agent {agent.name} is {agent.status}, not AUTONOMOUS")
                        return {
                            "success": False,
                            "error": f"JavaScript execution requires AUTONOMOUS maturity level. Agent {agent.name} is {agent.status}"
                        }

                    # Create agent execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Execute JavaScript in canvas {canvas_id}: {javascript[:100]}...",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

                    logger.info(f"Agent execution {agent_execution.id} for canvas JavaScript execution")

        # Basic JavaScript validation (security)
        if not javascript or not javascript.strip():
            return {
                "success": False,
                "error": "JavaScript code cannot be empty"
            }

        # Check for obviously dangerous patterns (basic security)
        # BUG FIX: the case-insensitive form (`javascript_lower`) was computed
        # but never used, so mixed-case variants ("EVAL(", "eVaL(") bypassed
        # the filter entirely. Matching is now truly case-insensitive.
        # BUG FIX: bracket-notation access ("document['cookie']",
        # "sessionStorage['password']") and the classic exfiltration /
        # script-injection vectors (fetch(), document.write, dynamic <script>
        # creation, innerHTML assignment) were missing from the blocklist,
        # letting the payloads enumerated in INTG-13 through.
        dangerous_patterns = [
            "eval(", "function(", "settimeout(", "setinterval(",
            "document.cookie", "localstorage.", "sessionstorage.",
            "window.location", "window.top", "window.parent",
            # Node/server-side APIs — never legitimate in browser canvas JS
            "process.exit", "require(",
            # Network exfiltration
            "fetch(", "xmlhttprequest", "sendbeacon",
            # DOM script injection / exfil sinks
            "document.write", "document.writeln",
            "createelement('script'", 'createelement("script"',
            ".innerhtml", "<script",
            # Bracket-notation access to sensitive globals
            "document[", "window[", "localstorage[", "sessionstorage[",
        ]

        javascript_lower = javascript.lower()
        for pattern in dangerous_patterns:
            idx = javascript_lower.find(pattern)
            if idx != -1:
                # Report the matched substring in its original casing so the
                # rejection message quotes what the agent actually wrote.
                matched = javascript[idx:idx + len(pattern)]
                logger.warning(f"JavaScript execution blocked: Dangerous pattern '{matched}' detected")
                # BUG FIX: blocked attempts were never audited — the security
                # event only reached the application log, leaving no CanvasAudit
                # trail (and a dangling "running" AgentExecution) for forensic
                # review. Record the violation and fail the execution.
                if FeatureFlags.should_enforce_governance('canvas'):
                    with get_db_session() as db:
                        await _create_canvas_audit(
                            db=db,
                            agent_id=agent.id if agent else None,
                            agent_execution_id=agent_execution.id if agent_execution else None,
                            user_id=user_id,
                            canvas_id=canvas_id,
                            session_id=session_id,
                            component_type="javascript_execution",
                            component_name=None,
                            action="execute",
                            governance_check_passed=False,
                            metadata={
                                "javascript": javascript,
                                "javascript_length": len(javascript),
                                "blocked": True,
                                "security_violation": matched,
                                "session_id": session_id,
                            },
                        )
                        if agent_execution:
                            execution = db.query(AgentExecution).filter(
                                AgentExecution.id == agent_execution.id
                            ).first()
                            if execution:
                                execution.status = "failed"
                                execution.error_message = (
                                    f"JavaScript contains potentially dangerous pattern: {matched}"
                                )
                                execution.completed_at = datetime.now()
                                db.commit()
                return {
                    "success": False,
                    "error": f"JavaScript contains potentially dangerous pattern: {matched}. Use of {matched} is not allowed."
                }

        # Send JavaScript execution request via WebSocket
        user_channels = _user_broadcast_channels(user_id, session_id)

        for _user_channel in user_channels:
            await ws_manager.broadcast(
                _user_channel,
            {
                "type": "canvas:execute",
                "data": {
                    "action": "execute_javascript",
                    "canvas_id": canvas_id,
                    "javascript": javascript,
                    "timeout_ms": timeout_ms
                }
            }
        )

        # Create audit entry with JavaScript content
        if FeatureFlags.should_enforce_governance('canvas'):
            with get_db_session() as db:
                await _create_canvas_audit(
                    db=db,
                    agent_id=agent.id if agent else None,
                    agent_execution_id=agent_execution.id if agent_execution else None,
                    user_id=user_id,
                    canvas_id=canvas_id,
                    session_id=session_id,
                    component_type="javascript_execution",
                    component_name=None,
                    action="execute",
                    governance_check_passed=governance_check["allowed"] if governance_check else None,
                    metadata={
                        "javascript": javascript,
                        "javascript_length": len(javascript),
                        "timeout_ms": timeout_ms,
                        "session_id": session_id
                    }
                )

                # Mark execution as completed
                if agent_execution:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "completed"
                        execution.output_summary = f"Executed JavaScript in canvas {canvas_id} ({len(javascript)} chars)"
                        execution.completed_at = datetime.now()
                        db.commit()

                        # Record outcome for confidence
                        from core.service_factory import ServiceFactory
                        governance_service = ServiceFactory.get_governance_service(db)
                        await governance_service.record_outcome(agent.id, success=True)

        logger.info(
            f"Executed JavaScript in canvas {canvas_id} for user {user_id} "
            f"({len(javascript)} chars)" + (f" (agent: {agent.name})" if agent else "")
        )
        return {
            "success": True,
            "canvas_id": canvas_id,
            "javascript_length": len(javascript),
            "agent_id": agent.id if agent else None,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Failed to execute JavaScript: {e}")

        # Mark execution as failed
        if agent_execution and FeatureFlags.should_enforce_governance('canvas'):
            try:
                with get_db_session() as db:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "failed"
                        execution.error_message = str(e)
                        execution.completed_at = datetime.now()
                        db.commit()

                        if agent:
                            from core.service_factory import ServiceFactory
                            governance_service = ServiceFactory.get_governance_service(db)
                            await governance_service.record_outcome(agent.id, success=False)
            except Exception as inner_e:
                logger.error(f"Failed to record execution failure: {inner_e}")

        return {"success": False, "error": str(e)}


async def present_specialized_canvas(
    user_id: str,
    canvas_type: str,
    component_type: str,
    data: Dict[str, Any],
    title: str = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    layout: str = None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
):
    """
    Present a specialized canvas with type-specific components.

    Generic function for presenting specialized canvas types:
    - docs: Documentation with rich editor, version history, comments
    - email: Email with threads, compose, attachments
    - sheets: Spreadsheet with grid, formulas, charts
    - orchestration: Multi-app workflows with kanban, gantt, diagrams
    - terminal: Command output, file trees, process monitoring
    - coding: Code editor, diff views, PR reviews

    Args:
        user_id: User ID to present canvas to
        canvas_type: Type of canvas (docs, email, sheets, orchestration, terminal, coding)
        component_type: Component type (rich_editor, thread_view, data_grid, etc.)
        data: Component-specific data
        title: Canvas title
        agent_id: Optional agent ID for governance
        session_id: Optional session ID for isolation
        layout: Optional layout (document, inbox, sheet, board, etc.)

    Returns:
        Dict with success status, canvas_id, and details

    Example:
        # Present documentation canvas
        await present_specialized_canvas(
            user_id="user-1",
            canvas_type="docs",
            component_type="rich_editor",
            data={"content": "# API Reference\\n\\nEndpoints..."},
            title="API Documentation",
            agent_id="agent-1"
        )

        # Present spreadsheet canvas
        await present_specialized_canvas(
            user_id="user-1",
            canvas_type="sheets",
            component_type="data_grid",
            data={"cells": {"A1": "Revenue", "B1": 100000}},
            title="Financial Model",
            layout="sheet"
        )
    """
    from core.database import get_db_session

    agent = None
    agent_execution = None
    governance_check = None
    audit = None
    audit_id = None

    try:
        # Validate canvas type
        if not canvas_type_registry.validate_canvas_type(canvas_type):
            logger.warning(f"Invalid canvas type: {canvas_type}")
            return {
                "success": False,
                "error": f"Invalid canvas type: {canvas_type}. Must be one of: {list(canvas_type_registry.get_all_types().keys())}"
            }

        # Validate component for canvas type
        if not canvas_type_registry.validate_component(canvas_type, component_type):
            logger.warning(f"Component {component_type} not supported for canvas type {canvas_type}")
            return {
                "success": False,
                "error": f"Component {component_type} not supported for {canvas_type} canvas"
            }

        # Validate layout if provided
        if layout and not canvas_type_registry.validate_layout(canvas_type, layout):
            logger.warning(f"Layout {layout} not supported for canvas type {canvas_type}")
            return {
                "success": False,
                "error": f"Layout {layout} not supported for {canvas_type} canvas"
            }

        # Governance: Resolve agent and check permissions
        if FeatureFlags.should_enforce_governance('canvas'):
            with get_db_session() as db:
                resolver = AgentContextResolver(db)
                from core.service_factory import ServiceFactory
                governance = ServiceFactory.get_governance_service(db)

                # Resolve agent
                agent, resolution_context = await resolver.resolve_agent_for_request(
                    user_id=user_id,
                    requested_agent_id=agent_id,
                    action_type=f"present_{canvas_type}"
                )

                # Check governance for this canvas type
                if agent:
                    governance_check = governance.can_perform_action(
                        agent_id=agent.id,
                        action_type=f"present_{canvas_type}"
                    )

                    if not governance_check["allowed"]:
                        logger.warning(f"Governance blocked {canvas_type} canvas: {governance_check['reason']}")
                        return {
                            "success": False,
                            "error": f"Agent not permitted to present {canvas_type} canvas: {governance_check['reason']}"
                        }

                    # Check maturity requirements
                    min_maturity = canvas_type_registry.get_min_maturity(canvas_type)
                    # Map agent.status to maturity level (string comparison)
                    # Agent status values: "student", "intern", "supervised", "autonomous"
                    maturity_order = {
                        "student": 0,
                        "intern": 1,
                        "supervised": 2,
                        "autonomous": 3
                    }
                    agent_maturity = maturity_order.get(agent.status, 0)
                    required_maturity = maturity_order.get(min_maturity.value, 3)

                    if agent_maturity < required_maturity:
                        logger.warning(
                            f"Agent maturity {agent.status} below required {min_maturity.value} for {canvas_type}"
                        )
                        return {
                            "success": False,
                            "error": f"Agent maturity {agent.status} insufficient for {canvas_type} canvas (requires {min_maturity.value})"
                        }

                    # Create agent execution record
                    agent_execution = AgentExecution(
                        agent_id=agent.id,
                        workspace_id="default",
                        status="running",
                        input_summary=f"Present {canvas_type} canvas: {title or component_type}",
                        triggered_by="canvas"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

                    logger.info(f"Agent execution {agent_execution.id} for {canvas_type} canvas")

        canvas_id = str(uuid.uuid4())
        # Build and commit the audit BEFORE broadcasting. Audit persistence is
        # independent of optional governance enforcement: a presentation with
        # no durable audit must never reach the user.
        with get_db_session() as db:
            audit = await _create_canvas_audit(
                db=db,
                require_durable_receipt=True,
                expected_tenant_id=tenant_id,
                expected_workspace_id=workspace_id,
                agent_id=agent.id if agent else None,
                agent_execution_id=agent_execution.id if agent_execution else None,
                user_id=user_id,
                canvas_id=canvas_id,
                session_id=session_id,
                canvas_type=canvas_type,
                component_type=component_type,
                component_name=None,
                action="present",
                governance_check_passed=governance_check["allowed"] if governance_check else None,
                metadata={
                    "title": title,
                    "layout": layout,
                    # Business fields remain in native content, not authority metadata.
                    "data": data,
                    "content": data,
                }
            )
            audit_id = str(audit.id) if audit is not None else None
            if audit is not None:
                user_id = str(audit.user_id)

        if audit is None:
            logger.error(
                f"{canvas_type} presentation refused: canvas audit was not persisted")
            return await _presentation_failure_result({
                "success": False,
                "status": "not_applied",
                "canvas_id": canvas_id,
                "verification": {"status": "refused", "effect": "none"},
                "error": (
                    "Canvas audit could not be persisted; "
                    f"{canvas_type} canvas was not presented")
            }, agent_execution.id if agent_execution else None)

        # Broadcast only after the audit row is durably committed.
        user_channels = _user_broadcast_channels(user_id, session_id)

        for _user_channel in user_channels:
            await ws_manager.broadcast(
                _user_channel,
            {
                "type": "canvas:update",
                "data": {
                    "action": "present",
                    "canvas_type": canvas_type,
                    "component": component_type,
                    "canvas_id": canvas_id,
                    "session_id": session_id,
                    "revision_audit_id": audit_id,
                    "title": title,
                    "layout": layout,
                    "data": data
                }
            }
        )

        # Mark execution as completed only after the audited presentation.
        if agent_execution:
            with get_db_session() as db:
                execution = db.query(AgentExecution).filter(
                    AgentExecution.id == agent_execution.id
                ).first()
                if execution:
                    execution.status = "completed"
                    execution.output_summary = f"Presented {canvas_type} canvas: {title or component_type}"
                    execution.completed_at = datetime.now()
                    db.commit()

                    # Record outcome for confidence
                    from core.service_factory import ServiceFactory
                    governance_service = ServiceFactory.get_governance_service(db)
                    await governance_service.record_outcome(agent.id, success=True)

        logger.info(
            f"Presented {canvas_type} canvas ({component_type}) to user {user_id}"
            + (f" (agent: {agent.name})" if agent else "")
        )
        return {
            "success": True,
            "canvas_type": canvas_type,
            "component_type": component_type,
            "canvas_id": canvas_id,
            "audit_id": audit_id,
            "agent_id": agent.id if agent else None,
            "title": title,
            "layout": layout
        }

    except CanvasPresentationReceiptError as error:
        return await _presentation_failure_result(error.as_result(), agent_execution.id if agent_execution else None)

    except Exception as e:
        if audit_id and audit is not None:
            logger.warning("Committed presentation follow-through unavailable", error_class=type(e).__name__)
            return await _presentation_failure_result(
                CanvasPresentationReceiptError(audit_id, canvas_id, True).as_result(),
                agent_execution.id if agent_execution else None)
        logger.error(f"Failed to present specialized canvas: {e}")

        # Mark execution as failed
        if agent_execution and FeatureFlags.should_enforce_governance('canvas'):
            try:
                with get_db_session() as db:
                    execution = db.query(AgentExecution).filter(
                        AgentExecution.id == agent_execution.id
                    ).first()
                    if execution:
                        execution.status = "failed"
                        execution.error_message = str(e)
                        execution.completed_at = datetime.now()
                        db.commit()

                        if agent:
                            from core.service_factory import ServiceFactory
                            governance_service = ServiceFactory.get_governance_service(db)
                            await governance_service.record_outcome(agent.id, success=False)
            except Exception as inner_e:
                logger.error(f"Failed to record execution failure: {inner_e}")

        return {"success": False, "error": str(e)}

"""Canvas typed receipts as ordinary assignment evidence and guarded actions.

The canvas is the authoring surface; the assignment executor remains the only
job engine. A receipt step consumes the exact server-issued snapshot, and a
guard step rechecks the current canvas revision/source/manifest immediately
before a declared action. Actions still dispatch through the registered action
registry and the executor's approval/operation/readback controls.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Optional, Sequence

from core.assignment_executor import (
    _action_registry_adapter,
    register_assignment_adapter,
)
from core.assignment_plan import (
    new_assignment,
    new_step,
    new_teaching_snapshot,
)


def _receipt_digest(receipt: Dict[str, Any]) -> str:
    payload = {
        key: value for key, value in receipt.items() if key != "digest"
    }
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()


def _context_identity(context: Dict[str, Any]) -> Dict[str, str]:
    provenance = dict(context.get("provenance") or {})
    return {
        "user_id": str(
            provenance.get("requester_id")
            or context.get("employee_id") or ""),
        "workspace_id": str(context.get("workspace_id") or "default"),
        "tenant_id": str(context.get("tenant_id") or "default"),
    }


def _authorized_canvas(canvas_id: str, context: Dict[str, Any]):
    """Load and authorize the canvas for the AUTHENTICATED requester.

    A known canvas id is not permission, and canvas.created_by is not a
    substitute for the assignment's authenticated principal.
    """
    from types import SimpleNamespace
    from core.database import get_db_session
    from core.models import Canvas
    from core.canvas_capability_service import CapabilityError, authorize_canvas

    identity = _context_identity(context)
    if not identity["user_id"]:
        return None, "The assignment has no authenticated canvas principal."
    user = SimpleNamespace(
        id=identity["user_id"], workspace_id=identity["workspace_id"],
        tenant_id=identity["tenant_id"], role="workspace_admin",
        is_active=True)
    with get_db_session() as db:
        canvas = (
            db.query(Canvas)
            .populate_existing()
            .filter(Canvas.id == canvas_id)
            .first()
        )
        if canvas is None:
            return None, "The canvas is no longer available."
        if (identity["tenant_id"] and canvas.tenant_id
                and identity["tenant_id"] != str(canvas.tenant_id)):
            return None, "The canvas belongs to a different tenant."
        try:
            authorize_canvas(db, canvas, user)
        except CapabilityError as exc:
            return None, f"Canvas access refused: {exc.code}."
        return canvas, ""


def _recomputed_receipt(canvas_id: str, context: Dict[str, Any]):
    """Recompute the receipt from the authoritative canvas snapshot.

    The browser/route value is only a selector. Rows, totals and the digest
    must match what the server derives now; a self-consistent forged receipt
    with the same revision/source is still refused.
    """
    from types import SimpleNamespace
    from core.database import get_db_session
    from core.models import Canvas
    from core.canvas_capability_service import (
        CapabilityError,
        current_revision,
        derive_operation,
        get_manifest,
        _dataset_source,
    )

    identity = _context_identity(context)
    if not identity["user_id"]:
        return None, "The assignment has no authenticated canvas principal."
    with get_db_session() as db:
        canvas = (
            db.query(Canvas)
            .populate_existing()
            .filter(Canvas.id == canvas_id)
            .first()
        )
        if canvas is None:
            return None, "The canvas is no longer available."
        manifest = get_manifest(canvas)
        source = _dataset_source(canvas)
        if (identity["tenant_id"] and canvas.tenant_id
                and identity["tenant_id"] != str(canvas.tenant_id)):
            return None, "The canvas belongs to a different tenant."
        user = SimpleNamespace(
            id=identity["user_id"],
            workspace_id=identity["workspace_id"],
            tenant_id=identity["tenant_id"],
            role="workspace_admin", is_active=True,
        )
        try:
            from core.canvas_capability_service import authorize_canvas

            authorize_canvas(db, canvas, user)
        except CapabilityError as exc:
            return None, f"Canvas access refused: {exc.code}."
        try:
            derived = derive_operation(
                db, canvas, user,
                expected_revision=current_revision(canvas),
                manifest_revision_value=str(
                    manifest.get("manifest_revision") or ""),
                source_version=str(source.get("source_version") or ""),
            )
        except CapabilityError as exc:
            return None, (
                f"The canvas receipt cannot be recomputed ({exc.code}): "
                f"{exc.message}")
        return dict(derived.get("input_receipt") or {}), ""


def _canvas_state(canvas: Any) -> Dict[str, Any]:
    from core.canvas_capability_service import (
        current_revision,
        get_manifest,
        _dataset_source,
    )

    manifest = get_manifest(canvas)
    source = _dataset_source(canvas)
    return {
        "revision": current_revision(canvas),
        "manifest": manifest,
        "manifest_revision": str(manifest.get("manifest_revision") or ""),
        "source": source,
        "source_version": str(source.get("source_version") or ""),
        "workspace_id": str(canvas.workspace_id or ""),
        "tenant_id": str(canvas.tenant_id or ""),
    }


@register_assignment_adapter(
    "canvas.receipt",
    description="Consume one server-issued typed canvas receipt",
    metadata={"effect": "local", "required_actions": ["calculate"],
              "allow_standing_authorization": False},
)
async def _canvas_receipt(inputs: Dict[str, Any], context: Dict[str, Any]):
    receipt = dict(inputs.get("receipt") or {})
    canvas_id = str(inputs.get("canvas_id") or "")
    if not receipt or not canvas_id:
        return {
            "status": "failed",
            "message": "No server-issued canvas receipt was bound.",
            "evidence": [],
        }
    digest = str(receipt.get("digest") or "")
    if digest != _receipt_digest(receipt):
        return {
            "status": "failed",
            "message": "The canvas receipt digest does not match its content.",
            "evidence": [],
        }
    expected_revision = inputs.get("expected_revision")
    expected_manifest = str(inputs.get("manifest_revision") or "")
    expected_source = str(inputs.get("source_version") or "")
    if str(receipt.get("canvas_id") or "") != canvas_id:
        return {
            "status": "failed",
            "message": "The receipt belongs to a different canvas.",
            "evidence": [],
        }
    if (expected_revision is not None
            and int(receipt.get("state_revision") or -1)
            != int(expected_revision)):
        return {
            "status": "failed",
            "message": "The receipt state revision is not the accepted one.",
            "evidence": [],
        }
    if expected_manifest and str(
            receipt.get("manifest_revision") or "") != expected_manifest:
        return {
            "status": "failed",
            "message": "The receipt manifest revision is not the accepted one.",
            "evidence": [],
        }
    source = dict(receipt.get("source") or {})
    if expected_source and str(
            source.get("source_version") or "") != expected_source:
        return {
            "status": "failed",
            "message": "The receipt source version is not the accepted one.",
            "evidence": [],
        }
    current, auth_error = _authorized_canvas(canvas_id, context)
    if current is None:
        return {
            "status": "failed",
            "message": auth_error or "The canvas is no longer available.",
            "evidence": [],
        }
    state = _canvas_state(current)
    if (
        state["revision"] != int(receipt.get("state_revision") or -1)
        or state["manifest_revision"] != str(
            receipt.get("manifest_revision") or "")
        or state["source_version"] != str(
            source.get("source_version") or "")
        or str(state["source"].get("sha256") or "") != str(
            source.get("sha256") or "")
    ):
        return {
            "status": "failed",
            "message": (
                "The canvas changed after the typed receipt was issued; the "
                "receipt is stale."),
            "evidence": [{"kind": "canvas_receipt", "digest": digest}],
        }
    workspace_id = str(context.get("workspace_id") or "")
    if workspace_id and state["workspace_id"] and (
            workspace_id != state["workspace_id"]):
        return {
            "status": "failed",
            "message": "The canvas belongs to a different workspace.",
            "evidence": [],
        }
    recomputed, recompute_error = _recomputed_receipt(canvas_id, context)
    if recomputed is None:
        return {
            "status": "failed",
            "message": recompute_error or "The canvas receipt is unavailable.",
            "evidence": [{"kind": "canvas_receipt", "digest": digest}],
        }
    if str(recomputed.get("digest") or "") != digest:
        return {
            "status": "failed",
            "message": (
                "The supplied canvas receipt is not the server-issued receipt "
                "for the current snapshot."),
            "error_class": "receipt_not_server_issued",
            "evidence": [{"kind": "canvas_receipt"}],
        }
    aggregates = dict(receipt.get("aggregates") or {})
    fields = list(receipt.get("fields") or [])
    currency = next(
        (str(item.get("currency") or "") for item in fields
         if item.get("currency")), "")
    first_total = next(iter(aggregates.values()), "")
    return {
        "status": "applied",
        "summary": (
            f"consumed canvas receipt {digest[:12]} with "
            f"{receipt.get('row_count')} rows"),
        "input_receipt": receipt,
        "rows": list(receipt.get("rows") or []),
        "aggregates": aggregates,
        "fields": fields,
        "value": first_total,
        "unit": currency,
        "source": source,
        "row_count": receipt.get("row_count"),
        "evidence": [{"kind": "canvas_receipt", "digest": digest}],
    }


@register_assignment_adapter(
    "canvas.guard",
    description="Recheck canvas revision and declared authority before an action",
    metadata={"effect": "read_only", "required_actions": [],
              "allow_standing_authorization": False},
)
async def _canvas_guard(inputs: Dict[str, Any], context: Dict[str, Any]):
    canvas_id = str(inputs.get("canvas_id") or "")
    action_id = str(inputs.get("action_id") or "")
    operation = str(inputs.get("operation") or "")
    if not canvas_id or not action_id:
        return {
            "status": "failed",
            "message": "The canvas action guard is incomplete.",
            "evidence": [],
        }
    current, auth_error = _authorized_canvas(canvas_id, context)
    if current is None:
        return {
            "status": "failed",
            "message": auth_error or "The canvas is no longer available.",
            "evidence": [],
        }
    state = _canvas_state(current)
    if int(inputs.get("expected_revision") or -1) != state["revision"]:
        return {
            "status": "failed",
            "message": "The canvas revision changed before the action.",
            "evidence": [{"kind": "canvas_guard", "reason": "stale_revision"}],
        }
    if str(inputs.get("manifest_revision") or "") != state[
            "manifest_revision"]:
        return {
            "status": "failed",
            "message": "The canvas manifest changed before the action.",
            "evidence": [{"kind": "canvas_guard", "reason": "stale_manifest"}],
        }
    if str(inputs.get("source_version") or "") != state["source_version"]:
        return {
            "status": "failed",
            "message": "The canvas source changed before the action.",
            "evidence": [{"kind": "canvas_guard", "reason": "stale_source"}],
        }
    workspace_id = str(context.get("workspace_id") or "")
    if workspace_id and state["workspace_id"] and (
            workspace_id != state["workspace_id"]):
        return {
            "status": "failed",
            "message": "The canvas belongs to a different workspace.",
            "evidence": [],
        }
    declared = {
        str(item.get("id") or ""): dict(item)
        for item in (state["manifest"].get("actions") or [])
        if isinstance(item, dict)
    }
    binding = declared.get(action_id)
    if binding is None:
        return {
            "status": "failed",
            "message": (
                f"Action {action_id!r} is no longer declared on the canvas."),
            "evidence": [{"kind": "canvas_guard", "reason": "action_removed"}],
        }
    if operation and str(binding.get("operation") or "") != operation:
        return {
            "status": "failed",
            "message": "The declared action operation changed before dispatch.",
            "evidence": [{"kind": "canvas_guard", "reason": "action_changed"}],
        }
    return {
        "status": "applied",
        "summary": f"canvas guard passed for {action_id}",
        "guard": {
            "canvas_id": canvas_id,
            "action_id": action_id,
            "operation": operation,
            "revision": state["revision"],
            "manifest_revision": state["manifest_revision"],
            "source_version": state["source_version"],
        },
        "evidence": [{
            "kind": "canvas_guard",
            "canvas_id": canvas_id,
            "action_id": action_id,
            "revision": state["revision"],
        }],
    }


@register_assignment_adapter(
    "canvas.action",
    description="Revalidate the canvas immediately before a declared action",
    metadata={"effect": "declared", "required_actions": [],
              "allow_standing_authorization": False},
)
async def _canvas_action(inputs: Dict[str, Any], context: Dict[str, Any]):
    """Final revision/authority check, then the shared registered dispatch."""
    canvas_id = str(inputs.get("canvas_id") or "")
    action_id = str(inputs.get("action_id") or "")
    operation = str(inputs.get("operation") or "")
    current, auth_error = _authorized_canvas(canvas_id, context)
    if current is None:
        return {
            "status": "failed",
            "message": auth_error or "The canvas is no longer available.",
            "error_class": "canvas_not_authorized",
        }
    state = _canvas_state(current)
    if int(inputs.get("expected_revision") or -1) != state["revision"]:
        return {
            "status": "failed",
            "message": "The canvas revision changed before execution.",
            "error_class": "stale_canvas_revision",
        }
    if str(inputs.get("manifest_revision") or "") != state[
            "manifest_revision"]:
        return {
            "status": "failed",
            "message": "The canvas manifest changed before execution.",
            "error_class": "stale_canvas_manifest",
        }
    if str(inputs.get("source_version") or "") != state["source_version"]:
        return {
            "status": "failed",
            "message": "The canvas source changed before execution.",
            "error_class": "stale_canvas_source",
        }
    workspace_id = str(context.get("workspace_id") or "")
    if workspace_id and state["workspace_id"] and (
            workspace_id != state["workspace_id"]):
        return {
            "status": "failed",
            "message": "The canvas belongs to a different workspace.",
            "error_class": "workspace_mismatch",
        }
    declared = {
        str(item.get("id") or ""): dict(item)
        for item in (state["manifest"].get("actions") or [])
        if isinstance(item, dict)
    }
    binding = declared.get(action_id)
    if binding is None:
        return {
            "status": "failed",
            "message": (
                f"Action {action_id!r} is no longer declared on the canvas."),
            "error_class": "action_revoked",
        }
    if operation and str(binding.get("operation") or "") != operation:
        return {
            "status": "failed",
            "message": "The declared action operation changed.",
            "error_class": "action_changed",
        }
    return await _action_registry_adapter({
        "action": operation,
        "arguments": dict(inputs.get("arguments") or {}),
    }, context)


def build_canvas_assignment_plan(
    canvas: Any, manifest: Dict[str, Any], receipt: Dict[str, Any],
    *, objective: str, employee_id: str, workspace_id: str, tenant_id: str,
    action_ids: Optional[Sequence[str]] = None, requester_id: str = "",
) -> Dict[str, Any]:
    """Build one assignment plan from a server-issued receipt and declarations."""
    from core.canvas_capability_service import (
        current_revision,
        render_canvas_action_arguments,
    )

    receipt_result = dict(receipt)
    receipt_payload = dict(receipt_result.get("input_receipt") or {})
    if not receipt_payload:
        raise ValueError("a complete typed receipt is required")
    revision = int(receipt_result.get("revision") or current_revision(canvas))
    manifest_revision = str(
        receipt_result.get("manifest_revision")
        or manifest.get("manifest_revision") or "")
    source_version = str(
        (receipt_result.get("source") or {}).get("source_version") or "")
    receipt_step = new_step(
        step_id="receipt",
        title="Consume the typed canvas receipt",
        operation_type="calculate",
        adapter="canvas.receipt",
        inputs={
            "canvas_id": canvas.id,
            "receipt": receipt_payload,
            "expected_revision": revision,
            "manifest_revision": manifest_revision,
            "source_version": source_version,
        },
        effect="local",
    )
    steps = [receipt_step]
    declared = {
        str(item.get("id") or ""): dict(item)
        for item in (manifest.get("actions") or [])
        if isinstance(item, dict)
    }
    selected = [
        declared[action_id]
        for action_id in (action_ids or list(declared))
        if action_id in declared
    ]
    for binding in selected:
        action_id = str(binding.get("id") or "")
        operation = str(binding.get("operation") or "")
        guard_id = f"guard-{action_id}"
        action_step_id = f"action-{action_id}"
        steps.append(new_step(
            step_id=guard_id,
            title=f"Validate authority for {action_id}",
            operation_type="retrieve",
            adapter="canvas.guard",
            depends_on=["receipt"],
            inputs={
                "canvas_id": canvas.id,
                "action_id": action_id,
                "operation": operation,
                "expected_revision": revision,
                "manifest_revision": manifest_revision,
                "source_version": source_version,
                "receipt_digest": receipt_payload.get("digest"),
            },
            effect="read_only",
        ))
        steps.append(new_step(
            step_id=action_step_id,
            title=f"Execute declared action {action_id}",
            operation_type="outbound",
            adapter="canvas.action",
            depends_on=[guard_id],
            inputs={
                "canvas_id": canvas.id,
                "action_id": action_id,
                "operation": operation,
                "expected_revision": revision,
                "manifest_revision": manifest_revision,
                "source_version": source_version,
                "arguments": render_canvas_action_arguments(
                    binding.get("arguments") or {}, receipt_result,
                    objective=objective, canvas_id=canvas.id),
            },
            effect="external",
            approval_required=True,
            approval_purpose=(
                f"Execute canvas action {action_id} through the registered "
                "provider boundary"),
        ))
    sources = [{
        "kind": "canvas_receipt",
        "canvas_id": canvas.id,
        "resource_id": receipt_payload.get("source", {}).get("resource_id"),
        "source_version": source_version,
        "sha256": receipt_payload.get("source", {}).get("sha256"),
        "manifest_revision": manifest_revision,
        "state_revision": revision,
        "receipt_digest": receipt_payload.get("digest"),
    }]
    return new_assignment(
        objective=objective,
        employee_id=employee_id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        teaching_snapshot=new_teaching_snapshot(
            revision=f"canvas:{manifest_revision}",
            matched_context={"canvas_id": canvas.id},
        ),
        steps=steps,
        sources=sources,
        authorized_actions=["calculate", "outbound"] if selected else [
            "calculate"],
        provenance={
            "canvas_id": canvas.id,
            "requester_id": str(requester_id or ""),
            "manifest_revision": manifest_revision,
            "state_revision": revision,
            "receipt_digest": receipt_payload.get("digest"),
            "source": receipt_payload.get("source"),
        },
        budget={
            "max_steps": 40,
            "max_attempts_per_step": 3,
            "max_wall_seconds": 600,
        },
    )

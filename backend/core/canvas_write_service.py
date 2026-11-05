"""Verified direct canvas writes for the authenticated HTTP routes.

The assignment-mediated canvas actions already run the postcondition oracle.
The direct PUT/restore routes bypassed it. This module freezes the expected
request material, dispatches the existing canvas CRUD tool, and re-derives the
committed result with the EXISTING ``canvas.update`` /
``canvas.restore_version`` verifiers.

It does not add a second store, digest or oracle engine. The verifier opens its
own read session, so a same-transaction identity-map echo cannot stand in for
the durable readback.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.oracle import oracle_verifier_enabled, validate
from core.oracle.postcondition_verifiers import canvas_content_digest
from tools.canvas_crud_tool import (
    WRITE_UNKNOWN,
    canonical_update_content,
    restore_canvas_version,
    update_canvas_content,
)

logger = logging.getLogger(__name__)


def _latest_audit(canvas_id: str):
    """Read the current audit row for canonical content resolution."""
    try:
        from sqlalchemy import desc

        from core.database import get_db_session
        from core.models import CanvasAudit

        with get_db_session() as db:
            return (
                db.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == canvas_id)
                .order_by(desc(CanvasAudit.created_at),
                          desc(CanvasAudit.id))
                .first()
            )
    except Exception:  # noqa: BLE001 — the tool owns the refusal path
        return None


def _expected_update_content(
    canvas_id: str,
    canvas_type: Optional[str],
    content: Any,
    manual_retype: bool,
):
    latest = _latest_audit(canvas_id)
    if latest is None:
        return (canvas_type or "generic"), content
    return canonical_update_content(
        latest, canvas_type, content, manual_retype)


def _identity(
    canvas_id: str, result: Dict[str, Any],
    operation_id: Optional[str], restored_from: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "canvas_id": canvas_id,
        "audit_id": result.get("audit_id"),
        "operation_id": operation_id or result.get("operation_id"),
        "restored_from": restored_from or result.get("restored_from"),
    }


async def _envelope(
    *,
    action: str,
    result: Dict[str, Any],
    canvas_id: str,
    content: Any,
    expected_digest: str,
    operation_id: Optional[str],
    restore_audit_id: str,
    tenant_id: Optional[str],
    workspace_id: Optional[str],
    actor_id: Optional[str],
) -> Dict[str, Any]:
    identity = _identity(
        canvas_id, result, operation_id, restore_audit_id or None)
    base = {**result, **identity}
    no_change = bool(result.get("no_change"))
    write_outcome = str(result.get("write_outcome") or "")

    if not result.get("success"):
        if write_outcome == WRITE_UNKNOWN:
            # The append may have committed. Never call this "nothing
            # changed"; keep the target/operation identity so a caller does
            # not blindly repeat the effect.
            return {
                **base,
                "status": "effect_unknown",
                "verification": {
                    "status": "unavailable",
                    "effect": "unknown",
                    "replay": "do_not_repeat",
                },
            }
        return {
            **base,
            "status": "refused",
            "verification": {"status": "not_attempted", "effect": "none"},
        }

    if not oracle_verifier_enabled():
        return {
            **base,
            "status": (
                "no_change_unverified" if no_change
                else "committed_unverified"),
            "verification": {
                "status": "disabled",
                "effect": "none" if no_change else "committed",
                "replay": "do_not_repeat",
            },
        }

    ctx: Dict[str, Any] = {
        "canvas_id": canvas_id,
        "audit_id": result.get("audit_id"),
        "write_outcome": result.get("write_outcome"),
        "no_change": no_change,
        "already_applied": bool(result.get("already_applied")),
        "content": content,
        "restored_from": result.get("restored_from"),
        "_oracle_action": action,
        "_oracle_expected_canvas_id": canvas_id,
        "_oracle_expected_canvas_content_sha256": expected_digest,
        "_oracle_expected_operation_id": operation_id or "",
        "_oracle_expected_restore_audit_id": restore_audit_id or "",
        "_oracle_expected_review_status": "accepted",
        "_oracle_expected_tenant_id": tenant_id or "",
        "_oracle_expected_workspace_id": workspace_id or "",
        "_oracle_expected_actor_id": actor_id or "",
    }
    try:
        oracle = await validate(action, ctx)
        verified = bool(oracle is not None and oracle.verified)
        evidence = str(getattr(oracle, "evidence", "") or "")
        unavailable = oracle is None
    except Exception as exc:  # noqa: BLE001 — a committed write stays honest
        logger.warning(
            "direct canvas %s oracle unavailable: %s", action, exc)
        verified = False
        evidence = f"oracle unavailable: {type(exc).__name__}"
        unavailable = True

    if verified:
        return {
            **base,
            "status": "no_change" if no_change else "verified",
            "verification": {
                "status": "verified",
                "effect": "none" if no_change else "committed",
                "no_change": True if no_change else False,
                "evidence": evidence,
            },
        }
    return {
        **base,
        "status": (
            "no_change_unverified" if no_change
            else "committed_unverified"),
        "verification": {
            "status": "unavailable" if unavailable else "refuted",
            "effect": "none" if no_change else "committed",
            "replay": "do_not_repeat",
            "evidence": evidence,
        },
    }


async def update_canvas_verified(
    user_id: str,
    canvas_id: str,
    content: Any,
    canvas_type: str = "generic",
    title: Optional[str] = None,
    manual_retype: bool = False,
    operation_id: Optional[str] = None,
    expected_prior_audit_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispatch the existing update tool, then verify its durable result."""
    resolved_type, resolved_content = _expected_update_content(
        canvas_id, canvas_type, content, manual_retype)
    expected_digest = canvas_content_digest(resolved_content)
    result = await update_canvas_content(
        user_id=user_id,
        canvas_id=canvas_id,
        content=content,
        canvas_type=resolved_type,
        title=title,
        manual_retype=manual_retype,
        operation_id=operation_id,
        expected_prior_audit_id=expected_prior_audit_id,
    )
    return await _envelope(
        action="canvas.update",
        result=result,
        canvas_id=canvas_id,
        content=resolved_content,
        expected_digest=expected_digest,
        operation_id=operation_id,
        restore_audit_id="",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        actor_id=user_id,
    )


async def restore_canvas_verified(
    user_id: str,
    canvas_id: str,
    audit_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispatch the existing restore tool, then verify its durable result."""
    result = await restore_canvas_version(
        user_id=user_id, canvas_id=canvas_id, audit_id=audit_id)
    return await _envelope(
        action="canvas.restore_version",
        result=result,
        canvas_id=canvas_id,
        content=None,
        expected_digest="",
        operation_id=None,
        restore_audit_id=str(audit_id),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        actor_id=user_id,
    )

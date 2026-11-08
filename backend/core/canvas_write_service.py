"""Verified direct canvas writes for the authenticated HTTP routes.

The assignment-mediated canvas actions already run the postcondition oracle.
The direct PUT/restore routes bypassed it, and the direct delete/undelete
routes bypassed both the oracle AND the accepted canvas scope gate. This module
freezes the expected request material and a server-owned operation identity,
authorizes the principal's tenant/workspace against the authoritative canvas
BEFORE dispatch, calls the existing canvas CRUD tool, and re-derives the
committed result with the EXISTING ``canvas.update`` /
``canvas.restore_version`` / ``canvas.delete`` / ``canvas.undelete`` verifiers.

It does not add a second store, digest or oracle engine. The verifier opens its
own read session, so a same-transaction identity-map echo cannot stand in for
the durable readback.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from core.oracle import oracle_verifier_enabled, validate
from core.oracle.postcondition_verifiers import canvas_content_digest
from tools import canvas_crud_tool as _canvas_crud
from tools.canvas_crud_tool import (
    WRITE_UNKNOWN,
    active_canvas_actor,
    canonical_update_content,
    canvas_lifecycle_owner_error,
    canvas_lifecycle_snapshot,
    canvas_write_scope_error,
    find_operation_audit,
    find_operation_audits,
)

logger = logging.getLogger(__name__)


async def update_canvas_content(*args, **kwargs):
    """Patchable seam that still honors tool-module patches.

    Existing callers/tests patch either this service symbol or
    ``tools.canvas_crud_tool.update_canvas_content``. Delegating through the
    module keeps both seams live without a second writer.
    """
    return await _canvas_crud.update_canvas_content(*args, **kwargs)


async def restore_canvas_version(*args, **kwargs):
    """Patchable seam for the restore writer (same rationale)."""
    return await _canvas_crud.restore_canvas_version(*args, **kwargs)


async def delete_canvas(*args, **kwargs):
    """Patchable seam for the delete writer (same rationale)."""
    return await _canvas_crud.delete_canvas(*args, **kwargs)


async def restore_deleted_canvas(*args, **kwargs):
    """Patchable seam for the undelete writer (same rationale)."""
    return await _canvas_crud.restore_deleted_canvas(*args, **kwargs)


def _new_operation_id(kind: str) -> str:
    """A fresh server-owned identity for one logical write.

    Manual callers that omit an id still get a distinct, durable operation
    identity, so an old identical audit can never certify a new save. A
    supplied id is honored separately for idempotent retries.
    """
    return f"http-canvas-{kind}:{uuid.uuid4().hex}"


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


def _preflight_scope(
    canvas_id: str,
    user_id: str,
    tenant_id: Optional[str],
    workspace_id: Optional[str],
    target_audit_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Read-only scope authorization before dispatch.

    The writer repeats this check inside the mutation transaction; this
    preflight only makes a foreign/moved canvas a clean before-effect refusal
    instead of a committed-but-unverified write.
    """
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            return canvas_write_scope_error(
                db, canvas_id, user_id, tenant_id, workspace_id,
                target_audit_id=target_audit_id)
    except Exception as exc:  # noqa: BLE001 — unreadable scope is not permission
        logger.warning("direct canvas scope preflight failed: %s", exc)
        return {
            "http_status": 503,
            "error": "Canvas scope could not be verified",
        }


def _refusal(
    canvas_id: str,
    error: str,
    http_status: int,
    *,
    operation_id: Optional[str] = None,
    restored_from: Optional[str] = None,
    action_type: Optional[str] = None,
    prior_audit_id: Optional[str] = None,
    tombstone_audit_id: Optional[str] = None,
    source_audit_id: Optional[str] = None,
    content_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "success": False,
        "status": "refused",
        "canvas_id": canvas_id,
        "audit_id": None,
        "operation_id": operation_id,
        "restored_from": restored_from,
        "action_type": action_type,
        "prior_audit_id": prior_audit_id,
        "tombstone_audit_id": tombstone_audit_id,
        "restored_from_tombstone_id": tombstone_audit_id,
        "source_audit_id": source_audit_id,
        "content_sha256": content_sha256,
        "error": error,
        "http_status": int(http_status),
        "verification": {"status": "not_attempted", "effect": "none"},
    }


def _operation_material_error(
    canvas_id: str,
    operation_id: str,
    expected_digest: str,
) -> Optional[Dict[str, Any]]:
    """Refuse a supplied operation id that already names different material.

    A logical-operation id is an idempotency key, not a way to reuse an old
    receipt for a new save. The writer repeats this binding inside its
    transaction.
    """
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            existing = find_operation_audit(db, canvas_id, operation_id)
            if existing is None:
                return None
            details = existing.details_json or {}
            status = str(details.get("review_status") or "unknown")
            content = details.get("content", details.get("data"))
            if (status != "accepted" or content is None
                    or canvas_content_digest(content) != expected_digest):
                return _refusal(
                    canvas_id,
                    "operation_id already used with different material or "
                    "is not an accepted save",
                    409,
                    operation_id=operation_id,
                )
    except Exception as exc:  # noqa: BLE001 — unreadable identity is not proof
        logger.warning("direct canvas operation binding failed: %s", exc)
        return _refusal(
            canvas_id,
            "operation identity could not be verified",
            503,
            operation_id=operation_id,
        )
    return None


def _identity(
    canvas_id: str, result: Dict[str, Any],
    operation_id: Optional[str], restored_from: Optional[str] = None,
) -> Dict[str, Any]:
    no_change = bool(result.get("no_change"))
    return {
        "canvas_id": canvas_id,
        # A no-change restore is a zero-effect contract, not a new write
        # receipt: do not invent an audit/operation id for it.
        "audit_id": None if no_change else result.get("audit_id"),
        "operation_id": (
            None if no_change
            else (operation_id or result.get("operation_id"))),
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
        # The direct HTTP slice freezes the principal's scope even when it is
        # empty; the verifier must refute a real scope in that case. Other
        # registered-action callers keep their existing conditional checks.
        "_oracle_require_scope_match": True,
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
    """Authorize scope, dispatch the existing update tool, then verify it."""
    supplied_operation_id = (operation_id or "").strip()
    operation_id = supplied_operation_id or _new_operation_id("update")

    scope_error = _preflight_scope(
        canvas_id, user_id, tenant_id, workspace_id)
    if scope_error:
        return _refusal(
            canvas_id,
            str(scope_error.get("error") or "Canvas write refused"),
            int(scope_error.get("http_status") or 403),
            operation_id=supplied_operation_id or None,
        )

    resolved_type, resolved_content = _expected_update_content(
        canvas_id, canvas_type, content, manual_retype)
    expected_digest = canvas_content_digest(resolved_content)
    material_error = _operation_material_error(
        canvas_id, operation_id, expected_digest)
    if material_error:
        return material_error

    result = await update_canvas_content(
        user_id=user_id,
        canvas_id=canvas_id,
        content=content,
        canvas_type=resolved_type,
        title=title,
        manual_retype=manual_retype,
        operation_id=operation_id,
        expected_prior_audit_id=expected_prior_audit_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        scope_required=True,
        bind_operation_material=True,
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
    """Authorize scope, dispatch the existing restore tool, then verify it."""
    restore_operation_id = _new_operation_id("restore")

    scope_error = _preflight_scope(
        canvas_id, user_id, tenant_id, workspace_id,
        target_audit_id=str(audit_id))
    if scope_error:
        return _refusal(
            canvas_id,
            str(scope_error.get("error") or "Canvas restore refused"),
            int(scope_error.get("http_status") or 403),
            restored_from=str(audit_id),
        )

    result = await restore_canvas_version(
        user_id=user_id,
        canvas_id=canvas_id,
        audit_id=audit_id,
        operation_id=restore_operation_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        scope_required=True,
    )
    return await _envelope(
        action="canvas.restore_version",
        result=result,
        canvas_id=canvas_id,
        content=None,
        expected_digest="",
        operation_id=restore_operation_id,
        restore_audit_id=str(audit_id),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        actor_id=user_id,
    )


# ---------------------------------------------------------------------------
# Verified delete / undelete (append-only canvas lifecycle)
# ---------------------------------------------------------------------------
def resolve_actor_scope(
    user_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve the authoritative current actor for a trusted dispatch.

    ``tenant_id``/``workspace_id`` are accepted for caller compatibility but
    are **not** authority: the current active User row is. A missing,
    unreadable, inactive or status-changed User returns ``ok=False``; there is
    no context-scope fallback.
    """
    resolved: Dict[str, Any] = {
        "ok": False,
        "active": False,
        "user_found": False,
        "tenant_id": None,
        "workspace_id": None,
        "status": None,
        "is_active": False,
        "http_status": None,
        "error": None,
    }
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            actor = active_canvas_actor(db, user_id)
    except Exception as exc:  # noqa: BLE001 - unreadable is not permission
        logger.warning(
            "canvas lifecycle actor authority lookup failed: %s", exc)
        resolved.update(
            http_status=503,
            error="Acting user could not be verified",
        )
        return resolved
    if not actor.get("ok"):
        resolved.update(
            user_found=bool(actor.get("user_found", False)),
            status=actor.get("status"),
            is_active=bool(actor.get("is_active", False)),
            http_status=int(actor.get("http_status") or 403),
            error=actor.get("error") or "Acting user is not active",
        )
        return resolved
    resolved.update(
        ok=True,
        active=True,
        user_found=True,
        tenant_id=actor.get("tenant_id"),
        workspace_id=actor.get("workspace_id"),
        status=actor.get("status"),
        is_active=bool(actor.get("is_active", False)),
    )
    return resolved


def _lifecycle_preflight(
    canvas_id: str,
    user_id: str,
    tenant_id: Optional[str],
    workspace_id: Optional[str],
) -> Dict[str, Any]:
    """Read-only active-actor + canvas snapshot before dispatch.

    The raw current User row is authority and is resolved here before the
    canvas snapshot. ``tenant_id``/``workspace_id`` are retained only for
    caller compatibility; they are never used as a scope grant. The writer
    repeats and atomically claims the same actor snapshot in its transaction.
    """
    try:
        from core.database import get_db_session

        with get_db_session() as db:
            actor = active_canvas_actor(db, user_id)
            owner_error = canvas_lifecycle_owner_error(
                db, canvas_id, user_id)
            if owner_error:
                # Preserve the legacy 404 for a non-owner regardless of the
                # account status. Attach the actor snapshot so the service can
                # dispatch to the ownership-first writer, which also returns
                # 404; a non-owner never becomes an active-status oracle.
                snapshot = dict(owner_error)
                snapshot["actor_tenant_id"] = actor.get("tenant_id")
                snapshot["actor_workspace_id"] = actor.get("workspace_id")
                snapshot["actor_status"] = actor.get("status")
                snapshot["actor_is_active"] = bool(
                    actor.get("is_active", False))
                return snapshot
            if not actor.get("ok"):
                return {
                    "http_status": int(actor.get("http_status") or 403),
                    "error": (
                        actor.get("error")
                        or "Acting user is not active"),
                }
            snapshot = canvas_lifecycle_snapshot(
                db, canvas_id, user_id,
                actor.get("tenant_id"), actor.get("workspace_id"))
            if not isinstance(snapshot, dict):
                return {
                    "http_status": 503,
                    "error": (
                        "Canvas lifecycle scope could not be verified"),
                }
            snapshot["actor_tenant_id"] = actor.get("tenant_id")
            snapshot["actor_workspace_id"] = actor.get("workspace_id")
            snapshot["actor_status"] = actor.get("status")
            snapshot["actor_is_active"] = bool(
                actor.get("is_active", False))
            return snapshot
    except Exception as exc:  # noqa: BLE001 - unreadable scope is not permission
        logger.warning("canvas lifecycle scope preflight failed: %s", exc)
        return {
            "http_status": 503,
            "error": "Canvas lifecycle scope could not be verified",
        }


def _lookup_lifecycle_operation(
    canvas_id: str, operation_id: str,
) -> Optional[Dict[str, Any]]:
    """Durable lookup of one logical lifecycle operation, or None.

    Multiple durable rows for one operation key are ambiguous identity, not a
    replay. The returned ``ambiguous`` marker makes the caller fail closed.
    """
    from core.database import get_db_session

    with get_db_session() as db:
        rows = find_operation_audits(db, canvas_id, operation_id)
        if not rows:
            return None
        if len(rows) > 1:
            return {
                "ambiguous": True,
                "count": len(rows),
                "action_type": "",
                "audit_id": "",
                "canvas_type": None,
                "details": {},
            }
        row = rows[0]
        details = row.details_json or {}
        if not isinstance(details, dict):
            details = {}
        return {
            "audit_id": str(row.id),
            "action_type": str(row.action_type or ""),
            "canvas_type": getattr(row, "canvas_type", None),
            "details": details,
        }


async def _lifecycle_envelope(
    *,
    action: str,
    result: Dict[str, Any],
    canvas_id: str,
    operation_id: Optional[str],
    tenant_id: Optional[str],
    workspace_id: Optional[str],
    actor_id: Optional[str],
    expected_operation_id: str,
    operation_optional: bool = False,
    expected_prior_audit_id: str = "",
    expected_tombstone_audit_id: str = "",
    expected_source_audit_id: str = "",
    expected_content_sha256: str = "",
) -> Any:
    """Build the truthful lifecycle receipt around the writer's result."""
    already_applied = bool(result.get("already_applied"))
    no_change = bool(result.get("no_change") or already_applied)
    tombstone_id = (
        result.get("tombstone_audit_id")
        or result.get("restored_from_tombstone_id"))
    identity = {
        "canvas_id": canvas_id,
        "audit_id": result.get("audit_id"),
        "operation_id": result.get("operation_id") or operation_id,
        "action_type": result.get("action_type"),
        "prior_audit_id": result.get("prior_audit_id"),
        "tombstone_audit_id": tombstone_id,
        "restored_from_tombstone_id": tombstone_id,
        "source_audit_id": result.get("source_audit_id"),
        "content_sha256": result.get("content_sha256"),
    }
    base = {**result, **identity}
    write_outcome = str(result.get("write_outcome") or "")

    if not result.get("success"):
        if write_outcome == WRITE_UNKNOWN:
            # The append may have committed. Never call this "nothing
            # changed"; keep the identity so a caller does not repeat it.
            return {
                **base,
                "status": "effect_unknown",
                "verification": {
                    "status": "unavailable",
                    "effect": "unknown",
                    "replay": "do_not_repeat",
                },
            }
        if write_outcome != "committed":
            return {
                **base,
                "status": "refused",
                "verification": {
                    "status": "not_attempted", "effect": "none"},
            }
        # The append IS durable; only the post-commit wrapper failed. Fall
        # through to the independent readback instead of reporting a refusal.

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
        "already_applied": already_applied,
        "_oracle_action": action,
        "_oracle_expected_canvas_id": canvas_id,
        "_oracle_expected_operation_id": expected_operation_id or "",
        "_oracle_lifecycle_operation_optional": bool(operation_optional),
        "_oracle_expected_prior_audit_id": expected_prior_audit_id or "",
        "_oracle_expected_tombstone_audit_id": (
            expected_tombstone_audit_id or ""),
        "_oracle_expected_source_audit_id": expected_source_audit_id or "",
        "_oracle_expected_canvas_content_sha256": (
            expected_content_sha256 or ""),
        "_oracle_expected_tenant_id": tenant_id or "",
        "_oracle_expected_workspace_id": workspace_id or "",
        "_oracle_expected_actor_id": actor_id or "",
        # The direct lifecycle slice freezes the principal's scope even when
        # it is empty; a real foreign scope must be refuted.
        "_oracle_require_scope_match": True,
    }
    try:
        oracle = await validate(action, ctx)
        verified = bool(oracle is not None and oracle.verified)
        evidence = str(getattr(oracle, "evidence", "") or "")
        unavailable = oracle is None
    except Exception as exc:  # noqa: BLE001 - a committed write stays honest
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


async def delete_canvas_verified(
    user_id: str,
    canvas_id: str,
    operation_id: Optional[str] = None,
    expected_prior_audit_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Authorize, dispatch the append-only delete, and verify the receipt."""
    supplied_operation_id = (operation_id or "").strip()
    operation_id = supplied_operation_id or _new_operation_id("delete")

    snapshot = _lifecycle_preflight(
        canvas_id, user_id, tenant_id, workspace_id) or {}
    status = snapshot.get("http_status")
    if status in (403, 409, 503):
        return _refusal(
            canvas_id,
            str(snapshot.get("error") or "Canvas delete refused"),
            int(status),
            operation_id=supplied_operation_id or None,
            action_type="delete",
            prior_audit_id=snapshot.get("latest_audit_id"),
            source_audit_id=snapshot.get("source_audit_id"),
            content_sha256=snapshot.get("content_sha256"),
        )
    if ("actor_tenant_id" not in snapshot
            or "actor_workspace_id" not in snapshot):
        return _refusal(
            canvas_id,
            "actor authority could not be verified",
            503,
            operation_id=supplied_operation_id or None,
            action_type="delete",
        )
    authority_tenant = snapshot.get("actor_tenant_id")
    authority_workspace = snapshot.get("actor_workspace_id")
    snapshot_available = status != 404

    existing = None
    if snapshot_available:
        try:
            existing = _lookup_lifecycle_operation(canvas_id, operation_id)
        except Exception as exc:  # noqa: BLE001 - unreadable identity is not proof
            logger.warning(
                "direct canvas delete operation binding failed: %s", exc)
            return _refusal(
                canvas_id,
                "operation identity could not be verified",
                503,
                operation_id=supplied_operation_id or None,
                action_type="delete",
            )

    if existing is not None:
        if existing.get("ambiguous"):
            return _refusal(
                canvas_id,
                "operation identity is ambiguous; multiple audit rows share it",
                409,
                operation_id=operation_id,
                action_type="delete",
            )
        existing_details = existing["details"]
        existing_prior = str(existing_details.get("prior_audit_id") or "")
        if str(existing["action_type"]) != "delete":
            return _refusal(
                canvas_id,
                "operation_id already used with a different canvas action",
                409,
                operation_id=operation_id,
                action_type="delete",
            )
        if (expected_prior_audit_id and existing_prior
                and existing_prior != str(expected_prior_audit_id)):
            return _refusal(
                canvas_id,
                "operation_id already used with different material or target",
                409,
                operation_id=operation_id,
                action_type="delete",
                prior_audit_id=existing_prior,
            )
        # The operation is only a replay while it still names the state it
        # landed on. If a later lifecycle row moved the canvas (for example
        # delete -> undelete), reusing the same id for a NEW delete targets
        # different material.
        intended_prior = str(expected_prior_audit_id or "")
        if (not intended_prior
                and snapshot.get("latest_action_type") != "delete"):
            intended_prior = str(snapshot.get("latest_audit_id") or "")
        if (existing_prior and intended_prior
                and existing_prior != intended_prior):
            return _refusal(
                canvas_id,
                "operation_id already used with different material or target",
                409,
                operation_id=operation_id,
                action_type="delete",
                prior_audit_id=existing_prior,
            )
        result = {
            "success": True,
            "already_applied": True,
            "replayed": True,
            "no_change": True,
            "write_outcome": "committed",
            "canvas_id": canvas_id,
            "audit_id": existing["audit_id"],
            "operation_id": operation_id,
            "action_type": "delete",
            "prior_audit_id": existing_prior or None,
            "source_audit_id": existing_details.get("source_audit_id"),
            "content_sha256": existing_details.get("content_sha256"),
            "canvas_type": existing.get("canvas_type"),
            "message": "Canvas delete already applied",
        }
        return await _lifecycle_envelope(
            action="canvas.delete",
            result=result,
            canvas_id=canvas_id,
            operation_id=operation_id,
            tenant_id=authority_tenant,
            workspace_id=authority_workspace,
            actor_id=user_id,
            expected_operation_id=operation_id,
            expected_prior_audit_id=existing_prior,
            expected_source_audit_id=str(
                existing_details.get("source_audit_id") or ""),
            expected_content_sha256=str(
                existing_details.get("content_sha256") or ""),
        )

    if (snapshot_available
            and snapshot.get("latest_action_type") == "delete"):
        expected_prior = str(
            snapshot.get("tombstone_prior_audit_id") or "")
        expected_source = str(
            snapshot.get("tombstone_source_audit_id") or "")
        expected_digest = str(
            snapshot.get("tombstone_content_sha256") or "")
        expected_operation = ""
        operation_optional = True
        writer_prior = (
            str(expected_prior_audit_id) if expected_prior_audit_id else None)
    else:
        expected_prior = str(snapshot.get("latest_audit_id") or "")
        expected_source = str(snapshot.get("source_audit_id") or "")
        expected_digest = str(snapshot.get("content_sha256") or "")
        expected_operation = operation_id
        operation_optional = False
        writer_prior = (
            str(expected_prior_audit_id) if expected_prior_audit_id
            else (expected_prior or None))

    if (snapshot_available
            and expected_prior_audit_id
            and snapshot.get("latest_action_type") != "delete"
            and str(expected_prior_audit_id)
            != str(snapshot.get("latest_audit_id") or "")):
        return _refusal(
            canvas_id,
            "canvas changed since the delete was planned",
            409,
            operation_id=operation_id,
            action_type="delete",
            prior_audit_id=snapshot.get("latest_audit_id"),
        )

    result = await delete_canvas(
        user_id=user_id,
        canvas_id=canvas_id,
        operation_id=operation_id,
        expected_prior_audit_id=writer_prior,
        tenant_id=authority_tenant,
        workspace_id=authority_workspace,
        expected_actor_status=snapshot.get("actor_status"),
        expected_actor_is_active=snapshot.get("actor_is_active"),
        scope_required=True,
    )
    if result.get("already_applied") and not result.get("replayed"):
        # A DIFFERENT logical operation met an already-deleted canvas. The
        # original tombstone is the durable state; this operation produced no
        # new row, so it cannot bind its own id to that historical row.
        expected_operation = ""
        operation_optional = True
        expected_prior = str(result.get("prior_audit_id") or "")
        expected_source = str(result.get("source_audit_id") or "")
        expected_digest = str(result.get("content_sha256") or "")
    elif result.get("already_applied") and result.get("replayed"):
        expected_operation = operation_id
        operation_optional = False

    return await _lifecycle_envelope(
        action="canvas.delete",
        result=result,
        canvas_id=canvas_id,
        operation_id=operation_id,
        tenant_id=authority_tenant,
        workspace_id=authority_workspace,
        actor_id=user_id,
        expected_operation_id=expected_operation,
        operation_optional=operation_optional,
        expected_prior_audit_id=expected_prior,
        expected_source_audit_id=expected_source,
        expected_content_sha256=expected_digest,
    )


async def restore_deleted_canvas_verified(
    user_id: str,
    canvas_id: str,
    operation_id: Optional[str] = None,
    tombstone_audit_id: Optional[str] = None,
    source_audit_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Authorize, dispatch the append-only undelete, and verify the receipt."""
    supplied_operation_id = (operation_id or "").strip()
    operation_id = supplied_operation_id or _new_operation_id("undelete")

    snapshot = _lifecycle_preflight(
        canvas_id, user_id, tenant_id, workspace_id) or {}
    status = snapshot.get("http_status")
    if status in (403, 409, 503):
        return _refusal(
            canvas_id,
            str(snapshot.get("error") or "Canvas undelete refused"),
            int(status),
            operation_id=supplied_operation_id or None,
            action_type="restore",
            tombstone_audit_id=snapshot.get("tombstone_audit_id"),
            source_audit_id=snapshot.get("source_audit_id"),
            content_sha256=snapshot.get("content_sha256"),
        )
    if ("actor_tenant_id" not in snapshot
            or "actor_workspace_id" not in snapshot):
        return _refusal(
            canvas_id,
            "actor authority could not be verified",
            503,
            operation_id=supplied_operation_id or None,
            action_type="restore",
        )
    authority_tenant = snapshot.get("actor_tenant_id")
    authority_workspace = snapshot.get("actor_workspace_id")
    snapshot_available = status != 404

    existing = None
    if snapshot_available:
        try:
            existing = _lookup_lifecycle_operation(canvas_id, operation_id)
        except Exception as exc:  # noqa: BLE001 - unreadable identity is not proof
            logger.warning(
                "direct canvas undelete operation binding failed: %s", exc)
            return _refusal(
                canvas_id,
                "operation identity could not be verified",
                503,
                operation_id=supplied_operation_id or None,
                action_type="restore",
            )

    if existing is not None:
        if existing.get("ambiguous"):
            return _refusal(
                canvas_id,
                "operation identity is ambiguous; multiple audit rows share it",
                409,
                operation_id=operation_id,
                action_type="restore",
            )
        existing_details = existing["details"]
        existing_tombstone = str(
            existing_details.get("tombstone_audit_id") or "")
        existing_source = str(
            existing_details.get("source_audit_id") or "")
        if (str(existing["action_type"]) != "restore"
                or (tombstone_audit_id and existing_tombstone
                    and existing_tombstone != str(tombstone_audit_id))
                or (source_audit_id and existing_source
                    and existing_source != str(source_audit_id))):
            return _refusal(
                canvas_id,
                "operation_id already used with different material or target",
                409,
                operation_id=operation_id,
                action_type="restore",
                tombstone_audit_id=existing_tombstone or None,
                source_audit_id=existing_source or None,
            )
        intended_tombstone = str(tombstone_audit_id or "")
        if (not intended_tombstone
                and snapshot.get("latest_action_type") == "delete"):
            intended_tombstone = str(
                snapshot.get("tombstone_audit_id") or "")
        if (existing_tombstone and intended_tombstone
                and existing_tombstone != intended_tombstone):
            return _refusal(
                canvas_id,
                "operation_id already used with different material or target",
                409,
                operation_id=operation_id,
                action_type="restore",
                tombstone_audit_id=existing_tombstone or None,
                source_audit_id=existing_source or None,
            )
        result = {
            "success": True,
            "already_applied": True,
            "replayed": True,
            "no_change": True,
            "write_outcome": "committed",
            "canvas_id": canvas_id,
            "audit_id": existing["audit_id"],
            "operation_id": operation_id,
            "action_type": "restore",
            "tombstone_audit_id": existing_tombstone or None,
            "restored_from_tombstone_id": existing_tombstone or None,
            "source_audit_id": existing_source or None,
            "content_sha256": existing_details.get("content_sha256"),
            "canvas_type": existing.get("canvas_type"),
            "message": "Canvas undelete already applied",
        }
        return await _lifecycle_envelope(
            action="canvas.undelete",
            result=result,
            canvas_id=canvas_id,
            operation_id=operation_id,
            tenant_id=authority_tenant,
            workspace_id=authority_workspace,
            actor_id=user_id,
            expected_operation_id=operation_id,
            expected_tombstone_audit_id=existing_tombstone,
            expected_source_audit_id=existing_source,
            expected_content_sha256=str(
                existing_details.get("content_sha256") or ""),
        )

    if (snapshot_available
            and snapshot.get("latest_action_type") != "delete"):
        return _refusal(
            canvas_id,
            "Canvas is not deleted",
            409,
            operation_id=operation_id,
            action_type="restore",
        )

    expected_tombstone = (
        str(tombstone_audit_id) if tombstone_audit_id
        else str(snapshot.get("tombstone_audit_id") or ""))
    expected_source = (
        str(source_audit_id) if source_audit_id
        else str(snapshot.get("source_audit_id") or ""))
    expected_digest = str(snapshot.get("content_sha256") or "")

    if (snapshot_available and tombstone_audit_id
            and str(tombstone_audit_id)
            != str(snapshot.get("tombstone_audit_id") or "")):
        return _refusal(
            canvas_id,
            "canvas tombstone changed since the undelete was planned",
            409,
            operation_id=operation_id,
            action_type="restore",
            tombstone_audit_id=snapshot.get("tombstone_audit_id"),
        )
    if (snapshot_available and source_audit_id
            and str(source_audit_id)
            != str(snapshot.get("source_audit_id") or "")):
        return _refusal(
            canvas_id,
            "canvas source content changed since the undelete was planned",
            409,
            operation_id=operation_id,
            action_type="restore",
            source_audit_id=snapshot.get("source_audit_id"),
        )
    if snapshot_available and not expected_source:
        return _refusal(
            canvas_id,
            "No content to restore",
            409,
            operation_id=operation_id,
            action_type="restore",
            tombstone_audit_id=expected_tombstone or None,
        )

    result = await restore_deleted_canvas(
        user_id=user_id,
        canvas_id=canvas_id,
        operation_id=operation_id,
        expected_tombstone_audit_id=(
            expected_tombstone or None),
        expected_source_audit_id=(expected_source or None),
        tenant_id=authority_tenant,
        workspace_id=authority_workspace,
        expected_actor_status=snapshot.get("actor_status"),
        expected_actor_is_active=snapshot.get("actor_is_active"),
        scope_required=True,
    )

    return await _lifecycle_envelope(
        action="canvas.undelete",
        result=result,
        canvas_id=canvas_id,
        operation_id=operation_id,
        tenant_id=authority_tenant,
        workspace_id=authority_workspace,
        actor_id=user_id,
        expected_operation_id=operation_id,
        expected_tombstone_audit_id=expected_tombstone,
        expected_source_audit_id=expected_source,
        expected_content_sha256=expected_digest,
    )

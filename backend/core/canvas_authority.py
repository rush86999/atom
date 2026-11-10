"""Shared authority adapter for specialized canvas families.

This is deliberately a thin adapter over the established Canvas CRUD
authority primitives in ``tools.canvas_crud_tool``:

* ``active_canvas_actor`` loads the current ``User`` row and freezes the
  active/status/tenant/workspace snapshot.
* ``canvas_lifecycle_scope_error`` applies the accepted ownership policy
  (creator OR historical co-editor authorship) and the canvas's authoritative
  tenant/workspace scope. It handles audit-only canvases, which legacy sheets
  and coding canvases may be.
* ``claim_canvas_actor`` conditionally binds the write transaction to that
  exact active User snapshot.
* An exact-target guarded no-op DML then freezes the Canvas row (or the
  authorized latest audit row for a legacy audit-only canvas) before the
  append. SQLite's ignored ``FOR UPDATE`` is not treated as a lock.

No canvas store, router, authentication engine or review lifecycle is added
here. Services call this adapter so direct tool calls cannot bypass the same
gate used by the public routes.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from tools.canvas_crud_tool import (
    active_canvas_actor,
    canvas_lifecycle_scope_error,
    claim_canvas_actor,
)


class CanvasAuthorityError(Exception):
    """A typed, fail-closed refusal before a canvas effect."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 403,
        code: str = "CANVAS_AUTHORITY_DENIED",
    ) -> None:
        super().__init__(message)
        self.status_code = int(status_code)
        self.code = str(code)


def _exact(column: Any, value: Any):
    """Exact raw-value predicate; NULL is distinct from empty and default."""
    if value is None:
        return column.is_(None)
    return column == str(value)


def require_active_actor(db: Any, user_id: Optional[str]) -> Dict[str, Any]:
    """Resolve the current active User snapshot or raise a typed refusal.

    There is no session-type escape hatch: an unreadable/unsupported session
    is a refusal, never a reason to skip authority.
    """
    actor = active_canvas_actor(db, user_id)
    if not actor.get("ok"):
        raise CanvasAuthorityError(
            str(actor.get("error") or "Acting user is not active"),
            status_code=int(actor.get("http_status") or 403),
            code="CANVAS_ACTOR_REFUSED",
        )
    # Raw actor fields stay untouched for the shared exact snapshot/claim.
    # Personal Edition resource lookup uses the documented NULL->default
    # fallback from the authoritative User row; never infer from target data.
    from core.models import Tenant
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    user = actor.get("user")
    effective_tenant = resolve_tenant_id(user)
    effective_workspace = resolve_workspace_id(user)
    if db.query(Tenant.id).filter(
            Tenant.id == effective_tenant).first() is None:
        raise CanvasAuthorityError(
            "Acting user's effective tenant is unavailable",
            status_code=403,
            code="CANVAS_ACTOR_SCOPE_MISSING",
        )
    return {
        **actor,
        "effective_tenant_id": effective_tenant,
        "effective_workspace_id": effective_workspace,
    }


def require_canvas_read(
    db: Any,
    canvas_id: str,
    actor: Dict[str, Any],
) -> None:
    """Apply the accepted owner/co-editor + current scope policy to a read."""
    error = canvas_lifecycle_scope_error(
        db,
        str(canvas_id),
        str(actor["id"]),
        actor.get("tenant_id"),
        actor.get("workspace_id"),
    )
    if error:
        raise CanvasAuthorityError(
            str(error.get("error") or f"Canvas {canvas_id} not found"),
            status_code=int(error.get("http_status") or 404),
            code="CANVAS_NOT_AUTHORIZED",
        )


def _latest_audit(db: Any, canvas_id: str):
    from sqlalchemy import desc

    from core.models import CanvasAudit

    return (
        db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == str(canvas_id))
        .order_by(desc(CanvasAudit.created_at), desc(CanvasAudit.id))
        .first()
    )


def _claim_canvas_target(
    db: Any,
    canvas_id: str,
    *,
    canvas: Any,
    latest: Any,
) -> None:
    """Freeze the authorized Canvas/audit snapshot with exact guarded DML.

    A Canvas-backed canvas uses the tenant/workspace/creator/status snapshot
    captured BEFORE the scope check. A legacy audit-only canvas uses the
    authorized latest audit row's exact id/tenant/author/type/action. The
    guarded no-op DML is the linearization point; a scope/material move after
    the check matches zero rows. A fresh read after the DML rejects a
    concurrent append so this writer never silently overwrites it.
    """
    from sqlalchemy import update

    from core.models import Canvas, CanvasAudit

    if canvas is not None:
        expected_creator = canvas.created_by
        expected_tenant = canvas.tenant_id
        expected_workspace = canvas.workspace_id
        expected_status = canvas.status
        statement = (
            update(Canvas)
            .where(
                Canvas.id == str(canvas_id),
                _exact(Canvas.tenant_id, expected_tenant),
                _exact(Canvas.workspace_id, expected_workspace),
                _exact(Canvas.created_by, expected_creator),
                _exact(Canvas.status, expected_status),
            )
            .values(status=Canvas.status)
        )
        with db.no_autoflush:
            result = db.execute(statement)
        if result.rowcount != 1:
            db.rollback()
            raise CanvasAuthorityError(
                "Canvas target changed before write",
                status_code=409,
                code="CANVAS_TARGET_CHANGED",
            )
        db.expire(canvas)
        fresh = db.query(Canvas).filter(Canvas.id == str(canvas_id)).first()
        if (
            fresh is None
            or fresh.created_by != expected_creator
            or fresh.tenant_id != expected_tenant
            or fresh.workspace_id != expected_workspace
            or fresh.status != expected_status
        ):
            db.rollback()
            raise CanvasAuthorityError(
                "Canvas target changed before write",
                status_code=409,
                code="CANVAS_TARGET_CHANGED",
            )
        return

    if latest is None:
        raise CanvasAuthorityError(
            f"Canvas {canvas_id} not found",
            status_code=404,
            code="CANVAS_NOT_FOUND",
        )
    expected_id = str(latest.id)
    expected_tenant = latest.tenant_id
    expected_user = latest.user_id
    expected_type = latest.canvas_type
    expected_action = latest.action_type
    statement = (
        update(CanvasAudit)
        .where(
            CanvasAudit.id == expected_id,
            CanvasAudit.canvas_id == str(canvas_id),
            _exact(CanvasAudit.tenant_id, expected_tenant),
            _exact(CanvasAudit.user_id, expected_user),
            _exact(CanvasAudit.canvas_type, expected_type),
            _exact(CanvasAudit.action_type, expected_action),
        )
        .values(action_type=CanvasAudit.action_type)
    )
    with db.no_autoflush:
        result = db.execute(statement)
    if result.rowcount != 1:
        db.rollback()
        raise CanvasAuthorityError(
            "Canvas target changed before write",
            status_code=409,
            code="CANVAS_TARGET_CHANGED",
        )
    fresh = _latest_audit(db, canvas_id)
    if fresh is None or str(fresh.id) != expected_id:
        db.rollback()
        raise CanvasAuthorityError(
            "Canvas target changed before write",
            status_code=409,
            code="CANVAS_TARGET_CHANGED",
        )


def require_canvas_write(
    db: Any,
    canvas_id: str,
    actor: Dict[str, Any],
) -> None:
    """Authorize, claim the actor, then freeze the exact target before append."""
    from core.models import Canvas

    # Capture the target BEFORE the scope check. The guarded DML below binds
    # the write to this exact snapshot; a move committed after the check
    # matches zero rows. Never re-read a moved target and call it authorized.
    canvas = db.query(Canvas).filter(Canvas.id == str(canvas_id)).first()
    latest = None if canvas is not None else _latest_audit(db, canvas_id)
    error = canvas_lifecycle_scope_error(
        db,
        str(canvas_id),
        str(actor["id"]),
        actor.get("tenant_id"),
        actor.get("workspace_id"),
    )
    if error:
        raise CanvasAuthorityError(
            str(error.get("error") or f"Canvas {canvas_id} not found"),
            status_code=int(error.get("http_status") or 404),
            code="CANVAS_NOT_AUTHORIZED",
        )
    if not claim_canvas_actor(db, actor):
        db.rollback()
        raise CanvasAuthorityError(
            "Actor authority changed before canvas write",
            status_code=409,
            code="CANVAS_AUTHORITY_CHANGED",
        )
    _claim_canvas_target(db, canvas_id, canvas=canvas, latest=latest)


def claim_active_actor(db: Any, actor: Dict[str, Any]) -> None:
    """Conditionally claim the exact active User snapshot before an insert."""
    if not claim_canvas_actor(db, actor):
        db.rollback()
        raise CanvasAuthorityError(
            "Actor authority changed before canvas write",
            status_code=409,
            code="CANVAS_AUTHORITY_CHANGED",
        )


def reserve_canvas_id(
    db: Any,
    *,
    canvas_id: str,
    actor: Dict[str, Any],
    title: str,
    canvas_type: str,
) -> None:
    """Atomically reserve a new canvas id through the existing Canvas table.

    The Canvas primary key is the uniqueness arbiter for concurrent same-id
    creates. A pre-check gives a clean typed conflict for an id that exists
    only in the audit trail; the flush makes the concurrent same-id race
    atomic. No new table or id registry is introduced.
    """
    from sqlalchemy.exc import IntegrityError

    from core.models import Canvas, CanvasAudit

    existing = (
        db.query(Canvas.id).filter(Canvas.id == str(canvas_id)).first()
        or db.query(CanvasAudit.id)
        .filter(CanvasAudit.canvas_id == str(canvas_id))
        .first()
    )
    if existing is not None:
        raise CanvasAuthorityError(
            f"Canvas id {canvas_id} already exists",
            status_code=409,
            code="CANVAS_ID_CONFLICT",
        )
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    effective_tenant = (
        actor.get("effective_tenant_id")
        or resolve_tenant_id(actor.get("user"))
    )
    effective_workspace = (
        actor.get("effective_workspace_id")
        or resolve_workspace_id(actor.get("user"))
    )
    db.add(
        Canvas(
            id=str(canvas_id),
            tenant_id=str(effective_tenant),
            workspace_id=str(effective_workspace),
            created_by=str(actor["id"]),
            name=str(title or "Canvas"),
            canvas_type=str(canvas_type),
            status="active",
        )
    )
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise CanvasAuthorityError(
            f"Canvas id {canvas_id} already exists",
            status_code=409,
            code="CANVAS_ID_CONFLICT",
        ) from exc

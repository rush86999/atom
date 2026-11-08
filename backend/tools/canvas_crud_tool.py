"""
Canvas CRUD tools — read, update, delete for ALL canvas types.

Previously only Create (present_*) worked for all types. Read was missing,
Update existed only for docs, and Delete was broken (closed by user_id, not
canvas_id). This module provides generic CRUD that works across all 7 canvas
types using the CanvasAudit append-only trail as the source of truth (same
pattern as canvas_docs_tool.update_docs_canvas).

Every canvas interaction (present/read/update/delete) writes a CanvasAudit
row, so the full lifecycle is auditable and episodes can capture it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.chat_session_context import audit_agent_id, audit_session_id

logger = logging.getLogger(__name__)


# Canvas-audit action types that record an EVENT on a canvas rather than
# AUTHORSHIP of it. ``submit`` lands here: a public/shared form canvas accepts
# submissions from users who do not own it (api/canvas_routes.py::submit_canvas
# appends the caller's user_id with no ownership check), so such a row proves
# interaction, not ownership. It must therefore never be accepted as an
# ownership claim — nor as grounds for listing the canvas in the submitter's
# gallery (see list_canvases).
_EVENT_ONLY_ACTIONS = ("submit",)

#: ``write_outcome`` — did the call CHANGE the canvas? See
#: `update_canvas_content`'s docstring for why a `success: False` is not
#: evidence of a zero effect, and why only ``WRITE_NOT_ATTEMPTED`` may be
#: reported to a user as "nothing was changed".
WRITE_NOT_ATTEMPTED = "not_attempted"
WRITE_COMMITTED = "committed"
WRITE_UNKNOWN = "unknown"


def _verify_canvas_owner(db, canvas_id: str, user_id: str) -> bool:
    """Return True if ``canvas_id`` exists and belongs to ``user_id``.

    Guards against IDOR: the canvas CRUD functions previously queried by
    canvas_id only, so any authenticated user could read/modify/delete another
    user's canvas by guessing the id.

    Ownership is established by EITHER source of record:
      * ``Canvas.created_by`` — the authoritative creator (NOT NULL), and/or
      * ``CanvasAudit.user_id`` — the acting user, for any action that records
        authorship (create / update / present / restore / fork / mini_app_* …).

    Both are needed because the two are legitimately different users: the
    gallery lists every canvas the user has an audit row on, and a canvas
    CREATED by one user can then be EDITED by another (canvas co-editing; the
    office ``/present`` flow persists ONE Canvas row per file and every later
    presenter edits that same row). Trusting only ``created_by`` whenever a
    Canvas row existed made those canvases 404 on read/update/delete while the
    gallery kept listing them — live 2026-09-10: ``canvas_formulacheck01``
    (created_by a test member, newest audit row the admin) 404'd on GET and on
    the gallery's DELETE.

    Agent-created canvases (present_markdown & friends) historically write
    ONLY a CanvasAudit row — no Canvas row exists for them — and are covered by
    the same audit-trail branch.

    Event-only rows (``_EVENT_ONLY_ACTIONS``) are ignored, so a form submitter
    gains nothing. IDOR protection is otherwise unchanged: a user with neither
    a matching Canvas row nor an authoring audit row is still denied.
    """
    from core.models import Canvas, CanvasAudit

    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if canvas is not None and canvas.created_by == user_id:
        return True

    authorship = (
        db.query(CanvasAudit)
        .filter(
            CanvasAudit.canvas_id == canvas_id,
            CanvasAudit.user_id == user_id,
            CanvasAudit.action_type.notin_(_EVENT_ONLY_ACTIONS),
        )
        .first()
    )
    return authorship is not None


def _scope_allows(scope_value: Any, principal_value: Any) -> bool:
    """Whether a canvas/audit scope admits the authenticated principal.

    An unscoped canvas (NULL/empty scope) is legacy and remains available to
    an authorized same-tenant editor. A real canvas scope admits only an exact
    principal match. A principal with no workspace/tenant claim is treated as
    the legacy ``default`` scope ONLY when the canvas itself is unscoped or
    ``default`` — a real foreign scope is never silently mapped into default.
    """
    scope = str(scope_value or "").strip()
    principal = str(principal_value or "").strip()
    if not scope:
        return True
    if principal:
        return scope == principal
    return scope.lower() == "default"


def canvas_write_scope_error(
    db,
    canvas_id: str,
    user_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    target_audit_id: Optional[str] = None,
    lock: bool = False,
) -> Optional[Dict[str, Any]]:
    """Return a pre-effect refusal for an out-of-scope canvas write.

    Read-only. The direct HTTP service calls this before dispatch and the
    writer calls it again inside the mutation transaction, so a separate
    preflight cannot create a TOCTOU window. Ownership is still the first
    gate; creator/audit authorship is not a cross-tenant or cross-workspace
    grant.

    The authoritative Canvas row carries the scope. A target audit (restore)
    must belong to the same canvas and tenant. New audit rows are stamped with
    the Canvas tenant, never a foreign audit's tenant.
    """
    from core.models import Canvas, CanvasAudit
    from sqlalchemy import desc

    canvas_query = db.query(Canvas).filter(Canvas.id == canvas_id)
    if lock:
        # Bind the scope decision to the same row version the append commits
        # against. SQLite ignores FOR UPDATE; PostgreSQL takes the row lock.
        canvas_query = canvas_query.with_for_update()
    canvas = canvas_query.first()
    if canvas is None:
        return {"http_status": 404, "error": f"Canvas {canvas_id} not found"}
    if not _verify_canvas_owner(db, canvas_id, user_id):
        return {"http_status": 404, "error": f"Canvas {canvas_id} not found"}

    if not _scope_allows(canvas.tenant_id, tenant_id):
        return {
            "http_status": 403,
            "error": "Canvas belongs to a different tenant",
        }
    if not _scope_allows(canvas.workspace_id, workspace_id):
        return {
            "http_status": 403,
            "error": "Canvas belongs to a different workspace",
        }

    latest = (
        db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas_id)
        .order_by(desc(CanvasAudit.created_at), desc(CanvasAudit.id))
        .first()
    )
    if latest is None:
        return {"http_status": 404, "error": f"Canvas {canvas_id} not found"}

    if target_audit_id:
        target = (
            db.query(CanvasAudit)
            .filter(
                CanvasAudit.id == str(target_audit_id),
                CanvasAudit.canvas_id == canvas_id,
            )
            .first()
        )
        if target is None:
            return {"http_status": 404, "error": "Version not found"}
        if not _scope_allows(target.tenant_id, canvas.tenant_id):
            return {
                "http_status": 403,
                "error": "Version belongs to a different tenant",
            }
    return None


def _latest_canvas_audit(db, canvas_id: str, *, lock: bool = False):
    """Newest audit row, with the same ``created_at, id`` tiebreak every
    other canvas read uses.

    Delete/undelete historically ordered by ``created_at`` only, so a
    legacy same-second tie could pick the wrong state. The order is part of
    the lifecycle contract now, not an accident of UUID ordering.
    """
    from core.models import CanvasAudit
    from sqlalchemy import desc

    query = db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id)
    if lock:
        query = query.with_for_update()
    return query.order_by(
        desc(CanvasAudit.created_at), desc(CanvasAudit.id)).first()


def latest_canvas_content_audit(db, canvas_id: str):
    """Newest non-delete row that actually carries a canvas body.

    Contentless event rows (``email_send`` / ``email_send_attempt``) append
    after the real revision. The lifecycle source row must be the same one
    ``read_canvas`` would serve, or undelete would restore an event stamp
    instead of the user's content.
    """
    from core.models import CanvasAudit
    from sqlalchemy import desc

    try:
        rows = (
            db.query(CanvasAudit)
            .filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.action_type.notin_(
                    ("delete",) + _EVENT_ONLY_ACTIONS),
            )
            .order_by(desc(CanvasAudit.created_at), desc(CanvasAudit.id))
            .limit(50)
            .all()
        )
    except Exception:  # noqa: BLE001 - a legacy shape has no content row
        return None
    for row in rows or []:
        details = row.details_json or {}
        if _audit_content(details) is not None:
            return row
    return None


def _audit_content(details: Any) -> Any:
    """Body from audit details, preserving falsy-but-valid values."""
    if not isinstance(details, dict):
        return None
    for key in ("content", "data"):
        if key in details and details[key] is not None:
            return details[key]
    return None


def canvas_lifecycle_scope_error(
    db,
    canvas_id: str,
    user_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    *,
    lock: bool = False,
) -> Optional[Dict[str, Any]]:
    """Scope gate for the delete/undelete lifecycle writers.

    The accepted update/restore gate (``canvas_write_scope_error``) assumes a
    ``Canvas`` mirror exists. Agent-created canvases are audit-only, so the
    lifecycle gate must authorize those against the newest audit tenant
    instead of 404-ing a supported path. The rules are otherwise the same:

    * ownership is still the FIRST gate (creator or historical co-editor);
    * a Canvas-backed canvas is authorized against its current
      tenant/workspace snapshot (``_scope_allows`` incl. Personal null/default);
    * an audit-only canvas is authorized against the newest audit tenant and
      its workspace is legacy/unqualified — never a foreign-scope grant.
    """
    from core.models import Canvas

    canvas_query = db.query(Canvas).filter(Canvas.id == canvas_id)
    if lock:
        canvas_query = canvas_query.with_for_update()
    canvas = canvas_query.first()

    if not _verify_canvas_owner(db, canvas_id, user_id):
        return {"http_status": 404, "error": f"Canvas {canvas_id} not found"}

    latest = _latest_canvas_audit(db, canvas_id, lock=lock)
    if latest is None:
        return {"http_status": 404, "error": f"Canvas {canvas_id} not found"}

    if canvas is not None:
        if not _scope_allows(canvas.tenant_id, tenant_id):
            return {
                "http_status": 403,
                "error": "Canvas belongs to a different tenant",
            }
        if not _scope_allows(canvas.workspace_id, workspace_id):
            return {
                "http_status": 403,
                "error": "Canvas belongs to a different workspace",
            }
        return None

    # Audit-only canvas: the newest audit tenant is the only scope evidence.
    # A workspace claim cannot be checked against a row that has no workspace
    # column, so it is recorded as legacy rather than treated as a grant.
    if not _scope_allows(latest.tenant_id, tenant_id):
        return {
            "http_status": 403,
            "error": "Canvas belongs to a different tenant",
        }
    return None


def canvas_lifecycle_snapshot(
    db,
    canvas_id: str,
    user_id: str,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Read-only identity/material snapshot frozen before a lifecycle write.

    The service uses this to bind one logical operation to the exact scope,
    prior row, tombstone and source content before dispatch. The writer
    repeats every check inside its own transaction; this snapshot is not
    authority, only the expectation the verifier will grade.
    """
    from core.models import Canvas
    from core.oracle.postcondition_verifiers import canvas_content_digest

    scope_error = canvas_lifecycle_scope_error(
        db, canvas_id, user_id, tenant_id, workspace_id)
    if scope_error:
        return scope_error

    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    latest = _latest_canvas_audit(db, canvas_id)
    if latest is None:
        return {"http_status": 404, "error": f"Canvas {canvas_id} not found"}

    latest_details = latest.details_json or {}
    if not isinstance(latest_details, dict):
        latest_details = {}
    source = latest_canvas_content_audit(db, canvas_id)
    source_details = (
        source.details_json or {} if source is not None else {})
    if not isinstance(source_details, dict):
        source_details = {}
    content = _audit_content(source_details)
    try:
        digest = (
            canvas_content_digest(content) if content is not None else "")
    except Exception:  # noqa: BLE001 - unreadable material is missing proof
        digest = ""

    is_tombstone = str(latest.action_type or "") == "delete"
    return {
        "canvas_id": canvas_id,
        "mirror": canvas is not None,
        "canvas_tenant_id": str(
            getattr(canvas, "tenant_id", "") or "") if canvas is not None else "",
        "canvas_workspace_id": str(
            getattr(canvas, "workspace_id", "") or "") if canvas is not None else "",
        "authoritative_tenant_id": str(
            (getattr(canvas, "tenant_id", None) if canvas is not None else None)
            or latest.tenant_id or ""),
        "latest_audit_id": str(latest.id),
        "latest_action_type": str(latest.action_type or ""),
        "tombstone_audit_id": str(latest.id) if is_tombstone else "",
        "tombstone_prior_audit_id": (
            str(latest_details.get("prior_audit_id") or "")
            if is_tombstone else ""),
        "tombstone_source_audit_id": (
            str(latest_details.get("source_audit_id") or "")
            if is_tombstone else ""),
        "tombstone_content_sha256": (
            str(latest_details.get("content_sha256") or "")
            if is_tombstone else ""),
        "tombstone_operation_id": (
            str(latest_details.get("operation_id") or "")
            if is_tombstone else ""),
        "source_audit_id": str(source.id) if source is not None else "",
        "content_sha256": digest,
        "canvas_type": str(
            latest.canvas_type
            or (getattr(source, "canvas_type", None) if source is not None else None)
            or "generic"),
        "title": source_details.get("title") if source is not None else None,
    }


def _audit_scope_claim_cas(
    db,
    canvas_id: str,
    expected_audit_id: str,
    expected_tenant: Any,
) -> bool:
    """Bind an audit-only lifecycle append to the authorized audit row.

    There is no Canvas mirror to lock, so the newest authorized audit row is
    the reservation: a same-tenant move that replaced it (or a foreign tenant
    stamp) makes the guarded DML match zero rows and the caller rolls back
    before effect.
    """
    from sqlalchemy import update

    from core.models import CanvasAudit

    statement = (
        update(CanvasAudit)
        .where(
            CanvasAudit.id == str(expected_audit_id),
            CanvasAudit.canvas_id == canvas_id,
            CanvasAudit.tenant_id == str(expected_tenant or ""),
        )
        .values(action_type=CanvasAudit.action_type)
    )
    with db.no_autoflush:
        result = db.execute(statement)
        if result.rowcount != 1:
            db.rollback()
            return False
    return True


def deleted_canvas_ids(db, canvas_ids) -> set:
    """Subset of ``canvas_ids`` whose NEWEST audit row is a delete tombstone.

    The delete path is append-only (``delete_canvas``), so a deleted canvas
    keeps ``Canvas.status == "active"`` and is recognizable ONLY by the latest
    row of its trail (``restore_deleted_canvas`` appends past the tombstone).
    Callers that touch a canvas outside this module — the office file→canvas
    fan-out, office canvas reuse — must consult this, or they silently
    un-delete a canvas the user removed: live 2026-09-10, the duplicate office
    canvas ``canvas_c7b3491aebf8`` was deleted at 13:46:10 and an agent file
    edit appended an "update" row at 14:04:10, putting the card back in the
    gallery.

    One grouped query, dialect-portable (no window function needed); the
    created_at/id ordering matches ``list_canvases``' newest-row tiebreak.
    """
    wanted = [cid for cid in canvas_ids if cid]
    if not wanted:
        return set()

    from core.models import CanvasAudit
    from sqlalchemy import desc

    rows = (
        db.query(CanvasAudit.canvas_id, CanvasAudit.action_type)
        .filter(CanvasAudit.canvas_id.in_(wanted))
        .order_by(
            CanvasAudit.canvas_id,
            desc(CanvasAudit.created_at),
            desc(CanvasAudit.id),
        )
        .all()
    )
    newest: Dict[str, str] = {}
    for canvas_id, action_type in rows:
        newest.setdefault(canvas_id, action_type)
    return {cid for cid, action in newest.items() if action == "delete"}


async def read_canvas(
    user_id: str,
    canvas_id: str,
) -> Dict[str, Any]:
    """Read the current content/state of a canvas by ID.

    Reads the latest CanvasAudit row for the canvas (the audit trail IS the
    source of truth). Returns the content, canvas_type, and metadata.

    Args:
        user_id: User requesting the action
        canvas_id: The canvas ID (from a previous present_* call)
    """
    try:
        from core.database import get_db_session
        from core.models import Canvas, CanvasAudit
        from sqlalchemy import desc

        with get_db_session() as db:
            # IDOR guard: only the owner may read this canvas.
            if not _verify_canvas_owner(db, canvas_id, user_id):
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            audit = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).order_by(
                desc(CanvasAudit.created_at), desc(CanvasAudit.id),
            ).first()

            if not audit:
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            # Skip if the latest action was a delete.
            if audit.action_type == "delete":
                return {"success": False, "error": "Canvas has been deleted", "deleted": True}

            content_audit = audit
            details = audit.details_json or {}
            audit_canvas_type = audit.canvas_type
            # Preserve falsy-but-valid content ("" / [] / 0): the old `or`
            # chain replaced empty content with the whole details dict, so an
            # empty doc/email body came back as {"title": ..., "content": ...}
            # instead of the empty string.
            raw_content = details.get("content")
            if raw_content is None:
                raw_content = details.get("data")
            if raw_content is None and not (
                "content" in details or "data" in details
            ):
                # The latest row carries no body key — but that row may be an
                # EVENT stamp, not the content history: email_send /
                # email_send_attempt rows (canvas_email_service.record_send)
                # append after every send without content. Falling back
                # straight to the Canvas.content column here served the
                # creation-era snapshot and made the real draft vanish after
                # any send attempt (observed 2026-08-31). The audit trail is
                # the content history: scan back to the latest row that
                # actually carries a body.
                content_rows = (
                    db.query(CanvasAudit)
                    .filter(
                        CanvasAudit.canvas_id == canvas_id,
                        CanvasAudit.created_at < audit.created_at,
                    )
                    .order_by(desc(CanvasAudit.created_at))
                    .limit(10)
                    .all()
                )
                for row in content_rows:
                    row_details = row.details_json or {}
                    if "content" in row_details:
                        raw_content = row_details.get("content")
                    elif "data" in row_details:
                        raw_content = row_details.get("data")
                    else:
                        continue
                    # The event row carries no title/type of its own — the
                    # content row is the provenance for both. A type pin on
                    # the NEWEST row still outranks the older row's choice.
                    details = {
                        **row_details,
                        **({"type_pinned": details["type_pinned"]} if details.get("type_pinned") else {}),
                    }
                    audit_canvas_type = row.canvas_type
                    content_audit = row
                    break
            if raw_content is None and "content" not in details and "data" not in details:
                # No content-bearing row in the recent history either —
                # legacy canvas whose body lives only on the Canvas row.
                # Fall back to the Canvas.content column so the page renders
                # the document instead of showing the details
                # metadata ({source, title}) as if it were the body.
                canvas_row = db.query(Canvas).filter(Canvas.id == canvas_id).first()
                if canvas_row is not None and canvas_row.content is not None:
                    raw_content = canvas_row.content
                    content_audit = None
            content = raw_content if raw_content is not None else details

            # EMAIL DRAFT-STATE READ (2026-10-03, the taught-employee job
            # step 7): EmailCanvasService.save_draft appends a save_draft
            # audit whose `content` is the EMPTY draft shell while the
            # real body lives under details["draft"]["body"]. Serving that
            # shell made every agent turn see an empty draft on any
            # panel-typical email canvas (the Halton quote: the employee
            # answered "the quote isn't in front of me" for a fully seeded
            # quote). Read shape, not history: when the served content is
            # a blank email body and the draft carries the actual body,
            # the draft IS the content.
            try:
                _draft = details.get("draft")
                if (
                    isinstance(content, dict)
                    and isinstance(_draft, dict)
                    and isinstance(content.get("body"), str)
                    and not content.get("body").strip()
                    and str(_draft.get("body") or "").strip()
                ):
                    content = {
                        **content,
                        "body": _draft.get("body"),
                        "subject": content.get("subject")
                        or _draft.get("subject")
                        or "",
                        "to": content.get("to")
                        or ", ".join(_draft.get("to_emails") or []),
                    }
            except Exception:  # noqa: BLE001 — read normalization only
                pass

            # Office snapshot refresh: a pre-upgrade workbook snapshot can
            # carry a truncated sheet array with no dimensions. The file is
            # authoritative — re-read it once and return the complete used
            # range instead of trusting the stale display window forever.
            try:
                if (isinstance(content, dict)
                        and content.get("office_file")
                        and str(content.get("format") or "").lower() in ("xlsx", "xlsm")
                        and not content.get("sheets_complete")):
                    from core.office_sync_service import OfficeSyncService

                    fresh = OfficeSyncService._read_structured_content(
                        str(content["office_file"]))
                    if fresh:
                        content = {**content, **fresh}
            except Exception as office_err:  # noqa: BLE001 — read fallback only
                logger.debug(f"office snapshot refresh skipped: {office_err}")

            # Email-draft normalization: canvases created before the
            # classifier existed (and EmailCanvasService's draft-details
            # shape) render on /canvas/{id} as documents/raw JSON with no
            # To/Subject fields or Send button. The audit trail stays
            # append-only — the read normalizes the shape, it never
            # rewrites history. A user-pinned type (manual retype in the
            # UI) is exempt: their choice outranks the classifier, forever.
            from core.chat_draft_classifier import coerce_email_canvas

            if details.get("type_pinned"):
                canvas_type = audit.canvas_type
            else:
                canvas_type, content = coerce_email_canvas(audit_canvas_type, content)

            return {
                "success": True,
                "canvas_id": canvas_id,
                "canvas_type": canvas_type,
                "content": content,
                "title": details.get("title"),
                "action_type": audit.action_type,
                "audit_id": content_audit.id if content_audit else None,
                "operation_id": (details or {}).get("operation_id"),
                "review_status": (details or {}).get("review_status", "unknown"),
                "created_at": (
                    content_audit.created_at.isoformat()
                    if content_audit and content_audit.created_at else None
                ),
            }
    except Exception as e:
        logger.error(f"Canvas read failed: {e}")
        return {"success": False, "error": str(e)}


def _operation_audit_row(db: Any, canvas_id: str, operation_id: str):
    from core.models import CanvasAudit
    from sqlalchemy import desc

    try:
        from core.sql_json import json_field_equals

        predicate = json_field_equals(
            db, CanvasAudit.details_json, "$.operation_id", operation_id)
        query = db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id,
        )
        if predicate is not None:
            query = query.filter(predicate)
        return query.order_by(
            desc(CanvasAudit.created_at), desc(CanvasAudit.id),
        ).first()
    except Exception:
        try:
            rows = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).all()
            for row in rows or []:
                details = row.details_json or {}
                if details.get("operation_id") == operation_id:
                    return row
        except Exception:
            return None
    return None


def find_operation_audit(db: Any, canvas_id: str, operation_id: str):
    """Public lookup for the direct verified-write service."""
    return _operation_audit_row(db, canvas_id, operation_id)


def find_operation_audits(
    db: Any, canvas_id: str, operation_id: str,
) -> List[Any]:
    """ALL audit rows carrying one logical operation id, newest first.

    A logical operation id must name one durable event. Duplicate rows for
    one key are ambiguous identity, not a replay: callers fail closed rather
    than certifying whichever row happens to sort first.
    """
    from core.models import CanvasAudit
    from sqlalchemy import desc

    try:
        from core.sql_json import json_field_equals

        predicate = json_field_equals(
            db, CanvasAudit.details_json, "$.operation_id", operation_id)
        query = db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id)
        if predicate is not None:
            query = query.filter(predicate)
        return query.order_by(
            desc(CanvasAudit.created_at), desc(CanvasAudit.id)).all() or []
    except Exception:
        try:
            rows = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).all()
            matches = []
            for row in rows or []:
                details = row.details_json or {}
                if (isinstance(details, dict)
                        and details.get("operation_id") == operation_id):
                    matches.append(row)
            matches.sort(
                key=lambda row: (
                    str(getattr(row, "created_at", "") or ""),
                    str(getattr(row, "id", "") or "")),
                reverse=True)
            return matches
        except Exception:
            return []


def canonical_update_content(
    latest: Any,
    requested_type: Optional[str],
    content: Any,
    manual_retype: bool = False,
):
    """Resolve the content the update tool will persist.

    ONE representation shared by the writer and the direct-HTTP verifier.
    The type rules are the tool's established rules: manual retype wins and
    pins; an existing pin survives; a generic request preserves the canvas's
    own type; otherwise the same email coercion runs. Returns
    ``(canvas_type, content)``.
    """
    latest_details = dict(getattr(latest, "details_json", None) or {})
    latest_type = getattr(latest, "canvas_type", None)
    requested = (requested_type or "").strip().lower()
    if manual_retype:
        return requested or "generic", content
    if latest_details.get("type_pinned"):
        return latest_type, content
    if requested in ("", "generic") and latest_type:
        canvas_type = latest_type
    else:
        canvas_type = requested
    from core.chat_draft_classifier import coerce_email_canvas

    return coerce_email_canvas(canvas_type, content)


def _scope_cas_predicates(
    canvas_id: str,
    expected_tenant: Any,
    expected_workspace: Any,
):
    """Database predicates matching the authorized canvas scope snapshot.

    Mirrors ``_scope_allows`` exactly, including the legacy null/default
    policy. A scope move after the authorization read makes the guarded DML
    match zero rows instead of writing into the new scope.
    """
    from sqlalchemy import or_

    from core.models import Canvas

    tenant = str(expected_tenant or "").strip()
    workspace = str(expected_workspace or "").strip()
    predicates = [Canvas.id == canvas_id]
    # Bind the EXACT snapshot value. Authorization treats a null/empty scope
    # as legacy/default, but a concurrent move between null, empty and
    # "default" is still a scope move and must match zero rows.
    if tenant:
        predicates.append(Canvas.tenant_id == tenant)
    else:
        predicates.append(or_(
            Canvas.tenant_id.is_(None),
            Canvas.tenant_id == "",
        ))
    if workspace:
        predicates.append(Canvas.workspace_id == workspace)
    else:
        predicates.append(or_(
            Canvas.workspace_id.is_(None),
            Canvas.workspace_id == "",
        ))
    return predicates


def _scope_claim_cas(
    db: Any,
    canvas_row: Any,
    canvas_id: str,
    expected_tenant: Any,
    expected_workspace: Any,
) -> bool:
    """Acquire the write reservation under the authorized scope.

    Used when the review is not mirrored (pending review): the no-op guarded
    UPDATE still binds the transaction to the scope snapshot and gives SQLite
    its write reservation. Zero matches means the scope moved after the final
    check; the caller rolls back and refuses before effect.
    """
    from sqlalchemy import update

    from core.models import Canvas

    statement = (
        update(Canvas)
        .where(*_scope_cas_predicates(
            canvas_id, expected_tenant, expected_workspace))
        .values(last_edited_at=Canvas.last_edited_at)
    )
    with db.no_autoflush:
        result = db.execute(statement)
        if result.rowcount != 1:
            db.rollback()
            return False
        if canvas_row is not None and canvas_row in db:
            db.expire(canvas_row)
    return True


def _mirror_accepted_canvas_cas(
    db: Any,
    canvas_row: Any,
    canvas_id: str,
    content: Any,
    canvas_type: str,
    title: Optional[str],
    user_id: str,
    expected_tenant: Any,
    expected_workspace: Any,
) -> bool:
    """Conditional accepted-mirror write bound to the authorized scope.

    The guarded UPDATE is the transaction's linearization point: a scope move
    committed after the final check makes it match zero rows, so the pending
    audit/mirror work is rolled back and the caller refuses before effect.
    """
    from datetime import datetime, timezone

    from sqlalchemy import update

    from core.models import Canvas

    values: Dict[str, Any] = {
        "content": content,
        "last_edited_by": user_id,
        "last_edited_at": datetime.now(timezone.utc),
    }
    if canvas_type:
        values["canvas_type"] = canvas_type
    if title:
        values["name"] = title
    statement = (
        update(Canvas)
        .where(*_scope_cas_predicates(
            canvas_id, expected_tenant, expected_workspace))
        .values(**values)
    )
    with db.no_autoflush:
        result = db.execute(statement)
        if result.rowcount != 1:
            db.rollback()
            return False
        if canvas_row is not None and canvas_row in db:
            db.expire(canvas_row)
    return True


def canonical_restore_content(latest: Any, target: Any):
    """Resolve the content a restore will persist.

    ONE representation shared by the restore writer and the postcondition
    verifier: a pinned current canvas keeps its type and raw target content;
    otherwise the target's own type (falling back to the current type) goes
    through the same email coercion as a read/update. Returns
    ``(canvas_type, content)``.
    """
    target_details = dict(getattr(target, "details_json", None) or {})
    latest_details = dict(getattr(latest, "details_json", None) or {})
    content = target_details.get("content", target_details.get("data"))
    if latest_details.get("type_pinned"):
        return getattr(latest, "canvas_type", None), content
    canvas_type = (
        getattr(target, "canvas_type", None)
        or getattr(latest, "canvas_type", None)
        or "generic")
    from core.chat_draft_classifier import coerce_email_canvas

    return coerce_email_canvas(canvas_type, content)


def _mirror_accepted_canvas(
    db: Any,
    canvas_id: str,
    content: Any,
    canvas_type: str,
    title: Optional[str],
    user_id: str,
) -> None:
    from datetime import datetime, timezone
    from core.models import Canvas

    row = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if row is None:
        return
    row.content = content
    if canvas_type:
        row.canvas_type = canvas_type
    if title:
        row.name = title
    row.last_edited_by = user_id
    row.last_edited_at = datetime.now(timezone.utc)


async def update_canvas_content(
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
    scope_required: bool = False,
    bind_operation_material: bool = False,
    pending_review: bool = False,
    evidence_refs: Optional[List[str]] = None,
    postconditions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Update the content of an existing canvas.

    Reads the latest CanvasAudit, merges the new content, and appends a new
    CanvasAudit row with action_type="update". Also broadcasts a WS update
    so the frontend reflects the change immediately.

    Works for ALL canvas types (sheets, email, docs, coding, terminal, etc.)
    — generalizes the docs-only update pattern.

    ``write_outcome`` — DID THIS CALL CHANGE ANYTHING?
    Every return carries it, because a `success: False` here is NOT evidence
    that the canvas is untouched, and callers turn exactly that into user-facing
    text ("the store refused, nothing was changed"). The append happens inside a
    context manager that commits on clean exit, and everything after the commit
    (refresh, the exit commit, the broadcast) can still raise — and an exception
    there is reported as a refusal while the row is already durable. So the store
    states which of three things happened:

      ``not_attempted``  refused before the append (IDOR, missing canvas,
                         deleted canvas, revision conflict). VERIFIED zero effect.
      ``committed``      the append is durable. VERIFIED.
      ``unknown``        the append was attempted and the outcome cannot be
                         established from here — a commit that raised (a lost
                         connection after the server committed is the classic
                         case) or a post-commit failure.

    Only ``not_attempted`` may be reported to a user as "nothing was changed".

    Args:
        user_id: User requesting the action
        canvas_id: The canvas ID to update
        content: New content (type depends on canvas_type)
        canvas_type: Canvas type (default "generic")
        title: Optional new title
        manual_retype: True when a HUMAN switched the canvas type in the UI
            (the escape hatch for a wrong classifier guess). Pins the choice
            into the audit row (``details.type_pinned``) and skips email
            coercion so the manual type survives every later read/save.
        operation_id: Optional stable id for the LOGICAL operation this
            write belongs to (e.g. a background turn continuation). Stamped
            into ``details_json.operation_id`` so "did THIS operation
            already land?" is a definitive audit query, not a timestamp
            inference (review 2026-09-22: audit timestamps are not
            idempotency keys).
        expected_prior_audit_id: Optional optimistic-concurrency token —
            the audit row id the caller planned against. Checked against
            the LATEST audit row inside this same DB session, immediately
            before the append: a mismatch means the canvas moved during the
            caller's planning/retry window and the write is REFUSED
            with a conflict marker instead of overwriting concurrent
            edits.
        pending_review: Optional review state for an agent proposal. Pending
            content remains readable from the audit trail but is not mirrored
            into the accepted ``canvases.content`` snapshot.
    """
    #: See the docstring. Advanced on the way to the commit and after it, so the
    #: except branch can distinguish "never tried" from "tried, outcome unknown".
    write_outcome = WRITE_NOT_ATTEMPTED
    try:
        from core.database import get_db_session
        from core.models import Canvas, CanvasAudit
        from sqlalchemy import desc

        with get_db_session() as db:
            # Snapshot the authorized scope BEFORE the final check. The
            # guarded UPDATE below binds the effect to this snapshot; a move
            # committed after the check must match zero rows.
            canvas_row = (
                db.query(Canvas).filter(Canvas.id == canvas_id).first()
            )
            expected_tenant = (
                str(canvas_row.tenant_id or "")
                if canvas_row is not None else "")
            expected_workspace = (
                str(canvas_row.workspace_id or "")
                if canvas_row is not None else "")
            if scope_required:
                # Authoritative scope gate in the SAME transaction as the
                # append. The conditional write below is the linearization
                # point; this check rejects a move already visible here.
                scope_error = canvas_write_scope_error(
                    db, canvas_id, user_id, tenant_id, workspace_id,
                    lock=True)
                if scope_error:
                    return {
                        "success": False,
                        "write_outcome": write_outcome,
                        **scope_error,
                    }
            elif not _verify_canvas_owner(db, canvas_id, user_id):
                # IDOR guard: only the owner may update this canvas.
                return {"success": False, "write_outcome": write_outcome,
                        "error": f"Canvas {canvas_id} not found"}

            # Read the latest audit row for this canvas.
            latest = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).order_by(
                desc(CanvasAudit.created_at), desc(CanvasAudit.id),
            ).first()

            if not latest:
                return {"success": False, "write_outcome": write_outcome,
                        "error": f"Canvas {canvas_id} not found"}

            if latest.action_type == "delete":
                return {"success": False, "write_outcome": write_outcome,
                        "error": "Cannot update a deleted canvas"}

            # Type resolution is shared with the direct-HTTP verifier:
            # manual retype wins and pins; an existing pin survives; a generic
            # request preserves the canvas's own type; otherwise the same
            # email coercion runs. ONE canonical persisted representation.
            requested_type = (canvas_type or "").strip().lower()
            canvas_type, content = canonical_update_content(
                latest, requested_type, content, manual_retype)

            review_status = "pending_review" if pending_review else "accepted"
            if operation_id:
                existing = _operation_audit_row(db, canvas_id, operation_id)
                if existing is not None:
                    existing_details = existing.details_json or {}
                    existing_status = existing_details.get("review_status", "unknown")
                    if bind_operation_material:
                        # A supplied logical-operation id is a retry, not a
                        # license to reuse the id for different material.
                        from core.oracle.postcondition_verifiers import (
                            canvas_content_digest,
                        )

                        existing_content = existing_details.get(
                            "content", existing_details.get("data"))
                        if (existing_status != "accepted"
                                or existing_content is None
                                or canvas_content_digest(existing_content)
                                != canvas_content_digest(content)):
                            return {
                                "success": False,
                                "conflict": True,
                                "write_outcome": write_outcome,
                                "error": (
                                    "operation_id already used with different "
                                    "material or is not an accepted save"),
                            }
                    duplicate_outcome = WRITE_COMMITTED
                    if existing_status == "accepted":
                        existing_content = existing_details.get(
                            "content", existing_details.get("data"))
                        # Only refresh the mirror when this operation's audit
                        # row is STILL the current version. A retry after a
                        # later edit must not clobber that newer content; the
                        # direct verified route reports the stale operation as
                        # unverified instead of claiming the current save.
                        if (existing_content is not None
                                and existing.id == latest.id):
                            if scope_required:
                                if not _mirror_accepted_canvas_cas(
                                        db, canvas_row, canvas_id,
                                        existing_content,
                                        existing.canvas_type,
                                        existing_details.get("title"),
                                        user_id, expected_tenant,
                                        expected_workspace):
                                    return {
                                        "success": False,
                                        "conflict": True,
                                        "write_outcome": WRITE_NOT_ATTEMPTED,
                                        "http_status": 409,
                                        "error": (
                                            "canvas scope changed after "
                                            "authorization; write refused"),
                                    }
                                write_outcome = WRITE_UNKNOWN
                                db.commit()
                                write_outcome = WRITE_COMMITTED
                                duplicate_outcome = write_outcome
                            else:
                                _mirror_accepted_canvas(
                                    db, canvas_id, existing_content,
                                    existing.canvas_type,
                                    existing_details.get("title"), user_id,
                                )
                    return {
                        "success": True,
                        "already_applied": True,
                        # This operation's content IS on the canvas — it landed
                        # on an earlier call. Not a new write, but not zero
                        # effect either, and a caller must not report it as
                        # "nothing changed".
                        "write_outcome": duplicate_outcome,
                        "canvas_id": canvas_id,
                        "canvas_type": existing.canvas_type,
                        "audit_id": existing.id,
                        "review_status": existing_status,
                        "message": "Canvas update already applied",
                    }

            # ATOMIC REVISION DOOR (2026-09-22): the caller planned against a
            # specific revision; if anything has appended since, refuse — a
            # background write over a concurrently-edited canvas is never
            # acceptable. Same DB session as the append below, so the
            # check-then-write window is the transaction itself.
            if expected_prior_audit_id and latest.id != expected_prior_audit_id:
                return {
                    "success": False,
                    "conflict": True,
                    "write_outcome": write_outcome,
                    "error": (
                        "canvas changed since the edit was planned "
                        f"(expected audit {expected_prior_audit_id[:12]}…, "
                        f"latest {str(latest.id)[:12]}…) — write refused"),
                }

            # Merge new content into the existing details.
            details = dict(latest.details_json or {})
            details.pop("operation_id", None)
            details.pop("evidence_refs", None)
            details.pop("postconditions", None)
            details["content"] = content
            details["review_status"] = review_status
            if operation_id:
                details["operation_id"] = operation_id
            if evidence_refs:
                details["evidence_refs"] = list(dict.fromkeys(evidence_refs))[:50]
            if postconditions:
                details["postconditions"] = list(postconditions)[:50]
            if title:
                details["title"] = title
            if manual_retype:
                details["type_pinned"] = True

            # Append a new audit row (append-only trail). The authoritative
            # Canvas tenant wins over a legacy audit row's tenant so a new
            # save cannot inherit a foreign scope (CanvasAudit.tenant_id is
            # NOT NULL). STRICT RECENCY: legacy audit rows carry
            # SECOND-precision
            # timestamps, so an update fired in the same second as the row it
            # supersedes tied on created_at and ordering could serve the OLD
            # content (same incident class as the delete tombstone — pinned
            # at least 1µs past the row it supersedes).
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td

            _prev_ts = latest.created_at or _dt.min.replace(tzinfo=_tz.utc)
            if _prev_ts.tzinfo is None:
                _prev_ts = _prev_ts.replace(tzinfo=_tz.utc)
            new_audit = CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=(
                    (canvas_row.tenant_id if canvas_row is not None else None)
                    or latest.tenant_id
                ),
                session_id=audit_session_id(None),
                agent_id=audit_agent_id(None),
                canvas_type=canvas_type,
                action_type="update",
                user_id=user_id,
                created_at=max(_dt.now(_tz.utc), _prev_ts + _td(microseconds=1)),
                details_json=details,
            )
            db.add(new_audit)
            if scope_required:
                if review_status == "accepted":
                    guarded = _mirror_accepted_canvas_cas(
                        db, canvas_row, canvas_id, content, canvas_type,
                        details.get("title"), user_id,
                        expected_tenant, expected_workspace)
                else:
                    guarded = _scope_claim_cas(
                        db, canvas_row, canvas_id,
                        expected_tenant, expected_workspace)
                if not guarded:
                    return {
                        "success": False,
                        "conflict": True,
                        "write_outcome": WRITE_NOT_ATTEMPTED,
                        "http_status": 409,
                        "error": (
                            "canvas scope changed after authorization; "
                            "write refused"),
                    }
            elif review_status == "accepted":
                _mirror_accepted_canvas(
                    db, canvas_id, content, canvas_type,
                    details.get("title"), user_id,
                )
            # From here the row is going to the database: past this point a
            # failure is NOT proof that nothing changed.
            write_outcome = WRITE_UNKNOWN
            db.commit()
            write_outcome = WRITE_COMMITTED
            db.refresh(new_audit)

        # Broadcast the update via WebSocket.
        await _broadcast_canvas_update(user_id, canvas_id, canvas_type, content, title or details.get("title"))

        logger.info(f"Updated canvas {canvas_id} ({canvas_type})")
        return {
            "success": True,
            "write_outcome": write_outcome,
            "canvas_id": canvas_id,
            "canvas_type": canvas_type,
            "audit_id": str(new_audit.id),
            "operation_id": operation_id,
            "review_status": review_status,
            "message": "Canvas updated successfully",
        }
    except Exception as e:
        logger.error(f"Canvas update failed: {e}")
        return {"success": False, "error": str(e), "write_outcome": write_outcome}


async def _broadcast_canvas_update(
    user_id: str,
    canvas_id: str,
    canvas_type: str,
    content: Any,
    title: Optional[str],
) -> None:
    """WS broadcast shared by every write path (update, restore). Mirrors the
    present-flow contract: the email composer reads To/Cc/Subject from
    `metadata`. Best-effort — a broadcast failure never fails the write."""
    try:
        from core.websockets import manager as ws_manager

        broadcast_data = {
            "action": "update",
            "canvas_id": canvas_id,
            "component": canvas_type,
            "data": content,
            "title": title,
        }
        if canvas_type == "email" and isinstance(content, dict):
            broadcast_data["metadata"] = {
                "to": content.get("to", ""),
                "cc": content.get("cc", ""),
                "subject": content.get("subject", ""),
            }
        await ws_manager.broadcast(f"user:{user_id}", {
            "type": "canvas:update",
            "data": broadcast_data,
        })
    except Exception as ws_err:
        logger.debug(f"Canvas update WS broadcast skipped: {ws_err}")


_VERSION_PREVIEW_CHARS = 600
# Upper bound when a caller asks for FULL version content (agents reading a
# version before reverting). Generous enough for real drafts, tight enough
# that one version can't blow the agent's context window.
_VERSION_FULL_CONTENT_CHARS = 20000


def _serialize_version_text(content: Any, cap: Optional[int] = None) -> str:
    """Version content as bounded text for agent-facing listings."""
    if isinstance(content, str):
        text = content
    else:
        try:
            import json as _json

            text = _json.dumps(content, indent=2, default=str)
        except Exception:
            text = str(content)
    if cap is not None and len(text) > cap:
        return text[:cap] + "…(truncated)"
    return text


async def list_canvas_versions(
    user_id: str,
    canvas_id: str,
    limit: int = 20,
    include_content: bool = False,
) -> Dict[str, Any]:
    """List the version history of a canvas (newest first).

    Every write to a canvas appends a CanvasAudit row, so the audit trail IS
    the version history. Contentless event rows (email_send stamps, delete
    markers) are not versions and are skipped. The newest content-bearing
    row is flagged ``is_current`` — restoring to it would be a no-op.

    Companion to ``restore_canvas_version``: the agent lists versions
    (bounded previews identify each one), picks the right ``audit_id``, and
    restores. Owner-scoped like every other CRUD entry point.

    Args:
        user_id: User requesting the action
        canvas_id: The canvas ID
        limit: Max versions to return (default 20, capped at 50)
        include_content: Include each version's full content (bounded)
            instead of a short preview
    """
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from sqlalchemy import desc

        with get_db_session() as db:
            if not _verify_canvas_owner(db, canvas_id, user_id):
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            rows = (
                db.query(CanvasAudit)
                .filter(
                    CanvasAudit.canvas_id == canvas_id,
                    CanvasAudit.action_type != "delete",
                )
                .order_by(desc(CanvasAudit.created_at), desc(CanvasAudit.id))
                .limit(max(1, min(int(limit or 20), 50)))
                .all()
            )

            versions: list = []
            for r in rows:
                details = r.details_json or {}
                content = details.get("content", details.get("data"))
                if content is None:
                    continue  # an event stamp, not a version
                cap = _VERSION_FULL_CONTENT_CHARS if include_content else _VERSION_PREVIEW_CHARS
                entry = {
                    "audit_id": r.id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "actor": "agent" if r.agent_id else "supervisor",
                    "action_type": r.action_type,
                    "title": details.get("title"),
                    "restored_from": (details.get("restored_from") or {}).get("audit_id")
                    if isinstance(details.get("restored_from"), dict)
                    else None,
                    "content": _serialize_version_text(content, cap),
                    "content_truncated": len(_serialize_version_text(content)) > cap,
                    "is_current": False,
                }
                versions.append(entry)

            if versions:
                versions[0]["is_current"] = True

            return {
                "success": True,
                "canvas_id": canvas_id,
                "versions": versions,
                "count": len(versions),
            }
    except Exception as e:
        logger.error(f"Canvas version list failed: {e}")
        return {"success": False, "error": str(e)}


async def restore_canvas_version(
    user_id: str,
    canvas_id: str,
    audit_id: str,
    operation_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    scope_required: bool = False,
) -> Dict[str, Any]:
    """Restore an earlier version from the append-only audit trail.

    A restore is itself APPENDED as a new "update" row (nothing is rewritten
    or deleted — the pre-restore state stays in history as its own version),
    carrying `restored_from` provenance. Broadcasts the same WS update as a
    normal edit so every open canvas converges.

    No-op guard: restoring a version whose content equals the current
    content appends nothing and reports ``no_change`` — byte-identical
    "restores" were audit-trail noise that read to the user as an undo that
    did something (same rationale as the editor's no_change guard).

    Type resolution: the restored version's own canvas_type is authoritative
    for its content, EXCEPT when the canvas carries a human type pin
    (`type_pinned`) — the supervisor's manual choice outranks history.

    Carries the same ``write_outcome`` contract as `update_canvas_content`:
    a refusal is only a verified zero effect when the store says the append was
    never attempted.
    """
    write_outcome = WRITE_NOT_ATTEMPTED
    try:
        from core.database import get_db_session
        from core.models import Canvas, CanvasAudit
        from sqlalchemy import desc

        with get_db_session() as db:
            # Authorized scope snapshot, captured before the final check.
            canvas_row = (
                db.query(Canvas).filter(Canvas.id == canvas_id).first()
            )
            expected_tenant = (
                str(canvas_row.tenant_id or "")
                if canvas_row is not None else "")
            expected_workspace = (
                str(canvas_row.workspace_id or "")
                if canvas_row is not None else "")
            if scope_required:
                # Same-transaction scope gate as the update path. The target
                # audit is checked against the authoritative canvas tenant.
                scope_error = canvas_write_scope_error(
                    db, canvas_id, user_id, tenant_id, workspace_id,
                    target_audit_id=str(audit_id), lock=True)
                if scope_error:
                    return {
                        "success": False,
                        "write_outcome": write_outcome,
                        **scope_error,
                    }
            elif not _verify_canvas_owner(db, canvas_id, user_id):
                # IDOR guard: only the owner may restore this canvas.
                return {"success": False, "write_outcome": write_outcome,
                        "error": f"Canvas {canvas_id} not found"}

            target = (
                db.query(CanvasAudit)
                .filter(CanvasAudit.id == str(audit_id), CanvasAudit.canvas_id == canvas_id)
                .first()
            )
            if not target:
                return {"success": False, "write_outcome": write_outcome,
                        "error": "Version not found"}
            if target.action_type == "delete":
                return {"success": False, "write_outcome": write_outcome,
                        "error": "Cannot restore a deletion marker"}

            target_details = target.details_json or {}
            content = target_details.get("content", target_details.get("data"))
            if content is None:
                return {"success": False, "write_outcome": write_outcome,
                        "error": "Version carries no restorable content"}

            latest = (
                db.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == canvas_id)
                .order_by(desc(CanvasAudit.created_at))
                .first()
            )
            if not latest:
                return {"success": False, "write_outcome": write_outcome,
                        "error": f"Canvas {canvas_id} not found"}
            if latest.action_type == "delete":
                return {"success": False, "write_outcome": write_outcome,
                        "error": "Cannot update a deleted canvas"}

            latest_details = dict(latest.details_json or {})

            # No-op guard: the requested version IS the current content.
            latest_body = latest_details.get("content", latest_details.get("data"))
            if latest_body is not None and content == latest_body:
                return {
                    "success": True,
                    # Nothing appended, and nothing to append: VERIFIED zero
                    # effect for this restore.
                    "write_outcome": write_outcome,
                    "canvas_id": canvas_id,
                    "no_change": True,
                    "restored_from": audit_id,
                    "message": "Canvas is already at that version — nothing restored",
                }

            canvas_type, content = canonical_restore_content(latest, target)

            # Base the new row on the LATEST details (preserves send metadata,
            # pins, learning-loop state), then override content/title and mark
            # the provenance.
            new_details = dict(latest_details)
            new_details.pop("operation_id", None)
            new_details.pop("evidence_refs", None)
            new_details.pop("postconditions", None)
            new_details["content"] = content
            new_details["review_status"] = "accepted"
            if operation_id:
                new_details["operation_id"] = operation_id
            if target_details.get("title"):
                new_details["title"] = target_details["title"]
            new_details["restored_from"] = {
                "audit_id": target.id,
                "created_at": target.created_at.isoformat() if target.created_at else None,
                "actor": "agent" if target.agent_id else "supervisor",
            }

            # STRICT RECENCY (same second-precision tie as the delete
            # tombstone): a restore landing in the same second as the edit it
            # reverts must still order AFTER that row, or read_canvas serves
            # the pre-restore content the moment the page refreshes.
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td

            _prev_ts = latest.created_at or _dt.min.replace(tzinfo=_tz.utc)
            if _prev_ts.tzinfo is None:
                _prev_ts = _prev_ts.replace(tzinfo=_tz.utc)
            new_audit = CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=(
                    (canvas_row.tenant_id if canvas_row is not None else None)
                    or latest.tenant_id
                ),
                session_id=audit_session_id(None),
                agent_id=audit_agent_id(None),
                canvas_type=canvas_type,
                action_type="update",
                user_id=user_id,
                created_at=max(_dt.now(_tz.utc), _prev_ts + _td(microseconds=1)),
                details_json=new_details,
            )
            db.add(new_audit)
            if scope_required:
                guarded = _mirror_accepted_canvas_cas(
                    db, canvas_row, canvas_id, content, canvas_type,
                    new_details.get("title"), user_id,
                    expected_tenant, expected_workspace)
                if not guarded:
                    return {
                        "success": False,
                        "conflict": True,
                        "write_outcome": WRITE_NOT_ATTEMPTED,
                        "http_status": 409,
                        "error": (
                            "canvas scope changed after authorization; "
                            "restore refused"),
                    }
            else:
                _mirror_accepted_canvas(
                    db, canvas_id, content, canvas_type,
                    new_details.get("title"), user_id,
                )
            # The append is going to the database: past this point a failure is
            # not proof that nothing changed.
            write_outcome = WRITE_UNKNOWN
            db.commit()
            write_outcome = WRITE_COMMITTED
            db.refresh(new_audit)

        await _broadcast_canvas_update(
            user_id, canvas_id, canvas_type, content,
            new_details.get("title"),
        )
        logger.info(
            f"Restored canvas {canvas_id} to version {audit_id} "
            f"({canvas_type}) — appended as a new version"
        )
        return {
            "success": True,
            "write_outcome": write_outcome,
            "canvas_id": canvas_id,
            "canvas_type": canvas_type,
            "audit_id": str(new_audit.id),
            "operation_id": operation_id,
            "review_status": "accepted",
            "restored_from": audit_id,
            "message": "Version restored (appended as the newest version)",
        }
    except Exception as e:
        logger.error(f"Canvas restore failed: {e}")
        return {"success": False, "error": str(e), "write_outcome": write_outcome}


async def delete_canvas(
    user_id: Optional[str],
    canvas_id: str,
    *,
    operation_id: Optional[str] = None,
    expected_prior_audit_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    scope_required: bool = False,
) -> Dict[str, Any]:
    """Delete (close) a specific canvas by ID.

    Writes a CanvasAudit with action_type="delete" and broadcasts a WS close.
    The audit trail is preserved (append-only), so the history is recoverable.

    ``scope_required`` is the verified consumer contract (HTTP route and the
    registered-tool service). It authorizes the acting principal's CURRENT
    tenant/workspace against the authoritative Canvas row — or, for an
    audit-only canvas, against the newest audit tenant. A historical
    co-editor whose scope has since moved is refused before effect. Direct
    tool callers that omit it keep the legacy owner/co-editor ownership gate.

    ``operation_id`` is the server-owned identity of one LOGICAL delete. The
    same id with the same target/prior state replays the original tombstone
    id with no second row or broadcast. Reusing it for a different target or
    prior state is a conflict. ``expected_prior_audit_id`` is the optional
    optimistic token; a mismatch refuses before effect.

    Args:
        user_id: User requesting the action
        canvas_id: The canvas ID to delete
    """
    write_outcome = WRITE_NOT_ATTEMPTED
    appended_audit_id = ""
    try:
        from core.database import get_db_session
        from core.models import Canvas, CanvasAudit
        from core.oracle.postcondition_verifiers import canvas_content_digest
        from core.websockets import manager as ws_manager

        with get_db_session() as db:
            canvas_row = (
                db.query(Canvas).filter(Canvas.id == canvas_id).first()
            )
            expected_tenant = (
                str(getattr(canvas_row, "tenant_id", None) or "")
                if canvas_row is not None else "")
            expected_workspace = (
                str(getattr(canvas_row, "workspace_id", None) or "")
                if canvas_row is not None else "")

            if scope_required:
                # Authoritative scope gate in the SAME transaction as the
                # append. The guarded write below is the linearization point.
                scope_error = canvas_lifecycle_scope_error(
                    db, canvas_id, user_id, tenant_id, workspace_id,
                    lock=True)
                if scope_error:
                    return {
                        "success": False,
                        "write_outcome": write_outcome,
                        **scope_error,
                    }
            elif not _verify_canvas_owner(db, canvas_id, user_id):
                # IDOR guard: only the owner/co-editor may delete this canvas.
                return {"success": False, "write_outcome": write_outcome,
                        "error": f"Canvas {canvas_id} not found"}

            latest = _latest_canvas_audit(db, canvas_id, lock=scope_required)
            if not latest:
                return {"success": False, "write_outcome": write_outcome,
                        "error": f"Canvas {canvas_id} not found"}

            latest_details = latest.details_json or {}
            if not isinstance(latest_details, dict):
                latest_details = {}
            existing_operation = str(
                latest_details.get("operation_id") or "")
            operation_id = (operation_id or "").strip() or None

            if operation_id:
                existing = _operation_audit_row(db, canvas_id, operation_id)
                if existing is not None:
                    existing_details = existing.details_json or {}
                    if not isinstance(existing_details, dict):
                        existing_details = {}
                    existing_prior = str(
                        existing_details.get("prior_audit_id") or "")
                    intended_prior = str(expected_prior_audit_id or "")
                    if not intended_prior and latest.action_type != "delete":
                        intended_prior = str(latest.id)
                    if (str(existing.action_type or "") != "delete"
                            or (existing_prior and intended_prior
                                and existing_prior != intended_prior)):
                        return {
                            "success": False,
                            "conflict": True,
                            "write_outcome": write_outcome,
                            "http_status": 409,
                            "operation_id": operation_id,
                            "error": (
                                "operation_id already used with different "
                                "material or target"),
                        }
                    return {
                        "success": True,
                        "already_applied": True,
                        "replayed": True,
                        "no_change": True,
                        "write_outcome": WRITE_COMMITTED,
                        "canvas_id": canvas_id,
                        "audit_id": str(existing.id),
                        "operation_id": operation_id,
                        "action_type": "delete",
                        "prior_audit_id": existing_prior or None,
                        "source_audit_id":
                            existing_details.get("source_audit_id"),
                        "content_sha256":
                            existing_details.get("content_sha256"),
                        "canvas_type": existing.canvas_type,
                        "message": "Canvas delete already applied",
                    }

            if (expected_prior_audit_id
                    and str(latest.id) != str(expected_prior_audit_id)):
                return {
                    "success": False,
                    "conflict": True,
                    "write_outcome": write_outcome,
                    "http_status": 409,
                    "operation_id": operation_id,
                    "error": (
                        "canvas changed since the delete was planned "
                        f"(expected audit {str(expected_prior_audit_id)[:12]}…, "
                        f"latest {str(latest.id)[:12]}…) — write refused"),
                }

            if latest.action_type == "delete":
                # IDEMPOTENT: deleting an already-deleted canvas succeeds.
                # The gallery's delete button raced the refetch window once
                # and the non-idempotent 400 surfaced as an AxiosError
                # overlay (observed live 2026-09-01). REST DELETE is
                # idempotent by contract; the outcome is identical. A
                # DIFFERENT operation id still reports the original
                # tombstone, and never appends a second row or broadcast.
                return {
                    "success": True,
                    "already_applied": True,
                    "replayed": False,
                    "no_change": True,
                    "already_deleted": True,
                    "write_outcome": WRITE_COMMITTED,
                    "canvas_id": canvas_id,
                    "audit_id": str(latest.id),
                    "operation_id": operation_id,
                    "applied_operation_id": existing_operation or None,
                    "action_type": "delete",
                    "prior_audit_id":
                        latest_details.get("prior_audit_id"),
                    "source_audit_id":
                        latest_details.get("source_audit_id"),
                    "content_sha256":
                        latest_details.get("content_sha256"),
                    "canvas_type": latest.canvas_type,
                    "message": "Canvas was already deleted",
                }

            source = latest_canvas_content_audit(db, canvas_id)
            source_details = (
                source.details_json or {} if source is not None else {})
            if not isinstance(source_details, dict):
                source_details = {}
            content = _audit_content(source_details)
            try:
                content_sha256 = (
                    canvas_content_digest(content)
                    if content is not None else "")
            except Exception:  # noqa: BLE001 - unreadable material is no proof
                content_sha256 = ""
            canvas_type = (
                latest.canvas_type
                or (getattr(source, "canvas_type", None)
                    if source is not None else None)
                or "generic")

            details: Dict[str, Any] = {
                "deleted": True,
                "previous_action": latest.action_type,
                "prior_audit_id": str(latest.id),
                "content_sha256": content_sha256,
            }
            if source is not None:
                details["source_audit_id"] = str(source.id)
            if operation_id:
                details["operation_id"] = operation_id

            # Write the delete audit. Carry the AUTHORITATIVE Canvas tenant
            # when the mirror exists (never a foreign audit tenant).
            # STRICT RECENCY: legacy audit rows carry SECOND-precision
            # timestamps (func.now() server default), so a delete fired in the
            # same second as the action it supersedes tied on created_at and
            # the uuid tiebreak let the OLD state win — deletes "came back"
            # (observed live 2026-09-01: delete → restore same second, and a
            # later delete silently no-opped). The new row is pinned at least
            # 1µs past the row it supersedes.
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td

            _prev_ts = latest.created_at or _dt.min.replace(tzinfo=_tz.utc)
            if _prev_ts.tzinfo is None:
                _prev_ts = _prev_ts.replace(tzinfo=_tz.utc)
            delete_audit = CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=(
                    (getattr(canvas_row, "tenant_id", None)
                     if canvas_row is not None else None)
                    or latest.tenant_id
                ),
                session_id=audit_session_id(None),
                agent_id=audit_agent_id(None),
                canvas_type=canvas_type,
                action_type="delete",
                user_id=user_id,
                created_at=max(_dt.now(_tz.utc), _prev_ts + _td(microseconds=1)),
                details_json=details,
            )
            db.add(delete_audit)

            if scope_required:
                if canvas_row is not None:
                    guarded = _scope_claim_cas(
                        db, canvas_row, canvas_id,
                        expected_tenant, expected_workspace)
                else:
                    guarded = _audit_scope_claim_cas(
                        db, canvas_id, latest.id, latest.tenant_id)
                if not guarded:
                    return {
                        "success": False,
                        "conflict": True,
                        "write_outcome": WRITE_NOT_ATTEMPTED,
                        "http_status": 409,
                        "operation_id": operation_id,
                        "error": (
                            "canvas scope changed after authorization; "
                            "delete refused"),
                    }

            try:
                db.flush()
                appended_audit_id = str(delete_audit.id)
            except Exception:
                write_outcome = WRITE_UNKNOWN
                raise
            # From here the row is going to the database: past this point a
            # failure is NOT proof that nothing changed.
            write_outcome = WRITE_UNKNOWN
            db.commit()
            write_outcome = WRITE_COMMITTED
            appended_audit_id = str(delete_audit.id)

        # Broadcast close via WebSocket — ONE frame for a NEW effect only.
        try:
            user_channel = f"user:{user_id}"
            await ws_manager.broadcast(user_channel, {
                "type": "canvas:update",
                "data": {
                    "action": "close",
                    "canvas_id": canvas_id,
                },
            })
        except Exception as ws_err:
            logger.debug(f"Canvas delete WS broadcast skipped: {ws_err}")

        logger.info(f"Deleted canvas {canvas_id}")
        return {
            "success": True,
            "write_outcome": write_outcome,
            "canvas_id": canvas_id,
            "audit_id": appended_audit_id,
            "operation_id": operation_id,
            "action_type": "delete",
            "prior_audit_id": details["prior_audit_id"],
            "source_audit_id": details.get("source_audit_id"),
            "content_sha256": content_sha256,
            "canvas_type": canvas_type,
            "message": "Canvas deleted successfully",
        }
    except Exception as e:
        logger.error(f"Canvas delete failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "write_outcome": write_outcome,
            "audit_id": appended_audit_id or None,
            "operation_id": operation_id,
        }


# ----------------------------------------------------------------------------
# Discovery helpers — search / display titles / snippets.
#
# The audit trail's details_json carries the body under different keys
# depending on the writer (present_* tools use "content", some flows "data",
# chat_draft_to_canvas stores the document only on the Canvas row). read_canvas
# already resolves that ladder; list/search must walk the SAME ladder or those
# canvases become unfindable (no title, no snippet, no content match).
# ----------------------------------------------------------------------------

_BODY_KEYS = ("content", "data")


def _audit_body(details: Dict[str, Any]) -> Any:
    """Resolve the body from audit details, preserving empty-but-valid values."""
    for key in _BODY_KEYS:
        if key in details and details[key] is not None:
            return details[key]
    return None


def _text_of(content: Any) -> str:
    """Flatten canvas content (str | dict | list) to searchable/preview text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts: list = []
        for key in ("subject", "to", "title", "content", "text", "instruction", "body"):
            if isinstance(content.get(key), str) and content[key].strip():
                parts.append(content[key].strip())
        if parts:
            return " ".join(parts)
        import json as _json

        try:
            return _json.dumps(content, default=str)
        except Exception:
            return str(content)
    if isinstance(content, (list, tuple)):
        return " ".join(_text_of(item) for item in content)
    return str(content)


def _first_meaningful_line(text: str, cap: int = 80) -> Optional[str]:
    """First non-empty line with markdown noise stripped — the Notion-style
    derived title for untitled canvases, so a card never shows a raw UUID."""
    for line in text.splitlines():
        cleaned = line.lstrip("#*>- ` \t").strip()
        if cleaned:
            return cleaned[:cap] + ("…" if len(cleaned) > cap else "")
    return None


def _derive_display_title(
    canvas_type: Optional[str],
    details: Dict[str, Any],
    body: Any,
    canvas_name: Optional[str] = None,
) -> str:
    """Best-effort human title. Priority: explicit audit title → Canvas.name →
    type-aware content inference → typed fallback."""
    explicit = (details.get("title") or "").strip() if isinstance(details.get("title"), str) else details.get("title")
    if explicit:
        return str(explicit)[:120]
    if canvas_name:
        return str(canvas_name)[:120]

    ctype = (canvas_type or "").lower()
    if isinstance(body, dict):
        subject = str(body.get("subject") or "").strip()
        if subject:
            return subject[:120]
        to = str(body.get("to") or "").strip()
        if to:
            recipient = to.split(",")[0].strip()
            return f"Email to {recipient}"[:120]
        if ctype == "email":
            return "Email draft"
    line = _first_meaningful_line(_text_of(body))
    if line:
        return line
    if ctype:
        return f"Untitled {ctype} canvas"
    return "Untitled canvas"


def _content_snippet(body: Any, q: Optional[str], cap: int = 140) -> Optional[str]:
    """Short text excerpt for list cards. When searching, window the excerpt
    around the first match so the user sees WHY the canvas matched."""
    text = " ".join(_text_of(body).split())
    if not text:
        return None
    needle = (q or "").strip().lower()
    if needle:
        idx = text.lower().find(needle)
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(text), idx + len(needle) + (cap - 40))
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(text) else ""
            return prefix + text[start:end] + suffix
    return text[:cap] + ("…" if len(text) > cap else "")



async def restore_deleted_canvas(
    user_id: Optional[str],
    canvas_id: str,
    *,
    operation_id: Optional[str] = None,
    expected_tombstone_audit_id: Optional[str] = None,
    expected_source_audit_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    scope_required: bool = False,
) -> Dict[str, Any]:
    """Un-delete a tombstoned canvas.

    The delete path is append-only (a CanvasAudit tombstone), so restoring is
    appending an action_type="restore" row carrying the PRE-delete content
    forward — nothing is rewritten, the delete stays in history. After this,
    the latest row is no longer a tombstone: listings include the canvas
    again, read_canvas serves the restored content, and update_canvas_content
    accepts writes.

    ``scope_required`` is the verified consumer contract (HTTP route and the
    registered-tool service). It authorizes the acting principal's CURRENT
    tenant/workspace against the authoritative Canvas row — or, for an
    audit-only canvas, against the newest audit tenant. A historical
    co-editor whose scope has since moved is refused before effect.

    ``operation_id`` is the server-owned identity of one LOGICAL undelete.
    The same id replays the original restore row with no second row or
    broadcast; reusing it for a different tombstone/source is a conflict.
    ``expected_tombstone_audit_id`` / ``expected_source_audit_id`` are the
    optional optimistic tokens; a mismatch refuses before effect.

    The source is the newest CONTENT-bearing non-delete row (the same row
    ``read_canvas`` would serve), and the new row records its exact id and
    content digest so the receipt binds the restored material.
    """
    write_outcome = WRITE_NOT_ATTEMPTED
    appended_audit_id = ""
    operation_id = (operation_id or "").strip() or None
    try:
        from core.database import get_db_session
        from core.models import Canvas, CanvasAudit
        from core.oracle.postcondition_verifiers import canvas_content_digest

        with get_db_session() as db:
            canvas_row = (
                db.query(Canvas).filter(Canvas.id == canvas_id).first()
            )
            expected_tenant = (
                str(getattr(canvas_row, "tenant_id", None) or "")
                if canvas_row is not None else "")
            expected_workspace = (
                str(getattr(canvas_row, "workspace_id", None) or "")
                if canvas_row is not None else "")

            if scope_required:
                scope_error = canvas_lifecycle_scope_error(
                    db, canvas_id, user_id, tenant_id, workspace_id,
                    lock=True)
                if scope_error:
                    return {
                        "success": False,
                        "write_outcome": write_outcome,
                        **scope_error,
                    }
            elif not _verify_canvas_owner(db, canvas_id, user_id):
                return {"success": False, "write_outcome": write_outcome,
                        "error": f"Canvas {canvas_id} not found"}

            latest = _latest_canvas_audit(db, canvas_id, lock=scope_required)
            if not latest:
                return {"success": False, "write_outcome": write_outcome,
                        "error": f"Canvas {canvas_id} not found"}

            if operation_id:
                existing = _operation_audit_row(db, canvas_id, operation_id)
                if existing is not None:
                    existing_details = existing.details_json or {}
                    if not isinstance(existing_details, dict):
                        existing_details = {}
                    existing_tombstone = str(
                        existing_details.get("tombstone_audit_id") or "")
                    existing_source = str(
                        existing_details.get("source_audit_id") or "")
                    mismatch = (
                        str(existing.action_type or "") != "restore"
                        or (expected_tombstone_audit_id
                            and existing_tombstone
                            and existing_tombstone != str(
                                expected_tombstone_audit_id))
                        or (expected_source_audit_id
                            and existing_source
                            and existing_source != str(
                                expected_source_audit_id)))
                    if mismatch:
                        return {
                            "success": False,
                            "conflict": True,
                            "write_outcome": write_outcome,
                            "http_status": 409,
                            "operation_id": operation_id,
                            "error": (
                                "operation_id already used with different "
                                "material or target"),
                        }
                    return {
                        "success": True,
                        "already_applied": True,
                        "replayed": True,
                        "no_change": True,
                        "write_outcome": WRITE_COMMITTED,
                        "canvas_id": canvas_id,
                        "audit_id": str(existing.id),
                        "operation_id": operation_id,
                        "action_type": "restore",
                        "tombstone_audit_id": existing_tombstone or None,
                        "restored_from_tombstone_id":
                            existing_tombstone or None,
                        "source_audit_id": existing_source or None,
                        "content_sha256":
                            existing_details.get("content_sha256"),
                        "canvas_type": existing.canvas_type,
                        "message": "Canvas undelete already applied",
                    }

            if latest.action_type != "delete":
                return {
                    "success": False,
                    "write_outcome": write_outcome,
                    "conflict": True,
                    "http_status": 409,
                    "operation_id": operation_id,
                    "error": "Canvas is not deleted",
                }
            if (expected_tombstone_audit_id
                    and str(latest.id) != str(expected_tombstone_audit_id)):
                return {
                    "success": False,
                    "conflict": True,
                    "write_outcome": write_outcome,
                    "http_status": 409,
                    "operation_id": operation_id,
                    "error": (
                        "canvas tombstone changed since the undelete was "
                        "planned — write refused"),
                }

            # The pre-delete content: the most recent CONTENT-bearing row
            # that is not a tombstone. Event-only rows (email_send_stamp)
            # carry no body and must not replace the restored draft.
            source = latest_canvas_content_audit(db, canvas_id)
            if source is None:
                return {
                    "success": False,
                    "write_outcome": write_outcome,
                    "conflict": True,
                    "http_status": 409,
                    "operation_id": operation_id,
                    "error": "No content to restore",
                }
            if (expected_source_audit_id
                    and str(source.id) != str(expected_source_audit_id)):
                return {
                    "success": False,
                    "conflict": True,
                    "write_outcome": write_outcome,
                    "http_status": 409,
                    "operation_id": operation_id,
                    "error": (
                        "canvas source content changed since the undelete "
                        "was planned — write refused"),
                }

            source_details = dict(source.details_json or {})
            content = _audit_content(source_details)
            try:
                content_sha256 = (
                    canvas_content_digest(content)
                    if content is not None else "")
            except Exception:  # noqa: BLE001 - unreadable material is no proof
                content_sha256 = ""
            if content is None:
                return {
                    "success": False,
                    "write_outcome": write_outcome,
                    "conflict": True,
                    "http_status": 409,
                    "operation_id": operation_id,
                    "error": "No content to restore",
                }

            details = dict(source_details)
            details.pop("operation_id", None)
            details.pop("evidence_refs", None)
            details.pop("postconditions", None)
            details["restored_from_delete"] = True
            details["tombstone_audit_id"] = str(latest.id)
            details["source_audit_id"] = str(source.id)
            details["content_sha256"] = content_sha256
            if operation_id:
                details["operation_id"] = operation_id

            from datetime import datetime as _dt, timezone as _tz, timedelta as _td

            _prev_ts2 = latest.created_at or _dt.min.replace(tzinfo=_tz.utc)
            if _prev_ts2.tzinfo is None:
                _prev_ts2 = _prev_ts2.replace(tzinfo=_tz.utc)
            tombstone_audit_id = str(latest.id)
            source_audit_id = str(source.id)
            canvas_type = str(
                latest.canvas_type
                or (getattr(source, "canvas_type", None))
                or "generic")
            restore_audit = CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=(
                    (getattr(canvas_row, "tenant_id", None)
                     if canvas_row is not None else None)
                    or latest.tenant_id
                ),
                session_id=audit_session_id(None),
                agent_id=audit_agent_id(None),
                canvas_type=canvas_type,
                action_type="restore",
                user_id=user_id,
                created_at=max(_dt.now(_tz.utc), _prev_ts2 + _td(microseconds=1)),
                details_json=details,
            )
            db.add(restore_audit)

            if scope_required:
                if canvas_row is not None:
                    guarded = _scope_claim_cas(
                        db, canvas_row, canvas_id,
                        expected_tenant, expected_workspace)
                else:
                    guarded = _audit_scope_claim_cas(
                        db, canvas_id, latest.id, latest.tenant_id)
                if not guarded:
                    return {
                        "success": False,
                        "conflict": True,
                        "write_outcome": WRITE_NOT_ATTEMPTED,
                        "http_status": 409,
                        "operation_id": operation_id,
                        "error": (
                            "canvas scope changed after authorization; "
                            "undelete refused"),
                    }

            try:
                db.flush()
                appended_audit_id = str(restore_audit.id)
            except Exception:
                write_outcome = WRITE_UNKNOWN
                raise
            write_outcome = WRITE_UNKNOWN
            db.commit()
            write_outcome = WRITE_COMMITTED
            appended_audit_id = str(restore_audit.id)

        canvas_type = str(canvas_type or "generic")
        broadcast_content = None
        for _body_key in ("content", "data"):
            if (_body_key in details
                    and details[_body_key] is not None):
                broadcast_content = details[_body_key]
                break
        await _broadcast_canvas_update(
            user_id, canvas_id, canvas_type,
            broadcast_content, details.get("title"),
        )

        logger.info(f"Restored deleted canvas {canvas_id}")
        return {
            "success": True,
            "write_outcome": write_outcome,
            "canvas_id": canvas_id,
            "audit_id": appended_audit_id,
            "operation_id": operation_id,
            "action_type": "restore",
            "tombstone_audit_id": tombstone_audit_id,
            "restored_from_tombstone_id": tombstone_audit_id,
            "source_audit_id": source_audit_id,
            "content_sha256": content_sha256,
            "canvas_type": canvas_type,
            "restored_from_delete": True,
            "message": "Canvas restored (append-only undelete)",
        }
    except Exception as e:
        logger.warning(f"Canvas restore failed for {canvas_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "write_outcome": write_outcome,
            "audit_id": appended_audit_id or None,
            "operation_id": operation_id,
        }


async def list_canvases(
    user_id: str,
    canvas_type: Optional[str] = None,
    include_deleted: bool = False,
    q: Optional[str] = None,
    limit: Optional[int] = 60,
    offset: int = 0,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """List a user's canvases from the audit trail — searchable and paginated.

    Returns the latest state of each unique canvas_id (the audit trail IS the
    source of truth; agent-created canvases have no Canvas row). As canvas
    counts grow this stays fast: the DB collapses to one row per canvas via a
    ROW_NUMBER() window (instead of materializing every historical audit row)
    and only the requested page is serialized.

    Discovery features (the "find the right canvas" journey):
    - ``q``: case-insensitive substring match over derived title, canvas_type,
      canvas_id, and the canvas body text — finds untitled canvases by content.
    - ``display_title``: title derived from content when no explicit title
      exists (email subject/recipient, first line of a doc) — never a raw UUID.
    - ``snippet``: content excerpt, windowed around the search match.
    - ``session_id``: scope to canvases touched in one chat session — the
      agent-chat Artifacts panel lists what that conversation produced. The
      session filter applies to the audit rows BEFORE the latest-per-canvas
      window, so a canvas presented in this session still appears even if its
      newest edit happened elsewhere; ``version`` counts this session's rows.

    Args:
        user_id: User requesting the action
        canvas_type: Optional filter (e.g. "sheets", "email")
        include_deleted: Include deleted canvases (default False)
        q: Optional search string (title / content / type / id)
        limit: Page size (default 60; capped at 200; None = no cap for
            internal callers that want the full set)
        offset: Page offset
        session_id: Optional chat-session scope (CanvasAudit.session_id)
    """
    try:
        from core.database import get_db_session
        from core.models import Canvas, CanvasAudit
        from sqlalchemy import func
        from sqlalchemy.orm import aliased

        with get_db_session() as db:
            # Latest audit row per canvas_id (deterministic: newest created_at,
            # then id as tiebreak for same-commit timestamps) + how many rows
            # this scope has per canvas (the sidebar's v{n} badge — one more
            # window over the same partition, no extra query).
            rn = (
                func.row_number()
                .over(
                    partition_by=CanvasAudit.canvas_id,
                    order_by=(CanvasAudit.created_at.desc(), CanvasAudit.id.desc()),
                )
                .label("rn")
            )
            version_count = (
                func.count()
                .over(partition_by=CanvasAudit.canvas_id)
                .label("version_count")
            )
            base = db.query(CanvasAudit, rn, version_count).filter(
                CanvasAudit.user_id == user_id,
                # Only AUTHORSHIP rows establish that a canvas belongs in this
                # user's gallery — the same predicate _verify_canvas_owner
                # authorizes with. Event-only rows (form submissions on a
                # shared canvas) used to list somebody else's canvas here while
                # every per-canvas endpoint 404'd on it; they also leaked the
                # owner's content through the listing's Canvas.content fallback.
                CanvasAudit.action_type.notin_(_EVENT_ONLY_ACTIONS),
            )
            if canvas_type:
                base = base.filter(CanvasAudit.canvas_type == canvas_type)
            if session_id:
                base = base.filter(CanvasAudit.session_id == session_id)

            subq = base.subquery()
            latest = (
                db.query(aliased(CanvasAudit, subq), subq.c.version_count)
                .filter(subq.c.rn == 1)
                .order_by(subq.c.created_at.desc(), subq.c.id.desc())
                .all()
            )

            # Canvas-row enrichment, two batched queries:
            # 1. names for every listed canvas (Canvas.name outranks
            #    content-derived titles — office /present canvases carry a
            #    real filename there);
            # 2. content ONLY for canvases whose audit details carry no body
            #    key at all (chat_draft_to_canvas writes the document only on
            #    the Canvas row — same fallback ladder as read_canvas).
            all_ids = [row.canvas_id for row, _vc in latest]
            canvas_names: Dict[str, str] = {}
            if all_ids:
                for cid, name in (
                    db.query(Canvas.id, Canvas.name)
                    .filter(Canvas.id.in_(all_ids))
                    .all()
                ):
                    canvas_names[cid] = name
            fallback_ids = []
            for row, _version_count in latest:
                details = row.details_json or {}
                if _audit_body(details) is None and "content" not in details and "data" not in details:
                    fallback_ids.append(row.canvas_id)
            canvas_content: Dict[str, Any] = {}
            if fallback_ids:
                for row in db.query(Canvas).filter(Canvas.id.in_(fallback_ids)).all():
                    canvas_content[row.id] = row.content

            # Goal-run back-links (GOAL_RUN_ORCHESTRATION.md): only canvases
            # that carry one — the gallery groups a goal's touch points by it.
            goal_run_links: Dict[str, str] = {}
            linked_ids = [cid for cid in all_ids]
            if linked_ids:
                for cid, grid in (
                    db.query(Canvas.id, Canvas.goal_run_id)
                    .filter(Canvas.id.in_(linked_ids), Canvas.goal_run_id.isnot(None))
                    .all()
                ):
                    goal_run_links[cid] = grid

            needle = (q or "").strip().lower()
            matches: list = []
            for row, version_count in latest:
                if row.action_type == "delete" and not include_deleted:
                    continue

                details = row.details_json or {}
                body = _audit_body(details)
                if body is None:
                    body = canvas_content.get(row.canvas_id)

                display_title = _derive_display_title(
                    row.canvas_type, details, body,
                    canvas_name=canvas_names.get(row.canvas_id),
                )

                if needle:
                    haystack = " ".join(
                        part.lower()
                        for part in (
                            display_title,
                            str(details.get("title") or ""),
                            row.canvas_type or "",
                            row.canvas_id,
                            _text_of(body),
                        )
                        if part
                    )
                    if needle not in haystack:
                        continue

                matches.append({
                    "canvas_id": row.canvas_id,
                    "canvas_type": row.canvas_type,
                    "action_type": row.action_type,
                    "title": details.get("title"),
                    "display_title": display_title,
                    "snippet": _content_snippet(body, q),
                    "deleted": row.action_type == "delete",
                    "last_updated": row.created_at.isoformat() if row.created_at else None,
                    "version": int(version_count or 1),
                    # Additive (GOAL_RUN_ORCHESTRATION.md §5): present only
                    # when the canvas was produced as a goal-run step.
                    **({"goal_run_id": goal_run_links[row.canvas_id]}
                       if row.canvas_id in goal_run_links else {}),
                })

            total = len(matches)
            if limit is None:
                # Internal full-set callers: no cap, no paging.
                page = matches[int(offset):]
            else:
                page_limit = max(1, min(int(limit), 200))
                page = matches[int(offset): int(offset) + page_limit]

            return {
                "success": True,
                "canvases": page,
                "count": len(page),
                "total": total,
            }
    except Exception as e:
        logger.error(f"Canvas list failed: {e}")
        return {"success": False, "error": str(e)}

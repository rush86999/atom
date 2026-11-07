"""
Concrete postcondition verifiers for high-risk mutating actions (W2, P3a).

Each verifier re-derives success against the system of record (NOT the tool's
own claim). Add new mutating actions here by ``@register_postcondition``.

Pattern (verify-before-retry, arXiv 2608.02645): on an ambiguous timeout,
call ``validate(action, ctx)`` BEFORE retrying — if the postcondition is
already met, the action succeeded despite the timeout; don't duplicate it.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, Optional

from core.oracle import OracleResult, register_postcondition

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: Any) -> str:
    return str(value or "").strip().lower()


def _valid_digest(value: Any) -> bool:
    return bool(_SHA256_RE.match(_digest(value)))


def _first_field(fields: Any, names: Iterable[str]) -> Optional[Any]:
    if not isinstance(fields, dict):
        return None
    for name in names:
        value = fields.get(name)
        if value not in (None, "", [], {}):
            return value
    return None


def _material_fields(action: str) -> tuple:
    """Required material-field aliases for each connected mutation class."""
    if action.endswith("books.create_estimate"):
        return (
            ("customer_id",),
            ("currency_code", "currency"),
            ("date", "estimate_date"),
            ("reference_number",),
            ("total", "grand_total"),
            ("line_items", "lines"),
        )
    if action.endswith("books.create_bill"):
        return (
            ("vendor_id",),
            ("currency_code", "currency"),
            ("date", "bill_date"),
            ("reference_number", "bill_number"),
            ("total", "grand_total"),
            ("line_items", "lines"),
        )
    if action.endswith("outlook.create_draft"):
        return (
            ("subject",),
            ("body",),
            ("toRecipients", "to_recipients"),
        )
    return ()


@register_postcondition("trigger_workflow")
async def _verify_workflow_triggered(ctx: Dict[str, Any]) -> OracleResult:
    """A triggered workflow must actually exist in the DB and be runnable."""
    workflow_id = ctx.get("workflow_id")
    db = ctx.get("db")
    if not workflow_id or not db:
        return OracleResult("trigger_workflow", False, "missing workflow_id or db session")
    try:
        from core.models import Workflow
        wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if wf is None:
            return OracleResult("trigger_workflow", False, f"workflow {workflow_id} not in DB")
        active = str(getattr(wf, "status", "")).lower() in {"active", "running", "enabled", "true"}
        return OracleResult(
            "trigger_workflow", verified=active,
            evidence=f"workflow.status == {getattr(wf, 'status', None)!r}",
        )
    except Exception as e:
        return OracleResult("trigger_workflow", False, f"DB read-back failed: {e}")


async def _verify_connected_mutation(ctx: Dict[str, Any]) -> OracleResult:
    """Verify a registered connected write's authoritative readback receipt.

    The production action already performs provider readback. The oracle
    independently checks that the returned receipt is bound to the same remote
    object, carries a syntactically valid payload digest that agrees with the
    independently supplied request digest, and did not report an uncertain,
    conflict or incomplete verification. It never treats a bare success label
    as proof.
    """
    action = str(ctx.get("_oracle_action") or "connected.mutation")
    if str(ctx.get("action_result") or "").strip().lower() != "applied":
        return OracleResult(
            action, False,
            f"action_result == {ctx.get('action_result')!r}, not applied")
    remote_id = str(ctx.get("remote_id") or "").strip()
    if not remote_id:
        return OracleResult(action, False, "no remote_id in the result")
    read_receipt = ctx.get("read_receipt")
    if not isinstance(read_receipt, dict) or not read_receipt:
        return OracleResult(action, False, "no authoritative read_receipt")
    if str(read_receipt.get("resource_id") or "") != remote_id:
        return OracleResult(
            action, False,
            "read_receipt.resource_id does not match remote_id")
    coverage = str(read_receipt.get("coverage") or "").lower()
    if coverage not in {"single", "complete"}:
        return OracleResult(
            action, False, f"read_receipt.coverage == {coverage!r}")
    fields = read_receipt.get("fields")
    if not isinstance(fields, dict) or not fields:
        return OracleResult(
            action, False,
            "read_receipt carries no complete material-field mapping")
    required = _material_fields(action)
    missing_material = [
        aliases[0] for aliases in required
        if _first_field(fields, aliases) is None
    ]
    if missing_material:
        return OracleResult(
            action, False,
            "read_receipt is missing material field(s): "
            + ", ".join(missing_material))
    verification = ctx.get("verification")
    if not isinstance(verification, dict) or not verification:
        return OracleResult(
            action, False, "no explicit verification object")
    status = str(verification.get("status") or "").lower()
    if status != "verified":
        return OracleResult(
            action, False, f"verification.status == {status!r}, not verified")
    if verification.get("mismatches"):
        return OracleResult(
            action, False, "verification reports mismatches")
    if verification.get("missing_fields"):
        return OracleResult(
            action, False, "verification reports missing fields")
    receipt = ctx.get("provider_receipt")
    receipt = receipt if isinstance(receipt, dict) else {}
    top_digest = _digest(ctx.get("payload_sha256"))
    receipt_digest = _digest(receipt.get("payload_sha256"))
    if not top_digest or not receipt_digest:
        return OracleResult(action, False, "no payload digest in the receipt")
    if not _valid_digest(top_digest) or not _valid_digest(receipt_digest):
        return OracleResult(
            action, False, "payload digest is not a 64-character hex digest")
    if top_digest != receipt_digest:
        return OracleResult(
            action, False,
            "top-level and provider-receipt payload digests disagree")
    expected_digest = _digest(
        ctx.get("_oracle_expected_payload_sha256"))
    if expected_digest:
        if not _valid_digest(expected_digest):
            return OracleResult(
                action, False,
                "expected request payload digest is malformed")
        if expected_digest != top_digest:
            return OracleResult(
                action, False,
                "returned payload digest does not match the expected request")
    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "")
    if expected_operation:
        observed_operation = str(
            receipt.get("operation_id") or verification.get("operation_id")
            or "")
        if not observed_operation:
            return OracleResult(
                action, False,
                "provider receipt carries no operation identity")
        if observed_operation != expected_operation:
            return OracleResult(
                action, False,
                "returned operation id does not match the expected operation")
    expected_org = str(
        ctx.get("_oracle_expected_organization_id") or "")
    if expected_org:
        observed_org = str(
            read_receipt.get("account_id")
            or read_receipt.get("organization_id") or "")
        if not observed_org:
            return OracleResult(
                action, False,
                "readback carries no account/organization identity")
        if observed_org != expected_org:
            return OracleResult(
                action, False,
                "readback account/organization does not match the request")
    expected_provider = str(
        ctx.get("_oracle_expected_provider") or "")
    if expected_provider:
        observed_provider = str(ctx.get("provider") or "")
        if not observed_provider:
            return OracleResult(
                action, False, "result carries no provider identity")
        if observed_provider != expected_provider:
            return OracleResult(
                action, False,
                "result provider does not match the expected provider")
        receipt_provider = str(read_receipt.get("provider") or "")
        if receipt_provider and receipt_provider != expected_provider:
            return OracleResult(
                action, False,
                "readback provider does not match the expected provider")
    expected_target = str(
        ctx.get("_oracle_expected_target") or "")
    if expected_target:
        observed_target = _first_field(
            fields, ("reference_number", "bill_number", "external_id",
                     "subject"))
        if observed_target is None:
            return OracleResult(
                action, False,
                "readback carries no target identity")
        if " ".join(str(observed_target).split()).casefold() != (
                " ".join(expected_target.split()).casefold()):
            return OracleResult(
                action, False,
                "readback target does not match the authorized request")
    verification_digest = _digest(verification.get("payload_sha256"))
    if verification_digest:
        if not _valid_digest(verification_digest):
            return OracleResult(
                action, False,
                "verification payload digest is malformed")
        if verification_digest != top_digest:
            return OracleResult(
                action, False,
                "verification payload digest disagrees with the receipt")
    return OracleResult(
        action, True,
        f"remote {remote_id} read back ({coverage}); "
        f"payload {top_digest[:12]}")


def _connected_postcondition(action: str):
    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        return await _verify_connected_mutation(
            {**ctx, "_oracle_action": action})
    return _verify


for _action in (
    "brennan.books.create_bill",
    "brennan.books.create_estimate",
    "brennan.outlook.create_draft",
    "connected.books.create_bill",
    "connected.books.create_estimate",
    "connected.outlook.create_draft",
):
    register_postcondition(_action)(_connected_postcondition(_action))


@register_postcondition("mini_app_set_tests")
async def _verify_mini_app_set_tests(ctx: Dict[str, Any]) -> OracleResult:
    """Independent readback for a mini-app manifest write.

    The handler appends a CanvasAudit row with the exact tests digest and the
    executor-owned operation id. This verifier requires BOTH that receipt and
    the persisted manifest to match the frozen authorized request, so neither
    an old identical row nor the handler's own success flag can certify a new
    operation.
    """
    action = "mini_app_set_tests"
    app_id = str(
        ctx.get("_oracle_expected_app_id") or ctx.get("app_id") or "").strip()
    expected_tests = ctx.get("_oracle_expected_tests")
    if expected_tests is None:
        expected_tests = ctx.get("tests")
    expected_operation = str(
        ctx.get("_oracle_expected_operation_id") or "").strip()
    audit_id = str(ctx.get("audit_id") or "").strip()
    expected_tenant = str(ctx.get("_oracle_expected_tenant_id") or "")
    expected_workspace = str(ctx.get("_oracle_expected_workspace_id") or "")
    expected_actor = str(ctx.get("_oracle_expected_actor_id") or "")
    if not app_id:
        return OracleResult(action, False, "missing app_id")
    if not isinstance(expected_tests, list):
        return OracleResult(
            action, False, "no frozen acceptance-test request")
    if not expected_operation:
        return OracleResult(
            action, False, "no frozen operation identity")
    if not audit_id:
        return OracleResult(
            action, False, "no audit receipt from this invocation")
    if not expected_tenant:
        return OracleResult(
            action, False, "no frozen tenant identity")
    if not expected_actor:
        return OracleResult(
            action, False, "no frozen actor identity")
    try:
        from core.task_lifecycle import _approval_payload_hash

        expected_digest = str(
            ctx.get("_oracle_expected_tests_sha256") or ""
        ) or _approval_payload_hash(expected_tests)
    except Exception as exc:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(
            action, False, f"test request digest unavailable: {exc}")

    def _read(session):
        from core.models import Canvas, CanvasAudit, MiniApp

        app = session.query(MiniApp).filter(MiniApp.id == app_id).first()
        audit = (
            session.query(CanvasAudit)
            .filter(CanvasAudit.id == audit_id)
            .first()
        )
        canvas = None
        if app is not None and app.blueprint_canvas_id:
            canvas = (
                session.query(Canvas)
                .filter(Canvas.id == app.blueprint_canvas_id)
                .first()
            )
        return app, audit, canvas

    def _same(actual, expected) -> bool:
        return str(actual or "") == str(expected or "")

    try:
        # Fresh session: the caller's session/identity map is never used to
        # certify authoritative columns. Peer commits are visible; dirty
        # request objects are not.
        app, audit, canvas = _fresh_read_with_db(ctx, _read)
        if app is None:
            return OracleResult(
                action, False, f"MiniApp {app_id} absent in DB")
        if audit is None:
            return OracleResult(
                action, False,
                f"audit receipt {audit_id[:12]} absent for this app")
        if canvas is None:
            return OracleResult(
                action, False,
                f"blueprint canvas {app.blueprint_canvas_id!r} absent")
        details = audit.details_json or {}
        if isinstance(details, str):
            details = json.loads(details)
        details = details if isinstance(details, dict) else {}
        manifest = app.manifest if isinstance(app.manifest, dict) else {}
        reasons = []
        # Authoritative MiniApp scope/owner must match the frozen request.
        if not _same(app.tenant_id, expected_tenant):
            reasons.append(
                f"app tenant={app.tenant_id!r}, expected "
                f"{expected_tenant!r}")
        if not _same(app.workspace_id, expected_workspace):
            reasons.append(
                f"app workspace={app.workspace_id!r}, expected "
                f"{expected_workspace!r}")
        if not _same(app.created_by, expected_actor):
            reasons.append(
                f"app owner={app.created_by!r}, expected {expected_actor!r}")
        if not app.blueprint_canvas_id:
            reasons.append("app has no blueprint canvas")
        # The authoritative audit row and blueprint canvas must be the same
        # current objects, at the same scope.
        if str(audit.canvas_id or "") != str(app.blueprint_canvas_id or ""):
            reasons.append("audit canvas does not match app blueprint canvas")
        if str(canvas.id or "") != str(app.blueprint_canvas_id or ""):
            reasons.append("blueprint canvas identity mismatch")
        if not _same(canvas.tenant_id, expected_tenant):
            reasons.append(
                f"canvas tenant={canvas.tenant_id!r}, expected "
                f"{expected_tenant!r}")
        if not _same(canvas.workspace_id, expected_workspace):
            reasons.append(
                f"canvas workspace={canvas.workspace_id!r}, expected "
                f"{expected_workspace!r}")
        if str(audit.action_type or "") != action:
            reasons.append(f"audit action_type={audit.action_type!r}")
        if not _same(audit.tenant_id, expected_tenant):
            reasons.append(
                f"audit tenant={audit.tenant_id!r}, expected "
                f"{expected_tenant!r}")
        if not _same(audit.user_id, expected_actor):
            reasons.append(
                f"audit actor={audit.user_id!r}, expected {expected_actor!r}")
        # Details are corroboration, never a fallback for an authoritative
        # contradiction above.
        if not _same(details.get("app_id"), app_id):
            reasons.append("audit app_id does not match the request")
        if not _same(details.get("tests_sha256"), expected_digest):
            reasons.append("audit tests digest does not match the request")
        if not _same(details.get("operation_id"), expected_operation):
            reasons.append("audit operation id does not match this operation")
        if not _same(details.get("tenant_id"), expected_tenant):
            reasons.append("audit details tenant does not match the request")
        if not _same(details.get("workspace_id"), expected_workspace):
            reasons.append(
                "audit details workspace does not match the request")
        if not _same(details.get("actor_id"), expected_actor):
            reasons.append("audit details actor does not match the request")
        if manifest.get("tests") != expected_tests:
            reasons.append("persisted manifest tests do not match the request")
        return OracleResult(
            action, not reasons,
            f"MiniApp {app_id} manifest tests={len(manifest.get('tests') or [])} "
            f"audit={audit_id[:12]} operation={expected_operation[:12]} "
            f"scope={expected_tenant}/{expected_workspace}/{expected_actor}"
            + ("" if not reasons else "; " + "; ".join(reasons)))
    except Exception as e:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(
            action, False, f"mini-app read-back failed: {e}")


@register_postcondition("tasks.create")
async def _verify_task_created(ctx: Dict[str, Any]) -> OracleResult:
    """A created task must persist to the DB (not just be returned by the tool)."""
    task = ctx.get("task") if isinstance(ctx.get("task"), dict) else {}
    task_id = str(ctx.get("task_id") or task.get("id") or "")
    if not task_id:
        return OracleResult("tasks.create", False, "missing task id")

    def _read(session):
        from core.models_board import BoardTask
        return session.query(BoardTask).filter(
            BoardTask.id == task_id).first()

    try:
        row = _read_with_db(ctx, _read)
        if row is None:
            return OracleResult(
                "tasks.create", False,
                f"BoardTask {task_id} absent in DB")
        expected_title = str(
            ctx.get("_oracle_expected_task_title")
            or ctx.get("title") or "")
        expected_board = str(
            ctx.get("_oracle_expected_board_id")
            or ctx.get("board_id") or "")
        verified = True
        if expected_title:
            verified = verified and str(row.title or "") == expected_title
        if expected_board:
            verified = (
                verified and str(row.board_id or "") == expected_board)
        return OracleResult(
            "tasks.create", verified,
            f"BoardTask {task_id} title={row.title!r} "
            f"board={row.board_id!r}")
    except Exception as e:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(
            "tasks.create", False, f"DB read-back failed: {e}")


def _content_digest(value: Any) -> str:
    blob = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def canvas_content_digest(value: Any) -> str:
    """Public alias for the canonical canvas material digest.

    The direct HTTP write service must freeze the SAME material the oracle
    verifier reads back. Keeping one digest prevents a self-consistent
    parallel representation from passing while the real consumer sees a
    different value.
    """
    return _content_digest(value)


def _read_with_db(ctx: Dict[str, Any], reader):
    db = ctx.get("db")
    if db is not None:
        return reader(db)
    from core.database import get_db_session
    with get_db_session() as session:
        return reader(session)


def _fresh_read_with_db(ctx: Dict[str, Any], reader):
    """Read through a NEW session bound to the caller's store.

    Verification must not reuse the caller's identity map or uncommitted
    request objects: a dirty in-memory object could otherwise certify an
    authoritative row it does not match. The predecessor session is only used
    to discover the engine; the read runs in its own session.
    """
    db = ctx.get("db") or ctx.get("session")
    if db is not None:
        from sqlalchemy.orm import sessionmaker

        bind = db.get_bind()
        engine = getattr(bind, "engine", bind)
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        session = Session()
        try:
            return reader(session)
        finally:
            session.close()
    from core.database import get_db_session
    with get_db_session() as session:
        return reader(session)


def _canvas_present_postcondition(component_type: str):
    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        action = str(ctx.get("_oracle_action") or "canvas.present")
        canvas_id = str(
            ctx.get("_oracle_expected_canvas_id")
            or ctx.get("canvas_id") or ctx.get("remote_id") or "").strip()
        audit_id = str(ctx.get("audit_id") or "").strip()
        expected_material_digest = str(
            ctx.get("_oracle_expected_material_sha256") or "").strip()
        expected_operation = str(
            ctx.get("_oracle_expected_operation_id") or "").strip()
        if not canvas_id:
            return OracleResult(action, False, "missing canvas_id")
        if not audit_id:
            return OracleResult(
                action, False,
                "no audit_id from the current presentation invocation")
        if not expected_material_digest:
            return OracleResult(
                action, False,
                "no frozen material digest for the presentation")
        if not expected_operation:
            return OracleResult(
                action, False,
                "no frozen operation identity for the presentation")

        def _read(session):
            from core.models import CanvasAudit
            return (
                session.query(CanvasAudit)
                .filter(CanvasAudit.id == audit_id,
                        CanvasAudit.canvas_id == canvas_id)
                .first()
            )

        try:
            row = _read_with_db(ctx, _read)
            if row is None:
                return OracleResult(
                    action, False,
                    f"canvas_audit {audit_id[:12]} not found for canvas "
                    f"{canvas_id}")
            details = row.details_json or {}
            if isinstance(details, str):
                details = json.loads(details)
            details = details if isinstance(details, dict) else {}
            observed_component = str(details.get("component_type") or "")
            observed_operation = str(details.get("operation_id") or "")
            observed_digest = str(details.get("material_sha256") or "")
            observed_material = details.get("material")
            from core.presentation_material import material_sha256
            computed_digest = (
                material_sha256(observed_material)
                if isinstance(observed_material, dict) else "")
            expected_workspace = str(
                ctx.get("_oracle_expected_workspace_id") or "")
            expected_tenant = str(
                ctx.get("_oracle_expected_tenant_id") or "")
            observed_workspace = str(details.get("workspace_id") or "")
            observed_tenant = str(
                details.get("tenant_id") or row.tenant_id or "")
            reasons = []
            if str(row.action_type or "") != "present":
                reasons.append(f"action_type={row.action_type!r}")
            if observed_component != component_type:
                reasons.append(f"component_type={observed_component!r}")
            if observed_operation != expected_operation:
                reasons.append(
                    f"operation_id={observed_operation!r}, expected "
                    f"{expected_operation!r}")
            if not observed_material or not observed_digest:
                reasons.append("audit carries no material/digest")
            elif observed_digest != computed_digest:
                reasons.append("audit material digest does not match its material")
            elif observed_digest != expected_material_digest:
                reasons.append("audit material does not match the authorized request")
            if expected_workspace and observed_workspace != expected_workspace:
                reasons.append(
                    f"workspace={observed_workspace!r}, expected "
                    f"{expected_workspace!r}")
            if expected_tenant and observed_tenant != expected_tenant:
                reasons.append(
                    f"tenant={observed_tenant!r}, expected {expected_tenant!r}")
            verified = not reasons
            return OracleResult(
                action, verified,
                f"canvas_audit {row.id} action_type={row.action_type!r} "
                f"component_type={observed_component!r} "
                f"operation={observed_operation!r} "
                f"material={observed_digest[:12]}"
                + ("" if verified else "; " + "; ".join(reasons)))
        except Exception as e:  # noqa: BLE001 - unreadable is not verified
            return OracleResult(
                action, False, f"audit read-back failed: {e}")
    return _verify


def _canvas_write_postcondition(restore: bool):
    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        action = str(ctx.get("_oracle_action") or "canvas.update")
        canvas_id = str(
            ctx.get("_oracle_expected_canvas_id")
            or ctx.get("canvas_id") or "").strip()
        if not canvas_id:
            return OracleResult(action, False, "missing canvas_id")
        expected_tenant = str(
            ctx.get("_oracle_expected_tenant_id") or "").strip()
        expected_workspace = str(
            ctx.get("_oracle_expected_workspace_id") or "").strip()
        expected_actor = str(
            ctx.get("_oracle_expected_actor_id") or "").strip()
        write_outcome = str(ctx.get("write_outcome") or "")
        no_change = bool(ctx.get("no_change"))

        def _read_canvas(session):
            from core.models import Canvas
            return (
                session.query(Canvas)
                .filter(Canvas.id == canvas_id)
                .first()
            )

        def _scope_value_allowed(observed, expected):
            """Mirror the writer's legacy/default scope rule."""
            observed = str(observed or "").strip()
            expected = str(expected or "").strip()
            if not observed:
                return True
            if expected:
                return observed == expected
            return observed.lower() == "default"

        def _scope_reasons(row, canvas, *, check_actor: bool):
            reasons = []
            strict_scope = bool(ctx.get("_oracle_require_scope_match"))
            if expected_tenant or strict_scope:
                if not _scope_value_allowed(row.tenant_id, expected_tenant):
                    reasons.append(
                        f"audit tenant={row.tenant_id!r}, expected "
                        f"{expected_tenant!r}")
            if canvas is None:
                reasons.append("canvas mirror missing")
            else:
                if (expected_tenant or strict_scope) and (
                        not _scope_value_allowed(
                            canvas.tenant_id, expected_tenant)):
                    reasons.append(
                        f"canvas tenant={canvas.tenant_id!r}, expected "
                        f"{expected_tenant!r}")
                if (expected_workspace or strict_scope) and (
                        not _scope_value_allowed(
                            canvas.workspace_id, expected_workspace)):
                    reasons.append(
                        f"canvas workspace={canvas.workspace_id!r}, expected "
                        f"{expected_workspace!r}")
            if check_actor and expected_actor:
                if str(row.user_id or "") != expected_actor:
                    reasons.append(
                        f"audit actor={row.user_id!r}, expected "
                        f"{expected_actor!r}")
            return reasons

        def _read_new(session, audit_id: str):
            from core.models import CanvasAudit, Canvas
            row = (
                session.query(CanvasAudit)
                .filter(CanvasAudit.id == audit_id,
                        CanvasAudit.canvas_id == canvas_id)
                .first()
            )
            canvas = (
                session.query(Canvas)
                .filter(Canvas.id == canvas_id)
                .first()
            )
            return row, canvas

        def _read_audit(session, audit_id: str):
            from core.models import CanvasAudit
            return (
                session.query(CanvasAudit)
                .filter(CanvasAudit.id == audit_id,
                        CanvasAudit.canvas_id == canvas_id)
                .first()
            )

        def _latest(session):
            from core.models import CanvasAudit
            from sqlalchemy import desc
            return (
                session.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == canvas_id)
                .order_by(desc(CanvasAudit.created_at),
                          desc(CanvasAudit.id))
                .first()
            )

        def _details(row):
            value = row.details_json or {}
            if isinstance(value, str):
                value = json.loads(value)
            return value or {}

        def _latest_content(session):
            """Latest CONTENT revision, skipping event-only audit stamps.

            A send/event row can append after the write without carrying a
            body. Recency must compare against the current content revision,
            not the absolute newest event row.
            """
            from core.models import CanvasAudit
            from sqlalchemy import desc

            rows = (
                session.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == canvas_id)
                .order_by(desc(CanvasAudit.created_at),
                          desc(CanvasAudit.id))
                .limit(50)
                .all()
            )
            for candidate in rows:
                details = _details(candidate)
                if "content" in details or "data" in details:
                    return candidate
            return rows[0] if rows else None

        try:
            if no_change:
                target_id = str(
                    ctx.get("_oracle_expected_restore_audit_id")
                    or ctx.get("restored_from") or "")
                if not target_id:
                    return OracleResult(
                        action, False, "no-change restore has no target audit")
                target = _read_with_db(
                    ctx, lambda session: _read_audit(session, target_id))
                latest = _read_with_db(ctx, _latest_content)
                if target is None or latest is None:
                    return OracleResult(
                        action, False,
                        "no-change restore could not read the target/current "
                        "version")
                if str(target.action_type or "") == "delete":
                    return OracleResult(
                        action, False,
                        "no-change target is a deletion marker")
                target_details = _details(target)
                if ("content" not in target_details
                        and "data" not in target_details):
                    return OracleResult(
                        action, False,
                        "no-change target carries no restorable content")
                canvas = _read_with_db(ctx, _read_canvas)
                scope_reasons = _scope_reasons(
                    latest, canvas, check_actor=False)
                if scope_reasons:
                    return OracleResult(
                        action, False, "; ".join(scope_reasons))
                if canvas is None:
                    return OracleResult(
                        action, False,
                        "no-change restore has no authoritative canvas "
                        "mirror")
                expected_target_tenant = expected_tenant or str(
                    canvas.tenant_id or "")
                if not _scope_value_allowed(
                        target.tenant_id, expected_target_tenant):
                    return OracleResult(
                        action, False,
                        f"target audit tenant={target.tenant_id!r}, expected "
                        f"{expected_target_tenant!r}")
                from tools.canvas_crud_tool import (
                    canonical_restore_content,
                )

                _, restored_content = canonical_restore_content(
                    latest, target)
                if restored_content is None:
                    return OracleResult(
                        action, False,
                        "no-change target carries no restorable content")
                target_digest = _content_digest(restored_content)
                latest_digest = _content_digest(
                    _details(latest).get("content",
                                         _details(latest).get("data")))
                mirror_digest = _content_digest(canvas.content)
                verified = (
                    target_digest == latest_digest == mirror_digest)
                return OracleResult(
                    action, verified,
                    f"no-change restore target {target_id[:12]} "
                    f"content_match={target_digest == latest_digest} "
                    f"mirror_match={latest_digest == mirror_digest}")
            if write_outcome and write_outcome != "committed":
                return OracleResult(
                    action, False,
                    f"write_outcome == {write_outcome!r}, not committed")
            new_audit_id = str(ctx.get("audit_id") or "")
            if not new_audit_id:
                return OracleResult(
                    action, False, "no appended audit_id in the result")
            row, canvas = _read_with_db(
                ctx, lambda session: _read_new(session, new_audit_id))
            if row is None:
                return OracleResult(
                    action, False,
                    f"canvas_audit {new_audit_id[:12]} not found")
            scope_reasons = _scope_reasons(row, canvas, check_actor=True)
            if scope_reasons:
                return OracleResult(
                    action, False, "; ".join(scope_reasons))
            if str(row.action_type or "") != "update":
                return OracleResult(
                    action, False,
                    f"canvas_audit action_type == {row.action_type!r}")
            latest_content = _read_with_db(ctx, _latest_content)
            if (latest_content is None
                    or str(latest_content.id) != new_audit_id):
                return OracleResult(
                    action, False,
                    "audit is not the current content revision; a later "
                    "content audit exists")
            details = _details(row)
            observed_content = details.get("content", details.get("data"))
            if restore:
                expected_operation = str(
                    ctx.get("_oracle_expected_operation_id") or "")
                if expected_operation and str(
                        details.get("operation_id") or ""
                ) != expected_operation:
                    return OracleResult(
                        action, False,
                        "restore audit operation_id does not match the "
                        "authorized operation")
                expected_target = str(
                    ctx.get("_oracle_expected_restore_audit_id") or "")
                restored_from = details.get("restored_from") or {}
                observed_target = str(
                    restored_from.get("audit_id") or "") if isinstance(
                        restored_from, dict) else ""
                if not expected_target:
                    return OracleResult(
                        action, False,
                        "restore has no frozen target audit id")
                if observed_target != expected_target:
                    return OracleResult(
                        action, False,
                        "restored_from does not match the authorized target")
                target = _read_with_db(
                    ctx, lambda session: _read_audit(
                        session, expected_target))
                if target is None:
                    return OracleResult(
                        action, False, "authorized target version not found")
                if str(target.action_type or "") == "delete":
                    return OracleResult(
                        action, False,
                        "authorized target is a deletion marker")
                expected_target_tenant = expected_tenant
                if not expected_target_tenant and canvas is not None:
                    expected_target_tenant = str(canvas.tenant_id or "")
                if not _scope_value_allowed(
                        target.tenant_id, expected_target_tenant):
                    return OracleResult(
                        action, False,
                        f"target audit tenant={target.tenant_id!r}, expected "
                        f"{expected_target_tenant!r}")
                from tools.canvas_crud_tool import (
                    canonical_restore_content,
                )

                _, restored_content = canonical_restore_content(row, target)
                if restored_content is None:
                    return OracleResult(
                        action, False,
                        "authorized target carries no restorable content")
                expected_digest = _content_digest(restored_content)
            else:
                expected_digest = str(
                    ctx.get("_oracle_expected_canvas_content_sha256") or "")
                if not expected_digest:
                    if "content" not in ctx:
                        return OracleResult(
                            action, False,
                            "authorized content was not captured")
                    expected_digest = _content_digest(ctx.get("content"))
                expected_operation = str(
                    ctx.get("_oracle_expected_operation_id") or "")
                if expected_operation:
                    if str(details.get("operation_id") or "") != expected_operation:
                        return OracleResult(
                            action, False,
                            "audit operation_id does not match the authorized "
                            "operation")
                expected_review = str(
                    ctx.get("_oracle_expected_review_status") or "")
                if expected_review:
                    if str(details.get("review_status") or "") != expected_review:
                        return OracleResult(
                            action, False,
                            "audit review_status does not match the authorized "
                            "request")
            observed_digest = _content_digest(observed_content)
            if observed_digest != expected_digest:
                return OracleResult(
                    action, False,
                    "persisted canvas content does not match the authorized "
                    "content")
            review_status = str(details.get("review_status") or "accepted")
            if canvas is not None and review_status == "accepted":
                canvas_digest = _content_digest(canvas.content)
                if canvas_digest != observed_digest:
                    return OracleResult(
                        action, False,
                        "accepted canvas mirror does not match the audit content")
            return OracleResult(
                action, True,
                f"canvas_audit {new_audit_id[:12]} action_type=update "
                f"content={observed_digest[:12]} canvas_id={canvas_id}")
        except Exception as e:  # noqa: BLE001 - unreadable is not verified
            return OracleResult(
                action, False, f"canvas read-back failed: {e}")
    return _verify


def _goal_postcondition(mode: str):
    async def _verify(ctx: Dict[str, Any]) -> OracleResult:
        action = str(ctx.get("_oracle_action") or "goals")
        expected_goal_id = str(
            ctx.get("_oracle_expected_goal_id") or "")
        try:
            if mode == "create":
                goal = ctx.get("goal") or {}
                goal_id = str(goal.get("id") or expected_goal_id or "")
                if not goal_id:
                    return OracleResult(action, False, "missing goal id")

                def _read(session):
                    from core.models import GoalObjective
                    return session.query(GoalObjective).filter(
                        GoalObjective.id == goal_id).first()

                row = _read_with_db(ctx, _read)
                if row is None:
                    return OracleResult(
                        action, False, f"goal {goal_id} not persisted")
                expected_title = str(
                    ctx.get("_oracle_expected_goal_title") or "")
                expected_workspace = str(
                    ctx.get("_oracle_expected_workspace_id") or "")
                verified = True
                if expected_title:
                    verified = verified and str(row.title or "") == expected_title
                if expected_workspace:
                    verified = (
                        verified
                        and str(row.workspace_id or "") == expected_workspace)
                return OracleResult(
                    action, verified,
                    f"GoalObjective {goal_id} title={row.title!r} "
                    f"workspace={row.workspace_id!r}")
            if mode == "evaluate":
                goal_id = expected_goal_id or str(ctx.get("goal_id") or "")
                if not goal_id:
                    return OracleResult(action, False, "missing goal id")
                if ctx.get("error"):
                    return OracleResult(
                        action, False, f"goal evaluation error: {ctx['error']}")

                def _read(session):
                    from core.models import GoalObjective
                    return session.query(GoalObjective).filter(
                        GoalObjective.id == goal_id).first()

                row = _read_with_db(ctx, _read)
                if row is None:
                    return OracleResult(
                        action, False, f"goal {goal_id} not persisted")
                result_status = str(ctx.get("status") or "")
                result_progress = ctx.get("progress")
                if not result_status and result_progress is None:
                    return OracleResult(
                        action, False,
                        "the evaluation returned no status/progress "
                        "observation to compare with the persisted goal")
                verified = True
                if result_status:
                    verified = verified and str(row.status or "") == result_status
                if result_progress is not None:
                    try:
                        verified = (
                            verified
                            and abs(float(row.progress or 0)
                                    - float(result_progress)) < 0.01)
                    except (TypeError, ValueError):
                        verified = False
                return OracleResult(
                    action, verified,
                    f"GoalObjective {goal_id} status={row.status!r} "
                    f"progress={row.progress!r}")
            if mode == "run":
                run = ctx.get("run") or {}
                run_id = str(ctx.get("id") or run.get("id") or "")
                if not run_id:
                    return OracleResult(action, False, "missing run id")

                def _read(session):
                    from core.models import GoalRun
                    return session.query(GoalRun).filter(
                        GoalRun.id == run_id).first()

                row = _read_with_db(ctx, _read)
                if row is None:
                    return OracleResult(
                        action, False, f"goal run {run_id} not persisted")
                expected_agent = str(
                    ctx.get("_oracle_expected_agent_id") or "")
                verified = True
                if expected_goal_id:
                    verified = (
                        verified
                        and str(row.goal_id or "") == expected_goal_id)
                if expected_agent:
                    verified = (
                        verified
                        and str(row.agent_id or "") == expected_agent)
                if str(row.status or "").lower() in {"failed", "cancelled"}:
                    verified = False
                return OracleResult(
                    action, verified,
                    f"GoalRun {run_id} goal={row.goal_id!r} "
                    f"agent={row.agent_id!r} status={row.status!r}")
            return OracleResult(action, False, f"unknown goal mode {mode!r}")
        except Exception as e:  # noqa: BLE001 - unreadable is not verified
            return OracleResult(
                action, False, f"goal read-back failed: {e}")
    return _verify


@register_postcondition("goals.decompose")
async def _verify_plan_produced(ctx: Dict[str, Any]) -> OracleResult:
    action = "goals.decompose"
    plan = ctx.get("plan")
    if not isinstance(plan, dict):
        return OracleResult(action, False, "no plan object in the result")
    if plan.get("cycles"):
        return OracleResult(
            action, False,
            f"plan contains dependency cycles: {plan.get('cycles')!r}")
    subtasks = [item for item in (plan.get("subtasks") or [])
                if isinstance(item, dict)]
    if not subtasks:
        return OracleResult(action, False, "plan has no subtasks")
    ids = [str(item.get("id") or "") for item in subtasks]
    if any(not item for item in ids) or len(set(ids)) != len(ids):
        return OracleResult(
            action, False, "plan subtask ids are missing or duplicated")
    known = set(ids)
    for item in subtasks:
        for dependency in item.get("depends_on") or []:
            if str(dependency) not in known:
                return OracleResult(
                    action, False,
                    f"subtask {item.get('id')!r} depends on unknown "
                    f"{dependency!r}")
    groups = plan.get("execution_groups") or []
    grouped = {str(step) for group in groups if isinstance(group, list)
               for step in group}
    if grouped and grouped != known:
        return OracleResult(
            action, False,
            "execution groups do not cover exactly the subtasks")
    return OracleResult(
        action, True,
        f"plan method={plan.get('method')!r} subtasks={len(subtasks)} "
        f"groups={len(groups)}")


register_postcondition("canvas.present_markdown")(
    _canvas_present_postcondition("markdown"))
register_postcondition("canvas.present_chart")(
    _canvas_present_postcondition("chart"))
register_postcondition("canvas.update")(
    _canvas_write_postcondition(restore=False))
register_postcondition("canvas.restore_version")(
    _canvas_write_postcondition(restore=True))
register_postcondition("goals.create")(_goal_postcondition("create"))
register_postcondition("goals.evaluate")(_goal_postcondition("evaluate"))
register_postcondition("goal_runs.start")(_goal_postcondition("run"))

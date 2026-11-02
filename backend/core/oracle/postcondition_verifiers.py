"""
Concrete postcondition verifiers for high-risk mutating actions (W2, P3a).

Each verifier re-derives success against the system of record (NOT the tool's
own claim). Add new mutating actions here by ``@register_postcondition``.

Pattern (verify-before-retry, arXiv 2608.02645): on an ambiguous timeout,
call ``validate(action, ctx)`` BEFORE retrying — if the postcondition is
already met, the action succeeded despite the timeout; don't duplicate it.
"""
from __future__ import annotations

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


@register_postcondition("tasks.create")
async def _verify_task_created(ctx: Dict[str, Any]) -> OracleResult:
    """A created task must persist to the DB (not just be returned by the tool)."""
    task_id = ctx.get("task_id")
    db = ctx.get("db")
    if not task_id or not db:
        return OracleResult("tasks.create", False, "missing task_id or db session")
    try:
        from core.models_board import BoardTask
        exists = db.query(BoardTask).filter(BoardTask.id == task_id).first() is not None
        return OracleResult(
            "tasks.create", verified=exists,
            evidence=f"BoardTask {task_id} {'present' if exists else 'absent'} in DB",
        )
    except Exception as e:
        return OracleResult("tasks.create", False, f"DB read-back failed: {e}")


@register_postcondition("canvas.present_markdown")
async def _verify_canvas_markdown_presented(
        ctx: Dict[str, Any]) -> OracleResult:
    """A presented markdown canvas must exist in the audit system of record.

    The tool broadcasts over the websocket and returns its own success flag;
    neither is independent. The audit row written in the same dispatch is the
    durable record, so it is the authority here. A missing row, a failed
    query or a component mismatch is a refutation -- never a pass.
    """
    canvas_id = str(
        ctx.get("canvas_id") or ctx.get("remote_id") or "").strip()
    if not canvas_id:
        return OracleResult(
            "canvas.present_markdown", False, "missing canvas_id")
    db = ctx.get("db")

    def _read(session):
        from core.models import CanvasAudit
        return (
            session.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == canvas_id)
            .order_by(CanvasAudit.created_at.desc())
            .first()
        )

    try:
        if db is not None:
            row = _read(db)
        else:
            from core.database import get_db_session
            with get_db_session() as session:
                row = _read(session)
        if row is None:
            return OracleResult(
                "canvas.present_markdown", False,
                f"no canvas_audit row for canvas {canvas_id}")
        details = row.details_json or {}
        if isinstance(details, str):
            details = json.loads(details)
        component = str((details or {}).get("component_type") or "")
        verified = (
            str(row.action_type or "") == "present"
            and component == "markdown"
        )
        return OracleResult(
            "canvas.present_markdown", verified=verified,
            evidence=(
                f"canvas_audit {row.id} action_type={row.action_type!r} "
                f"component_type={component!r}"),
        )
    except Exception as e:  # noqa: BLE001 - unreadable is not verified
        return OracleResult(
            "canvas.present_markdown", False,
            f"audit read-back failed: {e}")

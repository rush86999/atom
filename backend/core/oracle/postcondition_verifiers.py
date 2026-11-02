"""
Concrete postcondition verifiers for high-risk mutating actions (W2, P3a).

Each verifier re-derives success against the system of record (NOT the tool's
own claim). Add new mutating actions here by ``@register_postcondition``.

Pattern (verify-before-retry, arXiv 2608.02645): on an ambiguous timeout,
call ``validate(action, ctx)`` BEFORE retrying — if the postcondition is
already met, the action succeeded despite the timeout; don't duplicate it.
"""
from __future__ import annotations

from typing import Any, Dict

from core.oracle import OracleResult, register_postcondition


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
    object, carries a payload digest, and did not report an uncertain,
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
    top_digest = str(ctx.get("payload_sha256") or "")
    receipt_digest = str(receipt.get("payload_sha256") or "")
    if not top_digest or not receipt_digest:
        return OracleResult(action, False, "no payload digest in the receipt")
    if top_digest != receipt_digest:
        return OracleResult(
            action, False,
            "top-level and provider-receipt payload digests disagree")
    verification_digest = str(verification.get("payload_sha256") or "")
    if verification_digest and verification_digest != top_digest:
        return OracleResult(
            action, False,
            "verification payload digest disagrees with the receipt")
    digest = top_digest
    return OracleResult(
        action, True,
        f"remote {remote_id} read back ({coverage}); "
        f"payload {digest[:12]}")


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

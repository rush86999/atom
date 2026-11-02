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

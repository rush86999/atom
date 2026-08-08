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


@register_postcondition("tasks.create")
async def _verify_task_created(ctx: Dict[str, Any]) -> OracleResult:
    """A created task must persist to the DB (not just be returned by the tool)."""
    task_id = ctx.get("task_id")
    db = ctx.get("db")
    if not task_id or not db:
        return OracleResult("tasks.create", False, "missing task_id or db session")
    try:
        from core.models import AgentTask
        exists = db.query(AgentTask).filter(AgentTask.id == task_id).first() is not None
        return OracleResult(
            "tasks.create", verified=exists,
            evidence=f"AgentTask {task_id} {'present' if exists else 'absent'} in DB",
        )
    except Exception as e:
        return OracleResult("tasks.create", False, f"DB read-back failed: {e}")

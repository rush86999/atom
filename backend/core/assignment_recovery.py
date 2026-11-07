"""Startup entrypoint for durable employee-assignment recovery.

The executor already owns ordinary re-entry (``recover_ready_assignments``):
it resumes eligible pending/waiting work, replays a wake committed before a
crash, and — as of the TASK-WAIT-01 process-recovery repair — hands durable
accepted evidence to the same adaptation consumer the public source route and
``/advance`` use.

What was missing was a boot caller. ``GoalRunService`` is workspace/tenant
scoped by design, so this thin startup adapter enumerates the active run scopes
and invokes that SAME owner once per scope. It is not a daemon, table or second
task engine: it is a bounded, one-shot startup pass (also safe to await from a
successor process) and every action remains scoped to the run's own
workspace/tenant.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_ACTIVE_RUN_STATUSES = ("planning", "active", "waiting", "paused_hitl")


async def recover_active_assignments_at_startup(
    *, limit: int = 50, max_steps_per_assignment: int = 20,
) -> List[Dict[str, Any]]:
    """Run the existing assignment recovery owner over active run scopes."""
    from core.assignment_executor import AssignmentExecutor
    from core.database import get_db_session
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.models import GoalRun
    from core.task_lifecycle import TaskLifecycle

    bound = max(1, min(int(limit), 200))
    with get_db_session() as db:
        scopes = (
            db.query(GoalRun.workspace_id, GoalRun.tenant_id)
            .filter(GoalRun.status.in_(_ACTIVE_RUN_STATUSES))
            .distinct()
            .limit(bound)
            .all()
        )
    results: List[Dict[str, Any]] = []
    for workspace_id, tenant_id in scopes:
        workspace_id = str(workspace_id or "default")
        tenant_id = str(tenant_id or "default")
        try:
            lifecycle = TaskLifecycle(
                GoalRunService(
                    workspace_id=workspace_id, tenant_id=tenant_id),
                GoalService(
                    workspace_id=workspace_id, tenant_id=tenant_id),
            )
            results.extend(await AssignmentExecutor(
                lifecycle).recover_ready_assignments(
                    limit=bound,
                    max_steps_per_assignment=max_steps_per_assignment))
        except Exception as exc:  # noqa: BLE001 — per-scope isolation
            logger.warning(
                "assignment startup recovery failed for %s/%s: %s",
                workspace_id, tenant_id, exc)
    if results:
        logger.info(
            "Assignment startup recovery: resumed %d active assignment(s)",
            len(results))
    return results

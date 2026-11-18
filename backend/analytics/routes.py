"""Analytics routes.

The durable workflow reviewer log readback lives on its own router.  That
router is mounted twice by the main application:

* ``/api/v1/analytics``          -> canonical reviewer log path
* ``/api/v1/analytics/analytics`` -> the pre-existing double-prefix alias

Keeping it separate restores the canonical log path without relocating the
long-standing analytics routes (heatmap/stats/optimize), whose paths are part
of the existing surface.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, false, func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import WorkflowExecution, WorkflowExecutionLog
from core.rbac_service import Permission
from core.security_dependencies import require_permission
from core.workflow_endpoints import (
    _authorize_execution_row,
    _caller_scope,
    _current_read_actor,
    _generated_definition_scope,
    _row_server_scope,
    _scope_matches_user,
)

# Router prefix is just "/analytics".
# The plugin registers it under "/api/v1/analytics", resulting in the legacy
# "/api/v1/analytics/analytics" surface for these established routes.
router = APIRouter(prefix="/analytics", tags=["Workflow DNA"])

# Reviewer log readback is mounted independently (see the module docstring) and
# therefore carries no local prefix: the mount supplies the version/segment.
workflow_logs_router = APIRouter(tags=["Workflow Logs"])

MAX_LOG_LIMIT = 200


class OptimizeRequest(BaseModel):
    workflow: Dict[str, Any]


class OptimizeResponse(BaseModel):
    suggestions: List[Dict[str, Any]]


def _owner_id(row: Any) -> str:
    """Durable owner binding for an execution row."""
    return str(
        getattr(row, "owner_id", None)
        or getattr(row, "user_id", None)
        or ""
    )


def _authorize_log_execution(user: Any, row: Any) -> bool:
    """Authorize one durable execution for reviewer log readback.

    The shared durable helpers supply the execution scope and the generated
    definition authority.  On top of that this reader requires *owner or
    matching durable scoped authority* for legacy rows, so a legacy row can no
    longer be read just because its definition is legacy-shaped.
    """
    if not _authorize_execution_row(user, row):
        return False

    resolved = _generated_definition_scope(
        str(getattr(row, "workflow_id", "") or "")
    )
    kind = resolved.get("kind")
    owner_id = _owner_id(row)

    if kind == "generated":
        # A generated execution without an owner binding is not reviewer
        # authority, and never falls back to a workspace/global grant.
        return bool(owner_id) and owner_id == str(user.id)

    # Legacy or unknown definition authority: the row must carry an owner that
    # is the caller, or a server-bound scope that matches the caller's durable
    # scope.  Anonymous legacy rows belong to nobody.
    if owner_id and owner_id == str(user.id):
        return True
    tenant_id, workspace_id = _row_server_scope(row)
    return _scope_matches_user(user, tenant_id, workspace_id)


def _log_scope_filter(user: Any, workflow_id: str):
    """SQL pre-filter for the joined execution rows.

    This runs before ``limit`` so unauthorized newest rows cannot starve an
    authorized page.  Workspace-scoped legacy context is still verified per
    row by :func:`_authorize_log_execution`.
    """
    resolved = _generated_definition_scope(str(workflow_id))
    kind = resolved.get("kind")
    owner_match = or_(
        WorkflowExecution.owner_id == str(user.id),
        WorkflowExecution.user_id == str(user.id),
    )
    tenant_id = str(_caller_scope(user).get("tenant_id") or "")

    if kind == "generated":
        # Generated rows are owner-bound; the shared helper checks the
        # definition tenant/workspace per row below.
        return owner_match
    if kind == "legacy":
        if tenant_id:
            return or_(owner_match, WorkflowExecution.tenant_id == tenant_id)
        return owner_match
    # Unknown definition authority: only a server-bound tenant row is a
    # positive grant.  Never treat "unknown" as implicit legacy authority.
    if tenant_id:
        return WorkflowExecution.tenant_id == tenant_id
    return false()


def _serialize_log(log: Any) -> Dict[str, Any]:
    """Project only reviewer-safe fields.

    Raw parameters/results (and the legacy trigger/results payloads) are
    deliberately omitted: they can contain secrets, credentials and complete
    upstream payloads.
    """
    created_at = getattr(log, "created_at", None)
    if created_at is not None and hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    return {
        "id": getattr(log, "id", None),
        "workflow_id": getattr(log, "workflow_id", None),
        "execution_id": getattr(log, "execution_id", None),
        "step_id": getattr(log, "step_id", None),
        "status": getattr(log, "status", None),
        "duration_ms": getattr(log, "duration_ms", None),
        "created_at": created_at,
    }


@router.get("/workflows/{workflow_id}/heatmap")
def get_workflow_heatmap(workflow_id: str, db: Session = Depends(get_db)):
    """
    Get aggregated performance metrics for a specific workflow's steps.
    Used to generate the 'Workflow DNA' heatmap.
    """
    # SQL: SELECT step_id, AVG(duration_ms), COUNT(*) ... GROUP BY step_id
    stats = db.query(
        WorkflowExecutionLog.step_id,
        func.avg(WorkflowExecutionLog.duration_ms).label("avg_duration"),
        func.count(WorkflowExecutionLog.id).label("total_runs"),
        func.sum(func.case((WorkflowExecutionLog.status == 'FAILED', 1), else_=0)).label("fail_count")
    ).filter(
        WorkflowExecutionLog.workflow_id == workflow_id
    ).group_by(
        WorkflowExecutionLog.step_id
    ).all()

    # Format as a dictionary map: { step_id: { metrics } }
    heatmap = {}
    for step_id, avg, total, fails in stats:
        heatmap[step_id] = {
            "avg_duration": round(avg or 0, 2),
            "total_runs": total,
            "failure_rate": round(fails / total, 2) if total > 0 else 0,
            "status": "red" if (avg > 5000 or (fails/total) > 0.1) else "green"
            # Simple heuristic: >5s or >10% fail = Red
        }

    return heatmap


@workflow_logs_router.get("/workflows/{workflow_id}/logs")
def get_workflow_logs(
    workflow_id: str,
    limit: int = Query(20, ge=1, le=MAX_LOG_LIMIT),
    user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
    db: Session = Depends(get_db),
):
    """Read reviewer-safe execution log rows for one workflow.

    Reads are bound to the caller's live durable actor/scope, the durable
    execution definition scope and the execution owner.  Both the canonical
    and legacy-alias mounts point at this single handler and therefore share
    the same ``WORKFLOW_VIEW`` permission gate.
    """
    scope = _caller_scope(user)
    if _current_read_actor(db, scope) is None:
        raise HTTPException(status_code=404, detail="Workflow logs not found")

    # Generated definitions are authentic only inside the caller's live
    # tenant/workspace scope; do not enumerate their logs from outside.
    resolved = _generated_definition_scope(str(workflow_id))
    if resolved.get("kind") == "generated" and not _scope_matches_user(
        user, resolved.get("tenant_id"), resolved.get("workspace_id")
    ):
        raise HTTPException(status_code=404, detail="Workflow logs not found")

    # Join the log to its durable execution on BOTH identifiers.  A log row
    # that only matches one identifier is not a reviewer-visible execution.
    joined = (
        db.query(WorkflowExecutionLog, WorkflowExecution)
        .join(
            WorkflowExecution,
            and_(
                WorkflowExecutionLog.workflow_id == WorkflowExecution.workflow_id,
                WorkflowExecutionLog.execution_id == WorkflowExecution.execution_id,
            ),
        )
        .filter(WorkflowExecutionLog.workflow_id == workflow_id)
        .filter(_log_scope_filter(user, workflow_id))
        .order_by(
            WorkflowExecutionLog.created_at.desc(),
            WorkflowExecutionLog.id.desc(),
        )
    )

    rows: List[Dict[str, Any]] = []
    for log, execution in joined:
        # Authorize before applying the page limit: row-level scope can only
        # be resolved in Python, and limiting first would let a foreign newest
        # row empty the page.
        if not _authorize_log_execution(user, execution):
            continue
        rows.append(_serialize_log(log))
        if len(rows) >= limit:
            break

    return rows


@router.get("/stats/glance")
def get_global_stats(db: Session = Depends(get_db)):
    """Quick stats for the dashboard"""
    total = db.query(func.count(WorkflowExecutionLog.id)).scalar()
    return {"total_steps_analyzed": total}


@router.post("/optimize")
def optimize_workflow(request: OptimizeRequest):
    """
    Analyze a workflow definition and return optimization suggestions.
    This is a static analysis that doesn't run the workflow.
    """
    try:
        # Imported lazily so the analytics router (and the reviewer log
        # readback) does not depend on the optimizer at import time.
        from analytics.optimizer import WorkflowOptimizer

        optimizer = WorkflowOptimizer()
        suggestions = optimizer.analyze(request.workflow)

        # Convert dataclasses to dicts for JSON response
        results = [
            {
                "type": s.type,
                "description": s.description,
                "affected_nodes": s.affected_nodes,
                "savings_estimate_ms": s.savings_estimate_ms,
                "action": s.action
            }
            for s in suggestions
        ]

        return OptimizeResponse(suggestions=results)
    except HTTPException:
        raise
    except Exception as e:
        # LOGIC FIX: Don't expose internal errors to clients
        # Log the actual error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Analytics optimization failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to optimize workflows. Please contact support if this persists."
        )

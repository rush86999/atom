"""
Agent Action Audit — read API for the per-decision audit trail.

Serves the rows written by core/agent_action_audit.py (event types
``agent_action`` and ``llm_call`` in saas_audit_logs) so accountants can
review every decision an AI agent made: which tools it invoked with which
arguments, which LLM calls it made with which model and prompt, and how
each run ended.

Endpoints (prefix /api/audit):
- GET /events                 — filterable event feed
- GET /executions             — list audited runs (from execution_start events)
- GET /executions/{id}        — full replayable timeline for one run
- GET /summary                — aggregate stats for dashboard headers
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import AgentExecution, AuditLog, User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])

# Event types owned by the agent action audit trail.
AUDIT_EVENT_TYPES = ("agent_action", "llm_call")
# agent_action sub-actions that bracket a run.
EXECUTION_START = "execution_start"
EXECUTION_COMPLETE = "execution_complete"


def _parse_metadata(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _execution_filter(execution_id: str):
    from core.agent_action_audit import execution_needle

    return AuditLog.metadata_json.like(f"%{execution_needle(execution_id)}%")


def _serialize_event(row: AuditLog) -> Dict[str, Any]:
    meta = _parse_metadata(row.metadata_json)
    return {
        "id": row.id,
        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        "event_type": row.event_type,
        "action": row.action,
        "description": row.description,
        "agent_id": meta.get("agent_id") or row.resource,
        "agent_execution_id": meta.get("agent_execution_id"),
        "user_id": row.user_id,
        "workspace_id": row.workspace_id,
        "success": row.success,
        "error_message": row.error_message,
        "metadata": meta,
    }


def _base_event_query(db: Session):
    return db.query(AuditLog).filter(AuditLog.event_type.in_(AUDIT_EVENT_TYPES))


# ---------------------------------------------------------------------------
# R89: the audit trail exposes ALL users' agent decisions — tool arguments,
# prompt excerpts, model/provider per LLM call. It is an accountant/reviewer
# surface, so it is gated to supervisor-grade roles (TEAM_LEAD+), mirroring
# agent_maturity_routes._require_supervisor.
# ---------------------------------------------------------------------------

_SUPERVISOR_ROLES = [
    UserRole.TEAM_LEAD.value,
    UserRole.WORKSPACE_ADMIN.value,
    UserRole.SUPER_ADMIN.value,
]


def _require_supervisor(db: Session, current_user: User) -> None:
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role not in _SUPERVISOR_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Required role: TEAM_LEAD or ADMIN",
        )


# --------------------------------------------------------------------------- #
# Event feed
# --------------------------------------------------------------------------- #
@router.get("/events")
def list_events(
    agent_id: Optional[str] = Query(None, description="Filter by agent id"),
    execution_id: Optional[str] = Query(None, description="Filter by execution id"),
    event_type: Optional[str] = Query(None, description="agent_action | llm_call"),
    success: Optional[bool] = Query(None, description="Filter by outcome"),
    start: Optional[datetime] = Query(None, description="ISO timestamp lower bound"),
    end: Optional[datetime] = Query(None, description="ISO timestamp upper bound"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_supervisor(db, current_user)
    query = _base_event_query(db)

    if agent_id:
        query = query.filter(AuditLog.resource == agent_id)
    if execution_id:
        query = query.filter(_execution_filter(execution_id))
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if success is not None:
        query = query.filter(AuditLog.success == success)
    if start:
        query = query.filter(AuditLog.timestamp >= start)
    if end:
        query = query.filter(AuditLog.timestamp <= end)

    total = query.count()
    rows = (
        query.order_by(AuditLog.timestamp.desc(), AuditLog.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"items": [_serialize_event(r) for r in rows], "total": total, "limit": limit, "offset": offset}


# --------------------------------------------------------------------------- #
# Execution list + timeline
# --------------------------------------------------------------------------- #
@router.get("/executions")
def list_executions(
    agent_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List audited runs, newest first.

    Runs are anchored on their ``execution_start`` event; status comes from
    the matching ``execution_complete`` event when present (RUNNING implies
    the run crashed or the audit close-out failed — itself a signal).
    """
    _require_supervisor(db, current_user)
    query = (
        _base_event_query(db)
        .filter(AuditLog.event_type == "agent_action")
        .filter(AuditLog.action == EXECUTION_START)
    )
    if agent_id:
        query = query.filter(AuditLog.resource == agent_id)

    total = query.count()
    starts = (
        query.order_by(AuditLog.timestamp.desc(), AuditLog.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: List[Dict[str, Any]] = []
    for start_row in starts:
        event = _serialize_event(start_row)
        execution_id = event["agent_execution_id"]
        item = {
            "execution_id": execution_id,
            "agent_id": event["agent_id"],
            "started_at": event["timestamp"],
            "status": "running",
            "completed_at": None,
            "task_input": (event.get("metadata") or {}).get("task_input"),
            "tool_calls": 0,
            "llm_calls": 0,
            "failed_events": 0,
        }
        if not execution_id:
            items.append(item)
            continue

        run_rows = (
            _base_event_query(db)
            .filter(_execution_filter(execution_id))
            .order_by(AuditLog.timestamp.asc())
            .all()
        )
        for row in run_rows:
            action = row.action or ""
            if row.event_type == "llm_call":
                item["llm_calls"] += 1
            elif action.startswith("tool:"):
                item["tool_calls"] += 1
            if row.success is False:
                item["failed_events"] += 1
            if action == EXECUTION_COMPLETE:
                meta = _parse_metadata(row.metadata_json)
                item["status"] = meta.get("status") or ("success" if row.success else "failed")
                item["completed_at"] = row.timestamp.isoformat() if row.timestamp else None
        items.append(item)

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/executions/{execution_id}")
def get_execution_timeline(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full replayable decision chain for one agent execution."""
    _require_supervisor(db, current_user)
    rows = (
        _base_event_query(db)
        .filter(_execution_filter(execution_id))
        .order_by(AuditLog.timestamp.asc(), AuditLog.id)
        .all()
    )
    if not rows:
        # Fall back to the persisted execution record — the run may predate
        # per-event auditing or died before its first audited event.
        exec_row = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
        if exec_row is None:
            raise HTTPException(status_code=404, detail=f"No audit trail found for execution {execution_id}")
        return {
            "execution_id": execution_id,
            "found_events": False,
            "execution": {
                "id": exec_row.id,
                "agent_id": exec_row.agent_id,
                "status": exec_row.status,
                "input_summary": exec_row.input_summary,
                "output_summary": exec_row.output_summary,
                "error_message": exec_row.error_message,
                "started_at": exec_row.started_at.isoformat() if exec_row.started_at else None,
                "completed_at": exec_row.completed_at.isoformat() if exec_row.completed_at else None,
            },
            "events": [],
            "counts": {"tool_calls": 0, "llm_calls": 0, "failed_events": 0},
        }

    events = [_serialize_event(r) for r in rows]
    counts = {
        "tool_calls": sum(1 for e in events if (e["action"] or "").startswith("tool:")),
        "llm_calls": sum(1 for e in events if e["event_type"] == "llm_call"),
        "failed_events": sum(1 for e in events if e["success"] is False),
    }
    start_event = next((e for e in events if e["action"] == EXECUTION_START), None)
    complete_event = next((e for e in events if e["action"] == EXECUTION_COMPLETE), None)

    execution_summary: Dict[str, Any] = {"id": execution_id}
    exec_row = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
    if exec_row is not None:
        execution_summary.update({
            "agent_id": exec_row.agent_id,
            "status": exec_row.status,
            "input_summary": exec_row.input_summary,
            "output_summary": exec_row.output_summary,
            "error_message": exec_row.error_message,
            "started_at": exec_row.started_at.isoformat() if exec_row.started_at else None,
            "completed_at": exec_row.completed_at.isoformat() if exec_row.completed_at else None,
        })
    if start_event:
        execution_summary.setdefault("agent_id", start_event["agent_id"])
        execution_summary["task_input"] = (start_event.get("metadata") or {}).get("task_input")
    if complete_event:
        execution_summary["status"] = (complete_event.get("metadata") or {}).get(
            "status", execution_summary.get("status")
        )

    return {
        "execution_id": execution_id,
        "found_events": True,
        "execution": execution_summary,
        "events": events,
        "counts": counts,
    }


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
@router.get("/summary")
def audit_summary(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate stats over the recent window, for dashboard headers."""
    _require_supervisor(db, current_user)
    from datetime import timedelta

    window_start = datetime.now(timezone.utc) - timedelta(days=days)
    base = _base_event_query(db).filter(AuditLog.timestamp >= window_start)

    total = base.count()
    if total == 0:
        return {
            "days": days,
            "total_events": 0,
            "by_event_type": {},
            "by_action": {},
            "failures": 0,
            "success_rate": None,
            "distinct_agents": 0,
            "executions_tracked": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    by_type: Dict[str, int] = {
        str(k): int(v)
        for k, v in db.query(AuditLog.event_type, func.count(AuditLog.id))
        .filter(AuditLog.event_type.in_(AUDIT_EVENT_TYPES))
        .filter(AuditLog.timestamp >= window_start)
        .group_by(AuditLog.event_type)
        .all()
    }
    by_action: Dict[str, int] = {
        str(k): int(v)
        for k, v in db.query(AuditLog.action, func.count(AuditLog.id))
        .filter(AuditLog.event_type.in_(AUDIT_EVENT_TYPES))
        .filter(AuditLog.timestamp >= window_start)
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(20)
        .all()
    }
    failures = base.filter(AuditLog.success.is_(False)).count()
    distinct_agents = (
        db.query(func.count(func.distinct(AuditLog.resource)))
        .filter(AuditLog.event_type.in_(AUDIT_EVENT_TYPES))
        .filter(AuditLog.timestamp >= window_start)
        .scalar()
    ) or 0
    executions_tracked = (
        _base_event_query(db)
        .filter(AuditLog.action == EXECUTION_START)
        .filter(AuditLog.timestamp >= window_start)
        .count()
    )

    return {
        "days": days,
        "total_events": total,
        "by_event_type": by_type,
        "by_action": by_action,
        "failures": failures,
        "success_rate": round((total - failures) / total * 100, 1) if total else None,
        "distinct_agents": distinct_agents,
        "executions_tracked": executions_tracked,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

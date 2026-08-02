"""Gateway request-log viewer routes (Phase B4).

Owner-scoped read access to ``GatewayRequestLog`` rows. Requires a normal JWT
(``get_current_user``); a user can only see their own gateway traffic.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import GatewayRequestLog, User

router = APIRouter(prefix="/api/v1/gateway/logs", tags=["LLM Gateway Logs"])


def _row_to_dict(r: GatewayRequestLog) -> Dict[str, Any]:
    return {
        "id": r.id,
        "provider": r.provider,
        "model": r.model,
        "stream": r.stream,
        "status_code": r.status_code,
        "latency_ms": r.latency_ms,
        "prompt_tokens": r.prompt_tokens,
        "completion_tokens": r.completion_tokens,
        "cost_usd": r.cost_usd,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "request_json": r.request_json,
        "response_json": r.response_json,
    }


@router.get("")
def list_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows = (
        db.query(GatewayRequestLog)
        .filter(GatewayRequestLog.user_id == current_user.id)
        .order_by(GatewayRequestLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"success": True, "data": [_row_to_dict(r) for r in rows]}


@router.get("/{log_id}")
def get_log(
    log_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(GatewayRequestLog)
        .filter(
            GatewayRequestLog.id == log_id,
            GatewayRequestLog.user_id == current_user.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"success": True, "data": _row_to_dict(row)}

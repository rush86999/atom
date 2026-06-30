"""
P3.2 — Dashboard activity feed aggregate endpoint.

Single GET /api/dashboard/feed returns everything the new landing page needs:
  - recent_executions: last 5 agent runs with status + agent name
  - recent_canvases:   last 3 canvas presentations, click-to-reopen
  - last_chat_session: most recent chat session id (for "pick up where you left off")
  - agents_progress:   the user's agents with tier + next-tier threshold

Why a single aggregate call: the previous landing page would have fired 4-5
N+1 fetches on mount. One round-trip keeps the dashboard feeling instant.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import AgentExecution, AgentRegistry, ChatSession, CanvasAudit, User
from core.personal_scope import resolve_tenant_id, resolve_workspace_id

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/feed")
async def get_dashboard_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate dashboard data in one round-trip.

    Scope resolution: Personal Edition is single-tenant (tenant_id == workspace_id
    == "default"), but we resolve each independently because the underlying models
    key on different columns (CanvasAudit → tenant_id; AgentExecution / AgentRegistry
    / ChatSession → workspace_id). See core/personal_scope.py for the contract.
    """
    workspace_id = resolve_workspace_id(current_user)
    tenant_id = resolve_tenant_id(current_user)

    recent_executions = _recent_executions(db, workspace_id, limit=5)
    recent_canvases = _recent_canvases(db, tenant_id, limit=3)
    last_chat_session = _last_chat_session(db, current_user.id)
    agents_progress = _agents_progress(db, workspace_id)

    return router.success_response(
        data={
            "recent_executions": recent_executions,
            "recent_canvases": recent_canvases,
            "last_chat_session": last_chat_session,
            "agents_progress": agents_progress,
        }
    )


# ---------------------------------------------------------------------------
# Helpers — each one fails open (returns []) so a missing table or schema drift
# in one section doesn't blank out the whole dashboard.
# ---------------------------------------------------------------------------

def _recent_executions(db: Session, workspace_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        rows = (
            db.query(AgentExecution, AgentRegistry.name)
            .outerjoin(AgentRegistry, AgentExecution.agent_id == AgentRegistry.id)
            .filter(AgentExecution.workspace_id == workspace_id)
            .order_by(AgentExecution.started_at.desc().nullslast())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": exec_row.id,
                "agent_id": exec_row.agent_id,
                "agent_name": agent_name or "Unknown",
                "status": exec_row.status,
                "input_summary": (exec_row.input_summary or "")[:200],
                "started_at": exec_row.started_at.isoformat() if exec_row.started_at else None,
                "duration_seconds": exec_row.duration_seconds or 0.0,
            }
            for exec_row, agent_name in rows
        ]
    except Exception as exc:
        logger.warning("dashboard recent_executions failed: %s", exc)
        return []


def _recent_canvases(db: Session, tenant_id: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Recent canvas audit rows. CanvasAudit keys on ``tenant_id`` (not workspace_id)."""
    try:
        rows = (
            db.query(CanvasAudit)
            .filter(CanvasAudit.tenant_id == tenant_id)
            .order_by(CanvasAudit.created_at.desc().nullslast())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "canvas_id": getattr(r, "canvas_id", None),
                "action": getattr(r, "action_type", None),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("dashboard recent_canvases failed: %s", exc)
        return []


def _last_chat_session(db: Session, user_id: str) -> Optional[Dict[str, Any]]:
    try:
        row = (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc().nullslast())
            .first()
        )
        if not row:
            return None
        return {
            "id": row.id,
            "title": getattr(row, "title", None) or "Untitled session",
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }
    except Exception as exc:
        logger.warning("dashboard last_chat_session failed: %s", exc)
        return None


def _agents_progress(db: Session, workspace_id: str) -> List[Dict[str, Any]]:
    try:
        # Local import keeps the criteria map optional — if graduation service
        # can't be imported, we still return tier names without thresholds.
        try:
            from core.agent_graduation_service import AgentGraduationService
            criteria = AgentGraduationService.CRITERIA
        except Exception:
            criteria = {}

        rows = (
            db.query(AgentRegistry)
            .filter(AgentRegistry.workspace_id == workspace_id)
            .filter(AgentRegistry.category != "system")  # hide system/demo agents
            .order_by(AgentRegistry.updated_at.desc().nullslast())
            .limit(20)
            .all()
        )

        tier_order = ["student", "intern", "supervised", "autonomous"]
        result = []
        for a in rows:
            tier = (a.status or "student").lower()
            if tier not in tier_order:
                tier = "student"
            idx = tier_order.index(tier)
            next_tier = tier_order[idx + 1] if idx < len(tier_order) - 1 else None
            next_threshold = None
            if next_tier and next_tier.upper() in criteria:
                next_threshold = criteria[next_tier.upper()].get("min_episodes")
            result.append({
                "id": a.id,
                "name": a.name,
                "current_tier": tier,
                "next_tier": next_tier,
                "next_threshold_episodes": next_threshold,
            })
        return result
    except Exception as exc:
        logger.warning("dashboard agents_progress failed: %s", exc)
        return []

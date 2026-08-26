"""
Episode API Routes

REST endpoints for episodic memory system with governance integration.
"""

import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.auth import get_current_user, User
from core.agent_governance_service import AgentGovernanceService
from core.agent_graduation_service import AgentGraduationService
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.episode_retrieval_service import EpisodeRetrievalService
from core.episode_segmentation_service import EpisodeSegmentationService
from core.models import AgentFeedback, Episode, User, UserRole
from core.security_dependencies import get_current_user

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/episodes", tags=["episodes"])

# Feature flags
EPISODE_GOVERNANCE_ENABLED = os.getenv("EPISODE_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

# R87: graduation and lifecycle-maintenance mutations are supervisor-grade
# operations. promote/exam hand out maturity levels (the platform's entire
# permission model) and decay/consolidate mutate fleet-wide episode state —
# none may be driven by an ordinary member JWT.
_SUPERVISOR_ROLES = [
    UserRole.TEAM_LEAD.value,
    UserRole.WORKSPACE_ADMIN.value,
    UserRole.SUPER_ADMIN.value,
]


def _require_supervisor(db: Session, current_user: User) -> None:
    """Require a supervisor-grade role (TEAM_LEAD+), 403 otherwise."""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role not in _SUPERVISOR_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Required role: TEAM_LEAD or ADMIN",
        )


# Request Models
class CreateEpisodeRequest(BaseModel):
    session_id: str
    agent_id: str
    title: Optional[str] = None


class TemporalRetrievalRequest(BaseModel):
    agent_id: str
    time_range: str = "7d"  # 1d, 7d, 30d, 90d
    user_id: Optional[str] = None
    limit: int = Field(default=50, le=200)


class SemanticRetrievalRequest(BaseModel):
    agent_id: str
    query: str
    limit: int = Field(default=10, le=100)


class ContextualRetrievalRequest(BaseModel):
    agent_id: str
    current_task: str
    limit: int = Field(default=5, le=50)


class EpisodeFeedbackRequest(BaseModel):
    episode_id: Optional[str] = Field(default=None, description="Deprecated — episode id comes from the URL path")
    feedback_score: float = Field(ge=-1.0, le=1.0, description="Feedback score from -1.0 (negative) to 1.0 (positive)")


class CanvasTypeRetrievalRequest(BaseModel):
    agent_id: str
    canvas_type: str  # 'sheets', 'charts', 'generic', etc.
    action: Optional[str] = None  # 'present', 'submit', 'close', etc.
    time_range: str = "30d"
    limit: int = Field(default=10, le=100)


class CanvasAwareRetrievalRequest(BaseModel):
    agent_id: str
    query: str
    canvas_type: Optional[str] = None
    canvas_context_detail: str = "summary"  # "summary" | "standard" | "full"
    limit: int = Field(default=10, le=100)


class BusinessDataRetrievalRequest(BaseModel):
    agent_id: str
    filters: Dict[str, Any]  # e.g., {"approval_status": "approved", "revenue": {"$gt": 1000000}}
    limit: int = Field(default=10, le=100)


class FeedbackSubmissionRequest(BaseModel):
    feedback_type: str  # 'thumbs_up', 'thumbs_down', 'rating'
    rating: Optional[int] = None  # 1-5 for rating type
    corrections: Optional[str] = None


@router.post("/create")
async def create_episode(
    request: CreateEpisodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create episode from session"""
    service = EpisodeSegmentationService(db)
    episode = await service.create_episode_from_session(
        session_id=request.session_id,
        agent_id=request.agent_id,
        title=request.title
    )

    if not episode:
        raise router.error_response(
            error_code="EPISODE_CREATE_FAILED",
            message="Failed to create episode",
            status_code=400
        )

    return router.success_response(
        data={
            "episode_id": episode.id,
            "title": episode.task_description,
            "status": episode.status
        },
        message="Episode created successfully"
    )


@router.post("/retrieve/temporal")
async def retrieve_temporal(
    request: TemporalRetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Temporal retrieval by time range"""
    service = EpisodeRetrievalService(db)
    return await service.retrieve_temporal(
        agent_id=request.agent_id,
        time_range=request.time_range,
        user_id=current_user.id,
        limit=request.limit
    )


@router.post("/retrieve/semantic")
async def retrieve_semantic(
    request: SemanticRetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Semantic retrieval by similarity"""
    service = EpisodeRetrievalService(db)
    return await service.retrieve_semantic(
        agent_id=request.agent_id,
        query=request.query,
        limit=request.limit
    )


@router.get("/retrieve/{episode_id}")
async def retrieve_sequential(
    episode_id: str,
    agent_id: str,
    include_canvas: bool = True,
    include_feedback: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sequential retrieval with full segments and optional canvas/feedback context.

    GET /api/episodes/{episode_id}/retrieve?include_canvas=true&include_feedback=true
    """
    service = EpisodeRetrievalService(db)
    return await service.retrieve_sequential(
        episode_id=episode_id,
        agent_id=agent_id,
        include_canvas=include_canvas,
        include_feedback=include_feedback
    )


@router.post("/retrieve/contextual")
async def retrieve_contextual(
    request: ContextualRetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Contextual retrieval for current task"""
    service = EpisodeRetrievalService(db)
    return await service.retrieve_contextual(
        agent_id=request.agent_id,
        current_task=request.current_task,
        limit=request.limit
    )


@router.get("/trajectories")
async def list_trajectories(
    workspace_id: Optional[str] = Query(None, description="Scope to a workspace"),
    agent_id: Optional[str] = Query(None, description="Scope to one agent"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Agent execution trajectories for the memory-recall feed.

    The UI (components/Agents/MemoryRecallFeed.tsx) previously fetched a
    /api/governance/analytics/trajectories endpoint that no backend route
    served — the memory-recall feed was permanently empty. This is the live
    episodic-memory-backed surface for it.
    """
    query = db.query(Episode)
    if agent_id:
        query = query.filter(Episode.agent_id == agent_id)
    if workspace_id:
        query = query.filter(Episode.workspace_id == workspace_id)
    episodes = query.order_by(Episode.started_at.desc()).limit(limit).all()

    def _trajectory(e: Episode) -> Dict[str, Any]:
        meta = e.metadata_json if isinstance(e.metadata_json, dict) else {}
        return {
            "id": e.id,
            "agent_id": e.agent_id,
            "task_type": meta.get("task_type") or "completion",
            "outcome": e.outcome or "unknown",
            "step_efficiency": e.step_efficiency,
            "confidence_score": e.confidence_score,
            "timestamp": e.started_at.isoformat() if getattr(e, "started_at", None) else None,
            "summary": (e.task_description or "").strip(),
            "learnings": (meta.get("learnings") if isinstance(meta.get("learnings"), list) else None),
        }

    return router.success_response(
        data=[_trajectory(e) for e in episodes],
        metadata={"count": len(episodes)}
    )


@router.get("/{agent_id}/list")
async def list_episodes(
    agent_id: str,
    skip: int = 0,
    limit: int = 50,    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List episodes with pagination"""
    episodes = db.query(Episode).filter(
        Episode.agent_id == agent_id
    ).order_by(Episode.started_at.desc()).offset(skip).limit(limit).all()

    return router.success_response(
        data=[
            {
                "id": e.id,
                "title": e.task_description or "Episode",
                "status": e.status,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "importance_score": e.importance_score,
                "maturity_at_time": e.maturity_at_time,
                "human_intervention_count": e.human_intervention_count
            }
            for e in episodes
        ],
        metadata={"count": len(episodes)}
    )


@router.post("/{episode_id}/feedback")
async def submit_feedback(
    episode_id: str,
    request: EpisodeFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit feedback to update importance score (authenticated)

    Updates episode importance based on user feedback.
    Feedback score must be between -1.0 (negative) and 1.0 (positive).

    **Security**: Requires authentication
    """
    service = EpisodeLifecycleService(db)
    success = await service.update_importance_scores(
        episode_id, request.feedback_score
    )

    return router.success_response(
        data={"updated": success},
        message="Feedback submitted successfully"
    )


@router.post("/retrieve/by-canvas-type")
async def retrieve_by_canvas_type(
    request: CanvasTypeRetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve episodes filtered by canvas type and action.

    POST /api/episodes/retrieve/by-canvas-type
    {
        "agent_id": "agent_123",
        "canvas_type": "sheets",
        "action": "present",
        "time_range": "30d",
        "limit": 10
    }
    """
    service = EpisodeRetrievalService(db)
    result = await service.retrieve_by_canvas_type(
        agent_id=request.agent_id,
        canvas_type=request.canvas_type,
        action=request.action,
        time_range=request.time_range,
        limit=request.limit
    )
    return result


@router.post("/retrieve/canvas-aware")
async def retrieve_episodes_canvas_aware(
    request: CanvasAwareRetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retrieve episodes with canvas-aware semantic search.

    POST /api/episodes/retrieve/canvas-aware
    {
        "agent_id": "agent_123",
        "query": "workflow approval",
        "canvas_type": "orchestration",
        "canvas_context_detail": "standard",
        "limit": 10
    }

    Canvas context detail levels:
    - "summary": presentation_summary only (~50 tokens) - DEFAULT
    - "standard": summary + critical_data_points (~200 tokens)
    - "full": all fields including visual_elements (~500 tokens)

    Returns:
        Episodes with canvas context filtered by detail level
    """
    service = EpisodeRetrievalService(db)
    return await service.retrieve_canvas_aware(
        agent_id=request.agent_id,
        query=request.query,
        canvas_type=request.canvas_type,
        canvas_context_detail=request.canvas_context_detail,
        limit=request.limit
    )


@router.get("/retrieve/canvas-type/{canvas_type}")
async def retrieve_episodes_by_canvas_type(
    agent_id: str,
    canvas_type: str,
    query: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    canvas_context_detail: str = Query("summary", regex="^(summary|standard|full)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retrieve episodes filtered by canvas type.

    GET /api/episodes/retrieve/canvas-type/orchestration?agent_id=agent_123&query=approval&canvas_context_detail=standard

    Args:
        agent_id: Agent ID
        canvas_type: Canvas type filter (generic, docs, email, sheets, orchestration, terminal, coding)
        query: Optional semantic search query
        limit: Max results
        canvas_context_detail: Detail level for canvas context (summary|standard|full)

    Returns:
        Episodes filtered by canvas type
    """
    service = EpisodeRetrievalService(db)

    if query:
        return await service.retrieve_canvas_aware(
            agent_id=agent_id,
            query=query,
            canvas_type=canvas_type,
            canvas_context_detail=canvas_context_detail,
            limit=limit
        )
    else:
        # Use temporal retrieval without semantic search
        return await service.retrieve_temporal(
            agent_id=agent_id,
            time_range="90d",  # Default to 90 days
            limit=limit
        )


@router.post("/retrieve/business-data")
async def retrieve_episodes_by_business_data(
    request: BusinessDataRetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retrieve episodes by business data in canvas context.

    POST /api/episodes/retrieve/business-data
    {
        "agent_id": "agent_123",
        "filters": {
            "approval_status": "approved",
            "revenue": {"$gt": 1000000}
        },
        "limit": 10
    }

    Returns:
        Episodes matching business data filters

    Examples:
        Find $1M+ approved workflows:
        {
            "agent_id": "agent_123",
            "filters": {
                "approval_status": "approved",
                "revenue": {"$gt": 1000000}
            }
        }
    """
    service = EpisodeRetrievalService(db)
    return await service.retrieve_by_business_data(
        agent_id=request.agent_id,
        business_filters=request.filters,
        limit=request.limit
    )


@router.get("/canvas-types")
async def list_canvas_types(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List all available canvas types for filtering.

    GET /api/episodes/canvas-types

    Returns:
        Canvas types with descriptions and example use cases
    """
    return router.success_response(
        data={
            "canvas_types": {
                "generic": "Generic canvas with charts, forms, markdown",
                "docs": "Documentation canvas",
                "email": "Email composer/viewer",
                "sheets": "Spreadsheet with data grids",
                "orchestration": "Workflow orchestration board",
                "terminal": "Terminal/console output",
                "coding": "Code editor and diff viewer"
            },
            "detail_levels": {
                "summary": "presentation_summary only (~50 tokens) - default",
                "standard": "summary + critical_data_points (~200 tokens)",
                "full": "all fields including visual_elements (~500 tokens)"
            }
        },
        message="Canvas types retrieved successfully"
    )


@router.post("/{episode_id}/feedback/submit")
async def submit_episode_feedback(
    episode_id: str,
    request: FeedbackSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit detailed feedback for an episode.

    Creates AgentFeedback record linked to episode.
    Updates Episode.aggregate_feedback_score.

    POST /api/episodes/{episode_id}/feedback/submit
    {
        "feedback_type": "rating",
        "rating": 5,
        "corrections": "Great work on the charts"
    }
    """
    # Get episode
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise router.error_response(
            error_code="EPISODE_NOT_FOUND",
            message="Episode not found",
            status_code=404
        )

    # Create feedback record (AgentFeedback is linked to the episode via the
    # episode's feedback_ids list; the model has no episode_id column).
    feedback = AgentFeedback(
        agent_id=episode.agent_id,
        user_id=current_user.id,
        tenant_id=episode.tenant_id,
        feedback_type=request.feedback_type,
        rating=request.rating,
        original_output=episode.task_description or "",
        user_correction=request.corrections or "",
        thumbs_up_down=(request.feedback_type == "thumbs_up") if request.feedback_type in ["thumbs_up", "thumbs_down"] else None
    )
    db.add(feedback)
    db.flush()  # Ensure the new feedback is visible to the aggregate query below

    # Update episode aggregate score. AgentFeedback has no episode_id column —
    # the linkage is the episode's feedback_ids list, so scope by that.
    linked_ids = list(episode.feedback_ids or []) + [feedback.id]
    all_feedback = db.query(AgentFeedback).filter(
        AgentFeedback.id.in_(linked_ids)
    ).all()

    # Recalculate aggregate score
    scores = []
    for f in all_feedback:
        if f.feedback_type == "thumbs_up" or f.thumbs_up_down is True:
            scores.append(1.0)
        elif f.feedback_type == "thumbs_down" or f.thumbs_up_down is False:
            scores.append(-1.0)
        elif f.rating:
            scores.append((f.rating - 3) / 2)  # Convert 1-5 to -1.0 to 1.0

    episode.aggregate_feedback_score = sum(scores) / len(scores) if scores else None
    episode.feedback_ids = [f.id for f in all_feedback]

    db.commit()
    db.refresh(feedback)

    return router.success_response(
        data={
            "feedback_id": feedback.id,
            "aggregate_score": episode.aggregate_feedback_score
        },
        message="Feedback submitted successfully"
    )


@router.get("/{episode_id}/feedback/list")
async def get_episode_feedback(
    episode_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve all feedback for an episode.

    GET /api/episodes/{episode_id}/feedback/list
    """
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise router.error_response(
            error_code="EPISODE_NOT_FOUND",
            message="Episode not found",
            status_code=404
        )

    # AgentFeedback has no episode_id column — the linkage is the episode's
    # feedback_ids list (mirror of submit_episode_feedback). Querying
    # AgentFeedback.episode_id previously 500'd every request.
    linked_ids = list(episode.feedback_ids or [])
    if not linked_ids:
        return router.success_response(data={"feedbacks": [], "count": 0})

    feedbacks = db.query(AgentFeedback).filter(
        AgentFeedback.id.in_(linked_ids)
    ).order_by(AgentFeedback.created_at.desc()).all()

    return router.success_response(
        data={
            "feedbacks": [
                {
                    "id": f.id,
                    "feedback_type": f.feedback_type,
                    "rating": f.rating,
                    "corrections": f.user_correction,
                    "created_at": f.created_at.isoformat() if f.created_at else None
                }
                for f in feedbacks
            ],
            "count": len(feedbacks)
        }
    )


@router.get("/analytics/feedback-episodes")
async def get_feedback_weighted_episodes(
    agent_id: str,
    min_feedback_score: float = 0.5,
    time_range: str = "30d",
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve episodes with high feedback scores.

    GET /api/episodes/analytics/feedback-episodes?agent_id=agent_123&min_feedback_score=0.5
    """
    from datetime import datetime, timedelta

    deltas = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
    days = deltas.get(time_range, 30)
    cutoff = datetime.now() - timedelta(days=days)

    episodes = db.query(Episode).filter(
        Episode.agent_id == agent_id,
        Episode.started_at >= cutoff,
        Episode.aggregate_feedback_score >= min_feedback_score
    ).order_by(Episode.aggregate_feedback_score.desc()).limit(limit).all()

    return router.success_response(
        data={
            "episodes": [
                {
                    "id": e.id,
                    "title": e.task_description or "Episode",
                    "aggregate_feedback_score": e.aggregate_feedback_score,
                    "canvas_action_count": e.canvas_action_count,
                    "started_at": e.started_at.isoformat() if e.started_at else None
                }
                for e in episodes
            ],
            "count": len(episodes),
            "min_feedback_score": min_feedback_score
        }
    )


# Graduation endpoints
@router.get("/graduation/readiness/{agent_id}")
async def get_readiness(
    agent_id: str,
    target_maturity: str = "INTERN",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Calculate graduation readiness score"""
    service = AgentGraduationService(db)
    return await service.calculate_readiness_score(agent_id, target_maturity)


@router.post("/graduation/exam")
async def run_exam(
    agent_id: str,
    edge_case_episodes: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Run graduation exam on edge cases"""
    _require_supervisor(db, current_user)
    service = AgentGraduationService(db)
    return await service.run_graduation_exam(agent_id, edge_case_episodes)


@router.post("/graduation/promote")
async def promote_agent(
    agent_id: str,
    new_maturity: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Promote agent after validation"""
    _require_supervisor(db, current_user)
    service = AgentGraduationService(db)
    success = await service.promote_agent(agent_id, new_maturity, current_user.id)

    return router.success_response(
        data={
            "agent_id": agent_id,
            "new_maturity": new_maturity,
            "promoted": success
        },
        message=f"Agent promoted to {new_maturity}" if success else "Promotion failed"
    )


@router.get("/graduation/audit/{agent_id}")
async def get_audit_trail(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get full audit trail for governance review"""
    service = AgentGraduationService(db)
    return await service.get_graduation_audit_trail(agent_id)


# Lifecycle endpoints
@router.post("/lifecycle/decay")
async def trigger_decay(
    days_threshold: int = 90,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger decay process"""
    _require_supervisor(db, current_user)
    service = EpisodeLifecycleService(db)
    return await service.decay_old_episodes(days_threshold)


@router.post("/lifecycle/consolidate")
async def consolidate_episodes(
    agent_id: str,    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Consolidate similar episodes"""
    _require_supervisor(db, current_user)
    service = EpisodeLifecycleService(db)
    return await service.consolidate_similar_episodes(agent_id)


@router.get("/stats/{agent_id}")
async def get_stats(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get episode statistics"""
    from sqlalchemy import func

    stats = db.query(
        func.count(Episode.id).label("total"),
        func.avg(Episode.importance_score).label("avg_importance"),
        func.avg(Episode.constitutional_score).label("avg_constitutional"),
        func.sum(Episode.human_intervention_count).label("total_interventions")
    ).filter(Episode.agent_id == agent_id).first()

    return router.success_response(
        data={
            "agent_id": agent_id,
            "total_episodes": stats.total or 0,
            "avg_importance_score": float(stats.avg_importance or 0),
            "avg_constitutional_score": float(stats.avg_constitutional or 0),
            "total_interventions": stats.total_interventions or 0
        }
    )

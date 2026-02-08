"""
Episode API Routes

REST endpoints for episodic memory system with governance integration.
"""

import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.agent_graduation_service import AgentGraduationService
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.episode_retrieval_service import EpisodeRetrievalService
from core.episode_segmentation_service import EpisodeSegmentationService
from core.models import AgentFeedback, Episode, User
from core.security_dependencies import get_current_user

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/episodes", tags=["episodes"])

# Feature flags
EPISODE_GOVERNANCE_ENABLED = os.getenv("EPISODE_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"


# Request Models
class CreateEpisodeRequest(BaseModel):
    session_id: str
    agent_id: str
    title: Optional[str] = None


class TemporalRetrievalRequest(BaseModel):
    agent_id: str
    time_range: str = "7d"  # 1d, 7d, 30d, 90d
    user_id: Optional[str] = None
    limit: int = 50


class SemanticRetrievalRequest(BaseModel):
    agent_id: str
    query: str
    limit: int = 10


class ContextualRetrievalRequest(BaseModel):
    agent_id: str
    current_task: str
    limit: int = 5


class EpisodeFeedbackRequest(BaseModel):
    episode_id: str
    feedback_score: float  # -1.0 to 1.0


class CanvasTypeRetrievalRequest(BaseModel):
    agent_id: str
    canvas_type: str  # 'sheets', 'charts', 'generic', etc.
    action: Optional[str] = None  # 'present', 'submit', 'close', etc.
    time_range: str = "30d"
    limit: int = 10


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
            "title": episode.title,
            "status": episode.status
        },
        message="Episode created successfully"
    )


@router.post("/retrieve/temporal")
async def retrieve_temporal(
    request: TemporalRetrievalRequest,
    db: Session = Depends(get_db)
):
    """Temporal retrieval by time range"""
    service = EpisodeRetrievalService(db)
    return await service.retrieve_temporal(
        agent_id=request.agent_id,
        time_range=request.time_range,
        user_id=request.user_id,
        limit=request.limit
    )


@router.post("/retrieve/semantic")
async def retrieve_semantic(
    request: SemanticRetrievalRequest,
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
    db: Session = Depends(get_db)
):
    """Contextual retrieval for current task"""
    service = EpisodeRetrievalService(db)
    return await service.retrieve_contextual(
        agent_id=request.agent_id,
        current_task=request.current_task,
        limit=request.limit
    )


@router.get("/{agent_id}/list")
async def list_episodes(
    agent_id: str,
    skip: int = 0,
    limit: int = 50,
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
                "title": e.title,
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
    db: Session = Depends(get_db)
):
    """Submit feedback to update importance score"""
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

    # Create feedback record
    feedback = AgentFeedback(
        agent_id=episode.agent_id,
        user_id=current_user.id,
        episode_id=episode_id,
        feedback_type=request.feedback_type,
        rating=request.rating,
        user_correction=request.corrections or "",
        thumbs_up_down=(request.feedback_type == "thumbs_up") if request.feedback_type in ["thumbs_up", "thumbs_down"] else None
    )
    db.add(feedback)

    # Update episode aggregate score
    all_feedback = db.query(AgentFeedback).filter(
        AgentFeedback.episode_id == episode_id
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
    db: Session = Depends(get_db)
):
    """
    Retrieve all feedback for an episode.

    GET /api/episodes/{episode_id}/feedback/list
    """
    feedbacks = db.query(AgentFeedback).filter(
        AgentFeedback.episode_id == episode_id
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
                    "title": e.title,
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
    db: Session = Depends(get_db)
):
    """Calculate graduation readiness score"""
    service = AgentGraduationService(db)
    return await service.calculate_readiness_score(agent_id, target_maturity)


@router.post("/graduation/exam")
async def run_exam(
    agent_id: str,
    edge_case_episodes: List[str],
    db: Session = Depends(get_db)
):
    """Run graduation exam on edge cases"""
    service = AgentGraduationService(db)
    return await service.run_graduation_exam(agent_id, edge_case_episodes)


@router.post("/graduation/promote")
async def promote_agent(
    agent_id: str,
    new_maturity: str,
    validated_by: str,
    db: Session = Depends(get_db)
):
    """Promote agent after validation"""
    service = AgentGraduationService(db)
    success = await service.promote_agent(agent_id, new_maturity, validated_by)

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
    db: Session = Depends(get_db)
):
    """Get full audit trail for governance review"""
    service = AgentGraduationService(db)
    return await service.get_graduation_audit_trail(agent_id)


# Lifecycle endpoints
@router.post("/lifecycle/decay")
async def trigger_decay(
    days_threshold: int = 90,
    db: Session = Depends(get_db)
):
    """Trigger decay process"""
    service = EpisodeLifecycleService(db)
    return await service.decay_old_episodes(days_threshold)


@router.post("/lifecycle/consolidate")
async def consolidate_episodes(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """Consolidate similar episodes"""
    service = EpisodeLifecycleService(db)
    return await service.consolidate_similar_episodes(agent_id)


@router.get("/stats/{agent_id}")
async def get_stats(
    agent_id: str,
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

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
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.episode_segmentation_service import EpisodeSegmentationService
from core.episode_retrieval_service import EpisodeRetrievalService
from core.agent_graduation_service import AgentGraduationService
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import User, Episode
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
    db: Session = Depends(get_db)
):
    """Sequential retrieval with full segments"""
    service = EpisodeRetrievalService(db)
    return await service.retrieve_sequential(episode_id, agent_id)


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

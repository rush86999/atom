"""
Enhanced Feedback API Endpoints

Provides REST endpoints for collecting and managing user feedback on agent actions.
Supports thumbs up/down, star ratings, detailed corrections, and feedback analytics.

Endpoints:
- POST /api/feedback/submit - Submit enhanced feedback
- GET /api/feedback/agent/{agent_id} - Get feedback for an agent
- GET /api/feedback/analytics - Get feedback analytics
- GET /api/feedback/trends - Get feedback trends over time
"""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import AgentExecution, AgentFeedback, AgentRegistry

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/feedback", tags=["feedback"])


# ============================================================================
# Request/Response Models
# ============================================================================

class FeedbackSubmitRequest(BaseModel):
    """Request to submit enhanced feedback."""
    agent_id: str = Field(..., description="ID of the agent")
    agent_execution_id: Optional[str] = Field(None, description="ID of the agent execution")
    user_id: str = Field(..., description="ID of the user submitting feedback")

    # Feedback content (at least one required)
    thumbs_up_down: Optional[bool] = Field(None, description="Thumbs up (True) or down (False)")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Star rating (1-5)")
    user_correction: Optional[str] = Field(None, description="Detailed correction or comment")

    # Context
    input_context: Optional[str] = Field(None, description="Input that triggered the agent")
    original_output: Optional[str] = Field(None, description="Agent's original output")

    # Feedback type (auto-detected if not provided)
    feedback_type: Optional[str] = Field(
        None,
        description="Type of feedback: correction, rating, approval, comment"
    )


class FeedbackSubmitResponse(BaseModel):
    """Response from feedback submission."""
    success: bool
    feedback_id: str
    agent_id: str
    feedback_type: str
    message: str


class FeedbackSummary(BaseModel):
    """Feedback summary for an agent."""
    agent_id: str
    agent_name: str
    total_feedback: int
    positive_count: int
    negative_count: int
    thumbs_up_count: int
    thumbs_down_count: int
    average_rating: Optional[float]
    rating_distribution: Dict[int, int]  # 1-5 stars
    feedback_types: Dict[str, int]


class FeedbackAnalytics(BaseModel):
    """Overall feedback analytics."""
    total_feedback: int
    total_agents_with_feedback: int
    overall_positive_ratio: float
    overall_average_rating: Optional[float]
    top_performing_agents: List[Dict[str, Any]]
    most_corrected_agents: List[Dict[str, Any]]
    feedback_by_type: Dict[str, int]
    feedback_trends_7d: Dict[str, int]
    feedback_trends_30d: Dict[str, int]


class FeedbackTrend(BaseModel):
    """Feedback trend data point."""
    date: str
    total: int
    positive: int
    negative: int
    average_rating: Optional[float]


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/submit", response_model=FeedbackSubmitResponse)
async def submit_enhanced_feedback(
    request: FeedbackSubmitRequest,
    db: Session = Depends(get_db)
):
    """
    Submit enhanced feedback on an agent action.

    Supports multiple feedback types:
    - **Thumbs Up/Down**: Quick positive/negative feedback
    - **Star Rating**: 1-5 star rating
    - **Correction**: Detailed correction of agent output
    - **Comment**: General feedback or notes

    Feedback Types (auto-detected if not provided):
    - `rating` - Star rating provided
    - `correction` - User correction provided
    - `approval` - Thumbs up without correction
    - `comment` - Text feedback without rating

    Args:
        request: Enhanced feedback request
        db: Database session

    Returns:
        FeedbackSubmitResponse with feedback ID and type
    """
    # Validate agent exists
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == request.agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", request.agent_id)

    # Validate at least one feedback type provided
    has_feedback = any([
        request.thumbs_up_down is not None,
        request.rating is not None,
        request.user_correction is not None
    ])

    if not has_feedback:
        raise router.validation_error(
            field="feedback",
            message="At least one feedback type must be provided",
            details={
                "required_fields": ["thumbs_up_down", "rating", "user_correction"],
                "provided": {
                    "thumbs_up_down": request.thumbs_up_down,
                    "rating": request.rating,
                    "user_correction": request.user_correction is not None
                }
            }
        )

    # Auto-detect feedback type if not provided
    feedback_type = request.feedback_type
    if not feedback_type:
        if request.rating is not None:
            feedback_type = "rating"
        elif request.user_correction:
            feedback_type = "correction"
        elif request.thumbs_up_down is True:
            feedback_type = "approval"
        else:
            feedback_type = "comment"

    # Validate rating if provided
    if request.rating is not None and not (1 <= request.rating <= 5):
        raise router.validation_error(
            field="rating",
            message="Rating must be between 1 and 5",
            details={"provided": request.rating}
        )

    # Create feedback record
    feedback = AgentFeedback(
        agent_id=request.agent_id,
        agent_execution_id=request.agent_execution_id,
        user_id=request.user_id,
        input_context=request.input_context,
        original_output=request.original_output or "",
        user_correction=request.user_correction or "",
        feedback_type=feedback_type,
        thumbs_up_down=request.thumbs_up_down,
        rating=request.rating,
        status="pending"  # Pending adjudication
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    logger.info(
        f"Enhanced feedback submitted: agent={request.agent_id}, "
        f"type={feedback_type}, thumbs={request.thumbs_up_down}, "
        f"rating={request.rating}, user={request.user_id}"
    )

    return router.success_response(
        data={
            "feedback_id": feedback.id,
            "agent_id": request.agent_id,
            "feedback_type": feedback_type
        },
        message="Feedback submitted successfully"
    )


@router.get("/agent/{agent_id}", response_model=FeedbackSummary)
async def get_agent_feedback(
    agent_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """
    Get feedback summary for a specific agent.

    Returns aggregated feedback statistics including:
    - Total feedback count
    - Positive/negative breakdown
    - Thumbs up/down counts
    - Average star rating
    - Rating distribution (1-5 stars)
    - Feedback types breakdown

    Args:
        agent_id: ID of the agent
        days: Number of days to look back (default: 30)
        db: Database session

    Returns:
        FeedbackSummary with aggregated statistics
    """
    # Validate agent exists
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)

    # Calculate date cutoff
    cutoff_date = datetime.now() - timedelta(days=days)

    # Query feedback
    feedback_query = db.query(AgentFeedback).filter(
        AgentFeedback.agent_id == agent_id,
        AgentFeedback.created_at >= cutoff_date
    )

    all_feedback = feedback_query.all()

    # Calculate statistics
    total = len(all_feedback)

    thumbs_up = sum(1 for f in all_feedback if f.thumbs_up_down is True)
    thumbs_down = sum(1 for f in all_feedback if f.thumbs_up_down is False)

    # Positive: thumbs up OR rating >= 4
    positive = sum(
        1 for f in all_feedback
        if f.thumbs_up_down is True or (f.rating is not None and f.rating >= 4)
    )

    # Negative: thumbs down OR rating <= 2
    negative = sum(
        1 for f in all_feedback
        if f.thumbs_up_down is False or (f.rating is not None and f.rating <= 2)
    )

    # Rating distribution
    rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    ratings = [f.rating for f in all_feedback if f.rating is not None]
    for r in ratings:
        rating_dist[r] += 1

    avg_rating = sum(ratings) / len(ratings) if ratings else None

    # Feedback types
    feedback_types = {}
    for f in all_feedback:
        if f.feedback_type:
            feedback_types[f.feedback_type] = feedback_types.get(f.feedback_type, 0) + 1

    return router.success_response(
        data={
            "agent_id": agent_id,
            "agent_name": agent.name,
            "total_feedback": total,
            "positive_count": positive,
            "negative_count": negative,
            "thumbs_up_count": thumbs_up,
            "thumbs_down_count": thumbs_down,
            "average_rating": avg_rating,
            "rating_distribution": rating_dist,
            "feedback_types": feedback_types
        },
        message=f"Retrieved feedback summary for agent {agent_id}"
    )


@router.get("/analytics", response_model=FeedbackAnalytics)
async def get_feedback_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    limit: int = Query(10, ge=1, le=100, description="Limit for top/bottom agents"),
    db: Session = Depends(get_db)
):
    """
    Get overall feedback analytics.

    Returns comprehensive analytics including:
    - Total feedback count
    - Overall positive/negative ratio
    - Overall average rating
    - Top performing agents
    - Most corrected agents
    - Feedback by type
    - Feedback trends (7d, 30d)

    Args:
        days: Number of days to analyze (default: 30)
        limit: Limit for top/bottom agent lists (default: 10)
        db: Database session

    Returns:
        FeedbackAnalytics with comprehensive statistics
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    # Total feedback
    total_feedback = db.query(AgentFeedback).filter(
        AgentFeedback.created_at >= cutoff_date
    ).count()

    # Total agents with feedback
    agents_with_feedback = db.query(AgentFeedback.agent_id).filter(
        AgentFeedback.created_at >= cutoff_date
    ).distinct().count()

    # All feedback in date range
    all_feedback = db.query(AgentFeedback).filter(
        AgentFeedback.created_at >= cutoff_date
    ).all()

    # Positive/negative counts
    positive = sum(
        1 for f in all_feedback
        if f.thumbs_up_down is True or (f.rating is not None and f.rating >= 4)
    )
    negative = sum(
        1 for f in all_feedback
        if f.thumbs_up_down is False or (f.rating is not None and f.rating <= 2)
    )

    positive_ratio = positive / total_feedback if total_feedback > 0 else 0

    # Average rating
    ratings = [f.rating for f in all_feedback if f.rating is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else None

    # Top performing agents (highest positive ratio)
    agent_stats = {}
    for f in all_feedback:
        if f.agent_id not in agent_stats:
            agent_stats[f.agent_id] = {"positive": 0, "total": 0}
        agent_stats[f.agent_id]["total"] += 1
        if f.thumbs_up_down is True or (f.rating is not None and f.rating >= 4):
            agent_stats[f.agent_id]["positive"] += 1

    # Sort by positive ratio
    sorted_agents = sorted(
        agent_stats.items(),
        key=lambda x: x[1]["positive"] / x[1]["total"] if x[1]["total"] > 0 else 0,
        reverse=True
    )

    # Get agent names
    top_agents = []
    for agent_id, stats in sorted_agents[:limit]:
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if agent:
            top_agents.append({
                "agent_id": agent_id,
                "agent_name": agent.name,
                "positive_count": stats["positive"],
                "total_count": stats["total"],
                "positive_ratio": stats["positive"] / stats["total"] if stats["total"] > 0 else 0
            })

    # Most corrected agents (by correction type feedback)
    correction_counts = {}
    for f in all_feedback:
        if f.feedback_type == "correction":
            correction_counts[f.agent_id] = correction_counts.get(f.agent_id, 0) + 1

    sorted_corrected = sorted(correction_counts.items(), key=lambda x: x[1], reverse=True)

    most_corrected = []
    for agent_id, count in sorted_corrected[:limit]:
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if agent:
            most_corrected.append({
                "agent_id": agent_id,
                "agent_name": agent.name,
                "correction_count": count
            })

    # Feedback by type
    feedback_by_type = {}
    for f in all_feedback:
        if f.feedback_type:
            feedback_by_type[f.feedback_type] = feedback_by_type.get(f.feedback_type, 0) + 1

    # Feedback trends
    trend_7d = db.query(AgentFeedback).filter(
        AgentFeedback.created_at >= datetime.now() - timedelta(days=7)
    ).count()

    trend_30d = db.query(AgentFeedback).filter(
        AgentFeedback.created_at >= datetime.now() - timedelta(days=30)
    ).count()

    return router.success_response(
        data={
            "total_feedback": total_feedback,
            "total_agents_with_feedback": agents_with_feedback,
            "overall_positive_ratio": positive_ratio,
            "overall_average_rating": avg_rating,
            "top_performing_agents": top_agents,
            "most_corrected_agents": most_corrected,
            "feedback_by_type": feedback_by_type,
            "feedback_trends_7d": {"total": trend_7d},
            "feedback_trends_30d": {"total": trend_30d}
        },
        message=f"Retrieved analytics for {days} days"
    )


@router.get("/trends", response_model=List[FeedbackTrend])
async def get_feedback_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get feedback trends over time.

    Returns daily feedback counts and ratings for the specified time period.

    Args:
        days: Number of days to analyze (default: 30)
        db: Database session

    Returns:
        List of FeedbackTrend data points
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    # Get all feedback in date range
    all_feedback = db.query(AgentFeedback).filter(
        AgentFeedback.created_at >= cutoff_date
    ).all()

    # Group by date
    trends_by_date = {}
    for f in all_feedback:
        date_key = f.created_at.strftime("%Y-%m-%d")

        if date_key not in trends_by_date:
            trends_by_date[date_key] = {
                "total": 0,
                "positive": 0,
                "negative": 0,
                "ratings": []
            }

        trends_by_date[date_key]["total"] += 1

        if f.thumbs_up_down is True or (f.rating is not None and f.rating >= 4):
            trends_by_date[date_key]["positive"] += 1

        if f.thumbs_up_down is False or (f.rating is not None and f.rating <= 2):
            trends_by_date[date_key]["negative"] += 1

        if f.rating is not None:
            trends_by_date[date_key]["ratings"].append(f.rating)

    # Convert to response format
    trends = []
    for date_key in sorted(trends_by_date.keys()):
        data = trends_by_date[date_key]
        ratings = data["ratings"]
        avg_rating = sum(ratings) / len(ratings) if ratings else None

        trends.append(FeedbackTrend(
            date=date_key,
            total=data["total"],
            positive=data["positive"],
            negative=data["negative"],
            average_rating=avg_rating
        ))

    return router.success_list_response(
        items=trends,
        message=f"Retrieved feedback trends for {days} days"
    )

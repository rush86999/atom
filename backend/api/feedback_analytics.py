"""
Feedback Analytics Dashboard Endpoint

Provides a comprehensive analytics dashboard for agent feedback data.
Aggregates feedback statistics, trends, and insights.

Endpoints:
- GET /api/feedback/analytics - Overall feedback analytics
- GET /api/feedback/agent/{agent_id}/analytics - Per-agent analytics
- GET /api/feedback/trends - Feedback trends over time
"""

import logging
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.feedback_analytics import FeedbackAnalytics

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def get_feedback_analytics_dashboard(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    limit: int = Query(10, ge=1, le=100, description="Limit for top/bottom agents"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive feedback analytics dashboard.

    Returns a complete overview of feedback including:
    - Total feedback count
    - Overall positive/negative ratio
    - Overall average rating
    - Top performing agents
    - Most corrected agents
    - Feedback breakdown by type
    - Feedback trends (7d, 30d)

    Args:
        days: Number of days to analyze (default: 30)
        limit: Limit for top/bottom agent lists (default: 10)
        db: Database session

    Returns:
        Complete analytics dashboard
    """
    analytics = FeedbackAnalytics(db)

    # Get overall statistics
    stats = analytics.get_feedback_statistics(days=days)

    # Get top performing agents
    top_agents = analytics.get_top_performing_agents(days=days, limit=limit)

    # Get most corrected agents
    most_corrected = analytics.get_most_corrected_agents(days=days, limit=limit)

    # Get feedback breakdown by type
    breakdown = analytics.get_feedback_breakdown_by_type(days=days)

    # Get trends
    trends = analytics.get_feedback_trends(days=days)

    return {
        "period_days": days,
        "summary": stats,
        "top_performing_agents": top_agents,
        "most_corrected_agents": most_corrected,
        "feedback_by_type": breakdown,
        "trends": trends
    }


@router.get("/agent/{agent_id}")
async def get_agent_feedback_dashboard(
    agent_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get detailed feedback dashboard for a specific agent.

    Returns comprehensive analytics for a single agent including:
    - Total feedback count
    - Positive/negative breakdown
    - Thumbs up/down counts
    - Average rating
    - Rating distribution
    - Feedback types breakdown
    - Learning signals
    - Improvement suggestions

    Args:
        agent_id: ID of the agent
        days: Number of days to analyze (default: 30)
        db: Database session

    Returns:
        Agent-specific analytics dashboard
    """
    from core.agent_learning_enhanced import AgentLearningEnhanced

    analytics = FeedbackAnalytics(db)
    learning = AgentLearningEnhanced(db)

    # Get feedback summary
    summary = analytics.get_agent_feedback_summary(agent_id=agent_id, days=days)

    # Get learning signals
    signals = learning.get_learning_signals(agent_id=agent_id, days=days)

    return {
        "agent_id": agent_id,
        "period_days": days,
        "feedback_summary": summary,
        "learning_signals": signals
    }


@router.get("/trends")
async def get_feedback_trends_endpoint(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get feedback trends over time.

    Returns daily feedback counts, positive/negative breakdown,
    and average ratings for the specified time period.

    Useful for visualizing feedback patterns in charts/graphs.

    Args:
        days: Number of days to analyze (default: 30)
        db: Database session

    Returns:
        List of daily feedback trends
    """
    analytics = FeedbackAnalytics(db)
    trends = analytics.get_feedback_trends(days=days)

    return {
        "period_days": days,
        "trends": trends
    }

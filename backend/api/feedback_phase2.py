"""
Feedback Phase 2 API Endpoints

Integrates all Phase 2 features:
- Batch operations
- Promotion suggestions
- Export functionality
- Advanced analytics

Endpoints:
- GET /api/feedback/phase2/promotion-suggestions - Get agents ready for promotion
- GET /api/feedback/phase2/promotion-path/{agent_id} - Get promotion path for agent
- GET /api/feedback/phase2/export - Export feedback data
- GET /api/feedback/phase2/analytics/advanced - Advanced analytics
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.agent_promotion_service import AgentPromotionService
from core.database import get_db
from core.feedback_advanced_analytics import AdvancedFeedbackAnalytics
from core.feedback_export_service import FeedbackExportService

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Promotion Endpoints
# ============================================================================

@router.get("/promotion-suggestions")
async def get_promotion_suggestions(
    limit: int = Query(10, ge=1, le=50, description="Maximum number of suggestions"),
    db: Session = Depends(get_db)
):
    """
    Get agents ready for promotion with detailed reasoning.

    Analyzes all agents and returns those meeting promotion criteria.

    Response:
        List of promotion suggestions with:
        - Agent info (id, name, current status)
        - Target status
        - Readiness score (0.0 to 1.0)
        - Reason for readiness
        - Criteria met and failed
    """
    service = AgentPromotionService(db)
    suggestions = service.get_promotion_suggestions(limit=limit)

    return {
        "total_suggestions": len(suggestions),
        "suggestions": suggestions
    }


@router.get("/promotion-path/{agent_id}")
async def get_promotion_path(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed promotion path for an agent.

    Shows the complete path from current level to AUTONOMOUS
    with requirements and progress for each step.

    Response:
        Promotion path with:
        - Current status and confidence
        - Steps to next level
        - Requirements for each step
        - Current progress
        - Criteria met/failed
    """
    service = AgentPromotionService(db)
    path = service.get_promotion_path(agent_id)

    if "error" in path:
        raise HTTPException(status_code=404, detail=path["error"])

    return path


@router.get("/promotion-check/{agent_id}")
async def check_agent_promotion_readiness(
    agent_id: str,
    target_status: Optional[str] = Query(None, description="Target status (auto-detected if not provided)"),
    db: Session = Depends(get_db)
):
    """
    Check if a specific agent is ready for promotion.

    Evaluates agent against promotion criteria and provides
    detailed feedback on readiness.

    Response:
        Readiness evaluation with:
        - Ready status (boolean)
        - Readiness score
        - Target status
        - Criteria met and failed
        - Reason for decision
    """
    service = AgentPromotionService(db)
    evaluation = service.is_agent_ready_for_promotion(
        agent_id=agent_id,
        target_status=target_status
    )

    if "error" in evaluation:
        raise HTTPException(status_code=404, detail=evaluation["error"])

    return evaluation


# ============================================================================
# Export Endpoints
# ============================================================================

@router.get("/export")
async def export_feedback(
    format: str = Query("json", description="Export format: json or csv"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days to export"),
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum records"),
    db: Session = Depends(get_db)
):
    """
    Export feedback data in JSON or CSV format.

    Supports filtering by agent, date range, feedback type, and status.

    Query Parameters:
        - format: Export format (json or csv)
        - agent_id: Optional agent filter
        - days: Number of days to look back
        - feedback_type: Optional feedback type filter
        - status: Optional status filter
        - limit: Maximum records to export

    Response:
        Downloadable file with feedback data
    """
    service = FeedbackExportService(db)

    if format == "json":
        data = service.export_to_json(
            agent_id=agent_id,
            days=days,
            feedback_type=feedback_type,
            status=status,
            limit=limit
        )
        media_type = "application/json"
        filename = f"feedback_export_{datetime.now().strftime('%Y%m%d')}.json"

    elif format == "csv":
        data = service.export_to_csv(
            agent_id=agent_id,
            days=days,
            feedback_type=feedback_type,
            status=status,
            limit=limit
        )
        media_type = "text/csv"
        filename = f"feedback_export_{datetime.now().strftime('%Y%m%d')}.csv"

    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Must be 'json' or 'csv'"
        )

    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/export/summary")
async def export_feedback_summary(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Export feedback summary statistics.

    Provides aggregated statistics rather than individual records.

    Response:
        Summary statistics in JSON format
    """
    service = FeedbackExportService(db)
    data = service.export_summary_to_json(
        agent_id=agent_id,
        days=days
    )

    return Response(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=feedback_summary_{datetime.now().strftime('%Y%m%d')}.json"
        }
    )


@router.get("/export/filters")
async def get_export_filters(
    db: Session = Depends(get_db)
):
    """
    Get available filter values for export.

    Returns unique values for agent IDs, feedback types, and statuses
    to help build export UI filters.

    Response:
        Available filter values
    """
    service = FeedbackExportService(db)
    filters = service.get_export_filters(db)

    return filters


# ============================================================================
# Advanced Analytics Endpoints
# ============================================================================

@router.get("/analytics/advanced/correlation/{agent_id}")
async def analyze_feedback_performance_correlation(
    agent_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Analyze correlation between feedback and agent execution performance.

    Determines if positive feedback correlates with successful executions.

    Response:
        Correlation analysis with:
        - Positive/negative feedback execution counts
        - Success rates for each
        - Correlation strength
        - Interpretation
    """
    service = AdvancedFeedbackAnalytics(db)
    correlation = service.analyze_feedback_performance_correlation(
        agent_id=agent_id,
        days=days
    )

    return correlation


@router.get("/analytics/advanced/cohorts")
async def analyze_feedback_by_cohorts(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Analyze feedback patterns by agent cohorts (categories).

    Groups agents by category and compares feedback patterns.

    Response:
        Cohort analysis with:
        - Agent categories
        - Feedback counts per category
        - Positive/negative ratios
        - Average ratings
        - Correction counts
    """
    service = AdvancedFeedbackAnalytics(db)
    cohorts = service.analyze_feedback_by_agent_cohort(days=days)

    return cohorts


@router.get("/analytics/advanced/prediction/{agent_id}")
async def predict_agent_performance(
    agent_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Predict agent future performance based on feedback trends.

    Analyzes feedback trends to make predictions about future performance.

    Response:
        Performance prediction with:
        - Trend analysis
        - Prediction (improving/stable/declining)
        - Confidence level
        - Recommendations
    """
    service = AdvancedFeedbackAnalytics(db)
    prediction = service.predict_agent_performance(
        agent_id=agent_id,
        days=days
    )

    return prediction


@router.get("/analytics/advanced/velocity/{agent_id}")
async def analyze_feedback_velocity(
    agent_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Analyze the velocity of feedback (accumulation rate).

    Determines if feedback is accumulating steadily or in bursts.

    Response:
        Velocity analysis with:
        - Average feedback per day
        - Max/min per day
        - Pattern (uniform/bursty/variable)
        - Daily breakdown
    """
    service = AdvancedFeedbackAnalytics(db)
    velocity = service.analyze_feedback_velocity(
        agent_id=agent_id,
        days=days
    )

    return velocity

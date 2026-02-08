"""
Project Health Routes

Provides project health metrics and monitoring.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User
from core.security_dependencies import get_current_user

router = BaseAPIRouter(prefix="/api/v1/projects", tags=["project-health"])
logger = logging.getLogger(__name__)


# Request/Response Models
class ProjectHealthRequest(BaseModel):
    """Project health check request"""
    notion_api_key: Optional[str] = Field(None, description="Notion API key")
    notion_database_id: Optional[str] = Field(None, description="Notion database ID")
    github_owner: Optional[str] = Field(None, description="GitHub repository owner")
    github_repo: Optional[str] = Field(None, description="GitHub repository name")
    slack_channel_id: Optional[str] = Field(None, description="Slack channel ID")
    time_range_days: int = Field(7, ge=1, le=90, description="Time range for analysis")

    model_config = ConfigDict(extra="allow")


class HealthMetric(BaseModel):
    """Individual health metric"""
    name: str
    score: float
    max_score: float
    status: str  # excellent, good, warning, critical
    details: dict
    trend: str  # improving, stable, declining


class ProjectHealthResponse(BaseModel):
    """Project health check response"""
    check_id: str
    overall_score: float
    overall_status: str
    metrics: dict[str, HealthMetric]
    recommendations: List[str]
    checked_at: datetime
    time_range_days: int


async def calculate_notion_health(
    api_key: str,
    database_id: str,
    time_range_days: int
) -> HealthMetric:
    """
    Calculate Notion task management health.

    Measures: Task completion rate, overdue tasks, task velocity.

    TODO: Integrate with actual Notion API
    """
    # Simulated data for development
    # In production, query Notion API for actual task data

    total_tasks = 50
    completed_tasks = 35
    completion_rate = (completed_tasks / total_tasks) * 100

    # Calculate score
    score = completion_rate

    # Determine status
    if score >= 80:
        status = "excellent"
    elif score >= 60:
        status = "good"
    elif score >= 40:
        status = "warning"
    else:
        status = "critical"

    return HealthMetric(
        name="Task Management",
        score=round(score, 1),
        max_score=100.0,
        status=status,
        details={
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": f"{completion_rate:.1f}%",
            "overdue_tasks": 3,
            "upcoming_deadlines": 12
        },
        trend="stable"
    )


async def calculate_github_health(
    owner: str,
    repo: str,
    time_range_days: int
) -> HealthMetric:
    """
    Calculate GitHub code health.

    Measures: Commit activity, PR status, code review speed, issues.

    TODO: Integrate with actual GitHub API
    """
    # Simulated data for development
    # In production, query GitHub API for actual repository data

    commits_per_week = 15
    open_prs = 5
    closed_issues_last_week = 8

    # Calculate score based on activity
    activity_score = min(100, (commits_per_week / 20) * 50)  # Max 50 points
    pr_score = max(0, 50 - (open_prs * 5))  # Lose points for open PRs
    issue_score = min(50, (closed_issues_last_week / 10) * 50)  # Max 50 points

    score = activity_score + pr_score + issue_score

    # Determine status
    if score >= 80:
        status = "excellent"
    elif score >= 60:
        status = "good"
    elif score >= 40:
        status = "warning"
    else:
        status = "critical"

    return HealthMetric(
        name="Code Health",
        score=round(score, 1),
        max_score=150.0,
        status=status,
        details={
            "commits_per_week": commits_per_week,
            "open_pull_requests": open_prs,
            "closed_issues_last_week": closed_issues_last_week,
            "avg_review_time_hours": 24
        },
        trend="improving"
    )


async def calculate_slack_health(
    channel_id: str,
    time_range_days: int
) -> HealthMetric:
    """
    Calculate Slack communication health.

    Measures: Message volume, response time, sentiment.

    TODO: Integrate with actual Slack API
    """
    # Simulated data for development
    # In production, query Slack API for actual message data

    messages_per_day = 45
    avg_response_time_hours = 2.5
    sentiment_score = 65  # -100 to 100 scale

    # Calculate score
    volume_score = min(50, (messages_per_day / 50) * 50)  # Max 50 points
    response_score = max(0, 50 - (avg_response_time_hours * 5))  # Max 50 points
    sentiment_adjustment = (sentiment_score / 100) * 50  # Max 50 points

    score = volume_score + response_score + sentiment_adjustment

    # Determine status
    if score >= 80:
        status = "excellent"
    elif score >= 60:
        status = "good"
    elif score >= 40:
        status = "warning"
    else:
        status = "critical"

    return HealthMetric(
        name="Communication",
        score=round(score, 1),
        max_score=150.0,
        status=status,
        details={
            "messages_per_day": messages_per_day,
            "avg_response_time_hours": round(avg_response_time_hours, 1),
            "sentiment_score": sentiment_score,
            "active_members": 12
        },
        trend="stable"
    )


async def calculate_meeting_health(time_range_days: int) -> HealthMetric:
    """
    Calculate meeting health.

    Measures: Meeting load, meeting effectiveness, focus time.

    TODO: Integrate with Google Calendar API
    """
    # Simulated data for development

    meeting_hours_per_week = 12
    focus_hours_per_week = 20
    avg_meeting_attendees = 6

    # Calculate score
    # Ideal: 10-15 hours of meetings per week
    if meeting_hours_per_week <= 15:
        meeting_score = 50
    elif meeting_hours_per_week <= 20:
        meeting_score = 30
    else:
        meeting_score = 10

    focus_score = (focus_hours_per_week / 25) * 50  # Max 50 points

    score = meeting_score + focus_score

    # Determine status
    if score >= 80:
        status = "excellent"
    elif score >= 60:
        status = "good"
    elif score >= 40:
        status = "warning"
    else:
        status = "critical"

    return HealthMetric(
        name="Meeting Balance",
        score=round(score, 1),
        max_score=100.0,
        status=status,
        details={
            "meeting_hours_per_week": meeting_hours_per_week,
            "focus_hours_per_week": focus_hours_per_week,
            "avg_meeting_attendees": avg_meeting_attendees,
            "meetings_per_week": 8
        },
        trend="declining" if meeting_hours_per_week > 15 else "stable"
    )


def generate_overall_recommendations(metrics: dict[str, HealthMetric]) -> List[str]:
    """Generate recommendations based on health metrics."""
    recommendations = []

    for metric_name, metric in metrics.items():
        if metric.status in ["warning", "critical"]:
            if metric_name == "Task Management":
                recommendations.append(
                    "Consider prioritizing overdue tasks and breaking down large tasks into smaller chunks"
                )
            elif metric_name == "Code Health":
                recommendations.append(
                    "Focus on closing open PRs and reducing code review turnaround time"
                )
            elif metric_name == "Communication":
                recommendations.append(
                    "Improve response times and consider async communication for non-urgent matters"
                )
            elif metric_name == "Meeting Balance":
                recommendations.append(
                    "Reduce meeting load and protect focus time for deep work"
                )

    if not recommendations:
        recommendations.append("Project health is good! Maintain current practices.")

    return recommendations


def calculate_overall_score(metrics: dict[str, HealthMetric]) -> tuple[float, str]:
    """Calculate overall health score from individual metrics."""
    if not metrics:
        return 0.0, "unknown"

    # Normalize scores to 0-100 scale
    normalized_scores = []
    for metric in metrics.values():
        normalized = (metric.score / metric.max_score) * 100
        normalized_scores.append(normalized)

    overall = sum(normalized_scores) / len(normalized_scores)

    # Determine status
    if overall >= 80:
        status = "excellent"
    elif overall >= 60:
        status = "good"
    elif overall >= 40:
        status = "warning"
    else:
        status = "critical"

    return round(overall, 1), status


@router.post("/health", response_model=ProjectHealthResponse)
async def check_project_health(
    request: Request,
    payload: ProjectHealthRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check overall project health across multiple dimensions.

    Analyzes:
    - Task management (Notion)
    - Code quality (GitHub)
    - Communication (Slack)
    - Meeting balance (Calendar)

    Returns overall score, individual metrics, and recommendations.

    TODO: Integrate with actual APIs (Notion, GitHub, Slack, Calendar)
    TODO: Implement time-series tracking for trends
    TODO: Add alerting thresholds
    """
    try:

        # Generate check ID
        check_id = str(uuid.uuid4())

        logger.info(
            f"Checking project health: user={current_user.id}, "
            f"check_id={check_id}, "
            f"time_range={payload.time_range_days} days"
        )

        metrics = {}

        # Calculate Notion health (if credentials provided)
        if payload.notion_api_key and payload.notion_database_id:
            try:
                notion_metric = await calculate_notion_health(
                    payload.notion_api_key,
                    payload.notion_database_id,
                    payload.time_range_days
                )
                metrics["notion"] = notion_metric
            except Exception as e:
                logger.error(f"Failed to calculate Notion health: {e}")

        # Calculate GitHub health (if credentials provided)
        if payload.github_owner and payload.github_repo:
            try:
                github_metric = await calculate_github_health(
                    payload.github_owner,
                    payload.github_repo,
                    payload.time_range_days
                )
                metrics["github"] = github_metric
            except Exception as e:
                logger.error(f"Failed to calculate GitHub health: {e}")

        # Calculate Slack health (if credentials provided)
        if payload.slack_channel_id:
            try:
                slack_metric = await calculate_slack_health(
                    payload.slack_channel_id,
                    payload.time_range_days
                )
                metrics["slack"] = slack_metric
            except Exception as e:
                logger.error(f"Failed to calculate Slack health: {e}")

        # Calculate meeting health (always available)
        try:
            meeting_metric = await calculate_meeting_health(payload.time_range_days)
            metrics["meetings"] = meeting_metric
        except Exception as e:
            logger.error(f"Failed to calculate meeting health: {e}")

        # If no metrics could be calculated, return error
        if not metrics:
            raise HTTPException(
                status_code=400,
                detail="No valid credentials provided. At least one integration is required."
            )

        # Calculate overall score
        overall_score, overall_status = calculate_overall_score(metrics)

        # Generate recommendations
        recommendations = generate_overall_recommendations(metrics)

        logger.info(
            f"Project health check complete: check_id={check_id}, "
            f"overall_score={overall_score}, "
            f"metrics_calculated={len(metrics)}"
        )

        return ProjectHealthResponse(
            check_id=check_id,
            overall_score=overall_score,
            overall_status=overall_status,
            metrics=metrics,
            recommendations=recommendations,
            checked_at=datetime.utcnow(),
            time_range_days=payload.time_range_days
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Project health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check project health: {str(e)}"
        )


@router.get("/health/templates")
async def list_health_check_templates():
    """
    List available project health check templates.

    Pre-configured templates for different project types.
    """
    templates = {
        "software_development": {
            "name": "Software Development",
            "metrics": ["notion", "github", "slack", "meetings"],
            "description": "Full-stack development project health"
        },
        "product_team": {
            "name": "Product Team",
            "metrics": ["notion", "slack", "meetings"],
            "description": "Product management and design team"
        },
        "research": {
            "name": "Research Project",
            "metrics": ["notion", "slack", "meetings"],
            "description": "Academic or industry research"
        },
        "startup": {
            "name": "Startup",
            "metrics": ["notion", "github", "slack"],
            "description": "Early-stage startup with rapid iteration"
        }
    }

    return {
        "templates": templates,
        "total": len(templates)
    }

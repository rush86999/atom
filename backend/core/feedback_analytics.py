"""
Feedback Analytics Service

Provides analytics and aggregation functions for agent feedback data.
Computes statistics, trends, and patterns from user feedback.

Usage:
    from core.feedback_analytics import FeedbackAnalytics

    analytics = FeedbackAnalytics(db)

    # Get agent feedback summary
    summary = analytics.get_agent_feedback_summary("agent-1", days=30)

    # Get overall statistics
    stats = analytics.get_feedback_statistics(days=30)

    # Get trends
    trends = analytics.get_feedback_trends(days=30)
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.models import AgentFeedback, AgentRegistry

logger = logging.getLogger(__name__)


class FeedbackAnalytics:
    """
    Service for analyzing agent feedback data.

    Provides methods for aggregating feedback, computing statistics,
    and identifying patterns in user feedback.
    """

    def __init__(self, db: Session):
        """
        Initialize feedback analytics service.

        Args:
            db: Database session
        """
        self.db = db

    def get_agent_feedback_summary(
        self,
        agent_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get feedback summary for a specific agent.

        Args:
            agent_id: ID of the agent
            days: Number of days to look back

        Returns:
            Dictionary with feedback summary statistics

        Raises:
            ValueError: If agent not found
        """
        # Validate agent exists
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent '{agent_id}' not found")

        cutoff_date = datetime.now() - timedelta(days=days)

        # Query feedback
        feedback = self.db.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent_id,
            AgentFeedback.created_at >= cutoff_date
        ).all()

        total = len(feedback)

        if total == 0:
            return {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "total_feedback": 0,
                "positive_count": 0,
                "negative_count": 0,
                "thumbs_up_count": 0,
                "thumbs_down_count": 0,
                "average_rating": None,
                "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                "feedback_types": {}
            }

        # Calculate statistics
        thumbs_up = sum(1 for f in feedback if f.thumbs_up_down is True)
        thumbs_down = sum(1 for f in feedback if f.thumbs_up_down is False)

        positive = sum(
            1 for f in feedback
            if f.thumbs_up_down is True or (f.rating is not None and f.rating >= 4)
        )

        negative = sum(
            1 for f in feedback
            if f.thumbs_up_down is False or (f.rating is not None and f.rating <= 2)
        )

        # Rating distribution
        rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        ratings = [f.rating for f in feedback if f.rating is not None]
        for r in ratings:
            rating_dist[r] += 1

        avg_rating = sum(ratings) / len(ratings) if ratings else None

        # Feedback types
        feedback_types = {}
        for f in feedback:
            if f.feedback_type:
                feedback_types[f.feedback_type] = feedback_types.get(f.feedback_type, 0) + 1

        return {
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
        }

    def get_feedback_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get overall feedback statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with overall statistics
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Total feedback
        total_feedback = self.db.query(AgentFeedback).filter(
            AgentFeedback.created_at >= cutoff_date
        ).count()

        # Total agents with feedback
        agents_with_feedback = self.db.query(func.count(func.distinct(AgentFeedback.agent_id))).filter(
            AgentFeedback.created_at >= cutoff_date
        ).scalar() or 0

        # All feedback in date range
        all_feedback = self.db.query(AgentFeedback).filter(
            AgentFeedback.created_at >= cutoff_date
        ).all()

        if total_feedback == 0:
            return {
                "total_feedback": 0,
                "total_agents_with_feedback": 0,
                "overall_positive_ratio": 0,
                "overall_average_rating": None,
                "feedback_by_type": {}
            }

        # Positive/negative counts
        positive = sum(
            1 for f in all_feedback
            if f.thumbs_up_down is True or (f.rating is not None and f.rating >= 4)
        )

        negative = sum(
            1 for f in all_feedback
            if f.thumbs_up_down is False or (f.rating is not None and f.rating <= 2)
        )

        positive_ratio = positive / total_feedback

        # Average rating
        ratings = [f.rating for f in all_feedback if f.rating is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else None

        # Feedback by type
        feedback_by_type = {}
        for f in all_feedback:
            if f.feedback_type:
                feedback_by_type[f.feedback_type] = feedback_by_type.get(f.feedback_type, 0) + 1

        return {
            "total_feedback": total_feedback,
            "total_agents_with_feedback": agents_with_feedback,
            "overall_positive_ratio": positive_ratio,
            "overall_average_rating": avg_rating,
            "feedback_by_type": feedback_by_type
        }

    def get_top_performing_agents(
        self,
        days: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top performing agents by positive feedback ratio.

        Args:
            days: Number of days to analyze
            limit: Maximum number of agents to return

        Returns:
            List of top performing agents with statistics
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Get all feedback in date range
        all_feedback = self.db.query(AgentFeedback).filter(
            AgentFeedback.created_at >= cutoff_date
        ).all()

        # Aggregate by agent
        agent_stats = {}
        for f in all_feedback:
            if f.agent_id not in agent_stats:
                agent_stats[f.agent_id] = {"positive": 0, "total": 0}
            agent_stats[f.agent_id]["total"] += 1
            if f.thumbs_up_down is True or (f.rating is not None and f.rating >= 4):
                agent_stats[f.agent_id]["positive"] += 1

        # Sort by positive ratio (minimum 5 feedback to qualify)
        qualified_agents = {
            agent_id: stats for agent_id, stats in agent_stats.items()
            if stats["total"] >= 5
        }

        sorted_agents = sorted(
            qualified_agents.items(),
            key=lambda x: x[1]["positive"] / x[1]["total"],
            reverse=True
        )

        # Get agent names and build result
        top_agents = []
        for agent_id, stats in sorted_agents[:limit]:
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if agent:
                top_agents.append({
                    "agent_id": agent_id,
                    "agent_name": agent.name,
                    "positive_count": stats["positive"],
                    "total_count": stats["total"],
                    "positive_ratio": stats["positive"] / stats["total"]
                })

        return top_agents

    def get_most_corrected_agents(
        self,
        days: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get agents with the most correction feedback.

        Args:
            days: Number of days to analyze
            limit: Maximum number of agents to return

        Returns:
            List of most corrected agents with correction counts
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Count corrections by agent
        correction_counts = self.db.query(
            AgentFeedback.agent_id,
            func.count(AgentFeedback.id).label('count')
        ).filter(
            AgentFeedback.created_at >= cutoff_date,
            AgentFeedback.feedback_type == "correction"
        ).group_by(
            AgentFeedback.agent_id
        ).order_by(
            func.count(AgentFeedback.id).desc()
        ).limit(limit).all()

        # Get agent names
        most_corrected = []
        for agent_id, count in correction_counts:
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if agent:
                most_corrected.append({
                    "agent_id": agent_id,
                    "agent_name": agent.name,
                    "correction_count": count
                })

        return most_corrected

    def get_feedback_trends(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get feedback trends over time.

        Args:
            days: Number of days to analyze

        Returns:
            List of daily feedback trends
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Get all feedback in date range
        all_feedback = self.db.query(AgentFeedback).filter(
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

        # Convert to list sorted by date
        trends = []
        for date_key in sorted(trends_by_date.keys()):
            data = trends_by_date[date_key]
            ratings = data["ratings"]
            avg_rating = sum(ratings) / len(ratings) if ratings else None

            trends.append({
                "date": date_key,
                "total": data["total"],
                "positive": data["positive"],
                "negative": data["negative"],
                "average_rating": avg_rating
            })

        return trends

    def get_feedback_breakdown_by_type(
        self,
        days: int = 30
    ) -> Dict[str, int]:
        """
        Get feedback breakdown by type.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary mapping feedback type to count
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        feedback = self.db.query(AgentFeedback).filter(
            AgentFeedback.created_at >= cutoff_date
        ).all()

        breakdown = {}
        for f in feedback:
            if f.feedback_type:
                breakdown[f.feedback_type] = breakdown.get(f.feedback_type, 0) + 1

        return breakdown

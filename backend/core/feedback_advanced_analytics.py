"""
Advanced Feedback Analytics Service

Provides sophisticated analytics on feedback data including:
- Feedback correlation with agent performance
- Cohort analysis
- Predictive insights
- Trend analysis

Usage:
    from core.feedback_advanced_analytics import AdvancedFeedbackAnalytics

    analytics = AdvancedFeedbackAnalytics(db)

    # Correlation analysis
    correlation = analytics.analyze_feedback_performance_correlation("agent-1")

    # Cohort analysis
    cohorts = analytics.analyze_feedback_by_agent_cohort(days=30)

    # Predictive insights
    predictions = analytics.predict_agent_performance("agent-1")
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from collections import defaultdict

from core.models import AgentFeedback, AgentRegistry, AgentExecution

logger = logging.getLogger(__name__)


class AdvancedFeedbackAnalytics:
    """
    Advanced analytics service for feedback data.

    Provides insights beyond basic statistics:
    - Correlation between feedback and performance
    - Cohort-based analysis
    - Predictive modeling
    - Trend detection
    """

    def __init__(self, db: Session):
        """
        Initialize advanced analytics service.

        Args:
            db: Database session
        """
        self.db = db

    def analyze_feedback_performance_correlation(
        self,
        agent_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze correlation between feedback and agent execution performance.

        Determines if positive feedback correlates with successful executions
        and identifies patterns.

        Args:
            agent_id: ID of the agent to analyze
            days: Number of days to analyze

        Returns:
            Dictionary with correlation analysis results
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Get feedback with linked executions
        feedback_with_executions = self.db.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent_id,
            AgentFeedback.created_at >= cutoff_date,
            AgentFeedback.agent_execution_id.isnot(None)
        ).all()

        if not feedback_with_executions:
            return {
                "agent_id": agent_id,
                "message": "Insufficient data for correlation analysis"
            }

        # Analyze correlation
        positive_feedback_executions = set()
        negative_feedback_executions = set()

        for feedback in feedback_with_executions:
            if feedback.agent_execution_id:
                if feedback.thumbs_up_down is True or (feedback.rating and feedback.rating >= 4):
                    positive_feedback_executions.add(feedback.agent_execution_id)
                elif feedback.thumbs_up_down is False or (feedback.rating and feedback.rating <= 2):
                    negative_feedback_executions.add(feedback.agent_execution_id)

        # Get execution outcomes
        successful_with_positive = 0
        successful_with_negative = 0
        failed_with_positive = 0
        failed_with_negative = 0

        if positive_feedback_executions:
            successful_executions = self.db.query(AgentExecution).filter(
                AgentExecution.id.in_(positive_feedback_executions),
                AgentExecution.status == "completed"
            ).count()

            failed_executions = self.db.query(AgentExecution).filter(
                AgentExecution.id.in_(positive_feedback_executions),
                AgentExecution.status.in_(["failed", "error"])
            ).count()

            successful_with_positive = successful_executions
            failed_with_positive = failed_executions

        if negative_feedback_executions:
            successful_executions = self.db.query(AgentExecution).filter(
                AgentExecution.id.in_(negative_feedback_executions),
                AgentExecution.status == "completed"
            ).count()

            failed_executions = self.db.query(AgentExecution).filter(
                AgentExecution.id.in_(negative_feedback_executions),
                AgentExecution.status.in_(["failed", "error"])
            ).count()

            successful_with_negative = successful_executions
            failed_with_negative = failed_executions

        # Calculate correlation
        total_positive = len(positive_feedback_executions)
        total_negative = len(negative_feedback_executions)

        positive_success_rate = (
            successful_with_positive / total_positive
            if total_positive > 0 else 0
        )

        negative_success_rate = (
            successful_with_negative / total_negative
            if total_negative > 0 else 0
        )

        # Correlation strength
        correlation_strength = positive_success_rate - negative_success_rate

        return {
            "agent_id": agent_id,
            "analysis_period_days": days,
            "feedback_with_executions": len(feedback_with_executions),
            "positive_feedback_executions": total_positive,
            "negative_feedback_executions": total_negative,
            "positive_success_rate": positive_success_rate,
            "negative_success_rate": negative_success_rate,
            "correlation_strength": correlation_strength,
            "interpretation": self._interpret_correlation(correlation_strength)
        }

    def _interpret_correlation(self, strength: float) -> str:
        """Interpret correlation strength."""
        if strength > 0.3:
            return "Strong positive correlation - positive feedback predicts success"
        elif strength > 0.1:
            return "Moderate positive correlation - positive feedback associated with success"
        elif strength > -0.1:
            return "Weak correlation - feedback and performance not strongly linked"
        elif strength > -0.3:
            return "Moderate negative correlation - surprising pattern, needs investigation"
        else:
            return "Strong negative correlation - investigate feedback quality"

    def analyze_feedback_by_agent_cohort(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze feedback patterns grouped by agent cohorts.

        Groups agents by category and compares feedback patterns
        across cohorts.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with cohort analysis results
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Get all agents with feedback
        agents_with_feedback = self.db.query(
            AgentFeedback.agent_id
        ).filter(
            AgentFeedback.created_at >= cutoff_date
        ).distinct().all()

        # Group by category
        cohort_data = defaultdict(lambda: {
            "agents": [],
            "total_feedback": 0,
            "positive_count": 0,
            "negative_count": 0,
            "average_rating": [],
            "corrections": 0
        })

        for (agent_id,) in agents_with_feedback:
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                continue

            category = agent.category or "Uncategorized"

            # Get feedback for this agent
            feedback = self.db.query(AgentFeedback).filter(
                AgentFeedback.agent_id == agent_id,
                AgentFeedback.created_at >= cutoff_date
            ).all()

            # Aggregate
            cohort_data[category]["agents"].append({
                "id": agent.id,
                "name": agent.name
            })

            cohort_data[category]["total_feedback"] += len(feedback)

            for f in feedback:
                if f.thumbs_up_down is True or (f.rating and f.rating >= 4):
                    cohort_data[category]["positive_count"] += 1
                elif f.thumbs_up_down is False or (f.rating and f.rating <= 2):
                    cohort_data[category]["negative_count"] += 1

                if f.rating is not None:
                    cohort_data[category]["average_rating"].append(f.rating)

                if f.feedback_type == "correction":
                    cohort_data[category]["corrections"] += 1

        # Calculate averages per cohort
        cohort_summary = {}
        for category, data in cohort_data.items():
            avg_rating = (
                sum(data["average_rating"]) / len(data["average_rating"])
                if data["average_rating"] else 0
            )

            positive_ratio = (
                data["positive_count"] / data["total_feedback"]
                if data["total_feedback"] > 0 else 0
            )

            cohort_summary[category] = {
                "agent_count": len(data["agents"]),
                "total_feedback": data["total_feedback"],
                "positive_count": data["positive_count"],
                "negative_count": data["negative_count"],
                "positive_ratio": positive_ratio,
                "average_rating": avg_rating,
                "corrections": data["corrections"]
            }

        return {
            "analysis_period_days": days,
            "cohorts": cohort_summary
        }

    def predict_agent_performance(
        self,
        agent_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Predict agent future performance based on feedback trends.

        Analyzes feedback trends to make predictions about future performance.

        Args:
            agent_id: ID of the agent
            days: Number of days to analyze

        Returns:
            Dictionary with performance predictions
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Get feedback over time
        feedback = self.db.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent_id,
            AgentFeedback.created_at >= cutoff_date
        ).order_by(AgentFeedback.created_at.asc()).all()

        if len(feedback) < 5:
            return {
                "agent_id": agent_id,
                "message": "Insufficient data for prediction"
            }

        # Split into two halves for trend analysis
        mid_point = len(feedback) // 2
        first_half = feedback[:mid_point]
        second_half = feedback[mid_point:]

        # Calculate metrics for each half
        first_half_positive = sum(
            1 for f in first_half
            if f.thumbs_up_down is True or (f.rating and f.rating >= 4)
        )

        second_half_positive = sum(
            1 for f in second_half
            if f.thumbs_up_down is True or (f.rating and f.rating >= 4)
        )

        first_half_ratio = first_half_positive / len(first_half) if first_half else 0
        second_half_ratio = second_half_positive / len(second_half) if second_half else 0

        # Trend
        trend = second_half_ratio - first_half_ratio

        # Predictions
        if trend > 0.2:
            prediction = "improving"
            confidence = "high"
            message = "Agent shows strong improvement trend"
        elif trend > 0.05:
            prediction = "improving"
            confidence = "moderate"
            message = "Agent shows modest improvement trend"
        elif trend > -0.05:
            prediction = "stable"
            confidence = "moderate"
            message = "Agent performance is stable"
        elif trend > -0.2:
            prediction = "declining"
            confidence = "moderate"
            message = "Agent shows modest decline trend"
        else:
            prediction = "declining"
            confidence = "high"
            message = "Agent shows strong decline trend - intervention recommended"

        return {
            "agent_id": agent_id,
            "analysis_period_days": days,
            "total_feedback": len(feedback),
            "first_half_positive_ratio": first_half_ratio,
            "second_half_positive_ratio": second_half_ratio,
            "trend": trend,
            "prediction": prediction,
            "confidence": confidence,
            "message": message,
            "recommendation": self._get_prediction_recommendation(prediction, confidence)
        }

    def _get_prediction_recommendation(self, prediction: str, confidence: str) -> str:
        """Get recommendation based on prediction."""
        if prediction == "improving" and confidence == "high":
            return "Consider agent for promotion"
        elif prediction == "stable":
            return "Continue monitoring"
        elif prediction == "declining" and confidence == "high":
            return "Review agent configuration and consider additional training"
        elif prediction == "declining":
            return "Monitor closely and investigate issues"
        else:
            return "Continue current approach"

    def analyze_feedback_velocity(
        self,
        agent_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze the velocity of feedback (how quickly feedback is received).

        Determines if feedback is accumulating steadily or in bursts.

        Args:
            agent_id: ID of the agent
            days: Number of days to analyze

        Returns:
            Dictionary with velocity analysis
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Get feedback with timestamps
        feedback = self.db.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent_id,
            AgentFeedback.created_at >= cutoff_date
        ).order_by(AgentFeedback.created_at.asc()).all()

        if not feedback:
            return {
                "agent_id": agent_id,
                "message": "No feedback data available"
            }

        # Group by day
        feedback_by_day = defaultdict(int)
        for f in feedback:
            day_key = f.created_at.strftime("%Y-%m-%d")
            feedback_by_day[day_key] += 1

        # Calculate statistics
        daily_counts = list(feedback_by_day.values())
        avg_per_day = sum(daily_counts) / len(daily_counts) if daily_counts else 0
        max_per_day = max(daily_counts) if daily_counts else 0
        min_per_day = min(daily_counts) if daily_counts else 0

        # Determine pattern
        if max_per_day == min_per_day:
            pattern = "uniform"
        elif max_per_day > avg_per_day * 2:
            pattern = "bursty"
        else:
            pattern = "variable"

        return {
            "agent_id": agent_id,
            "analysis_period_days": days,
            "total_feedback": len(feedback),
            "days_with_feedback": len(feedback_by_day),
            "average_per_day": avg_per_day,
            "max_per_day": max_per_day,
            "min_per_day": min_per_day,
            "pattern": pattern,
            "feedback_by_day": dict(feedback_by_day)
        }

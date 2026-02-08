"""
Supervisor Performance Service

Tracks and analyzes supervisor performance metrics for learning and improvement.

Calculates:
- Intervention success rate
- Average rating trends
- Learning curve
- Performance recommendations
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.models import (
    AgentRegistry,
    InterventionOutcome,
    SupervisorPerformance,
    SupervisionSession,
)

logger = logging.getLogger(__name__)


class SupervisorPerformanceService:
    """
    Track and analyze supervisor performance.

    Provides insights into supervisor effectiveness and learning progress.
    """

    def __init__(self, db: Session):
        self.db = db

    async def get_supervisor_metrics(
        self,
        supervisor_id: str,
        time_range_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics for a supervisor.

        Args:
            supervisor_id: Supervisor to analyze
            time_range_days: Time range for analysis (default: 30 days)

        Returns:
            {
                "overall": {
                    "total_sessions": int,
                    "total_interventions": int,
                    "average_rating": float,
                    "confidence_score": float,
                    "competence_level": str
                },
                "interventions": {
                    "total": int,
                    "successful": int,
                    "failed": int,
                    "success_rate": float
                },
                "ratings": {
                    "average": float,
                    "total": int,
                    "distribution": {1: int, 2: int, 3: int, 4: int, 5: int}
                },
                "feedback": {
                    "comments_given": int,
                    "upvotes_received": int,
                    "downvotes_received": int,
                    "vote_ratio": float
                },
                "learning": {
                    "performance_trend": str,
                    "learning_rate": float,
                    "agents_promoted": int,
                    "confidence_boosted": float
                }
            }
        """
        performance = self.db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == supervisor_id
        ).first()

        if not performance:
            return self._empty_metrics()

        # Calculate time-range filtered metrics
        cutoff = datetime.now() - timedelta(days=time_range_days)

        # Get recent sessions
        recent_sessions = self.db.query(SupervisionSession).filter(
            SupervisionSession.supervisor_id == supervisor_id,
            SupervisionSession.started_at >= cutoff
        ).all()

        # Calculate intervention success rate
        intervention_outcomes = self.db.query(InterventionOutcome).filter(
            InterventionOutcome.supervisor_id == supervisor_id,
            InterventionOutcome.assessed_at >= cutoff
        ).all()

        successful = sum(1 for o in intervention_outcomes if o.outcome == "success")
        failed = sum(1 for o in intervention_outcomes if o.outcome == "failure")
        total_interventions = successful + failed

        success_rate = successful / total_interventions if total_interventions > 0 else 0.0

        # Calculate vote ratio
        total_votes = performance.total_upvotes_received + performance.total_downvotes_received
        vote_ratio = performance.total_upvotes_received / total_votes if total_votes > 0 else 0.5

        return {
            "overall": {
                "total_sessions": performance.total_sessions_supervised,
                "total_interventions": performance.total_interventions,
                "average_rating": round(performance.average_rating, 2),
                "confidence_score": round(performance.confidence_score, 3),
                "competence_level": performance.competence_level,
            },
            "interventions": {
                "total": total_interventions,
                "successful": successful,
                "failed": failed,
                "success_rate": round(success_rate, 3),
            },
            "ratings": {
                "average": round(performance.average_rating, 2),
                "total": performance.total_ratings,
                "distribution": {
                    1: performance.rating_1_count,
                    2: performance.rating_2_count,
                    3: performance.rating_3_count,
                    4: performance.rating_4_count,
                    5: performance.rating_5_count,
                }
            },
            "feedback": {
                "comments_given": performance.total_comments_given,
                "upvotes_received": performance.total_upvotes_received,
                "downvotes_received": performance.total_downvotes_received,
                "vote_ratio": round(vote_ratio, 3),
            },
            "learning": {
                "performance_trend": performance.performance_trend,
                "learning_rate": round(performance.learning_rate, 4),
                "agents_promoted": performance.agents_promoted,
                "confidence_boosted": round(performance.agent_confidence_boosted, 3),
            }
        }

    async def track_intervention_outcome(
        self,
        supervision_session_id: str,
        intervention_type: str,
        intervention_timestamp: datetime,
        outcome: str,
        agent_behavior_change: Optional[str] = None,
        task_completion: Optional[str] = None,
        seconds_to_recovery: Optional[int] = None,
        was_necessary: bool = True,
        was_effective: bool = True,
        would_recommend: Optional[bool] = None,
        lesson_learned: Optional[str] = None,
    ) -> InterventionOutcome:
        """
        Track outcome of a supervisor intervention for learning.

        Args:
            supervision_session_id: Session containing intervention
            intervention_type: Type of intervention
            intervention_timestamp: When intervention occurred
            outcome: "success", "partial", "failure"
            agent_behavior_change: How agent behavior changed
            task_completion: What happened to the task
            seconds_to_recovery: Time until agent back on track
            was_necessary: Was this intervention needed?
            was_effective: Did it help?
            would_recommend: Would supervisor do this again?
            lesson_learned: What the supervisor learned

        Returns:
            Created InterventionOutcome
        """
        session = self.db.query(SupervisionSession).filter(
            SupervisionSession.id == supervision_session_id
        ).first()

        if not session:
            raise ValueError(f"Supervision session {supervision_session_id} not found")

        # Create outcome record
        outcome_record = InterventionOutcome(
            supervision_session_id=supervision_session_id,
            supervisor_id=session.supervisor_id,
            agent_id=session.agent_id,
            intervention_type=intervention_type,
            intervention_timestamp=intervention_timestamp,
            outcome=outcome,
            agent_behavior_change=agent_behavior_change,
            task_completion=task_completion,
            seconds_to_recovery=seconds_to_recovery,
            was_necessary=was_necessary,
            was_effective=was_effective,
            would_recommend=would_recommend,
            lesson_learned=lesson_learned,
        )

        self.db.add(outcome_record)
        self.db.commit()

        # Update supervisor performance metrics
        await self._update_intervention_metrics(
            session.supervisor_id,
            outcome,
            was_effective
        )

        logger.info(
            f"Tracked intervention outcome: {outcome} "
            f"by {session.supervisor_id} for {session.agent_id}"
        )

        return outcome_record

    async def get_leaderboard(
        self,
        metric: str = "average_rating",
        limit: int = 10,
        time_range_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get supervisor leaderboard based on metric.

        Args:
            metric: "average_rating", "confidence_score", "success_rate", "total_sessions"
            limit: Max results
            time_range_days: Time range for analysis

        Returns:
            List of supervisors ranked by metric
        """
        cutoff = datetime.now() - timedelta(days=time_range_days)

        # Get all supervisors with activity in time range
        supervisors = self.db.query(SupervisorPerformance).join(
            SupervisionSession,
            SupervisorPerformance.supervisor_id == SupervisionSession.supervisor_id
        ).filter(
            SupervisionSession.started_at >= cutoff
        ).all()

        # Calculate metric for each supervisor
        ranked = []
        for perf in supervisors:
            if metric == "average_rating":
                score = perf.average_rating or 0
            elif metric == "confidence_score":
                score = perf.confidence_score
            elif metric == "success_rate":
                # Calculate success rate from interventions
                outcomes = self.db.query(InterventionOutcome).filter(
                    InterventionOutcome.supervisor_id == perf.supervisor_id,
                    InterventionOutcome.assessed_at >= cutoff
                ).all()

                successful = sum(1 for o in outcomes if o.outcome == "success")
                total = len(outcomes)
                score = successful / total if total > 0 else 0
            elif metric == "total_sessions":
                score = perf.total_sessions_supervised
            else:
                score = 0

            ranked.append({
                "supervisor_id": perf.supervisor_id,
                "score": round(score, 3),
                "competence_level": perf.competence_level,
                "total_sessions": perf.total_sessions_supervised,
                "average_rating": round(perf.average_rating, 2),
            })

        # Sort by score descending
        ranked.sort(key=lambda x: x["score"], reverse=True)

        return ranked[:limit]

    async def get_performance_recommendations(
        self,
        supervisor_id: str
    ) -> List[str]:
        """
        Generate personalized recommendations for supervisor improvement.

        Analyzes performance data and provides actionable insights.
        """
        metrics = await self.get_supervisor_metrics(supervisor_id)
        recommendations = []

        # Analyze rating distribution
        if metrics["ratings"]["total"] > 10:
            # Check for rating imbalance
            low_ratings = metrics["ratings"]["distribution"][1] + metrics["ratings"]["distribution"][2]
            high_ratings = metrics["ratings"]["distribution"][4] + metrics["ratings"]["distribution"][5]

            if low_ratings > high_ratings * 2:
                recommendations.append(
                    "Focus on providing clearer guidance - low ratings suggest "
                    "your interventions may not be clear enough for agents to follow."
                )

        # Analyze intervention success rate
        if metrics["interventions"]["total"] > 10:
            success_rate = metrics["interventions"]["success_rate"]

            if success_rate < 0.5:
                recommendations.append(
                    f"Your intervention success rate is {success_rate:.1%}. Consider "
                    "waiting longer before intervening, or providing more specific guidance."
                )
            elif success_rate > 0.9:
                recommendations.append(
                    "Excellent intervention success rate! Consider documenting your "
                    "approach as best practices to share with other supervisors."
                )

        # Analyze vote ratio
        if metrics["feedback"]["vote_ratio"] < 0.3:
            recommendations.append(
                "Your feedback is receiving more downvotes than upvotes. "
                "Try being more constructive and specific in your comments."
            )

        # Analyze learning trend
        if metrics["learning"]["performance_trend"] == "declining":
            recommendations.append(
                "Your performance metrics have been declining recently. "
                "Consider reviewing recent supervision sessions to identify areas for improvement."
            )
        elif metrics["learning"]["performance_trend"] == "improving":
            recommendations.append(
                "Great job! Your performance has been improving over time. "
                "Continue with your current approach."
            )

        # Check competence level
        if metrics["overall"]["competence_level"] == "novice" and metrics["ratings"]["total"] > 20:
            recommendations.append(
                "You've completed 20+ supervision sessions. Consider reviewing "
                "training materials to advance to intermediate level."
            )

        return recommendations

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _update_intervention_metrics(
        self,
        supervisor_id: str,
        outcome: str,
        was_effective: bool
    ):
        """Update performance metrics after tracking intervention outcome."""
        performance = self.db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == supervisor_id
        ).first()

        if not performance:
            return

        # Update intervention counts
        if was_effective:
            performance.successful_interventions += 1
        else:
            performance.failed_interventions += 1

        # Update total interventions
        performance.total_interventions += 1

        # Update confidence based on effectiveness
        if was_effective:
            # Effective interventions increase confidence slightly
            performance.confidence_score = min(1.0, performance.confidence_score + 0.01)
        else:
            # Ineffective interventions decrease confidence more
            performance.confidence_score = max(0.1, performance.confidence_score - 0.02)

        performance.last_updated = datetime.now()
        self.db.commit()

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            "overall": {
                "total_sessions": 0,
                "total_interventions": 0,
                "average_rating": 0.0,
                "confidence_score": 0.5,
                "competence_level": "novice",
            },
            "interventions": {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
            },
            "ratings": {
                "average": 0.0,
                "total": 0,
                "distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            },
            "feedback": {
                "comments_given": 0,
                "upvotes_received": 0,
                "downvotes_received": 0,
                "vote_ratio": 0.5,
            },
            "learning": {
                "performance_trend": "stable",
                "learning_rate": 0.0,
                "agents_promoted": 0,
                "confidence_boosted": 0.0,
            }
        }

    async def calculate_intervention_success_rate(
        self,
        supervisor_id: str,
        time_range_days: int = 30
    ) -> float:
        """
        Calculate intervention success rate for a supervisor.

        Returns:
            Success rate (0.0 to 1.0)
        """
        cutoff = datetime.now() - timedelta(days=time_range_days)

        outcomes = self.db.query(InterventionOutcome).filter(
            InterventionOutcome.supervisor_id == supervisor_id,
            InterventionOutcome.assessed_at >= cutoff
        ).all()

        if not outcomes:
            return 0.0

        successful = sum(1 for o in outcomes if o.outcome == "success")
        return successful / len(outcomes)

    async def get_supervisor_learning_curve(
        self,
        supervisor_id: str,
        time_range_days: int = 90
    ) -> Dict[str, Any]:
        """
        Calculate supervisor learning curve over time.

        Returns:
            {
                "dates": List[str],
                "ratings": List[float],
                "success_rates": List[float],
                "confidence_scores": List[float],
                "trend": str
            }
        """
        cutoff = datetime.now() - timedelta(days=time_range_days)

        # Get sessions in date order
        sessions = self.db.query(SupervisionSession).filter(
            SupervisionSession.supervisor_id == supervisor_id,
            SupervisionSession.completed_at.isnot(None),
            SupervisionSession.completed_at >= cutoff
        ).order_by(
            SupervisionSession.completed_at.asc()
        ).all()

        if not sessions:
            return {"dates": [], "ratings": [], "success_rates": [], "confidence_scores": [], "trend": "stable"}

        # Group by week
        weekly_data = {}
        for session in sessions:
            week_key = session.completed_at.strftime("%Y-W%U")
            if week_key not in weekly_data:
                weekly_data[week_key] = {
                    "sessions": [],
                    "ratings": [],
                }
            weekly_data[week_key]["sessions"].append(session)

        # Calculate metrics by week
        dates = []
        ratings = []
        confidence_scores = []
        success_rates = []

        for week_key in sorted(weekly_data.keys()):
            week_sessions = weekly_data[week_key]["sessions"]

            # Average rating for this week
            week_ratings = [s.supervisor_rating for s in week_sessions if s.supervisor_rating]
            avg_rating = sum(week_ratings) / len(week_ratings) if week_ratings else 0
            ratings.append(avg_rating)

            # Success rate for this week
            week_outcomes = self.db.query(InterventionOutcome).filter(
                InterventionOutcome.supervisor_id == supervisor_id,
                InterventionOutcome.assessed_at >= week_sessions[0].completed_at,
                InterventionOutcome.assessed_at <= week_sessions[-1].completed_at + timedelta(days=7)
            ).all()

            successful = sum(1 for o in week_outcomes if o.outcome == "success")
            success_rate = successful / len(week_outcomes) if week_outcomes else 0
            success_rates.append(success_rate)

            # Average confidence from performance records
            perf = self.db.query(SupervisorPerformance).filter(
                SupervisorPerformance.supervisor_id == supervisor_id
            ).first()

            confidence_scores.append(perf.confidence_score if perf else 0.5)
            dates.append(week_key)

        # Determine trend
        if len(ratings) >= 4:
            recent_avg = sum(ratings[-2:]) / 2
            earlier_avg = sum(ratings[:-2]) / len(ratings[:-2])

            if recent_avg > earlier_avg + 0.3:
                trend = "improving"
            elif recent_avg < earlier_avg - 0.3:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "dates": dates,
            "ratings": ratings,
            "success_rates": success_rates,
            "confidence_scores": confidence_scores,
            "trend": trend,
        }

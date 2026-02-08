"""
Supervisor Learning Service

Orchestrates supervisor learning from feedback and outcomes.
Updates confidence scores, tracks improvement, and generates insights.

Key Features:
- Confidence score updates based on feedback
- Learning rate calculation
- Performance trend analysis
- Personalized learning recommendations
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.models import (
    SupervisorPerformance,
    SupervisorRating,
    SupervisorComment,
    FeedbackVote,
    InterventionOutcome,
)

logger = logging.getLogger(__name__)


class SupervisorLearningService:
    """
    Orchestrate supervisor learning and improvement.

    Coordinates feedback collection, performance tracking,
    and confidence score updates to enable continuous learning.
    """

    # Confidence adjustment parameters
    RATING_BOOST = {
        5: 0.05,   # Excellent rating -> +5% confidence
        4: 0.02,   # Good rating -> +2% confidence
        3: 0.0,    # Neutral -> no change
        2: -0.02,  # Poor rating -> -2% confidence
        1: -0.05,  # Terrible rating -> -5% confidence
    }

    def __init__(self, db: Session):
        self.db = db

    async def process_feedback_for_learning(
        self,
        supervisor_id: str,
        feedback_type: str,
        feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process feedback and update supervisor learning.

        Args:
            supervisor_id: Supervisor receiving feedback
            feedback_type: "rating", "vote", "comment_vote", "intervention_outcome"
            feedback_data: Feedback details

        Returns:
            Learning update summary
        """
        performance = await self._get_or_create_performance(supervisor_id)

        old_confidence = performance.confidence_score
        old_competence = performance.competence_level

        # Process based on feedback type
        if feedback_type == "rating":
            await self._process_rating(performance, feedback_data)
        elif feedback_type == "vote":
            await self._process_vote(performance, feedback_data)
        elif feedback_type == "intervention_outcome":
            await self._process_intervention_outcome(performance, feedback_data)
        else:
            logger.warning(f"Unknown feedback type: {feedback_type}")

        # Update trend and competence
        await self._update_learning_metrics(performance)

        new_confidence = performance.confidence_score
        new_competence = performance.competence_level

        self.db.commit()

        logger.info(
            f"Processed {feedback_type} for {supervisor_id}: "
            f"confidence {old_confidence:.3f} -> {new_confidence:.3f}, "
            f"competence {old_competence} -> {new_competence}"
        )

        return {
            "supervisor_id": supervisor_id,
            "feedback_type": feedback_type,
            "old_confidence": round(old_confidence, 3),
            "new_confidence": round(new_confidence, 3),
            "confidence_change": round(new_confidence - old_confidence, 3),
            "old_competence": old_competence,
            "new_competence": new_competence,
            "learning_rate": round(performance.learning_rate, 4),
        }

    async def calculate_learning_insights(
        self,
        supervisor_id: str,
        time_range_days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate comprehensive learning insights for a supervisor.

        Analyzes:
        - Recent performance trend
        - Strengths and weaknesses
        - Improvement recommendations
        - Learning velocity
        """
        performance = self.db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == supervisor_id
        ).first()

        if not performance:
            return self._empty_insights()

        cutoff = datetime.now() - timedelta(days=time_range_days)

        # Get recent ratings
        recent_ratings = self.db.query(SupervisorRating).filter(
            SupervisorRating.supervisor_id == supervisor_id,
            SupervisorRating.created_at >= cutoff
        ).all()

        # Get recent intervention outcomes
        recent_outcomes = self.db.query(InterventionOutcome).filter(
            InterventionOutcome.supervisor_id == supervisor_id,
            InterventionOutcome.assessed_at >= cutoff
        ).all()

        # Calculate insights
        insights = {
            "supervisor_id": supervisor_id,
            "time_range_days": time_range_days,
            "current_state": {
                "confidence_score": round(performance.confidence_score, 3),
                "competence_level": performance.competence_level,
                "performance_trend": performance.performance_trend,
                "learning_rate": round(performance.learning_rate, 4),
            },
            "strengths": await self._identify_strengths(performance, recent_ratings, recent_outcomes),
            "weaknesses": await self._identify_weaknesses(performance, recent_ratings, recent_outcomes),
            "recommendations": await self._generate_recommendations(performance, recent_ratings, recent_outcomes),
            "learning_velocity": await self._calculate_learning_velocity(performance, time_range_days),
            "recent_feedback_summary": {
                "total_ratings": len(recent_ratings),
                "average_rating": round(sum(r.rating for r in recent_ratings) / len(recent_ratings), 2) if recent_ratings else None,
                "intervention_success_rate": round(
                    sum(1 for o in recent_outcomes if o.outcome == "success") / len(recent_outcomes), 3
                ) if recent_outcomes else None,
            }
        }

        return insights

    async def get_top_performers(
        self,
        metric: str = "confidence_score",
        limit: int = 10,
        competence_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get top-performing supervisors for recognition and learning.

        Args:
            metric: "confidence_score", "average_rating", "success_rate", "total_sessions"
            limit: Max results
            competence_level: Filter by level (optional)

        Returns:
            Ranked list of top performers
        """
        query = self.db.query(SupervisorPerformance)

        if competence_level:
            query = query.filter(SupervisorPerformance.competence_level == competence_level)

        performances = query.all()

        # Sort by metric
        if metric == "confidence_score":
            sorted_perfs = sorted(performances, key=lambda p: p.confidence_score, reverse=True)
        elif metric == "average_rating":
            sorted_perfs = sorted(performances, key=lambda p: p.average_rating or 0, reverse=True)
        elif metric == "total_sessions":
            sorted_perfs = sorted(performances, key=lambda p: p.total_sessions_supervised, reverse=True)
        else:
            sorted_perfs = performances

        return [{
            "supervisor_id": p.supervisor_id,
            "competence_level": p.competence_level,
            "confidence_score": round(p.confidence_score, 3),
            "average_rating": round(p.average_rating, 2) if p.average_rating else None,
            "total_sessions": p.total_sessions_supervised,
            "total_interventions": p.total_interventions,
            "performance_trend": p.performance_trend,
        } for p in sorted_perfs[:limit]]

    async def update_competence_level(
        self,
        supervisor_id: str
    ) -> Dict[str, Any]:
        """
        Re-evaluate and update supervisor competence level.

        Competence levels based on:
        - Confidence score
        - Total sessions supervised
        - Intervention success rate
        """
        performance = await self._get_or_create_performance(supervisor_id)

        old_level = performance.competence_level

        # Calculate competence criteria
        confidence = performance.confidence_score
        sessions = performance.total_sessions_supervised

        # Get intervention success rate
        successful = performance.successful_interventions or 0
        failed = performance.failed_interventions or 0
        total_interventions = successful + failed
        success_rate = successful / total_interventions if total_interventions > 0 else 0.5

        # Determine new level
        new_level = old_level  # Default: no change

        if confidence >= 0.85 and sessions >= 100 and success_rate >= 0.90:
            new_level = "expert"
        elif confidence >= 0.70 and sessions >= 50 and success_rate >= 0.80:
            new_level = "advanced"
        elif confidence >= 0.50 and sessions >= 20 and success_rate >= 0.70:
            new_level = "intermediate"
        elif confidence < 0.40 or sessions < 10:
            new_level = "novice"

        performance.competence_level = new_level
        performance.last_updated = datetime.now()

        self.db.commit()

        level_changed = old_level != new_level

        if level_changed:
            logger.info(
                f"Competence level changed for {supervisor_id}: "
                f"{old_level} -> {new_level}"
            )

        return {
            "supervisor_id": supervisor_id,
            "old_level": old_level,
            "new_level": new_level,
            "level_changed": level_changed,
            "criteria": {
                "confidence_score": round(confidence, 3),
                "total_sessions": sessions,
                "intervention_success_rate": round(success_rate, 3),
            }
        }

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _get_or_create_performance(self, supervisor_id: str) -> SupervisorPerformance:
        """Get or create supervisor performance record."""
        performance = self.db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == supervisor_id
        ).first()

        if not performance:
            performance = SupervisorPerformance(
                supervisor_id=supervisor_id,
                confidence_score=0.5,
                competence_level="novice",
            )
            self.db.add(performance)
            self.db.commit()

        return performance

    async def _process_rating(self, performance: SupervisorPerformance, feedback_data: Dict[str, Any]):
        """Process supervisor rating feedback."""
        rating = feedback_data.get("rating", 3)

        # Apply confidence adjustment
        adjustment = self.RATING_BOOST.get(rating, 0.0)

        # Smooth adjustment (exponential moving average)
        alpha = 0.2  # Learning rate for ratings
        performance.confidence_score = max(
            0.1,
            min(0.95, performance.confidence_score + alpha * adjustment)
        )

        # Update total ratings count
        performance.total_ratings = (performance.total_ratings or 0) + 1

    async def _process_vote(self, performance: SupervisorPerformance, feedback_data: Dict[str, Any]):
        """Process thumbs up/down vote feedback."""
        vote_type = feedback_data.get("vote_type", "up")

        # Small adjustment for votes
        if vote_type == "up":
            adjustment = 0.01
        else:  # down vote
            adjustment = -0.02

        # Apply smooth adjustment
        alpha = 0.1  # Lower learning rate for votes
        performance.confidence_score = max(
            0.1,
            min(0.95, performance.confidence_score + alpha * adjustment)
        )

    async def _process_intervention_outcome(self, performance: SupervisorPerformance, feedback_data: Dict[str, Any]):
        """Process intervention outcome feedback."""
        outcome = feedback_data.get("outcome", "partial")
        was_effective = feedback_data.get("was_effective", True)

        # Adjust based on outcome
        if outcome == "success" and was_effective:
            adjustment = 0.03
        elif outcome == "failure" or not was_effective:
            adjustment = -0.05
        else:  # partial
            adjustment = 0.0

        # Apply adjustment
        alpha = 0.15  # Higher learning rate for outcomes
        performance.confidence_score = max(
            0.1,
            min(0.95, performance.confidence_score + alpha * adjustment)
        )

        # Update intervention counts
        performance.total_interventions = (performance.total_interventions or 0) + 1

        if was_effective:
            performance.successful_interventions = (performance.successful_interventions or 0) + 1
        else:
            performance.failed_interventions = (performance.failed_interventions or 0) + 1

    async def _update_learning_metrics(self, performance: SupervisorPerformance):
        """Update learning rate and performance trend."""
        supervisor_id = performance.supervisor_id

        # Get recent ratings for trend calculation
        cutoff = datetime.now() - timedelta(days=30)
        recent_ratings = self.db.query(SupervisorRating).filter(
            SupervisorRating.supervisor_id == supervisor_id,
            SupervisorRating.created_at >= cutoff
        ).order_by(SupervisorRating.created_at.desc()).limit(20).all()

        if len(recent_ratings) >= 10:
            # Calculate trend (compare first half to second half)
            mid_point = len(recent_ratings) // 2
            first_half = recent_ratings[mid_point:]
            second_half = recent_ratings[:mid_point]

            avg_first = sum(r.rating for r in first_half) / len(first_half)
            avg_second = sum(r.rating for r in second_half) / len(second_half)

            difference = avg_second - avg_first

            # Update trend and learning rate
            if difference > 0.5:
                performance.performance_trend = "improving"
                performance.learning_rate = min(difference / 2, 0.1)
            elif difference < -0.5:
                performance.performance_trend = "declining"
                performance.learning_rate = max(difference / 2, -0.1)
            else:
                performance.performance_trend = "stable"
                performance.learning_rate = 0.0
        else:
            performance.performance_trend = "stable"
            performance.learning_rate = 0.0

        performance.last_updated = datetime.now()

    async def _identify_strengths(
        self,
        performance: SupervisorPerformance,
        ratings: List[SupervisorRating],
        outcomes: List[InterventionOutcome]
    ) -> List[str]:
        """Identify supervisor strengths."""
        strengths = []

        # High confidence
        if performance.confidence_score >= 0.8:
            strengths.append("High overall confidence")

        # High ratings
        if ratings:
            avg_rating = sum(r.rating for r in ratings) / len(ratings)
            if avg_rating >= 4.5:
                strengths.append("Exceptional supervisor ratings")
            elif avg_rating >= 4.0:
                strengths.append("Strong supervisor ratings")

        # Successful interventions
        if outcomes:
            success_rate = sum(1 for o in outcomes if o.outcome == "success") / len(outcomes)
            if success_rate >= 0.9:
                strengths.append("Excellent intervention success rate")
            elif success_rate >= 0.8:
                strengths.append("Good intervention success rate")

        # High volume
        if performance.total_sessions_supervised >= 100:
            strengths.append("Extensive supervision experience")

        # Positive trend
        if performance.performance_trend == "improving":
            strengths.append("Consistently improving performance")

        return strengths if strengths else ["Developing core skills"]

    async def _identify_weaknesses(
        self,
        performance: SupervisorPerformance,
        ratings: List[SupervisorRating],
        outcomes: List[InterventionOutcome]
    ) -> List[str]:
        """Identify areas for improvement."""
        weaknesses = []

        # Low confidence
        if performance.confidence_score < 0.5:
            weaknesses.append("Low confidence score needs improvement")

        # Low ratings
        if ratings:
            avg_rating = sum(r.rating for r in ratings) / len(ratings)
            if avg_rating < 3.0:
                weaknesses.append("Below-average supervisor ratings")

        # Poor intervention success
        if outcomes:
            success_rate = sum(1 for o in outcomes if o.outcome == "success") / len(outcomes)
            if success_rate < 0.7:
                weaknesses.append("Intervention success rate needs improvement")

        # Declining trend
        if performance.performance_trend == "declining":
            weaknesses.append("Declining performance trend")

        # Low volume
        if performance.total_sessions_supervised < 20:
            weaknesses.append("Limited supervision experience")

        return weaknesses if weaknesses else ["No significant weaknesses identified"]

    async def _generate_recommendations(
        self,
        performance: SupervisorPerformance,
        ratings: List[SupervisorRating],
        outcomes: List[InterventionOutcome]
    ) -> List[str]:
        """Generate personalized improvement recommendations."""
        recommendations = []

        # Based on competence level
        if performance.competence_level == "novice":
            recommendations.append(
                "Focus on completing training modules and building foundational supervision skills"
            )
        elif performance.competence_level == "intermediate":
            recommendations.append(
                "Continue practicing supervision and study successful intervention patterns"
            )
        elif performance.competence_level == "advanced":
            recommendations.append(
                "Consider mentoring novice supervisors and documenting best practices"
            )

        # Based on intervention success
        if outcomes:
            success_rate = sum(1 for o in outcomes if o.outcome == "success") / len(outcomes)
            if success_rate < 0.7:
                recommendations.append(
                    "Review intervention techniques - consider waiting longer before intervening"
                )
            elif success_rate > 0.9:
                recommendations.append(
                    "Excellent success rate - document your approach for knowledge sharing"
                )

        # Based on ratings
        if ratings:
            low_ratings = [r for r in ratings if r.rating <= 2]
            if len(low_ratings) > len(ratings) * 0.2:
                recommendations.append(
                    "Analyze low-rated sessions to identify patterns and improvement areas"
                )

        # Based on trend
        if performance.performance_trend == "declining":
            recommendations.append(
                "Performance declining - review recent sessions and seek feedback from experienced supervisors"
            )

        return recommendations if recommendations else ["Continue current approach"]

    async def _calculate_learning_velocity(
        self,
        performance: SupervisorPerformance,
        time_range_days: int
    ) -> Dict[str, Any]:
        """Calculate how quickly supervisor is learning."""
        return {
            "learning_rate": round(performance.learning_rate, 4),
            "performance_trend": performance.performance_trend,
            "confidence_velocity": round(
                performance.learning_rate / time_range_days * 30, 4
            ) if performance.learning_rate else 0.0,  # Normalized to 30 days
            "estimated_time_to_next_level": self._estimate_time_to_next_level(performance),
        }

    def _estimate_time_to_next_level(self, performance: SupervisorPerformance) -> Optional[str]:
        """Estimate time to reach next competence level."""
        current_level = performance.competence_level
        confidence = performance.confidence_score
        learning_rate = performance.learning_rate

        if learning_rate <= 0 or current_level == "expert":
            return None

        # Estimate based on confidence gap and learning rate
        level_thresholds = {
            "novice": 0.50,      # Need to reach intermediate
            "intermediate": 0.70,  # Need to reach advanced
            "advanced": 0.85,      # Need to reach expert
        }

        threshold = level_thresholds.get(current_level, 0.85)
        gap = threshold - confidence

        if gap <= 0:
            return "Ready for promotion"

        # Estimate days (assuming constant learning rate)
        estimated_days = gap / (learning_rate * 30) if learning_rate > 0 else None

        if estimated_days:
            if estimated_days < 30:
                return f"~{int(estimated_days)} days"
            elif estimated_days < 90:
                return f"~{int(estimated_days / 30)} months"
            else:
                return f"~{int(estimated_days / 30)}+ months"

        return "Unable to estimate"

    def _empty_insights(self) -> Dict[str, Any]:
        """Return empty insights structure."""
        return {
            "current_state": {
                "confidence_score": 0.5,
                "competence_level": "novice",
                "performance_trend": "stable",
                "learning_rate": 0.0,
            },
            "strengths": [],
            "weaknesses": [],
            "recommendations": ["Start supervising sessions to establish baseline"],
            "learning_velocity": {
                "learning_rate": 0.0,
                "performance_trend": "stable",
                "confidence_velocity": 0.0,
                "estimated_time_to_next_level": None,
            },
            "recent_feedback_summary": {
                "total_ratings": 0,
                "average_rating": None,
                "intervention_success_rate": None,
            }
        }

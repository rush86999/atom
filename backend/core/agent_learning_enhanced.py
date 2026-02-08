"""
Enhanced Agent Learning with Feedback

Integrates user feedback into agent confidence scoring and learning.
Provides feedback-weighted confidence adjustments and learning signals.

Usage:
    from core.agent_learning_enhanced import AgentLearningEnhanced

    learning = AgentLearningEnhanced(db)

    # Adjust confidence based on feedback
    new_confidence = learning.adjust_confidence_with_feedback(
        agent_id="agent-1",
        feedback=feedback_obj
    )

    # Get learning signals from feedback
    signals = learning.get_learning_signals("agent-1", days=30)
"""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.agent_world_model import AgentExperience, WorldModelService
from core.models import AgentExecution, AgentFeedback, AgentRegistry

logger = logging.getLogger(__name__)


class AgentLearningEnhanced:
    """
    Enhanced learning service with feedback integration.

    Incorporates user feedback (thumbs up/down, ratings, corrections)
    into agent confidence scoring and world model learning.
    """

    def __init__(self, db: Session):
        """
        Initialize enhanced learning service.

        Args:
            db: Database session
        """
        self.db = db
        self.world_model = WorldModelService()

    def adjust_confidence_with_feedback(
        self,
        agent_id: str,
        feedback: AgentFeedback,
        current_confidence: float
    ) -> float:
        """
        Adjust agent confidence based on user feedback.

        Feedback weights:
        - Thumbs up: +0.05
        - Thumbs down: -0.05
        - 5-star rating: +0.10
        - 4-star rating: +0.05
        - 3-star rating: 0.00
        - 2-star rating: -0.05
        - 1-star rating: -0.10
        - Correction: -0.03 (indicates mistake)

        Args:
            agent_id: ID of the agent
            feedback: Feedback object
            current_confidence: Current confidence score

        Returns:
            Adjusted confidence score (0.0 to 1.0)
        """
        adjustment = 0.0

        # Thumbs up/down
        if feedback.thumbs_up_down is True:
            adjustment += 0.05
        elif feedback.thumbs_up_down is False:
            adjustment -= 0.05

        # Star rating
        if feedback.rating is not None:
            rating_weights = {
                1: -0.10,
                2: -0.05,
                3: 0.00,
                4: 0.05,
                5: 0.10
            }
            adjustment += rating_weights.get(feedback.rating, 0.0)

        # Correction feedback
        if feedback.feedback_type == "correction":
            adjustment -= 0.03

        # Apply adjustment and clamp to [0.0, 1.0]
        new_confidence = max(0.0, min(1.0, current_confidence + adjustment))

        logger.info(
            f"Adjusted confidence for agent {agent_id}: "
            f"{current_confidence:.3f} -> {new_confidence:.3f} "
            f"(adjustment: {adjustment:+.3f})"
        )

        return new_confidence

    def get_learning_signals(
        self,
        agent_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get learning signals from recent feedback.

        Analyzes feedback patterns to provide insights for agent improvement.

        Args:
            agent_id: ID of the agent
            days: Number of days to analyze

        Returns:
            Dictionary with learning signals and insights
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Get recent feedback
        feedback = self.db.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent_id,
            AgentFeedback.created_at >= cutoff_date
        ).all()

        if not feedback:
            return {
                "agent_id": agent_id,
                "total_feedback": 0,
                "learning_signals": [],
                "improvement_suggestions": []
            }

        # Analyze patterns
        total = len(feedback)

        # Positive vs negative
        positive = sum(
            1 for f in feedback
            if f.thumbs_up_down is True or (f.rating is not None and f.rating >= 4)
        )

        negative = sum(
            1 for f in feedback
            if f.thumbs_up_down is False or (f.rating is not None and f.rating <= 2)
        )

        positive_ratio = positive / total if total > 0 else 0

        # Correction analysis
        corrections = [f for f in feedback if f.feedback_type == "correction"]

        # Generate learning signals
        signals = []

        if positive_ratio >= 0.8:
            signals.append({
                "type": "strength",
                "message": "Agent is performing well with high positive feedback",
                "confidence_impact": "positive"
            })
        elif positive_ratio <= 0.4:
            signals.append({
                "type": "weakness",
                "message": "Agent is struggling with low positive feedback",
                "confidence_impact": "negative"
            })

        if len(corrections) >= 5:
            signals.append({
                "type": "pattern",
                "message": f"Agent received {len(corrections)} corrections - may need retraining",
                "confidence_impact": "negative",
                "correction_count": len(corrections)
            })

        # Rating analysis
        ratings = [f.rating for f in feedback if f.rating is not None]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            if avg_rating >= 4.5:
                signals.append({
                    "type": "strength",
                    "message": f"Excellent average rating: {avg_rating:.1f}/5.0",
                    "confidence_impact": "positive"
                })
            elif avg_rating <= 2.5:
                signals.append({
                    "type": "weakness",
                    "message": f"Poor average rating: {avg_rating:.1f}/5.0",
                    "confidence_impact": "negative"
                })

        # Improvement suggestions
        suggestions = []

        if len(corrections) > 0:
            suggestions.append({
                "type": "training",
                "message": "Review common correction patterns to identify knowledge gaps",
                "priority": "high"
            })

        if positive_ratio < 0.6:
            suggestions.append({
                "type": "supervision",
                "message": "Increase human supervision until performance improves",
                "priority": "medium"
            })

        return {
            "agent_id": agent_id,
            "total_feedback": total,
            "positive_ratio": positive_ratio,
            "correction_count": len(corrections),
            "learning_signals": signals,
            "improvement_suggestions": suggestions
        }

    async def record_feedback_in_world_model(
        self,
        feedback: AgentFeedback
    ) -> bool:
        """
        Record feedback as a learning experience in the world model.

        This enables agents to learn from past feedback and avoid repeating mistakes.

        Args:
            feedback: Feedback object to record

        Returns:
            True if successfully recorded, False otherwise
        """
        try:
            # Get execution context if available
            execution = None
            if feedback.agent_execution_id:
                execution = self.db.query(AgentExecution).filter(
                    AgentExecution.id == feedback.agent_execution_id
                ).first()

            # Determine outcome based on feedback
            if feedback.thumbs_up_down is True or (feedback.rating and feedback.rating >= 4):
                outcome = "Success"
            elif feedback.thumbs_up_down is False or (feedback.rating and feedback.rating <= 2):
                outcome = "Failure"
            else:
                outcome = "Mixed"

            # Calculate feedback score (-1.0 to 1.0)
            feedback_score = 0.0

            if feedback.thumbs_up_down is not None:
                feedback_score += 0.5 if feedback.thumbs_up_down else -0.5

            if feedback.rating is not None:
                # Map 1-5 to -1.0 to 1.0
                feedback_score += (feedback.rating - 3) / 2.0

            # Clamp to [-1.0, 1.0]
            feedback_score = max(-1.0, min(1.0, feedback_score))

            # Create experience
            experience = AgentExperience(
                id=str(uuid.uuid4()),  # Will need to import uuid
                agent_id=feedback.agent_id,
                task_type=feedback.feedback_type or "general",
                input_summary=feedback.input_context or "User feedback",
                outcome=outcome,
                learnings=feedback.user_correction or feedback.ai_reasoning or "",
                confidence_score=0.5,
                feedback_score=feedback_score,
                artifacts=[feedback.agent_execution_id] if feedback.agent_execution_id else [],
                agent_role="Agent",  # Could be enhanced
                specialty=None,
                timestamp=datetime.now()
            )

            # Record in world model
            success = await self.world_model.record_experience(experience)

            if success:
                logger.info(
                    f"Recorded feedback in world model: agent={feedback.agent_id}, "
                    f"feedback_score={feedback_score:.2f}"
                )

            return success

        except Exception as e:
            logger.error(f"Failed to record feedback in world model: {e}")
            return False

    def batch_update_confidence_from_feedback(
        self,
        agent_id: str,
        days: int = 30
    ) -> Optional[float]:
        """
        Batch update agent confidence based on recent feedback.

        Aggregates all feedback from the last N days and adjusts confidence.

        Args:
            agent_id: ID of the agent
            days: Number of days to analyze

        Returns:
            New confidence score, or None if agent not found
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return None

        cutoff_date = datetime.now() - timedelta(days=days)

        # Get recent feedback
        feedback = self.db.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent_id,
            AgentFeedback.created_at >= cutoff_date
        ).all()

        if not feedback:
            return agent.confidence_score

        # Calculate aggregate adjustment
        total_adjustment = 0.0

        for f in feedback:
            # Use individual feedback adjustments
            # Weight by recency (more recent = higher weight)
            days_old = (datetime.now() - f.created_at).days
            recency_weight = max(0.1, 1.0 - (days_old / days))  # Decay to 0.1

            adjustment = 0.0

            if f.thumbs_up_down is True:
                adjustment += 0.05
            elif f.thumbs_up_down is False:
                adjustment -= 0.05

            if f.rating is not None:
                rating_weights = {1: -0.10, 2: -0.05, 3: 0.00, 4: 0.05, 5: 0.10}
                adjustment += rating_weights.get(f.rating, 0.0)

            if f.feedback_type == "correction":
                adjustment -= 0.03

            total_adjustment += adjustment * recency_weight

        # Apply adjustment
        new_confidence = max(0.0, min(1.0, agent.confidence_score + total_adjustment))

        logger.info(
            f"Batch confidence update for agent {agent_id}: "
            f"{agent.confidence_score:.3f} -> {new_confidence:.3f} "
            f"(total adjustment: {total_adjustment:+.3f} from {len(feedback)} feedback)"
        )

        return new_confidence

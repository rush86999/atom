"""
Continuous Learning Service for Agent Adaptation

Enables agents to learn from experience and adapt over time:
- Online learning (incremental updates)
- RLHF from user feedback
- Adaptive parameter tuning
- Per-user preference learning

Multi-tenant: Each tenant's learning data is isolated.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from core.models import (
    AgentLearning,
    AgentFeedback,
    AgentRegistry
)

logger = logging.getLogger(__name__)


class ContinuousLearningService:
    """
    Service for continuous agent learning and adaptation.

    Implements online learning, RLHF, and personalization
    to improve agent performance over time.
    """

    def __init__(self, db: Session):
        self.db = db

    def record_feedback(
        self,
        tenant_id: str,
        agent_id: str,
        execution_id: str,
        user_id: str,
        feedback_type: str,  # "positive", "negative", "correction", "rating"
        rating: Optional[int] = None,  # 1-5 scale
        comments: Optional[str] = None,
        corrected_output: Optional[str] = None
    ) -> Optional[str]:
        """
        Record user feedback for RLHF (Reinforcement Learning from Human Feedback).
        """
        try:
            feedback = AgentFeedback(
                tenant_id=tenant_id,
                agent_id=agent_id,
                agent_execution_id=execution_id,
                user_id=user_id,
                feedback_type=feedback_type,
                rating=rating,
                ai_reasoning=comments,  # Using ai_reasoning as a generic comment field for now
                user_correction=corrected_output or "",
                created_at=datetime.now(timezone.utc)
            )

            self.db.add(feedback)
            self.db.commit()
            self.db.refresh(feedback)

            # Trigger learning update
            self.update_from_feedback(feedback)

            logger.info(f"Recorded feedback for execution {execution_id}")
            return feedback.id

        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
            self.db.rollback()
            return None

    def update_from_feedback(self, feedback: AgentFeedback):
        """
        Update agent learning parameters from feedback.
        Implements online learning by adjusting parameters based on feedback.
        """
        try:
            # Get existing learning record
            learning = self.db.query(AgentLearning).filter(
                and_(
                    AgentLearning.agent_id == feedback.agent_id,
                    AgentLearning.tenant_id == feedback.tenant_id
                )
            ).first()

            if not learning:
                # Create initial learning record
                learning = AgentLearning(
                    tenant_id=feedback.tenant_id,
                    agent_id=feedback.agent_id,
                    total_feedback=1,
                    positive_feedback=1 if feedback.feedback_type in ["positive", "approval"] else 0,
                    negative_feedback=1 if feedback.feedback_type in ["negative", "rejection", "correction"] else 0,
                    avg_rating=float(feedback.rating) if feedback.rating else None,
                    learning_rate=0.01,  # Initial learning rate
                    parameters_json={
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "frequency_penalty": 0.0,
                        "presence_penalty": 0.0
                    },
                    last_updated_at=datetime.now(timezone.utc)
                )
                self.db.add(learning)
                # Flush to ensure total_feedback etc are available for _adjust_parameters
                self.db.flush()
            else:
                # Update existing learning record
                learning.total_feedback += 1

                if feedback.feedback_type in ["positive", "approval"]:
                    learning.positive_feedback += 1
                elif feedback.feedback_type in ["negative", "rejection", "correction"]:
                    learning.negative_feedback += 1

                # Update average rating
                if feedback.rating:
                    if learning.avg_rating:
                        # Incremental average update
                        n = learning.total_feedback
                        learning.avg_rating = (
                            (learning.avg_rating * (n - 1) + feedback.rating) / n
                        )
                    else:
                        learning.avg_rating = float(feedback.rating)

            # Recalculate success rate before adjustment
            if learning.total_feedback > 0:
                learning.success_rate = (learning.total_feedback - learning.negative_feedback) / learning.total_feedback

            # Adjust parameters based on feedback
            learning.parameters_json = self._adjust_parameters(
                learning,
                feedback
            )

            learning.last_updated_at = datetime.now(timezone.utc)

            self.db.commit()
            logger.info(f"Updated learning parameters for agent {feedback.agent_id}")

        except Exception as e:
            logger.error(f"Failed to update learning from feedback: {e}")
            self.db.rollback()

    def _adjust_parameters(
        self,
        learning: AgentLearning,
        feedback: AgentFeedback
    ) -> Dict[str, float]:
        """
        Adjust agent parameters based on feedback (online learning).
        """
        params = (learning.parameters_json or {
            "temperature": 0.7,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }).copy()

        # Learning rate (decreases over time as agent converges)
        # Fix: use learning.total_feedback instead of feedback.agent_id.total_feedback
        lr = learning.learning_rate or 0.01
        actual_lr = lr / max(1, (learning.total_feedback / 10.0))

        # Adjust based on feedback type
        if feedback.feedback_type in ["positive", "approval"]:
            # Reinforce current behavior
            # Slightly decrease temperature for more consistency
            params["temperature"] = max(0.1, params.get("temperature", 0.7) - actual_lr * 0.1)

        elif feedback.feedback_type in ["negative", "rejection", "correction"]:
            # Encourage exploration or change
            # Increase temperature for more variety
            params["temperature"] = min(1.0, params.get("temperature", 0.7) + actual_lr * 0.2)

            # Adjust penalties for novelty
            params["presence_penalty"] = min(2.0, params.get("presence_penalty", 0.0) + actual_lr * 0.1)

        # Clamp values to valid ranges
        params["temperature"] = max(0.0, min(1.5, params.get("temperature", 0.7)))
        params["top_p"] = max(0.0, min(1.0, params.get("top_p", 0.9)))
        params["frequency_penalty"] = max(-2.0, min(2.0, params.get("frequency_penalty", 0.0)))
        params["presence_penalty"] = max(-2.0, min(2.0, params.get("presence_penalty", 0.0)))

        return params

    def get_learning_progress(
        self,
        tenant_id: str,
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Get learning progress and adaptation metrics for an agent.
        """
        try:
            learning = self.db.query(AgentLearning).filter(
                and_(
                    AgentLearning.agent_id == agent_id,
                    AgentLearning.tenant_id == tenant_id
                )
            ).first()

            if not learning:
                return {
                    "agent_id": agent_id,
                    "status": "not_started",
                    "total_feedback": 0,
                    "positive_rate": 0,
                    "avg_rating": None,
                    "parameters": {},
                    "improvement_trend": "unknown"
                }

            # Calculate positive feedback rate
            positive_rate = (
                learning.positive_feedback / learning.total_feedback
                if learning.total_feedback > 0
                else 0
            )

            # Get recent feedback trend (last 7 days)
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            recent_feedback = self.db.query(AgentFeedback).filter(
                and_(
                    AgentFeedback.agent_id == agent_id,
                    AgentFeedback.tenant_id == tenant_id,
                    AgentFeedback.created_at >= cutoff
                )
            ).all()

            recent_positive = sum(1 for f in recent_feedback if f.feedback_type in ["positive", "approval"])
            recent_rate = recent_positive / len(recent_feedback) if recent_feedback else 0

            # Determine trend
            if len(recent_feedback) >= 3:
                if recent_rate > positive_rate + 0.05:
                    trend = "improving"
                elif recent_rate < positive_rate - 0.05:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"

            return {
                "agent_id": agent_id,
                "status": "learning",
                "total_feedback": learning.total_feedback,
                "positive_feedback": learning.positive_feedback,
                "negative_feedback": learning.negative_feedback,
                "positive_rate": round(positive_rate, 2),
                "recent_positive_rate": round(recent_rate, 2) if recent_feedback else None,
                "avg_rating": round(learning.avg_rating, 2) if learning.avg_rating else None,
                "parameters": learning.parameters_json,
                "learning_rate": learning.learning_rate,
                "last_updated": learning.last_updated_at.isoformat() if learning.last_updated_at else None,
                "improvement_trend": trend
            }

        except Exception as e:
            logger.error(f"Failed to get learning progress: {e}")
            return {
                "agent_id": agent_id,
                "status": "error",
                "error": str(e)
            }

    def get_personalized_parameters(
        self,
        tenant_id: str,
        agent_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get personalized parameters for agent based on user preferences.
        """
        try:
            # Get agent learning
            learning = self.db.query(AgentLearning).filter(
                and_(
                    AgentLearning.agent_id == agent_id,
                    AgentLearning.tenant_id == tenant_id
                )
            ).first()

            base_params = (learning.parameters_json if learning else {
                "temperature": 0.7,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0
            }).copy()

            # If user-specific personalization requested
            if user_id:
                # Get user's feedback history with this agent
                user_feedback = self.db.query(AgentFeedback).filter(
                    and_(
                        AgentFeedback.agent_id == agent_id,
                        AgentFeedback.tenant_id == tenant_id,
                        AgentFeedback.user_id == user_id
                    )
                ).all()

                if user_feedback:
                    # Calculate user-specific preferences
                    user_positive_rate = sum(
                        1 for f in user_feedback if f.feedback_type in ["positive", "approval"]
                    ) / len(user_feedback)

                    # Adjust based on user preferences
                    if user_positive_rate > 0.8:
                        # User prefers current behavior - lower temperature for consistency
                        base_params["temperature"] = max(0.2, base_params.get("temperature", 0.7) - 0.1)
                    elif user_positive_rate < 0.4:
                        # User wants more variety - higher temperature
                        base_params["temperature"] = min(1.2, base_params.get("temperature", 0.7) + 0.1)

            return base_params

        except Exception as e:
            logger.error(f"Failed to get personalized parameters: {e}")
            return {
                "temperature": 0.7,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0
            }

    def generate_adaptations(
        self,
        tenant_id: str,
        agent_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generate recommended adaptations based on learning data.
        """
        try:
            progress = self.get_learning_progress(tenant_id, agent_id)
            adaptations = []

            # Low positive rate → recommend exploration
            if progress.get("positive_rate", 0) < 0.6 and progress.get("total_feedback", 0) > 5:
                adaptations.append({
                    "type": "parameter_adjustment",
                    "priority": "high",
                    "recommendation": "Increase temperature for more creative exploration",
                    "reason": f"Positive rate {progress.get('positive_rate', 0):.0%} is below target",
                    "action": "temperature_increase"
                })

            # Declining trend → recommend retraining/review
            if progress.get("improvement_trend") == "declining":
                adaptations.append({
                    "type": "performance_review",
                    "priority": "critical",
                    "recommendation": "Review recent failure patterns and corrections",
                    "reason": "Agent performance trend is declining",
                    "action": "failure_analysis"
                })

            # High success rate → recommend maturity advancement
            if progress.get("positive_rate", 0) > 0.9 and progress.get("total_feedback", 0) > 50:
                adaptations.append({
                    "type": "maturity_advancement",
                    "priority": "medium",
                    "recommendation": "Consider advancing agent to next maturity level",
                    "reason": f"Sustained high performance ({progress.get('positive_rate', 0):.0%})",
                    "action": "promote_agent"
                })

            return adaptations[:limit]

        except Exception as e:
            logger.error(f"Failed to generate adaptations: {e}")
            return []

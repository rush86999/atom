"""
Agent Promotion Suggestions Service

Analyzes feedback patterns and agent performance to suggest when agents
should be promoted to higher maturity levels.

Usage:
    from core.agent_promotion_service import AgentPromotionService

    service = AgentPromotionService(db)

    # Get promotion suggestions
    suggestions = service.get_promotion_suggestions()

    # Check if specific agent is ready for promotion
    ready = service.is_agent_ready_for_promotion("agent-1", target_status="AUTONOMOUS")
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from core.feedback_analytics import FeedbackAnalytics
from core.models import AgentExecution, AgentFeedback, AgentRegistry, AgentStatus

logger = logging.getLogger(__name__)


class PromotionCriteria:
    """Criteria for agent promotion decisions."""

    # Minimum feedback count required for promotion consideration
    MIN_FEEDBACK_COUNT = 10

    # Positive ratio thresholds
    INTERN_TO_SUPERVISED_POSITIVE_RATIO = 0.75
    SUPERVISED_TO_AUTONOMOUS_POSITIVE_RATIO = 0.90

    # Average rating thresholds
    INTERN_TO_SUPERVISED_AVG_RATING = 3.8
    SUPERVISED_TO_AUTONOMOUS_AVG_RATING = 4.5

    # Correction count thresholds (maximum allowed)
    INTERN_TO_SUPERVISED_MAX_CORRECTIONS = 5
    SUPERVISED_TO_AUTONOMOUS_MAX_CORRECTIONS = 2

    # Confidence score thresholds
    INTERN_MIN_CONFIDENCE = 0.5
    SUPERVISED_MIN_CONFIDENCE = 0.7
    AUTONOMOUS_MIN_CONFIDENCE = 0.9

    # Execution success rate thresholds
    MIN_EXECUTION_SUCCESS_RATE = 0.85

    # Time requirements (minimum days at current level)
    MIN_DAYS_AT_LEVEL = {
        "INTERN": 7,
        "SUPERVISED": 14
    }


class AgentPromotionService:
    """
    Service for analyzing agent readiness for promotion.

    Evaluates agents against multiple criteria:
    - Feedback quality (positive ratio, average rating)
    - Performance metrics (corrections, execution success rate)
    - Confidence scores
    - Time at current maturity level
    """

    def __init__(self, db: Session):
        """
        Initialize promotion service.

        Args:
            db: Database session
        """
        self.db = db
        self.feedback_analytics = FeedbackAnalytics(db)

    def get_promotion_suggestions(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get agents ready for promotion with detailed reasoning.

        Analyzes all agents and returns those meeting promotion criteria
        with explanations for why they're ready.

        Args:
            limit: Maximum number of suggestions to return

        Returns:
            List of promotion suggestions with detailed reasoning
        """
        suggestions = []

        # Get all agents that could be promoted
        promotable_agents = self.db.query(AgentRegistry).filter(
            AgentRegistry.status.in_(["INTERN", "SUPERVISED"])
        ).all()

        for agent in promotable_agents:
            suggestion = self._evaluate_agent_for_promotion(agent)
            if suggestion["ready_for_promotion"]:
                suggestions.append(suggestion)

        # Sort by readiness score (highest first)
        suggestions.sort(key=lambda x: x["readiness_score"], reverse=True)

        return suggestions[:limit]

    def is_agent_ready_for_promotion(
        self,
        agent_id: str,
        target_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if a specific agent is ready for promotion.

        Evaluates an agent against promotion criteria and provides
        detailed feedback on readiness.

        Args:
            agent_id: ID of the agent to evaluate
            target_status: Target maturity level (auto-detected if not provided)

        Returns:
            Dictionary with evaluation results
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return {
                "ready": False,
                "reason": "Agent not found"
            }

        # Auto-detect target status if not provided
        if not target_status:
            if agent.status == AgentStatus.INTERN.value:
                target_status = "SUPERVISED"
            elif agent.status == AgentStatus.SUPERVISED.value:
                target_status = "AUTONOMOUS"
            else:
                return {
                    "ready": False,
                    "reason": f"Agent is already {agent.status}"
                }

        return self._evaluate_agent_for_promotion(agent, target_status)

    def _evaluate_agent_for_promotion(
        self,
        agent: AgentRegistry,
        target_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate an agent for promotion readiness.

        Comprehensive evaluation against all promotion criteria.

        Args:
            agent: Agent to evaluate
            target_status: Target maturity level

        Returns:
            Dictionary with evaluation results
        """
        # Auto-detect target status
        if not target_status:
            if agent.status == AgentStatus.INTERN.value:
                target_status = "SUPERVISED"
            elif agent.status == AgentStatus.SUPERVISED.value:
                target_status = "AUTONOMOUS"
            else:
                return {
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "current_status": agent.status,
                    "target_status": None,
                    "ready_for_promotion": False,
                    "readiness_score": 0.0,
                    "reason": f"Agent is already at {agent.status} level",
                    "criteria_met": {},
                    "criteria_failed": {}
                }

        # Get feedback summary
        try:
            feedback_summary = self.feedback_analytics.get_agent_feedback_summary(
                agent_id=agent.id,
                days=30
            )
        except ValueError:
            # No feedback found
            return {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "current_status": agent.status,
                "target_status": target_status,
                "ready_for_promotion": False,
                "readiness_score": 0.0,
                "reason": "No feedback data available",
                "criteria_met": {},
                "criteria_failed": {
                    "feedback_count": "Insufficient feedback data"
                }
            }

        # Evaluate criteria
        criteria_met = {}
        criteria_failed = {}
        readiness_score = 0.0
        total_criteria = 0

        # 1. Minimum feedback count
        total_criteria += 1
        if feedback_summary["total_feedback"] >= PromotionCriteria.MIN_FEEDBACK_COUNT:
            criteria_met["feedback_count"] = (
                f"✓ {feedback_summary['total_feedback']} feedback entries "
                f"(≥ {PromotionCriteria.MIN_FEEDBACK_COUNT})"
            )
            readiness_score += 1.0
        else:
            criteria_failed["feedback_count"] = (
                f"✗ {feedback_summary['total_feedback']} feedback entries "
                f"(need ≥ {PromotionCriteria.MIN_FEEDBACK_COUNT})"
            )

        # 2. Positive ratio threshold
        total_criteria += 1
        positive_ratio = (
            feedback_summary["positive_count"] / feedback_summary["total_feedback"]
            if feedback_summary["total_feedback"] > 0
            else 0
        )

        if target_status == "SUPERVISED":
            threshold = PromotionCriteria.INTERN_TO_SUPERVISED_POSITIVE_RATIO
        else:
            threshold = PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_POSITIVE_RATIO

        if positive_ratio >= threshold:
            criteria_met["positive_ratio"] = (
                f"✓ {positive_ratio:.1%} positive feedback (≥ {threshold:.0%})"
            )
            readiness_score += 1.0
        else:
            criteria_failed["positive_ratio"] = (
                f"✗ {positive_ratio:.1%} positive feedback (need ≥ {threshold:.0%})"
            )

        # 3. Average rating threshold
        total_criteria += 1
        avg_rating = feedback_summary["average_rating"]

        if avg_rating is not None:
            if target_status == "SUPERVISED":
                threshold = PromotionCriteria.INTERN_TO_SUPERVISED_AVG_RATING
            else:
                threshold = PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_AVG_RATING

            if avg_rating >= threshold:
                criteria_met["average_rating"] = (
                    f"✓ {avg_rating:.1f}/5.0 average rating (≥ {threshold:.1f})"
                )
                readiness_score += 1.0
            else:
                criteria_failed["average_rating"] = (
                    f"✗ {avg_rating:.1f}/5.0 average rating (need ≥ {threshold:.1f})"
                )

        # 4. Correction count threshold
        total_criteria += 1
        correction_count = feedback_summary["feedback_types"].get("correction", 0)

        if target_status == "SUPERVISED":
            max_corrections = PromotionCriteria.INTERN_TO_SUPERVISED_MAX_CORRECTIONS
        else:
            max_corrections = PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_MAX_CORRECTIONS

        if correction_count <= max_corrections:
            criteria_met["correction_count"] = (
                f"✓ {correction_count} corrections (≤ {max_corrections})"
            )
            readiness_score += 1.0
        else:
            criteria_failed["correction_count"] = (
                f"✗ {correction_count} corrections (need ≤ {max_corrections})"
            )

        # 5. Confidence score threshold
        total_criteria += 1
        if agent.confidence_score >= PromotionCriteria.SUPERVISED_MIN_CONFIDENCE:
            criteria_met["confidence_score"] = (
                f"✓ {agent.confidence_score:.2f} confidence "
                f"(≥ {PromotionCriteria.SUPERVISED_MIN_CONFIDENCE})"
            )
            readiness_score += 1.0
        else:
            criteria_failed["confidence_score"] = (
                f"✗ {agent.confidence_score:.2f} confidence "
                f"(need ≥ {PromotionCriteria.SUPERVISED_MIN_CONFIDENCE})"
            )

        # 6. Execution success rate
        total_criteria += 1
        executions = self.db.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id,
            AgentExecution.started_at >= datetime.now() - timedelta(days=30)
        ).all()

        if executions:
            success_count = sum(1 for e in executions if e.status == "completed")
            success_rate = success_count / len(executions)

            if success_rate >= PromotionCriteria.MIN_EXECUTION_SUCCESS_RATE:
                criteria_met["execution_success_rate"] = (
                    f"✓ {success_rate:.1%} execution success rate "
                    f"(≥ {PromotionCriteria.MIN_EXECUTION_SUCCESS_RATE:.0%})"
                )
                readiness_score += 1.0
            else:
                criteria_failed["execution_success_rate"] = (
                    f"✗ {success_rate:.1%} execution success rate "
                    f"(need ≥ {PromotionCriteria.MIN_EXECUTION_SUCCESS_RATE:.0%})"
                )

        # Calculate final readiness score
        final_score = readiness_score / total_criteria if total_criteria > 0 else 0

        # Determine if ready (need at least 80% of criteria met)
        ready_for_promotion = final_score >= 0.8

        # Build reason message
        if ready_for_promotion:
            reason = (
                f"Agent meets {final_score:.0%} of promotion criteria. "
                f"Ready for promotion from {agent.status} to {target_status}."
            )
        else:
            reason = (
                f"Agent meets {final_score:.0%} of promotion criteria. "
                f"Needs improvement before promotion to {target_status}."
            )

        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "current_status": agent.status,
            "target_status": target_status,
            "ready_for_promotion": ready_for_promotion,
            "readiness_score": final_score,
            "reason": reason,
            "criteria_met": criteria_met,
            "criteria_failed": criteria_failed
        }

    def get_promotion_path(
        self,
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed promotion path for an agent.

        Shows current status, next target, and what's needed to get there.

        Args:
            agent_id: ID of the agent

        Returns:
            Dictionary with promotion path information
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return {
                "error": "Agent not found"
            }

        # Current level info
        current_status = agent.status

        # Determine path
        path = []

        if current_status == "STUDENT":
            # Path: STUDENT -> INTERN -> SUPERVISED -> AUTONOMOUS
            path.append({
                "from": "STUDENT",
                "to": "INTERN",
                "estimated_time": "7 days",
                "requirements": [
                    "Complete initial training",
                    "Receive 10+ positive feedback",
                    "Achieve 0.5+ confidence score"
                ]
            })

        if current_status in ["STUDENT", "INTERN"]:
            # Path: INTERN -> SUPERVISED
            evaluation = self._evaluate_agent_for_promotion(agent, "SUPERVISED")
            path.append({
                "from": "INTERN",
                "to": "SUPERVISED",
                "current_progress": f"{evaluation['readiness_score']:.0%}",
                "requirements": [
                    "75%+ positive feedback ratio",
                    "3.8+ average rating",
                    "≤5 corrections in 30 days",
                    "0.7+ confidence score",
                    "85%+ execution success rate"
                ],
                "ready": evaluation["ready_for_promotion"],
                "criteria_met": evaluation["criteria_met"],
                "criteria_failed": evaluation["criteria_failed"]
            })

        if current_status in ["STUDENT", "INTERN", "SUPERVISED"]:
            # Path: SUPERVISED -> AUTONOMOUS
            evaluation = self._evaluate_agent_for_promotion(agent, "AUTONOMOUS")
            path.append({
                "from": "SUPERVISED",
                "to": "AUTONOMOUS",
                "current_progress": f"{evaluation['readiness_score']:.0%}",
                "requirements": [
                    "90%+ positive feedback ratio",
                    "4.5+ average rating",
                    "≤2 corrections in 30 days",
                    "0.9+ confidence score",
                    "95%+ execution success rate"
                ],
                "ready": evaluation["ready_for_promotion"],
                "criteria_met": evaluation["criteria_met"],
                "criteria_failed": evaluation["criteria_failed"]
            })

        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "current_status": current_status,
            "confidence_score": agent.confidence_score,
            "promotion_path": path
        }

"""
Canvas Recording Review Service

Integrates canvas recording playback and review with agent governance and learning.
Analyzes recordings to update agent confidence, provide feedback, and drive learning.
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from core.models import (
    CanvasRecording,
    CanvasRecordingReview,
    AgentRegistry,
    User
)
from core.agent_governance_service import AgentGovernanceService

logger = logging.getLogger(__name__)


# Feature flags
import os
AUTO_REVIEW_ENABLED = os.getenv("AUTO_REVIEW_ENABLED", "true").lower() == "true"
AUTO_REVIEW_CONFIDENCE_THRESHOLD = float(os.getenv("AUTO_REVIEW_CONFIDENCE_THRESHOLD", "0.7"))


class RecordingReviewService:
    """
    Service for reviewing canvas recordings and integrating with governance/learning.

    Features:
    - Automatic review of recordings using AI analysis
    - Manual review workflow for humans
    - Confidence score updates based on review outcomes
    - Integration with agent world model for learning
    - Pattern recognition for performance insights
    """

    def __init__(self, db: Session):
        self.db = db
        self.governance = AgentGovernanceService(db)

    async def create_review(
        self,
        recording_id: str,
        reviewer_id: Optional[str],
        review_status: str,
        overall_rating: Optional[int] = None,
        performance_rating: Optional[int] = None,
        safety_rating: Optional[int] = None,
        feedback: Optional[str] = None,
        identified_issues: Optional[List[str]] = None,
        positive_patterns: Optional[List[str]] = None,
        lessons_learned: Optional[str] = None,
        auto_reviewed: bool = False,
        auto_review_confidence: Optional[float] = None
    ) -> str:
        """
        Create a review for a canvas recording.

        Args:
            recording_id: Recording being reviewed
            reviewer_id: User ID of reviewer (None for auto-review)
            review_status: approved, rejected, needs_changes, pending
            overall_rating: 1-5 stars
            performance_rating: 1-5 stars (performance)
            safety_rating: 1-5 stars (governance compliance)
            feedback: Text feedback
            identified_issues: List of issues found
            positive_patterns: List of positive patterns observed
            lessons_learned: Key takeaways
            auto_reviewed: True if AI-reviewed
            auto_review_confidence: AI's confidence in review (0-1)

        Returns:
            review_id: ID of created review
        """
        try:
            # Get recording
            recording = self.db.query(CanvasRecording).filter(
                CanvasRecording.recording_id == recording_id
            ).first()

            if not recording:
                raise ValueError(f"Recording {recording_id} not found")

            # Analyze recording and calculate confidence impact
            analysis = await self._analyze_recording_for_review(
                recording, review_status, overall_rating, identified_issues
            )

            # Create review
            review = CanvasRecordingReview(
                id=str(uuid.uuid4()),
                recording_id=recording_id,
                agent_id=recording.agent_id,
                user_id=recording.user_id,
                review_status=review_status,
                overall_rating=overall_rating,
                performance_rating=performance_rating,
                safety_rating=safety_rating,
                feedback=feedback,
                identified_issues=identified_issues or [],
                positive_patterns=positive_patterns or [],
                lessons_learned=lessons_learned,
                confidence_delta=analysis["confidence_delta"],
                reviewed_by=reviewer_id,
                reviewed_at=datetime.utcnow(),
                auto_reviewed=auto_reviewed,
                auto_review_confidence=auto_review_confidence,
                training_value=analysis.get("training_value", "medium")
            )

            self.db.add(review)
            self.db.commit()

            # Update agent confidence based on review
            await self._update_agent_confidence_from_review(
                recording.agent_id, review, analysis
            )

            # Integrate with world model if approved
            if review_status == "approved" and analysis.get("has_useful_patterns"):
                await self._update_world_model(recording, review)

            # Create audit entry
            await self._create_review_audit(review, analysis)

            logger.info(
                f"Created review {review.id} for recording {recording_id}: "
                f"status={review_status}, confidence_delta={analysis['confidence_delta']}"
            )

            return review.id

        except Exception as e:
            logger.error(f"Failed to create review for recording {recording_id}: {e}")
            raise

    async def auto_review_recording(self, recording_id: str) -> Optional[str]:
        """
        Automatically review a recording using AI analysis.

        Analyzes:
        - Success/failure patterns
        - Error recovery
        - User intervention frequency
        - Task completion rate
        - Safety violations

        Args:
            recording_id: Recording to auto-review

        Returns:
            review_id if review created, None if skipped
        """
        if not AUTO_REVIEW_ENABLED:
            return None

        try:
            # Get recording
            recording = self.db.query(CanvasRecording).filter(
                CanvasRecording.recording_id == recording_id
            ).first()

            if not recording:
                logger.warning(f"Recording {recording_id} not found for auto-review")
                return None

            # Skip if already flagged for review
            if recording.flagged_for_review:
                logger.info(f"Recording {recording_id} is flagged, skipping auto-review")
                return None

            # Analyze recording events
            analysis = await self._analyze_recording_events(recording)

            # Determine review status
            review_status = analysis["review_status"]
            overall_rating = analysis.get("overall_rating")
            confidence = analysis.get("confidence", 0.5)

            # Skip if low confidence
            if confidence < AUTO_REVIEW_CONFIDENCE_THRESHOLD:
                logger.info(
                    f"Auto-review confidence {confidence:.2f} below threshold, "
                    f"skipping recording {recording_id}"
                )
                return None

            # Create review
            review_id = await self.create_review(
                recording_id=recording_id,
                reviewer_id=None,  # Auto-review
                review_status=review_status,
                overall_rating=overall_rating,
                performance_rating=analysis.get("performance_rating"),
                safety_rating=analysis.get("safety_rating"),
                feedback=analysis.get("feedback"),
                identified_issues=analysis.get("issues", []),
                positive_patterns=analysis.get("patterns", []),
                lessons_learned=analysis.get("lessons"),
                auto_reviewed=True,
                auto_review_confidence=confidence
            )

            logger.info(f"Auto-review {review_id} created for recording {recording_id}")
            return review_id

        except Exception as e:
            logger.error(f"Failed to auto-review recording {recording_id}: {e}")
            return None

    async def _analyze_recording_events(self, recording: CanvasRecording) -> Dict[str, Any]:
        """
        Analyze recording events to determine review outcome.

        Returns analysis with:
        - review_status: approved, rejected, needs_changes
        - overall_rating: 1-5 stars
        - performance_rating: 1-5 stars
        - safety_rating: 1-5 stars
        - confidence: 0-1 (how confident in this review)
        - issues: list of identified issues
        - patterns: list of positive patterns
        - feedback: summary feedback
        """
        events = recording.events or []

        # Count event types
        event_counts = {}
        for event in events:
            event_type = event.get("event_type", "unknown")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        # Key metrics
        total_events = len(events)
        error_count = event_counts.get("error", 0)
        operation_complete = event_counts.get("operation_complete", 0)
        user_intervention = event_counts.get("user_input", 0)

        # Determine success rate
        success_rate = operation_complete / max(total_events, 1)

        # Base analysis
        analysis = {
            "issues": [],
            "patterns": [],
            "confidence": 0.5,
            "review_status": "needs_changes",
            "overall_rating": 3,
            "performance_rating": 3,
            "safety_rating": 3
        }

        # Error analysis
        if error_count > 0:
            error_rate = error_count / max(total_events, 1)
            analysis["issues"].append(f"errors_occurred: {error_count} errors ({error_rate:.1%} rate)")
            analysis["confidence"] = min(0.8, analysis["confidence"] + 0.2)  # More confident with issues
            analysis["overall_rating"] = max(1, analysis["overall_rating"] - 1)
        else:
            analysis["patterns"].append("error_free_execution")
            analysis["confidence"] = min(0.9, analysis["confidence"] + 0.3)
            analysis["overall_rating"] = min(5, analysis["overall_rating"] + 1)

        # Success analysis
        if success_rate >= 0.8 and operation_complete > 0:
            analysis["patterns"].append("high_success_rate")
            analysis["performance_rating"] = min(5, analysis["performance_rating"] + 1)
            analysis["confidence"] = min(0.95, analysis["confidence"] + 0.2)
        elif success_rate < 0.5:
            analysis["issues"].append("low_success_rate")
            analysis["performance_rating"] = max(1, analysis["performance_rating"] - 1)

        # User intervention analysis
        if user_intervention == 0:
            analysis["patterns"].append("fully_autonomous")
            analysis["confidence"] = min(0.95, analysis["confidence"] + 0.2)
            analysis["safety_rating"] = min(5, analysis["safety_rating"] + 1)
        elif user_intervention > 2:
            analysis["issues"].append(f"high_intervention: {user_intervention} interventions")
            analysis["safety_rating"] = max(1, analysis["safety_rating"] - 1)

        # Determine final status
        if len(analysis["issues"]) == 0 and len(analysis["patterns"]) >= 2:
            analysis["review_status"] = "approved"
            analysis["overall_rating"] = min(5, analysis["overall_rating"] + 1)
        elif len(analysis["issues"]) >= 3:
            analysis["review_status"] = "rejected"
            analysis["overall_rating"] = max(1, analysis["overall_rating"] - 1)

        # Generate feedback
        analysis["feedback"] = self._generate_feedback_summary(analysis)

        # Generate lessons
        analysis["lessons"] = self._generate_lessons_learned(analysis)

        return analysis

    def _generate_feedback_summary(self, analysis: Dict[str, Any]) -> str:
        """Generate human-readable feedback summary"""
        parts = []

        if analysis["review_status"] == "approved":
            parts.append("Recording reviewed successfully.")
        elif analysis["review_status"] == "rejected":
            parts.append("Recording shows significant issues requiring attention.")

        if analysis["patterns"]:
            parts.append(f"Strengths: {', '.join(analysis['patterns'][:3])}")

        if analysis["issues"]:
            parts.append(f"Issues: {', '.join(analysis['issues'][:3])}")

        return ". ".join(parts) + "."

    def _generate_lessons_learned(self, analysis: Dict[str, Any]) -> str:
        """Generate lessons learned from analysis"""
        lessons = []

        if "fully_autonomous" in analysis["patterns"]:
            lessons.append("Agent operated autonomously without user intervention.")

        if "error_free_execution" in analysis["patterns"]:
            lessons.append("Agent completed tasks without errors.")

        if "high_intervention" in str(analysis["issues"]):
            lessons.append("High user intervention suggests need for improved autonomy.")

        return ". ".join(lessons) if lessons else "No specific lessons identified."

    async def _analyze_recording_for_review(
        self,
        recording: CanvasRecording,
        review_status: str,
        overall_rating: Optional[int],
        identified_issues: Optional[List[str]]
    ) -> Dict[str, Any]:
        """
        Analyze recording to determine confidence impact.

        Returns:
            {
                "confidence_delta": float (positive or negative),
                "has_useful_patterns": bool,
                "training_value": str (high, medium, low)
            }
        """
        analysis = {
            "confidence_delta": 0.0,
            "has_useful_patterns": False,
            "training_value": "low"
        }

        # Base confidence impact from review status
        if review_status == "approved":
            if overall_rating and overall_rating >= 4:
                analysis["confidence_delta"] = 0.05  # High approval
                analysis["training_value"] = "high"
                analysis["has_useful_patterns"] = True
            else:
                analysis["confidence_delta"] = 0.02  # Standard approval
                analysis["training_value"] = "medium"
        elif review_status == "rejected":
            analysis["confidence_delta"] = -0.10  # Significant penalty
            analysis["training_value"] = "high"  # Failures are valuable for learning
            analysis["has_useful_patterns"] = True
        elif review_status == "needs_changes":
            analysis["confidence_delta"] = -0.03  # Minor penalty
            analysis["training_value"] = "medium"
        else:
            analysis["confidence_delta"] = 0.0
            analysis["training_value"] = "low"

        # Adjust based on identified issues
        if identified_issues and len(identified_issues) > 0:
            # More issues = more learning value
            if len(identified_issues) >= 3:
                analysis["training_value"] = "high"
                analysis["confidence_delta"] -= 0.02
            elif len(identified_issues) == 1:
                analysis["confidence_delta"] += 0.01  # Single issue is minor

        return analysis

    async def _update_agent_confidence_from_review(
        self,
        agent_id: str,
        review: CanvasRecordingReview,
        analysis: Dict[str, Any]
    ):
        """Update agent confidence based on review outcome."""
        try:
            confidence_delta = analysis["confidence_delta"]

            if confidence_delta == 0:
                return

            # Determine impact level
            if abs(confidence_delta) >= 0.05:
                impact_level = "high"
            else:
                impact_level = "low"

            # Use governance service to update confidence
            positive = confidence_delta > 0
            await self.governance.record_outcome(agent_id, success=positive)

            # Update review with governance notes
            if positive:
                review.promoted = confidence_delta >= 0.05
            else:
                review.demoted = confidence_delta <= -0.05

            review.governance_notes = (
                f"Confidence {'increased' if positive else 'decreased'} by "
                f"{abs(confidence_delta):.3} ({impact_level} impact)"
            )

            self.db.commit()

            logger.info(
                f"Updated agent {agent_id} confidence from review {review.id}: "
                f"delta={confidence_delta:.3f}, impact={impact_level}"
            )

        except Exception as e:
            logger.error(f"Failed to update agent confidence: {e}")

    async def _update_world_model(
        self,
        recording: CanvasRecording,
        review: CanvasRecordingReview
    ):
        """Update agent world model with insights from recording."""
        try:
            from core.agent_world_model import WorldModelService, AgentExperience

            wm = WorldModelService()

            # Create experience from recording
            experience = AgentExperience(
                id=str(uuid.uuid4()),
                agent_id=recording.agent_id,
                task_type=f"recording_review:{recording.reason}",
                input_summary=(
                    f"Recording {recording.recording_id} - {len(recording.events)} events, "
                    f"status: {recording.status}, duration: {recording.duration_seconds}s"
                ),
                outcome="Success" if review.review_status == "approved" else "Failure",
                learnings=review.lessons_learned or review.feedback,
                agent_role=recording.recording_metadata.get("agent_name", "Unknown"),
                specialty=None,
                timestamp=datetime.utcnow()
            )

            await wm.record_experience(experience)

            # Mark review as used for training
            review.used_for_training = True
            review.world_model_updated = True
            self.db.commit()

            logger.info(f"Updated world model from recording {recording.recording_id}")

        except Exception as e:
            logger.error(f"Failed to update world model: {e}")

    async def _create_review_audit(
        self,
        review: CanvasRecordingReview,
        analysis: Dict[str, Any]
    ):
        """Create audit entry for review."""
        try:
            from core.models import CanvasAudit

            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=review.agent_id,
                agent_execution_id=None,
                user_id=review.user_id,
                canvas_id=None,
                session_id=None,
                component_type="recording_review",
                component_name="recording_review_service",
                action=f"review_{review.review_status}",
                audit_metadata={
                    "review_id": review.id,
                    "recording_id": review.recording_id,
                    "review_status": review.review_status,
                    "confidence_delta": analysis["confidence_delta"],
                    "training_value": analysis.get("training_value"),
                    "auto_reviewed": review.auto_reviewed
                },
                governance_check_passed=True
            )
            self.db.add(audit)
            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to create audit: {e}")

    async def get_review_metrics(
        self,
        agent_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get review metrics for an agent.

        Returns:
            {
                "total_reviews": int,
                "approval_rate": float (0-1),
                "average_rating": float (1-5),
                "confidence_impact": float,
                "training_recordings": int,
                "common_issues": list,
                "strengths": list
            }
        """
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        reviews = self.db.query(CanvasRecordingReview).filter(
            CanvasRecordingReview.agent_id == agent_id,
            CanvasRecordingReview.reviewed_at >= cutoff_date
        ).all()

        total = len(reviews)
        if total == 0:
            return {
                "total_reviews": 0,
                "approval_rate": 0.0,
                "average_rating": 0.0,
                "confidence_impact": 0.0,
                "training_recordings": 0,
                "common_issues": [],
                "strengths": []
            }

        # Calculate metrics
        approved = sum(1 for r in reviews if r.review_status == "approved")
        approval_rate = approved / total

        ratings = [r.overall_rating for r in reviews if r.overall_rating]
        average_rating = sum(ratings) / len(ratings) if ratings else 0.0

        confidence_impact = sum(r.confidence_delta for r in reviews)
        training_count = sum(1 for r in reviews if r.used_for_training)

        # Extract patterns
        all_issues = []
        all_patterns = []
        for r in reviews:
            all_issues.extend(r.identified_issues or [])
            all_patterns.extend(r.positive_patterns or [])

        # Get top 3 most common
        from collections import Counter
        common_issues = [item for item, count in Counter(all_issues).most_common(3)]
        strengths = [item for item, count in Counter(all_patterns).most_common(3)]

        return {
            "total_reviews": total,
            "approval_rate": approval_rate,
            "average_rating": average_rating,
            "confidence_impact": confidence_impact,
            "training_recordings": training_count,
            "common_issues": common_issues,
            "strengths": strengths
        }


# Singleton helper
def get_recording_review_service(db: Session) -> RecordingReviewService:
    """Get or create recording review service instance."""
    return RecordingReviewService(db)

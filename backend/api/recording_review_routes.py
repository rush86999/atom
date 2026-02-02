"""
Recording Review API Routes

Provides REST API endpoints for reviewing canvas recordings and integrating
with agent governance and learning systems.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.recording_review_service import RecordingReviewService, get_recording_review_service
from core.models import CanvasRecordingReview, CanvasRecording

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/canvas/recording/review", tags=["canvas-recording-review"])


# Request/Response Models
class CreateReviewRequest(BaseModel):
    """Request to create a recording review"""
    recording_id: str = Field(..., description="Recording being reviewed")
    review_status: str = Field(..., description="approved, rejected, needs_changes, pending")
    overall_rating: Optional[int] = Field(None, ge=1, le=5, description="Overall rating 1-5")
    performance_rating: Optional[int] = Field(None, ge=1, le=5, description="Performance rating 1-5")
    safety_rating: Optional[int] = Field(None, ge=1, le=5, description="Safety rating 1-5")
    feedback: Optional[str] = Field(None, description="Review feedback")
    identified_issues: Optional[list] = Field(default_factory=list, description="Issues identified")
    positive_patterns: Optional[list] = Field(default_factory=list, description="Positive patterns")
    lessons_learned: Optional[str] = Field(None, description="Key lessons learned")


class CreateReviewResponse(BaseModel):
    """Response when review is created"""
    review_id: str
    recording_id: str
    agent_id: str
    review_status: str
    confidence_delta: float
    governance_notes: str


class ReviewResponse(BaseModel):
    """Recording review details"""
    review_id: str
    recording_id: str
    agent_id: str
    user_id: str
    review_status: str
    overall_rating: Optional[int]
    performance_rating: Optional[int]
    safety_rating: Optional[int]
    feedback: Optional[str]
    identified_issues: list
    positive_patterns: list
    lessons_learned: Optional[str]
    confidence_delta: float
    promoted: bool
    demoted: bool
    governance_notes: Optional[str]
    reviewed_by: Optional[str]
    reviewed_at: Optional[str]
    auto_reviewed: bool
    training_value: Optional[str]
    created_at: str


class ReviewMetricsResponse(BaseModel):
    """Review metrics for an agent"""
    total_reviews: int
    approval_rate: float
    average_rating: float
    confidence_impact: float
    training_recordings: int
    common_issues: list
    strengths: list


# Dependencies
def get_current_user_id() -> str:
    """Get current user ID from auth context (placeholder)"""
    # TODO: Integrate with actual auth system
    return "default_user"


# Endpoints
@router.post("", response_model=CreateReviewResponse)
async def create_review(
    request: CreateReviewRequest,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(get_current_user_id)
):
    """
    Create a manual review for a canvas recording.

    - **recording_id**: Recording being reviewed
    - **review_status**: approved, rejected, needs_changes, pending
    - **overall_rating**: Overall rating 1-5 stars
    - **performance_rating**: Performance rating 1-5 stars
    - **safety_rating**: Safety/compliance rating 1-5 stars
    - **feedback**: Text feedback
    - **identified_issues**: List of issues found
    - **positive_patterns**: List of positive patterns observed

    The review will:
    - Update agent confidence based on outcome
    - Integrate with agent world model for learning
    - Create audit trail
    """
    try:
        review_service = get_recording_review_service(db)

        # Verify recording exists
        recording = db.query(CanvasRecording).filter(
            CanvasRecording.recording_id == request.recording_id
        ).first()

        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recording {request.recording_id} not found"
            )

        # Create review
        review_id = await review_service.create_review(
            recording_id=request.recording_id,
            reviewer_id=reviewer_id,
            review_status=request.review_status,
            overall_rating=request.overall_rating,
            performance_rating=request.performance_rating,
            safety_rating=request.safety_rating,
            feedback=request.feedback,
            identified_issues=request.identified_issues,
            positive_patterns=request.positive_patterns,
            lessons_learned=request.lessons_learned,
            auto_reviewed=False  # Manual review
        )

        # Get created review
        review = db.query(CanvasRecordingReview).filter(
            CanvasRecordingReview.id == review_id
        ).first()

        return CreateReviewResponse(
            review_id=review.id,
            recording_id=review.recording_id,
            agent_id=review.agent_id,
            review_status=review.review_status,
            confidence_delta=review.confidence_delta,
            governance_notes=review.governance_notes or "Review completed"
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create review: {str(e)}"
        )


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get recording review details.

    Returns complete review information including:
    - Ratings and feedback
    - Confidence impact on agent
    - Governance notes
    - Learning integration status
    """
    try:
        review = db.query(CanvasRecordingReview).filter(
            CanvasRecordingReview.id == review_id
        ).first()

        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Review {review_id} not found"
            )

        # Verify user has access (owns the recording or is admin)
        recording = db.query(CanvasRecording).filter(
            CanvasRecording.recording_id == review.recording_id
        ).first()

        if not recording or (recording.user_id != user_id):
            # TODO: Add admin check
            pass  # Allow for now

        return ReviewResponse(
            review_id=review.id,
            recording_id=review.recording_id,
            agent_id=review.agent_id,
            user_id=review.user_id,
            review_status=review.review_status,
            overall_rating=review.overall_rating,
            performance_rating=review.performance_rating,
            safety_rating=review.safety_rating,
            feedback=review.feedback,
            identified_issues=review.identified_issues or [],
            positive_patterns=review.positive_patterns or [],
            lessons_learned=review.lessons_learned,
            confidence_delta=review.confidence_delta,
            promoted=review.promoted or False,
            demoted=review.demoted or False,
            governance_notes=review.governance_notes,
            reviewed_by=review.reviewed_by,
            reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None,
            auto_reviewed=review.auto_reviewed,
            training_value=review.training_value,
            created_at=review.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get review: {str(e)}"
        )


@router.get("/recording/{recording_id}", response_model=list[ReviewResponse])
async def get_recording_reviews(
    recording_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get all reviews for a specific recording.

    Returns list of reviews (both auto and manual) for the recording.
    """
    try:
        # Verify recording exists and user has access
        recording = db.query(CanvasRecording).filter(
            CanvasRecording.recording_id == recording_id
        ).first()

        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recording {recording_id} not found"
            )

        if recording.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this recording"
            )

        # Get reviews
        reviews = db.query(CanvasRecordingReview).filter(
            CanvasRecordingReview.recording_id == recording_id
        ).order_by(CanvasRecordingReview.created_at.desc()).all()

        return [
            ReviewResponse(
                review_id=r.id,
                recording_id=r.recording_id,
                agent_id=r.agent_id,
                user_id=r.user_id,
                review_status=r.review_status,
                overall_rating=r.overall_rating,
                performance_rating=r.performance_rating,
                safety_rating=r.safety_rating,
                feedback=r.feedback,
                identified_issues=r.identified_issues or [],
                positive_patterns=r.positive_patterns or [],
                lessons_learned=r.lessons_learned,
                confidence_delta=r.confidence_delta,
                promoted=r.promoted or False,
                demoted=r.demoted or False,
                governance_notes=r.governance_notes,
                reviewed_by=r.reviewed_by,
                reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
                auto_reviewed=r.auto_reviewed,
                training_value=r.training_value,
                created_at=r.created_at.isoformat()
            )
            for r in reviews
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recording reviews: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recording reviews: {str(e)}"
        )


@router.get("/agent/{agent_id}/metrics", response_model=ReviewMetricsResponse)
async def get_agent_review_metrics(
    agent_id: str,
    days: int = 30,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get review metrics for an agent.

    Returns aggregated metrics including:
    - Total reviews and approval rate
    - Average rating
    - Confidence impact
    - Common issues and strengths
    - Training data usage

    - **days**: Number of days to look back (default 30)
    """
    try:
        review_service = get_recording_review_service(db)

        metrics = await review_service.get_review_metrics(
            agent_id=agent_id,
            days=days
        )

        return ReviewMetricsResponse(**metrics)

    except Exception as e:
        logger.error(f"Failed to get agent metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent metrics: {str(e)}"
        )


@router.post("/recording/{recording_id}/auto-review")
async def trigger_auto_review(
    recording_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Manually trigger auto-review for a recording.

    Useful for:
    - Re-reviewing after system updates
    - Reviewing recordings that were skipped
    - Testing auto-review system

    Returns the review_id if review was created, or indicates if skipped.
    """
    try:
        review_service = get_recording_review_service(db)

        # Verify recording exists
        recording = db.query(CanvasRecording).filter(
            CanvasRecording.recording_id == recording_id
        ).first()

        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recording {recording_id} not found"
            )

        # Trigger auto-review
        review_id = await review_service.auto_review_recording(recording_id)

        if review_id:
            return {
                "success": True,
                "message": "Auto-review created",
                "review_id": review_id
            }
        else:
            return {
                "success": True,
                "message": "Auto-review skipped (low confidence or disabled)",
                "review_id": None
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger auto-review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger auto-review: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "recording_review"}

"""
Feedback Service

Manages 5-star ratings, threaded comments, and thumbs up/down votes
for supervision sessions and supervisor performance.

Enables bidirectional learning where both agents and supervisors improve.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.models import (
    SupervisorRating,
    SupervisorComment,
    FeedbackVote,
    SupervisorPerformance,
    SupervisionSession,
    User,
)

logger = logging.getLogger(__name__)


class FeedbackService:
    """
    Manage feedback for supervision sessions.

    Provides:
    - 5-star ratings for supervisors
    - Threaded comments for discussions
    - Thumbs up/down votes
    - Performance metrics aggregation
    """

    def __init__(self, db: Session):
        self.db = db

    # ========================================================================
    # Rating Management
    # ========================================================================

    async def rate_supervisor(
        self,
        supervision_session_id: str,
        rater_id: str,
        rating: int,  # 1-5
        rating_category: str,
        reason: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> SupervisorRating:
        """
        Submit a 5-star rating for supervisor performance.

        Args:
            supervision_session_id: Session being rated
            rater_id: User submitting the rating
            rating: 1-5 star rating
            rating_category: Category of rating
            reason: Optional explanation
            agent_id: Optional agent context

        Returns:
            Created SupervisorRating
        """
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        # Check if session exists and is completed
        session = self.db.query(SupervisionSession).filter(
            SupervisionSession.id == supervision_session_id
        ).first()

        if not session:
            raise ValueError(f"Supervision session {supervision_session_id} not found")

        if session.status != "completed":
            raise ValueError("Can only rate completed supervision sessions")

        # Check if user already rated this session
        existing = self.db.query(SupervisorRating).filter(
            SupervisorRating.supervision_session_id == supervision_session_id,
            SupervisorRating.rater_id == rater_id
        ).first()

        if existing:
            # Update existing rating
            existing.rating = rating
            existing.rating_category = rating_category
            existing.reason = reason
            existing.was_helpful = rating >= 3
            existing.updated_at = datetime.now()
            self.db.commit()
            logger.info(f"Updated rating for session {supervision_session_id} by {rater_id}")
            return existing

        # Create new rating
        supervisor_rating = SupervisorRating(
            supervision_session_id=supervision_session_id,
            supervisor_id=session.supervisor_id,
            rater_id=rater_id,
            agent_id=agent_id,
            rating=rating,
            rating_category=rating_category,
            reason=reason,
            was_helpful=rating >= 3,
        )

        self.db.add(supervisor_rating)
        self.db.commit()

        # Update supervisor performance metrics
        await self._update_supervisor_performance(session.supervisor_id)

        logger.info(
            f"Rated supervisor {session.supervisor_id} "
            f"{rating}/5 stars by {rater_id}"
        )

        return supervisor_rating

    async def get_supervisor_ratings(
        self,
        supervisor_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all ratings for a supervisor."""
        ratings = self.db.query(SupervisorRating).filter(
            SupervisorRating.supervisor_id == supervisor_id
        ).order_by(
            SupervisorRating.created_at.desc()
        ).limit(limit).all()

        return [{
            "id": r.id,
            "session_id": r.supervision_session_id,
            "rating": r.rating,
            "category": r.rating_category,
            "reason": r.reason,
            "was_helpful": r.was_helpful,
            "rater_id": r.rater_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in ratings]

    # ========================================================================
    # Comment Management (Threaded)
    # ========================================================================

    async def add_comment(
        self,
        supervision_session_id: str,
        author_id: str,
        content: str,
        parent_comment_id: Optional[str] = None,
        comment_type: Optional[str] = None,
        content_type: str = "text",
    ) -> SupervisorComment:
        """
        Add comment to supervision session.

        Supports threading via parent_comment_id for nested discussions.

        Args:
            supervision_session_id: Session being commented on
            author_id: User writing the comment
            content: Comment text
            parent_comment_id: Parent comment for threading
            comment_type: Type of comment
            content_type: "text", "code", "suggestion"

        Returns:
            Created SupervisorComment
        """
        session = self.db.query(SupervisionSession).filter(
            SupervisionSession.id == supervision_session_id
        ).first()

        if not session:
            raise ValueError(f"Supervision session {supervision_session_id} not found")

        # Calculate thread path and depth
        thread_path = "root"
        depth = 0

        if parent_comment_id:
            parent = self.db.query(SupervisorComment).filter(
                SupervisorComment.id == parent_comment_id
            ).first()

            if not parent:
                raise ValueError(f"Parent comment {parent_comment_id} not found")

            thread_path = f"{parent.thread_path}.{parent_comment_id}"
            depth = parent.depth + 1

            # Increment parent reply count
            parent.reply_count += 1

        # Create comment
        comment = SupervisorComment(
            supervision_session_id=supervision_session_id,
            author_id=author_id,
            parent_comment_id=parent_comment_id,
            content=content,
            content_type=content_type,
            comment_type=comment_type,
            thread_path=thread_path,
            depth=depth,
        )

        self.db.add(comment)
        self.db.commit()

        logger.info(
            f"Comment added to session {supervision_session_id} "
            f"by {author_id} (depth: {depth})"
        )

        return comment

    async def get_comment_thread(
        self,
        supervision_session_id: str,
        root_comment_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get comment thread for a supervision session.

        Args:
            supervision_session_id: Session ID
            root_comment_id: Optional root comment to get sub-thread

        Returns:
            Hierarchical comment tree
        """
        query = self.db.query(SupervisorComment).filter(
            SupervisorComment.supervision_session_id == supervision_session_id,
            SupervisorComment.deleted_at.is_(None)
        )

        if root_comment_id:
            # Get only descendants of this root comment
            root = self.db.query(SupervisorComment).filter(
                SupervisorComment.id == root_comment_id
            ).first()

            if not root:
                return []

            query = query.filter(
                SupervisorComment.thread_path.like(f"{root.thread_path}%")
            )

        comments = query.order_by(
            SupervisorComment.created_at.asc()
        ).all()

        # Build hierarchical structure
        comments_by_id = {c.id: self._serialize_comment(c) for c in comments}
        root_comments = []

        for comment in comments:
            comment_dict = comments_by_id[comment.id]
            if comment.depth == 0:
                root_comments.append(comment_dict)

            # Add to parent's children list
            if comment.parent_comment_id and comment.parent_comment_id in comments_by_id:
                parent = comments_by_id[comment.parent_comment_id]
                if "replies" not in parent:
                    parent["replies"] = []
                parent["replies"].append(comment_dict)

        return root_comments

    async def update_comment(
        self,
        comment_id: str,
        user_id: str,
        content: Optional[str] = None,
        is_resolved: Optional[bool] = None,
    ) -> Optional[SupervisorComment]:
        """Update comment (edit or resolve)."""
        comment = self.db.query(SupervisorComment).filter(
            SupervisorComment.id == comment_id
        ).first()

        if not comment:
            raise ValueError(f"Comment {comment_id} not found")

        if comment.author_id != user_id:
            raise ValueError("Can only edit your own comments")

        if content:
            comment.content = content
            comment.is_edited = True
            comment.updated_at = datetime.now()

        if is_resolved is not None:
            comment.is_resolved = is_resolved
            comment.resolved_at = datetime.now() if is_resolved else None

        self.db.commit()

        logger.info(f"Comment {comment_id} updated by {user_id}")
        return comment

    async def vote_on_comment(
        self,
        comment_id: str,
        user_id: str,
        vote_type: str,  # "up", "down"
    ) -> FeedbackVote:
        """
        Vote thumbs up/down on a comment.

        Args:
            comment_id: Comment being voted on
            user_id: User voting
            vote_type: "up" or "down"

        Returns:
            Created or updated FeedbackVote
        """
        if vote_type not in ["up", "down"]:
            raise ValueError("vote_type must be 'up' or 'down'")

        # Check for existing vote
        existing = self.db.query(FeedbackVote).filter(
            FeedbackVote.comment_id == comment_id,
            FeedbackVote.user_id == user_id
        ).first()

        if existing:
            # Get comment to update counts
            comment = self.db.query(SupervisorComment).filter(
                SupervisorComment.id == comment_id
            ).first()

            # Remove vote if same type (toggle off), otherwise update
            if existing.vote_type == vote_type:
                # Decrement count before deleting
                if comment:
                    if vote_type == "up":
                        comment.upvote_count = max(0, comment.upvote_count - 1)
                    else:
                        comment.downvote_count = max(0, comment.downvote_count - 1)

                self.db.delete(existing)
                self.db.commit()
                logger.info(f"Removed {vote_type}vote on comment {comment_id} by {user_id}")
                return None
            else:
                # Change vote type - decrement old, increment new
                if comment:
                    if existing.vote_type == "up":
                        comment.upvote_count = max(0, comment.upvote_count - 1)
                    else:
                        comment.downvote_count = max(0, comment.downvote_count - 1)

                    if vote_type == "up":
                        comment.upvote_count += 1
                    else:
                        comment.downvote_count += 1

                existing.vote_type = vote_type
                self.db.commit()
                logger.info(f"Changed vote on comment {comment_id} to {vote_type} by {user_id}")
                return existing

        # Create new vote
        vote = FeedbackVote(
            comment_id=comment_id,
            user_id=user_id,
            vote_type=vote_type,
        )

        self.db.add(vote)
        self.db.commit()

        # Update comment vote counts
        comment = self.db.query(SupervisorComment).filter(
            SupervisorComment.id == comment_id
        ).first()

        if comment:
            if vote_type == "up":
                comment.upvote_count += 1
            else:
                comment.downvote_count += 1
            self.db.commit()

        logger.info(f"{vote_type}vote on comment {comment_id} by {user_id}")
        return vote

    # ========================================================================
    # Session Feedback (Thumbs Up/Down)
    # ========================================================================

    async def vote_on_session(
        self,
        supervision_session_id: str,
        user_id: str,
        vote_type: str,
        vote_reason: Optional[str] = None,
    ) -> FeedbackVote:
        """
        Vote thumbs up/down on a supervision session.

        Args:
            supervision_session_id: Session being voted on
            user_id: User voting
            vote_type: "up" or "down"
            vote_reason: Optional reason

        Returns:
            Created or updated FeedbackVote
        """
        if vote_type not in ["up", "down"]:
            raise ValueError("vote_type must be 'up' or 'down'")

        # Check for existing vote
        existing = self.db.query(FeedbackVote).filter(
            FeedbackVote.supervision_session_id == supervision_session_id,
            FeedbackVote.user_id == user_id,
            FeedbackVote.comment_id.is_(None)
        ).first()

        if existing:
            # Toggle off if same type, otherwise update
            if existing.vote_type == vote_type:
                self.db.delete(existing)
                self.db.commit()
                logger.info(f"Removed {vote_type}vote on session {supervision_session_id} by {user_id}")
                return None
            else:
                existing.vote_type = vote_type
                existing.vote_reason = vote_reason
                self.db.commit()
                logger.info(f"Changed vote on session {supervision_session_id} to {vote_type} by {user_id}")
                return existing

        # Create new vote
        vote = FeedbackVote(
            supervision_session_id=supervision_session_id,
            user_id=user_id,
            vote_type=vote_type,
            vote_reason=vote_reason,
        )

        self.db.add(vote)
        self.db.commit()

        logger.info(f"{vote_type}vote on session {supervision_session_id} by {user_id}")
        return vote

    async def get_session_feedback_summary(
        self,
        supervision_session_id: str
    ) -> Dict[str, Any]:
        """
        Get feedback summary for a supervision session.

        Returns:
            {
                "upvotes": int,
                "downvotes": int,
                "net_score": int,
                "comment_count": int,
                "average_rating": float
            }
        """
        upvotes = self.db.query(FeedbackVote).filter(
            FeedbackVote.supervision_session_id == supervision_session_id,
            FeedbackVote.vote_type == "up"
        ).count()

        downvotes = self.db.query(FeedbackVote).filter(
            FeedbackVote.supervision_session_id == supervision_session_id,
            FeedbackVote.vote_type == "down"
        ).count()

        comment_count = self.db.query(SupervisorComment).filter(
            SupervisorComment.supervision_session_id == supervision_session_id,
            SupervisorComment.deleted_at.is_(None)
        ).count()

        ratings = self.db.query(SupervisorRating).filter(
            SupervisorRating.supervision_session_id == supervision_session_id
        ).all()

        average_rating = None
        if ratings:
            average_rating = sum(r.rating for r in ratings) / len(ratings)

        return {
            "upvotes": upvotes,
            "downvotes": downvotes,
            "net_score": upvotes - downvotes,
            "comment_count": comment_count,
            "average_rating": round(average_rating, 2) if average_rating else None,
            "rating_count": len(ratings),
        }

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _update_supervisor_performance(self, supervisor_id: str):
        """Update supervisor performance metrics after new rating."""
        performance = self.db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == supervisor_id
        ).first()

        if not performance:
            # Create new performance record
            performance = SupervisorPerformance(
                supervisor_id=supervisor_id,
                confidence_score=0.5,
                competence_level="novice",
            )
            self.db.add(performance)

        # Recalculate metrics
        await self._recalculate_performance(performance)

        self.db.commit()

    async def _recalculate_performance(self, performance: SupervisorPerformance):
        """Recalculate all performance metrics from scratch."""
        supervisor_id = performance.supervisor_id

        # Get all ratings for this supervisor
        ratings = self.db.query(SupervisorRating).filter(
            SupervisorRating.supervisor_id == supervisor_id
        ).all()

        # Calculate rating metrics
        performance.total_ratings = len(ratings)
        if ratings:
            performance.average_rating = sum(r.rating for r in ratings) / len(ratings)

            # Distribution
            performance.rating_1_count = sum(1 for r in ratings if r.rating == 1)
            performance.rating_2_count = sum(1 for r in ratings if r.rating == 2)
            performance.rating_3_count = sum(1 for r in ratings if r.rating == 3)
            performance.rating_4_count = sum(1 for r in ratings if r.rating == 4)
            performance.rating_5_count = sum(1 for r in ratings if r.rating == 5)

        # Get comment and vote metrics
        performance.total_comments_given = self.db.query(SupervisorComment).filter(
            SupervisorComment.author_id == supervisor_id
        ).count()

        performance.total_upvotes_received = self.db.query(FeedbackVote).join(
            SupervisorComment,
            FeedbackVote.comment_id == SupervisorComment.id
        ).filter(
            SupervisorComment.author_id == supervisor_id,
            FeedbackVote.vote_type == "up"
        ).count()

        performance.total_downvotes_received = self.db.query(FeedbackVote).join(
            SupervisorComment,
            FeedbackVote.comment_id == SupervisorComment.id
        ).filter(
            SupervisorComment.author_id == supervisor_id,
            FeedbackVote.vote_type == "down"
        ).count()

        # Update confidence and competence based on ratings
        await self._update_confidence_and_competence(performance)

        # Update trend
        await self._update_performance_trend(performance)

        performance.last_updated = datetime.now()

    async def _update_confidence_and_competence(self, performance: SupervisorPerformance):
        """Update supervisor confidence and competence level based on ratings."""
        avg_rating = performance.average_rating or 3.0
        total_ratings = performance.total_ratings or 0

        # More ratings and higher ratings increase confidence
        rating_volume_score = min(total_ratings / 50, 1.0)  # Max at 50 ratings
        rating_quality_score = (avg_rating - 3) / 2  # -1.0 to 1.0

        # Combined score: 0.5 (base) + 0.3 (volume) + 0.2 (quality)
        new_confidence = max(0.1, min(0.95, 0.5 + 0.3 * rating_volume_score + 0.2 * rating_quality_score))

        # Smooth transition (exponential moving average)
        alpha = 0.1  # Learning rate
        performance.confidence_score = (alpha * new_confidence + (1 - alpha) * performance.confidence_score)

        # Update competence level based on confidence and total sessions
        total_sessions = performance.total_sessions_supervised or 0
        if performance.confidence_score >= 0.8 and total_sessions >= 50:
            performance.competence_level = "expert"
        elif performance.confidence_score >= 0.6 and total_sessions >= 25:
            performance.competence_level = "advanced"
        elif performance.confidence_score >= 0.4 and total_sessions >= 10:
            performance.competence_level = "intermediate"
        else:
            performance.competence_level = "novice"

    async def _update_performance_trend(self, performance: SupervisorPerformance):
        """Calculate performance trend (improving/stable/declining)."""
        supervisor_id = performance.supervisor_id

        # Get recent ratings (last 20)
        recent_ratings = self.db.query(SupervisorRating).filter(
            SupervisorRating.supervisor_id == supervisor_id
        ).order_by(
            SupervisorRating.created_at.desc()
        ).limit(20).all()

        if len(recent_ratings) < 10:
            performance.performance_trend = "stable"
            performance.learning_rate = 0.0
            return

        # Compare first half to second half
        mid_point = len(recent_ratings) // 2
        first_half = recent_ratings[mid_point:]
        second_half = recent_ratings[:mid_point]

        avg_first = sum(r.rating for r in first_half) / len(first_half) if first_half else 0
        avg_second = sum(r.rating for r in second_half) / len(second_half) if second_half else 0

        difference = avg_second - avg_first

        # Update trend
        if difference > 0.5:
            performance.performance_trend = "improving"
            performance.learning_rate = min(difference / 2, 0.1)  # Cap at 0.1
        elif difference < -0.5:
            performance.performance_trend = "declining"
            performance.learning_rate = max(difference / 2, -0.1)  # Cap at -0.1
        else:
            performance.performance_trend = "stable"
            performance.learning_rate = 0.0

    def _serialize_comment(self, comment: SupervisorComment) -> Dict[str, Any]:
        """Serialize comment to dict."""
        return {
            "id": comment.id,
            "content": comment.content,
            "content_type": comment.content_type,
            "comment_type": comment.comment_type,
            "author_id": comment.author_id,
            "parent_comment_id": comment.parent_comment_id,
            "thread_path": comment.thread_path,
            "depth": comment.depth,
            "reply_count": comment.reply_count,
            "upvote_count": comment.upvote_count,
            "downvote_count": comment.downvote_count,
            "is_edited": comment.is_edited,
            "is_resolved": comment.is_resolved,
            "resolved_at": comment.resolved_at.isoformat() if comment.resolved_at else None,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
        }

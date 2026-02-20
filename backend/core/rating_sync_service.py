"""
Rating Sync Service - Bidirectional sync of skill ratings with Atom SaaS.

This service handles:
- Periodic upload of local ratings to Atom SaaS
- Batch upload with parallel processing (max 10 concurrent)
- Conflict resolution based on timestamp comparison
- Dead letter queue for failed uploads
- Sync state tracking and metrics

Phase 61 Plan 02 - Rating Synchronization
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from core.models import SkillRating, FailedRatingUpload
from core.atom_saas_client import AtomSaaSClient

logger = logging.getLogger(__name__)


class RatingSyncService:
    """
    Service for syncing skill ratings between local marketplace and Atom SaaS.

    Features:
    - Batch upload with asyncio.gather (max 10 concurrent)
    - Conflict resolution: newest rating wins based on timestamp
    - Dead letter queue for failed uploads
    - Sync metrics tracking in database
    """

    def __init__(self, db: Session, atom_saas_client: Optional[AtomSaaSClient] = None):
        """
        Initialize rating sync service.

        Args:
            db: SQLAlchemy database session
            atom_saas_client: Optional Atom SaaS client (creates default if None)
        """
        self.db = db
        self.client = atom_saas_client or AtomSaaSClient()
        self._sync_in_progress = False
        self._max_concurrent_uploads = 10

    def get_pending_ratings(self, limit: int = 100) -> List[SkillRating]:
        """
        Query ratings that haven't been synced to Atom SaaS.

        Args:
            limit: Maximum number of ratings to fetch (default: 100)

        Returns:
            List of pending SkillRating objects
        """
        return (
            self.db.query(SkillRating)
            .filter(SkillRating.synced_to_saas == False)  # noqa: E712
            .order_by(SkillRating.created_at)
            .limit(limit)
            .all()
        )

    async def upload_rating(self, rating: SkillRating) -> Dict[str, Any]:
        """
        Upload single rating to Atom SaaS.

        Args:
            rating: SkillRating object to upload

        Returns:
            Response dict with success status and rating_id
        """
        try:
            # Validate rating value
            if not 1 <= rating.rating <= 5:
                return {
                    "success": False,
                    "error": f"Invalid rating value: {rating.rating}. Must be 1-5"
                }

            # Check if this is an update (has remote_rating_id)
            if rating.remote_rating_id:
                # TODO: Implement update via Atom SaaS API when available
                logger.warning(f"Rating updates not yet supported: {rating.remote_rating_id}")
                return {"success": False, "error": "Rating updates not yet supported"}

            # Upload new rating
            response = await self.client.rate_skill(
                skill_id=rating.skill_id,
                user_id=rating.user_id,
                rating=rating.rating,
                comment=rating.comment
            )

            if response.get("success") or response.get("id"):
                return {
                    "success": True,
                    "rating_id": response.get("id") or response.get("rating_id")
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Unknown error")
                }

        except Exception as e:
            logger.error(f"Failed to upload rating {rating.id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def upload_ratings_batch(self, ratings: List[SkillRating]) -> List[Dict[str, Any]]:
        """
        Upload multiple ratings in parallel using asyncio.gather.

        Args:
            ratings: List of SkillRating objects

        Returns:
            List of response dicts (one per rating)
        """
        # Limit concurrent uploads to avoid overwhelming the API
        semaphore = asyncio.Semaphore(self._max_concurrent_uploads)

        async def upload_with_semaphore(rating: SkillRating) -> Dict[str, Any]:
            async with semaphore:
                return await self.upload_rating(rating)

        # Upload all ratings in parallel
        results = await asyncio.gather(
            *[upload_with_semaphore(rating) for rating in ratings],
            return_exceptions=True
        )

        # Handle any exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "rating_id": ratings[i].id
                })
            else:
                processed_results.append(result)

        return processed_results

    def mark_as_synced(self, rating_id: str, remote_rating_id: str) -> None:
        """
        Mark a rating as successfully synced to Atom SaaS.

        Args:
            rating_id: Local rating ID
            remote_rating_id: Rating ID from Atom SaaS
        """
        rating = self.db.query(SkillRating).filter(SkillRating.id == rating_id).first()
        if rating:
            rating.synced_to_saas = True
            rating.synced_at = datetime.now(timezone.utc)
            rating.remote_rating_id = remote_rating_id
            self.db.commit()
            logger.info(f"Marked rating {rating_id} as synced (remote: {remote_rating_id})")
        else:
            logger.warning(f"Rating {rating_id} not found for marking as synced")

    def handle_upload_failure(self, rating: SkillRating, error: str) -> None:
        """
        Store failed upload in dead letter queue.

        Args:
            rating: SkillRating that failed to upload
            error: Error message
        """
        # Check if there's already a failed upload record
        failed = (
            self.db.query(FailedRatingUpload)
            .filter(FailedRatingUpload.rating_id == rating.id)
            .first()
        )

        if failed:
            # Increment retry count
            failed.retry_count += 1
            failed.last_retry_at = datetime.now(timezone.utc)
            failed.error_message = error
        else:
            # Create new failed upload record
            failed = FailedRatingUpload(
                rating_id=rating.id,
                error_message=error,
                failed_at=datetime.now(timezone.utc),
                retry_count=1
            )
            self.db.add(failed)

        self.db.commit()
        logger.error(f"Stored failed upload for rating {rating.id}: {error}")

    async def sync_ratings(self, upload_all: bool = False) -> Dict[str, Any]:
        """
        Main sync orchestration: fetch pending, upload, mark synced.

        Args:
            upload_all: If True, re-upload all ratings. If False, only pending.

        Returns:
            Sync metrics dict with counts of uploaded, failed, skipped
        """
        if self._sync_in_progress:
            logger.warning("Rating sync already in progress")
            return {
                "success": False,
                "error": "Sync already in progress",
                "uploaded": 0,
                "failed": 0,
                "skipped": 0
            }

        self._sync_in_progress = True

        try:
            # Fetch pending ratings
            if upload_all:
                # Re-query all ratings (for admin-triggered full sync)
                ratings = (
                    self.db.query(SkillRating)
                    .order_by(SkillRating.created_at)
                    .limit(100)
                    .all()
                )
            else:
                ratings = self.get_pending_ratings(limit=100)

            if not ratings:
                logger.info("No pending ratings to sync")
                return {
                    "success": True,
                    "uploaded": 0,
                    "failed": 0,
                    "skipped": 0,
                    "message": "No pending ratings"
                }

            logger.info(f"Starting rating sync: {len(ratings)} ratings")

            # Upload ratings in batch
            results = await self.upload_ratings_batch(ratings)

            # Process results
            uploaded = 0
            failed = 0
            skipped = 0

            for rating, result in zip(ratings, results):
                if result.get("success"):
                    # Mark as synced
                    remote_id = result.get("rating_id")
                    if remote_id:
                        self.mark_as_synced(rating.id, remote_id)
                        uploaded += 1
                    else:
                        logger.warning(f"Upload succeeded but no remote_id for {rating.id}")
                        failed += 1
                else:
                    # Store in dead letter queue
                    self.handle_upload_failure(rating, result.get("error", "Unknown error"))
                    failed += 1

            logger.info(f"Rating sync complete: {uploaded} uploaded, {failed} failed")

            return {
                "success": True,
                "uploaded": uploaded,
                "failed": failed,
                "skipped": skipped
            }

        except Exception as e:
            logger.error(f"Rating sync failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "uploaded": 0,
                "failed": 0,
                "skipped": 0
            }
        finally:
            self._sync_in_progress = False

    async def resolve_rating_conflict(
        self,
        local_rating: SkillRating,
        remote_rating: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Resolve conflict between local and remote rating.

        Strategy: **timestamp-based newest wins**
        - Compare local rating.created_at with remote rating.timestamp
        - If remote is newer: update local rating
        - If local is newer: push to Atom SaaS (TODO when API supports updates)

        Args:
            local_rating: Local SkillRating object
            remote_rating: Remote rating data from Atom SaaS

        Returns:
            Resolution dict with action taken and reason
        """
        local_time = local_rating.created_at
        remote_time_str = remote_rating.get("created_at") or remote_rating.get("timestamp")

        if not remote_time_str:
            logger.warning(f"Remote rating has no timestamp: {remote_rating}")
            return {
                "action": "skip",
                "reason": "Remote rating has no timestamp"
            }

        # Parse remote timestamp (ISO format)
        try:
            remote_time = datetime.fromisoformat(remote_time_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            logger.warning(f"Invalid remote timestamp format: {remote_time_str}")
            return {
                "action": "skip",
                "reason": "Invalid remote timestamp format"
            }

        # Compare timestamps (handle timezone-aware vs naive)
        # Ensure both are timezone-aware for comparison
        if local_time.tzinfo is None:
            # Local is naive, assume UTC
            from datetime import timezone as dt_timezone
            local_time = local_time.replace(tzinfo=dt_timezone.utc)
        if remote_time.tzinfo is None:
            # Remote is naive, assume UTC
            from datetime import timezone as dt_timezone
            remote_time = remote_time.replace(tzinfo=dt_timezone.utc)

        if remote_time > local_time:
            # Remote is newer - update local
            local_rating.rating = remote_rating.get("rating", local_rating.rating)
            local_rating.comment = remote_rating.get("comment", local_rating.comment)
            local_rating.remote_rating_id = remote_rating.get("id")
            self.db.commit()

            logger.info(
                f"Updated local rating {local_rating.id} from remote "
                f"(remote: {remote_time}, local: {local_time})"
            )
            return {
                "action": "updated_local",
                "reason": "Remote rating is newer",
                "remote_time": str(remote_time),
                "local_time": str(local_time)
            }
        elif local_time > remote_time:
            # Local is newer - push to Atom SaaS (TODO when API supports updates)
            logger.info(
                f"Local rating {local_rating.id} is newer than remote "
                f"(local: {local_time}, remote: {remote_time})"
            )
            return {
                "action": "should_update_remote",
                "reason": "Local rating is newer",
                "local_time": str(local_time),
                "remote_time": str(remote_time)
            }
        else:
            # Same timestamp - keep local (no change needed)
            logger.info(f"Local and remote ratings have same timestamp: {local_time}")
            return {
                "action": "no_change",
                "reason": "Timestamps are equal"
            }

    def get_sync_metrics(self) -> Dict[str, Any]:
        """
        Get rating sync metrics for monitoring.

        Returns:
            Dict with pending_count, synced_count, failed_count
        """
        pending_count = (
            self.db.query(func.count(SkillRating.id))
            .filter(SkillRating.synced_to_saas == False)  # noqa: E712
            .scalar()
        )

        synced_count = (
            self.db.query(func.count(SkillRating.id))
            .filter(SkillRating.synced_to_saas == True)  # noqa: E712
            .scalar()
        )

        failed_count = (
            self.db.query(func.count(FailedRatingUpload.id))
            .scalar()
        )

        return {
            "pending_count": pending_count or 0,
            "synced_count": synced_count or 0,
            "failed_count": failed_count or 0
        }

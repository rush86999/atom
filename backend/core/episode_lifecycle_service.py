"""
Episode Lifecycle Service

Manages episode lifecycle:
- Decay old episodes (90-day window)
- Consolidate similar episodes
- Archive to cold storage
- Update importance scores
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.models import Episode, EpisodeSegment
from core.lancedb_handler import get_lancedb_handler

logger = logging.getLogger(__name__)


class EpisodeLifecycleService:
    """Episode lifecycle management"""

    def __init__(self, db: Session):
        self.db = db
        self.lancedb = get_lancedb_handler()

    async def decay_old_episodes(self, days_threshold: int = 90) -> Dict[str, int]:
        """
        Apply decay scores to episodes older than threshold.

        Decay formula: decay_score = max(0, 1 - (days_old / 180))
        Episodes reach 0 decay score after 180 days.

        Args:
            days_threshold: Apply decay to episodes older than this

        Returns:
            {"affected": int, "archived": int}
        """
        cutoff = datetime.now() - timedelta(days=days_threshold)

        episodes = self.db.query(Episode).filter(
            Episode.started_at < cutoff,
            Episode.status != "archived"
        ).all()

        affected = 0
        archived = 0

        for episode in episodes:
            days_old = (datetime.now() - episode.started_at).days
            new_decay = max(0, 1 - (days_old / 180))

            episode.decay_score = new_decay
            episode.access_count += 1  # Track access
            affected += 1

            # Archive if very old (>180 days)
            if days_old > 180:
                episode.status = "archived"
                episode.archived_at = datetime.now()
                archived += 1

        self.db.commit()
        logger.info(f"Decay applied to {affected} episodes, archived {archived}")

        return {"affected": affected, "archived": archived}

    async def consolidate_similar_episodes(
        self,
        agent_id: str,
        similarity_threshold: float = 0.85
    ) -> Dict[str, int]:
        """
        Merge related episodes into parent episode.

        Args:
            agent_id: Agent ID
            similarity_threshold: Semantic similarity threshold

        Returns:
            {"consolidated": int, "parent_episodes": int}
        """
        # Get recent completed episodes
        episodes = self.db.query(Episode).filter(
            Episode.agent_id == agent_id,
            Episode.status == "completed"
        ).order_by(Episode.started_at.desc()).limit(100).all()

        # Group by semantic similarity
        consolidated = 0
        parent_count = 0

        # TODO: Implement semantic clustering
        # For now, return placeholder
        logger.info(f"Consolidated {consolidated} episodes into {parent_count} parents")

        return {"consolidated": consolidated, "parent_episodes": parent_count}

    async def archive_to_cold_storage(self, episode_id: str) -> bool:
        """
        Move episode metadata to LanceDB cold storage.

        Note: Full content already in LanceDB from creation.
        This only marks PostgreSQL record as archived.

        Args:
            episode_id: Episode ID

        Returns:
            True if successful
        """
        episode = self.db.query(Episode).filter(
            Episode.id == episode_id
        ).first()

        if not episode:
            return False

        episode.status = "archived"
        episode.archived_at = datetime.now()

        self.db.commit()
        logger.info(f"Episode {episode_id} archived to cold storage")

        return True

    async def update_importance_scores(
        self,
        episode_id: str,
        user_feedback: float
    ) -> bool:
        """
        Update episode importance based on user feedback.

        Args:
            episode_id: Episode ID
            user_feedback: Feedback score (-1.0 to 1.0)

        Returns:
            True if successful
        """
        episode = self.db.query(Episode).filter(
            Episode.id == episode_id
        ).first()

        if not episode:
            return False

        # Update importance score (feedback has 20% weight)
        new_importance = episode.importance_score * 0.8 + (user_feedback + 1.0) / 2.0 * 0.2
        episode.importance_score = max(0.0, min(1.0, new_importance))

        self.db.commit()
        logger.info(f"Episode {episode_id} importance updated to {episode.importance_score:.2f}")

        return True

    async def batch_update_access_counts(
        self,
        episode_ids: List[str]
    ) -> Dict[str, int]:
        """
        Increment access counts for multiple episodes.

        Args:
            episode_ids: List of episode IDs

        Returns:
            {"updated": int}
        """
        updated = 0

        for episode_id in episode_ids:
            episode = self.db.query(Episode).filter(
                Episode.id == episode_id
            ).first()

            if episode:
                episode.access_count += 1
                updated += 1

        self.db.commit()
        logger.info(f"Updated access counts for {updated} episodes")

        return {"updated": updated}

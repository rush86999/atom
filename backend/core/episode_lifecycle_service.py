"""
Episode Lifecycle Service

Manages episode lifecycle:
- Decay old episodes (90-day window)
- Consolidate similar episodes
- Archive to cold storage
- Update importance scores
"""

from datetime import datetime, timedelta
import logging
from typing import Dict, List
from sqlalchemy.orm import Session

from core.lancedb_handler import get_lancedb_handler
from core.models import Episode, EpisodeSegment

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
        Merge related episodes into parent episode using semantic clustering.

        Uses LanceDB vector search to find semantically similar episodes
        and consolidate them under a single parent episode.

        Args:
            agent_id: Agent ID
            similarity_threshold: Semantic similarity threshold (0.0-1.0)

        Returns:
            {"consolidated": int, "parent_episodes": int}
        """
        # Get recent completed episodes that haven't been consolidated
        episodes = self.db.query(Episode).filter(
            Episode.agent_id == agent_id,
            Episode.status == "completed",
            Episode.consolidated_into.is_(None)  # Not already consolidated
        ).order_by(Episode.started_at.desc()).limit(100).all()

        if not episodes:
            return {"consolidated": 0, "parent_episodes": 0}

        consolidated = 0
        parent_count = 0
        processed_ids = set()

        try:
            # Process each episode as a potential parent
            for potential_parent in episodes:
                if potential_parent.id in processed_ids:
                    continue

                # Use episode title/description as search query
                search_query = f"{potential_parent.title} {potential_parent.description or ''}"

                # Search for semantically similar episodes in LanceDB
                search_results = self.lancedb.search(
                    table_name="episodes",
                    query=search_query,
                    filter_str=f"agent_id == '{agent_id}'",
                    limit=20
                )

                # Extract episode IDs from results
                similar_episode_ids = []
                for result in search_results:
                    metadata = result.get("metadata", {})
                    if isinstance(metadata, str):
                        import json
                        metadata = json.loads(metadata)
                    episode_id = metadata.get("episode_id")
                    if episode_id and episode_id != potential_parent.id:
                        # Calculate similarity score from LanceDB distance
                        # LanceDB returns distance, we need similarity = 1 - distance
                        distance = result.get("_distance", 1.0)
                        similarity = 1.0 - distance

                        if similarity >= similarity_threshold:
                            similar_episode_ids.append((episode_id, similarity))

                if similar_episode_ids:
                    # Mark similar episodes as consolidated
                    for child_id, similarity in similar_episode_ids:
                        child_episode = self.db.query(Episode).filter(
                            Episode.id == child_id,
                            Episode.consolidated_into.is_(None)  # Not already consolidated
                        ).first()

                        if child_episode:
                            child_episode.consolidated_into = potential_parent.id
                            processed_ids.add(child_id)
                            consolidated += 1

                    parent_count += 1
                    processed_ids.add(potential_parent.id)

            self.db.commit()
            logger.info(
                f"Consolidated {consolidated} episodes into {parent_count} parent episodes "
                f"for agent {agent_id} (threshold: {similarity_threshold})"
            )

        except Exception as e:
            logger.error(f"Semantic consolidation failed for agent {agent_id}: {e}")
            self.db.rollback()

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

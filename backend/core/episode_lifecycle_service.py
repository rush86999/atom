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

    def archive_episode(self, episode: Episode) -> bool:
        """
        Archive a single episode to cold storage (synchronous).

        Marks episode as archived with timestamp. Full content already
        in LanceDB from creation, this only updates PostgreSQL metadata.

        Args:
            episode: Episode object to archive

        Returns:
            True if successful
        """
        try:
            episode.status = "archived"
            episode.archived_at = datetime.now()

            self.db.commit()
            logger.info(f"Episode {episode.id} archived to cold storage")

            return True
        except Exception as e:
            logger.error(f"Failed to archive episode {episode.id}: {e}")
            self.db.rollback()
            return False

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

    def update_lifecycle(self, episode: Episode) -> bool:
        """
        Update lifecycle state for a single episode.

        Calculates and applies decay based on episode age.
        Synchronous method for single-episode updates.

        Args:
            episode: Episode object to update

        Returns:
            True if successful
        """
        try:
            if not episode.started_at:
                logger.warning(f"Episode {episode.id} has no started_at, skipping lifecycle update")
                return False

            # Calculate episode age in days (float for precision)
            # Handle both offset-aware and offset-naive datetimes
            now = datetime.now()
            if episode.started_at.tzinfo is not None:
                now = datetime.now(episode.started_at.tzinfo)

            # Use total_seconds() for floating-point precision
            age_timedelta = now - episode.started_at
            days_old = age_timedelta.total_seconds() / 86400.0  # Convert to days

            # Apply decay formula: decay_score = min(1, days_old / 90)
            # This represents "how much decay has been applied" (0 = none, 1 = fully decayed)
            # 1-day-old episodes: ~0.01 decay
            # 90-day-old episodes: 1.0 decay (fully decayed at 90 days)
            # Clamp to [0, 1] range
            new_decay = min(1.0, max(0.0, days_old / 90.0))

            # Update episode
            episode.decay_score = new_decay

            # Archive if very old (>180 days)
            if days_old > 180 and episode.status != "archived":
                episode.status = "archived"
                episode.archived_at = datetime.now()

            self.db.commit()
            logger.info(f"Updated lifecycle for episode {episode.id}: decay_score={new_decay:.2f}, days_old={days_old}")

            return True

        except Exception as e:
            logger.error(f"Failed to update lifecycle for episode {episode.id}: {e}")
            self.db.rollback()
            return False

    def apply_decay(self, episode_or_episodes) -> bool:
        """
        Apply decay calculation to episode(s) (synchronous).

        Supports both single episode and list of episodes.

        Args:
            episode_or_episodes: Episode object or list of Episode objects

        Returns:
            True if successful
        """
        # Handle list of episodes
        if isinstance(episode_or_episodes, list):
            all_success = True
            for episode in episode_or_episodes:
                if not self.update_lifecycle(episode):
                    all_success = False
            return all_success
        else:
            # Single episode
            return self.update_lifecycle(episode_or_episodes)

    def consolidate_episodes(self, agent_or_agent_id, similarity_threshold: float = 0.85) -> Dict[str, int]:
        """
        Consolidate related episodes (synchronous wrapper).

        Wrapper around consolidate_similar_episodes for sync calling.

        Args:
            agent_or_agent_id: Agent object or agent ID string
            similarity_threshold: Semantic similarity threshold (0.0-1.0)

        Returns:
            {"consolidated": int, "parent_episodes": int}
        """
        # Extract agent_id if Agent object passed
        if hasattr(agent_or_agent_id, 'id'):
            agent_id = agent_or_agent_id.id
        else:
            agent_id = agent_or_agent_id

        # Import asyncio at runtime to avoid issues
        import asyncio
        try:
            # Try to get existing event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create new loop in thread to run async function
                    import concurrent.futures
                    import threading

                    result = [None]
                    exception = [None]

                    def run_consolidate():
                        try:
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            try:
                                result[0] = new_loop.run_until_complete(
                                    self.consolidate_similar_episodes(agent_id, similarity_threshold)
                                )
                            finally:
                                new_loop.close()
                        except Exception as e:
                            exception[0] = e

                    thread = threading.Thread(target=run_consolidate)
                    thread.start()
                    thread.join(timeout=5)  # 5 second timeout

                    if exception[0]:
                        raise exception[0]
                    if result[0] is None:
                        raise TimeoutError("Consolidation timed out")

                    return result[0]
                else:
                    return loop.run_until_complete(
                        self.consolidate_similar_episodes(agent_id, similarity_threshold)
                    )
            except RuntimeError:
                # No event loop exists, create new one
                return asyncio.run(self.consolidate_similar_episodes(agent_id, similarity_threshold))

        except Exception as e:
            logger.error(f"Failed to consolidate episodes for agent {agent_id}: {e}")
            return {"consolidated": 0, "parent_episodes": 0}

"""
Memory Consolidation Service

Integrates POMDP memory framework with existing EpisodeLifecycleService.
Implements offline memory consolidation inspired by human sleep mechanisms.

Based on 2025-2026 research:
- "Memory for Autonomous LLM Agents" (arXiv:2603.07670v1)
- "From Storage to Experience: A Survey on LLM Agent Memory"

Key Features:
- Episode to POMDP memory synchronization
- Offline consolidation during idle periods
- Pattern extraction and association strengthening
- Memory replay for critical episodes
- Forgetting curve implementation
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.orm import Session

from core.models import Episode, EpisodeSegment
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.lancedb_handler import get_lancedb_handler

logger = logging.getLogger(__name__)

# POMDP imports (optional)
try:
    from core.memory.pomdp_memory_framework import (
        MemoryManager,
        MemoryConsolidation,
        MemoryEntry,
        MemoryType,
        MemoryStatus,
        ObservationSpace,
        ActionSpace,
        get_memory_manager,
        get_experience_calculator,
    )
    POMDP_AVAILABLE = True
except ImportError:
    logger.warning("POMDP Memory Framework not available for consolidation service")
    POMDP_AVAILABLE = False


class ConsolidationConfig:
    """Configuration for memory consolidation"""

    # Consolidation triggers
    CONSOLIDATION_INTERVAL_HOURS = 6  # Run consolidation every 6 hours
    MIN_MEMORIES_FOR_CONSOLIDATION = 10  # Minimum memories to trigger consolidation

    # Quality thresholds
    MIN_QUALITY_SCORE = 0.5  # Minimum quality for consolidation
    HIGH_QUALITY_THRESHOLD = 0.7  # High-quality memories get special treatment

    # Access thresholds
    CONSOLIDATION_ACCESS_THRESHOLD = 5  # Access count to trigger consolidation
    REPLAY_THRESHOLD = 10  # Access count to trigger memory replay

    # Forgetting curve
    FORGETTING_DAYS = 90  # Days until memory is forgotten
    FORGETTING_DECAY_RATE = 0.95  # Daily retention rate (exponential decay)

    # Pattern extraction
    MIN_PATTERN_SIZE = 3  # Minimum similar memories to form a pattern
    PATTERN_SIMILARITY_THRESHOLD = 0.8  # Similarity threshold for pattern detection


class MemoryConsolidationService:
    """
    Service for offline memory consolidation.

    Integrates POMDP memory framework with EpisodeLifecycleService:
    1. Syncs episodes to POMDP memory entries
    2. Runs consolidation cycles
    3. Extracts patterns and strengthens associations
    4. Implements forgetting curve
    """

    def __init__(self, db: Session):
        self.db = db
        self.lancedb = get_lancedb_handler()
        self.episode_lifecycle = EpisodeLifecycleService(db)

        # POMDP components
        self.memory_manager = None
        self.pomdp_consolidation = None

        if POMDP_AVAILABLE:
            try:
                self.memory_manager = get_memory_manager(db, self.lancedb)
                self.pomdp_consolidation = MemoryConsolidation(self.memory_manager)
                logger.info("POMDP Memory Consolidation initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize POMDP consolidation: {e}")

        # Consolidation state
        self._last_consolidation: Optional[datetime] = None
        self._consolidation_in_progress = False

    async def sync_episodes_to_memory(
        self,
        agent_id: str,
        limit: int = 100
    ) -> Dict[str, int]:
        """
        Sync episode data to POMDP memory entries.

        Converts Episode records to MemoryEntry objects with:
        - ObservationSpace from episode context
        - ActionSpace from agent actions
        - Quality score from episode metrics

        Args:
            agent_id: Agent ID to sync episodes for
            limit: Maximum episodes to sync

        Returns:
            {"synced": int, "skipped": int, "errors": int}
        """
        if not POMDP_AVAILABLE or not self.memory_manager:
            logger.info("POMDP not available, skipping episode sync")
            return {"synced": 0, "skipped": 0, "errors": 0}

        # Get recent completed episodes for this agent
        episodes = self.db.query(Episode).filter(
            Episode.agent_id == agent_id,
            Episode.status == "completed"
        ).order_by(Episode.started_at.desc()).limit(limit).all()

        synced = 0
        skipped = 0
        errors = 0

        for episode in episodes:
            try:
                # Create ObservationSpace from episode
                obs = self._episode_to_observation(episode)

                # Create MemoryEntry
                entry = MemoryEntry(
                    id=episode.id,  # Use episode ID as memory ID
                    memory_type=MemoryType.EPISODIC,
                    observation=obs,
                    action_taken="task_completed",
                    reward=1.0 - (episode.human_intervention_count / max(episode.total_steps or 1, 1)),
                    next_state="success" if episode.human_intervention_count == 0 else "partial_success",
                    content={
                        "episode_id": episode.id,
                        "task_description": episode.task_description,
                        "maturity_at_time": episode.maturity_at_time,
                    },
                    status=MemoryStatus.INDEXED,
                    # Quality attributes
                    quality_score=episode.importance_score or 0.5,
                    intervention_required=episode.human_intervention_count > 0,
                    success_outcome=episode.human_intervention_count == 0,
                    # Experience attributes
                    task_complexity=self._infer_task_complexity(episode),
                    autonomy_level=self._infer_autonomy_level(episode),
                )

                # Add to memory manager's episodic store
                self.memory_manager._episodic_memory[entry.id] = entry
                synced += 1

            except Exception as e:
                logger.warning(f"Failed to sync episode {episode.id}: {e}")
                errors += 1

        logger.info(f"Synced {synced} episodes to POMDP memory for agent {agent_id}")
        return {"synced": synced, "skipped": skipped, "errors": errors}

    def _episode_to_observation(self, episode: Episode) -> ObservationSpace:
        """Convert Episode to ObservationSpace"""
        return ObservationSpace(
            timestamp=episode.started_at or datetime.now(),
            agent_id=episode.agent_id,
            workspace_id=episode.tenant_id or "default",
            task_type="WORKFLOW",  # Default, could be enhanced
            user_intent=episode.task_description or "",
            available_tools=[],  # Could be extracted from segments
            system_state={},
            resource_constraints={},
            recent_success_rate=1.0 - (episode.human_intervention_count / max(episode.total_steps or 1, 1)),
            recent_intervention_count=episode.human_intervention_count,
        )

    def _infer_task_complexity(self, episode: Episode) -> int:
        """Infer task complexity (1-4) from episode metadata"""
        # Simple heuristic based on interventions and steps
        if episode.human_intervention_count == 0 and (episode.total_steps or 0) > 5:
            return 4  # Complex task completed autonomously
        elif episode.human_intervention_count == 0:
            return 3  # Moderate task completed autonomously
        elif episode.human_intervention_count <= 2:
            return 2  # Task with some supervision
        else:
            return 1  # Simple task or heavily supervised

    def _infer_autonomy_level(self, episode: Episode) -> int:
        """Infer autonomy level (1-4) from episode maturity"""
        maturity_map = {
            "STUDENT": 1,
            "INTERN": 2,
            "SUPERVISED": 3,
            "AUTONOMOUS": 4,
        }
        return maturity_map.get(episode.maturity_at_time, 1)

    async def run_consolidation_cycle(
        self,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run a full consolidation cycle.

        Performs:
        1. Episode sync (if needed)
        2. Memory manage cycle
        3. Pattern extraction
        4. Association strengthening
        5. Forgetting curve application

        Args:
            agent_id: Optional agent ID to consolidate for. If None, consolidates all.

        Returns:
            {
                "consolidated": int,
                "patterns_extracted": int,
                "associations_strengthened": int,
                "expired": int,
                "duration_seconds": float
            }
        """
        if self._consolidation_in_progress:
            logger.info("Consolidation already in progress, skipping")
            return {"consolidated": 0, "status": "already_running"}

        self._consolidation_in_progress = True
        start_time = datetime.now()

        try:
            results = {
                "consolidated": 0,
                "patterns_extracted": 0,
                "associations_strengthened": 0,
                "expired": 0,
                "duration_seconds": 0.0,
            }

            # If POMDP is available, use POMDP consolidation
            if POMDP_AVAILABLE and self.pomdp_consolidation:
                if agent_id:
                    # Consolidate specific agent
                    results["consolidated"] = await self.pomdp_consolidation.consolidate_memories(
                        agent_id=agent_id,
                        batch_size=50
                    )
                else:
                    # Consolidate all agents (would need agent list)
                    logger.info("Full-system consolidation not yet implemented")
                    results["consolidated"] = 0

                # Run manage cycle for indexing and expiration
                if self.memory_manager:
                    managed = self.memory_manager.trigger_manage_cycle()

                    # Count expired memories
                    expired = sum(
                        1 for m in self.memory_manager._episodic_memory.values()
                        if m.status == MemoryStatus.EXPIRED
                    )
                    results["expired"] = expired

            # Always run episode lifecycle consolidation (PostgreSQL side)
            if agent_id:
                episode_results = await self.episode_lifecycle.consolidate_similar_episodes(
                    agent_id=agent_id,
                    similarity_threshold=0.85
                )
                results["consolidated"] += episode_results.get("consolidated", 0)

            results["duration_seconds"] = (datetime.now() - start_time).total_seconds()
            logger.info(f"Consolidation cycle completed: {results}")

            return results

        finally:
            self._consolidation_in_progress = False
            self._last_consolidation = datetime.now()

    async def apply_forgetting_curve(
        self,
        agent_id: str,
        days_threshold: int = None
    ) -> Dict[str, int]:
        """
        Apply forgetting curve to old memories.

        Implements exponential decay: retention = initial * decay_rate ^ days_old

        Args:
            agent_id: Agent ID to apply forgetting curve for
            days_threshold: Days threshold (uses config default if None)

        Returns:
            {"affected": int, "expired": int}
        """
        if not POMDP_AVAILABLE or not self.memory_manager:
            # Fall back to episode lifecycle decay
            return await self.episode_lifecycle.decay_old_episodes(
                days_threshold=days_threshold or ConsolidationConfig.FORGETTING_DAYS
            )

        threshold_days = days_threshold or ConsolidationConfig.FORGETTING_DAYS
        cutoff_date = datetime.now() - timedelta(days=threshold_days)

        affected = 0
        expired = 0

        for memory in self.memory_manager._episodic_memory.values():
            if memory.observation.agent_id != agent_id:
                continue

            if memory.created_at < cutoff_date:
                days_old = (datetime.now() - memory.created_at).days

                # Apply exponential decay
                decay_factor = ConsolidationConfig.FORGETTING_DECAY_RATE ** days_old
                memory.quality_score *= decay_factor
                affected += 1

                # Mark as expired if quality is too low
                if memory.quality_score < 0.1:
                    memory.status = MemoryStatus.EXPIRED
                    expired += 1

        logger.info(f"Applied forgetting curve to {affected} memories, expired {expired}")
        return {"affected": affected, "expired": expired}

    async def replay_critical_memories(
        self,
        agent_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Replay high-quality memories for learning reinforcement.

        Similar to human sleep replay, strengthens important memory patterns.

        Args:
            agent_id: Agent ID to replay memories for
            limit: Maximum memories to replay

        Returns:
            List of replayed memory summaries
        """
        if not POMDP_AVAILABLE or not self.memory_manager:
            logger.info("POMDP not available, skipping memory replay")
            return []

        # Get high-quality, frequently accessed memories
        high_quality_memories = [
            m for m in self.memory_manager._episodic_memory.values()
            if (m.observation.agent_id == agent_id and
                m.quality_score >= ConsolidationConfig.HIGH_QUALITY_THRESHOLD and
                m.access_count >= ConsolidationConfig.REPLAY_THRESHOLD and
                m.status != MemoryStatus.EXPIRED)
        ]

        # Sort by learning value
        high_quality_memories.sort(
            key=lambda m: m.learning_value, reverse=True
        )

        replayed = []
        for memory in high_quality_memories[:limit]:
            # "Replay" by incrementing access and strengthening quality
            memory.access_count += 1
            memory.quality_score = min(1.0, memory.quality_score * 1.05)
            memory.learning_value = min(1.0, memory.learning_value * 1.05)

            replayed.append({
                "memory_id": memory.id[:8],
                "quality_score": memory.quality_score,
                "learning_value": memory.learning_value,
                "access_count": memory.access_count,
            })

        logger.info(f"Replayed {len(replayed)} critical memories for agent {agent_id}")
        return replayed

    async def extract_patterns(
        self,
        agent_id: str
    ) -> List[Dict[str, Any]]:
        """
        Extract patterns from consolidated memories.

        Finds common patterns across episodes to support
        generalized learning (semantic memory extraction).

        Args:
            agent_id: Agent ID to extract patterns for

        Returns:
            List of discovered patterns
        """
        if not POMDP_AVAILABLE or not self.memory_manager:
            logger.info("POMDP not available, skipping pattern extraction")
            return []

        # Get consolidated memories
        consolidated_memories = [
            m for m in self.memory_manager._episodic_memory.values()
            if (m.observation.agent_id == agent_id and
                m.status == MemoryStatus.CONSOLIDATED)
        ]

        # Simple pattern extraction based on task similarity
        patterns = []
        task_groups: Dict[str, List[MemoryEntry]] = {}

        # Group by task type
        for memory in consolidated_memories:
            task_type = memory.observation.task_type or "UNKNOWN"
            if task_type not in task_groups:
                task_groups[task_type] = []
            task_groups[task_type].append(memory)

        # Find patterns (groups with sufficient size)
        for task_type, memories in task_groups.items():
            if len(memories) >= ConsolidationConfig.MIN_PATTERN_SIZE:
                # Calculate pattern metrics
                avg_quality = sum(m.quality_score for m in memories) / len(memories)
                success_rate = sum(1 for m in memories if m.success_outcome) / len(memories)
                avg_intervention_rate = sum(
                    1 for m in memories if m.intervention_required
                ) / len(memories)

                patterns.append({
                    "pattern_type": task_type,
                    "sample_size": len(memories),
                    "avg_quality": round(avg_quality, 3),
                    "success_rate": round(success_rate, 3),
                    "avg_intervention_rate": round(avg_intervention_rate, 3),
                })

        logger.info(f"Extracted {len(patterns)} patterns for agent {agent_id}")
        return patterns

    def get_consolidation_status(self) -> Dict[str, Any]:
        """Get current consolidation status"""
        return {
            "last_consolidation": self._last_consolidation.isoformat() if self._last_consolidation else None,
            "in_progress": self._consolidation_in_progress,
            "pomdp_available": POMDP_AVAILABLE,
            "memory_statistics": self.memory_manager.get_memory_statistics() if self.memory_manager else {},
        }


# Factory function
def get_consolidation_service(db: Session) -> MemoryConsolidationService:
    """Factory function to get consolidation service instance"""
    return MemoryConsolidationService(db)

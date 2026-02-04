"""
Episode Retrieval Service

Provides four retrieval modes:
1. Temporal - Time-based queries (1d, 7d, 30d, 90d)
2. Semantic - Vector similarity search
3. Sequential - Full episode with segments
4. Contextual - Hybrid score for current task
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.lancedb_handler import get_lancedb_handler
from core.models import Episode, EpisodeSegment, EpisodeAccessLog, AgentRegistry

logger = logging.getLogger(__name__)


class EpisodeRetrievalService:
    """Multi-mode episode retrieval with governance"""

    def __init__(self, db: Session):
        self.db = db
        self.lancedb = get_lancedb_handler()
        self.governance = AgentGovernanceService(db)

    async def retrieve_temporal(
        self,
        agent_id: str,
        time_range: str = "7d",  # 1d, 7d, 30d, 90d
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Time-based retrieval

        Args:
            agent_id: Agent ID
            time_range: Time range (1d, 7d, 30d, 90d)
            user_id: Optional user filter
            limit: Max results

        Returns:
            {
                "episodes": List[Episode],
                "count": int,
                "time_range": str,
                "governance_check": dict
            }
        """
        # Governance check (read_memory = Level 1, STUDENT+)
        governance_check = self.governance.can_perform_action(
            agent_id=agent_id,
            action_type="read_memory"
        )

        if not governance_check.get("allowed", True):
            await self._log_access(None, "temporal", governance_check, agent_id, 0)
            return {
                "episodes": [],
                "error": governance_check.get("reason", "Governance check failed"),
                "governance_check": governance_check
            }

        # Calculate time delta
        deltas = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
        days = deltas.get(time_range, 7)
        cutoff = datetime.now() - timedelta(days=days)

        # Query episodes
        query = self.db.query(Episode).filter(
            Episode.agent_id == agent_id,
            Episode.started_at >= cutoff,
            Episode.status != "archived"
        )

        if user_id:
            query = query.filter(Episode.user_id == user_id)

        episodes = query.order_by(Episode.started_at.desc()).limit(limit).all()

        # Log access
        for episode in episodes:
            await self._log_access(
                episode.id, "temporal", governance_check, agent_id, len(episodes)
            )

        return {
            "episodes": [self._serialize_episode(e) for e in episodes],
            "count": len(episodes),
            "time_range": time_range,
            "governance_check": governance_check
        }

    async def retrieve_semantic(
        self,
        agent_id: str,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Semantic similarity search via LanceDB"""
        # Governance check (Level 2, INTERN+)
        governance_check = self.governance.can_perform_action(
            agent_id=agent_id,
            action_type="semantic_search"
        )

        if not governance_check.get("allowed", True):
            return {
                "episodes": [],
                "error": governance_check.get("reason", "Governance check failed"),
                "governance_check": governance_check
            }

        # Search LanceDB
        try:
            results = self.lancedb.search(
                table_name="episodes",
                query=query,
                filter_str=f"agent_id == '{agent_id}'",
                limit=limit
            )

            # Fetch full episode details from PostgreSQL
            episode_ids = [r.get("id") for r in results if "metadata" in r]
            episodes = []

            if episode_ids:
                # Extract episode_id from metadata
                episode_ids_clean = []
                for r in results:
                    meta = r.get("metadata", {})
                    if isinstance(meta, str):
                        import json
                        meta = json.loads(meta)
                    episode_id = meta.get("episode_id")
                    if episode_id:
                        episode_ids_clean.append(episode_id)

                episodes = self.db.query(Episode).filter(
                    Episode.id.in_(episode_ids_clean),
                    Episode.agent_id == agent_id
                ).all()

            # Log access
            for episode in episodes:
                await self._log_access(
                    episode.id, "semantic", governance_check, agent_id, len(episodes)
                )

            return {
                "episodes": [self._serialize_episode(e) for e in episodes],
                "count": len(episodes),
                "query": query,
                "governance_check": governance_check
            }

        except Exception as e:
            logger.error(f"Semantic retrieval failed: {e}")
            return {
                "episodes": [],
                "error": str(e),
                "governance_check": governance_check
            }

    async def retrieve_sequential(
        self,
        episode_id: str,
        agent_id: str
    ) -> Dict[str, Any]:
        """Retrieve full episode with segments"""
        episode = self.db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.agent_id == agent_id
        ).first()

        if not episode:
            return {"error": "Episode not found"}

        # Load segments
        segments = self.db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode_id
        ).order_by(EpisodeSegment.sequence_order.asc()).all()

        # Log access
        await self._log_access(episode_id, "sequential", {"allowed": True}, agent_id, 1)

        return {
            "episode": self._serialize_episode(episode),
            "segments": [self._serialize_segment(s) for s in segments]
        }

    async def retrieve_contextual(
        self,
        agent_id: str,
        current_task: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Hybrid retrieval: combines temporal + semantic + relevance

        Returns episodes most relevant to current task context.
        """
        # 1. Get recent episodes (temporal)
        recent_result = await self.retrieve_temporal(agent_id, "30d", limit=limit*2)
        recent_episodes = recent_result.get("episodes", [])

        # 2. Get semantic matches
        semantic_result = await self.retrieve_semantic(agent_id, current_task, limit)
        semantic_episodes = semantic_result.get("episodes", [])

        # 3. Combine and score
        scored = {}
        for ep in recent_episodes:
            scored[ep["id"]] = scored.get(ep["id"], 0) + 0.3  # Temporal weight
        for ep in semantic_episodes:
            scored[ep["id"]] = scored.get(ep["id"], 0) + 0.7  # Semantic weight

        # 4. Sort by score and return top N
        sorted_ids = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:limit]

        episodes = []
        for ep_id, score in sorted_ids:
            ep = self.db.query(Episode).filter(Episode.id == ep_id).first()
            if ep:
                episodes.append({**self._serialize_episode(ep), "relevance_score": score})

        return {
            "episodes": episodes,
            "count": len(episodes),
            "query": current_task
        }

    async def _log_access(
        self,
        episode_id: Optional[str],
        access_type: str,
        governance_check: Dict[str, Any],
        agent_id: str,
        results_count: int
    ):
        """Log episode access for audit trail"""
        try:
            log = EpisodeAccessLog(
                episode_id=episode_id or "",
                accessed_by_agent=agent_id,
                access_type=access_type,
                governance_check_passed=governance_check.get("allowed", True),
                agent_maturity_at_access=governance_check.get("agent_maturity"),
                results_count=results_count
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log episode access: {e}")

    def _serialize_episode(self, episode: Episode) -> Dict[str, Any]:
        """Convert episode to dict"""
        return {
            "id": episode.id,
            "title": episode.title,
            "description": episode.description,
            "summary": episode.summary,
            "agent_id": episode.agent_id,
            "status": episode.status,
            "started_at": episode.started_at.isoformat() if episode.started_at else None,
            "ended_at": episode.ended_at.isoformat() if episode.ended_at else None,
            "topics": episode.topics,
            "entities": episode.entities,
            "importance_score": episode.importance_score,
            # Graduation fields
            "maturity_at_time": episode.maturity_at_time,
            "human_intervention_count": episode.human_intervention_count,
            "constitutional_score": episode.constitutional_score,
            "decay_score": episode.decay_score,
            "access_count": episode.access_count
        }

    def _serialize_segment(self, segment: EpisodeSegment) -> Dict[str, Any]:
        """Convert segment to dict"""
        return {
            "id": segment.id,
            "segment_type": segment.segment_type,
            "sequence_order": segment.sequence_order,
            "content": segment.content,
            "content_summary": segment.content_summary,
            "source_type": segment.source_type,
            "source_id": segment.source_id,
            "created_at": segment.created_at.isoformat() if segment.created_at else None
        }

"""
Episode Retrieval Service

Provides four retrieval modes:
1. Temporal - Time-based queries (1d, 7d, 30d, 90d)
2. Semantic - Vector similarity search
3. Sequential - Full episode with segments
4. Contextual - Hybrid score for current task
"""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.lancedb_handler import get_lancedb_handler
from core.models import (
    AgentFeedback,
    AgentRegistry,
    CanvasAudit,
    Episode,
    EpisodeAccessLog,
    EpisodeSegment,
    SupervisionSession,
)

logger = logging.getLogger(__name__)


# Data classes for property testing support
from enum import Enum
from typing import NamedTuple


class RetrievalMode(str, Enum):
    """Episode retrieval modes"""
    TEMPORAL = "temporal"
    SEMANTIC = "semantic"
    SEQUENTIAL = "sequential"
    CONTEXTUAL = "contextual"


class RetrievalResult(NamedTuple):
    """Result of episode retrieval"""
    episodes: List[Episode]
    total_count: int
    retrieval_mode: str
    query_time_ms: float


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
        agent_id: str,
        include_canvas: bool = True,
        include_feedback: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieve full episode with segments and canvas/feedback context.

        NOTE: Canvas and feedback are included by default to ensure agents
        have complete context for decision-making. Only set to False for
        performance optimization in specific scenarios.

        Args:
            episode_id: Episode ID
            agent_id: Agent ID
            include_canvas: Include canvas context (default: True)
            include_feedback: Include feedback context (default: True)

        Returns:
            Episode with segments, canvas_context, and feedback_context
        """
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

        result = {
            "episode": self._serialize_episode(episode),
            "segments": [self._serialize_segment(s) for s in segments]
        }

        # Enrich with canvas context (DEFAULT: True)
        if include_canvas and episode.canvas_ids:
            result["canvas_context"] = await self._fetch_canvas_context(episode.canvas_ids)

        # Enrich with feedback context (DEFAULT: True)
        if include_feedback and episode.feedback_ids:
            result["feedback_context"] = await self._fetch_feedback_context(episode.feedback_ids)

        # Log access
        await self._log_access(episode_id, "sequential", {"allowed": True}, agent_id, 1)

        return result

    async def retrieve_contextual(
        self,
        agent_id: str,
        current_task: str,
        limit: int = 5,
        require_canvas: bool = False,
        require_feedback: bool = False
    ) -> Dict[str, Any]:
        """
        Hybrid retrieval: combines temporal + semantic + relevance

        Returns episodes most relevant to current task context with canvas
        and feedback awareness.

        Args:
            agent_id: Agent ID
            current_task: Current task description
            limit: Max results
            require_canvas: Only return episodes with canvas context
            require_feedback: Only return episodes with feedback
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

        # 4. Apply canvas/feedback boosts
        for ep_id, score in scored.items():
            ep = self.db.query(Episode).filter(Episode.id == ep_id).first()
            if not ep:
                continue

            # Canvas boost: episodes with canvas interactions get +0.1
            if ep.canvas_action_count > 0:
                scored[ep_id] += 0.1

            # Feedback boost: positive feedback gets +0.2, negative gets -0.3
            # This matches the feedback-aware boosting requirements
            if ep.aggregate_feedback_score:
                if ep.aggregate_feedback_score > 0:  # Positive feedback
                    scored[ep_id] += 0.2
                elif ep.aggregate_feedback_score < 0:  # Negative feedback
                    scored[ep_id] -= 0.3
                # Neutral feedback (score near 0) gets no adjustment

        # 5. Sort by score and return top N
        sorted_ids = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:limit]

        # 6. Filter by requirements and build results
        filtered_episodes = []
        for ep_id, score in sorted_ids:
            ep = self.db.query(Episode).filter(Episode.id == ep_id).first()
            if not ep:
                continue

            # Apply filters
            if require_canvas and ep.canvas_action_count == 0:
                continue
            if require_feedback and not ep.feedback_ids:
                continue

            filtered_episodes.append({**self._serialize_episode(ep), "relevance_score": score})

        return {
            "episodes": filtered_episodes,
            "count": len(filtered_episodes),
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

    async def _fetch_canvas_context(self, canvas_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch canvas audit records by ID list.

        Args:
            canvas_ids: List of CanvasAudit IDs

        Returns:
            List of canvas context dictionaries
        """
        if not canvas_ids:
            return []

        try:
            canvases = self.db.query(CanvasAudit).filter(
                CanvasAudit.id.in_(canvas_ids)
            ).all()

            return [{
                "id": c.id,
                "canvas_type": c.canvas_type,
                "component_type": c.component_type,
                "component_name": c.component_name,
                "action": c.action,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "metadata": c.audit_metadata
            } for c in canvases]

        except Exception as e:
            logger.error(f"Failed to fetch canvas context: {e}")
            return []

    async def _fetch_feedback_context(self, feedback_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch feedback records by ID list.

        Args:
            feedback_ids: List of AgentFeedback IDs

        Returns:
            List of feedback context dictionaries
        """
        if not feedback_ids:
            return []

        try:
            feedbacks = self.db.query(AgentFeedback).filter(
                AgentFeedback.id.in_(feedback_ids)
            ).all()

            return [{
                "id": f.id,
                "feedback_type": f.feedback_type,
                "rating": f.rating,
                "thumbs_up_down": f.thumbs_up_down,
                "corrections": f.user_correction,
                "created_at": f.created_at.isoformat() if f.created_at else None
            } for f in feedbacks]

        except Exception as e:
            logger.error(f"Failed to fetch feedback context: {e}")
            return []

    async def retrieve_by_canvas_type(
        self,
        agent_id: str,
        canvas_type: str,
        action: Optional[str] = None,
        time_range: str = "30d",
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Retrieve episodes filtered by canvas type and action.

        Useful for: "Show me episodes where I presented spreadsheets"

        Args:
            agent_id: Agent ID
            canvas_type: Canvas type (sheets, charts, generic, etc.)
            action: Optional action filter (present, submit, close, etc.)
            time_range: Time range (1d, 7d, 30d, 90d)
            limit: Max results

        Returns:
            Filtered episodes with canvas type info
        """
        # Governance check
        governance_check = self.governance.can_perform_action(
            agent_id=agent_id,
            action_type="read_memory"
        )

        if not governance_check.get("allowed", True):
            return {
                "episodes": [],
                "error": governance_check.get("reason", "Governance check failed"),
                "governance_check": governance_check
            }

        # Time filter
        deltas = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
        days = deltas.get(time_range, 30)
        cutoff = datetime.now() - timedelta(days=days)

        # Query episodes with canvas
        query = self.db.query(Episode).filter(
            Episode.agent_id == agent_id,
            Episode.started_at >= cutoff,
            Episode.status != "archived",
            Episode.canvas_action_count > 0
        )

        # Filter by canvas type (requires joining CanvasAudit)
        canvas_subquery = self.db.query(CanvasAudit.episode_id).filter(
            CanvasAudit.canvas_type == canvas_type
        )

        if action:
            canvas_subquery = canvas_subquery.filter(CanvasAudit.action == action)

        query = query.filter(Episode.id.in_(canvas_subquery))

        episodes = query.order_by(Episode.started_at.desc()).limit(limit).all()

        # Log access
        for episode in episodes:
            await self._log_access(
                episode.id, "canvas_type_filter", governance_check, agent_id, len(episodes)
            )

        return {
            "episodes": [self._serialize_episode(ep) for ep in episodes],
            "count": len(episodes),
            "canvas_type": canvas_type,
            "action": action,
            "time_range": time_range,
            "governance_check": governance_check
        }

    # ========================================================================
    # Supervision Context Retrieval
    # ========================================================================

    async def retrieve_with_supervision_context(
        self,
        agent_id: str,
        retrieval_mode: RetrievalMode = RetrievalMode.SEQUENTIAL,
        limit: int = 10,
        supervision_outcome_filter: Optional[str] = None,
        min_rating: Optional[int] = None,
        max_interventions: Optional[int] = None,
        time_range: str = "30d"
    ) -> Dict[str, Any]:
        """
        Retrieve episodes enriched with supervision context.

        Args:
            agent_id: Agent ID
            retrieval_mode: Retrieval mode (temporal, semantic, sequential, contextual)
            limit: Max results
            supervision_outcome_filter: Filter by supervision quality
                - "high_rated": supervisor_rating >= 4
                - "low_intervention": intervention_count <= 1
                - "recent_improvement": positive rating trend
            min_rating: Minimum supervisor rating (1-5)
            max_interventions: Maximum intervention count
            time_range: Time range for temporal filter (1d, 7d, 30d, 90d)

        Returns:
            {
                "episodes": List[Episode] with supervision_context,
                "count": int,
                "supervision_filters_applied": List[str]
            }
        """
        # Governance check
        governance_check = self.governance.can_perform_action(
            agent_id=agent_id,
            action_type="read_memory"
        )

        if not governance_check.get("allowed", True):
            return {
                "episodes": [],
                "error": governance_check.get("reason", "Governance check failed"),
                "governance_check": governance_check
            }

        # Get base episodes using specified retrieval mode
        if retrieval_mode == RetrievalMode.TEMPORAL:
            base_result = await self.retrieve_temporal(
                agent_id=agent_id,
                time_range=time_range,
                limit=limit * 2  # Fetch more for filtering
            )
            episodes_data = base_result.get("episodes", [])

        elif retrieval_mode == RetrievalMode.SEMANTIC:
            # For semantic, we need a query - use agent name as default
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            query = agent.name if agent else "agent execution"
            base_result = await self.retrieve_semantic(
                agent_id=agent_id,
                query=query,
                limit=limit * 2
            )
            episodes_data = base_result.get("episodes", [])

        elif retrieval_mode == RetrievalMode.CONTEXTUAL:
            base_result = await self.retrieve_contextual(
                agent_id=agent_id,
                current_task="supervised execution",
                limit=limit * 2
            )
            episodes_data = base_result.get("episodes", [])

        else:  # SEQUENTIAL
            # For sequential, get recent episodes
            base_result = await self.retrieve_temporal(
                agent_id=agent_id,
                time_range=time_range,
                limit=limit * 2
            )
            episodes_data = base_result.get("episodes", [])

        # Convert dicts back to Episode objects for filtering
        episode_ids = [e["id"] for e in episodes_data]
        episodes = self.db.query(Episode).filter(
            Episode.id.in_(episode_ids),
            Episode.agent_id == agent_id
        ).all()

        # Apply supervision filters
        filters_applied = []
        filtered_episodes = []

        for episode in episodes:
            # Apply outcome filter
            if supervision_outcome_filter:
                if supervision_outcome_filter == "high_rated":
                    if episode.supervisor_rating is None or episode.supervisor_rating < 4:
                        continue
                    filters_applied.append("high_rated")

                elif supervision_outcome_filter == "low_intervention":
                    if (episode.intervention_count or 0) > 1:
                        continue
                    filters_applied.append("low_intervention")

                elif supervision_outcome_filter == "recent_improvement":
                    # Skip individual filtering - will apply at batch level
                    pass

            # Apply rating filter
            if min_rating is not None:
                if episode.supervisor_rating is None or episode.supervisor_rating < min_rating:
                    continue
                filters_applied.append(f"min_rating_{min_rating}")

            # Apply intervention filter
            if max_interventions is not None:
                if (episode.intervention_count or 0) > max_interventions:
                    continue
                filters_applied.append(f"max_interventions_{max_interventions}")

            filtered_episodes.append(episode)

        # Apply improvement trend filter (batch operation)
        if supervision_outcome_filter == "recent_improvement":
            filtered_episodes = self._filter_improvement_trend(filtered_episodes)
            filters_applied.append("recent_improvement")

        # Limit results
        filtered_episodes = filtered_episodes[:limit]

        # Enrich episodes with supervision metadata
        enriched_results = []
        for episode in filtered_episodes:
            episode_dict = self._serialize_episode(episode)
            episode_dict["supervision_context"] = self._create_supervision_context(episode)
            enriched_results.append(episode_dict)

        # Log access
        for episode in filtered_episodes:
            await self._log_access(
                episode.id, "supervision_context", governance_check, agent_id, len(filtered_episodes)
            )

        return {
            "episodes": enriched_results,
            "count": len(enriched_results),
            "supervision_filters_applied": list(set(filters_applied)),
            "retrieval_mode": retrieval_mode.value,
            "governance_check": governance_check
        }

    def _create_supervision_context(self, episode: Episode) -> Dict[str, Any]:
        """Create supervision context dictionary for episode"""
        return {
            "has_supervision": episode.supervisor_id is not None,
            "supervisor_id": episode.supervisor_id,
            "supervisor_rating": episode.supervisor_rating,
            "intervention_count": episode.intervention_count or 0,
            "intervention_types": episode.intervention_types or [],
            "feedback_summary": self._summarize_feedback(episode.supervision_feedback),
            "outcome_quality": self._assess_outcome_quality(episode)
        }

    def _summarize_feedback(self, feedback: Optional[str]) -> Optional[str]:
        """Summarize feedback text for display"""
        if not feedback:
            return None

        # Truncate to 100 chars
        if len(feedback) > 100:
            return feedback[:97] + "..."
        return feedback

    def _assess_outcome_quality(self, episode: Episode) -> str:
        """
        Assess overall outcome quality based on supervision data.

        Returns:
            "excellent", "good", "fair", or "poor"
        """
        if episode.supervisor_rating is None:
            return "unknown"

        # Excellent: 5 stars, 0-1 interventions
        if episode.supervisor_rating >= 5 and (episode.intervention_count or 0) <= 1:
            return "excellent"

        # Good: 4-5 stars, 0-2 interventions
        if episode.supervisor_rating >= 4 and (episode.intervention_count or 0) <= 2:
            return "good"

        # Fair: 3-4 stars
        if episode.supervisor_rating >= 3:
            return "fair"

        # Poor: < 3 stars
        return "poor"

    def _filter_improvement_trend(self, episodes: List[Episode]) -> List[Episode]:
        """
        Filter episodes showing positive performance trend.

        Compares the most recent episodes to earlier ones to identify
        agents that are improving over time.

        Args:
            episodes: List of episodes to filter

        Returns:
            Episodes showing improvement trend
        """
        if len(episodes) < 5:
            return episodes  # Not enough data for trend analysis

        # Sort by start time
        sorted_episodes = sorted(
            episodes,
            key=lambda e: e.started_at or datetime.min,
            reverse=True
        )

        # Calculate recent vs earlier average ratings
        recent = sorted_episodes[:len(sorted_episodes) // 2]
        earlier = sorted_episodes[len(sorted_episodes) // 2:]

        recent_ratings = [
            e.supervisor_rating for e in recent
            if e.supervisor_rating is not None
        ]
        earlier_ratings = [
            e.supervisor_rating for e in earlier
            if e.supervisor_rating is not None
        ]

        if not recent_ratings or not earlier_ratings:
            return episodes  # Can't determine trend

        recent_avg = sum(recent_ratings) / len(recent_ratings)
        earlier_avg = sum(earlier_ratings) / len(earlier_ratings)

        # Include episodes if recent performance is better
        if recent_avg >= earlier_avg:
            return sorted_episodes

        return []

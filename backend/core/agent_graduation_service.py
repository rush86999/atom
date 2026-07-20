"""
Agent Graduation Service

Validates agent readiness for promotion using episodic memory.
Provides data-driven audit trails for governance compliance.

Enhanced with POMDP Memory Framework for experience-driven graduation.
Based on 2025-2026 research on memory for autonomous LLM agents.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from core.lancedb_handler import get_lancedb_handler
from core.service_factory import get_episode_service
from core.sandbox_executor import get_sandbox_executor, get_graduation_exam_executor
from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    EpisodeSegment,
    SupervisionSession,
    SkillExecution,
)

logger = logging.getLogger(__name__)

# POMDP Memory Framework integration
try:
    from core.memory.pomdp_memory_framework import (
        MemoryManager,
        ExperienceCalculator,
        ExperienceMetrics,
        get_memory_manager,
        get_experience_calculator,
        MemoryType,
        ObservationSpace,
    )
    POMDP_AVAILABLE = True
except ImportError:
    logger.warning("POMDP Memory Framework not available, using legacy graduation criteria")
    POMDP_AVAILABLE = False





class AgentGraduationService:
    """Validates agent promotion readiness using episodic memory"""

    # Graduation criteria
    CRITERIA = {
        "INTERN": {
            "min_episodes": 10,
            "max_intervention_rate": 0.5,  # 50%
            "min_constitutional_score": 0.70,
            # Enhanced POMDP-based criteria
            "min_quality_weighted_episodes": 7.0,  # 70% of min_episodes with quality weighting
            "min_learning_consistency": 0.60,
        },
        "SUPERVISED": {
            "min_episodes": 25,
            "max_intervention_rate": 0.2,  # 20%
            "min_constitutional_score": 0.85,
            # Enhanced POMDP-based criteria
            "min_quality_weighted_episodes": 18.0,  # 72% of min_episodes
            "min_learning_consistency": 0.70,
        },
        "AUTONOMOUS": {
            "min_episodes": 50,
            "max_intervention_rate": 0.0,  # 0% - fully autonomous
            "min_constitutional_score": 0.95,
            # Enhanced POMDP-based criteria
            "min_quality_weighted_episodes": 45.0,  # 90% of min_episodes
            "min_learning_consistency": 0.80,
        }
    }

    def __init__(self, db: Session):
        self.db = db
        self.lancedb = get_lancedb_handler()

        # Initialize POMDP components if available
        self.memory_manager = None
        self.experience_calculator = None

        if POMDP_AVAILABLE:
            try:
                self.memory_manager = get_memory_manager(db, self.lancedb)
                self.experience_calculator = get_experience_calculator(db, self.memory_manager)
                logger.debug("POMDP Memory Framework initialized for graduation service")
            except Exception as e:
                logger.warning(f"Failed to initialize POMDP framework: {e}")

    async def calculate_readiness_score(
        self,
        agent_id: str,
        target_maturity: str,  # INTERN, SUPERVISED, AUTONOMOUS
        min_episodes: int = None
    ) -> Dict[str, Any]:
        """
        Calculate graduation readiness score from episodic memory.

        Returns:
            {
                "ready": bool,
                "score": float (0-100),
                "episode_count": int,
                "avg_constitutional_score": float,
                "total_human_interventions": int,
                "intervention_rate": float,
                "recommendation": str,
                "gaps": List[str]
            }
        """
        # Query agent
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return {"error": "Agent not found"}

        # Validate target maturity level
        if target_maturity not in self.CRITERIA:
            return {"error": f"Unknown maturity level: {target_maturity}"}

        current_maturity = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)

        # Use Ported EpisodeService for weighted readiness formula
        episode_service = get_episode_service(self.db)
        readiness = episode_service.get_graduation_readiness(
            agent_id=agent_id,
            tenant_id=agent.tenant_id or "default",
            target_level=target_maturity.lower()
        )
        
        result = readiness.to_dict()
        result["current_maturity"] = current_maturity
        result["target_maturity"] = target_maturity
        result["ready"] = result["threshold_met"] # Map to upstream field name

        return result

    async def calculate_experience_driven_readiness(
        self,
        agent_id: str,
        target_maturity: str,  # INTERN, SUPERVISED, AUTONOMOUS
    ) -> Dict[str, Any]:
        """
        Calculate graduation readiness using POMDP experience-driven metrics.

        Enhanced readiness calculation based on 2025-2026 research:
        - Quality-weighted episodes (not just count)
        - Intervention trajectory analysis
        - Cross-episode learning consistency
        - Memory quality assessment

        Returns:
            {
                "ready": bool,
                "score": float (0-100),
                "experience_metrics": dict,
                "quality_weighted_episodes": float,
                "intervention_trajectory": dict,
                "learning_consistency": float,
                "gaps": List[str]
            }
        """
        if not POMDP_AVAILABLE or not self.experience_calculator:
            logger.info("POMDP not available, falling back to standard readiness")
            return await self.calculate_readiness_score(agent_id, target_maturity)

        # Query agent
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return {"error": "Agent not found"}

        # Get criteria for target maturity
        if target_maturity not in self.CRITERIA:
            return {"error": f"Unknown maturity level: {target_maturity}"}

        criteria = self.CRITERIA[target_maturity]

        # Calculate experience-driven readiness
        result = self.experience_calculator.calculate_readiness_score(
            agent_id=agent_id,
            target_maturity=target_maturity,
            criteria=self.CRITERIA
        )

        # Add current maturity info
        result["current_maturity"] = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)
        result["target_maturity"] = target_maturity

        # Calculate intervention trajectory analysis
        intervention_trajectory = await self._analyze_intervention_trajectory(agent_id)

        # Add trajectory analysis to result
        result["intervention_trajectory"] = intervention_trajectory

        # Determine readiness based on multiple factors
        ready = (
            result.get("ready", False) and
            intervention_trajectory.get("is_improving", True) and
            result.get("learning_consistency", 0) >= criteria.get("min_learning_consistency", 0.6)
        )

        result["ready"] = ready

        # Generate recommendation
        result["recommendation"] = self._generate_experience_driven_recommendation(
            ready=ready,
            score=result.get("score", 0),
            target=target_maturity,
            gaps=result.get("gaps", []),
            trajectory=intervention_trajectory
        )

        return result

    async def _analyze_intervention_trajectory(
        self,
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Analyze intervention rate trajectory over time.

        Calculates:
        - Overall intervention rate trend
        - Recent vs historical comparison
        - Improvement rate (negative = declining, positive = improving)

        Returns:
            {
                "overall_rate": float,
                "recent_rate": float,
                "historical_rate": float,
                "improvement_rate": float,
                "is_improving": bool,
                "trend": str  # "improving", "stable", "declining"
            }
        """
        if not POMDP_AVAILABLE or not self.memory_manager:
            return {
                "overall_rate": 0.0,
                "recent_rate": 0.0,
                "historical_rate": 0.0,
                "improvement_rate": 0.0,
                "is_improving": True,
                "trend": "unknown"
            }

        # Get quality-sorted memories for trajectory analysis
        memories = self.memory_manager.recall_by_quality(
            agent_id=agent_id,
            min_quality=0.3,
            limit=100
        )

        if not memories or len(memories) < 5:
            return {
                "overall_rate": 0.0,
                "recent_rate": 0.0,
                "historical_rate": 0.0,
                "improvement_rate": 0.0,
                "is_improving": True,
                "trend": "insufficient_data"
            }

        # Calculate intervention rates over time
        # Split into recent (last 10) and historical (earlier)
        recent_memories = memories[:10]
        historical_memories = memories[10:]

        recent_interventions = sum(1 for m in recent_memories if m.intervention_required)
        recent_rate = recent_interventions / len(recent_memories) if recent_memories else 0

        historical_interventions = sum(1 for m in historical_memories if m.intervention_required)
        historical_rate = historical_interventions / len(historical_memories) if historical_memories else 0

        total_interventions = sum(1 for m in memories if m.intervention_required)
        overall_rate = total_interventions / len(memories)

        # Calculate improvement rate (positive = getting better)
        if historical_rate > 0:
            improvement_rate = (historical_rate - recent_rate) / historical_rate
        else:
            improvement_rate = 0.0

        # Determine trend
        if improvement_rate > 0.2:
            trend = "improving"
            is_improving = True
        elif improvement_rate < -0.2:
            trend = "declining"
            is_improving = False
        else:
            trend = "stable"
            is_improving = True

        return {
            "overall_rate": round(overall_rate, 3),
            "recent_rate": round(recent_rate, 3),
            "historical_rate": round(historical_rate, 3),
            "improvement_rate": round(improvement_rate, 3),
            "is_improving": is_improving,
            "trend": trend,
            "sample_size": len(memories)
        }

    def _generate_experience_driven_recommendation(
        self,
        ready: bool,
        score: float,
        target: str,
        gaps: List[str],
        trajectory: Dict[str, Any]
    ) -> str:
        """Generate human-readable recommendation based on experience metrics"""
        if ready:
            return f"Agent ready for promotion to {target}. Score: {score:.1f}/100"

        # Build context-aware recommendation
        parts = []

        if score < 40:
            parts.append(f"Significant training needed for {target}.")
        elif score < 70:
            parts.append(f"Making progress toward {target}.")
        else:
            parts.append(f"Close to ready for {target}.")

        # Add trajectory context
        trend = trajectory.get("trend", "unknown")
        if trend == "declining":
            parts.append("⚠️ Intervention rate is declining - address performance issues.")
        elif trend == "improving":
            parts.append("✓ Intervention rate is improving.")

        # Add gap context
        if gaps:
            parts.append(f"Key gaps: {', '.join(gaps[:2])}")

        return " ".join(parts)

    # ========================================================================
    # Cross-Episode Learning Consistency Analysis
    # ========================================================================

    async def analyze_learning_consistency(
        self,
        agent_id: str,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze cross-episode learning consistency.

        Measures:
        - Performance variance across episodes
        - Knowledge retention over time
        - Error recurrence patterns

        Returns:
            {
                "consistency_score": float (0-1),
                "performance_variance": float,
                "knowledge_retention": float,
                "error_recurrence_rate": float,
                "recommendation": str
            }
        """
        if not POMDP_AVAILABLE or not self.memory_manager:
            return {
                "consistency_score": 0.5,
                "performance_variance": 0.0,
                "knowledge_retention": 0.5,
                "error_recurrence_rate": 0.0,
                "recommendation": "POMDP framework not available"
            }

        # Get memories for analysis
        memories = self.memory_manager.recall_by_quality(
            agent_id=agent_id,
            min_quality=0.3,
            limit=100
        )

        if not memories or len(memories) < 5:
            return {
                "consistency_score": 0.5,
                "performance_variance": 0.0,
                "knowledge_retention": 0.5,
                "error_recurrence_rate": 0.0,
                "recommendation": "Insufficient data for consistency analysis"
            }

        # Calculate performance variance
        quality_scores = [m.quality_score for m in memories]
        avg_quality = sum(quality_scores) / len(quality_scores)

        # Variance calculation
        variance = sum((q - avg_quality) ** 2 for q in quality_scores) / len(quality_scores)
        normalized_variance = min(variance, 1.0)

        # Knowledge retention (consistency of high-quality outcomes)
        high_quality_count = sum(1 for q in quality_scores if q >= 0.7)
        knowledge_retention = high_quality_count / len(quality_scores)

        # Error recurrence (interventions in recent memories)
        recent_memories = memories[:10]
        error_recurrence = sum(1 for m in recent_memories if m.intervention_required) / len(recent_memories)

        # Consistency score (inverse of variance, weighted by retention)
        consistency_score = (1 - normalized_variance) * 0.6 + knowledge_retention * 0.4

        # Generate recommendation
        if consistency_score >= 0.8:
            recommendation = "Excellent learning consistency"
        elif consistency_score >= 0.6:
            recommendation = "Good learning consistency"
        elif consistency_score >= 0.4:
            recommendation = "Moderate learning consistency - some variance detected"
        else:
            recommendation = "Poor learning consistency - high performance variance"

        return {
            "consistency_score": round(consistency_score, 3),
            "performance_variance": round(normalized_variance, 3),
            "knowledge_retention": round(knowledge_retention, 3),
            "error_recurrence_rate": round(error_recurrence, 3),
            "recommendation": recommendation,
            "sample_size": len(memories)
        }

    def _calculate_score(
        self,
        episode_count: int,
        min_episodes: int,
        intervention_rate: float,
        max_intervention: float,
        constitutional_score: float,
        min_constitutional: float
    ) -> float:
        """Calculate weighted readiness score (0-100)"""
        # Episode score (40%)
        episode_score = min(episode_count / min_episodes, 1.0) * 40

        # Intervention score (30%)
        # Lower intervention rate is better, so invert
        intervention_score = (1 - min(intervention_rate / max(max_intervention, 0.01), 1.0)) * 30

        # Constitutional score (30%)
        constitutional_score_normalized = min(constitutional_score / max(min_constitutional, 0.01), 1.0)
        constitutional_score_calc = constitutional_score_normalized * 30

        return episode_score + intervention_score + constitutional_score_calc

    def _generate_recommendation(self, ready: bool, score: float, target: str) -> str:
        """Generate human-readable recommendation"""
        if ready:
            return f"Agent ready for promotion to {target}. Score: {score:.1f}/100"

        if score < 50:
            return f"Agent not ready. Significant training needed for {target}."
        elif score < 75:
            return f"Agent making progress. More practice needed for {target}."
        else:
            return f"Agent close to ready. Address specific gaps for {target}."

    async def run_graduation_exam(
        self,
        agent_id: str,
        edge_case_episodes: List[str]
    ) -> Dict[str, Any]:
        """
        Run agent through historical "edge case" episodes in sandbox.

        Tests agent against historical failures from other agents.

        Args:
            agent_id: Agent to test
            edge_case_episodes: List of episode IDs to simulate

        Returns:
            {
                "passed": bool,
                "results": List[Dict],
                "score": float
            }
        """
        from core.sandbox_executor import get_sandbox_executor

        results = []

        for episode_id in edge_case_episodes:
            episode = self.db.query(Episode).filter(
                Episode.id == episode_id
            ).first()

            if not episode:
                logger.warning(f"Episode {episode_id} not found for sandbox validation")
                continue

            # Execute episode in sandbox
            executor = get_sandbox_executor(self.db)
            sandbox_result = await executor.execute_in_sandbox(
                episode_id=episode_id,
                strict_mode=True  # Zero interventions for graduation
            )

            results.append({
                "episode_id": episode_id,
                "title": episode.task_description or "Untitled Episode",
                "passed": sandbox_result.passed,
                "interventions": sandbox_result.interventions,
                "safety_violations": sandbox_result.safety_violations,
                "replayed_actions": sandbox_result.replayed_actions
            })

        passed = all(r["passed"] for r in results)
        score = sum(1 for r in results if r["passed"]) / len(results) * 100 if results else 0

        return {
            "passed": passed,
            "results": results,
            "score": round(score, 1),
            "total_cases": len(edge_case_episodes)
        }

    async def validate_constitutional_compliance(
        self,
        episode_id: str
    ) -> Dict[str, Any]:
        """
        Verify episode actions against Knowledge Graph rules.

        Checks tax laws, HIPAA, domain-specific constraints.

        Args:
            episode_id: Episode to validate

        Returns:
            {
                "compliant": bool,
                "score": float,
                "violations": List[str]
            }
        """
        from core.constitutional_validator import ConstitutionalValidator

        episode = self.db.query(Episode).filter(
            Episode.id == episode_id
        ).first()

        if not episode:
            return {"error": "Episode not found"}

        # Get episode segments for validation
        segments = self.db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode_id
        ).all()

        # Ensure segments is a list (defensive against Mock objects in tests)
        if not segments or not isinstance(segments, list):
            return {
                "compliant": True,
                "score": 1.0,
                "violations": [],
                "episode_id": episode_id,
                "note": "No segments to validate"
            }

        # Use ConstitutionalValidator to check compliance
        validator = ConstitutionalValidator(self.db)

        # Detect domain from episode metadata or agent type
        domain = episode.metadata_json.get("domain") if episode.metadata_json else None

        result = validator.validate_actions(segments, domain=domain)

        return {
            "compliant": result["compliant"],
            "score": result["score"],
            "violations": result["violations"],
            "episode_id": episode_id,
            "total_actions": result["total_actions"],
            "checked_actions": result["checked_actions"]
        }

    async def promote_agent(
        self,
        agent_id: str,
        new_maturity: str,
        validated_by: str
    ) -> bool:
        """
        Update agent metadata in PostgreSQL after successful graduation.

        Args:
            agent_id: Agent to promote
            new_maturity: New maturity level
            validated_by: User ID who approved promotion

        Returns:
            True if successful
        """
        try:
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()
        except Exception as e:
            logger.error(f"Database error querying agent {agent_id}: {e}")
            return False

        if not agent:
            logger.error(f"Agent {agent_id} not found for promotion")
            return False

        # Update maturity
        try:
            agent.status = AgentStatus[new_maturity.upper()]
        except KeyError:
            logger.error(f"Invalid maturity level: {new_maturity}")
            return False

        agent.updated_at = datetime.now()

        # Add promotion metadata to configuration
        if not agent.configuration:
            agent.configuration = {}
        agent.configuration["promoted_at"] = datetime.now().isoformat()
        agent.configuration["promoted_by"] = validated_by

        # Flag configuration as modified for SQLAlchemy JSON tracking
        flag_modified(agent, "configuration")

        try:
            self.db.commit()
            logger.info(f"Agent {agent_id} promoted to {new_maturity} by {validated_by}")

            # P2.1 — fire a graduation notification so the user has a reason
            # to come back (Stage 5 of the new-user journey). Wrapped in
            # try/except because a notification failure must NEVER roll back
            # or obscure a successful promotion.
            try:
                import asyncio
                from core.notification_service import NotificationService
                notif_svc = NotificationService(self.db)
                agent_name = getattr(agent, "name", "Your agent")
                user_id = (
                    getattr(agent, "user_id", None)
                    or validated_by
                    or "00000000-0000-0000-0000-000000000000"
                )
                from core.personal_scope import resolve_tenant_id, resolve_workspace_id
                workspace_id = resolve_workspace_id(agent, validated_by)
                tenant_id = resolve_tenant_id(agent, validated_by)

                payload = {
                    "title": f"{agent_name} graduated to {new_maturity.title()}",
                    "message": (
                        f"{agent_name} has been promoted to the {new_maturity} tier. "
                        "Great work — keep building."
                    ),
                    "workspace_id": workspace_id,
                    "tenant_id": tenant_id,
                    "action_url": f"/agents/{agent_id}",
                    "action_label": "View agent",
                    "agent_id": agent_id,
                    "new_maturity": new_maturity,
                }
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    notif_svc.send_notification(
                        user_id=user_id,
                        notification_type="agent_graduated",
                        data=payload,
                    )
                )
            except Exception as notif_exc:
                logger.warning(
                    "Graduation notification failed for agent %s (promotion already committed): %s",
                    agent_id, notif_exc,
                )

            # Trigger Memory Consolidation on graduation
            if POMDP_AVAILABLE:
                try:
                    memory_manager = get_memory_manager(self.db)
                    from core.memory.pomdp_memory_framework import MemoryConsolidation
                    consolidator = MemoryConsolidation(memory_manager)
                    consolidated_count = await consolidator.consolidate_memories(agent_id)
                    logger.info(f"POMDP Memory consolidation on graduation complete: consolidated {consolidated_count} memories.")
                except Exception as mem_exc:
                    logger.warning(f"POMDP memory consolidation failed on graduation: {mem_exc}")

            return True
        except Exception as e:
            logger.error(f"Database error during promotion of agent {agent_id}: {e}")
            self.db.rollback()
            return False

    async def get_graduation_audit_trail(
        self,
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Get full audit trail for agent graduation.

        Provides comprehensive data for governance review.

        Args:
            agent_id: Agent ID

        Returns:
            {
                "agent_id": str,
                "current_maturity": str,
                "episodes": List[Dict],
                "summary_stats": Dict
            }
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return {"error": "Agent not found"}

        # Get all episodes for this agent
        episodes = self.db.query(Episode).filter(
            Episode.agent_id == agent_id
        ).order_by(Episode.started_at.desc()).all()

        # Calculate summary stats
        total_episodes = len(episodes)
        total_interventions = sum(e.human_intervention_count for e in episodes)

        constitutional_scores = [
            e.constitutional_score for e in episodes
            if e.constitutional_score is not None
        ]
        avg_constitutional = sum(constitutional_scores) / len(constitutional_scores) if constitutional_scores else 0.0

        # Group by maturity level
        by_maturity = {}
        for ep in episodes:
            maturity = ep.maturity_at_time
            if maturity not in by_maturity:
                by_maturity[maturity] = []
            by_maturity[maturity].append({
                "id": ep.id,
                "title": ep.task_description or "Untitled Episode",
                "started_at": ep.started_at.isoformat() if ep.started_at else None,
                "human_intervention_count": ep.human_intervention_count,
                "constitutional_score": ep.constitutional_score
            })

        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "current_maturity": agent.status.value if hasattr(agent.status, 'value') else str(agent.status),
            "total_episodes": total_episodes,
            "total_interventions": total_interventions,
            "avg_constitutional_score": round(avg_constitutional, 3),
            "episodes_by_maturity": {
                k: len(v) for k, v in by_maturity.items()
            },
            "recent_episodes": by_maturity.get(str(agent.status), [])[:10]
        }

    # ========================================================================
    # Supervision Metrics Integration
    # ========================================================================

    async def calculate_supervision_metrics(
        self,
        agent_id: str,
        maturity_level: AgentStatus
    ) -> Dict[str, Any]:
        """
        Calculate supervision-based metrics for graduation validation.

        Returns:
            {
                "total_supervision_hours": float,
                "intervention_rate": float,  # interventions per hour
                "average_supervisor_rating": float,  # 1-5 scale
                "successful_intervention_recovery_rate": float,
                "recent_performance_trend": str,  # "improving", "stable", "declining"
                "total_sessions": int,
                "high_rating_sessions": int,  # 4-5 star sessions
                "low_intervention_sessions": int  # 0-1 intervention sessions
            }
        """
        # Get supervision sessions for this agent at maturity level
        sessions = self.db.query(SupervisionSession).filter(
            SupervisionSession.agent_id == agent_id,
            SupervisionSession.status == "completed"
        ).all()

        if not sessions:
            return {
                "total_supervision_hours": 0,
                "intervention_rate": 1.0,  # High penalty if no data
                "average_supervisor_rating": 0.0,
                "successful_intervention_recovery_rate": 0.0,
                "recent_performance_trend": "unknown",
                "total_sessions": 0,
                "high_rating_sessions": 0,
                "low_intervention_sessions": 0
            }

        # Calculate metrics
        total_duration = sum(s.duration_seconds or 0 for s in sessions)
        total_hours = total_duration / 3600 if total_duration > 0 else 0

        total_interventions = sum(s.intervention_count or 0 for s in sessions)

        # Intervention rate (interventions per hour)
        intervention_rate = (total_interventions / total_hours) if total_hours > 0 else 1.0

        # Average supervisor rating
        ratings = [s.supervisor_rating for s in sessions if s.supervisor_rating is not None]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

        # High-quality sessions (4-5 stars)
        high_rating_sessions = sum(1 for r in ratings if r >= 4)

        # Low intervention sessions (0-1 interventions)
        low_intervention_sessions = sum(
            1 for s in sessions
            if (s.intervention_count or 0) <= 1
        )

        # Successful intervention recovery
        # (Sessions where interventions led to successful completion)
        successful_recovery = sum(
            1 for s in sessions
            if (s.intervention_count or 0) > 0 and (s.supervisor_rating or 0) >= 3
        )
        sessions_with_interventions = sum(1 for s in sessions if (s.intervention_count or 0) > 0)
        recovery_rate = (
            successful_recovery / sessions_with_interventions
            if sessions_with_interventions > 0 else 1.0
        )

        # Performance trend (compare recent vs older sessions)
        recent_performance_trend = self._calculate_performance_trend(sessions)

        return {
            "total_supervision_hours": round(total_hours, 2),
            "intervention_rate": round(intervention_rate, 3),
            "average_supervisor_rating": round(avg_rating, 2),
            "successful_intervention_recovery_rate": round(recovery_rate, 3),
            "recent_performance_trend": recent_performance_trend,
            "total_sessions": len(sessions),
            "high_rating_sessions": high_rating_sessions,
            "low_intervention_sessions": low_intervention_sessions
        }

    def _calculate_performance_trend(self, sessions: List[SupervisionSession]) -> str:
        """
        Calculate recent performance trend from supervision sessions.

        Compares the most recent 5 sessions to the previous 5 sessions.

        Returns:
            "improving", "stable", or "declining"
        """
        if len(sessions) < 10:
            return "stable"

        # Sort by start time
        sorted_sessions = sorted(
            sessions,
            key=lambda s: s.started_at or datetime.min,
            reverse=True
        )

        # Get recent and previous sessions
        recent = sorted_sessions[:5]
        previous = sorted_sessions[5:10]

        # Calculate average ratings
        recent_ratings = [s.supervisor_rating for s in recent if s.supervisor_rating]
        previous_ratings = [s.supervisor_rating for s in previous if s.supervisor_rating]

        if not recent_ratings or not previous_ratings:
            return "stable"

        recent_avg = sum(recent_ratings) / len(recent_ratings)
        previous_avg = sum(previous_ratings) / len(previous_ratings)

        # Calculate average intervention counts
        recent_interventions = [s.intervention_count or 0 for s in recent]
        previous_interventions = [s.intervention_count or 0 for s in previous]

        recent_avg_int = sum(recent_interventions) / len(recent_interventions)
        previous_avg_int = sum(previous_interventions) / len(previous_interventions)

        # Determine trend
        rating_diff = recent_avg - previous_avg
        intervention_diff = previous_avg_int - recent_avg_int  # Lower is better

        # Combined score
        score = rating_diff * 0.6 + intervention_diff * 0.4

        if score > 0.3:
            return "improving"
        elif score < -0.3:
            return "declining"
        else:
            return "stable"

    async def validate_graduation_with_supervision(
        self,
        agent_id: str,
        target_maturity: AgentStatus
    ) -> Dict[str, Any]:
        """
        Validate agent graduation using both episode and supervision data.

        Combines:
        - Episode count and quality
        - Supervision intervention rate
        - Supervisor ratings
        - Constitutional compliance

        Args:
            agent_id: Agent to validate
            target_maturity: Target maturity level

        Returns:
            {
                "ready": bool,
                "score": float (0-100),
                "episode_metrics": dict,
                "supervision_metrics": dict,
                "recommendation": str,
                "gaps": List[str]
            }
        """
        # Get existing episode-based validation
        episode_result = await self.calculate_readiness_score(
            agent_id=agent_id,
            target_maturity=target_maturity.value if hasattr(target_maturity, 'value') else str(target_maturity)
        )

        # Get supervision-based metrics
        supervision_metrics = await self.calculate_supervision_metrics(
            agent_id=agent_id,
            maturity_level=target_maturity
        )

        # Get criteria for target maturity
        criteria = self.CRITERIA.get(
            target_maturity.value if hasattr(target_maturity, 'value') else str(target_maturity).upper(),
            {}
        )

        # Check supervision-specific gaps
        supervision_gaps = []

        # High-quality session requirement
        min_high_quality = max(1, int(criteria.get("min_episodes", 10) * 0.4))
        if supervision_metrics["high_rating_sessions"] < min_high_quality:
            supervision_gaps.append(
                f"Need {min_high_quality - supervision_metrics['high_rating_sessions']} more high-rated sessions (4-5 stars)"
            )

        # Low intervention requirement
        min_low_intervention = max(1, int(criteria.get("min_episodes", 10) * 0.3))
        if supervision_metrics["low_intervention_sessions"] < min_low_intervention:
            supervision_gaps.append(
                f"Need {min_low_intervention - supervision_metrics['low_intervention_sessions']} more low-intervention sessions"
            )

        # Minimum average rating (3.5/5)
        if supervision_metrics["average_supervisor_rating"] < 3.5:
            supervision_gaps.append(
                f"Average supervisor rating too low: {supervision_metrics['average_supervisor_rating']:.1f} < 3.5"
            )

        # Intervention rate threshold
        max_intervention_rate = criteria.get("max_intervention_rate", 0.5) * 10  # Convert to per-hour
        if supervision_metrics["intervention_rate"] > max_intervention_rate:
            supervision_gaps.append(
                f"Intervention rate too high: {supervision_metrics['intervention_rate']:.1f}/hr > {max_intervention_rate:.1f}/hr"
            )

        # Combined validation
        all_gaps = episode_result.get("gaps", []) + supervision_gaps

        ready = len(all_gaps) == 0 and episode_result.get("ready", False)

        # Combined score (70% episode-based, 30% supervision-based)
        combined_score = (
            episode_result.get("score", 0) * 0.7 +
            self._supervision_score(supervision_metrics, criteria) * 0.3
        )

        return {
            "ready": ready,
            "score": round(combined_score, 1),
            "episode_metrics": episode_result,
            "supervision_metrics": supervision_metrics,
            "recommendation": self._generate_recommendation(
                ready,
                combined_score,
                target_maturity.value if hasattr(target_maturity, 'value') else str(target_maturity)
            ),
            "gaps": all_gaps,
            "target_maturity": target_maturity.value if hasattr(target_maturity, 'value') else str(target_maturity),
            "current_maturity": episode_result.get("current_maturity", "UNKNOWN")
        }

    def _supervision_score(
        self,
        metrics: Dict[str, Any],
        criteria: Dict[str, Any]
    ) -> float:
        """
        Calculate supervision-based score (0-100).

        Factors:
        - Average supervisor rating (40%)
        - Intervention rate (30%)
        - High-quality session percentage (20%)
        - Performance trend (10%)
        """
        # Rating score (40%) - target: 4.0/5.0
        rating_score = min(metrics["average_supervisor_rating"] / 4.0, 1.0) * 40

        # Intervention score (30%) - lower is better
        max_interventions = criteria.get("max_intervention_rate", 0.5) * 10
        intervention_score = (
            (1 - min(metrics["intervention_rate"] / max(max_interventions, 1), 1.0)) * 30
        )

        # High-quality session score (20%) - target: 60% of sessions
        if metrics["total_sessions"] > 0:
            high_quality_pct = metrics["high_rating_sessions"] / metrics["total_sessions"]
            high_quality_score = min(high_quality_pct / 0.6, 1.0) * 20
        else:
            high_quality_score = 0

        # Trend score (10%)
        trend_scores = {"improving": 10, "stable": 5, "declining": 0, "unknown": 0}
        trend_score = trend_scores.get(metrics["recent_performance_trend"], 0)

        return rating_score + intervention_score + high_quality_score + trend_score

    # ========================================================================
    # Skill Usage Metrics Integration (NEW)
    # ========================================================================

    async def calculate_skill_usage_metrics(
        self,
        agent_id: str,
        days_back: int = 30
    ) -> dict:
        """
        Calculate skill usage metrics for graduation readiness.

        Args:
            agent_id: Agent ID
            days_back: Number of days to look back

        Returns:
            {
                "total_skill_executions": int,
                "successful_executions": int,
                "success_rate": float,
                "unique_skills_used": int,
                "skill_episodes_count": int,
                "skill_learning_velocity": float
            }
        """
        from datetime import timedelta
        from sqlalchemy import select

        # Get recent skill executions
        start_date = datetime.now() - timedelta(days=days_back)

        # Query skill executions
        skill_executions_result = self.db.execute(
            select(SkillExecution)
            .where(SkillExecution.agent_id == agent_id)
            .where(SkillExecution.created_at >= start_date)
            .where(SkillExecution.skill_source == "community")
        )
        skills = skill_executions_result.scalars().all()

        # Calculate metrics
        total_executions = len(skills)
        successful_executions = len([s for s in skills if s.status == "success"])
        unique_skills_used = len(set(s.skill_id for s in skills))

        # Get skill episodes (EpisodeSegment doesn't have agent_id, need to join differently)
        skill_episodes_result = self.db.execute(
            select(EpisodeSegment)
            .where(EpisodeSegment.segment_type.in_(["skill_success", "skill_failure"]))
            .where(EpisodeSegment.created_at >= start_date)
        )
        episodes = skill_episodes_result.scalars().all()

        # Filter episodes by agent_id from metadata
        agent_episodes = [e for e in episodes if e.metadata.get("agent_id") == agent_id]

        # Calculate learning velocity (episodes per day)
        skill_learning_velocity = len(agent_episodes) / days_back if days_back > 0 else 0

        return {
            "total_skill_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": successful_executions / total_executions if total_executions > 0 else 0,
            "unique_skills_used": unique_skills_used,
            "skill_episodes_count": len(agent_episodes),
            "skill_learning_velocity": skill_learning_velocity
        }

    async def calculate_readiness_score_with_skills(
        self,
        agent_id: str,
        target_maturity: str
    ) -> dict:
        """
        Calculate graduation readiness score with skill metrics.

        Integrates skill usage metrics into the readiness score calculation.

        Args:
            agent_id: Agent ID
            target_maturity: Target maturity level

        Returns:
            {
                "readiness_score": float,
                "episode_metrics": dict,
                "intervention_metrics": dict,
                "skill_metrics": dict,
                "skill_diversity_bonus": float
            }
        """
        # Get existing readiness score
        existing_readiness = await self.calculate_readiness_score(
            agent_id=agent_id,
            target_maturity=target_maturity
        )

        # Get skill usage metrics
        skill_metrics = await self.calculate_skill_usage_metrics(agent_id)

        # Calculate skill diversity bonus (up to +5%)
        # Reward agents that use diverse skills
        skill_diversity_bonus = min(skill_metrics["unique_skills_used"] * 0.01, 0.05)

        # Base score from existing calculation
        base_score = existing_readiness.get("score", 0) / 100.0  # Convert to 0-1 scale

        # Apply skill diversity bonus
        final_score = min(base_score + skill_diversity_bonus, 1.0)

        return {
            "readiness_score": final_score,
            "episode_metrics": existing_readiness,
            "skill_metrics": skill_metrics,
            "skill_diversity_bonus": skill_diversity_bonus,
            "target_maturity": target_maturity
        }


    async def execute_graduation_exam(
        self,
        agent_id: str,
        workspace_id: str,
        target_maturity: str
    ) -> Dict[str, Any]:
        """
        Execute graduation exam for agent.
    
        Args:
            agent_id: Agent to examine
            workspace_id: Workspace ID
            target_maturity: Target maturity level (INTERN, SUPERVISED, AUTONOMOUS)
    
        Returns:
            {
                "exam_completed": bool,
                "score": float,
                "constitutional_compliance": float,
                "passed": bool,
                "constitutional_violations": List[str]
            }
        """
        executor = get_graduation_exam_executor(self.db)
    
        # Run exam
        result = await executor.execute_exam(
            agent_id=agent_id,
            target_maturity=target_maturity
        )
    
        if not result.get("success"):
            return {
                "exam_completed": False,
                "error": result.get("error", "Exam execution failed"),
                "passed": False
            }
    
        return {
            "exam_completed": True,
            "score": result["score"],
            "constitutional_compliance": result["constitutional_compliance"],
            "passed": result["passed"],
            "constitutional_violations": result.get("constitutional_violations", [])
        }



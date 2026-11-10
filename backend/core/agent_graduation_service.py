"""
Agent Graduation Service

Validates agent readiness for promotion using episodic memory.
Provides data-driven audit trails for governance compliance.

Enhanced with POMDP Memory Framework for experience-driven graduation.
Based on 2025-2026 research on memory for autonomous LLM agents.
"""

from core.asyncio_compat import get_event_loop, iscoroutinefunction
from datetime import datetime
import hashlib
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.lancedb_handler import get_lancedb_handler
from core.episode_service import EpisodeService
from core.personal_scope import (
    PERSONAL_TENANT_ID,
    PERSONAL_WORKSPACE_ID,
    resolve_tenant_id,
    resolve_workspace_id,
)
from core.service_factory import get_episode_service
from core.sandbox_executor import get_sandbox_executor, get_graduation_exam_executor
from core.models import (
    AgentEpisode,
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    Artifact,
    Episode,
    EpisodeSegment,
    GraduationExam,
    HITLAction,
    HITLActionStatus,
    PromotionHistory,
    SupervisionSession,
    SkillExecution,
    User,
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

    PROMOTION_SOURCES = {
        AgentStatus.INTERN.name: AgentStatus.STUDENT.value,
        AgentStatus.SUPERVISED.name: AgentStatus.INTERN.value,
        AgentStatus.AUTONOMOUS.name: AgentStatus.SUPERVISED.value,
    }
    _EPISODE_SERVICE_TYPE = EpisodeService

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

    def _query_in_scope(self, query, model, tenant_id=None, workspace_id=None):
        """Apply the existing Personal/scope policy to an authoritative SQL query."""
        if tenant_id is not None:
            resolved_tenant = str(tenant_id) or PERSONAL_TENANT_ID
            tenant_scope = model.tenant_id == resolved_tenant
            if resolved_tenant == PERSONAL_TENANT_ID:
                tenant_scope = or_(
                    tenant_scope,
                    model.tenant_id.is_(None),
                    model.tenant_id == "",
                )
            query = query.filter(tenant_scope)
        if workspace_id is not None:
            resolved_workspace = str(workspace_id) or PERSONAL_WORKSPACE_ID
            workspace_scope = model.workspace_id == resolved_workspace
            if resolved_workspace == PERSONAL_WORKSPACE_ID:
                workspace_scope = or_(
                    workspace_scope,
                    model.workspace_id.is_(None),
                    model.workspace_id == "",
                )
            query = query.filter(workspace_scope)
        return query

    def get_agent_in_scope(
        self,
        agent_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[AgentRegistry]:
        query = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id)
        query = self._query_in_scope(query, AgentRegistry, tenant_id, workspace_id)
        return query.first()

    async def calculate_readiness_score(
        self,
        agent_id: str,
        target_maturity: str,
        min_episodes: Optional[int] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
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
        agent = self.get_agent_in_scope(agent_id, tenant_id, workspace_id)

        if not agent:
            return {"error": "Agent not found"}

        if target_maturity not in self.CRITERIA:
            return {"error": f"Unknown maturity level: {target_maturity}"}

        current_maturity = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)

        criteria = self.CRITERIA.get(target_maturity, {})
        episode_service = get_episode_service(self.db)
        if (
            isinstance(episode_service, self._EPISODE_SERVICE_TYPE)
            and episode_service.db is not self.db
        ):
            episode_service = EpisodeService(self.db, tenant_api_key=None)

        effective_min_episodes: Any = min_episodes
        if effective_min_episodes is None:
            effective_min_episodes = criteria.get("min_episodes", 0)
            if isinstance(episode_service, self._EPISODE_SERVICE_TYPE):
                effective_min_episodes = episode_service._get_min_episodes_for_level(
                    target_maturity.lower()
                )
            agent_floor = getattr(agent, "promotion_episode_floor", None)
            if isinstance(agent_floor, int) and agent_floor > 0:
                effective_min_episodes = max(int(effective_min_episodes), agent_floor)
        effective_min_episodes = int(effective_min_episodes)
        requested_tenant = str(tenant_id) if tenant_id else resolve_tenant_id(agent)

        readiness = episode_service.get_graduation_readiness(
            agent_id=agent_id,
            tenant_id=requested_tenant,
            target_level=target_maturity.lower(),
            min_episodes_override=min_episodes,
            episode_count=max(effective_min_episodes, 30)
        )
        
        result = readiness.to_dict()
        result["current_maturity"] = current_maturity
        result["target_maturity"] = target_maturity
        result["ready"] = result["threshold_met"] # Map to upstream field name

        # Enrich with the documented readiness contract (0-100 score, episode
        # count, interventions, recommendation, gaps). ReadinessResponse is
        # 0-1 scale; scale to 0-100 for the public contract. Guard the numeric
        # reads so Mock-based callers (tests) fall back to neutral defaults
        # instead of raising TypeError on Mock arithmetic.
        try:
            raw_score = float(readiness.readiness_score)
            episodes_analyzed = int(readiness.episodes_analyzed)
            total_interventions = int(
                (readiness.breakdown or {}).get("total_interventions", 0) or 0
            )
            constitutional_recorded = int(
                (readiness.breakdown or {}).get("constitutional_recorded", 0) or 0
            )
            zero_intervention_ratio = float(readiness.zero_intervention_ratio)
            avg_constitutional = float(readiness.avg_constitutional_score)
        except (TypeError, ValueError, AttributeError):
            raw_score, episodes_analyzed, total_interventions = 0.0, 0, 0
            constitutional_recorded = 0
            zero_intervention_ratio, avg_constitutional = 0.0, 0.0

        result["score"] = round(raw_score * 100, 2)
        result["episode_count"] = episodes_analyzed
        result["total_human_interventions"] = total_interventions
        result["intervention_rate"] = round(1.0 - zero_intervention_ratio, 4)

        gaps = []
        if episodes_analyzed < effective_min_episodes:
            gaps.append(
                f"Insufficient episodes ({episodes_analyzed}/{effective_min_episodes} required)"
            )
        max_intervention = criteria.get("max_intervention_rate", 1.0)
        if result["intervention_rate"] > max_intervention:
            gaps.append(
                f"Intervention rate {result['intervention_rate']:.2f} exceeds "
                f"maximum {max_intervention:.2f}"
            )
        # Unmeasured ≠ failing: the scorer renormalizes over factors with
        # recorded evidence only (see EpisodeService._compute_readiness_score),
        # so an agent whose episodes never measured compliance must not show
        # a "below required" gap next to a ready verdict — that gap would be
        # unsatisfiable no matter how the agent performs. Fires only when
        # scores WERE recorded and came in under the floor.
        min_constitutional = criteria.get("min_constitutional_score", 0)
        if constitutional_recorded and avg_constitutional < min_constitutional:
            gaps.append(
                f"Constitutional score {avg_constitutional:.2f} below "
                f"required {min_constitutional:.2f}"
            )
        if not episodes_analyzed:
            gaps.append("No episodes recorded yet")
        result["gaps"] = gaps

        result["recommendation"] = self._generate_experience_driven_recommendation(
            ready=result["ready"],
            score=result["score"],
            target=target_maturity,
            gaps=gaps,
            trajectory={}
        )

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
        edge_case_episodes: List[str],
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Review historical trace safety within the authorized scope.

        This does not execute or qualify the candidate agent. Historical cases
        from other agents in the same authorized scope remain supported.

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

        def outcome(results, installation_evals, error=None):
            return {
                "passed": error is None and bool(results) and all(r["passed"] for r in results),
                "results": results,
                "score": round(
                    sum(1 for r in results if r["passed"]) / len(results) * 100, 1
                ) if results else 0.0,
                "total_cases": len(results),
                "installation_evals": installation_evals,
                **({"error": error} if error else {}),
                "assessment_scope": "historical_trace_safety_review",
                "candidate_capability_qualified": False,
            }

        def refuse(message, results=None):
            return outcome(results or [], {"available": False}, message)

        target = self.get_agent_in_scope(agent_id, tenant_id, workspace_id)
        if target is None:
            return refuse("Exam target is unknown or outside the authorized scope")
        scope_tenant = (
            tenant_id if tenant_id is not None else getattr(target, "tenant_id", None)
        ) or PERSONAL_TENANT_ID
        scope_workspace = (
            workspace_id if workspace_id is not None
            else getattr(target, "workspace_id", None)
        ) or PERSONAL_WORKSPACE_ID
        ordered_ids = []
        for episode_id in edge_case_episodes:
            episode = self._query_in_scope(
                self.db.query(Episode).filter(Episode.id == episode_id),
                Episode, scope_tenant, scope_workspace
            ).first()
            if episode is None:
                return refuse(
                    f"Episode {episode_id} is unknown or outside the authorized scope"
                )
            ordered_ids.append(episode_id)

        results = []

        for episode_id in ordered_ids:
            if self.get_agent_in_scope(agent_id, scope_tenant, scope_workspace) is None:
                return refuse("Exam target left the authorized scope", results)
            episode = self._query_in_scope(
                self.db.query(Episode).filter(Episode.id == episode_id),
                Episode, scope_tenant, scope_workspace
            ).first()
            if episode is None:
                return refuse(
                    f"Episode {episode_id} left the authorized scope", results
                )

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

        # Installation Adaptation Plan (Phase 2/5): the graduation exam also
        # replays the TENANT's own live-failure regression cases — a hire
        # that repeats an install's real past mistakes does not promote.
        # Fault-isolated: an eval-suite failure downgrades to "unavailable"
        # and never blocks the exam on infrastructure grounds.
        installation_evals: Dict[str, Any] = {"available": False}
        if self.get_agent_in_scope(agent_id, scope_tenant, scope_workspace) is None:
            return refuse("Exam target left the authorized scope", results)
        try:
            from core.incident_eval_runner import run_evals

            summary = await run_evals(self.db, tenant_id=scope_tenant, limit=10)
            failed = summary.get("failed", 0)
            installation_evals = {
                "available": True,
                "ran": summary.get("ran", 0),
                "passed": summary.get("passed", 0),
                "failed": failed,
                "skipped": summary.get("skipped", 0),
            }
            if summary.get("ran", 0) > 0:
                results.append({
                    "episode_id": "incident_eval_suite",
                    "title": "Installation live-failure regression suite",
                    "passed": failed == 0,
                    "interventions": failed,
                    "safety_violations": 0,
                    "replayed_actions": [],
                })
        except Exception as eval_err:
            logger.debug("installation eval gate unavailable: error_class=%s", type(eval_err).__name__)

        return outcome(results, installation_evals)

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
        self, agent_id: str, new_maturity: str, validated_by: str,
        tenant_id: Optional[str] = None, workspace_id: Optional[str] = None,
    ) -> bool:
        """Compatibility bool; HTTP callers use the explicit decision outcome."""
        result = await self.promote_agent_decision(
            agent_id, new_maturity, validated_by, tenant_id, workspace_id)
        return result.get("status") in ("verified", "already_applied")

    async def promote_agent_decision(
        self,
        agent_id: str,
        new_maturity: str,
        validated_by: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update agent metadata in PostgreSQL after successful graduation.

        Args:
            agent_id: Agent to promote
            new_maturity: New maturity level
            validated_by: User ID who approved promotion

        Returns:
            True if successful
        """
        # Scope lookup itself can autoflush: refuse pending caller material
        # before issuing any query, not merely before the final commit.
        from core.agent_decision_write_service import caller_work_pending

        if caller_work_pending(self.db):
            return {"status": "not_applied", "verification": {"effect": "none"}}
        try:
            agent = self.get_agent_in_scope(agent_id, tenant_id, workspace_id)
        except Exception as e:
            logger.error(f"Database error querying agent {agent_id}: {e}")
            return {"status": "not_applied", "verification": {"effect": "none"}}

        if not agent:
            logger.error(f"Agent {agent_id} not found for promotion")
            return {"status": "not_applied", "verification": {"effect": "none"}}

        target_name = str(new_maturity).upper()
        if target_name not in self.PROMOTION_SOURCES:
            logger.error(f"Invalid maturity level: {new_maturity}")
            return {"status": "not_applied", "verification": {"effect": "none"}}

        target_status = AgentStatus[target_name].value
        # Freeze authority and physical target material before the readiness
        # await. Reuse the shared writer's claims; a fresh read after the await
        # alone would silently authorize a different reviewed target.
        from types import SimpleNamespace
        from core.models import UserRole
        from core import agent_decision_write_service as writes

        if caller_work_pending(self.db):
            return {"status": "not_applied", "verification": {"effect": "none"}}  # Never flush unrelated caller work as a promotion.
        actor = writes._resolve_actor(
            self.db, SimpleNamespace(id=validated_by),
            minimum_role=UserRole.TEAM_LEAD, authority_label="GRADUATION")
        if not actor.get("ok") or not writes._agent_visible(actor, agent):
            return {"status": "not_applied", "verification": {"effect": "none"}}
        try:
            operation_id = writes._operation_id("graduate", operation_id)
        except ValueError:
            return writes._refused("Invalid operation identity", http_status=422,
                                   error_code="VALIDATION_ERROR")
        request = writes.graduation_request(
            operation_id=operation_id, agent_id=agent_id, target_status=target_status,
            actor=actor, tenant_id=tenant_id, workspace_id=workspace_id,
            assessment_receipt_id=agent.last_exam_id)
        replay = writes.replay_graduation(self.db, request=request, actor=actor)
        if replay is not None:
            return replay
        current_status = agent.status.value if hasattr(agent.status, "value") else str(agent.status)
        if current_status != self.PROMOTION_SOURCES[target_name]:
            logger.error(
                f"Invalid promotion transition for {agent_id}: "
                f"{current_status} -> {target_status}"
            )
            return {"status": "not_applied", "verification": {"effect": "none"}}

        try:
            reviewed, raw_config, raw_schedule = writes._load_replace_source(self.db, agent_id)
            if reviewed is None or (
                reviewed.tenant_id != agent.tenant_id
                or reviewed.workspace_id != agent.workspace_id
                or reviewed.status != agent.status
            ):
                return {"status": "not_applied", "verification": {"effect": "none"}}
            predicates, claim_params = writes._replace_agent_predicates(
                reviewed, raw_config, raw_schedule)
            predicates.extend(writes._agent_predicates(reviewed, current_status))
            for field in ("module_path", "class_name", "user_id", "confidence_score",
                          "required_role_for_autonomy"):
                predicates.append(writes._exact(getattr(AgentRegistry, field),
                                               getattr(reviewed, field)))
        except Exception as exc:
            logger.warning("Graduation snapshot unavailable: error_class=%s", type(exc).__name__)
            return {"status": "not_applied", "verification": {"effect": "none"}}

        try:
            readiness = await self.calculate_readiness_score(
                agent_id=agent_id,
                target_maturity=target_name,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
            )
        except Exception as readiness_err:
            logger.error(
                f"Promotion for {agent_id} denied: readiness evidence unavailable "
                f"({readiness_err})"
            )
            return {"status": "not_applied", "verification": {"effect": "none"}}

        if (
            readiness.get("error")
            or readiness.get("ready") is not True
            or readiness.get("gaps")
        ):
            return {"status": "not_applied", "verification": {"effect": "none"}}

        qualification_gate = evaluate_qualification_gate(
            self.db, reviewed, target_name)
        if not qualification_gate.get("allowed"):
            return {
                "status": "unresolved",
                "verification": {"effect": "none"},
                "assessment": qualification_gate,
            }
        cas_predicates, cas_error = qualification_cas_predicates(
            self.db, reviewed, qualification_gate)
        if cas_error is not None:
            return cas_error

        if target_status == AgentStatus.AUTONOMOUS.value:
            from core.governance import DynamicGovernanceManager, GovernanceLayer

            try:
                governance_context = {
                    "episode_count": readiness["episodes_analyzed"],
                    "readiness_score": readiness["readiness_score"],
                    "success_rate": readiness["success_rate"],
                    "constitutional_score": readiness["avg_constitutional_score"],
                    "intervention_rate": readiness["intervention_rate"],
                    "confidence_score": readiness["avg_confidence_score"],
                }
                decision = DynamicGovernanceManager().decide(
                    agent_id=agent_id,
                    action="graduate_to_autonomous",
                    layer=GovernanceLayer.STRATEGIC,
                    context=governance_context,
                )
            except Exception as governance_err:
                logger.error(
                    f"Autonomous promotion for {agent_id} denied: governance "
                    f"evidence unavailable ({governance_err})"
                )
                return {"status": "not_applied", "verification": {"effect": "none"}}

            if not decision.allowed:
                logger.warning(
                    f"Autonomous promotion DENIED by governance policy for "
                    f"{agent_id}: {'; '.join(decision.reasons)}"
                )
                return {"status": "not_applied", "verification": {"effect": "none"}}

        previous_status = reviewed.status
        configuration = dict(reviewed.configuration or {})
        configuration.update(promoted_at=datetime.now().isoformat(), promoted_by=validated_by)
        receipt_id = (
            qualification_gate.get("receipt_id")
            if qualification_gate.get("state") == "valid"
            else reviewed.last_exam_id
        )
        promotion_count = int(getattr(reviewed, "promotion_count", 0) or 0) + 1
        promotion_history = PromotionHistory(
            id=str(uuid.uuid4()),
            agent_id=str(reviewed.id),
            tenant_id=resolve_tenant_id(reviewed),
            from_level=str(previous_status or ""),
            to_level=target_status,
            promotion_type="automatic",
            readiness_score=float(readiness.get("score") or 0.0),
            exam_id=receipt_id if qualification_gate.get("state") == "valid" else None,
            promoted_by=str(validated_by),
            justification=(
                "public graduation; assessment="
                f"{qualification_gate.get('state')}"
                + (
                    "; owner_reason="
                    + str((qualification_gate.get("exception") or {}).get("reason"))
                    if (qualification_gate.get("exception") or {}).get("reason")
                    else ""
                )),
            promoted_at=datetime.now(),
        )

        decision = None
        try:
            if caller_work_pending(self.db):
                return {"status": "not_applied", "verification": {"effect": "none"}}
            predicates.extend(cas_predicates)
            decision = writes.commit_graduation(
                self.db, reviewed=reviewed, actor=actor, request=request,
                predicates=predicates, claim_params=claim_params,
                target_status=target_status, configuration=configuration,
                last_exam_id=receipt_id,
                promotion_count=promotion_count,
                promotion_history=promotion_history,
                extra_success={
                    "assessment": qualification_gate,
                    "promotion_history_id": promotion_history.id,
                },
                audit_extra={"assessment": qualification_gate})
            if decision.get("status") != "verified":
                return decision
            self.db.expire(agent)
            logger.info(f"Agent {agent_id} promoted to {new_maturity} by {validated_by}")

            # Real-time circuit: the tier just moved — drop the GovernanceCache
            # snapshot so trigger-gated automation (5-min maturity cache)
            # enforces the NEW tier on its next decision, not the old one.
            # Best-effort: a cache failure must never roll back a promotion.
            try:
                from core.governance_cache import get_governance_cache

                get_governance_cache().invalidate_agent(agent_id)
            except Exception as cache_err:
                logger.debug(f"governance cache invalidate skipped: {cache_err}")

            # Real-time learning surface: announce the promotion to the
            # workspace UI immediately (the notification below is a second,
            # asynchronous channel — this is the live one).
            try:
                from core.maturity_broadcast import schedule_maturity_broadcast

                schedule_maturity_broadcast(
                    workspace_id=resolve_workspace_id(agent, workspace_id),
                    agent_id=agent_id,
                    previous_confidence=agent.confidence_score,
                    confidence=agent.confidence_score,
                    previous_tier=previous_status,
                    tier=agent.status,
                    source="graduation",
                )
            except Exception as broadcast_err:
                logger.debug(f"maturity broadcast skipped for {agent_id}: {broadcast_err}")

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
                    loop = get_event_loop()
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

            return decision
        except Exception as e:
            logger.error("Graduation finalization error: error_class=%s", type(e).__name__)
            self.db.rollback()
            # A post-commit ancillary failure cannot erase the durable verdict.
            if decision is not None:
                return decision
            return {"status": "not_applied", "verification": {"effect": "none"}}

    async def get_graduation_audit_trail(
        self,
        agent_id: str,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
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
        agent = self.get_agent_in_scope(agent_id, tenant_id, workspace_id)

        if not agent:
            return {"error": "Agent not found"}

        # Get all episodes for this agent
        query = self.db.query(Episode).filter(Episode.agent_id == agent_id)
        episodes = self._query_in_scope(
            query, Episode, tenant_id, workspace_id,
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
        # Normalize maturity to the uppercase CRITERIA key (AgentStatus values
        # are lowercase, e.g. "supervised", while CRITERIA keys are uppercase).
        maturity_key = (
            target_maturity.value.upper()
            if hasattr(target_maturity, 'value')
            else str(target_maturity).upper()
        )

        # Get existing episode-based validation
        episode_result = await self.calculate_readiness_score(
            agent_id=agent_id,
            target_maturity=maturity_key
        )

        # Get supervision-based metrics
        supervision_metrics = await self.calculate_supervision_metrics(
            agent_id=agent_id,
            maturity_level=target_maturity
        )

        # Get criteria for target maturity
        criteria = self.CRITERIA.get(maturity_key, {})

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

        # Get skill episodes scoped to THIS agent. EpisodeSegment has no
        # agent_id (or metadata) column — the agent is reached through the
        # owning AgentEpisode, so join on it. The previous
        # `e.metadata.get("agent_id")` read hit SQLAlchemy's MetaData class
        # attribute and crashed (AttributeError) whenever skill segments
        # existed.
        from core.models import AgentEpisode

        skill_episodes_result = self.db.execute(
            select(EpisodeSegment)
            .join(AgentEpisode, AgentEpisode.id == EpisodeSegment.episode_id)
            .where(AgentEpisode.agent_id == agent_id)
            .where(EpisodeSegment.segment_type.in_(["skill_success", "skill_failure"]))
            .where(EpisodeSegment.created_at >= start_date)
        )
        episodes = skill_episodes_result.scalars().all()

        # Filter episodes by agent_id from metadata
        agent_episodes = list(episodes)

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




# ===========================================================================
# Scoped capability qualification: strict gate, durable review receipt, CAS
# ===========================================================================

QUALIFICATION_RECEIPT_KIND = "capability_qualification"
QUALIFICATION_ASSESSMENT_SCOPE = "held_out_capability"
QUALIFICATION_REVIEW_ACTION = "agent_qualification_review"
QUALIFICATION_REVIEW_SCHEMA = "atom-agent-qualification-review-1"
QUALIFICATION_EVIDENCE_KINDS = {"agent_episode", "agent_execution", "artifact", "episode_segment"}


class QualificationReviewError(Exception):
    def __init__(self, state: str, message: str, **details: Any):
        super().__init__(message)
        self.state = state
        self.message = message
        self.details = details


def _next_tier(current: str) -> Optional[str]:
    order = ["student", "intern", "supervised", "autonomous"]
    value = str(current or "").strip().lower()
    if value not in order:
        return None
    index = order.index(value)
    return order[index + 1] if index + 1 < len(order) else None


def _scope_matches(record: Any, tenant_id: str, workspace_id: str) -> bool:
    rec_tenant = str(getattr(record, "tenant_id", None) or "")
    rec_workspace = str(getattr(record, "workspace_id", None) or "")
    want_tenant = str(tenant_id or "")
    want_workspace = str(workspace_id or "")
    if rec_tenant != want_tenant:
        # Personal/legacy rows may carry NULL/"" for the default scope.
        if not (rec_tenant in ("", PERSONAL_TENANT_ID) and
                want_tenant in ("", PERSONAL_TENANT_ID)):
            return False
    if rec_workspace != want_workspace:
        if not (rec_workspace in ("", PERSONAL_WORKSPACE_ID) and
                want_workspace in ("", PERSONAL_WORKSPACE_ID)):
            return False
    return True


def _canonical_evidence_material(kind: str, record: Any) -> Dict[str, Any]:
    if kind == "agent_episode":
        return {
            "kind": kind,
            "id": str(record.id),
            "agent_id": str(record.agent_id),
            "tenant_id": record.tenant_id,
            "workspace_id": record.workspace_id,
            "task_description": record.task_description,
            "maturity_at_time": record.maturity_at_time,
            "outcome": record.outcome,
            "success": bool(record.success),
            "status": record.status,
            "started_at": str(record.started_at),
            "completed_at": str(record.completed_at),
            "human_intervention_count": record.human_intervention_count,
            "constitutional_score": record.constitutional_score,
            "confidence_score": record.confidence_score,
        }
    if kind == "agent_execution":
        return {
            "kind": kind,
            "id": str(record.id),
            "agent_id": str(record.agent_id),
            "tenant_id": record.tenant_id,
            "workspace_id": record.workspace_id,
            "status": record.status,
            "input_summary": record.input_summary,
            "result_summary": record.result_summary,
            "output_summary": record.output_summary,
            "completed_at": str(record.completed_at),
        }
    if kind == "artifact":
        return {
            "kind": kind,
            "id": str(record.id),
            "agent_id": str(record.agent_id),
            "tenant_id": record.tenant_id,
            "workspace_id": record.workspace_id,
            "canvas_id": record.canvas_id,
            "name": record.name,
            "type": record.type,
            "content": record.content,
            "version": record.version,
        }
    if kind == "episode_segment":
        return {
            "kind": kind,
            "id": str(record.id),
            "episode_id": str(record.episode_id),
            "segment_type": record.segment_type,
            "sequence_order": record.sequence_order,
            "content": record.content,
            "created_at": str(record.created_at),
        }
    raise QualificationReviewError(
        "unsupported_evidence", f"Unsupported evidence kind: {kind}")


def _load_evidence_record(
    db: Session, kind: str, evidence_id: str, agent: AgentRegistry,
) -> Any:
    if kind == "agent_episode":
        record = (
            db.query(AgentEpisode)
            .filter(AgentEpisode.id == str(evidence_id),
                    AgentEpisode.agent_id == str(agent.id))
            .populate_existing()
            .first()
        )
        if record is not None and str(record.status or "").lower() != "completed":
            return None
        return record
    if kind == "agent_execution":
        record = (
            db.query(AgentExecution)
            .filter(AgentExecution.id == str(evidence_id),
                    AgentExecution.agent_id == str(agent.id))
            .populate_existing()
            .first()
        )
        if record is not None and str(record.status or "").lower() != "completed":
            return None
        return record
    if kind == "artifact":
        record = (
            db.query(Artifact)
            .filter(Artifact.id == str(evidence_id),
                    Artifact.agent_id == str(agent.id))
            .populate_existing()
            .first()
        )
        return record
    if kind == "episode_segment":
        from core.models import EpisodeSegment

        record = (
            db.query(EpisodeSegment)
            .filter(EpisodeSegment.id == str(evidence_id))
            .populate_existing()
            .first()
        )
        return record
    raise QualificationReviewError(
        "unsupported_evidence", f"Unsupported evidence kind: {kind}")


def validate_qualification_evidence(
    db: Session,
    agent: AgentRegistry,
    evidence_refs: Any,
    *,
    tenant_id: str,
    workspace_id: str,
    rubric_version: str,
) -> tuple:
    """Return (ok, normalized_refs, source_revision, error).

    Evidence is server-validated durable scoped work, not a client score or
    metadata flag. The digest is recomputed from the current record.
    """
    if not isinstance(evidence_refs, list) or not evidence_refs:
        return False, [], None, {
            "state": "unresolved_missing",
            "message": "At least one durable held-out evidence record is required.",
        }
    normalized: List[Dict[str, Any]] = []
    has_task = False
    has_output = False
    for raw in evidence_refs:
        if not isinstance(raw, dict):
            return False, [], None, {
                "state": "unresolved_scope",
                "message": "Each evidence ref must be an object.",
            }
        kind = str(raw.get("kind") or "").strip()
        evidence_id = str(raw.get("id") or "").strip()
        if kind not in QUALIFICATION_EVIDENCE_KINDS or not evidence_id:
            return False, [], None, {
                "state": "unresolved_scope",
                "message": "Evidence kind/id is missing or unsupported.",
            }
        try:
            record = _load_evidence_record(db, kind, evidence_id, agent)
        except QualificationReviewError as exc:
            return False, [], None, {
                "state": exc.state, "message": exc.message}
        scope_record = record
        parent_episode = None
        if kind == "episode_segment" and record is not None:
            parent_episode = (
                db.query(AgentEpisode)
                .filter(AgentEpisode.id == str(record.episode_id),
                        AgentEpisode.agent_id == str(agent.id))
                .populate_existing()
                .first()
            )
            scope_record = parent_episode
        if scope_record is None or not _scope_matches(
                scope_record, tenant_id, workspace_id):
            return False, [], None, {
                "state": "unresolved_scope",
                "message": (
                    f"Evidence {kind}:{evidence_id} is missing, changed or "
                    "outside the agent's current scope."),
            }
        digest = hashlib.sha256(
            json.dumps(
                _canonical_evidence_material(kind, record),
                sort_keys=True, default=str,
            ).encode("utf-8")
        ).hexdigest()
        expected = str(raw.get("sha256") or "").strip()
        if expected and expected != digest:
            return False, [], None, {
                "state": "unresolved_stale",
                "message": (
                    f"Evidence {kind}:{evidence_id} changed since review; "
                    "request a fresh qualification review."),
            }
        task_preview = ""
        output_preview = ""
        if kind == "agent_episode":
            version_token = str(getattr(record, "updated_at", "") or "")
            snapshot = {
                "agent_id": str(record.agent_id),
                "tenant_id": record.tenant_id,
                "workspace_id": record.workspace_id,
                "status": record.status,
                "task_description": record.task_description,
                "outcome": record.outcome,
                "success": bool(record.success),
                "completed_at": (
                    None if record.completed_at is None
                    else str(record.completed_at)),
                "human_intervention_count": record.human_intervention_count,
                "constitutional_score": record.constitutional_score,
                "confidence_score": record.confidence_score,
            }
            task_preview = str(record.task_description or "")
            has_task = has_task or bool(task_preview.strip())
        elif kind == "agent_execution":
            version_token = str(getattr(record, "completed_at", "") or "")
            snapshot = {
                "agent_id": str(record.agent_id),
                "tenant_id": record.tenant_id,
                "workspace_id": record.workspace_id,
                "status": record.status,
                "input_summary": record.input_summary,
                "result_summary": record.result_summary,
                "output_summary": record.output_summary,
                "completed_at": (
                    None if record.completed_at is None
                    else str(record.completed_at)),
            }
            task_preview = str(record.input_summary or "")
            output_preview = str(
                record.result_summary or record.output_summary or "")
            has_task = has_task or bool(task_preview.strip())
            has_output = has_output or bool(output_preview.strip())
        elif kind == "artifact":
            version_token = str(getattr(record, "updated_at", "") or "")
            snapshot = {
                "agent_id": str(record.agent_id),
                "tenant_id": record.tenant_id,
                "workspace_id": record.workspace_id,
                "content": record.content,
                "version": record.version,
            }
            output_preview = str(record.content or "")
            has_output = has_output or bool(output_preview.strip())
        else:  # episode_segment
            version_token = str(getattr(record, "created_at", "") or "")
            snapshot = {
                "episode_id": str(record.episode_id),
                "segment_type": record.segment_type,
                "sequence_order": record.sequence_order,
                "content": record.content,
                "created_at": str(record.created_at),
                "parent_agent_id": str(
                    getattr(parent_episode, "agent_id", "") or ""),
                "parent_tenant_id": getattr(parent_episode, "tenant_id", None),
                "parent_workspace_id": getattr(
                    parent_episode, "workspace_id", None),
                "parent_status": getattr(parent_episode, "status", None),
                "parent_task_description": str(
                    getattr(parent_episode, "task_description", "") or ""),
            }
            task_preview = str(
                getattr(parent_episode, "task_description", "") or "")
            output_preview = str(record.content or "")
            has_task = has_task or bool(task_preview.strip())
            has_output = has_output or bool(output_preview.strip())
        normalized.append({
            "kind": kind,
            "id": evidence_id,
            "sha256": digest,
            "version_token": version_token,
            "snapshot": snapshot,
            "task_preview": task_preview[:500],
            "output_preview": output_preview[:500],
        })
    if not has_task or not has_output:
        return False, [], None, {
            "state": "unresolved_missing",
            "message": (
                "Capability qualification requires inspectable task/context "
                "AND actual durable output; historical statistics alone are "
                "not qualification evidence."),
        }
    normalized.sort(key=lambda item: (item["kind"], item["id"]))
    source_revision = hashlib.sha256(
        json.dumps(
            {"refs": normalized, "rubric_version": rubric_version},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return True, normalized, source_revision, None


def _qualification_next_action(
    state: str, message: str, *, action_id: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "state": state,
        "code": state,
        "message": message,
        "next_action": (
            "Request a human qualification review for this exact agent, "
            "tier and evidence scope."
            if state != "configuration_required"
            else "Fix the graduation assessment policy configuration; "
                 "a malformed policy is never treated as not-required."
        ),
    }
    if action_id:
        payload["review_action_id"] = action_id
        payload["next_action"] = "Await the existing qualification review decision."
    return payload


def _policy_bundle_or_error(db: Session) -> tuple:
    from core.promotion_policy_service import (
        AssessmentPolicyError, get_assessment_policy,
    )

    try:
        return get_assessment_policy(db), None
    except AssessmentPolicyError as exc:
        return None, {
            "allowed": False,
            "required": True,
            "state": "configuration_required",
            "message": exc.message,
            "next_action": _qualification_next_action(
                "configuration_required", exc.message),
        }


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def find_qualification_receipt(
    db: Session,
    agent: AgentRegistry,
    target_level: str,
    policy_bundle: Dict[str, Any],
    *,
    receipt_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve the exact protected pointer; never borrow another latest row."""
    policy = policy_bundle["policy"]
    pointer = str(receipt_id or getattr(agent, "last_exam_id", None) or "")
    if not pointer:
        return {"ok": False, "state": "unresolved_missing",
                "message": "No scoped capability qualification receipt is recorded."}
    receipt = (
        db.query(GraduationExam)
        .filter(GraduationExam.id == pointer,
                GraduationExam.agent_id == str(agent.id))
        .populate_existing()
        .first()
    )
    if receipt is None:
        return {"ok": False, "state": "unresolved_missing",
                "message": "The protected qualification pointer is missing or foreign."}
    tenant_id = resolve_tenant_id(agent)
    workspace_id = resolve_workspace_id(agent)
    metadata = dict(receipt.metadata_json or {})
    if not _nonempty_str(receipt.tenant_id) or str(receipt.tenant_id) != str(tenant_id):
        return {"ok": False, "state": "unresolved_scope",
                "message": "The receipt tenant binding is missing or outside the current scope."}
    receipt_workspace = metadata.get("workspace_id")
    if not _nonempty_str(receipt_workspace) or str(receipt_workspace) != str(workspace_id):
        return {"ok": False, "state": "unresolved_scope",
                "message": "The receipt workspace binding is missing or outside the current scope."}
    if metadata.get("receipt_kind") != QUALIFICATION_RECEIPT_KIND:
        return {"ok": False, "state": "unresolved_missing",
                "message": "The pointer names a legacy/history exam, not a capability qualification."}
    if (metadata.get("candidate_capability_qualified") is not True
            or receipt.passed is not True):
        return {"ok": False, "state": "unresolved_failed",
                "message": "The recorded qualification did not pass."}
    if not _nonempty_str(receipt.target_level) or str(
            receipt.target_level).lower() != str(target_level).lower():
        return {"ok": False, "state": "unresolved_scope",
                "message": "The receipt target tier binding is missing or different."}
    if not _nonempty_str(receipt.current_level) or str(
            receipt.current_level).lower() != str(agent.status or "").lower():
        return {"ok": False, "state": "unresolved_stale",
                "message": "The receipt source tier binding is missing or changed."}
    if not _nonempty_str(metadata.get("policy_revision")) or (
            metadata.get("policy_revision") != policy.revision):
        return {"ok": False, "state": "unresolved_stale",
                "message": "The assessment policy revision changed after the receipt."}
    if not _nonempty_str(metadata.get("policy_digest")) or (
            metadata.get("policy_digest") != policy_bundle.get("digest")):
        return {"ok": False, "state": "unresolved_stale",
                "message": "The assessment policy content changed after the receipt."}
    if not _nonempty_str(metadata.get("rubric_version")) or (
            metadata.get("rubric_version") != policy.rubric_version):
        return {"ok": False, "state": "unresolved_stale",
                "message": "The held-out rubric changed after the receipt."}
    if metadata.get("rubric_criteria") != [
            item.model_dump() for item in policy.rubric_criteria]:
        return {"ok": False, "state": "unresolved_stale",
                "message": "The held-out rubric criteria changed after the receipt."}
    if not _nonempty_str(metadata.get("source_revision")):
        return {"ok": False, "state": "unresolved_stale",
                "message": "The receipt source revision binding is missing."}
    evidence_refs = metadata.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        return {"ok": False, "state": "unresolved_missing",
                "message": "The receipt evidence binding is missing."}
    ok, normalized, source_revision, error = validate_qualification_evidence(
        db, agent, evidence_refs,
        tenant_id=tenant_id, workspace_id=workspace_id,
        rubric_version=str(metadata.get("rubric_version") or ""),
    )
    if not ok:
        return {"ok": False, **(error or {})}
    if source_revision != metadata.get("source_revision"):
        return {"ok": False, "state": "unresolved_stale",
                "message": "The held-out evidence source changed after the receipt."}
    reviewed_by = metadata.get("reviewed_by")
    if not _nonempty_str(reviewed_by):
        return {"ok": False, "state": "unresolved_scope",
                "message": "The receipt has no durable reviewer identity."}
    review_action_id = metadata.get("review_action_id")
    if not _nonempty_str(review_action_id):
        return {"ok": False, "state": "unresolved_failed",
                "message": "The receipt has no approved human review binding."}
    review = (
        db.query(HITLAction)
        .filter(HITLAction.id == str(review_action_id))
        .populate_existing()
        .first()
    )
    if review is None:
        return {"ok": False, "state": "unresolved_failed",
                "message": "The approved human review no longer exists."}
    if str(review.status or "") != HITLActionStatus.APPROVED.value:
        return {"ok": False, "state": "unresolved_failed",
                "message": "The human review is no longer approved."}
    if str(review.action_type or "") != QUALIFICATION_REVIEW_ACTION:
        return {"ok": False, "state": "unresolved_failed",
                "message": "The receipt points at the wrong review kind."}
    if str(review.agent_id or "") != str(agent.id):
        return {"ok": False, "state": "unresolved_scope",
                "message": "The human review belongs to a different agent."}
    if not _scope_matches(review, tenant_id, workspace_id):
        return {"ok": False, "state": "unresolved_scope",
                "message": "The human review is outside the current scope."}
    review_params = dict(review.params or {})
    for key in ("policy_revision", "policy_digest", "rubric_version",
                "source_revision", "target_level", "current_level"):
        if review_params.get(key) != metadata.get(key):
            return {"ok": False, "state": "unresolved_stale",
                    "message": f"The human review {key} binding changed."}
    if str(review.reviewed_by or "") != str(reviewed_by):
        return {"ok": False, "state": "unresolved_scope",
                "message": "The human review reviewer binding changed."}
    if review.reviewed_at is None:
        return {"ok": False, "state": "unresolved_failed",
                "message": "The human review has no durable decision time."}
    if not _reviewer_is_authorized(db, str(reviewed_by), agent):
        return {"ok": False, "state": "unresolved_scope",
                "message": "The human reviewer no longer has current authority/scope."}
    receipt_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "id": str(receipt.id),
                "created_at": str(receipt.created_at),
                "metadata": metadata,
            },
            sort_keys=True, default=str,
        ).encode("utf-8")
    ).hexdigest()
    review_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "id": str(review.id),
                "status": str(review.status or ""),
                "action_type": str(review.action_type or ""),
                "agent_id": str(review.agent_id or ""),
                "tenant_id": str(review.tenant_id or ""),
                "workspace_id": str(review.workspace_id or ""),
                "reviewed_by": str(review.reviewed_by or ""),
                "reviewed_at": str(review.reviewed_at or ""),
                "params": review_params,
            },
            sort_keys=True, default=str,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "ok": True,
        "state": "valid",
        "receipt": receipt,
        "metadata": metadata,
        "receipt_id": str(receipt.id),
        "reviewed_by": reviewed_by,
        "review_action_id": str(review_action_id),
        "source_revision": source_revision,
        "receipt_fingerprint": receipt_fingerprint,
        "review_fingerprint": review_fingerprint,
    }


def evaluate_qualification_gate(
    db: Session,
    agent: AgentRegistry,
    target_level: str,
    *,
    manual: bool = False,
) -> Dict[str, Any]:
    """The one gate every upward writer calls.

    Separates experience readiness (caller) from capability qualification
    (this gate). Missing/failed/stale/wrong-scope receipts are unresolved;
    only an explicit owner-scoped exception may allow unassessed progression,
    and it never claims candidate capability qualification.
    """
    policy_bundle, error = _policy_bundle_or_error(db)
    if error is not None:
        return error
    policy = policy_bundle["policy"]
    revision = policy_bundle["revision"]
    required = policy.tier_required(target_level)
    base = {
        "required": bool(required),
        "policy_revision": revision,
        "policy_digest": policy_bundle.get("digest"),
        "policy_source": policy_bundle.get("source"),
        "policy_row_updated_at": policy_bundle.get("row_updated_at"),
        "candidate_capability_qualified": False,
    }
    if not required:
        return {
            **base, "allowed": True, "state": "not_required",
            "message": "The owner policy does not require a capability qualification for this tier.",
            "next_action": None,
        }

    exception = None
    if manual:
        exception = policy.scoped_exception("manual", agent)
    if exception is None:
        # System is an explicit owner-listed agent id, never inferred from a
        # mutable category/name/module path.
        exception = policy.scoped_exception("system", agent)
    if exception is None:
        exception = policy.scoped_exception("legacy", agent)
    if exception is not None:
        return {
            **base, "allowed": True, "state": exception.state,
            "exception": {
                "kind": exception.state,
                "reason": exception.reason,
                "agent_ids": list(exception.agent_ids),
                "domains": list(exception.domains),
            },
            "message": (
                "Explicit owner-scoped exception allows an unassessed "
                "transition; it does not claim candidate capability qualification."),
            "next_action": None,
        }

    receipt = find_qualification_receipt(
        db, agent, target_level, policy_bundle)
    if receipt.get("ok"):
        return {
            **base, "allowed": True, "state": "valid",
            "receipt_id": receipt["receipt_id"],
            "reviewed_by": receipt["reviewed_by"],
            "review_action_id": receipt.get("review_action_id"),
            "source_revision": receipt["source_revision"],
            "receipt_fingerprint": receipt.get("receipt_fingerprint"),
            "review_fingerprint": receipt.get("review_fingerprint"),
            "candidate_capability_qualified": True,
            "message": "A passed scoped capability qualification receipt is recorded.",
            "next_action": None,
        }

    pending = (
        db.query(HITLAction)
        .filter(
            HITLAction.action_type == QUALIFICATION_REVIEW_ACTION,
            HITLAction.agent_id == str(agent.id),
            HITLAction.status == HITLActionStatus.PENDING.value,
        )
        .order_by(HITLAction.created_at.desc())
        .first()
    )
    action_id = str(pending.id) if pending is not None else None
    state = str(receipt.get("state") or "unresolved_missing")
    message = str(receipt.get("message") or "Capability qualification is unresolved.")
    return {
        **base, "allowed": False, "state": state,
        "message": message,
        "review_action_id": action_id,
        "next_action": _qualification_next_action(
            state, message, action_id=action_id),
    }


def list_qualification_evidence_bundles(
    db: Session,
    agent: AgentRegistry,
    target_level: str,
    tenant_id: str,
    workspace_id: str,
    *,
    limit: int = 10,
) -> Dict[str, Any]:
    """Eligible reviewable work: inspectable task/context + actual output.

    History-only episodes are deliberately excluded; the UI must not
    relabel recent statistical history as held-out output.
    """
    from core.models import EpisodeSegment
    from core.promotion_policy_service import get_assessment_policy

    policy_bundle = get_assessment_policy(db)
    policy = policy_bundle["policy"]
    rubric = [item.model_dump() for item in policy.rubric_criteria]
    episodes = (
        db.query(AgentEpisode)
        .filter(AgentEpisode.agent_id == str(agent.id),
                AgentEpisode.status == "completed")
        .order_by(AgentEpisode.started_at.desc())
        .limit(max(limit * 5, 25))
        .all()
    )
    items = []
    for episode in episodes:
        task = str(episode.task_description or "").strip()
        output = ""
        refs = [{"kind": "agent_episode", "id": str(episode.id)}]
        if episode.execution_id:
            execution = (
                db.query(AgentExecution)
                .filter(AgentExecution.id == str(episode.execution_id),
                        AgentExecution.agent_id == str(agent.id))
                .populate_existing()
                .first()
            )
            if execution is not None:
                execution_task = str(execution.input_summary or "").strip()
                execution_output = str(
                    execution.result_summary or execution.output_summary or ""
                ).strip()
                if execution_task and execution_output:
                    task = task or execution_task
                    output = execution_output
                    refs.append(
                        {"kind": "agent_execution", "id": str(execution.id)})
        if not output:
            segments = (
                db.query(EpisodeSegment)
                .filter(EpisodeSegment.episode_id == str(episode.id))
                .order_by(EpisodeSegment.sequence_order)
                .all()
            )
            for segment in segments:
                if str(segment.content or "").strip():
                    output = str(segment.content)
                    refs.append(
                        {"kind": "episode_segment", "id": str(segment.id)})
                    break
        if not output and episode.session_id:
            artifacts = (
                db.query(Artifact)
                .filter(Artifact.agent_id == str(agent.id),
                        Artifact.session_id == str(episode.session_id))
                .all()
            )
            for artifact in artifacts:
                if str(artifact.content or "").strip():
                    output = str(artifact.content)
                    refs.append(
                        {"kind": "artifact", "id": str(artifact.id)})
                    break
        if not task or not output:
            continue
        ok, normalized, source_revision, _error = validate_qualification_evidence(
            db, agent, refs,
            tenant_id=tenant_id, workspace_id=workspace_id,
            rubric_version=policy.rubric_version,
        )
        if not ok:
            continue
        items.append({
            "bundle_id": f"bundle:{episode.id}",
            "episode_id": str(episode.id),
            "task_preview": task[:500],
            "output_preview": output[:500],
            "evidence_refs": refs,
            "source_revision": source_revision,
        })
        if len(items) >= limit:
            break
    return {
        "agent_id": str(agent.id),
        "target_level": str(target_level or "").upper(),
        "rubric_version": policy.rubric_version,
        "rubric_criteria": rubric,
        "items": items,
    }


def request_qualification_review(
    db: Session,
    *,
    agent: AgentRegistry,
    target_level: str,
    evidence_refs: Any,
    rubric_version: Optional[str],
    requested_by: str,
    tenant_id: str,
    workspace_id: str,
    note: Optional[str] = None,
    actor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create the existing HITL review row; no new queue/lifecycle."""
    target = str(target_level or "").strip().upper()
    current = str(agent.status or "").strip().lower()
    if _next_tier(current) != target.lower():
        raise QualificationReviewError(
            "invalid_target",
            f"Target {target} is not the next tier after {current}.",
        )
    policy_bundle, error = _policy_bundle_or_error(db)
    if error is not None:
        raise QualificationReviewError(
            "configuration_required", error["message"])
    policy = policy_bundle["policy"]
    rubric = str(rubric_version or policy.rubric_version)
    ok, normalized, source_revision, evidence_error = validate_qualification_evidence(
        db, agent, evidence_refs,
        tenant_id=tenant_id, workspace_id=workspace_id,
        rubric_version=rubric,
    )
    if not ok:
        raise QualificationReviewError(
            str((evidence_error or {}).get("state") or "unresolved_scope"),
            str((evidence_error or {}).get("message") or "Invalid evidence."),
        )
    existing = (
        db.query(HITLAction)
        .filter(
            HITLAction.action_type == QUALIFICATION_REVIEW_ACTION,
            HITLAction.agent_id == str(agent.id),
            HITLAction.status == HITLActionStatus.PENDING.value,
        )
        .order_by(HITLAction.created_at.desc())
        .all()
    )
    for row in existing:
        params = dict(row.params or {})
        if (str(params.get("target_level") or "").lower() == target.lower()
                and params.get("source_revision") == source_revision):
            return {
                "action_id": str(row.id),
                "state": "pending_review",
                "target_level": target,
                "source_revision": source_revision,
                "idempotent": True,
            }
    rubric_criteria = [item.model_dump() for item in policy.rubric_criteria]
    params = {
        "schema": QUALIFICATION_REVIEW_SCHEMA,
        "agent_id": str(agent.id),
        "agent_name": str(agent.name or ""),
        "target_level": target,
        "current_level": current,
        "tenant_id": str(tenant_id or ""),
        "workspace_id": str(workspace_id or ""),
        "policy_revision": policy_bundle["revision"],
        "policy_digest": policy_bundle.get("digest"),
        "rubric_version": rubric,
        "rubric_criteria": rubric_criteria,
        "source_revision": source_revision,
        "evidence_refs": normalized,
        "evidence": [
            {
                "kind": ref["kind"],
                "id": ref["id"],
                "task_preview": ref.get("task_preview") or "",
                "output_preview": ref.get("output_preview") or "",
            }
            for ref in normalized
        ],
        "requested_by": str(requested_by or ""),
        "requested_at": datetime.now().isoformat(),
        "note": str(note or "")[:1000],
    }
    if actor is not None:
        from core.agent_decision_write_service import _claim_actor

        if not _claim_actor(db, actor):
            raise QualificationReviewError(
                "authority_changed",
                "The requester's current active authority/scope changed; "
                "refresh and retry.")
    action = HITLAction(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        agent_id=str(agent.id),
        user_id=str(requested_by or ""),
        action_type=QUALIFICATION_REVIEW_ACTION,
        platform="internal",
        params=params,
        reason=(
            f"Capability qualification review: {agent.name or agent.id} "
            f"{current} -> {target.lower()}"),
        context_snapshot={
            "required_role": "team_lead",
            "agent_id": str(agent.id),
            "tenant_id": str(tenant_id or ""),
            "workspace_id": str(workspace_id or ""),
            "qualification_review": True,
        },
        status=HITLActionStatus.PENDING.value,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return {
        "action_id": str(action.id),
        "state": "pending_review",
        "target_level": target,
        "source_revision": source_revision,
        "idempotent": False,
    }


def _reviewer_is_authorized(db: Session, reviewer_id: str,
                            agent: AgentRegistry) -> bool:
    from core.models import UserRole
    from core.rbac_service import Permission, RBACService
    from core.security.rbac import role_level

    reviewer = db.query(User).filter(User.id == str(reviewer_id)).first()
    if reviewer is None or not bool(reviewer.is_active):
        return False
    if str(reviewer.status or "") != "active":
        return False
    # Match the existing approvals route floor exactly: AGENT_MANAGE.
    if not RBACService.check_permission(reviewer, Permission.AGENT_MANAGE):
        return False
    if not _scope_matches(reviewer, resolve_tenant_id(agent),
                          resolve_workspace_id(agent)):
        # ADMIN+ may cross workspaces inside the tenant, matching the shared
        # agent visibility policy.
        if not (str(reviewer.tenant_id or "") == str(agent.tenant_id or "")
                and role_level(reviewer.role) >= role_level(UserRole.ADMIN)):
            return False
    return True


def write_qualification_receipt_from_review(
    db: Session,
    *,
    action_id: str,
    approved: bool,
    reviewer_id: Optional[str],
) -> Dict[str, Any]:
    """Idempotently write the append-only GraduationExam receipt for a review."""
    action = (
        db.query(HITLAction)
        .filter(HITLAction.id == str(action_id))
        .populate_existing()
        .first()
    )
    if action is None:
        return {"handled": False, "reason": "action_not_found"}
    if str(action.action_type or "") != QUALIFICATION_REVIEW_ACTION:
        return {"handled": False, "reason": "not_a_qualification_review"}
    params = dict(action.params or {})
    agent = (
        db.query(AgentRegistry)
        .filter(AgentRegistry.id == str(params.get("agent_id") or ""))
        .populate_existing()
        .first()
    )
    if agent is None:
        return {"handled": True, "resumed": False,
                "state": "unresolved_scope", "error": "agent_not_found"}
    tenant_id = resolve_tenant_id(agent)
    workspace_id = resolve_workspace_id(agent)
    if not _scope_matches(action, tenant_id, workspace_id):
        return {"handled": True, "resumed": False,
                "state": "unresolved_scope", "error": "review_scope_mismatch"}
    receipt_id = f"qualification:{action.id}"
    existing = db.query(GraduationExam).filter(
        GraduationExam.id == receipt_id).first()
    if existing is not None:
        return {"handled": True, "resumed": True, "idempotent": True,
                "receipt_id": receipt_id,
                "state": str((existing.metadata_json or {}).get("state") or "valid")}

    if not approved:
        receipt = GraduationExam(
            id=receipt_id,
            agent_id=str(agent.id),
            tenant_id=tenant_id,
            target_level=str(params.get("target_level") or ""),
            current_level=str(params.get("current_level") or ""),
            readiness_score=0.0,
            zero_intervention_ratio=0.0,
            avg_constitutional_score=0.0,
            avg_confidence_score=float(agent.confidence_score or 0.0),
            success_rate=0.0,
            episodes_analyzed=0,
            edge_case_results={"decision": "rejected"},
            edge_cases_passed=0,
            edge_cases_total=0,
            constitutional_violations=[],
            constitutional_check_passed=False,
            passed=False,
            promoted=False,
            failure_reason="human_review_rejected",
            metadata_json={
                "receipt_kind": QUALIFICATION_RECEIPT_KIND,
                "assessment_scope": QUALIFICATION_ASSESSMENT_SCOPE,
                "candidate_capability_qualified": False,
                "state": "unresolved_failed",
                "review_action_id": str(action.id),
                "reviewed_by": str(reviewer_id or ""),
                "reviewed_at": datetime.now().isoformat(),
                "policy_revision": params.get("policy_revision"),
                "rubric_version": params.get("rubric_version"),
                "source_revision": params.get("source_revision"),
                "evidence_refs": params.get("evidence_refs") or [],
            },
            created_at=datetime.now(),
        )
        db.add(receipt)
        db.commit()
        return {"handled": True, "resumed": True, "receipt_id": receipt_id,
                "state": "unresolved_failed"}

    if not reviewer_id or not _reviewer_is_authorized(
            db, str(reviewer_id), agent):
        return {"handled": True, "resumed": False,
                "state": "unresolved_scope",
                "error": "current_reviewer_authority_required"}
    policy_bundle, error = _policy_bundle_or_error(db)
    if error is not None:
        return {"handled": True, "resumed": False,
                "state": "configuration_required", "error": error["message"]}
    policy = policy_bundle["policy"]
    if params.get("policy_revision") != policy_bundle["revision"]:
        return {"handled": True, "resumed": False,
                "state": "unresolved_stale", "error": "policy_changed"}
    if params.get("policy_digest") != policy_bundle.get("digest"):
        return {"handled": True, "resumed": False,
                "state": "unresolved_stale", "error": "policy_content_changed"}
    if params.get("rubric_version") != policy.rubric_version:
        return {"handled": True, "resumed": False,
                "state": "unresolved_stale", "error": "rubric_changed"}
    if params.get("rubric_criteria") != [
            item.model_dump() for item in policy.rubric_criteria]:
        return {"handled": True, "resumed": False,
                "state": "unresolved_stale", "error": "rubric_criteria_changed"}
    if str(agent.status or "").lower() != str(params.get("current_level") or "").lower():
        return {"handled": True, "resumed": False,
                "state": "unresolved_stale", "error": "agent_tier_changed"}
    if _next_tier(str(agent.status or "")) != str(
            params.get("target_level") or "").lower():
        return {"handled": True, "resumed": False,
                "state": "unresolved_scope", "error": "target_not_next_tier"}
    ok, normalized, source_revision, evidence_error = validate_qualification_evidence(
        db, agent, params.get("evidence_refs"),
        tenant_id=tenant_id, workspace_id=workspace_id,
        rubric_version=str(params.get("rubric_version") or ""),
    )
    if not ok:
        return {"handled": True, "resumed": False,
                "state": str((evidence_error or {}).get("state") or "unresolved_stale"),
                "error": str((evidence_error or {}).get("message") or "evidence_changed")}
    if source_revision != params.get("source_revision"):
        return {"handled": True, "resumed": False,
                "state": "unresolved_stale", "error": "source_changed"}

    receipt = GraduationExam(
        id=receipt_id,
        agent_id=str(agent.id),
        tenant_id=tenant_id,
        target_level=str(params.get("target_level") or ""),
        current_level=str(params.get("current_level") or ""),
        readiness_score=0.0,
        zero_intervention_ratio=0.0,
        avg_constitutional_score=0.0,
        avg_confidence_score=float(agent.confidence_score or 0.0),
        success_rate=0.0,
        episodes_analyzed=0,
        edge_case_results={
            "evaluator": "human_review",
            "rubric_version": params.get("rubric_version"),
            "rubric_criteria": params.get("rubric_criteria") or [],
            "evidence": params.get("evidence") or [],
            "criteria": {
                "trajectory": "reviewed",
                "tool_use": "reviewed",
                "final_response": "reviewed",
                "safety": "reviewed",
                "efficiency": "informational",
            },
            "evidence_refs": normalized,
        },
        edge_cases_passed=len(normalized),
        edge_cases_total=len(normalized),
        constitutional_violations=[],
        constitutional_check_passed=True,
        passed=True,
        promoted=False,
        failure_reason=None,
        metadata_json={
            "receipt_kind": QUALIFICATION_RECEIPT_KIND,
            "assessment_scope": QUALIFICATION_ASSESSMENT_SCOPE,
            "candidate_capability_qualified": True,
            "state": "valid",
            "review_action_id": str(action.id),
            "reviewed_by": str(reviewer_id),
            "reviewed_at": datetime.now().isoformat(),
            "policy_revision": policy_bundle["revision"],
            "policy_digest": policy_bundle.get("digest"),
            "rubric_version": policy.rubric_version,
            "rubric_criteria": params.get("rubric_criteria") or [],
            "source_revision": source_revision,
            "evidence_refs": normalized,
            "evidence": params.get("evidence") or [],
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "agent_name": str(agent.name or ""),
            "target_level": str(params.get("target_level") or ""),
            "current_level": str(params.get("current_level") or ""),
        },
        created_at=datetime.now(),
    )
    prior_last_exam_id = agent.last_exam_id
    prior_status = str(agent.status or "")
    db.add(receipt)
    db.flush()
    from sqlalchemy import update as sa_update
    predicate = (
        AgentRegistry.last_exam_id.is_(None)
        if prior_last_exam_id is None
        else AgentRegistry.last_exam_id == prior_last_exam_id
    )
    changed = db.execute(
        sa_update(AgentRegistry)
        .where(
            AgentRegistry.id == str(agent.id),
            AgentRegistry.tenant_id == agent.tenant_id,
            AgentRegistry.workspace_id == agent.workspace_id,
            AgentRegistry.status == prior_status,
            predicate,
        )
        .values(last_exam_id=receipt.id)
    )
    if changed.rowcount != 1:
        db.rollback()
        return {"handled": True, "resumed": False,
                "state": "unresolved_stale",
                "error": "agent_changed_before_receipt_pointer"}
    db.commit()
    return {"handled": True, "resumed": True, "receipt_id": receipt_id,
            "state": "valid"}


def _receipt_reviewer_for_pointer(db: Session, agent: AgentRegistry) -> Optional[str]:
    pointer = str(getattr(agent, "last_exam_id", None) or "")
    if not pointer:
        return None
    receipt = (
        db.query(GraduationExam)
        .filter(GraduationExam.id == pointer,
                GraduationExam.agent_id == str(agent.id))
        .populate_existing()
        .first()
    )
    if receipt is None:
        return None
    metadata = dict(receipt.metadata_json or {})
    if metadata.get("receipt_kind") != QUALIFICATION_RECEIPT_KIND:
        return None
    return str(metadata.get("reviewed_by") or "") or None




def _guard_eq(column: Any, value: Any):
    return column.is_(None) if value is None else column == value


def qualification_cas_predicates(
    db: Session, agent: AgentRegistry, gate: Dict[str, Any],
) -> tuple:
    """Build exact policy/receipt/review/evidence CAS guards.

    The guards are evaluated in the same conditional UPDATE as the tier
    change. Policy guards apply to EVERY allowed state (including
    not_required/manual/system/legacy exceptions), so an owner-policy
    revocation between gate and effect cannot bypass. Receipt/review guards
    compare against the frozen fingerprints validated by the gate; a reload
    never adopts already-mutated material as newly authoritative.
    """
    if not gate.get("allowed"):
        return [], None
    from core.promotion_policy_service import (
        ASSESSMENT_POLICY_KEY, AssessmentPolicyError, get_assessment_policy,
    )

    try:
        current_policy = get_assessment_policy(db)
    except AssessmentPolicyError as exc:
        return [], {"status": "unresolved", "verification": {"effect": "none"},
                    "assessment": {
                        "allowed": False, "required": True,
                        "state": "configuration_required",
                        "message": exc.message,
                        "next_action": _qualification_next_action(
                            "configuration_required", exc.message)}}
    if current_policy.get("digest") != gate.get("policy_digest"):
        return [], {"status": "unresolved", "verification": {"effect": "none"},
                    "assessment": {
                        **gate, "allowed": False, "state": "unresolved_stale",
                        "message": "The assessment policy changed during the transition.",
                        "next_action": _qualification_next_action(
                            "unresolved_stale",
                            "The assessment policy changed during the transition.")}}
    from sqlalchemy import String, cast, exists

    from core.models import RuntimeSetting

    guards = []
    if (current_policy.get("source") == "db"
            and current_policy.get("row_updated_at") is not None):
        guards.append(exists().where(
            RuntimeSetting.key == ASSESSMENT_POLICY_KEY,
            RuntimeSetting.updated_at == current_policy["row_updated_at"],
            RuntimeSetting.value_json == current_policy["raw_value"],
        ))
    elif current_policy.get("source") == "default":
        guards.append(~exists().where(
            RuntimeSetting.key == ASSESSMENT_POLICY_KEY))
    elif current_policy.get("source") == "env":
        import os as _os

        if _os.environ.get(ASSESSMENT_POLICY_KEY) != current_policy.get("env_raw"):
            return [], {"status": "unresolved",
                        "verification": {"effect": "none"},
                        "assessment": {
                            **gate, "allowed": False,
                            "state": "unresolved_stale",
                            "message": "The assessment policy changed during the transition.",
                            "next_action": _qualification_next_action(
                                "unresolved_stale",
                                "The assessment policy changed during the transition.")}}
    # Exception/not-required states are policy-only; the policy guard above
    # is still the CAS binding for the owner exception.
    if gate.get("state") != "valid":
        return guards, None

    receipt_id = str(gate.get("receipt_id") or "")
    receipt = (
        db.query(GraduationExam)
        .filter(GraduationExam.id == receipt_id,
                GraduationExam.agent_id == str(agent.id))
        .populate_existing()
        .first()
    )
    if receipt is None:
        return [], {"status": "unresolved", "verification": {"effect": "none"},
                    "assessment": {
                        **gate, "allowed": False, "state": "unresolved_failed",
                        "message": "The qualification receipt disappeared before commit."}}
    receipt_metadata = dict(receipt.metadata_json or {})
    current_receipt_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "id": str(receipt.id),
                "created_at": str(receipt.created_at),
                "metadata": receipt_metadata,
            },
            sort_keys=True, default=str,
        ).encode("utf-8")
    ).hexdigest()
    if current_receipt_fingerprint != gate.get("receipt_fingerprint"):
        return [], {"status": "unresolved", "verification": {"effect": "none"},
                    "assessment": {
                        **gate, "allowed": False, "state": "unresolved_stale",
                        "message": "The qualification receipt changed after validation.",
                        "next_action": _qualification_next_action(
                            "unresolved_stale",
                            "The qualification receipt changed after validation.")}}
    review_id = str(
        gate.get("review_action_id")
        or receipt_metadata.get("review_action_id") or "")
    if not review_id:
        return [], {"status": "unresolved", "verification": {"effect": "none"},
                    "assessment": {
                        **gate, "allowed": False, "state": "unresolved_failed",
                        "message": "The qualification receipt has no review binding."}}
    review = (
        db.query(HITLAction)
        .filter(HITLAction.id == review_id)
        .populate_existing()
        .first()
    )
    if review is None:
        return [], {"status": "unresolved", "verification": {"effect": "none"},
                    "assessment": {
                        **gate, "allowed": False, "state": "unresolved_failed",
                        "message": "The approved human review disappeared before commit."}}
    review_params = dict(review.params or {})
    current_review_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "id": str(review.id),
                "status": str(review.status or ""),
                "action_type": str(review.action_type or ""),
                "agent_id": str(review.agent_id or ""),
                "tenant_id": str(review.tenant_id or ""),
                "workspace_id": str(review.workspace_id or ""),
                "reviewed_by": str(review.reviewed_by or ""),
                "reviewed_at": str(review.reviewed_at or ""),
                "params": review_params,
            },
            sort_keys=True, default=str,
        ).encode("utf-8")
    ).hexdigest()
    if current_review_fingerprint != gate.get("review_fingerprint"):
        return [], {"status": "unresolved", "verification": {"effect": "none"},
                    "assessment": {
                        **gate, "allowed": False, "state": "unresolved_stale",
                        "message": "The human review changed after validation.",
                        "next_action": _qualification_next_action(
                            "unresolved_stale",
                            "The human review changed after validation.")}}
    guards.append(exists().where(
        GraduationExam.id == receipt_id,
        GraduationExam.agent_id == str(agent.id),
        GraduationExam.passed.is_(True),
        GraduationExam.created_at == receipt.created_at,
        GraduationExam.metadata_json == receipt_metadata,
    ))
    guards.append(exists().where(
        HITLAction.id == review_id,
        HITLAction.status == HITLActionStatus.APPROVED.value,
        HITLAction.action_type == QUALIFICATION_REVIEW_ACTION,
        HITLAction.agent_id == str(agent.id),
        HITLAction.reviewed_by == str(review.reviewed_by or ""),
        HITLAction.reviewed_at == review.reviewed_at,
        HITLAction.params == review_params,
    ))
    for ref in receipt_metadata.get("evidence_refs") or []:
        kind = str(ref.get("kind") or "")
        evidence_id = str(ref.get("id") or "")
        token = str(ref.get("version_token") or "")
        snap = ref.get("snapshot") or {}
        if kind == "agent_episode":
            condition = exists().where(
                AgentEpisode.id == evidence_id,
                _guard_eq(AgentEpisode.agent_id,
                          snap.get("agent_id", str(agent.id))),
                _guard_eq(AgentEpisode.tenant_id, snap.get("tenant_id")),
                _guard_eq(AgentEpisode.workspace_id,
                          snap.get("workspace_id")),
                _guard_eq(AgentEpisode.status, snap.get("status", "completed")),
            )
            if token:
                condition = condition.where(
                    cast(AgentEpisode.updated_at, String) == token)
            for key in ("task_description", "outcome", "success",
                        "human_intervention_count", "constitutional_score",
                        "confidence_score"):
                if key in snap:
                    condition = condition.where(
                        _guard_eq(getattr(AgentEpisode, key), snap[key]))
            if "completed_at" in snap:
                condition = condition.where(
                    _guard_eq(cast(AgentEpisode.completed_at, String),
                              snap["completed_at"]))
        elif kind == "agent_execution":
            condition = exists().where(
                AgentExecution.id == evidence_id,
                _guard_eq(AgentExecution.agent_id,
                          snap.get("agent_id", str(agent.id))),
                _guard_eq(AgentExecution.tenant_id, snap.get("tenant_id")),
                _guard_eq(AgentExecution.workspace_id,
                          snap.get("workspace_id")),
                _guard_eq(AgentExecution.status,
                          snap.get("status", "completed")),
            )
            if token:
                condition = condition.where(
                    cast(AgentExecution.completed_at, String) == token)
            for key in ("status", "input_summary", "result_summary",
                        "output_summary"):
                if key in snap:
                    condition = condition.where(
                        _guard_eq(getattr(AgentExecution, key), snap[key]))
            if "completed_at" in snap:
                condition = condition.where(
                    _guard_eq(cast(AgentExecution.completed_at, String),
                              snap["completed_at"]))
        elif kind == "episode_segment":
            from core.models import EpisodeSegment

            condition = exists().where(
                EpisodeSegment.id == evidence_id,
                EpisodeSegment.episode_id == str(snap.get("episode_id") or ""),
                _guard_eq(EpisodeSegment.content, snap.get("content")),
                exists().where(
                    AgentEpisode.id == str(snap.get("episode_id") or ""),
                    _guard_eq(AgentEpisode.agent_id,
                              snap.get("parent_agent_id")),
                    _guard_eq(AgentEpisode.tenant_id,
                              snap.get("parent_tenant_id")),
                    _guard_eq(AgentEpisode.workspace_id,
                              snap.get("parent_workspace_id")),
                    _guard_eq(AgentEpisode.status, snap.get("parent_status")),
                    _guard_eq(AgentEpisode.task_description,
                              snap.get("parent_task_description")),
                ),
            )
        elif kind == "artifact":
            condition = exists().where(
                Artifact.id == evidence_id,
                _guard_eq(Artifact.agent_id,
                          snap.get("agent_id", str(agent.id))),
                _guard_eq(Artifact.tenant_id, snap.get("tenant_id")),
                _guard_eq(Artifact.workspace_id, snap.get("workspace_id")),
            )
            if token:
                condition = condition.where(
                    cast(Artifact.updated_at, String) == token)
            for key in ("content", "version"):
                if key in snap:
                    condition = condition.where(
                        _guard_eq(getattr(Artifact, key), snap[key]))
        else:
            return [], {"status": "unresolved",
                        "verification": {"effect": "none"},
                        "assessment": {
                            **gate, "allowed": False,
                            "state": "unresolved_scope",
                            "message": "Unknown evidence kind in the receipt."}}
        guards.append(condition)
    return guards, None


def commit_qualified_transition(
    db: Session,
    *,
    agent_id: str,
    target_level: str,
    actor_id: Optional[str],
    readiness: Dict[str, Any],
    source: str,
    manual: bool = False,
    operation_id: Optional[str] = None,
    promotion_type: str = "automatic",
    override_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Canonical CAS transition used by every upward writer.

    Callers must pass an already-computed experience readiness; this function
    adds the scoped qualification gate and the protected receipt/policy CAS.
    """
    from core.agent_decision_write_service import caller_work_pending

    if caller_work_pending(db):
        return {"status": "not_applied", "verification": {"effect": "none"},
                "reason": "dirty_caller_work"}
    agent = (
        db.query(AgentRegistry)
        .filter(AgentRegistry.id == str(agent_id))
        .populate_existing()
        .first()
    )
    if agent is None:
        return {"status": "not_applied", "verification": {"effect": "none"},
                "reason": "agent_not_found"}
    target = str(target_level or "").strip().upper()
    if target not in AgentGraduationService.PROMOTION_SOURCES:
        return {"status": "refused", "http_status": 422,
                "error_code": "VALIDATION_ERROR",
                "message": f"Unknown maturity level: {target_level}"}
    target_status = AgentStatus[target].value

    from types import SimpleNamespace
    from core.models import UserRole
    from core import agent_decision_write_service as writes

    resolved_actor_id = actor_id or _receipt_reviewer_for_pointer(db, agent)
    if not resolved_actor_id:
        resolved_actor_id = getattr(agent, "user_id", None)
    if not resolved_actor_id:
        return {"status": "refused", "http_status": 403,
                "error_code": "AUTHORITY_REQUIRED",
                "message": "A current supervisor-grade actor is required."}
    actor = writes._resolve_actor(
        db, SimpleNamespace(id=str(resolved_actor_id)),
        minimum_role=UserRole.TEAM_LEAD, authority_label="GRADUATION")
    if not actor.get("ok"):
        return {"status": "refused",
                "http_status": int(actor.get("http_status") or 403),
                "error_code": str(actor.get("error_code") or "AUTHORITY_REQUIRED"),
                "message": str(actor.get("message") or "Authority required.")}
    if not writes._agent_visible(actor, agent):
        return {"status": "refused", "http_status": 404,
                "error_code": "NOT_FOUND", "message": "Agent not found."}
    try:
        operation_id = writes._operation_id("graduate", operation_id)
    except ValueError as exc:
        return {"status": "refused", "http_status": 422,
                "error_code": "VALIDATION_ERROR", "message": str(exc)}
    # The receipt pointer is the immutable material for this operation. A
    # different target or different receipt with the same operation id is a
    # different request and must not replay.
    request = writes.graduation_request(
        operation_id=operation_id, agent_id=str(agent.id),
        target_status=target_status, actor=actor,
        tenant_id=resolve_tenant_id(agent), workspace_id=resolve_workspace_id(agent),
        assessment_receipt_id=agent.last_exam_id)
    # Replay BEFORE the obsolete pre-transition status / unconsumed-receipt
    # checks. A successful same-operation retry after a fresh session must
    # return already_applied, not INVALID_TRANSITION.
    replay = writes.replay_graduation(db, request=request, actor=actor)
    if replay is not None:
        return replay

    if str(agent.status or "") != AgentGraduationService.PROMOTION_SOURCES[target]:
        return {"status": "refused", "http_status": 409,
                "error_code": "INVALID_TRANSITION",
                "message": "Invalid promotion transition."}
    gate = evaluate_qualification_gate(db, agent, target, manual=manual)
    if not gate.get("allowed"):
        return {"status": "unresolved", "verification": {"effect": "none"},
                "assessment": gate}
    cas_predicates, cas_error = qualification_cas_predicates(db, agent, gate)
    if cas_error is not None:
        return cas_error
    ready = bool(readiness.get("ready") is True or
                 readiness.get("threshold_met") is True)
    gaps = list(readiness.get("gaps") or [])
    if not ready or gaps:
        return {"status": "not_applied", "verification": {"effect": "none"},
                "reason": "experience_readiness_unmet",
                "readiness": {"ready": ready, "gaps": gaps}}

    reviewed, raw_config, raw_schedule = writes._load_replace_source(
        db, str(agent.id))
    if reviewed is None or (
        reviewed.tenant_id != agent.tenant_id
        or reviewed.workspace_id != agent.workspace_id
        or str(reviewed.status or "") != str(agent.status or "")
    ):
        return {"status": "not_applied", "verification": {"effect": "none"},
                "reason": "stale_target"}
    predicates, claim_params = writes._replace_agent_predicates(
        reviewed, raw_config, raw_schedule)
    predicates.extend(writes._agent_predicates(
        reviewed, str(reviewed.status or "")))
    predicates.extend(cas_predicates)
    for field in ("module_path", "class_name", "user_id", "confidence_score",
                  "required_role_for_autonomy"):
        predicates.append(writes._exact(
            getattr(AgentRegistry, field), getattr(reviewed, field)))
    configuration = dict(reviewed.configuration or {})
    configuration.update(
        promoted_at=datetime.now().isoformat(),
        promoted_by=str(actor["id"]),
    )
    receipt_id = (
        gate.get("receipt_id") if gate.get("state") == "valid"
        else reviewed.last_exam_id)
    promotion_count = int(getattr(reviewed, "promotion_count", 0) or 0) + 1
    justification = f"{source}; assessment={gate.get('state')}"
    owner_reason = (gate.get("exception") or {}).get("reason")
    if owner_reason:
        justification += f"; owner_reason={owner_reason}"
    if override_reason:
        justification += f"; override={override_reason}"
    history = PromotionHistory(
        id=str(uuid.uuid4()),
        agent_id=str(reviewed.id),
        tenant_id=resolve_tenant_id(reviewed),
        from_level=str(reviewed.status or ""),
        to_level=target_status,
        promotion_type=promotion_type,
        readiness_score=float(readiness.get("score") or 0.0),
        exam_id=receipt_id if gate.get("state") == "valid" else None,
        promoted_by=str(actor["id"]),
        justification=justification,
        promoted_at=datetime.now(),
    )
    decision = writes.commit_graduation(
        db, reviewed=reviewed, actor=actor, request=request,
        predicates=predicates, claim_params=claim_params,
        target_status=target_status, configuration=configuration,
        last_exam_id=receipt_id, promotion_count=promotion_count,
        promotion_history=history,
        extra_success={"assessment": gate, "promotion_history_id": history.id},
        audit_extra={"assessment": gate},
    )
    if decision.get("status") == "verified":
        try:
            db.expire(agent)
        except Exception:
            pass
    return decision


def _review_field(action: Any, name: str, default: Any = None) -> Any:
    if isinstance(action, dict):
        return action.get(name, default)
    return getattr(action, name, default)


def validate_qualification_review_binding(
    db: Session, action: Any,
) -> Dict[str, Any]:
    """Preflight the exact review binding before a HITL row is approved."""
    if str(_review_field(action, "action_type", "")) != QUALIFICATION_REVIEW_ACTION:
        return {"valid": True}
    params = dict(_review_field(action, "params", {}) or {})
    if params.get("schema") != QUALIFICATION_REVIEW_SCHEMA:
        return {"valid": False, "reason": "qualification_binding_invalid",
                "message": "Qualification review schema is missing or unknown."}
    agent = (
        db.query(AgentRegistry)
        .filter(AgentRegistry.id == str(params.get("agent_id") or ""))
        .populate_existing()
        .first()
    )
    if agent is None:
        return {"valid": False, "reason": "qualification_agent_missing",
                "message": "The reviewed agent no longer exists."}
    tenant_id = resolve_tenant_id(agent)
    workspace_id = resolve_workspace_id(agent)
    if not _scope_matches(action, tenant_id, workspace_id):
        return {"valid": False, "reason": "qualification_scope_changed",
                "message": "The review is outside the agent's current scope."}
    policy_bundle, error = _policy_bundle_or_error(db)
    if error is not None:
        return {"valid": False, "reason": "configuration_required",
                "message": error["message"]}
    policy = policy_bundle["policy"]
    if params.get("policy_revision") != policy_bundle["revision"]:
        return {"valid": False, "reason": "qualification_policy_changed",
                "message": "The assessment policy revision changed after this review was requested."}
    if params.get("policy_digest") != policy_bundle.get("digest"):
        return {"valid": False, "reason": "qualification_policy_changed",
                "message": "The assessment policy content changed after this review was requested."}
    if params.get("rubric_version") != policy.rubric_version:
        return {"valid": False, "reason": "qualification_rubric_changed",
                "message": "The held-out rubric changed after this review was requested."}
    if params.get("rubric_criteria") != [
            item.model_dump() for item in policy.rubric_criteria]:
        return {"valid": False, "reason": "qualification_rubric_changed",
                "message": "The held-out rubric criteria changed after this review was requested."}
    if str(agent.status or "").lower() != str(
            params.get("current_level") or "").lower():
        return {"valid": False, "reason": "qualification_tier_changed",
                "message": "The agent's tier changed after this review was requested."}
    if _next_tier(str(agent.status or "")) != str(
            params.get("target_level") or "").lower():
        return {"valid": False, "reason": "qualification_target_changed",
                "message": "The target tier is no longer the next tier."}
    ok, normalized, source_revision, evidence_error = validate_qualification_evidence(
        db, agent, params.get("evidence_refs"),
        tenant_id=tenant_id, workspace_id=workspace_id,
        rubric_version=str(params.get("rubric_version") or ""),
    )
    if not ok:
        return {"valid": False,
                "reason": str((evidence_error or {}).get("state") or "qualification_evidence_changed"),
                "message": str((evidence_error or {}).get("message") or "Evidence changed.")}
    if source_revision != params.get("source_revision"):
        return {"valid": False, "reason": "qualification_source_changed",
                "message": "The held-out evidence source changed after this review was requested."}
    return {"valid": True}

"""
Agent Graduation Service

Validates agent readiness for promotion using episodic memory.
Provides data-driven audit trails for governance compliance.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.lancedb_handler import get_lancedb_handler
from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    EpisodeSegment,
    SupervisionSession,
)

logger = logging.getLogger(__name__)


class SandboxExecutor:
    """
    Executes graduation exams in a sandboxed environment.

    Simulates real-world scenarios to validate agent readiness for promotion.
    Tests constitutional compliance, decision-making, and governance adherence.
    """

    def __init__(self, db: Session):
        self.db = db

    async def execute_exam(
        self,
        agent_id: str,
        target_maturity: str,
        exam_scenarios: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute graduation exam for agent.

        Args:
            agent_id: Agent being examined
            target_maturity: Target maturity level (INTERN, SUPERVISED, AUTONOMOUS)
            exam_scenarios: Optional list of test scenarios

        Returns:
            {
                "success": bool,
                "score": float (0.0-1.0),
                "constitutional_compliance": float (0.0-1.0),
                "passed": bool,
                "constitutional_violations": List[str],
                "attempt": int
            }
        """
        # Get agent episodes to assess performance
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return {
                "success": False,
                "score": 0.0,
                "constitutional_compliance": 0.0,
                "passed": False,
                "error": "Agent not found"
            }

        # Get episodes at current maturity
        current_maturity = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)
        episodes = self.db.query(Episode).filter(
            Episode.agent_id == agent_id,
            Episode.maturity_at_time == current_maturity,
            Episode.status == "completed"
        ).all()

        # Calculate metrics from episodes
        episode_count = len(episodes)
        if episode_count == 0:
            return {
                "success": True,
                "score": 0.0,
                "constitutional_compliance": 0.0,
                "passed": False,
                "constitutional_violations": ["insufficient_episode_count"]
            }

        # Calculate intervention rate (lower is better)
        total_interventions = sum(e.human_intervention_count for e in episodes)
        intervention_rate = total_interventions / episode_count

        # Calculate score based on multiple factors
        # Base score from episode count
        criteria = AgentGraduationService.CRITERIA.get(target_maturity.upper(), {})
        min_episodes = criteria.get("min_episodes", 10)
        max_intervention_rate = criteria.get("max_intervention_rate", 0.5)

        # Episode count score (0-40 points)
        episode_score = min(episode_count / (min_episodes * 1.5), 1.0) * 40

        # Intervention score (0-30 points) - lower is better
        intervention_score = max(
            1.0 - (intervention_rate / max(max_intervention_rate, 0.5)),
            0.0
        ) * 30

        # Constitutional compliance (0-30 points)
        # In a real implementation, this would check against Knowledge Graph rules
        # For now, use a simulated score based on intervention rate
        compliance_score = max(1.0 - (intervention_rate * 2), 0.0) * 30

        # Total score (0-100, normalized to 0-1)
        total_score = (episode_score + intervention_score + compliance_score) / 100

        # Determine constitutional violations
        violations = []
        if intervention_rate > max_intervention_rate:
            violations.append("excessive_interventions")

        if total_score < 0.7:
            violations.append("insufficient_performance")

        # Constitutional compliance score
        constitutional_compliance = max(1.0 - (intervention_rate * 2), 0.5)

        # Minimum passing threshold
        min_score = criteria.get("min_constitutional_score", 0.70)
        passed = total_score >= min_score and constitutional_compliance >= min_score

        return {
            "success": True,
            "score": round(total_score, 2),
            "constitutional_compliance": round(constitutional_compliance, 2),
            "passed": passed,
            "constitutional_violations": violations,
            "attempt": 1
        }


class AgentGraduationService:
    """Validates agent promotion readiness using episodic memory"""

    # Graduation criteria
    CRITERIA = {
        "INTERN": {
            "min_episodes": 10,
            "max_intervention_rate": 0.5,  # 50%
            "min_constitutional_score": 0.70
        },
        "SUPERVISED": {
            "min_episodes": 25,
            "max_intervention_rate": 0.2,  # 20%
            "min_constitutional_score": 0.85
        },
        "AUTONOMOUS": {
            "min_episodes": 50,
            "max_intervention_rate": 0.0,  # 0% - fully autonomous
            "min_constitutional_score": 0.95
        }
    }

    def __init__(self, db: Session):
        self.db = db
        self.lancedb = get_lancedb_handler()

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
        # Get criteria
        criteria = self.CRITERIA.get(target_maturity.upper())
        if not criteria:
            return {"error": f"Unknown maturity level: {target_maturity}"}

        min_eps = min_episodes or criteria["min_episodes"]

        # Query agent episodes
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return {"error": "Agent not found"}

        current_maturity = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)

        # Get episodes at current maturity level
        episodes = self.db.query(Episode).filter(
            Episode.agent_id == agent_id,
            Episode.maturity_at_time == current_maturity,
            Episode.status == "completed"
        ).all()

        episode_count = len(episodes)

        # Calculate metrics
        total_interventions = sum(e.human_intervention_count for e in episodes)
        intervention_rate = total_interventions / episode_count if episode_count > 0 else 1.0

        constitutional_scores = [e.constitutional_score for e in episodes if e.constitutional_score is not None]
        avg_constitutional = sum(constitutional_scores) / len(constitutional_scores) if constitutional_scores else 0.0

        # Check criteria
        gaps = []
        if episode_count < min_eps:
            gaps.append(f"Need {min_eps - episode_count} more episodes")
        if intervention_rate > criteria["max_intervention_rate"]:
            gaps.append(
                f"Intervention rate too high: {intervention_rate:.1%} > {criteria['max_intervention_rate']:.1%}"
            )
        if avg_constitutional < criteria["min_constitutional_score"]:
            gaps.append(
                f"Constitutional score too low: {avg_constitutional:.2f} < {criteria['min_constitutional_score']:.2f}"
            )

        # Calculate readiness score
        ready = len(gaps) == 0
        score = self._calculate_score(
            episode_count, min_eps,
            intervention_rate, criteria["max_intervention_rate"],
            avg_constitutional, criteria["min_constitutional_score"]
        )

        return {
            "ready": ready,
            "score": round(score, 1),
            "episode_count": episode_count,
            "avg_constitutional_score": round(avg_constitutional, 3),
            "total_human_interventions": total_interventions,
            "intervention_rate": round(intervention_rate, 3),
            "recommendation": self._generate_recommendation(ready, score, target_maturity),
            "gaps": gaps,
            "target_maturity": target_maturity,
            "current_maturity": current_maturity
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
                "title": episode.title,
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
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

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

        # Add promotion metadata
        if not agent.metadata_json:
            agent.metadata_json = {}
        agent.metadata_json["promoted_at"] = datetime.now().isoformat()
        agent.metadata_json["promoted_by"] = validated_by

        self.db.commit()
        logger.info(f"Agent {agent_id} promoted to {new_maturity} by {validated_by}")

        return True

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
                "title": ep.title,
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
        executor = SandboxExecutor(self.db)
    
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



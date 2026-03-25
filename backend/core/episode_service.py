"""
Episode Service - Manages agent episodic memory lifecycle.

This service handles:
- Episode creation from agent executions
- Graduation readiness calculation
- Constitutional compliance scoring
- Step efficiency calculation (TRACE framework)
- Episode archival to LanceDB (cold storage)
- Progressive detail retrieval for episode recall
"""
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Literal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text, cast, String
import logging
import uuid
from dataclasses import dataclass
from enum import Enum

from core.models import (
    AgentEpisode, AgentExecution, AgentRegistry, EpisodeOutcome,
    AgentStatus, GraduationExam, AgentReasoningStep, Skill, EpisodeFeedback
)
from core.database import get_db
from core.lancedb_handler import get_lancedb_handler
from core.embedding_service import EmbeddingService
from core.constitutional_validator import get_constitutional_validator
from core.activity_publisher import ActivityPublisher

logger = logging.getLogger(__name__)

# Alias for backward compatibility if needed
Episode = AgentEpisode

class DetailLevel(str, Enum):
    """Detail level for episode recall - controls token usage"""
    SUMMARY = "summary"   # ~50 tokens: canvas type + summary + has_errors
    STANDARD = "standard" # ~200 tokens: summary + visual_elements + data
    FULL = "full"         # ~500 tokens: standard + full_state + audit_trail


# Progressive query templates for each detail level
PROGRESSIVE_QUERIES = {
    DetailLevel.SUMMARY: """
        SELECT
            e.id,
            e.agent_id,
            e.task_description,
            e.outcome,
            e.success,
            e.constitutional_score,
            e.human_intervention_count,
            e.started_at,
            e.completed_at,
            e.metadata_json->>'canvas_type' as canvas_type,
            e.metadata_json->>'presentation_summary' as presentation_summary,
            CASE WHEN e.metadata_json->'constitutional_violations' IS NOT NULL
                 AND jsonb_array_length((e.metadata_json->'constitutional_violations')::jsonb) > 0
                 THEN true ELSE false END as has_errors
        FROM agent_episodes e
        WHERE e.agent_id = :agent_id
        ORDER BY e.started_at DESC
        LIMIT :limit
    """,

    DetailLevel.STANDARD: """
        SELECT
            e.*,
            e.metadata_json->>'canvas_type' as canvas_type,
            e.metadata_json->>'presentation_summary' as presentation_summary,
            e.metadata_json->>'visual_elements' as visual_elements,
            e.metadata_json->>'critical_data_points' as critical_data_points,
            CASE WHEN e.metadata_json->'constitutional_violations' IS NOT NULL
                 AND jsonb_array_length((e.metadata_json->'constitutional_violations')::jsonb) > 0
                 THEN true ELSE false END as has_errors
        FROM agent_episodes e
        WHERE e.agent_id = :agent_id
        ORDER BY e.started_at DESC
        LIMIT :limit
    """,

    DetailLevel.FULL: """
        SELECT e.*, ca.audit_trail
        FROM agent_episodes e
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'action_id', ca.id,
                    'action_type', ca.action_type,
                    'canvas_id', ca.canvas_id,
                    'timestamp', ca.created_at,
                    'details', ca.audit_metadata
                )
            ) as audit_trail
            FROM canvas_audit ca
            WHERE ca.id = ANY(
                SELECT jsonb_array_elements_text((e.metadata_json->'canvas_action_ids')::jsonb)::uuid
                WHERE (e.metadata_json)::jsonb ? 'canvas_action_ids'
            )
        ) ca ON true
        WHERE e.agent_id = :agent_id
        ORDER BY e.started_at DESC
        LIMIT :limit
    """
}


class ReadinessThresholds:
    """Readiness score thresholds for agent maturity progression"""

    # student → intern
    STUDENT_TO_INTERN = {
        "success_rate": 0.70,
        "constitutional_score": 0.75,
        "zero_intervention_ratio": 0.40,
        "confidence_score": 0.50,
        "overall": 0.70
    }

    # intern → supervised
    INTERN_TO_SUPERVISED = {
        "success_rate": 0.85,
        "constitutional_score": 0.85,
        "zero_intervention_ratio": 0.60,
        "confidence_score": 0.70,
        "overall": 0.80
    }

    # supervised → autonomous
    SUPERVISED_TO_AUTONOMOUS = {
        "success_rate": 0.95,
        "constitutional_score": 0.95,
        "zero_intervention_ratio": 0.85,
        "confidence_score": 0.90,
        "overall": 0.95
    }


class ReadinessResponse:
    """Graduation readiness calculation response"""

    def __init__(
        self,
        agent_id: str,
        current_level: str,
        readiness_score: float,
        threshold_met: bool,
        zero_intervention_ratio: float,
        avg_constitutional_score: float,
        avg_confidence_score: float,
        success_rate: float,
        episodes_analyzed: int,
        breakdown: Dict[str, Any],
        supervision_success_rate: float = 0.0
    ):
        self.agent_id = agent_id
        self.current_level = current_level
        self.readiness_score = readiness_score
        self.threshold_met = threshold_met
        self.zero_intervention_ratio = zero_intervention_ratio
        self.avg_constitutional_score = avg_constitutional_score
        self.avg_confidence_score = avg_confidence_score
        self.success_rate = success_rate
        self.episodes_analyzed = episodes_analyzed
        self.breakdown = breakdown
        self.supervision_success_rate = supervision_success_rate

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            "agent_id": self.agent_id,
            "current_level": self.current_level,
            "readiness_score": self.readiness_score,
            "threshold_met": self.threshold_met,
            "zero_intervention_ratio": self.zero_intervention_ratio,
            "avg_constitutional_score": self.avg_constitutional_score,
            "avg_confidence_score": self.avg_confidence_score,
            "success_rate": self.success_rate,
            "episodes_analyzed": self.episodes_analyzed,
            "supervision_success_rate": self.supervision_success_rate,
            "breakdown": self.breakdown
        }


class EpisodeService:
    """
    Service for managing agent episodic memory.
    """

    def __init__(self, db: Session, workspace_id: str = "default", activity_publisher: Optional[ActivityPublisher] = None):
        self.db = db
        self.workspace_id = workspace_id
        self.activity_publisher = activity_publisher
        self.lancedb = get_lancedb_handler()
        self.embedding_service = EmbeddingService()

    async def create_episode_from_execution(
        self,
        execution_id: str,
        task_description: str,
        outcome: str,
        success: bool,
        constitutional_violations: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        domain: Optional[str] = None,
        **kwargs
    ) -> AgentEpisode:
        """
        Create an episode from a completed agent execution.
        """
        # Get the execution
        execution = self.db.query(AgentExecution).filter(
            AgentExecution.id == execution_id
        ).first()

        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        # Get agent for maturity level
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == execution.agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {execution.agent_id} not found")

        # Automated Constitutional Scoring if no violations provided directly
        if constitutional_violations is None:
            steps = self.db.query(AgentReasoningStep).filter(
                AgentReasoningStep.execution_id == execution_id
            ).all()
            
            # Map steps to validator format
            actions_to_check = []
            for step in steps:
                actions_to_check.append({
                    "action_type": step.step_type or "step",
                    "content": f"{step.thought or ''} {step.observation or ''}",
                    "metadata": step.action or {}
                })
            
            validator = get_constitutional_validator(self.db)
            validation_result = validator.validate_actions(actions_to_check, domain=domain or agent.category)
            constitutional_score = validation_result["score"]
            constitutional_violations = validation_result["violations"]
        else:
            # Manual scoring fallback
            constitutional_score = self._calculate_constitutional_score(
                constitutional_violations
            )

        # Calculate step efficiency (TRACE framework)
        step_efficiency = self._calculate_step_efficiency(execution_id)

        # Prepare metadata
        merged_metadata = metadata or {}
        if constitutional_violations:
            merged_metadata["constitutional_violations"] = constitutional_violations

        # Create episode
        episode = AgentEpisode(
            id=str(uuid.uuid4()),
            agent_id=execution.agent_id,
            tenant_id=execution.tenant_id,
            execution_id=execution_id,
            task_description=task_description,
            maturity_at_time=agent.status.value if hasattr(agent.status, 'value') else str(agent.status),
            constitutional_score=constitutional_score,
            human_intervention_count=execution.human_intervention_count,
            confidence_score=agent.confidence_score or 0.5,
            outcome=outcome,
            success=success,
            step_efficiency=step_efficiency,
            metadata_json=merged_metadata,
            started_at=execution.started_at,
            completed_at=execution.completed_at
        )

        self.db.add(episode)
        self.db.commit()
        self.db.refresh(episode)

        logger.info(
            f"Created episode {episode.id} for agent {execution.agent_id} "
            f"(outcome={outcome}, constitutional_score={constitutional_score:.2f})"
        )

        # Publish Activity
        publisher = self.activity_publisher
        if publisher:
            publisher.publish_episode_recording(
                tenant_id=episode.tenant_id or self.workspace_id,
                agent_id=episode.agent_id,
                episode_id=episode.id,
                status='completed'
            )

        return episode

    def get_graduation_readiness(
        self,
        agent_id: str,
        tenant_id: str,
        episode_count: int = 30,
        target_level: Optional[str] = None
    ) -> ReadinessResponse:
        """
        Calculate graduation readiness score for an agent.
        """
        agent = self.db.query(AgentRegistry).filter(
            and_(
                AgentRegistry.id == agent_id,
                AgentRegistry.tenant_id == tenant_id
            )
        ).first()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        current_level = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)

        if not target_level:
            target_level = self._get_next_level(current_level)

        episodes = self.db.query(AgentEpisode).filter(
            and_(
                AgentEpisode.agent_id == agent_id,
                AgentEpisode.tenant_id == tenant_id
            )
        ).order_by(AgentEpisode.started_at.desc()).limit(episode_count).all()

        if not episodes:
            return ReadinessResponse(
                agent_id=agent_id,
                current_level=current_level,
                readiness_score=0.0,
                threshold_met=False,
                zero_intervention_ratio=0.0,
                avg_constitutional_score=0.0,
                avg_confidence_score=agent.confidence_score or 0.5,
                success_rate=0.0,
                episodes_analyzed=0,
                breakdown={"reason": "No episodes found"}
            )

        metrics = self.calculate_readiness_metrics(episodes)
        supervision_metrics = self.calculate_supervision_metrics(episodes)
        skill_metrics = self.calculate_skill_diversity_metrics(agent_id, tenant_id)

        # Weighted formula
        readiness_score = (
            metrics["zero_intervention_ratio"] * 0.30 +
            metrics["avg_constitutional_score"] * 0.25 +
            metrics["avg_confidence_score"] * 0.15 +
            metrics["success_rate"] * 0.10 +
            supervision_metrics["supervision_success_rate"] * 0.10 +
            skill_metrics["skill_diversity_score"] * 0.10
        )

        threshold = self._get_threshold_for_level(target_level)
        threshold_met = readiness_score >= threshold

        return ReadinessResponse(
            agent_id=agent_id,
            current_level=current_level,
            readiness_score=round(float(readiness_score or 0.0), 4),
            threshold_met=threshold_met,
            zero_intervention_ratio=round(float(metrics["zero_intervention_ratio"] or 0.0), 4),
            avg_constitutional_score=round(float(metrics["avg_constitutional_score"] or 0.0), 4),
            avg_confidence_score=round(float(metrics["avg_confidence_score"] or 0.0), 4),
            success_rate=round(float(metrics["success_rate"] or 0.0), 4),
            episodes_analyzed=len(episodes),
            supervision_success_rate=round(float(supervision_metrics["supervision_success_rate"] or 0.0), 4),
            breakdown={
                "target_level": target_level,
                "threshold": threshold,
                "episodes_by_outcome": metrics["episodes_by_outcome"],
                "total_interventions": metrics["total_interventions"],
                "avg_step_efficiency": round(metrics.get("avg_step_efficiency", 1.0), 4),
                "supervision_metrics": supervision_metrics,
                "skill_metrics": skill_metrics
            }
        )

    def calculate_readiness_metrics(self, episodes: List[AgentEpisode]) -> Dict[str, Any]:
        """Calculate basic readiness metrics from episodes"""
        if not episodes:
            return {
                "success_rate": 0.0,
                "zero_intervention_ratio": 0.0,
                "avg_constitutional_score": 0.0,
                "avg_confidence_score": 0.0,
                "episodes_by_outcome": {},
                "total_interventions": 0,
                "avg_step_efficiency": 0.0
            }

        successful = sum(1 for e in episodes if e.success)
        success_rate = successful / len(episodes)

        zero_interventions = sum(1 for e in episodes if e.human_intervention_count == 0)
        zero_intervention_ratio = zero_interventions / len(episodes)

        avg_constitutional = sum(e.constitutional_score or 0.0 for e in episodes) / len(episodes)
        avg_confidence = sum(e.confidence_score or 0.0 for e in episodes) / len(episodes)

        episodes_by_outcome = {}
        for e in episodes:
            episodes_by_outcome[e.outcome] = episodes_by_outcome.get(e.outcome, 0) + 1

        total_interventions = sum(int(e.human_intervention_count or 0) for e in episodes)
        avg_step_efficiency = sum(float(e.step_efficiency or 1.0) for e in episodes) / float(len(episodes))

        return {
            "success_rate": success_rate,
            "zero_intervention_ratio": zero_intervention_ratio,
            "avg_constitutional_score": avg_constitutional,
            "avg_confidence_score": avg_confidence,
            "episodes_by_outcome": episodes_by_outcome,
            "total_interventions": total_interventions,
            "avg_step_efficiency": avg_step_efficiency
        }

    def calculate_supervision_metrics(self, episodes: List[AgentEpisode]) -> Dict[str, Any]:
        """Calculate supervision specific metrics"""
        supervision_episodes = [e for e in episodes if e.proposal_id is not None]

        if not supervision_episodes:
            return {
                "total_proposals": 0,
                "approved_proposals": 0,
                "rejected_proposals": 0,
                "execution_success_rate": 0.0,
                "approval_rate": 0.0,
                "supervision_success_rate": 0.0,
                "supervisor_type_breakdown": {"user": 0, "autonomous_agent": 0}
            }

        total = len(supervision_episodes)
        approved = sum(1 for e in supervision_episodes if e.supervision_decision == "approved")
        rejected = sum(1 for e in supervision_episodes if e.supervision_decision == "rejected")
        
        approval_rate = approved / total if total > 0 else 0.0
        
        executed_successfully = sum(
            1 for e in supervision_episodes 
            if e.supervision_decision == "approved" and e.execution_followed_proposal
        )
        execution_success_rate = executed_successfully / approved if approved > 0 else 0.0
        
        supervisor_breakdown = {
            "user": sum(1 for e in supervision_episodes if e.supervisor_type == "user"),
            "autonomous_agent": sum(1 for e in supervision_episodes if e.supervisor_type == "autonomous_agent")
        }
        
        supervision_success_rate = (approval_rate * 0.6) + (execution_success_rate * 0.4)

        return {
            "total_proposals": total,
            "approved_proposals": approved,
            "rejected_proposals": rejected,
            "execution_success_rate": round(execution_success_rate, 4),
            "approval_rate": round(approval_rate, 4),
            "supervision_success_rate": round(supervision_success_rate, 4),
            "supervisor_type_breakdown": supervisor_breakdown
        }

    def calculate_skill_diversity_metrics(self, agent_id: str, tenant_id: str) -> Dict[str, Any]:
        """Calculate skill diversity score"""
        skill_executions = self.db.query(Skill).join(
            AgentEpisode, cast(AgentEpisode.metadata_json["skill_id"], String) == Skill.id
        ).filter(
            AgentEpisode.agent_id == agent_id,
            AgentEpisode.tenant_id == tenant_id,
            AgentEpisode.success == True
        ).all()

        unique_skills = len(set(s.id for s in skill_executions))
        skill_diversity_score = min(unique_skills / 10.0, 1.0)

        return {
            "unique_skill_count": unique_skills,
            "skill_diversity_score": round(skill_diversity_score, 4),
            "total_skill_executions": len(skill_executions)
        }

    def _calculate_constitutional_score(self, violations: List[Dict[str, Any]]) -> float:
        """Calculate score based on violation severity"""
        if not violations:
            return 1.0
        
        severity_weights = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.1}
        total_penalty = sum(severity_weights.get(v.get("severity", "low").lower(), 0.1) for v in violations)
        return max(0.0, 1.0 - min(total_penalty, 1.0))

    def _calculate_step_efficiency(self, execution_id: str) -> float:
        """Calculate TRACE framework efficiency"""
        steps = self.db.query(AgentReasoningStep).filter(
            AgentReasoningStep.execution_id == execution_id
        ).all()
        
        if not steps:
            return 1.0
        
        actual = len(steps)
        # Simplified: optimal is roughly 80% for complex tasks
        optimal = max(1, int(actual * 0.8))
        return round(optimal / actual, 4)

    def _get_next_level(self, current_level: str) -> str:
        level_progression = {
            "student": "intern",
            "intern": "supervised",
            "supervised": "autonomous",
            "autonomous": "autonomous"
        }
        return level_progression.get(current_level.lower(), "intern")

    def _get_threshold_for_level(self, target_level: str) -> float:
        thresholds = {
            "intern": 0.70,
            "supervised": 0.80,
            "autonomous": 0.95
        }
        return thresholds.get(target_level.lower(), 0.70)

    async def archive_episode_to_cold_storage(self, episode_id: str) -> bool:
        """
        Archive an episode to LanceDB using the WorldModel's unified sync logic.
        """
        try:
            episode = self.db.query(AgentEpisode).filter(
                AgentEpisode.id == episode_id
            ).first()

            if not episode:
                logger.warning(f"Episode {episode_id} not found for archival")
                return False

            # Use WorldModelService for unified archival logic
            from core.service_factory import ServiceFactory
            world_model = ServiceFactory.get_world_model_service(workspace_id=self.workspace_id)
            
            # Extract learnings from metadata if available, else use outcome
            learnings = episode.metadata_json.get("learnings", episode.outcome or "No learnings recorded")
            
            await world_model.sync_episode_to_lancedb(
                episode_id=episode.id,
                agent_id=episode.agent_id,
                tenant_id=episode.tenant_id,
                task_description=episode.task_description or "Unknown task",
                outcome=episode.outcome or "unknown",
                learnings=learnings,
                agent_role=episode.metadata_json.get("agent_role", "assistant"),
                maturity_at_time=episode.maturity_at_time or "student",
                constitutional_score=float(episode.constitutional_score or 1.0),
                human_intervention_count=int(episode.human_intervention_count or 0),
                confidence_score=float(episode.confidence_score or 0.5),
                metadata=episode.metadata_json
            )
            
            # Mark as archived in PG if needed (models might need an is_archived flag)
            # For now, we follow the SaaS pattern of dual storage with PG retention
            
            return True
        except Exception as e:
            logger.error(f"Archival failed for episode {episode_id}: {e}")
            return False

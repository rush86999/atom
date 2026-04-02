"""
Episode Service - Manages agent episodic memory lifecycle.

This service handles:
- Episode creation from agent executions
- Graduation readiness calculation
- Constitutional compliance scoring
- Step efficiency calculation (TRACE framework)
- Episode archival to LanceDB (cold storage)
- Activity event publishing for menu bar companion
- Progressive detail retrieval for episode recall
"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any, Literal
from sqlalchemy.orm import Session
from sqlalchemy import func and_, or_, text, update, cast, String
import logging
import asyncio
import uuid
from dataclasses import dataclass
from enum import Enum

from core.models import (
 AgentEpisode, AgentExecution, AgentRegistry, EpisodeOutcome,
 AgentStatus, GraduationExam
)
from core.database import get_db
from core.lancedb_service import LanceDBService
from core.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class DetailLevel(str, Enum):
 """Detail level for episode recall - controls token usage"""
 SUMMARY = "summary" # ~50 tokens: canvas type + summary + has_errors
 STANDARD = "standard" # ~200 tokens: summary + visual_elements + data
 FULL = "full" # ~500 tokens: standard + full_state + audit_trail

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
 CASE WHEN e.constitutional_violations IS NOT NULL
 AND jsonb_array_length(e.constitutional_violations) > 0
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
 CASE WHEN e.constitutional_violations IS NOT NULL
 AND jsonb_array_length(e.constitutional_violations) > 0
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
 'details', ca.action_details
 )
 ) as audit_trail
 FROM canvas_audit ca
 WHERE ca.id = ANY(
 SELECT jsonb_array_elements_text(e.metadata_json->'canvas_action_ids')::uuid
 WHERE e.metadata_json ? 'canvas_action_ids'
 )
 ) ca ON true
 WHERE e.agent_id = :agent_id
 ORDER BY e.started_at DESC
 LIMIT :limit
 """
}

# Canvas context provider for episode metadata extraction
_canvas_context_provider = None
_canvas_summary_service = None

def _get_canvas_context_provider():
 """Get or create the global canvas context provider instance"""
 global _canvas_context_provider
 if _canvas_context_provider is None:
 from core.canvas_context_provider import CanvasContextProvider
 _canvas_context_provider = CanvasContextProvider()
 return _canvas_context_provider

def _get_canvas_summary_service(workspace_id: str):
 """Get or create the global canvas summary service instance"""
 if not workspace_id or workspace_id == "default":
 raise ValueError("workspace_id must be provided and cannot be 'default'")
 global _canvas_summary_service
 if _canvas_summary_service is None:
 from core.canvas_summary_service import CanvasSummaryService
 _canvas_summary_service = CanvasSummaryService(workspace_id)
 return _canvas_summary_service

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
 """Graduation readiness calculation response

 UPDATED: Now includes supervision_success_rate for supervision-learning integration
 """

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
 supervision_success_rate: float = 0.0 # NEW: Supervision success rate
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
 self.supervision_success_rate = supervision_success_rate # NEW

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
 "supervision_success_rate": self.supervision_success_rate, # NEW
 "breakdown": self.breakdown
 }

class EpisodeService:
 """
 Service for managing agent episodic memory.

 Key features:
 - Create episodes from completed executions
 - Calculate graduation readiness scores
 - Constitutional compliance scoring
 - TRACE framework step efficiency
 - Archive episodes to LanceDB for cold storage
 """

 def __init__(self, db: Session, tenant_api_key: Optional[str] = None, activity_publisher=None, embedding_service=None):
 """
 Initialize episode service.

 Args:
 db: Database session
 tenant_api_key: Optional tenant-specific OpenAI API key (BYOK)
 activity_publisher: Optional ActivityPublisher for menu bar updates
 embedding_service: Optional EmbeddingService instance (dependency injection for testing)
 """
 self.db = db
 self.lancedb = None
 self._tenant_api_key = tenant_api_key
 # Dependency injection: allow external EmbeddingService (for testing)
 # Lazy initialization: create on first access if not provided
 self._embedding_service = embedding_service
 # Activity publisher for menu bar companion
 self.activity_publisher = activity_publisher

 @property
 def embedding_service(self) -> EmbeddingService:
 """
 Get or lazy-initialize the embedding service.

 This property allows dependency injection while also supporting
 lazy initialization for production use. Tests can pass a mock
 EmbeddingService to avoid OpenAI dependency.

 Returns:
 EmbeddingService instance
 """
 if self._embedding_service is None:
 # Lazy initialization - only create when first accessed
 self._embedding_service = EmbeddingService(
 tenant_api_key=self._tenant_api_key
 )
 return self._embedding_service

 @embedding_service.setter
 def embedding_service(self, value: EmbeddingService):
 """
 Set the embedding service (for testing purposes).

 Args:
 value: EmbeddingService instance (usually a mock in tests)
 """
 self._embedding_service = value

 def _get_lancedb(self) -> Optional[LanceDBService]:
 """
 Get or initialize LanceDB service.

 Returns:
 LanceDBService instance or None if unavailable
 """
 if not self.lancedb:
 # Initialize LanceDB with correct vector dimension from embedding service
 vector_dim = self.embedding_service.get_embedding_dimension()
 self.lancedb = LanceDBService(vector_dim=vector_dim)
 if self.lancedb.connect():
 self.lancedb.get_or_create_episodes_table()
 else:
 logger.warning("Failed to connect to LanceDB - archival disabled")
 self.lancedb = None
 return self.lancedb

 async def _extract_canvas_metadata(self, execution_id: str, task_description: str = None) -> Dict[str, Any]:
 """
 Extract lightweight canvas metadata from execution context.

 This method adds canvas-related metadata to episodes for enhanced
 retrieval during future agent decision-making. The metadata is
 intentionally lightweight (IDs and counts only) to minimize storage
 overhead while enabling canvas-aware episodic recall.

 NEW: Now also includes canvas_action_ids to link canvas system actions
 to episodes. Full canvas actions are retrieved during decision-making.

 Args:
 execution_id: ID of the execution to extract canvas metadata from

 Returns:
 Dictionary with canvas metadata (canvas_id, artifact_count, comment_count,
 canvas_type, canvas_action_ids) or empty dict if no canvas context exists
 """
 try:
 execution = self.db.query(AgentExecution).filter(
 AgentExecution.id == execution_id
 ).first()

 if not execution or not execution.metadata_json:
 return {}

 canvas_id = execution.metadata_json.get("canvas_id")
 if not canvas_id:
 return {}

 # Fetch canvas context for counts (cached in CanvasContextProvider)
 provider = _get_canvas_context_provider()

 # This needs to be async-aware, but episode creation is sync
 # We'll do a simple sync query fallback
 from core.models import Canvas, Artifact, ArtifactComment, CanvasAudit

 canvas = self.db.query(Canvas).filter(
 Canvas.id == canvas_id).first()

 if not canvas:
 logger.warning(f"Canvas {canvas_id} not found for episode metadata")
 return {"canvas_id": canvas_id} # Fallback: just store the ID

 # Count artifacts and comments (lightweight queries)
 artifact_count = self.db.query(Artifact).filter(
 Artifact.canvas_id == canvas_id).count()

 # Count comments using a subquery for efficiency
 comment_count = self.db.query(ArtifactComment).join(
 Artifact, ArtifactComment.artifact_id == Artifact.id
 ).filter(
 Artifact.canvas_id == canvas_id).count()

 # Get canvas action IDs from CanvasAudit (linked, not stored)
 canvas_actions = self.db.query(CanvasAudit).filter(
 CanvasAudit.canvas_id == canvas_id,
 
 CanvasAudit.created_at.between(
 execution.started_at,
 execution.completed_at or datetime.now(timezone.utc)
 )
 ).all()

 canvas_action_ids = [action.id for action in canvas_actions]

 # NEW: Generate semantic summary if canvas is involved (Phase D)
 semantic_summary = None
 if canvas_id:
 try:
 summary_service = _get_canvas_summary_service(workspace_id=str(execution.workspace_id))
 # Fetch full canvas state from provider
 canvas_state = provider.get_canvas_state(canvas_id)
 if canvas_state:
 semantic_summary = await summary_service.generate_summary(
 canvas_type=canvas.canvas_type if canvas else "generic",
 canvas_state=canvas_state,
 agent_task=task_description
 )
 except Exception as e:
 logger.warning(f"Failed to generate semantic canvas summary: {e}")

 metadata = {
 "canvas_id": canvas_id,
 "canvas_artifact_count": artifact_count,
 "canvas_comment_count": comment_count,
 "canvas_type": canvas.canvas_type if canvas else "unknown",
 "canvas_action_ids": canvas_action_ids, # Links to canvas system
 "presentation_summary": semantic_summary # NEW: LLM-powered enrichment
 }

 logger.debug(
 f"Extracted canvas metadata: canvas_id={canvas_id}, "
 f"actions={len(canvas_action_ids)}, artifacts={artifact_count}, "
 f"semantic_summary={'yes' if semantic_summary else 'no'}"
 )

 return metadata

 except Exception as e:
 logger.warning(f"Failed to extract canvas metadata: {e}")
 return {}

 async def create_episode_from_execution(
 self,
 execution_id: str,
 task_description: str,
 outcome: str,
 success: bool,
 constitutional_violations: List[Dict[str, Any]] = None,
 metadata: Dict[str, Any] = None,
 **kwargs # Accept additional arguments from GenericAgent
 ) -> AgentEpisode:
 """
 Create an episode from a completed agent execution.

 NEW: Automatically extracts and includes canvas metadata if available
 in the execution context (canvas_id, artifact_count, comment_count).

 Canvas metadata is lightweight (IDs and counts only) and enables
 canvas-aware episodic recall for improved agent decision-making.

 NEW: Publishes activity events for menu bar companion integration.

 Args:
 execution_id: ID of the completed execution
 task_description: Description of the task performed
 outcome: Episode outcome (success/failure/partial)
 success: Whether the episode was successful
 constitutional_violations: List of constitutional violations during execution
 metadata: Additional episode metadata (merged with canvas metadata)

 Returns:
 Created AgentEpisode instance
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

 # Publish episode recording activity (menu bar companion)
 if self.activity_publisher:
 try:
 self.activity_publisher.publish_episode_recording(
 agent_id=str(execution.agent_id),
 episode_id="recording", # Will be updated after creation
 state="working",
 task_description=task_description,
 constitutional_violations=len(constitutional_violations or [])
 )
 except Exception as e:
 logger.warning(f"Failed to publish episode recording activity: {e}")

 # Calculate constitutional score
 constitutional_score = self._calculate_constitutional_score(
 constitutional_violations or []
 )

 # Calculate step efficiency (TRACE framework)
 step_efficiency = self._calculate_step_efficiency(execution_id)

 # Extract canvas metadata (NEW: Canvas-Enhanced Episodic Memory)
 canvas_metadata = await self._extract_canvas_metadata(execution_id, task_description=task_description)

 # Merge metadata with canvas context
 merged_metadata = metadata or {}
 merged_metadata.update(canvas_metadata)

 # Create episode
 episode = AgentEpisode(
 agent_id=execution.agent_id,
 execution_id=execution_id,
 task_description=task_description,
 maturity_at_time=agent.status,
 constitutional_score=constitutional_score,
 human_intervention_count=execution.human_intervention_count,
 confidence_score=agent.confidence_score,
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

 # Publish episode recording complete (menu bar companion)
 if self.activity_publisher:
 try:
 self.activity_publisher.publish_episode_recording(
 agent_id=str(execution.agent_id),
 episode_id=str(episode.id),
 state="idle",
 task_description=task_description,
 constitutional_violations=len(constitutional_violations or [])
 )
 except Exception as e:
 logger.warning(f"Failed to publish episode recording complete activity: {e}")

 logger.info(
 f"Created episode {episode.id} for agent {execution.agent_id} "
 f"(outcome={outcome}, constitutional_score={constitutional_score:.2f})"
 )

 return episode

 def get_graduation_readiness(
 self,
 agent_id: str,

 episode_count: int = 30,
 target_level: Optional[str] = None
 ) -> ReadinessResponse:
 """
 Calculate graduation readiness score for an agent.

 UPDATED READINESS FORMULA (with skill diversity integration):
 readiness = (zero_intervention_ratio * 0.30) +
 (avg_constitutional_score * 0.25) +
 (avg_confidence_score * 0.15) +
 (success_rate * 0.10) +
 (supervision_success_rate * 0.10) +
 (skill_diversity_score * 0.10)

 The new skill_diversity_score metric tracks the variety of skills
 an agent has successfully executed, showing broader capability.

 Args:
 agent_id: ID of the agent
 tenant_id: ID of the tenant (removed in upstream)
 episode_count: Number of recent episodes to analyze (default: 30)
 target_level: Target maturity level (if None, determines next level)

 Returns:
 ReadinessResponse with readiness score and breakdown (including skill metrics)
 """
 # Get agent
 agent = self.db.query(AgentRegistry).filter(
 and_(
 AgentRegistry.id == agent_id,
 AgentRegistry
 )
 ).first()

 if not agent:
 raise ValueError(f"tenant")

 current_level = agent.status

 # Determine target level if not specified
 if not target_level:
 target_level = self._get_next_level(current_level)

 # Get recent episodes
 episodes = self.db.query(AgentEpisode).filter(
 and_(
 AgentEpisode.agent_id == agent_id,
 AgentEpisode
 )
 ).order_by(AgentEpisode.started_at.desc()).limit(episode_count).all()

 if not episodes:
 # No episodes yet - return zero readiness
 return ReadinessResponse(
 agent_id=agent_id,
 current_level=current_level,
 readiness_score=0.0,
 threshold_met=False,
 zero_intervention_ratio=0.0,
 avg_constitutional_score=0.0,
 avg_confidence_score=agent.confidence_score,
 success_rate=0.0,
 episodes_analyzed=0,
 breakdown={"reason": "No episodes found"},
 supervision_success_rate=0.0
 )

 # Calculate metrics (including supervision)
 metrics = self.calculate_readiness_metrics(episodes)

 # Calculate supervision metrics
 supervision_metrics = self.calculate_supervision_metrics(episodes)

 # Calculate skill diversity metrics (NEW)
 skill_metrics = self.calculate_skill_diversity_metrics(
 agent_id=agent_id)

 # Calculate proposal quality metrics (Phase 224-04)
 proposal_quality_metrics = self.calculate_proposal_quality_metrics(
 agent_id=agent_id)

 # Calculate overall readiness score (UPDATED FORMULA with proposal quality)
 # Adjusted weights to accommodate proposal quality factor:
 # - Reduced skill_diversity from 0.10 to 0.07
 # - Added proposal_quality at 0.03 (small but meaningful)
 readiness_score = (
 metrics["zero_intervention_ratio"] * 0.30 + # Unchanged
 metrics["avg_constitutional_score"] * 0.25 + # Unchanged
 metrics["avg_confidence_score"] * 0.15 + # Unchanged
 metrics["success_rate"] * 0.10 + # Unchanged
 supervision_metrics["supervision_success_rate"] * 0.10 + # Unchanged
 skill_metrics["skill_diversity_score"] * 0.07 + # Reduced from 0.10
 proposal_quality_metrics["proposal_quality_score"] * 0.03 # NEW (Phase 224-04)
 )

 # Get threshold for target level
 threshold = self._get_threshold_for_level(target_level)
 threshold_met = readiness_score >= threshold

 return ReadinessResponse(
 agent_id=agent_id,
 current_level=current_level,
 readiness_score=round(readiness_score, 4),
 threshold_met=threshold_met,
 zero_intervention_ratio=round(metrics["zero_intervention_ratio"], 4),
 avg_constitutional_score=round(metrics["avg_constitutional_score"], 4),
 avg_confidence_score=round(metrics["avg_confidence_score"], 4),
 success_rate=round(metrics["success_rate"], 4),
 episodes_analyzed=len(episodes),
 supervision_success_rate=round(supervision_metrics["supervision_success_rate"], 4),
 breakdown={
 "target_level": target_level,
 "threshold": threshold,
 "episodes_by_outcome": metrics["episodes_by_outcome"],
 "total_interventions": metrics["total_interventions"],
 "avg_step_efficiency": round(metrics.get("avg_step_efficiency", 1.0), 4),
 "supervision_metrics": supervision_metrics,
 "skill_metrics": skill_metrics, # Skill diversity breakdown
 "proposal_quality_metrics": proposal_quality_metrics # NEW (Phase 224-04)
 }
 )

 def calculate_readiness_metrics(self, episodes: List[AgentEpisode]) -> Dict[str, Any]:
 """
 Calculate readiness metrics from a list of episodes.

 Returns:
 Dictionary with all readiness components
 """
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

 # Success rate
 successful = sum(1 for e in episodes if e.success)
 success_rate = successful / len(episodes)

 # Zero intervention ratio (episodes with no interventions)
 zero_interventions = sum(1 for e in episodes if e.human_intervention_count == 0)
 zero_intervention_ratio = zero_interventions / len(episodes)

 # Average constitutional score
 avg_constitutional_score = sum(e.constitutional_score for e in episodes) / len(episodes)

 # Average confidence score
 avg_confidence_score = sum(e.confidence_score for e in episodes) / len(episodes)

 # Episodes by outcome
 episodes_by_outcome = {}
 for episode in episodes:
 episodes_by_outcome[episode.outcome] = episodes_by_outcome.get(episode.outcome, 0) + 1

 # Total interventions
 total_interventions = sum(e.human_intervention_count for e in episodes)

 # Average step efficiency
 avg_step_efficiency = sum(e.step_efficiency for e in episodes if e.step_efficiency) / len(episodes) if episodes else 0.0

 return {
 "success_rate": success_rate,
 "zero_intervention_ratio": zero_intervention_ratio,
 "avg_constitutional_score": avg_constitutional_score,
 "avg_confidence_score": avg_confidence_score,
 "episodes_by_outcome": episodes_by_outcome,
 "total_interventions": total_interventions,
 "avg_step_efficiency": avg_step_efficiency
 }

 def calculate_supervision_metrics(self, episodes: List[AgentEpisode]) -> Dict[str, Any]:
 """
 Calculate supervision-specific metrics from episodes.

 Tracks intern agent performance under supervision:
 - Approval rate (approved proposals / total proposals)
 - Execution success rate (successful executions / approved proposals)
 - Supervisor type breakdown (user vs autonomous agent)
 - Overall supervision success rate

 Returns:
 Dictionary with supervision metrics
 """
 if not episodes:
 return {
 "total_proposals": 0,
 "approved_proposals": 0,
 "rejected_proposals": 0,
 "execution_success_rate": 0.0,
 "approval_rate": 0.0,
 "supervision_success_rate": 0.0,
 "supervisor_type_breakdown": {
 "user": 0,
 "autonomous_agent": 0
 }
 }

 # Filter episodes that are supervision-related (have proposal_id)
 supervision_episodes = [e for e in episodes if e.proposal_id is not None]

 if not supervision_episodes:
 return {
 "total_proposals": 0,
 "approved_proposals": 0,
 "rejected_proposals": 0,
 "execution_success_rate": 0.0,
 "approval_rate": 0.0,
 "supervision_success_rate": 0.0,
 "supervisor_type_breakdown": {
 "user": 0,
 "autonomous_agent": 0
 }
 }

 total_proposals = len(supervision_episodes)

 # Count approvals and rejections
 approved_proposals = sum(1 for e in supervision_episodes if e.supervision_decision == "approved")
 rejected_proposals = sum(1 for e in supervision_episodes if e.supervision_decision == "rejected")

 # Approval rate
 approval_rate = approved_proposals / total_proposals if total_proposals > 0 else 0.0

 # Execution success rate (successful executions of approved proposals)
 executed_successfully = sum(
 1 for e in supervision_episodes
 if e.supervision_decision == "approved" and e.execution_followed_proposal
 )
 execution_success_rate = executed_successfully / approved_proposals if approved_proposals > 0 else 0.0

 # Supervisor type breakdown
 supervisor_type_breakdown = {
 "user": sum(1 for e in supervision_episodes if e.supervisor_type == "user"),
 "autonomous_agent": sum(1 for e in supervision_episodes if e.supervisor_type == "autonomous_agent")
 }

 # Overall supervision success rate:
 # Combines approval rate and execution success rate
 # High approval rate + high execution success = high supervision success
 supervision_success_rate = (approval_rate * 0.6) + (execution_success_rate * 0.4)

 return {
 "total_proposals": total_proposals,
 "approved_proposals": approved_proposals,
 "rejected_proposals": rejected_proposals,
 "execution_success_rate": round(execution_success_rate, 4),
 "approval_rate": round(approval_rate, 4),
 "supervision_success_rate": round(supervision_success_rate, 4),
 "supervisor_type_breakdown": supervisor_type_breakdown
 }

 def calculate_skill_diversity_metrics(
 self,
 agent_id: str) -> Dict[str, Any]:
 """
 Calculate skill diversity metrics for graduation readiness.

 Tracks the variety of OpenClaw skills an agent has successfully executed.
 Agents using more diverse skills show broader capability.

 Args:
 agent_id: ID of the agent
 tenant_id: ID of the tenant (removed in upstream)

 Returns:
 Dictionary with skill diversity metrics
 """
 # Get skill usage summary
 skill_summaries = self.get_agent_skill_usage(
 agent_id=agent_id,
 limit=1000
 )

 # Count unique skills successfully executed
 unique_skill_count = len(skill_summaries)

 # Calculate skill diversity score (0.0 to 1.0)
 # Formula: min(unique_skill_count / 10, 1.0)
 # Agents using 10+ different diverse skills = max score
 # This encourages broad skill adoption
 skill_diversity_score = min(unique_skill_count / 10.0, 1.0)

 # Calculate average skill success rate across all skills
 if skill_summaries:
 avg_skill_success_rate = sum(
 s.success_rate for s in skill_summaries
 ) / len(skill_summaries)
 else:
 avg_skill_success_rate = 0.0

 # Get total skill execution count
 total_skill_executions = sum(
 s.execution_count for s in skill_summaries
 )

 return {
 "unique_skill_count": unique_skill_count,
 "skill_diversity_score": round(skill_diversity_score, 4),
 "avg_skill_success_rate": round(avg_skill_success_rate, 4),
 "total_skill_executions": total_skill_executions,
 "top_skills": [
 {
 "skill_id": s.skill_id,
 "skill_name": s.skill_name,
 "execution_count": s.execution_count,
 "success_rate": s.success_rate
 }
 for s in skill_summaries[:5] # Top 5 skills
 ]
 }

 def calculate_proposal_quality_metrics(
 self,
 agent_id: str) -> Dict[str, Any]:
 """
 Calculate proposal quality metrics for graduation readiness.

 Tracks the quality of Meta-Agent teaching moments the agent has received.
 Higher quality teaching moments indicate better mentorship and learning
 opportunities, which should contribute to graduation readiness.

 Args:
 agent_id: ID of the agent
 tenant_id: ID of the tenant (removed in upstream)

 Returns:
 Dictionary with proposal quality metrics
 """
 # Query proposal episodes for this agent
 proposal_episodes = self.db.query(AgentEpisode).filter(
 and_(
 AgentEpisode.agent_id == agent_id,
 AgentEpisode
 cast(AgentEpisode.metadata_json["episode_type"], String) == "meta_agent_proposal"
 )
 ).all()

 if not proposal_episodes:
 return {
 "proposal_episode_count": 0,
 "avg_proposal_quality": 0.0,
 "high_quality_proposal_count": 0,
 "proposal_quality_score": 0.0
 }

 # Extract quality scores
 quality_scores = []
 high_quality_count = 0

 for ep in proposal_episodes:
 metadata = ep.metadata_json or {}
 quality_score = metadata.get("quality_score", 0.0)

 if quality_score > 0:
 quality_scores.append(quality_score)
 if quality_score >= 0.8: # High quality threshold
 high_quality_count += 1

 # Calculate average quality
 if quality_scores:
 avg_proposal_quality = sum(quality_scores) / len(quality_scores)
 else:
 avg_proposal_quality = 0.0

 # Calculate proposal quality score (0.0 to 1.0)
 # Formula: min(avg_quality * 1.2, 1.0) - rewards high quality teaching
 # This means if average quality is 0.8+, score is 0.96 (near perfect)
 proposal_quality_score = min(avg_proposal_quality * 1.2, 1.0)

 return {
 "proposal_episode_count": len(proposal_episodes),
 "avg_proposal_quality": round(avg_proposal_quality, 4),
 "high_quality_proposal_count": high_quality_count,
 "proposal_quality_score": round(proposal_quality_score, 4)
 }

 def get_agent_episodes(
 self,
 agent_id: str,

 limit: int = 50,
 outcome_filter: Optional[str] = None,
 start_date: Optional[datetime] = None,
 end_date: Optional[datetime] = None
 ) -> List[AgentEpisode]:
 """
 Query episodes with filters.

 Args:
 agent_id: ID of the agent
 tenant_id: ID of the tenant (removed in upstream)
 limit: Maximum number of episodes to return
 outcome_filter: Filter by outcome (success/failure/partial)
 start_date: Filter episodes after this date
 end_date: Filter episodes before this date

 Returns:
 List of AgentEpisode instances
 """
 query = self.db.query(AgentEpisode).filter(
 and_(
 AgentEpisode.agent_id == agent_id,
 AgentEpisode
 )
 )

 if outcome_filter:
 query = query.filter(AgentEpisode.outcome == outcome_filter)

 if start_date:
 query = query.filter(AgentEpisode.started_at >= start_date)

 if end_date:
 query = query.filter(AgentEpisode.started_at <= end_date)

 return query.order_by(AgentEpisode.started_at.desc()).limit(limit).all()

 async def archive_episode_to_cold_storage(self, episode_id: str) -> bool:
 """
 Archive an episode to LanceDB (cold storage).

 This moves old episodes from PostgreSQL hot storage to LanceDB
 for long-term retention while keeping them available for semantic search.

 Args:
 episode_id: ID of the episode to archive

 Returns:
 True if archived successfully, False otherwise
 """
 try:
 # Get episode
 episode = self.db.query(AgentEpisode).filter(
 AgentEpisode.id == episode_id
 ).first()

 if not episode:
 logger.warning(f"Episode {episode_id} not found for archival")
 return False

 # Generate embedding for semantic search
 try:
 embedding = await self.embedding_service.generate_embedding(
 episode.task_description or ""
 )
 except Exception as e:
 logger.error(f"Failed to generate embedding for episode {episode_id}: {e}")
 # Use zero embedding as fallback with correct dimension
 vector_dim = self.embedding_service.get_embedding_dimension()
 embedding = [0.0] * vector_dim

 # Archive to LanceDB
 lancedb = self._get_lancedb()
 if not lancedb:
 logger.warning(f"LanceDB not available - episode {episode_id} not archived")
 return False

 success = lancedb.add_episode(episode, embedding)

 if success:
 logger.info(f"Episode {episode_id} archived to LanceDB successfully")
 
 # ACU Billing Integration
 try:
 acu_amount=1.0, # 1 ACU for archival overhead
 task_name=f"archive-episode-{episode_id}"
 )
 else:
 logger.error(f"Failed to archive episode {episode_id} to LanceDB")

 return success

 except Exception as e:
 logger.error(f"Error archiving episode {episode_id}: {e}")
 return False

 def _calculate_constitutional_score(
 self,
 violations: List[Dict[str, Any]]
 ) -> float:
 """
 Calculate constitutional compliance score from violations.

 Score formula: 1.0 - (severity_weighted_violations / max_possible)

 Severity weights:
 - critical: 1.0
 - high: 0.7
 - medium: 0.4
 - low: 0.1

 Args:
 violations: List of constitutional violations

 Returns:
 Compliance score from 0.0 to 1.0
 """
 if not violations:
 return 1.0

 severity_weights = {
 "critical": 1.0,
 "high": 0.7,
 "medium": 0.4,
 "low": 0.1
 }

 total_penalty = 0.0
 for violation in violations:
 severity = violation.get("severity", "low").lower()
 weight = severity_weights.get(severity, 0.1)
 total_penalty += weight

 # Cap penalty at 1.0
 penalty = min(total_penalty, 1.0)

 return max(0.0, 1.0 - penalty)

 def _calculate_step_efficiency(self, execution_id: str) -> float:
 """
 Calculate step efficiency using TRACE framework.

 Efficiency = optimal_steps / actual_steps

 Returns 1.0 if no reasoning steps recorded.

 Args:
 execution_id: ID of the execution

 Returns:
 Step efficiency score from 0.0 to 1.0
 """
 from core.models import AgentReasoningStep

 # Get reasoning steps for this execution
 steps = self.db.query(AgentReasoningStep).filter(
 AgentReasoningStep.execution_id == execution_id
 ).all()

 if not steps:
 return 1.0

 # Count actual steps
 actual_steps = len(steps)

 # Estimate optimal steps (simplified: remove redundant thought/observation cycles)
 optimal_steps = actual_steps
 redundant_count = 0

 for i, step in enumerate(steps):
 # Check for redundant thought-action pairs
 if i > 0 and steps[i-1].step_type == "thought" and step.step_type == "observation":
 # This is a normal ReAct cycle, not redundant
 continue
 if i > 1 and steps[i-2].step_type == "thought" and steps[i-1].step_type == "action" and step.step_type == "observation":
 # Normal cycle
 continue

 optimal_steps = max(1, actual_steps - redundant_count)

 # Calculate efficiency
 efficiency = optimal_steps / actual_steps if actual_steps > 0 else 1.0

 return round(efficiency, 4)

 def _get_next_level(self, current_level: str) -> str:
 """Get the next maturity level after current"""
 level_progression = {
 AgentStatus.STUDENT.value: AgentStatus.INTERN.value,
 AgentStatus.INTERN.value: AgentStatus.SUPERVISED.value,
 AgentStatus.SUPERVISED.value: AgentStatus.AUTONOMOUS.value,
 AgentStatus.AUTONOMOUS.value: AgentStatus.AUTONOMOUS.value # Max level
 }
 return level_progression.get(current_level, AgentStatus.INTERN.value)

 def _get_threshold_for_level(self, target_level: str) -> float:
 """Get readiness threshold for target level"""
 thresholds = {
 AgentStatus.INTERN.value: ReadinessThresholds.STUDENT_TO_INTERN["overall"],
 AgentStatus.SUPERVISED.value: ReadinessThresholds.INTERN_TO_SUPERVISED["overall"],
 AgentStatus.AUTONOMOUS.value: ReadinessThresholds.SUPERVISED_TO_AUTONOMOUS["overall"]
 }
 return thresholds.get(target_level, 0.70)

 # ============================================================================
 # Episode Feedback Methods (RLHF Integration)
 # ============================================================================

 def update_episode_feedback(
 self,
 episode_id: str,
 feedback_score: float,
 feedback_notes: Optional[str] = None,
 feedback_category: Optional[str] = None,
 provider_id: Optional[str] = None,
 capability_domain: Optional[str] = None, # NEW: Phase 247-06
 capability_name: Optional[str] = None # NEW: Phase 247-06
 ) -> str:
 """
 Update an episode with human feedback.

 This links RLHF feedback to specific episodes via a separate feedback table.
 Feedback is linked via metadata but retrieved completely for decision-making.

 Phase 247-06: Extended with capability domain tagging for per-capability RLHF.

 Args:
 episode_id: ID of the episode
 feedback_score: Feedback score (-1.0 to 1.0)
 feedback_notes: Optional detailed feedback notes
 feedback_category: Optional feedback category ("accuracy", "helpfulness", etc.)
 provider_id: Optional ID of the feedback provider
 capability_domain: Optional capability domain (data_analysis, code_execution, etc.)
 capability_name: Optional specific capability being feedback on

 Returns:
 ID of the created feedback record

 Raises:
 ValueError: If episode not found
 """
 try:
 from core.models import EpisodeFeedback

 # Verify episode exists
 episode = self.db.query(AgentEpisode).filter(
 AgentEpisode.id == episode_id
 ).first()

 if not episode:
 raise ValueError(f"Episode {episode_id} not found")

 # Create feedback record (separate table for full retrieval)
 feedback = EpisodeFeedback(
 id=str(uuid.uuid4()),
 episode_id=episode_id,
 feedback_score=feedback_score,
 feedback_notes=feedback_notes[:500] if feedback_notes else None, # Limit length
 feedback_category=feedback_category,
 capability_domain=capability_domain, # NEW: Phase 247-06
 capability_name=capability_name, # NEW: Phase 247-06
 provider_id=provider_id,
 provider_type="human",
 provided_at=datetime.now(timezone.utc)
 )

 self.db.add(feedback)

 # Update episode metadata with link (reference only)
 episode.metadata_json = episode.metadata_json or {}
 episode.metadata_json["feedback_id"] = feedback.id
 episode.metadata_json["feedback_score"] = feedback_score
 episode.metadata_json["feedback_provided_at"] = datetime.now(timezone.utc).isoformat()

 # Phase 247-06: Update capability usage stats when feedback submitted
 if capability_name and capability_domain:
 try:
 from core.capability_graduation_service import CapabilityGraduationService

 grad_service = CapabilityGraduationService(self.db)

 # Record usage with feedback outcome (positive feedback = successful use)
 success = feedback_score >= 0.7 # Positive feedback threshold
 grad_service.record_capability_usage(
 agent_id=episode.agent_id,
 capability_name=capability_name,
 success=success,
 capability_domain=capability_domain
 )

 logger.info(
 f"Recorded capability usage from feedback: {capability_name} "
 f"(domain={capability_domain}, success={success}, score={feedback_score})"
 )
 except Exception as cap_err:
 # Don't fail feedback submission if capability tracking fails
 logger.warning(f"Failed to record capability usage from feedback: {cap_err}")

 self.db.commit()
 self.db.refresh(feedback)

 logger.info(
 f"Created feedback {feedback.id} for episode {episode_id} "
 f"(score={feedback_score}, domain={capability_domain}, capability={capability_name})"
 )

 # Also sync to LanceDB for enhanced recall (fire and forget)
 try:
 loop = asyncio.get_event_loop()
 if loop.is_running():
 # If loop is running, create task in background
 asyncio.ensure_future(self._sync_feedback_to_lancedb(episode, feedback))
 else:
 # If no loop running, skip LanceDB sync for test compatibility
 logger.debug("No event loop running, skipping LanceDB sync")
 except RuntimeError:
 # No loop yet, skip sync in test environments
 logger.debug("Event loop not available, skipping LanceDB sync")

 return feedback.id

 except Exception as e:
 logger.error(f"Failed to create episode feedback: {e}")
 self.db.rollback()
 raise

 def get_episode_feedback(
 self,
 episode_id: str
 ) -> List[Dict[str, Any]]:
 """
 Get all feedback records for an episode.

 Retrieves complete feedback details for agent decision-making.

 Args:
 episode_id: ID of the episode

 Returns:
 List of feedback records with full details
 """
 try:
 from core.models import EpisodeFeedback

 feedback_records = self.db.query(EpisodeFeedback).filter(
 EpisodeFeedback.episode_id == episode_id
 ).order_by(EpisodeFeedback.provided_at.desc()).all()

 return [
 {
 "id": f.id,
 "feedback_score": f.feedback_score,
 "feedback_notes": f.feedback_notes,
 "feedback_category": f.feedback_category,
 "provider_id": f.provider_id,
 "provider_type": f.provider_type,
 "provided_at": f.provided_at.isoformat()
 }
 for f in feedback_records
 ]

 except Exception as e:
 logger.error(f"Failed to get episode feedback: {e}")
 return []

 def get_domain_feedback_metrics(
 self,

 domain: str,
 days: int = 30
 ) -> Dict[str, Any]:
 """
 Get aggregated feedback metrics for a specific capability domain.

 Phase 247-06: Domain-specific RLHF metrics for capability graduation.

 Args:
 tenant_id: Tenant ID for multi-tenancy
 domain: Capability domain (data_analysis, code_execution, integrations, reasoning)
 days: Number of days to look back (default 30)

 Returns:
 Dict with aggregated metrics: avg_rating, feedback_count, trend, by_maturity
 """
 try:
 from core.models import EpisodeFeedback
 from datetime import timedelta

 # Calculate date threshold
 since_date = datetime.now(timezone.utc) - timedelta(days=days)

 # Query feedback for domain
 feedback_query = self.db.query(EpisodeFeedback).filter(
 and_(
 EpisodeFeedback
 EpisodeFeedback.capability_domain == domain,
 EpisodeFeedback.provided_at >= since_date
 )
 )

 all_feedback = feedback_query.all()

 if not all_feedback:
 return {
 "domain": domain,
 "days": days,
 "avg_rating": 0.0,
 "feedback_count": 0,
 "positive_count": 0,
 "negative_count": 0,
 "neutral_count": 0,
 "trend": "no_data",
 "by_capability": {}
 }

 # Calculate metrics
 feedback_count = len(all_feedback)
 avg_rating = sum(f.feedback_score for f in all_feedback) / feedback_count

 # Count by sentiment
 positive_count = sum(1 for f in all_feedback if f.feedback_score >= 0.7)
 negative_count = sum(1 for f in all_feedback if f.feedback_score <= -0.7)
 neutral_count = feedback_count - positive_count - negative_count

 # Calculate trend (compare first half vs second half)
 midpoint = feedback_count // 2
 first_half = all_feedback[:midpoint] if midpoint > 0 else []
 second_half = all_feedback[midpoint:] if midpoint > 0 else all_feedback

 if first_half and second_half:
 first_avg = sum(f.feedback_score for f in first_half) / len(first_half)
 second_avg = sum(f.feedback_score for f in second_half) / len(second_half)

 if second_avg > first_avg + 0.1:
 trend = "improving"
 elif second_avg < first_avg - 0.1:
 trend = "declining"
 else:
 trend = "stable"
 else:
 trend = "insufficient_data"

 # Group by capability (if capability_name available)
 by_capability = {}
 for f in all_feedback:
 if f.capability_name:
 if f.capability_name not in by_capability:
 by_capability[f.capability_name] = {
 "count": 0,
 "avg_score": 0.0,
 "scores": []
 }
 by_capability[f.capability_name]["count"] += 1
 by_capability[f.capability_name]["scores"].append(f.feedback_score)

 # Calculate averages per capability
 for cap_name in by_capability:
 scores = by_capability[cap_name]["scores"]
 by_capability[cap_name]["avg_score"] = round(sum(scores) / len(scores), 3)
 del by_capability[cap_name]["scores"] # Remove raw scores

 return {
 "domain": domain,
 "days": days,
 "avg_rating": round(avg_rating, 3),
 "feedback_count": feedback_count,
 "positive_count": positive_count,
 "negative_count": negative_count,
 "neutral_count": neutral_count,
 "trend": trend,
 "by_capability": by_capability
 }

 except Exception as e:
 logger.error(f"Failed to get domain feedback metrics: {e}")
 return {
 "domain": domain,
 "error": str(e),
 "avg_rating": 0.0,
 "feedback_count": 0
 }

 async def _sync_feedback_to_lancedb(
 self,
 episode: AgentEpisode,
 feedback: 'EpisodeFeedback'
 ) -> bool:
 """
 Sync feedback updates to LanceDB for semantic search enhancement.

 Stores feedback reference in LanceDB metadata, but full feedback
 details are retrieved from PostgreSQL during agent decision-making.
 """
 try:
 from core.agent_world_model import WorldModelService

 world_model = WorldModelService("default")

 # Build learnings string that includes feedback
 learnings = episode.metadata_json.get("learnings", "")
 if feedback.feedback_notes:
 learnings += f"\n[Feedback: {feedback.feedback_notes}]"

 # Update the episode in LanceDB with feedback metadata
 success = await world_model.record_episode(
 episode_id=episode.id,
 agent_id=episode.agent_id,
 task_description=episode.task_description or "",
 outcome=episode.outcome,
 learnings=learnings,
 agent_role=episode.metadata_json.get("agent_role", "unknown"),
 maturity_at_time=episode.maturity_at_time,
 constitutional_score=episode.constitutional_score,
 human_intervention_count=episode.human_intervention_count,
 confidence_score=episode.confidence_score,
 metadata=episode.metadata_json # Includes feedback_id reference
 )

 if success:
 logger.info(f"Synced feedback for episode {episode.id} to LanceDB")

 return success

 except Exception as e:
 logger.error(f"Failed to sync feedback to LanceDB: {e}")
 return False

 # ============================================================================
 # Canvas Action Linking Methods
 # ============================================================================

 def get_canvas_actions_for_episode(
 self,
 episode_id: str
 ) -> List[Dict[str, Any]]:
 """
 Retrieve complete canvas action records for an episode.

 Called during agent decision-making to provide full canvas context,
 including form submissions, canvas closes, user interactions, etc.

 Args:
 episode_id: ID of the episode

 Returns:
 List of canvas action records
 """
 try:
 from core.models import CanvasAudit

 episode = self.db.query(AgentEpisode).filter(
 AgentEpisode.id == episode_id
 ).first()

 if not episode:
 return []

 canvas_action_ids = episode.metadata_json.get("canvas_action_ids", [])
 if not canvas_action_ids:
 return []

 # Fetch complete action records from canvas system
 actions = self.db.query(CanvasAudit).filter(
 CanvasAudit.id.in_(canvas_action_ids)).all()

 return [
 {
 "id": action.id,
 "action_type": action.action_type,
 "canvas_id": action.canvas_id,
 "user_id": action.user_id,
 "details": action.details_json,
 "created_at": action.created_at.isoformat()
 }
 for action in actions
 ]

 except Exception as e:
 logger.error(f"Failed to get canvas actions for episode: {e}")
 return []

 async def recall_episodes_with_detail(
 self,
 agent_id: str,

 detail_level: DetailLevel = DetailLevel.SUMMARY,
 limit: int = 30
 ) -> List[Dict[str, Any]]:
 """
 Recall episodes with progressive detail level

 Args:
 agent_id: Agent to recall episodes for
 tenant_id: Tenant ID for security filtering
 detail_level: Summary (50 tokens), Standard (200), Full (500)
 limit: Maximum episodes to return

 Returns:
 List of episodes with detail appropriate to level
 """
 # Verify tenant owns agent
 agent_check = await self.db.execute(
 text("SELECT id FROM agent_registry WHERE id = :agent_id AND= :"),
 {"agent_id": agent_id, }
 )
 if not agent_check.scalar_one_or_none():
 logger.warning(f"tenant")
 return []

 # Get query template for detail level
 query = PROGRESSIVE_QUERIES.get(detail_level, PROGRESSIVE_QUERIES[DetailLevel.SUMMARY])

 # Execute query
 result = await self.db.execute(
 text(query),
 {"agent_id": agent_id, "limit": limit}
 )

 rows = result.fetchall()
 episodes = [dict(row._mapping) for row in rows]

 return episodes

 async def link_canvas_actions_to_episode(
 self,
 episode_id: str,
 canvas_action_ids: List[str]
 ) -> bool:
 """
 Link canvas audit actions to an episode

 This should be called after episode creation if canvas
 actions were performed during the episode.

 Args:
 episode_id: Episode to link to
 canvas_action_ids: List of CanvasAudit record IDs

 Returns:
 True if successful
 """
 try:
 from sqlalchemy import update

 episode = self.db.query(AgentEpisode).filter(
 AgentEpisode.id == episode_id
 ).first()

 if not episode:
 logger.error(f"Episode {episode_id} not found for canvas action linking")
 return False

 # Update episode metadata with canvas action IDs
 episode.metadata_json = episode.metadata_json or {}
 episode.metadata_json["canvas_action_ids"] = canvas_action_ids

 self.db.commit()
 logger.info(f"Linked {len(canvas_action_ids)} canvas actions to episode {episode_id}")
 return True

 except Exception as e:
 logger.error(f"Failed to link canvas actions to episode {episode_id}: {e}")
 self.db.rollback()
 return False

 # ============================================================================
 # Skill Performance Tracking Methods (OpenClaw Integration)
 # ============================================================================

 @dataclass
 class SkillPerformanceStats:
 """Skill performance statistics for a specific skill"""
 skill_id: str
 skill_name: Optional[str] # From Skill.name join
 total_executions: int
 successful_executions: int
 success_rate: float
 avg_execution_time: Optional[float] # In seconds
 last_executed_at: Optional[datetime]

 @dataclass
 class SkillUsageSummary:
 """Summary of skill usage for an agent"""
 skill_id: str
 skill_name: Optional[str]
 execution_count: int
 success_rate: float
 last_executed_at: Optional[datetime]

 @dataclass
 class SkillMasteryAssessment:
 """Skill mastery assessment for graduation readiness"""
 mastery_score: float # Overall mastery score (0.0 to 1.0)
 skill_diversity: float # Unique skills used / required skills for level
 skill_success_rate: float # Average success rate across all skills
 skill_execution_count: int # Total OpenClaw skill executions
 required_skills_for_level: int # Required skills for target maturity level
 skills_used: set # Set of skill_id strings used by agent

 def get_skill_performance_stats(
 self,
 agent_id: str,

 skill_id: str,
 limit: int = 100
 ) -> SkillPerformanceStats:
 """
 Get performance statistics for a specific skill used by an agent.

 Queries AgentEpisode filtered by:
 - agent_id and tenant_id
 - metadata_json @> '{"skill_type": "openclaw"}' (JSONB contains skill_type)
 - metadata_json @> '{"skill_id": "<skill_id>"}' (specific skill)

 Args:
 agent_id: ID of the agent
 tenant_id: ID of the tenant (removed in upstream)
 skill_id: ID of the skill to analyze
 limit: Maximum number of episodes to analyze

 Returns:
 SkillPerformanceStats with execution metrics
 """
 # Query episodes with JSONB metadata filtering for OpenClaw skill executions

 episodes = self.db.query(AgentEpisode).filter(
 and_(
 AgentEpisode.agent_id == agent_id,
 AgentEpisode
 cast(AgentEpisode.metadata_json["skill_type"], String) == "openclaw",
 cast(AgentEpisode.metadata_json["skill_id"], String) == skill_id
 )
 ).order_by(AgentEpisode.started_at.desc()).limit(limit).all()

 if not episodes:
 # Try to get skill name for empty stats
 from core.models import Skill
 skill = self.db.query(Skill).filter(Skill.id == skill_id).first()
 skill_name = skill.name if skill else None

 return self.SkillPerformanceStats(
 skill_id=skill_id,
 skill_name=skill_name,
 total_executions=0,
 successful_executions=0,
 success_rate=0.0,
 avg_execution_time=None,
 last_executed_at=None
 )

 # Calculate statistics
 total_executions = len(episodes)
 successful_executions = sum(1 for e in episodes if e.success)
 success_rate = successful_executions / total_executions if total_executions > 0 else 0.0

 # Calculate average execution time (from started_at to completed_at)
 execution_times = []
 for ep in episodes:
 if ep.completed_at and ep.started_at:
 duration = (ep.completed_at - ep.started_at).total_seconds()
 execution_times.append(duration)

 avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else None

 # Get last execution time
 last_executed_at = episodes[0].completed_at if episodes else None

 # Get skill name from Skill table
 from core.models import Skill
 skill = self.db.query(Skill).filter(Skill.id == skill_id).first()
 skill_name = skill.name if skill else None

 return self.SkillPerformanceStats(
 skill_id=skill_id,
 skill_name=skill_name,
 total_executions=total_executions,
 successful_executions=successful_executions,
 success_rate=round(success_rate, 4),
 avg_execution_time=round(avg_execution_time, 2) if avg_execution_time else None,
 last_executed_at=last_executed_at
 )

 def get_agent_skill_usage(
 self,
 agent_id: str,

 limit: int = 1000
 ) -> List[SkillUsageSummary]:
 """
 Get skill usage summary for an agent, grouped by skill.

 Queries all OpenClaw skill episodes for agent and groups by skill_id.

 Args:
 agent_id: ID of the agent
 tenant_id: ID of the tenant (removed in upstream)
 limit: Maximum number of episodes to analyze

 Returns:
 List of SkillUsageSummary sorted by execution_count DESC
 """
 from collections import defaultdict

 # Query all OpenClaw skill episodes for this agent
 episodes = self.db.query(AgentEpisode).filter(
 and_(
 AgentEpisode.agent_id == agent_id,
 AgentEpisode
 cast(AgentEpisode.metadata_json["skill_type"], String) == "openclaw"
 )
 ).order_by(AgentEpisode.started_at.desc()).limit(limit).all()

 # Group by skill_id
 skill_stats = defaultdict(lambda: {
 "executions": [],
 "skill_name": None
 })

 for ep in episodes:
 skill_id = ep.metadata_json.get("skill_id") if ep.metadata_json else None
 if not skill_id:
 continue

 skill_stats[skill_id]["executions"].append(ep)

 # Build SkillUsageSummary for each skill
 summaries = []
 for skill_id, stats in skill_stats.items():
 executions = stats["executions"]
 execution_count = len(executions)
 successful = sum(1 for e in executions if e.success)
 success_rate = successful / execution_count if execution_count > 0 else 0.0

 # Get last executed time
 last_executed_at = executions[0].completed_at if executions else None

 # Get skill name from Skill table
 from core.models import Skill
 skill = self.db.query(Skill).filter(Skill.id == skill_id).first()
 skill_name = skill.name if skill else None

 summaries.append(self.SkillUsageSummary(
 skill_id=skill_id,
 skill_name=skill_name,
 execution_count=execution_count,
 success_rate=round(success_rate, 4),
 last_executed_at=last_executed_at
 ))

 # Sort by execution_count DESC
 summaries.sort(key=lambda x: x.execution_count, reverse=True)

 return summaries

 def get_skill_usage_count(
 self,
 agent_id: str) -> int:
 """
 Count OpenClaw skill executions for an agent.

 Used by GraduationExamService for readiness calculation.

 Args:
 agent_id: ID of the agent
 tenant_id: ID of the tenant (removed in upstream)

 Returns:
 Integer count of OpenClaw skill executions
 """
 count = self.db.query(AgentEpisode).filter(
 and_(
 AgentEpisode.agent_id == agent_id,
 AgentEpisode
 cast(AgentEpisode.metadata_json["skill_type"], String) == "openclaw"
 )
 ).count()

 return count

 def get_required_skills_for_level(self, target_level: str) -> int:
 """
 Get minimum required skills for a maturity level.

 Args:
 target_level: Target maturity level (student, intern, supervised, autonomous)

 Returns:
 Minimum required skills for the level
 """
 required_skills = {
 "student": 1,
 "intern": 3,
 "supervised": 5,
 "autonomous": 10
 }
 return required_skills.get(target_level.lower(), 1)

 def assess_skill_mastery(
 self,
 agent_id: str,

 target_level: str
 ) -> SkillMasteryAssessment:
 """
 Assess skill mastery for graduation readiness.

 Evaluates agent's proficiency with OpenClaw skills to determine
 if they meet skill requirements for target maturity level.

 Args:
 agent_id: ID of the agent
 tenant_id: ID of the tenant (removed in upstream)
 target_level: Target maturity level

 Returns:
 SkillMasteryAssessment with mastery metrics
 """
 # Get required skills for target level
 required_skills = self.get_required_skills_for_level(target_level)

 # Get skill usage summaries
 skill_summaries = self.get_agent_skill_usage(
 agent_id=agent_id,
 limit=1000
 )

 # Count unique skills used
 unique_skills = len(skill_summaries)
 skills_used = {s.skill_id for s in skill_summaries}

 # Calculate skill diversity (0.0 to 1.0)
 # Formula: unique_skills / required_skills (capped at 1.0)
 skill_diversity = min(unique_skills / required_skills, 1.0) if required_skills > 0 else 0.0

 # Calculate average skill success rate
 if skill_summaries:
 skill_success_rate = sum(s.success_rate for s in skill_summaries) / len(skill_summaries)
 else:
 skill_success_rate = 0.0

 # Count total skill executions
 skill_execution_count = sum(s.execution_count for s in skill_summaries)

 # Calculate mastery score (weighted combination)
 # Mastery = (skill_diversity * 0.6) + (skill_success_rate * 0.4)
 # This weights diversity higher than success rate to encourage skill breadth
 mastery_score = (skill_diversity * 0.6) + (skill_success_rate * 0.4)

 return self.SkillMasteryAssessment(
 mastery_score=round(mastery_score, 4),
 skill_diversity=round(skill_diversity, 4),
 skill_success_rate=round(skill_success_rate, 4),
 skill_execution_count=skill_execution_count,
 required_skills_for_level=required_skills,
 skills_used=skills_used
 )

 # ============================================================================
 # Proposal Episode Methods (Phase 224-04)
 # ============================================================================

 def get_proposal_episodes_for_learning(
 self,

 agent_id: str,
 capability_tags: List[str] = None,
 min_quality: float = 0.7,
 limit: int = 10
 ) -> List[Dict[str, Any]]:
 """
 Retrieve high-quality proposal episodes for agent learning.

 Filters by:
 - Quality score (only high-quality teaching moments)
 - Capability tags (relevant to agent's task)
 - Tenant isolation

 Args:
 tenant_id: Tenant namespace
 agent_id: Agent to retrieve episodes for
 capability_tags: Filter by capability tags
 min_quality: Minimum quality score (default 0.7)
 limit: Maximum number of episodes

 Returns:
 List of proposal episodes sorted by quality (descending)
 """
 # Query proposal episodes with tenant and agent filtering
 query = self.db.query(AgentEpisode).filter(
 and_(
 AgentEpisode.agent_id == agent_id,
 AgentEpisode
 cast(AgentEpisode.metadata_json["episode_type"], String) == "meta_agent_proposal"
 )
 )

 # Filter by quality score
 query = query.filter(
 cast(AgentEpisode.metadata_json["quality_score"], String).cast(Float) >= min_quality
 )

 # Order by quality score DESC
 query = query.order_by(
 cast(AgentEpisode.metadata_json["quality_score"], String).cast(Float).desc()
 )

 episodes = query.limit(limit).all()

 # Build results
 results = []
 for ep in episodes:
 metadata = ep.metadata_json or {}

 # Filter by capability tags if specified
 if capability_tags:
 episode_capabilities = metadata.get("capability_tags", [])
 if not any(cap in episode_capabilities for cap in capability_tags):
 continue

 results.append({
 "episode_id": ep.id,
 "proposal_id": metadata.get("proposal_id"),
 "task_description": ep.task_description,
 "quality_score": metadata.get("quality_score"),
 "teaching_value": metadata.get("teaching_value"),
 "capability_tags": metadata.get("capability_tags", []),
 "meta_agent_guidance": metadata.get("meta_agent_guidance"),
 "quality_breakdown": metadata.get("quality_breakdown", {}),
 "created_at": ep.started_at.isoformat() if ep.started_at else None
 })

 return results

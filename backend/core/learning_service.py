"""
LearningService - Backend service for recording and analyzing agent learning experiences.

This service provides the backend implementation for the cognitive architecture's
learning and adaptation system. It records user corrections, analyzes patterns and stores experiences for future adaptation opportunities.
"""

from sqlalchemy.orm import Session
from core.models import CognitiveExperience, AgentMemory
from typing import Dict, Any, Optional, List
import uuid
import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class LearningService:
 """Service for recording and analyzing agent learning experiences"""

 def __init__(self, db: Session):
 self.db = db

 async def record_user_correction(
 self,
 agent_id: str,

 original_action: Dict[str, Any],
 corrected_action: Dict[str, Any],
 context: Optional[str] = None
 ) -> str:
 """
 Record a user correction for agent learning.

 This captures the difference between what the agent proposed and what
 the user corrected it to, enabling the learning system to identify patterns
 and adapt future behavior.

 Args:
 agent_id: The agent that made the original proposal
 tenant_id: Tenant context (removed in upstream) for multi-tenancy
 original_action: The action the agent originally proposed
 corrected_action: The action the user corrected to
 context: Optional context about when/why the correction occurred

 Returns:
 experience_id: UUID of the recorded experience
 """
 experience_id = str(uuid.uuid4())

 try:
 # Classify the correction type
 correction_type = self._classify_correction(original_action, corrected_action)

 experience = CognitiveExperience(
 id=experience_id,
 agent_id=agent_id,
 experience_type="user_correction",
 task_type=corrected_action.get("action_type", "unknown"),
 input_summary=context or "User correction in canvas",
 output_summary=json.dumps({
 "original": original_action,
 "corrected": corrected_action
 }),
 outcome="correction",
 learnings={
 "original_action": original_action,
 "corrected_action": corrected_action,
 "correction_type": correction_type,
 "timestamp": datetime.now(timezone.utc).isoformat()
 },
 effectiveness_score=0.0 # Will be updated based on future performance
 )

 self.db.add(experience)
 self.db.commit()

 logger.info(
 f"Recorded user correction for agent {agent_id}: "
 f"{correction_type} in tenant {tenant_id}"
 )

 return experience_id

 except Exception as e:
 logger.error(f"Failed to record user correction: {e}")
 self.db.rollback()
 raise

 def _classify_correction(self, original: Dict, corrected: Dict) -> str:
 """
 Classify the type of correction made.

 This helps the learning system understand what kind of mistake the agent made,
 enabling more targeted adaptations.

 Args:
 original: The original action proposed by the agent
 corrected: The corrected action from the user

 Returns:
 correction_type: One of 'action_type_change', 'parameter_adjustment', 'other_correction'
 """
 if not isinstance(original, dict) or not isinstance(corrected, dict):
 return "other_correction"

 # Check if the action type itself changed
 if original.get("action_type") != corrected.get("action_type"):
 return "action_type_change"

 # Check if parameters changed
 if original.get("parameters") != corrected.get("parameters"):
 return "parameter_adjustment"

 # Check other common fields
 for key in ["target", "content", "recipient", "endpoint"]:
 if original.get(key) != corrected.get(key):
 return "parameter_adjustment"

 return "other_correction"

 async def get_recent_experiences(
 self,
 agent_id: str,

 limit: int = 50,
 experience_type: Optional[str] = None
 ) -> List[CognitiveExperience]:
 """
 Get recent experiences for pattern analysis.

 This retrieves recent learning experiences for an agent, which can be
 analyzed to identify patterns and generate adaptation suggestions.

 Args:
 agent_id: The agent to get experiences for
 tenant_id: Tenant context (removed in upstream) for multi-tenancy
 limit: Maximum number of experiences to retrieve
 experience_type: Optional filter for specific experience types

 Returns:
 List of recent cognitive experiences
 """
 try:
 query = self.db.query(CognitiveExperience).filter(
 CognitiveExperience.agent_id == agent_id,
 CognitiveExperience
 )

 if experience_type:
 query = query.filter(CognitiveExperience.experience_type == experience_type)

 experiences = query.order_by(
 CognitiveExperience.created_at.desc()
 ).limit(limit).all()

 logger.info(f"Retrieved {len(experiences)} experiences for agent {agent_id}")
 return experiences

 except Exception as e:
 logger.error(f"Failed to get recent experiences: {e}")
 return []

 async def analyze_failure_patterns(
 self,
 agent_id: str,

 min_occurrences: int = 3
 ) -> List[Dict[str, Any]]:
 """
 Analyze recent failures to identify recurring patterns.

 This is a key part of the learning system - identifying what kinds of
 mistakes the agent makes repeatedly so they can be addressed through
 adaptation.

 Args:
 agent_id: The agent to analyze
 tenant_id: Tenant context (removed in upstream) for multi-tenancy
 min_occurrences: Minimum number of occurrences to consider it a pattern

 Returns:
 List of identified failure patterns with occurrence counts
 """
 try:
 experiences = await self.get_recent_experiences(
 agent_id,
 tenant_id,
 limit=100
 )

 # Filter for failures and corrections
 failures = [e for e in experiences if e.outcome in ["failure", "correction"]]

 # Group by correction type
 patterns = {}
 for experience in failures:
 try:
 learnings = experience.learnings if isinstance(experience.learnings, dict) else {}
 correction_type = learnings.get("correction_type", "unknown")

 if correction_type not in patterns:
 patterns[correction_type] = {
 "correction_type": correction_type,
 "count": 0,
 "recent_examples": []
 }

 patterns[correction_type]["count"] += 1

 # Keep up to 3 recent examples
 if len(patterns[correction_type]["recent_examples"]) < 3:
 patterns[correction_type]["recent_examples"].append({
 "experience_id": experience.id,
 "task_type": experience.task_type,
 "created_at": experience.created_at.isoformat() if experience.created_at else None
 })

 except Exception as e:
 logger.warning(f"Failed to process experience {experience.id}: {e}")
 continue

 # Filter by minimum occurrences
 significant_patterns = [
 pattern for pattern in patterns.values()
 if pattern["count"] >= min_occurrences
 ]

 # Sort by frequency (most common first)
 significant_patterns.sort(key=lambda p: p["count"], reverse=True)

 logger.info(
 f"Found {len(significant_patterns)} significant failure patterns "
 f"for agent {agent_id}"
 )

 return significant_patterns

 return significant_patterns

 except Exception as e:
 logger.error(f"Failed to analyze failure patterns: {e}")
 return []

 async def record_rejection(
 self,
 agent_id: str,

 action_type: str,
 action_data: Dict[str, Any],
 reason: Optional[str] = None,
 context: Optional[str] = None
 ) -> str:
 """
 Record a user rejection for agent learning.
 
 This captures when a user explicitly rejects an agent's proposal,
 allowing the system to identify problematic action types or parameters.
 """
 experience_id = str(uuid.uuid4())
 try:
 experience = CognitiveExperience(
 id=experience_id,
 agent_id=agent_id,
 experience_type="user_rejection",
 task_type=action_type,
 input_summary=context or "User rejection in canvas",
 output_summary=json.dumps({
 "proposed_action": action_data,
 "rejection_reason": reason
 }),
 outcome="rejection",
 learnings={
 "proposed_action": action_data,
 "rejection_reason": reason,
 "rejection_type": "explicit_rejection"
 },
 effectiveness_score=-0.5 # Negative impact for rejections
 )

 self.db.add(experience)
 self.db.commit()

 logger.info(f"Recorded user rejection for agent {agent_id}: {action_type} in tenant {tenant_id}")
 return experience_id

 except Exception as e:
 logger.error(f"Failed to record user rejection: {e}")
 self.db.rollback()
 raise

 async def record_adaptation(
 self,
 agent_id: str,

 adaptation_type: str,
 adaptation_data: Dict[str, Any],
 expected_impact: str
 ) -> str:
 """
 Record an adaptation made to agent behavior.

 This stores adaptations in agent memory so they can be tracked and
 their effectiveness measured over time.

 Args:
 agent_id: The agent being adapted
 tenant_id: Tenant context (removed in upstream) for multi-tenancy
 adaptation_type: Type of adaptation (e.g., 'parameter_tuning', 'behavior_change')
 adaptation_data: The adaptation details
 expected_impact: What improvement is expected

 Returns:
 memory_id: UUID of the stored adaptation memory
 """
 memory_id = str(uuid.uuid4())

 try:
 memory = AgentMemory(
 id=memory_id,
 agent_id=agent_id,
 content=adaptation_data,
 memory_type="adaptation",
 importance_score=0.8, # Adaptations are important
 metadata={
 "adaptation_type": adaptation_type,
 "expected_impact": expected_impact,
 "created_at": datetime.now(timezone.utc).isoformat()
 }
 )

 self.db.add(memory)
 self.db.commit()

 logger.info(
 f"Recorded adaptation for agent {agent_id}: "
 f"{adaptation_type} in tenant {tenant_id}"
 )

 return memory_id

 except Exception as e:
 logger.error(f"Failed to record adaptation: {e}")
 self.db.rollback()
 raise

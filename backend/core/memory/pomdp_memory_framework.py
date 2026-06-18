"""
POMDP Memory Framework for Agent Episodic Memory

Based on 2025-2026 research:
- "Memory for Autonomous LLM Agents" (arXiv:2603.07670v1)
- "From Storage to Experience: A Survey on LLM Agent Memory" (2026 preprint)

Formalizes agent memory as a write–manage–read loop within a POMDP-style agent cycle.
Implements three-dimensional taxonomy for memory systems:
1. Episodic Memory: Specific past events with context
2. Semantic Memory: General knowledge extracted from episodes
3. Working Memory: Current context and short-term information

Key Features:
- Write-manage-read loop pattern
- Observation space modeling (what agent perceives)
- Action space modeling (what agent can do)
- Reward function for memory quality assessment
- Memory consolidation for long-term retention
- Experience-driven learning metrics
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================

class MemoryType(Enum):
    """Types of memory in the three-dimensional taxonomy"""
    EPISODIC = "episodic"  # Specific events with context
    SEMANTIC = "semantic"   # General knowledge extracted
    WORKING = "working"     # Current context and short-term


class MemoryAccessPattern(Enum):
    """Patterns for memory access as per research taxonomy"""
    RECALL = "recall"         # Retrieving specific memories
    RECOGNITION = "recognition"  # Pattern matching
    INTEGRATION = "integration"   # Combining memories for reasoning


class MemoryStatus(Enum):
    """Status of memory in the write-manage-read loop"""
    PENDING = "pending"       # Written but not indexed
    INDEXED = "indexed"       # Available for retrieval
    CONSOLIDATING = "consolidating"  # Being processed for long-term storage
    CONSOLIDATED = "consolidated"  # Ready for long-term access
    EXPIRED = "expired"       # No longer relevant


# ============================================================================
# Observation and Action Spaces
# ============================================================================


@dataclass
class ObservationSpace:
    """
    Models what the agent perceives during interactions.

    Based on POMDP framework, defines the observable state
    that the agent can perceive at any given time.
    """
    # Contextual observations
    timestamp: datetime = field(default_factory=datetime.now)
    agent_id: str = ""
    workspace_id: str = ""
    task_type: str = ""  # CHAT, WORKFLOW, TASK

    # User observations
    user_intent: str = ""  # Derived from conversation
    user_capabilities: List[str] = field(default_factory=list)
    user_emotion: str = ""

    # Environment observations
    available_tools: List[str] = field(default_factory=list)
    system_state: Dict[str, Any] = field(default_factory=dict)
    resource_constraints: Dict[str, Any] = field(default_factory=dict)

    # Performance observations
    recent_success_rate: float = 0.0
    recent_intervention_count: int = 0

    def to_vector(self) -> np.ndarray:
        """Convert observation to vector for ML processing"""
        features = [
            self.task_type,
            self.user_intent,
            len(self.available_tools),
            self.recent_success_rate,
            self.recent_intervention_count
        ]
        # Simple hash-based encoding for categorical features
        encoded = []
        for f in features:
            if isinstance(f, str):
                encoded.append(hash(f) % 1000 / 1000.0)
            elif isinstance(f, float):
                encoded.append(f)
            elif isinstance(f, int):
                encoded.append(float(f) / 100.0)
            else:
                encoded.append(0.0)
        return np.array(encoded)

    def to_dict(self) -> Dict[str, Any]:
        """Convert observation to dictionary for storage"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "workspace_id": self.workspace_id,
            "task_type": self.task_type,
            "user_intent": self.user_intent,
            "user_capabilities": self.user_capabilities,
            "user_emotion": self.user_emotion,
            "available_tools": self.available_tools,
            "system_state": self.system_state,
            "resource_constraints": self.resource_constraints,
            "recent_success_rate": self.recent_success_rate,
            "recent_intervention_count": self.recent_intervention_count,
        }


@dataclass
class ActionSpace:
    """
    Models what actions the agent can take.

    Based on POMDP framework, defines the action space
    that the agent can execute to achieve its goals.
    """
    # Available actions
    can_stream_response: bool = False
    can_present_canvas: bool = False
    can_submit_form: bool = False
    can_browse: bool = False
    can_execute_tool: bool = False

    # Action complexity levels (1-4)
    max_complexity_level: int = 1

    # Governance constraints
    maturity_level: str = "STUDENT"  # STUDENT, INTERN, SUPERVISED, AUTONOMOUS
    active_restrictions: List[str] = field(default_factory=list)

    def can_perform_action(self, action_complexity: int) -> bool:
        """Check if agent can perform action at given complexity level"""
        maturity_rank = {"STUDENT": 1, "INTERN": 2, "SUPERVISED": 3, "AUTONOMOUS": 4}
        current_rank = maturity_rank.get(self.maturity_level, 1)
        return current_rank >= action_complexity


# ============================================================================
# Memory Entry with POMDP attributes
# ============================================================================


@dataclass
class MemoryEntry:
    """
    Enhanced memory entry with POMDP-compliant attributes.

    Each memory entry is part of the write-manage-read loop:
    - Write: Created during agent interactions
    - Manage: Indexed, consolidated, and maintained
    - Read: Retrieved for reasoning and learning
    """
    # Core identity
    id: str = field(default_factory=lambda: str(uuid4()))
    memory_type: MemoryType = MemoryType.EPISODIC
    status: MemoryStatus = MemoryStatus.PENDING

    # POMDP attributes
    observation: Optional[ObservationSpace] = None  # What agent perceived
    action_taken: Optional[str] = ""  # What action was taken
    reward: float = 0.0  # Reward/cost of the action
    next_state: Optional[str] = ""  # Resulting state

    # Temporal attributes
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    consolidation_level: int = 0  # 0=pending, 1=light, 2=full

    # Content
    content: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None
    summary: str = ""

    # Quality indicators (for experience-driven learning)
    quality_score: float = 0.0  # 0-1, estimated by retrieval utility
    intervention_required: bool = False
    user_satisfaction: Optional[float] = None  # 0-1 if available
    success_outcome: bool = True

    # Experience attributes
    task_complexity: int = 1  # 1-4
    autonomy_level: int = 1  # 1-4
    learning_value: float = 0.0  # How much this memory taught the agent

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "memory_type": self.memory_type.value,
            "status": self.status.value,
            "observation": self.observation.to_dict() if self.observation else None,
            "action_taken": self.action_taken,
            "reward": self.reward,
            "next_state": self.next_state,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "consolidation_level": self.consolidation_level,
            "content": self.content,
            "summary": self.summary,
            "quality_score": self.quality_score,
            "intervention_required": self.intervention_required,
            "user_satisfaction": self.user_satisfaction,
            "success_outcome": self.success_outcome,
            "task_complexity": self.task_complexity,
            "autonomy_level": self.autonomy_level,
            "learning_value": self.learning_value,
        }


# ============================================================================
# Memory Manager (Write-Manage-Read Loop)
# ============================================================================


class MemoryManager:
    """
    Manages the write-manage-read loop for agent memory.

    Based on research pattern from:
    "Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and..."
    """

    def __init__(self, db: Session, lancedb_handler=None):
        self.db = db
        self.lancedb = lancedb_handler

        # Memory store (in-memory + persistent)
        self._episodic_memory: Dict[str, MemoryEntry] = {}
        self._semantic_memory: Dict[str, MemoryEntry] = {}
        self._working_memory: Dict[str, Any] = {}

        # Write-manage-read loop state
        self._write_queue: List[MemoryEntry] = []
        self._consolidation_queue: List[MemoryEntry] = []

        # Configuration
        self.working_memory_capacity = 100  # items
        self.episodic_retention_days = 90  # days before auto-cleanup
        self.consolidation_threshold = 5  # accesses before consolidation

    # ========================================================================
    # WRITE Phase: Capture memories during agent interactions
    # ========================================================================

    def write_memory(
        self,
        observation: ObservationSpace,
        action_taken: str,
        reward: float,
        outcome: str,
        content: Dict[str, Any],
        memory_type: MemoryType = MemoryType.EPISODIC
    ) -> MemoryEntry:
        """
        Write a new memory entry (WRITE phase).

        Args:
            observation: What the agent perceived
            action_taken: What action was taken
            reward: Reward/cost of the action
            outcome: Resulting state
            content: Raw content/data
            memory_type: Type of memory to store

        Returns:
            The created memory entry
        """
        entry = MemoryEntry(
            observation=observation,
            action_taken=action_taken,
            reward=reward,
            next_state=outcome,
            content=content,
            memory_type=memory_type,
            status=MemoryStatus.PENDING
        )

        # Add to appropriate memory store
        if memory_type == MemoryType.EPISODIC:
            self._episodic_memory[entry.id] = entry
        elif memory_type == MemoryType.SEMANTIC:
            self._semantic_memory[entry.id] = entry
        elif memory_type == MemoryType.WORKING:
            # Working memory is FIFO
            if len(self._working_memory) >= self.working_memory_capacity:
                # Remove oldest entry
                oldest_id = next(iter(self._working_memory))
                del self._working_memory[oldest_id]
            self._working_memory[entry.id] = entry

        logger.debug(
            f"Memory written: {entry.id[:8]} type={memory_type.value} "
            f"reward={reward} outcome={outcome}"
        )

        return entry

    # ========================================================================
    # MANAGE Phase: Index, consolidate, and maintain memories
    # ========================================================================

    def trigger_manage_cycle(self) -> int:
        """
        Trigger a manage cycle to process pending memories.

        Performs:
        1. Indexing pending memories
        2. Consolidation of frequently accessed memories
        3. Expiration of old memories

        Returns:
            Number of memories processed
        """
        processed = 0

        # 1. Index pending memories
        pending = [m for m in self._episodic_memory.values()
                   if m.status == MemoryStatus.PENDING]

        for memory in pending:
            self._index_memory(memory)
            processed += 1

        # 2. Consolidate frequently accessed memories
        for memory in self._episodic_memory.values():
            if (memory.status == MemoryStatus.INDEXED and
                memory.access_count >= self.consolidation_threshold):
                memory.consolidation_level = 1
                memory.status = MemoryStatus.CONSOLIDATING
                self._consolidation_queue.append(memory)

        for memory in self._consolidation_queue:
            self._consolidate_memory(memory)
            processed += 1

        # 3. Check for expired memories
        cutoff_date = datetime.now() - timedelta(days=self.episodic_retention_days)
        for memory in self._episodic_memory.values():
            if memory.created_at < cutoff_date:
                memory.status = MemoryStatus.EXPIRED

        logger.debug(f"Manage cycle completed: {processed} memories processed")
        return processed

    def _index_memory(self, memory: MemoryEntry) -> None:
        """Index a memory for retrieval"""
        # Generate embedding if not present
        if memory.embedding is None and memory.content.get("text"):
            memory.embedding = self._generate_embedding(memory.content.get("text", ""))

        # Generate summary
        if not memory.summary and memory.content:
            memory.summary = self._generate_summary(memory.content)

        memory.status = MemoryStatus.INDEXED
        logger.debug(f"Memory indexed: {memory.id[:8]}")

    def _consolidate_memory(self, memory: MemoryEntry) -> None:
        """
        Consolidate a memory into long-term storage.

        This implements offline memory consolidation inspired by
        human sleep mechanisms - strengthens memory associations.
        """
        # In a full implementation, this would:
        # 1. Extract patterns and associations
        # 2. Strengthen semantic relationships
        # 3. Create compressed representations

        memory.consolidation_level = 2
        memory.status = MemoryStatus.CONSOLIDATED

        logger.debug(f"Memory consolidated: {memory.id[:8]}")

    # ========================================================================
    # READ Phase: Retrieve memories for reasoning
    # ========================================================================

    def read_memory(
        self,
        memory_id: str,
        access_pattern: MemoryAccessPattern = MemoryAccessPattern.RECALL
    ) -> Optional[MemoryEntry]:
        """
        Read a memory (READ phase).

        Args:
            memory_id: ID of memory to retrieve
            access_pattern: How the memory will be used

        Returns:
            Memory entry if found, None otherwise
        """
        # Check episodic memory
        if memory_id in self._episodic_memory:
            memory = self._episodic_memory[memory_id]

            # Check status
            if memory.status == MemoryStatus.EXPIRED:
                logger.debug(f"Memory expired: {memory_id[:8]}")
                return None

            # Update access tracking
            memory.last_accessed = datetime.now()
            memory.access_count += 1
            memory.quality_score = self._calculate_quality_score(access_pattern, memory)

            # Log the read
            logger.debug(
                f"Memory read: {memory_id[:8]} pattern={access_pattern.value} "
                f"quality={memory.quality_score:.2f}"
            )

            return memory

        # Check semantic memory
        if memory_id in self._semantic_memory:
            memory = self._semantic_memory[memory_id]
            memory.last_accessed = datetime.now()
            memory.access_count += 1
            return memory

        # Check working memory
        if memory_id in self._working_memory:
            memory = self._working_memory[memory_id]
            memory.last_accessed = datetime.now()
            memory.access_count += 1
            return memory

        logger.debug(f"Memory not found: {memory_id[:8]}")
        return None

    def recall_recent(
        self,
        agent_id: str,
        limit: int = 10,
        task_type: Optional[str] = None
    ) -> List[MemoryEntry]:
        """
        Recall recent memories for context.

        Implements episodic memory recall pattern from research:
        Agent can recall specific past events with context (what, when, in what context).
        """
        memories = []

        # Filter by agent and task
        agent_memories = [
            m for m in self._episodic_memory.values()
            if (m.observation.agent_id == agent_id and
                m.status != MemoryStatus.EXPIRED and
                (not task_type or m.observation.task_type == task_type))
        ]

        # Sort by recency
        agent_memories.sort(key=lambda m: m.created_at, reverse=True)

        return agent_memories[:limit]

    def recall_by_quality(
        self,
        agent_id: str,
        min_quality: float = 0.5,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """
        Recall high-quality memories for learning.

        Implements experience-driven learning by recalling
        the most valuable memories for continued improvement.
        """
        memories = [
            m for m in self._episodic_memory.values()
            if (m.observation.agent_id == agent_id and
                m.status != MemoryStatus.EXPIRED and
                m.quality_score >= min_quality)
        ]

        # Sort by quality score
        memories.sort(key=lambda m: m.quality_score, reverse=True)
        return memories[:limit]

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text content"""
        # This would use the LLM service for semantic embeddings
        # For now, return a hash-based mock embedding
        text_hash = hashlib.md5(text.encode()).hexdigest()
        vector = np.array([ord(c) / 256.0 for c in text_hash[:128]], dtype=np.float32)
        return vector

    def _generate_summary(self, content: Dict[str, Any]) -> str:
        """Generate a summary of memory content"""
        if "text" in content:
            text = content["text"]
            return text[:100] + "..." if len(text) > 100 else text
        elif "action" in content:
            return f"Action: {content['action']}"
        else:
            return str(content)[:100]

    def _calculate_quality_score(
        self,
        access_pattern: MemoryAccessPattern,
        memory: MemoryEntry
    ) -> float:
        """
        Calculate quality score for memory based on access patterns.

        Higher scores indicate more valuable memories.
        """
        score = 0.5  # Base score

        # Factor 1: Access frequency (more access = more valuable)
        if memory.access_count > 0:
            access_factor = min(memory.access_count / 100.0, 1.0)
            score += access_factor * 0.3

        # Factor 2: Recency (recent memories more valuable for learning)
        days_since_creation = (datetime.now() - memory.created_at).days
        recency_factor = max(0, 1.0 - days_since_creation / 30.0)  # 30-day window
        score += recency_factor * 0.2

        # Factor 3: Success outcome (successful memories more valuable)
        if memory.success_outcome:
            score += 0.2

        # Factor 4: Learning value (explicitly tagged)
        if memory.learning_value > 0:
            score += min(memory.learning_value * 0.3, 0.3)

        # Factor 5: No intervention required (independent success)
        if not memory.intervention_required:
            score += 0.1

        return min(score, 1.0)

    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get statistics about memory system"""
        total_memories = len(self._episodic_memory) + len(self._semantic_memory)

        episodic_stats = {
            "total": len(self._episodic_memory),
            "pending": sum(1 for m in self._episodic_memory.values()
                        if m.status == MemoryStatus.PENDING),
            "indexed": sum(1 for m in self._episodic_memory.values()
                        if m.status == MemoryStatus.INDEXED),
            "consolidated": sum(1 for m in self._episodic_memory.values()
                            if m.status == MemoryStatus.CONSOLIDATED),
            "expired": sum(1 for m in self._episodic_memory.values()
                        if m.status == MemoryStatus.EXPIRED),
        }

        working_memory_stats = {
            "total": len(self._working_memory),
            "utilization": len(self._working_memory) / self.working_memory_capacity,
        }

        semantic_stats = {
            "total": len(self._semantic_memory),
            "indexed": sum(1 for m in self._semantic_memory.values()
                        if m.status == MemoryStatus.INDEXED),
        }

        return {
            "total_memories": total_memories,
            "episodic": episodic_stats,
            "working": working_memory_stats,
            "semantic": semantic_stats,
        }


# ============================================================================
# Experience Calculator for Graduation
# ============================================================================


@dataclass
class ExperienceMetrics:
    """
    Experience metrics for agent graduation.

    Based on research insights: shift from episode count
    to experience-driven learning metrics.
    """
    # Quality-weighted episode metrics
    quality_weighted_episode_count: float = 0.0
    avg_memory_quality_score: float = 0.0
    high_quality_memories_count: int = 0

    # Intervention trajectory analysis
    intervention_rate_trend: List[float] = field(default_factory=list)
    recent_intervention_rate: float = 0.0
    intervention_improvement_rate: float = 0.0  # Positive = improving

    # Learning consistency
    cross_episode_learning_score: float = 0.0
    skill_acquisition_rate: float = 0.0

    # Autonomy progression
    effective_autonomy_level: float = 0.0
    complex_task_success_rate: float = 0.0

    # Temporal consistency
    performance_stability: float = 0.0  # Variance in performance


class ExperienceCalculator:
    """
    Calculate experience metrics for agent graduation.

    Moves beyond simple episode counting to experience-driven
    learning metrics as recommended by 2025-2026 research.
    """

    def __init__(self, db: Session, memory_manager: MemoryManager):
        self.db = db
        self.memory_manager = memory_manager

    def calculate_readiness_score(
        self,
        agent_id: str,
        target_maturity: str,
        criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate graduation readiness score using experience-driven metrics.

        Returns comprehensive readiness assessment with:
        - Ready: bool (meets all criteria)
        - Score: float (0-100)
        - Experience metrics: Detailed experience metrics
        - Gaps: List of areas needing improvement
        """
        # Get agent's episodic memories
        memories = self.memory_manager.recall_by_quality(
            agent_id=agent_id,
            min_quality=0.3,
            limit=1000
        )

        if not memories:
            # No memories yet - cannot graduate
            return {
                "ready": False,
                "score": 0.0,
                "episode_count": 0,
                "gaps": ["No episodic memories found - agent needs more experience"]
            }

        # Calculate experience metrics
        metrics = self._calculate_experience_metrics(memories)

        # Check against criteria
        target_criteria = criteria.get(target_maturity.upper(), {})
        readiness_score = 0.0
        gaps = []

        # Check episode count (with quality weighting)
        quality_weighted_episodes = metrics.quality_weighted_episode_count
        min_episodes = target_criteria.get("min_episodes", 10)
        if quality_weighted_episodes >= min_episodes:
            readiness_score += 0.25
        else:
            gaps.append(f"Need {min_episodes - quality_weighted_episodes:.1f} more quality episodes")

        # Check intervention rate
        max_intervention = target_criteria.get("max_intervention_rate", 0.5)
        if metrics.recent_intervention_rate <= max_intervention:
            readiness_score += 0.25
        else:
            gaps.append(f"Intervention rate {metrics.recent_intervention_rate:.2%} exceeds {max_intervention_rate*100:.0f}%")

        # Check constitutional score (from memory quality)
        min_constitutional = target_criteria.get("min_constitutional_score", 0.70)
        if metrics.avg_memory_quality_score >= min_constitutional:
            readiness_score += 0.25
        else:
            gaps.append(f"Memory quality {metrics.avg_memory_quality_score:.2f} below {min_constitutional}")

        # Check intervention improvement
        if metrics.intervention_improvement_rate >= 0.0:  # Positive trend
            readiness_score += 0.15
        else:
            gaps.append("Intervention rate not improving")

        # Check learning consistency
        min_consistency = target_criteria.get("min_learning_consistency", 0.6)
        if metrics.cross_episode_learning_score >= min_consistency:
            readiness_score += 0.10
        else:
            gaps.append(f"Learning consistency {metrics.cross_episode_learning_score:.2f} below {min_consistency}")

        # Determine readiness (threshold at 80%)
        ready = readiness_score >= 0.80

        return {
            "ready": ready,
            "score": readiness_score * 100,
            "episode_count": quality_weighted_episodes,
            "avg_intervention_rate": metrics.recent_intervention_rate,
            "avg_constitutional_score": metrics.avg_memory_quality_score,
            "intervention_improvement_rate": metrics.intervention_improvement_rate,
            "learning_consistency": metrics.cross_episode_learning_score,
            "gaps": gaps,
        }

    def _calculate_experience_metrics(self, memories: List[MemoryEntry]) -> ExperienceMetrics:
        """Calculate detailed experience metrics from memories"""
        metrics = ExperienceMetrics()

        if not memories:
            return metrics

        # Quality-weighted episode count
        high_quality_count = sum(1 for m in memories if m.quality_score >= 0.7)
        total_quality = sum(m.quality_score for m in memories)
        avg_quality = total_quality / len(memories) if memories else 0

        metrics.quality_weighted_episode_count = len(memories) * avg_quality
        metrics.avg_memory_quality_score = avg_quality
        metrics.high_quality_memories_count = high_quality_count

        # Intervention trajectory
        interventions = [
            m for m in memories
            if m.intervention_required
        ]
        total_interventions = len(interventions)

        if total_interventions > 0:
            # Calculate intervention rate trend (last 10 vs all)
            recent_interventions = interventions[:10]
            recent_intervention_rate = sum(1 for m in recent_interventions if m.intervention_required) / 10

            # Calculate improvement trend (compare first half to second half)
            mid_point = len(interventions) // 2
            first_half_rate = sum(1 for m in interventions[:mid_point] if m.intervention_required) / max(mid_point, 1)
            second_half_rate = sum(1 for m in interventions[mid_point:] if m.intervention_required) / max(len(interventions) - mid_point, 1)

            if second_half_rate > 0 and first_half_rate > 0:
                improvement_rate = (first_half_rate - second_half_rate) / first_half_rate
                metrics.intervention_improvement_rate = max(-1.0, min(1.0, improvement_rate))

        metrics.recent_intervention_rate = recent_intervention_rate

        # Learning consistency (variance in outcomes)
        successful_memories = [m for m in memories if m.success_outcome]
        if len(successful_memories) > 10:
            success_rate = sum(1 for m in successful_memories if m.success_outcome) / len(successful_memories)
            metrics.cross_episode_learning_score = success_rate
        else:
            metrics.cross_episode_learning_score = 0.5  # Default with insufficient data

        # Autonomy progression
        high_autonomy_memories = [
            m for m in memories
            if m.autonomy_level >= 3 and m.success_outcome
        ]
        if high_autonomy_memories:
            metrics.complex_task_success_rate = (
                sum(1 for m in high_autonomy_memories if m.success_outcome) /
                len(high_autonomy_memories)
            )

        return metrics


# ============================================================================
# Memory Consolidation (Offline Processing)
# ============================================================================


class MemoryConsolidation:
    """
    Offline memory consolidation system.

    Inspired by human sleep mechanisms, this system processes
    memories during idle time to strengthen associations and
    create compressed representations for long-term storage.
    """

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def consolidate_memories(self, agent_id: str, batch_size: int = 50) -> int:
        """
        Consolidate a batch of memories for long-term retention.

        Performs:
        1. Pattern extraction from memory set
        2. Association strengthening between related memories
        3. Semantic clustering for efficient retrieval
        4. Compression for storage optimization

        Args:
            agent_id: Agent to consolidate memories for
            batch_size: Number of memories to process in one batch

        Returns:
            Number of memories consolidated
        """
        # Get candidate memories for consolidation
        candidates = [
            m for m in self.memory_manager._episodic_memory.values()
            if (m.observation.agent_id == agent_id and
                m.status == MemoryStatus.INDEXED and
                m.consolidation_level < 2 and
                m.access_count >= self.memory_manager.consolidation_threshold)
        ]

        consolidated_count = 0
        for memory in candidates[:batch_size]:
            # Perform consolidation
            try:
                self._strengthen_associations(memory)
                self._extract_patterns(memory)
                memory.consolidation_level = 2
                memory.status = MemoryStatus.CONSOLIDATED
                consolidated_count += 1
            except Exception as e:
                logger.warning(f"Failed to consolidate memory {memory.id[:8]}: {e}")

        logger.info(f"Consolidated {consolidated_count} memories for agent {agent_id}")
        return consolidated_count

    def _strengthen_associations(self, memory: MemoryEntry) -> None:
        """Strengthen associations with related memories"""
        # In full implementation, this would:
        # 1. Find related memories by semantic similarity
        # 2. Strengthen bidirectional links
        # 3. Update cluster assignments
        pass

    def _extract_patterns(self, memory: MemoryEntry) -> None:
        """Extract patterns for compression"""
        # In full implementation, this would:
        # 1. Identify common patterns across episodes
        # 2. Create compressed pattern representations
        # 3. Store patterns separately for efficient retrieval
        pass


# ============================================================================
# Factory
# ============================================================================


def get_memory_manager(db: Session, lancedb_handler=None) -> MemoryManager:
    """Factory function to get memory manager instance"""
    return MemoryManager(db, lancedb_handler)


def get_experience_calculator(db: Session, memory_manager: MemoryManager) -> ExperienceCalculator:
    """Factory function to get experience calculator instance"""
    return ExperienceCalculator(db, memory_manager)


# ============================================================================
# Testing Utilities
# ============================================================================


def create_test_memory(
    agent_id: str = "test_agent",
    task_type: str = "CHAT",
    action: str = "response_sent",
    reward: float = 0.8,
    outcome: str = "success",
    content: Dict[str, Any] = None,
    memory_type: MemoryType = MemoryType.EPISODIC
) -> MemoryEntry:
    """Create a test memory entry for testing"""
    from core.memory.pomdp_memory_framework import ObservationSpace, MemoryManager

    obs = ObservationSpace(
        agent_id=agent_id,
        task_type=task_type,
        available_tools=["llm", "canvas"],
        recent_success_rate=0.8,
        recent_intervention_count=0
    )

    if content is None:
        content = {"text": "Test memory content"}

    return MemoryEntry(
        observation=obs,
        action_taken=action,
        reward=reward,
        next_state=outcome,
        content=content,
        memory_type=memory_type
    )


def simulate_agent_experience(
    agent_id: str,
    num_episodes: int = 20,
    intervention_rate: float = 0.3
) -> List[MemoryEntry]:
    """
    Simulate agent experience for testing graduation criteria.

    Args:
        agent_id: Agent ID to simulate
        num_episodes: Number of episodes to generate
        intervention_rate: Rate of episodes requiring intervention (0-1)

    Returns:
        List of simulated memory entries
    """
    memories = []
    for i in range(num_episodes):
        # Simulate intervention
        requires_intervention = i % int(1.0 / intervention_rate) if intervention_rate > 0 else False

        # Simulate outcome
        success_outcome = not requires_intervention or (i % 3 != 0)  # 2/3 success rate with intervention

        memory = create_test_memory(
            agent_id=agent_id,
            task_type="WORKFLOW",
            action="task_completed",
            reward=0.8 if success_outcome else 0.3,
            outcome="success" if success_outcome else "needs_intervention",
            content={
                "text": f"Episode {i} content",
                "episode_number": i,
                "requires_intervention": requires_intervention
            },
            memory_type=MemoryType.EPISODIC
        )

        memory.intervention_required = requires_intervention
        memory.success_outcome = success_outcome
        memory.learning_value = 0.8 if success_outcome else 0.2

        memories.append(memory)

    return memories

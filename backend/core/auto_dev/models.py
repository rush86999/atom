"""
Auto-Dev Database Models

SQLAlchemy models for the self-evolving agent system:
- ToolMutation: Tracks code mutations and lineage for AlphaEvolver
- WorkflowVariant: Tracks workflow variations with fitness scores
- SkillCandidate: Memento-generated skill proposals awaiting validation
- HypothesisTreeRecord: Persisted Arbor HTR sessions (tree snapshots)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, JSON, String, Text

from core.database import Base


class ToolMutation(Base):
    """
    AlphaEvolve: Tracks tool code mutations, lineage, and sandbox test results.

    Each mutation has a parent_tool_id for lineage tracing, allowing the system
    to track evolutionary chains of code improvements.
    """

    __tablename__ = "tool_mutations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    parent_tool_id = Column(String(36), nullable=True, index=True)  # Lineage tracing
    tool_name = Column(String(255), nullable=False)
    mutated_code = Column(Text, nullable=False)
    sandbox_status = Column(String(50), default="pending")  # pending, passed, failed
    execution_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WorkflowVariant(Base):
    """
    AlphaEvolve: Tracks variations of workflows/prompts alongside their
    automated fitness scores.

    Fitness is evaluated in two stages:
    1. Immediate proxy signals (compilation, execution success)
    2. Deferred async signals (webhook events, conversion data)
    """

    __tablename__ = "workflow_variants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    parent_variant_id = Column(String(36), nullable=True, index=True)
    agent_id = Column(String(36), nullable=True, index=True)
    workflow_definition = Column(JSON, nullable=False)
    fitness_score = Column(Float, nullable=True)  # 0 to 1.0
    fitness_signals = Column(JSON, nullable=True)  # Raw proxy or external signals
    evaluation_status = Column(String(50), default="pending")  # pending, evaluated, pruned
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_evaluated_at = Column(DateTime(timezone=True), nullable=True)


class SkillCandidate(Base):
    """
    Memento-Skills: Skill proposals generated from failed episodes.

    When an agent fails a task repeatedly, the MementoEngine analyzes
    the failure pattern and generates a new skill candidate. The candidate
    must pass sandbox validation before it can be promoted to the active
    skill registry.

    Lifecycle: pending → validated/failed → promoted
    """

    __tablename__ = "skill_candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    agent_id = Column(String(36), nullable=True, index=True)
    source_episode_id = Column(String(36), nullable=True, index=True)
    skill_name = Column(String(255), nullable=False)
    skill_description = Column(Text, nullable=True)
    generated_code = Column(Text, nullable=False)
    failure_pattern = Column(JSON, nullable=True)  # Extracted from episode analysis
    validation_status = Column(
        String(50), default="pending"
    )  # pending, validated, failed, promoted
    validation_result = Column(JSON, nullable=True)  # Sandbox execution results
    fitness_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    validated_at = Column(DateTime(timezone=True), nullable=True)
    promoted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_skill_candidates_tenant_status", "tenant_id", "validation_status"),
    )


class HypothesisTreeRecord(Base):
    """
    Arbor HTR: Persisted snapshot of a completed hypothesis tree session.

    Trees are written to the DB when they reach a terminal state (SUCCESS,
    budget exhausted, or explicit DELETE via the REST API).  The full node
    graph is stored as a JSON snapshot in ``tree_snapshot`` so the tree can
    be replayed or inspected offline without a running in-memory session.

    Useful for:
    - Cross-session learning (feeding winning paths and negative constraints
      into new trees via the ``/create`` endpoint's ``learning_insights`` field)
    - Auditing which hypotheses were explored for a given task
    - Analytics: pruning rate, budget utilisation, winning strategy patterns

    Lifecycle: in-memory (HypothesisTree) → persist on completion → query via API
    """

    __tablename__ = "hypothesis_trees"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)

    # Human-readable task info
    task_description = Column(Text, nullable=False)
    task_type = Column(String(50), nullable=False, default="coding")  # coding|workflow|routing
    tier = Column(String(20), nullable=False, default="solo")          # free|solo|enterprise
    session_id = Column(String(36), nullable=True, index=True)

    # Outcome summary (denormalised for fast queries / analytics)
    total_nodes = Column(Integer, default=0)
    successful_nodes = Column(Integer, default=0)
    pruned_nodes = Column(Integer, default=0)
    total_tokens_used = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    optimization_score = Column(Float, nullable=True)    # best promise_score achieved
    winning_path = Column(JSON, nullable=True)            # list[str] of node IDs
    negative_constraints = Column(JSON, nullable=True)    # constraints learned from failures

    # Full serialised tree (nodes + metadata) for replay / deep inspection
    tree_snapshot = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_hypothesis_trees_tenant_type", "tenant_id", "task_type"),
        Index("ix_hypothesis_trees_tenant_tier", "tenant_id", "tier"),
        Index("ix_hypothesis_trees_session", "session_id"),
    )

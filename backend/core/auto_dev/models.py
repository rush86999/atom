"""
Auto-Dev Database Models

SQLAlchemy models for the self-evolving agent system:
- ToolMutation: Tracks code mutations and lineage for AlphaEvolver
- WorkflowVariant: Tracks workflow variations with fitness scores
- SkillCandidate: Memento-generated skill proposals awaiting validation
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, JSON, String, Text

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

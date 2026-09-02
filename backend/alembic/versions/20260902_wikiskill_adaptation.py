"""WikiSkill adaptation: knowledge_patterns, skill_impact_entries, plus
transfer-safety columns on experience_items and playbooks.

Revision ID: 20260902_wikiskill_adaptation
Revises: 20260902_installation_adaptation
Create Date: 2026-09-02

docs/architecture/WIKISKILL_ADAPTATION_PLAN.md — the Google WikiSkill
paper (arXiv:2608.27454) ported onto Atom's learning loops:
- knowledge_patterns  — the persistent wiki layer (W2/W3), maintainer-written,
  evolver-read; the runtime agent never reads it (W4).
- skill_impact_entries — wiki/skill-impact.md analog (W1): every mutation
  proposal outcome, so evolvers never re-propose rejected interventions.
- experience_items.source_model/validation_state — negative-transfer guard
  (W6): imports land quarantined until validated on this installation.
- playbooks.last_eval_result — outcome of the incident-eval replay at
  approval time (W5 gate).
"""
from alembic import op
import sqlalchemy as sa


revision = "20260902_wikiskill_adaptation"
down_revision = "20260902_installation_adaptation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_patterns",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False, index=True),
        sa.Column("workspace_id", sa.String(255), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="failure_mode", index=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("workaround", sa.Text(), nullable=True),
        sa.Column("evidence_ids", sa.JSON(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(32), nullable=False, server_default="maintainer"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active", index=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, index=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_knowledge_patterns_tenant_kind",
        "knowledge_patterns", ["tenant_id", "kind"],
    )

    op.create_table(
        "skill_impact_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("agent_id", sa.String(36), nullable=True, index=True),
        sa.Column("target", sa.String(255), nullable=False, index=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("stage", sa.String(40), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("proposal_summary", sa.Text(), nullable=True),
        sa.Column("unified_diff", sa.Text(), nullable=True),
        sa.Column("validation_score", sa.Float(), nullable=True),
        sa.Column("mutation_id", sa.String(50), nullable=True, index=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_skill_impact_tenant_target",
        "skill_impact_entries", ["tenant_id", "target"],
    )

    op.add_column(
        "playbooks",
        sa.Column("last_eval_result", sa.JSON(), nullable=True),
    )
    op.add_column(
        "experience_items",
        sa.Column("source_model", sa.String(255), nullable=True),
    )
    op.add_column(
        "experience_items",
        sa.Column("validation_state", sa.String(32), nullable=True),
    )
    op.create_index(
        "ix_experience_items_validation_state",
        "experience_items", ["validation_state"],
    )


def downgrade() -> None:
    op.drop_index("ix_experience_items_validation_state", table_name="experience_items")
    op.drop_column("experience_items", "validation_state")
    op.drop_column("experience_items", "source_model")
    op.drop_column("playbooks", "last_eval_result")
    op.drop_index("ix_skill_impact_tenant_target", table_name="skill_impact_entries")
    op.drop_table("skill_impact_entries")
    op.drop_index("ix_knowledge_patterns_tenant_kind", table_name="knowledge_patterns")
    op.drop_table("knowledge_patterns")

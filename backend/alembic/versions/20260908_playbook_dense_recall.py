"""Playbook dense-recall hybrid: store a playbook document embedding so
approved playbooks are also recalled by semantic similarity, not only by
literal trigger-keyword hits (paraphrased requests silently skipped
keyword-gated playbooks).

Revision ID: 20260908_playbook_dense_recall
Revises: 20260903_exchange_reasoning
Create Date: 2026-09-08

Both columns are nullable — a playbook without a stored embedding is still
retrieved by its trigger keywords / canvas type. embedding_model names the
embedder that produced the vector (bge-small-en-v1.5 by default) so a model
change invalidates stale vectors instead of scoring cross-model cosine.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260908_playbook_dense_recall"
down_revision = "20260903_exchange_reasoning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("playbooks", sa.Column("embedding", sa.JSON(), nullable=True))
    op.add_column("playbooks", sa.Column("embedding_model", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("playbooks", "embedding_model")
    op.drop_column("playbooks", "embedding")

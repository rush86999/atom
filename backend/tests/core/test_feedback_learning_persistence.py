"""Feedback → learning persistence (agent_learning tenant_id regression).

The thumbs loop (POST /api/reasoning/feedback →
AgentGovernanceService.submit_feedback) never stamped tenant_id on the
AgentFeedback row, so ContinuousLearningService.update_from_feedback failed
its NOT NULL agent_learning.tenant_id insert on EVERY submission — the
exception is caught upstream, so agent_learning stayed permanently empty
(verified 2026-08-31: 0 rows despite months of live feedback). Polarity was
lost with it: the route only carries thumbs_up/down in user_correction,
while update_from_feedback counts positive/negative via feedback_type.

Fix under test: submit_feedback stamps tenant_id (workspace-scoped,
"default" in Personal Edition) and mirrors the raw thumbs token into the
model's own feedback_type / thumbs_up_down columns.
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.agent_governance_service import AgentGovernanceService
from core.models import (
    AgentLearning,
    AgentRegistry,
    Base,
    Tenant,
    User,
    UserRole,
)


@pytest.fixture
def db():
    """Fresh in-memory SQLite DB with the full schema, one session per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed(db, agent_id="agent-1", user_id="user-1"):
    db.add(Tenant(id="default", name="Default", subdomain="default"))
    db.add(User(
        id=user_id, email="u@example.com", first_name="U", last_name="S",
        role=UserRole.WORKSPACE_ADMIN.value, status="active",
        tenant_id="default",
    ))
    db.add(AgentRegistry(
        id=agent_id, name="A", category="Operations",
        module_path="operations.automations.a", class_name="A",
    ))
    db.commit()


async def test_thumbs_down_persists_learning_row(db):
    _seed(db)
    svc = AgentGovernanceService(db)

    feedback = await svc.submit_feedback(
        agent_id="agent-1",
        user_id="user-1",
        original_output="the draft",
        user_correction="thumbs_down",
        input_context=json.dumps({"run_id": "canvas", "step_index": -1}),
    )

    assert feedback.tenant_id == "default"
    assert feedback.feedback_type == "correction"
    assert feedback.thumbs_up_down is False

    # The regression: this row did not exist at all before the fix —
    # the tenant_id NOT NULL insert failed inside update_from_feedback.
    learning = db.query(AgentLearning).filter_by(agent_id="agent-1").one()
    assert learning.tenant_id == "default"
    assert learning.total_feedback == 1
    assert learning.negative_feedback == 1
    assert learning.positive_feedback == 0


async def test_thumbs_up_counts_positive(db):
    _seed(db)
    svc = AgentGovernanceService(db)

    await svc.submit_feedback(
        agent_id="agent-1",
        user_id="user-1",
        original_output="the draft",
        user_correction="thumbs_up",
    )

    learning = db.query(AgentLearning).filter_by(agent_id="agent-1").one()
    assert learning.total_feedback == 1
    assert learning.positive_feedback == 1
    assert learning.negative_feedback == 0


async def test_free_text_comment_records_total_without_polarity(db):
    """A comment-only submission (no thumbs token) still persists the
    learning row; it just carries no positive/negative count."""
    _seed(db)
    svc = AgentGovernanceService(db)

    await svc.submit_feedback(
        agent_id="agent-1",
        user_id="user-1",
        original_output="the draft",
        user_correction="make the intro shorter",
    )

    learning = db.query(AgentLearning).filter_by(agent_id="agent-1").one()
    assert learning.total_feedback == 1
    assert learning.positive_feedback == 0
    assert learning.negative_feedback == 0

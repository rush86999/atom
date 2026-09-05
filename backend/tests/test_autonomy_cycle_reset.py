"""Human corrections reset the earned-autonomy cycle (auto_until_corrected).

Wiring under test (2026-09-04 supervisor directive: "cycle resets if human
correct until reaching autonomy again"): a correction arriving through the
shared paths — AgentLearningEnhanced.record_user_correction (proposal
approval-with-modifications, chat corrections) and ProposalService.
reject_proposal — must drop the hire's per-capability tier to student, so
the topic's gate proposes again until verified work re-graduates it.
"""
import contextlib
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentProposal, AgentRegistry

TABLES = [AgentRegistry.__table__, AgentProposal.__table__]


@pytest.fixture()
def fresh_db(tmp_path):
    """Brand-new sqlite schema (same way app startup creates it)."""
    eng = create_engine(f"sqlite:///{tmp_path}/autonomy_cycle.db")
    Base.metadata.create_all(bind=eng)
    Sess = sessionmaker(bind=eng, expire_on_commit=False)

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    yield db_session
    eng.dispose()


def _agent(session, agent_id="hire-1", configuration=None):
    session.add(AgentRegistry(
        id=agent_id, name=f"hire-{agent_id}", category="Operations",
        role="agent", type="personal", capabilities=[],
        module_path="operations.test", class_name="TestAgent",
        status="supervised", configuration=configuration or {},
    ))
    session.commit()
    return agent_id


def _tier(db, agent_id, domain):
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    maturities = (agent.configuration or {}).get("capability_maturities") or {}
    return maturities.get(domain)


def _proposal(db, agent_id="hire-1", proposal_id="prop-1"):
    row = AgentProposal(
        id=proposal_id, tenant_id="default", agent_id=agent_id,
        user_id="u-1", status="pending_approval",
        proposal_type="action",
        # proposed_action is a read-only property over proposal_data.
        proposal_data={"action_type": "send_email", "to": ["x@y.z"]},
    )
    db.add(row)
    db.commit()
    return row


def test_record_user_correction_resets_topic_cycle(fresh_db):
    from core.agent_learning_enhanced import AgentLearningEnhanced

    with fresh_db() as db:
        _agent(db)
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            AgentLearningEnhanced(db).record_user_correction(
                "hire-1", "default",
                original_action={"action_type": "send_email"},
                corrected_action={"action_type": "send_email", "to": ["right@person"]},
                context="test",
            )
        )
        assert _tier(db, "hire-1", "send_email") == "student"


def test_record_user_correction_ignores_unknown_action_type(fresh_db):
    from core.agent_learning_enhanced import AgentLearningEnhanced

    with fresh_db() as db:
        _agent(db)
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            AgentLearningEnhanced(db).record_user_correction(
                "hire-1", "default",
                original_action={},
                corrected_action={"action_type": "something_unmapped"},
                context="test",
            )
        )
        assert _tier(db, "hire-1", "send_email") is None
        assert _tier(db, "hire-1", "canvas_edit") is None


def test_rejected_proposal_resets_topic_cycle(fresh_db):
    from core.proposal_service import ProposalService

    with fresh_db() as db:
        _agent(db)
        _proposal(db)
        with patch("core.agent_learning_enhanced.AgentLearningEnhanced"):
            import asyncio

            asyncio.get_event_loop().run_until_complete(
                ProposalService(db).reject_proposal("prop-1", "u-1", "wrong recipient")
            )
        assert _tier(db, "hire-1", "send_email") == "student"

"""RED tests — STUDENT→INTERN promotion requires real-work evidence, not one
graded rehearsal.

Why: AgentRegistry.confidence_score defaults to 0.5 — exactly the INTERN band
floor — so the FIRST completed training session (min boost +0.05) instantly
promoted a brand-new employee. Promotion was gated purely on a supervisor's
subjective score of a single simulated session with zero production evidence.

Research consensus this violates (2025-26):
- CSA Agentic Trust Framework: tier promotions require quantitative evidence
  over an extended window (compliance/error-rate thresholds), not a review.
- RenLayer Trust Tiers: "trust is earned in production, not in staging";
  promote on demonstrated metrics; demote automatically.
- Progressive Autonomy pattern: advancing without instrumented outcomes
  creates "phantom trust".
- The repo's own higher tiers already agree: graduation needs 10/25/50
  outcome-tracked episodes with intervention caps (agent_graduation_service).

Fix under test: promotion additionally requires (env-tunable)
  - >= ATOM_PROMOTION_MIN_TRAINING_SESSIONS completed sessions (default 3)
  - >= ATOM_PROMOTION_MIN_EPISODES outcome-tracked episodes (default 10)
  - episode success ratio >= ATOM_PROMOTION_MIN_SUCCESS_RATIO (default 0.7)
Confidence still accumulates per session; the response carries a promotion
progress block so UIs can show "2/3 sessions · 7/10 clean runs".
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    AgentEpisode,
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    TriggerSource,
)
from core.student_training_service import StudentTrainingService, TrainingOutcome


@pytest.fixture
def db():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except (exc.NoReferencedTableError, Exception):
            continue
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _hire(db, agent_id="sales-rep-1", confidence=0.5):
    agent = AgentRegistry(
        id=agent_id,
        name="Sales Development Rep",
        category="Sales",
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status=AgentStatus.STUDENT.value,
        confidence_score=confidence,
    )
    db.add(agent)
    db.commit()
    return agent


def _seed_episodes(db, agent_id, successes, failures=0):
    for i in range(successes):
        db.add(AgentEpisode(
            agent_id=agent_id,
            tenant_id="t1",
            maturity_at_time=AgentStatus.STUDENT.value,
            outcome="success",
            success=True,
            status="completed",
        ))
    for i in range(failures):
        db.add(AgentEpisode(
            agent_id=agent_id,
            tenant_id="t1",
            maturity_at_time=AgentStatus.STUDENT.value,
            outcome="failure",
            success=False,
            status="completed",
        ))
    db.commit()


async def _run_session(db, agent, score=0.9):
    service = StudentTrainingService(db)
    blocked = BlockedTriggerContext(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_maturity_at_block=AgentStatus.STUDENT.value,
        confidence_score_at_block=agent.confidence_score,
        trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
        trigger_type="agent_message",
        trigger_context={"data": "test"},
        routing_decision="training",
        block_reason="Test block",
    )
    db.add(blocked)
    db.commit()
    proposal = await service.create_training_proposal(blocked)
    session = await service.approve_training(proposal.id, "supervisor", None)
    return await service.complete_training_session(session.id, TrainingOutcome(
        performance_score=score,
        supervisor_feedback="ok",
        errors_count=0,
        tasks_completed=10,
        total_tasks=10,
        capabilities_developed=["crm"],
        capability_gaps_remaining=[],
    ))


@pytest.mark.asyncio
async def test_one_session_never_promotes_a_fresh_hire(db, monkeypatch):
    """The core regression: perfect score on first session != promotion."""
    monkeypatch.delenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", raising=False)
    monkeypatch.delenv("ATOM_PROMOTION_MIN_EPISODES", raising=False)
    agent = _hire(db)

    result = await _run_session(db, agent, score=1.0)

    assert result["promoted_to_intern"] is False
    db.refresh(agent)
    assert agent.status == AgentStatus.STUDENT.value
    # Confidence still moved — evidence gate is orthogonal to confidence.
    assert agent.confidence_score > 0.5
    assert "sessions" in result["promotion"]["reason"] \
        or "episodes" in result["promotion"]["reason"]


@pytest.mark.asyncio
async def test_promotes_after_three_sessions_and_clean_record(db, monkeypatch):
    monkeypatch.delenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", raising=False)
    monkeypatch.delenv("ATOM_PROMOTION_MIN_EPISODES", raising=False)
    agent = _hire(db)
    _seed_episodes(db, agent.id, successes=9, failures=1)  # ratio 0.9

    for _ in range(2):
        await _run_session(db, agent)
        db.refresh(agent)
        assert agent.status == AgentStatus.STUDENT.value

    result = await _run_session(db, agent)  # third session

    assert result["promoted_to_intern"] is True
    db.refresh(agent)
    assert agent.status == AgentStatus.INTERN.value


@pytest.mark.asyncio
async def test_poor_work_record_blocks_promotion_despite_sessions(db, monkeypatch):
    monkeypatch.delenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", raising=False)
    monkeypatch.delenv("ATOM_PROMOTION_MIN_EPISODES", raising=False)
    agent = _hire(db)
    _seed_episodes(db, agent.id, successes=5, failures=5)  # ratio 0.5 < 0.7

    for _ in range(3):
        result = await _run_session(db, agent)

    assert result["promoted_to_intern"] is False
    db.refresh(agent)
    assert agent.status == AgentStatus.STUDENT.value


@pytest.mark.asyncio
async def test_env_knobs_relax_the_gate(db, monkeypatch):
    monkeypatch.setenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", "1")
    monkeypatch.setenv("ATOM_PROMOTION_MIN_EPISODES", "2")
    monkeypatch.setenv("ATOM_PROMOTION_MIN_SUCCESS_RATIO", "0.5")
    agent = _hire(db)
    _seed_episodes(db, agent.id, successes=1, failures=1)  # ratio 0.5 passes

    result = await _run_session(db, agent)

    assert result["promoted_to_intern"] is True


@pytest.mark.asyncio
async def test_progress_block_reports_evidence_counts(db, monkeypatch):
    monkeypatch.delenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", raising=False)
    monkeypatch.delenv("ATOM_PROMOTION_MIN_EPISODES", raising=False)
    agent = _hire(db)
    _seed_episodes(db, agent.id, successes=4, failures=0)

    result = await _run_session(db, agent)

    promo = result["promotion"]
    assert promo["training_sessions"] == 1
    assert promo["required_training_sessions"] == 3
    assert promo["episodes"] == 4
    assert promo["required_episodes"] == 10


# ---------------------------------------------------------------------------
# System-agent exemption: atom_main / Chat Assistant are the bootstrapping
# pathway — the platform's own agents must not be trapped behind an
# apprenticeship designed for user-hired employees.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_system_chat_assistant_promotes_immediately(db, monkeypatch):
    monkeypatch.delenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", raising=False)
    monkeypatch.delenv("ATOM_PROMOTION_MIN_EPISODES", raising=False)
    agent = _hire(db, agent_id="chat-assistant-1", confidence=0.5)
    agent.category = "system"
    agent.module_path = "system"
    agent.class_name = "ChatAssistant"
    db.commit()

    result = await _run_session(db, agent)

    assert result["promoted_to_intern"] is True
    assert result["promotion"]["pathway"] == "system_agent"


@pytest.mark.asyncio
async def test_atom_main_id_is_exempt(db, monkeypatch):
    monkeypatch.delenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", raising=False)
    monkeypatch.delenv("ATOM_PROMOTION_MIN_EPISODES", raising=False)
    agent = _hire(db, agent_id="atom_main", confidence=0.5)

    result = await _run_session(db, agent)

    assert result["promoted_to_intern"] is True
    assert result["promotion"]["pathway"] == "system_agent"


# ---------------------------------------------------------------------------
# Mentor pathway (1 of many): the meta agent teaches from its own verified
# episode record; mentored sessions graduate on a reduced independent-
# evidence requirement because apprenticeship substitutes part of it.
# ---------------------------------------------------------------------------

def _seed_role_mentor(db, student_category="Sales"):
    """A ROLE-SPECIFIC mentor: senior in the student's own domain with a
    verified win record — not the generic meta agent."""
    mentor = AgentRegistry(
        id="sales-lead-1",
        name="Sales Lead",
        category=student_category,
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.85,
    )
    db.add(mentor)
    db.commit()
    for i in range(3):
        db.add(AgentEpisode(
            agent_id=mentor.id,
            tenant_id="t1",
            maturity_at_time=AgentStatus.AUTONOMOUS.value,
            outcome="success",
            success=True,
            status="completed",
            task_description=f"Qualify inbound lead case {i}",
        ))
    db.commit()
    return mentor


@pytest.mark.asyncio
async def test_mentor_playbook_attached_to_proposal(db, monkeypatch):
    monkeypatch.delenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", raising=False)
    monkeypatch.delenv("ATOM_PROMOTION_MIN_EPISODES", raising=False)
    mentor = _seed_role_mentor(db)
    agent = _hire(db)  # Sales student -> Sales mentor

    service = StudentTrainingService(db)
    blocked = BlockedTriggerContext(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_maturity_at_block=AgentStatus.STUDENT.value,
        confidence_score_at_block=0.5,
        trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
        trigger_type="agent_message",
        trigger_context={"data": "test"},
        routing_decision="training",
        block_reason="Test block",
    )
    db.add(blocked)
    db.commit()
    proposal = await service.create_training_proposal(blocked)

    assert proposal.proposal_data.get("mentor_taught") is True
    playbook = proposal.proposal_data["mentor_playbook"]
    assert playbook["mentor_id"] == mentor.id
    assert len(playbook["cases"]) == 3


@pytest.mark.asyncio
async def test_generic_meta_agent_does_not_mentor_business_roles(db, monkeypatch):
    """atom_main is a generalist — its orchestration record is not a sales
    curriculum. No role-specific senior -> no playbook, self-directed path."""
    monkeypatch.delenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", raising=False)
    monkeypatch.delenv("ATOM_PROMOTION_MIN_EPISODES", raising=False)
    # Only the meta agent exists: senior, but WRONG DOMAIN for a Sales hire.
    db.add(AgentRegistry(
        id="atom_main",
        name="Atom",
        category="Meta",
        module_path="core.atom_meta_agent",
        class_name="AtomMetaAgent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=1.0,
    ))
    db.commit()
    agent = _hire(db)

    result = await _run_session(db, agent)

    assert result["promoted_to_intern"] is False
    assert result["promotion"]["pathway"] is None
    assert "[mentor_taught]" in (result["promotion"]["reason"] or "")


@pytest.mark.asyncio
async def test_meta_agent_teaches_system_students(db, monkeypatch):
    """Role-specificity cuts both ways: for system/Meta students the meta
    agent IS the domain expert."""
    monkeypatch.delenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", raising=False)
    monkeypatch.delenv("ATOM_PROMOTION_MIN_EPISODES", raising=False)
    db.add(AgentRegistry(
        id="atom_main",
        name="Atom",
        category="Meta",
        module_path="core.atom_meta_agent",
        class_name="AtomMetaAgent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=1.0,
    ))
    db.commit()
    agent = _hire(db, agent_id="chat-assistant-2", confidence=0.5)
    agent.category = "system"
    agent.module_path = "system"
    db.commit()

    service = StudentTrainingService(db)
    mentor = service._find_mentor(agent)
    assert mentor is not None and mentor.id == "atom_main"


@pytest.mark.asyncio
async def test_mentor_pathway_graduates_with_half_the_field_evidence(db, monkeypatch):
    """Apprenticeship under a qualified role mentor halves the solo floor."""
    monkeypatch.delenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", raising=False)
    monkeypatch.delenv("ATOM_PROMOTION_MIN_EPISODES", raising=False)
    _seed_role_mentor(db)
    agent = _hire(db)
    _seed_episodes(db, agent.id, successes=4, failures=1)  # ratio .8, only 5 < 10

    for _ in range(2):
        await _run_session(db, agent)
        db.refresh(agent)
        assert agent.status == AgentStatus.STUDENT.value

    result = await _run_session(db, agent)  # third MENTORED session

    assert result["promoted_to_intern"] is True
    assert result["promotion"]["pathway"] == "mentor_taught"

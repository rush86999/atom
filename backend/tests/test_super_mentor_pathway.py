"""RED tests — atom_main earns SUPER-MENTOR status per role.

Product goal: the meta agent should become "a super mentor for everyone" —
but EARNED, not assumed. Its orchestration outcomes are real work; the gap
was attribution: everything credited one blended row, so its sales-flavored
runs never accrued sales evidence. (Mentorship credit itself stays
role-gated per R86b — laundering a generalist record into a Sales teaching
credential violates skill_scoped_trust's anti-laundering principle.)

Fix under test:
  1. DomainExperienceLedger — precise SQL ledger of (agent_id, domain,
     outcome, task_summary) written from the meta agent's execution path.
  2. resolve_domain() — lightweight keyword routing over task text using the
     fleet DOMAIN_ALIASES vocabulary.
  3. Super-mentor qualification: atom_main may mentor role R once it has
     ATOM_SUPERMENTOR_MIN_DOMAIN_WINS verified wins in R (default 5).
     Evidence comparison picks the better-qualified teacher between the
     super-mentor and a same-role senior.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.domain_attribution import (
    build_domain_vocabulary,
    count_domain_wins,
    record_domain_outcome,
    resolve_domain,
)
from core.models import (
    AgentEpisode,
    AgentRegistry,
    AgentStatus,
    DomainExperienceLedger,
)
from core.student_training_service import StudentTrainingService


@pytest.fixture
def db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except exc.NoReferencedTableError:
            continue
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Domain resolution
# ---------------------------------------------------------------------------

def test_resolve_domain_sales_keywords():
    assert resolve_domain("Follow up on Acme deal and update CRM lead stage") == "sales"


def test_resolve_domain_finance_keywords():
    assert resolve_domain("Reconcile invoice INV-1042 against billing records") == "finance"


def test_resolve_domain_unknown_returns_none():
    assert resolve_domain("Summarize this quarterly planning document") is None


# ---------------------------------------------------------------------------
# Dynamic roles: edge businesses must attribute without code changes.
# ---------------------------------------------------------------------------

def test_learned_vocabulary_attributes_edge_roles(db):
    """A landscaping business's role emerges from its own work history."""
    from core.domain_attribution import build_domain_vocabulary

    db.add(AgentRegistry(
        id="landscape-lead", name="Field Lead", category="Landscaping",
        module_path="core.generic_agent", class_name="GenericAgent",
        status=AgentStatus.SUPERVISED.value, confidence_score=0.7,
    ))
    for i in range(4):
        db.add(AgentEpisode(
            agent_id="landscape-lead", tenant_id="t1",
            maturity_at_time=AgentStatus.SUPERVISED.value,
            outcome="success", success=True, status="completed",
            task_description=f"Inspect irrigation lines zone {i} and fertilize beds",
        ))
    db.commit()

    vocab = build_domain_vocabulary(db)
    assert "landscaping" in {k.lower() for k in vocab}
    assert any("irrigation" in t for t in vocab.get("landscaping", []))

    # Attribution keys are lowercase-normalized for ledger consistency.
    assert resolve_domain(
        "Check the irrigation controller at the Henderson site",
        vocabulary=vocab,
    ) == "landscaping"


@pytest.mark.asyncio
async def test_super_mentor_works_for_edge_roles(db, monkeypatch):
    monkeypatch.delenv("ATOM_SUPERMENTOR_MIN_DOMAIN_WINS", raising=False)
    monkeypatch.setenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", "1")
    monkeypatch.setenv("ATOM_PROMOTION_MIN_EPISODES", "0")
    db.add(AgentRegistry(
        id="atom_main", name="Atom", category="Meta",
        module_path="core.atom_meta_agent", class_name="AtomMetaAgent",
        status=AgentStatus.AUTONOMOUS.value, confidence_score=1.0,
    ))
    # Edge-role wins land under the role's own category string.
    for i in range(5):
        record_domain_outcome(db, "atom_main", "landscaping", True,
                              task_summary=f"Irrigation audit {i}")

    # Edge-role student: no static keywords exist for it, but ledger wins
    # were recorded under its exact category string.
    agent = AgentRegistry(
        id="crew-1", name="Crew Coordinator", category="landscaping",
        module_path="core.generic_agent", class_name="GenericAgent",
        status=AgentStatus.STUDENT.value, confidence_score=0.35,
    )
    db.add(agent)
    db.commit()

    service = StudentTrainingService(db)
    mentor = service._find_mentor(agent)
    assert mentor is not None and mentor.id == "atom_main"


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def test_ledger_records_and_counts_wins(db):
    record_domain_outcome(db, "atom_main", "sales", True, "Qualified Acme lead")
    record_domain_outcome(db, "atom_main", "sales", True, "Drafted follow-up")
    record_domain_outcome(db, "atom_main", "sales", False, "Lost thread")

    assert count_domain_wins(db, "atom_main", "sales") == 2
    assert count_domain_wins(db, "atom_main", "finance") == 0


# ---------------------------------------------------------------------------
# Super-mentor eligibility + selection
# ---------------------------------------------------------------------------

def _seed_student_and_meta(db, meta_wins=5, senior_wins=0):
    db.add(AgentRegistry(
        id="atom_main", name="Atom", category="Meta",
        module_path="core.atom_meta_agent", class_name="AtomMetaAgent",
        status=AgentStatus.AUTONOMOUS.value, confidence_score=1.0,
    ))
    if meta_wins:
        for i in range(meta_wins):
            db.add(DomainExperienceLedger(
                agent_id="atom_main", domain="sales", outcome="success",
                task_summary=f"Sales case {i}",
            ))
    if senior_wins:
        db.add(AgentRegistry(
            id="senior-sales", name="Senior Seller", category="Sales",
            module_path="core.generic_agent", class_name="GenericAgent",
            status=AgentStatus.SUPERVISED.value, confidence_score=0.8,
        ))
        for i in range(senior_wins):
            db.add(AgentEpisodeForTests(db, i))
    db.commit()


def AgentEpisodeForTests(db, i):
    from core.models import AgentEpisode
    ep = AgentEpisode(
        agent_id="senior-sales", tenant_id="t1",
        maturity_at_time=AgentStatus.SUPERVISED.value,
        outcome="success", success=True, status="completed",
        task_description=f"Senior case {i}",
    )
    db.add(ep)
    return ep


@pytest.mark.asyncio
async def test_super_mentor_qualifies_after_domain_wins(db, monkeypatch):
    monkeypatch.delenv("ATOM_SUPERMENTOR_MIN_DOMAIN_WINS", raising=False)
    monkeypatch.setenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", "1")
    monkeypatch.setenv("ATOM_PROMOTION_MIN_EPISODES", "0")
    _seed_student_and_meta(db, meta_wins=5)

    agent = AgentRegistry(
        id="sales-rep-9", name="SDR", category="Sales",
        module_path="core.generic_agent", class_name="GenericAgent",
        status=AgentStatus.STUDENT.value, confidence_score=0.35,
    )
    db.add(agent)
    db.commit()

    service = StudentTrainingService(db)
    mentor = service._find_mentor(agent)
    assert mentor is not None and mentor.id == "atom_main"

    # Playbook teaches from the LEDGER cases (real attributed work).
    playbook = service._build_mentor_playbook(agent)
    assert playbook["mentor_id"] == "atom_main"
    assert len(playbook["cases"]) == 5


@pytest.mark.asyncio
async def test_below_win_threshold_meta_agent_is_not_a_mentor(db, monkeypatch):
    monkeypatch.delenv("ATOM_SUPERMENTOR_MIN_DOMAIN_WINS", raising=False)
    _seed_student_and_meta(db, meta_wins=2)

    agent = AgentRegistry(
        id="sales-rep-10", name="SDR", category="Sales",
        module_path="core.generic_agent", class_name="GenericAgent",
        status=AgentStatus.STUDENT.value, confidence_score=0.35,
    )
    db.add(agent)
    db.commit()

    service = StudentTrainingService(db)
    assert service._find_mentor(agent) is None


@pytest.mark.asyncio
async def test_more_proven_role_senior_beats_super_mentor(db, monkeypatch):
    monkeypatch.delenv("ATOM_SUPERMENTOR_MIN_DOMAIN_WINS", raising=False)
    _seed_student_and_meta(db, meta_wins=5, senior_wins=8)

    agent = AgentRegistry(
        id="sales-rep-11", name="SDR", category="Sales",
        module_path="core.generic_agent", class_name="GenericAgent",
        status=AgentStatus.STUDENT.value, confidence_score=0.35,
    )
    db.add(agent)
    db.commit()

    service = StudentTrainingService(db)
    mentor = service._find_mentor(agent)
    assert mentor is not None and mentor.id == "senior-sales"


# ---------------------------------------------------------------------------
# Shared-path attribution wiring (record_outcome ledgers domains)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_outcome_attributes_sales_work(db, monkeypatch):
    """The production gap this closes: user-facing runs complete through
    AgentGovernanceService.record_outcome — sales work there must land in
    the domain ledger so a generalist can EARN super-mentor status."""
    import core.domain_attribution as da

    monkeypatch.setattr(da, "_VOCAB_CACHE", {"at": 0.0, "vocab": {}})
    from core.agent_governance_service import AgentGovernanceService

    svc = AgentGovernanceService(db, workspace_id="default")
    db.add(AgentRegistry(
        id="gm-1", name="Generalist", category="General",
        module_path="core.generic_agent", class_name="GenericAgent",
        workspace_id="default", status="autonomous", confidence_score=0.95,
    ))
    db.commit()

    await svc.record_outcome(
        "gm-1", success=True,
        task_summary="Draft a follow-up email with the quote for the Mark deal",
    )
    row = db.query(DomainExperienceLedger).one()
    assert row.domain == "sales"
    assert row.outcome == "success"
    assert "Mark deal" in row.task_summary


@pytest.mark.asyncio
async def test_record_outcome_without_domain_text_skips_ledger(db):
    from core.agent_governance_service import AgentGovernanceService

    svc = AgentGovernanceService(db, workspace_id="default")
    db.add(AgentRegistry(
        id="gm-2", name="Generalist", category="General",
        module_path="core.generic_agent", class_name="GenericAgent",
        workspace_id="default", status="autonomous", confidence_score=0.95,
    ))
    db.commit()

    await svc.record_outcome("gm-2", success=True, task_summary="What is the weather like")
    assert db.query(DomainExperienceLedger).count() == 0


@pytest.mark.asyncio
async def test_record_outcome_failure_ledgers_but_is_not_a_win(db):
    import core.domain_attribution as da

    from core.agent_governance_service import AgentGovernanceService

    da._VOCAB_CACHE.update({"at": 0.0, "vocab": {}})
    svc = AgentGovernanceService(db, workspace_id="default")
    db.add(AgentRegistry(
        id="gm-3", name="Generalist", category="General",
        module_path="core.generic_agent", class_name="GenericAgent",
        workspace_id="default", status="autonomous", confidence_score=0.95,
    ))
    db.commit()

    await svc.record_outcome(
        "gm-3", success=False, task_summary="Update the CRM pipeline for the deal"
    )
    row = db.query(DomainExperienceLedger).one()
    assert row.outcome == "failure"
    assert count_domain_wins(db, "gm-3", "sales") == 0


@pytest.mark.asyncio
async def test_earned_domain_wins_make_generalist_a_mentor(db):
    """End-to-end contract: a generalist that did 5 successful sales runs
    (via the shared outcome path) can teach a Sales student."""
    import core.domain_attribution as da

    from core.agent_governance_service import AgentGovernanceService

    da._VOCAB_CACHE.update({"at": 0.0, "vocab": {}})
    db.add(AgentRegistry(
        id="atom_main", name="Atom", category="Meta",
        module_path="core.generic_agent", class_name="GenericAgent",
        workspace_id="default", status="autonomous", confidence_score=1.0,
    ))
    db.add(AgentRegistry(
        id="stud-1", name="Sales Hire", category="Sales",
        module_path="core.generic_agent", class_name="GenericAgent",
        workspace_id="default", status="student", confidence_score=0.4,
    ))
    db.commit()

    svc = AgentGovernanceService(db, workspace_id="default")
    for _ in range(5):
        await svc.record_outcome(
            "atom_main", success=True, task_summary="Score the new lead and update the CRM deal",
        )
    assert count_domain_wins(db, "atom_main", "sales") == 5

    training = StudentTrainingService(db)
    student = db.query(AgentRegistry).filter(AgentRegistry.id == "stud-1").one()
    mentor = training._find_mentor(student)
    assert mentor is not None and mentor.id == "atom_main"

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
    count_domain_wins,
    record_domain_outcome,
    resolve_domain,
)
from core.models import (
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

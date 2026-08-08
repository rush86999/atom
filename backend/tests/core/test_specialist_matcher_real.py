"""
P1b — Real SpecialistMatcher (replaces the self-declared stub).

The stub at ``core/specialist_matcher.py:1-6`` returns ``[]`` and is missing
the three methods ``RecruitmentIntelligenceService`` calls on it
(``find_specialists_for_domains``, ``get_all_available_domains``,
``DOMAIN_ALIASES``) — so the wired fleet path (P1a) would AttributeError on
reach. This suite verifies the real implementation: ranked candidates from
``AgentRegistry``, the explicit scoring metric, and no AttributeError.

Run: ``cd backend && venv/bin/python -m pytest tests/core/test_specialist_matcher_real.py -v``
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.models import AgentRegistry, AgentStatus
from core.specialist_matcher import SpecialistMatcher, DOMAIN_ALIASES


# ---------------------------------------------------------------------------
# In-memory SQLite session (mirrors conftest's StaticPool pattern) so we can
# seed real AgentRegistry rows without a live DB.
# ---------------------------------------------------------------------------
@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from core.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _agent(
    db, *, name, category, capabilities, status=AgentStatus.AUTONOMOUS.value,
    confidence=0.5, self_healed=0, days_ago=0,
):
    """Insert an AgentRegistry row and return it."""
    ag = AgentRegistry(
        id=f"agent-{name.lower()}",
        name=name,
        category=category,
        capabilities=capabilities,
        status=status,
        confidence_score=confidence,
        self_healed_count=self_healed,
        last_request_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
        module_path="core.generic_agent",
        class_name="GenericAgent",
    )
    db.add(ag)
    db.commit()
    return ag


# ---------------------------------------------------------------------------
# 1. The three previously-missing symbols exist (no more AttributeError).
# ---------------------------------------------------------------------------
def test_matcher_exposes_required_symbols():
    assert hasattr(SpecialistMatcher, "find_specialists_for_domains")
    assert hasattr(SpecialistMatcher, "get_all_available_domains")
    assert isinstance(DOMAIN_ALIASES, dict) and len(DOMAIN_ALIASES) > 0


# ---------------------------------------------------------------------------
# 2. find_specialists_for_domains returns ranked candidates per domain.
# ---------------------------------------------------------------------------
def test_find_specialists_ranks_by_capability_overlap(db_session):
    # finance specialist with strong overlap
    _agent(
        db_session, name="StrongFin", category="Finance",
        capabilities=["budget", "cost", "invoice", "reconciliation"],
        confidence=0.9, self_healed=5, days_ago=1,
    )
    # finance specialist with weak overlap
    _agent(
        db_session, name="WeakFin", category="Finance",
        capabilities=["budget"],  # 1 of 3 keywords
        confidence=0.5, days_ago=30,
    )
    matcher = SpecialistMatcher(db_session)

    matches = matcher.find_specialists_for_domains(
        domains=["finance"], user_id="u1", limit_per_domain=3,
    )

    assert "finance" in matches
    fin = matches["finance"]
    assert len(fin) == 2
    # Strong overlap (3/3 keywords) + high confidence must rank above weak.
    assert fin[0]["agent_id"] == "agent-strongfin"
    assert fin[0]["capability_score"] > fin[1]["capability_score"]
    # Each match carries the roster-shape fields RecruitmentIntelligenceService reads.
    for m in fin:
        assert {"agent_id", "name", "capability_score"} <= set(m.keys())


# ---------------------------------------------------------------------------
# 3. The metric weights: a higher-tier agent outranks a lower-tier one even at
#    equal capability overlap (the 0.25 tier_floor term must matter).
# ---------------------------------------------------------------------------
def test_tier_floor_weight_matters(db_session):
    _agent(
        db_session, name="Student", category="Sales",
        capabilities=["crm", "lead", "deal"],
        status=AgentStatus.STUDENT.value, confidence=0.9,
    )
    _agent(
        db_session, name="Autonomous", category="Sales",
        capabilities=["crm", "lead", "deal"],
        status=AgentStatus.AUTONOMOUS.value, confidence=0.9,
    )
    matcher = SpecialistMatcher(db_session)

    matches = matcher.find_specialists_for_domains(
        domains=["sales"], user_id="u1", limit_per_domain=3,
    )
    ranked = matches["sales"]
    assert ranked[0]["agent_id"] == "agent-autonomous", (
        "equal overlap + confidence — AUTONOMOUS tier must outrank STUDENT (0.25 tier weight)"
    )


# ---------------------------------------------------------------------------
# 4. get_all_available_domains returns the distinct categories present.
# ---------------------------------------------------------------------------
def test_get_all_available_domains(db_session):
    _agent(db_session, name="A", category="Finance", capabilities=["budget"])
    _agent(db_session, name="B", category="Sales", capabilities=["crm"])
    matcher = SpecialistMatcher(db_session)

    domains = matcher.get_all_available_domains("u1")
    assert "Finance" in domains or "finance" in domains
    assert "Sales" in domains or "sales" in domains


# ---------------------------------------------------------------------------
# 5. Unknown domain with no specialists → empty list (not an error).
# ---------------------------------------------------------------------------
def test_unknown_domain_returns_empty(db_session):
    matcher = SpecialistMatcher(db_session)
    matches = matcher.find_specialists_for_domains(
        domains=["nonexistent"], user_id="u1", limit_per_domain=3,
    )
    assert matches.get("nonexistent") == []


# ---------------------------------------------------------------------------
# 6. match_specialists (the pre-existing method) still works (backward-compat).
# ---------------------------------------------------------------------------
def test_match_specialists_backward_compat(db_session):
    _agent(db_session, name="Fin", category="Finance", capabilities=["budget", "cost"])
    matcher = SpecialistMatcher(db_session)
    results = matcher.match_specialists(["budget", "cost"], count=1)
    assert len(results) >= 1

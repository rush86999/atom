"""
Tests for graduation skill-promotion success filtering (core/graduation_service.py).

check_skill_promotion counts episodes toward the "required_successes" threshold,
but the query had no success filter — so failed episodes counted toward the
gate. An agent with N failed episodes (zero successes) passed the count check
and reached the streak phase, violating the "N successful runs" semantics.
"""

import pytest
from datetime import datetime, timezone

from core.graduation_service import GraduationService
from core.models import AgentRegistry, AgentEpisode, Tenant


@pytest.fixture
def db(worker_database):
    SessionLocal = worker_database
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def _seed_agent(db, agent_id="grad-agent", tenant_id="t-grad"):
    if not db.query(Tenant).filter(Tenant.id == tenant_id).first():
        db.add(Tenant(id=tenant_id, name="T", subdomain=f"t-{tenant_id}"))
        db.flush()
    agent = AgentRegistry(
        id=agent_id,
        name="Grad Agent",
        category="general",
        status="active",
        tenant_id=tenant_id,
        module_path="core.generic_agent",
        class_name="GenericAgent",
    )
    db.add(agent)
    db.commit()
    return agent


def _add_episode(db, agent_id, skill_id, success=True, score=0.97, interventions=0, tenant_id="t-grad"):
    ep = AgentEpisode(
        agent_id=agent_id,
        tenant_id=tenant_id,
        maturity_at_time="supervised",
        success=success,
        constitutional_score=score,
        human_intervention_count=interventions,
        outcome="success" if success else "failure",
        started_at=datetime.now(timezone.utc),
        metadata_json={"skill_id": skill_id},
    )
    db.add(ep)
    return ep


@pytest.mark.asyncio
async def test_failed_episodes_do_not_count_toward_threshold(db):
    """An agent with 5 FAILED episodes (zero successes) must NOT pass the
    count gate — the threshold is 'required_successes', not 'required_episodes'."""
    agent = _seed_agent(db)
    for _ in range(5):
        _add_episode(db, agent.id, "skill-X", success=False)
    db.commit()

    svc = GraduationService(db)
    result = await svc.check_skill_promotion(agent.id, "skill-X", "moderate")

    assert result["promoted"] is False
    # The reason must reflect insufficient SUCCESSES, not "streak broken".
    # (The bug: the count gate passed with 5 failed episodes, reaching the
    # streak phase and reporting "Streak broken" instead of "Insufficient".)
    assert "insufficient" in result["reason"].lower(), (
        f"Expected an 'insufficient' reason with 0 successes, got: {result['reason']}"
    )


@pytest.mark.asyncio
async def test_successful_clean_episodes_promote(db):
    """Sanity: 5 clean successful episodes DO promote."""
    agent = _seed_agent(db, agent_id="grad-agent-2", tenant_id="t-grad2")
    for _ in range(5):
        _add_episode(db, agent.id, "skill-Y", success=True, score=0.97, interventions=0, tenant_id="t-grad2")
    db.commit()

    svc = GraduationService(db)
    result = await svc.check_skill_promotion(agent.id, "skill-Y", "moderate")

    assert result["promoted"] is True

"""Graduation gap list must follow the scorer's evidence rule.

The readiness scorer renormalizes over factors WITH recorded evidence only
(EpisodeService._compute_readiness_score) — an agent whose episodes never
measured constitutional compliance is scored as if the factor did not
exist, and can be verdict-ready at 98/100. The gap enrichment in
AgentGraduationService.calculate_readiness_score nonetheless compared the
0.0 unmeasured fallback against the tier's constitutional floor, so the
same panel showed "ready" AND an unsatisfiable "Constitutional score 0.00
below required 0.85" gap — one that no amount of agent performance could
ever clear (live case 2026-09-22: intern Sales Agent, 378 episodes, zero
constitutional measurements in the analyzed window).

Now the gap fires only when scores WERE recorded and came in under the
floor. Scratch-file sqlite — never the live dev DB (AGENTS.md).
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.agent_graduation_service import AgentGraduationService
from core.models import AgentEpisode, AgentRegistry, AgentStatus


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/readiness_gap_test.db")
    AgentRegistry.__table__.create(engine)
    AgentEpisode.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


def seed_intern(db, constitutional_score):
    """INTERN hire past the episode floor (10) with zero interventions."""
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name="Gap-rule intern",
        category="Sales",
        module_path="sales.agent",
        class_name="SalesAgent",
        status=AgentStatus.INTERN.value,
        tenant_id="default",
    )
    db.add(agent)
    base = datetime.now(timezone.utc)
    for i in range(12):
        db.add(AgentEpisode(
            agent_id=agent.id,
            tenant_id="default",
            task_description=f"Episode {i}",
            maturity_at_time=AgentStatus.INTERN.value,
            outcome="success",
            success=True,
            human_intervention_count=0,
            confidence_score=0.6,
            constitutional_score=constitutional_score,
            status="completed",
            metadata_json={},
            started_at=base,
        ))
    db.commit()
    return agent


def readiness_for(db, agent):
    with patch("core.agent_graduation_service.get_lancedb_handler",
               return_value=Mock()), \
         patch("core.agent_graduation_service.POMDP_AVAILABLE", False):
        return asyncio.run(
            AgentGraduationService(db).calculate_readiness_score(
                agent_id=agent.id,
                target_maturity="INTERN",
            )
        )


class TestConstitutionalGapEvidenceRule:
    def test_unmeasured_compliance_is_not_a_gap(self, db_session):
        """THE regression: all episodes unmeasured → no constitutional gap,
        and the breakdown states that explicitly."""
        result = readiness_for(db_session, seed_intern(db_session, None))

        assert "error" not in result
        assert result["gaps"] == []
        assert result["ready"] is True
        assert result["breakdown"]["constitutional_recorded"] == 0

    def test_breakdown_exposes_recorded_count(self, db_session):
        """The recorded count is per analyzed window — 12 here, 0 for the
        unmeasured case above — so consumers can tell 'unmeasured' from
        'measured at 0'."""
        result = readiness_for(db_session, seed_intern(db_session, 0.5))

        assert result["breakdown"]["constitutional_recorded"] == 12

    def test_measured_but_low_still_fires_the_gap(self, db_session):
        """Recorded evidence below the floor must keep failing — the rule
        only exempts UNMEASURED factors. (ready stays threshold_met-driven:
        the scorer's weighted verdict and the per-floor gap are separate
        surfaces by design.)"""
        result = readiness_for(db_session, seed_intern(db_session, 0.5))

        assert any(
            "Constitutional score 0.50 below required 0.70" in g
            for g in result["gaps"]
        )

    def test_measured_and_high_has_no_gap(self, db_session):
        result = readiness_for(db_session, seed_intern(db_session, 0.9))

        assert not any("Constitutional" in g for g in result["gaps"])

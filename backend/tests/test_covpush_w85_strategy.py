# -*- coding: utf-8 -*-
"""Coverage wave 85 — core/coordinated_strategy_service (never-wave-tested).

Covers multi-agent coordination:
- initiate_strategy: creates the strategy + initiator contribution (agent
  present vs missing), status negotiating, commit/refresh, logging.
- recruit_diverse_partner: missing strategy -> None; trait collection from
  existing contributors (with/without diversity_profile); picks a partner
  with a NEW trait value; skips candidates without a profile; falls back to
  first agent of the specialty; empty category -> None.
- add_contribution: success (specialty from agent category) + unknown-agent
  ValueError.
- finalize_strategy: exists -> approved + approved_at set; missing -> False.

Uses the real in-memory SQLite schema (no network, zero LLM spend).
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    AgentRegistry,
    CoordinatedStrategy,
    StrategyContribution,
)  # noqa: F401 (register models)


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_agent(db, agent_id="agent-1", category="Finance", traits=None, **kw):
    agent = AgentRegistry(
        id=agent_id,
        name=agent_id,
        workspace_id="ws-1",
        tenant_id="t1",
        category=category,
        module_path="test",
        class_name="Test",
        diversity_profile=traits,
        **kw,
    )
    db.add(agent)
    db.commit()
    return agent


def _make_strategy(db, strategy_id="strat-1", tenant_id="t1"):
    strat = CoordinatedStrategy(
        id=strategy_id,
        tenant_id=tenant_id,
        title="Q3 Growth",
        objective="Expand into new markets",
        status="negotiating",
    )
    db.add(strat)
    db.commit()
    return strat


class TestInitiateStrategy:
    def test_with_initiator_agent_adds_contribution(self, db):
        _make_agent(db, "agent-1", category="Finance")
        svc = __import__("core.coordinated_strategy_service", fromlist=["CoordinatedStrategyService"]).CoordinatedStrategyService(db)
        strategy = svc.initiate_strategy("t1", "Q3 Growth", "Expand", "agent-1")

        assert strategy.status == "negotiating"
        assert strategy.title == "Q3 Growth"
        db.refresh(strategy)
        assert len(strategy.contributions) == 1
        contrib = strategy.contributions[0]
        assert contrib.agent_id == "agent-1"
        assert contrib.specialty == "Finance"
        assert contrib.status == "proposed"
        assert "Expand" in contrib.content["proposal"]

    def test_without_initiator_agent_skips_contribution(self, db):
        svc = __import__("core.coordinated_strategy_service", fromlist=["CoordinatedStrategyService"]).CoordinatedStrategyService(db)
        strategy = svc.initiate_strategy("t1", "Q3 Growth", "Expand", "ghost-agent")

        db.refresh(strategy)
        assert strategy.contributions == []

    def test_strategy_id_is_uuid_and_committed(self, db):
        _make_agent(db, "agent-1")
        svc = __import__("core.coordinated_strategy_service", fromlist=["CoordinatedStrategyService"]).CoordinatedStrategyService(db)
        strategy = svc.initiate_strategy("t1", "T", "O", "agent-1")
        assert db.query(CoordinatedStrategy).count() == 1
        assert db.query(StrategyContribution).count() == 1
        assert strategy.id


class TestRecruitDiversePartner:
    def _initiated_strategy(self, db, initiator="initiator", category="Finance", traits=None):
        """Create initiator agent + strategy (fixed id) with the initiator's
        contribution, mirroring the real initiate_strategy flow."""
        _make_agent(db, initiator, category=category, traits=traits)
        _make_strategy(db)
        svc = __import__("core.coordinated_strategy_service", fromlist=["CoordinatedStrategyService"]).CoordinatedStrategyService(db)
        svc.add_contribution("strat-1", initiator, {"proposal": "Initial strategy"})
        return svc

    def test_strategy_missing_returns_none(self, db):
        svc = __import__("core.coordinated_strategy_service", fromlist=["CoordinatedStrategyService"]).CoordinatedStrategyService(db)
        assert svc.recruit_diverse_partner("nope", "Finance") is None

    def test_picks_agent_with_new_trait_value(self, db):
        svc = self._initiated_strategy(db, traits={"risk_profile": "conservative"})
        _make_agent(db, "candidate", category="Finance", traits={"risk_profile": "aggressive"})
        partner = svc.recruit_diverse_partner("strat-1", "Finance")
        assert partner.id == "candidate"

    def test_skips_candidate_without_profile_and_falls_back(self, db):
        # RED: before the fix, the fallback returned the strategy's OWN
        # initiator (recruiting the strategy's initiator as its partner).
        svc = self._initiated_strategy(db, traits={"risk_profile": "conservative"})
        _make_agent(db, "no-profile", category="Finance", traits=None)
        partner = svc.recruit_diverse_partner("strat-1", "Finance")
        assert partner.id == "no-profile"
        assert partner.id != "initiator"

    def test_fallback_never_returns_strategy_own_contributor(self, db):
        # Even when every other candidate shares the initiator's trait, the
        # fallback must NOT hand back the strategy's own initiator.
        svc = self._initiated_strategy(db, traits={"risk_profile": "conservative"})
        _make_agent(db, "same-trait", category="Finance", traits={"risk_profile": "conservative"})
        partner = svc.recruit_diverse_partner("strat-1", "Finance")
        assert partner.id == "same-trait"
        assert partner.id != "initiator"

    def test_no_new_trait_falls_back_to_any_specialty_agent(self, db):
        svc = self._initiated_strategy(db, traits={"risk_profile": "conservative"})
        _make_agent(db, "same-trait", category="Finance", traits={"risk_profile": "conservative"})
        partner = svc.recruit_diverse_partner("strat-1", "Finance")
        assert partner.id == "same-trait"

    def test_contributor_without_profile_is_skipped_for_trait_collection(self, db):
        # initiator has NO profile -> existing_traits stays empty, so the
        # candidate with a trait is chosen immediately.
        svc = self._initiated_strategy(db, traits=None)
        _make_agent(db, "candidate", category="Finance", traits={"risk_profile": "aggressive"})
        partner = svc.recruit_diverse_partner("strat-1", "Finance")
        assert partner.id == "candidate"

    def test_no_agents_in_specialty_returns_none(self, db):
        svc = self._initiated_strategy(db, traits={"risk_profile": "conservative"})
        assert svc.recruit_diverse_partner("strat-1", "Legal") is None

    def test_custom_complementary_trait(self, db):
        svc = self._initiated_strategy(db, category="Ops", traits={"risk_profile": "high"})
        _make_agent(db, "candidate", category="Ops", traits={"focus": "speed"})
        partner = svc.recruit_diverse_partner("strat-1", "Ops", complementary_trait="focus")
        assert partner.id == "candidate"


class TestAddContribution:
    def test_adds_contribution_with_agent_specialty(self, db):
        _make_agent(db, "agent-1", category="Legal")
        _make_strategy(db)
        svc = __import__("core.coordinated_strategy_service", fromlist=["CoordinatedStrategyService"]).CoordinatedStrategyService(db)
        contrib = svc.add_contribution("strat-1", "agent-1", {"critique": "risk too high"})

        assert contrib.strategy_id == "strat-1"
        assert contrib.agent_id == "agent-1"
        assert contrib.specialty == "Legal"
        assert contrib.content == {"critique": "risk too high"}
        assert contrib.status == "proposed"
        assert db.query(StrategyContribution).count() == 1

    def test_unknown_agent_raises_value_error(self, db):
        _make_strategy(db)
        svc = __import__("core.coordinated_strategy_service", fromlist=["CoordinatedStrategyService"]).CoordinatedStrategyService(db)
        with pytest.raises(ValueError, match="Agent not found"):
            svc.add_contribution("strat-1", "ghost", {"critique": "x"})
        assert db.query(StrategyContribution).count() == 0


class TestFinalizeStrategy:
    def test_approves_existing_strategy(self, db):
        _make_strategy(db)
        svc = __import__("core.coordinated_strategy_service", fromlist=["CoordinatedStrategyService"]).CoordinatedStrategyService(db)
        assert svc.finalize_strategy("strat-1") is True
        db.refresh(db.query(CoordinatedStrategy).first())
        strat = db.query(CoordinatedStrategy).first()
        assert strat.status == "approved"
        assert strat.approved_at is not None
        assert isinstance(strat.approved_at, datetime)

    def test_missing_strategy_returns_false(self, db):
        svc = __import__("core.coordinated_strategy_service", fromlist=["CoordinatedStrategyService"]).CoordinatedStrategyService(db)
        assert svc.finalize_strategy("nope") is False

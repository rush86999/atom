"""Coverage wave 45 — fleet stack: fleet_routing_config, specialist_matcher, fleet_admiral (W4/P1a).

- fleet_routing_config: flag defaults (OFF master, shadow force-enforce),
  env value matrix
- specialist_matcher helpers: _tier_floor_weight (none/known/unknown),
  _capability_overlap (list/str/empty/mismatch), _recency_bonus (none/string/
  invalid/today/window), _verified_episode_ratio (no-table 0.5, zero episodes,
  verified count, exception)
- SpecialistMatcher: get_all_available_domains (rows + exception fallback),
  find_specialists_for_domains (scored/ranked/limited, exception empty),
  match_specialists (legacy), analyze_domain_requirements (keywords, default
  domain, complexity levels)
- FleetAdmiral: _initialize_recruitment_intelligence (lazy + idempotent),
  analyze_task_requirements + recruit_and_execute with mocked services
"""
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.fleet_routing_config as frc
from core.fleet_routing_config import fleet_routing_enabled, fleet_routing_force_enforce
from core.specialist_matcher import (
    DOMAIN_ALIASES,
    SpecialistMatcher,
    _capability_overlap,
    _recency_bonus,
    _tier_floor_weight,
    _verified_episode_ratio,
)


@pytest.fixture
def fresh_db():
    import tempfile as _tf
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    fd, path = _tf.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


class TestFleetFlags:
    def test_defaults_on_shadow(self):
        # 2026-08-21: master switch defaults ON (shadow — recruitment+audit
        # run, responses still Queen→ReAct); FORCE_ENFORCE stays off.
        with patch.dict(os.environ, {}, clear=True):
            assert fleet_routing_enabled() is True
            assert fleet_routing_force_enforce() is False

    def test_kill_switch_off(self):
        with patch.dict(os.environ, {"ATOM_FLEET_ROUTING_ENABLED": "false"}):
            assert fleet_routing_enabled() is False

    def test_enabled_on(self):
        with patch.dict(os.environ, {"ATOM_FLEET_ROUTING_ENABLED": "true"}):
            assert fleet_routing_enabled() is True

    def test_force_enforce_on(self):
        with patch.dict(os.environ, {"ATOM_FLEET_ROUTING_FORCE_ENFORCE": "1"}):
            assert fleet_routing_force_enforce() is True

    def test_canonical_env_name(self):
        assert frc.ATOM_FLEET_ROUTING_ENABLED == "ATOM_FLEET_ROUTING_ENABLED"


class TestMatcherHelpers:
    def test_tier_floor_weight(self):
        assert _tier_floor_weight(None) > 0
        assert _tier_floor_weight("autonomous") > _tier_floor_weight("student")
        assert _tier_floor_weight("UNKNOWN_TIER") == _tier_floor_weight("student")

    def test_capability_overlap(self):
        assert _capability_overlap([], []) == 0.0
        assert _capability_overlap(["read", "write"], ["READ", "write", "other"]) == 1.0
        assert _capability_overlap(["read"], "read") == 1.0
        assert _capability_overlap(["read"], []) == 0.0
        assert _capability_overlap(["read"], None) == 0.0

    def test_recency_bonus(self):
        assert _recency_bonus(None) == 0.0
        assert _recency_bonus("not-a-date") == 0.0
        assert _recency_bonus(datetime.now(timezone.utc)) == 1.0
        old = datetime.now(timezone.utc) - timedelta(days=400)
        assert _recency_bonus(old) == 0.0
        mid = datetime.now(timezone.utc) - timedelta(days=15)
        assert 0.0 < _recency_bonus(mid) < 1.0
        # ISO string form
        assert _recency_bonus(datetime.now(timezone.utc).isoformat()) == 1.0

    def test_verified_episode_ratio_neutral(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        assert _verified_episode_ratio(db, "a1") == 0.5

    def test_verified_episode_ratio_zero_episodes(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        assert _verified_episode_ratio(db, "a1") == 0.5

    def test_verified_episode_ratio_counted(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 4
        db.query.return_value.join.return_value.filter.return_value.filter.return_value.distinct.return_value.count.return_value = 2
        assert _verified_episode_ratio(db, "a1") == 0.5

    def test_verified_episode_ratio_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        assert _verified_episode_ratio(db, "a1") == 0.5


class TestSpecialistMatcher:
    def test_get_all_available_domains(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("finance",), ("sales",), (None,),
        ]
        m = SpecialistMatcher(db)
        domains = m.get_all_available_domains()
        assert domains == ["finance", "sales"]

    def test_get_all_available_domains_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        m = SpecialistMatcher(db)
        assert m.get_all_available_domains() == list(DOMAIN_ALIASES.keys())

    def test_find_specialists_ranks_and_limits(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = [
            SimpleNamespace(id="a1", name="A1", category="finance",
                            capabilities=["reconciliation"], status="AUTONOMOUS",
                            confidence_score=0.9, last_request_date=None),
            SimpleNamespace(id="a2", name="A2", category="finance",
                            capabilities=[], status="STUDENT",
                            confidence_score=0.3, last_request_date=None),
        ]
        m = SpecialistMatcher(db)
        with patch("core.specialist_matcher._verified_episode_ratio", return_value=0.5):
            result = m.find_specialists_for_domains(["finance"], limit_per_domain=1)
        scored = result["finance"]
        assert len(scored) == 1
        assert scored[0]["agent_id"] == "a1"
        assert scored[0]["capability_score"] > 0

    def test_find_specialists_exception_empty(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        m = SpecialistMatcher(db)
        assert m.find_specialists_for_domains(["finance"]) == {"finance": []}

    def test_match_specialists_legacy(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            SimpleNamespace(id="a1", name="A1", capabilities=["read"], confidence_score=0.8),
            SimpleNamespace(id="a2", name="A2", capabilities=[], confidence_score=0.5),
        ]
        m = SpecialistMatcher(db)
        result = m.match_specialists(["read"], count=1)
        assert len(result) == 1
        assert result[0]["agent_id"] == "a1"

    def test_analyze_domain_requirements(self):
        m = SpecialistMatcher(MagicMock())
        low = m.analyze_domain_requirements("random text without domains")
        assert low["required_domains"]
        assert low["complexity"] == "low"
        high = m.analyze_domain_requirements("finance sales reconciliation pipeline")
        assert high["complexity"] in ("medium", "high")


class TestFleetAdmiral:
    def test_lazy_init_idempotent(self):
        with patch("core.fleet_admiral.AgentFleetService") as afs, \
             patch("core.fleet_admiral.RecruitmentIntelligenceService") as ris:
            from core.fleet_admiral import FleetAdmiral
            fa = FleetAdmiral(MagicMock(), MagicMock())
            fa._initialize_recruitment_intelligence()
            ris.assert_called_once()
            fa._initialize_recruitment_intelligence()  # no second init
            assert ris.call_count == 1

    async def test_analyze_task_requirements_delegates(self):
        with patch("core.fleet_admiral.AgentFleetService"), \
             patch("core.fleet_admiral.RecruitmentIntelligenceService") as ris:
            from core.fleet_admiral import FleetAdmiral
            fa = FleetAdmiral(MagicMock(), MagicMock())
            analysis = SimpleNamespace(
                complexity="low", required_capabilities=["data_analysis"],
                estimated_duration="5 minutes", specialist_count=2, reasoning="r",
            )
            fa.llm.generate_structured_response = AsyncMock(return_value=analysis)
            result = await fa.analyze_task_requirements("reconcile accounts", "u1")
        assert result["complexity"] == "low"
        assert result["required_capabilities"] == ["data_analysis"]

    async def test_analyze_task_requirements_fallback(self):
        with patch("core.fleet_admiral.AgentFleetService"):
            from core.fleet_admiral import FleetAdmiral
            fa = FleetAdmiral(MagicMock(), MagicMock())
            fa.llm.generate_structured_response = AsyncMock(side_effect=RuntimeError("llm down"))
            result = await fa.analyze_task_requirements("task", "u1")
        assert result["complexity"] == "medium"
        assert "fallback" not in result["complexity"]

    async def test_recruit_and_execute(self):
        with patch("core.fleet_admiral.AgentFleetService") as afs, \
             patch("core.fleet_admiral.RecruitmentIntelligenceService") as ris:
            from core.fleet_admiral import FleetAdmiral
            fa = FleetAdmiral(MagicMock(), MagicMock())
            fa.llm.generate_structured_response = AsyncMock(return_value=SimpleNamespace(
                complexity="medium", required_capabilities=["general"],
                estimated_duration="30 minutes", specialist_count=2, reasoning="r",
            ))
            afs.return_value.initialize_fleet.return_value = SimpleNamespace(
                id="chain-1", status="active",
            )
            ris.return_value.orchestrate_recruitment = AsyncMock(
                return_value={
                    "success": True,
                    "recruitment_roster": [{
                        "agent_id": "a1", "agent_name": "A1",
                        "domain": "finance", "capability_score": 0.8,
                        "optimization": "x",
                    }],
                }
            )
            afs.return_value.recruit_member.return_value = SimpleNamespace(id="link-1")
            fa._initialize_recruitment_intelligence()
            result = await fa.recruit_and_execute("finance task", "u1")
        assert result["specialists_count"] == 1
        assert result["chain_id"] == "chain-1"

# -*- coding: utf-8 -*-
"""Coverage wave 85 — core/graduation_service (never-wave-tested).

Covers the Dynamic Threshold skill-promotion gate:
- check_skill_promotion: threshold per complexity (simple=3, moderate=5,
  complex/advanced=8, unknown->5); insufficient episodes -> not promoted;
  full clean streak -> promoted (via _promote_skill_path); streak broken by
  human intervention / low constitutional score / mixed episodes.
- _promote_skill_path: missing agent no-op; promotion record written into
  agent.configuration["promoted_skills"] preserving existing entries.

Real in-memory SQLite (episodes filtered via JSON contains predicate).
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentEpisode, AgentRegistry  # noqa: F401 (register models)

import core.graduation_service as gs
from core.graduation_service import GraduationService


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_agent(db, agent_id="agent-1"):
    agent = AgentRegistry(
        id=agent_id,
        name=agent_id,
        workspace_id="ws-1",
        tenant_id="t1",
        category="Ops",
        module_path="test",
        class_name="Test",
    )
    db.add(agent)
    db.commit()
    return agent


def _episode(db, agent_id="agent-1", *, ep_id=None, skill="skill-1", success=True,
             intervention=0, constitutional=1.0, days_ago=1, outcome="success"):
    ep = AgentEpisode(
        id=ep_id or f"ep-{days_ago}-{intervention}-{constitutional}",
        agent_id=agent_id,
        tenant_id="t1",
        workspace_id="ws-1",
        task_description="task",
        maturity_at_time="intern",
        constitutional_score=constitutional,
        human_intervention_count=intervention,
        outcome=outcome,
        success=success,
        metadata_json={"skill_id": skill},
        started_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(ep)
    db.commit()
    return ep


def _seed_clean_streak(db, n, skill="skill-1"):
    for i in range(n):
        _episode(db, days_ago=n - i, ep_id=f"clean-{i}", skill=skill)
    return [e.id for e in db.query(AgentEpisode).all()]


class TestCheckSkillPromotion:
    def test_no_episodes_not_promoted(self, db):
        _make_agent(db)
        result = asyncio.run(GraduationService(db).check_skill_promotion("agent-1", "skill-1"))
        assert result == {"promoted": False,
                          "reason": "Insufficient episodes (0/5)",
                          "current_streak": 0}

    def test_insufficient_episodes_reports_count(self, db):
        _make_agent(db)
        _seed_clean_streak(db, 2)
        result = asyncio.run(GraduationService(db).check_skill_promotion("agent-1", "skill-1"))
        assert result["promoted"] is False
        assert result["reason"] == "Insufficient episodes (2/5)"

    def test_simple_complexity_threshold_is_three(self, db):
        _make_agent(db)
        _seed_clean_streak(db, 3)
        result = asyncio.run(GraduationService(db).check_skill_promotion(
            "agent-1", "skill-1", complexity="simple"))
        assert result["promoted"] is True
        assert result["streak"] == 3

    def test_complex_threshold_is_eight(self, db):
        _make_agent(db)
        _seed_clean_streak(db, 8)
        result = asyncio.run(GraduationService(db).check_skill_promotion(
            "agent-1", "skill-1", complexity="complex"))
        assert result["promoted"] is True
        assert result["streak"] == 8

    def test_advanced_maps_to_eight(self, db):
        _make_agent(db)
        _seed_clean_streak(db, 8)
        result = asyncio.run(GraduationService(db).check_skill_promotion(
            "agent-1", "skill-1", complexity="advanced"))
        assert result["promoted"] is True

    def test_unknown_complexity_defaults_to_moderate(self, db):
        _make_agent(db)
        _seed_clean_streak(db, 5)
        result = asyncio.run(GraduationService(db).check_skill_promotion(
            "agent-1", "skill-1", complexity="EXOTIC"))
        assert result["promoted"] is True

    def test_promotion_writes_config_and_returns_streak(self, db):
        _make_agent(db)
        _seed_clean_streak(db, 5)
        result = asyncio.run(GraduationService(db).check_skill_promotion("agent-1", "skill-1"))
        assert result["promoted"] is True
        assert result["reason"] == "Completed 5 consecutive clean runs."
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == "agent-1").first()
        entry = agent.configuration["promoted_skills"]["skill-1"]
        assert entry["status"] == "autonomous"
        assert entry["promoted_at"]
        assert entry["last_successful_episode"] == "clean-4"

    def test_streak_broken_by_human_intervention(self, db):
        _make_agent(db)
        _seed_clean_streak(db, 4)
        _episode(db, days_ago=1, intervention=2, ep_id="dirty")
        result = asyncio.run(GraduationService(db).check_skill_promotion("agent-1", "skill-1"))
        assert result["promoted"] is False
        assert result["current_streak"] == 0
        assert "Streak broken" in result["reason"]

    def test_streak_broken_by_low_constitutional_score(self, db):
        _make_agent(db)
        _seed_clean_streak(db, 4)
        _episode(db, days_ago=1, constitutional=0.5, ep_id="low-score")
        result = asyncio.run(GraduationService(db).check_skill_promotion("agent-1", "skill-1"))
        assert result["promoted"] is False
        assert result["current_streak"] == 0

    def test_streak_broken_midway_reports_partial(self, db):
        _make_agent(db)
        # 5 recent episodes: newest clean, second dirty, three older clean —
        # streak counting must stop at the dirty episode.
        _episode(db, days_ago=1, ep_id="newest-clean")
        _episode(db, days_ago=2, intervention=1, ep_id="middle-dirty")
        for i in range(3):
            _episode(db, days_ago=5 - i, ep_id=f"old-clean-{i}")
        result = asyncio.run(GraduationService(db).check_skill_promotion("agent-1", "skill-1"))
        assert result["promoted"] is False
        assert result["current_streak"] == 1
        assert "Streak broken or incomplete" in result["reason"]

    def test_failed_episodes_do_not_count(self, db):
        # 5 FAILED episodes must NOT satisfy the count gate (BUG-025 semantics)
        _make_agent(db)
        for i in range(5):
            _episode(db, days_ago=5 - i, success=False, outcome="failure", ep_id=f"fail-{i}")
        result = asyncio.run(GraduationService(db).check_skill_promotion("agent-1", "skill-1"))
        assert result["promoted"] is False
        assert result["reason"] == "Insufficient episodes (0/5)"

    def test_other_skill_episodes_excluded(self, db):
        _make_agent(db)
        _seed_clean_streak(db, 5, skill="other-skill")
        result = asyncio.run(GraduationService(db).check_skill_promotion("agent-1", "skill-1"))
        assert result["promoted"] is False
        assert result["reason"] == "Insufficient episodes (0/5)"


class TestPromoteSkillPath:
    def test_missing_agent_is_noop(self, db):
        result = asyncio.run(GraduationService(db)._promote_skill_path(
            "ghost", "skill-1", MagicEpisode("ep-1")))
        assert result is None

    def test_preserves_existing_promoted_skills(self, db):
        _make_agent(db)
        agent = db.query(AgentRegistry).first()
        agent.configuration = {"promoted_skills": {"skill-0": {"status": "autonomous"}}}
        db.commit()
        ep = _episode(db, days_ago=1, ep_id="ep-x")
        asyncio.run(GraduationService(db)._promote_skill_path("agent-1", "skill-1", ep))
        db.refresh(agent)
        skills = agent.configuration["promoted_skills"]
        assert "skill-0" in skills
        assert skills["skill-1"]["status"] == "autonomous"
        assert skills["skill-1"]["last_successful_episode"] == "ep-x"

    def test_agent_without_config_initializes(self, db):
        _make_agent(db)
        ep = _episode(db, days_ago=1, ep_id="ep-y")
        asyncio.run(GraduationService(db)._promote_skill_path("agent-1", "skill-1", ep))
        agent = db.query(AgentRegistry).first()
        assert agent.configuration["promoted_skills"]["skill-1"]["status"] == "autonomous"


from unittest.mock import MagicMock as MagicEpisode  # noqa: E402

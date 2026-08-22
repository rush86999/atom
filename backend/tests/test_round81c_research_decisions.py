"""Round 81c — research-informed journey decisions (R81j).

Web-research synthesis (2026 sources) behind these changes:

- Explicit user ratings are a HIGH-PRECISION but LOW-VOLUME, EXTREMES-BIASED
  signal (<10% participation; Prodinja 2026 "Thumbs, Edits, Retries"). The
  robust-RLHF literature treats such rewards as noisy inputs to be discounted,
  not trusted at full weight. Trust-in-automation work (Lee & See lineage;
  Ou 2026 "Progressive Autonomy as Preference Learning"; Sando's
  progressive-autonomy framework) grounds promotions in demonstrated outcome
  streaks, not subjective praise.
    => Positive ratings give a TINY confidence nudge (+0.005, half the
       outcome drip), only from TRUSTED users (admin or specialty match —
       same trust rule as governance adjudication), capped per day
       (anti-farming / diminishing returns). Outcome streaks and exams remain
       the promotion path. Flag: ATOM_POSITIVE_RATING_BOOST_ENABLED.

- Memory-hygiene is the standard production concern ("the silent killer" —
  2026 memory-stack surveys: tiered HOT/WARM/COLD, scheduled decay +
  consolidation; Mem0 consolidates rather than accumulates). Atom already has
  decay/consolidate + manual routes + an experiments-flag worker, but no
  turnkey daily maintenance. => EpisodeLifecycleService.run_daily_maintenance()
  plus an opt-in env-gated lifespan hook
  (ATOM_EPISODE_LIFECYCLE_MAINTENANCE_ENABLED, default OFF).
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock
from sqlalchemy.orm import Session

from core.models import (
    AgentFeedback,
    AgentRegistry,
    AgentStatus,
    User,
    UserRole,
)


def _sqlite_session():
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker

    engine = sa.create_engine("sqlite://")
    for table in (AgentRegistry.__table__, User.__table__, AgentFeedback.__table__):
        table.create(engine)
    return sessionmaker(bind=engine)()


def _agent(db, status="intern", confidence=0.55):
    row = db.query(AgentRegistry).filter_by(id="ag-1").first()
    if row:
        return row
    db.add(AgentRegistry(
        id="ag-1",
        name="Rated Agent",
        category="operations",
        module_path="t.m",
        class_name="T",
        status=status,
        confidence_score=confidence,
        tenant_id="default",
        workspace_id="default",
    ))
    db.commit()
    return db.query(AgentRegistry).filter_by(id="ag-1").first()


def _user(db, role=UserRole.SUPER_ADMIN.value):
    existing = db.query(User).filter_by(id="rate-user").first()
    if existing:
        return existing
    u = User(
        id="rate-user",
        email=f"{role}@x.io",
        role=role,
        first_name="R",
        last_name="U",
        status="active",
    )
    db.add(u)
    db.commit()
    return u


# ============================================================================
# G14 — positive ratings nudge confidence (trusted-only, tiny, capped)
# ============================================================================


class TestPositiveRatingBoost:
    async def _submit(self, db, rating, role=UserRole.SUPER_ADMIN.value):
        """Drive the endpoint logic with overridden auth/db deps."""
        from api.feedback_enhanced import submit_enhanced_feedback, FeedbackSubmitRequest

        agent = _agent(db)
        _user(db, role)
        req = FeedbackSubmitRequest(
            agent_id="ag-1",
            user_id="rate-user",
            original_output="out",
            rating=rating,
        )
        current_user = Mock(id="rate-user")
        return (
            await submit_enhanced_feedback(
                request=req, current_user=current_user, db=db
            ),
            agent,
        )

    @pytest.mark.asyncio
    async def test_trusted_five_star_boosts_by_magnitude(self, monkeypatch):
        monkeypatch.setenv("ATOM_POSITIVE_RATING_BOOST_ENABLED", "true")
        db = _sqlite_session()
        before = _agent(db).confidence_score

        response, _ = await self._submit(db, rating=5)
        assert response is not None

        after = db.query(AgentRegistry).filter_by(id="ag-1").first().confidence_score
        fbrow = db.query(AgentFeedback).first()
        assert abs((after - before) - 0.005) < 1e-9
        marker = (
            db.query(AgentFeedback)
            .filter(AgentFeedback.ai_reasoning.like("%rating_boost_applied%"))
            .count()
        )
        assert marker == 1

    @pytest.mark.asyncio
    async def test_daily_cap_blocks_repeat_boosts(self, monkeypatch):
        monkeypatch.setenv("ATOM_POSITIVE_RATING_BOOST_ENABLED", "true")
        monkeypatch.setenv("ATOM_POSITIVE_RATING_BOOST_DAILY_CAP", "1")
        db = _sqlite_session()

        await self._submit(db, rating=5)
        conf_after_first = db.query(AgentRegistry).filter_by(id="ag-1").first().confidence_score

        await self._submit(db, rating=5)
        conf_after_second = db.query(AgentRegistry).filter_by(id="ag-1").first().confidence_score

        assert conf_after_second == conf_after_first  # capped
        skipped = (
            db.query(AgentFeedback)
            .filter(AgentFeedback.ai_reasoning.like("%daily_cap%"))
            .count()
        )
        assert skipped == 1

    @pytest.mark.asyncio
    async def test_untrusted_rating_does_not_boost(self, monkeypatch):
        monkeypatch.setenv("ATOM_POSITIVE_RATING_BOOST_ENABLED", "true")
        db = _sqlite_session()
        before = _agent(db).confidence_score

        await self._submit(db, rating=5, role=UserRole.MEMBER.value)

        after = db.query(AgentRegistry).filter_by(id="ag-1").first().confidence_score
        assert after == before

    @pytest.mark.asyncio
    async def test_low_rating_is_neutral(self, monkeypatch):
        """Only corrections penalize today; a 2-star rating stays neutral so we
        don't double-punish alongside the correction pipeline."""
        monkeypatch.setenv("ATOM_POSITIVE_RATING_BOOST_ENABLED", "true")
        db = _sqlite_session()
        before = _agent(db).confidence_score

        await self._submit(db, rating=2)

        after = db.query(AgentRegistry).filter_by(id="ag-1").first().confidence_score
        assert after == before

    @pytest.mark.asyncio
    async def test_flag_disabled_disables_path(self, monkeypatch):
        monkeypatch.setenv("ATOM_POSITIVE_RATING_BOOST_ENABLED", "false")
        db = _sqlite_session()
        before = _agent(db).confidence_score

        self._submit(db, rating=5)

        after = db.query(AgentRegistry).filter_by(id="ag-1").first().confidence_score
        assert after == before


# ============================================================================
# G15 — episode lifecycle daily maintenance
# ============================================================================


class TestEpisodeLifecycleMaintenance:
    @pytest.mark.asyncio
    async def test_runs_decay_and_consolidate(self):
        from core.episode_lifecycle_service import EpisodeLifecycleService

        from unittest.mock import AsyncMock as _AM

        svc = MagicMock(spec=EpisodeLifecycleService)
        svc.decay_old_episodes = _AM(return_value={"decayed": 3})
        svc.consolidate_similar_episodes = _AM(return_value={"consolidated": 1})

        result = await EpisodeLifecycleService.run_daily_maintenance(
            svc, agents=["a1", "a2"]
        )

        svc.decay_old_episodes.assert_awaited_once_with(90)
        assert svc.consolidate_similar_episodes.await_count == 2
        assert result == {"decayed": 3, "consolidated": 2}

    @pytest.mark.asyncio
    async def test_decay_failure_does_not_block_consolidation(self):
        from core.episode_lifecycle_service import EpisodeLifecycleService

        svc = MagicMock(spec=EpisodeLifecycleService)

        async def boom(days_threshold):
            raise RuntimeError("db")

        from unittest.mock import AsyncMock as _AM

        svc.decay_old_episodes = boom
        svc.consolidate_similar_episodes = _AM(return_value={"consolidated": 5})

        result = await EpisodeLifecycleService.run_daily_maintenance(svc, agents=["a1"])
        assert result["consolidated"] == 5

    def test_lifespan_wiring_pinned(self):
        import inspect

        src = inspect.getsource(__import__("main_api_app"))
        assert "run_daily_maintenance" in src
        assert "ATOM_EPISODE_LIFECYCLE_MAINTENANCE_ENABLED" in src


def _async_return(value):
    async def _fn(*args, **kwargs):
        return value

    return _fn

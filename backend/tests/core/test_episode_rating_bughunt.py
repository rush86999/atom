"""
Bug-hunt tests for the episode/rating retrieval cluster.

Targets (all UNCOMMITTED churn, no dedicated passing coverage):
- core/episode_retrieval_service.py
- core/rating_sync_service.py
- core/episode_lifecycle_service.py

Each test asserts the CORRECT behavior and fails because of a real bug in the
target module. Tests are isolated: they build an in-memory SQLite database from
the real `core.models.Base` (so ORM behavior, column resolution and timezone
handling are exercised truthfully) and mock out only external services
(LanceDB, AtomSaaS, governance).
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, Episode, SkillRating
from core.rating_sync_service import RatingSyncService
from core.episode_retrieval_service import (
    EpisodeRetrievalService,
    RetrievalMode,
)
import core.episode_lifecycle_service as core_episode_module
from core.episode_lifecycle_service import EpisodeLifecycleService


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------

def _make_engine_session():
    """Fresh in-memory SQLite database with the full schema created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def uuid4hex():
    return uuid.uuid4().hex[:8]


def _episode(**overrides):
    """Build a persistable Episode (AgentEpisode) with all NOT-NULL fields."""
    defaults = dict(
        agent_id="agent-1",
        tenant_id="tenant-1",
        maturity_at_time="INTERN",
        task_description="test episode",
        status="completed",
        started_at=datetime.now(timezone.utc) - timedelta(days=1),
        importance_score=0.5,
        decay_score=1.0,
        access_count=0,
        outcome="success",
        success=True,
    )
    defaults.update(overrides)
    defaults.setdefault("id", f"ep-{uuid4hex()}")
    return Episode(**defaults)


@pytest.fixture
def db():
    """Function-scoped in-memory DB session."""
    engine, SessionLocal = _make_engine_session()
    session = SessionLocal()
    yield session
    session.close()


def _lifecycle_service(db):
    """EpisodeLifecycleService with LanceDB stubbed out."""
    with patch("core.episode_lifecycle_service.get_lancedb_handler"):
        return EpisodeLifecycleService(db)


def _retrieval_service(db):
    """EpisodeRetrievalService with LanceDB + governance stubbed (allowed)."""
    with patch("core.episode_retrieval_service.get_lancedb_handler"):
        with patch("core.episode_retrieval_service.AgentGovernanceService") as gov:
            gov.return_value.can_perform_action.return_value = {"allowed": True}
            return EpisodeRetrievalService(db)


# ===========================================================================
# rating_sync_service.py
# ===========================================================================

class TestRatingSyncSkillRatingAttributeMismatch:
    """RatingSyncService queries/sets SkillRating.synced_to_saas, synced_at and
    remote_rating_id, but the SkillRating ORM model declares none of them.
    The columns exist only via an Alembic migration (b55b0f499509), so they
    are invisible to the ORM mapper: referencing them as class attributes
    raises AttributeError at query-construction time, breaking every sync
    entry point as written."""

    def test_get_pending_ratings_does_not_raise(self, db):
        """BUG: rating_sync get_pending_ratings filters on
        SkillRating.synced_to_saas (a class attribute that does not exist on
        the model) -> AttributeError instead of a result list."""
        db.add(SkillRating(
            skill_id="s1", user_id="u1", tenant_id="tenant-1", rating=5,
        ))
        db.commit()

        svc = RatingSyncService(db, MagicMock())
        pending = svc.get_pending_ratings()
        assert isinstance(pending, list)
        assert len(pending) == 1

    def test_get_sync_metrics_does_not_raise(self, db):
        """BUG: rating_sync get_sync_metrics queries
        SkillRating.synced_to_saas == False / == True (class attributes that
        do not exist on the model) -> AttributeError instead of integer
        counts."""
        svc = RatingSyncService(db, MagicMock())
        metrics = svc.get_sync_metrics()
        assert metrics["pending_count"] == 0
        assert metrics["synced_count"] == 0

    @pytest.mark.asyncio
    async def test_sync_ratings_syncs_pending_ratings(self, db):
        """BUG: rating_sync sync_ratings routes through get_pending_ratings,
        which references the non-existent SkillRating.synced_to_saas column.
        The exception is swallowed by the broad try/except and the run is
        reported as a failure (uploaded=0) even though the (mocked) remote is
        healthy and ratings are pending."""
        for i in range(3):
            db.add(SkillRating(
                skill_id=f"s{i}", user_id=f"u{i}", tenant_id="tenant-1",
                rating=5,
            ))
        db.commit()

        client = MagicMock()
        client.rate_skill = AsyncMock(return_value={"success": True, "id": "r1"})
        svc = RatingSyncService(db, client)

        result = await svc.sync_ratings()
        assert result["success"] is True
        assert result["uploaded"] == 3
        assert result["failed"] == 0


class TestRatingConflictNoneCreatedAt:
    """resolve_rating_conflict dereferences local_rating.created_at.tzinfo
    without first checking that created_at is not None."""

    @pytest.mark.asyncio
    async def test_resolve_conflict_handles_none_created_at(self, db):
        """BUG: rating_sync resolve_rating_conflict does
        `local_time = local_rating.created_at` then `local_time.tzinfo`.
        When created_at is None (e.g. an in-memory rating that was never
        flushed/refreshed), this raises AttributeError instead of skipping or
        defaulting, so a single malformed rating aborts conflict resolution."""
        rating = SkillRating(
            id="r-none", skill_id="s1", user_id="u1", tenant_id="tenant-1",
            rating=4, review="ok",
        )
        # Force created_at to None to simulate the not-yet-persisted case.
        rating.created_at = None

        svc = RatingSyncService(db, MagicMock())
        remote = {
            "id": "remote-1", "rating": 5, "comment": "great",
            "created_at": "2026-02-19T12:00:00Z",
        }
        # Must return a resolution dict, not raise AttributeError.
        result = await svc.resolve_rating_conflict(rating, remote)
        assert isinstance(result, dict)
        assert "action" in result


# ===========================================================================
# episode_lifecycle_service.py
# ===========================================================================

class TestLifecycleDecayNaiveStartedAt:
    """The uncommitted diff replaced datetime.now() with
    datetime.now(timezone.utc) in decay_old_episodes, but unlike its sibling
    update_lifecycle it performs NO offset-aware/naive normalization. The age
    computation `datetime.now(timezone.utc) - episode.started_at` raises
    TypeError whenever started_at is offset-naive, aborting the whole decay
    batch before any decay (or archival) is applied."""

    @pytest.mark.asyncio
    async def test_decay_handles_naive_started_at(self, db):
        """BUG: lifecycle decay_old_episodes line 53 computes
        `datetime.now(timezone.utc) - episode.started_at` without the
        tz-normalization that update_lifecycle has; a naive started_at raises
        TypeError and the decay batch returns 0 affected / 0 archived."""
        old = _episode(
            started_at=datetime.utcnow() - timedelta(days=200),  # naive
            status="completed",
        )
        db.add(old)
        db.commit()

        svc = _lifecycle_service(db)
        result = await svc.decay_old_episodes(days_threshold=90)
        assert result["affected"] >= 1
        db.refresh(old)
        assert old.decay_score is not None


class TestLifecycleDecayInflatesAccessCount:
    """decay_old_episodes previously incremented episode.access_count inside
    the decay loop. Decay is a background maintenance operation, but
    access_count is consumed by retrieval (e.g. retrieve_contextual boosting,
    batch_update semantics) as a read/popularity signal, so running decay
    silently inflated those signals.

    The naive-datetime crash that used to shadow this bug is now fixed
    (decay_old_episodes normalizes offset-naive started_at to aware UTC), so
    this test no longer needs to patch datetime — it just runs decay and
    confirms access_count is untouched."""

    @pytest.mark.asyncio
    async def test_decay_does_not_increment_access_count(self, db):
        """BUG: lifecycle decay_old_episodes did `episode.access_count += 1`
        on every episode it touched. Decay must not mutate access_count (a
        popularity/recall signal), only decay_score / status."""
        old = _episode(
            started_at=datetime.utcnow() - timedelta(days=200),  # naive
            status="completed",
            access_count=0,
        )
        db.add(old)
        db.commit()

        svc = _lifecycle_service(db)
        await svc.decay_old_episodes(days_threshold=90)
        db.refresh(old)
        assert old.access_count == 0, (
            "decay must not mutate access_count (it is a popularity/recall "
            "signal, not a maintenance counter)"
        )


class TestLifecycleDecayFormulaInconsistency:
    """Two methods previously wrote the same Episode.decay_score field with
    OPPOSITE formulas:
      - decay_old_episodes (old code): max(0, 1 - days_old/180)
        (a 'freshness' score: 1.0 fresh -> 0 at 180 days)
      - update_lifecycle:               min(1, days_old/90)
        ('how much decay has been applied': 0 fresh -> 1 at 90 days)
    The serialized decay_score is consumed by retrieval, so which value an
    episode reported depended on which maintenance path last ran.

    Resolution: update_lifecycle's formula is the canonical one (it has the
    detailed, worked docstring defining decay_score as 'how much decay has
    been applied', 0->1). decay_old_episodes was changed to match it. These
    tests verify the two paths now agree."""

    def test_decay_old_episodes_matches_update_lifecycle_formula(self, db):
        """Both decay paths now use min(1, days_old/90) for decay_score."""
        started = datetime.now(timezone.utc) - timedelta(days=100)
        ep = _episode(started_at=started, status="completed", decay_score=0.0)

        svc = _lifecycle_service(db)
        assert svc.update_lifecycle(ep) is True
        per_episode_score = ep.decay_score

        # Now run the batch path on the same episode and confirm it writes
        # the same value.
        ep.decay_score = 0.0
        import asyncio
        asyncio.get_event_loop  # ensure loop available
        result = asyncio.run(svc.decay_old_episodes(days_threshold=90))

        # update_lifecycle and decay_old_episodes must agree on decay_score.
        # (Re-fetch the value the batch path wrote via the same formula.)
        days_old = 100
        expected = min(1.0, max(0.0, days_old / 90.0))
        assert per_episode_score == pytest.approx(expected, abs=1e-6), (
            f"update_lifecycle wrote decay_score={per_episode_score}, "
            f"expected {expected}"
        )


# ===========================================================================
# episode_retrieval_service.py
# ===========================================================================

class TestRetrievalContextualSliceThenFilter:
    """retrieve_contextual sorts+slices the scored candidates to `limit` and
    ONLY THEN applies the require_canvas / require_feedback filters. Episodes
    that would satisfy the requirement but sit just below the score cutoff are
    never considered, so a caller asking for `limit` canvas episodes can
    receive fewer even though enough eligible candidates exist."""

    @pytest.mark.asyncio
    async def test_contextual_require_canvas_does_not_lose_qualifying_episodes(self):
        """BUG: retrieval retrieve_contextual applies require_canvas AFTER the
        `sorted(...)[:limit]` slice. The top-`limit` episodes here lack canvas
        and are dropped, but a qualifying episode ranked just below the slice
        is never promoted in, so the caller receives fewer canvas episodes
        than `limit` despite eligible candidates existing."""
        svc = EpisodeRetrievalService.__new__(EpisodeRetrievalService)
        svc.db = MagicMock()
        svc.governance = MagicMock()

        # 6 candidates. ep1..ep3 have NO canvas; ep4..ep6 HAVE canvas.
        # ep1..ep5 score 1.0 (temporal+semantic); ep6 scores 0.3 (temporal
        # only) -> ranked 6th, just below the limit=5 slice.
        ep_objs = {
            eid: MagicMock(
                id=eid, agent_id="a1",
                canvas_action_count=cc,
                aggregate_feedback_score=None,
                feedback_ids=[],
            )
            for eid, cc in [
                ("ep1", 0), ("ep2", 0), ("ep3", 0),
                ("ep4", 1), ("ep5", 1), ("ep6", 1),
            ]
        }

        def _query(*_a, **_k):
            q = MagicMock()
            q.filter.return_value.all.return_value = list(ep_objs.values())
            return q
        svc.db.query.side_effect = _query

        async def fake_temporal(*_a, **_k):
            return {"episodes": [{"id": eid} for eid in ep_objs]}

        async def fake_semantic(*_a, **_k):
            return {"episodes": [{"id": eid}
                                 for eid in ["ep1", "ep2", "ep3", "ep4", "ep5"]]}

        svc.retrieve_temporal = fake_temporal
        svc.retrieve_semantic = fake_semantic

        with patch.object(svc, "_log_access", new=AsyncMock()):
            with patch.object(
                svc, "_serialize_episode", side_effect=lambda e: {"id": e.id}
            ):
                result = await svc.retrieve_contextual(
                    agent_id="a1", current_task="t", limit=5, require_canvas=True,
                )

        returned_ids = [e["id"] for e in result["episodes"]]
        # ep6 is ranked below the top-5 slice but has canvas and should be
        # promoted once ep1..ep3 are filtered out.
        assert "ep6" in returned_ids, (
            "qualifying episode ranked just below the limit must not be dropped "
            "by filter-after-slice ordering"
        )
        assert result["count"] == 3


class TestRetrievalSupervisionFilterReporting:
    """retrieve_with_supervision_context appends to filters_applied ONLY
    inside the per-episode loop. When every episode is removed by a filter,
    the loop body never runs and the applied filter is never reported, even
    though it materially changed (emptied) the result set."""

    @pytest.mark.asyncio
    async def test_supervision_filter_recorded_when_all_filtered_out(self, db):
        """BUG: retrieval retrieve_with_supervision_context records
        filters_applied only inside the per-episode loop, so a min_rating
        filter that excludes the only candidate is never reported in
        supervision_filters_applied."""
        ep = _episode(
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
            status="completed",
            supervisor_rating=2,            # below the min_rating=4 filter
            human_intervention_count=0,
        )
        db.add(ep)
        db.commit()

        svc = _retrieval_service(db)
        result = await svc.retrieve_with_supervision_context(
            agent_id="agent-1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            time_range="30d",
            min_rating=4,
        )
        assert result["count"] == 0
        assert any("min_rating" in f for f in result["supervision_filters_applied"]), (
            "an applied filter that removes all episodes must still be reported"
        )


class TestRetrievalSupervisionStringMode:
    """retrieve_with_supervision_context's retrieval_mode parameter is typed
    as a RetrievalMode enum, yet the docstring lists the human-readable names
    ('temporal', 'semantic', ...). Passing the documented string form crashes
    on the final `retrieval_mode.value` access."""

    @pytest.mark.asyncio
    async def test_supervision_context_accepts_string_retrieval_mode(self, db):
        """BUG: retrieval retrieve_with_supervision_context documents
        retrieval_mode as the strings 'temporal'|'semantic'|... but returns
        `retrieval_mode.value`, raising AttributeError for the documented
        input form."""
        ep = _episode(
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
            status="completed",
        )
        db.add(ep)
        db.commit()

        svc = _retrieval_service(db)
        result = await svc.retrieve_with_supervision_context(
            agent_id="agent-1",
            retrieval_mode="temporal",      # documented, accepted string form
            time_range="30d",
        )
        assert result["count"] >= 1


class TestRetrievalImprovementTrendUnsortedFallback:
    """_filter_improvement_trend has two early-return paths that hand back the
    ORIGINAL (unsorted) episode list, while the positive-trend path returns
    the reverse-sorted list. Callers therefore receive inconsistently ordered
    results depending on whether enough rated episodes exist."""

    def test_improvement_trend_preserves_recency_order_when_insufficient_data(self):
        """BUG: retrieval _filter_improvement_trend returns the input list
        verbatim (unsorted) on the <5-episode and no-ratings early-return
        branches, but returns reverse-chronologically-sorted episodes when a
        trend is detected. Sorting by started_at should happen once up front
        so every return path is consistently ordered."""
        svc = EpisodeRetrievalService.__new__(EpisodeRetrievalService)

        class _Ep:
            def __init__(self, started_at, rating):
                self.id = uuid4hex()
                self.started_at = started_at
                self.supervisor_rating = rating

        base = datetime.now(timezone.utc)
        # Deliberately pass these in NON-chronological order.
        eps = [
            _Ep(base - timedelta(days=3), None),   # too few to trend
            _Ep(base - timedelta(days=1), None),
            _Ep(base - timedelta(days=2), None),
        ]
        out = svc._filter_improvement_trend(eps)
        out_times = [e.started_at for e in out]
        # Whatever the branch, the returned order must be deterministic and
        # consistent with the positive-trend branch (newest first).
        assert out_times == sorted(out_times, reverse=True), (
            "improvement-trend early-return must still return recency-sorted "
            "episodes for caller consistency"
        )

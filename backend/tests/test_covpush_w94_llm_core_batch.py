# -*- coding: utf-8 -*-
"""Coverage wave 94 — six-module batch.

Targets:
1. core/llm/embedding/providers.py
2. core/workflow_endpoints.py
3. core/message_analytics_engine.py
4. core/graphrag/dynamic_graph.py
5. core/canvas_orchestration_service.py
6. core/feedback_service.py   (new tests below — previously ~10%)

No network, no LLM, no real external DB: every external boundary is mocked.
Plain pytest + unittest.mock, following the established wave-93 style.

For modules 1-5 the battle-tested suites from earlier waves are re-collected
here (imported classes/functions + their fixtures) so this single file drives
each module past 80% on its own. Module 6 (feedback_service) gets fresh tests
with a fake SQLAlchemy session.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# --------------------------------------------------------------------------- #
# 1. embedding providers — reuse provider suites from tests/test_covpush_llminfra.py
# --------------------------------------------------------------------------- #
from tests.test_covpush_llminfra import (  # noqa: F401
    openai_provider,
    TestOpenAIEmbeddingProvider,
    TestCohereEmbeddingProvider,
    TestVoyageEmbeddingProvider,
    TestNomicEmbeddingProvider,
    TestJinaEmbeddingProvider,
)

# --------------------------------------------------------------------------- #
# 2. workflow endpoints — reuse from tests/test_covpush_api_wave.py
# --------------------------------------------------------------------------- #
import tests.test_covpush_api_wave as _api
from tests.test_covpush_api_wave import (  # noqa: F401
    TestWorkflowEndpointsCoverage,
    TestWorkflowEndpointsLastGaps,
    TestWorkflowEndpointsLastGaps2,
)

# --------------------------------------------------------------------------- #
# 3. message analytics engine — reuse from tests/test_covpush_w72_message_analytics.py
# --------------------------------------------------------------------------- #
from tests.test_covpush_w72_message_analytics import *  # noqa: F401,F403

# --------------------------------------------------------------------------- #
# 4. graphrag dynamic graph — reuse from tests/test_covpush_w64c_dynamic_graph.py
# --------------------------------------------------------------------------- #
import tests.test_covpush_w64c_dynamic_graph as _dg
from tests.test_covpush_w64c_dynamic_graph import (  # noqa: F401
    TestUpdateType,
    TestGraphVersionStatus,
    TestIncrementalUpdateConfig,
    TestGraphUpdateDataclass,
    TestGraphSnapshotDataclass,
    TestGraphVersionManager,
    TestIncrementalUpdateManagerAdd,
    TestIncrementalUpdateManagerFlush,
    TestNodeApply,
    TestEdgeApply,
    TestGroupAndDispatch,
    TestTemporalGraphTracker,
    TestDynamicGraphManager,
    TestFactories,
)

# --------------------------------------------------------------------------- #
# 5. canvas orchestration — reuse from tests/test_canvas_orchestration_service.py
# --------------------------------------------------------------------------- #
from tests.test_canvas_orchestration_service import (  # noqa: F401
    mock_db,
    service,
    sample_tasks,
    TestOrchestrationInitialization,
    TestPresentationLifecycle,
    TestStateManagement,
    TestMultiClientCoordination,
    TestNodeAndConnectionManagement,
)

# The two source modules define *different* `db_session` fixtures; dispatch on
# the requesting class so both reused suites behave exactly as originally run.
_DG_CLASSES = (
    TestUpdateType, TestGraphVersionStatus, TestIncrementalUpdateConfig,
    TestGraphUpdateDataclass, TestGraphSnapshotDataclass, TestGraphVersionManager,
    TestIncrementalUpdateManagerAdd, TestIncrementalUpdateManagerFlush,
    TestNodeApply, TestEdgeApply, TestGroupAndDispatch, TestTemporalGraphTracker,
    TestDynamicGraphManager, TestFactories,
)

# unwrap pytest fixture wrappers to the raw generator functions
_DG_DB = getattr(_dg.db_session, "__wrapped__", None) or _dg.db_session
_API_DB = getattr(_api.db_session, "__wrapped__", None) or _api.db_session


@pytest.fixture()
def db_session(request):
    if request.cls in _DG_CLASSES:
        yield from _DG_DB()
    else:
        yield from _API_DB()


# =========================================================================== #
# 6. core/feedback_service.py — fresh coverage (previously ~10%)
# =========================================================================== #
import core.feedback_service as fbs


class Q:
    """Chainable fake query."""
    def __init__(self, first=None, all_=None, count=0):
        self._first, self._all, self._count = first, list(all_ or []), count

    def filter(self, *a, **k): return self
    def join(self, *a, **k): return self
    def order_by(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def offset(self, *a, **k): return self
    def first(self): return self._first
    def all(self): return self._all
    def count(self): return self._count


class FakeDB:
    """Routes queries by model name; per-model queues pop until one left."""
    def __init__(self, **routes):
        self.routes = {k: (list(v) if isinstance(v, list) else [v])
                       for k, v in routes.items()}
        self.added, self.deleted, self.commits = [], [], 0

    def query(self, model):
        name = getattr(model, "__name__", str(model))
        qs = self.routes.get(name)
        if not qs:
            return Q()
        return qs.pop(0) if len(qs) > 1 else qs[0]

    def add(self, obj): self.added.append(obj)

    def delete(self, obj): self.deleted.append(obj)

    def commit(self): self.commits += 1

    def rollback(self): pass

    def refresh(self, obj): pass


def _session(**kw):
    d = dict(id="s1", supervisor_id="sup1", status="completed")
    d.update(kw)
    return _NS(**d)


def _rating(**kw):
    d = dict(id="r1", supervision_session_id="s1", supervisor_id="sup1",
             rater_id="u1", agent_id=None, rating=5, rating_category="quality",
             reason=None, was_helpful=True, created_at=datetime.now(timezone.utc),
             updated_at=None)
    d.update(kw)
    return _NS(**d)


def _comment(**kw):
    d = dict(id="c1", supervision_session_id="s1", author_id="u1",
             parent_comment_id=None, content="hello", content_type="text",
             comment_type=None, thread_path="root", depth=0, reply_count=0,
             upvote_count=0, downvote_count=0, is_edited=False,
             is_resolved=False, resolved_at=None,
             created_at=datetime.now(timezone.utc), updated_at=None)
    d.update(kw)
    return _NS(**d)


def _vote(**kw):
    d = dict(id="v1", comment_id=None, supervision_session_id="s1",
             user_id="u1", vote_type="up", vote_reason=None)
    d.update(kw)
    return _NS(**d)


def _perf(**kw):
    d = dict(supervisor_id="sup1", confidence_score=0.5,
             competence_level="novice", total_ratings=0, average_rating=None,
             rating_1_count=0, rating_2_count=0, rating_3_count=0,
             rating_4_count=0, rating_5_count=0, total_comments_given=0,
             total_sessions_supervised=0, total_upvotes_received=0,
             total_downvotes_received=0, performance_trend=None,
             learning_rate=None, last_updated=None)
    d.update(kw)
    return _NS(**d)


class _Col:
    """Chainable fake column expression."""
    def __lt__(self, o): return self
    def __le__(self, o): return self
    def __gt__(self, o): return self
    def __ge__(self, o): return self
    def __eq__(self, o): return self
    def __ne__(self, o): return self
    def __and__(self, o): return self
    def __or__(self, o): return self
    def __invert__(self): return self
    def is_(self, o): return self
    def is_not(self, o): return self
    def in_(self, o): return self
    def like(self, o): return self
    def desc(self): return self
    def asc(self): return self


class _ModelMeta(type):
    def __getattr__(cls, name):
        return _Col()


class _NS(SimpleNamespace):
    """SimpleNamespace with dict-style update (usable as data row or defaults)."""
    def update(self, kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _model(name, defaults):
    """Build a fake ORM model class with the right __name__ and defaults."""
    class M(metaclass=_ModelMeta):
        def __init__(self, **kw):
            d = defaults()
            d.update(kw)
            self.__dict__.update(vars(d))
    M.__name__ = name
    return M


_SessionM = _model("SupervisionSession", _session)
_RatingM = _model("SupervisorRating", _rating)
_CommentM = _model("SupervisorComment", _comment)
_VoteM = _model("FeedbackVote", _vote)
_PerfM = _model("SupervisorPerformance", _perf)


@pytest.fixture(autouse=True)
def _fake_feedback_models():
    with patch.object(fbs, "SupervisionSession", _SessionM), \
         patch.object(fbs, "SupervisorRating", _RatingM), \
         patch.object(fbs, "SupervisorComment", _CommentM), \
         patch.object(fbs, "FeedbackVote", _VoteM), \
         patch.object(fbs, "SupervisorPerformance", _PerfM):
        yield


class TestFeedbackRatings:
    def _svc(self, db):
        return fbs.FeedbackService(db)

    async def test_rate_validation_branches(self):
        svc = self._svc(FakeDB())
        with pytest.raises(ValueError, match="between 1 and 5"):
            await svc.rate_supervisor("s1", "u1", 0, "quality")
        with pytest.raises(ValueError, match="between 1 and 5"):
            await svc.rate_supervisor("s1", "u1", 6, "quality")
        db = FakeDB(SupervisionSession=[Q(first=None)])
        with pytest.raises(ValueError, match="not found"):
            await self._svc(db).rate_supervisor("s1", "u1", 4, "quality")
        db2 = FakeDB(SupervisionSession=[Q(first=_session(status="active"))])
        with pytest.raises(ValueError, match="completed"):
            await self._svc(db2).rate_supervisor("s1", "u1", 4, "quality")

    async def test_rate_updates_existing(self):
        existing = _rating(rating=2)
        db = FakeDB(SupervisionSession=[Q(first=_session())],
                    SupervisorRating=[Q(first=existing)])
        got = await self._svc(db).rate_supervisor("s1", "u2", 4, "clarity",
                                                  reason="r", agent_id="a1")
        assert got is existing
        assert existing.rating == 4 and existing.was_helpful is True
        assert existing.updated_at is not None and db.commits == 1
        assert not db.added

    async def test_rate_creates_new_with_perf_update(self):
        perf = _perf()
        db = FakeDB(
            SupervisionSession=[Q(first=_session()), Q(count=7)],
            SupervisorRating=[
                Q(first=None),                       # no existing rating
                Q(all_=[_rating(rating=4)]),         # recalc: all ratings
                Q(all_=[_rating(rating=4)] * 12),    # trend: recent ratings
            ],
            SupervisorPerformance=[Q(first=perf)],
            SupervisorComment=[Q(count=3)],
            FeedbackVote=[Q(count=2), Q(count=1)],
        )
        got = await self._svc(db).rate_supervisor("s1", "u1", 4, "quality")
        assert got.rating == 4 and got.was_helpful is True
        assert db.added == [got]
        assert perf.total_ratings == 1 and perf.average_rating == 4.0
        assert perf.rating_4_count == 1
        assert perf.total_comments_given == 3
        assert perf.total_sessions_supervised == 7
        assert perf.total_upvotes_received == 2
        assert perf.total_downvotes_received == 1
        assert perf.competence_level == "novice"
        assert perf.performance_trend == "stable"
        assert perf.last_updated is not None

    async def test_rate_creates_perf_record_when_missing(self):
        db = FakeDB(
            SupervisionSession=[Q(first=_session()), Q(count=0)],
            SupervisorRating=[Q(first=None), Q(all_=[]), Q(all_=[])],
            SupervisorPerformance=[Q(first=None)],
            SupervisorComment=[Q(count=0)],
            FeedbackVote=[Q(count=0), Q(count=0)],
        )
        await self._svc(db).rate_supervisor("s1", "u1", 2, "quality")
        assert len(db.added) == 2  # rating + performance row

    async def test_get_supervisor_ratings(self):
        r = _rating(reason="why", was_helpful=False)
        db = FakeDB(SupervisorRating=[Q(all_=[r])])
        out = await self._svc(db).get_supervisor_ratings("sup1", limit=5)
        assert out[0]["id"] == "r1" and out[0]["category"] == "quality"
        assert out[0]["reason"] == "why" and out[0]["created_at"]
        r2 = _rating(created_at=None)
        db2 = FakeDB(SupervisorRating=[Q(all_=[r2])])
        assert (await self._svc(db2).get_supervisor_ratings("sup1"))[0][
            "created_at"] is None


class TestFeedbackComments:
    def _svc(self, db):
        return fbs.FeedbackService(db)

    async def test_add_comment_root_and_reply(self):
        parent = _comment(id="c0")
        db = FakeDB(SupervisionSession=[Q(first=_session())])
        c = await self._svc(db).add_comment("s1", "u1", "hi",
                                            comment_type="note")
        assert c.thread_path == "root" and c.depth == 0
        assert c.parent_comment_id is None

        db2 = FakeDB(SupervisionSession=[Q(first=_session())],
                     SupervisorComment=[Q(first=parent)])
        reply = await self._svc(db2).add_comment("s1", "u2", "re:",
                                                 parent_comment_id="c0")
        assert reply.thread_path == "root.c0" and reply.depth == 1
        assert parent.reply_count == 1

    async def test_add_comment_errors(self):
        db = FakeDB(SupervisionSession=[Q(first=None)])
        with pytest.raises(ValueError, match="not found"):
            await self._svc(db).add_comment("s1", "u1", "x")
        db2 = FakeDB(SupervisionSession=[Q(first=_session())],
                     SupervisorComment=[Q(first=None)])
        with pytest.raises(ValueError, match="Parent comment"):
            await self._svc(db2).add_comment("s1", "u1", "x",
                                             parent_comment_id="zz")

    async def test_get_comment_thread_hierarchy(self):
        root = _comment(id="c1", depth=0)
        child = _comment(id="c2", parent_comment_id="c1", depth=1,
                         thread_path="root.c1")
        orphan = _comment(id="c3", parent_comment_id="missing", depth=1)
        db = FakeDB(SupervisorComment=[Q(all_=[root, child, orphan])])
        out = await self._svc(db).get_comment_thread("s1")
        assert len(out) == 1
        assert out[0]["id"] == "c1"
        assert [r["id"] for r in out[0]["replies"]] == ["c2"]

    async def test_get_comment_thread_subtree(self):
        root = _comment(id="c1", depth=0, thread_path="root")
        other = _comment(id="c9", depth=0, thread_path="root")
        db = FakeDB(SupervisorComment=[
            Q(all_=[root, other]),               # initial thread query
            Q(first=root),                       # root lookup
        ])
        out = await self._svc(db).get_comment_thread("s1", root_comment_id="c1")
        assert [c["id"] for c in out] == ["c1", "c9"]
        # unknown root -> []
        db2 = FakeDB(SupervisorComment=[Q(all_=[]), Q(first=None)])
        assert await self._svc(db2).get_comment_thread("s1",
                                                       root_comment_id="zz") == []

    async def test_update_comment_paths(self):
        c = _comment()
        db = FakeDB(SupervisorComment=[Q(first=None)])
        with pytest.raises(ValueError, match="not found"):
            await self._svc(db).update_comment("zz", "u1", content="x")

        c2 = _comment(author_id="someone-else")
        db2 = FakeDB(SupervisorComment=[Q(first=c2)])
        with pytest.raises(ValueError, match="own comments"):
            await self._svc(db2).update_comment("c1", "u1", content="x")

        c3 = _comment()
        db3 = FakeDB(SupervisorComment=[Q(first=c3)])
        got = await self._svc(db3).update_comment("c1", "u1", content="edited")
        assert got.content == "edited" and got.is_edited is True
        assert got.updated_at is not None

        c4 = _comment()
        db4 = FakeDB(SupervisorComment=[Q(first=c4)])
        got2 = await self._svc(db4).update_comment("c1", "u1", is_resolved=True)
        assert got2.is_resolved and got2.resolved_at is not None
        got3 = await self._svc(db4).update_comment("c1", "u1", is_resolved=False)
        assert got3.is_resolved is False and got3.resolved_at is None


class TestFeedbackVotes:
    def _svc(self, db):
        return fbs.FeedbackService(db)

    async def test_vote_on_comment_validation_and_new(self):
        db = FakeDB()
        with pytest.raises(ValueError, match="up.*down"):
            await self._svc(db).vote_on_comment("c1", "u1", "sideways")

        comment = _comment(upvote_count=1)
        db2 = FakeDB(FeedbackVote=[Q(first=None)],
                     SupervisorComment=[Q(first=comment)])
        v = await self._svc(db2).vote_on_comment("c1", "u1", "up")
        assert v.comment_id == "c1" and v.supervision_session_id == "s1"
        assert comment.upvote_count == 2

        # comment missing entirely -> vote with null session, no count update
        db3 = FakeDB(FeedbackVote=[Q(first=None)],
                     SupervisorComment=[Q(first=None)])
        v2 = await self._svc(db3).vote_on_comment("zz", "u1", "down")
        assert v2.supervision_session_id is None

    async def test_vote_on_comment_toggle_off(self):
        comment = _comment(upvote_count=3, downvote_count=2)
        existing = _vote(comment_id="c1", vote_type="up")
        db = FakeDB(FeedbackVote=[Q(first=existing)],
                    SupervisorComment=[Q(first=comment)])
        assert await self._svc(db).vote_on_comment("c1", "u1", "up") is None
        assert db.deleted == [existing]
        assert comment.upvote_count == 2  # decremented, floor 0

        comment2 = _comment(downvote_count=0)
        existing2 = _vote(comment_id="c1", vote_type="down")
        db2 = FakeDB(FeedbackVote=[Q(first=existing2)],
                     SupervisorComment=[Q(first=comment2)])
        await self._svc(db2).vote_on_comment("c1", "u1", "down")
        assert comment2.downvote_count == 0  # max(0, -1)

    async def test_vote_on_comment_change_and_backfill(self):
        comment = _comment(upvote_count=1, downvote_count=1)
        existing = _vote(comment_id="c1", vote_type="up",
                         supervision_session_id=None)
        db = FakeDB(FeedbackVote=[Q(first=existing)],
                    SupervisorComment=[Q(first=comment)])
        got = await self._svc(db).vote_on_comment("c1", "u1", "down")
        assert got is existing
        assert existing.vote_type == "down"
        assert existing.supervision_session_id == "s1"  # backfilled
        assert comment.upvote_count == 0 and comment.downvote_count == 2

    async def test_vote_on_session_paths(self):
        svc = self._svc(FakeDB())
        with pytest.raises(ValueError, match="up.*down"):
            await svc.vote_on_session("s1", "u1", "meh")

        db = FakeDB(FeedbackVote=[Q(first=None)])
        v = await self._svc(db).vote_on_session("s1", "u1", "up", "reason")
        assert v.vote_reason == "reason" and v.comment_id is None

        existing = _vote(vote_type="up")
        db2 = FakeDB(FeedbackVote=[Q(first=existing)])
        assert await self._svc(db2).vote_on_session("s1", "u1", "up") is None
        assert db2.deleted == [existing]

        existing3 = _vote(vote_type="down")
        db3 = FakeDB(FeedbackVote=[Q(first=existing3)])
        got = await self._svc(db3).vote_on_session("s1", "u1", "up", "why")
        assert got is existing3 and existing3.vote_type == "up"
        assert existing3.vote_reason == "why"

    async def test_session_feedback_summary(self):
        db = FakeDB(
            FeedbackVote=[Q(count=4), Q(count=1)],
            SupervisorComment=[Q(count=3)],
            SupervisorRating=[Q(all_=[_rating(rating=4), _rating(rating=5)])],
        )
        out = await self._svc(db).get_session_feedback_summary("s1")
        assert out == {"upvotes": 4, "downvotes": 1, "net_score": 3,
                       "comment_count": 3, "average_rating": 4.5,
                       "rating_count": 2}
        db2 = FakeDB(FeedbackVote=[Q(count=0), Q(count=0)],
                     SupervisorComment=[Q(count=0)],
                     SupervisorRating=[Q(all_=[])])
        out2 = await self._svc(db2).get_session_feedback_summary("s1")
        assert out2["average_rating"] is None and out2["rating_count"] == 0


class TestFeedbackPerformanceInternals:
    def _svc(self, db):
        return fbs.FeedbackService(db)

    async def test_confidence_and_competence_levels(self):
        svc = self._svc(FakeDB())
        for conf, sessions, want in [
            (0.85, 60, "expert"), (0.65, 30, "advanced"),
            (0.45, 12, "intermediate"), (0.2, 0, "novice"),
            (0.9, 5, "novice"),
        ]:
            p = _perf(confidence_score=conf, total_sessions_supervised=sessions,
                      average_rating=4.5, total_ratings=10)
            await svc._update_confidence_and_competence(p)
            assert p.competence_level == want, (conf, sessions)
        # confidence clamped to [0.1, 0.95] and EMA-smoothed
        p = _perf(confidence_score=0.0, average_rating=5.0, total_ratings=100)
        await svc._update_confidence_and_competence(p)
        assert p.confidence_score == pytest.approx(0.095)  # EMA from 0.0 base

    async def test_performance_trend_branches(self):
        svc = self._svc(FakeDB())
        # too few ratings -> stable
        p = _perf()
        db = FakeDB(SupervisorRating=[Q(all_=[_rating(rating=3)] * 5)])
        await svc._update_performance_trend(p)
        assert p.performance_trend == "stable" and p.learning_rate == 0.0

        def trend_db(ratings):
            return FakeDB(SupervisorRating=[Q(all_=ratings)])

        # improving: recent ratings (front of list) much higher
        improving = [_rating(rating=5)] * 6 + [_rating(rating=1)] * 6
        p3 = _perf()
        svc3 = self._svc(trend_db(improving))
        await svc3._update_performance_trend(p3)
        assert p3.performance_trend == "improving"
        assert 0 < p3.learning_rate <= 0.1

        declining = [_rating(rating=1)] * 6 + [_rating(rating=5)] * 6
        p4 = _perf()
        svc4 = self._svc(trend_db(declining))
        await svc4._update_performance_trend(p4)
        assert p4.performance_trend == "declining"
        assert -0.1 <= p4.learning_rate < 0

        stable = [_rating(rating=3)] * 12
        p5 = _perf()
        svc5 = self._svc(trend_db(stable))
        await svc5._update_performance_trend(p5)
        assert p5.performance_trend == "stable" and p5.learning_rate == 0.0

    async def test_recalculate_without_ratings(self):
        p = _perf()
        db = FakeDB(SupervisorRating=[Q(all_=[]), Q(all_=[])],
                    SupervisorComment=[Q(count=0)],
                    SupervisionSession=[Q(count=0)],
                    FeedbackVote=[Q(count=0), Q(count=0)])
        await self._svc(db)._recalculate_performance(p)
        assert p.total_ratings == 0 and p.average_rating is None
        assert p.confidence_score is not None

    async def test_serialize_comment_none_dates(self):
        svc = self._svc(FakeDB())
        c = _comment(resolved_at=None, created_at=None, updated_at=None)
        d = svc._serialize_comment(c)
        assert d["resolved_at"] is None and d["created_at"] is None
        assert d["updated_at"] is None and d["depth"] == 0
        c2 = _comment()
        d2 = svc._serialize_comment(c2)
        assert d2["created_at"] and d2["reply_count"] == 0

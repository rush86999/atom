"""Coverage wave 38 — core/episode_retrieval_service remaining branches (29% → 85%+).

- _log_access (success + exception)
- _serialize_segment, _fetch_canvas_context (empty, found, exception),
  _fetch_feedback_context (empty, found, exception)
- _filter_canvas_context_detail (full/standard/summary)
- _create_supervision_context, _summarize_feedback (none/short/long),
  _assess_outcome_quality (unknown/excellent/good/fair/poor)
- _filter_improvement_trend (<5, no-ratings, improving, declining)
- retrieve_sequential not-found
- retrieve_contextual filtered result shape
"""
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.episode_retrieval_service import EpisodeRetrievalService, RetrievalMode
from core.models import AgentEpisode as Episode


@pytest.fixture
def fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


@pytest.fixture
def svc(fresh_db):
    s = EpisodeRetrievalService(fresh_db)
    s.governance = MagicMock()
    s.governance.can_perform_action = MagicMock(return_value={"allowed": True})
    return s


def _episode(db, **kw):
    defaults = dict(
        id=f"ep-{uuid.uuid4().hex[:8]}",
        agent_id="agent-1", tenant_id="t1", workspace_id="ws1",
        task_description="Task", maturity_at_time="SUPERVISED",
        constitutional_score=1.0, outcome="success", status="completed",
        importance_score=0.5, access_count=0, decay_score=0.0,
        started_at=datetime.now(timezone.utc) - timedelta(days=1),
        completed_at=datetime.now(timezone.utc),
    )
    defaults.update(kw)
    ep = Episode(**defaults)
    db.add(ep)
    db.commit()
    return ep


class TestLogAccess:
    async def test_logs_and_commits(self, svc, fresh_db):
        await svc._log_access("ep-1", "temporal", {"allowed": True}, "a1", 3)
        from core.models import EpisodeAccessLog
        rows = fresh_db.query(EpisodeAccessLog).all()
        assert len(rows) == 1
        assert rows[0].results_count == 3

    async def test_exception_swallowed(self, svc):
        db = MagicMock()
        db.add = Mock(side_effect=RuntimeError("boom"))
        svc.db = db
        await svc._log_access("ep-1", "temporal", {"allowed": True}, "a1", 3)
        # no raise


class TestSerialization:
    def test_serialize_segment(self):
        seg = SimpleNamespace(
            id="s1", segment_type="action", sequence_order=1, content="c",
            content_summary="cs", source_type="execution", source_id="x",
            created_at=datetime.now(timezone.utc),
        )
        svc = EpisodeRetrievalService(MagicMock())
        out = svc._serialize_segment(seg)
        assert out["id"] == "s1"
        assert out["segment_type"] == "action"
        assert out["created_at"] is not None

    async def test_fetch_canvas_context_empty(self, svc):
        assert await svc._fetch_canvas_context([]) == []

    async def test_fetch_canvas_context_found(self, svc, fresh_db):
        from core.models import CanvasAudit
        fresh_db.add(CanvasAudit(
            id="ca-1", canvas_id="cv-1", tenant_id="t1", action_type="present",
            details_json={"canvas_type": "docs", "component_type": "markdown"},
        ))
        fresh_db.commit()
        ctx = await svc._fetch_canvas_context(["ca-1"])
        assert len(ctx) == 1
        assert ctx[0]["canvas_type"] == "docs"
        assert ctx[0]["action"] == "present"

    async def test_fetch_canvas_context_exception(self, svc):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        svc.db = db
        assert await svc._fetch_canvas_context(["ca-1"]) == []

    async def test_fetch_feedback_empty(self, svc):
        assert await svc._fetch_feedback_context([]) == []

    async def test_fetch_feedback_found(self, svc, fresh_db):
        from core.models import AgentFeedback
        fresh_db.add(AgentFeedback(
            id="fb-1", agent_id="a1", user_id="u1",
            original_output="o", user_correction="corrected",
            feedback_type="correction", rating=4,
        ))
        fresh_db.commit()
        ctx = await svc._fetch_feedback_context(["fb-1"])
        assert len(ctx) == 1
        assert ctx[0]["corrections"] == "corrected"

    async def test_fetch_feedback_exception(self, svc):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        svc.db = db
        assert await svc._fetch_feedback_context(["fb-1"]) == []


class TestCanvasDetailFilter:
    def test_full_returns_everything(self):
        ctx = {"canvas_type": "docs", "presentation_summary": "s", "critical_data_points": {"a": 1}}
        svc = EpisodeRetrievalService(MagicMock())
        assert svc._filter_canvas_context_detail(ctx, "full") == ctx

    def test_standard(self):
        ctx = {"canvas_type": "docs", "presentation_summary": "s", "critical_data_points": {"a": 1}}
        svc = EpisodeRetrievalService(MagicMock())
        out = svc._filter_canvas_context_detail(ctx, "standard")
        assert "critical_data_points" in out
        assert "presentation_summary" in out

    def test_summary(self):
        ctx = {"canvas_type": "docs", "presentation_summary": "s", "critical_data_points": {"a": 1}}
        svc = EpisodeRetrievalService(MagicMock())
        out = svc._filter_canvas_context_detail(ctx, "summary")
        assert out == {"presentation_summary": "s"}


class TestSupervisionContext:
    def test_create_context(self, svc, fresh_db):
        ep = _episode(fresh_db, supervisor_id="sup-1", supervisor_rating=5,
                      human_intervention_count=1,
                      intervention_types=["pause"],
                      supervision_feedback="Great work")
        ctx = svc._create_supervision_context(ep)
        assert ctx["has_supervision"] is True
        assert ctx["intervention_count"] == 1
        assert ctx["outcome_quality"] == "excellent"

    def test_summarize_feedback(self, svc):
        assert svc._summarize_feedback(None) is None
        assert svc._summarize_feedback("short") == "short"
        long_fb = "x" * 150
        out = svc._summarize_feedback(long_fb)
        assert len(out) == 100
        assert out.endswith("...")

    def test_assess_outcome_quality(self, svc, fresh_db):
        cases = [
            (None, "unknown"),
            (5, "excellent"),
            (4, "good"),
            (3, "fair"),
            (2, "poor"),
        ]
        for rating, expected in cases:
            ep = _episode(fresh_db, supervisor_rating=rating,
                          human_intervention_count=0)
            assert svc._assess_outcome_quality(ep) == expected

    def test_assess_excellent_requires_low_interventions(self, svc, fresh_db):
        # rating 5 but 5 interventions → skips excellent AND good (needs <=2)
        ep = _episode(fresh_db, supervisor_rating=5, human_intervention_count=5)
        assert svc._assess_outcome_quality(ep) == "fair"


class TestImprovementTrend:
    def _ep(self, started_days_ago, rating, db):
        return _episode(db, supervisor_rating=rating,
                        started_at=datetime.now(timezone.utc) - timedelta(days=started_days_ago))

    def test_less_than_five(self, svc, fresh_db):
        eps = [self._ep(i, 4, fresh_db) for i in range(3)]
        out = svc._filter_improvement_trend(eps)
        assert len(out) == 3

    def test_no_ratings(self, svc, fresh_db):
        eps = [self._ep(i, None, fresh_db) for i in range(6)]
        out = svc._filter_improvement_trend(eps)
        assert len(out) == 6

    def test_improving_keeps(self, svc, fresh_db):
        # older episodes (earlier) rated lower, recent higher → keep
        eps = [self._ep(i, 5 if i < 3 else 2, fresh_db) for i in range(6)]
        out = svc._filter_improvement_trend(eps)
        assert len(out) == 6

    def test_declining_empty(self, svc, fresh_db):
        # recent rated lower than earlier → empty
        eps = [self._ep(i, 2 if i < 3 else 5, fresh_db) for i in range(6)]
        out = svc._filter_improvement_trend(eps)
        assert out == []


class TestSequentialMissing:
    async def test_retrieve_sequential_not_found(self, svc):
        result = await svc.retrieve_sequential("missing", "agent-1")
        assert result == {"error": "Episode not found"}


class TestSupervisionRetrieval:
    async def test_governance_blocked(self, svc):
        svc.governance.can_perform_action.return_value = {"allowed": False, "reason": "no"}
        result = await svc.retrieve_with_supervision_context("agent-1")
        assert result["episodes"] == []

    async def test_sequential_default_with_filters(self, svc, fresh_db):
        _episode(fresh_db, supervisor_rating=5, human_intervention_count=0)
        _episode(fresh_db, supervisor_rating=2, human_intervention_count=5)
        svc.retrieve_temporal = AsyncMock(return_value={
            "episodes": [{"id": e.id} for e in fresh_db.query(Episode).all()]
        })
        result = await svc.retrieve_with_supervision_context(
            "agent-1", min_rating=4, max_interventions=2,
        )
        assert result["count"] == 1
        assert "min_rating_4" in result["supervision_filters_applied"]
        assert result["episodes"][0]["supervision_context"]["outcome_quality"] == "excellent"

    async def test_high_rated_filter(self, svc, fresh_db):
        _episode(fresh_db, supervisor_rating=5)
        _episode(fresh_db, supervisor_rating=3)
        svc.retrieve_temporal = AsyncMock(return_value={
            "episodes": [{"id": e.id} for e in fresh_db.query(Episode).all()]
        })
        result = await svc.retrieve_with_supervision_context(
            "agent-1", supervision_outcome_filter="high_rated"
        )
        assert result["count"] == 1

    async def test_low_intervention_filter(self, svc, fresh_db):
        _episode(fresh_db, supervisor_rating=4, human_intervention_count=0)
        _episode(fresh_db, supervisor_rating=4, human_intervention_count=3)
        svc.retrieve_temporal = AsyncMock(return_value={
            "episodes": [{"id": e.id} for e in fresh_db.query(Episode).all()]
        })
        result = await svc.retrieve_with_supervision_context(
            "agent-1", supervision_outcome_filter="low_intervention"
        )
        assert result["count"] == 1

    async def test_recent_improvement_filter(self, svc, fresh_db):
        # most recent (i small) rated HIGH, older rated low → improving
        for i in range(6):
            _episode(fresh_db, supervisor_rating=5 if i < 3 else 2,
                     started_at=datetime.now(timezone.utc) - timedelta(days=i))
        svc.retrieve_temporal = AsyncMock(return_value={
            "episodes": [{"id": e.id} for e in fresh_db.query(Episode).all()]
        })
        result = await svc.retrieve_with_supervision_context(
            "agent-1", supervision_outcome_filter="recent_improvement"
        )
        assert result["count"] == 6

    async def test_string_mode_coerced(self, svc, fresh_db):
        _episode(fresh_db, supervisor_rating=5)
        svc.retrieve_temporal = AsyncMock(return_value={
            "episodes": [{"id": e.id} for e in fresh_db.query(Episode).all()]
        })
        result = await svc.retrieve_with_supervision_context(
            "agent-1", retrieval_mode="temporal"
        )
        assert result["retrieval_mode"] == "temporal"

    async def test_invalid_string_mode_falls_back(self, svc, fresh_db):
        _episode(fresh_db, supervisor_rating=5)
        svc.retrieve_temporal = AsyncMock(return_value={
            "episodes": [{"id": e.id} for e in fresh_db.query(Episode).all()]
        })
        result = await svc.retrieve_with_supervision_context(
            "agent-1", retrieval_mode="bogus"
        )
        assert result["retrieval_mode"] == "sequential"

    async def test_semantic_mode_uses_agent_name(self, svc, fresh_db):
        from core.models import AgentRegistry
        fresh_db.add(AgentRegistry(
            id="agent-1", name="Helper", category="g", description="d",
            status="SUPERVISED", confidence_score=0.7,
            module_path="m", class_name="C", workspace_id="default",
        ))
        fresh_db.commit()
        _episode(fresh_db, supervisor_rating=4)
        svc.retrieve_semantic = AsyncMock(return_value={
            "episodes": [{"id": e.id} for e in fresh_db.query(Episode).all()]
        })
        result = await svc.retrieve_with_supervision_context(
            "agent-1", retrieval_mode=RetrievalMode.SEMANTIC
        )
        assert result["retrieval_mode"] == "semantic"
        assert svc.retrieve_semantic.await_args.kwargs["query"] == "Helper"
